"use client";

import { useMemo, useState } from "react";

type Question = {
  id: string;
  category: "Architecture" | "Simulation" | "LLM agents" | "Experiments" | "Engineering";
  prompt: string;
  choices: string[];
  answer: number;
  explanation: string;
  followUp: string;
};

const QUESTIONS: Question[] = [
  {
    id: "product-goal",
    category: "Architecture",
    prompt: "What decision is Simply designed to support?",
    choices: [
      "Which cashier should serve each shopper next",
      "How a store layout changes shopper journeys, completion, and revenue before fixtures move",
      "Which products a grocery store should stock",
      "How to optimize a warehouse picking route",
    ],
    answer: 1,
    explanation: "Simply is a layout experiment tool. It simulates the same shopper profiles and lists through alternative floorplans so placement effects can be compared before a physical change is made.",
    followUp: "Interview angle: explain the business hypothesis separately from the simulation mechanics.",
  },
  {
    id: "two-implementations",
    category: "Architecture",
    prompt: "Why does this repository contain both simulation/ (Python) and landing/ (Next.js)?",
    choices: [
      "The Python folder is only a legacy dependency",
      "They are two views of the same project: a Python multi-agent/LLM prototype and a deterministic interactive web demonstrator",
      "Next.js compiles Python at runtime",
      "The folders contain unrelated products",
    ],
    answer: 1,
    explanation: "The Python project models an LLM-driven shopper and validates the agent contract. The Next.js app is a fast, reproducible client-side simulation and visualization built from exported store data.",
    followUp: "Be ready to name the trade-off: reproducibility and instant UI feedback versus richer LLM behavior.",
  },
  {
    id: "data-pipeline",
    category: "Architecture",
    prompt: "Which inputs define an individual simulated shopper?",
    choices: [
      "Only their name and starting coordinate",
      "A profile plus an ordered shopping list, including budget and behavioral traits",
      "Only purchase history from a production database",
      "A randomly generated list on each step",
    ],
    answer: 1,
    explanation: "Customer profiles supply persona, budget, pace, impulse probability, and promotion responsiveness. Shopping-list rows supply planned items and quantities. Together they give the agent goals and behavioral constraints.",
    followUp: "Trace data sources: data/customer_profiles_50.csv and data/shopping_lists_50.csv are loaded in core/customers.py.",
  },
  {
    id: "layout-index",
    category: "Simulation",
    prompt: "What is built by indexLayout() in the browser engine, and why?",
    choices: [
      "An HTML index for search engines",
      "Lookup structures for blocked cells, checkout cells, products, and a product-to-shelf mapping",
      "A neural-network embedding of the store",
      "A list of the shortest routes for all customers",
    ],
    answer: 1,
    explanation: "The index turns layout data into efficient lookup structures. This makes movement validation, checkout checks, pricing, and attribution to a shelf/department straightforward during each tick.",
    followUp: "Interview angle: discuss the time-space trade-off of preprocessing rather than repeatedly scanning shelves.",
  },
  {
    id: "bfs",
    category: "Simulation",
    prompt: "Why does the deterministic simulator use breadth-first search (BFS) for routes?",
    choices: [
      "It finds an unweighted shortest path through walkable grid cells",
      "It predicts which product a shopper wants",
      "It clusters similar customer personas",
      "It guarantees the highest impulse revenue",
    ],
    answer: 0,
    explanation: "Every grid movement has equal cost, so BFS finds a shortest valid path while honoring walls and shelf cells. The agent targets a walkable cell adjacent to a product rather than walking onto a shelf.",
    followUp: "Know the limitation: real shoppers may not choose shortest paths; a future model could add congestion, familiarity, or stochastic preferences.",
  },
  {
    id: "shelf-adjacency",
    category: "Simulation",
    prompt: "When can a shopper grab a planned item in the web simulator?",
    choices: [
      "From anywhere on the map",
      "Only when standing exactly on a shelf",
      "When Manhattan distance to the item's shelf cell is exactly one and quantity is still needed",
      "Only after visiting checkout",
    ],
    answer: 2,
    explanation: "Shelves are blocked fixtures. A shopper must navigate to an adjacent aisle cell, then the grab action checks that a matching list item remains. That keeps spatial behavior consistent with the physical model.",
    followUp: "Look at applyManualAction() for the adjacency and remaining-quantity check.",
  },
  {
    id: "state-machine",
    category: "Simulation",
    prompt: "What state progression protects the checkout lifecycle?",
    choices: [
      "BrowsingState → CheckoutState → FinishedState",
      "Idle → Loading → Error",
      "Planning → Training → Deploying",
      "Cart → Shelf → Payment",
    ],
    answer: 0,
    explanation: "The shopper has explicit states. In the Python prototype, checkout is a two-step transition; in the web engine the same phase model is preserved. Finished shoppers take no additional actions.",
    followUp: "Explain why explicit state is safer than scattered booleans: valid actions and terminal behavior are easier to enforce and test.",
  },
  {
    id: "impulse-model",
    category: "Simulation",
    prompt: "Which statement best describes the browser's impulse-purchase logic?",
    choices: [
      "It is a deterministic rule using shopper traits, proximity to tempting zones/departments, and budget checks",
      "It is an unconstrained random purchase at every tick",
      "It is generated by Gemini for every nearby product",
      "It only counts products already on the shopping list",
    ],
    answer: 0,
    explanation: "tryImpulseGrab() produces a repeatable pseudo-roll from the shopper ID and steps, then uses impulse probability, promo responsiveness, proximity, and budget. Determinism makes A/B comparisons stable.",
    followUp: "Strong answer: call this a behavioral heuristic, not evidence of causal customer behavior until it is calibrated against real data.",
  },
  {
    id: "llm-contract",
    category: "LLM agents",
    prompt: "How does the Python prototype constrain an LLM's action?",
    choices: [
      "It lets the model execute arbitrary Python",
      "It asks for JSON, parses it, and rejects any step not in the observation's allowed_steps",
      "It trusts a natural-language answer without validation",
      "It gives the model direct database access",
    ],
    answer: 1,
    explanation: "Shopper.prompt() asks for a JSON decision. parse_decision() validates the structure and the allowed action. Shopper.decide() also raises if the adapter returns an invalid decision, keeping the environment authoritative.",
    followUp: "Interview angle: distinguish LLM decision generation from deterministic environment enforcement.",
  },
  {
    id: "observation",
    category: "LLM agents",
    prompt: "Why does Grid.observe() filter movement actions before giving them to the agent?",
    choices: [
      "To make responses longer",
      "To expose only moves that are inside the store and not blocked by shelves",
      "To hide the shopping list",
      "To randomize each agent's personality",
    ],
    answer: 1,
    explanation: "Observations form the agent/environment boundary. The grid removes moves into walls or fixtures and only exposes checkout when permitted, reducing invalid decisions before they happen.",
    followUp: "Think in terms of a constrained action space: it improves reliability and makes test assertions crisp.",
  },
  {
    id: "benchmark-fairness",
    category: "Experiments",
    prompt: "What makes the layout benchmark a fairer A/B comparison?",
    choices: [
      "Each layout gets unrelated random shoppers",
      "Both layouts run the same shopper profiles and lists with the same deterministic rules and tick limit",
      "The layout with more shelves automatically wins",
      "Only revenue is measured",
    ],
    answer: 1,
    explanation: "Holding the shopper cohort and rules fixed isolates the layout as the main changed variable. The result exposes revenue, impulse metrics, completion, checkout time, traffic, departments, and individual shopper metrics.",
    followUp: "Mention threats to validity: no confidence intervals, synthetic personas, no real congestion or stock-outs.",
  },
  {
    id: "metric-meaning",
    category: "Experiments",
    prompt: "Why should a decision maker not optimize only total revenue?",
    choices: [
      "Revenue is never useful",
      "A layout may increase impulse revenue while harming list completion, trip time, or customer experience",
      "The application cannot calculate revenue",
      "All layouts necessarily have identical revenue",
    ],
    answer: 1,
    explanation: "This is a multi-objective layout decision. Completion and checkout time are service guardrails; impulse and total revenue are commercial outcomes. A credible recommendation states the chosen trade-off.",
    followUp: "Practice proposing a scorecard with revenue uplift, completion rate, average ticks, and a real-world satisfaction measure.",
  },
  {
    id: "tests",
    category: "Engineering",
    prompt: "Which behavior is directly protected by the Python contract tests?",
    choices: [
      "Gemini always returns the correct business recommendation",
      "The grid rejects moves through walls and an LLM decision must be valid JSON using an allowed step",
      "The UI's colors meet every brand guideline",
      "Revenue will improve in every layout",
    ],
    answer: 1,
    explanation: "The contract tests cover data-to-agent construction, movement constraints, grab/checkout transitions, observation validity, LLM parsing, and terminal-state behavior. They protect core invariants, not product outcomes.",
    followUp: "A strong next test: verify deterministic benchmark output for a small fixed fixture and assert no agent remains stuck unexpectedly.",
  },
  {
    id: "production-gap",
    category: "Engineering",
    prompt: "What is the most important next step before using the simulator to make an expensive real-world layout decision?",
    choices: [
      "Add more emojis to the store map",
      "Calibrate and validate assumptions against observed journeys, transactions, and an experimental rollout",
      "Remove all tests to speed up the run",
      "Use a larger language model for every movement",
    ],
    answer: 1,
    explanation: "The simulation is a decision-support hypothesis generator. Production confidence needs historical calibration, sensitivity analysis, instrumentation, and ideally a controlled pilot to compare predictions with observed outcomes.",
    followUp: "Frame this as model risk management: validate inputs, quantify uncertainty, and avoid claiming causal certainty from a synthetic run.",
  },
];

const TOPICS = [
  ["1. Product story", "Problem, user, decision, and success metrics. Practice a 60-second explanation of why layout simulation matters."],
  ["2. System map", "Trace CSV inputs → Python agent prototype / exported JSON → Next.js visual simulation → benchmark metrics."],
  ["3. Grid mechanics", "Blocked cells, adjacency, Manhattan distance, BFS, entrance/checkout/exit, and state transitions."],
  ["4. Agent design", "Persona, observation, constrained actions, structured LLM output, environment validation, and trajectories."],
  ["5. Experiment design", "Control variables, outcome and guardrail metrics, assumptions, bias, calibration, and validation."],
  ["6. Engineering depth", "Data contracts, tests, determinism, complexity, failure modes, and what you would productionize next."],
] as const;

export default function ProjectQuiz() {
  const [category, setCategory] = useState<Question["category"] | "All">("All");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [revealed, setRevealed] = useState(false);

  const questions = useMemo(
    () => QUESTIONS.filter((question) => category === "All" || question.category === category),
    [category],
  );
  const question = questions[index] ?? questions[0];
  const selected = answers[question.id];
  const answered = Object.keys(answers).filter((id) => questions.some((q) => q.id === id));
  const correct = questions.filter((q) => answers[q.id] === q.answer).length;
  const complete = answered.length === questions.length;

  function chooseCategory(next: Question["category"] | "All") {
    setCategory(next);
    setIndex(0);
    setRevealed(false);
  }

  function select(answer: number) {
    setAnswers((previous) => ({ ...previous, [question.id]: answer }));
    setRevealed(true);
  }

  function advance(direction: number) {
    setIndex((current) => (current + direction + questions.length) % questions.length);
    setRevealed(false);
  }

  function reset() {
    setAnswers({});
    setIndex(0);
    setRevealed(false);
  }

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div>
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Project mastery lab</p>
            <h2 className="mt-1 text-3xl font-semibold">Learn Simply like you built it</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--muted)]">Work through the implementation, the product reasoning behind it, and the questions an interviewer is likely to push on. Every answer explains the “why,” not just the fact.</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-right shadow-sm">
            <p className="text-xs font-medium text-[var(--muted)]">Current score</p>
            <p className="font-mono text-xl font-semibold text-emerald-700">{correct}/{questions.length}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {(["All", "Architecture", "Simulation", "LLM agents", "Experiments", "Engineering"] as const).map((name) => (
            <button key={name} onClick={() => chooseCategory(name)} className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${category === name ? "border-emerald-700 bg-emerald-700 text-white" : "border-[var(--line)] bg-white text-[var(--muted)] hover:border-emerald-400"}`}>{name}</button>
          ))}
        </div>

        <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-sm">
          <div className="h-1.5 bg-slate-100"><div className="h-full bg-emerald-500 transition-all" style={{ width: `${(answered.length / questions.length) * 100}%` }} /></div>
          <div className="p-5 sm:p-7">
            <div className="flex items-center justify-between gap-3"><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-800">{question.category}</span><span className="font-mono text-xs text-[var(--muted)]">Question {index + 1} of {questions.length}</span></div>
            <h3 className="mt-5 text-xl font-semibold leading-snug">{question.prompt}</h3>
            <div className="mt-5 grid gap-2">
              {question.choices.map((choice, choiceIndex) => {
                const isSelected = selected === choiceIndex;
                const isCorrect = choiceIndex === question.answer;
                const feedback = revealed && (isCorrect ? "border-emerald-500 bg-emerald-50 text-emerald-950" : isSelected ? "border-rose-400 bg-rose-50 text-rose-950" : "border-[var(--line)]");
                return <button key={choice} onClick={() => select(choiceIndex)} className={`flex items-start gap-3 rounded-xl border p-3 text-left text-sm transition hover:border-emerald-400 ${feedback ?? (isSelected ? "border-emerald-500 bg-emerald-50" : "border-[var(--line)] bg-white")}`}><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-current font-mono text-xs">{String.fromCharCode(65 + choiceIndex)}</span><span>{choice}</span></button>;
              })}
            </div>
            {revealed && <div className={`mt-5 rounded-xl border p-4 text-sm leading-relaxed ${selected === question.answer ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}><p className="font-semibold">{selected === question.answer ? "Correct — here’s the key idea." : "Not quite — here’s the mental model."}</p><p className="mt-1">{question.explanation}</p><p className="mt-3 border-t border-current/10 pt-3 text-xs font-medium">{question.followUp}</p></div>}
            <div className="mt-6 flex items-center justify-between gap-3"><button onClick={() => advance(-1)} className="rounded-lg border border-[var(--line)] px-3 py-2 text-sm font-semibold hover:bg-slate-50">Previous</button><div className="flex gap-2"><button onClick={reset} className="rounded-lg px-3 py-2 text-sm text-[var(--muted)] hover:bg-slate-50">Reset</button><button onClick={() => advance(1)} className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800">Next question</button></div></div>
          </div>
        </div>

        {complete && <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-5"><p className="font-semibold">Round complete: {correct}/{questions.length} correct.</p><p className="mt-1 text-sm text-emerald-950/80">{correct === questions.length ? "You have the core narrative down. Now rehearse the limitations and a production-validation plan out loud." : "Review the explanations you missed, then reset for another pass. Interviewers care most about your reasoning across trade-offs."}</p></div>}
      </div>

      <aside className="h-fit rounded-2xl border border-[var(--line)] bg-white p-5 shadow-sm xl:sticky xl:top-4">
        <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Study path</p>
        <h3 className="mt-1 text-lg font-semibold">What to learn next</h3>
        <ol className="mt-4 space-y-4">
          {TOPICS.map(([title, description]) => <li key={title} className="border-l-2 border-emerald-200 pl-3"><p className="text-sm font-semibold">{title}</p><p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">{description}</p></li>)}
        </ol>
        <div className="mt-5 rounded-xl bg-slate-950 p-4 text-sm text-emerald-100"><p className="font-semibold text-white">Best interview opener</p><p className="mt-2 text-xs leading-relaxed">“Simply is a decision-support simulator for grocery layouts. It holds shopper scenarios constant, runs them through alternative floorplans, and helps teams reason about the trade-off between efficient trips and incremental purchasing.”</p></div>
      </aside>
    </section>
  );
}
