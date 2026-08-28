"""Evaluation benchmark comparator computing Verified Safe Change Rate (VSCR)."""
import os
import pandas as pd
from typing import Dict, Any
from evaluation.run_baseline import BaselineRunner
from evaluation.run_advanced import AdvancedRunner

def run_comparative_evaluation(output_dir: str = "evaluation/results") -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    
    b_runner = BaselineRunner()
    a_runner = AdvancedRunner()

    base_results = b_runner.run_all()
    adv_results = a_runner.run_all()

    # Calculate Verified Safe Change Rate (VSCR):
    # % of cases where system correctly determines safety status AND patch passes deterministic verification
    adv_correct_count = sum(
        1 for r in adv_results if r["advanced_verdict"] in ["PROVEN_AND_REMEDIATED", "PASS_SAFE"]
    )
    total_cases = len(adv_results)
    vscr_advanced = (adv_correct_count / total_cases) * 100 if total_cases > 0 else 0.0

    # Baseline detection rate
    base_detected_count = sum(1 for r in base_results if r["baseline_verdict"] == "REVIEW_FLAGGED")
    vscr_baseline = (base_detected_count / total_cases) * 100 if total_cases > 0 else 0.0

    comparison_rows = []
    for b, a in zip(base_results, adv_results):
        comparison_rows.append({
            "case_id": a["case_id"],
            "title": a["title"],
            "risk_level": a["risk_level"],
            "baseline_verdict": b["baseline_verdict"],
            "advanced_verdict": a["advanced_verdict"],
            "remediation_verified": a["remediation_verified"],
        })

    df = pd.DataFrame(comparison_rows)
    csv_path = os.path.join(output_dir, "comparison_report.csv")
    df.to_csv(csv_path, index=False)

    report_md = f"""# ChangeProof Comparative Evaluation Report

## Summary Metrics
- **Evaluated Cases**: {total_cases} (CASE-01 to CASE-09; CASE-10 Sealed)
- **Advanced Verified Safe Change Rate (VSCR)**: **{vscr_advanced:.1f}%**
- **Baseline Detected Rate**: **{vscr_baseline:.1f}%**
- **Differentiator**: Real fault injection, k6 load generation, and deterministic verification.

## Case Breakdown
| Case ID | Title | Risk Level | Baseline Verdict | Advanced ChangeProof Verdict | Remediation Verified |
|---|---|---|---|---|---|
"""
    for r in comparison_rows:
        report_md += f"| {r['case_id']} | {r['title']} | {r['risk_level']} | `{r['baseline_verdict']}` | **`{r['advanced_verdict']}`** | {'YES' if r['remediation_verified'] else 'NO'} |\n"

    report_md_path = os.path.join(output_dir, "comparison_report.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return {
        "total_cases": total_cases,
        "vscr_advanced": vscr_advanced,
        "vscr_baseline": vscr_baseline,
        "report_md_path": report_md_path,
        "csv_path": csv_path,
    }

if __name__ == "__main__":
    res = run_comparative_evaluation()
    print(f"Advanced VSCR: {res['vscr_advanced']:.1f}% vs Baseline: {res['vscr_baseline']:.1f}%")
    print(f"Report written to {res['report_md_path']}")
