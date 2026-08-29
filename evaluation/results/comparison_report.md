# ChangeProof Evaluation Report — Honest Execution Coverage

> **WARNING**: This report reflects actual execution status.
> Metrics are computed only over cases where a real experiment was run or deterministic risk verification executed.
> NOT_EXECUTED cases are NOT included in any percentage.

## Execution Coverage

- **Cases in suite**: 10
- **Actually executed**: 3/10
- **Not yet executed**: 7

## Metrics (over 3/10 executed cases only)

- **Advanced Verified Safe Change Rate (VSCR)**: **100.0%** (Verified through deterministic metrics/AST)
- **Baseline VSCR**: **N/A — baseline does not perform deterministic verification by design**
- **Baseline Risk Detection Accuracy**: **100.0%** (Static review flags risk but cannot verify or fix)
- **Advanced PASS**: 3 | **FAIL**: 0 | **INCONCLUSIVE**: 0

## Full Case Status

| Case ID | Title | Executed? | Risk Level | Baseline Verdict | Advanced Verdict | Telemetry Used | Verifier Called | Verification Mechanism |
|---|---|---|---|---|---|---|---|---|
| case-01 | Downstream Latency Induces Retry Amplification Storm | YES | HIGH | `REVIEW_FLAGGED` | **`PASS`** | YES | YES | Deterministic Runtime Verifier |
| case-02 | Severe Downstream Latency Under Increased Retries | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO | None (Not Executed) |
| case-03 | Immediate Retries Cause Request Clustering | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO | None (Not Executed) |
| case-04 | Aggressive Timeout Triggers Pre-mature Retries | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO | None (Not Executed) |
| case-05 | Asynchronous Non-Critical Retries Do Not Impact Core Checkout | YES | LOW | `PASSED_UNCHECKED` | **`PASS_SAFE`** | NO | NO | Static AST Risk Assessment |
| case-06 | Removal of Circuit Breaker Causes Cascading Failure | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO | None (Not Executed) |
| case-07 | Multi-Tier Amplification Across Gateway and Business Services | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO | None (Not Executed) |
| case-08 | Retries Exhaust HTTP Client Connection Pool | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO | None (Not Executed) |
| case-09 | Traffic Burst Triggers Cascading Amplification Wave | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO | None (Not Executed) |
| case-10 | Compound Failure: High Latency and Concurrency Wave Induce Retry Cascade | YES | HIGH | `REVIEW_FLAGGED` | **`PASS`** | YES | YES | Deterministic Runtime Verifier |

## Not-Yet-Executed Cases

- **case-02**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-03**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-04**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-06**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-07**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-08**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-09**: No non-empty base metrics: True; no non-empty patched metrics: True
