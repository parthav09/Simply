/*
 * Writes the private study material as one Markdown file for voice practice with Claude
 * (upload it to a Claude project or conversation). Run: npm run study:export
 * With --check it only verifies the committed file is up to date.
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const crypto = require('node:crypto');

const root = path.resolve(__dirname, '..');
const OUT = path.join(root, 'study', 'voice-quiz-bank.md');

function compile(file, dependencies) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(code, { exports, require: name => {
    if (!(name in dependencies)) throw new Error(`Unexpected dependency in ${file}: ${name}`);
    return dependencies[name];
  } });
  return exports;
}

function load() {
  const only = { 'server-only': {} };
  const deps = {
    './quiz-content': compile('study/quiz-content.ts', only),
    './mle-interview': compile('study/mle-interview.ts', only),
    './agent-evals': compile('study/agent-evals.ts', only),
    './interview': compile('study/interview.ts', only),
    './numbers': compile('study/numbers.ts', only),
    './fundamentals': compile('study/fundamentals.ts', only),
  };
  return compile('study/content.ts', { ...only, ...deps }).studyData;
}

const groupBy = (items, key) => items.reduce((map, item) => map.set(item[key], [...(map.get(item[key]) ?? []), item]), new Map());

function render(data) {
  const lines = [];
  const add = (...xs) => lines.push(...xs);
  add('# Simply · voice quiz bank', '',
    'Private interview practice material, exported from the study room (landing/study). Regenerate with `npm run study:export --prefix landing`.', '',
    '## Instructions for Claude (voice quiz)', '',
    '- Quiz me one question at a time. Ask it as an open question first; do not read the options unless I ask for them.',
    '- After I answer, say whether I was right, give the correct answer in one sentence, then the "Why" in two or three sentences.',
    '- If I was wrong or vague, ask the follow-up from the linked study card or drill, then move on.',
    '- Start with the "Talk:" sections (my presentation), then the project concepts, then the general fundamentals. Mix topics after the first ten.',
    '- Every few questions, ask me to explain a number from "Numbers to know" or to defend a "Why this, not that" choice.',
    '- Keep score and, when I say stop, list the topics I missed.', '',
    `Contents: ${data.quiz.length} quiz questions · ${data.concepts.length} concept cards · ${data.questions.length} drills · ${data.numbers.length} number sheets.`, '');

  add('## Numbers to know', '');
  for (const group of data.numbers) {
    add(`### ${group.title}`, '', group.note, '', '| Item | Value | Note |', '|---|---|---|');
    for (const [label, value, note] of group.rows) add(`| ${label} | ${value} | ${note || ''} |`);
    add('', `Source: ${group.source}`, '');
  }

  add('## Quiz questions', '');
  let n = 0;
  for (const [area, questions] of groupBy(data.quiz, 'area')) {
    add(`### ${area}`, '');
    for (const q of questions) {
      n += 1;
      add(`**Q${n}. ${q.title}** (id \`${q.id}\`)`, '', `Question: ${q.prompt}`, '');
      // Stable shuffle keyed by question id, so the correct answer is not always option A.
      const key = option => crypto.createHash('sha256').update(`${q.id}\u0000${option}`).digest('hex');
      const order = q.options.map((option, i) => [key(option), option, i === q.correctIndex]).sort((x, y) => x[0].localeCompare(y[0]));
      order.forEach(([, option, correct], i) => add(`- ${String.fromCharCode(65 + i)}. ${option}${correct ? '  ← correct' : ''}`));
      add('', `Answer: ${q.options[q.correctIndex]}`, '', `Why: ${q.explanation.replace(/\n\n/g, ' ')}`, '');
      if (q.teachesTitle) add(`Study card: ${q.teachesTitle}`, '');
      add(`Source: ${q.source}`, '');
    }
  }

  add('## Concept cards', '');
  for (const [area, concepts] of groupBy(data.concepts, 'area')) {
    add(`### ${area}`, '');
    for (const c of concepts) {
      add(`#### ${c.title} (id \`${c.id}\`)`, '', `- Idea: ${c.idea}`, `- In Simply: ${c.implementation}`, `- Limits: ${c.tradeoff}`,
        `- Practice question: ${c.question}`, `- A strong answer covers: ${c.rubric.join(' / ')}`, `- Do not say: ${c.trap}`, `- Source: ${c.source}`, '');
    }
  }

  add('## Spoken-answer drills', '');
  for (const [area, drills] of groupBy(data.questions, 'area')) {
    add(`### ${area}`, '');
    for (const d of drills) {
      add(`#### ${d.title} (id \`${d.id}\`)`, '', `Prompt: ${d.prompt}`, '', `Model answer: ${d.answer.replace(/\n\n/g, ' ')}`, '',
        `A strong answer covers: ${d.rubric.join(' / ')}`, '', `Follow-up: ${d.followup}`);
      if (d.followupAnswer) add('', `Follow-up answer: ${d.followupAnswer}`);
      add('', `Source: ${d.source}`, '');
    }
  }
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

const text = render(load());
if (process.argv.includes('--check')) {
  if (!fs.existsSync(OUT) || fs.readFileSync(OUT, 'utf8') !== text) {
    console.error('study/voice-quiz-bank.md is out of date. Run: npm run study:export');
    process.exit(1);
  }
  console.log('Voice quiz bank is up to date.');
} else {
  fs.writeFileSync(OUT, text);
  console.log(`Wrote ${path.relative(root, OUT)} (${(text.length / 1024).toFixed(0)} KB).`);
}
