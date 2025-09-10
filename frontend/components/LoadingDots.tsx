"use client";
// Simple animated loading dots component
import React from 'react';

export function LoadingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce [animation-delay:-0.3s]"></span>
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce [animation-delay:-0.15s]"></span>
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce"></span>
    </span>
  );
}

