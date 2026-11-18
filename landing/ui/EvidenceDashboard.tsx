'use client';

import {useEffect,useState} from 'react';
import {loadCatalog} from '../lib/recordings';
import {decodeDashboard,type Dashboard,type DashboardModel} from '../lib/dashboard';
import {formatHistoryMetric as format} from '../lib/evidence';
import EvidenceCharts from './EvidenceCharts';

/** Compact headline measures. Every value is Python's exported metric; React only lays them out. */
const TABLE_MEASURES=['impulse_units_per_trip','impulse_trip_share','checkout_completion','purchased_unit_fulfillment','moves_per_trip','provider_reported_cost_per_run_usd'];
const viaOpenRouter=(m:{id:string;provider?:string})=>(m.provider??(m.id==='qwen2.5-7b-instruct'?'openrouter':''))==='openrouter';

export default function EvidenceDashboard(){
  const [data,setData]=useState<Dashboard|null>(null);const [error,setError]=useState('');
  useEffect(()=>{let active=true;
    loadCatalog().then(async catalog=>{
      if(!catalog.dashboard)throw new Error('No comparison dashboard has been exported');
      const response=await fetch(catalog.dashboard.url,{cache:'no-store'});
      if(!response.ok)throw new Error('The comparison dashboard is unavailable');
      const decoded=await decodeDashboard(await response.text(),catalog.dashboard);
      if(active)setData(decoded);
    }).catch(cause=>{if(active)setError(cause instanceof Error?cause.message:'Unable to load results');});
    return()=>{active=false;};
  },[]);
  if(error)return <section className="evidence-notice is-warning" role="alert"><p>{error}. No results have been substituted.</p></section>;
  if(!data)return <p className="evidence-footnote" role="status">Loading verified recorded results…</p>;
  return <DashboardContent data={data}/>;
}

function modelLine(model:DashboardModel){return model.caption??(model.status==='not_evaluated'?'Not evaluated · results pending':'Measured');}

export function DashboardContent({data}:{data:Dashboard}){
  const view=data.views.find(v=>v.id===data.default_view)??data.views[0];
  const models=view.models;
  const measures=TABLE_MEASURES.map(id=>data.measures.find(m=>m.id===id)).filter((m):m is NonNullable<typeof m>=>Boolean(m))
    .filter(m=>!m.id.startsWith('provider_reported_')||models.some(viaOpenRouter));
  return <section className="model-evidence" aria-label="Model by layout comparison">
    <EvidenceCharts data={data} models={models}/>
    <p className="evidence-footnote evidence-scope"><strong>{view.runs} recorded runs · {view.trips} simulated trips.</strong> Simulations, not measured human behavior.</p>
    {view.highlights&&view.highlights.length>0&&<section className="evidence-takeaways" aria-label="What the runs show">
      <h3>What the runs show</h3>
      <ul>{view.highlights.map(text=><li key={text}>{text}</li>)}</ul>
    </section>}
    <p className="evidence-footnote">{view.note}</p>
    <div className="report-table model-layout-table"><table aria-label="Model metrics for Layout A and Layout B"><thead><tr><th scope="col">Model / measure</th>{data.layouts.map(layout=><th scope="col" key={layout.id}>{layout.label}<small>{layout.description}</small></th>)}</tr></thead>
      {models.map(model=><tbody key={model.id} aria-label={model.label}>
        <tr className="model-group"><th scope="rowgroup"><strong>{model.label}</strong><small>{modelLine(model)}</small></th>{data.layouts.map(layout=>{
          const c=model.cells[layout.id];
          return <td key={layout.id}>{c.status!=='recorded'?'N/A':`${c.runs} ${c.runs===1?'run':'runs'} · ${c.trips} trips`}<small>{c.status!=='recorded'?'No completed recording available':`${c.finished}/${c.trips} checked out`}</small></td>;
        })}</tr>
        {measures.map(measure=><tr key={measure.id}><th scope="row">{measure.label}</th>{data.layouts.map(layout=>{const c=model.cells[layout.id];
          return <td key={layout.id}>{c.status!=='recorded'||(measure.id.startsWith('provider_reported_')&&!viaOpenRouter(model))?'N/A':format(c.metrics[measure.id],measure.unit)}{measure.id==='purchased_unit_fulfillment'&&c.status==='recorded'&&<small>{c.purchased}/{c.requested} requested units paid</small>}</td>;})}</tr>)}
      </tbody>)}
    </table></div>
    <details className="evidence-details"><summary>Recordings behind this table</summary>{models.filter(m=>m.status==='recorded').map(model=><div key={model.id}><strong>{model.label}</strong>{data.layouts.map(layout=><p key={layout.id}>{layout.label}: {model.cells[layout.id].run_ids.map(id=><a key={id} href={`/replays/${id}.source.jsonl`} download>{id.slice(0,8)} · original recording </a>)}</p>)}</div>)}</details>
    <details className="evidence-details"><summary>Definitions, scope & verification</summary><ul>{data.limitations.map(text=><li key={text}>{text}</li>)}</ul><p><a href="/replays/evidence-dashboard.json" download>Download all table values, trip observations and source hashes</a></p><p>Python computes these results from canonical records. The browser only displays the exported metrics.</p></details>
  </section>;
}
