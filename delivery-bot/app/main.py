from fastapi import FastAPI
from app.scraper.blinkit import BlinkitScraper
from app.scraper.zepto import ZeptoScraper
from app.scraper.instamart import InstamartScraper
import asyncio

app = FastAPI(title="Quick Commerce Comparison Bot")

@app.get("/")
async def root():
    return {"message": "Delivery Bot is Online"}

@app.get("/compare")
async def compare(item: str, pincode: str = "110001"):
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
    
    # Simple logic to find the cheapest
    valid_results = [r for r in results if r["status"] == "success"]
    cheapest = min(valid_results, key=lambda x: x["price"]) if valid_results else None

    return {
        "query": item,
        "pincode": pincode,
        "cheapest_option": cheapest,
        "all_results": results
    }