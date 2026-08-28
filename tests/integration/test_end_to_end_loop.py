"""Integration test for full end-to-end ChangeProof loop on CASE-01."""
import os
import yaml
from changeproof.risk_assessor import RiskAssessor
from changeproof.context_builder import ContextBuilder
from changeproof.verifier import verify
from changeproof.capsule import CapsulePackager
from changeproof.certificate import CertificateGenerator
from changeproof.policy_store import record_policy, load_policies

def test_full_case01_pipeline_loop(tmp_path):
    # 1. Ingest PR Diff (CASE-01: retry count increase 3 -> 8)
    pr_diff = """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,2 +10,2 @@
-RETRIES_MAX = 3
-RETRY_BACKOFF_FACTOR = 0.5
+RETRIES_MAX = 8
+RETRY_BACKOFF_FACTOR = 0.0
"""
    # 2. Risk Assessment
    assessor = RiskAssessor()
    risk_result = assessor.assess_diff(pr_diff)
    assert risk_result["level"] == "HIGH"
    assert risk_result["score"] >= 50
    assert risk_result["requires_experiment"] is True

    # 3. Context Building
    builder = ContextBuilder(compose_path="docker-compose.yml")
    context = builder.build_context(pr_diff, prometheus_url=None)
    assert "checkout-service" in context["topology"]["services"]

    # 4. Load CASE-01 Experiment Specification
    case_path = "evaluation/cases/case_01.yaml"
    with open(case_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # 5. Simulate Experiment Pre and Post CSV generation
    run_dir = tmp_path / "run_case01"
    run_dir.mkdir(parents=True, exist_ok=True)

    pre_csv = run_dir / "metrics_pre.csv"
    post_csv = run_dir / "metrics_post.csv"
    spec_copy = run_dir / "experiment.yaml"

    with open(spec_copy, "w", encoding="utf-8") as f:
        yaml.dump(spec, f)

    import pandas as pd
    # Pre-patch failure reproduction (amplification: 220 retries/min)
    pd.DataFrame([
        {"timestamp": 1.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 0.0},
        {"timestamp": 45.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 220.0},
    ]).to_csv(pre_csv, index=False)

    # Post-patch remediated state (bounded: 25 retries/min)
    pd.DataFrame([
        {"timestamp": 1.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 0.0},
        {"timestamp": 45.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 25.0},
    ]).to_csv(post_csv, index=False)

    # 6. Deterministic Verification
    ver_res = verify(str(pre_csv), str(post_csv), spec["assertions"])
    assert ver_res.status == "PASS"

    # 7. Proof Certificate Generation
    cert_gen = CertificateGenerator()
    cert_path = run_dir / "proof_certificate.md"
    cert_gen.generate_and_save({
        "timestamp": "2026-08-29T12:00:00Z",
        "experiment_id": "case-01",
        "git_commit": "abc1234",
        "risk_level": risk_result["level"],
        "risk_score": risk_result["score"],
        "hypothesis_title": "Retry Amplification Storm",
        "hypothesis_confidence": "HIGH",
        "verification_status": ver_res.status,
        "diff_table": ver_res.diff_table,
        "capsule_path": "capsules/case-01.zip",
    }, str(cert_path))
    assert cert_path.exists()
    assert "PASS" in cert_path.read_text(encoding="utf-8")

    # 8. Reproduction Capsule Packaging
    packager = CapsulePackager(capsules_dir=str(tmp_path / "capsules"))
    patch_file = run_dir / "patch.diff"
    patch_file.write_text("patch content", encoding="utf-8")

    capsule_zip = packager.create_capsule(
        experiment_id="case-01",
        run_dir=str(run_dir),
        git_commit_base="main",
        patch_diff_path=str(patch_file),
    )
    assert os.path.exists(capsule_zip)

    # 9. Human Policy Learning Record
    policy_store_path = str(tmp_path / "policy_store.json")
    policy_record = {
        "policy_id": "POL-CASE-01",
        "created_at": "2026-08-29T12:05:00Z",
        "author": "reviewer",
        "trigger": {"service": "checkout", "metric": "retry_count_total", "condition": "rate_per_min > 100"},
        "rule": "max_retries <= 3 for payment service calls",
        "decision": "APPROVED_WITH_PATCH",
        "rationale": "Enforce bounded retries under downstream latency",
        "experiment_id": "case-01",
    }
    record_policy(policy_record, policy_store_path)
    policies = load_policies(policy_store_path)
    assert len(policies) == 1
    assert policies[0]["policy_id"] == "POL-CASE-01"
