"""Dedicated safety regression test suite for verifier INCONCLUSIVE path."""
import pandas as pd
from changeproof.verifier import verify
from changeproof.certificate import CertificateGenerator

def test_missing_evidence_returns_inconclusive(tmp_path):
    """Missing CSV files must return INCONCLUSIVE, never PASS."""
    non_existent_pre = str(tmp_path / "missing_pre.csv")
    non_existent_post = str(tmp_path / "missing_post.csv")
    
    assertions = {
        "pre_patch": [{"metric": "retry_count_total", "condition": "> 100"}],
        "post_patch": [{"metric": "retry_count_total", "condition": "< 50"}],
    }
    
    result = verify(non_existent_pre, non_existent_post, assertions)
    assert result.status == "INCONCLUSIVE"
    assert "metrics file missing" in result.reason

def test_insufficient_pre_patch_reproduction_returns_inconclusive(tmp_path):
    """When pre-patch experiment fails to reproduce the fault, verifier must abort with INCONCLUSIVE."""
    pre_csv = tmp_path / "metrics_pre.csv"
    post_csv = tmp_path / "metrics_post.csv"

    # Pre-patch did not trigger a retry storm (observed 5 retries, threshold > 100)
    pd.DataFrame([
        {"timestamp": 100.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 5.0},
    ]).to_csv(pre_csv, index=False)

    # Post-patch also low
    pd.DataFrame([
        {"timestamp": 200.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 2.0},
    ]).to_csv(post_csv, index=False)

    assertions = {
        "pre_patch": [{"metric": "retry_count_total", "condition": "> 100"}],
        "post_patch": [{"metric": "retry_count_total", "condition": "< 50"}],
    }

    result = verify(str(pre_csv), str(post_csv), assertions)
    assert result.status == "INCONCLUSIVE"
    assert "did not reproduce" in result.reason

def test_inconclusive_certificate_does_not_claim_safe(tmp_path):
    """A Proof Certificate generated with INCONCLUSIVE status must explicitly warn NOT CERTIFIED."""
    gen = CertificateGenerator()
    cert_path = tmp_path / "inconclusive_cert.md"
    
    ctx = {
        "timestamp": "2026-08-29T04:00:00Z",
        "experiment_id": "case-01-inconclusive-test",
        "git_commit": "abcdef1",
        "risk_level": "HIGH",
        "risk_score": 70,
        "hypothesis_title": "Unproven hypothesis",
        "hypothesis_confidence": "LOW",
        "verification_status": "INCONCLUSIVE",
        "diff_table": [],
        "capsule_path": "capsules/case-01.zip",
    }
    
    gen.generate_and_save(ctx, str(cert_path))
    with open(cert_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "INCONCLUSIVE" in content
    assert "NOT CERTIFIED FOR PRODUCTION" in content
    assert "PROVEN & VERIFIED SAFE" not in content
