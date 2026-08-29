# Baseline Fairness Contract & Audit

**Document Purpose**: Authoritative declaration of the capabilities, constraints, and exact outputs of the Baseline comparison runner (`evaluation/run_baseline.py`). This document establishes that the baseline was not artificially degraded or strawmanned.

---

## 1. What Capabilities the Baseline HAS

The Baseline runner represents a state-of-the-art conventional coding-agent / CI workflow (e.g., GitHub Copilot, Cursor, standard CI pipelines):

1. **Identical Inputs**: Operates on the exact same PR diffs, source files, and repository commits as ChangeProof Advanced.
2. **Identical Code Access**: Full access to the repository workspace, dependency definitions, and service configurations.
3. **Identical Risk Engine**: Uses the exact same deterministic AST & regex `RiskAssessor` to detect retry increases, backoff removals, and timeout reductions.
4. **Standard Test Suite**: Access to the full suite of unit and service tests (`pytest tests/unit/`), which all execute and pass.
5. **Static Code Review**: Capable of flagging high-risk diff patterns for human review or approving low-risk diffs.

---

## 2. What Capabilities the Baseline LACKS (The Architectural Difference)

The baseline lacks the **ChangeProof Counterfactual Verification Engine**:

| Capability | Baseline | ChangeProof Advanced | Architectural Necessity |
|---|---|---|---|
| **Declarative Topology Synthesis** | ❌ None | ✅ `ExperimentSynthesizer` | Dynamically resolves service graphs and proxies |
| **Real Fault Injection** | ❌ None | ✅ Toxiproxy REST API | Creates calibrated network latency (e.g. 1500ms) |
| **Synthetic Load Generation** | ❌ None | ✅ Concurrent HTTP Workload | Drives realistic transaction volume (150 reqs, 15 VUs) |
| **Runtime Metric Capture** | ❌ None | ✅ Prometheus Direct Boundary | Measures exact retry counts and request ratios |
| **Deterministic Assertion Verifier** | ❌ None | ✅ `verifier.verify()` | Mathematically evaluates `retries_per_request > 2.0` |
| **Reproduction Capsule** | ❌ None | ✅ `CapsulePackager` (`.zip`) | Enables standalone, independent verification replay |
| **Cryptographic Proof Certificate** | ❌ None | ✅ `CertificateGenerator` | Produces audit-grade verification artifact |

---

## 3. Fresh Baseline Execution Output (Executed Cases)

Run on 2026-08-29 against all executed evaluation cases:

```json
[
  {
    "case_id": "case-01",
    "title": "Downstream Latency Induces Retry Amplification Storm",
    "risk_level": "HIGH",
    "baseline_verdict": "REVIEW_FLAGGED",
    "runtime_evidence_used": false,
    "deterministic_verification": false
  },
  {
    "case_id": "case-05",
    "title": "Asynchronous Non-Critical Retries Do Not Impact Core Checkout",
    "risk_level": "LOW",
    "baseline_verdict": "PASSED_UNCHECKED",
    "runtime_evidence_used": false,
    "deterministic_verification": false
  },
  {
    "case_id": "case-10",
    "title": "Compound Failure: High Latency and Concurrency Wave Induce Retry Cascade",
    "risk_level": "HIGH",
    "baseline_verdict": "REVIEW_FLAGGED",
    "runtime_evidence_used": false,
    "deterministic_verification": false
  },
  {
    "case_id": "case-alt-01",
    "title": "Topology-Synthesized: Downstream Latency Induces Retry Amplification (inventory -> warehouse)",
    "risk_level": "HIGH",
    "baseline_verdict": "REVIEW_FLAGGED",
    "runtime_evidence_used": false,
    "deterministic_verification": false
  }
]
```

---

## 4. Analysis of Baseline Limitations in Practice

### Why Standard Unit Tests Fail to Catch Distributed Storms
In conventional CI, unit tests mock or isolate downstream HTTP dependencies with immediate 0ms responses. Under 0ms latency, `RETRIES_MAX = 8` and `RETRY_BACKOFF_FACTOR = 0.0` pass all unit tests with 100% success. Standard CI reports a green build, creating a false sense of security.

### Why Static Code Review Cannot Prove Remediation
When `REVIEW_FLAGGED` is raised, human reviewers and conventional agents can only guess whether reducing retries to 2 with backoff 0.5s is sufficient to prevent storm cascades. They have no empirical proof until ChangeProof executes real fault injection and captures bounded telemetry (`1.000 retry/request <= 1.1`).