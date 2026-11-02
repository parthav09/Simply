/* Privacy is an execution boundary, not a hidden URL or robots directive. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
function compile(file, dependencies, environment = 'development', config = {}) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(code, { exports, process: { env: { NODE_ENV: environment, ...config } }, require: name => {
    assert(name in dependencies, `Unexpected dependency: ${name}`);
    return dependencies[name];
  } });
  return exports;
}
(async () => {
  const config = { STUDY_PASSWORD: 'test-only-password', STUDY_SESSION_SECRET: crypto.randomBytes(32).toString('hex') };
  const auth = compile('study/auth.ts', { 'server-only': {}, 'node:crypto': crypto }, 'development', config);
  assert(auth.passwordMatches(config.STUDY_PASSWORD));
  for (const candidate of ['', 'wrong', null, {}, config.STUDY_PASSWORD + ' ', 'x'.repeat(257)]) assert(!auth.passwordMatches(candidate));
  const now = Date.now();
  const token = auth.createSession(now);
  assert(auth.validSession(token, now));
  assert(!auth.validSession(token, now + auth.SESSION_SECONDS * 1000));
  assert(!auth.validSession(token.slice(0, -1) + (token.endsWith('0') ? '1' : '0'), now));
  assert(!auth.validSession('true', now));
  const unconfigured = compile('study/auth.ts', { 'server-only': {}, 'node:crypto': crypto });
  assert(!unconfigured.passwordMatches('anything'));
  assert(!unconfigured.validSession(token));
  const rotated = compile('study/auth.ts', { 'server-only': {}, 'node:crypto': crypto }, 'development', { ...config, STUDY_SESSION_SECRET: 'another-secret' });
  assert(!rotated.validSession(token, now));
  const jsx = (type, props) => ({ type, props });
  async function renderProtected(page) { return page.default().props.children.type(); }
  for (const environment of ['production', 'test']) {
    const denied = new Error('404');
    const page = compile('app/secretstudy23/page.tsx', {
      'react/jsx-runtime': { jsx, jsxs: jsx }, 'react': { Suspense: 'suspense' },
      'next/navigation': { notFound: () => { throw denied; } },
      'next/headers': { cookies: () => assert.fail('Cookies read outside development') },
      'next/server': { connection: () => assert.fail('Production route reached request-time authentication') },
      '../../study/auth': auth, '../../styles/study.css': {},
    }, environment);
    await assert.rejects(renderProtected(page), error => error === denied);
  }
  const quizContent = compile('study/quiz-content.ts', { 'server-only': {} });
  const mle = compile('study/mle-interview.ts', { 'server-only': {} });
  const content = compile('study/content.ts', { 'server-only': {}, './quiz-content': quizContent, './mle-interview': mle }).studyData;
  assert(mle.mleQuestions.length >= 30, 'MLE interview coverage is incomplete');
  assert.deepEqual(mle.mleQuestions.map(q => q.id), mle.mleQuiz.map(q => q.id));
  for (const q of mle.mleQuestions) assert(q.followupAnswer, `${q.id}: missing follow-up answer`);
  const engine = compile('study/quiz-engine.ts', {});
  assert(content.quiz.length > content.questions.length, 'Concept questions must supplement project questions');
  assert.equal(new Set(content.quiz.map(q => q.id)).size, content.quiz.length);
  for (const area of ['LLM fundamentals', 'Systems fundamentals', 'Evaluation fundamentals', 'Training fundamentals']) {
    assert(content.quiz.filter(q => q.area === area).length >= 3, `Missing concept coverage: ${area}`);
  }
  for (const q of content.quiz) {
    assert.equal(q.options.length, 4, `${q.id}: missing quiz choices`);
    assert.equal(new Set(q.options).size, 4, `${q.id}: duplicated choices`);
    assert(q.prompt && q.explanation && q.options[q.correctIndex], `${q.id}: missing question/answer explanation`);
  }
  const frozenQuiz = JSON.stringify(content.quiz);
  const mixed = engine.prepareQuiz(content.quiz, 10, () => 0.37);
  assert.equal(mixed.length, 10);
  assert.equal(new Set(mixed.map(q => q.id)).size, 10);
  for (const q of mixed) {
    const original = content.quiz.find(item => item.id === q.id);
    assert.equal(q.options[q.correctIndex], original.options[original.correctIndex], 'Shuffle corrupted the answer key');
  }
  assert.equal(JSON.stringify(content.quiz), frozenQuiz, 'Shuffle changed the source questions');
  const correctAnswers = Object.fromEntries(mixed.map(q => [q.id, q.correctIndex]));
  assert.equal(engine.scoreQuiz(mixed, correctAnswers).correct, 10);
  assert.equal(engine.scoreQuiz(mixed, correctAnswers).percent, 100);
  assert.equal(engine.scoreQuiz(mixed, {}).unanswered, 10);
  assert.equal(engine.scoreQuiz(mixed, {}).correct, 0);
  assert.equal(engine.scoreQuiz(mixed, Object.fromEntries(mixed.map(q => [q.id, (q.correctIndex + 1) % 4]))).correct, 0);
  assert.equal(engine.scoreQuiz([], {}).percent, 0);
  for (const authenticated of [false, true]) {
    let requestReady = false;
    const deps = {
      'react/jsx-runtime': { jsx, jsxs: jsx }, 'react': { Suspense: 'suspense' },
      'next/navigation': { notFound: () => assert.fail('Development access denied') },
      'next/server': { connection: async () => { await Promise.resolve(); requestReady = true; } },
      'next/headers': { cookies: async () => {
        assert(requestReady, 'Authentication ran before the request-time boundary');
        return { get: () => ({ value: authenticated ? token : 'forged' }) };
      } },
      '../../study/auth': { ...auth, validSession: (...args) => {
        assert(requestReady, 'Time-sensitive session validation ran during prerendering');
        return auth.validSession(...args);
      } }, '../../styles/study.css': {},
    };
    if (authenticated) {
      deps['../../study/StudyRoom'] = { default: 'room' };
      deps['../../study/content'] = { studyData: content };
      deps['./actions'] = { logout: () => {} };
    } else deps['../../study/StudyLogin'] = { default: 'login' };
    const result = await renderProtected(compile('app/secretstudy23/page.tsx', deps));
    if (authenticated) assert.equal(result.props.children[1].props.data, content);
    else assert.equal(result.type, 'login', 'Unauthenticated request leaked private material');
  }
  const redirect = new Error('redirect');
  const writes = [];
  const actions = compile('app/secretstudy23/actions.ts', {
    'next/headers': { cookies: async () => ({ set: (...args) => writes.push(args) }) },
    'next/navigation': { notFound: () => assert.fail('Unexpected notFound'), redirect: () => { throw redirect; } },
    '../../study/auth': auth,
  }, 'development', config);
  assert.equal(await actions.login('', { get: () => 'wrong' }), 'Incorrect password.');
  assert.equal(writes.length, 0, 'Wrong password created a session');
  await assert.rejects(actions.login('', { get: () => config.STUDY_PASSWORD }), error => error === redirect);
  assert(auth.validSession(writes[0][1]));
  assert.equal(writes[0][2].httpOnly, true);
  assert.equal(writes[0][2].sameSite, 'strict');
  assert.equal(writes[0][2].path, '/secretstudy23');
  await assert.rejects(actions.logout(), error => error === redirect);
  assert.equal(writes[1][2].maxAge, 0);
  assert(!fs.readFileSync(path.join(root, 'site/SiteNav.tsx'), 'utf8').includes('/secretstudy23'), 'Study route linked in public navigation');
  assert.equal(new Set(content.questions.map(q => q.id)).size, content.questions.length);
  for (const q of content.questions) {
    assert.equal(q.rubric.length, 4, `${q.id}: incomplete scoring rubric`);
    assert(q.answer && q.prompt && q.followup && q.source, `${q.id}: incomplete interview material`);
    for (const source of q.source.split(' · ').filter(s => /^(simulation|landing|data|notebooks)\//.test(s))) {
      assert(fs.existsSync(path.join(root, '..', source)), `Missing source: ${source}`);
    }
  }
  const html = fs.readFileSync(path.join(root, '.next/server/app/secretstudy23.html'), 'utf8');
  const secrets = fs.existsSync(path.join(root, '.env.local'))
    ? fs.readFileSync(path.join(root, '.env.local'), 'utf8').split('\n').filter(line => /^STUDY_(PASSWORD|SESSION_SECRET)=/.test(line)).map(line => line.slice(line.indexOf('=') + 1)).filter(Boolean) : [];
  const privateMarkers = ['Go beyond', 'Defend your resume in 90 seconds', 'Make the explanation yours.', 'Your interview workbench', 'Take the quiz.', mle.mleQuestions[0].prompt, mle.mleQuiz[0].prompt, ...secrets];
  assert(!privateMarkers.some(marker => html.includes(marker)), 'Private HTML or configuration was prerendered publicly');
  function chunks(directory) {
    return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
      const file = path.join(directory, entry.name);
      return entry.isDirectory() ? chunks(file) : file.endsWith('.js') ? [file] : [];
    });
  }
  for (const file of chunks(path.join(root, '.next/static/chunks'))) {
    const script = fs.readFileSync(file, 'utf8');
    for (const marker of privateMarkers) {
      assert(!script.includes(marker), `Private study code leaked into ${path.relative(root, file)}`);
    }
  }
  console.log(`Study room passed: password/session checks, no unauthenticated private imports, logout, development-only gate, no production HTML/client content, ${content.concepts.length} concepts, ${content.quiz.length} multiple-choice questions, shuffle/score correctness and valid source paths.`);
})().catch(error => { console.error(error); process.exitCode = 1; });
