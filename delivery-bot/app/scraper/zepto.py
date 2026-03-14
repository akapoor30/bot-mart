# app/scraper/zepto.py
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from .base import BaseScraper

class ZeptoScraper(BaseScraper):
    async def search_product(self, product_name: str, pincode: str):
        async with async_playwright() as p:
            # headless=False to watch the bot (change to True once stable)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            try:
                # 1. Go directly to Zepto search URL
                search_url = f"https://www.zeptonow.com/search?query={product_name}"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                
                # 2. Product cards are <a> links with href containing "/pn/"
                product_links = await page.query_selector_all('a[href*="/pn/"]')
                
                if not product_links:
                    await page.screenshot(path="tmp/zepto_error.png")
                    return {"store": "Zepto", "status": "failed", "error": "No products found"}
                
                # 3. Loop through cards, parse each, pick first matching the search term
                #    Card text format: "ADD\n₹price\n(₹oldprice)\n(₹X OFF)\nName\nWeight\nRating"
                for product_link in product_links:
                    card_text = await product_link.inner_text()
                    lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                    
                    name = None
                    price = None
                    
                    for line in lines:
                        if line == 'ADD' or 'OFF' in line:
                            continue
                        if '₹' in line and price is None:
                            price = int(''.join(filter(str.isdigit, line)))
                        elif price is not None and name is None and '₹' not in line and not line.startswith('('):
                            if line[0].isdigit() and ('.' in line or '(' in line):
                                continue
                            name = line
                    
                    # Skip if we couldn't parse, or name doesn't match
                    if not name or price is None:
                        continue
                    if product_name.lower() not in name.lower():
                        continue  # Sponsored/ad product, skip it
                    
                    return {
                        "store": "Zepto",
                        "name": name,
                        "price": price,
                        "status": "success"
                    }
                
                # No matching product found
                await page.screenshot(path="tmp/zepto_error.png")
                return {"store": "Zepto", "status": "failed", "error": "No matching products found"}

            except Exception as e:
                await page.screenshot(path="tmp/zepto_error.png")
                return {"store": "Zepto", "status": "failed", "error": str(e)}
            finally:
                await browser.close()
