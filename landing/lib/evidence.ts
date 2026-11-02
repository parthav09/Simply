/** Read-only history transport and validation. Python owns metrics and differences. */
import { sha256 } from './replay';
import { loadCatalog } from './recordings';

export type RunRow = {
  run_id:string; recorded_at:string; provider:string; model:string; model_versions:string[];
  kind:'model'|'fixture'; layout_id:string; shopper_count:number; status:string;
  warnings:string[]; navigation_policy:string; action_limit:number|null; finished_count:number;
  shopping_rules?:string;
  metrics:Record<string,number|null>; cost_complete:boolean; source_sha256:string; source_file:string;
  published?:{url:string;evidence_url:string}|null;
};
export type RunComparison = {run_id:string;baseline_id:string;matched_controls:boolean;reasons:string[];
  differences:Record<string,{absolute:number|null;relative_percent:number|null}>};
export type History = {history_version:number;generated_at:string;scope:string;runs:RunRow[];
  counts:{runs:number;model_runs:number;fixtures:number;completed:number};
  metric_definitions:Record<string,{label:string;unit:string}>;
  issues:{file:string;reason:string}[];comparisons:Record<string,RunComparison[]>};

function requireValue(value:unknown,message:string):asserts value {if(!value)throw new Error(message);}
const numberOrNull=(value:unknown)=>value===null||(typeof value==='number'&&Number.isFinite(value));
export async function decodeHistory(text:string,expectedHash?:string):Promise<History>{
  if(expectedHash)requireValue(await sha256(text)===expectedHash,'Run history download integrity mismatch');
  const value=JSON.parse(text) as History;
  requireValue(value.history_version===1&&Array.isArray(value.runs)&&Array.isArray(value.issues),'Unsupported run history');
  requireValue(typeof value.generated_at==='string'&&typeof value.scope==='string','Missing history scope');
  const ids=new Set(value.runs.map(row=>row.run_id));
  requireValue(ids.size===value.runs.length,'Duplicate history run ID');
  requireValue(value.counts?.runs===value.runs.length&&Object.values(value.counts).every(n=>Number.isInteger(n)&&n>=0),'Invalid history counts');
  requireValue(value.metric_definitions&&Object.values(value.metric_definitions).every(d=>typeof d.label==='string'&&typeof d.unit==='string'),'Missing metric definitions');
  const keys=Object.keys(value.metric_definitions);
  for(const row of value.runs){
    requireValue(typeof row.run_id==='string'&&row.run_id.length>0&&typeof row.model==='string'&&typeof row.provider==='string'&&typeof row.layout_id==='string'&&typeof row.recorded_at==='string','Invalid run identity');
    requireValue(['model','fixture'].includes(row.kind)&&typeof row.status==='string'&&typeof row.navigation_policy==='string'&&Array.isArray(row.warnings),'Invalid run scope');
    requireValue(Number.isInteger(row.shopper_count)&&row.shopper_count>0&&Number.isInteger(row.finished_count)&&row.finished_count>=0&&row.finished_count<=row.shopper_count,'Invalid shopper counts');
    requireValue(row.metrics&&keys.every(key=>numberOrNull(row.metrics[key])),'Invalid Python metrics');
    requireValue(/^[a-f0-9]{64}$/.test(row.source_sha256),'Invalid source fingerprint');
    requireValue(!row.published||(row.published.url.startsWith('/replays/')&&row.published.evidence_url.startsWith('/replays/')),'Invalid recording links');
    const comparisons=value.comparisons?.[row.run_id];
    requireValue(Array.isArray(comparisons)&&comparisons.length===value.runs.length&&new Set(comparisons.map(c=>c.run_id)).size===value.runs.length,'Missing run comparisons');
    for(const comparison of comparisons){
      requireValue(ids.has(comparison.run_id)&&comparison.baseline_id===row.run_id&&typeof comparison.matched_controls==='boolean'&&Array.isArray(comparison.reasons),'Invalid comparison identity');
      requireValue(keys.every(key=>comparison.differences?.[key]&&numberOrNull(comparison.differences[key].absolute)&&numberOrNull(comparison.differences[key].relative_percent)),'Invalid Python comparison');
    }
  }
  return value;
}

export async function loadHistory():Promise<{history:History;local:boolean}>{
  let response:Response|undefined;
  try{response=await fetch('/api/simulation/evidence',{cache:'no-store',signal:AbortSignal.timeout(10000)});}catch{}
  if(response?.ok)return {history:await decodeHistory(await response.text()),local:true};
  if(response&&![404,502,503,504].includes(response.status))throw new Error('The local history service rejected this request.');
  const catalog=await loadCatalog(true);
  if(!catalog.history)throw new Error('No exported history is available. Start the Python service to inspect local saved runs.');
  const exported=await fetch(catalog.history.url,{cache:'no-store'});
  if(!exported.ok)throw new Error('The exported run history is unavailable.');
  return {history:await decodeHistory(await exported.text(),catalog.history.sha256),local:false};
}

export function formatHistoryMetric(value:number|null,unit:string,difference=false):string{
  if(value===null)return 'Unknown';
  const sign=difference&&value>0?'+':'';
  if(unit==='rate')return `${sign}${(value*100).toFixed(1)}${difference?' pp':'%'}`;
  const moneySign=value<0?'-':sign;
  if(unit==='cents')return `${moneySign}$${(Math.abs(value)/100).toFixed(2)}`;
  if(unit==='usd')return `${moneySign}$${Math.abs(value).toFixed(4)}`;
  if(unit==='milliseconds')return `${sign}${(value/1000).toFixed(1)} s`;
  return sign+value.toLocaleString('en-US',{maximumFractionDigits:unit==='integer'?0:2});
}
