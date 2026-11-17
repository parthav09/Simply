'use client';

import {useEffect,useRef,useState} from 'react';
import ReplayWorkspace from './ReplayWorkspace';
import {liveSnapshot,liveTransition,type LiveControl,type LiveSnapshot,type LiveTransition} from '../lib/live';
import {validateReplay,type ReplayData} from '../lib/replay';
import {Icon} from './Icons';
import Link from 'next/link';
import {invalidateCatalog} from '../lib/recordings';
import {liveEndNotice,liveStatusLabel,liveSessionStorage,readRememberedRun,rememberRun,restoreRunSelection} from '../lib/live-session';
const modelName=(id:string)=>({'gpt-6-luna':'GPT-6 Luna','gpt-6.1-terra':'GPT-6.1 Terra','qwen2.5-7b-pilot-mps':'Qwen 7B fine-tuned · MPS','qwen2.5-7b-pilot-mlx':'Qwen 7B fine-tuned · MLX'} as Record<string,string>)[id]??id;
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
  const [runs,setRuns]=useState<Run[]>([]);const [runId,setRunId]=useState('');
  const [layout,setLayout]=useState('costco_back_anchor');const [count,setCount]=useState(10);
  const [model,setModel]=useState('gpt-6-luna');const [preview,setPreview]=useState<ReplayData|null>(null);
  const [lastUpdate,setLastUpdate]=useState(0);const [now,setNow]=useState(0);
  const [data,setData]=useState<ReplayData|null>(null);const current=useRef<ReplayData|null>(null);
  const [control,setControl]=useState<LiveControl>({controllable:false,status:'observing'});
  const [connection,setConnection]=useState('connecting');const [error,setError]=useState('');
  const [serviceReady,setServiceReady]=useState<boolean|null>(null);const [busy,setBusy]=useState(false);
  const [reconnect]=useState(0);const [saved,setSaved]=useState(false);
  const [accounting,setAccounting]=useState<ApiAccounting|null>(null);
  const [mpsReady,setMpsReady]=useState(false);const [mlxReady,setMlxReady]=useState(false);
  const [confirming,setConfirming]=useState(false);
  useEffect(()=>{
    if(runId)return;
    let cancelled=false;
    api(`preview?layout=${layout}&shoppers=${count}&model=${model}`).then(value=>{if(!cancelled)setPreview(validateReplay(value));}).catch(()=>{if(!cancelled)setPreview(null);});
    return()=>{cancelled=true;};
  },[runId,layout,count,model]);
  useEffect(()=>{
    if(!runId||data?.source.status!=='incomplete'||control.status!=='waiting_for_model')return;
    const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);
  },[runId,data?.source.status,control.status]);
  useEffect(()=>{
    let cancelled=false,inFlight=false,failures=0;
    let timer:ReturnType<typeof setTimeout>|undefined;
    const refresh=async()=>{
      clearTimeout(timer);
      if(cancelled||document.hidden||inFlight)return;
      inFlight=true;
      try{
        const [value,health]=await Promise.all([api('runs'),api('health').catch(()=>null)]);
        if(!cancelled){setRuns(value.runs);setServiceReady(true);
          setMpsReady(health?.local_mps_available===true);setMlxReady(health?.local_mlx_available===true);setAccounting(health?.budget??null);
          setRunId(previous=>restoreRunSelection(previous,value.runs,readRememberedRun(liveSessionStorage())));}
        failures=0;
      }catch{if(!cancelled){setServiceReady(false);}failures++;}
      finally{
        inFlight=false;
        if(!cancelled&&!document.hidden)timer=setTimeout(refresh,Math.min(15000,3000*2**failures));
      }
    };
    const visibility=()=>{if(document.hidden)clearTimeout(timer);else void refresh();};
    void refresh();document.addEventListener('visibilitychange',visibility);
    return()=>{cancelled=true;clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);};
  },[]);
  useEffect(()=>{
    if(!runId)return;
    let active=true;
    const source=new EventSource(`/api/simulation/runs/${runId}/events`);
    const fail=(cause:unknown)=>{source.close();setConnection('error');setError(cause instanceof Error?cause.message:'Invalid Python stream');};
    source.addEventListener('snapshot',event=>{if(!active)return;try{
      const message=JSON.parse((event as MessageEvent).data) as LiveSnapshot;
      const next=liveSnapshot(message,current.current);if(next.source.run_id!==runId)throw new Error('Live run identity changed');
      current.current=next;setData(next);setLastUpdate(Date.now());setControl(message.control);setError('');
      rememberRun(liveSessionStorage(),runId);
      if(['gpt-6-luna','gpt-6.1-terra','qwen2.5-7b-pilot-mps','qwen2.5-7b-pilot-mlx'].includes(next.source.model))setModel(next.source.model);
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
  },[runId,reconnect]);
  const choose=(id:string)=>{rememberRun(liveSessionStorage(),id);current.current=null;setData(null);setRunId(id);setSaved(false);setError('');setConnection('connecting');};
  const start=async()=>{setConfirming(false);setBusy(true);setError('');try{const result=await api('runs',{layout,shoppers:count,model,provider:model.startsWith('qwen2.5-7b-pilot-')?'local_mps':'openrouter'});choose(result.run_id);setControl(result);}catch(cause){setError((cause as Error).message);}finally{setBusy(false);}};
  const command=async(command:string)=>{setBusy(true);setError('');try{setControl(await api(`runs/${runId}/control`,{command}));}catch(cause){setError((cause as Error).message);}finally{setBusy(false);}};
  const save=async()=>{setBusy(true);setError('');try{await api(`runs/${runId}/export`,{allow_partial:data?.source.status!=='completed'});invalidateCatalog();setSaved(true);}catch(cause){setError((cause as Error).message);}finally{setBusy(false);}};
  const localMps=(data?.source.provider??(model.startsWith('qwen2.5-7b-pilot-')?'local_mps':'openrouter'))==='local_mps';
  const ended=!!data&&data.source.status!=='incomplete';
  const activeRun=!!runId&&!ended;
  const owned=activeRun&&control.controllable;
  const statusLabel=({waiting_for_model:`Waiting for ${modelName(data?.source.model??model)}`,pausing:'Pausing after this round',paused:'Paused',running:'Running',stopping:'Stopping',observing:'Following Python'} as Record<string,string>)[control.status]??control.status;
  const waitSeconds=lastUpdate?Math.max(0,Math.floor((now-lastUpdate)/1000)):0;
  const waiting=connection==='connected'&&control.status==='waiting_for_model';
  const endNotice=data?liveEndNotice(data):null;
  const newSetup=()=>{setConfirming(false);rememberRun(liveSessionStorage(),'');current.current=null;setRunId('');setData(null);setPreview(null);setError('');setSaved(false);};
  const pickModel=(id:string)=>{if(model===id&&!runId)return;newSetup();setModel(id);};
  const pickLayout=(id:string)=>{if(layout===id&&!runId)return;newSetup();setLayout(id);};
  const pickCount=(n:number)=>{if(count===n&&!runId)return;newSetup();setCount(n);};
  const followRun=(run:Run)=>{if(['gpt-6-luna','gpt-6.1-terra','qwen2.5-7b-pilot-mps','qwen2.5-7b-pilot-mlx'].includes(run.model))setModel(run.model);setLayout(run.layout_id);if(run.shopper_count>=10)setCount(run.shopper_count);choose(run.run_id);};

  return <>
    <header className="page-head">
      <div><h1>Live run</h1><p>Start a model-driven shopping trip and watch it unfold. Python validates and records every move.</p></div>
      {runId&&<div className="live-session-controls">
        <span className={`run-state ${waiting?'is-waiting':''}`} role="status"><span className="live-dot"/>{connection==='connected'?`${statusLabel}${waiting&&waitSeconds>0?` · ${waitSeconds}s`:''}`:connection==='ended'?liveStatusLabel(data?.source.status??'ended'):connection==='reconnecting'?'Reconnecting':connection}</span>
        <div className="run-buttons">
          {owned&&<>
            <button disabled={busy||control.status==='paused'||control.status==='pausing'} onClick={()=>command('pause')}><Icon name="pause" size={14}/>Pause</button>
            <button disabled={busy||control.status!=='paused'} onClick={()=>command('resume')}><Icon name="play" size={14}/>Resume</button>
            <button className="stop-run" disabled={busy||control.status==='stopping'} onClick={()=>command('stop')}>Stop & save</button>
          </>}
          {ended&&<button disabled={busy||saved} onClick={save}>{saved?'Saved':data?.source.status==='completed'?'Save replay':'Save partial'}</button>}
          {(ended||(data&&!ended&&!control.controllable))&&<button onClick={newSetup}>New run</button>}
        </div>
      </div>}
    </header>
    {!runId&&<section className="live-setup" aria-label="Set up a live run">
      <div className="setup-field"><span className="setup-label">Model</span><div className="seg" role="group" aria-label="Shopper model">
        <button aria-pressed={model==='gpt-6-luna'} onClick={()=>pickModel('gpt-6-luna')}>GPT-6 Luna</button>
        <button aria-pressed={model==='gpt-6.1-terra'} onClick={()=>pickModel('gpt-6.1-terra')}>GPT-6.1 Terra</button>
        <button aria-pressed={model==='qwen2.5-7b-pilot-mlx'} disabled={!mlxReady} title={mlxReady?'Your fine-tuned adapter, served locally on MLX':'Start the local Qwen MLX server to enable'} onClick={()=>pickModel('qwen2.5-7b-pilot-mlx')}>Qwen fine-tuned</button>
      </div></div>
      <div className="setup-field"><span className="setup-label">Store layout</span><div className="seg" role="group" aria-label="Live layout">
        <button aria-pressed={layout==='costco_back_anchor'} onClick={()=>pickLayout('costco_back_anchor')} title="Staples at the back: shoppers walk past more aisles">A · Anchor loop</button>
        <button aria-pressed={layout==='neighborhood_express'} onClick={()=>pickLayout('neighborhood_express')} title="Essentials near the front: shorter trips">B · Express</button>
      </div></div>
      <div className="setup-field"><span className="setup-label">Shoppers</span><div className="stepper" role="group" aria-label="Live shopper count">
        <button aria-label="Fewer shoppers" disabled={count<=10} onClick={()=>pickCount(count-1)}>−</button>
        <span>{count}</span>
        <button aria-label="More shoppers" disabled={count>=15} onClick={()=>pickCount(count+1)}>+</button>
      </div></div>
      <div className="setup-summary">
        <p><span>{localMps?'Runs on this Mac. No API fee, but a full trip takes a while.':'Each decision is one paid request, so a full trip is several hundred.'}</span></p>
        {confirming?<div className="setup-confirm" role="group" aria-label="Confirm paid run"><span>Start a paid run?</span><button className="product-primary" disabled={busy} onClick={start}>Yes, start</button><button onClick={()=>setConfirming(false)}>Cancel</button></div>
          :<button className="product-primary" disabled={!serviceReady||busy||activeRun||(model==='qwen2.5-7b-pilot-mps'&&!mpsReady)||(model==='qwen2.5-7b-pilot-mlx'&&!mlxReady)} onClick={()=>localMps?start():setConfirming(true)}><Icon name="play" size={15}/>{busy?'Starting…':'Start run'}</button>}
      </div>
    </section>}
    {accounting&&!localMps&&runId&&<p className="lab-note api-accounting" role="status">${accounting.known_estimated_usd.toFixed(4)} spent so far · no spending cap</p>}
    {endNotice&&<section className={`live-end-notice ${endNotice.warning?'is-warning':''}`} role="status"><strong>{endNotice.title}</strong><p>{endNotice.detail}</p></section>}
    {!activeRun&&!runId&&runs.length>0&&<details className="lab-history"><summary>Recent runs <span>{runs.length}</span></summary><div className="lab-picker" role="group" aria-label="Follow Python run">{runs.slice(0,8).map(run=><button key={run.run_id} aria-pressed={run.run_id===runId} onClick={()=>followRun(run)}>{layoutShort(run.layout_id)} · {modelName(run.model)} · {run.status} · {run.run_id.slice(0,8)}</button>)}</div></details>}
    {serviceReady===false&&<div className="live-banner" role="alert">The live service is offline. <Link href="/replays">Watch saved replays instead</Link></div>}
    {error&&<div className="live-banner" role="alert">{error}</div>}
    {data&&data.source.run_id===runId?<ReplayWorkspace key={runId} live={{data,connection,controlStatus:control.status}}/>:preview&&!runId?<ReplayWorkspace live={{data:preview,connection:'preview',preview:true}}/>:<div className="replay-empty"><h2>{runId?'Connecting to this run…':serviceReady===false?'Live service unavailable':'Loading store preview…'}</h2><p>{runId?'Restoring the saved state of this run.':serviceReady===false?'Saved replays work without it.':'A model is called only when you start a run.'}</p>{serviceReady===false&&!runId&&<Link className="product-primary" href="/replays">Watch replays <Icon name="arrow" size={16}/></Link>}</div>}
  </>;
}
