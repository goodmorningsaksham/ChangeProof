"""End-to-end live runner for case-inconclusive-01 (Natural Boundary Case)."""
import os
import sys
import time
import json
import asyncio
import subprocess
import httpx
import yaml
from changeproof.toxiproxy_client import ToxiproxyClient
from changeproof.verifier import verify
from changeproof.certificate import CertificateGenerator
from changeproof.capsule import CapsulePackager
from changeproof.ci_pipeline import run_live_http_workload, read_direct_metrics

OUTPUT_DIR = "runs/case_inconclusive_01"
CAPSULES_DIR = "capsules"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CAPSULES_DIR, exist_ok=True)

# 1. Ensure primary Docker Compose environment is running
print("Ensuring primary Docker Compose environment is running...")
subprocess.run(["docker", "compose", "up", "-d"], check=False)

CHECKOUT_MAIN = "app/checkout/main.py"
with open(CHECKOUT_MAIN, "r", encoding="utf-8") as f:
    orig_code = f.read()

# PR diff: RETRIES_MAX=4, TIMEOUT=1.5, BACKOFF=0.0
diff_text = """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))  # Baseline: safe retry count
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))  # Baseline: exponential backoff
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "4"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.5"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
"""

from changeproof.experiment_synthesizer import ExperimentSynthesizer
synth = ExperimentSynthesizer(compose_path="docker-compose.yml", toxiproxy_config_path="toxiproxy_init.json")
spec = synth.synthesize(diff_text, case_id="case-inconclusive-01", git_commit="inconclusive-boundary-run")

with open(os.path.join(OUTPUT_DIR, "experiment.yaml"), "w", encoding="utf-8") as f:
    yaml.dump(spec, f, sort_keys=False)

# Step A: Apply boundary PR configuration to app/checkout/main.py
pr_code = (
    orig_code
    .replace('RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))', 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "4"))')
    .replace('RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))', 'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.5"))')
    .replace('RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))', 'RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))')
)
with open(CHECKOUT_MAIN, "w", encoding="utf-8") as f:
    f.write(pr_code)

print("Rebuilding checkout-service with boundary PR configuration (RETRIES_MAX=4, TIMEOUT=1.5, BACKOFF=0.0)...")
subprocess.run(["docker", "compose", "build", "checkout-service"], check=False)
subprocess.run(["docker", "compose", "up", "-d", "checkout-service"], check=False)
time.sleep(3.0)

# Phase 3: BASE execution under 3000ms latency (calibrated against 1.5s timeout)
print("\n=== EXECUTING BASE STATE (case-inconclusive-01) ===")
toxi = ToxiproxyClient(admin_url="http://localhost:8474")
toxi.reset()
toxi.add_latency("payment-proxy", latency_ms=3000, jitter_ms=150)

pre_m_base = read_direct_metrics("http://localhost:8001/metrics")
print(f"Pre-workload metrics (BASE): {pre_m_base}")

t0 = time.time()
asyncio.run(
    run_live_http_workload(
        "http://localhost:8000/orders",
        total_requests=150,
        concurrency=15,
        timeout_s=6.0,
    )
)
t_base_end = time.time()
phase_base_dur = max(0.001, t_base_end - t0)

time.sleep(2.0)
post_m_base = read_direct_metrics("http://localhost:8001/metrics")
print(f"Post-workload metrics (BASE): {post_m_base}")

retries_base = max(0.0, post_m_base["retry_count"] - pre_m_base["retry_count"])
reqs_base = max(0.0, post_m_base["checkout_requests"] - pre_m_base["checkout_requests"]) or 150.0
ratio_base = round(retries_base / reqs_base, 4)
rate_base = round((retries_base / phase_base_dur) * 60.0, 2)
tp_base = round(reqs_base / phase_base_dur, 2)

base_csv = os.path.join(OUTPUT_DIR, "metrics_base.csv")
with open(base_csv, "w", encoding="utf-8") as f:
    f.write("timestamp,metric_name,value\n")
    f.write(f"{int(t0)},retry_count_total,{pre_m_base['retry_count']}\n")
    f.write(f"{int(t_base_end)},retry_count_total,{post_m_base['retry_count']}\n")
    f.write(f"{int(t0)},checkout_requests_total,{pre_m_base['checkout_requests']}\n")
    f.write(f"{int(t_base_end)},checkout_requests_total,{post_m_base['checkout_requests']}\n")

base_summary = {
    "phase": "base",
    "duration_s": round(phase_base_dur, 2),
    "total_requests": reqs_base,
    "retries_counted": retries_base,
    "retries_per_request": ratio_base,
    "rate_per_min": rate_base,
    "throughput_req_per_sec": tp_base,
    "metrics_csv": base_csv,
}
with open(os.path.join(OUTPUT_DIR, "manifest_base.json"), "w", encoding="utf-8") as f:
    json.dump(base_summary, f, indent=2)

print(f"BASE Summary: {base_summary}")

# Phase 4: PATCHED execution (Remediation: RETRIES_MAX=2, TIMEOUT=1.0, BACKOFF=0.5)
print("\n=== EXECUTING PATCHED STATE (case-inconclusive-01) ===")
remediated_code = (
    orig_code
    .replace('RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))', 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "2"))')
    .replace('RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))', 'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))')
)
with open(CHECKOUT_MAIN, "w", encoding="utf-8") as f:
    f.write(remediated_code)

print("Rebuilding checkout-service with remediated configuration...")
subprocess.run(["docker", "compose", "build", "checkout-service"], check=False)
subprocess.run(["docker", "compose", "up", "-d", "checkout-service"], check=False)
time.sleep(3.0)

toxi.reset()
toxi.add_latency("payment-proxy", latency_ms=3000, jitter_ms=150)

pre_m_patch = read_direct_metrics("http://localhost:8001/metrics")
print(f"Pre-workload metrics (PATCHED): {pre_m_patch}")

t0_patch = time.time()
asyncio.run(
    run_live_http_workload(
        "http://localhost:8000/orders",
        total_requests=150,
        concurrency=15,
        timeout_s=6.0,
    )
)
t_patch_end = time.time()
phase_patch_dur = max(0.001, t_patch_end - t0_patch)

time.sleep(2.0)
post_m_patch = read_direct_metrics("http://localhost:8001/metrics")
print(f"Post-workload metrics (PATCHED): {post_m_patch}")

retries_patch = max(0.0, post_m_patch["retry_count"] - pre_m_patch["retry_count"])
reqs_patch = max(0.0, post_m_patch["checkout_requests"] - pre_m_patch["checkout_requests"]) or 150.0
ratio_patch = round(retries_patch / reqs_patch, 4)
rate_patch = round((retries_patch / phase_patch_dur) * 60.0, 2)
tp_patch = round(reqs_patch / phase_patch_dur, 2)

patched_csv = os.path.join(OUTPUT_DIR, "metrics_patched.csv")
with open(patched_csv, "w", encoding="utf-8") as f:
    f.write("timestamp,metric_name,value\n")
    f.write(f"{int(t0_patch)},retry_count_total,{pre_m_patch['retry_count']}\n")
    f.write(f"{int(t_patch_end)},retry_count_total,{post_m_patch['retry_count']}\n")
    f.write(f"{int(t0_patch)},checkout_requests_total,{pre_m_patch['checkout_requests']}\n")
    f.write(f"{int(t_patch_end)},checkout_requests_total,{post_m_patch['checkout_requests']}\n")

patched_summary = {
    "phase": "patched",
    "duration_s": round(phase_patch_dur, 2),
    "total_requests": reqs_patch,
    "retries_counted": retries_patch,
    "retries_per_request": ratio_patch,
    "rate_per_min": rate_patch,
    "throughput_req_per_sec": tp_patch,
    "metrics_csv": patched_csv,
}
with open(os.path.join(OUTPUT_DIR, "manifest_patched.json"), "w", encoding="utf-8") as f:
    json.dump(patched_summary, f, indent=2)

print(f"PATCHED Summary: {patched_summary}")

# Restore baseline
with open(CHECKOUT_MAIN, "w", encoding="utf-8") as f:
    f.write(orig_code)

toxi.reset()

# Write manifest.json
manifest_data = {
    "experiment_id": "case-inconclusive-01",
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "base": base_summary,
    "patched": patched_summary,
}
with open(os.path.join(OUTPUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest_data, f, indent=2)

# Phase 5: Verification
ver_res = verify(base_csv, patched_csv, spec["assertions"])
print(f"\n=== DETERMINISTIC VERIFIER VERDICT: [{ver_res.status}] ===")
print(f"Reason: {ver_res.reason}")
for r in ver_res.diff_table:
    print(f"  * {r['metric']} ({r['phase']}): observed {r['observed_value']} | condition `{r['condition']}` -> MET: {r['condition_met']}")

# Phase 6: Proof Certificate & Capsule Packaging
cert_path = os.path.join(OUTPUT_DIR, "proof_certificate.md")
cert_gen = CertificateGenerator()
cert_gen.generate_and_save({
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "experiment_id": "case-inconclusive-01",
    "git_commit": "inconclusive-boundary-run",
    "risk_level": "HIGH",
    "risk_score": 50,
    "hypothesis_title": spec["title"],
    "hypothesis_confidence": "HIGH",
    "verification_status": ver_res.status,
    "diff_table": ver_res.diff_table,
    "pre_summary": base_summary,
    "post_summary": patched_summary,
    "capsule_path": "capsules/case-inconclusive-01.zip",
}, cert_path)

packager = CapsulePackager(capsules_dir=CAPSULES_DIR)
capsule_zip = packager.create_capsule(
    experiment_id="case-inconclusive-01",
    run_dir=OUTPUT_DIR,
    git_commit_base="inconclusive-boundary-run",
)
print(f"\nCreated Capsule: {capsule_zip}")
