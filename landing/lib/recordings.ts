/** Shared, bounded cache of verified recordings. No shopping decisions or mutable run state. */
import { decodeReplay, type Catalog, type CatalogEntry, type ReplayData } from './replay';
import impulseShowcase from '../data/impulse-showcase.json';

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

/** Fixed showcase: a completed main-study Luna recording that contains recorded off-list purchases. */
export const showcase = impulseShowcase;
export async function loadShowcaseRecording(): Promise<{run: ReplayData; entry: CatalogEntry}> {
  const catalog = await loadCatalog();
  const entry = catalog.runs.find(run => run.run_id === impulseShowcase.run_id && run.status === 'completed');
  if (!entry) throw new Error('The showcase recording is unavailable.');
  const run = await loadRecording(entry);
  if (run.source.warnings.length || !run.shoppers.some(s => s.id === impulseShowcase.shopper_id)) throw new Error('The showcase recording does not match its identity.');
  return {run, entry};
}
