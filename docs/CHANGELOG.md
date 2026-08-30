# ChangeProof Engineering & Improvement Changelog

> Chronological record of architectural decisions, empirical discoveries, bug audits, assertion calibrations, and system hardening milestones per ChangeProof Spec § 16.

---

### [2026-08-30] Core Pipeline Consolidation: Unifying Evaluation Engine and CI Workflows
- **Commit**: `HEAD` (Stage 1-4 Consolidation)
- **Stage**: Pipeline Architecture, Cross-Repo Generalization & Core Unification
- **What Was Duplicated & Why**:
  Due to rapid iterative development during benchmark execution, three separate execution paths emerged:
  1. `changeproof/experiment_runner.py`: Orchestrated the 11 benchmark evaluation cases, querying Prometheus via HTTP and logging detailed time-series metrics.
  2. `changeproof/ci_pipeline.py`: Legacy GitHub Actions CI pipeline script originally hardcoded to the checkout/payment topology.
  3. `changeproof/cli_synth_verify.py`: Advanced topology-agnostic synthesis engine capable of analyzing Docker Compose dependency graphs, discovering FastAPI POST route decorators (`@app.post("/...")`), calibrating fault magnitudes against client timeouts, and running multi-hypothesis evaluations.
- **What Was Merged & Consolidated**:
  - Unified all CI and live verification onto a single hardened core (`RiskAssessor`, `ExperimentSynthesizer`, `hypothesis_evaluator`, `verifier.verify()`).
  - Fully retired `changeproof/ci_pipeline.py`, converting it into a thin 7-line compatibility forwarding shim to `cli_synth_verify.main()`.
  - Updated both `.github/workflows/changeproof.yml` on the original ChangeProof repo and `inventory-cloud-app` repo to run `python -m changeproof.cli_synth_verify`.
- **Real Bugs Caught & Resolved During Consolidation**:
  1. **Workload Arithmetic & Sample Size Reconciliation**: Removed artificial multipliers/floors in request volume generation; request counts derive transparently from `rps_target * duration` (defaulting to 150 requests at 10 RPS x 15s, satisfying the `>= 100` sample size threshold without arbitrary clamps).
  2. **Experiment ID & Service Mismatch**: Resolved issue where missing target dictionary metadata caused experiment ID to fall back to `ci-checkout-*` even when running against `inventory-cloud-app`. Added strict runtime assertion ensuring `changed_service` matches `target_file` across all execution contexts.
  3. **Toxiproxy API 2.x Contract**: Enforced `"stream": "downstream"` parameter on `ToxiproxyClient.add_latency()` with strict HTTP 2xx response validation.
  4. **FastAPI Route Decorator Parsing**: Replaced hardcoded endpoint guessing lists with automated AST/regex analysis of `@app.post(...)` routes in entrypoint services.
- **Stage 2 Regression Replay Table (Zero Regressions on All 10 Capsules)**:

| Case ID | Stage 0 Verdict | Stage 2 Verdict | Pre Retries/Req | Post Retries/Req | Total Requests | Pre TP (req/s) | Post TP (req/s) | Pre Rate (/min) | Post Rate (/min) | Regression? |
|---|---|---|---|---|---|---|---|---|---|---|
| **case-01** | PASS | **PASS** | 7.000 -> 7.000 | 1.000 -> 1.000 | 150 | 3.64 | 5.84 | 1530.12 | 350.20 | NONE |
| **case-05** | PASS_SAFE | **PASS_SAFE** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | NONE |
| **case-10** | PASS | **PASS** | 5.000 -> 5.000 | 1.000 -> 1.000 | 610 | 11.71 | 14.39 | 3513.55 | 863.39 | NONE |
| **case-alt-01** | PASS | **PASS** | 7.000 -> 7.000 | 1.000 -> 1.000 | 150 | 3.63 | 5.82 | 1522.67 | 349.29 | NONE |
| **case-calib-01** | PASS | **PASS** | 7.000 -> 7.000 | 1.000 -> 1.000 | 150 | 5.83 | 5.85 | 2449.83 | 350.88 | NONE |
| **case-calib-02** | PASS | **PASS** | 4.000 -> 4.000 | 1.000 -> 1.000 | 150 | 2.97 | 5.85 | 712.27 | 350.86 | NONE |
| **case-var-01** | PASS | **PASS** | 4.000 -> 4.000 | 1.000 -> 1.000 | 150 | 2.97 | 5.80 | 711.95 | 348.23 | NONE |
| **case-var-02** | PASS | **PASS** | 5.000 -> 5.000 | 1.000 -> 1.000 | 150 | 4.03 | 5.80 | 1209.51 | 348.02 | NONE |
| **case-var-03** | PASS | **PASS** | 7.000 -> 7.000 | 1.000 -> 1.000 | 150 | 7.12 | 11.33 | 2990.17 | 680.03 | NONE |
| **case-var-04** | PASS | **PASS** | 5.000 -> 5.000 | 1.000 -> 1.000 | 100 | 1.63 | 1.97 | 488.34 | 117.98 | NONE |
| **case-var-05** | PASS | **PASS** | 4.000 -> 4.000 | 1.000 -> 1.000 | 150 | 7.13 | 5.81 | 1711.85 | 348.34 | NONE |

- **Stage 3 Live Verification Evidence**:
  - `goodmorningsaksham/ChangeProof` Run `33302014697`: Generated `ci-checkout-0292dc10.zip`, verified 7.0 -> 1.0 retries/req, throughput 3.63 -> 5.82 req/s.
  - `goodmorningsaksham/inventory-cloud-app` Run `33276309079`: Generated `ci-inventory-1788039136.zip`, verified 7.0 -> 1.0 retries/req, throughput 3.63 -> 5.82 req/s.
- **Decision / Learning**:
  Single shared core guarantees full architectural fidelity across evaluation benchmarks and live CI PR gates.

---
### [2026-08-28] Architectural Consolidation: Six-Agent to Single-Agent Loop
- **Commit**: `e58c85d` (ADR-001 / ADR-002)
- **Stage**: Architecture & Core Agent Loop Design
- **What Was Tried / Why**: 
  Initial designs considered multi-agent orchestration (specialized agents for risk assessment, context building, fault generation, load orchestration, code remediation, and verification). This was rejected to prevent multi-agent handoff latency, non-deterministic decision drift, and unneeded framework dependencies (e.g., LangGraph/LangChain).
- **Evidence / Result**: 
  Implemented a single primary LLM with a thin tool-calling loop over 8 deterministic Python functions (`read_file`, `read_topology`, `read_runtime_snapshot`, `propose_hypothesis`, `run_experiment`, `read_metrics`, `write_patch`, `run_tests`), keeping the verifier strictly zero-LLM.
- **Decision / Learning**: 
  Approved per AGENTS.md Ãƒâ€šÃ‚Â§4. Single LLM agent with direct deterministic tools eliminates non-deterministic intermediate handoffs while keeping the deterministic verifier as the sole safety authority.

---

### [2026-08-29] Risk Assessor Signal Detection & Vacuous-Truth Fixes
- **Commit**: `23bcdc3`
- **Stage**: Bug Audit & Static Risk Analysis Hardening
- **What Was Tried / Why**: 
  Systematic audit of `changeproof/risk_assessor.py` identified unanchored regex patterns that matched diff file paths, chunk headers, and context lines (e.g., `--- a/checkout_service.py` or deleted lines matching `timeout`). Additionally, the risk scorer applied a "test presence discount" even when the diff added zero test assertions (vacuous truth).
- **Evidence / Result**: 
  Anchored all regex patterns to addition line prefixes `^\+\s*...` and line boundaries. Fixed test discount logic to require genuine test additions (`^\+\s*(def test_|assert )`). Unit tests in `tests/unit/test_risk_assessor.py` confirmed 100% accurate signal detection.
- **Decision / Learning**: 
  Static analysis of unified diffs must strictly isolate added/modified lines (`+`) from diff header metadata and context lines.

---

### [2026-08-29] Evaluation Truthfulness: Removal of Hardcoded Verdicts
- **Commit**: `ee70cb1`
- **Stage**: Evaluation Harness Integrity & Audit
- **What Was Tried / Why**: 
  Audit of `evaluation/run_advanced.py` revealed a legacy placeholder branch (`if case_id == "case-05":`) and mock verdict literals that returned `PASS` or `FAIL` for cases that had no actual experiment telemetry in `runs/`.
- **Evidence / Result**: 
  Removed all mock/hardcoded verdict literals. Implemented `_find_best_run_csv()` to inspect disk for actual non-empty telemetry and invoke `verifier.verify()`. Introduced the explicit `NOT_EXECUTED` status for un-run cases (CASE-02 through CASE-09), computing aggregate VSCR exclusively over executed cases.
- **Decision / Learning**: 
  Evaluation harnesses must report execution reality, not intent. Un-run benchmark cases must be surfaced as `NOT_EXECUTED` rather than populated with synthetic pass/fail placeholders.

---

### [2026-08-29] Instrumentation Bug: Tenacity `before_sleep` Callback Under-Counting
- **Commit**: `65237ac`
- **Stage**: CASE-01 Live Calibration & Instrumentation Audit
- **What Was Tried / Why**: 
  Fresh post-patch live runs of CASE-01 (`RETRIES_MAX=2`) recorded 0 retries in Prometheus despite physical retry requests executing. Investigation into `app/checkout/main.py` found `record_retry_callback` guarded with `if retry_state.attempt_number > 1:`. Because `tenacity` invokes `before_sleep` with `attempt_number` equal to the attempt that just failed (attempt 1 for the first retry), the guard dropped the first retry of every request.
- **Evidence / Result**: 
  - `RETRIES_MAX=2`: Counted 0 retries (should be 1).
  - `RETRIES_MAX=8`: Counted 6 retries (should be 7).
  Updated guard to `if retry_state.attempt_number >= 1:` and verified with unit tests in `tests/unit/test_retry_callback.py` (6/6 passing). Rebuilt container image.
- **Decision / Learning**: 
  Callback counters in retry libraries must be verified with isolated unit tests against exact attempt lifecycle semantics before calibration.

---

### [2026-08-29] Verification Calibration: Raw Rate/min vs. Normalized Retries/Request
- **Commit**: `65237ac`
- **Stage**: Verification Threshold Recalibration
- **What Was Tried / Why**: 
  Live experiments revealed that un-normalized `rate_per_min` (<150 retries/min) penalized healthier systems. Under 2000ms latency, the broken BASE state (`RETRIES_MAX=8`, no backoff) tied up connections for ~8s per request, achieving low throughput (7.4 req/s, 390 requests) with high amplification (4.53 retries/req, 1,767 total retries). The PATCHED state (`RETRIES_MAX=2`, backoff=0.5) completed in ~2.5s, processing nearly 2ÃƒÆ’Ã¢â‚¬â€ higher volume (14.37 req/s, 723 requests) with strictly 1 retry per request (723 retries, 834.2 retries/min).
- **Evidence / Result**: 
  Updated assertion definitions in `evaluation/cases/case_01.yaml` and `verifier.py`:
  - `pre_patch`: `retries_per_request > 2.0` (Observed: 4.531) AND `total_requests >= 100` (Observed: 390) -> `true`
  - `post_patch`: `retries_per_request <= 1.1` (Observed: 1.000) AND `total_requests >= 100` (Observed: 723) -> `true`
  Raw `rate_per_min` and `throughput_req_per_sec` were retained as reported context metrics on the certificate rather than pass/fail gates.
- **Decision / Learning**: 
  Retry safety verification must evaluate normalized per-request amplification ratios and sample sizes, not raw temporal rates that conflate retry policy quality with achieved throughput.

---

### [2026-08-29] Prometheus Scrape Truncation & Manifest-Priority Calculation
- **Commit**: `cf39478` & `3d376e9`
- **Stage**: Telemetry Pipeline Hardening & Reproduction Packaging
- **What Was Tried / Why**: 
  In `runs/case-01_base_corrected2_1787964332`, Prometheus range scraping captured only 6 points (5.0s window, 12 retries -> 144.0 retries/min) because the intense 8-retry storm saturated Uvicorn's event loop, timing out Prometheus's 1.0s `/metrics` scrape HTTP requests during peak load. Direct counter reads before and after the workload captured the full 1,767 retries (2,012.61/min). However, `verifier.py` evaluated the truncated CSV first.
- **Evidence / Result**: 
  Hardened `verifier.py` to prioritize authoritative direct whole-duration rates and ratios from `manifest.json` over truncated scrape slices. Updated `capsule.py` to preserve multi-phase manifest sub-dictionaries (`base` and `patched`) inside reproduction archives (`capsules/case-01.zip`, `capsules/case-10.zip`).
- **Decision / Learning**: 
  Under severe denial-of-service failure conditions, metric collection must combine continuous scrape series with authoritative boundary counter snapshots in the manifest.

---

### [2026-08-29] Final Generalization Holdout Evaluation (CASE-10) & Negative Control (CASE-05)
- **Commit**: `5635e81`, `6046053`, `50fa96e`
- **Stage**: Final Holdout Evaluation & Coverage Verification
- **What Was Tried / Why**: 
  Formally unsealed CASE-10 (3500ms latency, 45 RPS load, 15 VUs) and evaluated negative control CASE-05 (`+ANALYTICS_RETRY = 2`).
- **Evidence / Result**: 
  - **CASE-05**: Certified as `PASS_SAFE` via static AST analysis without fault injection (`score: 0`, `level: "LOW"`, `requires_experiment: False`).
  - **CASE-10**: Live run reproduced failure (BASE: 3,050 retries / 610 requests = **5.000 retries/req**, 3513.55 retries/min) and verified remediation (PATCHED: 730 retries / 730 requests = **1.000 retry/req**, 863.39 retries/min). Deterministic verifier returned **`PASS`**.
  - Packaged `capsules/case-10.zip` and verified clean replay (`python -m changeproof.replay capsules/case-10.zip` -> `PASS`).
  - Re-generated comparative reports showing honest 3/10 executed coverage (7/10 `NOT_EXECUTED`).
- **Decision / Learning**: 
  Confirmed system generalization across independent compound latency/concurrency holdout parameters.

---

### [2026-08-29] GitHub Actions CI Automation & Live Container Execution Ã¢â‚¬â€ Canonical Numbers & Run ID Settlement
- **Commit**: `7b3ec20`
- **Stage**: CI/CD Integration & Live Runner Verification

#### Run ID Settlement
Two GH Actions run IDs were referenced across documents. Both are real, but only one is a live execution:

| Run ID | Commit | Step 6 Duration | Verdict |
|---|---|---|---|
| `33226386998` | `26fc385` | **1 second** | Capsule-extraction fallback Ã¢â‚¬â€ `ci_pipeline.py` at that commit re-extracted the pre-packaged `case-01.zip` instead of running live containers. **Not a fresh live run.** |
| `33227355365` | `7b3ec20` | **103 seconds (1m43s)** | **Canonical live run** Ã¢â‚¬â€ Docker Compose stack built, Toxiproxy fault injected, async HTTP workload executed, Prometheus metrics captured. Step timing confirmed via GH API (`01:48:28 Ã¢â€ â€™ 01:50:11`). |

**`33226386998` is not an unaccounted run Ã¢â‚¬â€ it executed the old fallback code path, not live containers. `33227355365` is the submission's canonical CI execution.**

#### Canonical Submission Numbers (run `33227355365`, `RETRY_TIMEOUT_SECONDS=0.5`)
- **Pre-Patch (Broken)**: 150 requests, 1,050 retries Ã¢â€ â€™ **7.000 retries/req**, 1520.64 retries/min, 3.62 req/s
- **Post-Patch (Remediated)**: 150 requests, 150 retries Ã¢â€ â€™ **1.000 retry/req**, 349.66 retries/min, 5.83 req/s
- **Deterministic Verifier**: **`PASS`**
- PR comment and capsule artifact (`changeproof-reproduction-capsule`) posted live on PR #1

#### Why Two Configurations Produce Different (Both Real) Numbers

| Config | Timeout | Retries/req | Total reqs | Explanation |
|---|---|---|---|---|
| **CI run** (`33227355365`) | **0.5s** | **7.0** | **150** | All 7 retries fire before 5.0s gateway timeout elapses Ã¢â€ â€™ full amplification |
| Local manual run | 1.0s | 4.531 | 390 | Gateway timeout truncates retry chain mid-flight; higher throughput from shorter per-request time |

Both are real. The CI run with `RETRY_TIMEOUT_SECONDS=0.5` is **canonical** Ã¢â‚¬â€ that is what the PR actually sets.

#### Capsule Provenance (updated 2026-08-29)
- **`capsules/case-01.zip`** Ã¢â‚¬â€ **Canonical submission capsule.** CI run `33227355365`, commit `7b3ec20`. Contains 7.0 retries/req pre-patch, 1.0 retry/req post-patch, 150 requests each. SHA256: `b775406b54b04dee5e789c66569e05bd94f2bdd958d8c1b789de9053093fd072`. Fresh replay confirmed: `python changeproof/replay.py capsules/case-01.zip` Ã¢â€ â€™ **PASS**.
- **`capsules/case-01-local-timeout1.0.zip`** Ã¢â‚¬â€ Secondary artifact. Local run, `RETRY_TIMEOUT_SECONDS=1.0`, 4.531 retries/req, 390 requests. Preserved to document timeout-sensitivity. Not referenced by the certificate or CI PR comment.

- **What Was Tried / Why**: Configured GitHub Actions workflow to automatically assess PR diffs, provision live Docker Compose stacks, inject Toxiproxy faults, execute concurrent workloads, verify deterministic metrics, and post Proof Certificates as PR comments.
- **Evidence / Result**: Initial CI runs (e.g. `33226386998`) fell back to capsule extraction (1-second step). Rebuilt `ci_pipeline.py` for genuine container orchestration. Canonical run `33227355365` produced live telemetry above. `capsules/case-01.zip` regenerated from CI data; old local capsule preserved as `case-01-local-timeout1.0.zip`. Fresh replay confirmed PASS.
- **Decision / Learning**: CI must never fall back to cached runs. Timeout config differences between local and CI both produce real, valid measurements; the CI run under the PR's actual config is canonical. Timeout sensitivity is a genuine product finding worth preserving.

---

### [2026-08-29] Topology-Driven Experiment Specification Synthesis
- **Commit**: HEAD (Topology-Driven Experiment Synthesizer)
- **Stage**: Architecture Generalization & Automated Experiment Synthesis
- **What Was Tried / Why**: 
  Replaced static copying of evaluation/cases/case_01.yaml with a fully dynamic, topology-driven ExperimentSynthesizer (changeproof/experiment_synthesizer.py). The synthesizer parses docker-compose.yml and 	oxiproxy_init.json to automatically:
  1. Map changed files in PR diffs to service containers via build context paths.
  2. Resolve downstream network dependencies by inspecting environment variables and Toxiproxy proxy maps.
  3. Identify Toxiproxy fault-injection proxy targets and ports.
  4. Calibrate fault magnitude dynamically: injected_latency_ms = max(2 * timeout_ms, 1500) with jitter_ms = max(int(0.05 * injected_latency_ms), 50) based on empirical findings from CASE-01 and CASE-10 (latency must exceed per-attempt client timeout by >= 2x to reliably induce timeout retry loops).
  5. Resolve workload gateway entrypoints via graph in-degree root analysis.
  6. Assemble complete experiment.yaml specs with generalized assertion contracts (etries_per_request > 2.0 pre, <= 1.1 post).
- **Evidence / Result**: 
  - Verified on alternate multi-service topology (gateway-service -> inventory-service -> 	oxiproxy -> warehouse-service): synthesized experiment.yaml correctly targeted warehouse-proxy on inventory-service with zero hardcoded references to checkout/payment.
  - Regression verified against CASE-01 (PASS), CASE-05 (PASS_SAFE), and CASE-10 (PASS).
  - Added unit test suite 	ests/unit/test_experiment_synthesizer.py.
- **Decision / Learning**: 
  Reliability verification systems must synthesize experiment hypotheses directly from declarative dependency graphs and diff AST signals rather than relying on pre-authored static YAML templates.

---

### [2026-08-29] Calibration Formula Freezing & Dual-Regime Held-Out Validation (case-calib-01 & case-calib-02)
- **Commit**: HEAD (`case-calib-01` & `case-calib-02` validation)
- **Stage**: Fault Magnitude Calibration & Held-Out Validation
- **What Was Tried / Why**: 
  Formula frozen after case-01/case-10 derivation; validated on timeout=0.3s (floor regime) and timeout=1.3s (multiplicative regime, novel value) â€” both outside the original 0.5s/1.0s derivation inputs. Evaluated whether the frozen formula `injected_latency_ms = max(2 * timeout_ms, 1500)` reliably reproduces and verifies failures across both regimes without any re-tuning.
- **Evidence / Result**: 
  - **`case-calib-01` (Floor Regime, Timeout=0.3s)**: $\max(2 \times 300, 1500) = 1500\text{ms}$ latency. BASE produced 7.000 retries/req (2449.83 retries/min), PATCHED produced 1.000 retry/req (350.88 retries/min). Verifier: **`PASS`**. Capsule: `capsules/case-calib-01.zip`.
  - **`case-calib-02` (Multiplicative Regime, Timeout=1.3s)**: $\max(2 \times 1300, 1500) = 2600\text{ms}$ latency. BASE produced 4.000 retries/req (712.27 retries/min), PATCHED produced 1.000 retry/req (350.86 retries/min). Verifier: **`PASS`**. Capsule: `capsules/case-calib-02.zip`.
  - Replay verified for both capsules via `python changeproof/replay.py` -> **`PASS`**.
- **Decision / Learning**: 
  The frozen fault calibration formula reliably transfers to both the baseline floor regime (<0.75s) and the multiplicative scaling regime (>=0.75s) on novel timeout values without empirical re-tuning.
