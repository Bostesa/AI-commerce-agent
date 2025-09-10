"use client";
// Chat message component - handles both user and assistant messages
// Shows products when the AI recommends them
import React from 'react';
import Link from 'next/link';

export type Msg = {
  role: 'user' | 'assistant';
  content: string;        // The text message
  products?: any[];       // Products recommended by the AI (if any)
  trace?: any;           // Debug info about how the response was generated
};

function resolveImage(url?: string): string | undefined {
  // Handle both absolute URLs and relative paths from our backend
  if (!url) return undefined;
  if (/^https?:\/\//i.test(url)) return url; // already absolute
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || '';
  return `${base}${url}`; // make it absolute
}

type Actions = {
  onCopy?: (text: string) => void;
  onRegenerate?: () => void;
  showRegenerate?: boolean;
};

export function ChatMessage({ msg, onCopy, onRegenerate, showRegenerate }: { msg: Msg } & Actions) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="mr-2 mt-1 h-8 w-8 shrink-0 rounded-full bg-emerald-500/20 text-emerald-300 grid place-items-center text-xs font-semibold">
          AI
        </div>
      )}
      <div
        className={`max-w-[85%] sm:max-w-[70%] rounded-2xl px-4 py-3 leading-relaxed shadow-sm border ${
          isUser
            ? 'bg-emerald-600 text-white border-emerald-500'
            : 'bg-neutral-900 border-neutral-800'
        }`}
      >
        <div className="whitespace-pre-wrap">{msg.content}</div>
        {Array.isArray(msg.products) && msg.products.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
            {msg.products.map((p: any) => (
              <div key={p.id} className="card p-3">
                <div className="flex gap-3">
                  {p.image_url && (
                    <Link href={`/product/${encodeURIComponent(p.id)}`}>
                      <img
                        src={resolveImage(p.image_url)}
                        alt={p.title || 'product image'}
                        className="h-16 w-16 rounded-md object-cover border border-neutral-800"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).src = '/placeholder.svg';
                        }}
                      />
                    </Link>
                  )}
                  <div className="min-w-0">
                    <Link href={`/product/${encodeURIComponent(p.id)}`} className="font-medium truncate hover:underline">{p.title}</Link>
                    <div className="text-xs opacity-80 truncate">
                      {[p.brand, p.category].filter(Boolean).join(' • ')}
                    </div>
                    <div className="text-sm mt-1">
                      {p.price}
                      {p.currency}
                    </div>
                  </div>
                </div>
                {p.tags && (
                  <div className="text-xs opacity-75 mt-2 truncate">{p.tags}</div>
                )}
                <div className="mt-2 text-xs flex gap-3">
                  <Link className="text-emerald-400 hover:underline" href={`/product/${encodeURIComponent(p.id)}`}>Details</Link>
                  {p.product_url && (
                    <a className="text-blue-400 hover:underline" href={p.product_url} target="_blank" rel="noreferrer">Buy</a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-2 flex gap-3 text-xs opacity-80">
          {onCopy && (
            <button className="hover:underline" onClick={() => onCopy(msg.content)}>Copy</button>
          )}
          {!isUser && showRegenerate && onRegenerate && (
            <button className="hover:underline" onClick={onRegenerate}>Regenerate</button>
          )}
        </div>
        {msg.trace && (
          <details className="mt-2 opacity-80 text-xs">
            <summary className="cursor-pointer">Details</summary>
            <pre className="mt-1 whitespace-pre-wrap break-words">{JSON.stringify(msg.trace, null, 2)}</pre>
          </details>
        )}
      </div>
      {isUser && (
        <div className="ml-2 mt-1 h-8 w-8 shrink-0 rounded-full bg-emerald-500/20 text-emerald-300 grid place-items-center text-xs font-semibold">
          You
        </div>
      )}
    </div>
  );
}
