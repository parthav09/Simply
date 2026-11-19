'use client';

import { useEffect, useState } from 'react';
import ComparePlayer from '../ui/ComparePlayer';
import { useDashboardData } from '../ui/useDashboardData';
import { loadDemoMatrix, pick, type DemoMatrix } from '../lib/demo-runs';
import { formatHistoryMetric as format } from '../lib/evidence';
import checks from '../data/run-checks.json';

/**
 * Presentation widgets. Display only: recordings and metrics come from Python-written files
 * (published replays, evidence-dashboard.json, run-checks.json). Nothing here simulates,
 * scores or invents an outcome; bar widths are chart geometry.
 */

/* ── One decision, animated ─────────────────────────────────────────────── */
const STAGES = [
  ['Observe', 'core/perception.py → agents/prompts.py', 'Python writes the prompt: profile, position, cart, nearby shelves, turns left, allowed steps. The state is snapshotted so the reply is tied to what the shopper saw.'],
  ['Propose', 'core/rounds.py → provider', 'The model returns one action as strict JSON: step, product_id, reason. Up to N shoppers wait on the API at once; workers never touch state.'],
  ['Check', 'agents/schema.py', 'Is it valid JSON for the schema? Is the step in the allowed steps for this state? If not, it is recorded as an invalid reply.'],
  ['Assist', 'core/navigation.py', 'guided_nav_v3 may replace the proposal (grab a reachable list item, head to checkout, avoid busy cells). Both versions are recorded.'],
  ['Apply', 'core/grid.py · core/shopping.py', 'Python applies the action or rejects it (not reachable, duplicate SKU). Only checkout turns a cart into a purchase.'],
  ['Record', 'core/run_log.py', 'The before/after state, prompt, raw reply, proposal, adjustment and outcome are flushed to the canonical log. If logging fails, the run stops.'],
  ['Replay', 'lib/replay.ts', 'React verifies hashes and redraws the recorded states. Seeking never applies an action.'],
] as const;

export function Pipeline() {
  const [active, setActive] = useState(0);
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    if (!auto || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const id = window.setInterval(() => setActive(a => (a + 1) % STAGES.length), 2200);
    return () => window.clearInterval(id);
  }, [auto]);
  const [title, file, text] = STAGES[active];
  return <div className="pz-pipeline">
    <ol className="pz-stages">{STAGES.map(([name], i) => <li key={name}>
      <button aria-pressed={i === active} className={i < active ? 'is-past' : ''} onClick={() => { setAuto(false); setActive(i); }}>
        <small>0{i + 1}</small>{name}{i === 3 && <em>may override</em>}
      </button></li>)}</ol>
    <div className="pz-track" aria-hidden="true"><span style={{ left: `${(active + 0.5) / STAGES.length * 100}%` }}/></div>
    <article className="pz-stage-detail" key={active}><p className="pz-file">{file}</p><h3>{title}</h3><p>{text}</p></article>
    <p className="pz-hint">{auto ? 'Auto-playing · click a step to stop' : <button onClick={() => setAuto(true)}>Resume auto-play</button>}</p>
  </div>;
}

/* ── Live replay of recorded runs ───────────────────────────────────────── */
export function LiveReplay({ initial = 'gpt-6.1-terra' }: { initial?: string }) {
  const [matrix, setMatrix] = useState<DemoMatrix | null>(null);
  const [error, setError] = useState('');
  const [model, setModel] = useState(initial);
  useEffect(() => { loadDemoMatrix().then(setMatrix).catch(cause => setError(cause.message)); }, []);
  if (error) return <div className="replay-empty" role="alert"><h3>Recordings unavailable</h3><p>{error}</p></div>;
  if (!matrix) return <div className="replay-empty" role="status"><h3>Verifying the recordings…</h3></div>;
  const current = matrix.models.find(m => m.id === model) ?? matrix.models[0];
  return <div className="pz-live">
    <div className="pz-segmented" role="group" aria-label="Model">{matrix.models.map(m => <button key={m.id} aria-pressed={m.id === current.id} onClick={() => setModel(m.id)}>{m.short}</button>)}</div>
    <ComparePlayer key={current.id} cells={current.cells.map(c => pick(c, 0))}/>
  </div>;
}

/* ── Results bars from the Python dashboard ─────────────────────────────── */
const RESULT_METRICS = ['impulse_units_per_trip', 'purchased_unit_fulfillment', 'checkout_completion', 'provider_reported_cost_per_checkout_usd', 'requests_per_trip'] as const;
const SHORT: Record<string, string> = { 'gpt-6-luna': 'Luna', 'gpt-6.1-terra': 'Terra', 'qwen2.5-7b-instruct': 'Qwen 7B base', 'qwen2.5-7b-impulse-v3-cuda': 'Qwen 7B tuned' };

export function ResultsBars({ initial = 'impulse_units_per_trip' }: { initial?: typeof RESULT_METRICS[number] }) {
  const { data, error } = useDashboardData();
  const [metric, setMetric] = useState<string>(initial);
  if (error) return <div className="replay-empty" role="alert"><h3>Results unavailable</h3><p>{error}</p></div>;
  if (!data) return <div className="replay-empty" role="status"><h3>Loading results…</h3></div>;
  const view = data.views.find(v => v.id === data.default_view)!;
  const measure = data.measures.find(m => m.id === metric)!;
  const value = (modelId: string, layoutId: string) => view.models.find(m => m.id === modelId)?.cells[layoutId]?.metrics[metric] ?? null;
  const max = Math.max(1e-9, ...view.models.flatMap(m => data.layouts.map(l => value(m.id, l.id) ?? 0)));
  return <div className="pz-results">
    <div className="pz-segmented" role="group" aria-label="Measure">{RESULT_METRICS.map(id => <button key={id} aria-pressed={id === metric} onClick={() => setMetric(id)}>{data.measures.find(m => m.id === id)?.label ?? id}</button>)}</div>
    <div className="pz-bars" role="table" aria-label={measure.label}>
      {view.models.map(m => <div className="pz-bar-row" role="row" key={m.id}>
        <span role="rowheader">{SHORT[m.id] ?? m.label}</span>
        {data.layouts.map((l, i) => { const v = value(m.id, l.id); const free = metric.includes('cost') && m.provider === 'local_mps';
          return <div role="cell" key={l.id} className={`pz-bar is-${i ? 'b' : 'a'}`}>
            <i style={{ width: `${v === null ? 0 : Math.max(1.5, v / max * 100)}%` }}/>
            <b>{i ? 'B' : 'A'} · {free ? 'no API fee' : format(v, measure.unit)}</b></div>; })}
      </div>)}
    </div>
    <p className="pz-caption">{view.label}: one run per model and layout, ten shoppers. Qwen base is the earlier Nov 3 run. Source: evidence-dashboard.json.</p>
  </div>;
}

/* ── LoRA explainer ─────────────────────────────────────────────────────── */
// Qwen2.5 7B: 28 layers; hidden 3,584; K/V width 512; MLP 18,944. Per-layer adapter size is
// r × Σ(d + k) over the seven projections = r × 90,112. Precomputed teaching arithmetic, not evidence.
const RANKS = [[4, '10.1M'], [8, '20.2M'], [16, '40.4M'], [32, '80.7M'], [64, '161.5M']] as const;

export function LoraLab() {
  const [index, setIndex] = useState(2);
  const [rank, params] = RANKS[index];
  return <div className="pz-lora">
    <div className="pz-matrix">
      <div className="pz-w"><span>W</span><small>3,584 × 3,584<br/>frozen · 4-bit NF4</small></div>
      <span className="pz-plus">+</span>
      <div className="pz-ba">
        <div className="pz-b" style={{ width: `${18 + rank * 1.4}px` }}><span>B</span><small>3,584<br/>× {rank}</small></div>
        <span className="pz-times">×</span>
        <div className="pz-a" style={{ height: `${18 + rank * 1.4}px` }}><span>A</span><small>{rank} × 3,584</small></div>
      </div>
      <span className="pz-plus">=</span>
      <div className="pz-w is-out"><span>W + BA</span><small>same shape,<br/>only B and A train</small></div>
    </div>
    <label className="pz-slider">Rank r <b>{rank}</b>
      <input type="range" min={0} max={RANKS.length - 1} value={index} onChange={e => setIndex(Number(e.target.value))}/></label>
    <dl className="pz-facts">
      <div><dt>Trainable params</dt><dd>{params}<small>of 7.6B · 7 projections × 28 layers</small></dd></div>
      <div><dt>Used in Simply</dt><dd>r = 16<small>α 32 · 392 tensors · 161.5 MB adapter</small></dd></div>
      <div><dt>Base weights in memory</dt><dd>≈15 GB → ≈4–5 GB<small>bf16 → 4-bit NF4 (the “Q” in QLoRA)</small></dd></div>
    </dl>
  </div>;
}

/* ── Before / after bars (quoted numbers) ───────────────────────────────── */
export function BeforeAfter({ rows, max = 1 }: { rows: [label: string, before: number, after: number, note?: string][]; max?: number }) {
  const pct = (v: number) => `${(v * 100).toFixed(v * 100 % 1 ? 1 : 0)}%`;
  return <div className="pz-ba-chart">{rows.map(([label, before, after, note]) => <div key={label} className="pz-ba-row">
    <span>{label}{note && <small>{note}</small>}</span>
    <div className="pz-ba-track"><i className="is-before" style={{ width: `${before / max * 100}%` }}/><b>{pct(before)}</b></div>
    <div className="pz-ba-track"><i className="is-after" style={{ width: `${after / max * 100}%` }}/><b>{pct(after)}</b></div>
  </div>)}<p className="pz-legend"><em><span className="is-before"/>before (untuned)</em><em><span className="is-after"/>after (tuned)</em></p></div>;
}

/* ── Run checks from guardrails.py ──────────────────────────────────────── */
type CheckRow = { model_id: string; layout_id: string; shoppers_pass: number; shoppers_review: number; shoppers_fail: number; shoppers_total: number; verdict: string };
export function RunCheckBars() {
  const rows = checks.runs as CheckRow[];
  return <div className="pz-checks">{rows.map(r => <div className="pz-check-row" key={`${r.model_id}-${r.layout_id}`}>
    <span>{SHORT[r.model_id] ?? r.model_id} · {r.layout_id === 'costco_back_anchor' ? 'A' : 'B'}</span>
    <div className="pz-stack" aria-label={`${r.shoppers_pass} pass, ${r.shoppers_review} review, ${r.shoppers_fail} fail`}>
      {(['pass', 'review', 'fail'] as const).map(k => { const n = r[`shoppers_${k}`]; return n ? <i key={k} className={`is-${k}`} style={{ flexGrow: n }}>{n}</i> : null; })}
    </div>
    <b className={`pz-verdict is-${r.verdict}`}>{r.verdict}</b>
  </div>)}<p className="pz-legend"><em><span className="is-pass"/>pass</em><em><span className="is-review"/>review</em><em><span className="is-fail"/>fail</em><em>shoppers per run · run-checks.json</em></p></div>;
}
