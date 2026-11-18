/** Simply mark: a basket with one item dropping in — the item nobody planned for. */
export function BrandMark({ size = 30 }: { size?: number }) {
  return <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="9" className="bm-bg" />
    <circle cx="16" cy="8.6" r="3.1" className="bm-dot" />
    <rect x="6.5" y="13.5" width="19" height="3.4" rx="1.7" className="bm-glyph" />
    <path d="M8.6 18.6h14.8l-1.5 6.4a2 2 0 0 1-1.95 1.55h-7.9A2 2 0 0 1 10.1 25l-1.5-6.4Z" className="bm-glyph" />
  </svg>;
}

export function Wordmark() {
  return <><BrandMark /><span className="brand-word">simply<span className="brand-dot">.</span></span></>;
}
