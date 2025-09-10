"use client";
// Search filters panel with dropdowns for brand, category, price, and tags
import React from 'react';
import type { FilterSpec } from '../lib_api';

type Meta = { brands: string[]; categories: string[]; price_min: number; price_max: number };

type Props = {
  meta: Meta | null;  // Catalog metadata for dropdown options
  value: FilterSpec;  // Current filter values
  onChange: (v: FilterSpec) => void;  // Update filters
  onClear: () => void;  // Clear all filters
};

export function FiltersPanel({ meta, value, onChange, onClear }: Props) {
  const [maxPrice, setMaxPrice] = React.useState<number | ''>(value.price_max ?? '');
  React.useEffect(() => {
    setMaxPrice(value.price_max ?? '');
  }, [value.price_max]);

  const update = (patch: Partial<FilterSpec>) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <select
          className="bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm"
          value={value.brand ?? ''}
          onChange={(e) => update({ brand: e.target.value || null })}
        >
          <option value="">Any brand</option>
          {meta?.brands.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
        <select
          className="bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm"
          value={value.category ?? ''}
          onChange={(e) => update({ category: e.target.value || null })}
        >
          <option value="">Any category</option>
          {meta?.categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-2 items-center">
        <input
          type="number"
          placeholder="Max price"
          className="bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm"
          value={maxPrice}
          onChange={(e) => {
            const v = e.target.value;
            setMaxPrice(v === '' ? '' : Number(v));
            update({ price_max: v === '' ? null : Number(v) });
          }}
        />
        <input
          type="text"
          placeholder="Tag contains (e.g. breathable)"
          className="bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm"
          value={value.tags_contains ?? ''}
          onChange={(e) => update({ tags_contains: e.target.value || null })}
        />
      </div>

      <div className="flex justify-between">
        <div className="text-xs opacity-70">Applied to the next message</div>
        <button type="button" className="text-xs text-neutral-300 hover:text-white" onClick={onClear}>
          Clear filters
        </button>
      </div>
    </div>
  );
}
