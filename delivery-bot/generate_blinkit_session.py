import asyncio
from playwright.async_api import async_playwright
import os

SESSION_FILE = os.path.join(os.path.dirname(__file__), "sessions", "blinkit_auth.json")

async def main():
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    print(f"Session will be saved to {SESSION_FILE}")
    
    async with async_playwright() as p:
        # Launch using the system's Google Chrome which is less likely to be blocked
        browser = await p.chromium.launch(headless=False, channel="chrome", args=['--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("Opening Blinkit...")
        await page.goto("https://blinkit.com/")
        
        print("\n*** ACTION REQUIRED ***")
        print("Please set your delivery location (e.g., specific pincode or address) in the browser popup.")
        print("Once the location is set correctly on the homepage,")
        print("press ENTER in this terminal to save the session and continue.")
        print("***********************\n")
        
        # Wait for user to press Enter in the terminal
        await asyncio.to_thread(input, "Press ENTER here when ready to save session...")
        
        print("Saving session...")
        await context.storage_state(path=SESSION_FILE)
        print("Session saved successfully!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
