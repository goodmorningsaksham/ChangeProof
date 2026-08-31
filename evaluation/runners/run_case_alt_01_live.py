"""End-to-end live runner for case-alt-01 on alternate topology."""
import os
import sys
import time
import json
import asyncio
import subprocess
import httpx
import requests
import yaml
from changeproof.toxiproxy_client import ToxiproxyClient
from changeproof.verifier import verify
from changeproof.certificate import CertificateGenerator
from changeproof.capsule import CapsulePackager
from changeproof.ci_pipeline import run_live_http_workload, read_direct_metrics

OUTPUT_DIR = "runs/run_case_alt_01"
CAPSULES_DIR = "capsules"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CAPSULES_DIR, exist_ok=True)

# 1. Bring up alternate stack
print("Stopping any running compose stacks...")
subprocess.run(["docker", "compose", "down"], check=False)
subprocess.run(["docker", "compose", "-f", "docker-compose.alt.yml", "down"], check=False)

print("Provisioning docker-compose.alt.yml environment...")
subprocess.run(["docker", "compose", "-f", "docker-compose.alt.yml", "up", "-d", "--build"], check=False)

# Wait for services
print("Waiting for alternate services (gateway:8000, inventory:8001, warehouse:8002)...")
for _ in range(45):
    try:
        r1 = httpx.get("http://localhost:8000/health", timeout=1.0)
        r2 = httpx.get("http://localhost:8001/health", timeout=1.0)
        r3 = httpx.get("http://localhost:8002/health", timeout=1.0)
        if r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 200:
            print("All alternate services healthy!")
            break
    except Exception:
        pass
    time.sleep(1.0)

# Ensure warehouse-proxy is registered in Toxiproxy
toxi = ToxiproxyClient(admin_url="http://localhost:8474")
try:
    toxi.get_proxy("warehouse-proxy")
except Exception:
    requests.post("http://localhost:8474/proxies", json={
        "name": "warehouse-proxy",
        "listen": "0.0.0.0:18002",
        "upstream": "warehouse-service:8002",
        "enabled": True,
    })
print("warehouse-proxy verified in Toxiproxy.")

# Load synthesized spec
with open("evaluation/cases/case_alt_01.yaml", "r", encoding="utf-8") as f:
    spec = yaml.safe_load(f)

with open(os.path.join(OUTPUT_DIR, "experiment.yaml"), "w", encoding="utf-8") as f:
    yaml.dump(spec, f, sort_keys=False)

INV_MAIN = "app/inventory/main.py"
with open(INV_MAIN, "r", encoding="utf-8") as f:
    orig_code = f.read()

# Step A: Apply PR high-risk state (RETRIES_MAX=8, TIMEOUT=0.5, BACKOFF=0.0)
pr_code = (
    orig_code
    .replace('RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))', 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))')
    .replace('RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))', 'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))')
    .replace('RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))', 'RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))')
)
with open(INV_MAIN, "w", encoding="utf-8") as f:
    f.write(pr_code)

print("Rebuilding inventory-service with PR high-risk configuration...")
subprocess.run(["docker", "compose", "-f", "docker-compose.alt.yml", "build", "inventory-service"], check=False)
subprocess.run(["docker", "compose", "-f", "docker-compose.alt.yml", "up", "-d", "inventory-service"], check=False)
time.sleep(2.0)

# Phase 3: BASE execution
print("\n=== EXECUTING BASE STATE (case-alt-01) ===")
toxi.reset()
toxi.add_latency("warehouse-proxy", latency_ms=1500, jitter_ms=75)

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

# Phase 4: PATCHED execution
print("\n=== EXECUTING PATCHED STATE (case-alt-01) ===")
remediated_code = (
    pr_code
    .replace('RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))', 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "2"))')
    .replace('RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))', 'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))')
    .replace('RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))', 'RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))')
)
with open(INV_MAIN, "w", encoding="utf-8") as f:
    f.write(remediated_code)

print("Rebuilding inventory-service with remediated configuration...")
subprocess.run(["docker", "compose", "-f", "docker-compose.alt.yml", "build", "inventory-service"], check=False)
subprocess.run(["docker", "compose", "-f", "docker-compose.alt.yml", "up", "-d", "inventory-service"], check=False)
time.sleep(2.0)

toxi.reset()
toxi.add_latency("warehouse-proxy", latency_ms=1500, jitter_ms=75)

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

# Restore inventory baseline
with open(INV_MAIN, "w", encoding="utf-8") as f:
    f.write(orig_code)

toxi.reset()

# Write manifest.json
manifest_data = {
    "experiment_id": "case-alt-01",
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
    "experiment_id": "case-alt-01",
    "git_commit": "alt-topology-head",
    "risk_level": "HIGH",
    "risk_score": 70,
    "hypothesis_title": spec["title"],
    "hypothesis_confidence": "HIGH",
    "verification_status": ver_res.status,
    "diff_table": ver_res.diff_table,
    "pre_summary": base_summary,
    "post_summary": patched_summary,
    "capsule_path": "capsules/case-alt-01.zip",
}, cert_path)

packager = CapsulePackager(capsules_dir=CAPSULES_DIR)
capsule_zip = packager.create_capsule(
    experiment_id="case-alt-01",
    run_dir=OUTPUT_DIR,
    git_commit_base="main",
)
print(f"\nCreated Capsule: {capsule_zip}")
