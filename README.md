# RazorPay Agentic Commerce — v3.1

A voice-first, customer-first product-discovery website with live pricing from multiple sources.

## Architecture

```
Browser (index.html / app.js)
  │
  ├─ Text / Voice query
  ├─ Category detection + query parsing (app.js)
  │
  └─► FastAPI backend (backend/server.py, port 8003)
          │
          ├─ MobilePipeline  → SerpAPI Google Shopping (Amazon + Flipkart)
          ├─ BikePipeline    → BikeWale live web scraping
          ├─ CarPipeline     → CarDekho live web scraping
          └─ GeneralPipeline → SerpAPI Google Shopping (shoes, laptops, etc.)
```

## Supported categories

| What you say | Category | Live source |
|---|---|---|
| "mobile", "phone", "iPhone", "Android" | mobile | SerpAPI → Amazon + Flipkart |
| "bike", "motorcycle", "scooter" | bike | BikeWale (live scraping) |
| "car", "SUV", "sedan" | car | CarDekho (live scraping) |
| "laptop", "notebook" | laptop | SerpAPI Google Shopping |
| "shoes", "sneakers", "footwear" | shoes | SerpAPI Google Shopping |
| "headphones", "earbuds" | headphones | SerpAPI Google Shopping |
| "watch", "smartwatch" | watches | SerpAPI Google Shopping |
| "shirt", "clothing", "jeans" | clothing | SerpAPI Google Shopping |
| "bags", "backpack" | bags | SerpAPI Google Shopping |
| "gaming", "controller" | gaming | SerpAPI Google Shopping |
| "TV", "monitor", "camera" | electronics | SerpAPI Google Shopping |

## Installation

### Requirements

- Python 3.10+
- pip

```powershell
cd Razorpay_3.0_Live
python -m pip install -r backend\requirements.txt
```

## Environment variables

Copy `.env.example` to `.env` (one level **above** `Razorpay_3.0_Live/`, i.e. in the project root):

```powershell
# D:\Razorpay 3.0\.env
SERPAPI_KEY=your_serpapi_key_here
```

The API key is read server-side only. It is never sent to the browser.

Get your SerpAPI key at https://serpapi.com/

## Running

### Option A — Batch file (Windows)

Double-click `Start-on-Windows.bat`. It starts:
1. The FastAPI backend on port 8003
2. A Python HTTP server on port 8000
3. Opens http://127.0.0.1:8000/ in your browser

### Option B — Manual

Terminal 1 — Backend:
```powershell
cd Razorpay_3.0_Live
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8003 --reload
```

Terminal 2 — Frontend:
```powershell
cd Razorpay_3.0_Live
python -m http.server 8000 --bind 127.0.0.1
```

Then open http://127.0.0.1:8000/

## Example queries

### Mobiles
- "mobile under 15000"
- "Samsung phones under 30000"
- "OnePlus phones under 40000"
- "iPhone under 60000"
- "5G phones under 25000"
- "256GB phones under 30000"
- "best camera phone under 30000"

### Bikes
- "bike under 2 lakh"
- "Royal Enfield bikes under 3 lakh"
- "Kawasaki bike under 20 lakh"
- "commuter bike under 1 lakh"

### Cars
- "car under 10 lakh"
- "Tata car under 15 lakh"
- "electric car under 20 lakh"
- "automatic SUV under 20 lakh"

### General
- "Nike running shoes under 5000"
- "gaming laptop under 80000"
- "wireless headphones under 5000"
- "men's running shoes under 4000"

## Live / Demo transparency

Every result is clearly labelled:
- **LIVE** — fetched from a real source (SerpAPI, BikeWale, CarDekho)
- **DEMO** — local demo catalog shown when live search is unavailable

Demo data is never silently presented as live data.

## Price integrity

- Prices ₹2, ₹5, ₹49 are automatically rejected (category-aware minimum prices)
- No invented prices or arbitrary markups
- Amazon and Flipkart prices are compared for the same model
- Prices displayed exactly as returned by the source

## Security

- `SERPAPI_KEY` is only read by the backend — never sent to the browser
- `.env` is in `.gitignore` at both root and project level
- User inputs are validated and length-capped server-side
- CORS is restricted to local development origins

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Server status |
| `GET /api/search` | Product search (see query params below) |
| `GET /api/addons` | Product accessories |

### `/api/search` parameters

| Param | Type | Description |
|---|---|---|
| `category` | string | Required. E.g. mobile, bike, car, laptop, shoes |
| `budget` | float | Maximum price in INR |
| `min_budget` | float | Minimum price in INR |
| `brand` | string | Brand filter |
| `model` | string | Model filter |
| `storage` | int | Storage in GB (mobile) |
| `keywords` | string | Free-text keywords |
| `body_type` | string | Car body type (suv, sedan, etc.) |
| `fuel` | string | Car fuel type |
| `transmission` | string | Car transmission |
| `cc_min`/`cc_max` | float | Bike engine displacement |
| `intent` | string | `best` or `cheapest` |
