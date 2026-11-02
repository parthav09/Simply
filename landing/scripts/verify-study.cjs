/* Offline Python study -> published report -> actual React report rendering. */
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm');
const crypto=require('node:crypto'),assert=require('node:assert/strict'),cp=require('node:child_process'),ts=require('typescript');
const root=path.resolve(__dirname,'../..'),directory=fs.mkdtempSync(path.join(os.tmpdir(),'simply-study-contract-'));
function compile(file,dependencies={}){
 const exports={};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'landing',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
  {exports,TextEncoder,crypto:crypto.webcrypto,require:name=>{assert(name in dependencies,`Unexpected import ${name}`);return dependencies[name];}});
 return exports;
}
(async()=>{
 const python=fs.existsSync(path.join(root,'.venv/bin/python'))?path.join(root,'.venv/bin/python'):'python';
 const result=cp.spawnSync(python,['-c',[
  'import sys,socket',
  'from pathlib import Path',
  'from simulation.evaluation.study import prepare,execute,publish',
  'socket.socket.connect=lambda *args: (_ for _ in ()).throw(AssertionError("No network in offline study verification"))',
  'root=Path(sys.argv[1])',
  'prepare(root,provider="fake",repetitions=5,turn_budget=3)',
  'execute(root)',
  'publish(root,root/"public",allow_test=True)',
  'import json',
  'from simulation.tests.test_simple_shopping import SimpleShoppingTests',
  'from core.export_replay import export_run',
  'from live.protocol import LiveProjection',
  'case=SimpleShoppingTests();case.setUp()',
  'try:',
  ' for layout in ("costco_back_anchor","neighborhood_express"):',
  '  session,provider,product=case.setup_trip(layout);session.run()',
  '  destination=root/layout;export_run(session.path,destination,allow_test=True)',
  '  projection=LiveProjection();messages=[]',
  '  for line in session.path.read_bytes().splitlines(keepends=True):',
  '   kind=projection.append(line)',
  '   message={"stream_version":1,"run":projection.snapshot()} if kind=="run_start" else projection.transition(kind=="run_end")',
  '   messages.append({"kind":kind,"message":message,"frame":projection.snapshot()["final"]})',
  '  (destination/"messages.json").write_text(json.dumps(messages))',
  'finally:case.doCleanups()',
 ].join('\n'),directory],{cwd:root,encoding:'utf8'});
 assert.equal(result.status,0,result.stderr||result.stdout);
 const replay=compile('lib/replay.ts'),reader=compile('lib/report.ts',{'./replay':replay});
 const live=compile('lib/live.ts',{'./replay':replay});
 const normal=value=>JSON.parse(JSON.stringify(value));
 for(const layout of ['costco_back_anchor','neighborhood_express']){
  const destination=path.join(directory,layout),catalog=JSON.parse(fs.readFileSync(path.join(destination,'index.json')));
  const entry=catalog.runs[0],bundle=await replay.decodeReplay(fs.readFileSync(path.join(destination,path.basename(entry.url)),'utf8'),entry);
  let current;
  for(const {kind,message,frame} of JSON.parse(fs.readFileSync(path.join(destination,'messages.json')))){
   current=kind==='run_start'?live.liveSnapshot(message):live.liveTransition(current,message);
   assert.deepEqual(normal(current.final),frame);
  }
  assert.deepEqual(normal(current.final),normal(bundle.final));
  assert.equal(bundle.config.shopping_rules,'unique_single_checkout_v1');
  assert.equal(bundle.summary.finished_count,1);
  assert.equal(bundle.events.filter(event=>event.action?.step==='checkout').length,1);
  assert(bundle.events.every(event=>event.after.phase!=='CheckoutState'));
  assert(bundle.summary.shoppers[0].checkout_overshoot_cents>0);
 }
 const catalog=JSON.parse(fs.readFileSync(path.join(directory,'public/index.json')));
 const entry=catalog.reports[0],text=fs.readFileSync(path.join(directory,'public',path.basename(entry.url)),'utf8');
 const report=await reader.decodeReport(text,entry);
 assert.equal(report.study_kind,'layout');assert.equal(report.provider,'fake');assert.equal(report.runs.length,10);
 assert.equal(report.arms[0].recorded_runs,5);assert.equal(report.runs[0].finished_count,0);
 assert(report.arms.every(arm=>arm.metrics.checkout_completion===0));
 assert(report.paired.find(row=>row.metric==='checkout_completion').ci95);
 assert.equal(report.paired.find(row=>row.metric==='cost_per_completed_trip_usd').mean_difference,null);
 assert('overspending_fraction' in report.arms[0].metrics&&'request_latency_p95_ms' in report.arms[0].metrics);
 await assert.rejects(reader.decodeReport(text+' ',entry));
 const changed=value=>{const text=JSON.stringify(value);return reader.decodeReport(text,{...entry,sha256:crypto.createHash('sha256').update(text).digest('hex')});};
 await assert.rejects(changed({...report,protocol_sha256:'wrong'}));
 await assert.rejects(changed({...report,arms:[{...report.arms[0],recorded_runs:0},report.arms[1]]}));
 await assert.rejects(changed({...report,protocol_url:'https://untrusted.example/protocol.json'}));
 const React=require('../node_modules/react'),renderer=require('../node_modules/react-dom/server');
 function render(value){
  let index=0;const states=[true,0,[entry],entry.url,value,'',`${entry.url}:${entry.sha256}`];
  const component=compile('ui/ExperimentReport.tsx',{
   react:{useState:()=>[states[index++],()=>{}],useEffect:()=>{}},
   'react/jsx-runtime':require('../node_modules/react/jsx-runtime'),
   'next/link':{default:props=>React.createElement('a',props)},'./Icons':{Icon:()=>null},
   '../lib/recordings':{},'../lib/report':reader,
  }).default;
  return renderer.renderToStaticMarkup(React.createElement(component));
 }
 const html=render(report);
 assert.match(html,/Offline test report/);assert.match(html,/5 completed runs/);
 assert.match(html,/all shoppers/);assert.match(html,/missing measurements/);
 assert.match(html,/Off-list units purchased/);assert.match(html,/Download frozen study protocol/);
 assert.match(render({...report,study_kind:'model'}),/Repeated model evaluation/);
 assert.match(render({...report,study_kind:'assistance'}),/Repeated navigation assistance evaluation/);
 assert.match(render({...report,repetitions:1}),/Single-pair layout evaluation/);
 console.log('Study contract passed: repeated pairs, unknown costs, protocol integrity, report rendering, and single-checkout Python/React live/replay equivalence in both layouts. No API calls.');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>fs.rmSync(directory,{recursive:true,force:true}));
