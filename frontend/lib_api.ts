// All the API functions to talk to Python backend
export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

// Type for search filters matches the backend FilterSpec model
export type FilterSpec = {
  brand?: string | null;        // "Nike", "Adidas", etc.
  category?: string | null;     // "t-shirt", "sneakers", etc.
  price_min?: number | null;    // Minimum price
  price_max?: number | null;    // Maximum price (budget constraint)
  tags_contains?: string | null; // Required tag like "waterproof"
};

export async function chat(
  messages: { role: 'user' | 'assistant'; content: string }[],
  imageBase64?: string,
  filters?: FilterSpec,
  top_k: number = 8,
) {
  // The main chat API send messages, get AI response + products back
  const res = await fetch(`${BACKEND_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, image_base64: imageBase64 || null, top_k, filters: filters || null }),
  });
  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
  return res.json(); // Returns {reply, products, trace}
}

export async function getMeta() {
  // Get catalog metadata all available brands, categories, price range
  // Used to populate the filters dropdown
  const res = await fetch(`${BACKEND_URL}/meta`);
  if (!res.ok) throw new Error(`Meta request failed: ${res.status}`);
  return res.json() as Promise<{ brands: string[]; categories: string[]; price_min: number; price_max: number }>;
}

export async function getProduct(id: string) {
  // Get details for a single product by ID
  const res = await fetch(`${BACKEND_URL}/products/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Product request failed: ${res.status}`);
  return res.json() as Promise<any>;
}

export async function getSimilar(id: string, top_k: number = 6) {
  // Find products similar to the given product ID
  // Used on product detail pages for "you might also like" section
  const res = await fetch(`${BACKEND_URL}/similar/${encodeURIComponent(id)}?top_k=${top_k}`);
  if (!res.ok) throw new Error(`Similar request failed: ${res.status}`);
  return res.json() as Promise<{ products: any[] }>;
}

// Eval API
export type EvaluationSummary = {
  metadata: {
    start_time: string;
    catalog_size: number;
    duration_seconds: number;
  };
  key_metrics: {
    'ndcg@5'?: number;
    'precision@5'?: number;
    'recall@5'?: number;
    mrr?: number;
    intent_accuracy?: number;
    filter_accuracy?: number;
    p95_latency_ms?: number;
    throughput_qps?: number;
  };
};

export type EvaluationStatus = {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  mode: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
};

export type EvaluationHistory = {
  evaluations: Array<{
    filename: string;
    timestamp: string;
    duration_seconds: number;
    catalog_size: number;
    'ndcg@5': number;
  }>;
};

export async function startEvaluation(mode: string = 'quick'): Promise<EvaluationStatus> {
  const res = await fetch(`${BACKEND_URL}/api/eval/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new Error(`Evaluation start failed: ${res.status}`);
  return res.json();
}

export async function getEvaluationStatus(jobId: string): Promise<EvaluationStatus> {
  const res = await fetch(`${BACKEND_URL}/api/eval/status/${jobId}`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

export async function getEvaluationSummary(): Promise<EvaluationSummary> {
  const res = await fetch(`${BACKEND_URL}/api/eval/summary`);
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('No evaluation results found. Run an evaluation first.');
    }
    throw new Error(`Summary fetch failed: ${res.status}`);
  }
  return res.json();
}

export async function getEvaluationHistory(): Promise<EvaluationHistory> {
  const res = await fetch(`${BACKEND_URL}/api/eval/history`);
  if (!res.ok) throw new Error(`History fetch failed: ${res.status}`);
  return res.json();
}

export async function getEvaluationResults(jobId: string = 'latest'): Promise<any> {
  const res = await fetch(`${BACKEND_URL}/api/eval/results/${jobId}`);
  if (!res.ok) throw new Error(`Results fetch failed: ${res.status}`);
  return res.json();
}
