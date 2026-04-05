"""
app/ai/matcher.py
-----------------
AI-powered product matching & price comparison using Groq (llama-3.3-70b).

After all three scrapers complete, this module:
  1. Verifies all platforms returned the SAME product (brand, variant, weight)
  2. Computes TOTAL cost on each platform (item price + all fees)
  3. Flags mismatches with a plain-English reason
  4. Identifies the cheapest platform by TOTAL cost (not just item price)

Gracefully degrades (returns basic totals only) if GROQ_API_KEY is not set.
"""

import os
import json
import asyncio
from groq import AsyncGroq

GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Prompt ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a product comparison expert for Indian quick-commerce apps 
(Blinkit, Zepto, Swiggy Instamart). Your job is to analyze scraped product data and 
determine if all platforms returned the SAME product (same brand, same variant, same weight/volume).

Always respond with valid JSON only — no markdown, no explanation outside the JSON.
"""

def _build_user_prompt(query: str, results: list[dict]) -> str:
    lines = []
    for r in results:
        store   = r.get("store", "Unknown")
        name    = r.get("name", "N/A")
        price   = r.get("price", 0)
        weight  = r.get("weight", "")
        d_fee   = r.get("delivery_fee", 0)
        h_fee   = r.get("handling_fee", 0)
        p_fee   = r.get("platform_fee", 0)
        gst     = r.get("gst_fee", 0)
        total   = price + d_fee + h_fee + p_fee + gst
        lines.append(
            f"- {store}: \"{name}\" {weight} @ ₹{price} "
            f"(delivery ₹{d_fee}, handling ₹{h_fee}, platform ₹{p_fee}, gst ₹{gst}) "
            f"→ TOTAL ₹{total}"
        )

    products_text = "\n".join(lines)

    return f"""User searched for: "{query}"

Scraped results:
{products_text}

Tasks:
1. Decide if ALL platforms returned the SAME product (same brand, variant, AND weight/volume).
2. Provide a single canonical product name (short, clear).
3. For each platform, set is_match=true if it matches the canonical product, else false and give a mismatch_reason.
4. Calculate total_price = item_price + delivery + handling + platform_fee + gst for each.
5. Identify the cheapest VALID (is_match=true) platform by total_price.

Return ONLY this JSON structure (no extra text):
{{
  "canonical_name": "<short canonical product name>",
  "comparison_valid": <true if all platforms matched, else false>,
  "results": [
    {{
      "store": "<store name>",
      "is_match": <true/false>,
      "mismatch_reason": "<null or short reason>",
      "total_price": <integer>
    }}
  ],
  "cheapest_valid_store": "<store name or null>",
  "cheapest_total_price": <integer or null>,
  "ai_note": "<one sentence summary, e.g. 'All platforms matched. Zepto is cheapest including fees.'>",
  "confidence": "<high|medium|low>"
}}"""


# ── Core function ────────────────────────────────────────────────────────────

async def match_products(query: str, results: list[dict]) -> dict:
    """
    Runs AI product matching on scraped results.
    Falls back to basic total-price calculation if GROQ_API_KEY is not set
    or if the API call fails.
    """
    # Always compute totals locally regardless of AI availability
    enriched = _compute_totals(results)

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[AI] GROQ_API_KEY not set — skipping AI matching, using basic totals")
        return _basic_analysis(query, enriched)

    try:
        client = AsyncGroq(api_key=api_key)
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": _build_user_prompt(query, enriched)},
            ],
            temperature=0.0,       # deterministic
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        print(f"[AI] Raw response: {raw[:300]}")
        analysis = json.loads(raw)
        print(f"[AI] Matched → canonical='{analysis.get('canonical_name')}', "
              f"valid={analysis.get('comparison_valid')}, "
              f"cheapest={analysis.get('cheapest_valid_store')} @ ₹{analysis.get('cheapest_total_price')}")
        return analysis

    except Exception as exc:
        print(f"[AI] Groq call failed ({exc}) — falling back to basic analysis")
        return _basic_analysis(query, enriched)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _compute_totals(results: list[dict]) -> list[dict]:
    """Attach total_price to each result dict (mutates a copy)."""
    out = []
    for r in results:
        rc = dict(r)
        rc["total_price"] = (
            rc.get("price", 0)
            + rc.get("delivery_fee", 0)
            + rc.get("handling_fee", 0)
            + rc.get("platform_fee", 0)
            + rc.get("gst_fee", 0)
        )
        out.append(rc)
    return out


def _basic_analysis(query: str, results: list[dict]) -> dict:
    """
    Fallback when AI is unavailable: assume all results are valid,
    pick cheapest by total price, no mismatch detection.
    """
    valid = [r for r in results if r.get("status") == "success"]
    cheapest = min(valid, key=lambda r: r["total_price"]) if valid else None
    return {
        "canonical_name": query.title(),
        "comparison_valid": True,
        "results": [
            {
                "store":            r.get("store"),
                "is_match":         True,
                "mismatch_reason":  None,
                "total_price":      r.get("total_price", r.get("price", 0)),
            }
            for r in results
        ],
        "cheapest_valid_store":  cheapest["store"] if cheapest else None,
        "cheapest_total_price":  cheapest["total_price"] if cheapest else None,
        "ai_note":  "AI matching unavailable — showing raw scraped data.",
        "confidence": "low",
    }
