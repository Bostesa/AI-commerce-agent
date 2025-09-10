# Agent API

Base URL: http://localhost:8000

This service uses JSON over HTTP and UTF-8 everywhere. Images sent to `/chat` must be base64 data and images sent to `/image-search` must be multipart files. The image size limit is 4 MB. The `top_k` parameter is clamped to a range from 2 to 24.

The Swagger UI lives at `/docs`. The raw OpenAPI schema lives at `/openapi.json`.

---

## POST /chat

Single entry point for the agent. The routing happens on the server and can handle small talk, text recommendation, image search, and image plus text.

Request body:

```
{
  "messages": [{"role": "user" | "assistant", "content": "string"}],
  "image_base64": "string or null",
  "top_k": 8,
  "filters": {
    "brand": "string or null",
    "category": "string or null",
    "price_min": 0 or null,
    "price_max": 0 or null,
    "tags_contains": "string or null"
  }
}
```

Notes:
- Filters are applied to the next turn only in the UI. When present the backend enforces brand category and price bounds. Tag matches from free text are a soft signal unless a tag is set in `filters`.
- `image_base64` uses a data URL such as `data:image/jpeg;base64,...`.

Response body:

```
{
  "reply": "string",
  "products": [Product],
  "trace": {"intent": "string", "filters": {...}, "used_tools": ["string"], "returned": 8}
}
```

`Product` is the catalog row:

```
{
  "id": "string",
  "title": "string",
  "description": "string",
  "category": "string",
  "brand": "string",
  "price": 0,
  "currency": "string",
  "image_url": "string",
  "product_url": "string or null",
  "tags": "string"
}
```

Example call:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "messages":[{"role":"user","content":"recommend t shirts under $30"}],
    "image_base64": null,
    "top_k": 8,
    "filters": null
  }'
```

---

## POST /image-search

Image only search. This returns items that are visually similar in the catalog.

Form field: `file` is the image file

Query parameter: `top_k` optional

Response is the same shape as `/chat`.

Example:

```bash
curl -F "file=@/path/to/photo.jpg" http://localhost:8000/image-search
```

---

## GET /products/{id}

Return one product by id.

Example:

```bash
curl http://localhost:8000/products/tee-001
```

---

## GET /meta

Return metadata used by the filter UI. The body contains brand names, category names, and the price range of the current catalog.

---

## GET /similar/{id}

Return products that are close to the given item in the embedding space.

---

## GET /health

Return a small JSON body that includes `catalog_size` and `status`.

## GET /version

Return the running version.

---

## Errors

The server uses standard HTTP codes.

- 400 for invalid input such as a bad image
- 404 for a missing product id
- 500 for a server side error such as an index that failed to load

