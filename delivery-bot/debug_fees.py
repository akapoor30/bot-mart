"""
debug_fees.py — Run fee scraping for a single platform in isolation.
Shows exact errors and takes screenshots at each step.

IMPORTANT: Stores must be OPEN for fee scraping to work.
Blinkit/Zepto/Instamart dark stores typically operate 6 AM - 2 AM.
Running this at night will show closed stores with no ADD buttons.

Usage:
    cd delivery-bot
    source ../venv/bin/activate
    python debug_fees.py blinkit
    python debug_fees.py zepto
    python debug_fees.py instamart
"""
import asyncio
import sys
import os

async def debug_blinkit():
    from playwright.async_api import async_playwright
    from app.scraper.fee_utils import parse_fees_from_text

    print("\n=== BLINKIT FEE DEBUG ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, channel="chrome",
            args=['--disable-blink-features=AutomationControlled', '--window-size=1280,900']
        )
        session_path = "sessions/blinkit_auth.json"
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            storage_state=session_path if os.path.exists(session_path) else None
        )
        page = await context.new_page()

        try:
            print("1. Going to Blinkit search for Maggi...")
            await page.goto("https://blinkit.com/s/?q=maggi", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_blinkit_search.png")

            print("2. Finding product cards...")
            cards = await page.query_selector_all('div[role="button"][id]')
            print(f"   Found {len(cards)} cards")
            
            # Find first Maggi card with ADD button
            target_card = None
            target_id = None
            for card in cards:
                cid = await card.get_attribute('id')
                if not cid or not cid.isdigit():
                    continue
                text = await card.inner_text()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                print(f"   id={cid}: {lines[:5]}")
                if 'maggi' in text.lower() and 'ADD' in lines:
                    target_card = card
                    target_id = cid
                    print(f"   ✅ Found ADD-able Maggi card: id={cid}")
                    break
            
            if not target_card:
                print("   ❌ No Maggi card with ADD button found. Store may be CLOSED.")
                print("   Check the screenshot to see current store status.")
                input("\nPress ENTER to close...")
                await browser.close()
                return

            print(f"3. Clicking ADD button on card id={target_id}...")
            # Use locator API to click text="ADD" within this specific card
            card_locator = page.locator(f'div[role="button"][id="{target_id}"]')
            add_btn = card_locator.get_by_text("ADD", exact=True)
            count = await add_btn.count()
            print(f"   ADD button locator count: {count}")
            if count > 0:
                await add_btn.click()
                print("   ✅ Clicked ADD button")
            else:
                await target_card.click()
                print("   ⚠️ Fallback: clicked card")
            
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_blinkit_after_add.png")

            print("4. Clicking cart button to open sidebar...")
            # Blinkit cart button shows "1 item ₹20" in green next to search bar
            # MUST use Playwright native click (not JS) for React apps
            import re as _re
            cart_btn = page.get_by_text(_re.compile(r"\d+\s+items?"))
            cart_count = await cart_btn.count()
            print(f"   Found {cart_count} elements matching 'N item(s)'")
            if cart_count > 0:
                await cart_btn.first.click()
                print("   ✅ Clicked cart button")
            else:
                my_cart = page.get_by_text("My Cart", exact=True)
                if await my_cart.count() > 0:
                    await my_cart.click()
                    print("   ✅ Clicked 'My Cart'")
                else:
                    print("   ❌ Could not find cart button")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_blinkit_sidebar.png")

            print("5. Scraping 'Bill details' from sidebar via JS...")
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
                return "BILL SECTION NOT FOUND";
            }''')
            
            print(f"   Bill text:\n{bill_text[:400]}")
            fees = parse_fees_from_text(bill_text)
            print(f"   ✅ Fees parsed: {fees}")

        except Exception as e:
            print(f"ERROR: {e}")
            await page.screenshot(path="tmp/debug_blinkit_error.png")
        finally:
            input("\nPress ENTER to close browser...")
            await browser.close()


async def debug_instamart():
    from playwright.async_api import async_playwright
    from app.scraper.fee_utils import parse_fees_from_text

    print("\n=== INSTAMART FEE DEBUG ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, channel="chrome",
            args=['--disable-blink-features=AutomationControlled', '--window-size=1280,900']
        )
        session_path = "sessions/swiggy_auth.json"
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            storage_state=session_path if os.path.exists(session_path) else None
        )
        page = await context.new_page()
        try:
            print("1. Going to Instamart search for Maggi...")
            await page.goto("https://www.swiggy.com/instamart/search?query=maggi", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_instamart_search.png")

            print("2. Looking for ADD buttons...")
            add_btns = page.locator('div[aria-label="Add item to cart"]')
            count = await add_btns.count()
            print(f"   Found {count} ADD buttons")

            if count == 0:
                print("   ❌ No ADD buttons — store may be CLOSED or 'Try Again' error shown.")
                input("\nPress ENTER to close...")
                await browser.close()
                return

            print("3. Clicking first ADD button...")
            await add_btns.first.click()
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_instamart_after_add.png")

            print("4. Navigating to /instamart/cart...")
            await page.goto("https://www.swiggy.com/instamart/cart", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_instamart_cart.png")

            # Try clicking "View Detailed Bill" first
            view_bill = page.locator('text="View Detailed Bill"')
            if await view_bill.count() > 0:
                print("   Clicking 'View Detailed Bill'...")
                await view_bill.first.click()
                await page.wait_for_timeout(1500)

            print("5. Extracting fee section via JS (ignoring product price lines)...")
            bill_text = await page.evaluate('''() => {
                const all = document.querySelectorAll("div, section");
                for (const el of all) {
                    const t = el.innerText || "";
                    if ((t.includes("Delivery fee") || t.includes("Handling fee") || t.includes("Platform fee"))
                        && t.length < 1000 && !t.includes("quantity")) return t;
                }
                return "FEE SECTION NOT FOUND";
            }''')
            print(f"   Bill text:\n{bill_text[:400]}")
            fees = parse_fees_from_text(bill_text)
            print(f"   ✅ Fees parsed: {fees}")

        except Exception as e:
            print(f"ERROR: {e}")
            await page.screenshot(path="tmp/debug_instamart_error.png")
        finally:
            input("\nPress ENTER to close browser...")
            await browser.close()


async def debug_zepto():
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    from app.scraper.fee_utils import parse_fees_from_text

    print("\n=== ZEPTO FEE DEBUG ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        session_path = "sessions/zepto_auth.json"
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            storage_state=session_path if os.path.exists(session_path) else None
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        try:
            print("1. Going to Zepto search for Maggi...")
            await page.goto("https://www.zeptonow.com/search?query=maggi", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)
            await page.screenshot(path="tmp/debug_zepto_search.png")

            print("2. Finding product cards...")
            links = await page.query_selector_all('a[href*="/pn/"]')
            print(f"   Found {len(links)} product links")

            if not links:
                print("   ❌ No product cards found")
                input("\nPress ENTER to close...")
                await browser.close()
                return

            print("3. Clicking ADD button via JS...")
            result = await links[0].evaluate('''el => {
                const btn = el.querySelector("button");
                if (btn) { btn.click(); return "clicked: " + btn.textContent.trim(); }
                return "no button found";
            }''')
            print(f"   Result: {result}")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_zepto_after_add.png")

            # KEY FIX: Zepto cart opens as sidebar via ?cart=open on search page
            # NOT by navigating to /cart (that gives a 404)
            print("4. Opening cart sidebar via ?cart=open on search URL...")
            await page.goto("https://www.zeptonow.com/search?query=maggi&cart=open", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="tmp/debug_zepto_cart.png")

            print("5. Extracting 'Bill summary' from cart sidebar via JS...")
            bill_text = await page.evaluate('''() => {
                const all = document.querySelectorAll("div, section");
                for (const el of all) {
                    const t = el.innerText || "";
                    if (t.includes("Bill summary") && t.includes("Fee") && t.length < 1500) return t;
                }
                for (const el of all) {
                    const t = el.innerText || "";
                    if ((t.includes("Delivery Fee") || t.includes("Handling Fee")) && t.length < 800) return t;
                }
                return "BILL SECTION NOT FOUND";
            }''')
            print(f"   Bill text:\n{bill_text[:400]}")
            fees = parse_fees_from_text(bill_text)
            print(f"   ✅ Fees parsed: {fees}")

        except Exception as e:
            print(f"ERROR: {e}")
            await page.screenshot(path="tmp/debug_zepto_error.png")
        finally:
            input("\nPress ENTER to close browser...")
            await browser.close()


if __name__ == "__main__":
    platform = sys.argv[1] if len(sys.argv) > 1 else "blinkit"
    os.makedirs("tmp", exist_ok=True)
    if platform == "blinkit":
        asyncio.run(debug_blinkit())
    elif platform == "instamart":
        asyncio.run(debug_instamart())
    elif platform == "zepto":
        asyncio.run(debug_zepto())
    else:
        print("Usage: python debug_fees.py [blinkit|instamart|zepto]")
