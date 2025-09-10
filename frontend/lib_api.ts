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
