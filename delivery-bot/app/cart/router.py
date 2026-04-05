from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CartItem, PriceSnapshot, PlatformName
from app.auth import get_current_user
from app.models import User
from pydantic import BaseModel

router = APIRouter(prefix="/cart", tags=["cart"])

class AddItemRequest(BaseModel):
    search_query: str   # The original user query, e.g. "milk"
    quantity: int = 1


# ── Fee threshold rules ───────────────────────────────────────────────────────
# Each platform removes delivery/platform fees when the cart total crosses
# certain thresholds. These rules are approximate and change over time.
# The scraper captures fees for SINGLE-ITEM carts; for multi-item carts we
# adjust using these thresholds so the comparison stays accurate.
#
# Rules observed (April 2025):
#   Blinkit  : delivery free at ₹199+; handling ₹2 always
#   Zepto    : delivery free at ₹200+
#   Instamart: delivery free at ₹250+ (or always free with Swiggy ONE)
#              small-cart platform fee (₹20) removed at ₹99+
#              handling fee (~₹11) always applied; GST scales down with other fees
_FEE_THRESHOLDS = {
    "blinkit": {
        "delivery_free_above":  199,   # ₹199+ → free delivery
        "platform_free_above":  None,  # no platform-fee threshold for Blinkit
    },
    "zepto": {
        "delivery_free_above":  200,
        "platform_free_above":  None,
    },
    "instamart": {
        "delivery_free_above":  200,   # free delivery above ₹200 (Swiggy ONE subscription)
        "platform_free_above":  99,    # small-cart fee removed above ₹99
    },
}


def _adjust_fees(platform_name: str, item_total: int,
                 delivery_fee: int, handling_fee: int,
                 platform_fee: int, gst_fee: int) -> dict:
    """
    Given the combined item_total for a platform, zero out fees that the
    platform waives above their threshold.  GST is proportionally reduced
    (if delivery+platform become ₹0, GST halves as an approximation).
    """
    rules = _FEE_THRESHOLDS.get(platform_name, {})

    # Delivery threshold
    delivery_free_above = rules.get("delivery_free_above")
    if delivery_free_above is not None and item_total >= delivery_free_above:
        delivery_fee = 0

    # Platform / small-cart-fee threshold
    platform_free_above = rules.get("platform_free_above")
    if platform_free_above is not None and item_total >= platform_free_above:
        platform_fee = 0

    # GST is charged on the fees themselves.
    # If all chargeable fees (delivery + platform) are now ₹0, GST → 0.
    # If only some are removed, keep GST as-is (small rounding error is acceptable).
    waivable = delivery_fee + platform_fee
    if waivable == 0:
        gst_fee = 0

    return {
        "delivery_fee": delivery_fee,
        "handling_fee": handling_fee,
        "platform_fee": platform_fee,
        "gst_fee": gst_fee,
    }


# ── GET /cart/ ──────────────────────────────────────────────────────────────
@router.get("/")
async def list_cart(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.keycloak_id == current_user["keycloak_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Call /api/me first.")
    items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    return {
        "user": current_user["email"],
        "cart": [
            {"id": i.id, "search_query": i.search_query, "product_name": i.product_name, "quantity": i.quantity}
            for i in items
        ]
    }

# ── POST /cart/add ───────────────────────────────────────────────────────────
@router.post("/add")
async def add_to_cart(
    body: AddItemRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.keycloak_id == current_user["keycloak_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Call /api/me first.")

    query = body.search_query.lower().strip()

    existing = db.query(CartItem).filter(
        CartItem.user_id == user.id,
        CartItem.search_query == query
    ).first()
    if existing:
        existing.quantity += body.quantity
        db.commit()
        db.refresh(existing)
        return {"message": "Quantity updated", "item": {"id": existing.id, "search_query": existing.search_query, "quantity": existing.quantity}}

    item = CartItem(user_id=user.id, search_query=query, product_name=None, quantity=body.quantity)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"message": "Item added to cart", "item": {"id": item.id, "search_query": item.search_query, "quantity": item.quantity}}

# ── DELETE /cart/{item_id} ────────────────────────────────────────────────────
@router.delete("/{item_id}")
async def remove_from_cart(
    item_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.keycloak_id == current_user["keycloak_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in your cart.")
    db.delete(item)
    db.commit()
    return {"message": f"'{item.search_query}' removed from cart."}

# ── DELETE /cart/ ─────────────────────────────────────────────────────────────
@router.delete("/")
async def clear_cart(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.keycloak_id == current_user["keycloak_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    db.query(CartItem).filter(CartItem.user_id == user.id).delete()
    db.commit()
    return {"message": "Cart cleared."}

# ── GET /cart/compare ─────────────────────────────────────────────────────────
@router.get("/compare")
async def compare_cart_totals(
    pincode: str = "560095",
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare full cart totals across platforms.

    Fee adjustment logic:
    - Fees in PriceSnapshot were captured for SINGLE-ITEM carts.
    - When multiple items raise the order total above platform thresholds
      (e.g. ₹199+ on Blinkit, ₹250+ on Instamart), delivery becomes free.
    - We apply _FEE_THRESHOLDS to zero out applicable fees so comparisons
      reflect what the user would actually pay on each platform.
    """
    user = db.query(User).filter(User.keycloak_id == current_user["keycloak_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    if not cart_items:
        return {"message": "Your cart is empty."}

    platform_totals = {p.value: {
        "item_total": 0,
        "raw_delivery_fee": 0, "raw_handling_fee": 0,
        "raw_platform_fee": 0, "raw_gst_fee": 0,
        "items_found": [], "items_missing": []
    } for p in PlatformName}

    for cart_item in cart_items:
        for platform in PlatformName:
            snapshot = db.query(PriceSnapshot).filter(
                PriceSnapshot.search_query == cart_item.search_query,
                PriceSnapshot.platform == platform,
                PriceSnapshot.pincode == pincode,
            ).order_by(PriceSnapshot.scraped_at.desc()).first()

            pname = platform.value
            if snapshot and snapshot.in_stock:
                cost = snapshot.price * cart_item.quantity
                platform_totals[pname]["item_total"] += cost
                # Take the highest scraped fee per category across items.
                # (Base rate before threshold adjustment below.)
                platform_totals[pname]["raw_delivery_fee"] = max(
                    platform_totals[pname]["raw_delivery_fee"], snapshot.delivery_fee or 0)
                platform_totals[pname]["raw_handling_fee"] = max(
                    platform_totals[pname]["raw_handling_fee"], snapshot.handling_fee or 0)
                platform_totals[pname]["raw_platform_fee"] = max(
                    platform_totals[pname]["raw_platform_fee"], snapshot.platform_fee or 0)
                platform_totals[pname]["raw_gst_fee"] = max(
                    platform_totals[pname]["raw_gst_fee"], snapshot.gst_fee or 0)
                platform_totals[pname]["items_found"].append({
                    "query":   cart_item.search_query,
                    "product": snapshot.product_name,
                    "price":   snapshot.price,
                })
            else:
                platform_totals[pname]["items_missing"].append(cart_item.search_query)

    results = []
    for pname, data in platform_totals.items():
        # ── Apply threshold adjustment ────────────────────────────────────────
        # Recalculate fees based on the COMBINED item total so that free-delivery
        # thresholds are honoured correctly for multi-item carts.
        adjusted = _adjust_fees(
            platform_name=pname,
            item_total=data["item_total"],
            delivery_fee=data["raw_delivery_fee"],
            handling_fee=data["raw_handling_fee"],
            platform_fee=data["raw_platform_fee"],
            gst_fee=data["raw_gst_fee"],
        )

        grand_total = (
            data["item_total"]
            + adjusted["delivery_fee"]
            + adjusted["handling_fee"]
            + adjusted["platform_fee"]
            + adjusted["gst_fee"]
        )

        # Tell UI which fees were waived (for display purposes)
        delivery_waived  = data["raw_delivery_fee"]  > adjusted["delivery_fee"]
        platform_waived  = data["raw_platform_fee"]  > adjusted["platform_fee"]

        results.append({
            "platform":     pname,
            "item_total":   data["item_total"],
            "delivery_fee": adjusted["delivery_fee"],
            "handling_fee": adjusted["handling_fee"],
            "platform_fee": adjusted["platform_fee"],
            "gst_fee":      adjusted["gst_fee"],
            "grand_total":  grand_total,
            "items_found":  data["items_found"],
            "items_missing": data["items_missing"],
            "complete_order": len(data["items_missing"]) == 0,
            # Informational — shown in UI as "🎉 Delivery free!"
            "fees_waived": {
                "delivery": delivery_waived,
                "platform": platform_waived,
            }
        })

    results.sort(key=lambda x: (not x["complete_order"], x["grand_total"]))
    cheapest = next((r for r in results if r["complete_order"]), results[0] if results else None)
    savings = None
    if cheapest and len(results) > 1:
        most_expensive = max(
            (r for r in results if r["complete_order"]),
            key=lambda x: x["grand_total"], default=None
        )
        if most_expensive and most_expensive["grand_total"] != cheapest["grand_total"]:
            savings = most_expensive["grand_total"] - cheapest["grand_total"]

    return {
        "user":              current_user["email"],
        "pincode":           pincode,
        "cheapest_platform": cheapest["platform"] if cheapest else None,
        "you_save":          savings,
        "comparison":        results,
        "fee_note":          "Delivery/platform fees are waived automatically when your cart total crosses each platform's threshold (Blinkit ₹199+, Zepto ₹200+, Instamart ₹250+).",
    }
