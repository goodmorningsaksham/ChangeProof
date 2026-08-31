# ChangeProof: Autonomous Counterfactual Reliability Verification for CI

> **Conventional CI tells you that the unit tests passed.**  
> **ChangeProof subjects the proposed change to the failure condition it is supposed to survive, measures the resulting runtime behavior, and produces tamper-evident, replayable proof.**

[![ChangeProof CI](https://github.com/goodmorningsaksham/ChangeProof/actions/workflows/changeproof.yml/badge.svg)](https://github.com/goodmorningsaksham/ChangeProof/actions/workflows/changeproof.yml)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Architecture: Zero-LLM Verifier](https://img.shields.io/badge/Verifier-Zero--LLM_Deterministic-brightgreen.svg)](#architecture-the-bounded-agentic-loop)
[![Evidence: 18 Sealed Capsules](https://img.shields.io/badge/Evidence-18_Sealed_Capsules-purple.svg)](#full-case-inventory--benchmark-evaluation)
[![GitHub Repository](https://img.shields.io/badge/GitHub-goodmorningsaksham%2FChangeProof-black?logo=github)](https://github.com/goodmorningsaksham/ChangeProof)

---

## Executive Overview

Modern CI tells backend and SRE teams whether code compiles, static linters pass, and unit tests succeed. However, for distributed microservices, the most catastrophic production outages—such as **cascading retry storms**, **connection pool exhaustion**, and **deadlocks**—only emerge when a change encounters real runtime failure conditions: transient downstream latency, partial network partitions, slow database queries, or resource pressure.

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   THE CORE ARCHITECTURAL PRINCIPLE                               │
│                                                                                                  │
│   LLM                 ──► Proposes hypotheses and candidate remediation patches                  │
│   Runtime Experiment  ──► Measures empirical Prometheus telemetry under Toxiproxy latency       │
│   Deterministic Engine──► Decides PASS / FAIL mathematically (Zero-LLM mathematical arbiter)    │
│   Proof Certificate   ──► Records tamper-evident evidence in PR comments & sealed capsules    │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

ChangeProof is an agentic SRE verification system designed for platform, reliability, and backend teams reviewing reliability-sensitive pull requests (retries, timeouts, backoff, circuit breakers, rate limits, and connection pools). Given a pull request, ChangeProof:

1. **Understands the change statically** by scanning diffs for reliability-sensitive signals (retry increases, timeout reductions, backoff removals) and stored organizational governance policies.
2. **Synthesizes a counterfactual experiment directly from the application's Docker Compose topology** without requiring manually crafted test scenarios.
3. **Creates a real downstream failure condition** using **Toxiproxy** to inject calibrated TCP network latency into live service traffic (not mocked HTTP responses).
4. **Measures concrete runtime evidence** using Prometheus counters ($\Delta\text{retries}/\Delta\text{requests}$, throughput, and request durations).
5. **Uses AI for reasoning, not authority**: An LLM (Gemini, OpenAI, Anthropic) or deterministic template proposes failure hypotheses and candidate remediation patches, but is **never** permitted to declare whether a change is safe.
6. **Verifies the remediation independently**: The patched service is rebuilt and subjected to the exact same failure scenario under a deterministic zero-LLM verifier.
7. **Closes the loop when a fix is insufficient**: If an initial patch fails verification, observed runtime evidence is fed back to the model for automated diagnosis and patch revision within a bounded 2-attempt budget.
8. **Produces tamper-evident proof**: Emits a Markdown **Proof Certificate** and packages raw telemetry CSVs, diffs, and SHA-256 hashes into a compact, self-contained **Reproduction Capsule** that replays offline in under 2 seconds without Docker.
9. **Surfaces evidence directly in GitHub Pull Requests**: Posts the full Proof Certificate, before/after metric comparison tables, and capsule download links directly as automated PR comments.

---

## Reference Documentation & Evidence Links

* 📄 **Submission Status & Evidence Matrix**: [`docs/SUBMISSION_STATUS.md`](docs/SUBMISSION_STATUS.md)  
* 📊 **Comparative Benchmark Report (VSCR)**: [`evaluation_report.md`](evaluation_report.md) & [`evaluation_report.csv`](evaluation_report.csv)  
* 🔬 **Confounded Multi-Signal Analysis Case**: [`docs/CHALLENGING_CASE.md`](docs/CHALLENGING_CASE.md)  
* 🤖 **Representative Agent Trajectories (Deliverable 04)**: [`docs/AGENT_TRAJECTORIES.md`](docs/AGENT_TRAJECTORIES.md)
* 📜 **Engineering Audit Trail & Changelog**: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)  
* 🔗 **Live GitHub PR Demonstrations**:
  * [ChangeProof PR #2 (FastAPI Checkout Service)](https://github.com/goodmorningsaksham/ChangeProof/pull/2)
  * [express-order-app PR #2 (Node.js Express Service)](https://github.com/goodmorningsaksham/express-order-app/pull/2)


---

## Hackathon Deliverables Index

| Official Deliverable | Description | Authoritative Repository Path |
|---|---|---|
| **Deliverable 01 — Complete Solution Code & Improvement Changelog** | Complete verification engine, target microservices, topology configurations, agent instructions, and unedited engineering audit trail | Full source code ([`changeproof/`](changeproof/), [`app/`](app/), [`docker-compose.yml`](docker-compose.yml)) & [`docs/CHANGELOG.md`](docs/CHANGELOG.md) |
| **Deliverable 02 — Reproduction Guide** | Canonical clean-environment reproduction guide: setup, dependencies, optional API keys, exact single-command replay, live Docker reproduction, runtime benchmarks, approximate costs, and tamper detection | [`README.md`](README.md) |
| **Deliverable 04 — Representative Agent Trajectories** | Case-10 tool-call JSONL trace, Case-Self-Correction-01 multi-attempt remediation capsule, and trajectory documentation | [`docs/AGENT_TRAJECTORIES.md`](docs/AGENT_TRAJECTORIES.md), [`runs/case-10_agent_run/agent_trajectory.jsonl`](runs/case-10_agent_run/agent_trajectory.jsonl), [`capsules/case-self-correction-01.zip`](capsules/case-self-correction-01.zip) |

---

## Architecture: The Bounded Agentic Loop

```text
                         [ Pull Request Diff ]
                                   │
                                   ▼
                       [ Step 1: Risk Assessor ]
            (AST & Regex scan: RETRIES_MAX 2 -> 8, TIMEOUT 0.5s)
                                   │
                                   ▼
                  [ Step 2: Experiment Synthesizer ]
       (Parses docker-compose.yml & toxiproxy_init.json -> Spec)
                                   │
                                   ▼
                 [ Step 3: Hypothesis Evaluator (LLM) ]
          (Proposes candidate mechanisms grounded in code context)
                                   │
                                   ▼
                  [ Step 4: Topology Provisioning ]
                 (Docker Compose UP: 5 Microservices)
                                   │
                                   ▼
                     [ Step 5: Toxiproxy Fault ]
            (Injects 1500ms downstream TCP latency toxic)
                                   │
                                   ▼
                 [ Step 6: BASE Workload Execution ]
        (150 reqs @ 10 VUs -> 7.0 retries/req storm confirmed)
                                   │
                                   ▼
                  [ Step 7: LLM Patch Remediation ]
            (Gemini / Fallback proposes safe parameters:
             RETRIES=2, TIMEOUT=1.0s, BACKOFF=0.5s -> Rebuild)
                                   │
                                   ▼
               [ Step 8: PATCHED Workload Execution ]
      (Identical 150 reqs under 1500ms fault -> 1.0 retry/req)
                                   │
                                   ▼
             [ Step 9: Deterministic Zero-LLM Verifier ]
    (Math: Δretries/Δrequests <= 1.1? -> PASS | Dur > 5.6s? -> PASS)
                                   │
                    ┌──────────────┴──────────────┐
                 [ PASS ]                      [ FAIL ]
                    │                             │
                    ▼                             ▼
        [ Step 10: Certificate ]       [ Self-Correction Loop ]
         & [ Step 11: Capsule ]        (Telemetry feedback -> Attempt 2)
                    │
                    ▼
       [ GitHub PR Comment & Replay ]
```

### Key Architectural Safeguards

1. **Zero-LLM Verification Arbiter**: The pass/fail verdict is computed exclusively by [`changeproof/verifier.py`](changeproof/verifier.py) based on Prometheus delta counters. An LLM never decides whether a patch is safe.
2. **Duration Sanity Check**: If a workload finishes implausibly fast ($dur < \frac{N}{VUs} \times L_{\text{fault}} \times 0.25$), the verifier rejects the run as `INCONCLUSIVE` to prevent false passes caused by bypassed proxies or network anomalies.
3. **Multi-Provider Fail-Fast Fallback**: [`changeproof/llm_client.py`](changeproof/llm_client.py) evaluates Gemini (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), and Anthropic (`claude-3-5-sonnet`) with strict 20s timeouts. If the API key is missing, network fails, or 429 quota exhaustion occurs, the pipeline immediately engages deterministic static fallback parameters (`RETRIES_MAX=2, TIMEOUT=1.0s, BACKOFF=0.5s`) with explicit provenance labels (`[PATCH SOURCE: FALLBACK]`), ensuring zero blocking.
4. **3-Layer Hash Integrity**: Reproduction capsules enforce SHA-256 spec integrity, individual raw evidence CSV checksums, and mathematical cross-validation between manifest claims and raw metric rows.
5. **Organizational Policy Learning**: Human review policies are persisted in `policy_store.json` and deterministically enforced as hard gates on future PRs.

---

## Live Reference Run vs. Benchmark Evidence

To maintain strict scientific precision, ChangeProof distinguishes between the **live reference reproduction run** and **historical benchmark evidence**:

### 1. The Canonical Live Reference Run (`evaluation/cases/case_01_pr.diff`)
* **Workload**: 150 requests @ 10 concurrency against `http://localhost:8000/orders`
* **Injected Fault**: 1500ms downstream latency with 75ms jitter on `payment-proxy`
* **BASE Measurement (PR State: `RETRIES=8, TIMEOUT=0.5s, BACKOFF=0.0s`)**:
  * Duration: **61.4s** ($15 \text{ batches} \times 4.0\text{s/req}$)
  * Retries / Request: **7.000** ($1050 \text{ retries} / 150 \text{ requests}$)
  * Rate: **1025.7 retries/min** | Throughput: **2.44 req/s**
* **PATCHED Measurement (Remediated: `RETRIES=2, TIMEOUT=1.0s, BACKOFF=0.5s`)**:
  * Duration: **38.2s** ($15 \text{ batches} \times 2.5\text{s/req}$)
  * Retries / Request: **1.000** ($150 \text{ retries} / 150 \text{ requests}$)
  * Rate: **235.5 retries/min** | Throughput: **3.92 req/s**
* **Deterministic Verification**: `retries_per_request <= 1.1` $\rightarrow$ **`[PASS]`**

### 2. Multi-Attempt Self-Correction Artifact (`capsules/case-self-correction-01.zip`)
In complex failure scenarios, an initial fix may be insufficient. ChangeProof demonstrates full iterative remediation:
* **Attempt 1**: LLM proposes naive reduction to `RETRIES_MAX = 3` with unchanged 0.4s timeout $\rightarrow$ Rebuilt service yields **2.0 retries/req** $\rightarrow$ Verifier issues **`[FAIL]`** ($2.0 > 1.1$).
* **Empirical Feedback**: Verifier telemetry is fed back to the LLM (*"Attempt 1 failed because RETRIES_MAX was still set too high (3) and RETRY_BACKOFF_FACTOR was 0.0..."*).
* **Attempt 2**: LLM increases timeout to `1.5s`, adds exponential backoff `0.5s`, and sets `RETRIES_MAX = 1` $\rightarrow$ Rebuilt service yields **0.0 retries/req** $\rightarrow$ Verifier issues **`[PASS]`**.

---

## Fresh-Download Reproduction Guide

Follow these step-by-step instructions to reproduce ChangeProof from a freshly extracted source ZIP.

### Prerequisites
* **Python**: `3.10` or `3.11`
* **Approximate Verification Cost**: $\approx \$0.04$ per verification in the evaluated local configuration, with external LLM/API usage provider/model dependent (offline deterministic fallback runs at $\$0.00$).
* **Docker Desktop / Docker Engine & Docker Compose** (required only for Live Docker reproduction; offline replay requires zero Docker)
* **Operating System**: Windows (PowerShell), Linux, or macOS

---

### Step 1: Environment Setup

Extract the source ZIP, open a terminal in the project root directory, and create a virtual environment:

#### Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

#### Linux / macOS (bash / zsh):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

### Step 2: Offline Proof Replay (Safest First Demonstration — Zero Docker Required)

Verify any historical or sealed experiment capsule in under 1 second without installing or starting Docker:

```bash
# Replay the Multi-Attempt Self-Correction proof
python -m changeproof.replay capsules/case-self-correction-01.zip

# Replay the Canonical Case-01 storm proof
python -m changeproof.replay capsules/case-01.zip

# Replay Alternate Inventory-Warehouse Topology proof
python -m changeproof.replay capsules/case-alt-01.zip

# Replay Node.js Express Framework proof
python -m changeproof.replay capsules/case-framework-gen-02.zip
```

**Expected Output**:
```json
{
  "replay_mode": "evidence_verification",
  "replay_status": "COMPLETED",
  "spec_verified": true,
  "verification": {
    "status": "PASS",
    "reason": "Fix verified successfully",
    "diff_table": [ ... ],
    "pre_summary": { "retries_per_request": 7.0, "total_requests": 150 },
    "post_summary": { "retries_per_request": 0.0, "total_requests": 150 }
  }
}
```

---

### Step 3: Run the Full Benchmark Suite (Offline Benchmark Evaluation)

Compare ChangeProof's Verified Safe Change Rate against conventional CI baselines across the 11-case benchmark suite:

```bash
# 1. Evaluate Conventional Baseline (shows 10/10 unsafe PRs unmitigated)
python evaluate.py --baseline

# 2. Evaluate ChangeProof Engine (shows 100% VSCR / 11 of 11 cases verified)
python evaluate.py --changeproof
```

**Expected ChangeProof Summary Table**:
```text
================================================================================
CHANGEPROOF VERIFIED EVALUATION (11 Executed Cases)
================================================================================
Case ID         | Verdict    | Pre-Patch Retries  | Post-Patch Retries | Verification Status           
----------------------------------------------------------------------------------------------------
case-01         | PASS       | 7.0                | 1.0                | PROVEN (7.0 -> 1.0 retries/req)
case-05         | PASS_SAFE  | N/A                | N/A                | PASS_SAFE (Static AST Cleared)
case-10         | PASS       | 5.0                | 1.0                | PROVEN (5.0 -> 1.0 retries/req)
case-alt-01     | PASS       | 7.0                | 1.0                | PROVEN (7.0 -> 1.0 retries/req)
case-calib-01   | PASS       | 7.0                | 1.0                | PROVEN (7.0 -> 1.0 retries/req)
case-calib-02   | PASS       | 4.0                | 1.0                | PROVEN (4.0 -> 1.0 retries/req)
case-var-01     | PASS       | 4.0                | 1.0                | PROVEN (4.0 -> 1.0 retries/req)
case-var-02     | PASS       | 5.0                | 1.0                | PROVEN (5.0 -> 1.0 retries/req)
case-var-03     | PASS       | 7.0                | 1.0                | PROVEN (7.0 -> 1.0 retries/req)
case-var-04     | PASS       | 5.0                | 1.0                | PROVEN (5.0 -> 1.0 retries/req)
case-var-05     | PASS       | 4.0                | 1.0                | PROVEN (4.0 -> 1.0 retries/req)

Summary: 11/11 cases independently proven safe / cleared via deterministic verification.
VSCR (Verified Safe Change Rate): 100.0% (11/11).
Dynamic Remediation Verified: 100.0% (10/10 unsafe changes bounded to <= 1.1).
```

---

### Step 4: Run the Live Tamper-Detection Demonstration

Demonstrate ChangeProof's 3-layer cryptographic and telemetric tamper detection in ~2.5 seconds:

#### Windows (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_tamper_detection.ps1
```

#### Linux / macOS:
```bash
bash scripts/demo_tamper_detection.sh
```

**Demonstrated Behavior**:
1. Extracts `capsules/case-01.zip`.
2. Simulates a malicious edit by modifying `manifest.json` from `7.0` to `3.0` retries/req.
3. Replays tampered archive $\rightarrow$ **Fails loudly** with `TAMPER_DETECTED`:  
   `[ERROR] EVIDENCE TAMPERED: manifest summary (3.0) contradicts raw telemetry in metrics_base.csv (7.0)` (Exit code 1).
4. Replays original untouched archive $\rightarrow$ **Passes cleanly** with `[PASS]` (Exit code 0).

---

### Step 5: Live Docker Counterfactual Investigation (Full CI Pipeline)

Ensure Docker Desktop / Docker Engine is running, clean existing containers, and run the unified CI verification engine:

```bash
# Clean existing container state
docker compose down --remove-orphans

# (Optional) Export Gemini API Key for live LLM reasoning; if omitted, safe fallback activates automatically
# Windows: $env:GEMINI_API_KEY = "your-key"
# Linux:   export GEMINI_API_KEY="your-key"

# Run full live verification on the Case-01 PR diff
python -u -m changeproof.cli_synth_verify --diff evaluation/cases/case_01_pr.diff
```

#### Generated Artifacts:
* 📄 **Proof Certificate**: [`runs/ci_run/proof_certificate.md`](runs/ci_run/proof_certificate.md) — Rendered Markdown certificate with before/after metrics and diffs.
* 📝 **Real-Time Observability Log**: [`runs/ci_run/verification.log`](runs/ci_run/verification.log) — Real-time execution log tracking Docker commands and step transitions.
* 📦 **Reproduction Capsule**: `runs/ci_run/capsules/ci-checkout-*.zip` — Compact, self-contained ZIP archive ($<50\text{ KB}$).
* 📊 **Raw Telemetry CSVs**: `runs/ci_run/metrics_base.csv` & `runs/ci_run/metrics_patched.csv`.
* 📋 **Run Manifest**: `runs/ci_run/manifest.json`.

---

### Step 6: Automated Test Suite & Code Quality Gates

Run the comprehensive unit test suite, linter, and static type checker:

```bash
# 1. Run all 61 unit tests
python -m pytest tests/unit/ -v

# 2. Run Ruff linter
python -m ruff check changeproof/ tests/ scripts/ evaluation/

# 3. Run MyPy static type checker
python -m mypy changeproof/ --ignore-missing-imports
```

**Test Suite Coverage Summary**:
* `test_experiment_synthesizer.py` (6 tests) — Topology generalization across FastAPI, Flask, and Express.
* `test_human_approval_gate.py` (3 tests) — Governance and approval boundary enforcement.
* `test_hypothesis_evaluator.py` (12 tests) — Multi-signal reasoning, confounded attribution labels, and fallbacks.
* `test_policy_governance.py` & `test_policy_store.py` (4 tests) — Policy learning and persistent governance.
* `test_retry_callback.py` (6 tests) — Prometheus counter arithmetic and hook precision.
* `test_self_correction.py` (5 tests) — Telemetry feedback prompts, clamp boundaries, and multi-attempt trajectories.
* `test_tamper_detection.py` (2 tests) — SHA-256 spec hashes and CSV metric cross-validation.
* `test_target_app.py` (8 tests) — Microservice health and Prometheus metric endpoints.
* `test_tools_unit.py` & `test_toxiproxy_client.py` (7 tests) — Agent tooling boundaries and Toxiproxy REST client.
* `test_verifier.py` & `test_verifier_safety.py` (8 tests) — Deterministic math assertions and duration sanity guards.

---

## Submission Package Contents

The submitted source-code ZIP is cleanly organized and strictly excludes build caches, local `.env` files, and bytecode:

| Directory / File | Status | Description |
|---|---|---|
| `changeproof/` | **Included** | Core verification engine, synthesizer, verifier, capsule packager, LLM client, replay |
| `app/` | **Included** | Target microservices under test (`checkout`, `payment`, `frontend`, `inventory`, `warehouse`, `flask_service`) |
| `capsules/` | **Included** | 18 sealed reproduction capsule archives for offline replay |
| `evaluation/` | **Included** | 15 benchmark case specifications, diffs, and comparison runners |
| `tests/` | **Included** | 61 unit tests across 13 test modules |
| `scripts/` | **Included** | Automated tamper-detection demo scripts (`.ps1` and `.sh`) |
| `.github/` | **Included** | GitHub Actions PR reliability gate workflow (`changeproof.yml`) |
| `monitoring/` | **Included** | Prometheus scrape configuration (`prometheus.yml`) |
| `docs/` | **Included** | Formal specification, evaluation reports, submission status, changelog |
| `docker-compose*.yml` | **Included** | Multi-tier service topologies across FastAPI, Flask, and Express |
| `toxiproxy_init*.json`| **Included** | Toxiproxy JSON proxy configurations |
| `policy_store.json` | **Included** | Persisted organizational reliability policies |
| `requirements.txt` | **Included** | Pinned dependencies with `google-generativeai==0.8.3` |
| `.mypy_cache/`, `*.pyc` | **Excluded** | Generated caches and Python bytecode (kept ZIP to $< 1\text{ MB}$) |
| `.env` | **Excluded** | Local API keys / credentials (strictly never packaged) |

---

## Full Case Inventory & Benchmark Evaluation

ChangeProof's evaluation distinguishes between the **primary 11-case comparative benchmark** (executed by evaluate.py) and the **broader 18-capsule evidence archive** on disk (covering 16 distinct scenarios):

* **Primary Comparative Benchmark (11 cases)**: Evaluated directly in evaluate.py --changeproof vs evaluate.py --baseline, measuring Verified Safe Change Rate (VSCR) across canonical storms, holdouts, negative controls, and parameter variations.
* **Full Evidence Archive (18 capsules across 16 scenarios)**: Preserves sealed, hash-verified execution capsules for offline replay, including multi-framework generalization (FastAPI, Flask, Node.js Express), calibration bounds, and multi-attempt self-correction.

| Scenario Case | Target Service & Stack | Injected Fault | Pre-Patch Retries | Post-Patch Retries | Status | Replay Capsule |
|---|---|---|---|---|---|---|
| `case-01` | Checkout (FastAPI) | 1500ms on `payment-proxy` | **7.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-01.zip` |
| `case-self-correction-01` | Checkout (FastAPI) | 1500ms on `payment-proxy` | **7.0** retries/req | **0.0** retries/req | `PASS` | `capsules/case-self-correction-01.zip` |
| `case-10` | Checkout (FastAPI) | 1500ms on `payment-proxy` | **5.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-10.zip` |
| `case-alt-01` | Inventory (FastAPI) | 1500ms on `warehouse-proxy` | **7.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-alt-01.zip` |
| `case-framework-gen-01` | Flask Payment (Flask) | 1500ms on `flask-payment-proxy` | **7.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-framework-gen-01.zip` |
| `case-framework-gen-02` | Express Payment (Node.js) | 1500ms on `express-payment-proxy` | **7.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-framework-gen-02.zip` |
| `case-calib-01` | Checkout (FastAPI) | 50ms (sub-threshold fault) | **7.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-calib-01.zip` |
| `case-calib-02` | Checkout (FastAPI) | 1500ms (single-retry code) | **4.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-calib-02.zip` |
| `case-var-01` to `05` | Checkout (FastAPI) | Parameter variations | **4.0–7.0** retries/req| **1.0** retry/req | `PASS` | `capsules/case-var-01..05.zip` |
| `case-inconclusive-01` | Checkout (FastAPI) | 1500ms (boundary retry code) | **3.0** retries/req | **1.0** retry/req | `PASS` | `capsules/case-inconclusive-01.zip` |

---

## Topology Generalization: Point ChangeProof at Custom Services

ChangeProof does not rely on hardcoded container names. Point `ExperimentSynthesizer` at any multi-tier Docker Compose environment:

```python
from changeproof.experiment_synthesizer import ExperimentSynthesizer

# Point at an alternate topology (e.g., Inventory-Warehouse or Flask)
synth = ExperimentSynthesizer(
    compose_path="docker-compose.alt.yml",
    toxiproxy_config_path="toxiproxy_init.alt.json",
)
spec = synth.synthesize(pr_diff_text, case_id="custom-service-01")
print(f"Target Proxy: {spec['fault']['proxy']}")
print(f"Calibrated Latency: {spec['fault']['toxic']['attributes']['latency']}ms")
```

---

## Summary: Evidence Over Confidence

ChangeProof embodies a fundamental philosophy for AI-assisted software engineering:

> **An AI-generated patch is merely a hypothesis until the system produces empirical evidence that it survives real failure conditions.**

By separating LLM reasoning from deterministic verification, injecting genuine network faults via Toxiproxy, measuring Prometheus telemetry, and capturing evidence into tamper-evident reproduction capsules, ChangeProof moves software resilience from speculative code reviews to **reproducible, mathematical proof**.

