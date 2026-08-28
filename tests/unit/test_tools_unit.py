"""Unit tests for agent tools."""
import pytest
from changeproof.tools import read_file, propose_hypothesis, read_topology

def test_read_file_security():
    with pytest.raises(PermissionError):
        read_file("../outside.txt")

def test_read_topology():
    topo = read_topology()
    assert "services" in topo
    assert "checkout-service" in topo["services"]

def test_propose_hypothesis(tmp_path):
    out = tmp_path / "hyp.json"
    hyps = [{"id": "H1", "label": "retry_amplification", "rank": 1}]
    res = propose_hypothesis(hyps, output_path=str(out))
    assert res["status"] == "recorded"
    assert res["count"] == 1
