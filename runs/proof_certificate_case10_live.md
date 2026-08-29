# CHANGE PROOF CERTIFICATE
Generated: 2026-08-29T06:40:00Z | Experiment: case-10 | Commit: main


> **STATUS**: ✅ **PROVEN & VERIFIED SAFE** — Patch passed deterministic criteria.


## Evaluation Summary
- **Risk Level**: HIGH (Score: 85/100)
- **Failure Class**: Retry Amplification / Retry Storm
- **Hypothesis**: High latency (3500ms) and concurrency spike induce compound retry cascade (Confidence: HIGH)
- **Deterministic Verification Verdict**: **PASS**

## Key Metric Observations & Throughput Context
| Metric | Pre-Patch (Broken) | Post-Patch (Remediated) | Target / Safe Bound | Status |
|---|---|---|---|---|
| **Retries / Request** | **5.0** | **1.0** | `> 2.0` (Pre) / `<= 1.1` (Post) | ✅ CONTROLLED |
| **Throughput (req/s)** | 11.71 req/s | 14.39 req/s | Context (Normalized capacity) | ℹ️ Reported |
| **Total Requests** | 610 | 730 | `>= 100` Sample Size | ✅ Validated |
| **Rate (retries/min)** | 3513.55 /min | 863.39 /min | Context (Un-normalized rate) | ℹ️ Reported |

## Deterministic Assertion Verification
| Metric | Phase | Observed Value | Condition | Condition Met |
|---|---|---|---|---|

| retries_per_request | pre_patch | 5.0 | `> 2.0` | YES |

| total_requests | pre_patch | 610.0 | `>= 100` | YES |

| retries_per_request | post_patch | 1.0 | `<= 1.1` | YES |

| total_requests | post_patch | 730.0 | `>= 100` | YES |


## Reproducibility & Artifacts
- **Reproduction Capsule**: `capsules/case-10.zip`
- **Replay Command**: `python changeproof/replay.py capsules/case-10.zip`

## Human Engineering Decision
[ ] APPROVED FOR DEPLOYMENT   [ ] REJECTED   [ ] ESCALATE FOR REVIEW
Reviewer Signature: _______________________ Date: _______________