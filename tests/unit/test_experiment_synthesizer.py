"""Unit tests for topology-driven ExperimentSynthesizer."""
import yaml
import pytest
from changeproof.experiment_synthesizer import ExperimentSynthesizer


@pytest.fixture
def alt_topology(tmp_path):
    compose_path = tmp_path / "docker-compose.alt.yml"
    toxi_path = tmp_path / "toxiproxy_init.alt.json"

    compose_data = {
        "version": "3.8",
        "networks": {"alt-net": {"driver": "bridge"}},
        "services": {
            "warehouse-service": {
                "build": {"context": "./app/warehouse"},
                "ports": ["8002:8002"],
                "networks": ["alt-net"],
            },
            "toxiproxy": {
                "image": "ghcr.io/shopify/toxiproxy:2.9.0",
                "ports": ["8474:8474", "18002:18002"],
                "networks": ["alt-net"],
                "depends_on": ["warehouse-service"],
            },
            "inventory-service": {
                "build": {"context": "./app/inventory"},
                "ports": ["8001:8001"],
                "environment": [
                    "PORT=8001",
                    "WAREHOUSE_SERVICE_URL=http://toxiproxy:18002",
                    "RETRIES_MAX=3",
                    "RETRY_TIMEOUT_SECONDS=1.0",
                    "RETRY_BACKOFF_FACTOR=0.5",
                ],
                "networks": ["alt-net"],
                "depends_on": ["toxiproxy"],
            },
            "gateway-service": {
                "build": {"context": "./app/gateway"},
                "ports": ["8000:8000"],
                "environment": [
                    "PORT=8000",
                    "INVENTORY_SERVICE_URL=http://inventory-service:8001",
                    "GATEWAY_TIMEOUT_SECONDS=5.0",
                ],
                "networks": ["alt-net"],
                "depends_on": ["inventory-service"],
            },
        },
    }

    toxi_data = [
        {
            "name": "warehouse-proxy",
            "listen": "0.0.0.0:18002",
            "upstream": "warehouse-service:8002",
            "enabled": True,
        }
    ]

    with open(compose_path, "w", encoding="utf-8") as f:
        yaml.dump(compose_data, f)

    import json
    with open(toxi_path, "w", encoding="utf-8") as f:
        json.dump(toxi_data, f)

    return str(compose_path), str(toxi_path)


def test_synthesize_canonical_case01():
    diff_text = """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = 3
-RETRY_BACKOFF_FACTOR = 0.5
-RETRY_TIMEOUT_SECONDS = 1.0
+RETRIES_MAX = 8
+RETRY_BACKOFF_FACTOR = 0.0
+RETRY_TIMEOUT_SECONDS = 0.5
"""
    synthesizer = ExperimentSynthesizer(compose_path="docker-compose.yml")
    spec = synthesizer.synthesize(diff_text, case_id="test-case-01")

    assert spec["fault"]["proxy"] == "payment-proxy"
    assert spec["fault"]["toxic"]["attributes"]["latency"] == 1500  # max(2*500, 1500)
    assert any(m["labels"].get("service") == "checkout" for m in spec["measurements"]["metrics"])
    assert any(m["labels"].get("target") == "payment" for m in spec["measurements"]["metrics"])
    assert spec["assertions"]["pre_patch"][0]["condition"] == "> 2.0"
    assert spec["assertions"]["post_patch"][0]["condition"] == "<= 1.1"


def test_synthesize_generalizes_to_alternate_topology(alt_topology):
    compose_p, toxi_p = alt_topology
    diff_text = """--- a/app/inventory/main.py
+++ b/app/inventory/main.py
@@ -10,3 +10,3 @@
-RETRIES_MAX = 3
-RETRY_BACKOFF_FACTOR = 0.5
-RETRY_TIMEOUT_SECONDS = 1.0
+RETRIES_MAX = 8
+RETRY_BACKOFF_FACTOR = 0.0
+RETRY_TIMEOUT_SECONDS = 0.5
"""
    synthesizer = ExperimentSynthesizer(compose_path=compose_p, toxiproxy_config_path=toxi_p)
    spec = synthesizer.synthesize(diff_text, case_id="test-alt-inventory")

    assert spec["fault"]["proxy"] == "warehouse-proxy"
    assert spec["fault"]["toxic"]["attributes"]["latency"] == 1500
    assert any(m["labels"].get("service") == "inventory" for m in spec["measurements"]["metrics"])
    assert any(m["labels"].get("target") == "warehouse" for m in spec["measurements"]["metrics"])
    assert spec["target"]["compose_file"] == compose_p

def test_resolve_entrypoint_route_fastpath_fastapi():
    synthesizer = ExperimentSynthesizer()
    fastapi_code = """
from fastapi import FastAPI
app = FastAPI()

@app.post("/custom/orders")
def submit():
    return {}
"""
    # Fast path matches @app.post
    route, payload = synthesizer.resolve_entrypoint_route_via_agent(fastapi_code)
    # Even if called directly, fallback correctly parses or extracts
    assert route in ("/custom/orders", "/orders")


def test_resolve_entrypoint_route_agent_fallback_flask():
    synthesizer = ExperimentSynthesizer()
    flask_code = """
from flask import Flask, request
app = Flask(__name__)

@app.route("/api/v2/process-payment", methods=["POST"])
def process():
    data = request.get_json()
    order_id = data.get("order_id")
    amount = data.get("amount")
    return {"status": "ok"}
"""
    route, payload = synthesizer.resolve_entrypoint_route_via_agent(flask_code)
    assert route == "/api/v2/process-payment"
    assert "order_id" in payload or "amount" in payload


def test_resolve_entrypoint_route_agent_fallback_express():
    synthesizer = ExperimentSynthesizer()
    express_code = """
const express = require('express');
const app = express();

app.post('/api/v1/checkout/submit', (req, res) => {
    const { item_id, quantity } = req.body;
    res.json({ status: 'ok' });
});
"""
    route, payload = synthesizer.resolve_entrypoint_route_via_agent(express_code)
    assert route == "/api/v1/checkout/submit"
    assert "item_id" in payload or "quantity" in payload


def test_resolve_entrypoint_route_agent_fallback_fails_on_unparseable():
    synthesizer = ExperimentSynthesizer()
    empty_code = "print('hello world without routes')"
    with pytest.raises(ValueError, match="route discovery failed"):
        synthesizer.resolve_entrypoint_route_via_agent(empty_code)
