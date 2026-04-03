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

    # If same search query already in cart, just bump quantity
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
    For each item in cart, look up ALL PriceSnapshots for the same search_query.
    This correctly handles different platform product names for the same search.
    """
    user = db.query(User).filter(User.keycloak_id == current_user["keycloak_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    if not cart_items:
        return {"message": "Your cart is empty."}

    platform_totals = {p.value: {
        "item_total": 0, "delivery_fee": 0, "handling_fee": 0,
        "platform_fee": 0, "gst_fee": 0, "items_found": [], "items_missing": []
    } for p in PlatformName}

    for cart_item in cart_items:
        for platform in PlatformName:
            # KEY FIX: Match by search_query, not product_name
            snapshot = db.query(PriceSnapshot).filter(
                PriceSnapshot.search_query == cart_item.search_query,
                PriceSnapshot.platform == platform,
                PriceSnapshot.pincode == pincode,
            ).order_by(PriceSnapshot.scraped_at.desc()).first()

            pname = platform.value
            if snapshot and snapshot.in_stock:
                cost = snapshot.price * cart_item.quantity
                platform_totals[pname]["item_total"] += cost
                platform_totals[pname]["delivery_fee"] = max(platform_totals[pname]["delivery_fee"], snapshot.delivery_fee)
                platform_totals[pname]["handling_fee"] = max(platform_totals[pname]["handling_fee"], snapshot.handling_fee)
                platform_totals[pname]["platform_fee"] = max(platform_totals[pname]["platform_fee"], snapshot.platform_fee)
                platform_totals[pname]["gst_fee"] = max(platform_totals[pname]["gst_fee"], snapshot.gst_fee or 0)
                platform_totals[pname]["items_found"].append({
                    "query": cart_item.search_query,
                    "product": snapshot.product_name,
                    "price": snapshot.price,
                })
            else:
                platform_totals[pname]["items_missing"].append(cart_item.search_query)

    results = []
    for pname, data in platform_totals.items():
        grand_total = data["item_total"] + data["delivery_fee"] + data["handling_fee"] + data["platform_fee"] + data["gst_fee"]
        results.append({
            "platform": pname,
            "item_total": data["item_total"],
            "delivery_fee": data["delivery_fee"],
            "handling_fee": data["handling_fee"],
            "platform_fee": data["platform_fee"],
            "gst_fee": data["gst_fee"],
            "grand_total": grand_total,
            "items_found": data["items_found"],
            "items_missing": data["items_missing"],
            "complete_order": len(data["items_missing"]) == 0
        })

    results.sort(key=lambda x: (not x["complete_order"], x["grand_total"]))
    cheapest = next((r for r in results if r["complete_order"]), results[0] if results else None)
    savings = None
    if cheapest and len(results) > 1:
        most_expensive = max((r for r in results if r["complete_order"]), key=lambda x: x["grand_total"], default=None)
        if most_expensive and most_expensive["grand_total"] != cheapest["grand_total"]:
            savings = most_expensive["grand_total"] - cheapest["grand_total"]

    return {
        "user": current_user["email"],
        "pincode": pincode,
        "cheapest_platform": cheapest["platform"] if cheapest else None,
        "you_save": savings,
        "comparison": results
    }
