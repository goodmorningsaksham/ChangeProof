# ChangeProof: Representative Agent Trajectories (Deliverable 04)

This document indexes and explains the **genuine, unedited agent trajectory artifacts** recorded during ChangeProof execution runs, and maps all hackathon deliverables to their canonical submission paths.

---

## Hackathon Deliverables Mapping

| Hackathon Deliverable | Canonical Submission Artifacts & Documentation |
|---|---|
| **Deliverable 01: Complete Solution Code & Changelog** | • Full source code: [`changeproof/`](../changeproof/), [`app/`](../app/), [`docker-compose.yml`](../docker-compose.yml)<br>• Agent instructions: [`changeproof/agent.py`](../changeproof/agent.py)<br>• Improvement changelog & audit trail: [`docs/CHANGELOG.md`](CHANGELOG.md) |
| **Deliverable 02: Clean-Environment Reproduction Guide** | • Canonical reproduction guide: [`README.md`](../README.md)<br>• Covers setup, dependencies, optional API keys, exact single-command replay, live Docker reproduction, runtime benchmarks, and tamper detection. |
| **Deliverable 04: Representative Agent Trajectories** | • Primary Tool-Calling Trajectory: [`runs/case-10_agent_run/agent_trajectory.jsonl`](../runs/case-10_agent_run/agent_trajectory.jsonl)<br>• Iterative Self-Correction Trajectory: [`capsules/case-self-correction-01.zip`](../capsules/case-self-correction-01.zip)<br>• Trajectory documentation & analysis: [`docs/AGENT_TRAJECTORIES.md`](AGENT_TRAJECTORIES.md) |

---

## 1. Primary Tool-Call Trajectory: Case-10 Autonomous Investigation

* **Artifact Path**: [`runs/case-10_agent_run/agent_trajectory.jsonl`](../runs/case-10_agent_run/agent_trajectory.jsonl)
* **Agent Identity & Role**: ChangeProof Reliability Investigator Agent (`changeproof/agent.py`)
* **System Prompt / Instructions**: Preserved in [`changeproof/agent.py`](../changeproof/agent.py) (lines 14–31):
  ```text
  You are the ChangeProof Reliability Investigator Agent.
  Your role is to evaluate high-risk code changes by constructing counterfactual experiments,
  reproducing failures under real faults, generating minimal remediation patches, and replaying experiments.

  You have access to 8 engineering tools:
  1. read_file(path)
  2. read_topology()
  3. read_runtime_snapshot()
  4. propose_hypothesis(hypotheses)
  5. run_experiment(spec)
  6. read_metrics(run_id)
  7. write_patch(diff)
  8. run_tests()

  Rules:
  - Form hypotheses grounded in code, topology, and metrics.
  - Execute experiments via run_experiment(spec) to test failure hypotheses.
  - Propose minimal code patches for reproduced failures.
  - You propose; the deterministic verifier decides.
  ```

### Step-by-Step Trajectory Record

The JSONL artifact records the 10 sequential execution steps of a full autonomous investigation on PR diff `case-10`:

| Step # | Action Type | Action Details & Grounding |
|---|---|---|
| **Step 1** | `CONTEXT_INGESTION` | Ingests PR diff changing `app/checkout/main.py` (`RETRIES_MAX: 3 -> 6`, `TIMEOUT: 1.0s -> 0.6s`, `BACKOFF: 0.5 -> 0.0`). |
| **Step 2** | `RISK_ASSESSMENT` | Computes deterministic risk score: **105/100 (HIGH)**; identifies stored human policy violation (`POL-1788006970`: retries > 4). |
| **Step 3** | `READ_TOPOLOGY` | Tool call discovers active container topology (`payment-service`, `toxiproxy`, `checkout-service`, `frontend-service`, `prometheus`, `payment-proxy`). |
| **Step 4** | `PROPOSE_HYPOTHESES` | Generates 3 multi-signal grounded hypotheses: `H-RETRY-CEILING` (retry storm), `H-NO-BACKOFF` (burst concentration), `H-AGGRESSIVE-TIMEOUT` (premature timeout). |
| **Step 5** | `TOOL_CALL` (`run_experiment`) | Executes BASE workload under $3500\text{ms}$ Toxiproxy downstream latency on `payment-proxy` (610 requests @ 15 VUs). |
| **Step 6** | `OBSERVE_METRICS` | Collects Prometheus delta metrics: **5.0 retries/request** ($3513.55\text{ retries/min}$) $\rightarrow$ `FAILURE_REPRODUCED`. |
| **Step 7** | `PROPOSE_PATCH` | Synthesizes remediation patch: `RETRIES_MAX = 2`, `RETRY_TIMEOUT_SECONDS = 1.0`, `RETRY_BACKOFF_FACTOR = 0.5`. |
| **Step 8** | `TOOL_CALL` (`run_experiment`) | Rebuilds container and executes PATCHED workload under the identical $3500\text{ms}$ fault (730 requests @ 15 VUs). |
| **Step 9** | `DETERMINISTIC_VERIFICATION` | Verifier evaluates mathematical assertions: pre-patch $5.0 > 2.0$ (`YES`), post-patch $1.0 \le 1.1$ (`YES`) $\rightarrow$ **`[PASS]`**. |
| **Step 10** | `HUMAN_CHECKPOINT` | Emits Proof Certificate and halts with status **`AWAITING_HUMAN_DECISION`** (agent cannot self-merge). |

> **Note on Historical Path in JSONL Step 10**:
> In line 10 of `runs/case-10_agent_run/agent_trajectory.jsonl`, the entry records `certificate_path: "runs/case-10_run/proof_certificate.md"`. This is an authentic historical run directory reference from the original execution session. In this submission package, the canonical sealed evidence is packaged in [`capsules/case-10.zip`](../capsules/case-10.zip) and the reference CI certificate is at [`runs/ci_run/proof_certificate.md`](../runs/ci_run/proof_certificate.md). The raw JSONL file is intentionally preserved unmodified as unedited historical evidence.

---

## 2. Iterative Self-Correction Trajectory: Case-Self-Correction-01

* **Artifact Path**: [`capsules/case-self-correction-01.zip`](../capsules/case-self-correction-01.zip)
* **Agent Role**: Adaptive Remediation Agent (`changeproof/cli_synth_verify.py` / `diagnose_and_revise_patch`)
* **Evidence Format**: Sealed multi-attempt reproduction capsule containing `manifest.json`, before/after diffs (`patch_attempt_1.diff`, `patch_attempt_2.diff`), and per-attempt Prometheus metric CSVs (`metrics_post_attempt_1.csv`, `metrics_post_attempt_2.csv`).

### Multi-Attempt Remediation Trajectory

```text
  [ PR Diff Ingestion: RETRIES_MAX = 8, TIMEOUT = 0.4s, BACKOFF = 0.0 ]
                                 │
                                 ▼
           [ BASE Workload: 7.0 retries/req storm confirmed ]
                                 │
                                 ▼
                     ───► [ Attempt 1 Proposal ]
                     │    Proposed: RETRIES_MAX = 3, TIMEOUT = 0.4s, BACKOFF = 0.0
                     │    Runtime Result: 2.0 retries/req (946.78/min)
                     │    Deterministic Verifier: [FAIL] (2.0 > 1.1 threshold)
                     │           │
                     │           ▼
                     │    [ Telemetry Feedback Loop ]
                     │    Model ingests: "Attempt 1 failed because RETRIES_MAX was still
                     │    set too high (3) and RETRY_BACKOFF_FACTOR was 0.0..."
                     │           │
                     └─── [ Attempt 2 Proposal ]
                          Proposed: RETRIES_MAX = 1, TIMEOUT = 1.5s, BACKOFF = 0.5
                          Runtime Result: 0.0 retries/req (0.0/min, 100% success)
                          Deterministic Verifier: [PASS] (0.0 <= 1.1 threshold)
                                 │
                                 ▼
                  [ Proof Certificate & Capsule Sealed ]
```

### Replay Command (Zero Docker Required)
Judges can verify this complete multi-attempt trajectory in $<1.0\text{s}$:
```bash
python -m changeproof.replay capsules/case-self-correction-01.zip
```
