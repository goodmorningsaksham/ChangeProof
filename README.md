# ChangeProof — Autonomous Counterfactual Reliability Verification

ChangeProof is an agentic reliability verification engine for distributed cloud services. When a developer submits a pull request touching retry limits, timeouts, or network client configurations, ChangeProof:
1. **Assesses Risk**: Flags critical AST signals and stored organizational policy violations.
2. **Synthesizes Counterfactual Experiments**: Dynamically analyzes the multi-service dependency topology (e.g. `docker-compose.yml` and `toxiproxy_init.json`) to resolve fault proxies, entrypoints, and calibrated latency parameters.
3. **Reproduces Storms Under Faults**: Injects calibrated network latency via Toxiproxy to empirically observe failure loops.
4. **Verifies Remediation Patches**: Generates minimal code fixes and re-runs deterministic assertions (`retries_per_request <= 1.1`).
5. **Packages Cryptographic Capsules**: Emits standalone `.zip` reproduction capsules replayable without Docker.

> 📌 **Authoritative Submission Status**: [`docs/SUBMISSION_STATUS.md`](docs/SUBMISSION_STATUS.md)  
> 📌 **Designated Challenging Case**: [`docs/CHALLENGING_CASE.md`](docs/CHALLENGING_CASE.md)  
> 📌 **Benchmark Report**: [`evaluation_report.md`](evaluation_report.md)

---

## Benchmark Highlights (11 Real Executed Cases)

- **Verified Safe Change Rate (VSCR)**: **`100.0%`** (11 / 11 executed cases proven safe vs. Baseline **`N/A`**)
- **Risk Detection Accuracy**: **`100.0%`** (11 / 11 correct on both systems)
- **Failure Reproduction Rate**: **`100.0%`** (10 / 10 unsafe PRs reproduced live)
- **Independent Capsule Replay**: **`100.0%`** (All 11 executed capsules pass byte-perfect verification)

---

## Quickstart Guide

### 1. Clone & Environment Setup

```bash
git clone https://github.com/goodmorningsaksham/ChangeProof.git
cd ChangeProof
pip install -r requirements.txt
```

### 2. Standalone Capsule Replay (Zero Docker Required)

Verify any historical or CI-executed experiment in under 2 seconds:

```bash
python changeproof/replay.py capsules/case-01.zip
python changeproof/replay.py capsules/case-10.zip
python changeproof/replay.py capsules/case-alt-01.zip
```

### 3. Single-Command Evaluation Runners

```bash
# Run baseline evaluation across 11 cases
python evaluate.py --baseline

# Run ChangeProof verified evaluation across 11 cases
python evaluate.py --changeproof
```

### 4. Run Live Counterfactual Investigation on Docker

```bash
# 1. Start the target service stack
docker compose up -d

# 2. Run investigation on a PR diff
python changeproof/cli.py run --pr tests/fixtures/case_01_diff.patch
```

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

## Human Engineering Governance & Policy Store

Record human review verdicts on proof certificates and enforce pre-commit rules on future PRs:

```bash
# Record an approved decision with organizational policy learning
python changeproof/cli.py decide \
  --cert runs/ci_run/proof_certificate.md \
  --decision APPROVED \
  --author "Saksham (Reliability Lead)" \
  --rationale "Empirically verified retry storm suppression (7.0 -> 1.0) under 1500ms latency" \
  --policy-rule "payment-service retries must not exceed 4"
```

Subsequent PRs violating stored policies will automatically trigger `Stored Human Policy Violation` risk signals.

---

## Running Tests & Quality Gate

```bash
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python -m ruff check changeproof/ tests/ evaluation/
PYTHONPATH=. python -m mypy changeproof/ --ignore-missing-imports
```