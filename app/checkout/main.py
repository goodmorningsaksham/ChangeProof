import os
import time
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential, retry_if_exception_type
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="Checkout Service", version="1.0.0")

# Configuration (Defaults for baseline behavior)
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://toxiproxy:18002")
RETRIES_MAX = int(os.getenv("RETRIES_MAX", "2"))  # Baseline: safe retry count
RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))  # Baseline: exponential backoff

# Prometheus Metrics
CHECKOUT_REQUESTS_TOTAL = Counter(
    "checkout_requests_total",
    "Total checkout requests received",
    ["status"],
)
CHECKOUT_LATENCY_SECONDS = Histogram(
    "checkout_latency_seconds",
    "Latency of checkout processing in seconds",
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
CHECKOUT_REQUESTS_TOTAL.labels(status="failure").inc(0)


class CheckoutRequest(BaseModel):
    order_id: str
    amount: float
    customer_id: str


def record_retry_callback(retry_state):
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
        "retries_max": RETRIES_MAX,
        "retry_timeout_s": RETRY_TIMEOUT_SECONDS,
        "retry_backoff_factor": RETRY_BACKOFF_FACTOR,
    }


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/checkout")
def process_checkout(req: CheckoutRequest):
    if RETRY_BACKOFF_FACTOR > 0:
        wait_strategy = wait_exponential(
            multiplier=RETRY_BACKOFF_FACTOR,
            min=0.1,
            max=5.0,
        )
    else:
        wait_strategy = wait_fixed(0)

    @retry(
        stop=stop_after_attempt(RETRIES_MAX),
        wait=wait_strategy,
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        before_sleep=record_retry_callback,
        reraise=True,
    )
    def call_payment_service():
        with httpx.Client(timeout=RETRY_TIMEOUT_SECONDS) as client:
            resp = client.post(
                f"{PAYMENT_SERVICE_URL}/authorize",
                json={"order_id": req.order_id, "amount": req.amount, "customer_id": req.customer_id},
            )
            resp.raise_for_status()
            return resp.json()

    start_time = time.time()
    try:
        payment_res = call_payment_service()
        duration = time.time() - start_time
        CHECKOUT_LATENCY_SECONDS.observe(duration)
        CHECKOUT_REQUESTS_TOTAL.labels(status="success").inc()
        return {
            "status": "success",
            "order_id": req.order_id,
            "payment": payment_res,
            "duration_seconds": round(duration, 3),
        }
    except httpx.HTTPStatusError as exc:
        duration = time.time() - start_time
        CHECKOUT_LATENCY_SECONDS.observe(duration)
        CHECKOUT_REQUESTS_TOTAL.labels(status="failure").inc()
        RETRY_EXHAUSTED_TOTAL.labels(service="checkout", target="payment").inc()
        HTTP_ERRORS_TOTAL.labels(error_type=f"http_{exc.response.status_code}").inc()
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Payment service rejected: {exc.response.text}",
        )
    except Exception as exc:
        duration = time.time() - start_time
        CHECKOUT_LATENCY_SECONDS.observe(duration)
        CHECKOUT_REQUESTS_TOTAL.labels(status="failure").inc()
        RETRY_EXHAUSTED_TOTAL.labels(service="checkout", target="payment").inc()
        HTTP_ERRORS_TOTAL.labels(error_type="timeout_or_unreachable").inc()
        raise HTTPException(
            status_code=500,
            detail=f"Payment service timeout or unreachable: {str(exc)}",
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
