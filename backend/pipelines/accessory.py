from __future__ import annotations

import logging
from typing import Any, Dict, List

from .serpapi import search_accessories

LOGGER = logging.getLogger(__name__)

# ── Bike accessories — grouped by type, real-world relevant ──────────────────
_BIKE_ACCESSORIES: List[Dict[str, Any]] = [
    # Safety
    {"name": "Full-Face Helmet (ISI Certified)",    "type": "Safety Gear",    "type_key": "helmet",  "type_icon": "helmet",  "price": 2999,  "reason": "Mandatory safety — full face shields better than half-face.", "source": "Demo", "live": False},
    {"name": "Modular Flip-Up Helmet",               "type": "Safety Gear",    "type_key": "helmet",  "type_icon": "helmet",  "price": 4999,  "reason": "Flip-up visor for convenience at traffic stops.", "source": "Demo", "live": False},
    {"name": "Riding Gloves (Anti-Slip)",            "type": "Safety Gear",    "type_key": "gloves",  "type_icon": "gloves",  "price": 799,   "reason": "Grip + knuckle protection in all weather.", "source": "Demo", "live": False},
    {"name": "Riding Jacket with CE Armour",         "type": "Safety Gear",    "type_key": "jacket",  "type_icon": "jacket",  "price": 3499,  "reason": "CE-rated armour at shoulders, elbows, and back.", "source": "Demo", "live": False},
    {"name": "Riding Boots (Ankle Protection)",      "type": "Safety Gear",    "type_key": "boots",   "type_icon": "boots",   "price": 2499,  "reason": "Ankle and toe protection for impact scenarios.", "source": "Demo", "live": False},
    # Maintenance
    {"name": "Waterproof Bike Cover",                "type": "Maintenance",    "type_key": "cover",   "type_icon": "cover",   "price": 1299,  "reason": "Protects from rain, dust, UV damage when parked.", "source": "Demo", "live": False},
    {"name": "Heavy-Duty Chain Lock",                "type": "Maintenance",    "type_key": "lock",    "type_icon": "lock",    "price": 599,   "reason": "Anti-theft security for urban parking.", "source": "Demo", "live": False},
    {"name": "Portable Tyre Inflator",               "type": "Maintenance",    "type_key": "tools",   "type_icon": "tools",   "price": 1199,  "reason": "Emergency tyre pressure fix anywhere.", "source": "Demo", "live": False},
    # Storage & Comfort
    {"name": "Tail Bag / Saddle Bag (20L)",          "type": "Storage",        "type_key": "bag",     "type_icon": "bag",     "price": 1599,  "reason": "Expandable bag for daily commute and touring.", "source": "Demo", "live": False},
    {"name": "Tank Bag with Phone Mount",            "type": "Storage",        "type_key": "bag",     "type_icon": "bag",     "price": 1299,  "reason": "Quick-access storage + navigation visibility.", "source": "Demo", "live": False},
    # Accessories
    {"name": "Crash Guard / Engine Guard",           "type": "Protection",     "type_key": "guard",   "type_icon": "guard",   "price": 2199,  "reason": "Steel guard absorbs impact in tip-overs.", "source": "Demo", "live": False},
    {"name": "LED Bar End Mirrors",                  "type": "Style & Mods",   "type_key": "mirrors", "type_icon": "mirrors", "price": 699,   "reason": "Better rear visibility + integrated turn signals.", "source": "Demo", "live": False},
    {"name": "Mobile Phone Holder (360° Rotate)",   "type": "Style & Mods",   "type_key": "mount",   "type_icon": "mount",   "price": 399,   "reason": "Navigation-ready mount for any handlebar.", "source": "Demo", "live": False},
    {"name": "Handlebar Grips (Anti-Vibration)",    "type": "Style & Mods",   "type_key": "grips",   "type_icon": "grips",   "price": 349,   "reason": "Reduces fatigue on long rides.", "source": "Demo", "live": False},
]

# ── Car accessories — grouped by type, real-world relevant ───────────────────
_CAR_ACCESSORIES: List[Dict[str, Any]] = [
    # Interior comfort
    {"name": "Custom Fit Seat Covers (Leatherette)", "type": "Interior",       "type_key": "seat",    "type_icon": "seat",    "price": 3499,  "reason": "Protects original upholstery; easy to clean.", "source": "Demo", "live": False},
    {"name": "3D Mat Set (Driver + Co-Driver + Rear)","type": "Interior",      "type_key": "mat",     "type_icon": "mat",     "price": 1799,  "reason": "Waterproof mats trap dirt and water.", "source": "Demo", "live": False},
    {"name": "Steering Wheel Cover (Leather)",       "type": "Interior",       "type_key": "steering","type_icon": "steering","price": 699,   "reason": "Better grip; protects steering from UV.", "source": "Demo", "live": False},
    {"name": "Car Perfume / Air Freshener",          "type": "Interior",       "type_key": "fragrance","type_icon": "fragrance","price": 349,  "reason": "Keeps cabin smelling fresh on every drive.", "source": "Demo", "live": False},
    {"name": "Boot / Trunk Organiser",               "type": "Interior",       "type_key": "organiser","type_icon": "organiser","price": 899,  "reason": "Keeps groceries, tools, and bags sorted.", "source": "Demo", "live": False},
    # Technology
    {"name": "Dash Camera (Front + Rear, 4K)",       "type": "Technology",     "type_key": "camera",  "type_icon": "camera",  "price": 3999,  "reason": "Evidence in accidents; 24h parking mode.", "source": "Demo", "live": False},
    {"name": "Wireless Phone Charger Mount",         "type": "Technology",     "type_key": "mount",   "type_icon": "mount",   "price": 1299,  "reason": "15W fast wireless charging on the dashboard.", "source": "Demo", "live": False},
    {"name": "OBD2 Bluetooth Diagnostic Scanner",    "type": "Technology",     "type_key": "tools",   "type_icon": "tools",   "price": 899,   "reason": "Real-time engine health and mileage on your phone.", "source": "Demo", "live": False},
    {"name": "Rear Parking Camera (HD)",             "type": "Technology",     "type_key": "camera",  "type_icon": "camera",  "price": 1499,  "reason": "Wide-angle reversing camera eliminates blind spots.", "source": "Demo", "live": False},
    # Protection
    {"name": "Waterproof Car Body Cover",            "type": "Protection",     "type_key": "cover",   "type_icon": "cover",   "price": 2499,  "reason": "Full body cover against rain, hail, bird drops.", "source": "Demo", "live": False},
    {"name": "Windshield Sun Shade (Foldable)",      "type": "Protection",     "type_key": "sunshade","type_icon": "sunshade","price": 599,   "reason": "Reduces cabin temp by up to 20°C in summer.", "source": "Demo", "live": False},
    {"name": "Tyre Pressure Monitoring System (TPMS)","type": "Protection",    "type_key": "tpms",    "type_icon": "tools",   "price": 1999,  "reason": "Real-time tyre pressure alerts prevent blowouts.", "source": "Demo", "live": False},
    # Emergency
    {"name": "Jump Starter + Power Bank (12000mAh)","type": "Emergency Kit",   "type_key": "emergency","type_icon": "emergency","price": 2999, "reason": "Start a dead battery and charge devices on the road.", "source": "Demo", "live": False},
    {"name": "Portable Tyre Inflator (12V)",         "type": "Emergency Kit",  "type_key": "tools",   "type_icon": "tools",   "price": 1299,  "reason": "Inflate a flat tyre without a mechanic.", "source": "Demo", "live": False},
]

# ── Mobile fallback (when live SerpAPI search fails) ─────────────────────────
_MOBILE_FALLBACK: List[Dict[str, Any]] = [
    {"name": "Back Cover & Case",                    "type": "Cases & Covers",       "type_key": "case",             "type_icon": "case",             "price": None, "reason": "Protect from drops and scratches.",  "source": "Suggestion", "live": False},
    {"name": "Tempered Glass Screen Protector",      "type": "Screen Protectors",    "type_key": "screen_protector", "type_icon": "screen_protector", "price": None, "reason": "Guards the display against cracks.", "source": "Suggestion", "live": False},
    {"name": "Fast Charger & USB-C Cable",           "type": "Chargers & Cables",    "type_key": "charger",          "type_icon": "charger",          "price": None, "reason": "Keep your phone powered up fast.",  "source": "Suggestion", "live": False},
    {"name": "Wireless Earbuds / TWS",               "type": "Earphones & Earbuds",  "type_key": "earphones",        "type_icon": "earphones",        "price": None, "reason": "Best wireless audio companion.",    "source": "Suggestion", "live": False},
]


def _tag_model(items: List[Dict[str, Any]], model: str) -> List[Dict[str, Any]]:
    """Attach the product model name to each accessory item so JS can display it."""
    tagged = []
    for item in items:
        entry = dict(item)
        entry["compatible_model"] = model
        tagged.append(entry)
    return tagged


def get_addons(category: str, context: Any = None) -> List[Dict[str, Any]]:
    model = context.get("model") if isinstance(context, dict) else context
    model = (model or "").strip()

    if category == "mobile":
        if model:
            try:
                live = search_accessories(model)
                if live:
                    return live
            except Exception as exc:
                LOGGER.warning("Accessory live search failed for model=%r: %s", model, exc)
        # Fallback: generic suggestions with model name attached
        if model:
            return _tag_model(_MOBILE_FALLBACK, model)
        return list(_MOBILE_FALLBACK)

    if category == "bike":
        return _tag_model(_BIKE_ACCESSORIES, model or "your bike")

    if category == "car":
        return _tag_model(_CAR_ACCESSORIES, model or "your car")

    return []
