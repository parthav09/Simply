'use client';

import {useEffect,useState} from 'react';
import {decodePilotProgress,type PilotProgress as Progress} from '../lib/pilot-progress';

export default function PilotProgress({onProgress,backend='mps'}:{onProgress?:(progress:Progress|null)=>void;backend?:'mps'|'mlx'}={}){
  const [progress,setProgress]=useState<Progress|null>(null);const [unavailable,setUnavailable]=useState(false);
  useEffect(()=>{
    let active=true,timer:ReturnType<typeof setTimeout>|undefined;
    const refresh=async()=>{
      clearTimeout(timer);
      if(!active||document.hidden)return;
      try{
        const response=await fetch(`/api/simulation/${backend==='mlx'?'mlx-progress':'pilot-progress'}`,{cache:'no-store',signal:AbortSignal.timeout(10000)});
        if(!response.ok)throw new Error('Progress unavailable');
        const value=decodePilotProgress(await response.json(),`qwen2.5-7b-pilot-${backend}`);
        if(active){setProgress(value);setUnavailable(!value.available);onProgress?.(value);}
      }catch{if(active){setUnavailable(true);onProgress?.(null);}}
      finally{if(active&&!document.hidden)timer=setTimeout(refresh,30000);}
    };
    const visible=()=>{if(document.hidden)clearTimeout(timer);else void refresh();};
    void refresh();document.addEventListener('visibilitychange',visible);
    return()=>{active=false;clearTimeout(timer);document.removeEventListener('visibilitychange',visible);};
  },[onProgress,backend]);
  const finished=progress?.available&&progress.completed_runs===2;
  return <aside className="evidence-notice" aria-label="Fine-tuned Qwen collection status">
    <strong>Fine-tuned Qwen · {backend.toUpperCase()} · {finished?'both runs finished':'collection progress'}</strong>
    {unavailable?<p>Live collection status is unavailable. The table below contains exported recordings only.</p>:!progress?.available?<p>Reading the local pilot recordings…</p>:<>
      <ul>{progress.runs!.map(run=><li key={run.layout_id}><strong>{run.layout_id==='costco_back_anchor'?'Layout A':'Layout B'}</strong>: {run.status==='queued'?'Queued':run.status==='recording'?`Recording · ${run.decision_count.toLocaleString()} decisions saved`:run.status==='completed'?`Finished · ${run.finished_count}/${run.shopper_count} checked out`:`Stopped · ${run.status.replaceAll('_',' ')} · ${run.decision_count.toLocaleString()} decisions saved`}</li>)}</ul>
      <p>{finished?'Refresh this page to load the final exported metrics.':'Final metrics and replay downloads appear after each run finishes. These counts come from saved Python events; this view makes no model calls.'} <a href="/lab">Follow recordings in the shopper lab</a>.</p>
    </>}
  </aside>;
}
