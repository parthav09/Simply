'use client';

import { useEffect } from 'react';

/**
 * Pointer-driven presentation only: writes --mx/--my (cursor position inside an element)
 * and --rx/--ry (tilt) as CSS variables. It never touches recording or business state.
 */
export default function HoverFx() {
  useEffect(() => {
    if (!matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const glow = '.surface-card, .steps article, .hero, .cta';
    const tilt = '.hero-stage';
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      const target = e.target as Element | null;
      if (!target) return;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const g = target.closest<HTMLElement>(glow);
        if (g) {
          const r = g.getBoundingClientRect();
          g.style.setProperty('--mx', `${e.clientX - r.left}px`);
          g.style.setProperty('--my', `${e.clientY - r.top}px`);
        }
        const t = target.closest<HTMLElement>(tilt);
        if (t) {
          const r = t.getBoundingClientRect();
          const px = (e.clientX - r.left) / r.width - 0.5;
          const py = (e.clientY - r.top) / r.height - 0.5;
          t.style.setProperty('--ry', `${(px * 7).toFixed(2)}deg`);
          t.style.setProperty('--rx', `${(-py * 7).toFixed(2)}deg`);
        }
      });
    };
    const onLeave = (e: PointerEvent) => {
      const t = (e.target as Element | null)?.closest<HTMLElement>(tilt);
      if (t && !t.contains(e.relatedTarget as Node | null)) {
        t.style.setProperty('--rx', '0deg');
        t.style.setProperty('--ry', '0deg');
      }
    };
    document.addEventListener('pointermove', onMove, { passive: true });
    document.addEventListener('pointerout', onLeave, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerout', onLeave);
    };
  }, []);
  return null;
}
