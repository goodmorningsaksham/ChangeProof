"""Unit tests for ChangeProof iterative patch self-correction and feedback loop."""
import unittest
from unittest.mock import patch

from changeproof.cli_synth_verify import (
    _build_diagnostic_prompt,
    diagnose_and_revise_patch,
)
from changeproof.certificate import CertificateGenerator


class TestSelfCorrection(unittest.TestCase):
    def setUp(self):
        self.sample_code = (
            'RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))\n'
            'RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))\n'
            'RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))\n'
        )
        self.diff_text = "+RETRIES_MAX = 8\n+RETRY_TIMEOUT_SECONDS = 0.5\n+RETRY_BACKOFF_FACTOR = 0.0"
        self.base_summary = {
            "retries_per_request": 7.0,
            "rate_per_min": 1050.0,
            "total_requests": 150,
        }
        self.attempt_1_record = {
            "attempt": 1,
            "proposal": {
                "retries_max": 3,
                "timeout_s": 0.5,
                "backoff_factor": 0.0,
                "reasoning": "Lowered retries to 3",
            },
            "patched_summary": {
                "retries_per_request": 2.0,
                "rate_per_min": 500.0,
                "throughput_req_per_sec": 3.0,
                "total_requests": 150,
            },
            "reason": "Assertion retries_per_request <= 1.1 failed (observed: 2.0)",
            "verdict": "FAIL",
            "patch_diff": "--- a/app/checkout/main.py\n+++ b/app/checkout/main.py\n@@ -1,1 +1,1 @@\n-RETRIES_MAX = 8\n+RETRIES_MAX = 3",
            "source": "llm",
            "reasoning": "Lowered retries to 3",
        }
        self.signals = ["Aggressive retry count increase", "Removal of backoff"]

    def test_build_diagnostic_prompt_includes_failure_telemetry(self):
        prompt = _build_diagnostic_prompt(
            self.diff_text,
            self.sample_code,
            self.base_summary,
            self.attempt_1_record,
            self.signals,
        )
        self.assertIn("EMPIRICAL VERIFICATION RESULT (Attempt 1 FAILED)", prompt)
        self.assertIn("retries_per_request: 2.000", prompt)
        self.assertIn("retries_max: 3", prompt)
        self.assertIn("Assertion retries_per_request <= 1.1 failed", prompt)

    @patch("changeproof.cli_synth_verify.call_llm")
    def test_diagnose_and_revise_patch_success(self, mock_llm):
        mock_llm.return_value = (
            '{\n'
            '  "diagnosis": "Attempt 1 kept RETRIES_MAX at 3 without backoff, leading to 2.0 retries/req.",\n'
            '  "reasoning": "Reduce RETRIES_MAX to 2 and add exponential backoff factor 0.5.",\n'
            '  "retries_max": 2,\n'
            '  "timeout_s": 1.0,\n'
            '  "backoff_factor": 0.5,\n'
            '  "timeout_ms": null,\n'
            '  "backoff_ms": null\n'
            '}'
        )
        result = diagnose_and_revise_patch(
            self.sample_code,
            self.diff_text,
            self.base_summary,
            self.attempt_1_record,
            self.signals,
        )
        self.assertEqual(result["source"], "llm")
        self.assertEqual(result["retries_max"], 2)
        self.assertEqual(result["timeout_s"], 1.0)
        self.assertEqual(result["backoff_factor"], 0.5)
        self.assertIn("Attempt 1 kept RETRIES_MAX at 3", result["reasoning"])

    @patch("changeproof.cli_synth_verify.call_llm")
    def test_diagnose_and_revise_patch_clamps_unsafe_values(self, mock_llm):
        mock_llm.return_value = (
            '{\n'
            '  "diagnosis": "Attempt 1 failed.",\n'
            '  "reasoning": "Setting retries to 10 and timeout to 0.1",\n'
            '  "retries_max": 10,\n'
            '  "timeout_s": 0.1,\n'
            '  "backoff_factor": 5.0\n'
            '}'
        )
        result = diagnose_and_revise_patch(
            self.sample_code,
            self.diff_text,
            self.base_summary,
            self.attempt_1_record,
            self.signals,
        )
        self.assertEqual(result["retries_max"], 5)  # clamped from 10 to 5
        self.assertEqual(result["timeout_s"], 0.3)  # clamped from 0.1 to 0.3
        self.assertEqual(result["backoff_factor"], 2.0)  # clamped from 5.0 to 2.0

    @patch("changeproof.cli_synth_verify.call_llm")
    def test_diagnose_and_revise_patch_fallback_on_error(self, mock_llm):
        mock_llm.return_value = None
        result = diagnose_and_revise_patch(
            self.sample_code,
            self.diff_text,
            self.base_summary,
            self.attempt_1_record,
            self.signals,
        )
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["retries_max"], 1)

    def test_certificate_renders_multi_attempt_trajectory(self):
        attempt_2_record = {
            "attempt": 2,
            "proposal": {"retries_max": 2, "timeout_s": 1.0, "backoff_factor": 0.5},
            "patched_summary": {
                "retries_per_request": 1.0,
                "rate_per_min": 230.0,
                "throughput_req_per_sec": 3.9,
                "total_requests": 150,
            },
            "reason": "Fix verified successfully",
            "verdict": "PASS",
            "patch_diff": "--- a/app/checkout/main.py\n+++ b/app/checkout/main.py\n@@ -1,1 +1,1 @@\n-RETRIES_MAX = 8\n+RETRIES_MAX = 2",
            "source": "llm",
            "reasoning": "Diagnosed residual storm and added backoff.",
        }

        ctx = {
            "timestamp": "2026-08-31T00:00:00Z",
            "experiment_id": "case-self-correction-01",
            "git_commit": "abcdef12",
            "verification_status": "PASS",
            "risk_level": "HIGH",
            "risk_score": 70,
            "hypothesis_title": "Retry ceiling causes storm under latency",
            "hypothesis_confidence": "HIGH",
            "pre_summary": self.base_summary,
            "post_summary": attempt_2_record["patched_summary"],
            "patch_diff": attempt_2_record["patch_diff"],
            "patch_attempts": [self.attempt_1_record, attempt_2_record],
            "diff_table": [
                {"metric": "retries_per_request", "phase": "pre_patch", "observed_value": 7.0, "condition": "> 2.0", "condition_met": True},
                {"metric": "retries_per_request", "phase": "post_patch", "observed_value": 1.0, "condition": "<= 1.1", "condition_met": True},
            ],
            "capsule_path": "capsules/case-self-correction-01.zip",
        }

        cert_gen = CertificateGenerator()
        rendered = cert_gen.render(ctx)

        self.assertIn("## Remediation Patch Trajectory (Agentic Feedback Loop)", rendered)
        self.assertIn("### Patch Attempt 1 — Verdict: `[FAIL]`", rendered)
        self.assertIn("### Patch Attempt 2 — Verdict: `[PASS]`", rendered)
        self.assertIn("2.0 retries/req", rendered)


if __name__ == "__main__":
    unittest.main()
