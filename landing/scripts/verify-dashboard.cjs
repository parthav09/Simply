/* Validate source-backed dashboard -> strict reader -> actual React output. No APIs. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const ts=require('typescript'),React=require('react'),renderer=require('react-dom/server');
const root=path.resolve(__dirname,'..');
function compile(file,dependencies={}){
 const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
 {exports,TextEncoder,crypto:crypto.webcrypto,require:name=>{assert(name in dependencies,`Unexpected import ${name}`);return dependencies[name];}});return exports;
}
(async()=>{
 const index=JSON.parse(fs.readFileSync(path.join(root,'public/replays/index.json'),'utf8'));
 const text=fs.readFileSync(path.join(root,'public/replays/evidence-dashboard.json'),'utf8');
 const replay=compile('lib/replay.ts'),reader=compile('lib/dashboard.ts',{'./replay':replay});
 const data=await reader.decodeDashboard(text,index.dashboard);
 const qwenRuns=data.runs.filter(r=>r.group==='qwen_baseline');
 const pilotRuns=data.runs.filter(r=>r.group==='qwen_pilot');
 const mlxRuns=data.runs.filter(r=>r.group==='qwen_mlx');
 const localRuns=data.runs.filter(r=>r.group==='local_mps');
 assert.equal(data.coverage.retained_runs,13+qwenRuns.length+pilotRuns.length+mlxRuns.length+localRuns.length);assert.equal(data.coverage.retained_trips,130+(qwenRuns.length+pilotRuns.length+mlxRuns.length+localRuns.length)*10);
 assert.equal(data.views[0].runs,4);assert.equal(data.views[0].trips,40);
 assert.equal(data.views[1].runs,7);assert.equal(data.views[2].runs,8);
 const entry=value=>({url:index.dashboard.url,sha256:crypto.createHash('sha256').update(value).digest('hex')});
 await assert.rejects(reader.decodeDashboard(text+' ',index.dashboard));
 const fake=JSON.parse(text);fake.views[0].models[2].cells.costco_back_anchor.metrics.checkout_completion=0;
 const fakeText=JSON.stringify(fake);await assert.rejects(reader.decodeDashboard(fakeText,entry(fakeText)));
 const wrong=JSON.parse(text);wrong.views[0].models[0].cells.costco_back_anchor.run_ids=[data.runs.find(r=>r.group==='openrouter').run_id];
 const wrongText=JSON.stringify(wrong);await assert.rejects(reader.decodeDashboard(wrongText,entry(wrongText)));
 const history=compile('lib/evidence.ts',{'./replay':replay,'./recordings':{}});
 let states=[];
 const progressReader=compile('lib/pilot-progress.ts');
 const progressUI=compile('ui/PilotProgress.tsx',{react:{useState:value=>[states.length?states.shift():value,()=>{}],useEffect:()=>{}},'react/jsx-runtime':require('react/jsx-runtime'),'../lib/pilot-progress':progressReader});
 const ui=compile('ui/EvidenceDashboard.tsx',{
  react:{useState:value=>[states.length?states.shift():value,()=>{}],useEffect:()=>{}},
  'react/jsx-runtime':require('react/jsx-runtime'),'../lib/dashboard':reader,'../lib/recordings':{},'../lib/evidence':history,'./PilotProgress':progressUI,'../lib/pilot-progress':progressReader,
 });
 states=['matched_first',false];
 const html=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 assert.match(html,/GPT-6 Luna/);assert.match(html,/GPT-6[.]1 Terra/);assert.match(html,/Qwen3-4B-Instruct-2507/);assert.match(html,/Qwen 4B · fine-tuned/);
 assert.match(html,/4 recorded runs · 40 simulated trips/);assert.match(html,/1 run · 10 trips/);assert.match(html,/N\/A/);
 assert.match(html,/\$0[.]5454/);assert.match(html,/\$4[.]8757/);assert.ok(html.includes(`${data.coverage.retained_runs} retained runs · ${data.coverage.retained_trips} attempted trips`));
 assert.match(html,/Distribution measure/);assert.match(html,/Source|source|Original recording/);
 states=['all_attempts',true];
 const all=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 assert.match(all,/8 recorded runs · 80 simulated trips/);assert.match(all,/Unknown/);assert.match(all,/1 interrupted/);
 assert.match(all,/Input tokens \/ run/);assert.match(all,/Request latency/);
 states=['qwen_baseline',true];
 const pending=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 assert.match(pending,/Qwen2[.]5 7B Instruct/);assert.match(pending,/OpenRouter \/ Phala/);
 if(qwenRuns.length)assert.match(pending,/Measured · OpenRouter \/ Phala/);else assert.match(pending,/Collection has not started/);
 assert.ok(pending.includes(`${4+qwenRuns.length+pilotRuns.length+mlxRuns.length} recorded runs · ${40+(qwenRuns.length+pilotRuns.length+mlxRuns.length)*10} simulated trips`));
 assert.match(pending,/GPT-6 Luna/);assert.match(pending,/GPT-6[.]1 Terra/);
 assert.match(pending,/OpenRouter-reported charge/);assert.match(pending,/N\/A/);
 // Explicit offline fixture exercises the measured Qwen reader and React path.
 const measured=JSON.parse(text),qview=measured.views.find(v=>v.id==='qwen_baseline');
 const source=measured.runs.find(r=>r.group==='openrouter');
 source.group='qwen_baseline';source.model='qwen2.5-7b-instruct';
 const model=qview.models[2];model.status='recorded';
 for(const cell of Object.values(model.cells)){Object.assign(cell,{status:'missing',runs:0,trips:0,finished:0,requested:0,purchased:0,stopped_runs:0,run_ids:[]});for(const key of Object.keys(cell.metrics))cell.metrics[key]=null;}
 const c=model.cells[source.layout_id];
 Object.assign(c,{status:'recorded',runs:1,trips:10,finished:0,requested:source.points.reduce((n,p)=>n+p.requested,0),purchased:0,stopped_runs:1,run_ids:[source.run_id]});
 c.metrics.checkout_completion=0;c.metrics.provider_reported_cost_per_run_usd=.001;
 qview.runs=5+pilotRuns.length;qview.trips=50+pilotRuns.length*10;
 const measuredText=JSON.stringify(measured),decoded=await reader.decodeDashboard(measuredText,entry(measuredText));
 states=['qwen_baseline',true];
 const qhtml=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data:decoded}));
 assert.match(qhtml,/Measured · OpenRouter \/ Phala/);assert.match(qhtml,/\$0[.]0010/);assert.ok(qhtml.includes(`${5+pilotRuns.length} recorded runs · ${50+pilotRuns.length*10} simulated trips`));
 source.group='main';const mixed=JSON.stringify(measured);
 await assert.rejects(reader.decodeDashboard(mixed,entry(mixed)));
 const local=JSON.parse(text),localView=local.views.find(v=>v.id==='qwen_baseline');
 const localSource=local.runs.find(r=>r.group==='openrouter');
 Object.assign(localSource,{group:'qwen_pilot',provider:'local_mps',model:'qwen2.5-7b-pilot-mps'});
 const localModel=localView.models[3];localModel.status='recorded';
 for(const cell of Object.values(localModel.cells)){Object.assign(cell,{status:'missing',runs:0,trips:0,finished:0,requested:0,purchased:0,stopped_runs:0,run_ids:[]});for(const key of Object.keys(cell.metrics))cell.metrics[key]=null;}
 const lc=localModel.cells[localSource.layout_id];
 Object.assign(lc,{status:'recorded',runs:1,trips:10,finished:0,requested:localSource.points.reduce((n,p)=>n+p.requested,0),purchased:0,stopped_runs:1,run_ids:[localSource.run_id]});
 lc.metrics.estimated_cost_per_run_usd=0;
 localView.runs=5+qwenRuns.length;localView.trips=(5+qwenRuns.length)*10;
 const localText=JSON.stringify(local),localData=await reader.decodeDashboard(localText,entry(localText));
 states=['qwen_baseline',true];
 const localHtml=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data:localData}));
 assert.match(localHtml,/Measured · local MPS pilot/);assert.match(localHtml,/\$0[.]0000/);
 assert.match(localHtml,/hardware and compute costs are unmeasured/);
 localSource.group='local_mps';const unrelated=JSON.stringify(local);
 await assert.rejects(reader.decodeDashboard(unrelated,entry(unrelated)));
 if(localView.models.length===5){
  const mlx=JSON.parse(text),mv=mlx.views.find(v=>v.id==='qwen_baseline');
  const ms=mlx.runs.find(r=>r.group==='openrouter');Object.assign(ms,{group:'qwen_mlx',provider:'local_mps',model:'qwen2.5-7b-pilot-mlx'});
  const mm=mv.models[4];mm.status='recorded';const mc=mm.cells[ms.layout_id];
  Object.assign(mc,{status:'recorded',runs:1,trips:10,finished:0,requested:ms.points.reduce((n,p)=>n+p.requested,0),purchased:0,stopped_runs:1,run_ids:[ms.run_id]});
  const mt=JSON.stringify(mlx),decodedMlx=await reader.decodeDashboard(mt,entry(mt));
  states=['qwen_baseline',false];assert.match(renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data:decodedMlx})),/Measured · local MLX pilot/);
  ms.group='qwen_pilot';const badMlx=JSON.stringify(mlx);await assert.rejects(reader.decodeDashboard(badMlx,entry(badMlx)));
 }
 const continued=JSON.parse(text),original=continued.runs.find(r=>r.group==='qwen_mlx');
 if(original){
  const derived=JSON.parse(JSON.stringify(original));derived.run_id='e'.repeat(32);derived.source_sha256='f'.repeat(64);
  derived.source_url=`/replays/${derived.run_id}.source.jsonl`;derived.replay_url=`/replays/${derived.run_id}.json`;
  derived.group='local_mps';derived.continuation={source_run_id:original.run_id,source_sha256:original.source_sha256,source_event_count:354};
  continued.runs.push(derived);continued.coverage.retained_runs++;continued.coverage.retained_trips+=derived.points.length;
  const derivedText=JSON.stringify(continued),decoded=await reader.decodeDashboard(derivedText,entry(derivedText));
  states=['qwen_baseline',false];const rendered=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data:decoded}));
  assert.match(rendered,/Continued MLX pilot/);assert.match(rendered,/not an additional independent repetition/);
  derived.continuation.source_sha256='0'.repeat(64);const invalid=JSON.stringify(continued);
  await assert.rejects(reader.decodeDashboard(invalid,entry(invalid)));
 }
 const progress=progressReader.decodePilotProgress({progress_version:1,available:true,study_id:'a'.repeat(32),protocol_sha256:'b'.repeat(64),scheduled_runs:2,completed_runs:0,runs:[
 {layout_id:'neighborhood_express',model:'qwen2.5-7b-pilot-mps',status:'recording',decision_count:16,finished_count:0,shopper_count:10,run_id:'c'.repeat(32)},
 {layout_id:'costco_back_anchor',model:'qwen2.5-7b-pilot-mps',status:'queued',decision_count:0,finished_count:0,shopper_count:10,run_id:null}]});
 states=[progress,false];const progressHtml=renderer.renderToStaticMarkup(React.createElement(progressUI.default));
 assert.match(progressHtml,/16 decisions saved/);assert.match(progressHtml,/Queued/);assert.match(progressHtml,/after each run finishes/);
 assert.throws(()=>progressReader.decodePilotProgress({...progress,completed_runs:2}));
 states=['qwen_baseline',false,progress];
 const collecting=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 assert.match(collecting,/Recording/);assert.match(collecting,/16 decisions saved · final metrics pending/);
 assert.match(collecting,/Queued/);assert.match(collecting,/Run has not started/);
 assert.doesNotMatch(collecting,/No recording available/);
 assert.equal(progressReader.pilotCellLabel(progress.runs[0]).label,'Recording');
 assert.equal(progressReader.pilotCellLabel(progress.runs[1]).label,'Queued');
 assert.equal(progressReader.pilotCellLabel({...progress.runs[0],status:'completed'}).label,'Finished');
 console.log('Dashboard passed: real source coverage, four-row model hierarchy, measured versus N/A/unknown, all-attempt controls and React rendering. No model calls.');
})().catch(error=>{console.error(error);process.exitCode=1;});
