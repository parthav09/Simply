import type { QuizQuestion } from './types';

export function shuffled<T>(values: readonly T[], random = Math.random): T[] {
  const result = [...values];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

export function prepareQuiz(pool: QuizQuestion[], count: number, random = Math.random): QuizQuestion[] {
  return shuffled(pool, random).slice(0, count).map(question => {
    const order = shuffled(question.options.map((_, index) => index), random);
    return { ...question, options: order.map(index => question.options[index]), correctIndex: order.indexOf(question.correctIndex) };
  });
}

export function scoreQuiz(questions: QuizQuestion[], answers: Record<string, number>) {
  const correct = questions.filter(q => answers[q.id] === q.correctIndex).length;
  const answered = questions.filter(q => Number.isInteger(answers[q.id]) && answers[q.id] >= 0 && answers[q.id] < q.options.length).length;
  return { correct, total: questions.length, unanswered: questions.length - answered, percent: questions.length ? Math.round(correct / questions.length * 100) : 0 };
}
