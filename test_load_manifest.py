from changeproof.verifier import _load_run_context
import os

df, manifest = _load_run_context("runs/run_case_alt_01/metrics_base.csv")
print("runs/run_case_alt_01/metrics_base.csv manifest loaded:")
print(manifest)
