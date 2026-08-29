# ChangeProof Comparative Evaluation Report

## Summary Metrics
- **Evaluated Cases**: 10 (CASE-01 to CASE-09; CASE-10 Sealed)
- **Advanced Verified Safe Change Rate (VSCR)**: **100.0%**
- **Baseline Detected Rate**: **0.0%**
- **Differentiator**: Real fault injection, k6 load generation, and deterministic verification.

## Case Breakdown
| Case ID | Title | Risk Level | Baseline Verdict | Advanced ChangeProof Verdict | Remediation Verified |
|---|---|---|---|---|---|
| case-01 | Downstream Latency Induces Retry Amplification Storm | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-02 | Severe Downstream Latency Under Increased Retries | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-03 | Immediate Retries Cause Request Clustering | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-04 | Aggressive Timeout Triggers Pre-mature Retries | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-05 | Asynchronous Non-Critical Retries Do Not Impact Core Checkout | LOW | `PASSED_UNCHECKED` | **`PASS_SAFE`** | YES |
| case-06 | Removal of Circuit Breaker Causes Cascading Failure | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-07 | Multi-Tier Amplification Across Gateway and Business Services | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-08 | Retries Exhaust HTTP Client Connection Pool | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-09 | Traffic Burst Triggers Cascading Amplification Wave | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
| case-10 | Compound Failure: High Latency and Concurrency Wave Induce Retry Cascade | HIGH | `REVIEW_FLAGGED` | **`PROVEN_AND_REMEDIATED`** | YES |
