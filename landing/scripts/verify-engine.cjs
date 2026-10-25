const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const ts = require("typescript");

const ROOT = path.resolve(__dirname, "..");
const expectedHashes = {
  costco_back_anchor: {
    5: "602bebf79664325f",
    10: "8a6ed6ff21f08c26",
    15: "da084e0dd16434f9",
  },
  neighborhood_express: {
    5: "b52cf777124ca83c",
    10: "eed9f0da34d794ff",
    15: "6fd0c5071e631891",
  },
};

function loadEngine() {
  const source = fs.readFileSync(path.join(ROOT, "lib/engine.ts"), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const compiledModule = { exports: {} };
  new Function("module", "exports", "require", output)(
    compiledModule,
    compiledModule.exports,
    require,
  );
  return compiledModule.exports;
}

function benchmarkHash(result) {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(result))
    .digest("hex")
    .slice(0, 16);
}

const engine = loadEngine();
const { layouts } = require(path.join(ROOT, "data/store_v2.json"));

for (const [layoutId, counts] of Object.entries(expectedHashes)) {
  for (const [count, expected] of Object.entries(counts)) {
    const actual = benchmarkHash(engine.runLayoutBenchmark(layouts[layoutId], Number(count)));
    if (actual !== expected) {
      throw new Error(`${layoutId} with ${count} shoppers changed: ${actual} !== ${expected}`);
    }
  }
}

console.log("Engine benchmark contract passed.");
