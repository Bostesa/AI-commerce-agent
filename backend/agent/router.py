"""Lightweight intent routing and rule based parsing

This module keeps the decision logic simple and easy to follow
The router decides if a turn is small talk text recommend image search or image plus text
When an Ollama model is available we use it for light extraction and small talk and we always keep rules as a safe fallback
"""

from __future__ import annotations
import os, re, json, random
from datetime import datetime
from typing import Literal
from .models import FilterSpec

AGENT_NAME = os.environ.get("AGENT_NAME", "AI Commerce Agent")

def classify_intent(text: str, has_image: bool) -> Literal["IMAGE_AND_TEXT","IMAGE_SEARCH","TEXT_RECOMMEND","SMALLTALK"]:
    """Resolve a coarse intent for the turn

    Keep this conservative so later filtering can still shape the final answer
    """
    # This is probably the most important function in the whole router
    # It decides what the user actually wants to do with their input
    t_raw = text or ""
    t = t_raw.lower().strip()
    if has_image and len(t) > 2:
        return "IMAGE_AND_TEXT"  # They uploaded a pic AND wrote something meaningful
    if has_image:
        return "IMAGE_SEARCH"  # Just a picture, no real text to work with
    t = text.lower().strip()
    # These are the magic words that tell us someone wants to shop
    shopping_signals = [
        "recommend", "find me", "suggest", "looking for", "buy", "show me", "search for", "compare"
    ]
    # Money talk usually means they're serious about buying
    price_signals = ["under ", "$", "less than", "between", "from "]
    # If the user shows shopping intent OR mentions a price, treat as recommendation
    if any(k in t for k in shopping_signals) or any(p in t for p in price_signals):
        return "TEXT_RECOMMEND"
    return "SMALLTALK"

BRANDS = [
    "Nike","Adidas","Under Armour","Puma","Reebok","Champion","New Balance","ASICS",
    "Lululemon","Patagonia","Uniqlo","H&M","Sony","Bose","Apple","Beats",
    "Columbia","The North Face","Arcteryx","Samsonite","Herschel","Deuter","Salomon"
]

def _parse_price(text: str):
    """Parse a price band from free text

    Supports expressions like under 30 between 20 and 40 and ranges with a dash
    """
    t = text.lower()
    price_min = None
    price_max = None
    # Handle "under $50" or "less than 30"  pretty straightforward
    m = re.search(r"(under|less than|below)\s*\$?(\d+)", t)
    if m:
        price_max = float(m.group(2))  # Just grab that number
    # "between 20 and 40" or "from 10 to 25" gotta handle both orders
    m = re.search(r"(between|from)\s*\$?(\d+)\s*(and|-|to)\s*\$?(\d+)", t)
    if m:
        a = float(m.group(2)); b = float(m.group(4))
        price_min, price_max = min(a,b), max(a,b)  # Don't assume they'll put lower first
    # range like 20 to 40
    m = re.search(r"\$?(\d+)\s*-\s*\$?(\d+)", t)
    if m:
        a = float(m.group(1)); b = float(m.group(2))
        price_min, price_max = min(a,b), max(a,b)
    return price_min, price_max

def _parse_brand(text: str):
    # Just do a simple substring search works surprisingly well
    for b in BRANDS:
        if b.lower() in text.lower():
            return b
    return None  
TAG_MAP = {
    "breathable":"breathable",
    "lightweight":"lightweight",
    "mesh":"mesh",
    "dry fit":"dry-fit",
    "dri fit":"dry-fit",
    "dri-fit":"dry-fit",
    "quick dry":"quick-dry",
    "quick-dry":"quick-dry",
    "cotton":"cotton",
    "graphic":"graphic",
    "compression":"compression",
    "long sleeve":"long-sleeve",
    "short sleeve":"short-sleeve",
    "athletic":"athletic",
    "sports":"athletic",
    "waterproof":"waterproof",
    "windproof":"windproof",
    "hiking":"hiking",
    "trail":"trail",
    "leather":"leather",
    "canvas":"canvas",
    "wireless":"wireless",
    "noise cancelling":"noise-cancelling",
    "cushioning":"cushioning",
}

def extract_filters_rules(text: str) -> FilterSpec:
    """Return a FilterSpec using only rules and simple matching"""
    t = text.lower()
    price_min, price_max = _parse_price(t)
    brand = _parse_brand(text)
    category = None
    CATEGORY_SYNONYMS = [
        ("t-shirt", ["t-shirt","tee","shirt","tshirt"]),
        ("hoodie", ["hoodie","hooded"]),
        ("shorts", ["shorts"]),
        ("sneakers", ["sneakers","running shoes","trainers","shoes"]),
        ("backpack", ["backpack","bag","daypack"]),
        ("headphones", ["headphones","headset","over-ear","on-ear","noise cancelling"]),
        ("jacket", ["jacket","shell","windbreaker","rain jacket","coat"]),
        ("leggings", ["leggings","tights"]),
        ("socks", ["socks"]),
        ("cap", ["cap","hat","beanie"]),
    ]
    for canonical, keys in CATEGORY_SYNONYMS:
        if any(k in t for k in keys):
            category = canonical
            break
    tags_contains = None
    for k, v in TAG_MAP.items():
        if k in t:
            tags_contains = v; break
    return FilterSpec(brand=brand, category=category, price_min=price_min, price_max=price_max, tags_contains=tags_contains)

def extract_filters_llm_or_rules(text: str) -> FilterSpec:
    """Return a FilterSpec using rules only

    The project is fully deterministic and does not rely on an external model
    """
    return extract_filters_rules(text)

def smalltalk_reply(text: str) -> str:
    """Friendly small talk that keeps the conversation in scope

    With an Ollama model configured we ask for a short natural sentence
    Without a model we use a small set of curated replies
    """
    t = (text or "").lower().strip()

    # Greetings
    if any(g in t for g in ["hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening"]):
        return f"Hi! I'm {AGENT_NAME}. How can I help today?"

    # Name / identity
    if any(k in t for k in ["what's your name", "what is your name", "your name", "who are you", "introduce yourself"]):
        return f"I'm {AGENT_NAME}. Your AI shopping buddy for our catalog."

    # Capabilities
    if any(k in t for k in ["what can you do", "capabilities", "how can you help", "help", "what do you do"]):
        return (
            "I can chat, recommend products from our catalog, and search by image. "
            "Try: ‘recommend breathable t‑shirts under $30’ or upload a photo and say ‘like this but cheaper’."
        )

    # Gratitude / sign‑off
    if any(k in t for k in ["thank you", "thanks", "thx", "ty"]):
        return "You're welcome! If you want more ideas, just ask."
    if any(k in t for k in ["bye", "goodbye", "see you", "later"]):
        return "Bye for now! Happy shopping."

    # How are you
    if "how are you" in t or "how's it going" in t or "hows it going" in t:
        return "Doing well, thanks! Ready to help you find great picks."

    # Time / date (local server time)
    if any(k in t for k in ["what time", "current time", "date", "what's the time", "time is it"]):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"It's {now} (server time)."

    # Jokes / fun
    if "joke" in t:
        jokes = [
            "Why did the web developer go broke? Because they used up all their cache.",
            "I told my sneakers a joke. They were laced with laughter.",
            "Why do shirts love autumn? Because it’s the best season to layer.",
        ]
        return random.choice(jokes)

    # Preferences / trivia
    if "favorite color" in t or "favourite colour" in t:
        return "Emerald green — goes well with dark mode."
    if "where are you" in t or "where do you live" in t:
        return "I live in the cloud, close to your shopping cart."
    if any(k in t for k in ["who made you", "who created you", "who built you"]):
        return "I was built by your team using FastAPI, CLIP embeddings, and Next.js."

    # No external model. Continue with a friendly default

    # Default friendly reply
    return (
        "How can I help with your shopping today? You can ask for recommendations, set filters, or drop in a photo."
    )
