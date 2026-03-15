# 🛒 Delivery Bot (Bot-Mart)

Delivery Bot is an automated quick commerce aggregator that searches for products across India's top rapid delivery platforms: **Blinkit**, **Zepto**, and **Swiggy Instamart**. It compares prices in real-time and identifies the cheapest option for your specific pincode.

## ✨ Features

- **Multi-Platform Scraping**: Concurrently searches Blinkit, Zepto, and Instamart using Playwright.
- **Anti-Bot Bypass**: Uses headed Chrome and authenticated browser sessions to bypass strict bot-protection systems like Datadome (Swiggy).
- **Session-Based Location**: Saves your delivery location context so the scrapers can easily find area-specific pricing without manual intervention on every run.
- **FastAPI Orchestrator**: A lightweight backend API (`/compare`) that runs the scrapers in asyncio parallel threads.
- **Premium Glassmorphic UI**: A beautifully designed Vanilla HTML/CSS/JS frontend to interact with the bot without using the terminal or cURL.

## 🚀 Getting Started

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/akapoor30/bot-mart.git
cd bot-mart

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install
```

### 2. Generate Authenticated Sessions (Crucial for Instamart & Blinkit)
Both Instamart and Blinkit require to know your location, and Swiggy actively blocks headless bots. To fix this, we generate real authenticated sessions:

```bash
cd delivery-bot

# 1. Generate Blinkit Session (Set your location)
python generate_blinkit_session.py
# (Wait for browser, set your pincode, return to terminal and press Enter)

# 2. Generate Swiggy Session (Log in & Set location)
python generate_swiggy_session.py
# (Wait for browser, log in via OTP, set your location, return to terminal and press Enter)
```

### 3. Start the Backend API

```bash
uvicorn app.main:app --reload
```
The FastAPI server will start at `http://127.0.0.1:8000`.

### 4. Open the UI Dashboard
With the Uvicorn server running, navigate to the `frontend/` folder in your file explorer and double-click `index.html` to open it in your browser. Enter a product name and your pincode, and the bot will orchestrate the scraping in real-time!

## 🧪 API Endpoints

- `GET /` : Health check.
- `GET /compare?item=<Product>&pincode=<Pincode>` : Runs all three scrapers simultaneously and returns a JSON payload containing the cheapest option and all results.

## 📁 Repository Structure
- `/delivery-bot/app/main.py`: The FastAPI Orchestrator.
- `/delivery-bot/app/scraper/`: Contains `blinkit.py`, `zepto.py`, `instamart.py`.
- `/delivery-bot/sessions/`: Where your `blinkit_auth.json` and `swiggy_auth.json` cookies are stored.
- `/frontend/`: Contains the Vanilla Web UI (`index.html`, `style.css`, `app.js`).
- `/delivery-bot/flow.md`: Detailed breakdown of parallel scraping logic.
- `instamart_fix.md`: Technical explanation of Swiggy Anti-bot bypasses.


# 🛒 Bot-Mart v2 — Auth + Smart Cart

## What's New in v2

- ✅ **JWT Authentication** — Register, login, refresh tokens, protected routes
- ✅ **Per-user Cart** — Items stored in DB per user with price snapshots
- ✅ **Cart Total Comparison** — Compare full cart cost across all platforms including all fees
- ✅ **Role-based Access** — `user` and `admin` roles
- ✅ **SQLite DB** — Zero-config local DB (swap to PostgreSQL for production)

---

## Project Structure

```
bot-mart/
├── delivery-bot/
│   ├── app/
│   │   ├── auth/
│   │   │   ├── router.py       # /auth/register, /auth/login, /auth/refresh, /auth/me
│   │   │   └── utils.py        # JWT encode/decode, bcrypt hashing
│   │   ├── cart/
│   │   │   └── router.py       # /cart/, /cart/add, /cart/{id}, /cart/compare/totals
│   │   ├── database.py         # SQLAlchemy engine + session
│   │   ├── models.py           # User, CartItem, PriceSnapshot ORM models
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   └── main.py             # FastAPI app + CORS + router registration
│   └── requirements.txt
└── frontend/
    ├── index.html              # Auth modals + search + cart sidebar
    ├── style.css               # Glassmorphic dark UI
    └── app.js                  # Auth flow + search + cart logic
```

---

## Setup

### 1. Install dependencies

```bash
cd delivery-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

### 2. Start the API

```bash
uvicorn app.main:app --reload
```

The DB (`botmart.db`) is created automatically on first run.

### 3. Open the frontend

Open `frontend/index.html` in your browser.

---

## API Endpoints

### Auth
| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| POST | `/auth/register` | ❌ | Create account |
| POST | `/auth/login` | ❌ | Login, get tokens |
| POST | `/auth/refresh` | ❌ | Refresh access token |
| GET | `/auth/me` | ✅ | Get current user |

### Compare
| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| GET | `/compare?item=X&pincode=Y` | ✅ | Compare prices across platforms |

### Cart
| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| GET | `/cart/` | ✅ | Get all cart items |
| POST | `/cart/add` | ✅ | Add item (auto-fetches prices) |
| DELETE | `/cart/{id}` | ✅ | Remove one item |
| DELETE | `/cart/` | ✅ | Clear cart |
| GET | `/cart/compare/totals` | ✅ | Compare full cart total by platform |

---

## Cart Comparison Logic

When you call `GET /cart/compare/totals`, the API:

1. Fetches all your cart items and their saved price snapshots
2. For each platform (Blinkit, Zepto, Instamart):
   - Sums all item prices × quantities
   - Adds delivery/handling/platform fees **once** (as a single order)
3. Returns sorted results (cheapest first) + how much you save vs the most expensive option

---

## Connecting Your Scrapers

In `app/cart/router.py`, the `fetch_prices()` function calls your existing `/compare` endpoint.
In `app/main.py`, replace the stub in `/compare` with your actual scraper calls:

```python
from app.scraper.blinkit import scrape_blinkit
from app.scraper.zepto import scrape_zepto
from app.scraper.instamart import scrape_instamart

results = await asyncio.gather(
    scrape_blinkit(item, pincode),
    scrape_zepto(item, pincode),
    scrape_instamart(item, pincode),
    return_exceptions=True
)
```

Make sure each scraper returns a dict with these keys:
```python
{
    "platform": "Blinkit",
    "price": 68.0,           # item price
    "delivery_fee": 0.0,
    "handling_fee": 4.0,
    "platform_fee": 3.0,
    "surge_fee": 0.0,
    "delivery_time": "8 min"
}
```

---

## Production Checklist

- [ ] Replace `SECRET_KEY` in `auth/utils.py` with an env variable
- [ ] Switch SQLite → PostgreSQL (`DATABASE_URL` in `database.py`)
- [ ] Set `allow_origins` in CORS to your actual frontend domain
- [ ] Run behind HTTPS (use nginx + certbot or a managed host)