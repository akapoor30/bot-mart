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
