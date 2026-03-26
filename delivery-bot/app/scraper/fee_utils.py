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
    # If "FREE" appears ANYWHERE in the text, the fee is 0 (even if ₹X precedes it)
    # This handles Zepto's "₹10 FREE" (strikethrough original, actual = free)
    if "FREE" in text.upper():
        return 0
    match = re.search(r"₹\s*([\d,]+)", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return 0


def parse_fees_from_text(page_text: str) -> dict:
    """
    Scan the raw innerText of a cart/checkout page and pull out the key fees.
    Returns a dict with keys: delivery_fee, handling_fee, platform_fee (all int, default 0).
    
    Handles naming variations across platforms:
      - Blinkit: "Delivery charge", "Handling charge"
      - Zepto:   "Delivery Fee", "Handling Fee", "Late Night Fee"
      - Instamart: "Delivery fee", "Handling fee", "Platform fee"
    """
    fees = {"delivery_fee": 0, "handling_fee": 0, "platform_fee": 0}
    lines = [l.strip() for l in page_text.split("\n") if l.strip()]

    for i, line in enumerate(lines):
        low = line.lower()

        # Skip lines that are clearly not fee lines
        if low.startswith("savings on") or low.startswith("discount"):
            continue

        # Grab amount from this line. If label-only line, check the next line too.
        amount = extract_amount(line)
        if amount == 0 and "FREE" not in line.upper() and i + 1 < len(lines):
            amount = extract_amount(lines[i + 1])

        # Match fee keywords (both "fee" and "charge" naming conventions)
        is_delivery = ("delivery" in low) and ("fee" in low or "charge" in low)
        is_handling = ("handling" in low) and ("fee" in low or "charge" in low or True)
        is_platform = ("platform fee" in low or "convenience" in low)
        is_late_night = ("late night" in low) and ("fee" in low)
        is_small_cart = ("small cart" in low or "small order" in low) and ("charge" in low or "fee" in low or "surcharge" in low or True)

        if is_delivery:
            fees["delivery_fee"] = amount
        elif is_handling:
            fees["handling_fee"] = amount
        elif is_platform:
            fees["platform_fee"] = amount
        elif is_late_night:
            # Late night fee (Zepto) — add to delivery_fee since it's a surcharge
            fees["delivery_fee"] += amount
        elif is_small_cart:
            # Small cart charge (Blinkit) — add to platform_fee
            fees["platform_fee"] += amount

    return fees
