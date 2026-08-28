"""Integration tests for live Docker Compose stack verifying real HTTP path and Toxiproxy routing."""
import time
import pytest
import requests

BASE_FRONTEND_URL = "http://localhost:8000"
BASE_CHECKOUT_URL = "http://localhost:8001"
BASE_PAYMENT_URL = "http://localhost:8002"
TOXIPROXY_ADMIN_URL = "http://localhost:8474"
PROMETHEUS_URL = "http://localhost:9090"

def is_stack_running():
    try:
        r = requests.get(f"{BASE_FRONTEND_URL}/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False

@pytest.mark.integration
class TestLiveServiceTopology:
    
    def test_all_health_endpoints(self):
        if not is_stack_running():
            pytest.skip("Docker Compose stack not running on localhost")
            
        r_front = requests.get(f"{BASE_FRONTEND_URL}/health")
        assert r_front.status_code == 200
        assert r_front.json()["service"] == "frontend"

        r_check = requests.get(f"{BASE_CHECKOUT_URL}/health")
        assert r_check.status_code == 200
        assert r_check.json()["service"] == "checkout"
        assert "toxiproxy:18002" in r_check.json()["payment_url"]

        r_pay = requests.get(f"{BASE_PAYMENT_URL}/health")
        assert r_pay.status_code == 200
        assert r_pay.json()["service"] == "payment"

    def test_toxiproxy_proxy_configured(self):
        if not is_stack_running():
            pytest.skip("Docker Compose stack not running on localhost")
            
        r_toxi = requests.get(f"{TOXIPROXY_ADMIN_URL}/proxies/payment-proxy")
        assert r_toxi.status_code == 200
        data = r_toxi.json()
        assert data["name"] == "payment-proxy"
        assert "18002" in data["listen"]
        assert data["upstream"] == "payment-service:8002"
        assert data["enabled"] is True

    def test_end_to_end_order_flow_success(self):
        if not is_stack_running():
            pytest.skip("Docker Compose stack not running on localhost")
            
        payload = {
            "item_id": "item_999",
            "quantity": 2,
            "amount": 100.0,
            "user_id": "test_buyer"
        }
        r = requests.post(f"{BASE_FRONTEND_URL}/orders", json=payload, timeout=5.0)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert "ord_" in data["order_id"]
        assert "pay_" in data["payment_id"]
        assert data["retries_attempted"] == 0

    def test_end_to_end_payment_failure_propagation(self):
        if not is_stack_running():
            pytest.skip("Docker Compose stack not running on localhost")
            
        payload = {
            "item_id": "item_fail",
            "quantity": 1,
            "amount": 50.0,
            "force_payment_failure": True
        }
        r = requests.post(f"{BASE_FRONTEND_URL}/orders", json=payload, timeout=5.0)
        assert r.status_code == 502

    def test_metrics_exposed_and_prometheus_healthy(self):
        if not is_stack_running():
            pytest.skip("Docker Compose stack not running on localhost")
            
        # Check Prometheus targets
        r_prom = requests.get(f"{PROMETHEUS_URL}/api/v1/targets")
        assert r_prom.status_code == 200
        targets = r_prom.json()["data"]["activeTargets"]
        job_names = {t["labels"]["job"] for t in targets}
        assert {"frontend", "checkout", "payment"}.issubset(job_names)

    def test_toxiproxy_in_path_verification(self):
        """Verifies that injecting latency via Toxiproxy directly impacts checkout request duration."""
        if not is_stack_running():
            pytest.skip("Docker Compose stack not running on localhost")
            
        toxic_payload = {
            "name": "test_latency",
            "type": "latency",
            "stream": "downstream",
            "attributes": {
                "latency": 400,
                "jitter": 0
            }
        }
        # Add latency toxic
        r_add = requests.post(f"{TOXIPROXY_ADMIN_URL}/proxies/payment-proxy/toxics", json=toxic_payload)
        assert r_add.status_code == 200
        
        try:
            start = time.time()
            payload = {"item_id": "item_lag", "quantity": 1, "amount": 25.0}
            r = requests.post(f"{BASE_FRONTEND_URL}/orders", json=payload, timeout=5.0)
            elapsed = time.time() - start
            assert r.status_code == 200
            assert elapsed >= 0.38, f"Expected elapsed time >= 0.38s due to 400ms toxic, got {elapsed}s"
        finally:
            # Clean up toxic
            requests.delete(f"{TOXIPROXY_ADMIN_URL}/proxies/payment-proxy/toxics/test_latency")
