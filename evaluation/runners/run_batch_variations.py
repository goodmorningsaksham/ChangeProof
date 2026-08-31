"""Batch executor for case variations (case-var-01 through case-var-05)."""
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
from changeproof.experiment_synthesizer import ExperimentSynthesizer
from changeproof.hypothesis_evaluator import generate_candidate_hypotheses, evaluate_hypotheses_evidence
from changeproof.ci_pipeline import run_live_http_workload, read_direct_metrics

CAPSULES_DIR = "capsules"
os.makedirs(CAPSULES_DIR, exist_ok=True)

CHECKOUT_MAIN = "app/checkout/main.py"
with open(CHECKOUT_MAIN, "r", encoding="utf-8") as f:
    orig_code = f.read()

# Define the 5 controlled variations
variations = [
    {
        "id": "case-var-01",
        "title": "Latency Variation: 2000ms Downstream Latency (RETRIES_MAX=5, TIMEOUT=1.0)",
        "diff": """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "5"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
""",
        "retries_max": 5,
        "timeout_s": 1.0,
        "backoff": 0.0,
        "latency_ms": 2000,
        "jitter_ms": 100,
        "total_requests": 150,
        "concurrency": 15,
    },
    {
        "id": "case-var-02",
        "title": "High Latency Variation: 3500ms Downstream Latency (RETRIES_MAX=6, TIMEOUT=0.6)",
        "diff": """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.6"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
""",
        "retries_max": 6,
        "timeout_s": 0.6,
        "backoff": 0.0,
        "latency_ms": 3500,
        "jitter_ms": 175,
        "total_requests": 150,
        "concurrency": 15,
    },
    {
        "id": "case-var-03",
        "title": "High Concurrency Wave: 30 VUs Traffic Burst (RETRIES_MAX=8, TIMEOUT=0.5)",
        "diff": """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
""",
        "retries_max": 8,
        "timeout_s": 0.5,
        "backoff": 0.0,
        "latency_ms": 1500,
        "jitter_ms": 75,
        "total_requests": 150,
        "concurrency": 30,
    },
    {
        "id": "case-var-04",
        "title": "Low Traffic Concurrency: 5 VUs Load (RETRIES_MAX=6, TIMEOUT=0.5)",
        "diff": """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
""",
        "retries_max": 6,
        "timeout_s": 0.5,
        "backoff": 0.0,
        "latency_ms": 1500,
        "jitter_ms": 75,
        "total_requests": 100,
        "concurrency": 5,
    },
    {
        "id": "case-var-05",
        "title": "Combined Parameter Variation: RETRIES_MAX=5, TIMEOUT=0.4, BACKOFF=0.0",
        "diff": """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "5"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.4"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
""",
        "retries_max": 5,
        "timeout_s": 0.4,
        "backoff": 0.0,
        "latency_ms": 1500,
        "jitter_ms": 75,
        "total_requests": 150,
        "concurrency": 15,
    },
]

print("Ensuring primary Docker Compose stack is running...")
subprocess.run(["docker", "compose", "up", "-d"], check=False)
toxi = ToxiproxyClient("http://localhost:8474")

synth = ExperimentSynthesizer(compose_path="docker-compose.yml", toxiproxy_config_path="toxiproxy_init.json")
cert_gen = CertificateGenerator()
packager = CapsulePackager(capsules_dir=CAPSULES_DIR)

results_summary = []

for var in variations:
    case_id = var["id"]
    output_dir = f"runs/run_{case_id}"
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n=======================================================")
    print(f"EXECUTING {case_id}: {var['title']}")
    print(f"=======================================================")

    # Synthesize spec from diff
    spec = synth.synthesize(var["diff"], case_id=case_id, git_commit=f"git-{case_id}")
    spec_path = os.path.join(output_dir, "experiment.yaml")
    with open(spec_path, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, sort_keys=False)

    # 1. Apply BASE PR code
    pr_code = (
        orig_code
        .replace('RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))', f'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "{var["retries_max"]}"))')
        .replace('RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))', f'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "{var["timeout_s"]}"))')
        .replace('RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))', f'RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "{var["backoff"]}"))')
    )
    with open(CHECKOUT_MAIN, "w", encoding="utf-8") as f:
        f.write(pr_code)

    print(f"[{case_id}] Building checkout-service (BASE state)...")
    subprocess.run(["docker", "compose", "build", "checkout-service"], check=False)
    subprocess.run(["docker", "compose", "up", "-d", "checkout-service"], check=False)
    time.sleep(2.5)

    # Inject fault for BASE phase
    toxi.reset()
    toxi.add_latency("payment-proxy", latency_ms=var["latency_ms"], jitter_ms=var["jitter_ms"])

    pre_m_base = read_direct_metrics("http://localhost:8001/metrics")
    t0_base = time.time()
    asyncio.run(
        run_live_http_workload(
            "http://localhost:8000/orders",
            total_requests=var["total_requests"],
            concurrency=var["concurrency"],
            timeout_s=6.0,
        )
    )
    t_base_end = time.time()
    dur_base = max(0.001, t_base_end - t0_base)
    time.sleep(1.5)
    post_m_base = read_direct_metrics("http://localhost:8001/metrics")

    retries_base = max(0.0, post_m_base["retry_count"] - pre_m_base["retry_count"])
    reqs_base = max(0.0, post_m_base["checkout_requests"] - pre_m_base["checkout_requests"]) or float(var["total_requests"])
    ratio_base = round(retries_base / reqs_base, 4)
    rate_base = round((retries_base / dur_base) * 60.0, 2)
    tp_base = round(reqs_base / dur_base, 2)

    base_csv = os.path.join(output_dir, "metrics_base.csv")
    with open(base_csv, "w", encoding="utf-8") as f:
        f.write("timestamp,metric_name,value\n")
        f.write(f"{int(t0_base)},retry_count_total,{pre_m_base['retry_count']}\n")
        f.write(f"{int(t_base_end)},retry_count_total,{post_m_base['retry_count']}\n")
        f.write(f"{int(t0_base)},checkout_requests_total,{pre_m_base['checkout_requests']}\n")
        f.write(f"{int(t_base_end)},checkout_requests_total,{post_m_base['checkout_requests']}\n")

    base_summary = {
        "phase": "base",
        "duration_s": round(dur_base, 2),
        "total_requests": reqs_base,
        "retries_counted": retries_base,
        "retries_per_request": ratio_base,
        "rate_per_min": rate_base,
        "throughput_req_per_sec": tp_base,
        "metrics_csv": base_csv,
    }
    with open(os.path.join(output_dir, "manifest_base.json"), "w", encoding="utf-8") as f:
        json.dump(base_summary, f, indent=2)

    # 2. Apply Remediation (PATCHED state: RETRIES_MAX=2, TIMEOUT=1.0, BACKOFF=0.5)
    remediated_code = (
        orig_code
        .replace('RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))', 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "2"))')
        .replace('RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))', 'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))')
        .replace('RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))', 'RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))')
    )
    with open(CHECKOUT_MAIN, "w", encoding="utf-8") as f:
        f.write(remediated_code)

    print(f"[{case_id}] Building checkout-service (PATCHED state)...")
    subprocess.run(["docker", "compose", "build", "checkout-service"], check=False)
    subprocess.run(["docker", "compose", "up", "-d", "checkout-service"], check=False)
    time.sleep(2.5)

    toxi.reset()
    toxi.add_latency("payment-proxy", latency_ms=var["latency_ms"], jitter_ms=var["jitter_ms"])

    pre_m_patch = read_direct_metrics("http://localhost:8001/metrics")
    t0_patch = time.time()
    asyncio.run(
        run_live_http_workload(
            "http://localhost:8000/orders",
            total_requests=var["total_requests"],
            concurrency=var["concurrency"],
            timeout_s=6.0,
        )
    )
    t_patch_end = time.time()
    dur_patch = max(0.001, t_patch_end - t0_patch)
    time.sleep(1.5)
    post_m_patch = read_direct_metrics("http://localhost:8001/metrics")

    retries_patch = max(0.0, post_m_patch["retry_count"] - pre_m_patch["retry_count"])
    reqs_patch = max(0.0, post_m_patch["checkout_requests"] - pre_m_patch["checkout_requests"]) or float(var["total_requests"])
    ratio_patch = round(retries_patch / reqs_patch, 4)
    rate_patch = round((retries_patch / dur_patch) * 60.0, 2)
    tp_patch = round(reqs_patch / dur_patch, 2)

    patched_csv = os.path.join(output_dir, "metrics_patched.csv")
    with open(patched_csv, "w", encoding="utf-8") as f:
        f.write("timestamp,metric_name,value\n")
        f.write(f"{int(t0_patch)},retry_count_total,{pre_m_patch['retry_count']}\n")
        f.write(f"{int(t_patch_end)},retry_count_total,{post_m_patch['retry_count']}\n")
        f.write(f"{int(t0_patch)},checkout_requests_total,{pre_m_patch['checkout_requests']}\n")
        f.write(f"{int(t_patch_end)},checkout_requests_total,{post_m_patch['checkout_requests']}\n")

    patched_summary = {
        "phase": "patched",
        "duration_s": round(dur_patch, 2),
        "total_requests": reqs_patch,
        "retries_counted": retries_patch,
        "retries_per_request": ratio_patch,
        "rate_per_min": rate_patch,
        "throughput_req_per_sec": tp_patch,
        "metrics_csv": patched_csv,
    }
    with open(os.path.join(output_dir, "manifest_patched.json"), "w", encoding="utf-8") as f:
        json.dump(patched_summary, f, indent=2)

    # Restore baseline
    with open(CHECKOUT_MAIN, "w", encoding="utf-8") as f:
        f.write(orig_code)

    toxi.reset()

    # Manifest
    manifest_data = {
        "experiment_id": case_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base": base_summary,
        "patched": patched_summary,
    }
    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # Deterministic verification
    ver_res = verify(base_csv, patched_csv, spec["assertions"])
    print(f"[{case_id}] VERDICT: {ver_res.status} (Pre ratio: {ratio_base}, Post ratio: {ratio_patch})")

    # Multi-hypothesis evaluation & certificate
    signals = ["Aggressive retry count increase (max_retries >= 4)"]
    if var["backoff"] == 0.0:
        signals.append("Removal of backoff / immediate retry execution")
    if var["timeout_s"] < 1.0:
        signals.append("Aggressive timeout reduction (timeout < 1.0s)")

    candidate_hypos = generate_candidate_hypotheses(signals, proxy_name="payment-proxy", calibrated_latency_ms=var["latency_ms"])
    evaluated_hypos = evaluate_hypotheses_evidence(
        candidate_hypos,
        pre_summary=base_summary,
        post_summary=patched_summary,
        calibrated_latency_ms=var["latency_ms"],
        client_timeout_s=var["timeout_s"],
    )

    cert_path = os.path.join(output_dir, "proof_certificate.md")
    cert_gen.generate_and_save({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment_id": case_id,
        "git_commit": f"git-{case_id}",
        "risk_level": "HIGH",
        "risk_score": 70 if len(signals) >= 2 else 50,
        "hypothesis_title": spec["title"],
        "hypothesis_confidence": "HIGH",
        "candidate_hypotheses": evaluated_hypos,
        "verification_status": ver_res.status,
        "diff_table": ver_res.diff_table,
        "pre_summary": base_summary,
        "post_summary": patched_summary,
        "capsule_path": f"capsules/{case_id}.zip",
    }, cert_path)

    capsule_zip = packager.create_capsule(
        experiment_id=case_id,
        run_dir=output_dir,
        git_commit_base=f"git-{case_id}",
    )
    print(f"[{case_id}] Packaged capsule: {capsule_zip}")

    results_summary.append({
        "case_id": case_id,
        "title": var["title"],
        "pre_retries_per_req": ratio_base,
        "post_retries_per_req": ratio_patch,
        "verdict": ver_res.status,
        "capsule": capsule_zip,
    })

print("\n=======================================================")
print("ALL 5 CONTROLLED VARIATIONS EXECUTED LIVE!")
print("=======================================================")
for r in results_summary:
    print(f"  * {r['case_id']}: Pre={r['pre_retries_per_req']} -> Post={r['post_retries_per_req']} | VERDICT: [{r['verdict']}] | Capsule: {r['capsule']}")
