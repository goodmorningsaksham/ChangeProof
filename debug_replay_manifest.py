import tempfile
import zipfile
import json
import os
from changeproof.verifier import _load_run_context, build_phase_summary

with zipfile.ZipFile("capsules/case-alt-01.zip", "r") as z:
    with tempfile.TemporaryDirectory() as tmp_dir:
        z.extractall(tmp_dir)
        print("Files in tmp_dir:", os.listdir(tmp_dir))
        
        pre_csv = os.path.join(tmp_dir, "metrics_base.csv")
        df, manifest = _load_run_context(pre_csv)
        print("Loaded manifest for pre_csv:")
        print(manifest)
        summary = build_phase_summary(df, manifest)
        print("Built summary:")
        print(summary)
