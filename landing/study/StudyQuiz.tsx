'use client';

import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import type { QuizQuestion } from './types';
import { prepareQuiz, scoreQuiz } from './quiz-engine';

type History = Record<string, { attempts: number; correct: number; lastCorrect: boolean }>;
const KEY = 'simply-secretstudy23-quiz-v2';
const CHANGE = 'simply-quiz-change';
function subscribe(callback: () => void) {
  window.addEventListener('storage', callback); window.addEventListener(CHANGE, callback);
  return () => { window.removeEventListener('storage', callback); window.removeEventListener(CHANGE, callback); };
}
function snapshot() { try { return localStorage.getItem(KEY) || '{}'; } catch { return '{}'; } }
function parse(raw: string): History {
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter((entry): entry is [string, History[string]] => {
      const item = entry[1] as History[string] | null;
      return !!item && Number.isInteger(item.attempts) && item.attempts > 0 && Number.isInteger(item.correct) && item.correct >= 0 && item.correct <= item.attempts && typeof item.lastCorrect === 'boolean';
    }));
  } catch { return {}; }
}
function write(value: History): boolean {
  try { localStorage.setItem(KEY, JSON.stringify(value)); window.dispatchEvent(new Event(CHANGE)); return true; } catch { return false; }
}
function record(results: Record<string, boolean>): boolean {
  const history = parse(snapshot());
  for (const [id, correct] of Object.entries(results)) {
    const old = history[id];
    history[id] = { attempts: (old?.attempts || 0) + 1, correct: (old?.correct || 0) + Number(correct), lastCorrect: correct };
  }
  return write(history);
}
export function useQuizProgress() {
  const raw = useSyncExternalStore(subscribe, snapshot, () => '{}');
  return useMemo(() => parse(raw), [raw]);
}

export default function StudyQuiz({ questions, focus, autoExam = false }: { questions: QuizQuestion[]; focus?: string; autoExam?: boolean }) {
  const history = useQuizProgress();
  const [topic, setTopic] = useState('All topics');
  const [count, setCount] = useState(10);
  const [mode, setMode] = useState<'practice' | 'exam'>(autoExam ? 'exam' : 'practice');
  const [missedOnly, setMissedOnly] = useState(false);
  const [round, setRound] = useState<QuizQuestion[]>(() => focus ? prepareQuiz(questions.filter(q => q.id === focus), 1) : autoExam ? prepareQuiz(questions, 8) : []);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({});
  const [finished, setFinished] = useState(false);
  const [deadline, setDeadline] = useState<number | null>(() => autoExam ? Date.now() + 20 * 60 * 1000 : null);
  const [seconds, setSeconds] = useState(20 * 60);
  const [saveError, setSaveError] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const topics = ['All topics', ...new Set(questions.map(q => q.area))];
  const pool = questions.filter(q => (topic === 'All topics' || q.area === topic) && (!missedOnly || history[q.id]?.lastCorrect === false));
  const current = round[index];
  const score = scoreQuiz(round, answers);
  const missed = round.filter(q => answers[q.id] !== q.correctIndex);
  const review = !!current && submitted[current.id];
  function start(pool: QuizQuestion[], requestedCount: number, selectedMode = mode) {
    setRound(prepareQuiz(pool, requestedCount)); setIndex(0); setAnswers({}); setSubmitted({}); setFinished(false); setMode(selectedMode);
    setDeadline(selectedMode === 'exam' ? Date.now() + 20 * 60 * 1000 : null); setSeconds(20 * 60);
  }
  function complete() {
    if (finished) return;
    setSaveError(!record(Object.fromEntries(round.filter(q => answers[q.id] !== undefined && (mode === 'exam' || !submitted[q.id])).map(q => [q.id, answers[q.id] === q.correctIndex]))));
    setFinished(true); setDeadline(null);
  }
  useEffect(() => {
    if (deadline === null || finished) return;
    const tick = () => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setSeconds(left);
      if (left === 0) {
        setSaveError(!record(Object.fromEntries(round.filter(q => answers[q.id] !== undefined).map(q => [q.id, answers[q.id] === q.correctIndex]))));
        setFinished(true); setDeadline(null);
      }
    };
    const timer = window.setInterval(tick, 500);
    return () => window.clearInterval(timer);
  }, [deadline, finished, round, answers]);
  function submit() {
    if (!current || answers[current.id] === undefined || review) return;
    setSubmitted({ ...submitted, [current.id]: true });
    setSaveError(!record({ [current.id]: answers[current.id] === current.correctIndex }));
  }
  function exportResults() {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ savedAt: new Date().toISOString(), history, latestQuiz: finished ? { score, answers, questions: round.map(q => ({ id: q.id, selected: q.options[answers[q.id]] ?? null, correct: q.options[q.correctIndex] })) } : null }, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'simply-quiz-results.json'; link.click(); URL.revokeObjectURL(url);
  }
  return <>
    <div className="study-heading"><p className="eyebrow">04 / Test your understanding</p><h1>{finished ? 'Your quiz results.' : round.length ? 'Think it through.' : 'Take the quiz.'}</h1><p>{finished ? 'Automatically scored. Review the explanations, then retry what you missed.' : 'Practice the concepts behind Simply and how the project applies them.'}</p></div>
    {saveError && <p role="alert" className="study-trap">Your quiz works, but browser storage is unavailable. Results could not be saved.</p>}
    {!round.length && <div className="study-card study-quiz-setup">
      <h2>Build your round</h2><p>Every question has one correct answer and three plausible distractors. Question order and answer positions are shuffled each round.</p>
      <div className="study-filters"><label>Topic<select value={topic} onChange={e => setTopic(e.target.value)}>{topics.map(t => <option key={t}>{t}</option>)}</select></label><label>Questions<select value={count} onChange={e => setCount(Number(e.target.value))}>{[5, 10, 20, questions.length].map(n => <option key={n} value={n}>{n === questions.length ? `All ${questions.length}` : n}</option>)}</select></label><label>Mode<select value={mode} onChange={e => setMode(e.target.value as 'practice' | 'exam')}><option value="practice">Practice · feedback after each answer</option><option value="exam">Timed · feedback after finishing</option></select></label></div>
      <label className="study-check"><input type="checkbox" checked={missedOnly} onChange={e => setMissedOnly(e.target.checked)}/>Only questions I previously missed</label>
      <p>{Math.min(count, pool.length)} questions selected. {mode === 'exam' ? '20-minute limit. Unanswered questions count as incorrect.' : 'No time limit. Submit before seeing the explanation.'}</p>
      <button className="study-primary" disabled={!pool.length} onClick={() => start(pool, count)}>Start quiz →</button>
      {!pool.length && <p>No questions match. Choose another topic or turn off the missed-question filter.</p>}
    </div>}
    {!!round.length && !finished && current && <>
      <div className="study-quiz-toolbar"><div><b>{mode === 'exam' ? 'Timed quiz' : 'Practice quiz'}</b><p>Question {index + 1} of {round.length} · {mode === 'exam' ? 'Answers revealed at the end' : 'One point per correct answer'}</p></div>{mode === 'exam' && <div role="timer" aria-label="Time remaining" className="study-clock">{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</div>}<button className="study-secondary" onClick={complete}>Finish quiz</button></div>
      <progress className="study-round-progress" aria-label="Quiz progress" value={mode === 'exam' ? round.length - score.unanswered : Object.keys(submitted).length} max={round.length}/>
      <article className="study-question" key={current.id}>
        <header><span className="study-topic">{current.area}</span><span className="study-question-score">{index + 1} / {round.length}</span></header>
        <h2>{current.prompt}</h2>
        <fieldset className="study-options" disabled={mode === 'practice' && review}><legend className="sr-only">Choose one answer</legend>{current.options.map((option, choice) => <label key={option} className={`${mode === 'practice' && review && choice === current.correctIndex ? 'is-correct' : ''} ${mode === 'practice' && review && choice === answers[current.id] && choice !== current.correctIndex ? 'is-incorrect' : ''}`}><input name={`quiz-${current.id}`} type="radio" checked={answers[current.id] === choice} onChange={() => setAnswers({ ...answers, [current.id]: choice })}/><span className="study-option-letter" aria-hidden="true">{String.fromCharCode(65 + choice)}</span><span>{option}</span>{mode === 'practice' && review && choice === current.correctIndex && <b>Correct answer</b>}</label>)}</fieldset>
        {mode === 'practice' && review && <div className="study-quiz-feedback" role="status"><h3>{answers[current.id] === current.correctIndex ? 'Correct · +1 point' : 'Incorrect · 0 points'}</h3>{current.explanation.split('\n\n').map((p, i) => <p key={i}>{p}</p>)}<p className="study-source">READ / {current.source}</p></div>}
        <div className="study-quiz-navigation"><button className="study-secondary" disabled={index === 0} onClick={() => setIndex(index - 1)}>← Previous</button>{mode === 'practice' && !review ? <button className="study-primary" disabled={answers[current.id] === undefined} onClick={submit}>Submit answer</button> : <button className="study-primary" onClick={() => index === round.length - 1 ? complete() : setIndex(index + 1)}>{index === round.length - 1 ? 'See results →' : 'Next question →'}</button>}</div>
      </article>
    </>}
    {finished && <>
      <div className="study-quiz-result" aria-live="polite"><strong>{score.correct}<small> / {score.total}</small></strong><h2>{score.percent}% correct</h2><p>{score.unanswered} unanswered · no self-grading</p><div className="study-hero-actions"><button className="study-primary" disabled={!missed.length} onClick={() => start(missed, missed.length, 'practice')}>Retry {missed.length} missed questions ↻</button><button className="study-secondary" onClick={() => { setRound([]); setFinished(false); }}>Build a new quiz →</button></div></div>
      <div className="study-two">{[...new Set(round.map(q => q.area))].map(area => { const result = scoreQuiz(round.filter(q => q.area === area), answers); return <div className="study-card" key={area}><b>{area}</b><p>{result.correct} / {result.total} correct</p></div>; })}</div>
      <h2>Answer review</h2>{round.map((q, i) => <details className="study-concept" key={q.id}><summary><span className="study-topic">{answers[q.id] === undefined ? 'Unanswered' : answers[q.id] === q.correctIndex ? 'Correct' : 'Incorrect'}</span><h2>{i + 1}. {q.title}</h2><span aria-hidden="true">+</span></summary><div className="study-concept-body"><p><b>{q.prompt}</b></p><p>Your answer: {q.options[answers[q.id]] ?? 'No answer selected'}</p><p>Correct answer: <b>{q.options[q.correctIndex]}</b></p>{q.explanation.split('\n\n').map((p, j) => <p key={j}>{p}</p>)}<p className="study-source">READ / {q.source}</p></div></details>)}
    </>}
    <footer className="study-notes-footer"><p>Quiz history saves in this browser. Earlier written notes remain stored separately. An unfinished round resets on reload.</p><button className="study-secondary" onClick={exportResults}>Export results ↓</button><button className="study-text-button" onClick={() => { if (confirmReset) { setSaveError(!write({})); setConfirmReset(false); } else setConfirmReset(true); }}>{confirmReset ? 'Confirm: reset quiz history' : 'Reset quiz history'}</button>{confirmReset && <button className="study-text-button" onClick={() => setConfirmReset(false)}>Cancel</button>}</footer>
  </>;
}
