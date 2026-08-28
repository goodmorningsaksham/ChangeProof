"""Unit tests for Toxiproxy client helper."""
import pytest
from unittest.mock import patch
from changeproof.toxiproxy_client import ToxiproxyClient

@pytest.fixture
def client():
    return ToxiproxyClient(admin_url="http://mock-toxiproxy:8474")

@patch("requests.get")
def test_get_proxies(mock_get, client):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"payment-proxy": {"name": "payment-proxy", "listen": "0.0.0.0:18002"}}
    
    proxies = client.get_proxies()
    assert "payment-proxy" in proxies
    mock_get.assert_called_once_with("http://mock-toxiproxy:8474/proxies", timeout=5.0)

@patch("requests.post")
def test_add_latency(mock_post, client):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"name": "latency_test", "type": "latency"}
    
    res = client.add_latency("payment-proxy", toxic_name="latency_test", latency_ms=1500, jitter_ms=50)
    assert res["name"] == "latency_test"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["attributes"]["latency"] == 1500

@patch("requests.delete")
def test_remove_toxic(mock_delete, client):
    mock_delete.return_value.status_code = 204
    assert client.remove_toxic("payment-proxy", "latency_test") is True

@patch("requests.post")
def test_reset(mock_post, client):
    mock_post.return_value.status_code = 204
    assert client.reset() is True
