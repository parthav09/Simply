'use client';

import {useEffect, useMemo, useRef, useState} from 'react';
import {loadDemoRecording} from '../lib/recordings';
import {frameAt, type ReplayData} from '../lib/replay';
import RecordedStoreMap from './RecordedStoreMap';

const demoSpeed = 2;
const eventInterval = 480 / demoSpeed;

function ReplayDemo({layoutId, label, name}: {layoutId: string; label: string; name: string}) {
  const [run, setRun] = useState<ReplayData | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const container = useRef<HTMLElement>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const data = await loadDemoRecording(layoutId);
      if (!cancelled) setRun(data);
    };
    load().catch(error => {if (!cancelled) setError(error.message);});
    return () => {cancelled = true;};
  }, [layoutId]);

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let visible = false;
    const update = () => setPlaying(visible && !document.hidden && !preference.matches);
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      update();
    }, {threshold: .15});
    if (container.current) observer.observe(container.current);
    preference.addEventListener('change', update);
    document.addEventListener('visibilitychange', update);
    return () => {
      observer.disconnect();
      preference.removeEventListener('change', update);
      document.removeEventListener('visibilitychange', update);
    };
  }, []);

  // Presentation only: advance through verified Python events and loop the recording.
  useEffect(() => {
    if (!playing || !run?.events.length) return;
    const timer = window.setTimeout(() => setCursor(n => n === run.events.length ? 0 : n + 1),
      cursor === run.events.length ? 2400 : eventInterval);
    return () => window.clearTimeout(timer);
  }, [playing, run, cursor]);

  const frame = useMemo(() => run ? frameAt(run, cursor) : null, [run, cursor]);
  const selected = run?.events[cursor - 1]?.agent_id ?? run?.shoppers[0]?.id ?? '';

  return <figure ref={container} className="replay-demo" aria-label={`${label} recorded demo`}>
    <header className="replay-demo-heading"><div><span className="eyebrow">{label}</span><h3>{name}</h3></div><span className="state-tag">Demo · 2×</span></header>
    {run && frame ? <>
      <RecordedStoreMap data={run} states={frame.states} summary={frame.summary} cursor={cursor}
        selected={selected} filter="" trail={false} heat={false}/>
      <figcaption className="replay-demo-caption"><span>{run.shoppers.length} shoppers · {run.source.model}</span><span>Event {cursor} / {run.events.length}</span></figcaption>
      <p className="replay-demo-source">Completed recording · {run.source.run_id.slice(0,8)}</p>
    </> : <div className="replay-empty" role={error ? 'alert' : 'status'}><h3>{error ? 'Recording unavailable' : 'Opening the demo…'}</h3><p>{error || 'Loading the recorded shopper journey.'}</p></div>}
  </figure>;
}

export default function LandingReplayDemos() {
  return <>
    <header className="replay-heading"><div><p className="eyebrow">Recorded simulations</p><h2>Two layouts. See the journeys.</h2><p>A top-down demo of completed shopper runs, replayed at 2× speed.</p></div></header>
    <div className="replay-demo-grid">
      <ReplayDemo layoutId="costco_back_anchor" label="Layout A" name="Anchor loop"/>
      <ReplayDemo layoutId="neighborhood_express" label="Layout B" name="Express essentials"/>
    </div>
  </>;
}
