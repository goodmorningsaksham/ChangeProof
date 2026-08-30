"""Unit tests for multi-signal candidate hypothesis generation and telemetry evaluation."""
from unittest.mock import patch
from changeproof.hypothesis_evaluator import generate_candidate_hypotheses, evaluate_hypotheses_evidence
from changeproof.certificate import CertificateGenerator


# ---------------------------------------------------------------------------
# Existing tests — must pass unchanged (no diff/code context supplied)
# ---------------------------------------------------------------------------

def test_generate_candidate_hypotheses_multi_signals():
    signals = [
        "Aggressive retry count increase (max_retries >= 4)",
        "Removal of backoff / immediate retry execution",
        "Aggressive timeout reduction (timeout < 1.0s)",
    ]
    hypos = generate_candidate_hypotheses(signals, proxy_name="payment-proxy", calibrated_latency_ms=1500)
    assert len(hypos) == 3
    ids = [h["id"] for h in hypos]
    assert "H-RETRY-CEILING" in ids
    assert "H-NO-BACKOFF" in ids
    assert "H-AGGRESSIVE-TIMEOUT" in ids


def test_evaluate_multi_signals_confounded_labeling():
    """Multi-signal co-occurrence must label as CONSISTENT WITH OBSERVED STORM."""
    signals = [
        "Aggressive retry count increase (max_retries >= 4)",
        "Removal of backoff / immediate retry execution",
        "Aggressive timeout reduction (timeout < 1.0s)",
    ]
    hypos = generate_candidate_hypotheses(signals, proxy_name="payment-proxy", calibrated_latency_ms=1500)

    pre_summary = {
        "retries_per_request": 7.0,
        "rate_per_min": 1530.12,
        "total_requests": 150,
        "throughput_req_per_sec": 3.64,
    }
    post_summary = {
        "retries_per_request": 1.0,
        "rate_per_min": 350.2,
        "total_requests": 150,
    }

    evaluated = evaluate_hypotheses_evidence(
        hypos,
        pre_summary=pre_summary,
        post_summary=post_summary,
        calibrated_latency_ms=1500,
        client_timeout_s=0.5,
    )

    assert len(evaluated) == 3
    for h in evaluated:
        assert h["supported"] is True
        assert h["is_confounded"] is True
        assert h["status_label"] == "[CONSISTENT WITH OBSERVED STORM]"


def test_evaluate_single_signal_isolated_labeling():
    """Single signal must label as SUPPORTED (ISOLATED) without confounding."""
    signals = ["Aggressive retry count increase (max_retries >= 4)"]
    hypos = generate_candidate_hypotheses(signals, proxy_name="payment-proxy", calibrated_latency_ms=1500)
    assert len(hypos) == 1

    pre_summary = {
        "retries_per_request": 3.0,
        "rate_per_min": 534.0,
        "total_requests": 150,
        "throughput_req_per_sec": 2.98,
    }
    post_summary = {
        "retries_per_request": 1.0,
        "rate_per_min": 350.0,
        "total_requests": 150,
    }

    evaluated = evaluate_hypotheses_evidence(
        hypos,
        pre_summary=pre_summary,
        post_summary=post_summary,
        calibrated_latency_ms=1600,
        client_timeout_s=0.8,
    )

    assert len(evaluated) == 1
    assert evaluated[0]["supported"] is True
    assert evaluated[0]["is_confounded"] is False
    assert evaluated[0]["status_label"] == "[SUPPORTED (ISOLATED)]"


def test_certificate_renders_joint_attribution_note_when_multi_signal():
    signals = [
        "Aggressive retry count increase (max_retries >= 4)",
        "Removal of backoff / immediate retry execution",
    ]
    hypos = generate_candidate_hypotheses(signals)
    evaluated = evaluate_hypotheses_evidence(
        hypos,
        pre_summary={"retries_per_request": 7.0, "total_requests": 150, "rate_per_min": 1500.0},
        post_summary={"retries_per_request": 1.0, "total_requests": 150, "rate_per_min": 350.0},
    )

    cert_gen = CertificateGenerator()
    rendered = cert_gen.render({
        "timestamp": "2026-08-29T11:00:00Z",
        "experiment_id": "test-multi-exp",
        "git_commit": "abc1234",
        "risk_level": "HIGH",
        "risk_score": 70,
        "hypothesis_title": "Primary Title",
        "hypothesis_confidence": "HIGH",
        "candidate_hypotheses": evaluated,
        "verification_status": "PASS",
        "diff_table": [],
        "capsule_path": "capsules/test.zip",
    })

    assert "Note on Joint Attribution" in rendered
    assert "CONSISTENT WITH OBSERVED STORM" in rendered


def test_certificate_omits_joint_attribution_note_when_single_signal():
    signals = ["Aggressive retry count increase (max_retries >= 4)"]
    hypos = generate_candidate_hypotheses(signals)
    evaluated = evaluate_hypotheses_evidence(
        hypos,
        pre_summary={"retries_per_request": 3.0, "total_requests": 150, "rate_per_min": 500.0},
        post_summary={"retries_per_request": 1.0, "total_requests": 150, "rate_per_min": 350.0},
    )

    cert_gen = CertificateGenerator()
    rendered = cert_gen.render({
        "timestamp": "2026-08-29T11:00:00Z",
        "experiment_id": "test-single-exp",
        "git_commit": "abc1234",
        "risk_level": "HIGH",
        "risk_score": 50,
        "hypothesis_title": "Primary Title",
        "hypothesis_confidence": "HIGH",
        "candidate_hypotheses": evaluated,
        "verification_status": "PASS",
        "diff_table": [],
        "capsule_path": "capsules/test.zip",
    })

    assert "Note on Joint Attribution" not in rendered
    assert "SUPPORTED (ISOLATED)" in rendered


# ---------------------------------------------------------------------------
# NEW tests — LLM-path with mocked call_llm
# ---------------------------------------------------------------------------

CHECKOUT_DIFF = """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
"""
CHECKOUT_CODE = 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))\nRETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))\n'

INVENTORY_DIFF = """--- a/app/inventory/main.py
+++ b/app/inventory/main.py
@@ -5,2 +5,2 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))
"""
INVENTORY_CODE = 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))\n'

EXPRESS_DIFF = """--- a/app/order/server.js
+++ b/app/order/server.js
@@ -3,2 +3,2 @@
-const RETRIES_MAX = 2;
+const RETRIES_MAX = 8;
-const RETRY_BACKOFF_MS = 500;
+const RETRY_BACKOFF_MS = 0;
"""
EXPRESS_CODE = "const RETRIES_MAX = 8;\nconst RETRY_BACKOFF_MS = 0;\n"


def _make_llm_response(title: str, description: str, code_evidence: str, mechanism: str) -> str:
    import json
    return json.dumps({
        "title": title,
        "description": description,
        "code_evidence": code_evidence,
        "mechanism": mechanism,
    })


def test_llm_path_produces_checkout_specific_text():
    """When diff_text is supplied, description must reference checkout-specific names."""
    signals = [
        "Aggressive retry count increase (max_retries >= 4)",
        "Removal of backoff / immediate retry execution",
    ]
    checkout_llm_responses = [
        _make_llm_response(
            "checkout-service retry ceiling raised from 3 to 8 amplifies payment-proxy storm",
            "The checkout service raised RETRIES_MAX from 3 to 8 via os.getenv default, "
            "allowing each stalled request to the payment-proxy to fire 8 consecutive retries. "
            "Combined with RETRY_BACKOFF_FACTOR=0.0, retries execute with no spacing.",
            "+RETRIES_MAX = int(os.getenv(\"RETRIES_MAX\", \"8\")) raises ceiling to 8.",
            "Each timed-out checkout→payment request retries 8 times instantly, "
            "multiplying downstream load by 8x.",
        ),
        _make_llm_response(
            "Backoff removed in checkout-service concentrates retry bursts on payment-proxy",
            "RETRY_BACKOFF_FACTOR set to 0.0 in checkout/main.py eliminates delay between retries.",
            "+RETRY_BACKOFF_FACTOR = float(os.getenv(\"RETRY_BACKOFF_FACTOR\", \"0.0\"))",
            "Zero backoff collapses retry intervals to zero, depriving payment-proxy of recovery time.",
        ),
    ]

    call_count = [0]
    def mock_call_llm(prompt, max_tokens=512):
        resp = checkout_llm_responses[call_count[0]]
        call_count[0] += 1
        return resp

    with patch("changeproof.hypothesis_evaluator.call_llm", side_effect=mock_call_llm):
        hypos = generate_candidate_hypotheses(
            signals,
            proxy_name="payment-proxy",
            calibrated_latency_ms=1500,
            diff_text=CHECKOUT_DIFF,
            code_context=CHECKOUT_CODE,
        )

    assert len(hypos) == 2
    retry_h = next(h for h in hypos if h["id"] == "H-RETRY-CEILING")
    backoff_h = next(h for h in hypos if h["id"] == "H-NO-BACKOFF")

    # Must reference checkout-specific names
    assert "checkout" in retry_h["description"].lower() or "8" in retry_h["description"]
    assert "payment-proxy" in retry_h["title"].lower() or "RETRIES_MAX" in retry_h["description"]
    assert "backoff" in backoff_h["description"].lower() or "0.0" in backoff_h["description"]

    # Structural fields must remain deterministic
    assert retry_h["id"] == "H-RETRY-CEILING"
    assert backoff_h["id"] == "H-NO-BACKOFF"
    assert retry_h["grounding"]["proxy"] == "payment-proxy"
    assert retry_h["grounding"]["calibrated_latency_ms"] == 1500


def test_llm_path_produces_inventory_specific_text():
    """Inventory/warehouse topology must produce inventory-specific description text."""
    signals = ["Aggressive retry count increase (max_retries >= 4)"]
    inventory_response = _make_llm_response(
        "inventory-service RETRIES_MAX raised from 3 to 6 amplifies warehouse-proxy load",
        "The inventory service increased RETRIES_MAX from 3 to 6 in app/inventory/main.py. "
        "Under warehouse-proxy latency, each inventory request fires up to 6 retries, "
        "doubling the expected downstream call volume.",
        "+RETRIES_MAX = int(os.getenv(\"RETRIES_MAX\", \"6\")) in app/inventory/main.py",
        "inventory→warehouse retry fan-out increases from 3x to 6x per stalled request.",
    )

    with patch("changeproof.hypothesis_evaluator.call_llm", return_value=inventory_response):
        hypos = generate_candidate_hypotheses(
            signals,
            proxy_name="warehouse-proxy",
            calibrated_latency_ms=2000,
            diff_text=INVENTORY_DIFF,
            code_context=INVENTORY_CODE,
        )

    assert len(hypos) == 1
    h = hypos[0]
    assert h["id"] == "H-RETRY-CEILING"
    assert "inventory" in h["description"].lower() or "6" in h["description"]
    assert h["grounding"]["proxy"] == "warehouse-proxy"
    assert h["grounding"]["calibrated_latency_ms"] == 2000


def test_llm_path_produces_express_specific_text():
    """Express/JS topology must produce JS-specific description text."""
    signals = [
        "Aggressive retry count increase (max_retries >= 4)",
        "Removal of backoff / immediate retry execution",
    ]
    responses = [
        _make_llm_response(
            "Express order-service const RETRIES_MAX raised from 2 to 8 triggers retry storm",
            "In app/order/server.js, const RETRIES_MAX was changed from 2 to 8. "
            "The Node.js order-service will now fire 8 retries per timed-out request "
            "to the order-proxy, amplifying downstream load by 4x compared to before.",
            "+const RETRIES_MAX = 8; in server.js raises ceiling from 2 to 8.",
            "JS retry loop executes 8 attempts per failure, up from 2.",
        ),
        _make_llm_response(
            "RETRY_BACKOFF_MS zeroed in server.js collapses retry spacing for order-proxy",
            "Setting const RETRY_BACKOFF_MS = 0 in app/order/server.js removes all delay "
            "between retry attempts, allowing Node's retry loop to fire all 8 retries "
            "in rapid succession against the order-proxy.",
            "+const RETRY_BACKOFF_MS = 0; removes all inter-retry delay.",
            "Zero backoff in JS setTimeout allows retries to stack instantly.",
        ),
    ]
    call_count = [0]
    def mock_call(prompt, max_tokens=512):
        resp = responses[call_count[0]]
        call_count[0] += 1
        return resp

    with patch("changeproof.hypothesis_evaluator.call_llm", side_effect=mock_call):
        hypos = generate_candidate_hypotheses(
            signals,
            proxy_name="order-proxy",
            calibrated_latency_ms=1600,
            diff_text=EXPRESS_DIFF,
            code_context=EXPRESS_CODE,
        )

    assert len(hypos) == 2
    retry_h = next(h for h in hypos if h["id"] == "H-RETRY-CEILING")
    backoff_h = next(h for h in hypos if h["id"] == "H-NO-BACKOFF")
    # Must reference JS/Express-specific context
    assert "server.js" in retry_h["description"].lower() or "order" in retry_h["description"].lower() or "8" in retry_h["description"]
    assert "0" in backoff_h["description"] or "backoff" in backoff_h["description"].lower()
    assert retry_h["grounding"]["proxy"] == "order-proxy"


def test_llm_fallback_to_template_on_bad_response():
    """If LLM returns garbage, falls back gracefully to static template text."""
    signals = ["Aggressive retry count increase (max_retries >= 4)"]

    with patch("changeproof.hypothesis_evaluator.call_llm", return_value="not valid json {{{{"):
        hypos = generate_candidate_hypotheses(
            signals,
            proxy_name="payment-proxy",
            calibrated_latency_ms=1500,
            diff_text=CHECKOUT_DIFF,
            code_context=CHECKOUT_CODE,
        )

    assert len(hypos) == 1
    h = hypos[0]
    assert h["id"] == "H-RETRY-CEILING"
    # Falls back to static template
    assert "RETRIES_MAX" in h["description"] or "retry ceiling" in h["description"].lower()


def test_llm_fallback_to_template_on_none_response():
    """If LLM returns None (no API key), falls back to static template."""
    signals = ["Aggressive retry count increase (max_retries >= 4)"]

    with patch("changeproof.hypothesis_evaluator.call_llm", return_value=None):
        hypos = generate_candidate_hypotheses(
            signals,
            proxy_name="payment-proxy",
            calibrated_latency_ms=1500,
            diff_text=CHECKOUT_DIFF,
            code_context=CHECKOUT_CODE,
        )

    assert len(hypos) == 1
    assert hypos[0]["id"] == "H-RETRY-CEILING"
    # Structural fields preserved
    assert hypos[0]["grounding"]["proxy"] == "payment-proxy"


def test_no_context_does_not_call_llm():
    """When diff_text and code_context are both empty, LLM is never called."""
    signals = ["Aggressive retry count increase (max_retries >= 4)"]

    with patch("changeproof.hypothesis_evaluator.call_llm") as mock_llm:
        hypos = generate_candidate_hypotheses(signals, proxy_name="payment-proxy", calibrated_latency_ms=1500)
        mock_llm.assert_not_called()

    assert len(hypos) == 1
    assert hypos[0]["id"] == "H-RETRY-CEILING"


def test_three_topologies_produce_different_descriptions():
    """Proof: same signal type across 3 diffs must yield distinct description text
    when LLM returns topology-grounded responses."""
    signals = ["Aggressive retry count increase (max_retries >= 4)"]

    checkout_resp = _make_llm_response(
        "checkout-service RETRIES_MAX=8 storms payment-proxy",
        "checkout-service RETRIES_MAX raised to 8 in app/checkout/main.py causes payment-proxy storm.",
        "+RETRIES_MAX=8 in checkout", "checkout→payment retry x8",
    )
    inventory_resp = _make_llm_response(
        "inventory-service RETRIES_MAX=6 storms warehouse-proxy",
        "inventory-service RETRIES_MAX raised to 6 in app/inventory/main.py causes warehouse-proxy storm.",
        "+RETRIES_MAX=6 in inventory", "inventory→warehouse retry x6",
    )
    express_resp = _make_llm_response(
        "order-service const RETRIES_MAX=8 storms order-proxy",
        "order-service const RETRIES_MAX raised to 8 in server.js causes order-proxy storm.",
        "+const RETRIES_MAX=8 in server.js", "order→order-proxy retry x8",
    )

    descriptions = []
    for diff, code, proxy, lat, llm_resp in [
        (CHECKOUT_DIFF, CHECKOUT_CODE, "payment-proxy", 1500, checkout_resp),
        (INVENTORY_DIFF, INVENTORY_CODE, "warehouse-proxy", 2000, inventory_resp),
        (EXPRESS_DIFF, EXPRESS_CODE, "order-proxy", 1600, express_resp),
    ]:
        with patch("changeproof.hypothesis_evaluator.call_llm", return_value=llm_resp):
            hypos = generate_candidate_hypotheses(
                signals, proxy_name=proxy, calibrated_latency_ms=lat,
                diff_text=diff, code_context=code,
            )
        descriptions.append(hypos[0]["description"])

    # All three descriptions must be distinct
    assert descriptions[0] != descriptions[1], "checkout and inventory descriptions are identical!"
    assert descriptions[1] != descriptions[2], "inventory and express descriptions are identical!"
    assert descriptions[0] != descriptions[2], "checkout and express descriptions are identical!"

    # Each must reference its own topology
    assert "checkout" in descriptions[0].lower()
    assert "inventory" in descriptions[1].lower()
    assert "server.js" in descriptions[2].lower() or "order" in descriptions[2].lower()
