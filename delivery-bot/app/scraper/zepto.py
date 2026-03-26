# app/scraper/zepto.py
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from .base import BaseScraper
from .fee_utils import parse_fees_from_text

class ZeptoScraper(BaseScraper):
    async def search_product(self, product_name: str, pincode: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # Load session if available (needed for fee scraping — adding to cart requires login)
            session_path = os.path.join(os.path.dirname(__file__), "../../sessions/zepto_auth.json")
            if os.path.exists(session_path):
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    storage_state=session_path
                )
            else:
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
                matched_link = None
                product_name_found = None
                price_found = None

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
                    
                    matched_link = product_link
                    product_name_found = name
                    price_found = price
                    break
                
                if not matched_link:
                    await page.screenshot(path="tmp/zepto_error.png")
                    return {"store": "Zepto", "status": "failed", "error": "No matching products found"}
                
                # 4. Scrape fees from cart (only possible with a logged-in session)
                fees = {"delivery_fee": 0, "handling_fee": 0, "platform_fee": 0}
                has_session = os.path.exists(session_path)

                if has_session:
                    try:
                        # Click the ADD button inside the matched product card via JavaScript
                        await matched_link.evaluate('''el => {
                            const btn = el.querySelector('button');
                            if (btn) btn.click();
                        }''')
                        await page.wait_for_timeout(3000)
                        
                        # Zepto opens cart as a sidebar via ?cart=open on the CURRENT search page
                        # (navigating to /cart gives a 404 "egg-sit" error page)
                        search_url = f"https://www.zeptonow.com/search?query={product_name}&cart=open"
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                        
                        # Scrape the "Bill summary" section from the cart sidebar
                        bill_text = await page.evaluate('''() => {
                            const all = document.querySelectorAll("div, section");
                            for (const el of all) {
                                const t = el.innerText || "";
                                // Zepto uses "Bill summary" as the heading
                                if (t.includes("Bill summary") && t.includes("Fee") && t.length < 1500) return t;
                            }
                            // Fallback: find any section with fee labels
                            for (const el of all) {
                                const t = el.innerText || "";
                                if ((t.includes("Delivery Fee") || t.includes("Handling Fee")) && t.length < 800) return t;
                            }
                            return "";
                        }''')
                        
                        if bill_text:
                            fees = parse_fees_from_text(bill_text)
                            print(f"Zepto fees scraped: {fees}")
                        else:
                            print("Zepto: Bill summary not found in cart sidebar")
                        
                        # Clear cart: remove the added item
                        minus_btn = await page.query_selector(
                            'button[aria-label*="decrease" i], button[aria-label*="remove" i], '
                            'button[class*="decrement" i], button[class*="remove" i]'
                        )
                        if minus_btn:
                            await minus_btn.click()
                            await page.wait_for_timeout(1000)

                    except Exception as fee_err:
                        print(f"Zepto fee scraping failed (non-fatal): {fee_err}")

                return {
                    "store": "Zepto",
                    "name": product_name_found,
                    "price": price_found,
                    "delivery_fee": fees.get("delivery_fee", 0),
                    "handling_fee": fees.get("handling_fee", 0),
                    "platform_fee": fees.get("platform_fee", 0),
                    "status": "success"
                }

            except Exception as e:
                await page.screenshot(path="tmp/zepto_error.png")
                return {"store": "Zepto", "status": "failed", "error": str(e)}
            finally:
                await browser.close()
