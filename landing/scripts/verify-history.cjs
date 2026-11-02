/* Verify Python-authored history metrics, differences, integrity and offline delivery. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict'),ts=require('typescript');
const root=path.resolve(__dirname,'..');
function compile(file,deps={},extras={}){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'lib',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,TextEncoder,crypto:crypto.webcrypto,AbortSignal,require:name=>{assert(name in deps);return deps[name];},...extras});return exports;}
(async()=>{
 const catalog=JSON.parse(fs.readFileSync(path.join(root,'public/replays/index.json')));
 if(!catalog.history){console.log('No exported run history; the page must retain its empty state.');return;}
 const text=fs.readFileSync(path.join(root,'public',catalog.history.url),'utf8');
 const replay=compile('replay.ts');let local='offline';
 const history=compile('evidence.ts',{'./replay':replay,'./recordings':{loadCatalog:async()=>catalog}},{fetch:async url=>url==='/api/simulation/evidence'?{ok:local!=='offline',status:local==='offline'?503:200,text:async()=>local==='corrupt'?'{}':text}:{ok:true,text:async()=>text}});
 const data=await history.decodeHistory(text,catalog.history.sha256);
 assert.equal(data.counts.model_runs,data.runs.filter(r=>r.kind==='model').length);
 assert.equal(data.counts.fixtures,data.runs.filter(r=>r.kind==='fixture').length);
 for(const baseline of data.runs){
  for(const row of data.runs){
   const comparison=data.comparisons[baseline.run_id].find(c=>c.run_id===row.run_id);
   assert(comparison);
   for(const key of Object.keys(data.metric_definitions)){
    const comparableCost=key!=='known_estimated_cost_usd'||(baseline.cost_complete&&row.cost_complete);
    const a=comparableCost?baseline.metrics[key]:null,b=comparableCost?row.metrics[key]:null;
    assert.equal(comparison.differences[key].absolute,a===null||b===null?null:b-a);
    const expected=a===null||b===null||a===0?null:(b-a)/Math.abs(a)*100;
    if(expected===null)assert.equal(comparison.differences[key].relative_percent,null);
    else assert(Math.abs(expected-comparison.differences[key].relative_percent)<1e-9);
   }
   if(row.kind==='fixture'||baseline.kind==='fixture')assert.equal(comparison.matched_controls,false);
  }
  if(!baseline.finished_count||!baseline.cost_complete)assert.equal(baseline.metrics.cost_per_completed_trip_usd,null);
 }
 await assert.rejects(history.decodeHistory(text+' ',catalog.history.sha256));
 const duplicate=JSON.parse(text);if(duplicate.runs.length){duplicate.runs.push(duplicate.runs[0]);await assert.rejects(history.decodeHistory(JSON.stringify(duplicate)));}
 const offline=await history.loadHistory();assert.equal(offline.local,false);
 local='online';assert.equal((await history.loadHistory()).local,true);
 local='corrupt';await assert.rejects(history.loadHistory(),'Corrupt local data must not be silently replaced by an older public snapshot');
 assert.equal(history.formatHistoryMetric(.03125,'rate',true),'+3.1 pp');
 assert.equal(history.formatHistoryMetric(-718,'cents',true),'-$7.18');
 assert.equal(history.formatHistoryMetric(null,'usd'),'Unknown');
 if(data.runs.length){
  const React=require('../node_modules/react'),renderer=require('../node_modules/react-dom/server');
  const sorted=[...data.runs].sort((a,b)=>b.recorded_at.localeCompare(a.recorded_at));
  let index=0;const states=[{history:data,local:false},'',0,sorted[1]?.run_id??sorted[0].run_id,sorted[0].run_id];
  const View=compile('../ui/RunHistory.tsx',{
   react:{useState:()=>[states[index++],()=>{}],useEffect:()=>{}},
   'react/jsx-runtime':require('../node_modules/react/jsx-runtime'),'../lib/evidence':history,'./Icons':{Icon:()=>null},
  }).default;
  const html=renderer.renderToStaticMarkup(React.createElement(View));
  const main=html.split('<details')[0];
  assert.equal((main.match(/class="evidence-run-card"/g)??[]).length,Math.min(2,data.runs.length));
  assert.equal((main.match(/<tr>/g)??[]).length,7,'Only six primary measures should be shown by default');
  assert.match(html,/<details class="evidence-details"><summary>Diagnostics &amp; source recordings/);
  assert(!main.includes('SHA-256'),'Source hashes belong in collapsed diagnostics');
  assert(!main.includes('Different settings / scope'),'Comparison limits should use plain-language context');
 }
 console.log(`History contract passed: ${data.runs.length} real/fixture records, all pairwise differences, unknown costs, integrity and offline delivery.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
