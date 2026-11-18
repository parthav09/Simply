'use client';

import {formatHistoryMetric as format} from '../lib/evidence';
import type {Dashboard,DashboardModel} from '../lib/dashboard';
import {useDashboardData} from './useDashboardData';

/**
 * Cost against quality, one point per model and layout. Display only: every value is a metric
 * Python exported in the results dashboard. Position and shape are chart geometry, nothing more.
 * Models with no API charge sit in their own band: $0 on a log scale is meaningless, and their
 * GPU time was not metered, so they are not shown as free.
 */
const W=640,H=340,L=64,R=24,T=40,B=56,BAND=84,GAP=16;
const P0=L+BAND+GAP;
const X_MIN=0.03,X_MAX=1;
const logX=(v:number)=>P0+(Math.log(v/X_MIN)/Math.log(X_MAX/X_MIN))*(W-P0-R);
const linY=(v:number)=>T+(1-v)*(H-T-B);
const X_TICKS=[0.05,0.1,0.2,0.5,1];
const Y_TICKS=[0,0.25,0.5,0.75,1];
const BAND_X=L+BAND/2;
const FINE_TUNED='qwen2.5-7b-impulse-v3-cuda';

type Point={model:DashboardModel;layoutId:string;layoutIndex:number;cost:number|null;quality:number};

/** Provider-reported charge per finished trip; null when there is no API charge to report. */
function costOf(model:DashboardModel,layoutId:string){
  const cell=model.cells[layoutId];
  if(!cell||cell.status!=='recorded')return null;
  return cell.metrics.provider_reported_cost_per_checkout_usd??null;
}

function pointsFor(models:DashboardModel[],data:Dashboard):Point[]{
  return models.flatMap(model=>data.layouts.flatMap((layout,layoutIndex)=>{
    const cost=costOf(model,layout.id);const quality=model.cells[layout.id]?.metrics.purchased_unit_fulfillment;
    return typeof quality==='number'&&(cost===null||cost>0)?[{model,layoutId:layout.id,layoutIndex,cost,quality}]:[];
  }));
}

const shortName=(model:DashboardModel)=>model.id===FINE_TUNED?['Qwen2.5 7B','fine-tuned']:[model.label.split(' · ')[0]];
const where=(p:Point)=>`${p.model.label} · Layout ${p.layoutIndex===0?'A':'B'}: ${p.cost===null?'no API charge':`${format(p.cost,'usd')} per finished trip`}, ${format(p.quality,'rate')} of the list bought`;
const cx=(p:Point)=>p.cost===null?BAND_X+(p.layoutIndex===0?-13:13):logX(p.cost);

export default function CostQuality(){
  const {data,error}=useDashboardData();
  if(error)return <section className="results-extra" aria-label="Cost against quality"><p className="evidence-footnote" role="alert">{error}. No values have been substituted.</p></section>;
  if(!data)return <section className="results-extra" aria-label="Cost against quality"><p className="evidence-footnote" role="status">Loading verified recorded results…</p></section>;
  const view=data.views.find(v=>v.id===data.default_view)??data.views[0];
  const models=view.models.filter(m=>Object.values(m.cells).some(c=>c.status==='recorded'));
  const points=pointsFor(models,data);
  const plotted=models.filter(m=>points.some(p=>p.model.id===m.id));
  const noApi=plotted.filter(m=>points.filter(p=>p.model.id===m.id).every(p=>p.cost===null));
  const summary=plotted.map(m=>`${m.label}: ${points.filter(p=>p.model.id===m.id).map(p=>`Layout ${p.layoutIndex===0?'A':'B'} ${p.cost===null?'no API charge':`${format(p.cost,'usd')} per finished trip`}, ${format(p.quality,'rate')} of the list bought`).join('; ')}`).join('. ');
  return <section className="results-extra" aria-labelledby="cost-quality-title">
    <h2 id="cost-quality-title">Cost against quality</h2>
    <p className="evidence-footnote">How much each model cost per finished trip, and how much of the shopping list it bought. Up and to the left is better: more of the list for less money.</p>
    <figure className="cost-quality-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Scatter chart of cost per finished trip against share of list bought. ${summary}`}>
        {noApi.length>0&&<rect className="cq-band" x={L} y={T} width={BAND} height={H-T-B} rx={6}/>}
        {Y_TICKS.map(t=><g key={t}><line className="cq-grid" x1={L} x2={W-R} y1={linY(t)} y2={linY(t)}/><text className="cq-tick" x={L-8} y={linY(t)+4} textAnchor="end">{Math.round(t*100)}%</text></g>)}
        {X_TICKS.map(t=><g key={t}><line className="cq-grid" x1={logX(t)} x2={logX(t)} y1={T} y2={H-B}/><text className="cq-tick" x={logX(t)} y={H-B+18} textAnchor="middle">{`$${t}`}</text></g>)}
        {noApi.length>0&&<text className="cq-tick" x={BAND_X} y={H-B+18} textAnchor="middle">No API charge</text>}
        <text className="cq-axis" x={(P0+W-R)/2} y={H-8} textAnchor="middle">Cost per finished trip (log scale)</text>
        <text className="cq-axis" transform={`translate(16 ${(T+H-B)/2}) rotate(-90)`} textAnchor="middle">Share of the list bought</text>
        {plotted.map(model=>{
          const own=points.filter(p=>p.model.id===model.id).sort((a,b)=>cx(a)-cx(b));
          const mid=own.reduce((s,p)=>s+cx(p),0)/own.length;
          const top=Math.min(...own.map(p=>linY(p.quality)));
          const name=shortName(model);
          return <g key={model.id}>
            {own.length>1&&<line className="cq-link" x1={cx(own[0])} y1={linY(own[0].quality)} x2={cx(own[own.length-1])} y2={linY(own[own.length-1].quality)}/>}
            {own.map(p=>{const x=cx(p),y=linY(p.quality);
              return p.layoutIndex===0
                ?<circle key={p.layoutId} className="cq-point is-a" cx={x} cy={y} r={7}><title>{where(p)}</title></circle>
                :<rect key={p.layoutId} className="cq-point is-b" x={x-6.5} y={y-6.5} width={13} height={13} transform={`rotate(45 ${x} ${y})`}><title>{where(p)}</title></rect>;})}
            <text className="cq-label" x={mid} y={top-14-(name.length-1)*14} textAnchor="middle">{name.map((line,i)=><tspan key={line} x={mid} dy={i===0?0:14}>{line}</tspan>)}</text>
          </g>;})}
      </svg>
      <figcaption className="cq-legend"><span><i className="is-a"/> Layout A</span><span><i className="is-b"/> Layout B</span></figcaption>
    </figure>
    {noApi.length>0&&<p className="evidence-footnote">{noApi.map(m=>m.id===FINE_TUNED
      ?'Qwen2.5 7B fine-tuned has no API charge. It ran on a Colab A100 GPU covered by a Google AI Pro subscription, and GPU time was not metered per run. It sits in the “No API charge” band instead of at a cost on the scale: the GPU time is real, just not measured per trip.'
      :`${m.label} has no API charge. Its compute was not metered per run, so it is shown apart from the cost scale and is not free.`).join(' ')}</p>}
    <div className="report-table"><table aria-label="Cost and quality by model and layout"><thead><tr><th scope="col">Model</th><th scope="col">Layout</th><th scope="col">Cost per finished trip</th><th scope="col">List bought</th><th scope="col">Finished the trip</th><th scope="col">Invalid replies</th></tr></thead>
      <tbody>{models.flatMap(model=>data.layouts.map((layout,i)=>{
        const cell=model.cells[layout.id];const recorded=cell?.status==='recorded';
        const cost=costOf(model,layout.id);
        return <tr key={`${model.id}-${layout.id}`}>
          <th scope="row">{i===0?model.label:<span className="sr-only">{model.label}</span>}</th>
          <td>{i===0?'A':'B'}</td>
          <td>{!recorded?'N/A':cost===null?<>No API charge<small>GPU time not metered per run</small></>:format(cost,'usd')}</td>
          <td>{recorded?format(cell.metrics.purchased_unit_fulfillment,'rate'):'N/A'}</td>
          <td>{recorded?`${cell.finished}/${cell.trips}`:'N/A'}</td>
          <td>{recorded?format(cell.metrics.invalid_replies,'integer'):'N/A'}</td>
        </tr>;}))}</tbody></table></div>
    <ul className="evidence-footnote cost-quality-notes">
      <li>Cost is the provider-reported charge for the whole run divided by trips that reached checkout. A model that fails more trips looks more expensive per finished trip.</li>
      <li>The Qwen baseline is an earlier run under the older navigation assist, so compare it with care. It shows what a small untuned model costs and where it falls short.</li>
      <li>Ten simulated shoppers per run. These are recorded simulations, not measured human behaviour.</li>
    </ul>
  </section>;
}
