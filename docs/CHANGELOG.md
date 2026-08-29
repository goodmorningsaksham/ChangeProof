# ChangeProof Engineering Changelog

> Chronological record of architectural decisions, empirical discoveries, assertion calibrations, and system hardening milestones.

---

### [2026-08-29] Calibration Update: Instrumentation Fix & Normalized Ratio Assertion (CASE-01)

#### 1. Context & Problem Statement
During deep live verification of CASE-01, two critical discoveries were made regarding retry counting instrumentation and assertion semantics:
1. **Instrumentation Counter Guard Bug**: In `app/checkout/main.py`, `record_retry_callback` guarded with `if retry_state.attempt_number > 1`. Because `tenacity` invokes `before_sleep` with `attempt_number` equal to the attempt that just failed (attempt 1 for the first retry attempt), the guard dropped the first retry of every request. For `RETRIES_MAX=2`, exactly 0 retries were counted despite physical retries executing. For `RETRIES_MAX=8`, 6 of 7 retries were counted.
2. **Assertion Conflation (Rate vs. Quality)**: The prior assertion relied on raw `rate_per_min` (`< 150` retries/min). Under heavy downstream latency (2000ms), a broken retry policy (`RETRIES_MAX=8, backoff=0.0`) spent ~8s per request chain, achieving low throughput (390 requests over 52.7s = 7.4 req/s) but generating 4.53 retries/req (1,767 total retries, 2,012.6 retries/min). Conversely, a remediated bounded policy (`RETRIES_MAX=2, backoff=0.5`) completed in ~2.5s, allowing the system to process nearly 2× higher request volume (723 requests over 50.3s = 14.37 req/s), executing exactly 1 retry per request (723 total retries, 834.2 retries/min). Comparing un-normalized `rate_per_min` penalized the healthy system for achieving higher capacity.

#### 2. Instrumentation Resolution
- Updated `record_retry_callback` in `app/checkout/main.py` to `if retry_state.attempt_number >= 1:`.
- Verified via unit tests (`tests/unit/test_retry_callback.py`):
  - `RETRIES_MAX=2`: Exactly 1 retry counted per failed request.
  - `RETRIES_MAX=8`: Exactly 7 retries counted per failed request.
  - `RETRIES_MAX=1`: Exactly 0 retries counted.

#### 3. Empirical Evidence (Live Re-Runs)
Under identical conditions (Toxiproxy 2000ms latency + 100ms jitter, k6 30 RPS load over 45s):

| Metric | BASE State (`case-01_base_corrected2_1787964332`) | PATCHED State (`case-01_patched_corrected_1787964030`) | Delta / Interpretation |
|---|---|---|---|
| **Configuration** | `RETRIES_MAX=8`, `BACKOFF=0.0`, `TIMEOUT=1.0s` | `RETRIES_MAX=2`, `BACKOFF=0.5`, `TIMEOUT=1.0s` | Remediated configuration |
| **Duration** | 52.7s | 50.3s | Comparable test windows |
| **Requests Processed** | 390 requests | 723 requests | +85.4% throughput capacity |
| **Throughput** | **7.40 req/s** | **14.37 req/s** | Faster release of concurrency slots |
| **Retries Counted** | 1,767 retries | 723 retries | Strictly bounded count |
| **Retries / Request** | **4.531 retries/req** | **1.000 retry/req** | **-77.9% reduction in retry amplification** |
| **Rate (retries/min)** | 2,012.61 / min (direct) | 834.23 / min (CSV) / 862.13 / min (abs) | Reported context metric |

#### 4. Calibrated Assertion Definitions
Updated `evaluation/cases/case_01.yaml` and `changeproof/verifier.py` to:
- **Pre-Patch Assertion (Failure Reproduction)**:
  - `retries_per_request > 2.0` (Observed: **4.531**) ✅
  - `total_requests >= 100` (Observed: **390**) ✅
- **Post-Patch Assertion (Remediation Verification)**:
  - `retries_per_request <= 1.1` (Observed: **1.000**) ✅
  - `total_requests >= 100` (Observed: **723**) ✅

#### 5. Verification Verdict
Deterministic verifier evaluates all 4 conditions as **MET** ($\text{PASS}$). Proof Certificate updated to present normalized ratios, throughput req/s, sample size, and reported rate_per_min.

---

### [2026-08-29] Evaluation Harness Truthfulness Hardening
- Replaced synthetic/hardcoded evaluation branching with deterministic verification checks against real telemetry.
- Un-executed cases (CASE-02 through CASE-10) are explicitly marked `NOT_EXECUTED` rather than fabricated `PASS`.
- Aggregate VSCR and coverage rates are calculated exclusively over genuinely executed and verified cases.
