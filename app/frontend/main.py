"""Frontend Gateway Service â€” Ingress API forwarding customer orders to Checkout."""
import os
import time
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import httpx
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="Frontend Gateway Service", version="1.0.0")

# Configuration
CHECKOUT_SERVICE_URL = os.getenv("CHECKOUT_SERVICE_URL", "http://checkout-service:8001")
GATEWAY_TIMEOUT_SECONDS = float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "5.0"))

# Prometheus Metrics
FRONTEND_REQUESTS_TOTAL = Counter(
    "frontend_requests_total",
    "Total ingress requests received at frontend gateway",
    ["status"],
)
FRONTEND_LATENCY_SECONDS = Histogram(
    "frontend_request_duration_seconds",
    "Duration of frontend order handling in seconds",
)

class OrderRequest(BaseModel):
    item_id: str
    quantity: int
    amount: Optional[float] = 99.99
    user_id: Optional[str] = "user_default"
    force_payment_failure: Optional[bool] = False

class OrderResponse(BaseModel):
    order_id: str
    status: str
    payment_id: Optional[str] = None
    retries_attempted: int = 0
    total_latency_ms: float

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "frontend",
        "checkout_url": CHECKOUT_SERVICE_URL,
    }

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/orders", response_model=OrderResponse)
def submit_order(order: OrderRequest):
    start_time = time.time()
    order_id = f"ord_{uuid.uuid4().hex[:8]}"
    
    checkout_payload = {
        "order_id": order_id,
        "amount": order.amount,
        "customer_id": order.user_id,`n        "user_id": order.user_id,
        "force_payment_failure": order.force_payment_failure,
    }
    
    try:
        with httpx.Client(timeout=GATEWAY_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{CHECKOUT_SERVICE_URL}/checkout", json=checkout_payload)
            resp.raise_for_status()
            checkout_data = resp.json()
            
        duration = time.time() - start_time
        FRONTEND_LATENCY_SECONDS.observe(duration)
        FRONTEND_REQUESTS_TOTAL.labels(status="success").inc()
        
        return OrderResponse(
            order_id=order_id,
            status=checkout_data.get("status", "completed"),
            payment_id=checkout_data.get("payment_id"),
            retries_attempted=checkout_data.get("retries_attempted", 0),
            total_latency_ms=round(duration * 1000, 2),
        )
    except httpx.HTTPStatusError as e:
        FRONTEND_REQUESTS_TOTAL.labels(status="downstream_error").inc()
        duration = time.time() - start_time
        FRONTEND_LATENCY_SECONDS.observe(duration)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Checkout failed: {e.response.text}",
        )
    except (httpx.RequestError, httpx.TimeoutException) as e:
        FRONTEND_REQUESTS_TOTAL.labels(status="timeout_or_unreachable").inc()
        duration = time.time() - start_time
        FRONTEND_LATENCY_SECONDS.observe(duration)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Checkout service unreachable or timed out: {str(e)}",
        )
    except Exception as e:
        FRONTEND_REQUESTS_TOTAL.labels(status="internal_error").inc()
        duration = time.time() - start_time
        FRONTEND_LATENCY_SECONDS.observe(duration)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Frontend gateway internal error: {str(e)}",
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


