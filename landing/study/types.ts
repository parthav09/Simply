export type Concept = { id: string; area: string; title: string; idea: string; implementation: string; tradeoff: string; source: string; question: string; rubric: string[]; trap: string };
export type Question = { id: string; area: string; title: string; prompt: string; answer: string; rubric: string[]; followup: string; followupAnswer?: string; source: string };
export type QuizQuestion = { id: string; area: string; title: string; prompt: string; options: string[]; correctIndex: number; explanation: string; source: string };
export type StudyData = { concepts: Concept[]; questions: Question[]; quiz: QuizQuestion[] };
