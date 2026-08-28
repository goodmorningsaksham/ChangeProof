"""Policy governance tests verifying human authority over policy store."""
import pytest
from changeproof.policy_store import load_policies, record_policy, validate_policy

def test_valid_human_policy_persists_and_loads(tmp_path):
    store_file = str(tmp_path / "policy_store.json")
    policy = {
        "policy_id": "POL-TEST-001",
        "created_at": "2026-08-29T04:00:00Z",
        "author": "Human Lead",
        "trigger": "payment_latency",
        "rule": "Max retries must be <= 2",
        "decision": "APPROVED_POLICY",
        "rationale": "Empirical evidence from live CASE-01 experiment",
        "experiment_id": "case-01",
    }
    
    assert validate_policy(policy) is True
    record_policy(policy, path=store_file)
    
    loaded = load_policies(path=store_file)
    assert len(loaded) == 1
    assert loaded[0]["policy_id"] == "POL-TEST-001"
    assert loaded[0]["rule"] == "Max retries must be <= 2"

def test_autonomous_unauthorized_policy_rejected(tmp_path):
    """An agent cannot write an un-authorized or malformed policy entry."""
    store_file = str(tmp_path / "policy_store.json")
    
    # Missing required human governance fields: 'author', 'rationale', 'decision'
    unauthorized_mutation = {
        "policy_id": "POL-AI-AUTONOMOUS",
        "rule": "Allow 10 retries always",
    }
    
    assert validate_policy(unauthorized_mutation) is False
    with pytest.raises(ValueError, match="Invalid policy schema"):
        record_policy(unauthorized_mutation, path=store_file)
