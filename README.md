# AI Commerce Agent

Single agent that handles:
- general chat
- text based product recommendations
- image based product search
  - image plus text fusion works too

Highlights:
- Next.js and Tailwind frontend
- Dockerfiles for backend and frontend with docker compose
- Filters panel in the UI for brand category price and tag
- Product details page with similar items and a compare view
- Deterministic catalog from CSV

---

## Quick Start (no Docker)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
# API: http://localhost:8000/docs
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
# UI: http://localhost:3000
```

This project does not require a language model. The agent uses rules for intent and filters and embeddings for retrieval.

---
## Docker (recommended)

```bash
docker compose up --build
# backend: http://localhost:8000
# frontend: http://localhost:3000
```

If you want to experiment with a local model later you can add an Ollama sidecar and call it from the router. For this demo we keep the system fully deterministic.

Deterministic mode recommended for review:
- Uses only `backend/data/catalog.csv` for images and buy links. No network calls. The repo ships in this mode.

Optional real images and links:
- If you want to experiment with enrichment you can add it back. In this repo we keep it off to keep the demo stable.

---

## Agent API quick reference

`POST /chat`
```json
{
  "messages": [{"role":"user","content":"recommend a breathable sports t-shirt under $30"}],
  "image_base64": null,
  "top_k": 8
}
```
Response:
```json
{
  "reply": "Here are 3 picks...",
  "products": [{"id":"...","title":"...","image_url":"...","product_url":"..."}],
  "trace": {"intent":"TEXT_RECOMMEND","used_tools":["text_vector_search"],"filters":{...}}
}
```

Endpoints:
- POST `/chat` single entry point for chat recommend and image search
- POST `/image-search` multipart image only search
- GET `/products/{id}` single product
- GET `/meta` catalog brands categories and price range
- GET `/similar/{id}` similar products

Full reference lives in `docs/API.md` and in the Swagger UI at `/docs`.

`ChatRequest` accepts optional UI-provided `filters` which override/augment auto-extracted filters.

---

## Catalog schema

`backend/data/catalog.csv`:
```
id,title,description,category,brand,price,currency,image_url,tags
```

Replace with your data and restart.

> Note: The demo catalog uses backend-hosted SVG thumbnails so the UI always renders images.

---

## How this meets the brief
- Single agent. `POST /chat` routes small talk text recommend image and image plus text with one pipeline
- Predefined catalog. All results come from `backend/data/catalog.csv`
- Text path. CLIP text embeddings feed FAISS. We apply strict filters then MMR for diversity
- Image path. CLIP image embeddings or a fusion with text feed the same pipeline
- UI. Next.js chat with drag and drop or paste image upload filters product details and compare

## Why this stack

I chose Python with FastAPI for the backend because it lets me ship a small, typed API quickly. Pydantic models give me schema‑checked request/response objects and clear validation, and FastAPI generates OpenAPI docs at `/docs` out of the box. Running under Uvicorn keeps startup time low and works well in containers, so the development loop stays fast.

For retrieval I use Sentence‑Transformers’ CLIP ViT‑B/32 together with FAISS. CLIP provides a single embedding space for both text and images, which means I can support text search, pure image search, and image‑plus‑text fusion without juggling multiple models. FAISS with inner‑product on normalized vectors is simple and fast on CPU for a small catalog. I cache the catalog embeddings on disk so restarts are instant after the first run.

I keep the product data in a CSV file to make the demo deterministic and easy to swap with another dataset. The loader is defensive about messy CSVs and normalizes missing columns. Thumbnails are served from the backend’s static folder, so the UI always renders even without external network access; this keeps the experience predictable for reviewers.

On the frontend I use Next.js 14 with React 18 and Tailwind CSS. Next’s DX and file‑based routing keep the UI straightforward, while Tailwind keeps styling lightweight and consistent. The client calls the backend with simple `fetch` requests using a single environment variable (`NEXT_PUBLIC_BACKEND_URL`), which makes it trivial to point the UI at any running backend.

I package both apps with Docker Compose to provide a reproducible environment: one command brings up the backend on port 8000 and the frontend on port 3000. Environment variables such as `ALLOWED_ORIGINS` and `NEXT_PUBLIC_BACKEND_URL` control cross‑origin access and service discovery so I don’t need any extra proxy layer.

Finally, I kept tests and observability pragmatic: a couple of unit tests lock in the intent router and filtering logic, `/health` offers a quick status check, and the `/chat` response includes a debug trace so I can understand which tools and filters were applied to each recommendation.

## What I did to raise quality
- Deterministic default. The CSV is the source of truth for images and links
- Diversity guarantees. We de duplicate by id and by title plus brand then fill inside the category before relaxing
- Clear filters. Brand category and price are always enforced when set
- Minimal tests. See `backend/tests/test_router_intents.py` and `backend/tests/test_tools_filters.py`

---

## Intent and filters

- The router chooses between `IMAGE_SEARCH` `TEXT_RECOMMEND` and `SMALLTALK`
- Filters for brand category price and tag come from simple rules so the behavior is predictable

---

## CI

`.github/workflows/ci.yml` builds backend (pip) and frontend (Next.js) on pushes.

---

## Testing

Run backend unit tests (no large model downloads):

```bash
cd backend
pytest -q
```

CI runs these tests automatically on PRs/pushes.

---
