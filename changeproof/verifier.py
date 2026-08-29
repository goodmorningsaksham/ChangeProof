"""Deterministic assertion verifier for ChangeProof — Zero LLM calls."""
import os
import re
import pandas as pd  # type: ignore[import-untyped]
from typing import Dict, Any, List, Optional

class VerificationResult:
    def __init__(self, status: str, reason: str = "", diff_table: Optional[List[Dict[str, Any]]] = None):
        self.status = status # "PASS" | "FAIL" | "INCONCLUSIVE"
        self.reason = reason
        self.diff_table = diff_table or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "diff_table": self.diff_table,
        }

def compute_metric_aggregate(sub_df: pd.DataFrame, condition_str: str) -> float:
    """Computes the appropriate metric aggregate (rate per min or mean).

    Rate computation requires a 'timestamp' column to calculate a per-minute rate.
    When the timestamp column is absent the function returns the last observed value
    (a raw counter snapshot), NOT a per-minute rate.  Callers that rely on rate
    semantics must ensure the DataFrame includes a 'timestamp' column — the
    export_metrics_to_df() method always provides one.
    """
    if sub_df.empty:
        return 0.0
    val_s = sub_df["value"]
    if "rate_per_min" in condition_str or "rate" in condition_str:
        if "timestamp" in sub_df.columns and len(sub_df) > 1:
            t_min = float(sub_df["timestamp"].min())
            t_max = float(sub_df["timestamp"].max())
            duration_s = max(t_max - t_min, 1.0)
            delta_val = max(float(val_s.max() - val_s.min()), 0.0)
            return float((delta_val / duration_s) * 60.0)
        else:
            # No timestamp available: return the last observed counter value.
            # This is NOT a rate; the condition threshold must be set accordingly
            # when using synthetic test data without timestamps.
            return float(val_s.iloc[-1])
    return float(val_s.mean())

def evaluate_condition_val(agg_val: float, condition_str: str) -> bool:
    """Evaluates comparison operator on aggregate value."""
    match = re.search(r'([><=]+)\s*([\d.]+)', condition_str)
    if not match:
        return False
    op, threshold_str = match.groups()
    threshold = float(threshold_str)
    
    if op == ">":
        return agg_val > threshold
    elif op == ">=":
        return agg_val >= threshold
    elif op == "<":
        return agg_val < threshold
    elif op == "<=":
        return agg_val <= threshold
    elif op == "==":
        return abs(agg_val - threshold) < 1e-3
    return False

def evaluate_condition(metric_series: pd.Series, condition_str: str) -> bool:
    """Backward-compatible series evaluation."""
    if metric_series.empty:
        return False
    df = pd.DataFrame({"value": metric_series})
    agg_val = compute_metric_aggregate(df, condition_str)
    return evaluate_condition_val(agg_val, condition_str)

def verify(pre_metrics_csv: str, post_metrics_csv: str, assertions: Dict[str, Any]) -> VerificationResult:
    """Sole deterministic authority evaluating pre and post experiment runs."""
    if not os.path.exists(pre_metrics_csv):
        return VerificationResult(status="INCONCLUSIVE", reason=f"Pre-patch metrics file missing: {pre_metrics_csv}")
    if not os.path.exists(post_metrics_csv):
        return VerificationResult(status="INCONCLUSIVE", reason=f"Post-patch metrics file missing: {post_metrics_csv}")

    pre_df = pd.read_csv(pre_metrics_csv)
    post_df = pd.read_csv(post_metrics_csv)

    diff_table = []

    # 1. Evaluate pre_patch assertions (Failure Reproduction check)
    pre_assertions = assertions.get("pre_patch", [])
    pre_reproduced = True
    for a in pre_assertions:
        m_name = a["metric"]
        cond = a["condition"]
        sub_df = pre_df[pre_df["metric_name"] == m_name] if not pre_df.empty else pd.DataFrame()
        agg_val = compute_metric_aggregate(sub_df, cond)
        passed_cond = evaluate_condition_val(agg_val, cond)
        diff_table.append({
            "metric": m_name,
            "phase": "pre_patch",
            "condition": cond,
            "observed_value": round(agg_val, 2),
            "condition_met": passed_cond,
        })
        if not passed_cond:
            pre_reproduced = False

    if not pre_reproduced and pre_assertions:
        return VerificationResult(
            status="INCONCLUSIVE",
            reason="Pre-patch experiment did not reproduce the expected failure condition",
            diff_table=diff_table,
        )

    # 2. Evaluate post_patch assertions (Remediation Verification check)
    post_assertions = assertions.get("post_patch", [])
    post_passed = True
    for a in post_assertions:
        m_name = a["metric"]
        cond = a["condition"]
        sub_df = post_df[post_df["metric_name"] == m_name] if not post_df.empty else pd.DataFrame()
        agg_val = compute_metric_aggregate(sub_df, cond)
        passed_cond = evaluate_condition_val(agg_val, cond)
        diff_table.append({
            "metric": m_name,
            "phase": "post_patch",
            "condition": cond,
            "observed_value": round(agg_val, 2),
            "condition_met": passed_cond,
        })
        if not passed_cond:
            post_passed = False

    if post_passed:
        return VerificationResult(status="PASS", reason="Fix verified successfully", diff_table=diff_table)
    else:
        return VerificationResult(status="FAIL", reason="Post-patch experiment violated safety thresholds", diff_table=diff_table)
