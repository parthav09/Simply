/**
 * Display-only impulse-buy lens over recorded Python events.
 * An impulse buy is an applied grab of a product that is not on the shopper's list,
 * the same definition Python uses for `off_list_units`. Totals shown as statistics come
 * from Python's exported shopper metrics; this module only filters and labels events.
 */
import type {Product, ReplayData, ReplayEvent, Summary} from './replay';

export type ImpulseBuy = {event: ReplayEvent; shopperId: string; shopperName: string; product: Product | undefined; productId: string; reason: string};

const listIndex = new WeakMap<ReplayData, Map<string, Set<string>>>();
function lists(data: ReplayData) {
  let index = listIndex.get(data);
  if (!index) {
    index = new Map(data.shoppers.map(s => [s.id, new Set(s.list.map(i => i.product_id))]));
    listIndex.set(data, index);
  }
  return index;
}

export const isPlanned = (data: ReplayData, shopperId: string, productId: string) => lists(data).get(shopperId)?.has(productId) ?? false;
export const productOf = (data: ReplayData, productId: string) => data.catalogue.find(p => p.id === productId);

/** Every applied off-list grab up to (and including) the cursor, oldest first. */
export function impulseBuys(data: ReplayData, cursor: number, shopperId?: string): ImpulseBuy[] {
  const out: ImpulseBuy[] = [];
  for (const event of data.events.slice(0, cursor)) {
    if (event.outcome !== 'applied' || event.action?.step !== 'grab' || !event.action.product_id) continue;
    if (shopperId && event.agent_id !== shopperId) continue;
    if (isPlanned(data, event.agent_id, event.action.product_id)) continue;
    out.push({event, shopperId: event.agent_id, shopperName: data.shoppers.find(s => s.id === event.agent_id)?.name ?? event.agent_id,
      product: productOf(data, event.action.product_id), productId: event.action.product_id, reason: event.action.reason});
  }
  return out;
}

export const isImpulseEvent = (data: ReplayData, event: ReplayEvent) =>
  event.outcome === 'applied' && event.action?.step === 'grab' && !!event.action.product_id && !isPlanned(data, event.agent_id, event.action.product_id);

/** Python's recorded off-list units for one shopper at this frame (null when unrecorded). */
export function offListUnits(summary: Summary, shopperId: string): number | null {
  const value = summary.shoppers.find(s => s.agent_id === shopperId)?.off_list_units;
  return typeof value === 'number' ? value : null;
}

/** Sum of Python's recorded off-list units across shoppers at this frame. */
export function totalOffListUnits(summary: Summary): number | null {
  let total = 0;
  for (const s of summary.shoppers) {
    if (typeof s.off_list_units !== 'number') return null;
    total += s.off_list_units;
  }
  return total;
}

export const money = (dollars: number | undefined) => dollars == null || !Number.isFinite(dollars) ? '—' : `$${dollars.toFixed(2)}`;
