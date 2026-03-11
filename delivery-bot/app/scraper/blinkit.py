# app/scraper/blinkit.py
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from .base import BaseScraper

class BlinkitScraper(BaseScraper):
    async def search_product(self, product_name: str, pincode: str):
        async with async_playwright() as p:
            # headless=False to watch the bot (change to True once stable)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            try:
                # 1. Go to Blinkit homepage
                await page.goto("https://blinkit.com", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                
                # 2. Click the search bar (it's a link to /s/, not a real input)
                search_link = await page.query_selector('a[href*="/s/"]')
                if search_link:
                    await search_link.click()
                    await page.wait_for_timeout(2000)
                
                # 3. Type into the real search input on the search page
                search_input = await page.query_selector('input')
                if not search_input:
                    return {"store": "Blinkit", "status": "failed", "error": "Search input not found"}
                
                await search_input.fill(product_name)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(5000)
                
                # 4. Get all product cards (they have numeric IDs)
                cards = await page.query_selector_all('div[role="button"][id]')
                
                # Loop through cards, parse each, pick the first whose name matches search term
                for card in cards:
                    card_id = await card.get_attribute('id')
                    if not card_id or not card_id.isdigit():
                        continue  # Skip non-product elements like "product_container"
                    
                    card_text = await card.inner_text()
                    lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                    
                    # Parse name and price from lines
                    name = None
                    price = None
                    for line in lines:
                        if 'MINS' in line or 'OFF' in line or line == 'ADD' or line == 'Ad':
                            continue
                        if '₹' in line and price is None:
                            price = int(''.join(filter(str.isdigit, line)))
                        elif name is None and '₹' not in line:
                            name = line
                    
                    # Skip if we couldn't parse, or name doesn't match the search term
                    if not name or price is None:
                        continue
                    if product_name.lower() not in name.lower():
                        continue  # This is an ad/sponsored product, skip it
                    
                    return {
                        "store": "Blinkit",
                        "name": name,
                        "price": price,
                        "status": "success"
                    }
                
                # No matching product found
                await page.screenshot(path="tmp/blinkit_error.png")
                return {"store": "Blinkit", "status": "failed", "error": "No matching products found"}

            except Exception as e:
                await page.screenshot(path="tmp/blinkit_error.png")
                return {"store": "Blinkit", "status": "failed", "error": str(e)}
            finally:
                await browser.close()