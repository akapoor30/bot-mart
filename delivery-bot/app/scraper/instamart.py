import asyncio
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from .base import BaseScraper
import re

class InstamartScraper(BaseScraper):
    async def search_product(self, product_name: str, pincode: str):
        async with async_playwright() as p:
            # Datadome blocks headless chromium. Must use visible Chrome.
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--window-position=-3000,0',   # Move off-screen so user doesn't see it
                    '--window-size=1280,900',
                ]
            )
            
            # Load the authenticated session
            session_path = os.path.join(os.path.dirname(__file__), "../../sessions/swiggy_auth.json")
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
            # Do not use Stealth with headed Chrome, it can cause detection
            
            try:
                # 1. Navigate to Instamart (Location is already set from session)
                await page.goto("https://www.swiggy.com/instamart", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Check for location prompt just in case it wasn't saved perfectly
                loc_box = page.locator("div._22d3o[role='button']")
                if await loc_box.count() > 0:
                    text_content = await loc_box.first.inner_text()
                    if "Setup your precise location" in text_content or "Location" in text_content:
                        # Fallback to manual location setting if needed
                        await loc_box.first.click()
                        await page.wait_for_timeout(1000)
                        
                        search_area = page.locator('div:has-text("Search for an area or address")').last
                        if await search_area.count() > 0:
                            await search_area.click()
                            await page.wait_for_timeout(2000)
                            
                            real_input = page.get_by_placeholder("Search for area, street name…")
                            if await real_input.count() > 0:
                                await real_input.first.fill(pincode)
                            else:
                                await page.keyboard.type(pincode)
                                
                            await page.wait_for_timeout(3000)
                            
                            # Try to click the first suggestion
                            suggestion = page.get_by_text(pincode, exact=False).last
                            if await suggestion.count() > 0:
                                try:
                                    await suggestion.click(timeout=3000)
                                except:
                                    await page.keyboard.press("ArrowDown")
                                    await page.wait_for_timeout(500)
                                    await page.keyboard.press("Enter")
                            else:
                                # Fallback
                                await page.keyboard.press("ArrowDown")
                                await page.wait_for_timeout(500)
                                await page.keyboard.press("Enter")
                            
                            await page.wait_for_timeout(3000)
                            
                            # check confirm location
                            confirm_btn = page.get_by_role("button", name="Confirm Location")
                            if await confirm_btn.count() > 0:
                                await confirm_btn.first.click()
                                await page.wait_for_timeout(3000)
                            else:
                                confirm_text = page.locator("text=Confirm location")
                                if await confirm_text.count() > 0:
                                    await confirm_text.first.click()
                                    await page.wait_for_timeout(3000)

                search_area = page.locator('div[data-testid="search-banner"], div:has-text("Search for")')
                if await search_area.last.count() > 0:
                    await search_area.last.click()
                    await page.wait_for_timeout(2000)
                    
                    real_input = page.locator('input[data-testid="search-plugin-input"], input[type="text"], input[type="search"]')
                    if await real_input.first.count() > 0:
                        await real_input.first.fill(product_name)
                    else:
                        await page.keyboard.type(product_name)
                        
                    await page.wait_for_timeout(2000)
                    await page.keyboard.press("Enter")
                    
                    # Wait for search results container or onboarding popups
                    await page.wait_for_timeout(3000)
                    
                    # Dismiss the onboarding popup "Refine results by filtering down..."
                    # It creates a massive overlay block that prevents the DOM from rendering cards sometimes
                    got_it = page.get_by_text("Got it!")
                    if await got_it.count() > 0:
                        try:
                            await got_it.first.click(timeout=2000)
                            await page.wait_for_timeout(2000)
                        except:
                            pass
                            
                    # Swiggy has an anti-bot check that throws a "Something went wrong" page on the first search
                    try_again = page.get_by_text("Try Again")
                    if await try_again.count() > 0:
                        print("Hit Swiggy search error boundary, clicking Try Again...")
                        await try_again.first.click()
                        await page.wait_for_timeout(4000)
                        
                        # Sometimes another "Got it" appears after retry
                        if await got_it.count() > 0:
                            try:
                                await got_it.first.click(timeout=1000)
                            except:
                                pass
                        
                    try:
                        # Wait for the item cards to appear
                        await page.wait_for_selector('div[aria-label="Add item to cart"], div[data-testid="item-card"]', timeout=15000)
                    except Exception as e:
                        print(f"Warning: Timeout waiting for item cards: {e}")
                        
                    await page.wait_for_timeout(3000)
                    
                    # Main extraction blocks
                    product_cards = page.locator('div[data-testid="item-card"]')
                    count = await product_cards.count()
                    
                    if count == 0:
                        # Fallback: Find cards by walking up from the ADD buttons
                        add_btns = page.locator('div[aria-label="Add item to cart"]')
                        count = await add_btns.count()
                        print(f"Fallback: Found {count} ADD buttons")
                        
                        if count == 0:
                            with open("/tmp/instamart_search_err.html", "w") as f:
                                f.write(await page.content())
                            return {"store": "Instamart", "status": "failed", "error": "No products found"}
                        
                        # Process using the fallback method (walking up the DOM)
                        results = []
                        for i in range(min(count, 5)):
                            btn = add_btns.nth(i)
                            try:
                                # A much simpler, less brittle Javascript evaluation for Instamart
                                product_data = await btn.evaluate('''el => {
                                    // Go up exactly to the main product card container level usually 5-7 levels up
                                    let container = el;
                                    for(let i=0; i<6; i++) {
                                        if(container.parentElement) container = container.parentElement;
                                    }
                                    
                                    const text = container.innerText || "";
                                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                                    
                                    let name = "Unknown";
                                    let price = 0;
                                    let weight = "";
                                    let is_ad = false;
                                    
                                    if (text.includes("Ad\\n") || text.includes("Sponsored\\n")) return {is_ad: true};
                                    
                                    // Price might have Rupee symbol or just be a bare number at the end
                                    const priceMatches = text.match(/₹[\\d,]+/g);
                                    if (priceMatches && priceMatches.length > 0) {
                                        price = parseInt(priceMatches[0].replace(/[^0-9]/g, ''));
                                    } else {
                                        // Try finding the last number that isn't connected to a weight unit
                                        let reversed = [...lines].reverse();
                                        for (let line of reversed) {
                                            if (/^\\d+$/.test(line)) {
                                                price = parseInt(line);
                                                break;
                                            }
                                        }
                                    }
                                    
                                    for (let line of lines) {
                                        if (line.length > 5 && !line.includes('₹') && !line.includes('MINS') && line !== 'ADD' && !line.includes('OFF') && line !== 'Ad' && line !== 'Sponsored' && !line.toLowerCase().includes('previously bought') && !line.toLowerCase().includes('explore more')) {
                                            name = line;
                                            break;
                                        }
                                    }
                                    
                                    for (let line of lines) {
                                        if (line.endsWith(' g') || line.endsWith(' kg') || line.endsWith(' ml') || line.endsWith(' L')) {
                                            weight = line;
                                            break;
                                        }
                                    }
                                    
                                    return {name, price, weight, is_ad: false, debug_text: text};
                                }''')
                                
                                if not product_data or product_data.get('is_ad'):
                                    continue
                                    
                                print(f"Parsed Card: {product_data}")
                                
                                if product_data.get('name') != "Unknown" and product_data.get('price') > 0:
                                    results.append({
                                        "name": product_data['name'],
                                        "price": product_data['price'],
                                        "weight": product_data['weight'],
                                        "store": "Instamart",
                                        "in_stock": True
                                    })
                                    
                            except Exception as e:
                                print(f"Error parsing Instamart fallback card {i}: {e}")
                                
                        if results:
                            return {
                                "store": "Instamart",
                                "name": results[0]["name"],
                                "price": results[0]["price"],
                                "status": "success"
                            }
                        return {"store": "Instamart", "status": "failed", "error": "No matching products found"}
                    
                    print(f"Found {count} products on Instamart")
                    
                    if count == 0:
                        with open("/tmp/instamart_search_err.html", "w") as f:
                            f.write(await page.content())
                        return {"store": "Instamart", "status": "failed", "error": "No products found"}

                    results = []
                    for i in range(min(count, 5)):
                        card = product_cards.nth(i)
                        try:
                            card_text = await card.inner_text()
                            lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                            
                            name = "Unknown"
                            weight = ""
                            price_num = 0
                            
                            # Ad check
                            is_ad = False
                            for line in lines:
                                if line == "Ad" or line == "Sponsored":
                                    is_ad = True
                                    break
                            if is_ad:
                                continue
                                
                            for line in lines:
                                if len(line) > 10 and not line.startswith("₹") and "OFF" not in line and "MINS" not in line and "ADD" not in line:
                                    name = line
                                    break
                                    
                            prices = [line.replace('₹', '').replace(',', '').strip() for line in lines if line.startswith('₹')]
                            if prices:
                                try:
                                    price_num = float(prices[0])
                                except:
                                    pass
                                    
                            for line in lines:
                                if " g" in line or " kg" in line or " ml" in line or " L" in line or " pc" in line:
                                    weight = line
                                    break

                            results.append({
                                "name": name,
                                "price": price_num,
                                "weight": weight,
                                "store": "Instamart",
                                "in_stock": True
                            })
                        except Exception as e:
                            print(f"Error parsing Instamart card {i}: {e}")

                    if results:
                        # Return the first one matching the old format
                        return {
                            "store": "Instamart",
                            "name": results[0]["name"],
                            "price": results[0]["price"],
                            "status": "success"
                        }
                    
                    return {"store": "Instamart", "status": "failed", "error": "No matching products found"}

            except Exception as e:
                await page.screenshot(path="tmp/instamart_error.png")
                return {"store": "Instamart", "status": "failed", "error": str(e)}
            finally:
                await browser.close()
