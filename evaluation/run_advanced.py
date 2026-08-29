"""Advanced ChangeProof evaluation runner — honest execution status reporting.

A case result is ONLY classified as PROVEN_AND_REMEDIATED or PASS_SAFE when:
  1. A run directory exists under runs/ prefixed with {case_id}_base_* containing
     a non-empty metrics CSV (>0 data rows).
  2. A run directory exists under runs/ prefixed with {case_id}_patched_* containing
     a non-empty metrics CSV (>0 data rows).
  3. verifier.verify() was called against those CSVs and returned PASS.

Any case not meeting ALL THREE conditions is reported as NOT_EXECUTED.
No hardcoded verdicts. No fabricated pass/fail.
"""
import os
import glob
import yaml
import json
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
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
}


def _find_best_run_csv(runs_dir: str, case_id: str, state: str) -> Optional[str]:
    """Return the path to the metrics CSV from the most recent non-empty run for
    {case_id}_{state}_* directories.  Returns None if no non-empty CSV exists."""
    # Match directories like case-01_base_* or case-01_patched_*
    pattern = os.path.join(runs_dir, f"{case_id}_{state}_*")
    candidates = sorted(glob.glob(pattern), reverse=True)  # newest first (highest timestamp)
    for run_dir in candidates:
        if not os.path.isdir(run_dir):
            continue
        # Metrics file may be named metrics_{state}.csv or metrics_base/patched.csv
        for csv_name in (f"metrics_{state}.csv", "metrics_base.csv", "metrics_patched.csv"):
            csv_path = os.path.join(run_dir, csv_name)
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                if len(df) > 0:
                    return csv_path
    return None


class AdvancedRunner:
    """Advanced ChangeProof workflow with honest execution-status reporting.

    Verdict logic:
      NOT_EXECUTED  — no real experiment run found with non-empty telemetry.
      PASS          — verifier.verify() returned PASS on real base+patched CSVs.
      FAIL          — verifier.verify() returned FAIL on real base+patched CSVs.
      INCONCLUSIVE  — verifier.verify() returned INCONCLUSIVE (e.g. pre-patch
                      did not reproduce the expected failure).
    """

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

        # 1. Deterministic Risk Assessment (metadata only — does NOT gate execution)
        diff_text = DIFF_MAP.get(case_id, "+RETRIES_MAX = 8\n+RETRY_BACKOFF_FACTOR = 0.0\n")
        assessor = RiskAssessor()
        risk_res = assessor.assess_diff(diff_text)

        # 2. Locate real experiment telemetry
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
                "deterministic_verification": False,
                "base_metrics_csv": base_csv,
                "patched_metrics_csv": patched_csv,
                "not_executed_reason": (
                    f"No non-empty base metrics: {base_csv is None}; "
                    f"no non-empty patched metrics: {patched_csv is None}"
                ),
            }

        # 3. Call verifier.verify() against real telemetry
        assertions = case_data.get("assertions", {})
        ver_result = verify(base_csv, patched_csv, assertions)

        return {
            "case_id": case_id,
            "title": case_data.get("title", ""),
            "risk_level": risk_res["level"],
            "advanced_verdict": ver_result.status,   # PASS / FAIL / INCONCLUSIVE
            "runtime_evidence_used": True,
            "deterministic_verification": True,
            "base_metrics_csv": base_csv,
            "patched_metrics_csv": patched_csv,
            "verifier_reason": ver_result.reason,
            "verifier_diff_table": ver_result.diff_table,
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
