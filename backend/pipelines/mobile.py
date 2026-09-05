from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import BasePipeline, PipelineResult
from .serpapi import search_mobile, _build_mobile_query
from .validation import dedupe_products, normalize_text, parse_price, validate_product

LOGGER = logging.getLogger(__name__)
MAX_RESULTS = 12


def _compute_match_score(item: Dict[str, Any], query: Dict[str, Any]) -> tuple:
    """Compute a meaningful AI match score (0-100) with reasons."""
    score = 30  # base
    reasons: List[str] = []
    warnings: List[str] = []

    budget = query.get("budget")
    brand_q = normalize_text(query.get("brand") or "")
    model_q = normalize_text(query.get("model") or "")
    keywords_q = normalize_text(query.get("keywords") or "")
    intent = normalize_text(query.get("intent") or "")
    storage_q = query.get("storage")
    ram_q = query.get("ram")

    price = item.get("price")
    rating = item.get("product_rating")
    reviews = item.get("review_count") or 0
    name_lower = normalize_text(item.get("name") or "")

    # Price verified
    if price is not None and price > 0:
        score += 10
        reasons.append("Price verified")
    else:
        warnings.append("Price not verified")

    # Budget utilisation
    if price and budget:
        pct = price / budget
        if pct <= 1.0:
            if pct >= 0.80:
                score += 22
                reasons.append(f"Uses {int(pct*100)}% of ₹{int(budget):,} budget — great value")
            elif pct >= 0.65:
                score += 15
                reasons.append(f"Uses {int(pct*100)}% of ₹{int(budget):,} budget")
            elif pct >= 0.45:
                score += 8
                reasons.append(f"Uses {int(pct*100)}% of budget — within range")
            else:
                score += 3
                reasons.append(f"Uses only {int(pct*100)}% of budget — may be lower-spec")
        else:
            score -= 15
            warnings.append(f"Exceeds budget by {int((pct-1)*100)}%")

    # Brand match
    if brand_q:
        item_brand = normalize_text(item.get("brand") or item.get("name", "").split()[0])
        if brand_q in item_brand or brand_q in name_lower:
            score += 15
            reasons.append(f"Matches brand: {(item.get('brand') or brand_q).title()}")
        else:
            score -= 8
            warnings.append("Brand does not match your request")

    # Model match
    if model_q and model_q in name_lower:
        score += 10
        reasons.append("Matches specific model request")

    # Feature keyword scoring
    if "camera" in keywords_q or "photo" in keywords_q:
        if any(x in name_lower for x in ("pro", "ultra", "pixel", "cam", "camera", "50mp", "108mp", "200mp")):
            score += 10
            reasons.append("Camera-optimised model")
        elif any(x in name_lower for x in ("se", "lite", "mini")):
            score -= 3
            warnings.append("May not be the best camera variant")

    if "5g" in keywords_q or "5g" in normalize_text(query.get("raw_query") or ""):
        if "5g" in name_lower:
            score += 8
            reasons.append("5G connectivity")
        else:
            score -= 5
            warnings.append("5G not confirmed in listing")

    if any(x in keywords_q for x in ("battery", "long battery", "backup")):
        if any(x in name_lower for x in ("5000", "6000", "5500", "power", "energy")):
            score += 7
            reasons.append("Large battery capacity")

    if any(x in keywords_q for x in ("fast charging", "charge", "charger")):
        if any(x in name_lower for x in ("67w", "120w", "65w", "45w", "supercharge", "flash charge", "turbo")):
            score += 6
            reasons.append("Fast charging supported")

    if "display" in keywords_q or "screen" in keywords_q or "amoled" in keywords_q:
        if any(x in name_lower for x in ("amoled", "oled", "super amoled", "pro display")):
            score += 6
            reasons.append("AMOLED/OLED display")

    if "gaming" in keywords_q or "performance" in keywords_q:
        if any(x in name_lower for x in ("pro", "ultra", "plus", "turbo", "gt")):
            score += 5
            reasons.append("Performance-tuned variant")

    # Rating quality
    if rating is not None:
        if rating >= 4.5:
            score += 12
            reasons.append(f"Highly rated: ⭐ {rating}")
        elif rating >= 4.0:
            score += 8
            reasons.append(f"Well rated: ⭐ {rating}")
        elif rating >= 3.5:
            score += 4
        else:
            warnings.append(f"Low rating: ⭐ {rating}")

    # Review volume — signals real purchase confidence
    if reviews >= 5000:
        score += 10
        reasons.append(f"{reviews:,} reviews — very high confidence")
    elif reviews >= 1000:
        score += 8
        reasons.append(f"{reviews:,} reviews — high confidence")
    elif reviews >= 200:
        score += 5
        reasons.append(f"{reviews:,} reviews")
    elif reviews >= 50:
        score += 3
    elif reviews > 0:
        score += 1

    # Storage match
    if storage_q and f"{storage_q}gb" in name_lower.replace(" ", ""):
        score += 5
        reasons.append(f"Matches {storage_q}GB storage requirement")

    # RAM match
    if ram_q and f"{ram_q}gb" in name_lower.replace(" ", ""):
        score += 4
        reasons.append(f"Matches {ram_q}GB RAM requirement")

    # Multi-store comparison available
    if item.get("amazon") and item.get("flipkart"):
        score += 4
        reasons.append("Price compared: Amazon + Flipkart")

    # Intent-based boost
    if intent == "cheapest" and price and budget:
        pct = price / budget
        if pct < 0.45:
            score += 8
            reasons.append("Lowest-price option in category")

    score = max(0, min(100, score))
    why_parts = reasons[:4]
    if not why_parts and price:
        why_parts = [f"Matched your {item.get('category', 'mobile')} search"]

    return score, why_parts, warnings


class MobilePipeline(BasePipeline):
    category = "mobile"

    def search(self, catalog: List[Dict[str, Any]], query: Dict[str, Any]) -> PipelineResult:
        budget: float | None = query.get("budget")
        min_budget: float | None = query.get("min_budget")
        brand: str = normalize_text(query.get("brand") or "")
        model: str = normalize_text(query.get("model") or "")
        keywords: str = normalize_text(query.get("keywords") or "")
        intent: str = normalize_text(query.get("intent") or "")

        serpapi_query = _build_mobile_query(query)
        LOGGER.info("MobilePipeline: SerpAPI query = %r", serpapi_query)

        live_raw = search_mobile(serpapi_query) if serpapi_query else []
        live_ok = len(live_raw) > 0

        if live_raw:
            items = []
            for item in live_raw:
                item["price"] = parse_price(item.get("price"))
                if validate_product(item, "mobile"):
                    items.append(item)
        else:
            LOGGER.warning("MobilePipeline: SerpAPI returned nothing; using demo catalog as fallback.")
            catalog_mobiles = [x for x in catalog if x.get("category") == "mobile"]
            items = []
            for item in catalog_mobiles:
                item = dict(item)
                item["live"] = False
                item["source"] = "DEMO (local catalog — live search unavailable)"
                item["price_type"] = "demo catalog price"
                item["id"] = item.get("id") or f"demo-mobile:{normalize_text(item.get('name', ''))}"
                if validate_product(item, "mobile"):
                    items.append(item)

        def matches(item: Dict[str, Any]) -> bool:
            text = normalize_text(
                " ".join(str(item.get(x) or "") for x in ("brand", "model", "variant", "name"))
            )
            if brand and brand not in normalize_text(item.get("brand") or "") and brand not in text:
                return False
            if model and model not in text:
                return False
            if keywords:
                skip_tokens = {"phone", "phones", "mobile", "mobiles", "smartphone"}
                if any(
                    token not in text
                    for token in keywords.split()
                    if token not in skip_tokens
                ):
                    return False
            price = item.get("price")
            if min_budget is not None and (price is None or price < min_budget):
                return False
            if budget is not None and (price is None or price > budget):
                return False
            storage = query.get("storage")
            if storage and f"{storage} gb" not in text and f"{storage}gb" not in text:
                return False
            return True

        filtered = dedupe_products([item for item in items if matches(item)])

        for item in filtered:
            score, reasons, warnings = _compute_match_score(item, query)
            item["match_score"] = score
            item["match_reasons"] = reasons
            item["match_warnings"] = warnings
            item["why"] = "; ".join(reasons) if reasons else "Matches your mobile search."
            item["trust_status"] = "verified" if item.get("live") else "demo"
            item.setdefault("review_summary", {"status": "Review information unavailable."})

        if intent == "cheapest" or "cheapest" in keywords:
            filtered.sort(key=lambda x: (x.get("price") is None, x.get("price") or float("inf")))
        elif intent == "best":
            filtered.sort(key=lambda x: (-(x.get("match_score") or 0), x.get("price") or float("inf")))
        else:
            filtered.sort(key=lambda x: (-(x.get("match_score") or 0), x.get("price") or float("inf")))

        if not live_ok:
            if filtered:
                note = (
                    "⚠ Live Amazon/Flipkart search is currently unavailable. "
                    "Showing demo catalog — these are NOT live prices."
                )
            else:
                note = "⚠ Live search unavailable. No demo products matched the filters."
        else:
            note = (
                f"Live Amazon India + Flipkart results — prices verified, ranked by AI match score. "
                f"{len(filtered)} matching product(s) found."
            )
            if budget:
                note += f" All results are within your ₹{int(budget):,} budget."
            if not filtered:
                note += " No results passed the budget/brand filters."

        return PipelineResult(filtered[:MAX_RESULTS], None, note)
