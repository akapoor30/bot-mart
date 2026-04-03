# app/scraper/blinkit.py
import asyncio
import os
import re
from playwright.async_api import async_playwright
from .base import BaseScraper
from .fee_utils import parse_fees_from_text

class BlinkitScraper(BaseScraper):
    async def search_product(self, product_name: str, pincode: str):
        async with async_playwright() as p:
            # headless=False with Chrome channel bypasses Datadome/Cloudflare better than stealth
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--window-position=-4001,0',   # Unique to Blinkit — used for targeted pkill
                    '--window-size=1280,900',
                ]
            )
            
            session_path = os.path.join(os.path.dirname(__file__), "../../sessions/blinkit_auth.json")
            if os.path.exists(session_path):
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    storage_state=session_path
                )
            else:
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                
            page = await context.new_page()

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
                
                matched_card = None
                product_name_found = None
                price_found = None

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
                    
                    matched_card = card
                    product_name_found = name
                    price_found = price
                    break
                
                if not matched_card:
                    await page.screenshot(path="tmp/blinkit_error.png")
                    return {"store": "Blinkit", "status": "failed", "error": "No matching products found"}
                
                # 5. Click the ADD button on the matched card to add to cart
                fees = {"delivery_fee": 0, "handling_fee": 0, "platform_fee": 0}
                matched_id = await matched_card.get_attribute("id")
                try:
                    # Use JS to find and click the ADD element inside this specific card
                    # The ADD element can be a div, span, or button — not always a <button>
                    click_result = await page.evaluate('''(cardId) => {
                        const card = document.querySelector('div[role="button"][id="' + cardId + '"]');
                        if (!card) return "card-not-found";
                        // Walk all child elements to find one with text "ADD"
                        const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
                        while (walker.nextNode()) {
                            if (walker.currentNode.textContent.trim() === "ADD") {
                                const el = walker.currentNode.parentElement;
                                el.click();
                                return "clicked-add";
                            }
                        }
                        return "add-not-found";
                    }''', matched_id)
                    print(f"Blinkit ADD click result: {click_result}")
                    
                    if click_result != "clicked-add":
                        print("Blinkit: ADD button not found on card (store may be closed)")
                    
                    # 6. Wait for add animation, then CLICK THE CART BUTTON to open sidebar
                    # Blinkit cart = green button next to search bar showing "N item(s) ₹X"
                    # MUST use Playwright native click (not JS el.click()) for React apps
                    await page.wait_for_timeout(2000)
                    
                    import re as _re
                    # Match "1 item" or "2 items" etc — the cart button text
                    cart_btn = page.get_by_text(_re.compile(r"\d+\s+items?"))
                    cart_count = await cart_btn.count()
                    print(f"Blinkit: found {cart_count} elements matching 'N item(s)'")
                    if cart_count > 0:
                        await cart_btn.first.click()
                        print("Blinkit: clicked cart button via Playwright locator")
                    else:
                        # Fallback: look for "My Cart"
                        my_cart = page.get_by_text("My Cart", exact=True)
                        if await my_cart.count() > 0:
                            await my_cart.click()
                            print("Blinkit: clicked 'My Cart' button")
                        else:
                            print("Blinkit: could not find cart button")
                    
                    # 7. Wait for cart sidebar to animate in
                    await page.wait_for_timeout(3000)
                    
                    # 7. Scrape "Bill details" section from the sidebar using JS
                    bill_text = await page.evaluate('''() => {
                        const all = document.querySelectorAll("div, section, aside");
                        for (const el of all) {
                            const t = el.innerText || "";
                            if (t.includes("Bill details") && (t.includes("charge") || t.includes("Grand total"))) {
                                if (t.length < 2000) return t;
                            }
                        }
                        for (const el of all) {
                            const t = el.innerText || "";
                            if (t.includes("Delivery charge") && t.length < 1000) return t;
                        }
                        return "";
                    }''')
                    
                    if bill_text:
                        fees = parse_fees_from_text(bill_text)
                        print(f"Blinkit fees scraped: {fees}")
                    else:
                        print("Blinkit: Bill details section not found in sidebar")
                    
                    # 8. Skip cart cleanup — btn.click() triggers a Blinkit cart API request
                    # that keeps Chrome alive and blocks browser.close() indefinitely.
                    
                except Exception as fee_err:
                    print(f"Blinkit fee scraping failed (non-fatal): {fee_err}")

                return {
                    "store": "Blinkit",
                    "name": product_name_found,
                    "price": price_found,
                    "delivery_fee": fees.get("delivery_fee", 0),
                    "handling_fee": fees.get("handling_fee", 0),
                    "platform_fee": fees.get("platform_fee", 0),
                    "gst_fee": fees.get("gst_fee", 0),
                    "status": "success"
                }

            except Exception as e:
                try:
                    await page.screenshot(path="tmp/blinkit_error.png")
                except Exception:
                    pass
                return {"store": "Blinkit", "status": "failed", "error": str(e)}
            finally:
                # browser.close() on headed Chrome can hang when Blinkit has pending cart
                # network requests or beforeunload handlers. Wrap with 5s timeout and
                # force-kill via pkill using --window-position=-4001 (unique to Blinkit).
                import subprocess
                try:
                    await asyncio.wait_for(browser.close(), timeout=5.0)
                except Exception:
                    subprocess.run(
                        ["pkill", "-9", "-f", "window-position=-4001"],
                        capture_output=True
                    )
                    print("Blinkit: force-killed stuck Chrome process")