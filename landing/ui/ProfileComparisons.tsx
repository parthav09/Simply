'use client';

import {useState} from 'react';
import type {Identity,MatrixReport,ProfileMetrics} from '../lib/matrix';
import {formatHistoryMetric as format} from '../lib/evidence';

const name=(row:Identity)=>`${row.model==='gpt-6-luna'?'Luna':'Terra'} · Layout ${row.layout_id==='costco_back_anchor'?'A':'B'}`;
const same=(a:Identity,b:Identity)=>a.model===b.model&&a.layout_id===b.layout_id;
const fields=[['purchased_unit_fulfillment','List purchased','rate'],['checkout_completion','Checkout','rate'],['mean_successful_moves','Moves','number'],['model_requests','API requests','number'],['estimated_cost_usd','Trip API estimate','usd']] as const;

export default function ProfileComparisons({report}:{report:MatrixReport}){
  const [comparisonIndex,setComparisonIndex]=useState(1);
  const [repetition,setRepetition]=useState(1);
  const [profileId,setProfileId]=useState('');
  const [effort,setEffort]=useState<'mean_successful_moves'|'model_requests'>('mean_successful_moves');
  const comparison=report.comparisons[comparisonIndex];
  const runs=report.runs.filter(r=>same(r,comparison.baseline)||same(r,comparison.candidate));
  const repetitions=[...new Set(runs.map(r=>r.repetition))].sort((a,b)=>a-b);
  const selectedRepetition=repetitions.includes(repetition)?repetition:repetitions[0];
  const own=runs.filter(r=>r.repetition===selectedRepetition).sort((a,b)=>Number(same(b,comparison.baseline))-Number(same(a,comparison.baseline)));
  const pairs=comparison.profile_pairs.filter(p=>p.repetition===selectedRepetition);
  const profiles=[...new Set(own.flatMap(r=>r.audit.profiles.map(p=>p.profile_id)))].sort();
  const selectedProfile=profiles.includes(profileId)?profileId:profiles[0];
  const points=own.flatMap(run=>run.audit.profiles.map(p=>({...p,run,side:same(run,comparison.baseline)?'baseline':'candidate'})));
  const selected=points.filter(p=>p.profile_id===selectedProfile);
  const maxMoves=Math.max(10,...points.map(p=>p.metrics.mean_successful_moves));
  const xMax=Math.ceil(maxMoves/10)*10;
  const maxDelta=Math.max(1,...pairs.map(p=>Math.abs(p.difference[effort]??0)));
  const x=(n:number)=>60+n/xMax*300;
  const y=(n:number)=>245-n*200;
  const pairHeight=Math.max(150,pairs.length*28+55);
  const select=(id:string)=>setProfileId(id);
  return <section className="profile-comparisons" aria-label="Per-profile experiment comparisons">
    <h3>Inspect the same profile in both conditions</h3>
    <p>Compare individual trips within one repetition. Profile IDs refer to the same frozen personas and shopping lists across conditions.</p>
    <div className="evidence-selectors">
      <label>Comparison<select value={comparisonIndex} onChange={e=>setComparisonIndex(Number(e.target.value))}>{report.comparisons.map((c,i)=><option key={i} value={i}>{name(c.candidate)} versus {name(c.baseline)}</option>)}</select></label>
      <label>Repetition<select value={selectedRepetition??''} onChange={e=>setRepetition(Number(e.target.value))}>{repetitions.map(n=><option key={n} value={n}>{n}{comparison.complete_repetitions.includes(n)?' · complete pair':' · incomplete pair'}</option>)}</select></label>
    </div>
    {!own.length?<p>No recordings collected for this comparison.</p>:<>
      <p className="profile-coverage">Repetition {selectedRepetition} · {points.length} retained trips · {pairs.length} matched profiles. {pairs.length?'Unfinished shoppers within completed runs remain paired.':'This pair is incomplete. Retained attempts appear below; paired differences are unavailable.'} Repeated profiles are not independent samples; no profile-level significance test is applied.</p>
      <div className="profile-chart-grid">
        <figure className="profile-chart"><figcaption><h4>Outcome versus effort</h4><p>Successful moves versus requested products actually paid for.</p></figcaption>
          <div className="profile-legend"><span className="profile-baseline">○ {name(comparison.baseline)}</span><span className="profile-candidate">■ {name(comparison.candidate)}</span><span>× interrupted run</span></div>
          <p className="profile-point-readout" aria-live="polite">{selectedProfile}: {selected.map(p=>`${name(p.run)} — ${p.metrics.mean_successful_moves} moves, ${format(p.metrics.purchased_unit_fulfillment,'rate')} purchased`).join('; ')}</p>
          <div className="profile-plot-scroll"><svg viewBox="0 0 390 300" aria-label="Trip movement and paid-list fulfillment. Select a point or use the profile selector for exact values.">
            {[0,.25,.5,.75,1].map(n=><g key={n}><line className="profile-grid" x1="60" x2="360" y1={y(n)} y2={y(n)}/><text x="51" y={y(n)+4} textAnchor="end">{n*100}%</text></g>)}
            <line className="profile-axis" x1="60" y1="45" x2="60" y2="245"/><line className="profile-axis" x1="60" y1="245" x2="360" y2="245"/>
            {[0,xMax/2,xMax].map(n=><text key={n} x={x(n)} y="265" textAnchor="middle">{n}</text>)}
            <text x="210" y="290" textAnchor="middle">Successful moves</text><text x="60" y="23">Paid-list fulfillment</text>
            {points.map(p=>{const cx=x(p.metrics.mean_successful_moves),cy=y(p.metrics.purchased_unit_fulfillment),active=p.profile_id===selectedProfile;
              const label=`${p.profile_id}, ${name(p.run)}, ${p.metrics.mean_successful_moves} moves, ${format(p.metrics.purchased_unit_fulfillment,'rate')} purchased${p.run.status!=='completed'?', interrupted run':''}`;
              return <g key={`${p.run.run_id}:${p.profile_id}`} role="button" tabIndex={0} aria-label={label} aria-pressed={active} className={`profile-point profile-${p.side}${active?' is-selected':''}`} onMouseEnter={()=>select(p.profile_id)} onFocus={()=>select(p.profile_id)} onClick={()=>select(p.profile_id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(p.profile_id);}}}>
                <circle className="profile-hit" cx={cx} cy={cy} r="10"/>
                {p.run.status!=='completed'?<path d={`M${cx-5},${cy-5}l10,10m-10,0l10,-10`}/>:p.side==='baseline'?<circle cx={cx} cy={cy} r={active?6:4}/>:<rect x={cx-(active?6:4)} y={cy-(active?6:4)} width={active?12:8} height={active?12:8}/>}
              </g>;})}
          </svg></div>
          <p>All retained attempts are shown, including interrupted trips with unpaid carts. Points can overlap; use the profile selector below to inspect each one.</p>
        </figure>
        <figure className="profile-chart"><figcaption><h4>Paired effort difference</h4><p>{name(comparison.candidate)} minus {name(comparison.baseline)}.</p></figcaption>
          <label className="profile-measure">Measure<select value={effort} onChange={e=>setEffort(e.target.value as typeof effort)}><option value="mean_successful_moves">Successful moves</option><option value="model_requests">Submitted API requests</option></select></label>
          {!pairs.length?<p role="status">No complete repetition pair. No paired effect is estimated.</p>:<div className="profile-plot-scroll"><svg viewBox={`0 0 390 ${pairHeight}`} aria-label="Per-profile paired effort differences. Negative values mean fewer moves or requests in the candidate condition.">
            <line className="profile-axis" x1="240" x2="240" y1="15" y2={pairHeight-35}/>
            {[-maxDelta,0,maxDelta].map(n=><text key={n} x={240+n/maxDelta*100} y={pairHeight-12} textAnchor="middle">{n>0?'+':''}{n}</text>)}
            {pairs.map((p,i)=>{const value=p.difference[effort],width=Math.abs(value??0)/maxDelta*100,cy=28+i*28;return <g key={p.profile_id}>
              <text x="72" y={cy+4} textAnchor="end">{p.profile_id}</text>
              {value===null?<text x="145" y={cy+4}>Unknown</text>:<><rect className="profile-delta" x={value<0?240-width:240} y={cy-7} width={Math.max(width,1)} height="14"/><text x="95" y={cy+4}>{value>0?'+':''}{value}</text></>}
            </g>;})}
          </svg></div>}
          <p>Negative = fewer {effort==='model_requests'?'submitted requests':'successful moves'} in the candidate. Check fulfillment alongside effort; a shorter unfinished trip is not an improvement.</p>
        </figure>
      </div>
      <div className="profile-inspector" aria-live="polite">
        <label>Inspect profile<select value={selectedProfile??''} onChange={e=>select(e.target.value)}>{profiles.map(id=><option key={id}>{id}</option>)}</select></label>
        <p>{selectedProfile} · repetition {selectedRepetition}. Cost is the estimated API charge for this attempted trip, including failed requests; unknown charges stay unknown.</p>
        <div className="report-table"><table><thead><tr><th>Measure</th>{selected.map(p=><th key={p.run.run_id}>{name(p.run)}<small>{p.run.status==='completed'?'Completed run':'Interrupted run'} · {p.metrics.checkout_completion?'Checked out':'Unfinished'}</small></th>)}</tr></thead><tbody>{fields.map(([key,label,unit])=><tr key={key}><th>{label}</th>{selected.map(p=><td key={p.run.run_id}>{format(p.metrics[key],unit)}{key==='purchased_unit_fulfillment'&&<small>{p.purchased_products}/{p.requested_products} requested products paid</small>}</td>)}</tr>)}</tbody></table></div>
        <p>{selected.map(p=><a key={p.run.run_id} href={`/replays/${p.run.run_id}.source.jsonl`} download>{name(p.run)} recording</a>)}</p>
      </div>
      <details className="evidence-details"><summary>All paired profile values · repetition {selectedRepetition}</summary>
        {!pairs.length?<p>No complete pair for this repetition.</p>:<div className="report-table"><table><thead><tr><th>Profile</th>{fields.map(([key,label])=><th key={key}>{label}<small>Baseline → candidate (difference)</small></th>)}</tr></thead><tbody>{pairs.map(p=><tr key={p.profile_id}><th>{p.profile_id}</th>{fields.map(([key,,unit])=><td key={key}>{format(p.baseline[key as keyof ProfileMetrics],unit)} → {format(p.candidate[key],unit)}<small>{format(p.difference[key],unit,true)}</small></td>)}</tr>)}</tbody></table></div>}
      </details>
    </>}
  </section>;
}
