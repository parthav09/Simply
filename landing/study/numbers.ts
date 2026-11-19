import 'server-only';
import type { NumberGroup } from './types';

/**
 * Numbers to know, quoted from Python-written sources (named in each group). Nothing is computed
 * here. Update by re-reading the source, never by editing a value to fit a story.
 */
export const numbers: NumberGroup[] = [
  {title: 'Setup', source: 'run_start.layout / config / pricing in the recorded runs',
    note: 'Same for every current run unless stated.',
    rows: [
      ['Store', '22 × 14 grid · 15 shelf groups · 303 products', 'Layout A costco_back_anchor (staples at the back) · Layout B neighborhood_express'],
      ['Cohort', '10 fixed synthetic shoppers', 'Same profiles on both layouts and every model'],
      ['Action limit', '120 actions per shopper', 'One model proposal per action'],
      ['Rules', 'guided_nav_v3 · unique_single_checkout_v1', 'One unit per SKU, one-action checkout'],
      ['Generation', 'strict JSON schema · max 256 tokens · reasoning off', 'OpenRouter pinned to OpenAI, fallbacks off'],
      ['Concurrency', 'default 10 · OpenRouter runs used 2 at 60 req/min', 'At most one pending request per shopper'],
      ['Terra price snapshot', '$1.00 in / $5.00 out per M tokens', 'Frozen per run (as of 2026-10-29)'],
    ]},
  {title: 'Latest runs · Nov 17 · OpenRouter · one run per cell', source: 'landing/public/replays/evidence-dashboard.json (view openrouter_v3)',
    note: 'Values are Layout A / Layout B. Qwen base is the earlier Nov 3 run under guided_nav_v2; read as context.',
    rows: [
      ['Impulse buys per trip', 'Luna 1.5 / 0.4 · Terra 2.2 / 2.0 · Qwen base 0 / 0 · Qwen tuned 0.3 / 0.5', 'Paid off-list units (Python off_list_units)'],
      ['Checkout completion', 'Luna 100% / 100% · Terra 100% / 100% · base 60% / 90% · tuned 90% / 100%', ''],
      ['List fulfilment', 'Luna 96% / 100% · Terra 100% / 100% · base 28% / 32% · tuned 36% / 40%', 'Paid requested units'],
      ['Cost per checkout (provider)', 'Luna $0.060 / $0.051 · Terra $0.518 / $0.395 · base $0.094 / $0.060', 'Tuned Qwen: no API fee; GPU time not metered'],
      ['Cost per run (provider)', 'Luna $0.60 / $0.51 · Terra $5.18 / $3.95', ''],
      ['Requests per trip', 'Luna 60.7 / 51.3 · Terra 51.0 / 41.0 · base 100.3 / 93.9 · tuned 98.8 / 93.0', ''],
      ['Assist-adjusted decisions', 'Luna 8.4% / 4.7% · Terra 6.1% / 5.4% · base 38.7% / 35.6% · tuned 13.1% / 14.3%', 'Terra A: 31 of 510 decisions'],
      ['Invalid replies per run', 'Luna 12 / 9 · Terra 0 / 0 · base 0 / 0 · tuned 35 / 66', ''],
      ['Median latency', 'Luna ≈1.24 s · Terra ≈2.0 s · base ≈0.7 s · tuned ≈0.97 s', ''],
      ['Aborted attempt', 'Luna B first attempt stopped after 548 actions', 'OpenAI content-filter HTTP 400; retained, replaced by a re-run'],
    ]},
  {title: 'Fine-tuning · Qwen2.5 7B · QLoRA', source: 'adapter ZIP experiment.json + offline evals · data/finetuning/impulse_v3/manifest.json',
    note: 'Labels come from a rule teacher, not from Luna, Terra or people.',
    rows: [
      ['Dataset', '210 teacher trips → 1,753 / 292 / 284 rows', '35 non-benchmark shoppers × 3 styles × 2 layouts; split by shopper'],
      ['Training mix', '745 rows: 250 move · 200 impulse pass · 120 list grab · 50 checkout · 125 impulse grab', '01b "more movement" retrain (first adapter had 60 moves)'],
      ['Teacher impulse grab rate', '23% / 12% / 4% / 0% by tier', 'impulsive / mixed / planner / below 0.10'],
      ['Base', 'unsloth/Qwen2.5-7B-Instruct-bnb-4bit (NF4, frozen)', ''],
      ['Adapter', 'rank 16 · alpha 32 · dropout 0 · 7 projections · 392 tensors · ≈40M params · 161.5 MB', '≈0.5% of 7.6B'],
      ['Optimiser', 'lr 1e-4 linear · AdamW 8-bit · batch 1 × accum 4 · 2 epochs · bf16', 'Best checkpoint by validation loss'],
      ['Context', 'max 16,384 · rows median 8,521 / max 15,599 tokens', 'Answer-only loss, no truncation'],
      ['Hardware / time', 'A100-SXM4-40GB · 3,569 s (≈1 h)', 'Final train loss 0.100'],
      ['Offline (88 val rows)', 'Step agreement 22.7% → 86.4% · impulse grab rate 0% → 57.6% (teacher 63.6%)', 'Checkout 0% → 100% · list grab 0% → 70%'],
      ['Online (full trips)', 'Fulfilment 36% / 40% vs base 28% / 32% · checkout 90% / 100%', 'Far below Luna/Terra'],
    ]},
  {title: 'Run checks (guardrails)', source: 'landing/data/run-checks.json (simulation/evaluation/guardrails.py)',
    note: 'Shoppers pass / review / fail. Pass is not proof of realism.',
    rows: [
      ['Luna', 'A 5 / 5 / 0 · B 8 / 2 / 0', 'Reviews: invalid replies, loops, stuck, impulse cap'],
      ['Terra', 'A 5 / 5 / 0 · B 9 / 1 / 0', 'Reviews: impulse cap and price, one over budget'],
      ['Qwen base', 'A 0 / 6 / 4 · B 0 / 9 / 1', 'Unfinished checkout, incomplete lists, loops, stuck'],
      ['Qwen tuned', 'A 0 / 9 / 1 · B 1 / 8 / 1', 'Plus high invalid-reply rate on B'],
      ['Thresholds', 'invalid > 5% review · > 20% fail · stuck 30+ turns', 'Impulse caps 2 / 1 / 1, prices $8.00 / $4.00 / $2.50'],
    ]},
  {title: 'Isabella Rossi (C0007)', source: 'simulation/docs/ideas.md · or-v3 runs · replicate 20261118 · probes',
    note: 'Observation, not a finding.',
    rows: [
      ['Profile', 'impulsive · p = 0.45 · no list requirement · 7 must-haves · $113.13 · household 4 · vegetarian', 'Largest budget in the cohort'],
      ['Off-list units', 'Terra 12 (A), 12 (B), 11 (A replicate) · Luna 0, 0, 0', ''],
      ['Impulse stops', 'Terra 4 of 8 (A), 5 of 8 (B)', 'Expected ≈3.6; luck probability 0.52 (A) / 0.26 (B)'],
      ['Probe', 'p lowered to 0.05 → 0 off-list units', 'One run, direction only'],
    ]},
  {title: 'Earlier study · Oct 29 · direct OpenAI · guided_nav_v2', source: 'landing/public/replays/matrix-48ea3402….md · simulation/docs/evals.md',
    note: 'The resume result. A different collection (date, transport, assist version) from the Nov 17 runs.',
    rows: [
      ['Requests (Terra)', 'A 488 + 487 = 975 · B 394 + 391 = 785', '19.4872% fewer on B'],
      ['Requests per completed trip', 'A 48.75 · B 39.25', 'Same 20-trip denominator'],
      ['Est. cost per completed trip', 'A $0.46902060 · B $0.38441120', '18.0396% lower ($9.380412 vs $7.688224 over 20)'],
      ['Successful moves per shopper', 'A 42.00 · B 32.95', '21.5476% fewer'],
      ['Checkouts / fulfilment', '20/20 each · 99.0566% vs 100%', 'Two paired repetitions × ten profiles'],
      ['Luna vs Terra (A)', '$0.05709545 vs $0.46902060 per checkout (87.8% lower)', 'Fulfilment 96.2264% vs 99.0566%'],
      ['Collection ledger', '200 planned · 80 attempted · 70 completed trips', '8 runs; one provider-credit interruption retained'],
    ]},
];
