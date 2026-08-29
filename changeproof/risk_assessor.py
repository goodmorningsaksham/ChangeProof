"""Deterministic AST and regex risk assessor for PR diffs."""
import re
from typing import Dict, Any, List

class RiskAssessor:
    def assess_diff(self, diff_text: str) -> Dict[str, Any]:
        """Calculates risk score based on deterministic signals in the diff.

        All patterns are anchored to the unified-diff addition prefix (^\\+) with
        a negative lookahead (?!\\+) to exclude the '+++ b/...' file-header lines,
        so that only genuine added lines trigger signals.

        Context lines (space-prefixed) and removed lines (^-) never match.
        """
        score = 0
        signals_detected: List[str] = []

        # Signal 1: Retry count increase on added lines only.
        # Excludes '+++ b/...' file header lines via negative lookahead (?!\+).
        if re.search(r'^\+(?!\+).*(?:RETRIES_MAX|max_retries)\s*=.*(["\']?([4-9]|\d{2,})["\']?)', diff_text, re.MULTILINE):
            score += 30
            signals_detected.append("Aggressive retry count increase (max_retries >= 4)")

        # Signal 2: Backoff removal on added lines only.
        if re.search(r'^\+(?!\+).*(?:RETRY_BACKOFF_FACTOR|backoff)\s*=.*(["\']?0(\.0)?["\']?)', diff_text, re.MULTILINE) or \
           re.search(r'^\+(?!\+).*wait_fixed\(0\)', diff_text, re.MULTILINE):
            score += 20
            signals_detected.append("Removal of backoff / immediate retry execution")

        # Signal 3: Aggressive timeout reduction on added lines only.
        if re.search(r'^\+(?!\+).*(?:RETRY_TIMEOUT_SECONDS|timeout)\s*=.*(["\']?0\.[1-9]["\']?)', diff_text, re.MULTILINE):
            score += 20
            signals_detected.append("Aggressive timeout reduction (timeout < 1.0s)")

        # Signal 4: Touches networking/client call without circuit breaker
        if "+with httpx.Client" in diff_text or "+client.post" in diff_text:
            score += 15
            signals_detected.append("Downstream HTTP dependency modification")

        # Signal 5: Test-only discount.
        # Only fires when the diff contains at least one +++ / --- file header
        # AND every such header points into the tests/ directory.  The
        # non-empty guard prevents vacuous-truth matches on headerless diffs.
        file_headers = [
            line for line in diff_text.splitlines()
            if line.startswith("+++ ") or line.startswith("--- ")
        ]
        if file_headers and all(
            line.startswith("+++ b/tests/") or line.startswith("--- a/tests/")
            for line in file_headers
        ):
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
