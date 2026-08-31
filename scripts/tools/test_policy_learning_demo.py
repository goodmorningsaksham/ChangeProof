import json
import sys
from changeproof.cli import main

# 1. Record human policy via CLI
print("=== 1. RECORDING HUMAN GOVERNANCE POLICY VIA CLI ===")
sys.argv = [
    "cli.py", "decide",
    "--cert", "runs/ci_run/proof_certificate.md",
    "--decision", "APPROVED",
    "--author", "Saksham (Reliability Lead)",
    "--rationale", "Empirical finding from CASE-01: retries > 4 trigger severe storm cascades under downstream latency",
    "--policy-rule", "payment-service retries must not exceed 4",
    "--experiment-id", "case-01"
]
main()

# 2. Verify policy_store.json validation
from changeproof.policy_store import load_policies, validate_policy
policies = load_policies("policy_store.json")
print("\n=== 2. POLICY STORE VALIDATION & CONTENTS ===")
print(f"Total Policies Loaded: {len(policies)}")
for p in policies:
    print(f"Policy ID: {p.get('policy_id')} | Rule: '{p.get('rule')}' | Author: '{p.get('author')}' | Valid: {validate_policy(p)}")

# 3. Construct a PR diff violating the stored policy (RETRIES_MAX = 6)
violating_diff = """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))
"""

print("\n=== 3. EVALUATING VIOLATING PR DIFF (RETRIES_MAX = 6) ===")
from changeproof.risk_assessor import RiskAssessor
from changeproof.context_builder import ContextBuilder

assessor = RiskAssessor("policy_store.json")
risk_res = assessor.assess_diff(violating_diff)
print("Risk Assessor Scorecard:")
print(json.dumps(risk_res, indent=2))

builder = ContextBuilder(policy_path="policy_store.json")
context = builder.build_context(violating_diff)
print("\nContext Builder Stored Policies Found in PR Context:")
for pol in context["policies"]:
    print(f"  - [{pol['policy_id']}] Rule: '{pol['rule']}' (Author: {pol['author']})")
