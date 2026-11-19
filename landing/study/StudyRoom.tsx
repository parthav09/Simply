'use client';

import Link from 'next/link';
import { useState } from 'react';
import StudyQuiz, { useQuizProgress } from './StudyQuiz';
import { ThemeControl } from '../ui/ThemeProvider';
import type { StudyData } from './types';

const tabs = ['Quiz', 'Concepts', 'Drills'] as const;
type Tab = typeof tabs[number];
type QuizStart = { key: number; focus?: string; preset?: 'talk' | 'exam' };

export default function StudyRoom({ data }: { data: StudyData }) {
  const history = useQuizProgress();
  const [tab, setTab] = useState<Tab>('Quiz');
  const [search, setSearch] = useState('');
  const [area, setArea] = useState('All topics');
  const [quiz, setQuiz] = useState<QuizStart>({ key: 0 });
  function open(next: Tab) { setTab(next); setSearch(''); setArea('All topics'); }
  function startQuiz(start: Omit<QuizStart, 'key'>) { setQuiz(previous => ({ key: previous.key + 1, ...start })); open('Quiz'); }
  const answered = data.quiz.filter(q => history[q.id]);
  const correct = answered.filter(q => history[q.id].lastCorrect);
  const talk = data.quiz.filter(q => q.area.startsWith('Talk'));
  const items = tab === 'Drills' ? data.questions : data.concepts;
  const topics = ['All topics', ...new Set(items.map(c => c.area))];
  const matches = (item: { area: string; title: string; prompt?: string }) => (area === 'All topics' || area === item.area) && `${item.title} ${item.area} ${item.prompt ?? ''}`.toLowerCase().includes(search.toLowerCase());
  const filters = <div className="study-filters"><label>Search<input value={search} onChange={e => setSearch(e.target.value)} placeholder={tab === 'Drills' ? 'Try QLoRA, assist, cost…' : 'Try replay or leakage'} type="search"/></label><label>Topic<select value={area} onChange={e => setArea(e.target.value)}>{topics.map(t => <option key={t}>{t}</option>)}</select></label></div>;

  return <main className="study-room" id="main-content">
    <a className="skip-link" href="#study-panel">Skip to study content</a>
    <aside className="study-sidebar">
      <Link className="study-wordmark" href="/">simply<span>.</span><small>FIELDNOTES / 23</small></Link>
      <div className="study-private">LOCAL ONLY <span aria-hidden="true">↗</span></div>
      <nav aria-label="Study sections">{tabs.map((name, i) => <button key={name} aria-current={tab === name ? 'page' : undefined} onClick={() => open(name)}><span>0{i + 1}</span>{name}<span aria-hidden="true">↗</span></button>)}</nav>
      <div className="study-progress"><span className="eyebrow">Your latest attempts</span><strong>{correct.length}<small> / {data.quiz.length}</small></strong><p>correct · {answered.length} tried</p><progress aria-label="Questions answered correctly" value={correct.length} max={data.quiz.length}/></div>
      <button className="study-primary" onClick={() => startQuiz({ preset: 'talk' })}>Presentation quiz · {Math.min(15, talk.length)} questions <span>↗</span></button>
      <button className="study-secondary" onClick={() => startQuiz({ preset: 'exam' })}>Timed 20-minute quiz</button>
      <div className="study-sidebar-bottom"><Link href="/present">Open the presentation ↗</Link><ThemeControl/><p>Unavailable in production.<br/>Answers stay in this browser.</p></div>
    </aside>
    <div className="study-main">
      <header className="study-topline"><span>SIMPLY / PRIVATE STUDY ROOM</span><span>CODE + EVIDENCE · NOV 18, 2026</span></header>
      <section className="study-panel" id="study-panel" aria-label={tab}>
      {tab === 'Concepts' && <>
        <div className="study-heading"><p className="eyebrow">02 / Know the numbers, then the ideas</p><h1>Concepts.</h1><p>Every number below is quoted from a Python-written source. Then each concept: what it is, how Simply does it, and where it stops.</p></div>
        <section className="study-numbers" aria-label="Numbers to know">{data.numbers.map((group, i) => <details key={group.title} open={i < 2} className="study-number-group"><summary><h2>{group.title}</h2><span aria-hidden="true">+</span></summary>
          <p className="study-note">{group.note}</p>
          <dl>{group.rows.map(([label, value, note]) => <div key={label}><dt>{label}</dt><dd>{value}{note && <small>{note}</small>}</dd></div>)}</dl>
          <p className="study-source">READ / {group.source}</p></details>)}</section>
        {filters}
        <div className="study-concepts">{data.concepts.filter(matches).map(c => <details className="study-concept" key={c.id}><summary><span className="study-topic">{c.area}</span><h2>{c.title}</h2><span aria-hidden="true">+</span></summary><div className="study-concept-body"><h3>The concept</h3><p>{c.idea}</p><h3>In this codebase</h3><p>{c.implementation}</p><h3>Tradeoffs & limits</h3><p>{c.tradeoff}</p><p className="study-source">READ / {c.source}</p><aside className="study-trap"><b>Do not say</b><p>{c.trap}</p></aside>{data.quiz.some(q => q.id === c.id) && <button className="study-text-button" onClick={() => startQuiz({ focus: c.id })}>Test this concept ↗</button>}</div></details>)}</div>
        {!data.concepts.some(matches) && <p className="study-card">No matching concepts. Clear the search or choose another topic.</p>}
      </>}
      {tab === 'Drills' && <>
        <div className="study-heading"><p className="eyebrow">03 / Practise out loud</p><h1>Drills.</h1><p>Answer aloud before opening the notes, then handle the follow-up. “Why this, not that” questions come first.</p></div>
        {filters}
        <p>{data.questions.filter(matches).length} prompts</p>
        {data.questions.filter(matches).map(q => <details className="study-concept" key={q.id}><summary><span className="study-topic">{q.area}</span><h2>{q.prompt}</h2><span aria-hidden="true">+</span></summary><div className="study-concept-body"><h3>{q.title}</h3>{q.answer.split('\n\n').map((paragraph, i) => <p key={i}>{paragraph}</p>)}<h3>A strong answer covers</h3><ul>{q.rubric.map(point => <li key={point}>{point}</li>)}</ul><div className="study-trap"><h3>Interviewer follow-up</h3><p>{q.followup}</p>{q.followupAnswer && <p><b>Answer:</b> {q.followupAnswer}</p>}</div><p className="study-source">SOURCE / {q.source}</p>{data.quiz.some(x => x.id === q.id) && <button className="study-secondary" onClick={() => startQuiz({ focus: q.id })}>Check this in the quiz ↗</button>}</div></details>)}
        {!data.questions.some(matches) && <p>No matching prompts. Try another topic or search.</p>}
      </>}
      <div hidden={tab !== 'Quiz'}><StudyQuiz key={quiz.key} questions={data.quiz} focus={quiz.focus} preset={quiz.preset}/></div>
      </section>
      <footer className="study-bottom">PRIVATE LEARNING MATERIAL · CODE IS THE AUTHORITY · NO NEW INFERENCE REQUESTS</footer>
    </div>
  </main>;
}
