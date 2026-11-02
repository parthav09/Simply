'use client';

import {useEffect,useRef,useState} from 'react';
import ReplayWorkspace from './ReplayWorkspace';
import {liveSnapshot,liveTransition,type LiveControl,type LiveSnapshot,type LiveTransition} from '../lib/live';
import {validateReplay,type ReplayData} from '../lib/replay';
import {Icon} from './Icons';
import {productEmoji} from './map-theme';
import {invalidateCatalog} from '../lib/recordings';
import {liveEndNotice,liveStatusLabel,liveSessionStorage,readRememberedRun,rememberRun,restoreRunSelection} from '../lib/live-session';
const modelName=(id:string)=>({'gpt-6-luna':'GPT-6 Luna','gpt-6.1-terra':'GPT-6.1 Terra'} as Record<string,string>)[id]??id;
const layoutShort=(id:string)=>({costco_back_anchor:'A',neighborhood_express:'B'} as Record<string,string>)[id]??id;

type Run={run_id:string;layout_id:string;shopper_count:number;model:string;status:string;controllable:boolean};
type ApiAccounting={known_estimated_usd:number;unresolved_reserved_usd:number;requests:number};
async function api(path:string,body?:object){
  const response=await fetch('/api/simulation/'+path,{cache:'no-store',...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
  const value=await response.json();
  if(!response.ok)throw new Error(value.error??'Python service request failed');
  return value;
}

export default function LiveWorkspace(){
  const [mode,setMode]=useState<'live'|'replay'>('live');
  const [runs,setRuns]=useState<Run[]>([]);const [runId,setRunId]=useState('');
  const [layout,setLayout]=useState('costco_back_anchor');const [count,setCount]=useState(10);
  const [model,setModel]=useState('gpt-6-luna');const [preview,setPreview]=useState<ReplayData|null>(null);
  const [lastUpdate,setLastUpdate]=useState(0);const [now,setNow]=useState(0);
  const [data,setData]=useState<ReplayData|null>(null);const current=useRef<ReplayData|null>(null);
  const [control,setControl]=useState<LiveControl>({controllable:false,status:'observing'});
  const [connection,setConnection]=useState('connecting');const [error,setError]=useState('');
  const [serviceReady,setServiceReady]=useState<boolean|null>(null);const [busy,setBusy]=useState(false);
  const [reconnect,setReconnect]=useState(0);const [saved,setSaved]=useState(false);
  const [feedFilter,setFeedFilter]=useState<'all'|'purchases'|'failures'>('all');
  const [accounting,setAccounting]=useState<ApiAccounting|null>(null);
  const [budgetEnforced,setBudgetEnforced]=useState<boolean|null>(null);
  useEffect(()=>{
    if(mode!=='live'||runId)return;
    let cancelled=false;
    api(`preview?layout=${layout}&shoppers=${count}&model=${model}`).then(value=>{if(!cancelled)setPreview(validateReplay(value));}).catch(()=>{if(!cancelled)setPreview(null);});
    return()=>{cancelled=true;};
  },[mode,runId,layout,count,model]);
  useEffect(()=>{
    if(mode!=='live'||!runId||data?.source.status!=='incomplete'||control.status!=='waiting_for_model')return;
    const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);
  },[mode,runId,data?.source.status,control.status]);
  useEffect(()=>{
    if(mode!=='live')return;
    let cancelled=false,inFlight=false,failures=0;
    let timer:ReturnType<typeof setTimeout>|undefined;
    const refresh=async()=>{
      clearTimeout(timer);
      if(cancelled||document.hidden||inFlight)return;
      inFlight=true;
      try{
        const [value,health]=await Promise.all([api('runs'),api('health').catch(()=>null)]);
        if(!cancelled){setRuns(value.runs);setServiceReady(true);
          setAccounting(health?.budget??null);setBudgetEnforced(typeof health?.api_budget_enforced==='boolean'?health.api_budget_enforced:null);
          setRunId(previous=>restoreRunSelection(previous,value.runs,readRememberedRun(liveSessionStorage())));}
        failures=0;
      }catch{if(!cancelled)setServiceReady(false);failures++;}
      finally{
        inFlight=false;
        if(!cancelled&&!document.hidden)timer=setTimeout(refresh,Math.min(15000,3000*2**failures));
      }
    };
    const visibility=()=>{if(document.hidden)clearTimeout(timer);else void refresh();};
    void refresh();document.addEventListener('visibilitychange',visibility);
    return()=>{cancelled=true;clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);};
  },[mode]);
  useEffect(()=>{
    if(mode!=='live'||!runId)return;
    let active=true;
    const source=new EventSource(`/api/simulation/runs/${runId}/events`);
    const fail=(cause:unknown)=>{source.close();setConnection('error');setError(cause instanceof Error?cause.message:'Invalid Python stream');};
    source.addEventListener('snapshot',event=>{if(!active)return;try{
      const message=JSON.parse((event as MessageEvent).data) as LiveSnapshot;
      const next=liveSnapshot(message,current.current);if(next.source.run_id!==runId)throw new Error('Live run identity changed');
      current.current=next;setData(next);setLastUpdate(Date.now());setControl(message.control);setError('');
      rememberRun(liveSessionStorage(),runId);
      if(['gpt-6-luna','gpt-6.1-terra'].includes(next.source.model))setModel(next.source.model);
      if(['costco_back_anchor','neighborhood_express'].includes(next.layout.id))setLayout(next.layout.id);
      if(next.shoppers.length>=10)setCount(next.shoppers.length);
      const ended=next.source.status!=='incomplete';setConnection(ended?'ended':'connected');if(ended)source.close();
    }catch(cause){fail(cause);}});
    const update=(event:Event)=>{if(!active)return;try{
      if(!current.current)throw new Error('Live stream has no initial state');
      const message=JSON.parse((event as MessageEvent).data) as LiveTransition;
      const next=liveTransition(current.current,message);current.current=next;setData(next);setLastUpdate(Date.now());setControl(message.control);
      if(event.type==='finished'){setConnection('ended');source.close();}else setConnection('connected');
    }catch(cause){fail(cause);}};
    source.addEventListener('transition',update);source.addEventListener('finished',update);
    source.addEventListener('control',event=>{if(!active)return;try{setControl(JSON.parse((event as MessageEvent).data));}catch(cause){fail(cause);}});
    source.addEventListener('stream_error',event=>fail(new Error(JSON.parse((event as MessageEvent).data).error)));
    source.onerror=()=>{if(active&&(!current.current||current.current.source.status==='incomplete'))setConnection('reconnecting');};
    return()=>{active=false;source.close();};
  },[mode,runId,reconnect]);
  const choose=(id:string)=>{rememberRun(liveSessionStorage(),id);current.current=null;setData(null);setRunId(id);setSaved(false);setError('');setConnection('connecting');};
  const start=async()=>{setBusy(true);setError('');try{const result=await api('runs',{layout,shoppers:count,model,provider:'openrouter'});choose(result.run_id);setControl(result);}catch(cause){setError((cause as Error).message);}finally{setBusy(false);}};
  const command=async(command:string)=>{setBusy(true);setError('');try{setControl(await api(`runs/${runId}/control`,{command}));}catch(cause){setError((cause as Error).message);}finally{setBusy(false);}};
  const save=async()=>{setBusy(true);setError('');try{await api(`runs/${runId}/export`,{allow_partial:data?.source.status!=='completed'});invalidateCatalog();setSaved(true);}catch(cause){setError((cause as Error).message);}finally{setBusy(false);}};
  const ended=!!data&&data.source.status!=='incomplete';
  const activeRun=!!runId&&!ended;
  const owned=activeRun&&control.controllable;
  const statusLabel=({waiting_for_model:`Waiting for ${modelName(data?.source.model??model)}`,pausing:'Pausing after this round',paused:'Paused',running:'Running',stopping:'Stopping',observing:'Following Python'} as Record<string,string>)[control.status]??control.status;
  const waitSeconds=lastUpdate?Math.max(0,Math.floor((now-lastUpdate)/1000)):0;
  const waiting=connection==='connected'&&control.status==='waiting_for_model';
  const latest=data?.events.at(-1);
  const latestShopper=data?.shoppers.find(s=>s.id===latest?.agent_id);
  const failures=data?Object.values(data.summary.failures).reduce((a,b)=>a+b,0):0;
  const feedRows=data?.events.filter(event=>feedFilter==='purchases'?event.action?.step==='grab'&&event.outcome==='applied':feedFilter==='failures'?event.outcome!=='applied':true)??[];
  const endNotice=data?liveEndNotice(data):null;
  const newSetup=()=>{rememberRun(liveSessionStorage(),'');current.current=null;setRunId('');setData(null);setPreview(null);setError('');setSaved(false);};
  const pickModel=(id:string)=>{if(model===id&&!runId)return;newSetup();setModel(id);};
  const pickLayout=(id:string)=>{if(layout===id&&!runId)return;newSetup();setLayout(id);};
  const pickCount=(n:number)=>{if(count===n&&!runId)return;newSetup();setCount(n);};
  const followRun=(run:Run)=>{if(['gpt-6-luna','gpt-6.1-terra'].includes(run.model))setModel(run.model);setLayout(run.layout_id);if(run.shopper_count>=10)setCount(run.shopper_count);choose(run.run_id);};
  return <>
    <header className="lab-toolbar">
      <div className="lab-mode-switch" role="group" aria-label="Lab mode">
        <button aria-pressed={mode==='live'} onClick={()=>setMode('live')}><span className="live-dot"/>Live</button>
        <button aria-pressed={mode==='replay'} onClick={()=>setMode('replay')}>Replay</button>
      </div>
      {mode==='live'&&!runId&&<div className="live-config">
        <div className="seg" role="group" aria-label="Shopper model">
          <button aria-pressed={model==='gpt-6-luna'} onClick={()=>pickModel('gpt-6-luna')}>Luna</button>
          <button aria-pressed={model==='gpt-6.1-terra'} onClick={()=>pickModel('gpt-6.1-terra')}>Terra</button>
        </div>
        <div className="seg" role="group" aria-label="Live layout">
          <button aria-pressed={layout==='costco_back_anchor'} onClick={()=>pickLayout('costco_back_anchor')}>A · Anchor</button>
          <button aria-pressed={layout==='neighborhood_express'} onClick={()=>pickLayout('neighborhood_express')}>B · Express</button>
        </div>
        <div className="stepper" role="group" aria-label="Live shopper count">
          <button aria-label="Fewer shoppers" disabled={count<=10} onClick={()=>pickCount(count-1)}>−</button>
          <span>{count}</span>
          <button aria-label="More shoppers" disabled={count>=15} onClick={()=>pickCount(count+1)}>+</button>
        </div>
        <button className="product-primary" disabled={!serviceReady||busy||activeRun} onClick={start}><Icon name="play" size={15}/>{busy?'Starting…':'Start'}</button>
      </div>}
      {mode==='live'&&runId&&<div className="live-session-controls">
        <span className={`run-state ${waiting?'is-waiting':''}`} role="status"><span className="live-dot"/>{connection==='connected'?`${statusLabel}${waiting&&waitSeconds>0?` · ${waitSeconds}s`:''}`:connection==='ended'?liveStatusLabel(data?.source.status??'ended'):connection==='reconnecting'?'Reconnecting':connection}</span>
        <div className="run-buttons">
          {owned&&<>
            <button disabled={busy||control.status==='paused'||control.status==='pausing'} onClick={()=>command('pause')}><Icon name="pause" size={14}/>Pause</button>
            <button disabled={busy||control.status!=='paused'} onClick={()=>command('resume')}><Icon name="play" size={14}/>Resume</button>
            <button disabled={busy||control.status!=='paused'} onClick={()=>command('advance')} title="Run exactly one round for all shoppers"><Icon name="next" size={14}/>One round</button>
            <button className="stop-run" disabled={busy||control.status==='stopping'} onClick={()=>command('stop')}>Stop & save</button>
          </>}
          {ended&&<button onClick={newSetup}>New setup</button>}
          {data&&!ended&&!control.controllable&&<button onClick={newSetup}>Leave recording</button>}
          {ended&&<button disabled={busy||saved} onClick={save}>{saved?'Saved':data?.source.status==='completed'?'Save replay':'Save partial'}</button>}
          <button className="reconnect-button" disabled={busy} onClick={()=>{setConnection('connecting');setReconnect(n=>n+1);}} title="Restore the recorded state without calling the model"><Icon name="reset" size={14}/>Reconnect</button>
        </div>
      </div>}
    </header>
    {mode==='replay'?<ReplayWorkspace/>:<>
      <p className="lab-note api-accounting" role="status">{data?`Recorded transport: ${data.source.provider} · `:'New sessions use OpenRouter · '}{budgetEnforced===false?'API cost tracking only · no app spending cap':budgetEnforced===true?'This session has an explicit API budget':'Checking API cost tracking…'}{accounting&&<> · Known estimate ${accounting.known_estimated_usd.toFixed(4)} · Unresolved reservations ${accounting.unresolved_reserved_usd.toFixed(4)}</>}. Provider rate and quota limits still apply.</p>
      {endNotice&&<section className={`live-end-notice ${endNotice.warning?'is-warning':''}`} role="status"><strong>{endNotice.title}</strong><p>{endNotice.detail}</p></section>}
      {mode==='live'&&!activeRun&&!runId&&runs.length>0&&<details className="lab-history"><summary>Recent runs <span>{runs.length}</span></summary><div className="lab-picker" role="group" aria-label="Follow Python run">{runs.slice(0,8).map(run=><button key={run.run_id} aria-pressed={run.run_id===runId} onClick={()=>followRun(run)}>{layoutShort(run.layout_id)} · {modelName(run.model)} · {run.status} · {run.run_id.slice(0,8)}</button>)}</div></details>}
      {serviceReady===false&&<div className="live-banner" role="alert">Live simulation is offline. Saved recordings are available to explore.</div>}
      {error&&<div className="live-banner" role="alert">{error}</div>}
      {data&&data.source.run_id===runId?<ReplayWorkspace key={runId} live={{data,connection,controlStatus:control.status}}/>:preview&&!runId?<ReplayWorkspace live={{data:preview,connection:'preview',preview:true}}/>:<div className="replay-empty"><h2>{runId?'Connecting to this run…':serviceReady===false?'Live service unavailable':'Loading store preview…'}</h2><p>{runId?'Restoring the saved state of this run.':serviceReady===false?'You can still replay saved trips, inspect baskets, and follow recorded decisions.':'A model is called only when you start a run.'}</p>{serviceReady===false&&!runId&&<button className="product-primary" onClick={()=>setMode('replay')}>Browse recorded replays <Icon name="arrow" size={16}/></button>}</div>}
      {data&&<section className="live-activity" aria-label="Live action feed">
        <div className="activity-heading">
          <h2>Decisions <span>{data.events.length} committed · {failures} failed</span></h2>
          <div className="feed-filters" role="group" aria-label="Decision feed filter">{(['all','purchases','failures'] as const).map(filter=><button key={filter} aria-pressed={feedFilter===filter} onClick={()=>setFeedFilter(filter)}>{filter==='all'?'All':filter==='purchases'?'Purchases':'Failures'}</button>)}</div>
        </div>
        {latest&&<p className="activity-latest"><strong>{latestShopper?.name}</strong> · {latest.action?.reason??latest.failure??'No valid action returned'}</p>}
        <div className="activity-rows">{feedRows.slice(-8).reverse().map(event=><div key={event.sequence} className={event.outcome==='applied'?'':'activity-failure'}><span>#{event.sequence}</span><strong>{data.shoppers.find(s=>s.id===event.agent_id)?.name}</strong><span className="action-chip">{event.action?.step==='grab'?'Pick up':(event.action?.step??event.outcome).replaceAll('_',' ')}</span><p>{event.action?.product_id&&<b><span className="item-emoji" aria-hidden="true">{productEmoji(data.catalogue.find(product=>product.id===event.action?.product_id)??event.action.product_id)}</span>{data.catalogue.find(product=>product.id===event.action?.product_id)?.name??event.action.product_id} · </b>}{event.failure??event.action?.reason}</p><span>({event.after.x}, {event.after.y})</span></div>)}</div>
        {!feedRows.length&&<p className="feed-empty">{feedFilter==='purchases'?'No purchases yet. Shoppers must reach a shelf before picking up an item.':feedFilter==='failures'?'No failed decisions recorded.':'The first decisions will appear here. Shopper inspection never calls the model.'}</p>}
      </section>}
    </>}
  </>;
}
