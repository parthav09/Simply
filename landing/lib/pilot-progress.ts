/** Read-only progress from Python's canonical recording, never final replay evidence. */
export type PilotProgressRun={layout_id:string;model:string;status:string;decision_count:number;finished_count:number;shopper_count:number;run_id:string|null};
export type PilotProgress={progress_version:1;available:boolean;study_id?:string;protocol_sha256?:string;scheduled_runs?:number;completed_runs?:number;runs?:PilotProgressRun[]};
export function pilotCellLabel(run?:PilotProgressRun):{label:string;detail:string}{
  if(!run)return {label:'Pending',detail:'Awaiting a completed recording'};
  if(run.status==='queued')return {label:'Queued',detail:'Run has not started'};
  if(run.status==='recording')return {label:'Recording',detail:`${run.decision_count.toLocaleString()} decisions saved · final metrics pending`};
  if(run.status==='completed')return {label:'Finished',detail:'Final replay export pending · refresh shortly'};
  return {label:'Stopped',detail:`${run.decision_count.toLocaleString()} decisions saved · partial results pending`};
}
export function decodePilotProgress(value:unknown, model='qwen2.5-7b-pilot-mps'):PilotProgress{
  const p=value as PilotProgress;
  const count=(n:unknown)=>Number.isInteger(n)&&Number(n)>=0;
  if(!p||p.progress_version!==1||typeof p.available!=='boolean')throw new Error('Invalid pilot progress');
  if(!p.available)return p;
  if(!/^[a-f0-9]{32}$/.test(p.study_id??'')||!/^[a-f0-9]{64}$/.test(p.protocol_sha256??'')||p.scheduled_runs!==2||!count(p.completed_runs)||(p.completed_runs??0)>2||p.runs?.length!==2)throw new Error('Invalid pilot study');
  if(p.completed_runs!==p.runs.filter(r=>r.status==='completed').length)throw new Error('Pilot completion count differs from recordings');
  if(new Set(p.runs.map(r=>r.layout_id)).size!==2||!p.runs.every(r=>
    ['costco_back_anchor','neighborhood_express'].includes(r.layout_id)&&r.model===model&&
    ['queued','recording','completed','aborted','cancelled','budget_exhausted','incomplete'].includes(r.status)&&
    count(r.decision_count)&&count(r.finished_count)&&r.shopper_count===10&&r.finished_count<=10&&
    (r.run_id===null?r.status==='queued'&&r.decision_count===0&&r.finished_count===0:/^[a-f0-9]{32}$/.test(r.run_id))
  ))throw new Error('Invalid pilot recording progress');
  return p;
}
