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
 const entry=value=>({url:index.dashboard.url,sha256:crypto.createHash('sha256').update(value).digest('hex')});
 // Integrity and coverage.
 assert.equal(data.coverage.retained_runs,data.runs.length);assert.equal(data.coverage.retained_trips,data.runs.length*10);
 assert(data.coverage.groups.every(g=>g.runs>0),'Empty evidence groups must not be listed');
 assert(data.measures.some(m=>m.id==='impulse_units_per_trip')&&data.distribution_measures.some(m=>m.id==='impulse'),'Impulse measures missing');
 await assert.rejects(reader.decodeDashboard(text+' ',index.dashboard));
 // The default view is the latest OpenRouter collection: Luna/Terra under guided_nav_v3 plus the earlier untuned Qwen baseline.
 assert.equal(data.default_view,'openrouter_v3');const view=data.views.find(v=>v.id==='openrouter_v3');
 assert.equal(view.models.map(m=>m.id).join(','),'gpt-6-luna,gpt-6.1-terra,qwen2.5-7b-instruct');
 assert.equal(view.runs,6);assert.equal(view.trips,60);assert(view.highlights.length===3,'Python highlights missing');
 for(const model of view.models)for(const layout of data.layouts){
  const c=model.cells[layout.id];assert.equal(c.status,'recorded');assert.equal(c.runs,1);assert.equal(c.trips,10);assert.equal(c.stopped_runs,0);
  const run=data.runs.find(r=>r.run_id===c.run_ids[0]);assert.equal(run.status,'completed');assert.equal(run.points.length,10);
  assert.equal(run.group,model.id==='qwen2.5-7b-instruct'?'qwen_baseline':'openrouter_v3');
  assert.equal(run.policy,model.id==='qwen2.5-7b-instruct'?'guided_nav_v2':'guided_nav_v3');assert.equal(run.shopping_rules,'unique_single_checkout_v1');
  assert.equal(run.provider,'openrouter');assert.equal(c.finished,run.points.filter(p=>p.finished).length);
 }
 // Retained but replaced attempts never enter the headline table.
 const retained=data.runs.filter(r=>r.group==='openrouter_v3');
 assert(retained.some(r=>r.status!=='completed'),'The aborted Luna attempt must stay retained');
 const counted=new Set(view.models.flatMap(m=>Object.values(m.cells).flatMap(c=>c.run_ids)));
 assert(retained.filter(r=>r.status!=='completed').every(r=>!counted.has(r.run_id)),'Aborted attempt counted in headline table');
 assert.match(view.note,/ended early/);
 // Tampering is rejected by the strict reader.
 const wrong=JSON.parse(text);wrong.views.find(v=>v.id==='openrouter_v3').models[0].cells.costco_back_anchor.run_ids=[data.runs.find(r=>r.group==='qwen_baseline').run_id];
 const wrongText=JSON.stringify(wrong);await assert.rejects(reader.decodeDashboard(wrongText,entry(wrongText)));
 const fake=JSON.parse(text);fake.views.find(v=>v.id==='openrouter_v3').models[1].status='not_evaluated';
 const fakeText=JSON.stringify(fake);await assert.rejects(reader.decodeDashboard(fakeText,entry(fakeText)));
 const scope=JSON.parse(text);scope.runs.find(r=>r.group==='openrouter_v3'&&r.model==='gpt-6-luna'&&r.status==='completed').group='main';
 const scopeText=JSON.stringify(scope);await assert.rejects(reader.decodeDashboard(scopeText,entry(scopeText)));
 const policy=JSON.parse(text);policy.runs.find(r=>r.group==='openrouter_v3'&&r.status==='completed').policy='guided_nav_v2';
 const policyText=JSON.stringify(policy);await assert.rejects(reader.decodeDashboard(policyText,entry(policyText)));
 // React output.
 const history=compile('lib/evidence.ts',{'./replay':replay,'./recordings':{}});
 const chartsUI=compile('ui/EvidenceCharts.tsx',{'react/jsx-runtime':require('react/jsx-runtime'),'../lib/evidence':history});
 const ui=compile('ui/EvidenceDashboard.tsx',{react:{useState:value=>[value,()=>{}],useEffect:()=>{}},'react/jsx-runtime':require('react/jsx-runtime'),
  '../lib/dashboard':reader,'../lib/recordings':{},'../lib/evidence':history,'./EvidenceCharts':chartsUI});
 const html=renderer.renderToStaticMarkup(React.createElement(ui.DashboardContent,{data}));
 for(const pattern of [/Results at a glance/,/What the runs show/,/GPT-6 Luna/,/GPT-6[.]1 Terra/,/Qwen2[.]5 7B Instruct/,/guided_nav_v2/,/guided_nav_v3/,/6 recorded runs · 60 simulated trips/,
  /Impulse buys per trip/,/Higher is better/,/Unplanned purchases/,/OpenRouter-reported charge/,/Recordings behind this table/,/not a same-conditions comparison/])assert.match(html,pattern);
 for(const pattern of [/Exact run distributions/,/Distribution measure/,/Study archive/,/Local MLX/,/Local MPS/])assert.doesNotMatch(html,pattern);
 // Python numbers appear exactly as exported.
 for(const model of view.models)for(const layout of data.layouts){const c=model.cells[layout.id];
  assert.ok(html.includes(`${c.finished}/${c.trips} checked out`));assert.ok(html.includes(`${c.purchased}/${c.requested} requested units paid`));}
 // Local pilot progress reader stays strict (used by the lab, not by this page).
 const progressReader=compile('lib/pilot-progress.ts');
 const progress=progressReader.decodePilotProgress({progress_version:1,available:true,study_id:'a'.repeat(32),protocol_sha256:'b'.repeat(64),scheduled_runs:2,completed_runs:0,runs:[
 {layout_id:'neighborhood_express',model:'qwen2.5-7b-pilot-mps',status:'recording',decision_count:16,finished_count:0,shopper_count:10,run_id:'c'.repeat(32)},
 {layout_id:'costco_back_anchor',model:'qwen2.5-7b-pilot-mps',status:'queued',decision_count:0,finished_count:0,shopper_count:10,run_id:null}]});
 assert.throws(()=>progressReader.decodePilotProgress({...progress,completed_runs:2}));
 console.log('Dashboard passed: source coverage, latest-run view, retained-but-excluded attempts, tamper rejection and compact React rendering. No model calls.');
})().catch(error=>{console.error(error);process.exitCode=1;});
