'use client';

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

/**
 * Shared deck shell. Keyboard: → / Space next, ← back, N notes, F fullscreen, Home / End.
 * Header and footer are fixed; the progress bar moves once per slide, not per build step.
 */
export type Slide = { section: string; title: string; steps?: number; body: ReactNode; notes: string; wide?: boolean };

const StepContext = createContext(0);

/** A build: hidden until the slide reaches step `at`. */
export function B({ at, children, as: Tag = 'div', className = '' }: { at: number; children: ReactNode; as?: 'div' | 'li' | 'span' | 'p'; className?: string }) {
  const step = useContext(StepContext);
  return <Tag className={`pz-build ${step >= at ? 'is-in' : ''} ${className}`} aria-hidden={step < at}>{children}</Tag>;
}

/** A code excerpt with a source label. Excerpts are condensed from the named file. */
export function Code({ file, children }: { file: string; children: string }) {
  return <figure className="pz-code"><figcaption>{file}</figcaption><pre><code>{children.replace(/^\n/, '')}</code></pre></figure>;
}

export function DeckShell({ slides, dense = false }: { slides: Slide[]; dense?: boolean }) {
  const [index, setIndex] = useState(0);
  const [step, setStep] = useState(0);
  const [notes, setNotes] = useState(false);
  const slide = slides[index];
  const steps = slide.steps ?? 0;
  const go = useCallback((next: number, nextStep = 0) => {
    const i = Math.max(0, Math.min(slides.length - 1, next));
    setIndex(i); setStep(nextStep === -1 ? (slides[i].steps ?? 0) : nextStep);
    try { window.history.replaceState(null, '', `#${i + 1}`); } catch { /* ignore */ }
  }, [slides]);
  const forward = useCallback(() => { if (step < steps) setStep(step + 1); else if (index < slides.length - 1) go(index + 1); }, [step, steps, index, go, slides.length]);
  const back = useCallback(() => { if (step > 0) setStep(step - 1); else if (index > 0) go(index - 1, -1); }, [step, index, go]);

  useEffect(() => {
    // Open the slide named in the URL (#12), on load and when the hash is edited by hand.
    const sync = () => { const n = Number(window.location.hash.slice(1)); if (Number.isInteger(n) && n >= 1 && n <= slides.length) go(n - 1); };
    const frame = window.requestAnimationFrame(sync);
    window.addEventListener('hashchange', sync);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener('hashchange', sync); };
  }, [go, slides.length]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('input, select, textarea') || e.metaKey || e.ctrlKey || e.altKey) return;
      if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); forward(); }
      else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); back(); }
      else if (e.key === 'Home') go(0);
      else if (e.key === 'End') go(slides.length - 1);
      else if (e.key.toLowerCase() === 'n') setNotes(v => !v);
      else if (e.key.toLowerCase() === 'f') { if (document.fullscreenElement) void document.exitFullscreen(); else void document.documentElement.requestFullscreen?.(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [forward, back, go, slides.length]);

  const sections = [...new Set(slides.map(s => s.section))];
  return <main className="pz-deck" id="main-content">
    <header className="pz-top"><span className="pz-brand">simply<span>.</span></span>
      <nav aria-label="Sections">{sections.map(s => <button key={s} aria-current={s === slide.section ? 'step' : undefined} onClick={() => go(slides.findIndex(x => x.section === s))}>{s}</button>)}</nav>
    </header>
    <StepContext.Provider value={step}>
      <section key={index} className={`pz-slide ${slide.wide ? 'is-wide' : ''} ${dense ? 'is-dense' : ''}`} aria-roledescription="slide" aria-label={`${index + 1} of ${slides.length}`}>{slide.body}</section>
    </StepContext.Provider>
    {notes && <aside className="pz-notes" aria-label="Speaker notes"><b>Notes</b><p>{slide.notes}</p></aside>}
    <footer className="pz-bottom">
      <button onClick={back} disabled={index === 0 && step === 0} aria-label="Previous">←</button>
      <div className="pz-progress" aria-hidden="true"><i style={{ width: `${index / Math.max(1, slides.length - 1) * 100}%` }}/></div>
      <button onClick={forward} disabled={index === slides.length - 1 && step === steps} aria-label="Next">→</button>
      <span className="pz-count">{index + 1} / {slides.length}</span>
      <span className="pz-steps-left">{steps > 0 && step < steps ? `+${steps - step}` : ''}</span>
      <button onClick={() => setNotes(v => !v)} aria-pressed={notes}>Notes (N)</button>
    </footer>
  </main>;
}
