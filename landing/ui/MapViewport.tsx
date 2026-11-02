'use client';

import { useEffect, useRef, type ReactNode } from 'react';

/** The workspace follows the store's proportions. Zoom pans inside the map. */
export default function MapViewport({ children, zoom, width, height }: {
  children: ReactNode; zoom: number; width: number; height: number;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const panel = element.closest('.replay-map-panel') as HTMLElement;
    const lab = element.closest('.recorded-lab') as HTMLElement;
    const content = element.closest('.lab-content') as HTMLElement | null;
    let frame = 0;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!panel || !lab) return;
        const body = lab.querySelector('.replay-body');
        const column = lab.querySelector('.replay-main-column') as HTMLElement | null;
        const top = element.getBoundingClientRect().top + window.scrollY;
        const controls = [...panel.children].filter(child => child !== element && !child.classList.contains('replay-map-heading'))
          .reduce((total, child) => total + child.getBoundingClientRect().height, 0);
        const available = Math.max(200, Math.min(720, window.innerHeight - top - controls - 20));
        const inspector = lab.querySelector('.replay-inspector') as HTMLElement | null;
        const gap = body ? parseFloat(getComputedStyle(body).columnGap) || 0 : 0;
        const sidebar = window.innerWidth > 760 ? (inspector?.offsetWidth ?? 280) + gap : 0;
        content?.style.setProperty('--lab-width', `${Math.round(available * width / height + sidebar)}px`);
        lab.style.setProperty('--map-panel-height', `${(column ?? panel).offsetHeight}px`);
      });
    };
    if (!panel || !lab) return;
    const observer = new ResizeObserver(measure);
    observer.observe(panel);
    if (content) observer.observe(content);
    window.addEventListener('resize', measure);
    measure();
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener('resize', measure); content?.style.removeProperty('--lab-width'); };
  }, [width, height]);
  useEffect(() => { if (zoom === 1) viewport.current?.scrollTo({ top: 0, left: 0 }); }, [zoom]);

  return <div ref={viewport} className="map-viewport" style={{ aspectRatio: `${width} / ${height}` }} tabIndex={0} aria-label="Store map viewport. Zoom to inspect items; scroll within this panel." role="region">
    <div className="map-scale" style={{ width: `${zoom * 100}%`, aspectRatio: `${width} / ${height}` }}>{children}</div>
  </div>;
}
