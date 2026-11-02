'use client';

import Link from 'next/link';
import { memo, useEffect, useId, useMemo, useRef, useState, type CSSProperties } from 'react';
import { frameAt, shopperHistory, type Catalog, type CatalogEntry, type ReplayData } from '../lib/replay';
import { Icon } from './Icons';
import RecordedStoreMap from './RecordedStoreMap';
import MapViewport from './MapViewport';
import {completedLayoutRecording, loadCatalog, loadRecording, preferredRecording} from '../lib/recordings';
import {CELL_SIZE} from '../lib/map-items';
import {productEmoji} from './map-theme';

const dollars=(v:number|null|undefined)=>v==null?'Unknown':`$${(v/100).toFixed(2)}`;
const phaseName=(phase:string)=>({BrowsingState:'Shopping',CheckoutState:'At checkout',FinishedState:'Checked out'}[phase]??phase);
const reasonName=(reason:string)=>({finished_checkout:'Checked out',turn_budget_exhausted:'Turn limit reached',global_round_limit:'Run limit reached',no_allowed_actions:'No legal actions',aborted:'Run stopped after an error',cancelled:'Stopped by user',budget_exhausted:'API spending limit reached',incomplete:'In progress at this event'}[reason]??reason.replaceAll('_',' '));
const layoutName=(id:string)=>({costco_back_anchor:'A · Anchor loop',neighborhood_express:'B · Express essentials',back_destination:'C · Back destinations'}[id]??id);
const layoutShort=(id:string)=>({costco_back_anchor:'Anchor',neighborhood_express:'Express',back_destination:'Back'}[id]??id);
const recordingLabel=(entry:CatalogEntry,duplicate:boolean)=>{
  const model=({'gpt-6-luna':'Luna','gpt-6.1-terra':'Terra'}[entry.model]??entry.model);
  const base=`${model} · ${layoutShort(entry.layout_id)} · ${entry.study?`Repeat ${entry.study.repetition}`:`${entry.shopper_count} shoppers`} · ${entry.status}`;
  if(!duplicate||entry.study)return base;
  const time=new Date(entry.recorded_at).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
  return `${base} · ${time}`;
};
const actionName=(name:string)=>name.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
type InspectorTab = 'overview' | 'decisions' | 'profile';

function ReplayWorkspace({compact=false,landing=false,live}:{compact?:boolean;landing?:boolean;live?:{data:ReplayData;connection:string;controlStatus?:string;preview?:boolean}}) {
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [entry,setEntry]=useState<CatalogEntry|null>(null);
  const [recordedData,setData]=useState<ReplayData|null>(null);
  const data=live?live.data:recordedData;
  const isPreview=live?.preview===true;
  const [error,setError]=useState('');
  const [replayCursor,setCursor]=useState(0);
  const cursor=live?(data?.events.length??0):replayCursor;
  const [playing,setPlaying]=useState(landing);
  const [visible,setVisible]=useState(false);
  const container=useRef<HTMLElement>(null);
  const [speed,setSpeed]=useState(1);
  const [selected,setSelected]=useState('');
  const [filter,setFilter]=useState('');
  const [heat,setHeat]=useState(false);
  const [trail,setTrail]=useState(true);
  const [tab,setTab]=useState<InspectorTab>('overview');
  const [zoom,setZoom]=useState(1);
  const [reload,setReload]=useState(0);
  const uid=useId();
  const Heading=compact?'h2':'h1';
  const isLive=!!live;
  useEffect(()=>{
    if(isLive)return;
    let cancelled=false;
    loadCatalog(reload>0).then(index=>{
      if(cancelled)return;
      const available=landing?{...index,runs:['costco_back_anchor','neighborhood_express'].flatMap(layout=>{
        const recording=completedLayoutRecording(index,layout);
        return recording?[recording]:[];
      })}:index;
      setCatalog(available);
      const first=landing?available.runs[0]:preferredRecording(available);
      if(first)setEntry(first);
    }).catch(error=>{if(!cancelled)setError(error.message);});
    return()=>{cancelled=true;};
  },[reload,isLive,landing]);
  useEffect(()=>{
    if(isLive||!entry)return;
    let cancelled=false;
    loadRecording(entry).then(run=>{
      if(!cancelled){setData(run);setSelected(run.shoppers[0].id);if(landing&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)setPlaying(false);}
    }).catch(error=>{if(!cancelled)setError(error.message);});
    return()=>{cancelled=true;};
  },[entry,reload,isLive,landing]);
  useEffect(()=>{
    if(!landing||!data||!container.current)return;
    const preference=window.matchMedia('(prefers-reduced-motion: reduce)');
    const reduceMotion=()=>{if(preference.matches)setPlaying(false);};
    let intersecting=false;
    const update=()=>setVisible(intersecting&&!document.hidden);
    const observer=new IntersectionObserver(([entry])=>{intersecting=entry.isIntersecting;update();},{threshold:.15});
    observer.observe(container.current);
    preference.addEventListener('change',reduceMotion);
    document.addEventListener('visibilitychange',update);
    return()=>{observer.disconnect();preference.removeEventListener('change',reduceMotion);document.removeEventListener('visibilitychange',update);};
  },[data,landing]);
  const activePlaying=!live&&!!data&&playing&&(!landing||visible)&&cursor<data.events.length;
  useEffect(()=>{
    if(!activePlaying||!data)return;
    const id=window.setInterval(()=>setCursor(n=>Math.min(n+1,data.events.length)),480/speed);
    return ()=>window.clearInterval(id);
  },[activePlaying,data,speed]);
  const frame=useMemo(()=>data?frameAt(data,cursor):null,[data,cursor]);
  const seek=(n:number)=>{if(live)return;setPlaying(false);setCursor(n);};
  const togglePlayback=()=>{if(!data||data.events.length===0)return;if(cursor===data.events.length)setCursor(0);setPlaying(!activePlaying);};
  useEffect(()=>{
    if(live||compact||!data)return;
    const onKey=(e:KeyboardEvent)=>{
      const target=e.target as HTMLElement;
      if(target.closest('.map-viewport,input,select,textarea,button,a,summary,[role="tab"],[contenteditable="true"]')||e.metaKey||e.ctrlKey||e.altKey)return;
      if(e.code==='Space'){e.preventDefault();if(data.events.length>0){setPlaying(p=>!p||cursor===data.events.length);if(cursor===data.events.length)setCursor(0);}}
      if(e.code==='ArrowRight'||e.code==='ArrowLeft'){e.preventDefault();setPlaying(false);setCursor(n=>Math.max(0,Math.min(data.events.length,n+(e.code==='ArrowRight'?1:-1))));}
    };
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[compact,data,cursor,live]);
  const changeRun=(id:string)=>{const next=catalog?.runs.find(r=>r.run_id===id);if(next){setPlaying(landing&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches);setCursor(0);setData(null);setError('');setFilter('');setZoom(1);setEntry(next);}};
  if(error)return <section className="replay-empty" role="alert"><span className="empty-icon"><Icon name="info" size={25}/></span><h2>Recording unavailable</h2><p>{error}. The original recording is required to show this journey.</p><button className="product-primary" onClick={()=>{setError('');setReload(n=>n+1);}}>Retry recording <Icon name="reset" size={16}/></button><Link href="/evaluation" className="text-link">Explore the method <Icon name="arrow" size={16}/></Link></section>;
  if(!data||!frame)return <section className="replay-empty" aria-busy={!catalog||catalog.runs.length>0}><span className="empty-icon"><Icon name="map" size={26}/></span><h2>{catalog&&catalog.runs.length===0?'No recordings published yet':'Opening the recording…'}</h2><p>{catalog&&catalog.runs.length===0?'Saved journeys will appear here, ready to replay and inspect.':'Loading the saved journey and verifying its recording.'}</p><Link href="/evaluation" className="text-link">How to read the evidence <Icon name="arrow" size={16}/></Link></section>;
  const shopper=data.shoppers.find(s=>s.id===selected)??data.shoppers[0];
  const state=frame.states[shopper.id];
  const metric=frame.summary.shoppers.find(s=>s.agent_id===shopper.id)!;
  const history=[...shopperHistory(data,cursor,shopper.id)].reverse();
  const counts:Record<string,number>={};state.cart.forEach(i=>counts[i.product_id]=(counts[i.product_id]??0)+i.quantity);
  const currentEvent=data.events[cursor-1];
  const failures=Object.values(frame.summary.failures).reduce((a,b)=>a+b,0);
  const showTab=(next:InspectorTab)=>setTab(next);
  const selectShopper=(id:string)=>{setSelected(id);if(filter)setFilter(id);};
  return <section ref={container} className={`recorded-lab ${compact?'recorded-compact':''} ${live?'is-live':''} ${isPreview?'is-preview':''}`} aria-label={live?"Live shopper lab":"Recorded shopper lab"}>
    {compact&&<header className="replay-heading"><div><p className="eyebrow">Recorded simulations · Layout A & Layout B</p><Heading>The store, from above.</Heading><p>Replay completed runs. Pick a shopper and follow every recorded decision.</p></div>{!landing&&<Link className="text-link" href="/lab">Open full lab <Icon name="arrow" size={16}/></Link>}</header>}

    {!live&&<div className="lab-picker" role="group" aria-label="Recording">{catalog&&catalog.runs.length>4?<label>Recording <select aria-label="Recorded run" value={entry?.run_id??''} onChange={event=>changeRun(event.target.value)}>{catalog.runs.map(run=><option key={run.run_id} value={run.run_id}>{recordingLabel(run,true)}</option>)}</select></label>:catalog?.runs.map(r=>{const base=`${r.layout_id}:${r.shopper_count}:${r.status}`;const duplicate=(catalog?.runs.filter(other=>`${other.layout_id}:${other.shopper_count}:${other.status}`===base).length??0)>1;return <button key={r.run_id} aria-pressed={r.run_id===entry?.run_id} title={r.run_id} onClick={()=>changeRun(r.run_id)}>{landing?`Layout ${r.layout_id==='costco_back_anchor'?'A · Anchor loop':'B · Express essentials'} · ${r.model}`:recordingLabel(r,duplicate)}</button>;})}</div>}
    {!live&&data.source.status!=='completed'&&<p className="lab-note" role="status">Partial recording · {data.shoppers.length} shoppers, {data.events.length} events · {data.source.status.replaceAll('_',' ')}. Outcomes do not establish a complete layout evaluation.</p>}
    {!isPreview&&!['openai','gemini','openrouter'].includes(data.source.provider)&&<p className="lab-note">Offline test fixture · scripted actions, not a model run.</p>}
    {['gary2_v1','gary2_v2'].includes(data.config?.navigation_policy??'')&&<p className="lab-note">Navigation assistance: avoid repeated routes, collect reachable list items, and head toward checkout.</p>}

    <div className="replay-body"><div className="replay-main-column"><div className="replay-map-panel">
      <div className="replay-map-heading">
        <div className="map-title"><h3>{layoutName(data.layout.id)} <span>{isPreview?'Preview':live?`Live · ${data.source.run_id.slice(0,8)}`:entry?entry.run_id.slice(0,8):''}</span></h3></div>
        <div className="map-layer-controls">
          <button aria-pressed={heat} onClick={()=>setHeat(!heat)} title="Show recorded foot traffic"><Icon name="heat" size={15}/><span>Traffic</span></button>
          <button aria-pressed={trail} onClick={()=>setTrail(!trail)} title="Show selected shopper’s recorded trail"><Icon name="route" size={15}/><span>Trail</span></button>
        </div>
        <div className="zoom-controls">
          <button aria-label="Zoom out" disabled={zoom<=1} onClick={()=>setZoom(z=>Math.max(1,Math.round((z-.25)*100)/100))}><Icon name="minus" size={14}/></button>
          <button className="zoom-reset" aria-label="Fit entire map" title="Fit entire store in view" onClick={()=>setZoom(1)}>{zoom===1?'Fit':`${Math.round(zoom*100)}%`}</button>
          <button aria-label="Zoom in" disabled={zoom>=4} onClick={()=>setZoom(z=>Math.min(4,Math.round((z+.25)*100)/100))}><Icon name="plus" size={14}/></button>
        </div>
      </div>
      <MapViewport zoom={zoom} width={data.layout.width*CELL_SIZE+32} height={data.layout.height*CELL_SIZE+36}><RecordedStoreMap data={data} states={frame.states} summary={frame.summary} cursor={cursor} selected={shopper.id} filter={filter} trail={trail} heat={heat} onSelect={selectShopper} focusProductId={currentEvent?.action?.product_id||undefined}/></MapViewport>
      <div className="map-bottom"><div className="map-legend"><span>Entrance</span><span>Checkout</span><span>Shopper</span><span className="item-legend">1 block = 1 item</span>{heat&&<span className="heat-legend">Low <i/> High traffic</span>}</div></div>
      {live&&!isPreview?<div className="replay-player" role="status"><div className="player-topline"><span>{live.connection==='connected'?(live.controlStatus==='paused'?'Paused · no model requests':live.controlStatus==='pausing'?'Pausing after the current round':live.controlStatus==='stopping'?'Stopping · saving confirmed actions':live.controlStatus==='waiting_for_model'?'Waiting for the next model decision':'Following confirmed Python actions'):live.connection==='ended'?'Python run ended':live.connection==='reconnecting'?'Reconnecting to Python':'Connecting to Python'}</span><span>{`Committed event ${cursor}`}</span></div></div>:!live?<div className="replay-player"><div className="player-topline"><span><span className={`status-dot ${activePlaying?'is-playing':''}`}/>{activePlaying?'Playing':cursor===data.events.length?'End of recording':cursor===0?'Ready':'Paused'}</span><label htmlFor={`${uid}-timeline`}>Event <b>{cursor}</b> / {data.events.length}</label></div><input id={`${uid}-timeline`} aria-label="Replay timeline" type="range" min={0} max={data.events.length} value={cursor} disabled={data.events.length===0} style={{'--progress':`${data.events.length?cursor/data.events.length*100:0}%`} as CSSProperties} onChange={e=>seek(Number(e.target.value))}/><div className="player-controls"><div className="transport-controls"><button aria-label="Restart replay" title="Restart replay" disabled={cursor===0} onClick={()=>seek(0)}><Icon name="reset" size={16}/></button><button aria-label="Previous event" title="Previous event (←)" disabled={cursor===0} onClick={()=>seek(Math.max(0,cursor-1))}><Icon name="back" size={16}/></button><button className="play-button" onClick={togglePlayback} disabled={data.events.length===0} aria-label={activePlaying?'Pause replay':cursor===data.events.length?'Replay recording':'Play recorded run'}><Icon name={activePlaying?'pause':'play'} size={17}/><span>{activePlaying?'Pause':cursor===data.events.length?'Replay':'Play'}</span></button><button aria-label="Next event" title="Next event (→)" disabled={cursor>=data.events.length} onClick={()=>seek(Math.min(data.events.length,cursor+1))}><Icon name="next" size={16}/></button></div><div className="speed-control" role="group" aria-label="Playback speed">{[1,2,4,8].map(n=><button key={n} aria-pressed={speed===n} onClick={()=>setSpeed(n)}>{n}×</button>)}</div>{!compact&&<span className="keyboard-hint"><kbd>space</kbd> play / pause</span>}</div></div>:null}
    </div>
    <div className="replay-score" aria-label="Run totals"><Stat label="Checked out" value={`${frame.summary.finished_count}`} suffix={`/ ${frame.summary.shopper_count}`} hint="Completed trips"/><Stat label="List fulfillment" value={`${(frame.summary.mean_list_completion*100).toFixed(1)}%`} hint="Mean across all shoppers"/><Stat label="Basket value" value={dollars(frame.summary.basket_value_cents)} hint="At this recorded event"/><Stat label="Completed sales" value={dollars(frame.summary.sales_cents)} hint="From checked-out baskets"/></div>
    {!isPreview&&<p className="event-peek" aria-live="polite">{currentEvent?<><strong>Event {currentEvent.sequence}</strong><span>{data.shoppers.find(s=>s.id===currentEvent.agent_id)?.name}</span>{currentEvent.action?actionName(currentEvent.action.step):'No valid decision'}<span className={currentEvent.outcome==='applied'?'':'event-failure'}>{currentEvent.outcome==='applied'?'Applied':actionName(currentEvent.outcome)}</span></>:live?'Waiting for the next confirmed Python action.':'Press play or use the timeline to explore the recording.'}</p>}
    </div>
    <aside className="replay-inspector" aria-label="Shopper inspector">
      <div className="shopper-roster" aria-label="Recorded shoppers">
        <div className="roster-heading">
          <h3>Shoppers <span>{data.shoppers.length}</span></h3>
          <div className="filter-control" role="group" aria-label="Viewing filter">
            <button aria-pressed={!filter} onClick={()=>setFilter('')} title="Show every shopper on the map">All</button>
            <button aria-pressed={!!filter} onClick={()=>setFilter(shopper.id)} title="Solo only changes the map. Run totals include every shopper.">Solo</button>
          </div>
        </div>
        <div className="shopper-cards" role="listbox" aria-label="Shoppers">{data.shoppers.map(s=><button key={s.id} role="option" aria-selected={s.id===shopper.id} className={`shopper-card ${s.id===shopper.id?'selected':''}`} onClick={()=>selectShopper(s.id)}>{s.name}</button>)}</div>
      </div>
      <div className="shopper-identity">
        <span className="avatar avatar-large"><span className="shopper-sprite" style={{backgroundPosition:`0px -${shopper.sprite_index*4*40}px`}}/></span>
        <div>
          <div className="inspector-heading"><span className="shopper-name">{shopper.name}</span><span className="state-tag">{isPreview?'Ready':phaseName(state.phase)}</span></div>
          <p>{shopper.style} · ({state.x}, {state.y})</p>
        </div>
      </div>
      <div className="inspector-tabs" role="tablist" aria-label="Shopper details">{(['overview','decisions','profile'] as const).map(t=><button key={t} id={`${uid}-${t}`} role="tab" aria-selected={tab===t} aria-controls={`${uid}-panel`} tabIndex={tab===t?0:-1} onClick={()=>showTab(t)} onKeyDown={e=>{const tabs:InspectorTab[]=['overview','decisions','profile'];let i=tabs.indexOf(t);if(e.key==='ArrowRight')i=(i+1)%3;else if(e.key==='ArrowLeft')i=(i+2)%3;else if(e.key==='Home')i=0;else if(e.key==='End')i=2;else return;e.preventDefault();showTab(tabs[i]);document.getElementById(`${uid}-${tabs[i]}`)?.focus();}}>{t==='overview'?'Overview':t==='decisions'?'Decisions':'Profile'}{t==='decisions'&&<span>{history.length}</span>}</button>)}</div>
      <div className="inspector-content" id={`${uid}-panel`} role="tabpanel" aria-labelledby={`${uid}-${tab}`} tabIndex={0}>
      {tab==='overview'&&<><div className="basket-overview"><span>Basket / budget</span><p><strong>{dollars(state.basket_cents)}</strong><span>/ {dollars(shopper.budget_cents)}</span></p><div className={`budget-meter ${metric.overshoot_cents!=null&&metric.overshoot_cents>0?'over-budget':''}`}><i style={{width:`${Math.min(100,shopper.budget_cents>0?(state.basket_cents??0)/shopper.budget_cents*100:0)}%`}}/></div>{metric.overshoot_cents!=null&&metric.overshoot_cents>0&&<small className="budget-warning">{dollars(metric.overshoot_cents)} over budget</small>}</div><div className="inspector-section-title"><h4>Shopping list</h4><span>{(metric.list_completion*100).toFixed(0)}% fulfilled</span></div><ul className="shopping-list">{shopper.list.map((i,n)=><li key={`${i.product_id}-${n}`}><span className={`list-check ${(counts[i.product_id]??0)>=i.quantity?'fulfilled':''}`} aria-hidden="true">{(counts[i.product_id]??0)>=i.quantity&&<Icon name="check" size={12}/>}</span><div><strong><span className="item-emoji" aria-hidden="true">{productEmoji(data.catalogue.find(product=>product.id===i.product_id)??i.product_name)}</span>{i.product_name}</strong><small>{i.priority.replaceAll('_',' ')}</small></div><span className="quantity">{counts[i.product_id]??0}<span>/{i.quantity}</span></span></li>)}</ul><div className="inspector-section-title"><h4>Current basket</h4><Icon name="bag" size={15}/></div>{state.cart.length?<ul className="basket-list">{state.cart.map((i,n)=><li key={n}><span><span className="item-emoji" aria-hidden="true">{productEmoji(data.catalogue.find(product=>product.id===i.product_id)??i.name)}</span>{i.name}</span><b>×{i.quantity}</b></li>)}</ul>:<div className="basket-empty"><Icon name="bag" size={23}/><p>Nothing in the basket yet.<span>Step through to see what changes.</span></p></div>}<dl className="shopper-facts"><div><dt>Recorded turns</dt><dd>{state.turns_used} / {state.turn_budget}</dd></div><div><dt>Stopping reason</dt><dd>{reasonName(metric.stop_reason)}</dd></div><div><dt>Budget overshoot</dt><dd>{dollars(metric.overshoot_cents)}</dd></div></dl></>}
      {tab==='decisions'&&<><div className="inspector-section-title"><h4>Recorded decisions</h4><span>Most recent first</span></div>{history.length?history.map(e=><button className={`replay-action ${e.outcome!=='applied'?'action-failed':''}`} key={e.sequence} onClick={()=>seek(e.sequence)}><span className="action-meta"><b>EVENT {String(e.sequence).padStart(2,'0')}</b><span>{e.outcome==='applied'?'Applied':actionName(e.outcome)}</span></span><strong>{e.action?actionName(e.action.step):'No valid decision'}</strong><p>{e.failure??e.action?.reason??'No explanation was recorded.'}</p>{e.action?.product_id&&<small><span className="item-emoji" aria-hidden="true">{productEmoji(data.catalogue.find(p=>p.id===e.action?.product_id)??e.action.product_id)}</span>{data.catalogue.find(p=>p.id===e.action?.product_id)?.name??e.action.product_id}</small>}<span className="action-jump">{live?'Confirmed by Python':'View this event'} <Icon name="arrow" size={12}/></span></button>):<div className="tab-empty"><Icon name="clock" size={24}/><h4>No decisions yet</h4><p>Play the recording to see {shopper.name.split(' ')[0]}’s decisions here.</p></div>}</>}
      {tab==='profile'&&<><p className="profile-description">Supplied preferences for {shopper.name.split(' ')[0]}’s trip.</p><dl className="persona-facts">{Object.entries(shopper.persona).map(([k,v])=><div key={k}><dt>{actionName(k)}</dt><dd>{Array.isArray(v)?v.join(', ')||'None':typeof v==='object'&&v!==null?JSON.stringify(v):String(v)}</dd></div>)}</dl><p className="view-note">Supplied personas are simulation inputs. They do not establish real customer behavior.</p></>}
      </div>
    </aside></div>
    {!isPreview&&<footer className="replay-evidence"><details><summary>Recording details</summary><dl><div><dt>Recorded status</dt><dd>{data.source.status.replaceAll('_',' ')}</dd></div><div><dt>Recorded at</dt><dd>{new Date(data.source.recorded_at).toLocaleString()}</dd></div><div><dt>Run</dt><dd>{data.source.run_id}</dd></div><div><dt>{live&&data.source.status==='incomplete'?'Recorded prefix hash':'Source hash'}</dt><dd>{data.source.sha256}</dd></div><div><dt>Model / prompt</dt><dd>{data.source.model} / {data.source.prompt_variant}</dd></div><div><dt>Known API estimate</dt><dd>{frame.summary.resources==null?'Unknown':`$${frame.summary.resources.known_estimated_cost_usd.toFixed(4)}`}</dd></div><div><dt>Attempts with unknown usage</dt><dd>{frame.summary.resources?.unknown_usage_requests??'Unrecorded'}</dd></div><div><dt>Failed attempts</dt><dd>{failures}</dd></div></dl></details><div>{!live&&<a href={entry?.evidence_url} download><Icon name="download" size={14}/> Original evidence</a>}<Link href="/evaluation">Method & limitations <Icon name="arrow" size={14}/></Link></div></footer>}
  </section>;
}
function Stat({label,value,suffix,hint}:{label:string;value:string;suffix?:string;hint:string}){return <div className="stat-card" title={hint}><span>{label}</span><strong>{value}{suffix&&<small>{suffix}</small>}</strong></div>;}

export default memo(ReplayWorkspace,(previous,next)=>previous.compact===next.compact&&previous.landing===next.landing
  &&previous.live?.data===next.live?.data&&previous.live?.connection===next.live?.connection
  &&previous.live?.controlStatus===next.live?.controlStatus&&previous.live?.preview===next.live?.preview);
