/** Read-only projections of Python evidence. No shopping policy or accounting. */
export type CartItem = {product_id: string; name: string; quantity: number};
export type ShopperState = {x:number; y:number; phase:string; cart:CartItem[]; turns_used:number; turn_budget:number; basket_cents:number|null; known_basket_cents:number; unresolved_units:number};
export type ShopperMetric = {agent_id:string; stop_reason:string; list_completion:number; fulfilled_units:number; requested_units:number; overshoot_cents:number|null; loop_detections?:number; [key:string]:unknown};
export type Summary = {status:string; shopper_count:number; finished_count:number; mean_list_completion:number; sales_cents?:number; basket_value_cents?:number; unit_fulfillment?:number; failures:Record<string,number>; shoppers:ShopperMetric[]; traffic?:Record<string,number>; resources?:{known_estimated_cost_usd:number; unknown_usage_requests:number; usage:Record<string,number>}; [key:string]:unknown};
export type RunSource = {run_id:string; sha256:string; provider:string; model:string; status:string; recorded_at:string; prompt_variant:string; prompt_version:string; warnings:string[]};
export type CatalogEntry = RunSource & {layout_id:string; shopper_count:number; url:string; evidence_url:string; bundle_sha256:string;study?:{matrix_id:string;repetition:number}};
export type MatrixEntry={url:string;sha256:string;protocol_url:string;title?:string};
export type Catalog = {schema_version:number; runs:CatalogEntry[]; reports:{url:string; title:string; sha256?:string}[]; history?:{url:string;sha256:string};matrix?:MatrixEntry;matrices?:MatrixEntry[];dashboard?:{url:string;sha256:string}};
export type Product = {id:string; name:string; price:number; department:string; x?:number; y?:number};
export type ReplayEvent = {sequence:number; round:number; agent_id:string; before:ShopperState; after:ShopperState; action:{step:string; product_id:string; reason:string}|null; outcome:string; failure:string|null; totals:Omit<Summary,'shoppers'>; shopper_metrics:ShopperMetric};
export type ReplayData = {
  schema_version:number; source:RunSource;
  config?:{navigation_policy?:string};
  layout:{id:string; width:number; height:number; entrance:number[][]; checkout:number[][]; exit:number[]; shelves:{x:number;y:number;department:string;offsets:number[][];products:Product[]}[]};
  catalogue:Product[];
  shoppers:{id:string;name:string;style:string;budget_cents:number;sprite_index:number;persona:Record<string,unknown>;list:{product_id:string;product_name:string;quantity:number;priority:string}[]}[];
  initial:{sequence:number;states:Record<string,ShopperState>;summary:Summary};
  events:ReplayEvent[]; summary:Summary;
  final:{sequence:number;states:Record<string,ShopperState>;summary:Summary};
};

function requireValue(condition:unknown, message:string):asserts condition { if(!condition) throw new Error(message); }
function stable(value:unknown):string {
  if(Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if(value && typeof value==='object') return `{${Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>`${JSON.stringify(k)}:${stable(v)}`).join(',')}}`;
  return JSON.stringify(value);
}
function checkState(s:ShopperState, data:ReplayData) {
  requireValue(s && Number.isInteger(s.x) && Number.isInteger(s.y) && s.x>=0 && s.x<data.layout.width && s.y>=0 && s.y<data.layout.height,'Invalid recorded position');
  requireValue(['BrowsingState','CheckoutState','FinishedState'].includes(s.phase),'Invalid phase');
  requireValue(Number.isInteger(s.turns_used) && s.turns_used>=0 && Number.isInteger(s.turn_budget) && s.turns_used<=s.turn_budget,'Invalid turn counts');
  requireValue(Array.isArray(s.cart) && s.cart.every(i=>typeof i.product_id==='string' && Number.isInteger(i.quantity) && i.quantity>0),'Invalid recorded cart');
  requireValue(s.basket_cents===null || (Number.isInteger(s.basket_cents) && s.basket_cents>=0),'Invalid basket value');
}
export function validateReplay(data:ReplayData, expected?:Pick<CatalogEntry,'run_id'|'sha256'|'provider'|'model'|'status'>):ReplayData {
  requireValue(data && data.schema_version===1 && data.source && /^[a-f0-9]{64}$/.test(data.source.sha256),'Unsupported or invalid replay');
  if(expected) for(const field of ['run_id','sha256','provider','model','status'] as const) requireValue(data.source[field]===expected[field],`Catalogue mismatch: ${field}`);
  requireValue(data.layout && Number.isInteger(data.layout.width) && data.layout.width>0 && Number.isInteger(data.layout.height) && data.layout.height>0,'Invalid recorded layout');
  requireValue(Array.isArray(data.shoppers) && data.shoppers.length>0 && new Set(data.shoppers.map(s=>s.id)).size===data.shoppers.length,'Duplicate or missing shopper');
  requireValue(Array.isArray(data.events) && data.initial.sequence===0,'Missing initial frame');
  const states={...data.initial.states}; const ids=data.shoppers.map(s=>s.id);
  requireValue(stable(Object.keys(states).sort())===stable([...ids].sort()),'Initial shopper mismatch');
  Object.values(states).forEach(s=>checkState(s,data));
  let round=0; const seen=new Set<string>();
  for(const [index,e] of data.events.entries()) {
    requireValue(e.sequence===index+1 && ids.includes(e.agent_id),'Missing, duplicate, or out-of-order event');
    requireValue(Number.isInteger(e.round) && e.round>=1 && e.round>=round,'Invalid round order');
    if(e.round!==round) { round=e.round;seen.clear(); }
    requireValue(!seen.has(e.agent_id),'Duplicate shopper commit');seen.add(e.agent_id);
    requireValue(stable(e.before)===stable(states[e.agent_id]),'Recorded state chain mismatch');
    checkState(e.after,data);
    requireValue(e.after.turn_budget===e.before.turn_budget && e.after.turns_used===e.before.turns_used+1,'Invalid recorded turn transition');
    requireValue(['applied','invalid_decision','grid_rejected','provider_exception'].includes(e.outcome),'Invalid recorded outcome');
    if(e.outcome!=='applied') {
      requireValue(stable({...e.before,turns_used:e.after.turns_used})===stable(e.after),'Failed action changed state');
    }
    requireValue(e.shopper_metrics.agent_id===e.agent_id,'Metric shopper mismatch');
    states[e.agent_id]=e.after;
  }
  requireValue(data.final.sequence===data.events.length && stable(states)===stable(data.final.states),'Final state mismatch');
  requireValue(stable(data.summary)===stable(data.final.summary),'Final summary mismatch');
  requireValue(data.summary.status===data.source.status,'Status mismatch');
  requireValue(data.summary.shoppers.length===ids.length && new Set(data.summary.shoppers.map(s=>s.agent_id)).size===ids.length && data.summary.shoppers.every(s=>ids.includes(s.agent_id)),'Final metric identity mismatch');
  return data;
}
export async function sha256(text:string):Promise<string> {
  const digest=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
}
export async function decodeReplay(text:string, entry?:CatalogEntry):Promise<ReplayData> {
  if(entry) requireValue(await sha256(text)===entry.bundle_sha256,'Replay download integrity mismatch');
  const envelope=JSON.parse(text);
  requireValue(envelope.bundle_version===1 && typeof envelope.payload_json==='string','Unsupported bundle');
  requireValue(await sha256(envelope.payload_json)===envelope.payload_sha256,'Replay payload integrity mismatch');
  return validateReplay(JSON.parse(envelope.payload_json),entry);
}
type ShopperHistory = { events: ReplayEvent[]; initial: ShopperState; metric: ShopperMetric };
const historyIndexes = new WeakMap<ReplayData, Map<string, ShopperHistory>>();
function histories(data: ReplayData) {
  let index = historyIndexes.get(data);
  if (!index) {
    index = new Map(data.shoppers.map(shopper => [shopper.id, {
      events: [], initial: data.initial.states[shopper.id],
      metric: data.initial.summary.shoppers.find(metric => metric.agent_id === shopper.id)!,
    }]));
    for (const event of data.events) index.get(event.agent_id)!.events.push(event);
    historyIndexes.set(data, index);
  }
  return index;
}
function upperBound(events: ReplayEvent[], sequence: number) {
  let low = 0, high = events.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if (events[middle].sequence <= sequence) low = middle + 1;
    else high = middle;
  }
  return low;
}
/** Read an identified shopper's existing events without rescanning the whole run. */
export function shopperHistory(data: ReplayData, sequence: number, shopperId: string): readonly ReplayEvent[] {
  const history = histories(data).get(shopperId);
  requireValue(history, 'Unknown recorded shopper');
  return history.events.slice(0, upperBound(history.events, sequence));
}
export function frameAt(data: ReplayData, sequence: number) {
  requireValue(Number.isInteger(sequence) && sequence >= 0 && sequence <= data.events.length, 'Invalid replay cursor');
  if (sequence === data.events.length) return data.final;
  if (sequence === 0) return data.initial;
  const index = histories(data);
  const states: Record<string, ShopperState> = {};
  const metrics: ShopperMetric[] = [];
  for (const shopper of data.shoppers) {
    const history = index.get(shopper.id)!;
    const last = history.events[upperBound(history.events, sequence) - 1];
    states[shopper.id] = last?.after ?? history.initial;
    metrics.push(last?.shopper_metrics ?? history.metric);
  }
  return { sequence, states, summary: { ...data.events[sequence - 1].totals, shoppers: metrics } as Summary };
}
