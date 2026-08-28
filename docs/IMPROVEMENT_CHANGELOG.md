# ChangeProof Improvement Changelog

> Chronological record of empirical observations, assertion calibrations, and system hardening milestones.

---

### [2026-08-28] Initial Architecture & Microservice Target Stack
- **Target Microservices**: Implemented 3 FastAPI services (`frontend`, `checkout`, `payment`) running in Docker Compose.
- **Toxiproxy Network Path**: Positioned `toxiproxy` proxy (`payment-proxy` listening on `:18002`) between `checkout` and `payment` (`:8002`).
- **Telemetry**: Instrumented services with Prometheus metrics (`checkout_requests_total`, `retry_count_total`, `retry_exhausted_total`, `http_errors_total`).

---

### [2026-08-28] Week 1 Live Empirical Baseline Observations (CASE-01)
- **Observed Behavior**: Injected 2000ms latency on payment proxy under 30 RPS inbound k6 load.
- **Base State Defect**: 8 retries with 0.0s backoff and 0.5s timeout generated an immediate runaway storm.
- **Empirical Measurement**:
  - Duration: 49.0s ($1,470$ total orders attempted).
  - Retry Count Delta: $+2,719$ retries.
  - Measured Storm Rate: **$3,329.39\text{ retries/min}$** ($55.49\text{ retries/sec}$) with $100\%$ gateway timeout errors.
- **Finding**: Mislabeled units in early documentation ("240 req/min" vs actual 240 req/sec) resolved through empirical Prometheus delta tracking.

---

### [2026-08-29] Deterministic Verifier Rate Calculation Hardening
- **Change**: Refactored `verifier.compute_metric_aggregate` to calculate exact rate per minute using timestamp deltas:
  $$\text{rate\_per\_min} = \frac{\Delta \text{value}}{\Delta t_{\text{seconds}}} \times 60.0$$
- **Rationale**: Eliminates bias from cumulative sample averages and provides instantaneous rate fidelity during load test windows.

---

### [2026-08-29] Assertion Threshold Calibration (CASE-01)
- **Pre-Patch Threshold**: Updated `pre_patch` condition to `rate_per_min > 500` (observed broken state was $3,329\text{ retries/min}$).
- **Post-Patch Threshold**: Updated `post_patch` condition to `rate_per_min < 150` (observed remediated state was $0.0\text{ retries/min}$).
- **Rationale**: Strict separation between runaway amplification storms ($>3000\text{/min}$) and healthy/bounded retries ($<150\text{/min}$).

---

### [2026-08-29] Reproduction Capsule & Clean Replay Contract
- **Packaging**: Created `CapsulePackager` to archive immutable `experiment.yaml` (with SHA-256 hash), raw `metrics_pre.csv` and `metrics_post.csv`, `patch.diff`, and manifest metadata into `capsules/case-01.zip`.
- **Replay Modes**: Implemented dual-mode replay in `replay.py`:
  - `--evidence` (default): Fast cryptographic hash and deterministic re-verification of recorded CSV metrics.
  - `--live`: Full containerized rebuild and live rerun across BASE and PATCHED states with fresh metric collection.

---

### [2026-08-29] Baseline & Evaluation Suite Implementation
- **Benchmark Suite**: Implemented `case_01.yaml` through `case_09.yaml` covering latency, clustering, premature timeouts, negative controls, circuit breaker drops, and connection starvation.
- **Fairness Contract**: `BaselineRunner` uses the identical LLM and test inputs, demonstrating that conventional static review passes high-risk retry changes unchecked while ChangeProof proves and verifies safety.
- **Holdout Evaluation**: Formal unsealing of `case_10.yaml` (Compound Failure) successfully executed and verified.
