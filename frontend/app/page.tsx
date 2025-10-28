'use client';
// The main chat interface - this is where all the magic happens
// Users can type, upload images, set filters, and see product recommendations
import React, { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { chat, getMeta, type FilterSpec } from '../lib_api';
import { ChatMessage, type Msg } from '../components/ChatMessage';
import { UploadBox } from '../components/UploadBox';
import { LoadingDots } from '../components/LoadingDots';
import { FiltersPanel } from '../components/FiltersPanel';
import { getMessages as storeGetMessages, setMessages as storeSetMessages, getFilters as storeGetFilters, setFilters as storeSetFilters, resetChat as storeReset } from '../state/chatStore';

export default function Home() {
  // All the state we need to track the conversation and UI
  const [msgs, setMsgs] = useState<Msg[]>(storeGetMessages()); // Chat history
  const [input, setInput] = useState('Recommend a breathable sports t‑shirt under $30'); // What the user is typing
  const [imageBase64, setImageBase64] = useState<string | null>(null); // Uploaded image
  const [loading, setLoading] = useState(false); // Show spinner when AI is thinking
  const endRef = useRef<HTMLDivElement>(null);
  const [meta, setMeta] = useState<{ brands: string[]; categories: string[]; price_min: number; price_max: number } | null>(null);
  const [filters, setFilters] = useState<FilterSpec>(storeGetFilters());
  const inputRef = useRef<HTMLInputElement>(null);
  const [recent] = useState<any[]>([]);
  const clearChat = () => {
    // Reset everything back to a fresh conversation
    const initial: Msg = {
      role: 'assistant',
      content:
        'Hi! Describe what you need and I will recommend products. You can also attach a photo of an item you like.',
    };
    setMsgs([initial]);
    setInput('');
    setImageBase64(null);
    storeReset(); // Clear the store too
  };

  useEffect(() => {
    // Load saved state when the component first mounts
    // Note: we don't persist across browser refreshes by design
    setMsgs(storeGetMessages());
    setFilters(storeGetFilters());
    getMeta().then(setMeta).catch(() => setMeta(null)); // Get catalog metadata for filters
  }, []);

  useEffect(() => {
    storeSetMessages(msgs);
  }, [msgs]);
  useEffect(() => {
    storeSetFilters(filters);
  }, [filters]);
  

  useEffect(() => {
    // Add keyboard shortcut: Cmd+K (Mac) or Ctrl+K (Windows) focuses the input
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus(); // Jump to search box like in other apps
      }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [msgs, loading]);

  const latestProducts = useMemo(() => {
    const last = [...msgs].reverse().find((m) => Array.isArray(m.products) && m.products.length > 0);
    return last?.products || [];
  }, [msgs]);

  const filterChips = useMemo(() => {
    const chips: { key: keyof FilterSpec; label: string }[] = [];
    if (filters.brand) chips.push({ key: 'brand', label: String(filters.brand) });
    if (filters.category) chips.push({ key: 'category', label: String(filters.category) });
    if (typeof filters.price_max === 'number') chips.push({ key: 'price_max', label: `≤ $${filters.price_max}` });
    if (filters.tags_contains) chips.push({ key: 'tags_contains', label: String(filters.tags_contains) });
    return chips;
  }, [filters]);

  const onSend = async () => {
    // Handle sending a message - this is where the chat magic happens
    let text = input.trim();
    const hasFilters = !!(filters.brand || filters.category ||
      filters.price_min !== undefined || filters.price_max !== undefined || filters.tags_contains);
    if (!text && !imageBase64 && !hasFilters) return; // Nothing to send
    // Smart default: if user just set filters without typing, create a search query for them
    if (!text && hasFilters) {
      const parts: string[] = [];
      if (filters.brand) parts.push(String(filters.brand));
      if (filters.category) parts.push(String(filters.category));
      if (filters.tags_contains) parts.push(String(filters.tags_contains));
      text = `recommend ${parts.filter(Boolean).join(' ')}${filters.price_max ? ` under $${filters.price_max}` : ''}`.trim();
    }
    const m = [...msgs, { role: 'user', content: text } as Msg];
    setMsgs(m);
    setInput('');
    setLoading(true);
    try {
      // Apply current filters to THIS message only
      const activeFilters = { ...filters };
      const resp = await chat(
        m.map((x) => ({ role: x.role, content: x.content })),
        imageBase64 || undefined,
        activeFilters,
        8,
      );
      setMsgs([...m, { role: 'assistant', content: resp.reply, products: resp.products, trace: resp.trace }]);
      setImageBase64(null);
      // Clear filters after they were applied to the message
      if (hasFilters) {
        setFilters({});
      }
    } catch (e: any) {
      setMsgs([...m, { role: 'assistant', content: 'Error: ' + e.message }]);
    } finally {
      setLoading(false);
    }
  };

  const onFile = (f: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      setImageBase64(reader.result as string);
    };
    reader.readAsDataURL(f);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <section className="lg:col-span-2">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-lg font-semibold">Chat with the Agent</h1>
            <button
              className="text-xs px-3 py-1 rounded-md border border-neutral-800 hover:bg-neutral-800"
              onClick={() => {
                if (msgs.length <= 1 || confirm('Clear chat? This will remove the current conversation.')) {
                  clearChat();
                }
              }}
              title="Clear chat"
            >
              Clear chat
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input
              className="flex-1"
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask for a product… e.g. waterproof hiking jacket under $120"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  onSend();
                }
              }}
            />
            <button className="btn" onClick={onSend} disabled={loading}>
              {loading ? <LoadingDots /> : 'Send'}
            </button>
          </div>
          {filterChips.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {filterChips.map((c) => (
                <span key={c.key as string} className="px-2 py-1 rounded-full bg-neutral-900 border border-neutral-800">
                  {c.label}
                  <button
                    className="ml-1 text-neutral-400 hover:text-white"
                    onClick={() => {
                      // Remove this one filter key and keep the rest
                      setFilters((cur) => {
                        const copy: any = { ...cur };
                        delete copy[c.key];
                        return copy as FilterSpec;
                      });
                    }}
                    aria-label={`Remove ${c.label}`}
                    title="Remove"
                  >
                    ×
                  </button>
                </span>
              ))}
              <button
                className="px-2 py-1 rounded-full border border-neutral-800 hover:bg-neutral-900"
                onClick={() => setFilters({})}
                title="Clear filters"
              >
                Clear
              </button>
              <span className="opacity-60 ml-auto">Applied to next message</span>
            </div>
          )}
          <div className="mt-3">
            <UploadBox
              preview={imageBase64}
              onFile={onFile}
              onClear={() => setImageBase64(null)}
            />
          </div>
          <div className="mt-3 text-xs text-neutral-400">
            Tip: Try “Compare these two running shoes for comfort and durability”.
          </div>
        </div>

        <div className="mt-6 space-y-4">
          {msgs.map((m, idx) => (
            <ChatMessage
              key={idx}
              msg={m}
              onCopy={async (txt) => { try { await navigator.clipboard.writeText(txt); } catch {} }}
              showRegenerate={idx === msgs.length - 1 && m.role === 'assistant'}
              onRegenerate={async () => {
                if (msgs.length === 0) return;
                const prev = [...msgs];
                // Remove the last assistant message
                if (prev[prev.length - 1]?.role === 'assistant') prev.pop();
                setLoading(true);
                try {
                  const resp = await chat(
                    prev.map((x) => ({ role: x.role, content: x.content })),
                    undefined,
                    filters,
                    8,
                  );
                  setMsgs([...prev, { role: 'assistant', content: resp.reply, products: resp.products, trace: resp.trace }]);
                } catch (e: any) {
                  setMsgs([...prev, { role: 'assistant', content: 'Error: ' + e.message }]);
                } finally {
                  setLoading(false);
                }
              }}
            />
          ))}
          {loading && (
            <div className="text-neutral-400 text-sm pl-2">
              The agent is thinking <LoadingDots />
            </div>
          )}
          <div ref={endRef} />
        </div>
      </section>

      <aside className="lg:col-span-1">
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Filters</h2>
          </div>
          <div className="mt-3">
            <FiltersPanel
              meta={meta}
              value={filters}
              onChange={setFilters}
              onClear={() => setFilters({})}
            />
          </div>
        </div>

        {/* ML Evaluation Dashboard CTA */}
        <Link href="/evaluation" className="block mt-6">
          <div className="card p-4 bg-gradient-to-br from-emerald-600 to-emerald-700 border-emerald-500 hover:from-emerald-500 hover:to-emerald-600 transition-all cursor-pointer">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-2xl">📊</span>
              <h2 className="font-semibold text-white">ML Evaluation</h2>
            </div>
            <p className="text-sm text-emerald-50 opacity-90 mb-3">
              View system metrics, run evaluations, and track performance over time.
            </p>
            <div className="flex items-center justify-between text-xs text-emerald-100">
              <span>View Dashboard →</span>
              <span className="opacity-75">Click to explore</span>
            </div>
          </div>
        </Link>

        <div className="card p-4 mt-6">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Suggested Prompts</h2>
            <span className="text-xs opacity-60">click to use</span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2">
            {[
              'Show me some nice t‑shirts',
              'Show some nice hoodies',
              'Show me some training shorts',
              'Show me some nice sneakers',
              'Show me cool backpacks',
              'Show me good headphones',
              'Show me fire jackets',
              'Show me some good leggings',
              'Show me some socks',
            ].map((s) => (
              <button
                key={s}
                className="text-left text-sm px-3 py-2 rounded-lg bg-neutral-900 border border-neutral-800 hover:bg-neutral-800"
                onClick={() => setInput(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="card p-4 mt-6">
          <h2 className="font-semibold">Latest Products</h2>
          {latestProducts.length === 0 ? (
            <div className="text-sm opacity-70 mt-2">Ask for a recommendation to see products here.</div>
          ) : (
            <div className="mt-3 space-y-3">
              {latestProducts.slice(0, 6).map((p: any) => (
                <Link
                  key={p.id}
                  href={`/product/${encodeURIComponent(p.id)}`}
                  className="flex gap-3 rounded-lg border border-neutral-800 hover:bg-neutral-900 p-2"
                >
                  {p.image_url && (
                    <img
                      src={(p.image_url?.startsWith('http') ? p.image_url : `${process.env.NEXT_PUBLIC_BACKEND_URL || ''}${p.image_url}`)}
                      className="h-14 w-14 rounded-md object-cover border border-neutral-800"
                      alt={p.title || 'product'}
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).src = '/placeholder.svg';
                      }}
                    />
                  )}
                  <div className="min-w-0">
                    <span className="text-sm font-medium truncate hover:underline">{p.title}</span>
                    <div className="text-xs opacity-75 truncate">
                      {[p.brand, p.category].filter(Boolean).join(' • ')}
                    </div>
                    <div className="text-xs mt-0.5">{p.price}{p.currency}</div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* General smalltalk is supported by typing naturally no auto fill needed. */}
        {/* Recently Viewed intentionally disabled for fresh sessions */}
      </aside>
    </div>
  );
}
