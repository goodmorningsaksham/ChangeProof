"""Clean environment replay CLI with cryptographic evidence integrity & tamper detection."""
import os
import sys
import json
import yaml
import zipfile
import tempfile
import hashlib
import pandas as pd
from typing import Dict, Any, Optional
from changeproof.experiment_runner import ExperimentRunner
from changeproof.verifier import verify


def _sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def _compute_csv_ratio(csv_path: str) -> Optional[float]:
    """Calculates retries_per_request directly from raw metric CSV without reading manifest."""
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return None
        if "metric_name" in df.columns and "value" in df.columns:
            r_df = df[df["metric_name"] == "retry_count_total"]
            q_df = df[df["metric_name"] == "checkout_requests_total"]
            if not r_df.empty and not q_df.empty:
                r_delta = max(float(r_df["value"].max() - r_df["value"].min()), 0.0)
                q_delta = max(float(q_df["value"].max() - q_df["value"].min()), 0.0)
                if q_delta > 0:
                    return round(float(r_delta / q_delta), 3)
    except Exception:
        pass
    return None


def replay_capsule(capsule_zip_path: str, mode: str = "evidence") -> Dict[str, Any]:
    """Replays a reproduction capsule.
    
    Modes:
    - 'evidence': Deterministic verification of archived runtime metrics against immutable spec.
    - 'live': Genuine clean-environment execution: runs live BASE experiment, applies patch,
              runs live PATCHED experiment, captures fresh metrics, and evaluates verifier.
    """
    if not os.path.exists(capsule_zip_path):
        raise FileNotFoundError(f"Capsule zip not found: {capsule_zip_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(capsule_zip_path, "r") as z:
            z.extractall(tmp_dir)

        manifest_path = os.path.join(tmp_dir, "manifest.json")
        spec_path = os.path.join(tmp_dir, "experiment.yaml")

        if not os.path.exists(manifest_path) or not os.path.exists(spec_path):
            raise ValueError("Capsule missing manifest.json or experiment.yaml")

        with open(manifest_path, "r", encoding="utf-8-sig") as f:
            manifest = json.load(f)

        with open(spec_path, "rb") as f:
            spec_bytes = f.read()
        spec_content = spec_bytes.decode("utf-8")
        spec = yaml.safe_load(spec_content)

        # 1. Cryptographic Spec Hash Verification
        current_sha256 = hashlib.sha256(spec_bytes).hexdigest()
        normalized_sha256 = hashlib.sha256(spec_content.replace("\r\n", "\n").encode("utf-8")).hexdigest()
        if manifest.get("spec_sha256") and manifest["spec_sha256"] != "none":
            expected_sha = manifest["spec_sha256"]
            if current_sha256 != expected_sha and normalized_sha256 != expected_sha:
                err_msg = f"EVIDENCE TAMPERED: hash mismatch on experiment.yaml (expected {expected_sha}, got {current_sha256})"
                sys.stderr.write(f"\n[ERROR] {err_msg}\n")
                return {
                    "replay_mode": "evidence_verification",
                    "replay_status": "TAMPER_DETECTED",
                    "spec_verified": False,
                    "error": err_msg,
                }

        # 2. Evidence Files Cryptographic Integrity (if stored)
        evidence_hashes = manifest.get("evidence_hashes", {})
        for fname, exp_hash in evidence_hashes.items():
            fpath = os.path.join(tmp_dir, fname)
            if os.path.exists(fpath):
                act_hash = _sha256_file(fpath)
                if act_hash != exp_hash:
                    err_msg = f"EVIDENCE TAMPERED: hash mismatch on {fname} (expected {exp_hash}, got {act_hash})"
                    sys.stderr.write(f"\n[ERROR] {err_msg}\n")
                    return {
                        "replay_mode": "evidence_verification",
                        "replay_status": "TAMPER_DETECTED",
                        "spec_verified": False,
                        "error": err_msg,
                    }

        # 3. Telemetry Cross-Validation (Manifest Claim vs Raw Evidence CSV)
        pre_metrics = os.path.join(tmp_dir, "metrics_pre.csv")
        if not os.path.exists(pre_metrics):
            pre_metrics = os.path.join(tmp_dir, "metrics_base.csv")

        post_metrics = os.path.join(tmp_dir, "metrics_post.csv")
        if not os.path.exists(post_metrics):
            post_metrics = os.path.join(tmp_dir, "metrics_patched.csv")

        if os.path.exists(pre_metrics):
            raw_pre_ratio = _compute_csv_ratio(pre_metrics)
            manifest_pre_ratio = None
            if "base" in manifest and isinstance(manifest["base"], dict):
                manifest_pre_ratio = manifest["base"].get("retries_per_request")
            elif "pre" in manifest and isinstance(manifest["pre"], dict):
                manifest_pre_ratio = manifest["pre"].get("retries_per_request")

            if raw_pre_ratio is not None and manifest_pre_ratio is not None:
                if abs(float(manifest_pre_ratio) - float(raw_pre_ratio)) > 0.05:
                    err_msg = (
                        f"EVIDENCE TAMPERED: manifest summary for base.retries_per_request ({manifest_pre_ratio}) "
                        f"contradicts raw telemetry in {os.path.basename(pre_metrics)} (computed: {raw_pre_ratio})"
                    )
                    sys.stderr.write(f"\n[ERROR] {err_msg}\n")
                    return {
                        "replay_mode": "evidence_verification",
                        "replay_status": "TAMPER_DETECTED",
                        "spec_verified": False,
                        "error": err_msg,
                    }

        # 4. Replay Execution
        if mode == "live":
            runner = ExperimentRunner(runs_dir=os.path.join(tmp_dir, "replay_runs"))
            
            base_run = runner.run(spec_path, state="base")
            if base_run.get("status") != "COMPLETED":
                return {"replay_status": "FAILED", "stage": "base_run", "error": base_run.get("error")}
            
            patched_run = runner.run(spec_path, state="patched")
            if patched_run.get("status") != "COMPLETED":
                return {"replay_status": "FAILED", "stage": "patched_run", "error": patched_run.get("error")}

            ver_res = verify(base_run["metrics_csv_path"], patched_run["metrics_csv_path"], spec.get("assertions", {}))
            return {
                "replay_mode": "live_reproduction",
                "replay_status": "COMPLETED",
                "spec_verified": True,
                "verification": ver_res.to_dict(),
            }
        else:
            if os.path.exists(pre_metrics) and os.path.exists(post_metrics):
                ver_res = verify(pre_metrics, post_metrics, spec.get("assertions", {}))
                return {
                    "replay_mode": "evidence_verification",
                    "replay_status": "COMPLETED",
                    "spec_verified": True,
                    "verification": ver_res.to_dict(),
                }

            return {
                "replay_mode": "evidence_verification",
                "replay_status": "INCONCLUSIVE",
                "reason": "Capsule does not contain metrics CSVs for verification",
            }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m changeproof.replay <capsule.zip> [--live]")
        sys.exit(1)
    
    live_flag = "--live" in sys.argv
    res = replay_capsule(sys.argv[1], mode="live" if live_flag else "evidence")
    print(json.dumps(res, indent=2))
    if res.get("replay_status") == "TAMPER_DETECTED":
        sys.exit(1)
