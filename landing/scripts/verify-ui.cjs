/* Cache correctness and indexed replay projection, with an informational CPU benchmark. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const assert=require('node:assert/strict'),ts=require('typescript'),{performance}=require('node:perf_hooks');
const root=path.resolve(__dirname,'..');
function compile(file,dependencies={},extras={}){
  const exports={};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'lib',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,
    {exports,TextEncoder,crypto:crypto.webcrypto,require:name=>{assert(name in dependencies,`Unexpected dependency ${name}`);return dependencies[name];},...extras});
  return exports;
}
const replay=compile('replay.ts');
const text=fs.readFileSync(path.join(root,'../simulation/tests/fixtures/golden.bundle.json'),'utf8');
const fixture=JSON.parse(JSON.parse(text).payload_json);
const entry={...fixture.source,url:'/fixture.json',bundle_sha256:crypto.createHash('sha256').update(text).digest('hex')};
let catalogCalls=0,recordingCalls=0,corrupt=false;
const catalog={schema_version:1,runs:[entry],reports:[]};
const demoIds=JSON.parse(fs.readFileSync(path.join(root,'data/demo-recordings.json'),'utf8'));
const recordingDependencies={'./replay':replay,'../data/demo-recordings.json':{default:demoIds}};
const cache=compile('recordings.ts',recordingDependencies,{fetch:async url=>{
  if(url==='/replays/index.json'){catalogCalls++;return {ok:true,json:async()=>catalog};}
  recordingCalls++;return {ok:true,text:async()=>corrupt?text+' ':text};
}});
function reference(data,sequence){
  const states={...data.initial.states};const rows=Object.fromEntries(data.initial.summary.shoppers.map(s=>[s.agent_id,s]));let summary=data.initial.summary;
  for(const event of data.events.slice(0,sequence)){states[event.agent_id]=event.after;rows[event.agent_id]=event.shopper_metrics;summary={...event.totals,shoppers:data.shoppers.map(s=>rows[s.id])};}
  if(sequence===data.events.length)summary=data.summary;
  return {sequence,states,summary};
}
const normal=value=>JSON.parse(JSON.stringify(value));
(async()=>{
  await Promise.all([cache.loadCatalog(),cache.loadCatalog()]);assert.equal(catalogCalls,1,'Concurrent catalogue requests were not shared');
  await cache.loadCatalog(true);assert.equal(catalogCalls,2,'Explicit catalogue refresh was ignored');
  cache.invalidateCatalog();await cache.loadCatalog();assert.equal(catalogCalls,3,'Newly exported evidence stayed hidden behind the catalogue cache');
  const [first,second]=await Promise.all([cache.loadRecording(entry),cache.loadRecording(entry)]);
  assert.equal(recordingCalls,1,'Cross-page recording load duplicated the download');assert.equal(first,second);
  await assert.rejects(cache.loadRecording({...entry,model:'changed'}),'A cached recording bypassed identity validation');
  corrupt=true;
  const other={...entry,url:'/retry.json'};
  await assert.rejects(cache.loadRecording(other),'Tampered evidence was accepted');
  corrupt=false;await cache.loadRecording(other);
  for(let i=0;i<=fixture.events.length;i++){
    assert.deepEqual(normal(replay.frameAt(first,i)),normal(reference(first,i)));
    for(const shopper of first.shoppers)assert.deepEqual(normal(replay.shopperHistory(first,i,shopper.id)),normal(first.events.slice(0,i).filter(event=>event.agent_id===shopper.id)));
  }
  console.log('UI data checks passed: coalesced requests, identity/integrity enforcement, failed-load retry, and indexed seeking.');
  const tokenCSS=fs.readFileSync(path.join(root,'styles/tokens.css'),'utf8');
  const parseTokens=source=>Object.fromEntries([...source.matchAll(/--([a-z-]+):\s*(#[a-f0-9]{6});/g)].map(match=>[match[1],match[2]]));
  const [lightCSS,darkCSS]=tokenCSS.split(':root[data-theme="dark"]');
  const light=parseTokens(lightCSS),dark={...light,...parseTokens(darkCSS)};
  const luminance=hex=>{const values=hex.slice(1).match(/../g).map(value=>{const channel=parseInt(value,16)/255;return channel<=.04045?channel/12.92:((channel+.055)/1.055)**2.4;});return values[0]*.2126+values[1]*.7152+values[2]*.0722;};
  for(const [theme,tokens] of [['light',light],['dark',dark]])for(const [foreground,background] of [
    ['color-text','color-surface'],['color-text-secondary','color-canvas'],['color-text-muted','color-canvas'],
    ['color-on-accent','color-accent'],['color-warning','color-warning-soft'],['color-success','color-success-soft'],['map-label','map-floor'],
  ]){
    const values=[luminance(tokens[foreground]),luminance(tokens[background])].sort((a,b)=>b-a);
    assert((values[0]+.05)/(values[1]+.05)>=4.5,`${theme}: insufficient contrast for ${foreground} on ${background}`);
  }
  console.log('Theme contrast passed: normal text, secondary text, controls, statuses, and map labels in light and dark.');

  const published=JSON.parse(fs.readFileSync(path.join(root,'public/replays/index.json'),'utf8'));
  const demoCache=compile('recordings.ts',recordingDependencies,{fetch:async url=>{
    assert(url.startsWith('/replays/'),'Demo requested a non-recording endpoint');
    return {ok:true,json:async()=>published,text:async()=>fs.readFileSync(path.join(root,'public',url),'utf8')};
  }});
  for(const [layoutId,runId] of Object.entries(demoIds)){
    const demo=await demoCache.loadDemoRecording(layoutId);
    assert.equal(demo.source.run_id,runId,'Demo silently selected another recording');
    assert.equal(demo.layout.id,layoutId);
    assert.equal(demo.summary.finished_count,10);
    assert.equal(demo.summary.mean_list_completion,1);
    assert(demo.events.every(event=>event.outcome==='applied'));
    assert(Object.values(replay.frameAt(demo,demo.events.length).states).every(state=>state.phase==='FinishedState'));
  }
  await assert.rejects(demoCache.loadDemoRecording('missing-layout'),'Missing demo silently fell back to another run');
  console.log('Published demos passed: pinned identities, bundle integrity, ten checkouts, complete lists, and no failed actions.');
  const featured=cache.preferredRecording(published);
  if(!featured)return;
  const data=JSON.parse(JSON.parse(fs.readFileSync(path.join(root,'public',featured.url.replace(/^\//,'')),'utf8')).payload_json);
  replay.validateReplay(data);replay.frameAt(data,1);
  const itemLayout=compile('map-items.ts');
  const originalLayout=JSON.stringify(data.layout);
  const cell=itemLayout.CELL_SIZE;
  const blocks=data.layout.shelves.flatMap(shelf=>itemLayout.shelfItemBlocks(shelf));
  const faces=blocks.flatMap(block=>block.products);
  const occupied=new Set(data.layout.shelves.flatMap(shelf=>shelf.products.filter(product=>Number.isInteger(product.x)&&Number.isInteger(product.y)).map(product=>`${product.x},${product.y}`)));
  assert.equal(blocks.length,occupied.size,'Each occupied shelf cell must be exactly one item block');
  assert.equal(faces.length,data.catalogue.length,'A recorded product left its original cell');
  assert.equal(new Set(faces.map(product=>product.id)).size,faces.length,'A recorded product is drawn on more than one block');
  assert(blocks.every(block=>block.products.length>=1&&block.width>cell/2&&block.height>cell/2),'A block was subdivided instead of showing one item');
  for(const block of blocks){
    for(const product of block.products){
      assert.equal(block.cellX,product.x);assert.equal(block.cellY,product.y);
    }
    assert(block.x>=block.cellX*cell&&block.x+block.width<=(block.cellX+1)*cell);
    assert(block.y>=block.cellY*cell&&block.y+block.height<=(block.cellY+1)*cell);
  }
  assert(data.layout.shelves.every(shelf=>{const plate=itemLayout.shelfPlate(shelf);return !shelf.offsets.length||(plate&&shelf.offsets.length<=6);}),'A shelf invented cells beyond its recorded bay');
  assert(data.layout.shelves.filter(shelf=>shelf.offsets.length>=4&&shelf.offsets.length<=6).length>=Math.ceil(data.layout.shelves.length/2),'Most shelves should remain 4–6 block bays');
  assert.equal(JSON.stringify(data.layout),originalLayout,'Item rendering changed the recorded grid');
  const unknown={...data.layout.shelves[0],products:[{id:'no-location',name:'Unpositioned',price:1,department:'Pantry'}]};
  assert.equal(itemLayout.shelfItemBlocks(unknown).length,0,'The display invented a product location');
  console.log(`Map display passed: ${blocks.length} item blocks on original cells, ${faces.length} recorded products, 4–6 block shelves, unchanged grid.`);

  const points=Array.from({length:200},(_,i)=>(i*97)%Math.max(1,data.events.length));
  for(const sequence of points)assert.deepEqual(normal(replay.frameAt(data,sequence)),normal(reference(data,sequence)));
  function time(fn){const start=performance.now();for(const sequence of points)fn(data,sequence);return performance.now()-start;}
  const before=time(reference),after=time(replay.frameAt);
  console.log(`Replay projection benchmark: ${data.events.length} events, ${points.length} seeks; full scan ${before.toFixed(2)}ms, indexed ${after.toFixed(2)}ms (${(before/Math.max(after,.001)).toFixed(1)}× CPU speedup).`);
})().catch(error=>{console.error(error);process.exitCode=1;});
