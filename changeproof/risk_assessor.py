"""Deterministic AST and regex risk assessor for PR diffs."""
import re
from typing import Dict, Any, List

class RiskAssessor:
    def assess_diff(self, diff_text: str) -> Dict[str, Any]:
        """Calculates risk score based on deterministic signals in the diff."""
        score = 0
        signals_detected: List[str] = []

        # Signal 1: Modification or increase of retry counts
        if re.search(r'[\+\s]*RETRIES_MAX\s*=\s*([4-9]|\d{2,})', diff_text) or re.search(r'[\+\s]*max_retries\s*=\s*([4-9]|\d{2,})', diff_text):
            score += 30
            signals_detected.append("Aggressive retry count increase (max_retries >= 4)")

        # Signal 2: Removal or reduction of backoff strategy
        if re.search(r'[\+\s]*RETRY_BACKOFF_FACTOR\s*=\s*0(\.0)?', diff_text) or re.search(r'[\+\s]*wait_fixed\(0\)', diff_text):
            score += 20
            signals_detected.append("Removal of backoff / immediate retry execution")

        # Signal 3: Reduced timeout duration
        if re.search(r'[\+\s]*RETRY_TIMEOUT_SECONDS\s*=\s*0\.[1-9]', diff_text) or re.search(r'[\+\s]*timeout\s*=\s*0\.[1-9]', diff_text):
            score += 20
            signals_detected.append("Aggressive timeout reduction (timeout < 1.0s)")

        # Signal 4: Touches networking/client call without circuit breaker
        if "+with httpx.Client" in diff_text or "+client.post" in diff_text:
            score += 15
            signals_detected.append("Downstream HTTP dependency modification")

        # Signal 5: Test-only discount
        if diff_text and all(line.startswith("+++ b/tests/") or line.startswith("--- a/tests/") for line in diff_text.splitlines() if line.startswith("+++ ") or line.startswith("--- ")):
            score = max(0, score - 40)
            signals_detected.append("Test-only modifications detected (discounted)")

        if score >= 50:
            level = "HIGH"
        elif score >= 20:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "score": score,
            "level": level,
            "signals": signals_detected,
            "requires_experiment": level == "HIGH",
        }
