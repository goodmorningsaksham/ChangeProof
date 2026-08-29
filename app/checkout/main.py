"""Checkout Service — Core business workflow with configurable downstream retries."""
import os
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, wait_fixed, retry_if_exception_type, RetryCallState
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="Checkout Service", version="1.0.0")

# Configuration (Defaults for baseline behavior)
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://toxiproxy:18002")
RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))
RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))

# Prometheus Metrics
CHECKOUT_REQUESTS_TOTAL = Counter(
    "checkout_requests_total",
    "Total checkout requests received",
    ["status"],
)
CHECKOUT_LATENCY_SECONDS = Histogram(
    "checkout_request_duration_seconds",
    "Duration of checkout requests in seconds",
)
RETRY_COUNT_TOTAL = Counter(
    "retry_count_total",
    "Total retry attempts made to downstream services",
    ["service", "target"],
)
RETRY_EXHAUSTED_TOTAL = Counter(
    "retry_exhausted_total",
    "Total times retry budget was exhausted",
    ["service", "target"],
)
HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "Total HTTP errors encountered in checkout handling",
    ["error_type"],
)

# Initialize metric labels so they appear immediately in Prometheus scrapes
RETRY_COUNT_TOTAL.labels(service="checkout", target="payment").inc(0)
RETRY_EXHAUSTED_TOTAL.labels(service="checkout", target="payment").inc(0)
CHECKOUT_REQUESTS_TOTAL.labels(status="success").inc(0)

class CheckoutRequest(BaseModel):
    order_id: str
    amount: float
    user_id: Optional[str] = "user_default"
    force_payment_failure: Optional[bool] = False

class CheckoutResponse(BaseModel):
    order_id: str
    status: str
    payment_id: Optional[str] = None
    retries_attempted: int = 0
    total_latency_ms: float

def record_retry_callback(retry_state: RetryCallState):
    """Increment retry counter on every retry attempt.

    tenacity calls before_sleep with attempt_number = the attempt that just
    failed and will be retried.  attempt_number >= 1 counts every retry
    (the first retry fires with attempt_number=1).  The prior guard
    (attempt_number > 1) silently dropped the first retry of each request.
    """
    if retry_state.attempt_number >= 1:
        RETRY_COUNT_TOTAL.labels(service="checkout", target="payment").inc()

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "checkout",
        "payment_url": PAYMENT_SERVICE_URL,
        "retries_max": RETRIES_MAX,
        "retry_timeout_s": RETRY_TIMEOUT_SECONDS,
        "retry_backoff_factor": RETRY_BACKOFF_FACTOR,
    }

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

def call_payment_with_retries(order_id: str, amount: float, force_failure: bool = False) -> tuple[dict, int]:
    """Call payment service with explicit retry and timeout semantics."""
    attempts = 0
    
    # Define retry policy dynamically based on service configuration
    wait_strategy = (
        wait_exponential(multiplier=RETRY_BACKOFF_FACTOR, min=0.1, max=3.0)
        if RETRY_BACKOFF_FACTOR > 0
        else wait_fixed(0)
    )

    @retry(
        stop=stop_after_attempt(RETRIES_MAX),
        wait=wait_strategy,
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        before_sleep=record_retry_callback,
        reraise=True,
    )
    def _execute_http_call():
        nonlocal attempts
        attempts += 1
        with httpx.Client(timeout=RETRY_TIMEOUT_SECONDS) as client:
            resp = client.post(
                f"{PAYMENT_SERVICE_URL}/authorize",
                json={
                    "order_id": order_id,
                    "amount": amount,
                    "force_failure": force_failure,
                },
            )
            resp.raise_for_status()
            return resp.json()

    try:
        payment_data = _execute_http_call()
        return payment_data, (attempts - 1)
    except Exception as e:
        RETRY_EXHAUSTED_TOTAL.labels(service="checkout", target="payment").inc()
        raise e

@app.post("/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest):
    start_time = time.time()
    
    try:
        payment_data, retries_made = call_payment_with_retries(
            order_id=req.order_id,
            amount=req.amount,
            force_failure=bool(req.force_payment_failure),
        )
        
        duration = time.time() - start_time
        CHECKOUT_LATENCY_SECONDS.observe(duration)
        CHECKOUT_REQUESTS_TOTAL.labels(status="success").inc()
        
        return CheckoutResponse(
            order_id=req.order_id,
            status="completed",
            payment_id=payment_data.get("payment_id"),
            retries_attempted=retries_made,
            total_latency_ms=round(duration * 1000, 2),
        )
    except httpx.HTTPStatusError as e:
        HTTP_ERRORS_TOTAL.labels(error_type="payment_status_error").inc()
        CHECKOUT_REQUESTS_TOTAL.labels(status="payment_failed").inc()
        duration = time.time() - start_time
        CHECKOUT_LATENCY_SECONDS.observe(duration)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Downstream payment failed: {str(e)}",
        )
    except (httpx.RequestError, httpx.TimeoutException) as e:
        HTTP_ERRORS_TOTAL.labels(error_type="payment_network_or_timeout").inc()
        CHECKOUT_REQUESTS_TOTAL.labels(status="timeout_or_unreachable").inc()
        duration = time.time() - start_time
        CHECKOUT_LATENCY_SECONDS.observe(duration)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Payment service timeout or unreachable: {str(e)}",
        )
    except Exception as e:
        HTTP_ERRORS_TOTAL.labels(error_type="internal_error").inc()
        CHECKOUT_REQUESTS_TOTAL.labels(status="internal_error").inc()
        duration = time.time() - start_time
        CHECKOUT_LATENCY_SECONDS.observe(duration)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Checkout processing error: {str(e)}",
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
