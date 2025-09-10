"use client";
// Image upload component with drag and drop, paste, and click support
import React from 'react';

type Props = {
  preview?: string | null;  // Base64 preview of uploaded image
  onFile: (file: File) => void;  // Called when user uploads a file
  onClear: () => void;  // Called when user removes the image
};

export function UploadBox({ preview, onFile, onClear }: Props) {
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Handle file drop from drag and drop
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  };
  // Handle file selection from file browser
  const handlePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) onFile(e.target.files[0]);
  };
  // Handle pasted images from clipboard
  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (it.type.startsWith('image/')) {
        const file = it.getAsFile();
        if (file) onFile(file);
        break;
      }
    }
  };

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onPaste={handlePaste}
        className="border-2 border-dashed border-neutral-700 rounded-xl p-4 text-sm flex items-center justify-between gap-3 hover:border-neutral-600 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-md bg-neutral-800 grid place-items-center">📷</div>
          <div>
            <div className="font-medium">Attach an image (optional)</div>
            <div className="opacity-70">Drag & drop, paste, or click to browse</div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="btn"
        >
          Browse
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={handlePick}
          className="hidden"
        />
      </div>
      {preview && (
        <div className="flex items-center gap-3">
          <img
            src={preview}
            alt="preview"
            className="h-16 w-16 rounded-lg object-cover border border-neutral-800"
          />
          <button
            type="button"
            className="text-sm text-red-400 hover:text-red-300"
            onClick={onClear}
          >
            Remove image
          </button>
        </div>
      )}
    </div>
  );
}