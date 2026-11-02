/** Display/session selection only. No simulation actions or provider calls. */
import type { ReplayData } from './replay';

export const liveRunStorageKey='simply.selected-live-run';
const runIdPattern=/^[a-f0-9]{32}$/;
type RunSelection={run_id:string;status:string;controllable:boolean};
export function liveSessionStorage():Storage|undefined{
  try{return typeof window==='undefined'?undefined:window.sessionStorage;}catch{return undefined;}
}
export function readRememberedRun(storage:Pick<Storage,'getItem'>|undefined):string{
  try{const id=storage?.getItem(liveRunStorageKey)??'';return runIdPattern.test(id)?id:'';}catch{return '';}
}
export function rememberRun(storage:Pick<Storage,'setItem'|'removeItem'>|undefined,id:string){
  try{if(runIdPattern.test(id))storage?.setItem(liveRunStorageKey,id);else storage?.removeItem(liveRunStorageKey);}catch{}
}
export function restoreRunSelection(current:string,runs:RunSelection[],remembered:string):string{
  if(current)return current;
  if(remembered&&runs.some(run=>run.run_id===remembered))return remembered;
  return runs.find(run=>run.status==='recording'&&run.controllable)?.run_id??'';
}
export function liveEndNotice(data:ReplayData):{title:string;detail:string;warning:boolean}|null{
  const status=data.source.status;
  if(status==='incomplete')return null;
  if(status==='budget_exhausted')return {title:'Stopped at the earlier local API budget',warning:true,
    detail:'This recording reached its configured experiment budget. New live runs now track API costs without an app-enforced spending cap. The stopped run’s final state is preserved.'};
  if(status==='aborted'){
    const limited=data.events.some(event=>event.failure?.includes('HTTP 429'));
    return {title:limited?'Stopped by a provider rate or quota limit':'Run stopped after an error',warning:true,
      detail:limited?'The provider returned HTTP 429. Provider rate and quota limits are separate from Simply’s cost tracking. Final positions and recorded decisions are preserved.':'Python stopped the run after a provider or configuration error. Final positions and recorded decisions are preserved; inspect the failures below.'};
  }
  if(status==='cancelled')return {title:'Run stopped',warning:false,detail:'The recorded final state is preserved. Save a partial replay or choose New setup when you want another run.'};
  return {title:'Run finished',warning:false,
    detail:`${data.summary.finished_count}/${data.summary.shopper_count} shoppers checked out. The final state is preserved. A finished run can include shoppers that reached an action or turn limit before checkout.`};
}
export function liveStatusLabel(status:string):string{
  return ({budget_exhausted:'Stopped · earlier local API budget',aborted:'Stopped · provider or configuration error',cancelled:'Stopped by user',completed:'Run finished'} as Record<string,string>)[status]??status.replaceAll('_',' ');
}
