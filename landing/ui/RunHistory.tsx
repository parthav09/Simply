'use client';

import {useEffect,useState} from 'react';
import {formatHistoryMetric as format,loadHistory,type History,type RunRow} from '../lib/evidence';
import {Icon} from './Icons';

const layoutName=(id:string)=>({costco_back_anchor:'Layout A · Anchor',neighborhood_express:'Layout B · Express'}[id]??id);
const modelName=(id:string)=>({'gpt-6-luna':'Luna','gpt-6.1-terra':'Terra'}[id]??id);
const when=(value:string)=>new Date(value).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/Los_Angeles'});
const status=(run:RunRow)=>({completed:'Finished',budget_exhausted:'Stopped · earlier API cap',aborted:'Stopped · provider error',cancelled:'Stopped by user',incomplete:'In progress / incomplete'}[run.status]??run.status.replaceAll('_',' '));
const primary=['checkout_completion','purchased_unit_fulfillment','mean_successful_moves','sales_cents','known_estimated_cost_usd','cost_per_completed_trip_usd'];
const diagnostic=['invalid_decision_count','grid_rejection_count','provider_failure_count','navigation_adjustments','overspending_fraction','checkout_overshoot_cents','purchased_off_list_units','loop_detections','request_latency_p50_ms','request_latency_p95_ms'];
const labels:Record<string,string>={checkout_completion:'Shoppers checked out',purchased_unit_fulfillment:'Shopping list purchased',mean_successful_moves:'Moves per shopper',sales_cents:'Simulated checkout sales',known_estimated_cost_usd:'Known API cost',cost_per_completed_trip_usd:'API cost per checkout'};

function RunCard({run,role}:{run:RunRow;role:string}){
  const finished=run.status==='completed';
  return <article className="evidence-run-card">
    <div className="run-card-top"><span className="eyebrow">{role}</span><span className={`evidence-status ${finished?'is-complete':''}`}>{status(run)}</span></div>
    <h2>{layoutName(run.layout_id)}</h2><p>{modelName(run.model)} · {run.shopper_count} shoppers · {when(run.recorded_at)} PT</p>
    <div className="run-card-progress"><span>Checked out <strong>{run.finished_count} / {run.shopper_count}</strong></span><div className="evidence-progress" role="img" aria-label={`${run.finished_count} of ${run.shopper_count} shoppers checked out`}><span style={{width:`${(run.metrics.checkout_completion??0)*100}%`}}/></div></div>
    <dl><div><dt>List purchased</dt><dd>{format(run.metrics.purchased_unit_fulfillment,'rate')}</dd></div><div><dt>Moves / shopper</dt><dd>{format(run.metrics.mean_successful_moves,'number')}</dd></div><div><dt>API estimate</dt><dd>{format(run.metrics.known_estimated_cost_usd,'usd')}</dd>{!run.cost_complete&&<small>Partial cost</small>}</div></dl>
  </article>;
}

export default function RunHistory(){
  const [snapshot,setSnapshot]=useState<{history:History;local:boolean}|null>(null);
  const [error,setError]=useState('');const [revision,setRevision]=useState(0);
  const [baseline,setBaseline]=useState('');const [candidate,setCandidate]=useState('');
  useEffect(()=>{
    let active=true,inFlight=false;let timer:ReturnType<typeof setTimeout>|undefined;
    const refresh=async()=>{
      if(!active||inFlight)return;inFlight=true;
      try{
        const next=await loadHistory();
        if(active){
          const sorted=[...next.history.runs].sort((a,b)=>b.recorded_at.localeCompare(a.recorded_at));
          setSnapshot(next);setError('');
          setBaseline(previous=>sorted.some(run=>run.run_id===previous)?previous:sorted[1]?.run_id??sorted[0]?.run_id??'');
          setCandidate(previous=>sorted.some(run=>run.run_id===previous)?previous:sorted[0]?.run_id??'');
        }
      }catch(cause){if(active)setError(cause instanceof Error?cause.message:'Could not load the saved runs.');}
      finally{inFlight=false;if(active&&!document.hidden)timer=setTimeout(refresh,15000);}
    };
    const visibility=()=>{clearTimeout(timer);if(!document.hidden)void refresh();};
    void refresh();document.addEventListener('visibilitychange',visibility);
    return()=>{active=false;clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);};
  },[revision]);
  if(!snapshot)return <section className="evidence-empty" aria-busy={!error}><h2>{error?'Results unavailable':'Opening saved results…'}</h2><p>{error||'Reading the Python recordings.'}</p>{error&&<button onClick={()=>setRevision(value=>value+1)}>Try again</button>}</section>;
  const {history,local}=snapshot;
  const runs=[...history.runs].sort((a,b)=>b.recorded_at.localeCompare(a.recorded_at));
  const left=runs.find(run=>run.run_id===baseline);const right=runs.find(run=>run.run_id===candidate);
  const selected=[...new Set([baseline,candidate])].map(id=>runs.find(run=>run.run_id===id)).filter((run):run is RunRow=>!!run);
  const comparison=history.comparisons[baseline]?.find(item=>item.run_id===candidate);
  const partial=selected.some(run=>run.status!=='completed');
  const metricTable=(keys:string[])=> <div className="report-table evidence-comparison-table"><table><thead><tr><th>Measure</th>{selected.map((run,index)=><th key={run.run_id}>{index===0?'Baseline':'Comparison'}<small>{layoutName(run.layout_id)} · {modelName(run.model)}</small></th>)}{selected.length===2&&<th>Change<small>Comparison − baseline</small></th>}</tr></thead><tbody>{keys.filter(key=>history.metric_definitions[key]).map(key=>{
    const definition=history.metric_definitions[key];const difference=comparison?.differences[key];
    return <tr key={key}><th>{labels[key]??definition.label}</th>{selected.map(run=><td key={run.run_id}>{format(run.metrics[key],definition.unit)}{key==='known_estimated_cost_usd'&&!run.cost_complete&&<small>Total cost unknown</small>}</td>)}{selected.length===2&&<td>{difference?format(difference.absolute,definition.unit,true):'—'}</td>}</tr>;
  })}</tbody></table></div>;
  return <section className="evidence-results" aria-label="Saved run comparison">
    <div className="evidence-results-heading"><p>{runs.length} saved {runs.length===1?'run':'runs'} · {local?'Saved locally':'Published snapshot'}</p><button aria-label="Refresh results" onClick={()=>setRevision(value=>value+1)}><Icon name="reset" size={14}/>Refresh</button></div>
    {error&&<p className="evidence-notice" role="alert">{error} Showing the last loaded results.</p>}
    {!runs.length?<div className="evidence-empty"><h2>No saved results yet.</h2><p>Finish a Python simulation to see its recorded outcomes here.</p></div>:<>
      {runs.length>2&&<div className="evidence-selectors"><label>Baseline<select aria-label="Comparison baseline" value={baseline} onChange={event=>setBaseline(event.target.value)}>{runs.map(run=><option key={run.run_id} value={run.run_id}>{layoutName(run.layout_id)} · {modelName(run.model)} · {when(run.recorded_at)}</option>)}</select></label><label>Compare with<select aria-label="Comparison run" value={candidate} onChange={event=>setCandidate(event.target.value)}>{runs.map(run=><option key={run.run_id} value={run.run_id}>{layoutName(run.layout_id)} · {modelName(run.model)} · {when(run.recorded_at)}</option>)}</select></label></div>}
      <div className="evidence-run-grid">{selected.map((run,index)=><RunCard key={run.run_id} run={run} role={index===0?'Baseline run':'Comparison run'}/>)}</div>
      <div className={`evidence-notice ${partial?'is-warning':''}`} role="status"><Icon name="info" size={17}/><p>{partial?'These runs include unfinished trips. Shorter paths and lower costs can reflect an early stop, so they do not demonstrate an improvement.':comparison?.matched_controls?'Recorded controls match. This pair describes observed results; repeated controlled runs are needed to establish an improvement.':'These runs use different settings or scope. Treat the numbers as a descriptive comparison.'}{left&&right&&left.layout_id===right.layout_id?' Both selected runs use the same layout.':''}</p></div>
      {metricTable(primary)}
      <p className="evidence-footnote">The list score counts items actually paid for. Every shopper is included. Sales are simulated; API cost is estimated. Rate changes use percentage points (pp). “Unknown” means the recording cannot establish the value.</p>
      <details className="evidence-details"><summary>Diagnostics & source recordings</summary>{metricTable(diagnostic)}{!!comparison?.reasons.length&&<p>Comparison limits: {comparison.reasons.join('; ')}.</p>}<div className="evidence-source-grid">{selected.map(run=><div key={run.run_id}><strong>{layoutName(run.layout_id)} · {modelName(run.model)}</strong><p><code>{run.run_id}</code><br/>{run.navigation_policy} · {run.shopping_rules==='unique_single_checkout_v1'?'Unique products · one checkout':'Original quantity / checkout rules'}</p>{run.published&&<a href={run.published.evidence_url} download>Download original recording</a>}<p className="evidence-source-hash">SHA-256 <code>{run.source_sha256}</code></p></div>)}</div><a href={local?'/api/simulation/evidence':'/replays/history.json'} download="simply-results.json">Download all result data</a>{!!history.issues.length&&<p>{history.issues.length} unreadable or unsupported files were excluded.</p>}</details>
    </>}
  </section>;
}
