/** Validate published Python reports; never calculate experimental outcomes here. */
import { sha256, type Catalog } from './replay';

export type Report={study_kind?:'layout'|'model'|'assistance';protocol_sha256?:string;protocol_url?:string;report_version:number;study_id:string;status:string;cohort_size:number;repetitions:number;provider:string;limitations:string[];missing_evidence?:string[];campaign_budget_evidence?:{source:'ledger'|'saved_snapshot'|'unavailable';recorded_at:string|null};arms:{arm_id?:string;label?:string;model?:string;policy?:string;store_layout_id?:string;recorded_runs?:number;layout_id:string;completed_runs:number;metrics:Record<string,number|null>}[];paired:{comparison:string;metric:string;mean_difference:number|null;ci95:[number,number]|null;blocks:number;missing_blocks?:number;status?:'assessed'|'unassessed'}[];runs:{arm_id?:string;model?:string;file?:string;source_sha256?:string;run_id:string;layout_id:string;repetition:number;status:string;summary:{mean_list_completion:number;checkout_completion:number}}[];behavior?:{status?:string;pairs:number;valid_decisions:number;attempts:number;directional_pairs:number;assessable_pairs:number};behavior_evidence?:{file:string;sha256:string;provider:string;status:string;url?:string}|null};

function requireValue(value:unknown,message:string):asserts value {if(!value)throw new Error(message);}
const finite=(value:unknown)=>typeof value==='number'&&Number.isFinite(value);

export async function decodeReport(text:string,entry:Catalog['reports'][number]):Promise<Report>{
  requireValue(entry.sha256&&/^[a-f0-9]{64}$/.test(entry.sha256),'Report has no verified catalogue identity');
  requireValue(await sha256(text)===entry.sha256,'Report download integrity mismatch');
  const report=JSON.parse(text) as Report;
  requireValue(report.report_version===1&&typeof report.study_id==='string'&&typeof report.provider==='string','Unsupported experiment report');
  requireValue(['completed','pilot_or_incomplete'].includes(report.status),'Invalid experiment status');
  requireValue(Number.isInteger(report.cohort_size)&&report.cohort_size>0&&Number.isInteger(report.repetitions)&&report.repetitions>0,'Invalid protocol');
  requireValue(Array.isArray(report.arms)&&report.arms.length>0&&new Set(report.arms.map(a=>a.layout_id)).size===report.arms.length,'Invalid layout arms');
  for(const arm of report.arms){
    requireValue(typeof arm.layout_id==='string'&&Number.isInteger(arm.completed_runs)&&arm.completed_runs>=0,'Invalid run count');
    requireValue(arm.metrics&&Object.values(arm.metrics).every(v=>v===null||finite(v)),'Invalid reported metric');
  }
  requireValue(Array.isArray(report.paired)&&report.paired.every(p=>(p.mean_difference===null||finite(p.mean_difference))&&Number.isInteger(p.blocks)&&p.blocks>=0&&(p.missing_blocks===undefined||(Number.isInteger(p.missing_blocks)&&p.missing_blocks>=0))&&(p.mean_difference!==null||(p.blocks===0&&p.ci95===null))&&(p.ci95===null||(Array.isArray(p.ci95)&&p.ci95.length===2&&p.ci95.every(finite)&&p.ci95[0]<=p.ci95[1]))),'Invalid reported uncertainty');
  requireValue(Array.isArray(report.runs)&&new Set(report.runs.map(r=>r.run_id)).size===report.runs.length,'Duplicate or missing run evidence');
  requireValue(report.runs.every(r=>typeof r.run_id==='string'&&typeof r.layout_id==='string'&&typeof r.status==='string'&&finite(r.summary?.mean_list_completion)&&finite(r.summary?.checkout_completion)),'Invalid run summary');
  requireValue(Array.isArray(report.limitations)&&report.limitations.every(l=>typeof l==='string'),'Missing report limitations');
  if(report.study_kind){
    requireValue(['layout','model','assistance'].includes(report.study_kind)&&/^[a-f0-9]{64}$/.test(report.protocol_sha256??''),'Invalid controlled study identity');
    requireValue(report.arms.length===2&&report.arms.every(a=>a.arm_id===a.layout_id&&typeof a.label==='string'&&typeof a.model==='string'&&typeof a.policy==='string'&&typeof a.store_layout_id==='string'&&typeof a.recorded_runs==='number'&&Number.isInteger(a.recorded_runs)&&a.recorded_runs>=a.completed_runs),'Missing controlled study arms');
    requireValue(!report.protocol_url||/^\/replays\/study-[a-f0-9]{32}[.]protocol[.]json$/.test(report.protocol_url),'Invalid protocol download');
  }
  if(report.behavior_evidence)requireValue(/^[a-f0-9]{64}$/.test(report.behavior_evidence.sha256)&&report.behavior_evidence.provider===report.provider&&typeof report.behavior_evidence.url==='string'&&/^\/replays\/[^/]+[.]behavior[.]jsonl$/.test(report.behavior_evidence.url),'Invalid preference evidence identity');
  return report;
}
