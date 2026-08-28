"""Human approval gate tests verifying that AI agent cannot bypass human decision."""
from unittest.mock import patch
from changeproof.cli import prompt_human_decision

def test_human_approval_required_and_respected():
    """Simulates explicit human approval."""
    with patch("builtins.input", return_value="1"):  # Option 1 = Approve & Deploy
        decision = prompt_human_decision("case-01")
        assert decision["status"] == "APPROVED"
        assert decision["action"] == "deploy"

def test_human_rejection_blocks_autonomous_deployment():
    """Simulates explicit human rejection."""
    with patch("builtins.input", return_value="2"):  # Option 2 = Reject
        decision = prompt_human_decision("case-01")
        assert decision["status"] == "REJECTED"
        assert decision["action"] == "block"

def test_agent_cannot_auto_approve_without_human_input():
    """When input is empty, invalid, or skipped, the system defaults to review/hold."""
    with patch("builtins.input", return_value=""):  # No input / default
        decision = prompt_human_decision("case-01")
        assert decision["status"] == "HOLD"
        assert decision["action"] == "escalate_for_review"
