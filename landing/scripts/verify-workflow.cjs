/* Read-only browser projections of the complete OFFLINE Python workflow. */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const ts=require('typescript');
const root=path.resolve(__dirname,'..');
const directory=path.resolve(process.argv[2]??'');
const normal=value=>JSON.parse(JSON.stringify(value));
function compile(file,dependencies={}){
  const code=ts.transpileModule(fs.readFileSync(path.join(root,'lib',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const exports={};
  vm.runInNewContext(code,{exports,TextEncoder,crypto:crypto.webcrypto,require:name=>{
    assert(name in dependencies,`Unexpected dependency: ${name}`);return dependencies[name];
  }},{filename:file});
  return exports;
}
(async()=>{
  const replay=compile('replay.ts');const report=compile('report.ts',{'./replay':replay});
  const audit=JSON.parse(fs.readFileSync(path.join(directory,'verification.json')));
  assert.equal(audit.real_api_requests,0);
  assert.equal(audit.results.length,4);
  const publicDir=path.join(directory,'public/replays');
  const catalog=JSON.parse(fs.readFileSync(path.join(publicDir,'index.json')));
  for(const result of audit.results){
    const entry=catalog.runs.find(r=>r.run_id===result.run_id);assert(entry);
    const data=await replay.decodeReplay(fs.readFileSync(result.bundle,'utf8'),entry);
    assert.equal(data.source.provider,'scripted_test');
    assert.equal(data.shoppers.length,result.shoppers);
    assert.equal(data.summary.finished_count,result.shoppers);
    assert.equal(data.summary.sales_cents,result.sales_cents);
    const expected=JSON.parse(fs.readFileSync(result.expected));
    for(const [sequence,frame] of Object.entries(expected))assert.deepEqual(normal(replay.frameAt(data,Number(sequence))),frame);
    console.log(`OFFLINE replay passed: ${result.layout}, ${result.shoppers} shoppers, ${result.events} events, full checkout.`);
  }
  assert.equal(catalog.reports.length,2);
  for(const entry of catalog.reports){
    const text=fs.readFileSync(path.join(publicDir,path.basename(entry.url)),'utf8');
    const decoded=await report.decodeReport(text,entry);
    assert.equal(decoded.provider,'scripted_test');assert.equal(decoded.status,'pilot_or_incomplete');
    assert.equal(decoded.arms.length,2);assert.equal(decoded.runs.length,2);
    assert(decoded.arms.every(a=>a.metrics.mean_list_completion===1&&a.metrics.checkout_completion===1));
    assert(decoded.paired.every(p=>p.ci95===null));
    assert.equal(decoded.behavior.attempts,40);assert.equal(decoded.behavior.directional_pairs,0);
    const evidence=fs.readFileSync(path.join(publicDir,path.basename(decoded.behavior_evidence.url)));
    assert.equal(crypto.createHash('sha256').update(evidence).digest('hex'),decoded.behavior_evidence.sha256);
    assert.equal(evidence.toString().split('\n').filter(Boolean).length,42);
    await assert.rejects(report.decodeReport(text+' ',entry));
    await assert.rejects(report.decodeReport(text,{...entry,sha256:undefined}));
    const bad=JSON.stringify({...decoded,arms:[decoded.arms[0],decoded.arms[0]]});
    await assert.rejects(report.decodeReport(bad,{...entry,sha256:crypto.createHash('sha256').update(bad).digest('hex')}));
    const unassessed={...decoded,paired:[{comparison:decoded.paired[0].comparison,metric:'request_latency_p95_ms',mean_difference:null,ci95:null,blocks:0,missing_blocks:1,status:'unassessed'}]};
    const readChanged=value=>{const json=JSON.stringify(value);return report.decodeReport(json,{...entry,sha256:crypto.createHash('sha256').update(json).digest('hex')});};
    assert.equal((await readChanged(unassessed)).paired[0].mean_difference,null);
    await assert.rejects(readChanged({...unassessed,paired:[{...unassessed.paired[0],blocks:1}]}));
    await assert.rejects(readChanged({...unassessed,paired:[{...unassessed.paired[0],ci95:[0,0]}]}));
  }
  console.log('OFFLINE reports passed: Python values, fixture identity, incomplete-study status, integrity, and uncertainty.');
})().catch(error=>{console.error(error);process.exitCode=1;});
