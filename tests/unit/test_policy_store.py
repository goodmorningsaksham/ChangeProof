from changeproof.policy_store import load_policies, record_policy, validate_policy

def test_empty_policy_store(tmp_path):
    store_file = str(tmp_path / "policy_store.json")
    policies = load_policies(store_file)
    assert policies == []

def test_record_policy(tmp_path):
    store_file = str(tmp_path / "policy_store.json")
    policy = {
        "policy_id": "POL-001",
        "created_at": "2026-08-29T12:00:00Z",
        "author": "human",
        "trigger": {"service": "checkout", "metric": "retry_count_total", "condition": "rate > 100"},
        "rule": "max_retries <= 3",
        "decision": "REJECT",
        "rationale": "Avoid payment storm",
        "experiment_id": "exp-01"
    }
    assert validate_policy(policy) is True
    record_policy(policy, store_file)
    loaded = load_policies(store_file)
    assert len(loaded) == 1
    assert loaded[0]["policy_id"] == "POL-001"
