/* Live messages and saved replay must present the same Python evidence. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process'),ts=require('typescript');
const root=path.resolve(__dirname,'../..');
function compile(file,deps={}){
  const exports={};const source=fs.readFileSync(path.join(root,'landing/lib',file),'utf8');
  vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports,TextEncoder,crypto:crypto.webcrypto,require:name=>{assert(name in deps);return deps[name];}});return exports;
}
const python=spawnSync(process.env.PYTHON??'python3',['-c',`
import sys,json
from pathlib import Path
sys.path.insert(0,'simulation')
from live.protocol import LiveProjection
p=LiveProjection()
for line in Path('simulation/tests/fixtures/golden.jsonl').read_bytes().splitlines(keepends=True):
 kind=p.append(line)
 message={'stream_version':1,'run':p.snapshot()} if kind=='run_start' else p.transition(kind=='run_end')
 print(json.dumps({'kind':kind,'message':message}))
`],{cwd:root,encoding:'utf8',maxBuffer:20*1024*1024});
assert.equal(python.status,0,python.stderr);
const replay=compile('replay.ts'),live=compile('live.ts',{'./replay':replay});
const expected=JSON.parse(fs.readFileSync(path.join(root,'simulation/tests/fixtures/golden.expected.json')));
let current,first;
const normal=v=>JSON.parse(JSON.stringify(v));
for(const line of python.stdout.trim().split('\n')){
  const {kind,message}=JSON.parse(line);
  if(kind==='run_start')current=live.liveSnapshot(message);
  else{
    const previous=current;current=live.liveTransition(current,message);
    if(kind==='decision'){
      first??=message;
      assert.throws(()=>live.liveTransition(current,message),'Duplicate live event accepted');
      assert.throws(()=>live.liveTransition(previous,{...message,source:{...message.source,run_id:'other'}}),'Wrong live identity accepted');
    }
  }
  const sequence=current.events.length;
  if(kind!=='decision'||sequence<expected.length-1)assert.deepEqual(normal(current.final),expected[sequence]);
}
assert.equal(current.source.status,'completed');
const resynced=live.liveSnapshot({stream_version:1,run:current},current);
assert.deepEqual(normal(resynced.final),expected.at(-1));
assert.throws(()=>live.liveSnapshot({stream_version:999,run:current}));
assert.throws(()=>live.liveSnapshot({stream_version:1,run:{...current,source:{...current.source,model:'other'}}},current));
assert.throws(()=>live.liveTransition({...current,events:[]},first));
console.log(`Live contract passed: ${expected.length} Python states, incremental commits, duplicate/identity rejection, reconnect, and final replay equivalence.`);
