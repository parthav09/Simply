'use client';

import Link from 'next/link';
import {useEffect, useMemo, useRef, useState} from 'react';
import {loadShowcaseRecording} from '../lib/recordings';
import {frameAt, type ReplayData} from '../lib/replay';
import {impulseBuys, money} from '../lib/impulse';
import RecordedStoreMap from './RecordedStoreMap';
import {productEmoji} from './map-theme';
import {Icon} from './Icons';

const interval = 110;

/** Presentation only: loops verified Python events and highlights recorded off-list grabs. */
export default function ImpulseReplayDemo() {
  const [run, setRun] = useState<ReplayData | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const container = useRef<HTMLElement>(null);

  useEffect(() => {
    let active = true;
    // Reduced motion: show the finished trip rather than an empty start.
    loadShowcaseRecording().then(({run}) => {if (!active) return; setRun(run); if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) setCursor(run.events.length);}).catch(cause => {if (active) setError(cause.message);});
    return () => {active = false;};
  }, []);

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let visible = false;
    const update = () => setPlaying(visible && !document.hidden && !preference.matches);
    const observer = new IntersectionObserver(([entry]) => {visible = entry.isIntersecting; update();}, {threshold: .2});
    if (container.current) observer.observe(container.current);
    preference.addEventListener('change', update);
    document.addEventListener('visibilitychange', update);
    return () => {observer.disconnect(); preference.removeEventListener('change', update); document.removeEventListener('visibilitychange', update);};
  }, []);

  useEffect(() => {
    if (!playing || !run?.events.length) return;
    const timer = window.setTimeout(() => setCursor(n => n === run.events.length ? 0 : n + 1), cursor === run.events.length ? 3000 : interval);
    return () => window.clearTimeout(timer);
  }, [playing, run, cursor]);

  const frame = useMemo(() => run ? frameAt(run, cursor) : null, [run, cursor]);
  const found = useMemo(() => run ? impulseBuys(run, cursor) : [], [run, cursor]);
  const marks = useMemo(() => {const m = new Map<string, number>(); for (const f of found) m.set(f.productId, (m.get(f.productId) ?? 0) + 1); return m;}, [found]);
  const latest = found.at(-1);
  const fresh = latest && cursor - latest.event.sequence < 14 ? latest : undefined;
  const selected = fresh?.shopperId ?? run?.events[cursor - 1]?.agent_id ?? run?.shoppers[0]?.id ?? '';

  return <section ref={container} className="impulse-demo" aria-label="Recorded trip with impulse buys highlighted">
    <div className="impulse-demo-map">
      {run && frame ? <RecordedStoreMap data={run} states={frame.states} summary={frame.summary} cursor={cursor} selected={selected} filter="" trail={false} heat={false} impulseMarks={marks} impulseFlash={fresh?.productId}/>
        : <div className="replay-empty" role={error ? 'alert' : 'status'}><h3>{error ? 'Recording unavailable' : 'Opening the recording…'}</h3><p>{error || 'Loading a saved trip.'}</p></div>}
      {run && <div className="impulse-demo-progress" aria-hidden="true"><i style={{width: `${run.events.length ? cursor / run.events.length * 100 : 0}%`}}/></div>}
    </div>
    <aside className="impulse-ticker" aria-live="polite">
      <header><span className="ticker-count">{found.length}</span><div><strong>Impulse buys spotted</strong><small>{run ? `${run.shoppers.length} shoppers · decision ${cursor} of ${run.events.length}` : '—'}</small></div></header>
      {found.length ? <ol>{[...found].reverse().slice(0, 4).map(f => <li key={f.event.sequence} className={f === fresh ? 'is-fresh' : ''}>
        <span className="item-emoji" aria-hidden="true">{productEmoji(f.product ?? f.productId)}</span>
        <div><strong>{f.product?.name ?? f.productId} <em>{money(f.product?.price)}</em></strong><small>{f.shopperName.split(' ')[0]} · not on their list</small></div>
      </li>)}</ol> : <p className="ticker-empty">Watching for items that aren’t on anyone’s list…</p>}
      <Link className="text-link" href={run ? `/lab?run=${run.source.run_id}` : '/lab'}>Inspect every decision <Icon name="arrow" size={14}/></Link>
    </aside>
  </section>;
}
