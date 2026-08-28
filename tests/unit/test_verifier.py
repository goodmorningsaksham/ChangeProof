"""Unit tests for deterministic verifier."""
import pandas as pd
from changeproof.verifier import verify, evaluate_condition

def test_evaluate_condition():
    s = pd.Series([10.0, 20.0, 30.0])
    assert evaluate_condition(s, "> 15") is True
    assert evaluate_condition(s, "< 10") is False
    assert evaluate_condition(s, "rate_per_min > 15") is True

def test_verify_pass(tmp_path):
    pre_csv = tmp_path / "metrics_pre.csv"
    post_csv = tmp_path / "metrics_post.csv"

    # Pre-patch failure data (high retry count)
    pd.DataFrame([
        {"timestamp": 100.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 250.0},
    ]).to_csv(pre_csv, index=False)

    # Post-patch remediated data (low retry count)
    pd.DataFrame([
        {"timestamp": 200.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 15.0},
    ]).to_csv(post_csv, index=False)

    assertions = {
        "pre_patch": [{"metric": "retry_count_total", "condition": "> 100"}],
        "post_patch": [{"metric": "retry_count_total", "condition": "< 50"}],
    }

    result = verify(str(pre_csv), str(post_csv), assertions)
    assert result.status == "PASS"

def test_verify_inconclusive_when_pre_not_reproduced(tmp_path):
    pre_csv = tmp_path / "metrics_pre.csv"
    post_csv = tmp_path / "metrics_post.csv"

    # Pre-patch data did NOT reach the failure threshold
    pd.DataFrame([
        {"timestamp": 100.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 20.0},
    ]).to_csv(pre_csv, index=False)

    pd.DataFrame([
        {"timestamp": 200.0, "metric_name": "retry_count_total", "service": "checkout", "target": "payment", "value": 10.0},
    ]).to_csv(post_csv, index=False)

    assertions = {
        "pre_patch": [{"metric": "retry_count_total", "condition": "> 100"}],
        "post_patch": [{"metric": "retry_count_total", "condition": "< 50"}],
    }

    result = verify(str(pre_csv), str(post_csv), assertions)
    assert result.status == "INCONCLUSIVE"
    assert "did not reproduce" in result.reason
