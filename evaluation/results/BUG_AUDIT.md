# ChangeProof Bug Audit Report

Audited by: Agent (Claude Sonnet, Antigravity IDE)
Date: 2026-08-29
Scope: All files in changeproof/, app/, evaluation/, tests/
AGENTS.md section-8 compliance: Two findings withheld from auto-fix.

---

## Pre-Fix Test Baseline

  Command: python -m pytest tests/unit tests/integration -v
  Result:  35 passed, 1 warning in 3.61s

---

## Bug Table

| # | File | Lines | Severity | Fix Applied? |
|---|------|-------|----------|--------------|
| BUG-01 | changeproof/risk_assessor.py | 12, 17, 22 | Blocks correctness | YES |
| BUG-02 | changeproof/risk_assessor.py | 32 | Wrong result silently | YES |
| BUG-03 | changeproof/risk_assessor.py | 12 | Blocks correctness | YES (BUG-01 fix) |
| BUG-04 | changeproof/verifier.py | 33-34 | Wrong result silently | YES |
| BUG-05 | changeproof/experiment_runner.py | 149-152 | Silent failure | YES |

### BUG-01 Description
Regex patterns use [\+\s]* which matches zero or more + or whitespace.
Context lines (space-prefixed, unchanged) trigger signals.
Minimal reproduction: ra.assess_diff(" RETRIES_MAX = 8\n") returns score=10 (wrong, should be 0).

### BUG-02 Description
Signal 5 test-only discount uses Python all() on an empty list.
all(condition for item in []) == True in Python (vacuous truth).
Every headerless diff (like "+RETRIES_MAX = 8\n") triggered the -40 discount.
Effect: CASE-01 through CASE-09 all scored LOW instead of HIGH.

### BUG-03 Description
Regex ^\+[^\+].*RETRIES_MAX consumed the first letter of the keyword (R via [^\+]),
then .*RETRIES_MAX required finding RETRIES_MAX again later in line - impossible.
Fixed: replaced [^\+] with (?!\+) negative lookahead.

### BUG-04 Description
compute_metric_aggregate else branch (no timestamp column, multi-row) returned
val[-1] - val[0] (raw counter delta, no time unit) as the rate aggregate.
Fixed: now returns val.iloc[-1] (last observed value, documented as NOT a rate).

### BUG-05 Description
Toxiproxy teardown: except Exception: pass - failure is completely invisible.
Fixed: error now recorded in manifest["warnings"] and manifest re-saved.

---

## Requires Human Approval (AGENTS.md Section 8)

### HA-01 - evaluation/run_baseline.py line 42
After the risk_assessor fix, all HIGH-risk case diffs score HIGH correctly.
Baseline verdict ("PASSED_UNCHECKED" if not HIGH) now returns REVIEW_FLAGGED for CASE-01 to CASE-09.
This changes comparative evaluation metrics.
Reason not auto-applied: AGENTS.md Section 8 "Changing any baseline fairness condition"

### HA-02 - evaluation/evaluate.py lines 86-88
Report markdown hardcodes "CASE-01 to CASE-09; CASE-10 Sealed" after CASE-10 was unsealed.
Reason not auto-applied: Formal output record - consequential product decision.

---

## Verified Post-Fix Risk Scores

| Case | Before | After | Expected |
|------|--------|-------|----------|
| CASE-01 | score=30 MEDIUM | score=70 HIGH | HIGH |
| CASE-02 | score=10 LOW | score=50 HIGH | HIGH |
| CASE-03 | score=10 LOW | score=50 HIGH | HIGH |
| CASE-04 | score=10 LOW | score=50 HIGH | HIGH |
| CASE-05 | score=0 LOW | score=0 LOW | LOW (negative control) |
| CASE-06 | score=10 LOW | score=50 HIGH | HIGH |
| CASE-07 | score=10 LOW | score=50 HIGH | HIGH |
| CASE-08 | score=10 LOW | score=50 HIGH | HIGH |
| CASE-09 | score=10 LOW | score=50 HIGH | HIGH |
| Context-only | score=10 (BUG) | score=0 CORRECT | 0 |

---

## Files Audited and Found Clean

context_builder.py - CLEAN
capsule.py - CLEAN
replay.py - CLEAN
certificate.py - CLEAN
policy_store.py - CLEAN
agent.py - CLEAN
cli.py - CLEAN
telemetry.py - CLEAN
toxiproxy_client.py - CLEAN
tools.py - CLEAN
app/frontend/main.py - CLEAN
app/checkout/main.py - CLEAN
app/payment/main.py - CLEAN
evaluation/evaluate.py - CLEAN (HA-02 noted)
evaluation/run_baseline.py - Logic CLEAN (HA-01 score impact)
evaluation/run_advanced.py - CLEAN
All unit and integration test files - CLEAN
tests/conftest.py - CLEAN

---

## Non-Determinism Check

RiskAssessor.assess_diff: 10 case diffs x 2 runs - all outputs identical
verifier.compute_metric_aggregate: pure function - deterministic
ContextBuilder.build_topology: parses same docker-compose.yml - deterministic

No non-determinism found.

---

## Race Condition Analysis

experiment_runner.py ordering:
[1] Read spec -> compute spec_sha256 -> write manifest  (CORRECT, before Docker)
[2] Write immutable spec copy to run_dir
[3] Apply Toxiproxy fault
[4] Run k6 workload
[5] Collect Prometheus metrics

Finding: start_time captured before fault injection (cosmetic timing artifact only).
Pre-fault baseline seconds show near-zero retries, do not affect delta computation.
Not filed as a bug.

---

## Post-Fix Test Results

  Command: python -m pytest tests/unit tests/integration -v
  Result:  35 passed, 1 warning in 3.37s  (zero regressions)

  Command: python -m ruff check changeproof tests app evaluation
  Result:  All checks passed!

  Command: python -m mypy changeproof app evaluation --ignore-missing-imports
  Result:  Success: no issues found in 24 source files
