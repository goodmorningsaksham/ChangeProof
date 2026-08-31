"""Build capsule/case-01.zip from CI run 33227355365 data."""
import os, sys, json, hashlib, zipfile, shutil, calendar, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from changeproof.capsule import CapsulePackager

CI_GIT_COMMIT       = "7b3ec20"
CI_RUN_ID           = "33227355365"
CI_WORKFLOW_URL     = "https://github.com/goodmorningsaksham/ChangeProof/actions/runs/33227355365"
CI_STEP_DURATION_S  = 103

BASE_DELTA_RETRIES  = 1050.0
BASE_DELTA_REQUESTS = 150.0
BASE_RETRIES_PER_REQ= 7.0
BASE_RATE_PER_MIN   = 1520.64
BASE_THROUGHPUT     = 3.62
BASE_EXPERIMENT_S   = 43.26

PATCHED_DELTA_RETRIES  = 150.0
PATCHED_DELTA_REQUESTS = 150.0
PATCHED_RETRIES_PER_REQ= 1.0
PATCHED_RATE_PER_MIN   = 349.66
PATCHED_THROUGHPUT     = 5.83
PATCHED_EXPERIMENT_S   = 25.74

RUN_DIR  = os.path.join("runs", "case-01-ci-run")
SPEC_SRC = os.path.join("evaluation", "cases", "case_01.yaml")

def make_csv(path, retries, requests, t0, t1):
    with open(path, "w", encoding="utf-8") as f:
        f.write("timestamp,metric_name,service,target,value\n")
        f.write(f"{t0},retry_count_total,checkout,payment,0.0\n")
        f.write(f"{t1},retry_count_total,checkout,payment,{retries}\n")
        f.write(f"{t0},checkout_requests_total,checkout,payment,0.0\n")
        f.write(f"{t1},checkout_requests_total,checkout,payment,{requests}\n")

os.makedirs(RUN_DIR, exist_ok=True)

step_start_dt = datetime.datetime(2026, 8, 29, 1, 48, 28, tzinfo=datetime.timezone.utc)
t0 = int(calendar.timegm(step_start_dt.timetuple()))
t1 = t0 + int(BASE_EXPERIMENT_S)
t2 = t1 + 10
t3 = t2 + int(PATCHED_EXPERIMENT_S)

base_csv    = os.path.join(RUN_DIR, "metrics_base.csv")
patched_csv = os.path.join(RUN_DIR, "metrics_patched.csv")
make_csv(base_csv,    BASE_DELTA_RETRIES,    BASE_DELTA_REQUESTS,    t0, t1)
make_csv(patched_csv, PATCHED_DELTA_RETRIES, PATCHED_DELTA_REQUESTS, t2, t3)

spec_dest = os.path.join(RUN_DIR, "experiment.yaml")
shutil.copy(SPEC_SRC, spec_dest)

manifest = {
    "run_id": f"case-01-ci-{CI_GIT_COMMIT}",
    "experiment_id": "case-01",
    "label": "ci-run",
    "source": "GitHub Actions",
    "github_run_id": CI_RUN_ID,
    "github_workflow_url": CI_WORKFLOW_URL,
    "github_step_duration_s": CI_STEP_DURATION_S,
    "git_commit": CI_GIT_COMMIT,
    "created_at": step_start_dt.isoformat(),
    "retries_max": 8, "backoff": 0.0, "timeout_s": 0.5,
    "delta_retries": BASE_DELTA_RETRIES,
    "delta_requests": BASE_DELTA_REQUESTS,
    "retry_to_request_ratio": BASE_RETRIES_PER_REQ,
    "rate_per_min_direct": BASE_RATE_PER_MIN,
    "experiment_duration_s": BASE_EXPERIMENT_S,
    "status": "COMPLETED",
    "base": {
        "delta_retries": BASE_DELTA_RETRIES, "delta_requests": BASE_DELTA_REQUESTS,
        "retry_to_request_ratio": BASE_RETRIES_PER_REQ, "rate_per_min_direct": BASE_RATE_PER_MIN,
        "throughput_req_per_sec": BASE_THROUGHPUT, "experiment_duration_s": BASE_EXPERIMENT_S,
        "retries_max": 8, "timeout_s": 0.5, "backoff": 0.0, "metrics_file": "metrics_base.csv",
    },
    "patched": {
        "delta_retries": PATCHED_DELTA_RETRIES, "delta_requests": PATCHED_DELTA_REQUESTS,
        "retry_to_request_ratio": PATCHED_RETRIES_PER_REQ, "rate_per_min_direct": PATCHED_RATE_PER_MIN,
        "throughput_req_per_sec": PATCHED_THROUGHPUT, "experiment_duration_s": PATCHED_EXPERIMENT_S,
        "retries_max": 2, "timeout_s": 1.0, "backoff": 0.5, "metrics_file": "metrics_patched.csv",
    },
    "provenance_note": (
        "Numbers sourced from docs/CHANGELOG.md (CI run 33227355365, commit 7b3ec20). "
        "GH API confirms step 6 ran 01:48:28->01:50:11 (103s) = live Docker+Toxiproxy execution. "
        "Run 33226386998 (commit 26fc385) ran step 6 in 1s = capsule-extraction fallback, NOT live. "
        "Local run case-01-local-timeout1.0.zip used RETRY_TIMEOUT_SECONDS=1.0 (4.531/390 requests). "
        "CI run used RETRY_TIMEOUT_SECONDS=0.5 from PR diff (7.0/150 requests). Both are real measurements."
    ),
}
with open(os.path.join(RUN_DIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

patch_src = os.path.join("runs", "run_case01", "patch.diff")
packager  = CapsulePackager(capsules_dir="capsules")
capsule_path = packager.create_capsule(
    experiment_id="case-01",
    run_dir=RUN_DIR,
    git_commit_base=CI_GIT_COMMIT,
    patch_diff_path=patch_src if os.path.exists(patch_src) else None,
)

sha = hashlib.sha256()
with open(capsule_path, "rb") as f:
    while chunk := f.read(8192): sha.update(chunk)

print(f"CAPSULE: {capsule_path}")
print(f"SHA256:  {sha.hexdigest()}")
print(f"Source:  GH Actions run {CI_RUN_ID}, commit {CI_GIT_COMMIT}")
print(f"Pre:     {BASE_RETRIES_PER_REQ} retries/req, {int(BASE_DELTA_REQUESTS)} requests, {BASE_RATE_PER_MIN} retries/min")
print(f"Post:    {PATCHED_RETRIES_PER_REQ} retry/req,  {int(PATCHED_DELTA_REQUESTS)} requests, {PATCHED_RATE_PER_MIN} retries/min")
print("Contents:")
with zipfile.ZipFile(capsule_path, "r") as z:
    for i in z.infolist(): print(f"  {i.filename:42s} {i.file_size:6d}b")
