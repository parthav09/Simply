/**
 * Model × layout demo selection. The run ids are a fixed, documented choice
 * (data/replay-selection.json, checked by a Python test); statistics come from the
 * integrity-checked Evidence dashboard. Nothing is simulated or chosen by outcome here.
 * A run missing from the published catalogue is dropped and shown as missing.
 */
import selection from '../data/replay-selection.json';
import {decodeDashboard, type DashboardRun} from './dashboard';
import {loadCatalog} from './recordings';
import type {CatalogEntry} from './replay';

export type DemoRun = {entry: CatalogEntry; partial: boolean; trips: number; finished: number; requested: number; purchased: number; impulse: number | null};
export type DemoCell = {modelId: string; modelLabel: string; layoutId: string; layoutLabel: string; layoutDescription: string; runs: DemoRun[]};
/** One recording chosen from a cell, as consumed by the players. */
export type DemoPick = Omit<DemoCell, 'runs'> & {entry: CatalogEntry | null; partial: boolean};
export type DemoModel = {id: string; label: string; short: string; transport: string; cells: DemoCell[]};
export type DemoMatrix = {rule: string; layouts: {id: string; label: string; description: string}[]; models: DemoModel[]};

const names: Record<string, [string, string]> = {
  'gpt-6-luna': ['GPT-6 Luna', 'OpenAI'],
  'gpt-6.1-terra': ['GPT-6.1 Terra', 'OpenAI'],
  'qwen2.5-7b-instruct': ['Qwen 7B · base', 'OpenRouter'],
  'qwen2.5-7b-pilot-mlx': ['Qwen 7B · fine-tuned', 'Local MLX 4-bit'],
};
export const modelShort = (id: string) => names[id]?.[0] ?? id;

export const pick = (cell: DemoCell, variant: number): DemoPick => {
  const run = cell.runs[Math.min(variant, cell.runs.length - 1)];
  const {runs: _runs, ...rest} = cell; void _runs;
  return {...rest, entry: run?.entry ?? null, partial: run?.partial ?? false};
};

function stats(entry: CatalogEntry, run: DashboardRun | undefined): DemoRun {
  const trips = run?.points.length ?? entry.shopper_count;
  const impulse = run ? run.points.reduce<number | null>((sum, p) => sum === null || p.values.impulse == null ? null : sum + p.values.impulse, 0) : null;
  return {entry, partial: entry.status !== 'completed', trips,
    finished: run?.points.filter(p => p.finished).length ?? 0,
    requested: run?.points.reduce((s, p) => s + p.requested, 0) ?? 0,
    purchased: run?.points.reduce((s, p) => s + p.purchased, 0) ?? 0, impulse};
}

let request: Promise<DemoMatrix> | undefined;
export function loadDemoMatrix(): Promise<DemoMatrix> {
  request ??= (async () => {
    const catalog = await loadCatalog();
    if (!catalog.dashboard) throw new Error('Evidence dashboard unavailable');
    const response = await fetch(catalog.dashboard.url, {cache: 'no-store'});
    if (!response.ok) throw new Error('Evidence dashboard unavailable');
    const dashboard = await decodeDashboard(await response.text(), catalog.dashboard);
    const models = selection.models.map(m => ({
      id: m.model, label: names[m.model]?.[0] ?? m.model, short: modelShort(m.model), transport: names[m.model]?.[1] ?? '',
      cells: dashboard.layouts.map(layout => {
        const ids = (m.cells as Record<string, string[]>)[layout.id] ?? [];
        const runs = ids.flatMap(id => {
          const entry = catalog.runs.find(r => r.run_id === id && r.model === m.model && r.layout_id === layout.id);
          return entry ? [stats(entry, dashboard.runs.find(r => r.run_id === id))] : [];
        });
        return {modelId: m.model, modelLabel: names[m.model]?.[0] ?? m.model, layoutId: layout.id, layoutLabel: layout.label, layoutDescription: layout.description, runs};
      }),
    }));
    return {rule: selection.rule, layouts: dashboard.layouts, models};
  })();
  request.catch(() => { request = undefined; });
  return request;
}
