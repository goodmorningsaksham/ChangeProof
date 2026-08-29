"""Advanced ChangeProof evaluation runner — honest execution status reporting.

A case result is classified as:
  - PASS_SAFE: Deterministic static risk assessment confirmed change is LOW risk
    and does not require counterfactual runtime experimentation (negative control).
  - PASS / FAIL / INCONCLUSIVE: Genuinely executed experiment evaluated by
    deterministic verifier.verify() on real base and patched telemetry.
  - NOT_EXECUTED: High-risk change requiring experiment that has not yet been
    executed with real telemetry on disk.
"""
import os
import glob
import yaml
import json
import pandas as pd
from typing import Dict, Any, List, Optional
from changeproof.risk_assessor import RiskAssessor
from changeproof.verifier import verify

DIFF_MAP: Dict[str, str] = {
    "case-01": "+RETRIES_MAX = 8\n+RETRY_BACKOFF_FACTOR = 0.0\n+RETRY_TIMEOUT_SECONDS = 0.5\n",
    "case-02": "+RETRIES_MAX = 6\n+RETRY_TIMEOUT_SECONDS = 0.5\n",
    "case-03": "+RETRY_BACKOFF_FACTOR = 0.0\n+RETRIES_MAX = 5\n",
    "case-04": "+RETRY_TIMEOUT_SECONDS = 0.2\n+RETRIES_MAX = 5\n",
    "case-05": "+ANALYTICS_RETRY = 2\n",
    "case-06": "+RETRIES_MAX = 5\n+RETRY_BACKOFF_FACTOR = 0.0\n",
    "case-07": "+RETRIES_MAX = 6\n+RETRY_TIMEOUT_SECONDS = 0.4\n",
    "case-08": "+RETRIES_MAX = 8\n+RETRY_BACKOFF_FACTOR = 0.0\n",
    "case-09": "+RETRIES_MAX = 5\n+RETRY_TIMEOUT_SECONDS = 0.5\n",
    "case-10": "+RETRIES_MAX = 6\n+RETRY_BACKOFF_FACTOR = 0.0\n+RETRY_TIMEOUT_SECONDS = 0.5\n",
}


def _find_best_run_csv(runs_dir: str, case_id: str, state: str) -> Optional[str]:
    """Return the path to the metrics CSV from the most recent non-empty run for
    {case_id}_{state}_* directories.  Returns None if no non-empty CSV exists."""
    pattern = os.path.join(runs_dir, f"{case_id}_{state}_*")
    matched_dirs = [d for d in glob.glob(pattern) if os.path.isdir(d)]
    candidates = sorted(matched_dirs, key=lambda d: os.path.getmtime(d), reverse=True)
    for run_dir in candidates:
        for csv_name in (f"metrics_{state}.csv", "metrics_base.csv", "metrics_patched.csv"):
            csv_path = os.path.join(run_dir, csv_name)
            if os.path.exists(csv_path):
                try:
                    df = pd.read_csv(csv_path)
                    if len(df) > 0:
                        return csv_path
                except Exception:
                    pass
    return None


class AdvancedRunner:
    """Advanced ChangeProof workflow with honest execution-status reporting."""

    def __init__(
        self,
        cases_dir: str = "evaluation/cases",
        runs_dir: str = "runs",
        results_dir: str = "evaluation/results",
    ):
        self.cases_dir = cases_dir
        self.runs_dir = runs_dir
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)

    def evaluate_case(self, case_file: str) -> Dict[str, Any]:
        case_path = os.path.join(self.cases_dir, case_file)
        with open(case_path, "r", encoding="utf-8") as f:
            case_data = yaml.safe_load(f)

        case_id = case_data.get("id", case_file)

        if case_data.get("status") == "SEALED":
            return {
                "case_id": case_id,
                "title": case_data.get("title", ""),
                "status": "SEALED",
                "advanced_verdict": "SKIPPED",
                "runtime_evidence_used": False,
                "deterministic_verification": False,
            }

        # 1. Deterministic Risk Assessment
        diff_text = DIFF_MAP.get(case_id, "+RETRIES_MAX = 8\n+RETRY_BACKOFF_FACTOR = 0.0\n")
        assessor = RiskAssessor()
        risk_res = assessor.assess_diff(diff_text)

        # 2. If change is classified as LOW risk and does not require experiment:
        # Grounded AST risk assessment deterministically approves negative control without fault injection.
        if not risk_res["requires_experiment"] and risk_res["level"] == "LOW":
            return {
                "case_id": case_id,
                "title": case_data.get("title", ""),
                "risk_level": "LOW",
                "advanced_verdict": "PASS_SAFE",
                "runtime_evidence_used": False,
                "verifier_called": False,
                "deterministic_classification": True,
                "verification_mechanism": "Static AST Risk Assessment",
                "not_executed_reason": "",
            }

        # 3. For High-Risk changes: locate real experiment telemetry
        base_csv = _find_best_run_csv(self.runs_dir, case_id, "base")
        patched_csv = _find_best_run_csv(self.runs_dir, case_id, "patched")

        if base_csv is None or patched_csv is None:
            # No real experiment was executed for this case.
            return {
                "case_id": case_id,
                "title": case_data.get("title", ""),
                "risk_level": risk_res["level"],
                "advanced_verdict": "NOT_EXECUTED",
                "runtime_evidence_used": False,
                "verifier_called": False,
                "deterministic_classification": True,
                "verification_mechanism": "None (Not Executed)",
                "base_metrics_csv": base_csv,
                "patched_metrics_csv": patched_csv,
                "not_executed_reason": (
                    f"No non-empty base metrics: {base_csv is None}; "
                    f"no non-empty patched metrics: {patched_csv is None}"
                ),
            }

        # 4. Call verifier.verify() against real telemetry
        assertions = case_data.get("assertions", {})
        ver_result = verify(base_csv, patched_csv, assertions)

        return {
            "case_id": case_id,
            "title": case_data.get("title", ""),
            "risk_level": risk_res["level"],
            "advanced_verdict": ver_result.status,  # PASS / FAIL / INCONCLUSIVE
            "runtime_evidence_used": True,
            "verifier_called": True,
            "deterministic_classification": True,
            "verification_mechanism": "Deterministic Runtime Verifier",
            "base_metrics_csv": base_csv,
            "patched_metrics_csv": patched_csv,
            "verifier_reason": ver_result.reason,
            "verifier_diff_table": ver_result.diff_table,
            "not_executed_reason": "",
        }

    def run_all(self, include_sealed: bool = False) -> List[Dict[str, Any]]:
        results = []
        for file in sorted(os.listdir(self.cases_dir)):
            if not file.endswith(".yaml"):
                continue
            if not include_sealed and file.startswith("case_10"):
                continue
            results.append(self.evaluate_case(file))
        return results


if __name__ == "__main__":
    runner = AdvancedRunner()
    res = runner.run_all(include_sealed=True)
    print(json.dumps(res, indent=2))
