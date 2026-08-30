"""Minimal Flask microservice target with standard Prometheus telemetry and retry loop."""
import os
import time
import requests
from flask import Flask, request, jsonify, Response
from tenacity import retry, stop_after_attempt, wait_exponential, wait_fixed, retry_if_exception_type, before_sleep
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))
RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))

DOWNSTREAM_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-proxy:8002/authorize")

RETRY_COUNT = Counter(
    "retry_count_total",
    "Total retry attempts across service boundaries",
    ["service", "target"]
)
REQUEST_COUNT = Counter(
    "checkout_requests_total",
    "Total incoming checkout requests",
    ["service", "status"]
)

def _count_retry(retry_state):
    if retry_state.attempt_number >= 1:
        RETRY_COUNT.labels(service="flask-checkout", target="payment").inc()

def get_retry_decorator():
    if RETRY_BACKOFF_FACTOR > 0:
        wait_strategy = wait_exponential(multiplier=RETRY_BACKOFF_FACTOR, min=0.1, max=2.0)
    else:
        wait_strategy = wait_fixed(0)
    return retry(
        stop=stop_after_attempt(RETRIES_MAX),
        wait=wait_strategy,
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        before_sleep=_count_retry,
        reraise=True
    )

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "framework": "flask"})

@app.route("/metrics", methods=["GET"])
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route("/api/v1/process-order", methods=["POST"])
def process_order():
    data = request.get_json() or {}
    item_id = data.get("item_id", "default_item")
    quantity = data.get("quantity", 1)
    
    @get_retry_decorator()
    def _call_downstream():
        resp = requests.post(
            DOWNSTREAM_URL,
            json={"order_id": f"ord_{int(time.time())}", "amount": 99.99},
            timeout=RETRY_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
        return resp.json()

    try:
        res = _call_downstream()
        REQUEST_COUNT.labels(service="flask-checkout", status="success").inc()
        return jsonify({"status": "SUCCESS", "item_id": item_id, "downstream": res}), 200
    except Exception as e:
        REQUEST_COUNT.labels(service="flask-checkout", status="error").inc()
        return jsonify({"status": "ERROR", "error": str(e)}), 504

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8005)
