# AI Commerce Agent

A unified agent for conversational product recommendations supporting text queries, image search, and multimodal image+text fusion.

**Tech Stack:** FastAPI, Next.js, CLIP embeddings, FAISS vector search, deterministic CSV catalog

**Features:**
- Single `/chat` endpoint handles all interaction types
- Rule-based intent classification and filter extraction
- CLIP-based semantic search with MMR diversity
- Built-in ML evaluation dashboard
- No external LLM required

## Quick Start

**Docker (recommended):**
```bash
docker compose up --build
```
- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Evaluation: http://localhost:3000/evaluation

**Local Development:**
```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## API Reference

### Core Endpoints

**`POST /chat`** - Main unified endpoint
- Accepts text queries, images, or both
- Returns product recommendations with debug trace
- Auto-extracts filters (brand, category, price, tags)

**`GET /products/{id}`** - Retrieve single product details

**`GET /similar/{id}`** - Get similar products by ID

**`GET /meta`** - Catalog metadata (brands, categories, price range)

**`POST /image-search`** - Image-only search (multipart form)

### Documentation
- Interactive API docs: http://localhost:8000/docs
- Full API reference: `docs/API.md`

### Catalog Format
`backend/data/catalog.csv`:
```
id,title,description,category,brand,price,currency,image_url,tags
```

---

## Architecture

### Backend
- **Framework:** FastAPI with Pydantic validation
- **Embeddings:** CLIP ViT-B/32 (unified text/image space)
- **Vector Search:** FAISS with inner product similarity
- **Catalog:** CSV-based deterministic product database
- **Diversity:** MMR (Maximal Marginal Relevance) post-processing
- **Caching:** Embedding cache for fast restarts

### Frontend
- **Framework:** Next.js 14 with React 18
- **Styling:** Tailwind CSS
- **Features:** Drag-and-drop image upload, filters panel, product comparison
- **API Client:** Simple fetch-based communication

### Deployment
- Docker Compose for single-command deployment
- No reverse proxy required
- CORS configured via environment variables

### Quality Assurance
- Deterministic routing (IMAGE_SEARCH / TEXT_RECOMMEND / SMALLTALK)
- Strict filter enforcement (brand, category, price)
- Result deduplication by ID and title+brand
- Debug trace in all responses
- Unit test coverage for intent routing and filter extraction
- Health check endpoint at `/health`

---

## Testing

### Unit Tests
```bash
cd backend
pytest -q
```

Tests cover:
- Intent classification logic
- Filter extraction rules
- Product search and filtering

### CI/CD
Automated testing via GitHub Actions (`.github/workflows/ci.yml`)
- Runs on all PRs and pushes
- Validates backend and frontend builds

---

## ML Evaluation

### Overview
Built-in evaluation dashboard for measuring system performance against golden test queries.

**Metrics Tracked:**
- Retrieval Quality: Precision@K, Recall@K, NDCG@K, MRR, MAP
- Classification: Intent accuracy with per-class breakdown
- Extraction: Filter accuracy (brand, category, price)
- Performance: Latency (p50, p95, p99), throughput
- Diversity: Brand and category distribution

### Usage

**Web Dashboard:**
```
http://localhost:3000/evaluation
```
Click "Quick Eval (~1s)" for instant metrics visualization.

**Command Line:**
```bash
cd backend
python -m evaluation.evaluate_hybrid --mode quick --report html
open evaluation/results/latest.html
```

**API Endpoints:**
- `POST /api/eval/run` - Start evaluation job
- `GET /api/eval/summary` - Get latest metrics
- `GET /api/eval/history` - View past evaluations

### Evaluation Modes
- `quick` - Retrieval + Intent (~1s)
- `all` - Complete evaluation (~5s)
- `retrieval` - Ranking metrics only
- `intent` - Classification metrics only
- `performance` - Latency benchmarks only

---
