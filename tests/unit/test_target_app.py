"""Unit tests for FastAPI target microservices logic."""
import pytest
from fastapi.testclient import TestClient
from app.payment.main import app as payment_app
from app.checkout.main import app as checkout_app
from app.frontend.main import app as frontend_app

@pytest.fixture
def payment_client():
    return TestClient(payment_app)

@pytest.fixture
def checkout_client():
    return TestClient(checkout_app)

@pytest.fixture
def frontend_client():
    return TestClient(frontend_app)

def test_payment_health(payment_client):
    res = payment_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["service"] == "payment"

def test_payment_metrics_endpoint(payment_client):
    res = payment_client.get("/metrics")
    assert res.status_code == 200
    assert b"payment_requests_total" in res.content

def test_payment_authorize_success(payment_client):
    res = payment_client.post("/authorize", json={"order_id": "ord_123", "amount": 49.99})
    assert res.status_code == 200
    data = res.json()
    assert data["order_id"] == "ord_123"
    assert data["status"] == "authorized"
    assert "pay_ord_123_" in data["payment_id"]

def test_payment_authorize_forced_failure(payment_client):
    res = payment_client.post("/authorize", json={"order_id": "ord_fail", "amount": 49.99, "force_failure": True})
    assert res.status_code == 400

def test_checkout_health(checkout_client):
    res = checkout_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "checkout"
    assert data["retries_max"] == 2  # Committed baseline default

def test_checkout_metrics_endpoint(checkout_client):
    res = checkout_client.get("/metrics")
    assert res.status_code == 200
    assert b"retry_count_total" in res.content
    assert b"checkout_requests_total" in res.content

def test_frontend_health(frontend_client):
    res = frontend_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["service"] == "frontend"

def test_frontend_metrics_endpoint(frontend_client):
    res = frontend_client.get("/metrics")
    assert res.status_code == 200
    assert b"frontend_requests_total" in res.content
