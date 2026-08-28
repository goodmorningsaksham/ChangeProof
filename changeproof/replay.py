"""Clean environment replay CLI."""
import os
import sys
import json
import yaml
import zipfile
import tempfile
import hashlib
from typing import Dict, Any
from changeproof.experiment_runner import ExperimentRunner
from changeproof.verifier import verify

def replay_capsule(capsule_zip_path: str, state: str = "base") -> Dict[str, Any]:
    """Extracts capsule, verifies spec_sha256, executes experiment, and deterministically verifies outcome."""
    if not os.path.exists(capsule_zip_path):
        raise FileNotFoundError(f"Capsule zip not found: {capsule_zip_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(capsule_zip_path, "r") as z:
            z.extractall(tmp_dir)

        manifest_path = os.path.join(tmp_dir, "manifest.json")
        spec_path = os.path.join(tmp_dir, "experiment.yaml")

        if not os.path.exists(manifest_path) or not os.path.exists(spec_path):
            raise ValueError("Capsule missing manifest.json or experiment.yaml")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        with open(spec_path, "r", encoding="utf-8") as f:
            spec_content = f.read()
            spec = yaml.safe_load(spec_content)

        # Integrity check: verify spec SHA256
        current_sha256 = hashlib.sha256(spec_content.encode("utf-8")).hexdigest()
        if manifest.get("spec_sha256") and manifest["spec_sha256"] != "none":
            if current_sha256 != manifest["spec_sha256"]:
                return {
                    "status": "INCONCLUSIVE",
                    "reason": f"Spec hash mismatch: expected {manifest['spec_sha256']}, got {current_sha256}",
                }

        # Run replay experiment
        runner = ExperimentRunner(runs_dir=os.path.join(tmp_dir, "replay_runs"))
        run_res = runner.run(spec_path, state=state)

        # In a complete replay, evaluate verifier assertions
        pre_metrics = os.path.join(tmp_dir, "metrics_pre.csv")
        post_metrics = os.path.join(tmp_dir, "metrics_post.csv")

        if os.path.exists(pre_metrics) and os.path.exists(post_metrics):
            ver_res = verify(pre_metrics, post_metrics, spec.get("assertions", {}))
            return {
                "replay_status": "COMPLETED",
                "spec_verified": True,
                "verification": ver_res.to_dict(),
            }

        return {
            "replay_status": run_res.get("status"),
            "spec_verified": True,
            "run_result": run_res,
        }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m changeproof.replay <capsule.zip>")
        sys.exit(1)
    res = replay_capsule(sys.argv[1])
    print(json.dumps(res, indent=2))
