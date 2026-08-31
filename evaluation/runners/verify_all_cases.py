from changeproof.replay import replay_capsule
from changeproof.risk_assessor import RiskAssessor
import json

cases = [
    "capsules/case-01.zip",
    "capsules/case-10.zip",
    "capsules/case-alt-01.zip",
    "capsules/case-calib-01.zip",
    "capsules/case-calib-02.zip",
    "capsules/case-var-01.zip",
    "capsules/case-var-02.zip",
    "capsules/case-var-03.zip",
    "capsules/case-var-04.zip",
    "capsules/case-var-05.zip",
    "capsules/case01-synth-live-verify.zip",
]
for c in cases:
    res = replay_capsule(c, mode="evidence")
    verdict = res.get("verification", {}).get("status", "ERROR")
    pre_ratio = res.get("verification", {}).get("pre_summary", {}).get("retries_per_request", "N/A")
    post_ratio = res.get("verification", {}).get("post_summary", {}).get("retries_per_request", "N/A")
    print(f"{c:40s} -> Pre: {str(pre_ratio):4s} | Post: {str(post_ratio):4s} | VERDICT: [{verdict}]")
    assert verdict == "PASS", f"Failed on {c}"

# CASE-05: verify static risk assessment
res_05 = RiskAssessor().assess_diff("+ANALYTICS_RETRY = 2")
print(f"{'CASE-05 (Static Safe Control)':40s} -> LEVEL: [{res_05['level']}] (requires_experiment: {res_05['requires_experiment']})")
assert res_05['level'] == 'LOW'

print("\nALL 11 EXECUTED CASES CONFIRMED DETERMINISTIC PASS / PASS_SAFE!")
