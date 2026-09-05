from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

PRICE_RE = re.compile(
    r"(?i)(?:₹\s*|rs\.?\s*|inr\s*)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|lac|crore|cr|k)?"
)

# Category-aware minimum valid prices (INR)
CATEGORY_MIN_PRICE: Dict[str, int] = {
    "bike": 15000,
    "car": 200000,
    "mobile": 2000,
    "shoes": 100,
    "clothing": 50,
    "laptop": 10000,
    "headphones": 200,
    "electronics": 100,
    "gaming": 200,
    "watches": 200,
    "bags": 100,
    "accessory": 50,
    "default": 1,
}

CATEGORY_MAX_PRICE: Dict[str, int] = {
    "bike": 100_000_000,
    "car": 1_000_000_000,
    "mobile": 10_000_000,
    "shoes": 1_000_000,
    "clothing": 500_000,
    "laptop": 10_000_000,
    "headphones": 500_000,
    "electronics": 10_000_000,
    "gaming": 10_000_000,
    "watches": 10_000_000,
    "bags": 1_000_000,
    "accessory": 100_000,
    "default": 1_000_000_000,
}


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def parse_price(value: Any) -> int | None:
    """Parse a price value from various formats into an integer INR amount."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in ("none", "null", "n/a", "unavailable", "price unavailable"):
        return None

    matches = PRICE_RE.findall(text)
    if not matches:
        return None

    number, unit = matches[0]
    try:
        amount = float(number)
    except ValueError:
        return None

    unit = unit.lower()
    if unit in ("lakh", "lakhs", "lac"):
        amount *= 100_000
    elif unit in ("crore", "cr"):
        amount *= 10_000_000
    elif unit == "k":
        amount *= 1_000

    result = int(amount)
    return result if result > 0 else None


def valid_url(value: Any) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def validate_product(product: Dict[str, Any], category: str) -> bool:
    """Return True if the product has a non-empty name and a sane price."""
    name = str(product.get("name") or "").strip()
    if not name or len(name) < 2:
        return False

    price = product.get("price")
    if price is not None:
        parsed = parse_price(price)
        if parsed is not None:
            product["price"] = parsed
            price = parsed
        else:
            price = None

    if price is not None:
        cat = category.lower()
        min_p = CATEGORY_MIN_PRICE.get(cat, CATEGORY_MIN_PRICE["default"])
        max_p = CATEGORY_MAX_PRICE.get(cat, CATEGORY_MAX_PRICE["default"])
        if price < min_p or price > max_p:
            # Invalid price — mark as unavailable rather than failing the whole product
            product["price"] = None
            product["price_type"] = f"Price unavailable (out of range for {category})"

    if product.get("source_url") and not valid_url(product["source_url"]):
        product["source_url"] = None

    return True


def dedupe_products(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate products based on normalised name/model/variant identity."""
    seen: set = set()
    result: List[Dict[str, Any]] = []
    for item in items:
        identity = normalize_text(
            " ".join(str(item.get(field) or "") for field in ("brand", "model", "variant", "name"))
        )
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result
