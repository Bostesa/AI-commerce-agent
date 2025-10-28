# Evaluation Dashboard

UI for viewing eval metrics in the browser. Go to `http://localhost:3000/evaluation` or click the "📊 Evaluation" link in the nav.

## Usage

Three buttons:
- **Quick Eval (~1s)** - retrieval + intent
- **Full Eval (~5s)** - all metrics
- **Retrieval Only** - ranking only

Runs in background, shows progress, auto-refreshes when done.

## Metrics

NDCG@5, intent accuracy, filter accuracy, p95 latency, precision, recall, MRR, throughput. Plus timestamp, catalog size, duration and history table.

## Implementation

Frontend hits REST API, gets job ID, polls every 2 seconds. Dark theme with emerald accents. Responsive layout.

Files: `frontend/app/evaluation/page.tsx`, `frontend/components/MetricCard.tsx`, extended `frontend/lib_api.ts` and `frontend/app/layout.tsx`.

---

## Tips

First time: click "Quick Eval (~1s)".

Good scores: NDCG@5 >0.75, intent accuracy >95%, p95 latency <100ms.

Detailed reports: open `backend/evaluation/results/latest.html` after running eval.

## Troubleshooting

- **No results:** Run first eval
- **Button disabled:** Wait for current eval to finish
- **Stuck:** Check `docker compose logs backend` or refresh page
- **API errors:** Verify backend is up with `curl http://localhost:8000/health`

## Customization

Colors: edit `frontend/components/MetricCard.tsx`
Layout: edit `frontend/app/evaluation/page.tsx`
Metrics: add to `backend/evaluation/metrics.py`, update `frontend/lib_api.ts`, add cards to page
