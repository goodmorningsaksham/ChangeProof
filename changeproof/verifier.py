"""Deterministic assertion verifier for ChangeProof — Zero LLM calls."""
import os
import re
import pandas as pd
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

def evaluate_condition(metric_series: pd.Series, condition_str: str) -> bool:
    """Evaluates simple threshold conditions like 'rate_per_min > 50', '> 20', '< 5'."""
    if metric_series.empty:
        return False

    # Extract comparison operator and number
    match = re.search(r'([><=]+)\s*([\d.]+)', condition_str)
    if not match:
        return False

    op, threshold_str = match.groups()
    threshold = float(threshold_str)
    
    # Calculate aggregate or rate
    # If checking rate_per_min, calculate delta or mean rate
    if "rate_per_min" in condition_str or "rate" in condition_str:
        # Rate in events/min = (max - min) / duration_min or sum
        val_diff = metric_series.max() - metric_series.min() if len(metric_series) > 1 else metric_series.iloc[-1]
        agg_val = float(val_diff)
    else:
        agg_val = float(metric_series.mean())

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
        sub_s = pre_df[pre_df["metric_name"] == m_name]["value"] if not pre_df.empty else pd.Series([], dtype=float)
        passed_cond = evaluate_condition(sub_s, cond)
        diff_table.append({
            "metric": m_name,
            "phase": "pre_patch",
            "condition": cond,
            "observed_value": float(sub_s.mean()) if not sub_s.empty else 0.0,
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
        sub_s = post_df[post_df["metric_name"] == m_name]["value"] if not post_df.empty else pd.Series([], dtype=float)
        passed_cond = evaluate_condition(sub_s, cond)
        diff_table.append({
            "metric": m_name,
            "phase": "post_patch",
            "condition": cond,
            "observed_value": float(sub_s.mean()) if not sub_s.empty else 0.0,
            "condition_met": passed_cond,
        })
        if not passed_cond:
            post_passed = False

    if post_passed:
        return VerificationResult(status="PASS", reason="Fix verified successfully", diff_table=diff_table)
    else:
        return VerificationResult(status="FAIL", reason="Post-patch experiment violated safety thresholds", diff_table=diff_table)
