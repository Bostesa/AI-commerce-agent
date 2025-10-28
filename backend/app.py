# FastAPI backend for AI Commerce Agent
# This is the main API server that handles chat requests, image search, and product lookups
import os
import io
import base64
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
import pandas as pd

from agent.models import Product, ChatRequest, ChatResponse, FilterSpec, ProductsResponse
from agent.router import classify_intent, extract_filters_llm_or_rules, smalltalk_reply
from agent.tools import CatalogIndex, apply_filters
from agent.embeddings import CLIPEncoder

# app

APP_VERSION = "1.1.0"
app = FastAPI(title="AI Commerce Agent API", version=APP_VERSION)

# Include evaluation API endpoints
try:
    from evaluation.api_endpoints import router as eval_router
    app.include_router(eval_router, prefix="/api/eval", tags=["evaluation"])
except Exception as e:
    print(f"Warning: Could not load evaluation endpoints: {e}")

# CORS setup for local development with Next.js frontend
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins + ["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve optional static frontend (not required for Next.js)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Global state for the catalog and AI models
CATALOG_PATH = os.environ.get("CATALOG_PATH", "data/catalog.csv")
INDEX: CatalogIndex | None = None  # Product catalog with embeddings
_ENCODER: CLIPEncoder | None = None  # CLIP model for image/text encoding  
_CATEGORY_TEXT_EMB = None  # Cached embeddings for category inference
_CATEGORY_LABELS = [
    "t-shirt",
    "hoodie",
    "shorts",
    "sneakers",
    "backpack",
    "headphones",
    "jacket",
    "leggings",
    "socks",
]

def _get_encoder() -> CLIPEncoder:
    global _ENCODER
    if _ENCODER is None:
        try:
            # Prefer the index's encoder if available
            if INDEX and getattr(INDEX, 'encoder', None):
                _ENCODER = INDEX.encoder  # type: ignore
            else:
                _ENCODER = CLIPEncoder()
        except Exception:
            _ENCODER = CLIPEncoder()
    return _ENCODER

def _infer_category_from_image(image: Image.Image) -> str | None:
    """Guess the product category from an uploaded image using CLIP"""
    global _CATEGORY_TEXT_EMB
    enc = _get_encoder()
    try:
        img_emb = enc.encode_image(image)
        if _CATEGORY_TEXT_EMB is None:
            prompts = [f"a photo of a {c}" for c in _CATEGORY_LABELS]
            _CATEGORY_TEXT_EMB = enc.encode_text(prompts)
        sims = (img_emb @ _CATEGORY_TEXT_EMB.T).reshape(-1)
        import numpy as np
        idx = int(np.argmax(sims))
        # Confidence heuristic: require margin over second best
        if len(sims) > 1:
            top = float(sims[idx])
            second = float(np.partition(sims, -2)[-2])
            if top - second < 0.02:  # low margin → uncertain
                return None
        return _CATEGORY_LABELS[idx]
    except Exception:
        return None

@app.on_event("startup")
def startup():
    # Load the product catalog when the server starts
    global INDEX
    try:
        INDEX = CatalogIndex(CATALOG_PATH)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize catalog index: {e}")

@app.get("/health")
def health():
    return {"status": "ok", "catalog_size": len(INDEX.df) if INDEX else 0, "version": APP_VERSION}

@app.get("/version")
def version():
    return {"version": APP_VERSION}

def _user_context(messages: List[dict]) -> str:
    # Take the last contiguous block of user messages to preserve immediate intent
    block: List[str] = []
    for m in reversed(messages):
        role = m.get("role")
        content = m.get("content")
        if role == "assistant":
            break
        if role == "user" and isinstance(content, str):
            block.append(content)
    return "\n".join(reversed(block)).strip()

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Main chat endpoint that handles text, images, and product recommendations
    if INDEX is None:
        raise HTTPException(status_code=500, detail="Index not ready")

    last_user_text = _user_context(req.messages)
    # Clamp and sanitize top_k for consistency and DoS protection
    try:
        requested_k = int(getattr(req, 'top_k', 8))
    except Exception:
        requested_k = 8
    top_k = max(2, min(requested_k, 24))

    intent = classify_intent(last_user_text, has_image=bool(req.image_base64))

    # Track what we did for debugging
    trace: Dict[str, Any] = {"intent": intent, "used_tools": [], "filters": {}}
    products: List[Product] = []

    # Merge UI provided filters (if any) with extracted filters. UI wins when provided.
    extracted = extract_filters_llm_or_rules(last_user_text)
    ui = req.filters or FilterSpec()
    def pick(a, b):
        return a if a not in (None, "", []) else b
    final_filters = FilterSpec(
        brand=pick(ui.brand, extracted.brand),
        category=pick(ui.category, extracted.category),
        price_min=pick(ui.price_min, extracted.price_min),
        price_max=pick(ui.price_max, extracted.price_max),
        tags_contains=pick(ui.tags_contains, extracted.tags_contains),
    )
    # Strict filters: everything the user chose is enforced. From the text, enforce
    # category and price bounds, but do NOT enforce tags unless the user set them.
    strict_filters = FilterSpec(
        brand=ui.brand or None,
        category=ui.category or extracted.category,
        price_min=ui.price_min if ui.price_min is not None else extracted.price_min,
        price_max=ui.price_max if ui.price_max is not None else extracted.price_max,
        tags_contains=ui.tags_contains or None,
    )
    trace["filters_ui"] = (ui.model_dump() if req.filters else None)
    trace["filters_extracted"] = extracted.model_dump()
    trace["filters_strict"] = strict_filters.model_dump()

    # If the user provided any explicit filters, treat the request as a recommendation
    # even if the free text lacks shopping keywords.
    if intent == "SMALLTALK":
        if any([
            final_filters.brand,
            final_filters.category,
            final_filters.price_min is not None,
            final_filters.price_max is not None,
            final_filters.tags_contains,
        ]):
            intent = "TEXT_RECOMMEND"
            trace["intent_override"] = "filters_present"

    def _enrich(products: List[Product]) -> List[Product]:
        # Deterministic mode: catalog.csv already contains image_url and product_url
        return products

    def _pick_with_filters(scored_list: List[tuple], filters: FilterSpec, top_k: int) -> List[int]:
        cand_idxs = [i for i, _ in scored_list]
        df = INDEX.df

        def norm(s: str) -> str:
            return ''.join(ch for ch in s.lower() if ch.isalnum() or ch.isspace()).strip()

        def add_unique(seed: List[int], pool: List[int]) -> List[int]:
            seen_keys = { (norm(str(df.iloc[i]["title"])), norm(str(df.iloc[i]["brand"])) ) for i in seed }
            out = list(seed)
            for i in pool:
                if len(out) >= top_k:
                    break
                key = (norm(str(df.iloc[i]["title"])), norm(str(df.iloc[i]["brand"])) )
                if key in seen_keys:
                    continue
                out.append(i)
                seen_keys.add(key)
            return out

        def within_price_brand(i: int) -> bool:
            row = df.iloc[i]
            # Always enforce price bounds
            try:
                price = float(row.get("price", 0.0))
            except Exception:
                price = 0.0
            if filters.price_min is not None and price < float(filters.price_min):
                return False
            if filters.price_max is not None and price > float(filters.price_max):
                return False
            # Always enforce brand when specified
            if filters.brand and str(row.get("brand","")) .lower() != str(filters.brand).lower():
                return False
            return True

        # Stage 1: strict filter
        allowed = apply_filters(df, filters)
        allowed_ids = set(allowed["id"].astype(str))
        primary_all = [i for i in cand_idxs if df.iloc[i]["id"] in allowed_ids]
        chosen: List[int] = add_unique([], primary_all)
        trace["filled_relaxed"] = len(chosen) < top_k

        # Stage 2: relax within the same category to keep results coherent
        if len(chosen) < top_k and filters.category:
            cat = str(filters.category).lower()
            cat_pool = [
                i for i in cand_idxs
                if i not in chosen and cat in str(df.iloc[i]["category"]).lower() and within_price_brand(i)
            ]
            before = len(chosen)
            chosen = add_unique(chosen, cat_pool)
            if len(chosen) > before:
                trace["filled_category_relax"] = True

        # Stage 3: fill with any strong semantic matches if still short
        # Important: if a category was explicitly requested, do NOT relax across categories.
        if len(chosen) < top_k and not filters.category:
            fill_pool = [i for i in cand_idxs if i not in chosen and within_price_brand(i)]
            before = len(chosen)
            chosen = add_unique(chosen, fill_pool)
            if len(chosen) > before:
                trace["filled_any_relax"] = True

        # Ensure at least two unique suggestions if available
        min_unique = int(os.environ.get("MIN_UNIQUE_RESULTS", "2"))
        if len(chosen) < min_unique and len(cand_idxs) >= min_unique:
            # take first two unique by title/brand from candidates
            chosen = add_unique([], cand_idxs)
            chosen = chosen[: max(min_unique, top_k) ]

        return chosen

    def _keyword_fallback(user_text: str, filters: FilterSpec, top_k: int) -> List[int]:
        # Lightweight, deterministic scoring if vector search returns nothing
        df = INDEX.df
        cand = apply_filters(df, filters) if any([
            filters.brand, filters.category, filters.price_min is not None,
            filters.price_max is not None, filters.tags_contains
        ]) else df

        text = (user_text or "").lower()
        tokens = [t for t in ''.join([c if c.isalnum() else ' ' for c in text]).split() if t]
        token_set = set(tokens)

        scores: List[tuple[int, float]] = []
        for i, row in cand.reset_index().iterrows():
            idx = int(row['index']) if 'index' in row else int(i)
            title = str(row.get('title','')).lower()
            desc = str(row.get('description','')).lower()
            brand = str(row.get('brand','')).lower()
            tags = str(row.get('tags','')).lower()
            try:
                price = float(row.get('price', 0.0))
            except Exception:
                price = 0.0
            s = 0.0
            # Brand signal
            if brand and brand in text:
                s += 5.0
            # Tag matches
            for tok in token_set:
                if tok and tok in tags:
                    s += 2.0
            # Title/description keyword presence
            for tok in token_set:
                if tok and (tok in title or tok in desc):
                    s += 1.0
            # Enforce budget bounds strictly
            if filters.price_min is not None and price < float(filters.price_min):
                continue
            if filters.price_max is not None and price > float(filters.price_max):
                continue
            # Slight preference to items closer to max (within budget)
            if filters.price_max is not None:
                mx = float(filters.price_max)
                s += 1.5 * (price / max(mx, 1e-6))
            # Category guard: never leave category if explicitly set
            if filters.category:
                cat = str(filters.category).lower()
                if cat not in str(row.get('category','')).lower():
                    continue
            if s > 0:
                scores.append((idx, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [i for i, _ in scores[:top_k]]

    if intent == "IMAGE_AND_TEXT":
        if not req.image_base64:
            raise HTTPException(status_code=400, detail="image_base64 missing")
        try:
            img_bytes = base64.b64decode(req.image_base64.split(",")[-1])
            if len(img_bytes) > 4 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Image too large (max 4MB)")
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image: {e}")
        # If user didn't provide a category, infer it from the image and enforce
        inferred_cat = None
        if not strict_filters.category:
            inferred_cat = _infer_category_from_image(image)
            if inferred_cat:
                strict_filters.category = inferred_cat
                trace["category_inferred"] = inferred_cat
        trace["filters"] = final_filters.model_dump()
        scored = INDEX.search_image_and_text(image, last_user_text, top_k=max(top_k * 10, 50), filters=strict_filters, alpha=0.6)
        chosen = _pick_with_filters(scored, strict_filters, req.top_k)
        products = [Product(**INDEX.df.iloc[i].to_dict()) for i in chosen]
        # Final safety: prune anything that accidentally violated filters
        if any([
            final_filters.brand,
            final_filters.category,
            final_filters.price_min is not None,
            final_filters.price_max is not None,
            final_filters.tags_contains,
        ]):
            allowed = apply_filters(INDEX.df, final_filters)
            allowed_ids = set(allowed["id"].astype(str))
            pre_n = len(products)
            products = [p for p in products if p.id in allowed_ids]
            pruned = pre_n - len(products)
            if pruned > 0:
                trace["post_filter_pruned"] = pruned
        products = _enrich(products)
        reply = INDEX.generate_copy(last_user_text, products, final_filters)
        trace["used_tools"].extend(["image_vector_search", "text_vector_search", "mmr", "fusion_alpha_0.6"])

    elif intent == "IMAGE_SEARCH":
        if not req.image_base64:
            raise HTTPException(status_code=400, detail="image_base64 missing")
        try:
            img_bytes = base64.b64decode(req.image_base64.split(",")[-1])
            if len(img_bytes) > 4 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Image too large (max 4MB)")
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image: {e}")
        filters = strict_filters
        trace["filters"] = filters.model_dump()
        # If user didn't provide a category, infer it from the image and enforce
        if not filters.category:
            inferred_cat = _infer_category_from_image(image)
            if inferred_cat:
                filters.category = inferred_cat
                trace["category_inferred"] = inferred_cat
        scored = INDEX.search_by_image(image, top_k=max(top_k * 10, 50), filters=filters)
        chosen = _pick_with_filters(scored, filters, req.top_k)
        products = [Product(**INDEX.df.iloc[i].to_dict()) for i in chosen]
        if any([
            filters.brand,
            filters.category,
            filters.price_min is not None,
            filters.price_max is not None,
            final_filters.tags_contains,
        ]):
            allowed = apply_filters(INDEX.df, filters)
            allowed_ids = set(allowed["id"].astype(str))
            pre_n = len(products)
            products = [p for p in products if p.id in allowed_ids]
            pruned = pre_n - len(products)
            if pruned > 0:
                trace["post_filter_pruned"] = pruned
        products = _enrich(products)
        reply = INDEX.generate_copy(last_user_text or "similar items", products, filters)
        trace["used_tools"].extend(["image_vector_search", "mmr"])

    elif intent == "TEXT_RECOMMEND":
        filters: FilterSpec = strict_filters
        trace["filters"] = filters.model_dump()
        scored = INDEX.search_by_text(last_user_text, top_k=max(top_k * 10, 100), filters=filters)
        chosen = _pick_with_filters(scored, filters, req.top_k)
        products = [Product(**INDEX.df.iloc[i].to_dict()) for i in chosen]
        if not products:
            # Fallback: simple keyword scoring within filters
            fallback_idxs = _keyword_fallback(last_user_text, filters, req.top_k)
            if fallback_idxs:
                products = [Product(**INDEX.df.iloc[i].to_dict()) for i in fallback_idxs]
                trace["fallback"] = "keyword"
        if any([
            filters.brand,
            filters.category,
            filters.price_min is not None,
            filters.price_max is not None,
            filters.tags_contains,
        ]):
            allowed = apply_filters(INDEX.df, filters)
            allowed_ids = set(allowed["id"].astype(str))
            pre_n = len(products)
            products = [p for p in products if p.id in allowed_ids]
            pruned = pre_n - len(products)
            if pruned > 0:
                trace["post_filter_pruned"] = pruned
        products = _enrich(products)

        # Generate a concise reply
        reply = INDEX.generate_copy(last_user_text, products, filters)

        trace["used_tools"].extend(["text_vector_search", "mmr"])

    else:  # SMALLTALK
        reply = smalltalk_reply(last_user_text)
        products = []

    # De duplicate products by id while preserving order
    _seen = set(); _unique: List[Product] = []
    for p in products:
        if p.id in _seen:
            continue
        _seen.add(p.id)
        _unique.append(p)
    products = _unique

    trace["requested_top_k"] = requested_k
    trace["returned"] = len(products)
    return ChatResponse(reply=reply, products=products, trace=trace)

@app.post("/image-search", response_model=ChatResponse)
async def image_search(file: UploadFile = File(...), top_k: int = 8):
    if INDEX is None:
        raise HTTPException(status_code=500, detail="Index not ready")
    try:
        content = await file.read()
        if len(content) > 4 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 4MB)")
        image = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    top_k = max(2, min(int(top_k), 24))
    scored = INDEX.search_by_image(image, top_k=top_k)
    products = [Product(**INDEX.df.iloc[i].to_dict()) for i, _ in scored]
    reply = f"Here are {len(products)} close matches to your image."
    return ChatResponse(reply=reply, products=products, trace={"intent": "IMAGE_SEARCH", "used_tools": ["image_vector_search"]})

@app.get("/products/{pid}", response_model=Product)
def get_product(pid: str):
    if INDEX is None:
        raise HTTPException(status_code=500, detail="Index not ready")
    row = INDEX.df.loc[INDEX.df["id"] == pid]
    if row.empty:
        raise HTTPException(status_code=404, detail="Not found")
    return Product(**row.iloc[0].to_dict())

@app.get("/meta")
def meta():
    if INDEX is None:
        raise HTTPException(status_code=500, detail="Index not ready")
    df = INDEX.df
    brands = sorted([b for b in df["brand"].dropna().unique().tolist()])
    categories = sorted([c for c in df["category"].dropna().unique().tolist()])
    price_min = float(df["price"].min()) if not df.empty else 0.0
    price_max = float(df["price"].max()) if not df.empty else 0.0
    return {"brands": brands, "categories": categories, "price_min": price_min, "price_max": price_max}

@app.get("/similar/{pid}", response_model=ProductsResponse)
def similar(pid: str, top_k: int = 6):
    if INDEX is None:
        raise HTTPException(status_code=500, detail="Index not ready")
    scored = INDEX.search_similar_to_id(pid, top_k=top_k)
    products = [Product(**INDEX.df.iloc[i].to_dict()) for i, _ in scored]
    return {"products": products}
