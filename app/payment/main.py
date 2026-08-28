"""Payment Service — Downstream payment authorization provider."""
import os
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="Payment Service", version="1.0.0")

# Prometheus Metrics
PAYMENT_REQUESTS_TOTAL = Counter(
    "payment_requests_total",
    "Total payment authorization requests received",
    ["status"],
)
PAYMENT_LATENCY_SECONDS = Histogram(
    "payment_request_duration_seconds",
    "Duration of payment authorization handling in seconds",
)

class AuthorizeRequest(BaseModel):
    order_id: str
    amount: float
    user_id: Optional[str] = None
    force_failure: Optional[bool] = False
    synthetic_delay_ms: Optional[int] = 0

class AuthorizeResponse(BaseModel):
    payment_id: str
    order_id: str
    status: str
    amount: float

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "payment"}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/authorize", response_model=AuthorizeResponse)
def authorize(req: AuthorizeRequest):
    start_time = time.time()
    
    if req.synthetic_delay_ms and req.synthetic_delay_ms > 0:
        time.sleep(req.synthetic_delay_ms / 1000.0)

    if req.force_failure or req.amount < 0:
        PAYMENT_REQUESTS_TOTAL.labels(status="failed").inc()
        duration = time.time() - start_time
        PAYMENT_LATENCY_SECONDS.observe(duration)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment authorization rejected",
        )

    PAYMENT_REQUESTS_TOTAL.labels(status="success").inc()
    duration = time.time() - start_time
    PAYMENT_LATENCY_SECONDS.observe(duration)
    
    payment_id = f"pay_{req.order_id}_{int(time.time() * 1000)}"
    return AuthorizeResponse(
        payment_id=payment_id,
        order_id=req.order_id,
        status="authorized",
        amount=req.amount,
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
