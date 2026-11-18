'use client';

import { useEffect, useRef } from 'react';

const GAP = 28;
const RADIUS = 110;
const DECAY = 0.955;

/**
 * Decorative backdrop: a store grid of small shelf cells. The cursor walks through it like a
 * shopper, warming the cells it passes; the trail cools slowly, like a heat map of a trip.
 * Presentation only; it carries no recording data.
 */
export default function ShelfField() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
    let w = 0, h = 0, cols = 0, rows = 0, raf = 0;
    let heat = new Float32Array(0);
    let last: { x: number; y: number } | null = null;

    const parse = (hex: string) => {
      const v = hex.trim().replace('#', '');
      const f = v.length === 3 ? v.split('').map(c => c + c).join('') : v.slice(0, 6);
      return [0, 2, 4].map(i => parseInt(f.slice(i, i + 2), 16)) as [number, number, number];
    };

    const resize = () => {
      const dpr = Math.min(devicePixelRatio || 1, 2);
      w = innerWidth; h = innerHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.ceil(w / GAP) + 1; rows = Math.ceil(h / GAP) + 1;
      heat = new Float32Array(cols * rows);
      draw();
    };

    const inject = (x: number, y: number) => {
      const c0 = Math.max(0, Math.floor((x - RADIUS) / GAP)), c1 = Math.min(cols - 1, Math.ceil((x + RADIUS) / GAP));
      const r0 = Math.max(0, Math.floor((y - RADIUS) / GAP)), r1 = Math.min(rows - 1, Math.ceil((y + RADIUS) / GAP));
      for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
        const d = Math.hypot(c * GAP + GAP / 2 - x, r * GAP + GAP / 2 - y);
        if (d < RADIUS) { const k = Math.pow(1 - d / RADIUS, 1.3); const i = r * cols + c; if (k > heat[i]) heat[i] = k; }
      }
    };

    function draw(): boolean {
      if (!ctx) return false;
      const css = getComputedStyle(document.documentElement);
      const rest = parse(css.getPropertyValue('--color-text') || '#222');
      const warm = parse(css.getPropertyValue('--color-highlight') || '#d0bb36');
      const hot = parse(css.getPropertyValue('--color-impulse') || '#8a5f14');
      ctx.clearRect(0, 0, w, h);
      let alive = false;
      for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
        const i = r * cols + c;
        const t = heat[i];
        if (t > 0.01) { heat[i] = t * DECAY; alive = true; } else heat[i] = 0;
        const size = 4 + t * 12;
        const x = c * GAP + GAP / 2, y = r * GAP + GAP / 2;
        if (t > 0.04) {
          const m = Math.min(1, t * 1.15);
          // cool cells are mustard; the hottest centre turns bronze, like an impulse grab
          const q = Math.max(0, (t - 0.55) / 0.45);
          const col = warm.map((v, n) => Math.round(v + (hot[n] - v) * q)) as number[];
          ctx.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${0.25 + m * 0.7})`;
        } else {
          ctx.fillStyle = `rgba(${rest[0]},${rest[1]},${rest[2]},0.26)`;
        }
        const rad = size > 8 ? 3 : 1.4;
        ctx.beginPath();
        ctx.roundRect(x - size / 2, y - size / 2, size, size, rad);
        ctx.fill();
      }
      return alive;
    }

    const loop = () => { raf = draw() ? requestAnimationFrame(loop) : 0; };
    const kick = () => { if (!raf) raf = requestAnimationFrame(loop); };
    const onMove = (e: PointerEvent) => {
      const p = { x: e.clientX, y: e.clientY };
      if (last) {
        const steps = Math.max(1, Math.ceil(Math.hypot(p.x - last.x, p.y - last.y) / 18));
        for (let s = 1; s <= steps; s++) inject(last.x + (p.x - last.x) * s / steps, last.y + (p.y - last.y) * s / steps);
      } else inject(p.x, p.y);
      last = p; kick();
    };
    const onLeave = () => { last = null; };

    resize();
    addEventListener('resize', resize);
    const themeObserver = new MutationObserver(() => draw());
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    if (fine && !reduced) {
      addEventListener('pointermove', onMove, { passive: true });
      document.documentElement.addEventListener('pointerleave', onLeave);
    }
    return () => {
      cancelAnimationFrame(raf);
      removeEventListener('resize', resize);
      removeEventListener('pointermove', onMove);
      document.documentElement.removeEventListener('pointerleave', onLeave);
      themeObserver.disconnect();
    };
  }, []);

  return <canvas ref={ref} className="slash-field" aria-hidden="true" />;
}
