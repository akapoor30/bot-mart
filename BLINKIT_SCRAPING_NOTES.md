# Blinkit Cart Fee Scraping — How It Was Solved

## Problem
Scraper could find products and prices, but couldn't fetch the fee breakdown (Delivery charge, Handling charge, etc.) from the cart sidebar.

---

## Why It Was Hard

### 1. Cart sidebar doesn't open automatically
Clicking the **ADD** button on a product card silently adds the item and updates a badge counter. The sidebar with **Bill details** only opens when you explicitly **click the green cart button** in the header.

### 2. JS `el.click()` doesn't work on React apps
The first attempts used `page.evaluate()` to find the cart element and call `el.click()` via JavaScript. This found the element but the sidebar never opened.

**Root cause:** Blinkit is a React app. React's event system uses **synthetic events** that sit on top of native DOM events. JavaScript's `el.click()` doesn't dispatch the right event type — React ignores it.

**Fix:** Use **Playwright's native `.click()`** which dispatches real pointer events that React's synthetic event system picks up correctly.

### 3. Cart button selector was wrong
Earlier attempts searched for elements with `"Cart"` text or `"₹"` alone in the header. The actual cart button contains text like `"1 item"` — paired with a price in a child element.

The correct pattern to match is **`\d+ items?`** (e.g. "1 item", "2 items").

### 4. ADD button is a `div`, not a `button`
The product card ADD element is a custom `div`, not a `<button>`. `query_selector('button')` inside the card returns `None`. The fix was to use a **JS TreeWalker** to scan all text nodes inside the card and click the parent of the node with text `"ADD"`.

---

## Final Working Solution

```python
# Step 1: Click ADD using JS TreeWalker (works for any element type)
click_result = await page.evaluate('''(cardId) => {
    const card = document.querySelector('div[role="button"][id="' + cardId + '"]');
    const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        if (walker.currentNode.textContent.trim() === "ADD") {
            walker.currentNode.parentElement.click();
            return "clicked-add";
        }
    }
    return "add-not-found";
}''', matched_id)

# Step 2: Click the green cart button using Playwright native click
import re
cart_btn = page.get_by_text(re.compile(r"\d+\s+items?"))  # "1 item", "2 items"
await cart_btn.first.click()  # native Playwright click → triggers React events

# Step 3: Scrape Bill details from sidebar using JS evaluate
bill_text = await page.evaluate('''() => {
    const all = document.querySelectorAll("div, section, aside");
    for (const el of all) {
        const t = el.innerText || "";
        if (t.includes("Bill details") && (t.includes("charge") || t.includes("Grand total"))) {
            if (t.length < 2000) return t;
        }
    }
    return "";
}''')
```

---

## Fee Labels on Blinkit

| Label in DOM | Maps to |
|---|---|
| `Delivery charge` | `delivery_fee` |
| `Handling charge` | `handling_fee` |
| `Small cart charge` | `platform_fee` (surcharge for small orders) |

Note: Blinkit says **"charge"** not "fee" — `fee_utils.py` handles both.

`FREE` is shown as text (not ₹0) — `extract_amount()` checks for `"FREE"` first and returns `0`.

---

## Key Files
- `app/scraper/blinkit.py` — the scraper
- `app/scraper/fee_utils.py` — shared fee text parser
- `debug_fees.py` — standalone debug script (`python debug_fees.py blinkit`)
