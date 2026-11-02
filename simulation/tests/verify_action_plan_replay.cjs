/* Compare explicit-plan fixtures with the real TypeScript replay/live readers. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'landing/node_modules/typescript'));
const directory = path.resolve(process.argv[2]);
const normal = value => JSON.parse(JSON.stringify(value));
function compile(file, dependencies = {}) {
  const exports = {};
  const source = fs.readFileSync(path.join(root, 'landing/lib', file), 'utf8');
  const js = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  }}).outputText;
  vm.runInNewContext(js, {exports, TextEncoder, crypto: crypto.webcrypto, require: name => {
    assert(name in dependencies);return dependencies[name];
  }});
  return exports;
}
(async () => {
  const replay = compile('replay.ts');
  const live = compile('live.ts', {'./replay': replay});
  const audit = JSON.parse(fs.readFileSync(path.join(directory, 'verification.json')));
  assert.equal(audit.real_api_requests, 0);
  for (const result of audit.results) {
    const data = await replay.decodeReplay(fs.readFileSync(result.bundle, 'utf8'));
    const expected = JSON.parse(fs.readFileSync(result.expected));
    assert.equal(data.source.provider, 'scripted_test');
    for (let i = 0; i < expected.length; i++) {
      assert.deepEqual(normal(replay.frameAt(data, i)), expected[i]);
    }
    let current;
    for (const {kind, message} of JSON.parse(fs.readFileSync(result.messages))) {
      current = kind === 'run_start' ? live.liveSnapshot(message) : live.liveTransition(current, message);
      const sequence = current.events.length;
      if (kind !== 'decision' || sequence < expected.length - 1) {
        assert.deepEqual(normal(current.final), expected[sequence]);
      }
    }
    assert.deepEqual(normal(current), normal(data));
    assert.deepEqual(normal(live.liveSnapshot({stream_version: 1, run: current}, current)), normal(data));
    console.log(`${result.layout}, plans=${result.plans}: ${expected.length} replay/live frames agree; ${result.requests} requests.`);
  }
})().catch(error => {console.error(error);process.exitCode = 1;});
