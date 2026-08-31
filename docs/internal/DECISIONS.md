# Architecture Decision Records (ADRs) — ChangeProof

## ADR-001: Selection of Docker Compose over Kubernetes for MVP Runtime
* **Status**: Accepted
* **Context**: Need a local, reproducible, low-friction container runtime to demonstrate real distributed microservices and network fault injection.
* **Decision**: Adopt Docker Compose. Reject Kubernetes (k3s, kind) for the MVP to eliminate cluster startup flakiness, DNS/CNI operational failures, and resource overhead during live demonstrations.
* **Consequences**: Fast startup (<5s), minimal dependencies, direct Toxiproxy network-level bridging.

## ADR-002: Network-Level Fault Injection via Toxiproxy
* **Status**: Accepted
* **Context**: Must inject real network latency and packet loss between microservices rather than mocking code paths.
* **Decision**: Place Toxiproxy between `checkout-service` and downstream `payment-service` with REST API programmatic control.
* **Consequences**: Exact latency parameters (e.g., 2000ms latency, 100ms jitter) injected dynamically at the TCP socket layer without restarting containers.

## ADR-003: Deterministic Assertion Verification with Zero LLM Calls
* **Status**: Accepted
* **Context**: Safety verification must be objective, auditable, and non-hallucinatory.
* **Decision**: Implement `changeproof/verifier.py` in pure Python. Evaluate structured metric series against YAML assertion rules.
* **Consequences**: The LLM proposes hypotheses and patches; the deterministic engine alone awards `PASS`, `FAIL`, or `INCONCLUSIVE`.

## ADR-004: Experiment Specification Immutability
* **Status**: Accepted
* **Context**: Prevent drift between designed experiments and executed/replayed experiments.
* **Decision**: Calculate SHA-256 hash of `experiment.yaml` prior to container startup. Lock spec against modification. `replay.py` validates this hash before execution.
* **Consequences**: Guaranteed reproducibility; clean-environment replay can verify exact historical test fidelity.

## ADR-005: Reproduction Capsule Packaging & Two Named States
* **Status**: Accepted
* **Context**: Third parties must be able to independently reproduce findings from a clean clone.
* **Decision**: Structure reproduction capsule with explicit `BASE STATE` (PR commit before patch, failure reproduction) and `PATCHED STATE` (remediated code, safety verification).
* **Consequences**: Clear separation between failure evidence and verified fix. Tier 1 infrastructure images pinned by digest; Tier 2 application images built deterministically from source.

## ADR-006: Policy Learning as Structured Institutional Memory
* **Status**: Accepted
* **Context**: Capture human engineering decisions for future evaluations without complex neural training.
* **Decision**: Append human approval/rejection rules into `policy_store.json` and inject active policies into future agent prompts as explicit constraints.
* **Consequences**: Simple, auditable, deterministic constraint propagation. Zero reinforcement learning overhead.
