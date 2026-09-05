from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

import requests

from .validation import parse_price, validate_product, normalize_text

LOGGER = logging.getLogger(__name__)

_ENV_LOADED = False


def _load_environment() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
        project = Path(__file__).resolve().parents[2]
        load_dotenv(project / ".env", override=False)
        load_dotenv(project.parent / ".env", override=False)
        _ENV_LOADED = True
    except ImportError:
        _ENV_LOADED = True


def _get_api_key() -> Optional[str]:
    _load_environment()
    return os.getenv("SERPAPI_KEY") or os.getenv("SERPAPI_API_KEY")


def _seller_from_source(source: str) -> Optional[str]:
    s = (source or "").lower()
    if "amazon" in s:
        return "Amazon"
    if "flipkart" in s:
        return "Flipkart"
    return None


def _best_url(row: Dict[str, Any], seller: Optional[str]) -> Optional[str]:
    """Return best available product URL from a SerpAPI shopping result row."""
    # product_link is the direct seller page when SerpAPI provides it
    for field in ("product_link", "link"):
        url = row.get(field) or ""
        if not url:
            continue
        url_lower = url.lower()
        if seller == "Amazon" and ("amazon.in" in url_lower or "amazon.com" in url_lower):
            return url
        if seller == "Flipkart" and "flipkart.com" in url_lower:
            return url
        # For non-Amazon/Flipkart or unmatched: still return if it's a real URL
        if url.startswith(("http://", "https://")):
            return url
    return None


def _model_identity(name: str) -> str:
    """Normalise a product name to a deduplication key."""
    text = re.sub(r"(?i)\b(amazon\.in|flipkart|india|buy|price|online|best|shop)\b", " ", name or "")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _build_mobile_query(q: Dict[str, Any]) -> str:
    """Build a focused SerpAPI query from parsed search parameters."""
    parts: List[str] = []
    brand = (q.get("brand") or "").strip()
    model = (q.get("model") or "").strip()
    keywords = (q.get("keywords") or "").strip()
    raw_query = (q.get("raw_query") or "").lower()
    storage = q.get("storage")
    ram = q.get("ram")
    budget = q.get("budget")
    min_budget = q.get("min_budget")

    if brand:
        parts.append(brand)
    if model and model.lower() != brand.lower():
        parts.append(model)
    if storage:
        parts.append(f"{storage}GB")
    if ram:
        parts.append(f"{ram}GB RAM")

    # Feature-aware keyword injection
    feature_parts: List[str] = []
    stop = {"phone", "phones", "mobile", "mobiles", "smartphone", "buy", "india", "under", "below", "best", "good"}
    if keywords:
        kw_tokens = [t for t in keywords.split() if t.lower() not in stop]
        if kw_tokens:
            feature_parts.extend(kw_tokens)

    # Extract key features from raw_query that improve search quality (avoid duplicates)
    fp_lower = " ".join(feature_parts).lower()
    if "5g" in raw_query and "5g" not in fp_lower:
        feature_parts.append("5G")
    if any(x in raw_query for x in ("camera", "photo", "photography")) and "camera" not in fp_lower:
        feature_parts.append("camera")
    if any(x in raw_query for x in ("gaming", "game", "performance")) and "gaming" not in fp_lower:
        feature_parts.append("gaming")
    if any(x in raw_query for x in ("battery", "backup")) and "battery" not in fp_lower:
        feature_parts.append("long battery")
    if "amoled" in raw_query and "amoled" not in fp_lower:
        feature_parts.append("AMOLED")

    if feature_parts:
        parts.append(" ".join(feature_parts))

    # Always anchor to phones/smartphones unless a specific model is named
    if not model:
        parts.append("smartphone")

    parts.append("buy online India")

    if budget:
        parts.append(f"under Rs {int(budget)}")

    return " ".join(parts)


def search_mobile(query_text: str) -> List[Dict[str, Any]]:
    """
    Search Amazon India and Flipkart for mobiles via SerpAPI Google Shopping.
    Returns a deduplicated list of products with Amazon/Flipkart price comparison.
    Falls back to empty list (NOT demo data) if the API fails.
    """
    api_key = _get_api_key()
    if not api_key:
        LOGGER.warning("SERPAPI_KEY not configured — live mobile search disabled.")
        return []

    checked_at = datetime.now(timezone.utc).isoformat()
    raw_results: List[Dict[str, Any]] = []

    try:
        response = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_shopping",
                "q": query_text,
                "hl": "en",
                "gl": "in",
                "api_key": api_key,
                "num": 20,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status in (401, 403):
            LOGGER.error("SerpAPI key invalid or expired (HTTP %s).", status)
        elif status == 429:
            LOGGER.warning("SerpAPI quota exceeded (HTTP 429).")
        else:
            LOGGER.warning("SerpAPI HTTP error %s: %s", status, exc)
        return []
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("SerpAPI request failed: %s", exc)
        return []

    for row in payload.get("shopping_results", []):
        title = str(row.get("title") or "").strip()
        if not title:
            continue

        # Strip retailer suffixes from title
        name = re.sub(r"\s*[-|]\s*(Amazon\.in|Flipkart|Amazon|India).*$", "", title, flags=re.I).strip()

        # Skip obvious non-product pages
        if re.search(r"(?i)(mobile phones? online|best prices? in india|mobile store|search results?|buy \w+ phones)", name):
            continue

        row_source = str(row.get("source") or "")
        seller = _seller_from_source(row_source)

        # We accept Amazon, Flipkart, and other major Indian sellers
        source_url = _best_url(row, seller)

        price = parse_price(row.get("extracted_price") or row.get("price"))
        rating = row.get("rating")
        reviews = row.get("reviews")
        thumbnail = row.get("thumbnail") or row.get("serpapi_thumbnail")

        item: Dict[str, Any] = {
            "name": name,
            "brand": name.split()[0] if name else None,
            "model": name,
            "variant": None,
            "price": price,
            "product_rating": float(rating) if isinstance(rating, (int, float)) else None,
            "review_count": int(reviews) if isinstance(reviews, (int, float)) else None,
            "source": seller or row_source or "Online",
            "source_url": source_url,
            "price_type": "live listing price" if price else "Price unavailable",
            "availability": "In stock" if price else None,
            "category": "mobile",
            "checked_at": checked_at,
            "identity": _model_identity(name),
            "image": thumbnail,
            "live": True,
        }

        if validate_product(item, "mobile"):
            raw_results.append(item)

    # Group by model identity and merge Amazon + Flipkart prices
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in raw_results:
        identity = item.get("identity") or _model_identity(item.get("name", ""))
        if not identity:
            continue

        product = grouped.setdefault(identity, {
            "id": f"live-mobile:{identity}",
            "name": item["name"],
            "brand": item.get("brand"),
            "model": item.get("model"),
            "variant": item.get("variant"),
            "category": "mobile",
            "amazon": None,
            "flipkart": None,
            "product_rating": item.get("product_rating"),
            "review_count": item.get("review_count"),
            "checked_at": item.get("checked_at"),
            "source": "LIVE",
            "availability": item.get("availability"),
            "image": item.get("image"),
            "live": True,
        })

        seller_key = item["source"].lower() if item["source"] in ("Amazon", "Flipkart") else None
        entry = {"price": item.get("price"), "url": item.get("source_url"), "source": item["source"]}

        if seller_key == "amazon":
            product["amazon"] = entry
        elif seller_key == "flipkart":
            product["flipkart"] = entry
        else:
            # Non-Amazon/Flipkart seller — store as generic source_url
            if not product.get("source_url"):
                product["source_url"] = item.get("source_url")
                product["other_source"] = item["source"]

        if item.get("product_rating") is not None and product.get("product_rating") is None:
            product["product_rating"] = item["product_rating"]
        if item.get("review_count") is not None and (product.get("review_count") or 0) < item["review_count"]:
            product["review_count"] = item["review_count"]
        if item.get("image") and not product.get("image"):
            product["image"] = item["image"]
        product["checked_at"] = max(product.get("checked_at") or "", item.get("checked_at") or "")

    results: List[Dict[str, Any]] = []
    for product in grouped.values():
        sellers = [product.get("amazon"), product.get("flipkart")]
        valid_prices = [x["price"] for x in sellers if x and isinstance(x.get("price"), (int, float)) and x["price"] > 0]

        product["price"] = min(valid_prices) if valid_prices else None
        product["price_type"] = "live Amazon/Flipkart listing" if valid_prices else "Price unavailable"
        product["best_price_source"] = next(
            (x["source"] for x in sellers if x and x.get("price") == product.get("price")), None
        )

        if product.get("amazon") and product.get("flipkart"):
            product["source"] = "LIVE • Amazon + Flipkart"
        elif product.get("amazon"):
            product["source"] = "LIVE • Amazon"
        elif product.get("flipkart"):
            product["source"] = "LIVE • Flipkart"
        else:
            product["source"] = f"LIVE • {product.get('other_source', 'Online')}"

        results.append(product)

    LOGGER.info("search_mobile('%s'): %d raw results → %d grouped products", query_text, len(raw_results), len(results))
    return results


def search_general(query: str, category: str = "product") -> List[Dict[str, Any]]:
    """
    Generic SerpAPI Google Shopping search for any product category.
    Used for shoes, laptops, electronics, headphones, etc.
    """
    api_key = _get_api_key()
    if not api_key:
        LOGGER.warning("SERPAPI_KEY not configured — live product search disabled.")
        return []

    checked_at = datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []

    try:
        response = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_shopping",
                "q": f"{query} India",
                "hl": "en",
                "gl": "in",
                "api_key": api_key,
                "num": 20,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status in (401, 403):
            LOGGER.error("SerpAPI key invalid or expired (HTTP %s).", status)
        elif status == 429:
            LOGGER.warning("SerpAPI quota exceeded (HTTP 429).")
        else:
            LOGGER.warning("SerpAPI HTTP error %s: %s", status, exc)
        return []
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("SerpAPI request failed: %s", exc)
        return []

    for row in payload.get("shopping_results", []):
        title = str(row.get("title") or "").strip()
        if not title:
            continue

        name = re.sub(r"\s*[-|]\s*(Amazon\.in|Flipkart|Amazon|India|Buy Online).*$", "", title, flags=re.I).strip()
        row_source = str(row.get("source") or "")
        seller = _seller_from_source(row_source)
        source_url = _best_url(row, seller)

        price = parse_price(row.get("extracted_price") or row.get("price"))
        if price is not None and price < 1:
            continue

        rating = row.get("rating")
        reviews = row.get("reviews")

        item: Dict[str, Any] = {
            "id": f"live-{category}:{_model_identity(name)}",
            "name": name,
            "brand": name.split()[0] if name else None,
            "model": name,
            "category": category,
            "price": price,
            "product_rating": float(rating) if isinstance(rating, (int, float)) else None,
            "review_count": int(reviews) if isinstance(reviews, (int, float)) else None,
            "source": seller or row_source or "Online",
            "source_url": source_url,
            "price_type": "live listing price" if price else "Price unavailable",
            "checked_at": checked_at,
            "image": row.get("thumbnail") or row.get("serpapi_thumbnail"),
            "live": True,
        }
        results.append(item)

    # Deduplicate by identity
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for item in results:
        key = _model_identity(item.get("name", ""))
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    LOGGER.info("search_general('%s', category='%s'): %d results", query, category, len(deduped))
    return deduped


_ACCESSORY_TYPES = [
    {
        "key": "case",
        "query_term": "back cover case",
        "label": "Cases & Covers",
        "icon": "case",
        "reason": "Protects your phone from drops and scratches.",
    },
    {
        "key": "screen_protector",
        "query_term": "tempered glass screen protector",
        "label": "Screen Protectors",
        "icon": "screen_protector",
        "reason": "Guards the display against cracks and fingerprints.",
    },
    {
        "key": "charger",
        "query_term": "fast charger charging cable",
        "label": "Chargers & Cables",
        "icon": "charger",
        "reason": "Fast-charge and cable replacement for daily use.",
    },
    {
        "key": "earphones",
        "query_term": "earphones TWS wireless earbuds",
        "label": "Earphones & Earbuds",
        "icon": "earphones",
        "reason": "Wireless audio companion for calls and music.",
    },
]


def search_accessories(model: str) -> List[Dict[str, Any]]:
    """Search for accessories compatible with a specific mobile model, grouped by type."""
    api_key = _get_api_key()
    if not api_key or not model:
        return []

    checked_at = datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []
    model_lower = model.lower()
    # Extract brand (first word) and meaningful model words (len > 3)
    model_words = [w for w in model_lower.split() if len(w) > 3]

    for acc in _ACCESSORY_TYPES:
        query = f"{model} {acc['query_term']} buy online India"
        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google_shopping",
                    "q": query,
                    "hl": "en",
                    "gl": "in",
                    "api_key": api_key,
                    "num": 6,
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            LOGGER.warning("Accessory search failed for '%s' type=%s: %s", model, acc["key"], exc)
            continue

        count = 0
        for row in payload.get("shopping_results", []):
            if count >= 2:
                break
            title = str(row.get("title") or "").strip()
            if not title:
                continue

            name_lower = title.lower()
            # Compatibility: at least one meaningful model word must appear in the title
            if model_words and not any(w in name_lower for w in model_words):
                continue

            row_source = str(row.get("source") or "")
            seller = _seller_from_source(row_source)
            source_url = _best_url(row, seller)
            price = parse_price(row.get("extracted_price") or row.get("price"))

            if price is not None and price < 1:
                continue

            item: Dict[str, Any] = {
                "name": title,
                "type": acc["label"],
                "type_key": acc["key"],
                "type_icon": acc["icon"],
                "category": "accessory",
                "compatible_model": model,
                "reason": acc["reason"],
                "price": price,
                "source": seller or row_source or "Online",
                "source_url": source_url,
                "price_type": "live listing price" if price else "Price unavailable",
                "checked_at": checked_at,
                "image": row.get("thumbnail"),
                "live": True,
            }
            results.append(item)
            count += 1

    return results
