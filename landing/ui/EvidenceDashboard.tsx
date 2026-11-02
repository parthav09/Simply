'use client';

import {useEffect,useState} from 'react';
import {loadCatalog} from '../lib/recordings';
import {decodeDashboard,type Dashboard,type DashboardRun,type TripPoint} from '../lib/dashboard';
import {formatHistoryMetric as format} from '../lib/evidence';

const modelName=(id:string)=>({'gpt-6-luna':'Luna','gpt-6.1-terra':'Terra'} as Record<string,string>)[id]??id;
const layoutName=(id:string)=>id==='costco_back_anchor'?'A':'B';
const groupName=(run:DashboardRun)=>run.group==='main'?`Main · R${run.repetition}`:run.group==='pilot'?'Separate pilot':run.group==='historical'?'Historical demo':'OpenRouter';

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

export function DashboardContent({data}:{data:Dashboard}){
  const [viewId,setViewId]=useState(data.default_view);const [expanded,setExpanded]=useState(false);
  const view=data.views.find(v=>v.id===viewId)??data.views[0];
  const measures=data.measures.filter(m=>expanded||m.primary);
  return <section className="model-evidence" aria-label="Model by layout comparison">
    <div className="evidence-results-heading"><div><p className="eyebrow">Recorded outcomes · direct OpenAI</p><h2>Models × layouts</h2></div><span className="evidence-status is-complete">Existing recordings · no new API calls</span></div>
    <div className="evidence-selectors dashboard-selectors">
      <label>Results shown<select value={view.id} onChange={e=>setViewId(e.target.value)}>{data.views.map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</select></label>
      <label className="evidence-toggle"><input type="checkbox" checked={expanded} onChange={e=>setExpanded(e.target.checked)}/>Show detailed metrics</label>
    </div>
    <p className="evidence-footnote"><strong>{view.runs} recorded runs · {view.trips} simulated trips.</strong> {view.note}</p>
    <p className="evidence-footnote">The same products, prices, profiles, lists and navigation assistance are frozen across the main study. Only shelf placement changes for a layout comparison. These results describe simulations, not measured human behavior.</p>
    <div className="report-table model-layout-table"><table aria-label="Model metrics for Layout A and Layout B"><thead><tr><th scope="col">Model / measure</th>{data.layouts.map(layout=><th scope="col" key={layout.id}>{layout.label}<small>{layout.description}</small></th>)}</tr></thead>
      {view.models.map(model=><tbody key={model.id} aria-label={model.label}>
        <tr className="model-group"><th scope="rowgroup"><strong>{model.label}</strong><small>{model.status==='not_evaluated'?'Not evaluated · results pending':'Measured · direct OpenAI API'}</small></th>{data.layouts.map(layout=>{const c=model.cells[layout.id];return <td key={layout.id}>{c.status==='not_evaluated'?'N/A':`${c.runs} ${c.runs===1?'run':'runs'} · ${c.trips} trips`}<small>{c.status==='not_evaluated'?'No recording available':`${c.finished}/${c.trips} checked out${c.stopped_runs?` · ${c.stopped_runs} interrupted`:''}`}</small></td>;})}</tr>
        {measures.map(measure=><tr key={measure.id}><th scope="row">{measure.label}</th>{data.layouts.map(layout=>{const c=model.cells[layout.id];return <td key={layout.id}>{c.status==='not_evaluated'||c.status==='missing'?'N/A':format(c.metrics[measure.id],measure.unit)}{measure.id==='purchased_unit_fulfillment'&&c.status==='recorded'&&<small>{c.purchased}/{c.requested} requested units paid</small>}</td>;})}</tr>)}
      </tbody>)}
    </table></div>
    <p className="evidence-footnote">N/A = no evaluation recorded. Unknown = a measured attempt has missing charge or usage information. API estimates include applicable cache charges; unfinished trips contribute costs but no paid purchases.</p>
    <details className="evidence-details"><summary>Recordings behind this table</summary>{view.models.filter(m=>m.status==='recorded').map(model=><div key={model.id}><strong>{model.label}</strong>{data.layouts.map(layout=><p key={layout.id}>{layout.label}: {model.cells[layout.id].run_ids.map(id=><a key={id} href={`/replays/${id}.source.jsonl`} download>{id.slice(0,8)} · original recording </a>)}</p>)}</div>)}</details>
    <RunDistributions data={data}/>
    <details className="evidence-details"><summary>Definitions, scope & verification</summary><ul>{data.limitations.map(text=><li key={text}>{text}</li>)}</ul><p><a href="/replays/evidence-dashboard.json" download>Download all table values, trip observations and source hashes</a></p><p>Python computes these results from canonical records. The browser only filters observations and displays the exported metrics.</p></details>
  </section>;
}

function RunDistributions({data}:{data:Dashboard}){
  const [group,setGroup]=useState('all');const [metricId,setMetricId]=useState('moves');
  const [pointId,setPointId]=useState('');
  const runs=data.runs.filter(r=>group==='all'||r.group===group);
  const metric=data.distribution_measures.find(m=>m.id===metricId)??data.distribution_measures[0];
  const options=runs.flatMap(run=>run.points.map(point=>({run,point,id:`${run.run_id}:${point.profile_id}`})));
  const selected=options.find(p=>p.id===pointId)??options[0];
  const selectedId=selected?.id??'';
  const hasKnown=runs.some(r=>r.distributions[metric.id].known>0);
  const scaleMax=metric.id==='fulfillment'?1:Math.max(1,...runs.map(r=>r.distributions[metric.id].max??0));
  const x=(value:number)=>290+value/scaleMax*330;
  const height=runs.length*62+75;
  const select=(run:DashboardRun,point:TripPoint)=>setPointId(`${run.run_id}:${point.profile_id}`);
  return <section className="run-distributions" aria-label="Distributions of all retained recordings">
    <h2>See the spread, not just the average</h2>
    <p className="evidence-footnote">{data.coverage.retained_runs} retained runs · {data.coverage.retained_trips} attempted trips · {data.coverage.completed_runs} completed runs · {data.coverage.stopped_runs} interrupted runs. Each row below is one recording; pilots, historical settings and OpenRouter are never averaged into the main comparison.</p>
    <div className="evidence-selectors">
      <label>Recordings<select value={group} onChange={e=>setGroup(e.target.value)}><option value="all">All retained recordings · {data.coverage.retained_runs} runs</option>{data.coverage.groups.map(g=><option key={g.id} value={g.id}>{g.label} · {g.runs} runs</option>)}</select></label>
      <label>Distribution measure<select value={metric.id} onChange={e=>setMetricId(e.target.value)}>{data.distribution_measures.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></label>
    </div>
    <p className="evidence-footnote">○ Checked out · × Unfinished. The shaded band is the middle 50% of observed trips in that run; the vertical mark is its median. These are distributions, not confidence intervals. Repeated profiles are not independent people.</p>
    {selected&&<p className="distribution-readout" aria-live="polite"><strong>{selected.point.profile_id}</strong> · {modelName(selected.run.model)} / Layout {layoutName(selected.run.layout_id)} · {groupName(selected.run)}: <strong>{format(selected.point.values[metric.id],metric.unit)}</strong> · {selected.point.finished?'Checked out':'Unfinished'} · <a href={selected.run.source_url} download>Original recording {selected.run.run_id.slice(0,8)}</a></p>}
    {!runs.length?<p className="evidence-footnote">No retained recordings in this group.</p>:<div className="distribution-chart-scroll"><svg viewBox={`0 0 850 ${height}`} className="distribution-chart" aria-label={`${metric.label} for every trip, grouped by source recording`}>
      <text x="8" y="18">Run / scope</text><text x="655" y="18">Median [middle 50%]</text>
      {hasKnown&&[0,.5,1].map(f=><g key={f}><line className="profile-grid" x1={x(scaleMax*f)} x2={x(scaleMax*f)} y1="30" y2={height-42}/><text x={x(scaleMax*f)} y={height-22} textAnchor="middle">{format(scaleMax*f,metric.unit)}</text></g>)}
      {runs.map((run,i)=>{const cy=52+i*62;const stat=run.distributions[metric.id];return <g key={run.run_id}>
        <text x="8" y={cy-3}>{modelName(run.model)} · Layout {layoutName(run.layout_id)} · {groupName(run)}</text><text x="8" y={cy+16} className="distribution-secondary">{run.status==='completed'?'Completed':'Interrupted'} · {run.points.length} trips · {run.run_id.slice(0,8)}</text>
        {stat.known>0&&<><line className="distribution-whisker" x1={x(stat.min!)} x2={x(stat.max!)} y1={cy} y2={cy}/><rect className="distribution-iqr" x={x(stat.q1!)} y={cy-10} width={Math.max(1,x(stat.q3!)-x(stat.q1!))} height="20"/><line className="distribution-median" x1={x(stat.median!)} x2={x(stat.median!)} y1={cy-14} y2={cy+14}/></>}
        {run.points.map((p,j)=>{const value=p.values[metric.id];if(value===null)return null;const px=x(value),py=cy+(j%3-1)*5;const active=`${run.run_id}:${p.profile_id}`===selectedId;return <g key={p.profile_id} className={`distribution-point${active?' is-selected':''}`} role="button" tabIndex={0} aria-pressed={active} aria-label={`${p.profile_id}, ${modelName(run.model)}, Layout ${layoutName(run.layout_id)}, ${groupName(run)}, ${format(value,metric.unit)}, ${p.finished?'checked out':'unfinished'}`} onMouseEnter={()=>select(run,p)} onFocus={()=>select(run,p)} onClick={()=>select(run,p)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(run,p);}}}>
          <circle className="distribution-hit" cx={px} cy={py} r="9"/>{p.finished?<circle cx={px} cy={py} r={active?5:3}/>:<path d={`M${px-4},${py-4}l8,8m-8,0l8,-8`}/>}
        </g>;})}
        <text x="655" y={cy}>{format(stat.median,metric.unit)}{stat.known>0?` [${format(stat.q1,metric.unit)}–${format(stat.q3,metric.unit)}]`:''}</text><text x="655" y={cy+18} className="distribution-secondary">{stat.known} known{stat.unknown?` · ${stat.unknown} unknown`:''}</text>
      </g>;})}
      <text x="455" y={height-2} textAnchor="middle">{metric.label}</text>
    </svg></div>}
    <label className="profile-measure">Inspect an exact trip<select value={selectedId} onChange={e=>setPointId(e.target.value)}>{options.map(p=><option key={p.id} value={p.id}>{p.point.profile_id} · {modelName(p.run.model)} · Layout {layoutName(p.run.layout_id)} · {groupName(p.run)} · {p.run.run_id.slice(0,8)}</option>)}</select></label>
    <details className="evidence-details"><summary>Exact run distributions & original sources</summary><div className="report-table"><table><thead><tr><th>Recording</th><th>Status / scope</th><th>Minimum</th><th>Median</th><th>Maximum</th><th>Known / unknown trips</th></tr></thead><tbody>{runs.map(run=>{const s=run.distributions[metric.id];return <tr key={run.run_id}><th><a href={run.source_url} download>{modelName(run.model)} · Layout {layoutName(run.layout_id)} · {run.run_id.slice(0,8)}</a></th><td>{run.status} · {groupName(run)}<small>{run.provider} · {run.shopping_rules}</small></td><td>{format(s.min,metric.unit)}</td><td>{format(s.median,metric.unit)}</td><td>{format(s.max,metric.unit)}</td><td>{s.known} / {s.unknown}</td></tr>;})}</tbody></table></div></details>
  </section>;
}
