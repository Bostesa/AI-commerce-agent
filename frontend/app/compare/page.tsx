"use client";
// Product comparison page for side-by-side product details
import React, { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { getProduct, BACKEND_URL } from '../../lib_api';

function resolve(u?: string) { return u?.startsWith('http') ? u : `${BACKEND_URL}${u || ''}`; }

function CompareInner() {
  const params = useSearchParams();
  const idsParam = params.get('ids') || '';
  const ids = idsParam.split(',').map((s) => s.trim()).filter(Boolean);
  const [prods, setProds] = React.useState<any[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (ids.length === 0) return;
    Promise.all(ids.map((id) => getProduct(id))).then(setProds).catch((e) => setError(String(e)));
  }, [idsParam]);

  if (error) return <div className="card p-4">Error: {error}</div>;
  if (ids.length === 0) return <div className="card p-4">Add product IDs via ?ids=sku-001,sku-002</div>;
  if (prods.length === 0) return <div className="card p-4">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="text-xl font-semibold">Compare</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {prods.map((p) => (
          <Link key={p.id} href={`/product/${encodeURIComponent(p.id)}`} className="card p-4">
            <div className="flex gap-4">
              {p.image_url && <img src={resolve(p.image_url)} className="w-32 h-32 rounded-lg object-cover border border-neutral-800" />}
              <div className="space-y-1 min-w-0">
                <div className="font-semibold truncate">{p.title}</div>
                <div className="text-sm opacity-80 truncate">{p.brand} • {p.category}</div>
                <div className="text-sm">{p.price}{p.currency}</div>
                <div className="text-xs opacity-75 truncate">{p.tags}</div>
                <div className="text-sm opacity-90 mt-2">{p.description}</div>
                <span className="text-emerald-400 text-sm">Open product</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="card p-4">Loading…</div>}>
      <CompareInner />
    </Suspense>
  );
}
