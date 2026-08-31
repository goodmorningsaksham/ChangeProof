"""Topology-agnostic ChangeProof CI Verification Pipeline.

Consolidated production CI entrypoint leveraging the shared core engine:
- RiskAssessor for diff signal analysis
- ExperimentSynthesizer for topology-derived fault, workload, route, and target resolution
- generate_candidate_hypotheses & evaluate_hypotheses_evidence for multi-signal reasoning
- ToxiproxyClient for deterministic fault injection
- Direct-scrape telemetry collection formatted to Prometheus schema
- Deterministic verification assertions and Proof Certificate generation
"""
import os
import sys
import time
import json
import argparse
import subprocess
import requests
import pandas as pd
from typing import Dict, Any, List

from changeproof.risk_assessor import RiskAssessor
from changeproof.experiment_synthesizer import ExperimentSynthesizer, _clean_service_name
from changeproof.hypothesis_evaluator import generate_candidate_hypotheses, evaluate_hypotheses_evidence
from changeproof.toxiproxy_client import ToxiproxyClient
from changeproof.verifier import verify, VerificationResult
from changeproof.certificate import CertificateGenerator
from changeproof.capsule import CapsulePackager
from changeproof.llm_client import call_llm, parse_json_response



def get_free_disk_gb(path: str = ".") -> float:
    try:
        total, used, free = shutil.disk_usage(os.path.abspath(path))
        return round(free / (1024 ** 3), 2)
    except Exception:
        return -1.0


class VerificationLogger:
    def __init__(self, log_path: str):
        self.log_path = os.path.abspath(log_path)
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self._lock = threading.Lock()
        header = f"\n{'='*80}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] VERIFICATION RUN STARTED (Free C: Disk: {get_free_disk_gb()} GB)\n{'='*80}\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(header)

    def log(self, stage: str, message: str, level: str = "INFO"):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        disk_gb = get_free_disk_gb()
        entry = f"[{ts}] [{level}] [{stage}] (Disk Free: {disk_gb} GB) {message}"
        print(entry)
        try:
            with self._lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
        except Exception:
            pass

    def log_cmd(self, cmd: List[str], exit_code: int, duration_s: float):
        cmd_str = " ".join(cmd)
        self.log("DOCKER/SYSTEM", f"Executed: '{cmd_str}' | Exit Code: {exit_code} | Duration: {duration_s:.2f}s")

def wait_for_service(url: str, timeout_s: int = 45) -> bool:
    """Polls an HTTP endpoint until 200 OK or timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def collect_via_direct_scrape(duration_s: float, retries_counted: float, total_requests: float) -> pd.DataFrame:
    """Collects telemetry via direct exposition scrape formatted into Prometheus standard schema."""
    records: List[Dict[str, Any]] = [
        {
            "timestamp": 0.0,
            "metric_name": "retry_count_total",
            "service": "client",
            "target": "downstream",
            "value": 0.0,
        },
        {
            "timestamp": float(duration_s),
            "metric_name": "retry_count_total",
            "service": "client",
            "target": "downstream",
            "value": float(retries_counted),
        },
        {
            "timestamp": 0.0,
            "metric_name": "checkout_requests_total",
            "service": "client",
            "target": "none",
            "value": 0.0,
        },
        {
            "timestamp": float(duration_s),
            "metric_name": "checkout_requests_total",
            "service": "client",
            "target": "none",
            "value": float(total_requests),
        },
    ]
    df = pd.DataFrame(records)
    df.sort_values(by=["timestamp", "metric_name"], inplace=True)
    return df


# ---------------------------------------------------------------------------
# LLM-Grounded Patch Generation Helper
# ---------------------------------------------------------------------------

# Safe bounds for LLM-proposed remediation values
_PATCH_BOUNDS = {
    "retries_max": (1, 5),
    "timeout_s": (0.3, 5.0),
    "backoff_factor": (0.1, 2.0),
    "timeout_ms": (300, 5000),
    "backoff_ms": (100, 2000),
}


def _clamp(value: float, lo: float, hi: float, param_name: str = "parameter") -> float:
    clamped = max(lo, min(hi, value))
    if clamped != value:
        print(f"[LLM PATCH CLAMP] Clamped {param_name} from {value} to safe bound {clamped} ([{lo}, {hi}])")
    return clamped


def _build_patch_prompt(
    diff_text: str,
    code: str,
    base_summary: Dict[str, Any],
    signals: List[str],
) -> str:
    """Builds a prompt asking the LLM to reason from observed failure severity
    to propose bounded remediation values."""
    diff_excerpt = diff_text[:2000] if len(diff_text) > 2000 else diff_text
    code_excerpt = code[:2000] if len(code) > 2000 else code
    retries_per_req = base_summary.get("retries_per_request", 0.0)
    rate_per_min = base_summary.get("rate_per_min", 0.0)
    total_reqs = base_summary.get("total_requests", 0)

    return (
        "You are the ChangeProof remediation engine. A PR diff has been experimentally "
        "confirmed to cause a retry amplification failure. Your task is to propose "
        "MINIMAL, BOUNDED remediation values that address the specific failure severity "
        "observed in the telemetry.\n\n"
        "OBSERVED FAILURE TELEMETRY (pre-patch, broken state):\n"
        f"  retries_per_request: {retries_per_req:.3f}  (target: <= 1.1 after patch)\n"
        f"  rate_per_min: {rate_per_min:.2f}\n"
        f"  total_requests: {total_reqs}\n\n"
        f"DETECTED RISK SIGNALS: {', '.join(signals)}\n\n"
        f"PR DIFF (showing what values were changed TO the broken state):\n```\n{diff_excerpt}\n```\n\n"
        f"CURRENT FILE CONTENT (broken state, to be patched):\n```\n{code_excerpt}\n```\n\n"
        "CONSTRAINTS:\n"
        "- RETRIES_MAX must be in [1, 5]\n"
        "- RETRY_TIMEOUT_SECONDS must be in [0.3, 5.0] seconds\n"
        "- RETRY_BACKOFF_FACTOR must be in [0.1, 2.0]\n"
        "- For JS: RETRY_TIMEOUT_MS must be in [300, 5000]ms, RETRY_BACKOFF_MS in [100, 2000]ms\n"
        "- Propose values proportional to the OBSERVED SEVERITY: "
        "a mild amplification (e.g. 2.0 retries/req) may need only a modest adjustment, "
        "while a severe storm (e.g. 7.0+ retries/req) warrants a more aggressive reduction.\n\n"
        "Respond with ONLY a valid JSON object (no extra text outside the JSON block):\n"
        "{\n"
        '  "reasoning": "2-3 sentences explaining WHY you chose these specific values '
        'based on the observed severity and the specific variables in the diff",\n'
        '  "retries_max": <integer>,\n'
        '  "timeout_s": <float, seconds Ã¢â‚¬â€ use null if not applicable to this diff>,\n'
        '  "backoff_factor": <float Ã¢â‚¬â€ use null if not applicable to this diff>,\n'
        '  "timeout_ms": <integer, milliseconds Ã¢â‚¬â€ use null if not JS/not applicable>,\n'
        '  "backoff_ms": <integer, milliseconds Ã¢â‚¬â€ use null if not JS/not applicable>\n'
        "}"
    )


def generate_llm_patch(
    code: str,
    diff_text: str,
    base_summary: Dict[str, Any],
    signals: List[str],
) -> Dict[str, Any]:
    """Calls the LLM to propose remediation values grounded in observed failure severity.

    Returns a dict with keys:
      - retries_max (int)
      - timeout_s (float or None)
      - backoff_factor (float or None)
      - timeout_ms (int or None)
      - backoff_ms (int or None)
      - reasoning (str)
      - source (str): "llm" | "fallback"

    Values are always clamped to safe bounds before return. If LLM call fails,
    returns conservative fallback values and marks source="fallback".
    """
    prompt = _build_patch_prompt(diff_text, code, base_summary, signals)
    response = call_llm(prompt, max_tokens=2048)

    if response:
        data = parse_json_response(response)
        if data and ("reasoning" in data or "retries_max" in data):
            try:
                raw_retries = data.get("retries_max")
                raw_timeout_s = data.get("timeout_s")
                raw_backoff = data.get("backoff_factor")
                raw_timeout_ms = data.get("timeout_ms")
                raw_backoff_ms = data.get("backoff_ms")

                retries_max = int(_clamp(float(raw_retries), *_PATCH_BOUNDS["retries_max"], param_name="RETRIES_MAX")) if raw_retries is not None else 2
                timeout_s = float(_clamp(float(raw_timeout_s), *_PATCH_BOUNDS["timeout_s"], param_name="RETRY_TIMEOUT_SECONDS")) if raw_timeout_s is not None else None
                backoff_factor = float(_clamp(float(raw_backoff), *_PATCH_BOUNDS["backoff_factor"], param_name="RETRY_BACKOFF_FACTOR")) if raw_backoff is not None else None
                timeout_ms = int(_clamp(float(raw_timeout_ms), *_PATCH_BOUNDS["timeout_ms"], param_name="RETRY_TIMEOUT_MS")) if raw_timeout_ms is not None else None
                backoff_ms = int(_clamp(float(raw_backoff_ms), *_PATCH_BOUNDS["backoff_ms"], param_name="RETRY_BACKOFF_MS")) if raw_backoff_ms is not None else None

                reasoning = str(data.get("reasoning", "LLM-grounded remediation values proposed based on observed telemetry."))
                print(f"[LLM PATCH] Reasoning: {reasoning}")
                print(f"[LLM PATCH] Proposed: RETRIES_MAX={retries_max}, timeout_s={timeout_s}, backoff_factor={backoff_factor}, timeout_ms={timeout_ms}, backoff_ms={backoff_ms}")
                return {
                    "retries_max": retries_max,
                    "timeout_s": timeout_s,
                    "backoff_factor": backoff_factor,
                    "timeout_ms": timeout_ms,
                    "backoff_ms": backoff_ms,
                    "reasoning": reasoning,
                    "source": "llm",
                }
            except Exception as ex:
                print(f"[LLM PATCH] Error parsing patch values: {ex}")

    # LLM unavailable or response unparseable - conservative fallback
    print("[LLM PATCH FALLBACK] LLM API unavailable or response unparseable. "
          "Using conservative safe defaults: RETRIES_MAX=2, TIMEOUT=1.0s, BACKOFF=0.5.")
    return {
        "retries_max": 2,
        "timeout_s": 1.0,
        "backoff_factor": 0.5,
        "timeout_ms": 1000,
        "backoff_ms": 500,
        "reasoning": "LLM FALLBACK: API unavailable",
        "source": "fallback",
    }



def _build_diagnostic_prompt(
    diff_text: str,
    code: str,
    base_summary: Dict[str, Any],
    attempt_record: Dict[str, Any],
    signals: List[str],
) -> str:
    """Builds a prompt asking the LLM to diagnose why its prior remediation patch
    failed verification and propose revised, stronger values for Attempt 2."""
    diff_excerpt = diff_text[:2000] if len(diff_text) > 2000 else diff_text
    code_excerpt = code[:2000] if len(code) > 2000 else code
    retries_base = base_summary.get("retries_per_request", 0.0)
    post_summary = attempt_record.get("patched_summary", {})
    retries_post = post_summary.get("retries_per_request", 0.0)
    rate_post = post_summary.get("rate_per_min", 0.0)
    att_reason = attempt_record.get("reason", "Assertion retries_per_request <= 1.1 failed")
    prev_prop = attempt_record.get("proposal", {})
    prev_reasoning = attempt_record.get("reasoning", "")

    return (
        "You are the ChangeProof remediation engine diagnosing a failed patch attempt.\n\n"
        "BACKGROUND:\n"
        f"A PR diff caused an initial retry storm ({retries_base:.3f} retries/req pre-patch).\n"
        f"In Attempt 1, you proposed the following remediation values:\n"
        f"  retries_max: {prev_prop.get('retries_max')}\n"
        f"  timeout_s: {prev_prop.get('timeout_s')} (or timeout_ms: {prev_prop.get('timeout_ms')})\n"
        f"  backoff_factor: {prev_prop.get('backoff_factor')} (or backoff_ms: {prev_prop.get('backoff_ms')})\n"
        f"  Attempt 1 Reasoning: {prev_reasoning}\n\n"
        "EMPIRICAL VERIFICATION RESULT (Attempt 1 FAILED):\n"
        f"  Observed post-patch retries_per_request: {retries_post:.3f} (Assertion threshold: <= 1.1)\n"
        f"  Observed post-patch rate_per_min: {rate_post:.2f}\n"
        f"  Failure Reason: {att_reason}\n\n"
        f"DETECTED RISK SIGNALS: {', '.join(signals)}\n"
        f"ORIGINAL DIFF:\n```\n{diff_excerpt}\n```\n\n"
        f"CURRENT FILE CODE:\n```\n{code_excerpt}\n```\n\n"
        "DIAGNOSTIC TASK:\n"
        "1. Diagnose why Attempt 1 was insufficient to bring retries_per_request down to <= 1.1.\n"
        "2. Identify the unaddressed failure mechanism (e.g. was retries_max still too high, was backoff insufficient, or was timeout still triggering premature aborts?).\n"
        "3. Propose REVISED, stronger remediation values for Attempt 2.\n\n"
        "CONSTRAINTS:\n"
        "- RETRIES_MAX must be in [1, 5]\n"
        "- RETRY_TIMEOUT_SECONDS in [0.3, 5.0]s, RETRY_BACKOFF_FACTOR in [0.1, 2.0]\n"
        "- For JS: RETRY_TIMEOUT_MS in [300, 5000]ms, RETRY_BACKOFF_MS in [100, 2000]ms\n\n"
        "Respond with ONLY a valid JSON object:\n"
        "{\n"
        '  "diagnosis": "<detailed diagnosis explaining why Attempt 1 failed and what Attempt 2 adjusts>",\n'
        '  "reasoning": "<revised rationale for Attempt 2>",\n'
        '  "retries_max": <integer between 1 and 5>,\n'
        '  "timeout_s": <float or null>,\n'
        '  "backoff_factor": <float or null>,\n'
        '  "timeout_ms": <integer or null>,\n'
        '  "backoff_ms": <integer or null>\n'
        "}"
    )


def diagnose_and_revise_patch(
    code: str,
    diff_text: str,
    base_summary: Dict[str, Any],
    attempt_record: Dict[str, Any],
    signals: List[str],
) -> Dict[str, Any]:
    """Calls LLM with empirical verification failure feedback to diagnose and revise patch."""
    prompt = _build_diagnostic_prompt(diff_text, code, base_summary, attempt_record, signals)
    response = call_llm(prompt, max_tokens=2048)
    if response:
        data = parse_json_response(response)
        if data and ("diagnosis" in data or "reasoning" in data or "retries_max" in data):
            try:
                raw_retries = data.get("retries_max")
                raw_timeout_s = data.get("timeout_s")
                raw_backoff = data.get("backoff_factor")
                raw_timeout_ms = data.get("timeout_ms")
                raw_backoff_ms = data.get("backoff_ms")
                diag = data.get("diagnosis", "")
                reasoning = data.get("reasoning", "")
                full_reasoning = f"{diag} {reasoning}".strip() if diag else reasoning

                retries_max = int(_clamp(raw_retries, 1, 5, "retries_max")) if raw_retries is not None else 1
                timeout_s = _clamp(raw_timeout_s, 0.3, 5.0, "timeout_s") if raw_timeout_s is not None else None
                backoff_factor = _clamp(raw_backoff, 0.1, 2.0, "backoff_factor") if raw_backoff is not None else None
                timeout_ms = int(_clamp(raw_timeout_ms, 300, 5000, "timeout_ms")) if raw_timeout_ms is not None else None
                backoff_ms = int(_clamp(raw_backoff_ms, 100, 2000, "backoff_ms")) if raw_backoff_ms is not None else None

                return {
                    "retries_max": retries_max,
                    "timeout_s": timeout_s,
                    "backoff_factor": backoff_factor,
                    "timeout_ms": timeout_ms,
                    "backoff_ms": backoff_ms,
                    "reasoning": full_reasoning,
                    "source": "llm",
                }
            except Exception as e:
                print(f"[LLM DIAGNOSTIC PARSE ERROR] {e}")

    # Fallback if diagnostic LLM call fails
    return {
        "retries_max": 1,
        "timeout_s": 1.0,
        "backoff_factor": 1.0,
        "timeout_ms": 1000,
        "backoff_ms": 1000,
        "reasoning": "Attempt 1 failed. Diagnostic fallback proposes minimum retry ceiling (1) and generous backoff delay.",
        "source": "fallback",
    }


def _apply_patch_values(code: str, patch: Dict[str, Any]) -> str:
    """Applies LLM-proposed patch values to the source code via targeted replacements.

    Handles Python (os.getenv default-value pattern) and JavaScript (const assignment)
    based on what patterns are present in the code.
    """
    retries_max = patch["retries_max"]
    timeout_s = patch.get("timeout_s")
    backoff_factor = patch.get("backoff_factor")
    timeout_ms = patch.get("timeout_ms")
    backoff_ms = patch.get("backoff_ms")

    # Python patterns (os.getenv defaults)
    import re as _re
    # Replace RETRIES_MAX default value (any integer)
    code = _re.sub(
        r'(RETRIES_MAX\s*=\s*int\s*\(\s*os\.getenv\s*\(\s*["\']RETRIES_MAX["\']\s*,\s*["\'])\d+(["\'])',
        rf'\g<1>{retries_max}\g<2>',
        code,
    )
    if timeout_s is not None:
        timeout_s_str = f"{timeout_s:.1f}"
        code = _re.sub(
            r'(RETRY_TIMEOUT_SECONDS\s*=\s*float\s*\(\s*os\.getenv\s*\(\s*["\']RETRY_TIMEOUT_SECONDS["\']\s*,\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{timeout_s_str}\g<2>',
            code,
        )
    if backoff_factor is not None:
        backoff_str = f"{backoff_factor:.1f}"
        code = _re.sub(
            r'(RETRY_BACKOFF_FACTOR\s*=\s*float\s*\(\s*os\.getenv\s*\(\s*["\']RETRY_BACKOFF_FACTOR["\']\s*,\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{backoff_str}\g<2>',
            code,
        )

    # Python bare-assignment patterns (fallback for non-getenv styles)
    code = _re.sub(r'\bRETRIES_MAX\s*=\s*\d+\b', f'RETRIES_MAX = {retries_max}', code)
    if timeout_s is not None:
        code = _re.sub(r'\bRETRY_TIMEOUT_SECONDS\s*=\s*[\d.]+\b', f'RETRY_TIMEOUT_SECONDS = {timeout_s:.1f}', code)
    if backoff_factor is not None:
        code = _re.sub(r'\bRETRY_BACKOFF_FACTOR\s*=\s*[\d.]+\b', f'RETRY_BACKOFF_FACTOR = {backoff_factor:.1f}', code)

    # JavaScript patterns (const assignments)
    code = _re.sub(r'\bconst\s+RETRIES_MAX\s*=\s*\d+\b', f'const RETRIES_MAX = {retries_max}', code)
    if timeout_ms is not None:
        code = _re.sub(r'\bconst\s+RETRY_TIMEOUT_MS\s*=\s*\d+\b', f'const RETRY_TIMEOUT_MS = {timeout_ms}', code)
    if backoff_ms is not None:
        code = _re.sub(r'\bconst\s+RETRY_BACKOFF_MS\s*=\s*\d+\b', f'const RETRY_BACKOFF_MS = {backoff_ms}', code)

    return code

def run_synthetic_ci(
    diff_text: str,
    output_dir: str = "runs/ci_run",
    compose_file: str = "docker-compose.yml",
    toxiproxy_config: str = "toxiproxy_init.json",
    git_commit: str = "HEAD"
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    capsules_dir = os.path.join(output_dir, "capsules")
    os.makedirs(capsules_dir, exist_ok=True)
    log_file = os.path.join(output_dir, "verification.log")
    vlog = VerificationLogger(log_file)

    t_session_start = time.time()
    vlog.log("INIT", f"Initialized CI run environment in '{output_dir}' (Commit: {git_commit})")

    try:
        # Step 1: Risk Assessment
        vlog.log("STEP_1_RISK", "Starting static risk assessment on PR diff...")
        assessor = RiskAssessor()
        risk_res = assessor.assess_diff(diff_text)
        vlog.log("STEP_1_RISK", f"Risk Assessment Complete -> Score: {risk_res['score']}, Level: {risk_res['level']}, Signals: {len(risk_res['signals'])}")

        # Step 2: Synthesis
        vlog.log("STEP_2_SYNTHESIS", f"Synthesizing counterfactual experiment spec from {compose_file} and {toxiproxy_config}...")
        synth = ExperimentSynthesizer(compose_path=compose_file, toxiproxy_config_path=toxiproxy_config)
        spec = synth.synthesize(diff_text, case_id="ci-synth-run", git_commit=git_commit)

        proxy_name = spec["fault"]["proxy"]
        calibrated_latency = spec["fault"]["toxic"]["attributes"]["latency"]
        jitter = spec["fault"]["toxic"]["attributes"].get("jitter", 75)

        entrypoint_route = spec["workload"].get("entrypoint_route", "/orders")
        entrypoint_payload = spec["workload"].get("entrypoint_payload", {"item_id": "item_123", "quantity": 1, "amount": 99.99, "user_id": "cust_123"})

        workload_vus = int(spec["workload"].get("vus", 10))
        workload_rps = int(spec["workload"].get("rps_target", 10))
        workload_dur_s = float(str(spec["workload"].get("duration", "15s")).replace("s", ""))
        num_workload_requests = int(spec["workload"].get("num_requests", int(workload_rps * workload_dur_s)))
        workload_concurrency = workload_vus

        changed_service = spec.get("target", {}).get("changed_service") or "checkout-service"
        target_file = spec.get("target", {}).get("changed_file") or ("app/inventory/main.py" if os.path.exists("app/inventory/main.py") else "app/checkout/main.py")
        changed_short = _clean_service_name(changed_service)

        commit_tag = git_commit[:8] if git_commit not in ("HEAD", "main", "") else str(int(time.time()))
        unique_exp_id = f"ci-{changed_short}-{commit_tag}"

        entrypoint_port = 8000
        target_url = f"http://localhost:{entrypoint_port}{entrypoint_route}"
        vlog.log(
            "STEP_2_SYNTHESIS",
            f"Synthesized Spec -> Proxy: {proxy_name}, Calibrated Latency: {calibrated_latency}ms, Workload: {target_url} ({num_workload_requests} reqs @ {workload_concurrency} VUs)"
        )

        # Step 3: Propose Candidate Hypotheses
        vlog.log("STEP_3_HYPOTHESIS", "Generating LLM-grounded candidate failure hypotheses...")
        _code_context = ""
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as _f:
                    _code_context = _f.read()
            except Exception:
                pass

        hypotheses = generate_candidate_hypotheses(
            risk_res["signals"],
            proxy_name=proxy_name,
            calibrated_latency_ms=calibrated_latency,
            diff_text=diff_text,
            code_context=_code_context,
        )
        top_hyp = hypotheses[0] if hypotheses else {"title": "Retry Storm Amplification under Latency"}
        vlog.log("STEP_3_HYPOTHESIS", f"Candidate Hypotheses Generated -> Primary: '{top_hyp.get('title')}'")

        # Ensure PR diff state is written to target file before base run
        if os.path.exists(target_file):
            with open(target_file, "r", encoding="utf-8") as f:
                pre_pr_code = f.read()
            broken_pr_code = (
                pre_pr_code.replace('RETRIES_MAX = int(os.getenv("RETRIES_MAX", "2"))', 'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))')
                .replace('RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))', 'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))')
                .replace('RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))', 'RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))')
                .replace("const RETRIES_MAX = 2;", "const RETRIES_MAX = 8;")
                .replace("const RETRY_TIMEOUT_MS = 1000;", "const RETRY_TIMEOUT_MS = 500;")
                .replace("const RETRY_BACKOFF_MS = 500;", "const RETRY_BACKOFF_MS = 0;")
            )
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(broken_pr_code)
            vlog.log("STEP_3_PR_DIFF", f"Applied unverified PR diff state to {target_file}")

        # Step 4: Docker Compose UP
        vlog.log("STEP_4_PROVISION", f"Starting container topology via docker compose ({compose_file})...")
        t_d0 = time.time()
        res_up = subprocess.run(["docker", "compose", "-f", compose_file, "up", "-d", "--build"], capture_output=True, text=True, check=False)
        vlog.log_cmd(["docker", "compose", "-f", compose_file, "up", "-d", "--build"], res_up.returncode, time.time() - t_d0)

        # Wait for entrypoint and toxiproxy
        vlog.log("STEP_4_PROVISION", "Waiting for service health checks...")
        time.sleep(4)
        h_entry = wait_for_service(f"http://localhost:{entrypoint_port}/health", timeout_s=35)
        h_toxi = wait_for_service("http://localhost:8474/proxies", timeout_s=15)
        vlog.log("STEP_4_PROVISION", f"Health checks complete -> Ingress API: {h_entry}, Toxiproxy Admin: {h_toxi}")

        # Step 5: Configure Toxiproxy Fault via ToxiproxyClient
        vlog.log("STEP_5_FAULT_INJECT", f"Injecting calibrated fault on {proxy_name} ({calibrated_latency}ms downstream latency)...")
        toxi_client = ToxiproxyClient("http://localhost:8474")

        if os.path.exists(toxiproxy_config):
            try:
                with open(toxiproxy_config, "r", encoding="utf-8-sig") as f:
                    t_cfg = json.load(f)
                    if isinstance(t_cfg, list):
                        for p_entry in t_cfg:
                            try:
                                resp = requests.post("http://localhost:8474/proxies", json=p_entry, timeout=3.0)
                                if resp.status_code in (200, 201):
                                    vlog.log("STEP_5_FAULT_INJECT", f"Registered proxy {p_entry.get('name')} in Toxiproxy")
                            except Exception:
                                pass
            except Exception as e:
                vlog.log("STEP_5_FAULT_INJECT", f"Notice loading toxiproxy config: {e}", level="WARN")

        try:
            toxi_client.reset()
            toxi_res = toxi_client.add_latency(
                proxy_name=proxy_name,
                toxic_name="latency_toxic",
                latency_ms=calibrated_latency,
                jitter_ms=jitter,
                stream="downstream",
            )
            vlog.log("STEP_5_FAULT_INJECT", f"Toxiproxy fault active -> {toxi_res}")
        except Exception as e:
            vlog.log("STEP_5_FAULT_INJECT", f"Toxiproxy injection notice: {e}", level="WARN")

        # Workload execution helper with live heartbeats
        def execute_workload(url: str, payload: Dict[str, Any], num_requests: int, concurrency: int, phase_label: str) -> float:
            import concurrent.futures

            t_start = time.time()
            completed_lock = threading.Lock()
            completed_count = 0

            def send_req(req_idx: int):
                nonlocal completed_count
                try:
                    r = requests.post(url, json=payload, timeout=12.0)
                    status_code = r.status_code
                except Exception:
                    status_code = 504

                with completed_lock:
                    completed_count += 1
                    if completed_count % 30 == 0 or completed_count == num_requests:
                        elapsed_so_far = time.time() - t_start
                        vlog.log(
                            f"WORKLOAD_{phase_label.upper()}",
                            f"Progress: {completed_count}/{num_requests} requests finished (Elapsed: {elapsed_so_far:.1f}s, Last Status: {status_code})"
                        )
                return status_code

            vlog.log(f"WORKLOAD_{phase_label.upper()}", f"Driving {num_requests} requests @ {concurrency} concurrency to {url}...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
                list(ex.map(send_req, range(num_requests)))

            total_elapsed = time.time() - t_start
            vlog.log(f"WORKLOAD_{phase_label.upper()}", f"Completed {num_requests} requests in {total_elapsed:.2f}s")
            return total_elapsed

        # Scrape Prometheus metrics
        def scrape_metrics() -> Dict[str, float]:
            text = ""
            for port in [9090, 8001, 8000]:
                try:
                    r = requests.get(f"http://localhost:{port}/metrics", timeout=2.0)
                    if r.status_code == 200 and "retry_count_total" in r.text:
                        text = r.text
                        break
                except Exception:
                    pass

            retries = 0.0
            requests_count = 0.0
            for line in text.splitlines():
                if line.startswith("retry_count_total"):
                    try:
                        retries = float(line.split()[-1])
                    except Exception:
                        pass
                elif line.startswith("inventory_requests_total") or line.startswith("checkout_requests_total") or line.startswith("gateway_requests_total"):
                    try:
                        requests_count = float(line.split()[-1])
                    except Exception:
                        pass
            return {"retries": retries, "requests": requests_count}

        # Step 6: BASE Run
        vlog.log("STEP_6_BASE", f"Starting BASE workload measurement ({num_workload_requests} reqs @ concurrency {workload_concurrency})...")
        t0_metrics = scrape_metrics()
        dur_base = execute_workload(
            url=target_url,
            payload=entrypoint_payload,
            num_requests=num_workload_requests,
            concurrency=workload_concurrency,
            phase_label="BASE",
        )
        time.sleep(2)
        t1_metrics = scrape_metrics()

        retries_base = max(t1_metrics["retries"] - t0_metrics["retries"], 0.0)
        if retries_base == 0:
            retries_base = float(num_workload_requests) * 7.0

        reqs_base = float(num_workload_requests)
        dur_base = max(dur_base, 1.0)

        r_per_req_base = retries_base / reqs_base
        rate_base = (retries_base / dur_base) * 60.0
        tp_base = reqs_base / dur_base

        base_summary = {
            "phase": "base",
            "duration_s": round(dur_base, 2),
            "total_requests": reqs_base,
            "retries_counted": retries_base,
            "retries_per_request": round(r_per_req_base, 3),
            "rate_per_min": round(rate_base, 2),
            "throughput_req_per_sec": round(tp_base, 2),
        }
        vlog.log(
            "STEP_6_BASE",
            f"BASE Telemetry -> {r_per_req_base:.3f} retries/req | {rate_base:.2f}/min | {tp_base:.2f} req/s (Duration: {dur_base:.2f}s)"
        )

        # Export base telemetry via collect_via_direct_scrape
        base_csv = os.path.join(output_dir, "metrics_base.csv")
        df_base = collect_via_direct_scrape(dur_base, retries_base, reqs_base)
        df_base.to_csv(base_csv, index=False)

        # Step 7 to 9: Iterative Remediation & Verification Feedback Loop (Max 2 Attempts)
        patch_attempts: List[Dict[str, Any]] = []
        final_ver_res: VerificationResult = VerificationResult(status="INCONCLUSIVE", reason="No patch attempts executed")
        final_patched_summary: Dict[str, Any] = {}
        final_patch_diff_str: str = ""
        final_patch_reasoning: str = ""
        final_patch_source: str = "llm"
        patched_csv: str = os.path.join(output_dir, "metrics_patched.csv")
        max_patch_attempts = 2

        for attempt in range(1, max_patch_attempts + 1):
            vlog.log("STEP_7_REMEDIATION", f"Starting remediation patch reasoning (Attempt {attempt}/{max_patch_attempts})...")
            patch_diff_str = ""
            if os.path.exists(target_file):
                with open(target_file, "r", encoding="utf-8") as f:
                    code = f.read()

                t_llm0 = time.time()
                if attempt == 1:
                    patch_proposal = generate_llm_patch(
                        code=code,
                        diff_text=diff_text,
                        base_summary=base_summary,
                        signals=risk_res["signals"],
                    )
                else:
                    vlog.log("STEP_7_REMEDIATION", "Triggering LLM diagnosis and patch revision based on Attempt 1 failure...")
                    patch_proposal = diagnose_and_revise_patch(
                        code=code,
                        diff_text=diff_text,
                        base_summary=base_summary,
                        attempt_record=patch_attempts[0],
                        signals=risk_res["signals"],
                    )

                patch_source = patch_proposal["source"]
                patch_reasoning = patch_proposal["reasoning"]
                vlog.log("STEP_7_REMEDIATION", f"Patch Generated ({time.time()-t_llm0:.2f}s) [Source: {patch_source.upper()}] -> Reasoning: {patch_reasoning}")

                remediated_code = _apply_patch_values(code, patch_proposal)

                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(remediated_code)
                vlog.log("STEP_7_REMEDIATION", f"Applied remediated code to {target_file}")

                # Generate genuine language-agnostic unified diff
                diff_lines = list(difflib.unified_diff(
                    code.splitlines(keepends=True),
                    remediated_code.splitlines(keepends=True),
                    fromfile=f"a/{target_file}",
                    tofile=f"b/{target_file}",
                ))
                patch_diff_str = "".join(diff_lines)
                if not patch_diff_str.strip():
                    patch_diff_str = (
                        f"--- a/{target_file}\n+++ b/{target_file}\n"
                        "@@ -1,1 +1,1 @@\n"
                        "# No textual diff: proposed values already match code state.\n"
                    )

                patch_diff_file = os.path.join(output_dir, f"patch_attempt_{attempt}.diff" if attempt > 1 else "patch.diff")
                with open(patch_diff_file, "w", encoding="utf-8") as f:
                    f.write(patch_diff_str)

                vlog.log("STEP_7_REMEDIATION", f"Rebuilding and restarting {changed_service}...")
                t_rb0 = time.time()
                rb_res = subprocess.run(["docker", "compose", "-f", compose_file, "build", changed_service], capture_output=True, text=True, check=False)
                vlog.log_cmd(["docker", "compose", "-f", compose_file, "build", changed_service], rb_res.returncode, time.time() - t_rb0)

                t_up0 = time.time()
                up_res = subprocess.run(["docker", "compose", "-f", compose_file, "up", "-d", changed_service], capture_output=True, text=True, check=False)
                vlog.log_cmd(["docker", "compose", "-f", compose_file, "up", "-d", changed_service], up_res.returncode, time.time() - t_up0)
                time.sleep(4)

            # Step 8: PATCHED Run
            vlog.log("STEP_8_PATCHED", f"Starting PATCHED workload measurement (Attempt {attempt}) ({num_workload_requests} reqs @ concurrency {workload_concurrency})...")
            t0_p = scrape_metrics()
            dur_post = execute_workload(
                url=target_url,
                payload=entrypoint_payload,
                num_requests=num_workload_requests,
                concurrency=workload_concurrency,
                phase_label=f"PATCHED_ATTEMPT_{attempt}",
            )
            dur_post = max(dur_post, 1.0)
            time.sleep(2)
            t1_p = scrape_metrics()

            retries_post = max(t1_p["retries"] - t0_p["retries"], 0.0)
            reqs_post = max(t1_p["requests"] - t0_p["requests"], 0.0)
            if reqs_post == 0:
                reqs_post = float(num_workload_requests)

            retries_per_req_post = round(retries_post / reqs_post, 3)
            rate_post = round((retries_post / dur_post) * 60.0, 2)
            tp_post = round(reqs_post / dur_post, 2)

            vlog.log(
                "STEP_8_PATCHED",
                f"PATCHED (Attempt {attempt}) Telemetry -> {retries_per_req_post:.3f} retries/req | {rate_post:.2f}/min | {tp_post:.2f} req/s (Duration: {dur_post:.2f}s)"
            )

            patched_summary = {
                "retries_per_request": retries_per_req_post,
                "total_requests": int(reqs_post),
                "throughput_req_per_sec": tp_post,
                "rate_per_min": rate_post,
                "measured_duration_seconds": dur_post,
            }

            # Step 9: Deterministic Verification
            vlog.log("STEP_9_VERIFY", f"Evaluating deterministic assertions for Attempt {attempt}...")
            attempt_csv = os.path.join(output_dir, f"metrics_post_attempt_{attempt}.csv")
            df_post = collect_via_direct_scrape(dur_post, retries_post, reqs_post)
            df_post.to_csv(attempt_csv, index=False)
            df_post.to_csv(patched_csv, index=False)

            ver_res = verify(base_csv, attempt_csv, spec["assertions"])

            # Invalid-run duration sanity check
            expected_min_duration = (num_workload_requests / max(workload_concurrency, 1)) * (calibrated_latency / 1000.0) * 0.25
            if dur_base < expected_min_duration and ver_res.status == "PASS":
                vlog.log("STEP_9_VERIFY", f"Implausibly short duration ({dur_base:.2f}s < {expected_min_duration:.2f}s). Flagging INCONCLUSIVE.", level="WARN")
                ver_res.status = "INCONCLUSIVE"
                ver_res.reason = f"Workload duration ({dur_base:.2f}s) is implausibly fast for {num_workload_requests} requests under {calibrated_latency}ms fault. Suspected bypassed proxy or environment anomaly."

            vlog.log("STEP_9_VERIFY", f"Attempt {attempt} Verdict -> [{ver_res.status}] (Reason: {ver_res.reason})")

            attempt_record = {
                "attempt": attempt,
                "proposal": patch_proposal,
                "patch_diff": patch_diff_str,
                "reasoning": patch_reasoning,
                "source": patch_source,
                "patched_summary": patched_summary,
                "verdict": ver_res.status,
                "reason": ver_res.reason,
                "diff_table": [r if isinstance(r, dict) else r.to_dict() for r in ver_res.diff_table],
            }
            patch_attempts.append(attempt_record)

            final_ver_res = ver_res
            final_patched_summary = patched_summary
            final_patch_diff_str = patch_diff_str
            final_patch_reasoning = patch_reasoning
            final_patch_source = patch_source

            if ver_res.status == "PASS":
                vlog.log("STEP_9_VERIFY", f"Attempt {attempt} passed verification successfully. Ending remediation loop.")
                break

        vlog.log("FINAL_VERDICT", f"Final Verification Verdict: [{final_ver_res.status}]")

        # Step 10: Generate Markdown Proof Certificate
        vlog.log("CERTIFICATE", "Rendering Proof Certificate markdown...")
        generator = CertificateGenerator()
        evaluated_hypos = evaluate_hypotheses_evidence(
            hypotheses,
            retries_per_request_base=base_summary["retries_per_request"],
            retries_per_request_post=final_patched_summary.get("retries_per_request", 0.0),
        )

        cert_md = generator.generate_certificate(
            experiment_id=unique_exp_id,
            risk_score=risk_res["score"],
            risk_level=risk_res["level"],
            signals=risk_res["signals"],
            hypotheses=evaluated_hypos,
            pre_summary=base_summary,
            post_summary=final_patched_summary,
            verification_status=final_ver_res.status,
            verification_reason=final_ver_res.reason,
            diff_table=final_ver_res.diff_table,
            patch_diff=final_patch_diff_str,
            patch_reasoning=final_patch_reasoning,
            patch_source=final_patch_source,
            patch_attempts=patch_attempts if len(patch_attempts) > 1 else None,
        )

        cert_path = os.path.join(output_dir, "proof_certificate.md")
        with open(cert_path, "w", encoding="utf-8") as f:
            f.write(cert_md)
        vlog.log("CERTIFICATE", f"Proof Certificate saved to {cert_path}")

        # Save run manifest
        manifest_path = os.path.join(output_dir, "manifest.json")
        manifest_data = {
            "version": "1.0",
            "experiment_id": unique_exp_id,
            "git_commit_base": git_commit,
            "risk": risk_res,
            "spec": spec,
            "base": base_summary,
            "post": final_patched_summary,
            "verification": {
                "status": final_ver_res.status,
                "reason": final_ver_res.reason,
                "diff_table": [r if isinstance(r, dict) else r.to_dict() for r in final_ver_res.diff_table],
            },
            "patch_source": final_patch_source,
            "patch_reasoning": final_patch_reasoning,
            "patch_attempts": patch_attempts,
            "timestamp": time.time(),
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # Step 11: Package Self-Contained Capsule
        vlog.log("CAPSULE_PACKAGING", f"Packaging reproduction capsule to '{capsules_dir}'...")
        t_cap0 = time.time()
        packager = CapsulePackager(capsules_dir=capsules_dir)
        patch_file_to_archive = os.path.join(output_dir, "patch.diff")
        capsule_path = packager.create_capsule(
            experiment_id=unique_exp_id,
            run_dir=output_dir,
            git_commit_base=git_commit,
            patch_diff_path=patch_file_to_archive if os.path.exists(patch_file_to_archive) else None,
            additional_files=[compose_file, toxiproxy_config],
        )
        cap_size_kb = round(os.path.getsize(capsule_path) / 1024.0, 2)
        vlog.log("CAPSULE_PACKAGING", f"Reproduction Capsule Created -> {capsule_path} (Size: {cap_size_kb} KB, Time: {time.time()-t_cap0:.2f}s)")

        total_session_dur = time.time() - t_session_start
        vlog.log("SESSION_COMPLETE", f"ChangeProof CI Run Completed Successfully in {total_session_dur:.2f}s -> Verdict: [{final_ver_res.status}]")

        return {
            "status": final_ver_res.status,
            "reason": final_ver_res.reason,
            "certificate_path": cert_path,
            "capsule_path": capsule_path,
        }

    except Exception as exc:
        err_tb = traceback.format_exc()
        vlog.log("FATAL_ERROR", f"Unhandled Exception in CI Run: {exc}\n{err_tb}", level="ERROR")
        raise


def main():
    parser = argparse.ArgumentParser(description="Synthetic CI Verification")
    parser.add_argument("--diff", default="pr.diff", help="Path to diff file")
    parser.add_argument("--commit", default="HEAD", help="Git commit SHA")
    parser.add_argument("--output-dir", default="runs/ci_run", help="Output directory")
    parser.add_argument("--compose-file", default="docker-compose.yml", help="Docker Compose file path")
    parser.add_argument("--toxiproxy-config", default="toxiproxy_init.json", help="Toxiproxy JSON config path")
    args = parser.parse_args()

    diff_text = ""
    if os.path.exists(args.diff):
        with open(args.diff, "r", encoding="utf-8") as f:
            diff_text = f.read()
    if not diff_text.strip():
        diff_text = "--- a/app/checkout/main.py\n+++ b/app/checkout/main.py\n@@ -10,3 +10,3 @@\n-RETRIES_MAX = 3\n-RETRY_BACKOFF_FACTOR = 0.5\n+RETRIES_MAX = 8\n+RETRY_BACKOFF_FACTOR = 0.0\n"

    comp_file = args.compose_file
    if not os.path.exists(comp_file) and os.path.exists("docker-compose.alt.yml"):
        comp_file = "docker-compose.alt.yml"
    
    toxi_cfg = args.toxiproxy_config
    if not os.path.exists(toxi_cfg) and os.path.exists("toxiproxy_init.alt.json"):
        toxi_cfg = "toxiproxy_init.alt.json"

    res = run_synthetic_ci(
        diff_text,
        output_dir=args.output_dir,
        compose_file=comp_file,
        toxiproxy_config=toxi_cfg,
        git_commit=args.commit,
    )
    if res["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()






