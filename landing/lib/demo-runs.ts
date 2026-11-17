/**
 * Model × layout demo selection, read from the integrity-checked Evidence dashboard.
 * The run chosen for each cell is exactly the one Python's default Evidence view is
 * built from, so demo replays and published numbers always describe the same trips.
 * No selection by outcome, no invented cells: missing recordings stay missing.
 */
import {decodeDashboard, type Dashboard, type DashboardCell} from './dashboard';
import {loadCatalog} from './recordings';
import type {CatalogEntry} from './replay';

export type DemoCell = {modelId: string; modelLabel: string; layoutId: string; layoutLabel: string; layoutDescription: string;
  entry: CatalogEntry | null; cell: DashboardCell | null; partial: boolean};
export type DemoModel = {id: string; label: string; short: string; transport: string; cells: DemoCell[]};
export type DemoMatrix = {viewLabel: string; note: string; layouts: Dashboard['layouts']; models: DemoModel[]};

const shortNames: Record<string, [string, string]> = {
  'gpt-6-luna': ['GPT-6 Luna', 'OpenAI'],
  'gpt-6.1-terra': ['GPT-6.1 Terra', 'OpenAI'],
  'qwen2.5-7b-instruct': ['Qwen 7B · base', 'OpenRouter'],
  'qwen2.5-7b-pilot-mlx': ['Qwen 7B · fine-tuned', 'Local MLX 4-bit'],
  'qwen2.5-7b-pilot-mps': ['Qwen 7B · fine-tuned', 'Local MPS'],
};
export const modelShort = (id: string) => shortNames[id]?.[0] ?? id;

let request: Promise<DemoMatrix> | undefined;
export function loadDemoMatrix(): Promise<DemoMatrix> {
  request ??= (async () => {
    const catalog = await loadCatalog();
    if (!catalog.dashboard) throw new Error('Evidence dashboard unavailable');
    const response = await fetch(catalog.dashboard.url, {cache: 'no-store'});
    if (!response.ok) throw new Error('Evidence dashboard unavailable');
    const dashboard = await decodeDashboard(await response.text(), catalog.dashboard);
    const view = dashboard.views.find(v => v.id === dashboard.default_view) ?? dashboard.views[0];
    const models = view.models.filter(m => m.status === 'recorded').map(m => ({
      id: m.id, label: m.label, short: modelShort(m.id), transport: shortNames[m.id]?.[1] ?? '',
      cells: dashboard.layouts.map(layout => {
        const cell = m.cells[layout.id] ?? null;
        // One representative recording per cell: the first run Python selected for it.
        const runId = cell?.status === 'recorded' ? cell.run_ids[0] : undefined;
        const entry = catalog.runs.find(run => run.run_id === runId) ?? null;
        return {modelId: m.id, modelLabel: m.label, layoutId: layout.id, layoutLabel: layout.label, layoutDescription: layout.description,
          entry, cell, partial: !!entry && entry.status !== 'completed'};
      }),
    }));
    return {viewLabel: view.label, note: view.note, layouts: dashboard.layouts, models};
  })();
  request.catch(() => { request = undefined; });
  return request;
}
