# ChangeProof â€” Designated Challenging Case: Confounded Multi-Signal Evaluation

**Case Identifier**: `CASE-01` (Canonical Multi-Signal Storm)  
**Artifacts**: [`runs/ci_run/proof_certificate.md`](file:///c:/Users/saksh/Downloads/proofchange/runs/ci_run/proof_certificate.md), [`capsules/case-01.zip`](file:///c:/Users/saksh/Downloads/proofchange/capsules/case-01.zip)  
**Status**: `PROVEN & VERIFIED SAFE` (Deterministic Verdict: `PASS`, VSCR: `100.0%`)

---

## 1. What Makes This Case Hard: The Confounding Dilemma

In real-world engineering pull requests, developers rarely modify a single parameter in isolation. In the canonical `CASE-01` diff on `app/checkout/main.py`, **three high-risk signals were altered simultaneously**:

```diff
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
```

### The Three Confounded Failure Mechanisms
1. **Elevated Retry Ceiling (`RETRIES_MAX = 8`)**: Allows each stalled request to multiply downstream load up to 8Ã—.
2. **Zero Backoff (`RETRY_BACKOFF_FACTOR = 0.0`)**: Removes delays between attempts, firing retries in instantaneous bursts and depriving downstream services of recovery windows.
3. **Aggressive Timeout Reduction (`RETRY_TIMEOUT_SECONDS = 0.5s`)**: Cuts client-side timeout in half, causing requests to abort prematurely while downstream processing is still in flight (e.g. under 1500ms latency).

### The False Independent Attribution Fallacy (What Naive Agents Do)
When a conventional AI agent executes a single counterfactual experiment on this diff, it observes a massive failure storm (1,050 retries across 150 requests = **7.000 retries/request**). Naive systems make a critical epistemic error:
> *"The experiment proves that `RETRIES_MAX = 8` caused the storm."*

This claim is scientifically invalid. In a single combined experiment, all three parameters are **completely confounded**. Was `RETRIES_MAX=8` alone sufficient to cause the storm? Or did the storm only occur because `RETRY_TIMEOUT_SECONDS=0.5s` triggered premature timeouts and `RETRY_BACKOFF_FACTOR=0.0` eliminated recovery spacing? A single experiment cannot distinguish individual sufficiency without factorial ablation.

---

## 2. How ChangeProof Solves It: Honest Joint Attribution

ChangeProof addresses this challenge through a multi-tiered epistemic framework in `changeproof/hypothesis_evaluator.py` and `changeproof/certificate.py`:

### A. Grounded Multi-Signal Hypothesis Formulation
Instead of collapsing the diff into a generic hypothesis, `generate_candidate_hypotheses()` parses AST signals to construct three distinct, grounded hypotheses:
- `H-RETRY-CEILING`: Retry count ceiling amplification
- `H-NO-BACKOFF`: Immediate unspaced load concentration
- `H-AGGRESSIVE-TIMEOUT`: Premature timeout triggering

### B. Confounded vs. Isolated Evaluation Vocabulary
When evaluating runtime telemetry from a single combined experiment:
- **For Multi-Signal Diffs (`N > 1`)**: Verdicts are strictly labeled **`[CONSISTENT WITH OBSERVED STORM]`** rather than falsely asserting independent proof (`[SUPPORTED]`).
- **For Single-Signal Diffs (`N = 1`)**: Verdicts are labeled **`[SUPPORTED (ISOLATED)]`**, reflecting genuine single-factor confirmation.

### C. Explicit Joint Attribution Note on Proof Certificates
When multiple signals co-occur, ChangeProof automatically injects a mandatory disclaimer into the Proof Certificate:

> **Note on Joint Attribution**: 3 signals were changed together in this diff and evaluated via a single combined experiment. This confirms the **COMBINATION** produced the observed failure; it does not isolate which individual signal(s) would be sufficient on their own. Independent attribution would require separate ablation experiments per signal.

---

## 3. Telemetry Evidence from the Confounded Execution

From the canonical live run (`33227355365` / `runs/ci_run/`):

| Hypothesis ID | Detected Signal | Evaluated Telemetry | Status Label | Grounded Telemetry Evidence |
|---|---|---|---|---|
| **`H-RETRY-CEILING`** | Retry Count Increase | Pre: 7.000 retries/req (>2.0) | `[CONSISTENT WITH OBSERVED STORM]` | 7.000 retries/req across 150 requests confirms elevated ceiling multiplies failed calls. |
| **`H-NO-BACKOFF`** | Removal of Backoff | Pre: 1530.12 retries/min (>500) | `[CONSISTENT WITH OBSERVED STORM]` | Storm rate of 1530.12/min confirms zero-backoff allows retries to fire in tight unspaced bursts. |
| **`H-AGGRESSIVE-TIMEOUT`** | Timeout Reduction | Latency (1500ms) > Timeout (500ms) | `[CONSISTENT WITH OBSERVED STORM]` | 1500ms downstream latency exceeded 500ms timeout, causing 100% of requests to timeout prematurely. |

---

## 4. Why This Is Superior Reliability Engineering

1. **Epistemic Humility Over False Precision**: ChangeProof does not overclaim what single-run data can mathematically prove.
2. **Actionable Remediation Without Delays**: By remediating the entire vulnerable pattern (`RETRIES_MAX=2`, `TIMEOUT=1.0s`, `BACKOFF=0.5s`), ChangeProof eliminates the storm completely (7.0 $\rightarrow$ 1.0 retry/req) in a single CI cycle without requiring 8 separate combinatorial ablation runs.
3. **Audit-Grade Compliance**: Human engineers reading the certificate immediately understand both the holistic safety of the remediated patch and the exact attribution limits of the underlying evidence.

---

---

## 5. Isolated Factorial Evidence: Single-Factor Backoff Ablation (`case-ablation-backoff-01`)

To test whether backoff removal alone (`RETRY_BACKOFF_FACTOR: 0.5 -> 0.0`) is sufficient to create a retry amplification storm (>2.0 retries/req) and whether isolated backoff restoration (0.0 -> 0.5) is sufficient to remediate it, ChangeProof executed an unconfounded single-factor ablation experiment.

### The True Single-Factor Diff & Isolated Reversion
- **Evaluated Diff**:
  ```diff
  --- a/app/checkout/main.py
  +++ b/app/checkout/main.py
  @@ -12,3 +12,3 @@
   RETRIES_MAX = 3
   RETRY_TIMEOUT_SECONDS = 1.0
  -RETRY_BACKOFF_FACTOR = 0.5
  +RETRY_BACKOFF_FACTOR = 0.0
  ```
- **Isolated Reversion (Remediation)**: Reverts *only* `RETRY_BACKOFF_FACTOR` to `0.5`, leaving `RETRIES_MAX = 3` and `RETRY_TIMEOUT_SECONDS = 1.0` strictly unchanged.

### 1. Risk Assessment & Signal Isolation
- **Risk Score**: `20/100` (Level: `MEDIUM`)
- **Signals Detected**: Exactly 1 signal: `["Removal of backoff / immediate retry execution"]`.

### 2. Live Runtime Telemetry (Under Standard Frozen Assertions)
- **Calibrated Injected Latency**: $2000\text{ms}$ on `payment-proxy` ($\max(2T, 1500\text{ms})$ against $1.0\text{s}$ timeout).
- **Pre-Patch State (`BACKOFF = 0.0`, `RETRIES_MAX = 3`, `TIMEOUT = 1.0`)**:
  - **Retries / Request**: **`2.000`** ($1\text{ attempt} + 2\text{ retries} = 2\text{ retries/req}$).
  - **Retry Rate**: **`435.31 retries/min`** (unspaced immediate firing).
  - **Assertion Check**: Condition `> 2.0` is **NOT MET** ($2.0 \ngtr 2.0$).
- **Post-Patch Reverted State (`BACKOFF = 0.5`, `RETRIES_MAX = 3`, `TIMEOUT = 1.0`)**:
  - **Retries / Request**: **`2.000`** (requests still timeout and execute 2 retries, spaced by backoff).
  - **Retry Rate**: **`387.10 retries/min`**.
  - **Assertion Check**: Condition `<= 1.1` is **NOT MET** ($2.0 \nleq 1.1$).
- **Deterministic Verifier Verdict**: **`INCONCLUSIVE`** (Pre-patch amplification threshold $> 2.0$ not reached; safety not proven).

### 3. Key Scientific Findings & Epistemic Implications
1. **Separation of Volume vs. Pacing**:
   - **Backoff controls temporal pacing**: Removing backoff spikes the instantaneous retry rate (435.31/min in bursts).
   - **Retry ceiling controls total volume**: Removing backoff *alone* does not increase total retries per request beyond $\text{RETRIES\_MAX} - 1 = 2.0$.
2. **Confounding Confirmation in CASE-01**:
   - In `CASE-01`, the massive 7.0 retries/req storm was driven by `RETRIES_MAX = 8` in combination with premature timeouts (`TIMEOUT = 0.5s`). Backoff removal aggravated the storm's burstiness, but was not independently sufficient to cause a $> 2.0$ amplification on its own when `RETRIES_MAX = 3`.
3. **Epistemic Integrity**:
   - Rather than shifting assertion thresholds or applying an unfaithful multi-parameter fix, ChangeProof faithfully evaluated the standard frozen assertions and returned `INCONCLUSIVE`, proving the verifier's complete refusal to fabricate safety certificates.

### 4. Reproduction Capsule
- **Capsule**: [`capsules/case-ablation-backoff-01.zip`](file:///c:/Users/saksh/Downloads/proofchange/capsules/case-ablation-backoff-01.zip)
- **Replay Verification**: `python -m changeproof.replay capsules/case-ablation-backoff-01.zip` $\rightarrow$ `[INCONCLUSIVE]`

