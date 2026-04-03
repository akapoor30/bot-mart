"""
fee_utils.py — Shared helpers for parsing cart/checkout fee breakdowns.

Usage:
    from app.scraper.fee_utils import parse_fees_from_text, extract_amount
"""
import re


def extract_amount(text: str) -> int:
    """
    Extract the fee amount from a string.
    Handles: ₹25, ₹ 25, FREE, ₹10 FREE (strikethrough = 0), ₹25.00
    Returns 0 if FREE or no amount found.
    """
    if "FREE" in text.upper():
        return 0
    match = re.search(r"₹\s*([\d,]+)", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return 0


# Lines that look like fee labels but are actually informational hints — skip them
_SKIP_PATTERNS = [
    "to avoid",           # "Add items worth ₹167 to avoid late night fee"
    "add items",          # "Add items worth ..."
    "add more",           # "Add more items ..."
    "savings on",
    "discount on",
    "saving on",
    "you saved",
    "get free delivery",
    "free delivery above",
    "orders above",       # "No small cart fee on orders above ₹99" (Instamart)
    "to avail",           # "Add items worth ₹185 to avail your Swiggy One Free Delivery"
    "no small cart",      # "No small cart fee on orders above ₹99"
    "minimum order",      # generic hint about minimum order amounts
    "worth ₹",            # any "worth ₹X" hint line not caught above
]


def _get_actual_amount(lines: list, i: int) -> int:
    """
    Get the ACTUAL (discounted) price for a fee label at line i.

    Handles three layouts:
      1. Amount on the SAME line as the label: "Small Cart Fee₹20.00"
      2. Amount on the NEXT line(s): "Handling Fee\\n₹12.76 ₹11.56"  -> last = 11
      3. FREE badge: returns 0

    Stops at hint/skip lines (e.g. 'No small cart fee on orders above ₹99')
    so we don't grab the hint's ₹ value instead of the real fee amount.
    """
    label_line = lines[i] if i < len(lines) else ""

    # Collect any inline ₹ amounts on the label line itself (used as fallback below)
    inline_amounts = re.findall(r"₹\s*([\d,]+)", label_line)

    amounts = []
    has_free = False
    j = i + 1
    while j < len(lines):
        t = lines[j].strip()
        if not t:
            j += 1
            continue
        tl = t.lower()

        # Stop if this is a known hint/informational line
        if any(pat in tl for pat in _SKIP_PATTERNS):
            break

        # A line that STARTS WITH LETTERS and also contains ₹ mid-sentence is a prose hint.
        # e.g. "No small cart fee on orders above ₹99"
        # Pure amount lines look like "₹20.00" or "₹12.76 ₹11.56"
        if "₹" in t and re.match(r"[A-Za-z]", t):
            break  # This is a hint sentence, stop before we grab its ₹ amount

        if "FREE" in t.upper():
            has_free = True
            j += 1
            continue

        m = re.search(r"₹\s*([\d,]+)", t)
        if m:
            amounts.append(int(m.group(1).replace(",", "")))
            j += 1
        else:
            break  # hit a non-amount line = next label

    if has_free:
        return 0
    if amounts:
        return amounts[-1]  # last value = discounted/actual price

    # Fallback: use the inline amount from the label line itself (e.g. "Small Cart Fee₹20.00")
    if inline_amounts:
        return int(inline_amounts[-1].replace(",", ""))

    return 0


def parse_fees_from_text(page_text: str) -> dict:
    """
    Scan the raw innerText of a cart/checkout page and pull out the key fees.
    Returns a dict: {delivery_fee, handling_fee, platform_fee, gst_fee} (int, default 0).

    Handles all platforms:
      - Blinkit:   "Delivery charge", "Handling charge", "Small cart charge"
      - Zepto:     "Delivery Fee", "Handling Fee", "Late Night Fee"
      - Instamart: "one Delivery Partner Fee", "Handling Fee", "Small Cart Fee",
                   "Late Night Fee", "GST and Charges"
    """
    fees = {"delivery_fee": 0, "handling_fee": 0, "platform_fee": 0, "gst_fee": 0}
    lines = [l.strip() for l in page_text.split("\n") if l.strip()]

    for i, line in enumerate(lines):
        low = line.lower()

        # Skip informational hint lines (contain fee keywords but aren't fee rows)
        if any(pat in low for pat in _SKIP_PATTERNS):
            continue

        # Identify which fee this line refers to
        fee_key = None
        additive = False

        if "late night" in low and "fee" in low:
            fee_key, additive = "delivery_fee", True   # Late night surcharge adds to delivery
        elif "rain" in low and "fee" in low:
            fee_key, additive = "delivery_fee", True   # Rain/surge fee
        elif "surge" in low and "fee" in low:
            fee_key, additive = "delivery_fee", True
        elif "delivery" in low and ("fee" in low or "charge" in low or "partner" in low):
            fee_key, additive = "delivery_fee", False
        elif "handling" in low:
            fee_key, additive = "handling_fee", False
        elif "platform fee" in low or "convenience" in low:
            fee_key, additive = "platform_fee", False
        elif "small cart" in low or "small order" in low:
            fee_key, additive = "platform_fee", True   # Small Cart Fee adds to platform
        elif "gst" in low:
            fee_key, additive = "gst_fee", True        # GST and Charges -> its own column

        if fee_key is None:
            continue

        # Get the actual amount (handles crossed-out prices, FREE badges, inline amounts)
        amount = _get_actual_amount(lines, i)

        if additive:
            fees[fee_key] += amount
        else:
            fees[fee_key] = amount

    return fees
