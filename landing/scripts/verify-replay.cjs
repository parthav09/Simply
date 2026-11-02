/* Cross-runtime acceptance: TypeScript must display Python's exact saved states. */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const ts=require('typescript');
const ROOT=path.resolve(__dirname,'..');
const fixture=path.resolve(ROOT,'../simulation/tests/fixtures');
const source=fs.readFileSync(path.join(ROOT,'lib/replay.ts'),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const exportsObject={};
vm.runInNewContext(js,{exports:exportsObject,TextEncoder,crypto:crypto.webcrypto,require},{filename:'replay.ts'});
const normal=value=>JSON.parse(JSON.stringify(value));
const envelopeText=fs.readFileSync(path.join(fixture,'golden.bundle.json'),'utf8');
const expected=JSON.parse(fs.readFileSync(path.join(fixture,'golden.expected.json'),'utf8'));
const hash=text=>crypto.createHash('sha256').update(text).digest('hex');
(async()=>{
  const data=await exportsObject.decodeReplay(envelopeText);
  const evidence=fs.readFileSync(path.join(fixture,'golden.jsonl'));
  assert.equal(data.source.sha256,crypto.createHash('sha256').update(evidence).digest('hex'));
  assert.equal(data.source.provider,'scripted_test','Fixtures cannot claim Gemini identity');
  const entry={...data.source,bundle_sha256:hash(envelopeText)};
  await exportsObject.decodeReplay(envelopeText,entry);
  for(let i=0;i<expected.length;i++)assert.deepEqual(normal(exportsObject.frameAt(data,i)),expected[i],`Backend/lab mismatch at event ${i}`);
  for(const i of [expected.length-1,0,3,1,expected.length-1])assert.deepEqual(normal(exportsObject.frameAt(data,i)),expected[i],`Seeking mismatch at event ${i}`);
  assert.throws(()=>exportsObject.frameAt(data,-1));
  assert.throws(()=>exportsObject.frameAt(data,.5));
  for(const mutate of [
    d=>d.events.splice(1,1),
    d=>d.events.splice(1,0,d.events[0]),
    d=>d.events.reverse(),
    d=>{d.events[0].after.x+=1;},
    d=>{d.final.states[d.shoppers[0].id].cart=[];},
    d=>{d.final.summary.sales_cents+=1;},
    d=>{d.initial.states.other=d.initial.states[d.shoppers[0].id];},
    d=>{d.events[0].shopper_metrics.agent_id='unknown';},
  ]){
    const changed=structuredClone(data);mutate(changed);
    assert.throws(()=>exportsObject.validateReplay(changed));
  }
  assert.throws(()=>exportsObject.validateReplay(data,{...entry,sha256:'0'.repeat(64)}));
  assert.throws(()=>exportsObject.validateReplay(data,{...entry,run_id:'other'}));
  const changed=JSON.parse(envelopeText);changed.payload_json=changed.payload_json.replace('Fixture purchase','Tampered explanation');
  await assert.rejects(exportsObject.decodeReplay(JSON.stringify(changed)));
  const badSummary=structuredClone(data);badSummary.summary.sales_cents+=1;badSummary.final.summary.sales_cents+=1;
  const text=JSON.stringify(badSummary);const signedChanged=JSON.stringify({bundle_version:1,payload_json:text,payload_sha256:hash(text)});
  await assert.rejects(exportsObject.decodeReplay(signedChanged,entry),'Catalogue binds published bundle integrity');
  for(const folder of ['app','site','ui','lib']){
    for(const name of fs.readdirSync(path.join(ROOT,folder),{recursive:true})){
      const file=path.join(ROOT,folder,name);
      if(!fs.statSync(file).isFile()||!/[.]tsx?$/.test(file))continue;
      const body=fs.readFileSync(file,'utf8');
      for(const forbidden of ['stepAgent','spawnAgents','runLayoutBenchmark','tryImpulseGrab'])assert(!body.includes(forbidden),`${file} reintroduces a browser policy`);
    }
  }
  console.log(`Replay contract passed: ${expected.length} Python frames, seeking, identity, integrity, failure isolation, and no browser policy.`);
})().catch(e=>{console.error(e);process.exitCode=1;});
