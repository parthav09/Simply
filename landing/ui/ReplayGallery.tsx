'use client';

import Link from 'next/link';
import {useEffect, useState} from 'react';
import {loadDemoMatrix, modelShort, pick, type DemoMatrix} from '../lib/demo-runs';
import {loadCatalog} from '../lib/recordings';
import type {CatalogEntry} from '../lib/replay';
import ReplayWorkspace from './ReplayWorkspace';
import ComparePlayer from './ComparePlayer';
import {Icon} from './Icons';

type Mode = 'watch' | 'compare';

/** Demo browser: fixed, documented recordings per model and layout. Display state only. */
export default function ReplayGallery() {
  const [matrix, setMatrix] = useState<DemoMatrix | null>(null);
  const [error, setError] = useState('');
  const [model, setModel] = useState('');
  const [layout, setLayout] = useState('');
  const [variant, setVariant] = useState(0);
  const [mode, setMode] = useState<Mode>('watch');
  // A deep link (?run=&shopper=) to any published recording, e.g. the home page receipt.
  const [linked, setLinked] = useState<{entry: CatalogEntry; shopper?: string} | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([loadDemoMatrix(), loadCatalog()]).then(([m, catalog]) => {
      if (!active) return;
      const params = new URLSearchParams(window.location.search);
      const run = params.get('run');
      const cells = m.models.flatMap(x => x.cells);
      const inCell = run ? cells.find(c => c.runs.some(r => r.entry.run_id === run)) : undefined;
      const linkedEntry = run && !inCell ? catalog.runs.find(r => r.run_id === run) : undefined;
      if (linkedEntry) setLinked({entry: linkedEntry, shopper: params.get('shopper') ?? undefined});
      const wantedModel = m.models.find(x => x.id === (inCell?.modelId ?? params.get('model'))) ?? m.models[0];
      const wantedLayout = m.layouts.find(l => l.id === (inCell?.layoutId ?? params.get('layout'))) ?? m.layouts[0];
      const wantedVariant = inCell ? Math.max(0, inCell.runs.findIndex(r => r.entry.run_id === run)) : Math.max(0, Number(params.get('run_n') ?? 1) - 1);
      setMatrix(m); setModel(wantedModel?.id ?? ''); setLayout(wantedLayout?.id ?? ''); setVariant(wantedVariant);
      if (params.get('view') === 'compare') setMode('compare');
    }).catch(cause => {if (active) setError(cause.message);});
    return () => {active = false;};
  }, []);

  useEffect(() => {
    if (!model || linked) return;
    const params = new URLSearchParams({model, layout, run_n: String(variant + 1), ...(mode === 'compare' ? {view: 'compare'} : {})});
    window.history.replaceState(null, '', `?${params}`);
  }, [model, layout, variant, mode, linked]);

  if (error) return <div className="replay-empty" role="alert"><h2>Replays unavailable</h2><p>{error}. Published recordings are required to show these trips.</p></div>;
  if (!matrix) return <div className="replay-empty" role="status"><h2>Loading recordings…</h2><p>Verifying the published recordings.</p></div>;
  if (!matrix.models.length) return <div className="replay-empty"><h2>No recordings published yet</h2><p>Run a study and publish it to Evidence to see replays here.</p></div>;

  const current = matrix.models.find(m => m.id === model) ?? matrix.models[0];
  const cell = current.cells.find(c => c.layoutId === layout) ?? current.cells[0];
  const chosen = pick(cell, variant);
  const chosenRun = cell.runs[Math.min(variant, cell.runs.length - 1)];
  const free = (next: () => void) => {setLinked(null); next();};
  const layoutLabel = (id: string) => matrix.layouts.find(l => l.id === id)?.label ?? id;
  const mostRuns = Math.max(...current.cells.map(c => c.runs.length));

  return <>
    <header className="page-head">
      <div><h1>Replays</h1><p>Watch a saved trip. Amber marks are items that were never on the shopper’s list.</p></div>
      <div className="replay-picker">
        <div className="seg" role="group" aria-label="Model">{matrix.models.map(m => <button key={m.id} aria-pressed={!linked && m.id === current.id} onClick={() => free(() => setModel(m.id))}>{m.short}</button>)}</div>
        <div className="seg" role="group" aria-label="Store layout">{matrix.layouts.map(l => {
          const c = current.cells.find(x => x.layoutId === l.id);
          const partial = !!c?.runs.length && c.runs.every(r => r.partial);
          return <button key={l.id} aria-pressed={!linked && mode === 'watch' && l.id === cell.layoutId} onClick={() => free(() => {setLayout(l.id); setMode('watch');})} title={partial ? `${l.description} · incomplete recording` : l.description}>{l.label}{partial && <span className="seg-flag" aria-label="incomplete">!</span>}</button>;
        })}
          <button aria-pressed={!linked && mode === 'compare'} onClick={() => free(() => setMode('compare'))} title="Both layouts side by side">Compare</button></div>
        {mostRuns > 1 && <div className="seg" role="group" aria-label="Recording">{Array.from({length: mostRuns}, (_, i) => <button key={i} aria-pressed={!linked && variant === i} onClick={() => free(() => setVariant(i))}>Run {i + 1}</button>)}</div>}
      </div>
    </header>

    {linked
      ? <><p className="lab-note linked-note" role="status">Linked trip · {modelShort(linked.entry.model)} on {layoutLabel(linked.entry.layout_id)}, recorded {new Date(linked.entry.recorded_at).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})}. Pick a model above to browse the comparison runs.</p>
          <ReplayWorkspace runId={linked.entry.run_id} shopperId={linked.shopper}/></>
      : mode === 'compare'
        ? <ComparePlayer key={`${current.id}:${variant}`} cells={current.cells.map(c => pick(c, variant))}/>
        : chosen.entry
          ? <>{chosenRun && <p className="lab-note run-facts" role="status">{current.short} · {cell.layoutLabel} · run {Math.min(variant, cell.runs.length - 1) + 1} of {cell.runs.length} · {chosenRun.finished}/{chosenRun.trips} shoppers paid · {chosenRun.purchased}/{chosenRun.requested} list items · {chosenRun.impulse ?? '—'} impulse {chosenRun.impulse === 1 ? 'buy' : 'buys'}{chosenRun.partial && ' · incomplete recording, not comparable with a finished trip'}</p>}
              <ReplayWorkspace runId={chosen.entry.run_id}/></>
          : <div className="replay-empty"><h3>No recording</h3><p>{current.short} has no recorded trip on {cell.layoutLabel}.</p></div>}

    <details className="replay-provenance">
      <summary>How these recordings were chosen</summary>
      <p>{matrix.rule}</p>
      <Link className="text-link" href="/evaluation">Open Results <Icon name="arrow" size={13}/></Link>
    </details>
  </>;
}
