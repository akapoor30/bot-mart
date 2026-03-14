# Instamart Scraper Fixes

This document outlines the specific changes and strategies implemented to fix the Swiggy Instamart scraper so that it can successfully bypass bot detection and extract product data.

## 1. Bypassing Datadome Bot Protection
Swiggy uses Datadome to block automated browsers. We encountered "Something went wrong" pages immediately upon navigation.
*   **Fix:** We load the authenticated user session cookies (`sessions/swiggy_auth.json`) into the Playwright context so that the browser appears as a logged-in human user.
*   **Fix:** We changed the Playwright launch configuration from `headless=True` to `headless=False` with `channel="chrome"` and `args=['--disable-blink-features=AutomationControlled']`. Datadome easily flags headless Chromium, but headed Google Chrome with the automation flags disabled passes the checks.
*   **Fix:** We removed the `playwright-stealth` plugin, as explicitly using it with headed Chrome was actually triggering detection rather than preventing it.

## 2. Handling the "Try Again" Error Boundary
Even with a valid session and headed Chrome, Swiggy deliberately throws a "Something went wrong!" error page *after* the initial search query is submitted, acting as a secondary Turing test.
*   **Fix:** Added logic to explicitly wait for and detect the "Try Again" button. If the button appears, the script clicks it and waits for the search results to load normally.

## 3. Dismissing Onboarding Overlays
Sometimes an onboarding tooltip ("Refine results by filtering down...") with a "Got it!" button appears. This tooltip creates a massive overlay that intercepts clicks and occasionally prevents the DOM from rendering product cards properly.
*   **Fix:** Added dynamic checks to locate the "Got it!" text and dismiss the tooltip before attempting to parse the search results.

## 4. Robust Product Data Extraction
The original scraper relied on specific CSS locators (`div._3zZNZ`, `div._2OAaO`, etc.) that were either broken or rendered dynamically with random class names. Additionally, simply finding `data-testid="item-card"` elements was unreliable depending on the specific search result view.
*   **Fix:** Implemented a robust fallback parser that searches for the universal "Add item to cart" buttons (`div[aria-label="Add item to cart"]`).
*   **Fix:** We use Playwright's `locator.evaluate()` to inject a JavaScript function that walks up the DOM tree from the "ADD" button (up to 6 levels) to find the parent product container.
*   **Fix:** The JavaScript function splits the raw `innerText` of the container into lines, applies Regex to cleanly extract the price (handling both `₹58` and plain `58` formats), and uses heuristics to reliably determine the product name (longest string excluding weights, discounts, and UI text) and weight.
*   **Fix:** Added filtering to ignore promotional items or sections labeled "Previously Bought" or "Sponsored" to ensure we only scrape genuine search results.
