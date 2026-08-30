# ChangeProof — Autonomous Counterfactual Reliability Verification

ChangeProof is an agentic reliability verification engine for distributed cloud services. When a developer submits a pull request touching retry limits, timeouts, or network client configurations, ChangeProof:
1. **Assesses Risk**: Flags critical AST signals and stored organizational policy violations.
2. **Synthesizes Counterfactual Experiments**: Dynamically analyzes the multi-service dependency topology (e.g. `docker-compose.yml` and `toxiproxy_init.json`) to resolve fault proxies, entrypoints, and calibrated latency parameters.
3. **Reproduces Storms Under Faults**: Injects calibrated network latency via Toxiproxy to empirically observe failure loops.
4. **Verifies Remediation Patches**: Generates minimal code fixes and re-runs deterministic assertions (`retries_per_request <= 1.1`).
5. **Packages Cryptographic Capsules**: Emits standalone `.zip` reproduction capsules replayable without Docker.

> 📋 **Authoritative Submission Status**: [`docs/SUBMISSION_STATUS.md`](docs/SUBMISSION_STATUS.md)  
> 📋 **Designated Challenging Case**: [`docs/CHALLENGING_CASE.md`](docs/CHALLENGING_CASE.md)  
> 📋 **Benchmark Report**: [`evaluation_report.md`](evaluation_report.md)

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

### 2. Standalone Capsule Replay (Zero Docker Required)

Verify any historical or CI-executed experiment in under 2 seconds:

```bash
python -m changeproof.replay capsules/case-01.zip
python -m changeproof.replay capsules/case-10.zip
python -m changeproof.replay capsules/case-alt-01.zip
python -m changeproof.replay capsules/case-framework-gen-02.zip
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
1. Performs static risk assessment on the diff.
2. Dynamically resolves service topology, fault proxies (`payment-proxy`), entrypoints (`POST /checkout`), and calibrated latency ($2000\text{ms}$) from `docker-compose.yml` and `toxiproxy_init.json`.
3. Provisions Docker containers and Toxiproxy proxy routes.
4. Injects calibrated downstream latency and executes baseline workload ($150$ requests @ $10$ concurrency).
5. Generates and applies the minimal remediation patch to `app/checkout/main.py`.
6. Executes post-patch workload and evaluates deterministic assertions ($> 2.0$ pre $\rightarrow \le 1.1$ post).
7. Emits the markdown **Proof Certificate** (`runs/ci_run/proof_certificate.md`) and self-contained **Reproduction Capsule** (`runs/ci_run/capsules/*.zip`).

---

## Topology Generalization: Point ChangeProof at Your Own Services

ChangeProof does not rely on hardcoded service names. Point `ExperimentSynthesizer` at any multi-tier Docker Compose environment:

```python
from changeproof.experiment_synthesizer import ExperimentSynthesizer

# Point at your custom service stack (proven on gateway -> inventory -> warehouse in CASE-ALT-01)
synth = ExperimentSynthesizer(
    compose_path="docker-compose.alt.yml",
    toxiproxy_config_path="toxiproxy_init.alt.json",
)
spec = synth.synthesize(pr_diff, case_id="custom-service-01")
print(f"Target Proxy: {spec['fault']['proxy']}")
print(f"Calibrated Latency: {spec['fault']['toxic']['attributes']['latency']}ms")
```

---

## Automated Test Suite & Quality Gate

```bash
python -m pytest tests/ -v
python -m ruff check changeproof/ tests/ evaluation/
python -m mypy changeproof/ --ignore-missing-imports
```
