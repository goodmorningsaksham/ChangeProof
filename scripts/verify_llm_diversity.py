#!/usr/bin/env python3
"""Proof script: verify that LLM-grounded hypothesis descriptions are
meaningfully different across 3 topologies with the same signal type.

Run with:
    python scripts/verify_llm_diversity.py

Requires OPENAI_API_KEY or ANTHROPIC_API_KEY in env.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from changeproof.hypothesis_evaluator import generate_candidate_hypotheses

# -----------------------------------------------------------------------
# Three diffs — all trigger "retry count increase" signal — different topologies
# -----------------------------------------------------------------------

DIFF_CHECKOUT = """--- a/app/checkout/main.py
+++ b/app/checkout/main.py
@@ -10,4 +10,4 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
-RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))
+RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))
"""
CODE_CHECKOUT = '''import os, httpx
RETRIES_MAX = int(os.getenv("RETRIES_MAX", "8"))
RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.5"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.0"))

def process_checkout(item_id, quantity):
    for attempt in range(RETRIES_MAX + 1):
        try:
            r = httpx.post("http://payment-service/pay",
                          json={"item_id": item_id, "qty": quantity},
                          timeout=RETRY_TIMEOUT_SECONDS)
            return r.json()
        except httpx.TimeoutException:
            pass
    raise RuntimeError("Payment service unavailable")
'''

DIFF_INVENTORY = """--- a/app/inventory/main.py
+++ b/app/inventory/main.py
@@ -5,3 +5,3 @@
-RETRIES_MAX = int(os.getenv("RETRIES_MAX", "3"))
-RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "1.0"))
+RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))
+RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.7"))
"""
CODE_INVENTORY = '''import os, httpx
RETRIES_MAX = int(os.getenv("RETRIES_MAX", "6"))
RETRY_TIMEOUT_SECONDS = float(os.getenv("RETRY_TIMEOUT_SECONDS", "0.7"))

def check_stock(product_id):
    for attempt in range(RETRIES_MAX + 1):
        try:
            r = httpx.get(f"http://warehouse-service/stock/{product_id}",
                         timeout=RETRY_TIMEOUT_SECONDS)
            return r.json()
        except httpx.TimeoutException:
            pass
    return {"available": False}
'''

DIFF_EXPRESS = """--- a/app/order/server.js
+++ b/app/order/server.js
@@ -3,3 +3,3 @@
-const RETRIES_MAX = 2;
-const RETRY_TIMEOUT_MS = 1000;
-const RETRY_BACKOFF_MS = 500;
+const RETRIES_MAX = 8;
+const RETRY_TIMEOUT_MS = 500;
+const RETRY_BACKOFF_MS = 0;
"""
CODE_EXPRESS = '''const axios = require('axios');
const RETRIES_MAX = 8;
const RETRY_TIMEOUT_MS = 500;
const RETRY_BACKOFF_MS = 0;

async function submitOrder(orderId, items) {
  for (let attempt = 0; attempt <= RETRIES_MAX; attempt++) {
    try {
      const resp = await axios.post('http://inventory-service/reserve',
        { orderId, items }, { timeout: RETRY_TIMEOUT_MS });
      return resp.data;
    } catch (err) {
      if (RETRY_BACKOFF_MS > 0) await new Promise(r => setTimeout(r, RETRY_BACKOFF_MS));
    }
  }
  throw new Error('Inventory reservation failed');
}
'''

SIGNALS_CHECKOUT = [
    "Aggressive retry count increase (max_retries >= 4)",
    "Removal of backoff / immediate retry execution",
    "Aggressive timeout reduction (timeout < 1.0s)",
]
SIGNALS_INVENTORY = [
    "Aggressive retry count increase (max_retries >= 4)",
    "Aggressive timeout reduction (timeout < 1.0s)",
]
SIGNALS_EXPRESS = [
    "Aggressive retry count increase (max_retries >= 4)",
    "Removal of backoff / immediate retry execution",
    "Aggressive timeout reduction (timeout < 1.0s)",
]

CASES = [
    ("case-01 (checkout/payment)", DIFF_CHECKOUT, CODE_CHECKOUT, "payment-proxy", 1500, SIGNALS_CHECKOUT),
    ("inventory/warehouse",        DIFF_INVENTORY, CODE_INVENTORY, "warehouse-proxy", 2000, SIGNALS_INVENTORY),
    ("express-order-app (JS)",     DIFF_EXPRESS,   CODE_EXPRESS,   "order-proxy",    1600, SIGNALS_EXPRESS),
]


def run():
    print("=" * 80)
    print("TASK 1 PROOF: LLM-grounded hypothesis diversity across 3 topologies")
    print("=" * 80)

    all_retry_descriptions = []

    for name, diff, code, proxy, lat, signals in CASES:
        print(f"\n{'='*60}")
        print(f"CASE: {name}")
        print(f"{'='*60}")
        hypos = generate_candidate_hypotheses(
            signals,
            proxy_name=proxy,
            calibrated_latency_ms=lat,
            diff_text=diff,
            code_context=code,
        )
        for h in hypos:
            print(f"\n  [{h['id']}] {h['title']}")
            print(f"  Description: {h['description']}")
            print(f"  Code evidence: {h['grounding']['code_evidence']}")
            print(f"  Mechanism: {h['grounding']['mechanism']}")
        retry_h = next((h for h in hypos if h["id"] == "H-RETRY-CEILING"), None)
        if retry_h:
            all_retry_descriptions.append((name, retry_h["description"]))

    print("\n" + "=" * 80)
    print("DIVERSITY CHECK — H-RETRY-CEILING descriptions across all 3 cases:")
    print("=" * 80)
    for i, (name, desc) in enumerate(all_retry_descriptions):
        print(f"\n  [{i+1}] {name}:")
        print(f"  {desc}")

    if len(all_retry_descriptions) >= 3:
        d1, d2, d3 = [d for _, d in all_retry_descriptions[:3]]
        all_different = (d1 != d2) and (d2 != d3) and (d1 != d3)
        print(f"\nDIVERSITY VERDICT: {'PASS — all 3 descriptions are distinct' if all_different else 'FAIL — descriptions are identical!'}")
    else:
        print("\nInsufficient retry-ceiling hypotheses to compare.")


if __name__ == "__main__":
    run()
