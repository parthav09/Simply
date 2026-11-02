/** Validate Python-authored factorial results. No browser outcome calculation. */
import {sha256,type Catalog} from './replay';
export type Identity={model:string;layout_id:string};
export type ProfileMetrics={checkout_completion:number;purchased_unit_fulfillment:number;mean_successful_moves:number;model_requests:number|null;estimated_cost_usd:number|null};
export type ProfileObservation={profile_id:string;agent_id:string;profile_sha256:string;requested_products:number;purchased_products:number;metrics:ProfileMetrics};
export type ProfilePair={profile_id:string;repetition:number;baseline_run_id:string;candidate_run_id:string;baseline:ProfileMetrics;candidate:ProfileMetrics;difference:ProfileMetrics};
export type MatrixReport={matrix_report_version:number;study_id:string;protocol_sha256:string;status:'completed'|'incomplete';repetitions:number;cohort_size:number;
  provider?:'openai'|'openrouter';pending_models?:{model:string;status:'pending';reason:string}[];
  collection:{planned_runs:number;recorded_runs:number;completed_runs:number;stopped_runs:number;missing_runs:number;attempted_trips:number;completed_checkouts:number;provider_error_codes:Record<string,number>;summary:string};
  conditions:(Identity&{policy:string;recorded_runs:number;finished:number;trips:number;collection_note?:string;metrics:Record<string,number|null>})[];
  comparisons:{baseline:Identity;candidate:Identity;metrics:Record<string,{difference:number|null;ci95:[number,number]|null;blocks:number;missing_blocks:number}>;complete_repetitions:number[];profile_pairs:ProfilePair[]}[];
  runs:(Identity&{run_id:string;source_sha256:string;repetition:number;status:string;warnings:string[];audit:{profiles:ProfileObservation[]}})[];limitations:string[]};
const finite=(n:unknown)=>typeof n==='number'&&Number.isFinite(n);
function check(condition:unknown,message:string):asserts condition{if(!condition)throw new Error(message);}
export async function decodeMatrix(text:string,entry:NonNullable<Catalog['matrix']>):Promise<MatrixReport>{
  check(/^[a-f0-9]{64}$/.test(entry.sha256)&&await sha256(text)===entry.sha256,'Matrix download integrity mismatch');
  check(/^\/replays\/matrix-[a-f0-9]{32}[.]json$/.test(entry.url),'Invalid matrix result link');
  check(/^\/replays\/matrix-[a-f0-9]{32}[.]protocol[.]json$/.test(entry.protocol_url),'Invalid matrix protocol link');
  const value=JSON.parse(text) as MatrixReport;
  check(value.matrix_report_version===2&&/^[a-f0-9]{32}$/.test(value.study_id)&&/^[a-f0-9]{64}$/.test(value.protocol_sha256),'Invalid matrix identity');
  check(entry.url===`/replays/matrix-${value.study_id}.json`&&entry.protocol_url===`/replays/matrix-${value.study_id}.protocol.json`,'Matrix catalogue identity mismatch');
  check(['completed','incomplete'].includes(value.status),'Invalid matrix status');
  check(value.provider===undefined||['openai','openrouter'].includes(value.provider),'Invalid matrix provider');
  check(value.pending_models===undefined||(Array.isArray(value.pending_models)&&value.pending_models.every(m=>typeof m.model==='string'&&m.status==='pending'&&typeof m.reason==='string')),'Invalid pending models');
  check(Number.isInteger(value.repetitions)&&value.repetitions>0&&Number.isInteger(value.cohort_size)&&value.cohort_size>0,'Invalid matrix population');
  check(value.collection&&typeof value.collection.summary==='string'&&['planned_runs','recorded_runs','completed_runs','stopped_runs','missing_runs','attempted_trips','completed_checkouts'].every(k=>Number.isInteger(value.collection[k as keyof typeof value.collection])&&Number(value.collection[k as keyof typeof value.collection])>=0),'Invalid collection coverage');
  check(Array.isArray(value.conditions)&&value.conditions.length===4,'Missing matrix conditions');
  const identity=(row:Identity)=>`${row.model}:${row.layout_id}`;
  const identities=new Set(value.conditions.map(identity));
  check(identities.size===4,'Duplicate matrix conditions');
  for(const row of value.conditions){
    check(typeof row.model==='string'&&typeof row.layout_id==='string'&&typeof row.policy==='string','Invalid matrix scope');
    check(row.collection_note===undefined||typeof row.collection_note==='string','Invalid condition coverage');
    check(['gpt-6-luna','gpt-6.1-terra'].includes(row.model)&&['costco_back_anchor','neighborhood_express'].includes(row.layout_id),'Unsupported matrix condition');
    check([row.recorded_runs,row.finished,row.trips].every(n=>Number.isInteger(n)&&n>=0)&&row.finished<=row.trips,'Invalid matrix counts');
    check(row.metrics&&Object.values(row.metrics).every(n=>n===null||finite(n)),'Invalid Python matrix metrics');
    check(['checkout_completion','purchased_unit_fulfillment','mean_successful_moves','cost_per_completed_trip_usd','assisted_request_fraction'].every(k=>row.metrics[k]===null||finite(row.metrics[k])),'Missing primary matrix metrics');
  }
  check(Array.isArray(value.comparisons)&&value.comparisons.length===4,'Missing planned comparisons');
  for(const row of value.comparisons){
    check(identities.has(identity(row.baseline))&&identities.has(identity(row.candidate)),'Unknown comparison condition');
    check(Object.values(row.metrics).every(v=>(v.difference===null||finite(v.difference))&&Number.isInteger(v.blocks)&&v.blocks>=0&&Number.isInteger(v.missing_blocks)&&v.missing_blocks>=0&&
      (v.ci95===null||(Array.isArray(v.ci95)&&v.ci95.length===2&&v.ci95.every(finite)&&v.ci95[0]<=v.ci95[1]))),'Invalid paired matrix result');
    check(['checkout_completion','purchased_unit_fulfillment','mean_successful_moves'].every(k=>row.metrics[k]),'Missing primary matrix contrasts');
  }
  check(Array.isArray(value.runs)&&new Set(value.runs.map(r=>r.run_id)).size===value.runs.length&&value.runs.every(r=>/^[a-f0-9]{64}$/.test(r.source_sha256)),'Invalid matrix sources');
  const profileKeys=['checkout_completion','purchased_unit_fulfillment','mean_successful_moves','model_requests','estimated_cost_usd'] as const;
  const validMetrics=(metrics:ProfileMetrics,delta=false)=>metrics&&profileKeys.every(k=>(metrics[k]===null&&['model_requests','estimated_cost_usd'].includes(k))||finite(metrics[k]))&&
    (delta||([0,1].includes(metrics.checkout_completion)&&metrics.purchased_unit_fulfillment>=0&&metrics.purchased_unit_fulfillment<=1&&metrics.mean_successful_moves>=0&&
      [metrics.model_requests,metrics.estimated_cost_usd].every(n=>n===null||n>=0)));
  for(const run of value.runs){
    check(identities.has(identity(run))&&Number.isInteger(run.repetition)&&run.repetition>0&&run.repetition<=value.repetitions&&Array.isArray(run.warnings),'Invalid profile run');
    check(Array.isArray(run.audit?.profiles)&&run.audit.profiles.length===value.cohort_size&&new Set(run.audit.profiles.map(p=>p.profile_id)).size===value.cohort_size,'Missing profile observations');
    for(const p of run.audit.profiles)check(typeof p.profile_id==='string'&&typeof p.agent_id==='string'&&/^[a-f0-9]{64}$/.test(p.profile_sha256)&&
      Number.isInteger(p.requested_products)&&Number.isInteger(p.purchased_products)&&p.requested_products>=0&&p.purchased_products>=0&&p.purchased_products<=p.requested_products&&validMetrics(p.metrics),'Invalid profile observation');
  }
  for(const comparison of value.comparisons){
    check(Array.isArray(comparison.complete_repetitions)&&new Set(comparison.complete_repetitions).size===comparison.complete_repetitions.length&&
      comparison.complete_repetitions.every(n=>Number.isInteger(n)&&n>0&&n<=value.repetitions),'Invalid profile repetition coverage');
    check(Array.isArray(comparison.profile_pairs)&&comparison.profile_pairs.length===comparison.complete_repetitions.length*value.cohort_size&&
      new Set(comparison.profile_pairs.map(p=>`${p.repetition}:${p.profile_id}`)).size===comparison.profile_pairs.length,'Invalid profile pair coverage');
    for(const pair of comparison.profile_pairs){
      check(comparison.complete_repetitions.includes(pair.repetition)&&validMetrics(pair.baseline)&&validMetrics(pair.candidate)&&validMetrics(pair.difference,true),'Invalid profile pair metrics');
      for(const side of ['baseline','candidate'] as const){
        const run=value.runs.find(r=>r.run_id===pair[`${side}_run_id`]);
        const profile=run?.audit.profiles.find(p=>p.profile_id===pair.profile_id);
        check(run&&identity(run)===identity(comparison[side])&&run.repetition===pair.repetition&&run.status==='completed'&&!run.warnings.length&&profile&&
          profileKeys.every(k=>profile.metrics[k]===pair[side][k]),'Profile pair source mismatch');
      }
    }
  }
  check(Array.isArray(value.limitations)&&value.limitations.every(l=>typeof l==='string'),'Missing matrix limitations');
  return value;
}
