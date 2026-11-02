/* Offline matrix -> integrity-checked metrics -> actual React summary. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const cp=require('node:child_process'),crypto=require('node:crypto'),assert=require('node:assert/strict'),ts=require('typescript');
const root=path.resolve(__dirname,'../..'),directory=fs.mkdtempSync(path.join(os.tmpdir(),'simply-matrix-'));
function compile(file,dependencies={}){
 const exports={};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'landing',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
  {exports,TextEncoder,crypto:crypto.webcrypto,require:name=>{assert(name in dependencies,`Unexpected import ${name}`);return dependencies[name];}});
 return exports;
}
(async()=>{
 const python=fs.existsSync(path.join(root,'.venv/bin/python'))?path.join(root,'.venv/bin/python'):'python';
 const output=cp.spawnSync(python,['-c',[
  'import sys,socket', 'from pathlib import Path', 'from unittest.mock import patch',
  'sys.path.insert(0,"simulation/tests")',
  'from test_matrix_study import MatrixStudyTests', 'from evaluation import matrix,study',
  'socket.socket.connect=lambda *args: (_ for _ in ()).throw(AssertionError("No network"))',
  'root=Path(sys.argv[1]);original=study.prepare',
  'def short(directory,**kwargs):return original(directory,**kwargs,turn_budget=2)',
  'with patch("evaluation.matrix.study.prepare",short):matrix.prepare(root/"experiment",repetitions=1)',
  'with patch("agents.openai_provider.OpenAIProvider._request",MatrixStudyTests.fixture),patch("evaluation.study.DECISION_RUNS_DIR",root/"accounting"):matrix.execute(root/"experiment")',
 ].join('\n'),directory],{cwd:root,encoding:'utf8'});
 assert.equal(output.status,0,output.stderr||output.stdout);
 const replay=compile('lib/replay.ts'),reader=compile('lib/matrix.ts',{'./replay':replay});
 const text=fs.readFileSync(path.join(directory,'experiment/matrix-report.json'),'utf8');
 const raw=JSON.parse(text),entry={url:`/replays/matrix-${raw.study_id}.json`,protocol_url:`/replays/matrix-${raw.study_id}.protocol.json`,sha256:crypto.createHash('sha256').update(text).digest('hex')};
 const report=await reader.decodeMatrix(text,entry);
 assert.equal(report.conditions.length,4);assert.equal(report.comparisons.length,4);
 assert.equal(report.conditions[0].trips,10);assert.equal(report.conditions[0].finished,0);
 assert.equal(report.conditions[0].metrics.cost_per_completed_trip_usd,null);
 assert.equal(report.comparisons[1].profile_pairs.length,10);
 assert.equal(report.comparisons[1].profile_pairs[0].baseline.checkout_completion,0);
 await assert.rejects(reader.decodeMatrix(text+' ',entry));
 const changed=value=>{const text=JSON.stringify(value);return reader.decodeMatrix(text,{...entry,sha256:crypto.createHash('sha256').update(text).digest('hex')});};
 await assert.rejects(changed({...report,conditions:[report.conditions[0],...report.conditions.slice(0,3)]}));
 const missing=JSON.parse(text);delete missing.conditions[0].metrics.purchased_unit_fulfillment;await assert.rejects(changed(missing));
 const invalid=JSON.parse(text);invalid.comparisons[0].metrics.checkout_completion.ci95=[1,0];await assert.rejects(changed(invalid));
 const wrongSource=JSON.parse(text);wrongSource.comparisons[0].profile_pairs[0].baseline_run_id='missing';await assert.rejects(changed(wrongSource));
 const duplicates=JSON.parse(text);duplicates.runs[0].audit.profiles[1]=duplicates.runs[0].audit.profiles[0];await assert.rejects(changed(duplicates));
 const React=require('../node_modules/react'),renderer=require('../node_modules/react-dom/server');
 const history=compile('lib/evidence.ts',{'./replay':replay,'./recordings':{}});
 let index=0;const states=[{report,entry},'',[], ''];
 const profiles=compile('ui/ProfileComparisons.tsx',{
  react:{useState:value=>[value,()=>{}]},'react/jsx-runtime':require('../node_modules/react/jsx-runtime'),
  '../lib/evidence':history,
 }).default;
 const component=compile('ui/MatrixResults.tsx',{
  react:{useState:()=>[states[index++],()=>{}],useEffect:()=>{}},'react/jsx-runtime':require('../node_modules/react/jsx-runtime'),
  '../lib/recordings':{},'../lib/matrix':reader,'../lib/evidence':history,
  './ProfileComparisons':{default:profiles},
 }).default;
 const html=renderer.renderToStaticMarkup(React.createElement(component));
 assert.match(html,/Luna · Layout A/);assert.match(html,/Terra · Layout B/);
 assert.match(html,/1 repetitions/);assert.match(html,/0\/10 checked out/);
 assert.match(html,/Unknown/);assert.match(html,/Scope &amp; verification/);assert.match(html,/Insufficient complete pairs/);
 assert.match(html,/Outcome versus effort/);assert.match(html,/Paired effort difference/);assert.match(html,/10 matched profiles/);
 assert.match(html,/requested products paid/);assert.match(html,/Trip API estimate/);assert.match(html,/\.source.jsonl/);
 console.log('Matrix contract passed: four frozen conditions, incomplete/unknown outcomes, source integrity, matched contrasts and actual React rendering. No API calls.');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>fs.rmSync(directory,{recursive:true,force:true}));
