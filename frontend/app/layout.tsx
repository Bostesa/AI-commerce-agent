// Root layout component that wraps all pages with header and footer
import type { Metadata } from 'next';
import '../styles/globals.css';
import { Inter } from 'next/font/google';
import Link from 'next/link';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'AI Commerce Agent',
  description: 'Chat about products and get recommendations',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-neutral-950 text-neutral-100">
          <header className="border-b border-neutral-900/80 bg-black/20 backdrop-blur supports-[backdrop-filter]:bg-black/10 sticky top-0 z-10">
            <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-3 hover:opacity-90">
                <div className="h-8 w-8 rounded-md bg-emerald-600 grid place-items-center font-semibold">AI</div>
                <div className="font-semibold">AI Commerce Agent</div>
              </Link>
              <div className="flex items-center gap-4">
                <Link
                  href="/evaluation"
                  className="text-sm text-neutral-300 hover:text-white flex items-center gap-1"
                >
                  <span>📊</span>
                  <span>Evaluation</span>
                </Link>
                <a
                  href={`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/docs`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-neutral-300 hover:text-white"
                >
                  Live Docs
                </a>
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
          <footer className="mx-auto max-w-6xl px-4 pb-8 pt-4 text-center text-xs opacity-60">
            Built with Next.js 14 • Tailwind CSS
          </footer>
        </div>
      </body>
    </html>
  );
}
