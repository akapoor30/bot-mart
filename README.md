# 🛒 Bot-Mart

A quick-commerce price comparison bot that searches **Blinkit**, **Zepto**, and **Swiggy Instamart** simultaneously, compares prices (including delivery, handling, and platform fees), and tells you where to order from.

---

## ✨ Features

- **Real-time multi-platform scraping** — Blinkit, Zepto, and Instamart searched in parallel
- **Full fee breakdown** — scrapes actual delivery fee, handling fee, and platform fee from each platform's checkout page (not hardcoded)
- **Smart cart** — add multiple items, compare total cost across all 3 platforms
- **Keycloak auth** — JWT-protected endpoints, users synced to local DB
- **React frontend** — search, results grid with cheapest badge, cart panel with total comparison
- **Anti-bot bypass** — headed Chrome + saved sessions for Blinkit and Instamart (Swiggy uses Datadome)

---

## 📁 Project Structure

```
bot-mart/
├── delivery-bot/
│   ├── app/
│   │   ├── scraper/
│   │   │   ├── base.py           # BaseScraper interface
│   │   │   ├── blinkit.py        # Blinkit scraper + fee scraping
│   │   │   ├── zepto.py          # Zepto scraper + fee scraping
│   │   │   ├── instamart.py      # Instamart scraper + fee scraping
│   │   │   └── fee_utils.py      # Shared fee parser utility
│   │   ├── cart/
│   │   │   └── router.py         # Cart CRUD + /cart/compare
│   │   ├── auth.py               # Keycloak JWT verification
│   │   ├── database.py           # SQLAlchemy engine + session
│   │   ├── models.py             # User, CartItem, PriceSnapshot, PlatformSession
│   │   └── main.py               # FastAPI app, CORS, /compare endpoint
│   ├── sessions/                 # Playwright auth cookies (gitignored)
│   │   ├── blinkit_auth.json
│   │   ├── swiggy_auth.json
│   │   └── zepto_auth.json
│   ├── generate_blinkit_session.py
│   ├── generate_swiggy_session.py
│   ├── generate_zepto_session.py
│   └── requirements.txt
├── frontend-react/               # React + Vite frontend
│   └── src/
│       ├── App.jsx               # Main UI: search, results, cart panel
│       ├── App.css               # Dark glassmorphic theme
│       └── services/api.js       # API client functions
└── README.md
```

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
git clone https://github.com/akapoor30/bot-mart.git
cd bot-mart

python3 -m venv venv
source venv/bin/activate
pip install -r delivery-bot/requirements.txt
playwright install chromium
```

### 2. Set up environment variables

Create `delivery-bot/.env`:

```env
KEYCLOAK_URL=http://localhost:8080/realms/bot-mart
DATABASE_URL=sqlite:///./botmart.db
```

### 3. Generate authenticated sessions

Scrapers need saved login sessions to bypass bot protection and add items to cart (for fee scraping).

```bash
cd delivery-bot

# Blinkit — opens Chrome, set your pincode, press Enter
python generate_blinkit_session.py

# Swiggy Instamart — opens Chrome, log in via OTP + set location, press Enter
python generate_swiggy_session.py

# Zepto — opens Chrome, log in via OTP + set location, press Enter
python generate_zepto_session.py
```

Sessions are saved to `sessions/` and are gitignored.

### 4. Start the backend API

```bash
cd delivery-bot
uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`.

### 5. Start the React frontend

```bash
cd delivery-bot/frontend-react
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`. Log in with your Keycloak account to use the app.

---

## 🔌 API Endpoints

### Core

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | ❌ | Health check |
| GET | `/api/me` | ✅ | Sync Keycloak user to local DB |
| GET | `/compare?item=X&pincode=Y` | ✅ | Run all 3 scrapers, return prices + fees |

### Cart

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/cart/` | ✅ | List cart items |
| POST | `/cart/add` | ✅ | Add item `{ search_query, quantity }` |
| DELETE | `/cart/{id}` | ✅ | Remove one item |
| DELETE | `/cart/` | ✅ | Clear entire cart |
| GET | `/cart/compare?pincode=Y` | ✅ | Compare full cart total across platforms |

### Sample `/compare` response

```json
{
  "query": "Maggi",
  "pincode": "560095",
  "cheapest_option": { "store": "Blinkit", "name": "Maggi Double Masala", "price": 20 },
  "all_results": [
    { "store": "Blinkit",   "price": 20, "delivery_fee": 0, "handling_fee": 4, "platform_fee": 0, "status": "success" },
    { "store": "Zepto",     "price": 50, "delivery_fee": 0, "handling_fee": 4, "platform_fee": 5, "status": "success" },
    { "store": "Instamart", "price": 60, "delivery_fee": 40, "handling_fee": 5, "platform_fee": 5, "status": "success" }
  ]
}
```

### Sample `/cart/compare` response

```json
{
  "cheapest_platform": "blinkit",
  "you_save": 24,
  "comparison": [
    { "platform": "blinkit",   "item_total": 95, "delivery_fee": 0, "handling_fee": 4, "grand_total": 99,  "complete_order": true },
    { "platform": "zepto",     "item_total": 74, "delivery_fee": 0, "handling_fee": 4, "grand_total": 83,  "complete_order": true },
    { "platform": "instamart", "item_total": 98, "delivery_fee": 40, "handling_fee": 5, "grand_total": 143, "complete_order": true }
  ]
}
```

---

## 🏗️ How Fee Scraping Works

Each scraper follows this flow:

1. Search for the product → extract price
2. Click **ADD** on the matched product card
3. Navigate to the platform's checkout page
4. Scrape the bill details section (delivery fee, handling fee, platform fee)
5. Remove the item from cart (cleanup)
6. Return the full result including real fees

Fee scraping is **non-fatal** — if it fails for any reason, the scraper returns successfully with fees defaulting to `0`.

---

## 🛡️ Anti-Bot Strategy

| Platform | Method |
|----------|--------|
| Blinkit | Headed Chrome (`channel="chrome"`) + saved session cookies |
| Zepto | Headless Chromium + `playwright-stealth` + saved session cookies |
| Instamart | Headed Chrome + saved session + auto-dismiss "Try Again" error boundary |

---

## 🗄️ Database Models

- **`User`** — synced from Keycloak on first login
- **`CartItem`** — per-user cart rows with `search_query` and quantity
- **`PriceSnapshot`** — cached price + fee data per platform per search query
- **`PlatformSession`** — (reserved) per-user Playwright session storage

---

## 📋 Roadmap

- [x] Blinkit scraper
- [x] Zepto scraper
- [x] Instamart scraper
- [x] FastAPI `/compare` endpoint
- [x] Keycloak JWT auth
- [x] Cart API with price snapshots
- [x] Cart total comparison across platforms
- [x] Real fee scraping from checkout pages
- [x] React frontend with cart panel
- [ ] Add-to-cart automation (click ADD on the winning platform)
- [ ] Price history & alerts