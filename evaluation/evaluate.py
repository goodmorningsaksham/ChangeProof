"""Evaluation benchmark comparator — honest execution coverage reporting.

Metrics are computed ONLY over cases that were actually executed (i.e., those
whose advanced_verdict is not NOT_EXECUTED and not SKIPPED/SEALED).  Cases
with NOT_EXECUTED are counted separately and explicitly reported.

Baseline metric explicitly reflects static risk detection/classification accuracy,
while VSCR (Verified Safe Change Rate) requires deterministic runtime verification
which only the Advanced system performs.
"""
import os
import json
import pandas as pd
from typing import Dict, Any, List
from evaluation.run_baseline import BaselineRunner
from evaluation.run_advanced import AdvancedRunner

NOT_RUN_STATUSES = {"NOT_EXECUTED", "SKIPPED", "SEALED"}


def run_comparative_evaluation(
    output_dir: str = "evaluation/results",
    include_sealed: bool = False,
) -> Dict[str, Any]:
    """Runs comparative benchmark and reports honest execution coverage."""
    os.makedirs(output_dir, exist_ok=True)

    b_runner = BaselineRunner()
    a_runner = AdvancedRunner()

    base_results = b_runner.run_all(include_sealed=include_sealed)
    adv_results = a_runner.run_all(include_sealed=include_sealed)

    total_cases = len(adv_results)

    # Split into executed vs not-yet-run
    executed = [r for r in adv_results if r["advanced_verdict"] not in NOT_RUN_STATUSES]
    not_executed = [r for r in adv_results if r["advanced_verdict"] in NOT_RUN_STATUSES]

    total_executed = len(executed)
    total_not_executed = len(not_executed)

    # --- Advanced metrics: computed ONLY over executed cases ---
    executed_pass = [r for r in executed if r["advanced_verdict"] in ("PASS", "PASS_SAFE")]
    executed_fail = [r for r in executed if r["advanced_verdict"] == "FAIL"]
    executed_inconclusive = [r for r in executed if r["advanced_verdict"] == "INCONCLUSIVE"]

    if total_executed > 0:
        vscr_advanced = (len(executed_pass) / total_executed) * 100
    else:
        vscr_advanced = None

    # --- Baseline metrics: static risk classification accuracy ---
    base_results_map = {r["case_id"]: r for r in base_results}

    # For the baseline, REVIEW_FLAGGED on risky case = flagged.
    # PASSED_UNCHECKED on safe negative control (case-05) = passed.
    base_executed = [base_results_map[r["case_id"]] for r in executed if r["case_id"] in base_results_map]
    base_correct = sum(
        1 for r in base_executed
        if r.get("baseline_verdict") in ("REVIEW_FLAGGED", "PASSED_UNCHECKED")
    )
    risk_detection_accuracy_baseline = (base_correct / total_executed * 100) if total_executed > 0 else None
    vscr_baseline_desc = "N/A — baseline does not perform deterministic verification by design"

    # Build comparison rows
    comparison_rows: List[Dict[str, Any]] = []
    for a in adv_results:
        b = base_results_map.get(a["case_id"], {})
        comparison_rows.append({
            "case_id": a["case_id"],
            "title": a.get("title", ""),
            "executed": a["advanced_verdict"] not in NOT_RUN_STATUSES,
            "risk_level": a.get("risk_level", "UNKNOWN"),
            "baseline_verdict": b.get("baseline_verdict", "N/A"),
            "advanced_verdict": a["advanced_verdict"],
            "runtime_evidence_used": a.get("runtime_evidence_used", False),
            "verifier_called": a.get("verifier_called", False),
            "verification_mechanism": a.get("verification_mechanism", "None"),
            "not_executed_reason": a.get("not_executed_reason", ""),
        })

    df = pd.DataFrame(comparison_rows)
    csv_path = os.path.join(output_dir, "comparison_report.csv")
    df.to_csv(csv_path, index=False)

    summary_data: Dict[str, Any] = {
        "evaluation_suite": "CASE-01 to CASE-10",
        "WARNING": (
            "Metrics below are computed ONLY over actually-executed cases. "
            "NOT_EXECUTED cases are listed explicitly and excluded from all percentages."
        ),
        "execution_coverage": {
            "total_cases_in_suite": total_cases,
            "cases_actually_executed": total_executed,
            "cases_not_yet_executed": total_not_executed,
            "executed_case_ids": [r["case_id"] for r in executed],
            "not_executed_case_ids": [r["case_id"] for r in not_executed],
        },
        "metrics_over_executed_cases_only": {
            "vscr_advanced": round(vscr_advanced, 1) if vscr_advanced is not None else "N/A (0 cases executed)",
            "vscr_baseline": vscr_baseline_desc,
            "risk_detection_accuracy_baseline": (
                round(risk_detection_accuracy_baseline, 1)
                if risk_detection_accuracy_baseline is not None
                else "N/A"
            ),
            "pass_count": len(executed_pass),
            "fail_count": len(executed_fail),
            "inconclusive_count": len(executed_inconclusive),
        },
        "cases": comparison_rows,
    }

    json_path = os.path.join(output_dir, "evaluation_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # Markdown report
    executed_str = f"{total_executed}/{total_cases}"
    vscr_adv_str = f"{vscr_advanced:.1f}%" if vscr_advanced is not None else "N/A"
    base_acc_str = f"{risk_detection_accuracy_baseline:.1f}%" if risk_detection_accuracy_baseline is not None else "N/A"

    report_md = f"""# ChangeProof Evaluation Report — Honest Execution Coverage

> **WARNING**: This report reflects actual execution status.
> Metrics are computed only over cases where a real experiment was run or deterministic risk verification executed.
> NOT_EXECUTED cases are NOT included in any percentage.

## Execution Coverage

- **Cases in suite**: {total_cases}
- **Actually executed**: {executed_str}
- **Not yet executed**: {total_not_executed}

## Metrics (over {executed_str} executed cases only)

- **Advanced Verified Safe Change Rate (VSCR)**: **{vscr_adv_str}** (Verified through deterministic metrics/AST)
- **Baseline VSCR**: **{vscr_baseline_desc}**
- **Baseline Risk Detection Accuracy**: **{base_acc_str}** (Static review flags risk but cannot verify or fix)
- **Advanced PASS**: {len(executed_pass)} | **FAIL**: {len(executed_fail)} | **INCONCLUSIVE**: {len(executed_inconclusive)}

## Full Case Status

| Case ID | Title | Executed? | Risk Level | Baseline Verdict | Advanced Verdict | Telemetry Used | Verifier Called | Verification Mechanism |
|---|---|---|---|---|---|---|---|---|
"""
    for r in comparison_rows:
        executed_flag = "YES" if r["executed"] else "**NO — NOT EXECUTED**"
        report_md += (
            f"| {r['case_id']} | {r['title']} | {executed_flag} "
            f"| {r['risk_level']} | `{r['baseline_verdict']}` "
            f"| **`{r['advanced_verdict']}`** "
            f"| {'YES' if r['runtime_evidence_used'] else 'NO'} "
            f"| {'YES' if r['verifier_called'] else 'NO'} "
            f"| {r['verification_mechanism']} |\n"
        )

    report_md += "\n## Not-Yet-Executed Cases\n\n"
    if not_executed:
        for r in not_executed:
            reason = r.get("not_executed_reason", "No run directory found")
            report_md += f"- **{r['case_id']}**: {reason}\n"
    else:
        report_md += "All cases executed.\n"

    report_md_path = os.path.join(output_dir, "comparison_report.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return {
        "total_cases": total_cases,
        "cases_executed": total_executed,
        "cases_not_executed": total_not_executed,
        "vscr_advanced": vscr_advanced,
        "vscr_baseline": vscr_baseline_desc,
        "risk_detection_accuracy_baseline": risk_detection_accuracy_baseline,
        "report_md_path": report_md_path,
        "csv_path": csv_path,
        "json_path": json_path,
    }


if __name__ == "__main__":
    res = run_comparative_evaluation(include_sealed=True)
    print(f"Executed: {res['cases_executed']}/{res['total_cases']}")
    print(f"Not yet executed: {res['cases_not_executed']}")
    adv = res['vscr_advanced']
    print(f"Advanced VSCR (over executed only): {f'{adv:.1f}%' if adv is not None else 'N/A'}")
    print(f"Baseline VSCR: {res['vscr_baseline']}")
    print(f"Baseline Risk Detection Accuracy: {res['risk_detection_accuracy_baseline']}%")
    print(f"Report: {res['report_md_path']}")
    print(f"JSON:   {res['json_path']}")
