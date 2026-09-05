from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import BasePipeline, PipelineResult
from .serpapi import search_general
from .validation import dedupe_products, normalize_text, parse_price

LOGGER = logging.getLogger(__name__)
MAX_RESULTS = 12

MIN_PRICE: Dict[str, int] = {
    "shoes": 200,
    "clothing": 100,
    "laptop": 10000,
    "headphones": 200,
    "electronics": 100,
    "gaming": 500,
    "watches": 300,
    "bags": 200,
    "default": 50,
}


def _build_query(query: Dict[str, Any]) -> str:
    parts: List[str] = []
    brand = (query.get("brand") or "").strip()
    model = (query.get("model") or "").strip()
    keywords = (query.get("keywords") or "").strip()
    category = (query.get("category") or "").strip()
    budget = query.get("budget")
    min_budget = query.get("min_budget")

    if brand:
        parts.append(brand)
    if model and model.lower() != brand.lower():
        parts.append(model)
    if keywords:
        parts.append(keywords)
    if category and category not in ("general", "product", "other"):
        parts.append(category)

    parts.append("buy online India")

    if min_budget and budget:
        parts.append(f"₹{int(min_budget)}-₹{int(budget)}")
    elif budget:
        parts.append(f"under ₹{int(budget)}")

    return " ".join(parts)


def _compute_score(item: Dict[str, Any], query: Dict[str, Any]) -> tuple:
    score = 30
    reasons: List[str] = []
    warnings: List[str] = []

    budget = query.get("budget")
    brand_q = normalize_text(query.get("brand") or "")
    keywords_q = normalize_text(query.get("keywords") or "")
    price = item.get("price")
    rating = item.get("product_rating")
    reviews = item.get("review_count") or 0
    name_lower = normalize_text(item.get("name") or "")

    if price is not None and price > 0:
        score += 10
        reasons.append("Price verified")

    if price and budget:
        pct = price / budget
        if pct <= 1.0:
            if pct >= 0.75:
                score += 18
                reasons.append(f"Uses {int(pct*100)}% of budget")
            elif pct >= 0.5:
                score += 10
                reasons.append(f"Uses {int(pct*100)}% of budget")
            else:
                score += 4

    if brand_q:
        if brand_q in name_lower:
            score += 15
            reasons.append(f"Matches brand: {brand_q.title()}")
        else:
            warnings.append("Brand does not match")

    if keywords_q:
        matched = sum(1 for t in keywords_q.split() if t in name_lower and len(t) > 3)
        if matched >= 2:
            score += 10
            reasons.append("Closely matches your requirements")
        elif matched == 1:
            score += 5

    if rating is not None:
        if rating >= 4.5:
            score += 12
            reasons.append(f"Highly rated: ⭐ {rating}")
        elif rating >= 4.0:
            score += 8
            reasons.append(f"Well rated: ⭐ {rating}")

    if reviews >= 500:
        score += 8
        reasons.append(f"{reviews:,} verified reviews")
    elif reviews >= 50:
        score += 4

    score = max(0, min(100, score))
    return score, reasons[:4], warnings


class GeneralPipeline(BasePipeline):
    category = "general"

    def search(self, catalog: List[Dict[str, Any]], query: Dict[str, Any]) -> PipelineResult:
        budget: float | None = query.get("budget")
        min_budget: float | None = query.get("min_budget")
        brand: str = normalize_text(query.get("brand") or "")
        keywords: str = normalize_text(query.get("keywords") or "")
        cat_name: str = query.get("category") or "product"

        serpapi_query = _build_query(query)
        LOGGER.info("GeneralPipeline('%s'): query = %r", cat_name, serpapi_query)

        raw = search_general(serpapi_query, category=cat_name)

        min_valid = MIN_PRICE.get(cat_name.lower(), MIN_PRICE["default"])

        def matches(item: Dict[str, Any]) -> bool:
            text = normalize_text(item.get("name") or "")
            if brand and brand not in text:
                return False
            if keywords:
                stop = {"buy", "online", "india", "best", "shop", "price"}
                if any(token not in text for token in keywords.split() if token not in stop):
                    return False
            price = item.get("price")
            if price is not None and price < min_valid:
                return False
            if min_budget is not None and (price is None or price < min_budget):
                return False
            if budget is not None and (price is None or price > budget):
                return False
            return True

        valid: List[Dict[str, Any]] = []
        for item in raw:
            item["price"] = parse_price(item.get("price"))
            if not matches(item):
                continue
            score, reasons, warnings = _compute_score(item, query)
            item["match_score"] = score
            item["match_reasons"] = reasons
            item["match_warnings"] = warnings
            item["why"] = "; ".join(reasons) if reasons else f"Matches your {cat_name} search."
            item["trust_status"] = "verified" if item.get("live") else "demo"
            valid.append(item)

        deduped = dedupe_products(valid)
        deduped.sort(key=lambda x: (-(x.get("match_score") or 0), x.get("price") or float("inf")))

        if not raw:
            note = f"⚠ Live product search is currently unavailable for '{cat_name}'."
        elif not deduped:
            note = f"Live search returned results but none passed your filters for '{cat_name}'."
        else:
            note = f"Live shopping results for '{cat_name}' — ranked by AI match score. {len(deduped)} matching product(s)."
            if budget:
                note += f" All results are within your ₹{int(budget):,} budget."

        return PipelineResult(deduped[:MAX_RESULTS], None, note)
