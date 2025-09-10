from __future__ import annotations
import os, json, csv
from typing import List, Tuple, Optional
import numpy as np
import pandas as pd
from PIL import Image
import faiss

from .embeddings import CLIPEncoder
from .models import Product, FilterSpec

def _compose_text(row: pd.Series) -> str:
    # Create a single text string from all product fields for embedding
    return f"{row['title']} | {row['description']} | category: {row['category']} | brand: {row['brand']} | tags: {row['tags']}"

def _ensure_float32(a: np.ndarray) -> np.ndarray:
    # FAISS is picky about data types so everything needs to be float32
    if a.dtype != np.float32:
        return a.astype('float32')
    return a

def apply_filters(df: pd.DataFrame, f: FilterSpec) -> pd.DataFrame:
    # Filter the dataframe based on user constraints
    out = df
    if f.brand:
        out = out[out["brand"].str.lower() == f.brand.lower()]  
    if f.category:
        out = out[out["category"].str.contains(f.category, case=False, na=False)] 
    if f.price_min is not None:
        out = out[out["price"] >= float(f.price_min)]
    if f.price_max is not None:
        out = out[out["price"] <= float(f.price_max)]  
    if f.tags_contains:
        out = out[out["tags"].str.contains(f.tags_contains, case=False, na=False)]  
    return out

class CatalogIndex:
    def __init__(self, csv_path: str):
        # Load the product catalog and build a searchable index
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(csv_path)
        skipped_rows = 0
        bad_lines: list[int] = []
        try:
            self.df = pd.read_csv(
                csv_path,
                dtype=str,
                keep_default_na=False,
                engine="c",
            )
        except Exception:
            # Fallback parser more forgiving with quotes and escape characters
            try:
                self.df = pd.read_csv(
                    csv_path,
                    dtype=str,
                    keep_default_na=False,
                    engine="python",
                    quotechar='"',
                    escapechar='\\',
                )
            except Exception:
                # Last resort: skip malformed lines to let the app start
                self.df = pd.read_csv(
                    csv_path,
                    dtype=str,
                    keep_default_na=False,
                    engine="python",
                    on_bad_lines='skip'
                )
                # Rough count of total vs parsed rows for operator visibility
                try:
                    with open(csv_path, newline='') as f:
                        total = sum(1 for _ in f) - 1  # minus header
                    skipped_rows = max(total - len(self.df), 0)
                except Exception:
                    skipped_rows = 0

        # Validate field counts and report exact malformed line numbers (non fatal)
        try:
            with open(csv_path, newline='') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    ncols = len(header)
                    for lineno, row in enumerate(reader, start=2):
                        if len(row) != ncols:
                            bad_lines.append(lineno)
        except Exception:
            pass
        # Ensure consistent types
        self.df["id"] = self.df["id"].astype(str)
        # Coerce types
        self.df["price"] = pd.to_numeric(self.df["price"], errors="coerce").fillna(0.0).astype(float)
        # Optional columns
        # Map external CSVs that use `buy_link` to our internal `product_url` field
        if "product_url" not in self.df.columns and "buy_link" in self.df.columns:
            self.df["product_url"] = self.df["buy_link"].fillna("")
        if "product_url" not in self.df.columns:
            self.df["product_url"] = ""
        # Normalize missing columns that the app depends on
        for col in ["title","description","category","brand","currency","image_url","tags"]:
            if col not in self.df.columns:
                self.df[col] = ""
        if skipped_rows or bad_lines:
            msg = f"[catalog] Loaded {len(self.df)} rows;"
            if skipped_rows:
                msg += f" skipped {skipped_rows} malformed row(s)."
            if bad_lines:
                preview = ", ".join(map(str, bad_lines[:20]))
                more = f" (+{len(bad_lines)-20} more)" if len(bad_lines) > 20 else ""
                msg += f" Malformed line numbers (1-based): {preview}{more}."
            msg += " Please fix CSV formatting (quote fields containing commas)."
            print(msg)

        # Set up the CLIP encoder this is what converts text/images to vectors
        self.encoder = CLIPEncoder()

        # Try to load cached embeddings if they match this catalog
        cache_dir = os.path.dirname(csv_path)
        emb_path = os.environ.get("EMBEDDINGS_PATH", os.path.join(cache_dir, "catalog_embeddings.npy"))
        ids_path = os.path.join(cache_dir, "catalog_ids.json")
        loaded = False
        try:
            if os.path.isfile(emb_path) and os.path.isfile(ids_path):
                with open(ids_path, "r") as f:
                    ids = json.load(f)
                embs = np.load(emb_path)
                if len(ids) == len(self.df) and embs.shape[0] == len(self.df):
                    if list(self.df["id"].astype(str)) == ids:
                        self.embeddings = embs.astype("float32")
                        loaded = True
        except Exception:
            loaded = False

        if not loaded:
            # No cache hit so time to compute embeddings from scratch
            # This can take a while for large catalogs but only happens once
            corpus = [ _compose_text(r) for _, r in self.df.iterrows() ]
            self.embeddings = self.encoder.encode_text(corpus)  # shape (N, D)
            try:
                np.save(emb_path, self.embeddings)
                with open(ids_path, "w") as f:
                    json.dump(list(self.df["id"].astype(str)), f)
            except Exception:
                pass
        # Build the FAISS index for fast similarity search
        # Inner product works well with normalized CLIP embeddings
        self.index = faiss.IndexFlatIP(self.embeddings.shape[1])
        self.index.add(_ensure_float32(self.embeddings))
        self.id_map = list(self.df["id"].values)  # Keep track of which row is which

    def _raw_search(self, query_emb: np.ndarray, fetch_k: int) -> Tuple[np.ndarray, np.ndarray]:
        query = _ensure_float32(query_emb.reshape(1, -1))
        scores, idxs = self.index.search(query, fetch_k)
        return scores[0], idxs[0]

    def _mmr(self, query_vec: np.ndarray, cand_idxs: np.ndarray, cand_scores: np.ndarray, top_k: int, diversity: float = 0.3) -> List[int]:
        # Maximal Marginal Relevance - avoid showing too many similar products
        # Balance relevance vs diversity so users don't see 8 identical t-shirts
        selected: List[int] = []
        query_vec = query_vec.reshape(1, -1)
        item_vecs = self.embeddings[cand_idxs]
        # precompute similarity between candidates
        sim_to_query = cand_scores  # already IP from faiss
        sim_items = item_vecs @ item_vecs.T
        while len(selected) < min(top_k, len(cand_idxs)):
            if not selected:
                j = int(np.argmax(sim_to_query))
            else:
                sel_mask = np.zeros(len(cand_idxs), dtype=bool)
                sel_mask[selected] = True  # indices into candidate list
                # compute penalty = max similarity to any selected item
                penalty = sim_items[:, sel_mask].max(axis=1) if sel_mask.any() else np.zeros(len(cand_idxs))
                mmr_score = diversity * sim_to_query - (1 - diversity) * penalty
                mmr_score[selected] = -1e9
                j = int(np.argmax(mmr_score))
            selected.append(j)
        return [int(cand_idxs[j]) for j in selected]

    def _search(self, query_emb: np.ndarray, top_k: int = 8, filters: Optional[FilterSpec] = None) -> List[Tuple[int, float]]:
        fetch_k = max(top_k * 5, 20)
        cand_scores, cand_idxs = self._raw_search(query_emb, fetch_k)
        # remove invalid ids ( 1) and de duplicate while preserving order
        if isinstance(cand_idxs, np.ndarray):
            mask = cand_idxs != -1
            cand_idxs = cand_idxs[mask]
            cand_scores = cand_scores[mask]
        seen = set()
        uniq_idxs: List[int] = []
        uniq_scores: List[float] = []
        for i, s in zip(cand_idxs.tolist(), cand_scores.tolist()):
            ii = int(i)
            if ii in seen:
                continue
            seen.add(ii)
            uniq_idxs.append(ii)
            uniq_scores.append(float(s))
        if not uniq_idxs:
            return []
        cand_idxs = np.array(uniq_idxs, dtype=np.int64)
        cand_scores = np.array(uniq_scores, dtype=np.float32)

        pick_idxs = self._mmr(query_emb, cand_idxs, cand_scores, top_k=top_k)

        # Build list with simple boosts for structured matches
        out: List[Tuple[int, float]] = []
        for idx in pick_idxs:
            score = float((query_emb @ self.embeddings[idx]).item())
            row = self.df.iloc[idx]
            if filters:
                if filters.brand and str(row["brand"]).lower() == filters.brand.lower():
                    score += 0.05
                if filters.category and filters.category.lower() in str(row["category"]).lower():
                    score += 0.03
                if filters.tags_contains and filters.tags_contains.lower() in str(row["tags"]).lower():
                    score += 0.02
                # soft budget preference: slightly favor items near but below the max
                if filters.price_max is not None:
                    try:
                        p = float(row["price"]) ; mx = float(filters.price_max)
                        if p <= mx:
                            score += 0.03 * (p / max(mx, 1e-6))
                    except Exception:
                        pass
            out.append((idx, score))
        # sort by adjusted score desc
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top_k]

    def search_by_text(self, text: str, top_k: int = 8, filters: Optional[FilterSpec] = None) -> List[Tuple[int, float]]:
        q = self.encoder.encode_text([text])[0]
        return self._search(q, top_k=top_k, filters=filters)

    def search_by_image(self, image: Image.Image, top_k: int = 8, filters: Optional[FilterSpec] = None) -> List[Tuple[int, float]]:
        q = self.encoder.encode_image(image)
        return self._search(q, top_k=top_k, filters=filters)

    def search_image_and_text(self, image: Image.Image, text: str, top_k: int = 8, filters: Optional[FilterSpec] = None, alpha: float = 0.6) -> List[Tuple[int, float]]:
        # Combine image and text by linear interpolation of similarities on a shared index
        q_img = self.encoder.encode_image(image)
        q_txt = self.encoder.encode_text([text])[0]
        q = alpha * q_img + (1 - alpha) * q_txt
        # normalize to unit length for inner product stability
        q = q / (np.linalg.norm(q) + 1e-12)
        return self._search(q.astype('float32'), top_k=top_k, filters=filters)

    def search_similar_to_id(self, pid: str, top_k: int = 8) -> List[Tuple[int, float]]:
        row = self.df[self.df['id'].astype(str) == str(pid)]
        if row.empty:
            return []
        base_idx = int(row.index[0])
        q = self.embeddings[base_idx]
        scored = self._search(q, top_k=top_k + 1)
        # filter out the same item
        out = [(i, s) for i, s in scored if self.df.iloc[i]['id'] != pid]
        return out[:top_k]

    def generate_copy(self, user_text: str, products: List[Product], filters: FilterSpec) -> str:
        if not products:
            return (
                "I couldn’t find great matches. Try a higher budget, different brand, or fewer constraints."
            )
        # Build a short, sales‑oriented line with rationale
        highlights = []
        if filters.brand:
            highlights.append(filters.brand)
        if filters.tags_contains:
            highlights.append(filters.tags_contains)
        if filters.category:
            highlights.append(filters.category)
        spec = ", ".join([h for h in highlights if h]) or "your request"
        budget = f" under {filters.price_max:g}{products[0].currency}" if filters.price_max else ""
        tops = products[:3]
        bullet_bits = "; ".join(
            [f"{p.title} — {p.brand}, {p.price:g}{p.currency}" for p in tops]
        )
        return f"Top picks for {spec}{budget}: {bullet_bits}. Want more options or a different style?"
