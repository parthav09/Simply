'use client';

import { Kalam } from 'next/font/google';
import { useEffect, useState, type ReactNode } from 'react';
import ComparePlayer from '../ui/ComparePlayer';
import { useDashboardData } from '../ui/useDashboardData';
import { loadDemoMatrix, pick, type DemoMatrix } from '../lib/demo-runs';
import { formatHistoryMetric as format } from '../lib/evidence';
import checks from '../data/run-checks.json';
import curve from '../data/present-training-curve.json';
import decision from '../data/present-decision.json';
import persona from '../data/present-persona-response.json';

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
  ['Assist', 'core/navigation.py', 'nav_support may replace the proposal (grab a reachable list item, head to checkout, avoid busy cells). Both versions are recorded.'],
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

/** One compact table: a row per model, a column pair (A / B) per measure. Every value is read from
 *  the Python-written evidence dashboard and formatted by the shared formatter; nothing is computed here. */
export function ResultsTable() {
  const { data, error } = useDashboardData();
  if (error) return <div className="replay-empty" role="alert"><h3>Results unavailable</h3><p>{error}</p></div>;
  if (!data) return <div className="replay-empty" role="status"><h3>Loading results…</h3></div>;
  const view = data.views.find(v => v.id === data.default_view)!;
  const measures = RESULT_METRICS.map(id => data.measures.find(m => m.id === id)!);
  return <div className="pz-results">
    <table className="pz-table pz-results-table" aria-label="Results by model, layout and measure">
      <thead>
        <tr><th rowSpan={2}>Model</th>{measures.map(m => <th key={m.id} colSpan={data.layouts.length} className="pz-grp">{m.label}</th>)}</tr>
        <tr>{measures.map(m => data.layouts.map((l, i) => <th key={`${m.id}-${l.id}`} className={`pz-ab${i === 0 ? ' pz-grp-start' : ''}`}>{i ? 'B' : 'A'}</th>))}</tr>
      </thead>
      <tbody>
        {view.models.map(model => <tr key={model.id}>
          <th scope="row">{SHORT[model.id] ?? model.label}</th>
          {measures.map(m => data.layouts.map((l, i) => {
            const v = model.cells[l.id]?.metrics[m.id] ?? null;
            const free = m.id.includes('cost') && model.provider === 'local_mps';
            // Heat shade = this value relative to the largest in its column group (display geometry only; neutral, not a ranking).
            const top = Math.max(1e-9, ...view.models.flatMap(x => data.layouts.map(y => x.cells[y.id]?.metrics[m.id] ?? 0)));
            const heat = v === null || free ? 0 : Math.round(v / top * 100);
            const tone = m.id === 'impulse_units_per_trip' ? 'var(--color-impulse)' : 'var(--color-accent)';
            return <td key={`${m.id}-${l.id}`} className={i === 0 ? 'pz-grp-start' : undefined}
              style={{ background: `color-mix(in srgb, ${tone} ${Math.round(heat * 0.42)}%, transparent)` }}>{free ? 'no API fee' : format(v, m.unit)}</td>;
          }))}
        </tr>)}
      </tbody>
    </table>
    <p className="pz-caption">{view.label}: one run per model and layout, ten shoppers. Qwen base is the earlier Nov 3 run. A = costco_back_anchor, B = neighborhood_express. Shade = size within each measure, not good or bad. Source: evidence-dashboard.json.</p>
  </div>;
}

/* ── LoRA explainer ─────────────────────────────────────────────────────── */
// Qwen2.5 7B: 28 layers; hidden 3,584; K/V width 512; MLP 18,944. Per-layer adapter size is
// Params = r × Σ(d + k) over the seven projections (90,112) × 28 layers; adapter file is fp32 (4 bytes/param).
// Teaching arithmetic on the real architecture, not evidence. Only r = 16 was trained.
const RANKS = [4, 8, 16, 32, 64, 128] as const;
const PER_RANK = 90_112 * 28, BASE_PARAMS = 7.6e9, TRAINED_RANK = 16;
const millions = (n: number) => `${(n / 1e6).toFixed(1)}M`;

export function LoraLab() {
  const [index, setIndex] = useState(2);
  const rank = RANKS[index], params = rank * PER_RANK, share = params / BASE_PARAMS * 100, trained = rank === TRAINED_RANK;
  return <div className="pz-lora">
    <div className="pz-matrix">
      <div className="pz-w"><span>W</span><small>3,584 × 3,584<br/>frozen · 4-bit NF4</small></div>
      <span className="pz-plus">+</span>
      <div className="pz-ba">
        <div className="pz-b" style={{ width: `${Math.min(96, 18 + rank * 0.8)}px` }}><span>B</span><small>3,584<br/>× {rank}</small></div>
        <span className="pz-times">×</span>
        <div className="pz-a" style={{ height: `${Math.min(96, 18 + rank * 0.8)}px` }}><span>A</span><small>{rank} × 3,584</small></div>
      </div>
      <span className="pz-plus">=</span>
      <div className="pz-w is-out"><span>W + BA</span><small>same shape,<br/>only B and A train</small></div>
    </div>
    <label className="pz-slider">Rank r <b>{rank}</b>
      <input type="range" min={0} max={RANKS.length - 1} value={index} onChange={e => setIndex(Number(e.target.value))}/>
      <em className={trained ? 'is-trained' : ''}>{trained ? '← the one I trained' : 'arithmetic, not trained'}</em></label>
    <div className="pz-bars" role="img" aria-label={`At rank ${rank}, ${millions(params)} of 7.6 billion parameters train (${share.toFixed(2)} percent).`}>
      <div className="pz-bar-row"><span>Frozen base</span><div className="pz-bar-track"><i className="is-base" style={{ width: '100%' }}/></div><b>7.6B</b></div>
      <div className="pz-bar-row"><span>Trained adapter</span><div className="pz-bar-track"><i className="is-lora" style={{ width: `${Math.max(share, 0.4)}%` }}/></div><b>{millions(params)}</b></div>
    </div>
    <dl className="pz-facts">
      <div><dt>Share that trains</dt><dd>{share.toFixed(2)}%<small>of 7.6B · 7 projections × 28 layers</small></dd></div>
      <div><dt>Adapter file</dt><dd>{(params * 4 / 1e6).toFixed(0)} MB<small>fp32 · r = 16 is the 161.5 MB I shipped</small></dd></div>
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

/* ── Agent architecture: a hand-drawn (Excalidraw-style) system diagram ─── */
const sketchFont = Kalam({ subsets: ['latin'], weight: ['400', '700'], variable: '--font-sketch' });
type Ink = 'src' | 'build' | 'agent' | 'core' | 'out';
const INKS: Ink[] = ['src', 'build', 'agent', 'core', 'out'];

/** Draws a shape twice with two roughness filters, like Excalidraw's double pencil stroke. */
function Sk({ k, fill = 'hatch', children }: { k: Ink; fill?: 'hatch' | 'solid' | 'none'; children: ReactNode }) {
  return <g className={`sd-sk ink-${k} fill-${fill}`} style={{ ['--hatch' as string]: `url(#pz-h-${k})` }}>
    <g className="sd-a" filter="url(#pz-rough)">{children}</g>
    <g className="sd-b" filter="url(#pz-rough-2)" transform="translate(1.6 1.2)">{children}</g>
  </g>;
}
const cyl = (x: number, y: number, w: number, h: number, r = 12) =>
  `M${x},${y + r} A${w / 2},${r} 0 0 1 ${x + w},${y + r} V${y + h - r} A${w / 2},${r} 0 0 1 ${x},${y + h - r} Z M${x},${y + r} A${w / 2},${r} 0 0 0 ${x + w},${y + r}`;
const doc = (x: number, y: number, w: number, h: number) =>
  `M${x},${y} H${x + w - 18} L${x + w},${y + 18} V${y + h} H${x} Z M${x + w - 18},${y} V${y + 18} H${x + w}`;
const Ar = ({ d, core = false, dash = false }: { d: string; core?: boolean; dash?: boolean }) =>
  <path d={d} filter="url(#pz-rough)" className={`sd-arrow${core ? ' is-core' : ''}${dash ? ' is-dash' : ''}`}/>;
const Tx = ({ x, y, c = 's', a = 'middle', children }: { x: number; y: number; c?: string; a?: 'start' | 'middle' | 'end'; children: ReactNode }) =>
  <text x={x} y={y} className={`sd-${c}`} textAnchor={a}>{children}</text>;
const In = ({ n, children }: { n: number; children: ReactNode }) => <g className="sd-in" style={{ animationDelay: `${n * 0.12}s` }}>{children}</g>;

export function AgentFlow() {
  return <figure className={`pz-sysd ${sketchFont.variable}`}>
    <svg viewBox="0 0 1410 532" role="img" aria-label="Agent architecture. Four data files feed a persona builder and a store builder. Every turn, per shopper: Python builds an observation, the LLM agent (served by OpenRouter or local MPS) proposes one JSON action, and the Python core checks it, lets nav_support fix bad moves, applies it, and loops the new state back. Every decision is written to a JSONL run log that feeds metrics, guardrails and the replay.">
      <defs>
        <filter id="pz-rough" filterUnits="userSpaceOnUse" x="-50" y="-50" width="1520" height="640"><feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="4"/><feDisplacementMap in="SourceGraphic" scale="3.2"/></filter>
        <filter id="pz-rough-2" filterUnits="userSpaceOnUse" x="-50" y="-50" width="1520" height="640"><feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" seed="11"/><feDisplacementMap in="SourceGraphic" scale="2.6"/></filter>
        {INKS.map(k => <pattern key={k} id={`pz-h-${k}`} width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <rect width="9" height="9" className="sd-hb"/><line x1="0" y1="0" x2="0" y2="9" className={`sd-hl ink-${k}`}/>
        </pattern>)}
        <marker id="pz-ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" className="sd-ah"/></marker>
        <marker id="pz-ah-core" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" className="sd-ah is-core"/></marker>
      </defs>

      {/* Column headers */}
      <Tx x={20} y={26} c="h" a="start">Data sources (frozen)</Tx>
      <Tx x={320} y={26} c="h" a="start">Built once per run</Tx>
      <Tx x={1130} y={26} c="h" a="start">Outputs</Tx>

      {/* 1 · Data sources */}
      <In n={0}>
        {[['customer_profiles_50.csv', '50 personas × 41 fields', 50], ['shopping_lists_50.csv', '497 rows · priority, qty, max $', 170], ['products.csv', '303 items · price, diet, allergy', 290]].map(([t, s, y]) => <g key={t as string}>
          <Sk k="src"><path d={cyl(20, y as number, 230, 95)}/></Sk>
          <Tx x={135} y={(y as number) + 52} c="f">{t}</Tx><Tx x={135} y={(y as number) + 75}>{s}</Tx>
        </g>)}
        <Sk k="src"><path d={doc(20, 410, 230, 95)}/></Sk>
        <Tx x={135} y={450} c="f">two_layouts_15_v2.json</Tx><Tx x={135} y={474}>layouts A / B · cohort</Tx>
      </In>

      {/* 2 · Builders */}
      <In n={2}>
        <Ar d="M250,97 C285,97 290,120 318,125"/><Ar d="M250,217 C290,217 290,180 318,175"/>
        <Ar d="M250,337 C285,337 290,345 318,350"/><Ar d="M250,457 C290,457 290,420 318,415"/>
        <Sk k="build"><rect x={320} y={60} width={220} height={170} rx={10}/></Sk>
        <Sk k="build" fill="none"><circle cx={430} cy={88} r={12}/><path d="M408,126 C408,104 452,104 452,126 Z"/></Sk>
        <Tx x={430} y={152} c="t">Persona builder</Tx><Tx x={430} y={175}>profile + list → persona text</Tx>
        <Tx x={430} y={199} c="e ink-build">Isabella · 38 · impulsive 0.45</Tx><Tx x={430} y={219} c="e ink-build">$113 budget</Tx>
        <Sk k="build"><rect x={320} y={290} width={220} height={180} rx={10}/></Sk>
        <Sk k="build" fill="solid"><rect x={385} y={306} width={90} height={42}/><path d="M403,306 V348 M421,306 V348 M439,306 V348 M457,306 V348 M385,320 H475 M385,334 H475"/></Sk>
        <rect x={404} y={307} width={16} height={12} className="sd-cell"/><rect x={458} y={335} width={16} height={12} className="sd-cell"/>
        <Tx x={430} y={377} c="t">Store builder</Tx><Tx x={430} y={400}>22 × 14 grid · 303 products</Tx>
        <Tx x={430} y={424} c="e ink-build">A: staples at the back</Tx><Tx x={430} y={445} c="e ink-build">B: essentials at the front</Tx>
      </In>

      {/* Model providers */}
      <In n={4}>
        <Sk k="agent" fill="none"><path d="M835,72 a16,16 0 0 1 4,-30 a22,22 0 0 1 38,-14 a20,20 0 0 1 34,6 a16,16 0 0 1 12,38 Z"/></Sk>
        <Tx x={879} y={60} c="f">OpenRouter</Tx>
        <Sk k="agent" fill="none"><rect x={950} y={22} width={130} height={54} rx={8}/></Sk>
        <Tx x={1015} y={45} c="f">local MPS</Tx><Tx x={1015} y={66}>Qwen 7B + LoRA</Tx>
        <Ar d="M880,74 C890,110 925,125 935,153" dash/><Ar d="M1015,78 C1012,110 1000,130 995,153" dash/>
      </In>

      {/* 3 · The per-turn loop */}
      <In n={5}>
        <Sk k="core" fill="none"><rect x={595} y={110} width={475} height={410} rx={16} className="sd-frame"/></Sk>
        <Tx x={615} y={140} c="h ink-core" a="start">Every turn, per shopper</Tx><Tx x={1052} y={510} c="l" a="end">≤ 120 actions per shopper</Tx>
        <Ar d="M540,140 C585,140 600,200 638,200"/><Tx x={546} y={128} c="l" a="start">persona</Tx>
        <Ar d="M540,380 C585,380 600,350 638,350"/><Tx x={546} y={400} c="l" a="start">store</Tx>
      </In>
      <In n={6}>
        <Sk k="core" fill="solid"><rect x={640} y={160} width={165} height={95} rx={8}/></Sk>
        <Tx x={722} y={194} c="t">Observation</Tx><Tx x={722} y={217}>persona + state</Tx><Tx x={722} y={238}>+ legal steps · ≈8k tok</Tx>
        <Ar d="M805,207 L872,207"/><Tx x={838} y={197} c="l">prompt</Tx>
      </In>
      <In n={7}>
        <Sk k="agent"><polygon points="875,207 898,157 1022,157 1045,207 1022,257 898,257"/></Sk>
        <Tx x={960} y={202} c="t">LLM agent</Tx><Tx x={960} y={226}>proposes one action</Tx>
      </In>
      <In n={8}>
        <Ar d="M960,257 L960,307" core/><Tx x={950} y={290} c="l" a="end">{'{step, product_id, reason}'}</Tx>
        <Sk k="core"><rect x={640} y={310} width={410} height={180} rx={10}/></Sk>
        <Tx x={658} y={340} c="t" a="start">Python core</Tx><Tx x={782} y={340} c="s" a="start">· the only authority</Tx>
        <Sk k="core" fill="solid"><polygon points="670,410 715,372 760,410 715,448"/></Sk><Tx x={715} y={415} c="f">valid?</Tx>
        <Ar d="M760,410 L793,410" core/><Tx x={776} y={400} c="l">yes</Tx>
        <Sk k="core" fill="solid"><rect x={795} y={380} width={120} height={60} rx={6}/></Sk><Tx x={855} y={406} c="f">nav_support</Tx><Tx x={855} y={427}>fixes bad moves</Tx>
        <Ar d="M915,410 L943,410" core/>
        <Sk k="core" fill="solid"><rect x={945} y={380} width={90} height={60} rx={6}/></Sk><Tx x={990} y={406} c="f">apply</Tx><Tx x={990} y={427}>grid + cart</Tx>
        <Ar d="M715,448 L715,464" core/><Tx x={725} y={480} c="l" a="start">no → rejected, still recorded</Tx>
      </In>
      <In n={9}>
        <Ar d="M640,472 C600,472 600,235 638,235" core/>
        <text x={630} y={285} transform="rotate(-90 630 285)" className="sd-l ink-core" textAnchor="middle">new state</text>
      </In>

      {/* 4 · Outputs */}
      <In n={10}>
        <Ar d="M1050,340 C1090,340 1090,120 1128,120"/>
        <Sk k="out"><path d={cyl(1130, 50, 250, 130)}/></Sk>
        <Tx x={1255} y={98} c="t">Run log · JSONL</Tx><Tx x={1255} y={121}>prompt · reply · proposal ·</Tx><Tx x={1255} y={141}>adjustment · outcome</Tx>
        <Tx x={1255} y={164} c="e ink-out">SHA-256 per record</Tx>
      </In>
      <In n={11}>
        <Ar d="M1255,182 L1255,236"/>
        <Sk k="out"><rect x={1130} y={240} width={250} height={120} rx={10}/></Sk>
        <Sk k="out" fill="solid"><rect x={1330} y={268} width={9} height={18}/><rect x={1343} y={258} width={9} height={28}/><rect x={1356} y={250} width={9} height={36}/></Sk>
        <Tx x={1148} y={280} c="t" a="start">Metrics +</Tx><Tx x={1148} y={302} c="t" a="start">guardrails</Tx>
        <Tx x={1148} y={326} a="start">completion · fulfilment · impulse</Tx><Tx x={1148} y={346} a="start">cost · audit (read-only)</Tx>
      </In>
      <In n={12}>
        <Ar d="M1380,120 C1406,120 1406,462 1382,462"/>
        <Sk k="out"><rect x={1130} y={400} width={250} height={120} rx={8}/><path d="M1130,424 H1380"/></Sk>
        <Sk k="out" fill="none"><circle cx={1146} cy={412} r={4}/><circle cx={1159} cy={412} r={4}/><circle cx={1172} cy={412} r={4}/></Sk>
        <Tx x={1255} y={458} c="t">Replay + dashboard</Tx><Tx x={1255} y={482}>React draws recorded</Tx><Tx x={1255} y={502}>states only</Tx>
      </In>
    </svg>
  </figure>;
}

/* ── Tool-call mechanism: how one model reply becomes (or fails to become) an action ── */
export function ToolCallFlow() {
  return <figure className={`pz-sysd ${sketchFont.variable}`}>
    <svg viewBox="0 0 1410 520" role="img" aria-label="Tool-call mechanism. Python offers the legal steps in the prompt, the model replies with one JSON call (step, product_id, reason), Python parses and validates it, nav_support may adjust it, Python executes it on the grid, and the result is logged and fed back as the next observation. An invalid reply or a rejected action is still recorded.">
      <defs>
        <filter id="pz-rough" filterUnits="userSpaceOnUse" x="-50" y="-50" width="1520" height="640"><feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="4"/><feDisplacementMap in="SourceGraphic" scale="3.2"/></filter>
        <filter id="pz-rough-2" filterUnits="userSpaceOnUse" x="-50" y="-50" width="1520" height="640"><feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" seed="11"/><feDisplacementMap in="SourceGraphic" scale="2.6"/></filter>
        {INKS.map(k => <pattern key={k} id={`pz-h-${k}`} width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <rect width="9" height="9" className="sd-hb"/><line x1="0" y1="0" x2="0" y2="9" className={`sd-hl ink-${k}`}/>
        </pattern>)}
      </defs>

      {/* Column headers */}
      {[[125, '1 · Tools offered'], [340, '2 · Call'], [560, '3 · Reply'], [780, '4 · Validate'], [960, '5 · Assist'], [1135, '6 · Execute'], [1315, '7 · Record']].map(([x, t]) =>
        <Tx key={t as string} x={x as number} y={84} c="h">{t}</Tx>)}

      <In n={0}>
        <Sk k="core" fill="solid"><rect x={20} y={110} width={210} height={150} rx={8}/></Sk>
        <Tx x={125} y={138} c="t">Observation</Tx>
        <Tx x={125} y={162}>state + allowed_steps:</Tx>
        <Tx x={125} y={184} c="f">move_left/right/up/down</Tx>
        <Tx x={125} y={206} c="f">grab · remove · checkout</Tx>
        <Tx x={125} y={238} c="e ink-core">{'the "tools" are Python\'s'}</Tx>
      </In>
      <In n={1}>
        <Ar d="M230,185 L276,185" core/>
        <Sk k="agent"><polygon points="280,185 302,140 378,140 400,185 378,230 302,230"/></Sk>
        <Tx x={340} y={182} c="t">LLM</Tx><Tx x={340} y={205}>picks one</Tx>
      </In>
      <In n={2}>
        <Ar d="M400,185 L446,185"/>
        <Sk k="agent"><path d={doc(450, 110, 220, 150)}/></Sk>
        <Tx x={560} y={146} c="f">{'{'}</Tx>
        <Tx x={560} y={170} c="f">{'"step": "grab",'}</Tx>
        <Tx x={560} y={194} c="f">{'"product_id": "p_031",'}</Tx>
        <Tx x={560} y={218} c="f">{'"reason": "on my list"'}</Tx>
        <Tx x={560} y={242} c="f">{'}'}</Tx>
      </In>
      <In n={3}>
        <Ar d="M670,185 L706,185" core/>
        <Sk k="core" fill="solid"><polygon points="780,120 850,185 780,250 710,185"/></Sk>
        <Tx x={780} y={180} c="f">valid?</Tx><Tx x={780} y={202} c="l">JSON · keys</Tx>
        <Ar d="M850,185 L886,185" core/><Tx x={868} y={173} c="l">yes</Tx>
        <Ar d="M780,250 L780,316" core dash/>
        <Sk k="out" fill="solid"><rect x={680} y={320} width={200} height={70} rx={8}/></Sk>
        <Tx x={780} y={348} c="f">invalid_decision</Tx><Tx x={780} y={372}>wrong step · item out of reach</Tx>
      </In>
      <In n={4}>
        <Sk k="build"><rect x={890} y={150} width={140} height={70} rx={8}/></Sk>
        <Tx x={960} y={180} c="f">nav_support</Tx><Tx x={960} y={202}>may swap action</Tx>
        <Tx x={960} y={248} c="e ink-build">original + adjusted</Tx><Tx x={960} y={268} c="e ink-build">both recorded</Tx>
        <Ar d="M1030,185 L1066,185" core/>
      </In>
      <In n={5}>
        <Sk k="core" fill="solid"><rect x={1070} y={150} width={130} height={70} rx={8}/></Sk>
        <Tx x={1135} y={180} c="f">perform()</Tx><Tx x={1135} y={202}>grid + cart</Tx>
        <Ar d="M1135,220 L1135,316" core dash/>
        <Sk k="out" fill="solid"><rect x={1040} y={320} width={190} height={70} rx={8}/></Sk>
        <Tx x={1135} y={348} c="f">grid_rejected</Tx><Tx x={1135} y={372}>duplicate SKU · blocked</Tx>
        <Ar d="M1200,185 L1246,185" core/>
      </In>
      <In n={6}>
        <Sk k="out"><path d={cyl(1250, 130, 130, 110)}/></Sk>
        <Tx x={1315} y={186} c="t">Run log</Tx><Tx x={1315} y={210}>every outcome</Tx>
      </In>
      <In n={7}>
        <Ar d="M1315,242 C1315,540 125,540 125,264" core/>
        <Tx x={720} y={490} c="l">outcome → next observation (≤ 120 turns per shopper)</Tx>
        <Tx x={957} y={306} c="e ink-out">a failed call is still logged</Tx>
      </In>
    </svg>
  </figure>;
}


/* ── Field of view: what the prompt lets the agent see. Radius comes from SHELF_SIGHT_RADIUS (core/perception.py). ── */
const FOV_RADIUS = 6;
export function FieldOfView() {
  const size = FOV_RADIUS * 2 + 1, cell = 15;
  // Same diamond (steps are Manhattan distance), turned 45° so it sits as a square.
  const mid = size * cell / 2, half = (FOV_RADIUS + 0.5) * cell / Math.SQRT2 + 2;
  const upright = cell / Math.SQRT2 - 1.5; // fits between neighbours once the layout is turned
  const cells: ReactNode[] = [];
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const d = Math.abs(x - FOV_RADIUS) + Math.abs(y - FOV_RADIUS);
    if (d > FOV_RADIUS) continue;
    const cls = d === 0 ? 'is-self' : d === 1 ? 'is-grab' : 'is-see';
    const cx = x * cell + cell / 2, cy = y * cell + cell / 2;
    // Each cell is turned back 45° about its own centre, so it stays upright inside the turned layout.
    cells.push(<rect key={`${x}-${y}`} x={cx - upright / 2} y={cy - upright / 2} width={upright} height={upright} rx={1.5} transform={`rotate(-45 ${cx} ${cy})`} className={`fov-${cls}`}/>);
  }
  return <figure className="pz-fov">
    <svg viewBox={`${mid - half} ${mid - half} ${half * 2} ${half * 2}`} role="img" aria-label={`Field of view: the agent sees every shelf within ${FOV_RADIUS} steps in all four directions, with no facing. It can grab only from a shelf one step away.`}><g transform={`rotate(45 ${mid} ${mid})`}>{cells}</g></svg>
    <figcaption>
      <span><i className="fov-sw is-see"/>Sees shelves within <b>{FOV_RADIUS} steps</b>, every direction, no facing</span>
      <span><i className="fov-sw is-grab"/>Grabs only from a shelf <b>1 step</b> away</span>
    </figcaption>
  </figure>;
}

/* ── Screenshot of the real app, in a browser frame ─────────────────────── */
export function Shot({ src, alt, caption, url = 'localhost:3000/replays' }: { src: string; alt: string; caption?: string; url?: string }) {
  return <figure className="pz-shot">
    <div className="pz-shot-bar" aria-hidden="true"><i/><i/><i/><span>{url}</span></div>
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={src} alt={alt} loading="eager"/>
    {caption && <figcaption>{caption}</figcaption>}
  </figure>;
}

/* ── Training loss, from the Colab training log ─────────────────────────── */
export function LossCurve() {
  const W = 460, H = 170, P = { l: 34, r: 10, t: 10, b: 24 };
  const maxStep = 374, maxLoss = 0.65;
  const x = (s: number) => P.l + (s / maxStep) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - v / maxLoss) * (H - P.t - P.b);
  const line = (pts: number[][]) => pts.map(([s, v], i) => `${i ? 'L' : 'M'}${x(s).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  return <figure className="pz-loss">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Training loss falls from 0.62 to about 0.03; validation loss settles near 0.07.">
      {[0, 0.2, 0.4, 0.6].map(v => <g key={v}><line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} className="grid"/><text x={P.l - 6} y={y(v) + 4} textAnchor="end">{v.toFixed(1)}</text></g>)}
      <line x1={x(187)} x2={x(187)} y1={P.t} y2={H - P.b} className="epoch"/><text x={x(187) + 4} y={P.t + 10}>epoch 2</text>
      <path d={line(curve.train)} className="train"/>
      <path d={line(curve.eval)} className="eval"/>
      {curve.eval.map(([s, v]) => <circle key={s} cx={x(s)} cy={y(v)} r={3} className="eval-dot"/>)}
      <text x={W - P.r} y={H - 6} textAnchor="end">step {maxStep}</text>
    </svg>
    <figcaption><span className="k-train">train loss</span> 0.62 → 0.03 · <span className="k-eval">validation loss</span> 0.13 → 0.07</figcaption>
  </figure>;
}

/* ── One real decision record, condensed ────────────────────────────────── */
export function RecordSnapshot() {
  const r = decision.record;
  const row = (k: string, v: ReactNode, cls = '') => <div className={`pz-rec-row ${cls}`}><dt>{k}</dt><dd>{v}</dd></div>;
  return <figure className="pz-rec">
    <div className="pz-shot-bar" aria-hidden="true"><i/><i/><i/><span>run_terra_A.jsonl · decision {r.sequence}</span></div>
    <dl>
      {row('before', <>pos ({r.before.x},{r.before.y}) · cart: {r.before.cart.join(', ')}</>)}
      {row('raw_response', <>{`{"step":"${r.raw_response.step}", "reason":"${r.raw_response.reason}"}`}</>, 'is-model')}
      {row('nav_support', <>{r.navigation.adjustment}</>, 'is-assist')}
      {row('action', <>{r.action.step} → {r.outcome}</>, 'is-core')}
      {row('usage', <>{r.usage.prompt_tokens.toLocaleString()} in · {r.usage.completion_tokens} out · ${r.usage.cost_usd.toFixed(4)} · {r.api_latency_ms} ms</>)}
      {row('serving', <>{r.serving.model} · {r.serving.provider} · seed {String(r.serving.request_seed)}</>)}
    </dl>
  </figure>;
}


/* ── Persona dial: the impulse setting vs what each shopper actually bought ─ */
export function PersonaDial() {
  const [mi, setMi] = useState(1);
  const [layout, setLayout] = useState<'A' | 'B'>('A');
  const [cut, setCut] = useState(0);
  const [pick, setPick] = useState<number | null>(null);
  const [probe, setProbe] = useState<'before' | 'after'>('before');
  const model = persona.models[mi];
  const pts = model.layouts[layout];
  const W = 520, H = 300, P = { l: 44, r: 16, t: 14, b: 38 };
  const maxN = 13, maxP = 0.7;
  const x = (v: number) => P.l + (v / maxP) * (W - P.l - P.r);
  const y = (n: number) => P.t + (1 - n / maxN) * (H - P.t - P.b);
  const shown = pick !== null ? pts[pick] : null;
  const pr = persona.probe[probe];
  return <div className="pz-dial">
    <div className="pz-dial-main">
      <div className="pz-dial-ctl" role="group" aria-label="Choose model and layout">
        {persona.models.map((m, i) => <button key={m.id} aria-pressed={i === mi} onClick={() => { setMi(i); setPick(null); }}>{m.label}</button>)}
        <span className="pz-dial-sep"/>
        {(['A', 'B'] as const).map(l => <button key={l} aria-pressed={l === layout} onClick={() => { setLayout(l); setPick(null); }}>Layout {l}</button>)}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Each dot is one shopper: the impulse setting in the profile against impulse buys in the trip, for ${model.label}, Layout ${layout}.`}>
        {[0, 4, 8, 12].map(n => <g key={n}><line x1={P.l} x2={W - P.r} y1={y(n)} y2={y(n)} className="grid"/><text x={P.l - 8} y={y(n) + 4} textAnchor="end">{n}</text></g>)}
        {[0, 0.2, 0.4, 0.6].map(v => <text key={v} x={x(v)} y={H - 20} textAnchor="middle">{v.toFixed(1)}</text>)}
        <line x1={x(cut)} x2={x(cut)} y1={P.t} y2={H - P.b} className="cut"/>
        <text x={W / 2} y={H - 3} textAnchor="middle" className="axis">impulse setting in the profile</text>
        <text x={12} y={H / 2} textAnchor="middle" transform={`rotate(-90 12 ${H / 2})`} className="axis">impulse buys in the trip</text>
        {pts.map((d, i) => <circle key={d.id} cx={x(d.p)} cy={y(d.n)} r={i === pick ? 8 : 6} tabIndex={0}
          className={`${d.p >= cut ? 'on' : 'off'}${i === pick ? ' pick' : ''}`}
          onMouseEnter={() => setPick(i)} onFocus={() => setPick(i)} onClick={() => setPick(i)}><title>{d.name}</title></circle>)}
        {pts.filter(d => d.id === 'C0007').map(d => <text key="isa" x={x(d.p)} y={y(d.n) - 12} textAnchor="middle" className="tag">{d.name}</text>)}
      </svg>
      <label className="pz-slider">Show shoppers with setting ≥ <b>{cut.toFixed(2)}</b>
        <input type="range" min={0} max={0.7} step={0.01} value={cut} onChange={e => setCut(Number(e.target.value))}/></label>
      <p className="pz-dial-read" aria-live="polite">{shown ? <><b>{shown.name}</b> · setting {shown.p.toFixed(2)} → <b>{shown.n}</b> impulse {shown.n === 1 ? 'buy' : 'buys'}</> : 'Hover a dot: one dot is one shopper in one recorded trip.'}</p>
    </div>
    <div className="pz-dial-probe">
      <p className="pz-eyebrow">Turn one dial · {persona.probe.shopper}</p>
      <div className="pz-dial-ctl" role="group" aria-label="Impulse setting">
        {(['before', 'after'] as const).map(k => <button key={k} aria-pressed={k === probe} onClick={() => setProbe(k)}>impulse {persona.probe[k].p.toFixed(2)}</button>)}
      </div>
      <div className="pz-dial-bar" aria-hidden="true"><i style={{ height: `${pr.units / 12 * 100}%` }} className={pr.units ? 'is-hi' : 'is-zero'}/></div>
      <p className="pz-dial-num"><b>{pr.units}</b> impulse items</p>
      <p className="pz-caption">{persona.probe.model}. {pr.note}.</p>
    </div>
  </div>;
}


/* ── Offline vs online on one chart: untuned (grey) to tuned (green) ───────── */
type OOGroup = { title: string; sub: string; rows: [label: string, before: number, after: number][] };
export function OfflineOnline({ groups }: { groups: OOGroup[] }) {
  const W = 560, L = 150, R = 36, rowH = 34, headH = 44;
  const x = (v: number) => L + v * (W - L - R);
  let y = 8;
  const items: ReactNode[] = [];
  groups.forEach((g, gi) => {
    items.push(<g key={`h${gi}`}><text x={0} y={y + 16} className="oo-head">{g.title}</text><text x={0} y={y + 33} className="oo-sub">{g.sub}</text></g>);
    y += headH;
    g.rows.forEach(([label, b, a]) => {
      const cy = y + rowH / 2;
      items.push(<g key={`${gi}${label}`}>
        <text x={0} y={cy + 4} className="oo-label">{label}</text>
        <line x1={x(0)} x2={x(1)} y1={cy} y2={cy} className="oo-track"/>
        <line x1={x(b)} x2={x(a)} y1={cy} y2={cy} className="oo-link"/>
        <circle cx={x(b)} cy={cy} r={7} className="oo-before"/>
        <circle cx={x(a)} cy={cy} r={8} className="oo-after"/>
        <text x={x(b) + 4} y={cy - 12} textAnchor="end" className="oo-val">{Math.round(b * 1000) / 10}%</text>
        <text x={x(a) - 4} y={cy - 12} textAnchor="start" className="oo-val is-after">{Math.round(a * 1000) / 10}%</text>
      </g>);
      y += rowH;
    });
    y += 14;
  });
  return <figure className="pz-oo">
    <svg viewBox={`0 0 ${W} ${y}`} role="img" aria-label="For each measure, a grey dot for the untuned model and a green dot for the tuned model. Offline measures rise a lot; online full-trip measures rise modestly.">
      {[0, 0.5, 1].map(v => <text key={v} x={x(v)} y={y - 2} textAnchor="middle" className="oo-axis">{v * 100}%</text>)}
      {items}
    </svg>
    <figcaption><i className="oo-key is-before"/> untuned <i className="oo-key is-after"/> tuned</figcaption>
  </figure>;
}
