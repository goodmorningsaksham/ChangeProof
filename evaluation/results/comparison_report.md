# ChangeProof Evaluation Report — Honest Execution Coverage

> **WARNING**: This report reflects actual execution status.
> Metrics are computed only over cases where a real experiment was run,
> real telemetry was collected, and verifier.verify() was called.
> NOT_EXECUTED cases are NOT included in any percentage.

## Execution Coverage

- **Cases in suite**: 10
- **Actually executed**: 1/10
- **Not yet executed**: 9

## Metrics (over 1/10 executed cases only)

- **Advanced VSCR**: 0.0%
- **Baseline VSCR** (same executed cases): 100.0%
- **Advanced PASS**: 0 | **FAIL**: 1 | **INCONCLUSIVE**: 0

## Full Case Status

| Case ID | Title | Executed? | Risk Level | Baseline Verdict | Advanced Verdict | Real Telemetry | Verifier Called |
|---|---|---|---|---|---|---|---|
| case-01 | Downstream Latency Induces Retry Amplification Storm | YES | HIGH | `REVIEW_FLAGGED` | **`FAIL`** | YES | YES |
| case-02 | Severe Downstream Latency Under Increased Retries | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |
| case-03 | Immediate Retries Cause Request Clustering | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |
| case-04 | Aggressive Timeout Triggers Pre-mature Retries | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |
| case-05 | Asynchronous Non-Critical Retries Do Not Impact Core Checkout | **NO — NOT EXECUTED** | LOW | `PASSED_UNCHECKED` | **`NOT_EXECUTED`** | NO | NO |
| case-06 | Removal of Circuit Breaker Causes Cascading Failure | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |
| case-07 | Multi-Tier Amplification Across Gateway and Business Services | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |
| case-08 | Retries Exhaust HTTP Client Connection Pool | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |
| case-09 | Traffic Burst Triggers Cascading Amplification Wave | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |
| case-10 | Compound Failure: High Latency and Concurrency Wave Induce Retry Cascade | **NO — NOT EXECUTED** | HIGH | `REVIEW_FLAGGED` | **`NOT_EXECUTED`** | NO | NO |

## Not-Yet-Executed Cases

- **case-02**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-03**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-04**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-05**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-06**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-07**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-08**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-09**: No non-empty base metrics: True; no non-empty patched metrics: True
- **case-10**: No non-empty base metrics: True; no non-empty patched metrics: True
