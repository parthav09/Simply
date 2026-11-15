import {formatHistoryMetric as format} from '../lib/evidence';
import type {Dashboard,DashboardModel,Measure} from '../lib/dashboard';

/** Plain-language chart panels. Display only: every number is Python's exported metric. */
const panels:{id:string;title:string;question:string;better:'higher'|'lower'}[]=[
  {id:'checkout_completion',title:'Finished the trip',question:'How many shoppers made it to checkout?',better:'higher'},
  {id:'purchased_unit_fulfillment',title:'Got what was on the list',question:'How much of the shopping list was actually bought?',better:'higher'},
  {id:'moves_per_trip',title:'Steps walked',question:'How far did the average shopper wander?',better:'lower'},
  {id:'estimated_cost_per_run_usd',title:'Cost to run',question:'What did one 10-shopper run cost in model usage?',better:'lower'},
];

function Panel({panel,measure,models,layouts}:{panel:typeof panels[number];measure:Measure;models:DashboardModel[];layouts:Dashboard['layouts']}){
  const values=models.flatMap(m=>layouts.map(l=>m.cells[l.id]?.metrics[panel.id])).filter((v):v is number=>typeof v==='number');
  const axis=measure.unit==='rate'?1:Math.max(...values,Number.EPSILON);
  return <figure className="chart-panel">
    <figcaption><strong>{panel.title}</strong><span>{panel.question}</span><em className={`chart-better is-${panel.better}`}>{panel.better==='higher'?'Higher is better':'Lower is better'}</em></figcaption>
    <div className="chart-rows" role="list">
      {models.map(model=><div className="chart-row" role="listitem" key={model.id}>
        <span className="chart-model">{model.label}</span>
        {layouts.map((layout,i)=>{
          const cell=model.cells[layout.id];const value=cell?.status==='recorded'?cell.metrics[panel.id]:null;
          const interrupted=(cell?.stopped_runs??0)>0;
          const text=(cell?.status!=='recorded'?'N/A':format(value??null,measure.unit))+(interrupted?' *':'');
          const width=typeof value==='number'?Math.max(value/axis*100,value>0?1.5:0):0;
          return <div className="chart-line" key={layout.id} title={`${model.label} · ${layout.label}: ${text}`}>
            <span className="chart-layout-tag">{i===0?'A':'B'}</span>
            <span className="chart-track"><span className={`chart-bar is-${i===0?'a':'b'}`} style={{width:`${width}%`}}/></span>
            <span className="chart-value">{text}</span>
          </div>;
        })}
      </div>)}
    </div>
  </figure>;
}

export default function EvidenceCharts({data,models}:{data:Dashboard;models:DashboardModel[]}){
  const shown=models.filter(m=>Object.values(m.cells).some(c=>c.status==='recorded'));
  const anyInterrupted=shown.some(m=>Object.values(m.cells).some(c=>c.stopped_runs>0));
  if(!shown.length)return null;
  return <section className="evidence-charts" aria-label="Results at a glance">
    <div className="evidence-charts-head">
      <div><h3>Results at a glance</h3><p>Each pair of bars compares one model in the two store layouts. Exact counts are in the table below.</p></div>
      <ul className="chart-legend" aria-label="Layout colors">{data.layouts.map((l,i)=><li key={l.id}><i className={`is-${i===0?'a':'b'}`}/><strong>{`Layout ${i===0?'A':'B'}`}</strong> {l.description}</li>)}</ul>
    </div>
    <div className="chart-grid">{panels.map(panel=>{const measure=data.measures.find(m=>m.id===panel.id);return measure?<Panel key={panel.id} panel={panel} measure={measure} models={shown} layouts={data.layouts}/>:null;})}</div>
    {anyInterrupted&&<p className="chart-note">* The run was interrupted before every shopper finished, so its numbers are partial and not comparable with a completed run.</p>}
  </section>;
}
