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
from app.models import Base, User
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
    current_user: dict = Depends(get_current_user) # <-- Secures the route! Requires a valid Token.
):
    """
    Now requires the user to be logged in via Keycloak.
    Later, we will extract their saved platform cookies from PostgreSQL here.
    """
    # Initialize scrapers
    blinkit = BlinkitScraper()
    zepto = ZeptoScraper()
    instamart = InstamartScraper()
    
    # Run all scrapers in parallel
    tasks = [
        blinkit.search_product(item, pincode),
        zepto.search_product(item, pincode),
        instamart.search_product(item, pincode),
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Filter out None results and handle errors
    valid_results = [r for r in results if r is not None and r.get("status") == "success"]
    cheapest = min(valid_results, key=lambda x: x["price"]) if valid_results else None

    # Replace any None results with a failure dict for the response if they exist
    processed_results = [
        r if r is not None else {"store": "Unknown", "status": "failed", "error": "Scraper crashed or returned None"}
        for r in results
    ]

    return {
        "user": current_user["email"], # Proof that the bot knows who is searching
        "query": item,
        "pincode": pincode,
        "cheapest_option": cheapest,
        "all_results": processed_results
    }