import os
import json
from changeproof.agent import ChangeProofAgent

diff_10 = """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.6"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
"""

agent = ChangeProofAgent(run_dir="runs/case-10_agent_run")
res = agent.run_investigation(diff_10)
print("Investigation completed:", res["status"])
traj_path = os.path.join(res["run_dir"], "agent_trajectory.jsonl")
print(f"Trajectory file exists: {os.path.exists(traj_path)} ({os.path.getsize(traj_path)} bytes)")
with open(traj_path, "r", encoding="utf-8") as f:
    for line in f:
        entry = json.loads(line)
        print(f"  - Action: {entry['action_type']} | Data keys: {list(entry['data'].keys())}")
