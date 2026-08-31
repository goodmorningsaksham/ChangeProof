# AGENTS.md — ChangeProof Operating Contract

> This file is the permanent operating contract for every coding agent working on this
> repository. Read it before reading anything else. Read it completely.

---

## 1. Source of Truth Hierarchy

When sources conflict, respect this order and **stop if ambiguous**:

1. Human-approved decisions in `docs/ChangeProof-Spec-v1.1.md`
2. Human-approved `docs/Architecture-Decision-Report-v1.2.md`
3. Human-approved ADRs and `DECISIONS.md` (when they exist)
4. Current implementation
5. Agent assumptions — **lowest authority; never self-authorising**

**If any two sources conflict: stop and request human clarification.**
An agent must never treat its own previous output as authoritative.

---

## 2. What ChangeProof Is

ChangeProof is an agentic reliability system that makes a high-risk code change
**prove itself** before production.

It does not review what code says. It constructs experiments to discover what the
system actually does under failure conditions, then proves whether the generated
fix works.

**Core loop**:
```
PR → Risk Assessment → Context → Counterfactual Hypothesis →
Executable Experiment → Real Failure Reproduction →
Coding-Agent Remediation → Exact Replay →
Independent Deterministic Verification →
Proof Certificate / Reproduction Capsule →
Human Decision → Policy Learning
```

**MVP focus**: ONE fully real, end-to-end, retry-amplification failure workflow.
One complete provable loop beats breadth every time.

---

## 3. Optimization Targets

Optimize for, in order:

1. Correctness
2. Reproducibility
3. Deterministic verification
4. Demonstrability
5. Maintainability
6. Honest evidence

Do **not** optimize for architectural sophistication, scale, or impressiveness.

---

## 4. Approved Architecture

The following components are approved. Do not add to this list without human approval.

| Component | Technology | Notes |
|-----------|-----------|-------|
| Target application | 3× FastAPI services | `frontend` → `checkout` → `payment` |
| Runtime | Docker Compose | NOT Kubernetes |
| Fault injection | Toxiproxy | Network-level; REST API controlled |
| Load generation | k6 | Declarative JS; script is part of capsule |
| Metrics collection | Prometheus | 1s scrape; saved to CSV as evidence |
| Risk Assessor | Deterministic Python | AST + grep; no LLM |
| Context Builder | Deterministic Python | Parses docker-compose.yml → topology JSON |
| Primary agent | One LLM + thin tool-call loop | Direct API; no framework |
| Agent tools | 8 Python functions | See §6 |
| Experiment spec | `experiment.yaml` (YAML) | Immutable once execution begins |
| Experiment Runner | `run_experiment.py` | Python orchestrator; no workflow engine |
| Deterministic Verifier | Pure Python | Zero LLM; evaluates metric assertions |
| Proof Certificate | Jinja2 → Markdown/HTML | No React dashboard |
| Reproduction Capsule | Python zipfile + manifest | See §9 |
| Replay | `replay.py` | Reads capsule; verifies spec hash |
| Policy Store | `policy_store.json` | Append-only JSON; human decisions only |
| Human Decision UI | CLI prompt | No autonomous production action |
| Baseline runner | Subset workflow | No fault injection; same LLM |
| Evaluation suite | 10 YAML case files | Fixed; CASE-10 sealed |

### 4.1 Not Part of the Approved MVP

Agents must **not** introduce any of the following without explicit written human
approval:

- Kubernetes, k3s, kind, or any cluster orchestration
- LangGraph, LangChain, or any agent orchestration framework
- Multi-agent or multi-LLM orchestration
- Any SQL or NoSQL database
- React, Next.js, or any frontend framework for dashboards
- Temporal, Airflow, or any workflow engine
- OpenTelemetry (approved only as optional, not required)
- Grafana (approved only as optional, not required)
- Chaos Mesh, Chaos Monkey, or any Kubernetes chaos tool
- Any new Python dependency not already in the project

---

## 5. Repository Structure

> **Note**: This map will be updated as implementation progresses.
> Do not assume a directory exists before verifying with the filesystem.

```
proofchange/
├── AGENTS.md                    ← this file
├── DECISIONS.md                 ← architecture decision records (when created)
├── docs/
│   ├── ChangeProof-Spec-v1.1.md      ← canonical specification
│   └── Architecture-Decision-Report-v1.2.md  ← approved architecture
├── app/                         ← target application (3 FastAPI services)
│   ├── frontend/
│   ├── checkout/
│   └── payment/
├── changeproof/                 ← ChangeProof system source
│   ├── risk_assessor.py
│   ├── context_builder.py
│   ├── agent.py
│   ├── tools.py
│   ├── experiment_runner.py
│   ├── verifier.py
│   ├── certificate.py
│   ├── capsule.py
│   ├── replay.py
│   └── policy_store.py
├── evaluation/
│   ├── cases/
│   │   ├── case_01.yaml ... case_09.yaml
│   │   └── case_10.yaml        ← SEALED; do not read until final evaluation
│   ├── run_baseline.py
│   ├── run_advanced.py
│   └── evaluate.py
├── runs/                        ← experiment run outputs (gitignored if large)
├── capsules/                    ← reproduction capsule archives
├── policy_store.json            ← human policy decisions
├── docker-compose.yml           ← canonical topology; source of dependency graph
├── Makefile                     ← make test, make eval, make demo
└── tests/
    ├── unit/
    └── integration/
```

---

## 6. Agent Tools

The primary agent is permitted to call exactly these tools:

| Tool | What it does |
|------|-------------|
| `read_file(path)` | Read source files from the repository |
| `read_topology()` | Parse docker-compose.yml → service dependency JSON |
| `read_runtime_snapshot()` | Fetch current Prometheus metric values |
| `propose_hypothesis(hypotheses)` | Log ranked candidate hypotheses with grounding |
| `run_experiment(spec)` | Execute one experiment run; returns run_id |
| `read_metrics(run_id)` | Retrieve saved metrics CSV as JSON |
| `write_patch(diff)` | Apply a unified diff to the repository |
| `run_tests()` | Run unit and integration tests; return pass/fail |

Agents must not invoke shell commands, make network calls, or access the filesystem
through any mechanism other than these tools unless the task explicitly requires it
and the action is outside the experiment loop.

---

## 7. Agent Reasoning Rules

Agents **must**:

1. Read this file first and completely.
2. Read the relevant `docs/` files before modifying code.
3. Inspect the existing implementation before making assumptions about structure.
4. Prefer existing patterns over introducing new ones.
5. Keep changes narrowly scoped to the stated task.
6. Plan non-trivial changes before writing code — summarize the plan; wait if asked.
7. Distinguish facts from assumptions; label assumptions explicitly.
8. Ask when an important decision is ambiguous or unresolved.
9. Report what commands were run and what the output was.
10. Never claim tests passed without actually running them.

Agents **must not**:

- Refactor code unrelated to the current task.
- Upgrade dependencies without documented justification.
- Introduce infrastructure components not on the approved list.
- Modify evaluation case files to make the system pass them.
- Weaken verification criteria or assertion thresholds to obtain PASS.
- Fabricate evidence, metrics, or test results.
- Silently redesign architecture.
- Treat absence of an explicit prohibition as permission.

---

## 8. Human Approval Gates

**Stop and request human approval before doing any of the following**:

- Changing the approved architecture or adding to §4
- Adding any dependency not already in the project
- Changing a public interface used by more than one component
- Changing the semantics of an ExperimentSpec field
- Changing the semantics of a verification assertion
- Changing calibrated verification thresholds after they have been set
- Changing the risk-scoring methodology or thresholds after calibration
- Opening, reading, or using CASE-10 holdout parameters before final evaluation
- Changing any baseline fairness condition (§10)
- Changing the policy_store.json schema in a way that affects evaluation
- Weakening any safety or verification condition for any reason
- Making a consequential product decision not explicitly covered by docs/

When in doubt: stop and ask. Do not proceed on a guess.

---

## 9. Experiment Rules

Experiments are evidence-producing operations. They are not throwaway scripts.

### 9.1 Spec Immutability

The `experiment.yaml` becomes **immutable** the moment Phase 2 (PROVISION) begins.

- `run_experiment.py` computes and records `spec_sha256` in the run manifest
  before starting Docker Compose.
- Any attempt to write to `experiment.yaml` after this point must abort with
  `INCONCLUSIVE`.
- `replay.py` verifies `spec_sha256` before replaying. If the hash does not match,
  it must abort.

**Never modify an experiment specification after execution to improve its result.**

### 9.2 Evidence Preservation

Every experiment run must preserve:

- `experiment.yaml` (with recorded hash)
- `metrics_pre.csv` or `metrics_post.csv` (raw metric series)
- `fault.json` (exact Toxiproxy configuration applied)
- `workloads/checkout_load.js` (verbatim workload script)
- `agent_trajectory.jsonl` (full tool-call trace)
- Timestamps for each phase
- Git commit SHA of the target application (base state)
- `patch.diff` if a patch was applied (patched state)

### 9.3 Inconclusive Preference

If evidence is insufficient to support a conclusion:

```
Result: INCONCLUSIVE
Reason: <specific reason>
Recommendation: human investigation required
```

**Do not convert INCONCLUSIVE into PASS through reasoning, narrative, or retries.**

---

## 10. Verification Rules

The deterministic verifier (`verifier.py`) is the **sole authority** for safety
verification. It contains zero LLM calls.

The LLM **may**:
- Propose hypotheses grounded in code, topology, and runtime evidence
- Reason about metric observations
- Propose patches
- Suggest remediation strategies

The LLM **may not**:
- Declare a patch safe
- Override a FAIL verdict
- Convert INCONCLUSIVE to PASS through argument

### 10.1 What Verification Evaluates

The verifier evaluates **assertions from `experiment.yaml`** against metric
aggregates — not raw numeric equality between runs.

- **Pre-patch assertions** must evaluate to FAIL (failure was reproduced).
- **Post-patch assertions** must evaluate to PASS (fix was verified).
- If pre-patch does not FAIL: result is INCONCLUSIVE.

### 10.2 Threshold Calibration

Assertion threshold values are **calibration parameters**, not architectural
constants. They are determined empirically after Week 1 experiments.

- Thresholds must be calibrated against real experimental observations.
- Once calibrated and recorded, they require human approval to change.
- The calibration and its rationale must be recorded in the improvement changelog.

---

## 11. Reproduction Rules

The Reproduction Capsule must support clean-environment replay by a person who
was not involved in the original run.

### 11.1 Two Named States

| State | Definition |
|-------|-----------|
| **BASE STATE** | Repository at the PR commit under evaluation, before any patch. This is the state in which failure is reproduced. |
| **PATCHED STATE** | Base state with `patch.diff` applied. This is the state that must survive the same experiment. |

The experiment specification is **identical** for both states. The only variable
is the target application code.

### 11.2 Image Reproducibility Tiers

| Tier | Images | Guarantee |
|------|--------|-----------|
| **Tier 1 — Infrastructure** | Toxiproxy, Prometheus, k6 | Pinned by `sha256` digest; pulled or loaded from tarball |
| **Tier 2 — Application** | frontend, checkout, payment | Built from source at pinned git commit; build must be deterministic |

Do not pin locally-built application images by digest as if they were pull targets.
Pin them by git commit + patch identity.

### 11.3 Replay Fidelity Contract

**What must be identical between original run and replay**:
- `experiment.yaml` content (verified by `spec_sha256`)
- Fault configuration (Toxiproxy parameters; read from spec)
- Workload script and parameters (read from spec)
- Target application state (`git_commit_base` + `patch.diff`)
- Assertions (read from spec)

**What may naturally vary between runs**:
- Absolute metric values (retry counts, latencies, exact timings)
- Prometheus scrape sample timing within the window
- k6 sub-millisecond VU scheduling

`replay.py` evaluates fresh assertions against fresh metrics.
It does **not** compare fresh metrics numerically against archived CSVs.
The archived CSVs are evidence; the assertions are the contract.

---

## 12. Baseline Fairness Contract

The following are binding on both baseline and advanced systems:

| Parameter | Contract |
|-----------|---------|
| LLM model and version | **Identical** |
| LLM temperature | **Identical** |
| Repository and git commit per case | **Identical** |
| PR diff presented | **Identical** |
| Evaluation cases (CASE-01 to CASE-10) | **Identical set, identical order** |
| Evaluation methodology (`evaluate.py`) | **Identical script** |
| Docker Compose environment | **Identical stack** |
| Target application code | **Identical** |

The advanced system's additional capabilities are **runtime evidence + executable
experimentation + deterministic verification**. Not a model upgrade.

Do not manipulate the baseline or evaluation cases to improve advanced results.

---

## 13. Policy Store Rules

`policy_store.json` is **structured institutional memory from human decisions**.

It is not:
- A machine-learning training system
- A reinforcement learning reward signal
- A neural preference model
- An automated inference system

A human makes a consequential engineering judgment. The system records it as a
structured rule. Future agent runs read active policies as explicit constraints
in the system prompt. The agent is **told** about a policy; it does not learn it.

Agents must not:
- Write to `policy_store.json` autonomously
- Modify or delete existing policy entries
- Interpret policies in ways not supported by their text

---

## 14. Testing Standards

Before declaring any task complete, run all applicable checks:

```bash
make test          # unit + integration tests
make typecheck     # mypy or equivalent
make lint          # ruff or equivalent
make eval          # full evaluation suite (when applicable)
```

Report the **actual commands run** and their **actual output**.

Do not claim:
- "Tests pass" without running them
- "Verification passes" without running `verifier.py`
- "Replay succeeds" without running `replay.py`

A task is complete only when **all** of the following are true:
- [ ] Requirements satisfied
- [ ] Implementation present
- [ ] Relevant tests exist and pass
- [ ] Validation executed and results reported
- [ ] Acceptance criteria met
- [ ] No unexplained regressions
- [ ] Required documentation updated

"Code exists" does not mean "task is complete."

---

## 15. Git Conventions

- Keep changes small and reviewable.
- One coherent task per logical commit.
- Commit message format: `<scope>: <imperative summary>` (e.g. `verifier: add INCONCLUSIVE path for missing pre-patch failure`)

Do not mix in a single commit:
- Feature implementation + unrelated refactoring
- Dependency upgrades + feature work
- Formatting changes to unrelated files
- Evaluation case edits + system changes

A change should be easy to review and easy to revert.

---

## 16. Documentation Synchronization

If implementation changes an established architectural behavior:

1. Update the relevant section in `docs/`.
2. Add or update the appropriate entry in `DECISIONS.md`.
3. Update this file if the change affects agent operating rules.

Do not allow documentation to silently contradict implementation.
Do not update documentation to retroactively justify a change that was not approved.

---

## 17. Sealed Holdout — CASE-10

`evaluation/cases/case_10.yaml` is **sealed**.

Agents must not:
- Open, read, or parse `case_10.yaml` before final evaluation
- Use any knowledge of CASE-10 parameters during development or tuning
- Generate code that specifically targets CASE-10 parameters

CASE-10 exists to test honest generalization. Contaminating it invalidates
the evaluation. Treat any accidental exposure as a disqualifying event and
report it immediately.

---

## 18. Unresolved Decisions

The following decisions are **not yet finalized** and require human input
before implementation in the affected area:

| Decision | Status |
|----------|--------|
| LLM model and version | Unresolved — awaiting hackathon access confirmation |
| Verification assertion thresholds | Unresolved — must be calibrated from Week 1 experiments |
| Risk-scoring weights and thresholds | Unresolved — proposed values need empirical confirmation |
| CASE-10 holdout parameters | Sealed — known only to designated team member |
| Human decision UI (CLI vs HTML) | Unresolved — CLI is recommended default |

Do not implement against an unresolved decision without first proposing a
concrete decision for human approval.

---

## 19. Quick Reference

| I need to... | Do this |
|-------------|---------|
| Start a new task | Read this file → read relevant docs → inspect existing code |
| Add a component | Check §4 — if not listed, request human approval first |
| Change an experiment | Only before execution; spec is immutable after Phase 2 |
| Interpret a FAIL result | Do not override; report exactly what was observed |
| Handle INCONCLUSIVE | Report honestly; do not manufacture confidence |
| Change a threshold | After calibration: human approval required |
| Read CASE-10 | Never, until explicitly instructed by a human at final evaluation |
| Disagree with the spec | Stop and raise it; do not silently work around it |
| Hit an ambiguity | Stop and ask; do not resolve it unilaterally |

---

*ChangeProof AGENTS.md — Revision 1.0*
*Derived from: ChangeProof Spec v1.1 + Architecture Decision Report v1.2*
*Status: Awaiting human approval*
