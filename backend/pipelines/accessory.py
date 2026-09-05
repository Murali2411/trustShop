from __future__ import annotations

import logging
from typing import Any, Dict, List

from .serpapi import search_accessories

LOGGER = logging.getLogger(__name__)

# Static fallback accessories for bike/car (no live search needed — generic items)
_STATIC_ACCESSORIES: Dict[str, List[Dict[str, Any]]] = {
    "bike": [
        {"name": "Helmet (Full-face)", "type": "Helmets", "type_key": "helmet", "type_icon": "helmet", "price": 2999, "reason": "Essential safety gear.", "source": "Demo", "live": False},
        {"name": "Bike Cover", "type": "Covers", "type_key": "cover", "type_icon": "cover", "price": 1299, "reason": "Protects the motorcycle when parked.", "source": "Demo", "live": False},
        {"name": "Riding Gloves", "type": "Gloves", "type_key": "gloves", "type_icon": "gloves", "price": 799, "reason": "Grip and protection while riding.", "source": "Demo", "live": False},
    ],
    "car": [
        {"name": "Car Cover", "type": "Covers", "type_key": "cover", "type_icon": "cover", "price": 2499, "reason": "Protects the car from dust and rain.", "source": "Demo", "live": False},
        {"name": "Dash Camera", "type": "Cameras", "type_key": "camera", "type_icon": "camera", "price": 3999, "reason": "Records driving footage for safety.", "source": "Demo", "live": False},
        {"name": "Car Organiser", "type": "Organisers", "type_key": "organiser", "type_icon": "organiser", "price": 699, "reason": "Keeps the interior tidy.", "source": "Demo", "live": False},
    ],
}

# Generic mobile accessory suggestions shown when live search is unavailable
_MOBILE_FALLBACK: List[Dict[str, Any]] = [
    {"name": "Back Cover & Case", "type": "Cases & Covers", "type_key": "case", "type_icon": "case", "price": None, "reason": "Protect from drops and scratches.", "source": "Suggestion", "live": False},
    {"name": "Tempered Glass Screen Protector", "type": "Screen Protectors", "type_key": "screen_protector", "type_icon": "screen_protector", "price": None, "reason": "Guards the display against cracks.", "source": "Suggestion", "live": False},
    {"name": "Fast Charger & USB-C Cable", "type": "Chargers & Cables", "type_key": "charger", "type_icon": "charger", "price": None, "reason": "Keep your phone powered up fast.", "source": "Suggestion", "live": False},
    {"name": "Wireless Earbuds / TWS", "type": "Earphones & Earbuds", "type_key": "earphones", "type_icon": "earphones", "price": None, "reason": "Best wireless audio companion.", "source": "Suggestion", "live": False},
]


def get_addons(category: str, context: Any = None) -> List[Dict[str, Any]]:
    if category == "mobile":
        model = context.get("model") if isinstance(context, dict) else context
        if model:
            try:
                live = search_accessories(model)
                if live:
                    return live
            except Exception as exc:
                LOGGER.warning("Accessory live search failed for model=%r: %s", model, exc)
        # Fallback: show generic accessory suggestions so the cart is never empty
        if model:
            fallback = []
            for item in _MOBILE_FALLBACK:
                entry = dict(item)
                entry["compatible_model"] = model
                fallback.append(entry)
            return fallback
        return []

    return _STATIC_ACCESSORIES.get(category, [])
