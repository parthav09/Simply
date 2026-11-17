'use client';

import Link from 'next/link';
import { memo, useEffect, useId, useMemo, useState, type CSSProperties } from 'react';
import { frameAt, shopperHistory, type CatalogEntry, type ReplayData } from '../lib/replay';
import { Icon } from './Icons';
import RecordedStoreMap from './RecordedStoreMap';
import MapViewport from './MapViewport';
import {loadCatalog, loadRecording} from '../lib/recordings';
import {impulseBuys, isImpulseEvent, isPlanned, money, offListUnits, totalOffListUnits} from '../lib/impulse';
import {CELL_SIZE} from '../lib/map-items';
import {productEmoji} from './map-theme';

const dollars=(v:number|null|undefined)=>v==null?'Unknown':`$${(v/100).toFixed(2)}`;
const phaseName=(phase:string)=>({BrowsingState:'Shopping',CheckoutState:'At checkout',FinishedState:'Checked out'}[phase]??phase);
const layoutName=(id:string)=>({costco_back_anchor:'A · Anchor loop',neighborhood_express:'B · Express essentials',back_destination:'C · Back destinations'}[id]??id);
const actionName=(name:string)=>name.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());

/** Displays one recorded run (by catalogue id) or a live Python stream. Display state only. */
function ReplayWorkspace({live,runId,shopperId}:{live?:{data:ReplayData;connection:string;controlStatus?:string;preview?:boolean};runId?:string;shopperId?:string}) {
  const [recordedData,setData]=useState<ReplayData|null>(null);
  const [entry,setEntry]=useState<CatalogEntry|null>(null);
  const data=live?live.data:recordedData;
  const isPreview=live?.preview===true;
  const [error,setError]=useState('');
  const [replayCursor,setCursor]=useState(0);
  const cursor=live?(data?.events.length??0):replayCursor;
  const [playing,setPlaying]=useState(false);
  const [speed,setSpeed]=useState(2);
  const [selected,setSelected]=useState('');
  const [filter,setFilter]=useState('');
  const heat=false,impulseLayer=true,trail=true;
  const [zoom,setZoom]=useState(1);
  const [reload,setReload]=useState(0);
  const uid=useId();
  const isLive=!!live;
  useEffect(()=>{
    if(isLive||!runId)return;
    let cancelled=false;
    loadCatalog(reload>0).then(async index=>{
      const entry=index.runs.find(run=>run.run_id===runId);
      if(!entry)throw new Error('This recording is not in the published catalogue');
      const run=await loadRecording(entry);
      if(cancelled)return;
      setCursor(0);setPlaying(false);setFilter('');setZoom(1);setEntry(entry);setData(run);
      setSelected(run.shoppers.find(s=>s.id===shopperId)?.id??run.shoppers[0].id);
    }).catch(cause=>{if(!cancelled)setError(cause.message);});
    return()=>{cancelled=true;};
  },[reload,isLive,runId,shopperId]);
  const activePlaying=!live&&!!data&&playing&&cursor<data.events.length;
  useEffect(()=>{
    if(!activePlaying||!data)return;
    const id=window.setInterval(()=>setCursor(n=>Math.min(n+1,data.events.length)),480/speed);
    return ()=>window.clearInterval(id);
  },[activePlaying,data,speed]);
  const frame=useMemo(()=>data?frameAt(data,cursor):null,[data,cursor]);
  const seek=(n:number)=>{if(live)return;setPlaying(false);setCursor(n);};
  const togglePlayback=()=>{if(!data||data.events.length===0)return;if(cursor===data.events.length)setCursor(0);setPlaying(!activePlaying);};
  useEffect(()=>{
    if(live||!data)return;
    const onKey=(e:KeyboardEvent)=>{
      const target=e.target as HTMLElement;
      if(target.closest('.map-viewport,input,select,textarea,button,a,summary,[role="tab"],[contenteditable="true"]')||e.metaKey||e.ctrlKey||e.altKey)return;
      if(e.code==='Space'){e.preventDefault();if(data.events.length>0){setPlaying(p=>!p||cursor===data.events.length);if(cursor===data.events.length)setCursor(0);}}
      if(e.code==='ArrowRight'||e.code==='ArrowLeft'){e.preventDefault();setPlaying(false);setCursor(n=>Math.max(0,Math.min(data.events.length,n+(e.code==='ArrowRight'?1:-1))));}
    };
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[data,cursor,live]);
  if(error)return <section className="replay-empty" role="alert"><span className="empty-icon"><Icon name="info" size={25}/></span><h2>Recording unavailable</h2><p>{error}. The original recording is required to show this journey.</p><button className="product-primary" onClick={()=>{setError('');setReload(n=>n+1);}}>Retry recording <Icon name="reset" size={16}/></button><Link href="/evaluation" className="text-link">See results <Icon name="arrow" size={16}/></Link></section>;
  if(!data||!frame)return <section className="replay-empty" role="status" aria-busy="true"><span className="empty-icon"><Icon name="map" size={26}/></span><h2>Opening the recording…</h2><p>Loading the saved trip and verifying its recording.</p></section>;
  const shopper=data.shoppers.find(s=>s.id===selected)??data.shoppers[0];
  const state=frame.states[shopper.id];
  const metric=frame.summary.shoppers.find(s=>s.agent_id===shopper.id)!;
  const history=[...shopperHistory(data,cursor,shopper.id)].reverse();
  const counts:Record<string,number>={};state.cart.forEach(i=>counts[i.product_id]=(counts[i.product_id]??0)+i.quantity);
  const currentEvent=data.events[cursor-1];
  const selectShopper=(id:string)=>{setSelected(id);if(filter)setFilter(id);};
  // Impulse lens: filters recorded events; totals shown come from Python's off_list_units.
  const allImpulses=impulseBuys(data,cursor);
  const visibleImpulses=filter?allImpulses.filter(i=>i.shopperId===filter):allImpulses;
  const marks=new Map<string,number>();for(const i of visibleImpulses)marks.set(i.productId,(marks.get(i.productId)??0)+1);
  const impulseTotal=totalOffListUnits(frame.summary);
  const currentImpulse=!!currentEvent&&isImpulseEvent(data,currentEvent);
  const jump=(shopperId:string,sequence:number)=>{selectShopper(shopperId);seek(sequence);};
  const tendency=typeof shopper.persona.impulse_buy_probability==='number'?Math.round(shopper.persona.impulse_buy_probability*100):null;
  const priceOf=(id:string)=>data.catalogue.find(p=>p.id===id)?.price;
  const cartSorted=[...state.cart].sort((a,b)=>Number(isPlanned(data,shopper.id,b.product_id))-Number(isPlanned(data,shopper.id,a.product_id)));
  const shopperImpulses=allImpulses.filter(i=>i.shopperId===shopper.id);
  return <section className={`recorded-lab ${live?'is-live':''} ${isPreview?'is-preview':''}`} aria-label={live?"Live shopper lab":"Recorded shopper lab"}>
    {!live&&data.source.status!=='completed'&&<p className="lab-note partial-note" role="status"><span className="state-tag warning">Incomplete</span>This recording stopped after {data.events.length} decisions{data.summary.finished_count===0?', before anyone checked out':` with ${data.summary.finished_count} of ${data.shoppers.length} shoppers checked out`}. It is not comparable with a finished trip.</p>}
    {!isPreview&&!['openai','gemini','openrouter','local_mps'].includes(data.source.provider)&&<p className="lab-note">Offline test fixture · scripted actions, not a model run.</p>}

    <div className="replay-score" aria-label="Run totals">
      <Stat tone="impulse" label="Impulse buys" value={impulseTotal==null?'—':String(impulseTotal)} hint="Units picked up that were not on the shopper’s list (Python off_list_units)"/>
      <Stat label="Checked out" value={`${frame.summary.finished_count}`} suffix={`/ ${frame.summary.shopper_count}`} hint="Completed trips"/>
      <Stat label="List fulfilled" value={`${(frame.summary.mean_list_completion*100).toFixed(0)}%`} hint="Mean across all shoppers"/>
    </div>

    <div className="replay-body"><div className="replay-main-column"><div className="replay-map-panel">
      <div className="replay-map-heading">
        <div className="map-title"><h3>{layoutName(data.layout.id)} <span>{isPreview?'Preview':live?`Live · ${data.source.run_id.slice(0,8)}`:entry?entry.run_id.slice(0,8):''}</span></h3></div>
      </div>
      <MapViewport zoom={zoom} width={data.layout.width*CELL_SIZE+32} height={data.layout.height*CELL_SIZE+36}><RecordedStoreMap data={data} states={frame.states} summary={frame.summary} cursor={cursor} selected={shopper.id} filter={filter} trail={trail} heat={heat} onSelect={selectShopper} focusProductId={currentEvent?.action?.product_id||undefined} impulseMarks={impulseLayer?marks:undefined} impulseFlash={currentImpulse?currentEvent?.action?.product_id:undefined}/></MapViewport>
      <div className="map-bottom"><div className="map-legend"><span className="legend-entrance">Entrance</span><span className="legend-checkout">Checkout</span><span className="impulse-legend">Impulse pick-up</span></div></div>
      {live&&!isPreview?<div className="replay-player" role="status"><div className="player-topline"><span>{live.connection==='connected'?(live.controlStatus==='paused'?'Paused · no model requests':live.controlStatus==='pausing'?'Pausing after the current round':live.controlStatus==='stopping'?'Stopping · saving confirmed actions':live.controlStatus==='waiting_for_model'?'Waiting for the next model decision':'Following confirmed Python actions'):live.connection==='ended'?'Python run ended':live.connection==='reconnecting'?'Reconnecting to Python':'Connecting to Python'}</span><span>{`Committed event ${cursor}`}</span></div></div>:!live?<div className="replay-player"><div className="player-topline"><span><span className={`status-dot ${activePlaying?'is-playing':''}`}/>{activePlaying?'Playing':cursor===data.events.length?'End of recording':cursor===0?'Ready':'Paused'}</span><label htmlFor={`${uid}-timeline`}>Decision <b>{cursor}</b> / {data.events.length}</label></div><div className="timeline-wrap"><input id={`${uid}-timeline`} aria-label="Replay timeline" type="range" min={0} max={data.events.length} value={cursor} disabled={data.events.length===0} style={{'--progress':`${data.events.length?cursor/data.events.length*100:0}%`} as CSSProperties} onChange={e=>seek(Number(e.target.value))}/><div className="timeline-ticks" aria-hidden="true">{impulseBuys(data,data.events.length).filter(i=>!filter||i.shopperId===filter).map(i=><i key={i.event.sequence} style={{left:`${i.event.sequence/data.events.length*100}%`}} className={i.event.sequence<=cursor?'is-past':''}/>)}</div></div><div className="player-controls"><div className="transport-controls"><button aria-label="Previous event" title="Previous event (←)" disabled={cursor===0} onClick={()=>seek(Math.max(0,cursor-1))}><Icon name="back" size={16}/></button><button className="play-button" onClick={togglePlayback} disabled={data.events.length===0} aria-label={activePlaying?'Pause replay':cursor===data.events.length?'Replay recording':'Play recorded run'}><Icon name={activePlaying?'pause':'play'} size={17}/><span>{activePlaying?'Pause':cursor===data.events.length?'Replay':'Play'}</span></button><button aria-label="Next event" title="Next event (→)" disabled={cursor>=data.events.length} onClick={()=>seek(Math.min(data.events.length,cursor+1))}><Icon name="next" size={16}/></button></div><div className="speed-control" role="group" aria-label="Playback speed">{[1,2,4].map(n=><button key={n} aria-pressed={speed===n} onClick={()=>setSpeed(n)}>{n}×</button>)}</div></div></div>:null}
    </div>
    {!isPreview&&<section className="impulse-log" aria-label="Impulse buys in this run">
      <header><h3><span className="impulse-badge">{visibleImpulses.length}</span>Impulse buys {filter?`· ${shopper.name.split(' ')[0]}`:'so far'}</h3></header>
      {visibleImpulses.length?<ol>{[...visibleImpulses].reverse().map(i=><li key={i.event.sequence}><button onClick={()=>jump(i.shopperId,i.event.sequence)} className={i.event.sequence===cursor?'is-current':''}>
        <span className="item-emoji" aria-hidden="true">{productEmoji(i.product??i.productId)}</span>
        <span className="impulse-what"><strong>{i.product?.name??i.productId}</strong><small>{i.shopperName} · {i.product?.department??'Shelf'} · event {i.event.sequence}</small></span>
        <span className="impulse-price">{money(i.product?.price)}</span>
        <q>{i.reason}</q>
      </button></li>)}</ol>:<p className="impulse-empty">{cursor===data.events.length||live?'No impulse buys recorded in this run. Every item picked up was on someone’s list.':'None yet. Amber ticks on the timeline mark where they happen.'}</p>}
    </section>}
    </div>
    <aside className="replay-inspector" aria-label="Shopper inspector">
      <div className="shopper-roster" aria-label="Recorded shoppers">
        <div className="roster-heading">
          <h3>Shoppers <span>{data.shoppers.length}</span></h3>
        </div>
        <div className="shopper-cards" role="listbox" aria-label="Shoppers">{data.shoppers.map(s=>{const n=offListUnits(frame.summary,s.id)??0;return <button key={s.id} role="option" aria-selected={s.id===shopper.id} className={`shopper-card ${s.id===shopper.id?'selected':''}`} onClick={()=>selectShopper(s.id)} title={phaseName(frame.states[s.id].phase)}><span><i className={`phase-dot phase-${frame.states[s.id].phase.replace('State','').toLowerCase()}`} aria-hidden="true"/>{s.name}</span>{n>0&&<span className="impulse-badge" aria-label={`${n} impulse ${n===1?'buy':'buys'}`}>{n}</span>}</button>;})}</div>
      </div>
      <div className="shopper-identity">
        <span className="avatar avatar-large"><span className="shopper-sprite" style={{backgroundPosition:`0px -${shopper.sprite_index*4*40}px`}}/></span>
        <div>
          <div className="inspector-heading"><span className="shopper-name">{shopper.name}</span><span className="state-tag">{isPreview?'Ready':phaseName(state.phase)}</span></div>
          <p>{shopper.style}{tendency!=null&&<> · <span className="tendency" title="Supplied profile input, not a measured outcome">{tendency}% impulse tendency</span></>}</p>
        </div>
      </div>
      {!isPreview&&<NowCard data={data} shopperName={shopper.name.split(' ')[0]} latest={history[0]}/>}
      <div className="inspector-content">
        <div className="basket-overview"><span>Basket / budget</span><p><strong>{dollars(state.basket_cents)}</strong><span>/ {dollars(shopper.budget_cents)}</span></p><div className={`budget-meter ${metric.overshoot_cents!=null&&metric.overshoot_cents>0?'over-budget':''}`}><i style={{width:`${Math.min(100,shopper.budget_cents>0?(state.basket_cents??0)/shopper.budget_cents*100:0)}%`}}/></div>{metric.overshoot_cents!=null&&metric.overshoot_cents>0&&<small className="budget-warning">{dollars(metric.overshoot_cents)} over budget</small>}</div>
        <div className="inspector-section-title"><h4>In the basket</h4><span>{shopperImpulses.length?<span className="tag tag-impulse">{offListUnits(frame.summary,shopper.id)??shopperImpulses.length} impulse</span>:cartSorted.length?'All planned':''}</span></div>
        {cartSorted.length?<ul className="basket-list">{cartSorted.map((i,n)=>{const planned=isPlanned(data,shopper.id,i.product_id);const why=planned?undefined:shopperImpulses.find(x=>x.productId===i.product_id);return <li key={n} className={planned?'':'is-impulse'}>
          <div className="basket-line"><span><span className="item-emoji" aria-hidden="true">{productEmoji(data.catalogue.find(product=>product.id===i.product_id)??i.name)}</span>{i.name}</span><span className={`tag ${planned?'tag-planned':'tag-impulse'}`}>{planned?'On list':'Impulse'}</span><b>{money(priceOf(i.product_id))}</b></div>
          {why&&<button className="basket-why" onClick={()=>seek(why.event.sequence)}>“{why.reason}” <span>event {why.event.sequence}</span></button>}
        </li>;})}</ul>:<div className="basket-empty"><Icon name="bag" size={23}/><p>Nothing in the basket yet.<span>Step through to see what changes.</span></p></div>}
        <div className="inspector-section-title"><h4>Shopping list</h4><span>{(metric.list_completion*100).toFixed(0)}% fulfilled</span></div>
        <ul className="shopping-list">{shopper.list.map((i,n)=><li key={`${i.product_id}-${n}`}><span className={`list-check ${(counts[i.product_id]??0)>=i.quantity?'fulfilled':''}`} aria-hidden="true">{(counts[i.product_id]??0)>=i.quantity&&<Icon name="check" size={12}/>}</span><div><strong><span className="item-emoji" aria-hidden="true">{productEmoji(data.catalogue.find(product=>product.id===i.product_id)??i.product_name)}</span>{i.product_name}</strong><small>{i.priority.replaceAll('_',' ')}</small></div><span className="quantity">{counts[i.product_id]??0}<span>/{i.quantity}</span></span></li>)}</ul>
      </div>
    </aside></div>
    {!isPreview&&!live&&entry&&<footer className="replay-evidence"><a href={entry.evidence_url} download><Icon name="download" size={14}/> Original recording</a><Link href="/evaluation">Method & limits <Icon name="arrow" size={14}/></Link></footer>}
  </section>;
}
function NowCard({data,shopperName,latest}:{data:ReplayData;shopperName:string;latest?:ReplayData['events'][number]}){
  const product=latest?.action?.product_id?data.catalogue.find(p=>p.id===latest.action?.product_id):undefined;
  const impulse=!!latest&&isImpulseEvent(data,latest);
  const step=latest?.action?.step;
  const past:Record<string,string>={grab:'picked up',checkout:'paid at checkout',remove:'put back',move_up:'walked up',move_down:'walked down',move_left:'walked left',move_right:'walked right'};
  const base:Record<string,string>={grab:'pick up',checkout:'pay at checkout',remove:'put back',move_up:'walk up',move_down:'walk down',move_left:'walk left',move_right:'walk right'};
  const what=!latest?'':!step?'returned no valid decision':`${latest.outcome==='applied'?past[step]??actionName(step):`tried to ${base[step]??step} (rejected)`}${product?` ${product.name}`:''}`;
  return <div className={`now-card ${impulse?'is-impulse':''}`}>
    <span className="now-label">{latest?`Latest · decision ${latest.sequence}`:'Not started yet'}</span>
    <p>{latest?<><strong>{shopperName}</strong> {what}{impulse&&<span className="tag tag-impulse">Impulse</span>}</>:<>Press play to watch <strong>{shopperName}</strong> shop.</>}</p>
    {latest&&(latest.failure??latest.action?.reason)&&<q>{latest.failure??latest.action?.reason}</q>}
    
  </div>;
}
function Stat({label,value,suffix,hint,tone}:{label:string;value:string;suffix?:string;hint:string;tone?:'impulse'}){return <div className={`stat-card ${tone==='impulse'?'is-impulse':''}`} title={hint}><span>{label}</span><strong>{value}{suffix&&<small>{suffix}</small>}</strong></div>;}

export default memo(ReplayWorkspace,(previous,next)=>previous.runId===next.runId&&previous.shopperId===next.shopperId
  &&previous.live?.data===next.live?.data&&previous.live?.connection===next.live?.connection
  &&previous.live?.controlStatus===next.live?.controlStatus&&previous.live?.preview===next.live?.preview);
