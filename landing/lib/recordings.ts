/** Shared, bounded cache of verified recordings. No shopping decisions or mutable run state. */
import { decodeReplay, type Catalog, type CatalogEntry, type ReplayData } from './replay';
import demoRecordings from '../data/demo-recordings.json';

let catalogRequest: { created: number; promise: Promise<Catalog> } | undefined;
const recordings = new Map<string, Promise<ReplayData>>();
const catalogLifetime = 30_000;
const recordingLimit = 3;

export function loadCatalog(refresh = false): Promise<Catalog> {
  if (!refresh && catalogRequest && Date.now() - catalogRequest.created < catalogLifetime) return catalogRequest.promise;
  const promise = fetch('/replays/index.json', { cache: 'no-store' }).then(async response => {
    if (!response.ok) throw new Error('Recording catalogue unavailable');
    const catalog: Catalog = await response.json();
    if (catalog.schema_version !== 1 || !Array.isArray(catalog.runs)) throw new Error('Unsupported recording catalogue');
    return catalog;
  });
  catalogRequest = { created: Date.now(), promise };
  promise.catch(() => { if (catalogRequest?.promise === promise) catalogRequest = undefined; });
  return promise;
}

/** Newly published evidence must be visible immediately after a live export. */
export function invalidateCatalog() { catalogRequest = undefined; }

export function preferredRecording(catalog: Catalog): CatalogEntry | undefined {
  const newest = [...catalog.runs].sort((a,b)=>b.recorded_at.localeCompare(a.recorded_at));
  const real=(run:CatalogEntry)=>['openrouter','openai','gemini'].includes(run.provider);
  return newest.find(run => real(run) && run.status === 'completed')
    ?? newest.find(real) ?? newest[0];
}

/** Landing previews only show completed model recordings of the requested layout. */
export function completedLayoutRecording(catalog: Catalog, layoutId: string): CatalogEntry | undefined {
  return [...catalog.runs]
    .filter(run => run.layout_id === layoutId && run.status === 'completed'
      && ['openrouter', 'openai', 'gemini'].includes(run.provider))
    .sort((a, b) => b.recorded_at.localeCompare(a.recorded_at))[0];
}

/** Fixed, audited demo pair: main-study Terra repetition 1, with the same ten profiles. */
export async function loadDemoRecording(layoutId: string): Promise<ReplayData> {
  const runId = demoRecordings[layoutId as keyof typeof demoRecordings];
  const catalog = await loadCatalog();
  const entry = catalog.runs.find(run => run.run_id === runId && run.layout_id === layoutId
    && run.provider === 'openai' && run.model === 'gpt-6.1-terra' && run.status === 'completed');
  if (!entry) throw new Error('The verified demo recording is unavailable.');
  const run = await loadRecording(entry);
  if (run.source.warnings.length || run.shoppers.length !== 10 || run.summary.finished_count !== 10
    || run.summary.mean_list_completion !== 1 || Object.values(run.summary.failures).some(count => count !== 0)
    || run.shoppers.some(shopper => run.final.states[shopper.id].phase !== 'FinishedState')) {
    throw new Error('The recording does not meet the completed demo requirements.');
  }
  return run;
}

export function loadRecording(entry: CatalogEntry): Promise<ReplayData> {
  const key = `${entry.url}:${entry.bundle_sha256}:${entry.run_id}:${entry.sha256}:${entry.provider}:${entry.model}:${entry.status}`;
  const cached = recordings.get(key);
  if (cached) { recordings.delete(key); recordings.set(key, cached); return cached; }
  const promise = fetch(entry.url).then(async response => {
    if (!response.ok) throw new Error('Saved recording unavailable');
    return decodeReplay(await response.text(), entry);
  });
  recordings.set(key, promise);
  while (recordings.size > recordingLimit) recordings.delete(recordings.keys().next().value!);
  promise.catch(() => { if (recordings.get(key) === promise) recordings.delete(key); });
  return promise;
}
