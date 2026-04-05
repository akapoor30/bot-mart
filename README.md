# 🛒 Bot-Mart

A quick-commerce price comparison engine that scrapes **Blinkit**, **Zepto**, and **Swiggy Instamart** in parallel, compares real checkout costs (item price + delivery + handling + platform fee + GST), and uses **AI** to verify you're comparing the exact same product across all three platforms.

---

## ✨ Features

- **Real-time parallel scraping** — All 3 platforms searched simultaneously using `asyncio.gather`
- **Real fee scraping** — Adds item to cart, navigates to checkout, reads the actual bill (delivery fee, handling fee, platform fee, GST) — nothing hardcoded
- **AI product matching** — Groq `llama-3.3-70b` verifies all platforms returned the same product variant (brand, weight, flavour). Flags mismatches like "Zepto returned 70g, others are 75g"
- **Total price comparison** — Cheapest by **item + all fees** (not just item price), so you see what actually comes out of your wallet
- **Smart cart** — Add multiple items, compare full cart total across platforms
- **Keycloak auth** — JWT-protected endpoints, users synced to PostgreSQL on first login
- **Resilient scraping** — Per-scraper timeout + `pkill` fallback so one hung browser never blocks the UI forever
- **Anti-bot bypass** — Headed Chrome + saved authenticated sessions for Blinkit and Instamart (Datadome / Cloudflare bypass)

---

## 📁 Project Structure

```
bot-mart/
├── delivery-bot/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   └── matcher.py          # Groq AI product matching & total-price calc
│   │   ├── scraper/
│   │   │   ├── base.py             # BaseScraper interface
│   │   │   ├── blinkit.py          # Blinkit scraper + fee scraping
│   │   │   ├── zepto.py            # Zepto scraper + fee scraping
│   │   │   ├── instamart.py        # Instamart scraper + fee scraping
│   │   │   └── fee_utils.py        # Shared bill-text parser
│   │   ├── cart/
│   │   │   └── router.py           # Cart CRUD + /cart/compare
│   │   ├── auth.py                 # Keycloak JWT verification
│   │   ├── database.py             # SQLAlchemy engine + session
│   │   ├── models.py               # User, CartItem, PriceSnapshot
│   │   └── main.py                 # FastAPI app, CORS, /compare endpoint
│   ├── sessions/                   # Playwright auth cookies (gitignored)
│   │   ├── blinkit_auth.json
│   │   ├── swiggy_auth.json
│   │   └── zepto_auth.json
│   ├── generate_blinkit_session.py
│   ├── generate_swiggy_session.py
│   ├── generate_zepto_session.py
│   ├── .env                        # Environment variables (see below)
│   └── requirements.txt
├── frontend-react/                 # React + Vite frontend
│   └── src/
│       ├── App.jsx                 # Main UI: search, AI results, cart panel
│       ├── App.css                 # Dark glassmorphic theme
│       └── services/api.js         # API client functions
└── README.md
```

---

## 🚀 Getting Started

### 1. Clone & install dependencies

```bash
git clone https://github.com/akapoor30/bot-mart.git
cd bot-mart/delivery-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
playwright install chrome
```

### 2. Start PostgreSQL & Keycloak

```bash
# PostgreSQL — create the database
createdb botmart

# Keycloak — start on port 8080 with realm 'bot-mart' configured
# (or use Docker: docker run -p 8080:8080 quay.io/keycloak/keycloak start-dev)
```

### 3. Set up environment variables

Create `delivery-bot/.env`:

```env
# Database
DATABASE_URL=postgresql://admin:admin@localhost:5432/botmart

# Keycloak
KEYCLOAK_URL=http://localhost:8080/realms/bot-mart

# AI product matching (free — get key at https://console.groq.com)
# Leave blank to disable AI (basic total-price calculation only)
GROQ_API_KEY=your_groq_key_here
```

### 4. Generate authenticated sessions

The scrapers need saved login sessions to bypass bot protection and add items to cart (required for fee scraping).

```bash
cd delivery-bot

# Blinkit — opens Chrome, set your pincode, press Enter when done
python generate_blinkit_session.py

# Swiggy Instamart — opens Chrome, log in via OTP + set location, press Enter
python generate_swiggy_session.py

# Zepto — opens Chrome, log in via OTP + set location, press Enter
python generate_zepto_session.py
```

Sessions are saved to `sessions/` and are gitignored.

### 5. Start the backend

```bash
cd delivery-bot
uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`.

### 6. Start the React frontend

```bash
cd delivery-bot/frontend-react
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`. Log in with your Keycloak account.

---

## 🔌 API Endpoints

### Core

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | ❌ | Health check |
| GET | `/api/me` | ✅ | Sync Keycloak user to local DB |
| GET | `/compare?item=X&pincode=Y` | ✅ | Scrape all 3 platforms + AI analysis |

### Cart

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/cart/` | ✅ | List cart items |
| POST | `/cart/add` | ✅ | Add item `{ search_query, quantity }` |
| DELETE | `/cart/{id}` | ✅ | Remove one item |
| DELETE | `/cart/` | ✅ | Clear entire cart |
| GET | `/cart/compare?pincode=Y` | ✅ | Compare full cart total across platforms |

### `/compare` response (with AI)

```json
{
  "query": "maggi",
  "pincode": "411057",
  "canonical_name": "MAGGI 2-Minute Instant Noodles 75g",
  "comparison_valid": false,
  "ai_note": "Only Blinkit and Instamart matched. Zepto returned a 70g variant.",
  "ai_confidence": "high",
  "cheapest_total": {
    "store": "Blinkit",
    "total_price": 67
  },
  "cheapest_option": { "store": "Blinkit", "price": 15 },
  "all_results": [
    {
      "store": "Blinkit",
      "name": "MAGGI 2-Minute Instant Noodles, Made With Quality Spices",
      "price": 15,
      "delivery_fee": 50,
      "handling_fee": 2,
      "platform_fee": 0,
      "gst_fee": 0,
      "total_price": 67,
      "ai_match": true,
      "ai_mismatch_reason": null,
      "status": "success"
    },
    {
      "store": "Zepto",
      "name": "Maggi Masala Noodles 70g",
      "price": 14,
      "delivery_fee": 30,
      "handling_fee": 0,
      "platform_fee": 0,
      "gst_fee": 0,
      "total_price": 44,
      "ai_match": false,
      "ai_mismatch_reason": "Different weight: 70g vs 75g",
      "status": "success"
    },
    {
      "store": "Instamart",
      "name": "MAGGI 2-Minute Noodles, Made With Quality Spices",
      "price": 15,
      "delivery_fee": 60,
      "handling_fee": 11,
      "platform_fee": 20,
      "gst_fee": 14,
      "total_price": 120,
      "ai_match": true,
      "ai_mismatch_reason": null,
      "status": "success"
    }
  ]
}
```

---

## 🤖 AI Integration — How & Why

### The Problem It Solves

Without AI, a search for "maggi" could return:

| Platform | Product | Price |
|----------|---------|-------|
| Blinkit | MAGGI 2-Minute Masala 75g | ₹15 |
| Zepto | Maggi Masala Noodles **70g** | ₹14 |
| Instamart | MAGGI **Atta** Noodles 75g | ₹18 |

Comparing these prices is misleading — they're all different products. UI would say "Zepto is cheapest at ₹14" when you'd actually be getting a smaller pack. This is the core problem AI fixes.

---

### Architecture: What Runs When

```
User searches "maggi"
        │
        ▼
asyncio.gather([Blinkit, Zepto, Instamart])   ← runs in parallel
        │                    takes ~60-90s
        ▼
match_products(query, results)                 ← AI step, ~1-2s
        │
        ├─ Sends all 3 scraped results to Groq llama-3.3-70b
        ├─ Model analyses: same product? same weight? same variant?
        ├─ Returns structured JSON with per-platform verdicts
        │
        ▼
Enrich each result + save to DB + return response
        │
        ▼
Frontend renders canonical name, total prices, mismatch badges
```

---

### Why Groq + llama-3.3-70b

| Requirement | Why Groq |
|---|---|
| **Speed** | ~1-2s response time (essential — scrapers already take 60-90s) |
| **Cost** | Free tier, no credit card required |
| **JSON output** | Supports `response_format={"type":"json_object"}` — returns valid JSON every time |
| **Quality** | llama-3.3-70b is excellent at product classification and structured reasoning |

We set `temperature=0.0` (fully deterministic) because product matching needs consistent, repeatable answers — not creative variation.

---

### The Prompt Design

We send a single structured message with:

1. **The search query** — what the user actually wanted
2. **All scraped results** — product name, weight, price, and every fee for each platform
3. **Pre-computed totals** — we calculate `total = item + delivery + handling + platform + gst` ourselves before sending, so the model doesn't need to do arithmetic (LLMs are unreliable at math)
4. **A strict JSON schema** — we tell the model exactly what fields to return

The model's job is purely **semantic reasoning**: "Is MAGGI 2-Minute Masala 75g the same as Maggi Masala Noodles 70g?" — something an LLM is very good at.

---

### Graceful Fallback

If `GROQ_API_KEY` is not set, or if the API call fails for any reason, the system automatically falls back to a basic mode:

- Assumes all results are valid matches
- Still computes total price (item + fees) correctly
- Returns results normally — no UI breakage

This means the app works without AI, just without the mismatch detection.

---

### What the AI Returns

```json
{
  "canonical_name":        "MAGGI 2-Minute Instant Noodles 75g",
  "comparison_valid":      false,
  "results": [
    { "store": "Blinkit",   "is_match": true,  "mismatch_reason": null,                     "total_price": 67  },
    { "store": "Zepto",     "is_match": false, "mismatch_reason": "Different weight: 70g",  "total_price": 44  },
    { "store": "Instamart", "is_match": true,  "mismatch_reason": null,                     "total_price": 120 }
  ],
  "cheapest_valid_store":  "Blinkit",
  "cheapest_total_price":  67,
  "ai_note": "Only Blinkit and Instamart matched. Blinkit is cheapest including all fees.",
  "confidence": "high"
}
```

`cheapest_valid_store` only considers platforms flagged as `is_match: true`, so mismatched variants are excluded from the "best deal" recommendation.

---

## 🏗️ How Fee Scraping Works

Real fees vary by order size, time of day, and user location. We scrape them directly from the cart checkout so the numbers are always accurate.

### Flow for each scraper

```
1. Search for product       → extract product name, price, weight
2. Click ADD button         → uses JS dispatchEvent (bypasses React overlay)
3. Open cart / checkout     → navigate to the bill details section
4. Scrape bill text         → parse "Delivery Fee ₹50", "Handling Fee ₹11", etc.
5. Close browser            → with 5s timeout + pkill fallback (see below)
6. Return full result       → price + all fees
```

Fee scraping is **non-fatal** — if it fails for any reason, the scraper returns the product price with fees defaulting to `0`.

---

## 🛡️ Anti-Bot & Reliability Strategy

### Platform-Specific Bypass

| Platform | Browser Mode | Session | Special Handling |
|----------|-------------|---------|-----------------|
| **Blinkit** | Headed Chrome (`headless=False`) | `blinkit_auth.json` | `--window-position=-4001,0` |
| **Zepto** | Headless Chromium | `zepto_auth.json` | Escape key on start to close cart drawer |
| **Instamart** | Headed Chrome (`headless=False`) | `swiggy_auth.json` | `--window-position=-5001,0`; `domcontentloaded` not `networkidle` |

**Why headed Chrome for Blinkit and Instamart?**
Both platforms use Datadome (Blinkit) and custom bot detection (Instamart/Swiggy) that reliably detect headless Chromium by fingerprinting JS APIs (`navigator.webdriver`, missing Chrome-specific globals, etc.). Using real Chrome with `channel="chrome"` presents an authentic browser fingerprint.

### The `browser.close()` Hang Problem (and the Fix)

**The bug:** After scraping, calling `await browser.close()` on headed Chrome would hang indefinitely. Root causes:

1. **Swiggy/Blinkit `beforeunload` handlers** — When Chrome tries to close, these sites fire a "Leave Site?" dialog. In macOS Chrome, this requires a human click to dismiss. Playwright's `browser.close()` waits for Chrome to acknowledge closure, but Chrome is waiting for the dialog.
2. **In-flight network requests** — Clicking the cart `-` button during cleanup triggers an async API call to the platform's cart service. Chrome won't close until these requests resolve.

**The fix — two layers:**

```python
# Layer 1: asyncio.wait_for gives browser.close() a 5-second deadline
try:
    await asyncio.wait_for(browser.close(), timeout=5.0)
except Exception:
    # Layer 2: if it still hangs, pkill by the unique window-position flag
    # --window-position=-4001 is set ONLY on Blinkit's Chrome launch args
    # --window-position=-5001 is set ONLY on Instamart's Chrome launch args
    # This uniquely identifies each scraper's process without hitting others
    subprocess.run(["pkill", "-9", "-f", "window-position=-4001"], capture_output=True)
    print("Blinkit: force-killed stuck Chrome process")
```

**Why separate window-position values?** Blinkit and Instamart run in parallel. Using the same flag (`-3000`) meant pkill could kill the wrong scraper's Chrome mid-scrape. Unique flags (`-4001` for Blinkit, `-5001` for Instamart) surgically target only the right process.

### Per-Scraper Timeout in `main.py`

Even with the pkill fix, we wrap every scraper in `asyncio.wait_for` as a safety net:

```python
async def safe_scrape(coro, store_name, timeout):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return {"store": store_name, "status": "failed", "error": "Timed out"}
```

This guarantees the `/compare` endpoint always returns within a bounded time, even under unexpected failure. If Instamart times out, Blinkit and Zepto results still come back.

### Why `dispatchEvent` Instead of `element.click()`

Quick-commerce apps (Blinkit, Zepto, Swiggy) use React with "Vaul" drawer overlays on the cart. These overlays have `pointer-events: none` CSS, which causes Playwright's `element.click()` to wait up to 30 seconds for the overlay to disappear (it never does) — a silent timeout.

Using JavaScript's `dispatchEvent(new MouseEvent("click", {bubbles: true}))` bypasses Playwright's pointer-events check and dispatches the event directly to the DOM element. React's synthetic event system picks it up via event bubbling to the root.

```python
# ❌ This hangs for 30s when there's a Vaul drawer overlay
await element.click()

# ✅ This works immediately, bypasses pointer-events checks
await page.evaluate('''() => {
    el.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, view: window}));
}''')
```

---

## 🗄️ Database Models

| Model | Purpose |
|-------|---------|
| `User` | Synced from Keycloak on first login (`keycloak_id`, `email`) |
| `CartItem` | Per-user cart rows (`search_query`, `quantity`) |
| `PriceSnapshot` | Cached price + fee data: `price`, `delivery_fee`, `handling_fee`, `platform_fee`, `gst_fee`, `platform`, `pincode`, `search_query` |

`PriceSnapshot` is written on every `/compare` call and read by `/cart/compare` to show cart totals without re-scraping.

---

## 📋 Roadmap

- [x] Blinkit scraper + fee scraping
- [x] Zepto scraper + fee scraping  
- [x] Instamart scraper + fee scraping
- [x] FastAPI `/compare` endpoint
- [x] Keycloak JWT auth
- [x] Cart API with price snapshots
- [x] Cart total comparison across platforms
- [x] Real fee scraping from checkout pages (delivery, handling, platform, GST)
- [x] React frontend with search, results grid, cart panel
- [x] Anti-bot: headed Chrome + saved sessions + `dispatchEvent` bypass
- [x] **AI product matching** — Groq llama-3.3-70b cross-platform verification
- [x] **Total price comparison** — cheapest by item + all fees (not just item price)
- [x] **Reliable browser cleanup** — `asyncio.wait_for` + `pkill` per unique Chrome flag
- [x] **Per-scraper safety timeout** — UI always gets a response even if one scraper hangs
- [ ] Add-to-cart automation — auto-open the winning platform and checkout
- [ ] Price history & alerts — notify when price drops below threshold
- [ ] More platforms — Swiggy Mart, BigBasket Now, Dunzo

---

## ⚙️ Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `KEYCLOAK_URL` | ✅ | Keycloak realm URL for JWT verification |
| `GROQ_API_KEY` | Optional | Groq API key for AI matching. Get free at [console.groq.com](https://console.groq.com). Without this, totals are computed but mismatch detection is skipped. |
| `PINCODE` | Optional | Default delivery pincode (fallback) |

---

## 🔧 Troubleshooting

### "Searching..." spinner never stops
The scraper is still running (takes 60–120s). Check uvicorn logs for `[compare] All scrapers done:`. If this never appears, check for zombie Chrome processes:
```bash
pkill -9 -f "window-position=-4001"  # Blinkit
pkill -9 -f "window-position=-5001"  # Instamart
```

### Instamart returns 0 fees or fails
Run `python generate_swiggy_session.py` to refresh the session. Swiggy sessions expire every few days.

### `StatReload detected changes — reloading...` mid-search
Uvicorn's hot-reload picked up a file save during an active scrape, killing the in-flight request. **Always save your files before triggering a search** when using `--reload`. For production, use `uvicorn app.main:app` without `--reload`.

### AI returns `comparison_valid: true` when products clearly differ
The model confidence is `medium` or `low` — check `ai_confidence` in the response. If product names are very similar or weight information is missing from scraped results, the model may not catch the discrepancy.