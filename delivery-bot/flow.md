# Delivery Bot — Code Flow & Instructions

## How to Run

```bash
cd delivery-bot
source ../venv/bin/activate
uvicorn app.main:app --reload
```

Server runs at `http://127.0.0.1:8000`

| Endpoint | What it does |
|----------|-------------|
| `GET /` | Health check — returns `"Delivery Bot is Online"` |
| `GET /compare?item=Maggi&pincode=411057` | Searches Blinkit + Zepto, returns prices |
| `GET /docs` | Interactive Swagger UI to test the API |

---

## Project Structure

```
delivery-bot/
├── app/
│   ├── __init__.py          # Makes 'app' a Python package
│   ├── main.py              # FastAPI server — receives requests, runs scrapers, returns results
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseScraper — interface all scrapers must implement
│   │   ├── blinkit.py       # Opens Chrome, searches Blinkit, extracts product + price
│   │   ├── zepto.py         # Opens Chrome, searches Zepto, extracts product + price
│   │   └── instamart.py     # Opens Chrome with auth, handles bot checks, extracts product + price
│   ├── utils/               # (Future) helper functions
│   └── models/              # (Future) Pydantic data schemas
├── tmp/                     # Debug screenshots saved here (gitignored)
├── sessions/                # Browser cookies/auth state (gitignored)
├── requirements.txt         # Python dependencies
└── .env                     # API keys and settings (gitignored)
```

---

## Request Flow

```
You hit: GET /compare?item=Maggi&pincode=411057
                │
                ▼
        ┌──── main.py ────┐
        │                  │
        │ Creates:         │
        │  - BlinkitScraper│
        │  - ZeptoScraper  │
        │                  │
        │ Runs BOTH in     │
        │ parallel using   │
        │ asyncio.gather() │
        └──┬──────────┬────┘
           │          │
     ┌─────▼──┐  ┌───▼─────┐
     │Blinkit │  │ Zepto   │
     │Scraper │  │ Scraper │
     └───┬────┘  └───┬─────┘
         │           │
   Launch Chrome  Launch Chrome
         │           │
   Go to blinkit  Go to zepto
     .com           .com/search
         │           │
   Click search   (direct URL)
   link → /s/         │
         │           │
   Type "Maggi"   Type "Maggi"
   + Enter        via URL param
         │           │
   Wait for       Wait for
   results        results
         │           │
   Find cards     Find links
   div[id=NUM]    a[href=/pn/]
         │           │
   Loop cards:    Loop cards:
   skip if name   skip if name
   ≠ search term  ≠ search term
         │           │
   Extract name   Extract name
   + ₹ price      + ₹ price
         │           │
         └─────┬─────┘
               │
        ┌──────▼──────┐
        │   main.py   │
        │             │
        │ Compares    │
        │ all prices  │
        │             │
        │ Returns:    │
        │ - cheapest  │
        │ - all_results│
        └─────────────┘
```

---

## How Each File Works

### `base.py` — The Contract

Every scraper must implement `search_product(product_name, pincode)` and return:

```python
{"store": "...", "name": "...", "price": 20, "status": "success"}
# or on failure:
{"store": "...", "status": "failed", "error": "..."}
```

### `main.py` — The Orchestrator

1. Receives the HTTP request with `item` and `pincode`
2. Creates scraper instances
3. Runs them **in parallel** with `asyncio.gather()`
4. Filters successful results
5. Finds the cheapest using `min(results, key=lambda x: x['price'])`
6. Returns JSON with `cheapest_option` + `all_results`

### `blinkit.py` — Blinkit Scraper

1. **Launch Chrome** (visible, with stealth anti-detection)
2. **Go to** `blinkit.com`
3. **Click search link** — homepage search bar is `<a href="/s/">`, not an `<input>`
4. **Type product name** into the real search input on `/s/`
5. **Wait 5 seconds** for results to load
6. **Find product cards** — selector: `div[role="button"][id]` where `id` is a number
7. **Loop through cards**, parse name + price from each:
   - Card text format: `"15 MINS\nProduct Name\n95 g\n₹20\nADD"`
   - Skip lines with: `MINS`, `OFF`, `ADD`
   - Price = line with `₹` → strip to digits
   - Name = first remaining line
8. **Skip ads** — if name doesn't contain the search term, it's a sponsored product
9. **Return** first matching product's `{store, name, price, status}`

### `zepto.py` — Zepto Scraper

1. **Launch Chrome** (visible, with stealth anti-detection)
2. **Go directly to** `zeptonow.com/search?query=Maggi` (no clicking needed)
3. **Wait 5 seconds** for results
4. **Find product links** — selector: `a[href*="/pn/"]`
5. **Loop through cards**, parse name + price:
   - Card text format: `"ADD\n₹20\nProduct Name\n1 pack\n4.7\n(10.9k)"`
   - Price = first `₹` line after `ADD`
   - Name = first non-price, non-rating line after price
6. **Skip ads** — same logic, name must contain search term
7. **Return** first matching product

### `instamart.py` — Swiggy Instamart Scraper

1. **Launch Chrome** (visible, disabled automation flags)
2. **Load Session** uses `sessions/swiggy_auth.json` to bypass Datadome bot protection
3. **Go to** `swiggy.com/instamart`
4. **Click search banner** to open the real input field
5. **Type product name** + Enter
6. **Handle Anti-Bot Error** — Wait for and click the "Try Again" error boundary overlay if it appears
7. **Handle Onboarding** — Dismiss "Got it!" tooltips that block the DOM
8. **Find product cards** — Locate universal "Add item to cart" buttons
9. **Parse DOM Tree** — Use `locator.evaluate` Javascript to walk up from the button to the product container and extract text
10. **Filter Names** — Skip "Previously Bought", "Ad", "Sponsored" 
11. **Return** first matching non-ad product `{store, name, price, status}`

---

## Ad Skipping Logic

Both scrapers use the same strategy:

```
For each product card:
  1. Parse the name and price
  2. Check: does the name contain the search term?
     - "Maggi Double Masala" contains "Maggi" → ✅ KEEP
     - "Too Yumm K-Bomb Ramen" doesn't contain "Maggi" → ❌ SKIP (it's an ad)
  3. Return the first matching product
```

---

## Error Handling

- If scraping fails → saves a screenshot to `tmp/blinkit_error.png` or `tmp/zepto_error.png`
- Returns `{"status": "failed", "error": "..."}` instead of crashing
- `finally: await browser.close()` ensures Chrome always closes, even on errors
- If one scraper fails, the other still returns results (they run independently)

---

## Key Technologies

| Technology | Purpose |
|-----------|---------|
| **FastAPI** | Web framework — creates the API server |
| **Uvicorn** | ASGI server — runs the FastAPI app |
| **Playwright** | Browser automation — controls Chrome programmatically |
| **playwright-stealth** | Anti-detection — makes the bot look like a real human |
| **asyncio** | Runs multiple scrapers simultaneously |

---

## Example Response

```json
{
  "query": "Maggi",
  "pincode": "411057",
  "cheapest_option": {
    "store": "Blinkit",
    "name": "Maggi Double Masala Instant Noodles",
    "price": 20,
    "status": "success"
  },
  "all_results": [
    {"store": "Blinkit", "name": "Maggi Double Masala Instant Noodles", "price": 20, "status": "success"},
    {"store": "Zepto", "name": "Maggi Chicken Instant Noodles", "price": 20, "status": "success"}
  ]
}
```
