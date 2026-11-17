'use client';

import {useEffect, useState} from 'react';
import {loadDemoMatrix, modelShort, type DemoMatrix} from '../lib/demo-runs';
import {loadCatalog} from '../lib/recordings';
import type {CatalogEntry} from '../lib/replay';
import ReplayWorkspace from './ReplayWorkspace';
import ComparePlayer from './ComparePlayer';

type Mode = 'watch' | 'compare';

/** Demo browser: one Evidence-selected recording per model and layout. Display state only. */
export default function ReplayGallery() {
  const [matrix, setMatrix] = useState<DemoMatrix | null>(null);
  const [error, setError] = useState('');
  const [model, setModel] = useState('');
  const [layout, setLayout] = useState('');
  const [mode, setMode] = useState<Mode>('watch');
  // A deep link (?run=&shopper=) to any published recording, e.g. the home page receipt.
  const [linked, setLinked] = useState<{entry: CatalogEntry; shopper?: string} | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([loadDemoMatrix(), loadCatalog()]).then(([m, catalog]) => {
      if (!active) return;
      const params = new URLSearchParams(window.location.search);
      const run = params.get('run');
      const cellMatch = m.models.flatMap(x => x.cells).find(c => c.entry?.run_id === run);
      const linkedEntry = run && !cellMatch ? catalog.runs.find(r => r.run_id === run) : undefined;
      if (linkedEntry) setLinked({entry: linkedEntry, shopper: params.get('shopper') ?? undefined});
      if (cellMatch) {params.set('model', cellMatch.modelId); params.set('layout', cellMatch.layoutId);}
      const wantedModel = m.models.find(x => x.id === params.get('model')) ?? m.models[0];
      const wantedLayout = m.layouts.find(l => l.id === params.get('layout')) ?? m.layouts[0];
      setMatrix(m); setModel(wantedModel?.id ?? ''); setLayout(wantedLayout?.id ?? '');
      if (params.get('view') === 'compare') setMode('compare');
    }).catch(cause => {if (active) setError(cause.message);});
    return () => {active = false;};
  }, []);

  useEffect(() => {
    if (!model || linked) return;
    const params = new URLSearchParams({model, layout, ...(mode === 'compare' ? {view: 'compare'} : {})});
    window.history.replaceState(null, '', `?${params}`);
  }, [model, layout, mode, linked]);

  if (error) return <div className="replay-empty" role="alert"><h2>Replays unavailable</h2><p>{error}. Published recordings are required to show these trips.</p></div>;
  if (!matrix) return <div className="replay-empty" role="status"><h2>Loading recordings…</h2><p>Verifying the published Evidence selection.</p></div>;
  if (!matrix.models.length) return <div className="replay-empty"><h2>No recordings published yet</h2><p>Run a study and publish it to Evidence to see replays here.</p></div>;

  const current = matrix.models.find(m => m.id === model) ?? matrix.models[0];
  const cell = current.cells.find(c => c.layoutId === layout) ?? current.cells[0];
  const pick = (next: () => void) => {setLinked(null); next();};
  const layoutLabel = (id: string) => matrix.layouts.find(l => l.id === id)?.label ?? id;

  return <>
    <header className="page-head">
      <div><h1>Replays</h1><p>Watch a saved trip. Amber marks are items that were never on the shopper’s list.</p></div>
      <div className="replay-picker">
        <div className="seg" role="group" aria-label="Model">{matrix.models.map(m => <button key={m.id} aria-pressed={!linked && m.id === current.id} onClick={() => pick(() => setModel(m.id))}>{m.short}</button>)}</div>
        <div className="seg" role="group" aria-label="Store layout">{matrix.layouts.map(l => <button key={l.id} aria-pressed={!linked && mode === 'watch' && l.id === cell.layoutId} onClick={() => pick(() => {setLayout(l.id); setMode('watch');})} title={current.cells.find(c => c.layoutId === l.id)?.partial ? `${l.description} · incomplete recording` : l.description}>{l.label}{current.cells.find(c => c.layoutId === l.id)?.partial && <span className="seg-flag" aria-label="incomplete">!</span>}</button>)}
          <button aria-pressed={!linked && mode === 'compare'} onClick={() => pick(() => setMode('compare'))} title="Both layouts side by side">Compare</button></div>
      </div>
    </header>

    {linked
      ? <><p className="lab-note linked-note" role="status">Linked trip · {modelShort(linked.entry.model)} on {layoutLabel(linked.entry.layout_id)}, recorded {new Date(linked.entry.recorded_at).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})}. Pick a model above to browse the comparison runs.</p>
          <ReplayWorkspace runId={linked.entry.run_id} shopperId={linked.shopper}/></>
      : mode === 'compare'
      ? <ComparePlayer key={current.id} cells={current.cells}/>
      : cell.entry
        ? <>
            <ReplayWorkspace runId={cell.entry.run_id}/></>
        : <div className="replay-empty"><h3>No recording</h3><p>{current.short} has no recorded trip on {cell.layoutLabel}.</p></div>}

  </>;
}
