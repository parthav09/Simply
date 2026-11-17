'use client';

import {useEffect, useMemo, useState, type CSSProperties} from 'react';
import {loadRecording} from '../lib/recordings';
import {frameAt, type ReplayData} from '../lib/replay';
import {impulseBuys, money, totalOffListUnits} from '../lib/impulse';
import type {DemoCell} from '../lib/demo-runs';
import RecordedStoreMap from './RecordedStoreMap';
import {productEmoji} from './map-theme';
import {Icon} from './Icons';

/**
 * Presentation only: two verified recordings advanced by one shared decision counter.
 * Each pane shows its own recorded state at min(step, its length); nothing is simulated.
 */
export default function ComparePlayer({cells}: {cells: DemoCell[]}) {
  const [runs, setRuns] = useState<(ReplayData | null)[]>(cells.map(() => null));
  const [error, setError] = useState('');
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const key = cells.map(c => c.entry?.run_id ?? '-').join(':');

  useEffect(() => {
    let active = true;
    Promise.all(cells.map(c => c.entry ? loadRecording(c.entry) : Promise.resolve(null)))
      .then(loaded => {if (!active) return; setRuns(loaded); setStep(0); setError('');
        setPlaying(!window.matchMedia('(prefers-reduced-motion: reduce)').matches);})
      .catch(cause => {if (active) setError(cause.message);});
    return () => {active = false;};
    // cells identity is captured by key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const length = Math.max(0, ...runs.map(r => r?.events.length ?? 0));
  const running = playing && step < length;
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setStep(n => Math.min(n + 1, length)), 400 / speed);
    return () => window.clearInterval(id);
  }, [running, speed, length]);

  if (error) return <div className="replay-empty" role="alert"><h3>Recording unavailable</h3><p>{error}</p></div>;
  const toggle = () => {if (step >= length) setStep(0); setPlaying(!running);};
  return <section className="compare-player" aria-label="Side-by-side replay">
    <div className="compare-grid">
      {cells.map((cell, i) => <ComparePane key={cell.layoutId} cell={cell} run={runs[i]} step={step}/>)}
    </div>
    <div className="compare-controls">
      <button className="play-button" onClick={toggle} disabled={!length} aria-label={running ? 'Pause both replays' : 'Play both replays'}>
        <Icon name={running ? 'pause' : step >= length && length ? 'reset' : 'play'} size={16}/><span>{running ? 'Pause' : step >= length && length ? 'Replay' : 'Play both'}</span>
      </button>
      <input type="range" aria-label="Shared timeline" min={0} max={length} value={step} disabled={!length}
        style={{'--progress': `${length ? step / length * 100 : 0}%`} as CSSProperties}
        onChange={e => {setPlaying(false); setStep(Number(e.target.value));}}/>
      <span className="compare-step">Decision <b>{step}</b> / {length}</span>
      <div className="speed-control" role="group" aria-label="Playback speed">{[1, 4, 8, 16].map(n => <button key={n} aria-pressed={speed === n} onClick={() => setSpeed(n)}>{n}×</button>)}</div>
    </div>
    <p className="compare-note">Both stores advance one recorded decision per tick. When one recording reaches its last decision it holds there while the other continues.</p>
  </section>;
}

function ComparePane({cell, run, step}: {cell: DemoCell; run: ReplayData | null; step: number}) {
  const cursor = run ? Math.min(step, run.events.length) : 0;
  const frame = useMemo(() => run ? frameAt(run, cursor) : null, [run, cursor]);
  const found = useMemo(() => run ? impulseBuys(run, cursor) : [], [run, cursor]);
  const marks = useMemo(() => {const m = new Map<string, number>(); for (const f of found) m.set(f.productId, (m.get(f.productId) ?? 0) + 1); return m;}, [found]);
  const latest = found.at(-1);
  const fresh = latest && cursor - latest.event.sequence < 12 ? latest : undefined;
  const done = !!run && cursor >= run.events.length;
  if (!cell.entry) return <article className="compare-pane is-missing"><header><strong>{cell.layoutLabel}</strong></header><div className="replay-empty"><h3>No recording</h3><p>This model has no recorded trip on {cell.layoutLabel}.</p></div></article>;
  return <article className={`compare-pane ${cell.partial ? 'is-partial' : ''}`}>
    <header>
      <div><strong>{cell.layoutLabel}</strong><small>{cell.layoutDescription}</small></div>
      {cell.partial ? <span className="state-tag warning">Incomplete recording</span> : done ? <span className="state-tag success">Trip finished</span> : <span className="state-tag">Shopping</span>}
    </header>
    <div className="compare-map">
      {run && frame ? <RecordedStoreMap data={run} states={frame.states} summary={frame.summary} cursor={cursor}
        selected={fresh?.shopperId ?? run.events[cursor - 1]?.agent_id ?? run.shoppers[0].id} filter="" trail={false} heat={false}
        impulseMarks={marks} impulseFlash={fresh?.productId}/> : <div className="replay-empty" role="status"><h3>Opening the recording…</h3></div>}
    </div>
    {frame && run && <dl className="compare-stats">
      <div className="is-impulse"><dt>Impulse buys</dt><dd>{totalOffListUnits(frame.summary) ?? '—'}</dd></div>
      <div><dt>Checked out</dt><dd>{frame.summary.finished_count}<small>/{frame.summary.shopper_count}</small></dd></div>
      <div><dt>List fulfilled</dt><dd>{Math.round(frame.summary.mean_list_completion * 100)}%</dd></div>
      <div><dt>Decisions</dt><dd>{cursor}<small>/{run.events.length}</small></dd></div>
    </dl>}
    <p className={`compare-latest ${fresh ? 'is-fresh' : ''}`} aria-live="polite">{latest
      ? <><span aria-hidden="true">{productEmoji(latest.product ?? latest.productId)}</span><span><strong>{latest.shopperName.split(' ')[0]}</strong> grabbed {latest.product?.name ?? latest.productId} <em>{money(latest.product?.price)}</em> — not on their list</span></>
      : <span>{done ? 'No impulse buys in this trip.' : 'No impulse buys yet.'}</span>}</p>
    {cell.partial && <p className="compare-caveat">Stopped after {run?.events.length ?? '…'} decisions, before anyone checked out. Not comparable with a completed trip.</p>}
  </article>;
}
