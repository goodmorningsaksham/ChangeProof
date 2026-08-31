"""Reproduction capsule packager and unarchiver."""
import os
import json
import zipfile
import hashlib
from typing import List, Optional, Dict

class CapsulePackager:
    def __init__(self, capsules_dir: str = "capsules"):
        self.capsules_dir = capsules_dir
        os.makedirs(self.capsules_dir, exist_ok=True)

    @staticmethod
    def sha256_file(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def create_capsule(
        self,
        experiment_id: str,
        run_dir: str,
        git_commit_base: str,
        patch_diff_path: Optional[str] = None,
        additional_files: Optional[List[str]] = None,
    ) -> str:
        """Packages run artifacts and metadata into a self-contained reproduction capsule zip."""
        capsule_filename = f"{experiment_id}.zip"
        capsule_path = os.path.join(self.capsules_dir, capsule_filename)

        abs_capsule_path = os.path.abspath(capsule_path)
        abs_capsules_dir = os.path.abspath(self.capsules_dir)
        abs_run_dir = os.path.abspath(run_dir)

        spec_file = os.path.join(run_dir, "experiment.yaml")
        spec_sha256 = self.sha256_file(spec_file) if os.path.exists(spec_file) else "none"
        patch_sha256 = self.sha256_file(patch_diff_path) if patch_diff_path and os.path.exists(patch_diff_path) else "none"

        run_manifest = {}
        run_manifest_path = os.path.join(run_dir, "manifest.json")
        if os.path.exists(run_manifest_path):
            try:
                with open(run_manifest_path, "r", encoding="utf-8") as f:
                    run_manifest = json.load(f)
            except Exception:
                pass

        # Compute evidence hashes for all valid metrics and data files in run_dir (skipping zip files/capsules dirs)
        evidence_hashes: Dict[str, str] = {}
        if os.path.exists(run_dir):
            for fname in os.listdir(run_dir):
                if fname.endswith((".csv", ".json", ".diff", ".yaml", ".yml", ".jsonl", ".log")):
                    if fname != "manifest.json":
                        fpath = os.path.join(run_dir, fname)
                        if os.path.isfile(fpath):
                            evidence_hashes[fname] = self.sha256_file(fpath)

        manifest = {
            "version": "1.0",
            "experiment_id": experiment_id,
            "git_commit_base": git_commit_base,
            "spec_sha256": spec_sha256,
            "patch_sha256": patch_sha256,
            "evidence_hashes": evidence_hashes,
            "packaged_at": os.path.getmtime(run_dir) if os.path.exists(run_dir) else 0,
        }
        # Preserve run metrics, ratios, durations, and rates in capsule manifest
        manifest.update(run_manifest)
        manifest["spec_sha256"] = spec_sha256
        manifest["patch_sha256"] = patch_sha256
        manifest["evidence_hashes"] = evidence_hashes

        with zipfile.ZipFile(capsule_path, "w", zipfile.ZIP_DEFLATED) as z:
            # Write capsule manifest
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            
            # Archive run directory contents (spec, metrics, trajectory)
            # CRITICAL: strictly exclude capsules directory, .zip files, .git, .venv to prevent recursive zip inflation
            if os.path.exists(run_dir):
                for root, dirs, files in os.walk(run_dir):
                    # Prune excluded directories
                    dirs[:] = [
                        d for d in dirs
                        if d not in ("capsules", ".git", ".venv", "node_modules", "__pycache__", "scratch")
                        and os.path.abspath(os.path.join(root, d)) != abs_capsules_dir
                    ]
                    
                    for file in files:
                        if file in ("manifest.json", "patch.diff"):
                            continue
                        if file.endswith((".zip", ".tar", ".gz", ".pyc", ".vhdx")):
                            continue
                        full_path = os.path.join(root, file)
                        if os.path.abspath(full_path) == abs_capsule_path:
                            continue
                        rel_path = os.path.relpath(full_path, run_dir)
                        z.write(full_path, arcname=rel_path)

            # Archive patch if provided
            if patch_diff_path and os.path.exists(patch_diff_path):
                z.write(patch_diff_path, arcname="patch.diff")

            # Archive additional files (e.g., compose, workload)
            if additional_files:
                for af in additional_files:
                    if os.path.exists(af) and not af.endswith((".zip", ".tar", ".gz")):
                        z.write(af, arcname=os.path.basename(af))

            # Include README with clean replay commands
            readme_text = (
                f"# ChangeProof Reproduction Capsule — {experiment_id}\n\n"
                f"Base Commit: `{git_commit_base}`\n"
                f"Spec SHA256: `{spec_sha256}`\n\n"
                f"## Clean Replay Instructions\n"
                f"```bash\n"
                f"python changeproof/replay.py capsules/{capsule_filename}\n"
                f"```\n"
            )
            z.writestr("README.md", readme_text)

        return capsule_path
