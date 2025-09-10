"use client";
// Product detail page showing individual product info and similar items
import React from 'react';
import Link from 'next/link';
import { getProduct, getSimilar, BACKEND_URL } from '../../../lib_api';

export default function ProductPage({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id);
  const [prod, setProd] = React.useState<any | null>(null);
  const [similar, setSimilar] = React.useState<any[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let mounted = true;
    getProduct(id)
      .then((p) => {
        if (!mounted) return;
        setProd(p);
        return getSimilar(id, 6);
      })
      .then((s) => {
        if (!mounted || !s) return;
        setSimilar(s.products || []);
      })
      .catch((e) => setError(String(e)));
    return () => {
      mounted = false;
    };
  }, [id]);

  const resolveImg = (u?: string) => (u?.startsWith('http') ? u : `${BACKEND_URL}${u || ''}`);

  if (error) return <div className="card p-4">Error: {error}</div>;
  if (!prod) return <div className="card p-4">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <div className="flex gap-4">
          {prod.image_url && (
            <img
              src={resolveImg(prod.image_url)}
              alt={prod.title}
              className="w-40 h-40 object-cover rounded-lg border border-neutral-800"
            />
          )}
          <div className="space-y-2">
            <div className="text-2xl font-semibold">{prod.title}</div>
            <div className="opacity-80">{prod.brand} • {prod.category}</div>
            <div className="font-medium">{prod.price}{prod.currency}</div>
            {prod.tags && <div className="text-sm opacity-75">{prod.tags}</div>}
            <div className="text-sm opacity-80 max-w-2xl">{prod.description}</div>
            <div className="flex gap-2 pt-2">
              <Link href={`/compare?ids=${encodeURIComponent(id)}`} className="btn">Compare…</Link>
              {prod.product_url && (
                <a href={prod.product_url} target="_blank" rel="noreferrer" className="btn">Buy</a>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="card p-4">
        <div className="font-semibold mb-3">Similar items</div>
        {similar.length === 0 ? (
          <div className="text-sm opacity-70">No similar items.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {similar.map((p) => (
              <a key={p.id} href={`/product/${encodeURIComponent(p.id)}`} className="card p-3">
                <div className="flex gap-3">
                  {p.image_url && (
                    <img src={resolveImg(p.image_url)} className="h-16 w-16 rounded-md object-cover border border-neutral-800" />
                  )}
                  <div className="min-w-0">
                    <div className="font-medium truncate">{p.title}</div>
                    <div className="text-xs opacity-80 truncate">{p.brand} • {p.category}</div>
                    <div className="text-xs mt-0.5">{p.price}{p.currency}</div>
                    <div className="text-xs mt-1 text-emerald-400">Compare</div>
                  </div>
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
