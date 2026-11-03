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
 assert.equal(data.coverage.retained_runs,13);assert.equal(data.coverage.retained_trips,130);
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
 const ui=compile('ui/EvidenceDashboard.tsx',{
  react:{useState:value=>[states.length?states.shift():value,()=>{}],useEffect:()=>{}},
  'react/jsx-runtime':require('react/jsx-runtime'),'../lib/dashboard':reader,'../lib/recordings':{},'../lib/evidence':history,
 });
 states=['matched_first',false];
 const html=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 assert.match(html,/GPT-6 Luna/);assert.match(html,/GPT-6[.]1 Terra/);assert.match(html,/Qwen3-4B-Instruct-2507/);assert.match(html,/Qwen 4B · fine-tuned/);
 assert.match(html,/4 recorded runs · 40 simulated trips/);assert.match(html,/1 run · 10 trips/);assert.match(html,/N\/A/);
 assert.match(html,/\$0[.]5454/);assert.match(html,/\$4[.]8757/);assert.match(html,/13 retained runs · 130 attempted trips/);
 assert.match(html,/Distribution measure/);assert.match(html,/Source|source|Original recording/);
 states=['all_attempts',true];
 const all=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 assert.match(all,/8 recorded runs · 80 simulated trips/);assert.match(all,/Unknown/);assert.match(all,/1 interrupted/);
 assert.match(all,/Input tokens \/ run/);assert.match(all,/Request latency/);
 states=['qwen_baseline',true];
 const pending=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 assert.match(pending,/Qwen2[.]5 7B Instruct/);assert.match(pending,/OpenRouter \/ Phala/);
 assert.match(pending,/Collection has not started/);assert.match(pending,/0 recorded runs · 0 simulated trips/);
 assert.match(pending,/OpenRouter-reported charge/);assert.match(pending,/N\/A/);
 // Explicit offline fixture exercises the measured Qwen reader and React path.
 const measured=JSON.parse(text),qview=measured.views.find(v=>v.id==='qwen_baseline');
 const source=measured.runs.find(r=>r.group==='openrouter');
 source.group='qwen_baseline';source.model='qwen2.5-7b-instruct';
 const model=qview.models[0];model.status='recorded';
 const c=model.cells[source.layout_id];
 Object.assign(c,{status:'recorded',runs:1,trips:10,finished:0,requested:source.points.reduce((n,p)=>n+p.requested,0),purchased:0,stopped_runs:1,run_ids:[source.run_id]});
 c.metrics.checkout_completion=0;c.metrics.provider_reported_cost_per_run_usd=.001;
 qview.runs=1;qview.trips=10;
 const measuredText=JSON.stringify(measured),decoded=await reader.decodeDashboard(measuredText,entry(measuredText));
 states=['qwen_baseline',true];
 const qhtml=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data:decoded}));
 assert.match(qhtml,/Measured · OpenRouter \/ Phala/);assert.match(qhtml,/\$0[.]0010/);assert.match(qhtml,/1 recorded runs · 10 simulated trips/);
 source.group='main';const mixed=JSON.stringify(measured);
 await assert.rejects(reader.decodeDashboard(mixed,entry(mixed)));
 console.log('Dashboard passed: real source coverage, four-row model hierarchy, measured versus N/A/unknown, all-attempt controls and React rendering. No model calls.');
})().catch(error=>{console.error(error);process.exitCode=1;});
