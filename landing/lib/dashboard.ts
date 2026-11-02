/** Integrity-checked Python outcomes. Filtering and chart geometry only in React. */
import {sha256,type Catalog} from './replay';

export type Measure={id:string;label:string;unit:string;primary?:boolean};
export type DashboardCell={status:'recorded'|'not_evaluated'|'missing';run_ids:string[];runs:number;trips:number;finished:number;requested:number;purchased:number;stopped_runs:number;metrics:Record<string,number|null>};
export type DashboardModel={id:string;label:string;status:'recorded'|'not_evaluated';cells:Record<string,DashboardCell>};
export type DashboardView={id:string;label:string;note:string;runs:number;trips:number;models:DashboardModel[]};
export type Distribution={known:number;unknown:number;min:number|null;q1:number|null;median:number|null;q3:number|null;max:number|null};
export type TripPoint={profile_id:string;finished:boolean;requested:number;purchased:number;values:Record<string,number|null>};
export type DashboardRun={run_id:string;source_sha256:string;provider:string;model:string;layout_id:string;recorded_at:string;status:string;warnings:string[];group:string;repetition:number|null;cohort_sha256:string;shopping_rules:string;policy:string;source_url:string;replay_url:string;points:TripPoint[];distributions:Record<string,Distribution>};
export type Dashboard={dashboard_version:number;main_study_id:string;default_view:string;layouts:{id:string;label:string;description:string}[];measures:Measure[];distribution_measures:Measure[];views:DashboardView[];runs:DashboardRun[];
  coverage:{retained_runs:number;retained_trips:number;completed_runs:number;stopped_runs:number;main_runs:number;main_trips:number;groups:{id:string;label:string;runs:number;trips:number}[]};limitations:string[]};

const numeric=(v:unknown)=>typeof v==='number'&&Number.isFinite(v);
const nullable=(v:unknown)=>v===null||numeric(v);
const count=(v:unknown)=>Number.isInteger(v)&&Number(v)>=0;
function check(v:unknown,message:string):asserts v{if(!v)throw new Error(message);}
export async function decodeDashboard(text:string,entry:NonNullable<Catalog['dashboard']>):Promise<Dashboard>{
  check(entry.url==='/replays/evidence-dashboard.json'&&/^[a-f0-9]{64}$/.test(entry.sha256)&&await sha256(text)===entry.sha256,'Evidence dashboard integrity mismatch');
  const d=JSON.parse(text) as Dashboard;
  check(d.dashboard_version===1&&/^[a-f0-9]{32}$/.test(d.main_study_id),'Invalid evidence dashboard');
  check(Array.isArray(d.layouts)&&d.layouts.length===2&&new Set(d.layouts.map(l=>l.id)).size===2,'Invalid comparison layouts');
  check(Array.isArray(d.measures)&&d.measures.length>0&&new Set(d.measures.map(m=>m.id)).size===d.measures.length&&d.measures.every(m=>typeof m.label==='string'&&typeof m.unit==='string'),'Invalid metric definitions');
  check(Array.isArray(d.distribution_measures)&&d.distribution_measures.length===4,'Missing distribution measures');
  check(Array.isArray(d.runs)&&new Set(d.runs.map(r=>r.run_id)).size===d.runs.length,'Duplicate dashboard sources');
  const runIds=new Set(d.runs.map(r=>r.run_id));
  for(const r of d.runs){
    check(/^[a-f0-9]{32}$/.test(r.run_id)&&/^[a-f0-9]{64}$/.test(r.source_sha256)&&/^[a-f0-9]{64}$/.test(r.cohort_sha256),'Invalid source identity');
    check(['main','pilot','historical','openrouter'].includes(r.group)&&['openai','openrouter','gemini'].includes(r.provider)&&d.layouts.some(l=>l.id===r.layout_id),'Invalid source scope');
    check(r.source_url===`/replays/${r.run_id}.source.jsonl`&&r.replay_url===`/replays/${r.run_id}.json`,'Invalid evidence source link');
    check(Array.isArray(r.points)&&r.points.length>0&&new Set(r.points.map(p=>p.profile_id)).size===r.points.length,'Invalid trip identities');
    for(const p of r.points){
      check(typeof p.finished==='boolean'&&count(p.requested)&&count(p.purchased)&&p.purchased<=p.requested&&typeof p.profile_id==='string','Invalid trip outcome');
      check(p.values&&d.distribution_measures.every(m=>nullable(p.values[m.id]))&&numeric(p.values.moves)&&numeric(p.values.fulfillment),'Invalid trip measurements');
      check(Number(p.values.fulfillment)>=0&&Number(p.values.fulfillment)<=1&&(!p.finished?p.purchased===0:true),'Unpaid purchase in evidence');
    }
    for(const m of d.distribution_measures){const s=r.distributions[m.id];
      check(s&&count(s.known)&&count(s.unknown)&&s.known+s.unknown===r.points.length,'Invalid distribution coverage');
      check([s.min,s.q1,s.median,s.q3,s.max].every(nullable)&&(s.known===0?[s.min,s.q1,s.median,s.q3,s.max].every(n=>n===null):
        [s.min,s.q1,s.median,s.q3,s.max].every(numeric)&&s.min!<=s.q1!&&s.q1!<=s.median!&&s.median!<=s.q3!&&s.q3!<=s.max!),'Invalid distribution bounds');
    }
  }
  check(Array.isArray(d.views)&&d.views.length===3&&d.views.some(v=>v.id===d.default_view),'Invalid comparison views');
  for(const v of d.views){
    check(count(v.runs)&&count(v.trips)&&typeof v.note==='string'&&v.models?.length===4,'Invalid comparison sample');
    check(v.models.map(m=>m.id).join(',')==='gpt-6-luna,gpt-6.1-terra,qwen3-4b-instruct-2507,qwen3-4b-instruct-2507-finetuned','Invalid model comparison rows');
    for(const model of v.models)for(const layout of d.layouts){const c=model.cells[layout.id];
      check(c&&[c.runs,c.trips,c.finished,c.requested,c.purchased,c.stopped_runs].every(count)&&c.finished<=c.trips&&c.purchased<=c.requested&&c.stopped_runs<=c.runs,'Invalid model/layout coverage');
      check(c.run_ids.length===c.runs&&new Set(c.run_ids).size===c.runs&&c.run_ids.every(id=>runIds.has(id)),'Invalid model/layout sources');
      check(d.measures.every(m=>nullable(c.metrics[m.id])),'Invalid Python table metric');
      if(model.status==='not_evaluated')check(c.status==='not_evaluated'&&!c.runs&&!c.trips&&Object.values(c.metrics).every(n=>n===null),'Unevaluated Qwen has fabricated results');
      for(const id of c.run_ids){const r=d.runs.find(r=>r.run_id===id)!;
        check(r.group==='main'&&r.provider==='openai'&&r.model===model.id&&r.layout_id===layout.id,'Non-comparable source in headline table');
        if(v.id!=='all_attempts')check(r.status==='completed'&&!r.warnings.length,'Stopped source in completed-run view');
      }
    }
  }
  check(d.coverage?.retained_runs===d.runs.length&&Object.entries(d.coverage).filter(([k])=>k!=='groups').every(([,v])=>count(v))&&Array.isArray(d.coverage.groups),'Invalid retained coverage');
  check(Array.isArray(d.limitations)&&d.limitations.every(s=>typeof s==='string'),'Missing evidence limitations');
  return d;
}
