from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env before anything else
load_dotenv()

# Scraper Imports
from app.scraper.blinkit import BlinkitScraper
from app.scraper.zepto import ZeptoScraper
from app.scraper.instamart import InstamartScraper

# Database & Auth Imports
from app.database import engine, get_db
from app.models import Base, User, PriceSnapshot, PlatformName
from app.auth import get_current_user

# Cart Router
from app.cart.router import router as cart_router

# Create database tables on startup if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Quick Commerce Comparison Bot")
app.include_router(cart_router)

# Enable CORS for the local frontend UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Locked down to your React app for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Delivery Bot is Online & Secured"}

# ==========================================
# NEW: Auth & User Management Endpoint
# ==========================================
@app.get("/api/me")
async def sync_user_profile(
    current_user: dict = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Takes the Keycloak JWT token, verifies it, and syncs the user 
    to our local PostgreSQL database.
    """
    # 1. Check if the user already exists in our database
    user = db.query(User).filter(User.keycloak_id == current_user["keycloak_id"]).first()
    
    # 2. If not, create a new record for them
    if not user:
        user = User(
            keycloak_id=current_user["keycloak_id"],
            email=current_user.get("email", "no-email@provided.com")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"message": "New user synced to database!", "user_id": user.id}

    return {"message": "User already exists in database.", "user_id": user.id}


# ==========================================
# UPDATED: Secured Scraping Endpoint
# ==========================================
@app.get("/compare")
async def compare(
    item: str,
    pincode: str = "110001",
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run all three scrapers in parallel, return results, and cache prices for cart comparison."""
    # Initialize scrapers
    blinkit = BlinkitScraper()
    zepto = ZeptoScraper()
    instamart = InstamartScraper()
    
    # Wrap each scraper with a timeout so a hung browser never stalls the request forever.
    # Instamart uses headed Chrome which is slower to close than headless Chromium.
    async def safe_scrape(coro, store_name: str, timeout: int = 120):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            print(f"[compare] {store_name} timed out after {timeout}s")
            return {"store": store_name, "status": "failed", "error": f"Timed out after {timeout}s"}
        except Exception as exc:
            print(f"[compare] {store_name} raised: {exc}")
            return {"store": store_name, "status": "failed", "error": str(exc)}

    # Run all scrapers in parallel
    tasks = [
        safe_scrape(blinkit.search_product(item, pincode), "Blinkit",    timeout=90),
        safe_scrape(zepto.search_product(item, pincode),   "Zepto",     timeout=90),
        safe_scrape(instamart.search_product(item, pincode), "Instamart", timeout=120),
    ]

    results = await asyncio.gather(*tasks)
    print(f"[compare] All scrapers done: {[r.get('store') if r else 'None' for r in results]}")

    # Save successful results as PriceSnapshots so /cart/compare can read them
    PLATFORM_MAP = {
        "Blinkit": PlatformName.BLINKIT,
        "Zepto": PlatformName.ZEPTO,
        "Instamart": PlatformName.INSTAMART,
    }
    print("[compare] Saving snapshots to DB...")
    for r in results:
        if r and r.get("status") == "success" and r.get("store") in PLATFORM_MAP:
            platform_enum = PLATFORM_MAP[r["store"]]
            # Delete stale snapshot for same SEARCH QUERY + pincode + platform
            db.query(PriceSnapshot).filter(
                PriceSnapshot.search_query == item.lower(),
                PriceSnapshot.platform == platform_enum,
                PriceSnapshot.pincode == pincode
            ).delete()
            snapshot = PriceSnapshot(
                search_query=item.lower(),
                product_name=r["name"],
                platform=platform_enum,
                pincode=pincode,
                price=r["price"],
                delivery_fee=r.get("delivery_fee", 0),
                handling_fee=r.get("handling_fee", 0),
                platform_fee=r.get("platform_fee", 0),
                gst_fee=r.get("gst_fee", 0),
                in_stock=1,
            )
            db.add(snapshot)
            print(f"[compare] Queued snapshot for {r['store']}")
    print("[compare] Committing...")
    db.commit()
    print("[compare] DB commit done.")

    # Filter and find cheapest
    valid_results = [r for r in results if r is not None and r.get("status") == "success"]
    cheapest = min(valid_results, key=lambda x: x["price"]) if valid_results else None

    processed_results = [
        r if r is not None else {"store": "Unknown", "status": "failed", "error": "Scraper returned None"}
        for r in results
    ]

    print("[compare] Returning response.")
    return {
        "user": current_user["email"],
        "query": item,
        "pincode": pincode,
        "cheapest_option": cheapest,
        "all_results": processed_results
    }