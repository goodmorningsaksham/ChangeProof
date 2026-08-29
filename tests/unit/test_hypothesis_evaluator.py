"""Unit tests for multi-signal candidate hypothesis generation and telemetry evaluation."""
from changeproof.hypothesis_evaluator import generate_candidate_hypotheses, evaluate_hypotheses_evidence
from changeproof.certificate import CertificateGenerator


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