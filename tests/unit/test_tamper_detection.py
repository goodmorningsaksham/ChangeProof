import os
import json
import zipfile
import tempfile
from changeproof.replay import replay_capsule


def test_tamper_detection_on_manifest_value_mismatch():
    capsule_path = "capsules/case-01.zip"
    assert os.path.exists(capsule_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Extract original capsule
        with zipfile.ZipFile(capsule_path, "r") as z:
            z.extractall(tmp_dir)

        # Tamper manifest.json
        manifest_path = os.path.join(tmp_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        manifest["base"]["retries_per_request"] = 3.0  # Real CSV is 7.0
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Repackage tampered capsule
        tampered_zip = os.path.join(tmp_dir, "tampered.zip")
        with zipfile.ZipFile(tampered_zip, "w") as z:
            for root, _, files in os.walk(tmp_dir):
                for file in files:
                    if file == "tampered.zip":
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, tmp_dir)
                    z.write(full_path, arcname=rel_path)

        # Replay tampered capsule
        res = replay_capsule(tampered_zip)
        assert res.get("replay_status") == "TAMPER_DETECTED"
        assert "EVIDENCE TAMPERED" in res.get("error", "")


def test_tamper_detection_on_spec_hash_mismatch():
    capsule_path = "capsules/case-01.zip"
    assert os.path.exists(capsule_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(capsule_path, "r") as z:
            z.extractall(tmp_dir)

        # Tamper experiment.yaml
        spec_path = os.path.join(tmp_dir, "experiment.yaml")
        with open(spec_path, "a", encoding="utf-8") as f:
            f.write("\n# Malicious spec change\n")

        tampered_zip = os.path.join(tmp_dir, "tampered_spec.zip")
        with zipfile.ZipFile(tampered_zip, "w") as z:
            for root, _, files in os.walk(tmp_dir):
                for file in files:
                    if file == "tampered_spec.zip":
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, tmp_dir)
                    z.write(full_path, arcname=rel_path)

        res = replay_capsule(tampered_zip)
        assert res.get("replay_status") == "TAMPER_DETECTED"
        assert "EVIDENCE TAMPERED" in res.get("error", "")
