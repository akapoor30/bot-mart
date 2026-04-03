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
                        # ── Step 0: Close any auto-opened cart drawer ──────────────────────────
                        # If the cart has leftover items from a previous run, Zepto auto-opens
                        # the Vaul drawer on page load. Close it with Escape BEFORE clicking ADD,
                        # to avoid the overlay blocking native Playwright pointer events.
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(800)

                        # ── Step 1: Add item via JS dispatchEvent ──────────────────────────────
                        # dispatchEvent(MouseEvent) triggers React synthetic events and bypasses
                        # any overlay that might still be present after the Escape above.
                        matched_href = await matched_link.get_attribute("href")
                        added = await page.evaluate('''(href) => {
                            const links = document.querySelectorAll('a[href*="/pn/"]');
                            for (const link of links) {
                                if (link.getAttribute("href") === href) {
                                    const btn = link.querySelector("button");
                                    if (btn) {
                                        btn.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, view: window}));
                                        return "dispatched";
                                    }
                                }
                            }
                            return "not-found";
                        }''', matched_href)
                        print(f"Zepto ADD dispatch result: {added}")

                        if added != "dispatched":
                            # Fallback: native click with a short timeout so we don't hang 30s
                            add_btn_el = await matched_link.query_selector("button")
                            if add_btn_el:
                                await add_btn_el.click(timeout=5000)

                        
                        # Zepto opens cart as a sidebar via ?cart=open on the CURRENT search page
                        # (navigating to /cart gives a 404 "egg-sit" error page)
                        search_url = f"https://www.zeptonow.com/search?query={product_name}&cart=open"
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                        
                        # Scrape the "Bill summary" section — pick the SMALLEST container
                        # with the bill heading + fee keywords (avoids hard size limits)
                        bill_text = await page.evaluate('''() => {
                            const all = Array.from(document.querySelectorAll("div, section"));
                            let best = null;
                            // Pass 1: smallest with Bill summary heading + fee keyword
                            for (const el of all) {
                                const t = (el.innerText || "").trim();
                                const hasHeading = t.includes("Bill summary") || t.includes("Bill Summary");
                                const hasFee = t.includes("Fee") || t.includes("Delivery");
                                if (hasHeading && hasFee && t.length > 20) {
                                    if (!best || t.length < best.length) best = t;
                                }
                            }
                            if (best) return best;
                            // Pass 2: smallest with both Delivery Fee and Handling Fee
                            for (const el of all) {
                                const t = (el.innerText || "").trim();
                                if ((t.includes("Delivery Fee") || t.includes("Handling Fee")) && t.length > 20) {
                                    if (!best || t.length < best.length) best = t;
                                }
                            }
                            if (best) return best;
                            return document.body.innerText || "";
                        }''')
                        
                        if bill_text:
                            fees = parse_fees_from_text(bill_text)
                            print(f"Zepto fees scraped: {fees}")
                        else:
                            print("Zepto: Bill summary not found in cart sidebar")
                        
                        # ── Step 3: Clean up cart ─────────────────────────────────────────────
                        # Navigate away from ?cart=open first to dismiss the Vaul drawer.
                        # On the search page (without cart=open), Zepto shows quantity controls
                        # (−/+) directly on the product card. We can JS-click the − button there.
                        await page.goto(
                            f"https://www.zeptonow.com/search?query={product_name}",
                            wait_until="domcontentloaded", timeout=15000
                        )
                        await page.wait_for_timeout(2000)
                        await page.keyboard.press("Escape")  # close drawer if re-opened
                        await page.wait_for_timeout(500)

                        removed = await page.evaluate('''() => {
                            // On search page, quantity chips show "−" button on each added item
                            const allBtns = document.querySelectorAll("button");
                            for (const btn of allBtns) {
                                const t = (btn.textContent || btn.innerText || "").trim();
                                if (t === "-" || t === "\u2212") {
                                    btn.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, view: window}));
                                    return true;
                                }
                            }
                            // Also try aria-label approach
                            const labeled = document.querySelector(
                                '[aria-label*="decrease" i], [aria-label*="remove" i], [aria-label*="minus" i]'
                            );
                            if (labeled) {
                                labeled.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, view: window}));
                                return true;
                            }
                            return false;
                        }''')
                        print(f"Zepto cart cleanup: {removed}")
                        if removed:
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
                    "gst_fee": fees.get("gst_fee", 0),
                    "status": "success"
                }

            except Exception as e:
                await page.screenshot(path="tmp/zepto_error.png")
                return {"store": "Zepto", "status": "failed", "error": str(e)}
            finally:
                await browser.close()
