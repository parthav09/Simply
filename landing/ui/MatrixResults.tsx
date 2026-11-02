'use client';

import {useEffect,useState} from 'react';
import {loadCatalog} from '../lib/recordings';
import {decodeMatrix,type MatrixReport} from '../lib/matrix';
import {formatHistoryMetric as format} from '../lib/evidence';
import type {Catalog,MatrixEntry} from '../lib/replay';
import ProfileComparisons from './ProfileComparisons';

const name=(row:{model:string;layout_id:string})=>`${row.model==='gpt-6-luna'?'Luna':'Terra'} · Layout ${row.layout_id==='costco_back_anchor'?'A':'B'}`;
const measures=[['checkout_completion','Checkout completion','rate'],['purchased_unit_fulfillment','Shopping list purchased','rate'],['mean_successful_moves','Moves per shopper','number'],['cost_per_completed_trip_usd','API cost per checkout','usd'],['assisted_request_fraction','Requests with an adjusted action','rate']] as const;

export default function MatrixResults(){
  const [result,setResult]=useState<{report:MatrixReport;entry:NonNullable<Catalog['matrix']>}|null>(null);
  const [error,setError]=useState('');
  const [available,setAvailable]=useState<MatrixEntry[]>([]);
  const [selectedUrl,setSelectedUrl]=useState('');
  useEffect(()=>{let active=true;loadCatalog().then(async catalog=>{
    if(!catalog.matrix)return;
    const entries=catalog.matrices?.length?catalog.matrices:[catalog.matrix];
    const entry=entries.find(e=>e.url===selectedUrl)??catalog.matrix;
    if(active){setAvailable(entries);setError('');}
    const response=await fetch(entry.url,{cache:'no-store'});
    if(!response.ok)throw new Error('Study results unavailable');
    const report=await decodeMatrix(await response.text(),entry);
    if(active)setResult({report,entry});
  }).catch(cause=>{if(active)setError(cause instanceof Error?cause.message:'Study results unavailable');});return()=>{active=false;};},[selectedUrl]);
  if(error)return <section className="evidence-notice is-warning" role="alert"><p>{error}. The verified study is needed to show these results.</p></section>;
  if(!result)return null;
  const {report,entry}=result;
  return <section aria-label="Controlled layout and model results" className="matrix-results">
    {available.length>1&&<label className="profile-measure">Recorded study<select value={entry.url} onChange={e=>setSelectedUrl(e.target.value)}>{available.map(e=><option key={e.url} value={e.url}>{e.title??e.url}</option>)}</select></label>}
    <p className="eyebrow">Controlled experiment · {report.status==='completed'?'Complete':'Incomplete'}</p>
    <h2>Two layouts. Two models. The same shoppers.</h2>
    <p>{report.repetitions} repetitions planned with {report.cohort_size} fixed profiles in each condition. Both models use the same navigation assistance. These are simulated trips, not independent customers.</p>
    <p>{report.provider==='openrouter'?'OpenRouter · pinned OpenAI endpoint · dated model checkpoints · fallbacks disabled. Reported charges and frozen-price estimates are separate.':'Direct OpenAI study · historical transport and pricing preserved.'}</p>
    {report.pending_models&&<details className="evidence-details"><summary>Qwen baseline & fine-tuned comparison · pending</summary>{report.pending_models.map(m=><p key={m.model}><strong>{m.model}</strong>: {m.reason}</p>)}</details>}
    {report.status==='incomplete'&&<div className="evidence-notice is-warning" role="status"><p>{report.collection.summary}</p></div>}
    <div className="report-table"><table><thead><tr><th>Measure</th>{report.conditions.map(row=><th key={name(row)}>{name(row)}<small>{row.recorded_runs} runs · {row.finished}/{row.trips} checked out</small>{row.collection_note&&<small>{row.collection_note}</small>}</th>)}</tr></thead><tbody>{measures.map(([key,label,unit])=><tr key={key}><th>{label}</th>{report.conditions.map(row=><td key={name(row)}>{format(row.metrics[key],unit)}</td>)}</tr>)}</tbody></table></div>
    {report.provider==='openrouter'&&<div className="report-table"><table><thead><tr><th>OpenRouter billing</th>{report.conditions.map(row=><th key={name(row)}>{name(row)}</th>)}</tr></thead><tbody><tr><th>Reported charge per checkout</th>{report.conditions.map(row=><td key={name(row)}>{format(row.metrics.provider_reported_cost_per_checkout_usd??null,'usd')}</td>)}</tr></tbody></table></div>}
    <h3>What changed</h3><p>Each difference compares completed repetition blocks. A 95% bootstrap interval appears after at least five complete pairs. Rate changes use percentage points (pp).</p>
    <div className="report-table"><table><thead><tr><th>Comparison − baseline</th>{measures.slice(0,3).map(([key,label])=><th key={key}>{label}</th>)}</tr></thead><tbody>{report.comparisons.map(row=><tr key={`${name(row.candidate)}-${name(row.baseline)}`}><th>{name(row.candidate)} − {name(row.baseline)}</th>{measures.slice(0,3).map(([key,,unit])=>{const metric=row.metrics[key];return <td key={key}>{format(metric.difference,unit,true)}<small>{metric.ci95?metric.ci95.map(n=>format(n,unit,true)).join(' to '):'Insufficient complete pairs'} · {metric.blocks} pairs</small></td>;})}</tr>)}</tbody></table></div>
    <details className="evidence-details"><summary>Scope & verification</summary><ul>{report.limitations.map(text=><li key={text}>{text}</li>)}</ul><p><a href={entry.url.replace(/\.json$/,'.md')} download>Download case study</a> · <a href={entry.url} download>Download all measured results</a> · <a href={entry.protocol_url} download>Download frozen experiment plan</a></p><p>Original recordings and per-run diagnostics are available below. No unfinished shopper is removed from the arm averages.</p><p>Experiment <code>{report.study_id}</code> · protocol <code>{report.protocol_sha256}</code></p></details>
    <ProfileComparisons report={report}/>
  </section>;
}
