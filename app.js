(() => {
"use strict";

const API = "http://127.0.0.1:8003";

// ── Helpers ───────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const money = (n) => {
  const num = Number(n);
  if (!isFinite(num) || num <= 0) return "Price unavailable";
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR", maximumFractionDigits: 0
  }).format(num);
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));

function storageGet(key, def) {
  try { return JSON.parse(localStorage.getItem(key) ?? JSON.stringify(def)); }
  catch (_) { return def; }
}
function storageSet(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
}

// ── Static fallback accessories (shown instantly; replaced by live API data) ──
const STATIC_MOBILE_ACCS = [
  { type:"Cases & Covers",     type_key:"case",             type_icon:"case",             name:"Back Cover & Case",                price:null, reason:"Protects your phone from drops and scratches.",       live:false, source:"Suggestion" },
  { type:"Screen Protectors",  type_key:"screen_protector", type_icon:"screen_protector", name:"Tempered Glass Screen Protector",  price:null, reason:"Guards the display against cracks and fingerprints.", live:false, source:"Suggestion" },
  { type:"Chargers & Cables",  type_key:"charger",          type_icon:"charger",          name:"Fast Charger & USB-C Cable",       price:null, reason:"Keep your phone powered up quickly.",                 live:false, source:"Suggestion" },
  { type:"Earphones & Earbuds",type_key:"earphones",        type_icon:"earphones",        name:"Wireless Earbuds / TWS",           price:null, reason:"Wireless audio companion for calls and music.",        live:false, source:"Suggestion" },
];
const STATIC_BIKE_ACCS = [
  { type:"Safety Gear",  type_key:"helmet",  type_icon:"helmet", name:"Full-Face Helmet (ISI Certified)",  price:2999, reason:"Mandatory safety — full face shields better.", live:false, source:"Demo" },
  { type:"Safety Gear",  type_key:"gloves",  type_icon:"gloves", name:"Riding Gloves (Anti-Slip)",         price:799,  reason:"Grip + knuckle protection in all weather.",   live:false, source:"Demo" },
  { type:"Safety Gear",  type_key:"jacket",  type_icon:"jacket", name:"Riding Jacket with CE Armour",      price:3499, reason:"CE-rated armour at shoulders, elbows, back.", live:false, source:"Demo" },
  { type:"Maintenance",  type_key:"cover",   type_icon:"cover",  name:"Waterproof Bike Cover",             price:1299, reason:"Protects from rain, dust, UV when parked.",   live:false, source:"Demo" },
  { type:"Maintenance",  type_key:"lock",    type_icon:"lock",   name:"Heavy-Duty Chain Lock",             price:599,  reason:"Anti-theft security for urban parking.",      live:false, source:"Demo" },
  { type:"Storage",      type_key:"bag",     type_icon:"bag",    name:"Saddle Bag / Tail Bag (20L)",       price:1599, reason:"Expandable bag for commute and touring.",     live:false, source:"Demo" },
  { type:"Style & Mods", type_key:"mount",   type_icon:"mount",  name:"Phone Holder (360° Rotate)",        price:399,  reason:"Navigation-ready mount for any handlebar.",   live:false, source:"Demo" },
  { type:"Protection",   type_key:"guard",   type_icon:"guard",  name:"Crash Guard / Engine Guard",        price:2199, reason:"Steel guard absorbs impact in tip-overs.",    live:false, source:"Demo" },
];
const STATIC_CAR_ACCS = [
  { type:"Interior",      type_key:"seat",      type_icon:"seat",      name:"Leatherette Seat Covers (Custom Fit)", price:3499, reason:"Protects original upholstery; easy to clean.", live:false, source:"Demo" },
  { type:"Interior",      type_key:"mat",       type_icon:"mat",       name:"3D Mat Set (Full Set)",                price:1799, reason:"Waterproof mats trap dirt and water.",         live:false, source:"Demo" },
  { type:"Technology",    type_key:"camera",    type_icon:"camera",    name:"Dash Camera (Front + Rear, 4K)",       price:3999, reason:"Evidence in accidents; 24h parking mode.",     live:false, source:"Demo" },
  { type:"Technology",    type_key:"mount",     type_icon:"mount",     name:"Wireless Phone Charger Mount (15W)",   price:1299, reason:"Fast wireless charging on the dashboard.",     live:false, source:"Demo" },
  { type:"Protection",    type_key:"cover",     type_icon:"cover",     name:"Waterproof Car Body Cover",            price:2499, reason:"Full body cover against rain, hail, dust.",    live:false, source:"Demo" },
  { type:"Protection",    type_key:"sunshade",  type_icon:"sunshade",  name:"Windshield Sun Shade (Foldable)",      price:599,  reason:"Reduces cabin temp by up to 20°C in summer.",  live:false, source:"Demo" },
  { type:"Interior",      type_key:"steering",  type_icon:"steering",  name:"Steering Wheel Cover (Leather)",       price:699,  reason:"Better grip; protects steering from UV.",      live:false, source:"Demo" },
  { type:"Emergency Kit", type_key:"emergency", type_icon:"emergency", name:"Jump Starter + Power Bank (12000mAh)",price:2999, reason:"Start a dead battery anywhere on the road.",   live:false, source:"Demo" },
];

// ── State ─────────────────────────────────────────────────────────────────────
let lastResults = [];
let currentSearch = null;          // { category, query (raw text), params }
let sessionContext = null;         // conversational context — refined across queries
const mobileRecommendations = {};
const vehicleRecommendations = {};
const recommendationLoads = {};
let listening = false;
let recognition = null;
let razorpayKeyId = null;          // loaded from backend health endpoint

// ── History ───────────────────────────────────────────────────────────────────
function saveHistory(query, category, count, isLive) {
  const old = storageGet("rz_history", []);
  const item = {
    q: query, category, count,
    live: isLive,
    date: new Date().toLocaleString("en-IN"),
  };
  const filtered = old.filter(x => String(x.q).toLowerCase() !== query.toLowerCase());
  storageSet("rz_history", [item, ...filtered].slice(0, 10));
  showHistory();
}

function showHistory() {
  const h = storageGet("rz_history", []);
  $("history").innerHTML = h.length
    ? h.map((x, i) => `
      <button class="hist" type="button" data-history-index="${i}">
        <b>${esc(x.q)}</b>
        <span>${esc(x.category)} • ${x.count} result(s) • ${x.live ? "LIVE" : "DEMO"} • ${esc(x.date)}</span>
      </button>`).join("")
    : '<p class="muted">No previous searches yet.</p>';

  document.querySelectorAll("[data-history-index]").forEach(btn => {
    btn.addEventListener("click", () => {
      const item = storageGet("rz_history", [])[Number(btn.dataset.historyIndex)];
      if (!item) return;
      $("input").value = item.q;
      $("input").focus();
    });
  });
}

function clearHistory() {
  try { localStorage.removeItem("rz_history"); } catch (_) {}
  showHistory();
}

// ── Price Watch ───────────────────────────────────────────────────────────────
function getWatchlist() {
  const w = storageGet("rz_watchlist", []);
  return Array.isArray(w) ? w : [];
}

function addToWatchlist(product, targetPrice) {
  const list = getWatchlist();
  const id = product.id || product.name;
  if (list.find(x => x.id === id)) {
    setAssistant(`Already watching ${product.name}.`);
    return;
  }
  list.push({
    id,
    name: product.name,
    currentPrice: product.price,
    targetPrice: targetPrice || (product.price ? Math.round(product.price * 0.9) : null),
    category: product.category,
    source: product.source,
    source_url: product.source_url || product.amazon?.url || product.flipkart?.url,
    addedAt: new Date().toISOString(),
  });
  storageSet("rz_watchlist", list.slice(0, 20));
  renderWatchlist();
  setAssistant(`Watching ${product.name} for price drops.`);
}

function removeFromWatchlist(id) {
  const list = getWatchlist().filter(x => x.id !== id);
  storageSet("rz_watchlist", list);
  renderWatchlist();
}

function renderWatchlist() {
  const list = getWatchlist();
  const panel = $("watchlistPanel");
  const el = $("watchlist");
  if (!panel || !el) return;
  if (!list.length) { panel.style.display = "none"; return; }
  panel.style.display = "";
  el.innerHTML = list.map(w => `
    <div class="watch-row">
      <div class="watch-info">
        <b>${esc(w.name)}</b>
        <span class="muted">Current: ${money(w.currentPrice)} • Target: ${w.targetPrice ? money(w.targetPrice) : "any drop"}</span>
        ${w.source_url ? `<a href="${esc(w.source_url)}" target="_blank" rel="noopener noreferrer" class="action-link">View ↗</a>` : ""}
      </div>
      <button type="button" class="secondary small" data-unwatch="${esc(w.id)}">Remove</button>
    </div>`).join("");

  el.querySelectorAll("[data-unwatch]").forEach(b =>
    b.addEventListener("click", () => removeFromWatchlist(b.dataset.unwatch))
  );
}

// ── Category detection ────────────────────────────────────────────────────────
function categoryFrom(text) {
  const t = text.toLowerCase();
  if (/\b(bike|bikes|motorcycle|motorbike|scooter|two[-\s]?wheel)\b/.test(t)) return "bike";
  // CC without explicit "bike" → almost always a bike query
  if (/\b\d{2,4}\s*cc\b/.test(t) && !/\b(car|suv|sedan|hatchback)\b/.test(t)) return "bike";
  if (/\b(car|cars|suv|sedan|hatchback|muv|coupe|vehicle|automobile)\b/.test(t)) return "car";
  // Litre/L engine displacement without bike context → car
  if (/\b\d+\.\d+\s*(?:litre|liter|l)\s*(?:engine|diesel|petrol)/i.test(t)) return "car";
  if (/\b(mobile|phone|phones|smartphone|iphone|android|handset)\b/.test(t)) return "mobile";
  if (/\b(laptop|laptops|notebook)\b/.test(t)) return "laptop";
  if (/\b(shoes?|sneakers?|footwear|sandals?|trainers?|running shoes?)\b/.test(t)) return "shoes";
  if (/\b(headphones?|earphones?|earbuds?|tws|wireless earbuds?)\b/.test(t)) return "headphones";
  if (/\b(watch|watches|smartwatch)\b/.test(t)) return "watches";
  if (/\b(shirt|tshirt|t-shirt|jeans|clothing|clothes|dress|kurta)\b/.test(t)) return "clothing";
  if (/\b(bag|bags|backpack|sling bag|handbag)\b/.test(t)) return "bags";
  if (/\b(gaming|game|controller|console|playstation|xbox)\b/.test(t)) return "gaming";
  if (/\b(tv|television|monitor|tablet|camera|speaker)\b/.test(t)) return "electronics";
  return null;
}

// ── Cubic capacity parsing ────────────────────────────────────────────────────
function parseCubicCapacity(text) {
  const t = text.toLowerCase().replace(/,/g, "");
  const result = {};

  // Exact range: "150-300cc", "150 to 300 cc", "between 150 and 300cc"
  const rangeM = t.match(/(\d{2,4})\s*(?:cc)?\s*(?:-|to|and)\s*(\d{2,4})\s*cc/i);
  if (rangeM) {
    result.cc_min = Number(rangeM[1]);
    result.cc_max = Number(rangeM[2]);
    result.target_cc = Math.round((result.cc_min + result.cc_max) / 2);
    return result;
  }

  // "above/over/more than Xcc"
  const aboveM = t.match(/(?:above|over|more than|at least|minimum)\s*(\d{2,4})\s*cc/i);
  if (aboveM) {
    result.cc_min = Number(aboveM[1]);
    result.target_cc = result.cc_min;
    return result;
  }

  // "under/below/less than Xcc"
  const belowM = t.match(/(?:under|below|less than|upto|up to|max)\s*(\d{2,4})\s*cc/i);
  if (belowM) {
    result.cc_max = Number(belowM[1]);
    result.target_cc = result.cc_max;
    return result;
  }

  // "around/approximately Xcc" — ±15%
  const aroundM = t.match(/(?:around|about|approx(?:imately)?|near)\s*(\d{2,4})\s*cc/i);
  if (aroundM) {
    const n = Number(aroundM[1]);
    result.target_cc = n;
    result.cc_min = Math.round(n * 0.85);
    result.cc_max = Math.round(n * 1.15);
    return result;
  }

  // Plain "Xcc" — ±20cc tolerance
  const plainM = t.match(/\b(\d{2,4})\s*cc\b/i);
  if (plainM) {
    const n = Number(plainM[1]);
    result.target_cc = n;
    result.cc_min = Math.max(0, n - 25);
    result.cc_max = n + 25;
    return result;
  }

  // Car litre displacement: "1.5 litre", "2.0L diesel"
  const litreM = t.match(/(\d+(?:\.\d+)?)\s*(?:litre|liter|l)\b/i);
  if (litreM) {
    const lv = Number(litreM[1]);
    if (lv > 0.4 && lv < 6.5) {
      const n = Math.round(lv * 1000);
      result.target_cc = n;
      result.cc_min = Math.round(n * 0.9);
      result.cc_max = Math.round(n * 1.1);
    }
  }

  return Object.keys(result).length ? result : null;
}

// ── Query parsing ─────────────────────────────────────────────────────────────
function parseBudget(text) {
  const t = text.toLowerCase().replace(/,/g, "");
  const maximum = t.match(/(?:under|below|upto|up to|less than|max(?:imum)?(?:\s+price)?)[^\d]*(\d+(?:\.\d+)?)\s*(lakh|lac|lakhs|k)?\b/i);
  const any = t.match(/(\d+(?:\.\d+)?)\s*(lakh|lac|lakhs|k)?\b/);
  const m = maximum || any;
  if (!m) return null;
  let n = Number(m[1] || m[1]);
  const unit = (m[2] || "").toLowerCase();
  if (["lakh", "lakhs", "lac"].includes(unit)) n *= 100000;
  if (unit === "k") n *= 1000;
  return Math.round(n) || null;
}

function parseMinBudget(text) {
  const t = text.toLowerCase().replace(/,/g, "");
  const m = t.match(/(?:above|over|from|at least|starting from|minimum)[^\d]*(\d+(?:\.\d+)?)\s*(lakh|lac|lakhs|k)?\b/i);
  if (!m) return null;
  let n = Number(m[1]);
  const unit = (m[2] || "").toLowerCase();
  if (["lakh", "lakhs", "lac"].includes(unit)) n *= 100000;
  if (unit === "k") n *= 1000;
  return Math.round(n) || null;
}

function parseBrand(text) {
  const brands = [
    "kawasaki", "triumph", "royal enfield", "ducati", "bmw", "yamaha", "honda",
    "ktm", "bajaj", "hero", "suzuki", "tvs", "aprilia", "benelli",
    "tata", "maruti", "hyundai", "mahindra", "kia", "toyota", "volkswagen",
    "skoda", "mg", "jeep", "byd", "renault", "nissan", "ford",
    "samsung", "oneplus", "motorola", "apple", "iphone", "xiaomi", "redmi",
    "realme", "vivo", "oppo", "google", "pixel", "nothing", "iqoo",
    "infinix", "tecno", "lava", "micromax",
    "nike", "adidas", "puma", "reebok", "skechers", "asics", "new balance",
    "lenovo", "dell", "hp", "asus", "acer", "msi",
    "sony", "jbl", "bose", "boat", "noise", "skullcandy",
    "titan", "casio", "fossil", "seiko",
  ];
  const t = text.toLowerCase();
  return brands.find(x => t.includes(x)) || null;
}

function parseQuery(text, category) {
  const q = {};
  const normalized = text.toLowerCase().replace(/,/g, "");

  const range = normalized.match(
    /(?:between|from)\s*(\d+(?:\.\d+)?)\s*(lakh|lac|lakhs|k)?\s*(?:and|to|-)\s*(\d+(?:\.\d+)?)\s*(lakh|lac|lakhs|k)?/i
  );
  if (range) {
    const toAmt = (n, u) => {
      let v = Number(n);
      if (["lakh", "lac", "lakhs"].includes((u || "").toLowerCase())) v *= 100000;
      if ((u || "").toLowerCase() === "k") v *= 1000;
      return Math.round(v);
    };
    q.min_budget = toAmt(range[1], range[2]);
    q.budget = toAmt(range[3], range[4] || range[2]);
  } else {
    const b = parseBudget(text);
    if (b) q.budget = b;
    const mb = parseMinBudget(text);
    if (mb) q.min_budget = mb;
  }

  const brand = parseBrand(text);
  if (brand) q.brand = brand;

  const storage = normalized.match(/(\d+)\s*gb/);
  if (storage) q.storage = Number(storage[1]);

  if (/\bbest\b/i.test(text)) q.intent = "best";
  if (/\bcheapest|lowest price\b/i.test(text)) q.intent = "cheapest";

  const stop = new Set([
    "show","me","give","find","the","a","an","best","cheap","cheapest","phones","phone",
    "mobiles","mobile","under","below","between","and","with","in","india","price","prices",
    "around","upto","up","to","for","brand","bike","bikes","motorcycle","car","cars",
    "lakh","lakhs","lac","k","gb","cc","shoes","shoe","laptop","laptops","headphones",
    "earphones","watch","watches","bag","bags","clothing","clothes","gaming","tv","television",
    "buy","online","smartphone","smartphones","iphone","android","want","need","looking","good",
    "camera","battery","display","screen"
  ]);

  const tokens = text.match(/[a-z0-9]+/gi) || [];
  const keywords = tokens.filter(token => {
    const t = token.toLowerCase();
    if (stop.has(t)) return false;
    if (/^\d+(?:\.\d+)?$/.test(t)) return false;
    // Strip cc tokens like "150cc", "350cc" — these go into target_cc params instead
    if (/^\d{2,4}cc$/i.test(t)) return false;
    // Strip lakh/k budget tokens like "1lakh", "50k"
    if (/^\d+(?:\.\d+)?(?:lakh|lakhs|lac|k)$/i.test(t)) return false;
    if (brand && t === brand.toLowerCase()) return false;
    return true;
  }).join(" ");

  if (keywords) q.keywords = keywords;

  // Capture camera/battery emphasis for scoring
  if (/\bgood camera\b|\bbest camera\b|\bcamera phone\b/i.test(text)) {
    q.keywords = ((q.keywords || "") + " camera").trim();
    q.intent = q.intent || "best";
  }

  // RAM parsing for mobiles
  if (category === "mobile") {
    const ramM = normalized.match(/(\d+)\s*gb\s*ram/i);
    if (ramM) q.ram = Number(ramM[1]);
    // Also store raw query for 5G detection in scoring
    q.raw_query = normalized;
  }

  if (category === "bike") {
    const type = ["sports", "commuter", "cruiser", "scooter", "adventure", "touring", "electric"]
      .find(v => normalized.includes(v));
    if (type) q.category_type = type;
    // Use the new cc parser — supports ranges, above/below, around
    const ccParams = parseCubicCapacity(text);
    if (ccParams) Object.assign(q, ccParams);
  }

  if (category === "car") {
    for (const x of ["suv","hatchback","sedan","muv","coupe"]) {
      if (new RegExp("\\b" + x + "\\b").test(normalized)) { q.body_type = x; break; }
    }
    for (const x of ["petrol","diesel","cng","electric","ev","hybrid"]) {
      if (new RegExp("\\b" + x + "\\b").test(normalized)) { q.fuel = x; break; }
    }
    for (const x of ["automatic","manual"]) {
      if (new RegExp("\\b" + x + "\\b").test(normalized)) { q.transmission = x; break; }
    }
    const seats = normalized.match(/(\d+)\s*(?:seater|seat)/);
    if (seats) q.seats = Number(seats[1]);
    // Engine displacement for cars
    const carCC = parseCubicCapacity(text);
    if (carCC) Object.assign(q, carCC);
  }

  return q;
}

// ── Conversational context ────────────────────────────────────────────────────
function isRefinement(text, prevCategory) {
  if (!prevCategory || !sessionContext) return false;
  const t = text.toLowerCase().trim();
  // Refinement patterns — adding a filter to previous search
  const refiners = [
    /^only\b/,          // "only Samsung"
    /^just\b/,          // "just the ones with…"
    /^with\b/,          // "with good camera"
    /^under\b/,         // "under 20k"
    /^below\b/,
    /^above\b/,
    /^by\b/,            // "by Yamaha"
    /^from\b/,
    /^good camera/,
    /^good battery/,
    /^best one/,
    /^cheapest/,
    /^most affordable/,
    /^cheapest one/,
    /^what'?s? (?:the )?(best|cheapest)/,
    /^which (is|one)/,
    /^sort by/,
    /^show (me )?(?:only|just)/,
    /^filter/,
  ];
  return refiners.some(r => r.test(t));
}

function mergeContext(prevParams, newParams) {
  // New params override old, but old params persist if not overridden
  const merged = { ...prevParams };
  for (const [k, v] of Object.entries(newParams)) {
    if (v !== undefined && v !== null && v !== "") {
      merged[k] = v;
    }
  }
  return merged;
}

function updateContextBar(category) {
  const bar = $("contextBar");
  const label = $("contextLabel");
  if (!bar || !label) return;
  if (sessionContext && category === sessionContext.category) {
    bar.classList.remove("hidden");
    label.textContent = `Refining "${sessionContext.rawQuery}" (${category}):`;
  } else {
    bar.classList.add("hidden");
  }
}

function clearContext() {
  sessionContext = null;
  const bar = $("contextBar");
  if (bar) bar.classList.add("hidden");
}

// ── Backend communication ─────────────────────────────────────────────────────
async function checkBackend() {
  const el = $("backendStatus");
  try {
    const r = await fetch(`${API}/api/health`, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    const sources = d.vehicle_sources || {};
    el.className = "backend-status success";
    el.textContent = `Backend connected • v${d.version || "3.x"} • SerpAPI + BikeWale + CarDekho`;

    // Store Razorpay key ID for checkout
    if (d.razorpay_key_id) {
      razorpayKeyId = d.razorpay_key_id;
    }
  } catch (e) {
    el.className = "backend-status error";
    el.textContent = `Backend not reachable at ${API}. Start the server with Start-on-Windows.bat.`;
  }
}

// ── Search ────────────────────────────────────────────────────────────────────
async function search(queryText) {
  queryText = queryText.trim();
  if (!queryText) { $("input").focus(); return; }

  let category = categoryFrom(queryText);
  let params;
  let effectiveQuery = queryText;

  // Conversational refinement
  if (!category && sessionContext && isRefinement(queryText, sessionContext.category)) {
    category = sessionContext.category;
    const newParams = parseQuery(queryText, category);
    params = mergeContext(sessionContext.params, newParams);
    effectiveQuery = sessionContext.rawQuery + " + " + queryText;
    setAssistant(`Refining your ${category} search…`);
  } else {
    // New search
    if (!category) {
      // Fall back to general search instead of rejecting
      category = "general";
    }
    params = parseQuery(queryText, category);
    clearContext();
  }

  currentSearch = { category, query: queryText, params };

  // Save context for next refinement
  sessionContext = { category, rawQuery: queryText, params };
  updateContextBar(category);

  $("transcript").textContent = effectiveQuery;
  $("flow").textContent = `${category} • ${
    category === "bike" ? "BikeWale live" :
    category === "car" ? "CarDekho live" :
    category === "mobile" ? "Amazon + Flipkart via SerpAPI" :
    "SerpAPI Google Shopping"
  }`;

  $("title").textContent = "SEARCHING…";
  const ccNote = params.target_cc
    ? (params.cc_min && params.cc_max
      ? `<p class="muted budget-note">🔧 Engine filter: ${params.cc_min}–${params.cc_max}cc (targeting ${params.target_cc}cc)</p>`
      : params.cc_min
      ? `<p class="muted budget-note">🔧 Engine filter: above ${params.cc_min}cc</p>`
      : params.cc_max
      ? `<p class="muted budget-note">🔧 Engine filter: up to ${params.cc_max}cc</p>`
      : "")
    : "";
  $("results").innerHTML = `
    <div class="panel loading-state">
      <div class="loader"></div>
      <h3>Searching live…</h3>
      <p class="muted">Querying live sources for <strong>${esc(category)}</strong>. This may take a few seconds.</p>
      ${params.budget ? `<p class="muted budget-note">🛡️ Budget protected: within ₹${Number(params.budget).toLocaleString("en-IN")}</p>` : ""}
      ${ccNote}
    </div>`;

  const urlParams = new URLSearchParams({ category });
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") urlParams.set(k, String(v));
  });

  try {
    const r = await fetch(`${API}/api/search?${urlParams.toString()}`, { cache: "no-store" });
    if (!r.ok) {
      const body = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status}: ${body.slice(0, 200)}`);
    }
    const data = await r.json();

    lastResults = Array.isArray(data.items) ? data.items : [];
    const isLive = lastResults.some(x => x.live !== false);
    renderResults(lastResults, data.explanation || "", category, params);
    saveHistory(queryText, category, lastResults.length, isLive);

    setAssistant(
      lastResults.length
        ? `Found ${lastResults.length} matching ${category} result(s). ${params.budget ? `All within ₹${Number(params.budget).toLocaleString("en-IN")} budget.` : ""}`
        : (data.explanation || `No matching ${category} listings found.`)
    );
  } catch (e) {
    $("title").textContent = "SEARCH ERROR";
    $("results").innerHTML = `
      <div class="panel">
        <h3>Live search unavailable</h3>
        <p class="muted">Could not reach the backend at <code>${esc(API)}</code>.</p>
        <p class="muted error-detail">${esc(e.message)}</p>
        <p class="muted">Make sure the FastAPI server is running. Use <strong>Start-on-Windows.bat</strong> to launch it.</p>
      </div>`;
    setAssistant("The live search service could not be reached. Check the backend terminal.");
  }
}

// ── Rendering ─────────────────────────────────────────────────────────────────
function renderResults(items, explanation, category, params) {
  $("title").textContent = items.length ? `RESULTS • ${items.length}` : "NO MATCHES";
  const el = $("results");
  el.innerHTML = "";

  if (!items.length) {
    const budgetMsg = params && params.budget
      ? ` within ₹${Number(params.budget).toLocaleString("en-IN")} budget` : "";
    el.innerHTML = `
      <div class="panel">
        <h3>No matching products found${budgetMsg}</h3>
        <p class="muted">${esc(explanation)}</p>
        <div class="no-results-tips">
          <p class="muted">Try broadening your search:</p>
          <ul class="muted">
            <li>Remove the brand filter</li>
            <li>Increase the budget</li>
            <li>Use simpler keywords</li>
          </ul>
        </div>
      </div>`;
    return;
  }

  items.forEach((p, i) => {
    const card = document.createElement("article");
    card.className = "product";

    const isDemo = p.live === false;
    const liveBadgeClass = isDemo ? "demo-badge" : "live-badge";
    const sourceDisplay = (p.source || "").replace(/^LIVE\s*[•·]\s*/i, "").trim();
    const liveLabel = isDemo ? `DEMO • ${esc(sourceDisplay)}` : `LIVE • ${esc(sourceDisplay)}`;

    // Build spec tags — shown as pills on vehicle cards
    const specTags = [
      p.engine_cc ? { label: `${p.engine_cc}cc`, cls: "spec-engine" } : null,
      p.body_type ? { label: p.body_type.toUpperCase(), cls: "spec-tag" } : null,
      p.fuel ? { label: p.fuel.toUpperCase(), cls: p.fuel === "electric" || p.fuel === "ev" ? "spec-ev" : "spec-tag" } : null,
      p.transmission ? { label: p.transmission, cls: "spec-tag" } : null,
      p.seats ? { label: `${p.seats} seats`, cls: "spec-tag" } : null,
      p.storage_gb ? { label: `${p.storage_gb}GB`, cls: "spec-tag" } : null,
    ].filter(Boolean);
    const specTagsHTML = specTags.length
      ? `<div class="spec-tags">${specTags.map(t => `<span class="${t.cls}">${esc(t.label)}</span>`).join("")}</div>`
      : "";
    const specs = specTags.map(t => t.label).join(" • ");

    const isMobile = p.category === "mobile" || category === "mobile";

    let priceBlock = "";
    if (isMobile && (p.amazon || p.flipkart)) {
      const amzPrice = p.amazon?.price;
      const fkPrice = p.flipkart?.price;
      priceBlock = `
        <div class="seller-prices">
          <div class="best-price">${p.price ? money(p.price) : "Price unavailable"}${p.best_price_source ? ` <span class="muted">via ${esc(p.best_price_source)}</span>` : ""}</div>
          <div class="price-row">
            <span>Amazon</span>
            <span>${amzPrice ? money(amzPrice) : "Not found"}</span>
            ${p.amazon?.url ? `<a href="${esc(p.amazon.url)}" target="_blank" rel="noopener noreferrer" class="action-link small">↗</a>` : ""}
          </div>
          <div class="price-row">
            <span>Flipkart</span>
            <span>${fkPrice ? money(fkPrice) : "Not found"}</span>
            ${p.flipkart?.url ? `<a href="${esc(p.flipkart.url)}" target="_blank" rel="noopener noreferrer" class="action-link small">↗</a>` : ""}
          </div>
          ${amzPrice && fkPrice ? `<div class="price-compare-note">${amzPrice < fkPrice ? "Amazon cheaper by " + money(fkPrice - amzPrice) : fkPrice < amzPrice ? "Flipkart cheaper by " + money(amzPrice - fkPrice) : "Same price on both"}</div>` : ""}
        </div>`;
    } else {
      priceBlock = `<div class="price">${p.price ? money(p.price) : "Price unavailable"}</div>`;
    }

    // Trust layer
    const trustStatus = p.live !== false ? "verified" : "demo";
    const trustHTML = `
      <div class="trust-layer">
        <span class="${trustStatus === 'verified' ? 'trust-ok' : 'trust-demo'}">
          ${trustStatus === 'verified' ? '✓ Live search result' : '⚠ Demo data — not live price'}
        </span>
        ${p.price ? '<span class="trust-ok">✓ Price found</span>' : '<span class="trust-warn">⚠ Price not verified</span>'}
        ${p.source_url || p.amazon?.url ? '<span class="trust-ok">✓ Seller identified</span>' : ''}
        ${p.checked_at ? `<span class="trust-muted">Checked ${new Date(p.checked_at).toLocaleTimeString("en-IN")}</span>` : ""}
      </div>`;

    // Match score
    let scoreBlock = "";
    if (p.match_score != null || p.why) {
      const scoreColor = p.match_score >= 75 ? "score-high" : p.match_score >= 50 ? "score-mid" : "score-low";
      const reasons = Array.isArray(p.match_reasons) ? p.match_reasons : [];
      const warnings = Array.isArray(p.match_warnings) ? p.match_warnings : [];
      scoreBlock = `
        <div class="why-product">
          ${p.match_score != null ? `<div class="match-score ${scoreColor}">
            <span class="score-num">${esc(p.match_score)}/100</span>
            <span class="score-label">AI Match Score</span>
            <small>(app-generated, not an official product rating)</small>
          </div>` : ""}
          ${reasons.length ? `<div class="match-reasons">
            ${reasons.map(r => `<span class="reason-tag">✓ ${esc(r)}</span>`).join("")}
          </div>` : ""}
          ${warnings.length ? `<div class="match-warnings">
            ${warnings.map(w => `<span class="warn-tag">⚠ ${esc(w)}</span>`).join("")}
          </div>` : ""}
          ${p.product_rating != null ? `<p class="muted">Rating: ⭐ ${esc(p.product_rating)}${p.review_count ? ` (${Number(p.review_count).toLocaleString("en-IN")} reviews)` : ""}</p>` : ""}
        </div>`;
    }

    let actionLinks = "";
    if (isMobile) {
      if (p.amazon?.url) actionLinks += `<a target="_blank" rel="noopener noreferrer" href="${esc(p.amazon.url)}" class="action-link">Amazon ↗</a>`;
      if (p.flipkart?.url) actionLinks += `<a target="_blank" rel="noopener noreferrer" href="${esc(p.flipkart.url)}" class="action-link">Flipkart ↗</a>`;
    }
    if (p.source_url) {
      actionLinks += `<a target="_blank" rel="noopener noreferrer" href="${esc(p.source_url)}" class="action-link">View ↗</a>`;
    }

    card.innerHTML = `
      ${p.image ? `<img src="${esc(p.image)}" alt="${esc(p.name || "Product")}" loading="lazy">` : ""}
      <div class="card-badges">
        <small class="${liveBadgeClass}">${liveLabel}</small>
        ${isDemo ? `<small class="demo-warning">Demo data — not live prices</small>` : ""}
        ${i === 0 && !isDemo ? `<small class="best-match-badge">🏆 Best Match</small>` : ""}
        ${p.engine_cc && !isDemo ? `<small class="cc-badge">${p.engine_cc}cc</small>` : ""}
      </div>
      <h3>${esc(p.name || "Product")}</h3>
      ${p.brand ? `<p class="muted brand">${esc(p.brand)}</p>` : ""}
      ${specTagsHTML || (specs ? `<p class="muted specs">${esc(specs)}</p>` : "")}
      ${priceBlock}
      ${scoreBlock}
      ${trustHTML}
      <p class="muted source-note">
        ${esc(p.price_type || "listing price")}
        ${p.checked_at ? ` • Last checked: ${esc(new Date(p.checked_at).toLocaleString("en-IN"))}` : ""}
      </p>
      <div class="actions">
        <button type="button" data-add="${i}" ${!p.price ? "title='Price unavailable — cannot add to cart'" : ""}>Add to cart</button>
        <button type="button" class="secondary watch-btn" data-watch="${i}">⏰ Watch price</button>
        ${actionLinks}
      </div>`;

    card.querySelector("[data-add]").addEventListener("click", () => addToCart(p));
    card.querySelector(".watch-btn").addEventListener("click", (e) => {
      const btn = e.currentTarget;
      // Show inline target-price input instead of prompt()
      if (btn.nextElementSibling && btn.nextElementSibling.classList.contains("watch-inline")) {
        btn.nextElementSibling.remove(); return;
      }
      const row = document.createElement("div");
      row.className = "watch-inline";
      const suggested = p.price ? Math.round(p.price * 0.9) : "";
      row.innerHTML = `
        <input class="watch-input" type="number" placeholder="Target price (₹)" value="${suggested}" min="1">
        <button type="button" class="watch-confirm">Watch</button>
        <button type="button" class="watch-cancel secondary small">✕</button>`;
      btn.insertAdjacentElement("afterend", row);
      row.querySelector(".watch-confirm").addEventListener("click", () => {
        const val = parseInt(row.querySelector(".watch-input").value.replace(/,/g, ""), 10);
        addToWatchlist(p, isNaN(val) ? null : val);
        row.remove();
      });
      row.querySelector(".watch-cancel").addEventListener("click", () => row.remove());
      row.querySelector(".watch-input").focus();
    });
    el.appendChild(card);
  });

  const note = document.createElement("div");
  note.className = "panel source-note-panel";
  note.innerHTML = `<b>Source &amp; filtering</b><p class="muted">${esc(explanation)}</p>
    <p class="muted">All prices retrieved from live sources. Corrupt prices (₹2, ₹5, ₹49) are automatically rejected.</p>`;
  el.appendChild(note);
}

// ── Cart ──────────────────────────────────────────────────────────────────────
function getCart() {
  const c = storageGet("rz_cart", { items: [] });
  if (!Array.isArray(c.items)) c.items = [];
  return c;
}

function saveCart(cart) {
  storageSet("rz_cart", cart);
}

function addToCart(product) {
  const cart = getCart();
  const found = cart.items.find(x => x.id === product.id);

  if (found) {
    found.qty = (found.qty || 1) + 1;
    if (product.price && found.price !== product.price) {
      found.price_changed_from = found.price;
      found.price = product.price;
    }
  } else {
    cart.items.push({ ...product, qty: 1 });
  }

  saveCart(cart);
  renderCart();
  if (product.category === "mobile") loadMobileRecommendations(product);
  if (product.category === "bike" || product.category === "car") loadVehicleRecommendations(product);
  setAssistant(`${product.name} added to cart.`);
}

function removeFromCart(productId) {
  const cart = getCart();
  cart.items = cart.items.filter(x => x.id !== productId);
  saveCart(cart);
  renderCart();
}

function updateQty(productId, delta) {
  const cart = getCart();
  const item = cart.items.find(x => x.id === productId);
  if (!item) return;
  item.qty = Math.max(1, (item.qty || 1) + delta);
  saveCart(cart);
  renderCart();
}

// Extract a clean "Brand Model" string from a full product title
// e.g. "Samsung Galaxy A55 5G (Iceblue, 8GB, 128GB)" → "Samsung Galaxy A55"
function extractMobileModel(name) {
  if (!name) return name;
  // Strip common suffixes in parentheses
  let m = name.replace(/\s*\(.*?\)\s*/g, " ").trim();
  // Keep only the first 4 tokens (Brand + up to 3 model words)
  const tokens = m.split(/\s+/).slice(0, 4);
  return tokens.join(" ");
}

async function loadMobileRecommendations(product) {
  const key = product.id || product.name;
  if (!key || recommendationLoads[key]) return;
  recommendationLoads[key] = true;
  try {
    const cleanModel = extractMobileModel(product.name || "");
    const params = new URLSearchParams({ category: "mobile", model: cleanModel });
    const response = await fetch(`${API}/api/addons?${params.toString()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.items) ? data.items : [];
    if (items.length) mobileRecommendations[key] = { product, items };
    renderCart();
  } catch (_) {
    delete recommendationLoads[key];
  }
}

async function loadVehicleRecommendations(product) {
  const key = product.id || product.name;
  if (!key || recommendationLoads["v:" + key]) return;
  recommendationLoads["v:" + key] = true;
  // Return immediately if already cached
  if (vehicleRecommendations[key]) return;
  try {
    const params = new URLSearchParams({ category: product.category, model: product.name || "" });
    const response = await fetch(`${API}/api/addons?${params.toString()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const items = Array.isArray(data.items) ? data.items : [];
    if (items.length) vehicleRecommendations[key] = { product, items };
    renderCart();
  } catch (_) {
    delete recommendationLoads["v:" + key];
  }
}

function renderCart() {
  const cart = getCart();
  const items = cart.items;
  const total = items.reduce((sum, x) => {
    const price = Number(x.price) || 0;
    return sum + price * (x.qty || 1);
  }, 0);

  const accessoryChoices = [];

  const ACC_ICONS = {
    // Mobile
    case: "📱", screen_protector: "🛡️", charger: "⚡", earphones: "🎧",
    // Bike
    helmet: "🪖", gloves: "🧤", jacket: "🧥", boots: "👢",
    cover: "🏍️", lock: "🔒", bag: "🎒", guard: "🛡️",
    mirrors: "🔭", mount: "📍", grips: "✊", tools: "🔧",
    // Car
    seat: "💺", mat: "🟫", steering: "🎡", fragrance: "🌸",
    organiser: "🧳", camera: "📷", sunshade: "☀️", tpms: "🔔",
    emergency: "🆘",
    other: "🔌",
  };

  // ── Shared helper: build a FBT section from a rec object ───────────────────
  function buildFBTSection(product, rec, emoji, titleLabel) {
    if (!rec || !rec.items || !rec.items.length) return "";
    const key = product.id || product.name;

    const byType = {};
    for (const acc of rec.items) {
      const tk = acc.type_key || "other";
      const icon = ACC_ICONS[acc.type_icon] || ACC_ICONS[tk] || "🔌";
      if (!byType[tk]) byType[tk] = { label: acc.type || tk, icon, items: [] };
      byType[tk].items.push(acc);
    }

    const typeBlocks = Object.values(byType).map(group => {
      const cards = group.items.map(accessory => {
        const hasPrice = accessory.price && Number(accessory.price) > 0;
        const isLive = accessory.live === true;
        const idx = accessoryChoices.push({
          ...accessory,
          id: `accessory:${key}:${accessory.name}`,
          category: "accessory",
          compatible_model: product.name,
        }) - 1;
        // Fallback search URL so every card always has an action
        const searchQ = encodeURIComponent(accessory.name + " " + product.name);
        const fallbackUrl = `https://www.amazon.in/s?k=${searchQ}`;
        const viewUrl = accessory.source_url || fallbackUrl;

        return `<div class="acc-card">
          ${accessory.image ? `<img class="acc-img" src="${esc(accessory.image)}" alt="${esc(accessory.name)}" loading="lazy">` : `<div class="acc-img-placeholder">${esc(group.icon)}</div>`}
          <div class="acc-info">
            <p class="acc-name">${esc(accessory.name)}</p>
            ${accessory.reason ? `<p class="acc-reason muted">${esc(accessory.reason)}</p>` : ""}
            <div class="acc-footer">
              <span class="acc-price">${hasPrice ? money(accessory.price) : '<span style="font-size:11px;color:var(--muted)">Check price ↗</span>'}</span>
              <span class="acc-badge ${isLive ? "live" : "demo"}">${isLive ? "LIVE" : "Curated"}</span>
            </div>
            <div class="acc-actions">
              ${hasPrice ? `<button type="button" class="acc-add-btn" data-add-accessory="${idx}">+ Add to Cart</button>` : `<a href="${esc(viewUrl)}" target="_blank" rel="noopener noreferrer" class="acc-add-btn" style="text-decoration:none;display:flex;align-items:center;justify-content:center;font-size:11px">Shop Now ↗</a>`}
              ${hasPrice ? `<a href="${esc(viewUrl)}" target="_blank" rel="noopener noreferrer" class="acc-view-link">Find ↗</a>` : ""}
            </div>
          </div>
        </div>`;
      }).join("");
      return `<div class="acc-type-group">
        <h4 class="acc-type-label">${esc(group.icon)} ${esc(group.label)}</h4>
        <div class="acc-type-cards">${cards}</div>
      </div>`;
    }).join("");

    if (!typeBlocks) return "";
    const hasLive = rec.items.some(x => x.live === true);
    return `<section class="panel recommendations fbt-panel">
      <div class="fbt-header">
        <span class="fbt-title">${emoji} ${esc(titleLabel)}</span>
        <span class="fbt-subtitle">For your ${esc(product.name)}</span>
        ${hasLive ? '<span class="fbt-live-badge">LIVE prices</span>' : '<span class="fbt-live-badge" style="background:var(--panel2);color:var(--muted)">Curated picks</span>'}
      </div>
      <p class="muted compat-note">✓ Recommended for ${esc(product.name)}</p>
      <div class="acc-types-container">${typeBlocks}</div>
    </section>`;
  }

  // ── Mobile FBT — live SerpAPI accessories (fallback to static instantly) ─────
  const mobileFBT = items
    .filter(x => x.category === "mobile")
    .map(product => {
      const key = product.id || product.name;
      // Use live data if available, else static fallback (always shows)
      const cached = mobileRecommendations[key];
      const rec = cached || { product, items: STATIC_MOBILE_ACCS.map(a => ({ ...a, compatible_model: product.name })) };
      return buildFBTSection(product, rec, "🛒", "Frequently Bought Together");
    }).join("");

  // ── Vehicle FBT — curated real-world accessories (always shows) ─────────────
  const vehicleFBT = items
    .filter(x => x.category === "bike" || x.category === "car")
    .map(product => {
      const key = product.id || product.name;
      const cached = vehicleRecommendations[key];
      const staticItems = product.category === "bike" ? STATIC_BIKE_ACCS : STATIC_CAR_ACCS;
      const rec = cached || { product, items: staticItems.map(a => ({ ...a, compatible_model: product.name })) };
      const emoji = product.category === "bike" ? "🏍️" : "🚗";
      const label = product.category === "bike" ? "Essential Bike Accessories" : "Must-Have Car Accessories";
      return buildFBTSection(product, rec, emoji, label);
    }).join("");

  const recsHTML = mobileFBT + vehicleFBT;

  $("cart").innerHTML = `
    <h2>Cart <span class="pill">${items.length} item(s)</span></h2>
    ${items.length
      ? items.map(x => {
          const price = Number(x.price) || 0;
          const priceTag = price > 0 ? money(price * (x.qty || 1)) : "Price unavailable";
          const priceChange = x.price_changed_from
            ? `<span class="price-change">⚠ Price changed from ${money(x.price_changed_from)}</span>` : "";
          const isAcc = x.category === "accessory";
          return `<div class="row cart-row">
            <span>
              ${isAcc ? '<span class="acc-badge-sm">Accessory</span> ' : ""}${esc(x.name)} × ${x.qty || 1}
              ${priceChange}
            </span>
            <div class="qty-controls">
              <button type="button" data-qty-dec="${x.id}">−</button>
              <button type="button" data-qty-inc="${x.id}">+</button>
              <button type="button" class="remove-btn" data-remove="${x.id}">Remove</button>
            </div>
            <b>${priceTag}</b>
          </div>`;
        }).join("")
      : '<p class="muted">Cart is empty.</p>'}
    ${items.length ? `
      <hr>
      <div class="row cart-total">
        <b>Total</b>
        <b>${total > 0 ? money(total) : "Prices unavailable"}</b>
      </div>
      <p class="muted cart-note">Prices are live search results — actual checkout price may vary. Verify on seller's website before purchase.</p>
      <button type="button" id="checkoutBtn" class="checkout-btn">Proceed to Checkout (Razorpay)</button>` : ""}
    ${recsHTML}`;

  const btn = $("checkoutBtn");
  if (btn) btn.addEventListener("click", () => { location.href = "payment.html"; });

  document.querySelectorAll("[data-add-accessory]").forEach(button => {
    button.addEventListener("click", () => {
      const acc = accessoryChoices[Number(button.dataset.addAccessory)];
      if (acc) addToCart(acc);
    });
  });
  document.querySelectorAll("[data-qty-inc]").forEach(b =>
    b.addEventListener("click", () => updateQty(b.dataset.qtyInc, 1))
  );
  document.querySelectorAll("[data-qty-dec]").forEach(b =>
    b.addEventListener("click", () => updateQty(b.dataset.qtyDec, -1))
  );
  document.querySelectorAll("[data-remove]").forEach(b =>
    b.addEventListener("click", () => removeFromCart(b.dataset.remove))
  );
}

// ── Voice ─────────────────────────────────────────────────────────────────────
function setAssistant(message) {
  const el = $("assistant");
  if (el) el.textContent = message;
  if ("speechSynthesis" in window) {
    try {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(message));
    } catch (_) {}
  }
}

function initVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    $("status").textContent = "Voice search unavailable — type instead";
    $("mic").disabled = true;
    $("mic").title = "Voice search is not supported in this browser";
    return;
  }
  recognition = new SR();
  recognition.lang = "en-IN";
  recognition.interimResults = false;
  recognition.continuous = false;

  recognition.onstart = () => {
    listening = true;
    $("mic").classList.add("listening");
    $("status").textContent = "Listening… speak now";
  };
  recognition.onresult = (event) => {
    const text = event.results?.[0]?.[0]?.transcript?.trim();
    if (text) { $("input").value = text; search(text); }
  };
  recognition.onerror = (event) => {
    listening = false;
    $("mic").classList.remove("listening");
    if (event.error === "not-allowed") {
      $("status").textContent = "Microphone blocked — type instead";
      setAssistant("Microphone permission was denied. You can type your request instead.");
    } else if (event.error === "no-speech") {
      $("status").textContent = "No speech detected — try again";
    } else {
      $("status").textContent = "Voice error — type instead";
    }
  };
  recognition.onend = () => {
    listening = false;
    $("mic").classList.remove("listening");
    $("status").textContent = "Ready";
  };
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const sendBtn = $("send");
  const input = $("input");
  const micBtn = $("mic");
  const clearBtn = $("clear");
  const clearCtx = $("clearContext");
  const clearWatch = $("clearWatch");

  sendBtn.addEventListener("click", () => search(input.value));
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); search(input.value); }
  });

  micBtn.addEventListener("click", () => {
    if (!recognition) initVoice();
    if (!recognition) return;
    try {
      if (listening) recognition.stop();
      else recognition.start();
    } catch (_) {}
  });

  clearBtn.addEventListener("click", clearHistory);
  if (clearCtx) clearCtx.addEventListener("click", () => { clearContext(); $("input").focus(); });
  if (clearWatch) clearWatch.addEventListener("click", () => {
    storageSet("rz_watchlist", []);
    renderWatchlist();
  });

  showHistory();
  renderCart();
  renderWatchlist();

  const cartItems = getCart().items;
  cartItems.filter(x => x.category === "mobile").forEach(loadMobileRecommendations);
  cartItems.filter(x => x.category === "bike" || x.category === "car").forEach(loadVehicleRecommendations);

  checkBackend();
  initVoice();
});
})();
