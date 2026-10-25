"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  blockedCells,
  cartCount,
  listProgress,
  productIndex,
  runLayoutBenchmark,
  spawnAgents,
  stepAgent,
  type LayoutBenchmark,
  type LayoutData,
  type ShopperAgent,
  type StoreData,
} from "../lib/engine";
import StoreMap from "./StoreMap";
import ProjectQuiz from "./ProjectQuiz";

const COUNTS = [5, 10, 15];

export default function Workspace({ store }: { store: StoreData }) {
  const layouts = useMemo<Record<string, LayoutData>>(
    () => store.layouts ?? { default: store },
    [store],
  );
  const ids = useMemo(() => Object.keys(layouts), [layouts]);
  const [layoutId, setLayoutId] = useState(ids[0]);
  const layout = layouts[layoutId] as LayoutData;
  const [count, setCount] = useState(15);
  const [agents, setAgents] = useState<ShopperAgent[]>(() => spawnAgents(layout, 15));
  const [selectedId, setSelectedId] = useState(agents[0]?.customer.id ?? "");
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showRoutes, setShowRoutes] = useState(true);
  const [tab, setTab] = useState<"live" | "results" | "learn">("live");
  const blocked = useMemo(() => blockedCells(layout), [layout]);
  const products = useMemo(() => productIndex(layout), [layout]);
  const selected = agents.find((a) => a.customer.id === selectedId) ?? agents[0];
  const benchmark = useMemo(() => runLayoutBenchmark(layout, count), [layout, count]);
  const results = useMemo(
    () =>
      tab === "results"
        ? ids.map((id) => runLayoutBenchmark(layouts[id], count))
        : [],
    [count, ids, layouts, tab],
  );

  function reset(nextLayout = layout, nextCount = count) {
    const next = spawnAgents(nextLayout, nextCount);
    setAgents(next);
    setSelectedId(next[0]?.customer.id ?? "");
    setTick(0);
    setPlaying(false);
  }

  function chooseLayout(id: string) {
    setLayoutId(id);
    reset(layouts[id] as LayoutData);
  }

  const oneStep = useCallback(() => {
    setTick((currentTick) => {
      const nextTick = currentTick + 1;
      setAgents((previous) =>
        previous.map((agent) => stepAgent(layout, blocked, agent, nextTick)),
      );
      return nextTick;
    });
  }, [layout, blocked]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(oneStep, 240);
    return () => window.clearInterval(timer);
  }, [playing, oneStep]);

  const revenue = agents.reduce((sum, a) => sum + a.spend, 0);
  const impulse = agents.reduce((sum, a) => sum + a.impulseSpend, 0);
  const done = agents.filter((a) => a.phase === "FinishedState").length;
  const progress = agents.reduce(
    (total, agent) => {
      const current = listProgress(agent);
      return {
        completed: total.completed + current.completed,
        total: total.total + current.total,
      };
    },
    { completed: 0, total: 0 },
  );

  return (
    <main className="min-h-screen">
      <header className="border-b border-white/10 bg-[#10201c] text-white">
        <div className="mx-auto flex max-w-[1560px] items-center justify-between gap-4 px-5 py-3">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500 font-bold">S</span>
            <div>
              <h1 className="text-sm font-semibold">Simply Layout Lab</h1>
              <p className="text-xs text-emerald-100/70">Simulate customer journeys before moving a shelf</p>
            </div>
          </div>
          <div className="flex rounded-lg bg-white/10 p-1 text-sm">
            <button onClick={() => setTab("live")} className={`rounded-md px-3 py-1.5 ${tab === "live" ? "bg-white text-slate-950" : "text-white/70"}`}>Live simulation</button>
            <button onClick={() => setTab("results")} className={`rounded-md px-3 py-1.5 ${tab === "results" ? "bg-white text-slate-950" : "text-white/70"}`}>Experiment results</button>
            <button onClick={() => setTab("learn")} className={`rounded-md px-3 py-1.5 ${tab === "learn" ? "bg-white text-slate-950" : "text-white/70"}`}>Learn & interview</button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1560px] px-5 py-5">
        {tab === "learn" ? (
          <ProjectQuiz />
        ) : tab === "results" ? (
          <Results results={results} />
        ) : (
          <>
            <section className="grid gap-3 lg:grid-cols-2">
              {ids.map((id, index) => {
                const candidate = layouts[id] as LayoutData;
                const active = id === layoutId;
                return (
                  <button key={id} onClick={() => chooseLayout(id)} className={`rounded-2xl border p-4 text-left ${active ? "border-emerald-500 bg-emerald-50 shadow-sm" : "border-[var(--line)] bg-white hover:border-emerald-300"}`}>
                    <div className="text-xs font-bold uppercase tracking-wider text-emerald-700">Layout {String.fromCharCode(65 + index)}</div>
                    <div className="mt-1 font-semibold">{candidate.name?.replace(/^Layout [AB] — /, "")}</div>
                    <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">{candidate.subtitle}</p>
                  </button>
                );
              })}
            </section>

            <section className="mt-4 flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-[var(--line)] bg-white p-4 shadow-sm">
              <div className="flex flex-wrap gap-5">
                <Control label="Shoppers">
                  {COUNTS.map((n) => <Choice key={n} active={count === n} onClick={() => { setCount(n); reset(layout, n); }}>{n}</Choice>)}
                </Control>
                <Control label="Floor overlays">
                  <Choice active={showRoutes} onClick={() => setShowRoutes((v) => !v)}>Routes</Choice>
                  <Choice active={showHeatmap} onClick={() => setShowHeatmap((v) => !v)}>Traffic</Choice>
                </Control>
              </div>
              <div className="flex gap-2">
                <Action onClick={() => setPlaying((v) => !v)} primary>{playing ? "Pause" : "Run simulation"}</Action>
                <Action onClick={oneStep}>Step</Action>
                <Action onClick={() => reset()}>Reset</Action>
              </div>
            </section>

            <section className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
              <Kpi label="Simulation time" value={`${tick} ticks`} />
              <Kpi label="Checked out" value={`${done}/${agents.length}`} />
              <Kpi label="Revenue" value={`$${revenue.toFixed(0)}`} />
              <Kpi label="Impulse revenue" value={`$${impulse.toFixed(0)}`} green />
              <Kpi label="List completion" value={`${progress.completed}/${progress.total}`} />
            </section>

            <section className="mt-4 grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="rounded-2xl border border-[var(--line)] bg-white p-4 shadow-sm">
                <StoreMap layout={layout} agents={agents} selected={selected} showHeatmap={showHeatmap} showRoutes={showRoutes} heatmap={benchmark.heatmap} onSelectAgent={setSelectedId} />
                <div className="mt-4 border-t border-[var(--line)] pt-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Shoppers in store</p>
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {agents.map((agent) => <button key={agent.customer.id} onClick={() => setSelectedId(agent.customer.id)} className={`min-w-36 rounded-lg border px-3 py-2 text-left text-xs ${agent.customer.id === selected?.customer.id ? "border-emerald-500 bg-emerald-50" : "border-[var(--line)] bg-white"}`}><b>{agent.customer.emoji} {agent.customer.name.split(" ")[0]}</b><br/><span className="font-mono text-[var(--muted)]">${agent.spend.toFixed(0)} · {agent.cart.length} items</span></button>)}
                  </div>
                </div>
              </div>
              {selected && <Inspector agent={selected} products={products} />}
            </section>
          </>
        )}
      </div>
    </main>
  );
}

function Inspector({ agent, products }: { agent: ShopperAgent; products: ReturnType<typeof productIndex> }) {
  const target = agent.customer.list.find((item) => cartCount(agent, item.productId) < item.quantity);
  const { completed, total } = listProgress(agent);
  return <aside className="sticky top-4 rounded-2xl border border-[var(--line)] bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-2"><div><div className="text-xs font-bold uppercase tracking-wider text-emerald-700">Selected shopper</div><h2 className="mt-1 font-semibold">{agent.customer.emoji} {agent.customer.name}</h2><p className="text-xs text-[var(--muted)]">{agent.customer.occupation} · {agent.customer.style}</p></div><span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-medium text-emerald-900">{agent.phase.replace("State", "")}</span></div>
    <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-slate-50 p-3 text-center text-xs"><div><b>{completed}/{total}</b><br/><span className="text-slate-500">List</span></div><div><b>${agent.spend.toFixed(0)}</b><br/><span className="text-slate-500">Spend</span></div><div><b>{agent.steps}</b><br/><span className="text-slate-500">Steps</span></div></div>
    <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm">{target ? <><span className="text-xs font-bold uppercase text-amber-800">Next decision target</span><br/><b>{target.emoji} {target.name}</b><br/><span className="text-xs text-amber-800">{target.department} · shelf ({target.x},{target.y})</span></> : <b>List complete — heading to checkout</b>}</div>
    <h3 className="mt-4 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">Shopping list</h3>
    <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto">{agent.customer.list.map((item) => { const have = cartCount(agent, item.productId); return <li key={item.productId} className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs ${have >= item.quantity ? "bg-slate-50 text-slate-400 line-through" : "bg-white"}`}><span>{item.emoji}</span><span className="flex-1 truncate">{item.name}</span><span className="font-mono">{have}/{item.quantity}</span></li>; })}</ul>
    {agent.impulseCart.length > 0 && <div className="mt-4"><h3 className="text-xs font-bold uppercase tracking-wider text-rose-600">Impulse picks</h3><div className="mt-2 flex flex-wrap gap-1">{agent.impulseCart.map((id, i) => <span key={`${id}-${i}`} className="rounded-full bg-rose-50 px-2 py-1 text-xs text-rose-800">{products.get(id)?.emoji} {products.get(id)?.name}</span>)}</div></div>}
    <h3 className="mt-4 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">Latest decision</h3><div className="mt-2 rounded-xl bg-slate-950 p-3 font-mono text-[11px] text-emerald-200"><b>{agent.lastDecision.step}</b><br/>{agent.lastDecision.reason}</div>
  </aside>;
}

function Results({ results }: { results: LayoutBenchmark[] }) {
  if (results.length === 0) return null;
  const a = results[0];
  const b = results[1] ?? a;
  const rows = [["Revenue", `$${a.totalRevenue.toFixed(0)}`, `$${b.totalRevenue.toFixed(0)}`],["Impulse revenue", `$${a.impulseRevenue.toFixed(0)}`, `$${b.impulseRevenue.toFixed(0)}`],["Impulse items", a.impulseItems, b.impulseItems],["List completion", `${a.listCompletionPct}%`, `${b.listCompletionPct}%`],["Avg. checkout time", `${a.avgTicksToCheckout} ticks`, `${b.avgTicksToCheckout} ticks`],["Unique products", a.uniqueSkus, b.uniqueSkus]];
  return <section><div className="mb-5"><p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Experiment report</p><h2 className="mt-1 text-3xl font-semibold">What changes when the layout changes?</h2><p className="mt-2 max-w-3xl text-[var(--muted)]">The same {a.shopperCount} shopper profiles and shopping lists ran through both floorplans. The comparison isolates the placement effect.</p></div>
    <div className="grid gap-4 md:grid-cols-2">{[a,b].map((result, i) => <div key={result.layoutId} className="rounded-2xl border border-[var(--line)] bg-white p-5 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Layout {String.fromCharCode(65+i)}</p><h3 className="mt-1 font-semibold">{result.layoutName}</h3><p className="mt-2 text-sm text-[var(--muted)]">{result.subtitle}</p><div className="mt-5 grid grid-cols-3 gap-2 text-center"><Kpi label="Revenue" value={`$${result.totalRevenue.toFixed(0)}`}/><Kpi label="Impulse" value={`${result.impulseItems}`}/><Kpi label="Time" value={`${result.avgTicksToCheckout}`}/></div></div>)}</div>
    <div className="mt-5 rounded-2xl border border-[var(--line)] bg-white p-5 shadow-sm"><h3 className="font-semibold">Research answers</h3><div className="mt-4 grid gap-3 md:grid-cols-2"><Insight title="Do shoppers spend more?" text={`Layout ${a.totalRevenue >= b.totalRevenue ? "A" : "B"} produces $${Math.abs(a.totalRevenue-b.totalRevenue).toFixed(0)} more total revenue.`}/><Insight title="Does back-wall placement drive impulse?" text={`Layout A captures ${a.frontImpulseItems} front-impulse items versus ${b.frontImpulseItems} in Layout B.`}/><Insight title="Do lists get completed?" text={`A: ${a.listCompletionPct}% completion · B: ${b.listCompletionPct}% completion.`}/><Insight title="Which layout is faster?" text={`Averages: A ${a.avgTicksToCheckout} ticks · B ${b.avgTicksToCheckout} ticks.`}/></div></div>
    <div className="mt-5 overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-sm"><table className="w-full text-sm"><thead className="bg-slate-950 text-left text-white"><tr><th className="p-3">Metric</th><th className="p-3">Layout A</th><th className="p-3">Layout B</th></tr></thead><tbody>{rows.map(([name, av, bv]) => <tr key={String(name)} className="border-t border-[var(--line)]"><td className="p-3 font-medium">{name}</td><td className="p-3 font-mono text-emerald-700">{av}</td><td className="p-3 font-mono text-blue-700">{bv}</td></tr>)}</tbody></table></div>
  </section>;
}

function Insight({ title, text }: { title: string; text: string }) { return <div className="rounded-xl bg-slate-50 p-4"><p className="font-semibold">{title}</p><p className="mt-1 text-sm text-[var(--muted)]">{text}</p></div>; }
function Kpi({ label, value, green = false }: { label: string; value: string; green?: boolean }) { return <div className="rounded-xl border border-[var(--line)] bg-white p-3 shadow-sm"><p className="text-xs font-medium text-[var(--muted)]">{label}</p><p className={`mt-1 font-mono text-lg font-semibold ${green ? "text-emerald-700" : ""}`}>{value}</p></div>; }
function Control({ label, children }: { label: string; children: React.ReactNode }) { return <div><p className="mb-1.5 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">{label}</p><div className="flex rounded-lg bg-slate-100 p-1">{children}</div></div>; }
function Choice({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) { return <button onClick={onClick} className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-white font-semibold shadow-sm" : "text-[var(--muted)]"}`}>{children}</button>; }
function Action({ onClick, children, primary = false }: { onClick: () => void; children: React.ReactNode; primary?: boolean }) { return <button onClick={onClick} className={`rounded-lg px-3.5 py-2 text-sm font-semibold ${primary ? "bg-emerald-700 text-white hover:bg-emerald-800" : "border border-[var(--line)] bg-white hover:bg-slate-50"}`}>{children}</button>; }
