# ChangeProof — Autonomous Counterfactual Reliability Verification

ChangeProof is an automated reliability verification system for distributed cloud applications. When a software engineer submits a pull request that modifies retry limits, network timeouts, or client configurations, ChangeProof does not rely on static guesswork or unit tests to assess reliability. Instead, it spins up a sandboxed replica of the service topology, programmatically injects real downstream network latency via Toxiproxy, and directly measures whether the change causes a cascading failure storm before the code can be merged into production.

For systems engineers, ChangeProof replaces brittle staging environments and speculative code reviews with counterfactual empirical proof. It dynamically extracts dependency graphs from container definitions, synthesizes calibrated network failure scenarios, executes reproducible traffic workloads, and evaluates deterministic, zero-LLM verification assertions. If a proposed change amplifies traffic or violates organizational governance policies, ChangeProof synthesizes a minimally disruptive remediation patch, verifies that the fix survives the exact same failure scenario, and packages the complete verification artifact into an independently replayable, cryptographically signed capsule.

> 📋 **Submission Status & Verification Evidence**: [`docs/SUBMISSION_STATUS.md`](docs/SUBMISSION_STATUS.md)  
> 🔬 **Confounded Multi-Signal Analysis**: [`docs/CHALLENGING_CASE.md`](docs/CHALLENGING_CASE.md)  
> 📊 **Evaluation Benchmark Report**: [`evaluation_report.md`](evaluation_report.md)  
> 📜 **Complete Project Audit Log**: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

---

## The Core Idea: How ChangeProof Works

Consider a common production incident: a developer modifies an API client configuration in an e-commerce checkout service, increasing `RETRIES_MAX` from 2 to 8, reducing `RETRY_TIMEOUT_SECONDS` from 1.0s to 0.4s, and removing backoff (`RETRY_BACKOFF_FACTOR = 0.0`). Under normal conditions in local unit tests, this change appears harmless. But in production, if downstream payment processing experiences momentary latency, every incoming checkout request immediately fires eight back-to-back requests, rapidly saturating the payment tier in an exponential retry storm.

ChangeProof intercepts this pull request in CI and runs a complete counterfactual evaluation trajectory (demonstrated live in `case-self-correction-01`):

1. **Risk Assessment & Synthesis**: ChangeProof detects aggressive retry parameters and stored policy violations via deterministic AST analysis. It analyzes `docker-compose.yml` and `toxiproxy_init.json` to identify the downstream dependency (`payment-proxy`) and entrypoint (`POST /checkout`), and computes a calibrated fault latency of $1500\text{ms}$.
2. **Empirical Reproduction**: It brings up the isolated topology, injects $1500\text{ms}$ latency via Toxiproxy, and drives 150 concurrent requests. The broken code amplifies traffic to **7.0 retries per request** ($1259.6\text{ retries/min}$), reproducing the failure condition.
3. **Attempt 1 Patch Synthesis & Deterministic Failure**: An LLM proposes an initial patch that naively reduces `RETRIES_MAX` to 3 but leaves the aggressive 0.4s timeout and zero backoff unchanged. ChangeProof applies the patch and re-runs the workload. The deterministic verifier evaluates the safety contract (`retries_per_request <= 1.1`) and records **2.0 retries per request**, immediately issuing a **`[FAIL]`** verdict.
4. **Agentic Self-Correction Loop**: Rather than aborting or substituting hardcoded constants, ChangeProof feeds the empirical failure telemetry back to the model. The model diagnoses why its fix was insufficient (*"retaining a 0.4s timeout caused premature aborts on 1500ms latency, triggering rapid retries without backoff spacing"*) and synthesizes a revised patch: `RETRIES_MAX = 1`, `TIMEOUT = 1.5s`, `BACKOFF = 0.5`.
5. **Verified Resolution & Capsule Packaging**: ChangeProof applies Attempt 2 and re-executes the workload. Retries drop to **0.0 retries per request** ($100\%$ success within the extended timeout), satisfying the verification assertion and yielding a **`[PASS]`** verdict. The full trajectory, diffs, metrics, and logs are sealed into `capsules/case-self-correction-01.zip`.

---

## Key Capabilities

- **Real Fault Injection via Toxiproxy (Not Simulated Mocks)**: Injects real downstream network latency into TCP proxy streams rather than mocking HTTP responses (*see `docs/SUBMISSION_STATUS.md`, `case-01`, `case-10`*).
- **Deterministic, Zero-LLM Verification**: The pass/fail decision is decided exclusively by `verifier.py` against mathematical bounds on Prometheus metric deltas ($\Delta\text{retries} / \Delta\text{requests} \le 1.1$). No LLM participates in the verification verdict (*see `tests/unit/test_verifier.py`*).
- **LLM-Grounded Reasoning with Transparent Provenance**: Hypotheses and patch proposals are reasoned dynamically by Gemini with fallbacks to OpenAI/Anthropic and deterministic templates. Grounding was validated across Python/FastAPI, Python/Flask, and Node.js/Express, addressing an early review finding where static templates were replaced with real model calls (*see `changeproof/llm_client.py`, `tests/unit/test_hypothesis_evaluator.py`*).
- **Iterative Self-Correction Feedback Loop**: When an initial patch fails verification, observed runtime metrics are fed back to the model for diagnosis and parameter revision within a bounded 2-attempt budget (*see `capsules/case-self-correction-01.zip`, `tests/unit/test_self_correction.py`*).
- **Topology-Agnostic Experiment Synthesis**: Synthesizes fault topologies automatically from container configurations across disparate architectures and distinct proxy routes (`payment-proxy`, `warehouse-proxy`, `flask-payment-proxy`, `express-payment-proxy`) (*see `capsules/case-alt-01.zip`, `capsules/case-framework-gen-01.zip`, `capsules/case-framework-gen-02.zip`*).
- **Cryptographic 3-Layer Evidence Integrity**: Reproduction capsules enforce immutability through SHA-256 spec hashes, individual raw evidence hashes, and mathematical cross-validation of manifest claims against raw CSV telemetry (*see `scripts/demo_tamper_detection.sh`*).
- **Human Approval Gate & Organizational Policy Learning**: ChangeProof never autonomously merges code to production. Human reliability policies recorded during review are persisted in `policy_store.json` and deterministically enforced on all future PRs (*see `policy_store.json`, `tests/unit/test_human_approval_gate.py`, `tests/unit/test_policy_governance.py`*).
- **Calibrated Fault Magnitude**: Fault latency is calibrated to service parameters using the formula $L_{\text{fault}} = \max(2 \times T_{\text{timeout}}, 1500\text{ms})$, validated across held-out timeout parameters ($0.3\text{s}$ and $1.3\text{s}$) never used during derivation (*see `capsules/case-calib-01.zip`, `capsules/case-calib-02.zip`*).

---

## Quickstart Guide

### 1. Clone & Environment Setup

```bash
# 1. Clone the repository
git clone https://github.com/goodmorningsaksham/ChangeProof.git
cd ChangeProof

# 2. Create and activate a clean virtual environment
python -m venv .venv

# On Linux / macOS (bash / zsh):
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. Install dependencies and local editable package
pip install -r requirements.txt
pip install -e .
```

#### Optional: Enable Live LLM Reasoning
ChangeProof includes a deterministic fallback chain that runs completely offline without external credentials. To enable live Gemini reasoning for hypothesis generation and patch diagnosis, export your API key:
```bash
# On Linux / macOS:
export GEMINI_API_KEY="your-api-key"

# On Windows (PowerShell):
$env:GEMINI_API_KEY = "your-api-key"
```

> **Note on Setup Timing**: First-time Docker runs require pulling base images (`python:3.11-slim`, `ghcr.io/shopify/toxiproxy`), which adds initial network download time beyond the steady-state runtime benchmarks reported in `docs/SUBMISSION_STATUS.md`.

### 2. Standalone Capsule Replay (Zero Docker Required)

Verify any historical or CI-executed experiment in under 2 seconds:

```bash
python -m changeproof.replay capsules/case-01.zip
python -m changeproof.replay capsules/case-10.zip
python -m changeproof.replay capsules/case-alt-01.zip
python -m changeproof.replay capsules/case-framework-gen-02.zip
python -m changeproof.replay capsules/case-self-correction-01.zip
```

### 3. Single-Command Evaluation Runners

```bash
# Run baseline evaluation across 11 cases
python evaluate.py --baseline

# Run ChangeProof verified evaluation across 11 cases
python evaluate.py --changeproof
```

### 4. Run Live Counterfactual Investigation on Docker (Local CI Entrypoint)

ChangeProof's unified production CI engine runs locally with a single command on any PR diff:

```bash
# Run full live synthesis, fault injection, baseline measurement, remediation, and verification
python -m changeproof.cli_synth_verify --diff evaluation/cases/case_01_pr.diff
```

This single command autonomously:
1. Performs static risk assessment on the diff and queries organizational policy constraints.
2. Dynamically resolves service topology, fault proxies (`payment-proxy`), entrypoints (`POST /checkout`), and calibrated latency ($2000\text{ms}$) from `docker-compose.yml` and `toxiproxy_init.json`.
3. Provisions Docker containers and Toxiproxy proxy routes.
4. Injects calibrated downstream latency and executes baseline workload ($150$ requests @ $10$ concurrency).
5. Generates and applies the remediation patch to `app/checkout/main.py`.
6. Executes post-patch workload and evaluates deterministic assertions ($> 2.0$ pre $\rightarrow \le 1.1$ post).
7. Emits the markdown **Proof Certificate** (`runs/ci_run/proof_certificate.md`) and self-contained **Reproduction Capsule** (`runs/ci_run/capsules/*.zip`).

---

## Try the Tamper-Detection Demo

Reproduction capsules are tamper-evident. If any party modifies a single value in `manifest.json`, edits `experiment.yaml`, or manipulates raw telemetry CSVs, ChangeProof detects the cryptographic or telemetric discrepancy and fails loudly rather than silently accepting corrupted data.

Run the automated ~20-second tamper detection demonstration:

```bash
# On Linux / macOS:
bash scripts/demo_tamper_detection.sh

# On Windows (PowerShell):
powershell -ExecutionPolicy Bypass -File scripts/demo_tamper_detection.ps1
```

The script extracts `capsules/case-01.zip`, alters `retries_per_request` in `manifest.json` from `7.0` to `3.0`, re-archives the capsule, and runs `replay.py`. It demonstrates an immediate `TAMPER_DETECTED` exit code `1` on the modified archive, followed by a clean `[PASS]` on the untouched original capsule.

---

## Topology Generalization: Point ChangeProof at Your Own Services

ChangeProof does not rely on hardcoded service names or single-language stacks. Point `ExperimentSynthesizer` at any multi-tier Docker Compose environment across FastAPI (Python), Flask (Python), or Express (Node.js):

```python
from changeproof.experiment_synthesizer import ExperimentSynthesizer

# Point at your custom service stack (proven across 3 distinct frameworks and topologies)
synth = ExperimentSynthesizer(
    compose_path="docker-compose.alt.yml",
    toxiproxy_config_path="toxiproxy_init.alt.json",
)
spec = synth.synthesize(pr_diff, case_id="custom-service-01")
print(f"Target Proxy: {spec['fault']['proxy']}")
print(f"Calibrated Latency: {spec['fault']['toxic']['attributes']['latency']}ms")
```

---

## Full Case Inventory & Evaluation

The repository contains 18 capsule archives on disk representing 16 distinct evaluation scenarios (15 executed reproduction capsules covering canonical storms, holdout parameters, multi-framework topology variations, calibration bounds, negative controls, and multi-attempt self-correction, plus `case-05` as a static negative control). An additional 7 speculative failure modes (`case-02`, `case-03`, `case-04`, `case-06`, `case-07`, `case-08`, `case-09`) are documented as unexecuted in `docs/SUBMISSION_STATUS.md`.

For complete parameter specifications, measured pre/post metrics, and comparative baseline benchmarks, refer to:
- [`docs/SUBMISSION_STATUS.md`](docs/SUBMISSION_STATUS.md) — Comprehensive case inventory, evidence matrix, and verified safe change rates.
- [`evaluation_report.md`](evaluation_report.md) — Primary comparative evaluation report.
- [`docs/CHALLENGING_CASE.md`](docs/CHALLENGING_CASE.md) — In-depth analysis of confounded multi-signal attribution.

---

## The Audit Trail: Engineering Honesty & Verification Discipline

The core thesis of ChangeProof is that software safety claims must rest on reproducible, deterministic evidence rather than self-reported confidence. Throughout the development of this project, we maintained strict auditing discipline:

1. **Retry Callback Guard Fix**: Discovered that an upstream callback guard (`attempt_number > 1`) silently dropped the first retry of each request, undercounting retries across the suite. We refactored the counting hook to `attempt_number >= 1`, added regression tests, and re-executed all evaluation runs.
2. **Template-to-LLM Transition**: External code review revealed that hypothesis and patch generation initially utilized static template mappings. We replaced this with a structured Gemini/OpenAI fallback pipeline and proved genuine multi-language reasoning across three live repositories.
3. **Agent Regression Table Audit**: Caught an agent hallucination during a late session where a regression summary table was generated without reading actual replay outputs. We rejected the summary, added strict single-command replay logging, and documented the incident transparently.

The complete, unedited record of all architectural decisions, bug fixes, and calibration audits is preserved in [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

---

## Automated Test Suite & Quality Gate

```bash
# Run full unit test suite (61 tests covering synthesis, verifier safety, tamper detection, and governance)
python -m pytest tests/unit/ -v

# Run linters and static type checker
python -m ruff check changeproof/ tests/ scripts/ evaluation/
python -m mypy changeproof/ --ignore-missing-imports
```
