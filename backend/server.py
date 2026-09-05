from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.pipelines.mobile import MobilePipeline
from backend.pipelines.bike import BikePipeline
from backend.pipelines.car import CarPipeline
from backend.pipelines.general import GeneralPipeline
from backend.pipelines.accessory import get_addons

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger(__name__)

# ── Environment ───────────────────────────────────────────────────────────────
def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        base = Path(__file__).resolve().parent.parent
        load_dotenv(base / ".env", override=False)
        load_dotenv(base.parent / ".env", override=False)
    except ImportError:
        pass

_load_env()

# ── Razorpay client (optional) ────────────────────────────────────────────────
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
_razorpay_client = None

def _get_razorpay():
    global _razorpay_client
    if _razorpay_client is not None:
        return _razorpay_client
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return None
    try:
        import razorpay  # type: ignore
        _razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        LOGGER.info("Razorpay client initialized (key: %s...)", RAZORPAY_KEY_ID[:12])
        return _razorpay_client
    except Exception as exc:
        LOGGER.warning("Razorpay SDK not available: %s", exc)
        return None

# ── Data ─────────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent

def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("Could not load %s: %s", path, exc)
        return []

CATALOG = _load_json(BASE / "data" / "mobile_catalog.json") + _load_json(BASE / "data" / "vehicles.json")
LOGGER.info("Loaded %d catalog items from local data files.", len(CATALOG))

# ── Pipelines ─────────────────────────────────────────────────────────────────
PIPELINES = {
    "mobile": MobilePipeline(),
    "bike": BikePipeline(),
    "car": CarPipeline(),
}
GENERAL_PIPELINE = GeneralPipeline()

# Map user-facing category words to canonical names
CATEGORY_ALIASES = {
    # mobile
    "phone": "mobile", "phones": "mobile", "smartphone": "mobile", "smartphones": "mobile",
    "iphone": "mobile", "android": "mobile", "handset": "mobile",
    # bike
    "bike": "bike", "bikes": "bike", "motorcycle": "bike", "motorcycles": "bike",
    "scooter": "bike", "scooters": "bike", "motorbike": "bike",
    # car
    "car": "car", "cars": "car", "suv": "car", "sedan": "car", "hatchback": "car", "muv": "car",
    "vehicle": "car", "vehicles": "car", "automobile": "car",
    # general
    "laptop": "laptop", "laptops": "laptop", "notebook": "laptop",
    "shoes": "shoes", "shoe": "shoes", "sneakers": "shoes", "footwear": "shoes", "sandals": "shoes",
    "headphones": "headphones", "earphones": "headphones", "earbuds": "headphones",
    "watch": "watches", "watches": "watches", "smartwatch": "watches",
    "clothing": "clothing", "clothes": "clothing", "shirt": "clothing", "tshirt": "clothing",
    "bags": "bags", "bag": "bags", "backpack": "bags",
    "gaming": "gaming", "game": "gaming",
    "electronics": "electronics",
    "tv": "electronics", "television": "electronics", "monitor": "electronics", "tablet": "electronics",
    "camera": "electronics",
    "accessories": "accessories",
}

PIPELINE_CATEGORIES = {"mobile", "bike", "car"}

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="RazorPay Agentic Commerce", version="3.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)


@app.get("/api/health")
def health():
    rz_available = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
    return {
        "status": "ok",
        "version": "3.2.0",
        "catalog_items": len(CATALOG),
        "pipelines": list(PIPELINES),
        "general_pipeline": True,
        "vehicle_sources": {"bike": "BikeWale", "car": "CarDekho"},
        "mobile_source": "SerpAPI (Amazon + Flipkart)",
        "razorpay": "configured" if rz_available else "not configured (add RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET to .env)",
        "razorpay_key_id": RAZORPAY_KEY_ID if rz_available else None,
    }


@app.get("/api/search")
def search(
    category: str = Query(..., description="Product category (mobile, bike, car, laptop, shoes, ...)"),
    budget: Optional[float] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    storage: Optional[int] = None,
    cc_min: Optional[float] = None,
    cc_max: Optional[float] = None,
    target_cc: Optional[float] = None,
    body_type: Optional[str] = None,
    fuel: Optional[str] = None,
    transmission: Optional[str] = None,
    seats: Optional[int] = None,
    rank_by: Optional[str] = None,
    intent: Optional[str] = None,
    category_type: Optional[str] = None,
    keywords: Optional[str] = None,
):
    t0 = time.perf_counter()

    cat_raw = (category or "").strip().lower()
    canonical = CATEGORY_ALIASES.get(cat_raw, cat_raw)

    effective_budget = max_budget if max_budget is not None else budget

    if brand and len(brand) > 100:
        raise HTTPException(status_code=400, detail="brand parameter too long")
    if model and len(model) > 200:
        raise HTTPException(status_code=400, detail="model parameter too long")
    if keywords and len(keywords) > 500:
        raise HTTPException(status_code=400, detail="keywords parameter too long")
    if effective_budget is not None and (effective_budget < 0 or effective_budget > 1_000_000_000):
        raise HTTPException(status_code=400, detail="budget out of valid range")

    q = {
        "category": canonical,
        "budget": effective_budget,
        "min_budget": min_budget,
        "brand": brand,
        "model": model,
        "storage": storage,
        "cc_min": cc_min,
        "cc_max": cc_max,
        "target_cc": target_cc,
        "body_type": body_type,
        "fuel": fuel,
        "transmission": transmission,
        "seats": seats,
        "rank_by": rank_by,
        "intent": intent,
        "category_type": category_type,
        "keywords": keywords,
    }

    LOGGER.info(
        "SEARCH category=%r brand=%r model=%r budget=%s min_budget=%s keywords=%r",
        canonical, brand, model, effective_budget, min_budget, keywords,
    )

    try:
        if canonical in PIPELINE_CATEGORIES:
            result = PIPELINES[canonical].search(CATALOG, q)
        else:
            result = GENERAL_PIPELINE.search(CATALOG, q)
    except Exception as exc:
        LOGGER.exception("Pipeline error for category=%r: %s", canonical, exc)
        return {
            "items": [],
            "upgrade": None,
            "explanation": "An internal error occurred. Please try again.",
        }

    elapsed = time.perf_counter() - t0
    LOGGER.info("SEARCH done: category=%r → %d results in %.2fs", canonical, len(result.items), elapsed)

    return {
        "items": result.items,
        "upgrade": result.upgrade,
        "explanation": result.explanation,
    }


@app.get("/api/addons")
def addons(
    category: str = Query(...),
    model: Optional[str] = None,
):
    if not category:
        raise HTTPException(status_code=400, detail="category is required")
    if model and len(model) > 200:
        raise HTTPException(status_code=400, detail="model parameter too long")

    LOGGER.info("ADDONS category=%r model=%r", category, model)
    items = get_addons(category, {"model": model})
    return {"items": items}


# ── Razorpay Payment Endpoints ────────────────────────────────────────────────

class OrderRequest(BaseModel):
    amount: int       # in paise (INR × 100)
    currency: str = "INR"
    receipt: str = ""
    notes: dict = {}

class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@app.post("/api/orders")
async def create_order(req: OrderRequest):
    """Create a Razorpay order server-side. Amount must be in paise."""
    if req.amount <= 0 or req.amount > 10_000_000_00:  # max ₹1cr
        raise HTTPException(status_code=400, detail="Invalid amount")

    client = _get_razorpay()
    if client is None:
        # Demo mode — return a fake order so the checkout can still be demonstrated
        fake_id = f"order_DEMO_{uuid.uuid4().hex[:14].upper()}"
        LOGGER.warning("Razorpay not configured — returning demo order %s", fake_id)
        return {
            "id": fake_id,
            "amount": req.amount,
            "currency": req.currency,
            "status": "created",
            "demo": True,
            "message": "Demo order (Razorpay keys not configured in .env). Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to enable real payments.",
        }

    try:
        receipt = req.receipt or f"receipt_{uuid.uuid4().hex[:12]}"
        order_data = {
            "amount": req.amount,
            "currency": req.currency,
            "receipt": receipt,
            "notes": req.notes,
        }
        order = client.order.create(data=order_data)
        LOGGER.info("Razorpay order created: %s  amount=%s", order.get("id"), req.amount)
        return {
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "status": order["status"],
            "demo": False,
        }
    except Exception as exc:
        LOGGER.exception("Razorpay order creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Payment service error: {exc}")


@app.post("/api/verify")
async def verify_payment(req: VerifyRequest):
    """Verify Razorpay payment signature server-side."""
    if not RAZORPAY_KEY_SECRET:
        # Demo mode
        return {"verified": True, "demo": True, "message": "Demo verification (no secret configured)."}

    msg = f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(RAZORPAY_KEY_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    if hmac.compare_digest(expected, req.razorpay_signature):
        LOGGER.info("Payment verified: order=%s payment=%s", req.razorpay_order_id, req.razorpay_payment_id)
        return {"verified": True, "demo": False}
    else:
        LOGGER.warning("Payment verification FAILED: order=%s", req.razorpay_order_id)
        raise HTTPException(status_code=400, detail="Payment verification failed — signature mismatch.")
