"""
generate_zepto_session.py
Run this once to log in to Zepto manually and save the session cookies.
The session is needed for the fee scraper to add items to cart and see checkout fees.

Usage:
    cd delivery-bot
    source ../venv/bin/activate
    python generate_zepto_session.py
"""
import asyncio
from playwright.async_api import async_playwright
import os

SESSION_FILE = os.path.join(os.path.dirname(__file__), "sessions", "zepto_auth.json")

async def main():
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    print(f"Session will be saved to: {SESSION_FILE}")
    
    async with async_playwright() as p:
        # Use visible Chrome so you can log in manually
        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("Opening Zepto...")
        await page.goto("https://www.zeptonow.com/")
        
        print("\n*** ACTION REQUIRED ***")
        print("1. Log in to Zepto using your phone number and OTP.")
        print("2. Make sure your delivery location/pincode is set.")
        print("3. Once you can see the Zepto homepage with products,")
        print("   press ENTER in this terminal to save the session.")
        print("***********************\n")
        
        await asyncio.to_thread(input, "Press ENTER when ready to save session...")
        
        print("Saving session...")
        await context.storage_state(path=SESSION_FILE)
        print(f"✅ Session saved to {SESSION_FILE}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
