'use client';

import { B, DeckShell, type Slide } from './kit';
import { BeforeAfter, LiveReplay, LoraLab, Pipeline, ResultsBars, RunCheckBars } from './widgets';

/** Overview draft. Every number is quoted from a Python-written source named on the slide or in its notes. */

const slides: Slide[] = [
  // ── Opening ──────────────────────────────────────────────────────────────
  { section: 'Simply', title: 'title', body: <div className="pz-title">
      <p className="pz-eyebrow">Simply · Nov 2026</p>
      <h1>Rehearsing a store layout<br/>with AI shoppers.</h1>
      <p className="pz-lede">A Python simulation where language-model shoppers walk two store layouts, and every decision is recorded, checked and replayable.</p>
      <ul className="pz-chips"><li>Customer side</li><li>Engineering</li><li>Fine-tuning Qwen 7B</li><li>Evals</li></ul>
    </div>,
    notes: 'One sentence: Simply lets you ask how a store layout changes what shoppers buy, especially things they did not plan to buy, before you move a shelf. Four parts: the customer side, how it is built, fine-tuning a small open model, and how I evaluate it.' },

  { section: 'Customer side', title: 'The question', steps: 3, body: <div className="pz-two">
      <div><h2>Moving shelves is expensive.<br/>Guessing is cheap.</h2>
        <B at={1}><p className="pz-big">Where should staples go?<br/>Where do treats get noticed?</p></B>
        <B at={2}><p>Simply runs the <b>same shoppers</b> through <b>two layouts</b> and compares what they buy, with a focus on <b className="pz-impulse">impulse buys</b>: paid items that were not on their list.</p></B></div>
      <B at={3} className="pz-card"><p className="pz-eyebrow">What it is not</p><ul><li>Not a forecast of real customers</li><li>No real customer data</li><li>Not a recommender</li></ul><p>It is a controlled way to compare layouts and models on identical, synthetic inputs.</p></B>
    </div>,
    notes: 'Retailers re-plan layouts by intuition and expensive pilots. Simply is a rehearsal: same shoppers, two layouts, compare outcomes. The headline outcome is impulse buys, counted by Python as paid off-list units. Be clear early that this does not predict real customers.' },

  { section: 'Customer side', title: 'A shopper', steps: 3, body: <div className="pz-two">
      <div className="pz-persona">
        <header><span className="pz-avatar" aria-hidden="true">IR</span><div><h3>Isabella Rossi</h3><p>C0007 · 38 · healthcare worker · household of 4</p></div></header>
        <dl>
          <div><dt>Budget</dt><dd>$113.13 <small>(largest in cohort)</small></dd></div>
          <div><dt>Style</dt><dd className="pz-impulse">impulsive · p = 0.45</dd></div>
          <div><dt>List</dt><dd>7 must-haves · not required to stick to it</dd></div>
          <div><dt>Diet</dt><dd>vegetarian · no alcohol</dd></div>
          <div><dt>Price sensitivity</dt><dd>2 / 5 · brand loyalty 1 / 5</dd></div>
          <div><dt>Trip</dt><dd>stock-up · knows the store (5 / 5)</dd></div>
        </dl>
      </div>
      <div><h2>A persona is a profile in the prompt.</h2>
        <B at={1}><p>About 40 synthetic fields per shopper. Ten fixed shoppers, the same on every layout and every model.</p></B>
        <B at={2}><p>The model reads the profile every turn. <b>No weights change per shopper.</b></p></B>
        <B at={3}><p className="pz-note">Hold on to Isabella. She comes back in the evals.</p></B></div>
    </div>,
    notes: 'Real profile from the recorded run. Personas are inference-time conditioning: the profile is text in the prompt. Ten fixed profiles are reused everywhere so comparisons are fair. Isabella is interesting because she is impulsive with a big budget; one model took 12 extra items for her, another took none.' },

  { section: 'Customer side', title: 'Two stores', steps: 2, body: <div className="pz-two">
      <div className="pz-layout-card"><p className="pz-eyebrow">Layout A · costco_back_anchor</p><h3>Anchor loop</h3><p>Staples at the back, with snacks and bakery near the entrance, so shoppers walk past treats.</p></div>
      <div className="pz-layout-card"><p className="pz-eyebrow">Layout B · neighborhood_express</p><h3>Express essentials</h3><p>Daily essentials near the entrance for shorter shopping trips.</p></div>
      <B at={1} className="pz-span"><p><b>Held fixed:</b> 22 × 14 grid · 15 shelf groups · 303 products and prices · the same 10 shoppers · 120 actions each · stock always replenished · no queues or crowding.</p></B>
      <B at={2} className="pz-span"><p><b>One action per model call:</b> move, grab from an adjacent shelf, or check out (pays in one action, one unit per product).</p></B>
    </div>,
    notes: 'Only placement changes between A and B. Everything else is frozen per run and recorded, so differences are attributable to placement within one model. Rules: unique_single_checkout_v1, one unit per SKU, duplicate pickups rejected.' },

  { section: 'Customer side', title: 'Watch a trip', wide: true, body: <div><h2 className="pz-inline">Recorded trips, replayed. <small>Pick a model; both layouts advance one decision per tick.</small></h2><LiveReplay/></div>,
    notes: 'This is a real recording, not an animation of a script. Each tick is one recorded decision. Point out impulse flashes (items not on the list), and switch models: Terra vs Luna vs the Qwen models. Nothing here calls a model; it replays Python records verified by hash.' },

  // ── Engineering ──────────────────────────────────────────────────────────
  { section: 'Engineering', title: 'divider', body: <div className="pz-divider"><p className="pz-eyebrow">Part 2</p><h1>How it is built.</h1><p>A model proposes. Python decides what happened.</p></div>, notes: 'Transition into engineering.' },

  { section: 'Engineering', title: 'One decision', wide: true, body: <div><h2>One decision, seven steps.</h2><Pipeline/></div>,
    notes: 'Walk the loop. Observe: Python builds the prompt and snapshots state. Propose: the model returns strict JSON (step, product_id, reason), max 256 tokens. Check: schema and allowed steps. Assist: guided_nav_v3 may override. Apply: physics, reachability, duplicate SKU. Record: canonical JSONL; a logging failure stops the run. Replay: React draws recorded states only.' },

  { section: 'Engineering', title: 'Authority', steps: 3, body: <div><h2>One owner of the truth.</h2>
      <div className="pz-authority">
        <div className="pz-actor"><b>Model</b><span>proposes</span><small>Luna · Terra · Qwen</small></div>
        <span className="pz-arrow" aria-hidden="true">→</span>
        <div className="pz-actor is-core"><b>Python core</b><span>validates · applies · records · scores</span><small>simulation/core</small></div>
        <span className="pz-arrow" aria-hidden="true">→</span>
        <div className="pz-actor"><b>React</b><span>displays</span><small>live (SSE) and replay</small></div>
      </div>
      <B at={1}><p>The browser never creates a purchase, route or checkout. Seeking a replay cannot change an outcome.</p></B>
      <B at={2}><p>Live view, replay and every dashboard number come from the <b>same records</b>, so they cannot disagree.</p></B>
      <B at={3}><p className="pz-note">No recording → an honest empty state. Never a scripted fallback.</p></B>
    </div>,
    notes: 'Why: with two places that can change state you get two truths. Here only Python changes state. React verifies hashes and redraws. Evidence numbers are computed in Python (evaluation/dashboard.py), never in React.' },

  { section: 'Engineering', title: 'The assist', steps: 3, body: <div className="pz-two">
      <div><h2>A rule layer that can override, in the open.</h2>
        <div className="pz-override"><p className="pz-eyebrow">Recorded · Terra · Layout A · decision 140</p>
          <p><span className="pz-tag">Model proposed</span> <code>move_down</code> “continue down the aisle toward checkout”</p>
          <B at={1}><p><span className="pz-tag is-assist">Applied</span> <code>move_right</code> “Navigation assist: head toward checkout”</p></B></div>
        <B at={2}><ul><li>Check out with ≤ 15 turns left</li><li>Grab a reachable list item</li><li>Head to checkout when done or below 30% of turns</li><li>Avoid busier cells</li></ul></B></div>
      <div><B at={2}><p className="pz-stat"><b>6.1%</b> of Terra’s decisions adjusted on Layout A <small>(31 of 510)</small></p></B>
        <B at={3}><div className="pz-card"><p className="pz-eyebrow">guided_nav_v3</p><p>Older versions replaced an impulse grab with a reachable list item, which erased the behaviour we measure. v3 keeps the model’s own reachable off-list grab.</p><p>Same versioned policy for every model. Results are <b>model + assist</b>.</p></div></B></div>
    </div>,
    notes: 'Without help, models waste many of their 120 actions wandering and the comparison becomes about navigation. The assist is a pure function, versioned, identical for all models; both proposal and applied action are recorded. Base Qwen had about 36-39% of decisions adjusted, Terra about 6%. That number is itself a quality signal.' },

  { section: 'Engineering', title: 'Verified replay', steps: 3, body: <div><h2>Every recording is checked before it is shown.</h2>
      <ol className="pz-steps">
        <B at={1} as="li"><b>Integrity.</b> Content hashes for the recording, the dashboard and the evidence index.</B>
        <B at={2} as="li"><b>Re-run the assist.</b> For every decision, Python re-runs the same pure assist function on the recorded state. If it would not produce the recorded adjustment, the recording is rejected. The raw model reply must also parse to the recorded proposal.</B>
        <B at={3} as="li"><b>Deterministic replay, not deterministic inference.</b> A recording always replays the same way. A fresh model run will not: providers do not support request seeds. That is why repeats matter.</B>
      </ol></div>,
    notes: 'run_log.py: "navigation adjustment contradicts recorded history". This works because adjusted_action takes all its inputs explicitly and they are saved. It also explains why guided_nav_v1/v2 cannot be deleted: old recordings are verified against them.' },

  { section: 'Engineering', title: 'Concurrency and cost', steps: 3, body: <div className="pz-two">
      <div><h2>Parallel calls, one writer.</h2>
        <B at={1}><p>A thread pool sends several shoppers’ requests at once (default 10; OpenRouter runs used 2 at 60 requests/min). Each shopper has at most one pending request.</p></B>
        <B at={2}><p>Workers only return proposals. The single Python owner commits results as they arrive, so a slow call never blocks others and never races on state.</p></B></div>
      <B at={3}><div className="pz-card"><p className="pz-eyebrow">Two kinds of cost, kept apart</p><p><b>Estimated:</b> tokens × a price snapshot frozen per run (Terra: $1 in / $5 out per M tokens).</p><p><b>Provider-reported:</b> what OpenRouter billed. Terra A: $5.1832 estimated vs $5.1832 billed.</p><p>Model ID frozen, fallbacks off, serving provider pinned.</p></div></B>
    </div>,
    notes: 'RoundCoordinator uses a ThreadPoolExecutor. Observations are snapshotted before the call. Shopper basket dollars are simulated and separate from API dollars. No app-level spending cap on manual runs; the ledger is preserved.' },

  // ── Results ──────────────────────────────────────────────────────────────
  { section: 'Results', title: 'divider', body: <div className="pz-divider"><p className="pz-eyebrow">Part 3</p><h1>What happened.</h1><p>Latest runs: Nov 17 · OpenRouter · guided_nav_v3 · one run per cell.</p></div>, notes: 'Transition to results. Emphasise one run per cell: descriptive, not significant.' },

  { section: 'Results', title: 'Results', wide: true, body: <div><h2 className="pz-inline">Four models, two layouts. <small>Click a measure.</small></h2><ResultsBars/></div>,
    notes: 'Impulse per trip A/B: Luna 1.5/0.4, Terra 2.2/2.0, Qwen base 0/0, tuned 0.3/0.5. Fulfilment: Luna 96/100%, Terra 100/100%, base 28/32%, tuned 36/40%. Cost per checkout: Luna ≈$0.06/$0.05, Terra ≈$0.52/$0.40. Requests per trip: Terra 51/41. The Qwen base row is the earlier Nov 3 run under guided_nav_v2.' },

  { section: 'Results', title: 'Cost vs quality', steps: 2, body: <div><h2>Cheap is not the same as equivalent.</h2>
      <div className="pz-three">
        <div className="pz-stat"><b>≈9×</b>cheaper per checkout<small>Luna $0.060 vs Terra $0.518 (Layout A)</small></div>
        <div className="pz-stat"><b>96% vs 100%</b>of the list bought<small>Luna vs Terra, Layout A</small></div>
        <div className="pz-stat"><b>0 vs 12</b>impulse items for Isabella<small>Luna vs Terra, Layout A</small></div>
      </div>
      <B at={1}><p>Both finish every trip. They behave differently, so a cheaper model is not a drop-in replacement for studying impulse behaviour.</p></B>
      <B at={2}><p className="pz-note">Fine-tuned Qwen has no API fee, but its GPU time was not metered. It is not “free”.</p></B>
    </div>,
    notes: 'Provider-reported per checkout. The interesting part is not price alone but price against behaviour.' },

  { section: 'Results', title: 'Earlier result', steps: 2, body: <div className="pz-two">
      <div><p className="pz-eyebrow">Oct 29 · direct OpenAI · Terra · guided_nav_v2</p><h2>Layout B needed 19.5% fewer requests.</h2>
        <p className="pz-big">975 → 785 requests</p><p>Two paired repetitions × ten profiles, 20/20 checkouts per layout.</p></div>
      <div><B at={1}><dl className="pz-facts">
          <div><dt>Cost per completed trip</dt><dd>$0.469 → $0.384<small>18.0% lower (estimated)</small></dd></div>
          <div><dt>Moves per shopper</dt><dd>42.00 → 32.95<small>21.5% fewer</small></dd></div>
          <div><dt>List fulfilment</dt><dd>99.06% → 100%</dd></div></dl></B>
        <B at={2}><p className="pz-note">A different collection from the Nov 17 runs (date, transport, assist version). Not pooled with them.</p></B></div>
    </div>,
    notes: '100 × (1 − 785/975) = 19.487%. Cost: $9.380412 vs $7.688224 over 20 completed trips each = 18.04%. Estimated with frozen token prices, not invoices. 200 trips were planned; 80 attempted, 70 completed; one run was interrupted by provider credit and is kept.' },

  // ── Fine-tuning ──────────────────────────────────────────────────────────
  { section: 'Fine-tuning', title: 'divider', body: <div className="pz-divider"><p className="pz-eyebrow">Part 4</p><h1>Can a small open model learn it?</h1><p>QLoRA fine-tuning of Qwen2.5 7B Instruct.</p></div>, notes: 'Transition to fine-tuning.' },

  { section: 'Fine-tuning', title: 'Why', steps: 2, body: <div className="pz-two">
      <div><h2>The untuned 7B model struggles.</h2>
        <div className="pz-three is-tight"><div className="pz-stat"><b>28% / 32%</b>of the list bought<small>A / B</small></div><div className="pz-stat"><b>60% / 90%</b>finished the trip</div><div className="pz-stat"><b>0</b>impulse buys</div></div></div>
      <div><B at={1}><p>Luna and Terra cost money on every call. A local 7B model has no API fee and can run on a laptop.</p></B>
        <B at={2}><p><b>Question:</b> can a small model learn the shopping and impulse policy from the prompt alone, and does it transfer to full trips?</p></B></div>
    </div>,
    notes: 'Baseline: qwen/qwen-2.5-7b-instruct via OpenRouter/Phala on Nov 3, fallbacks off, guided_nav_v2. That endpoint is no longer offered, so it stays as an earlier-run baseline.' },

  { section: 'Fine-tuning', title: 'Data', steps: 4, body: <div><h2>Labels from a rule teacher, run through the real engine.</h2>
      <div className="pz-funnel">
        <B at={1} className="pz-funnel-step"><b>Rule teacher</b><span>hand-written policy: when to move, grab, check out, and when an impulse grab fits the profile</span></B>
        <B at={2} className="pz-funnel-step"><b>210 trips</b><span>35 non-benchmark shoppers × 3 styles × 2 layouts · only actions Python applied unchanged become rows · 0 model calls</span></B>
        <B at={3} className="pz-funnel-step"><b>1,753 / 292 / 284</b><span>train / validation / test rows · split by shopper · the 10 benchmark shoppers never appear</span></B>
        <B at={4} className="pz-funnel-step"><b>745 trained</b><span>250 move · 200 impulse pass · 120 list grab · 50 checkout · all 125 impulse grabs</span></B>
      </div></div>,
    notes: 'This is behaviour cloning of a rule policy, not distillation from GPT. Impulse rule: tier by probability (≥0.40 up to 2 items, ≥0.20 one, ≥0.10 one cheap, <0.10 none) plus diet, allergy, alcohol, price and budget. Teacher grab rate by tier 23/12/4/0%. The split is by shopper because rows within a trip are near-duplicates. The capped mix balances rare decisions; the retrain raised moves from 60 to 250 after the first adapter navigated badly.' },

  { section: 'Fine-tuning', title: 'QLoRA', wide: true, body: <div><h2 className="pz-inline">QLoRA: train small adapters, freeze a 4-bit base. <small>Drag the rank.</small></h2><LoraLab/></div>,
    notes: 'LoRA: instead of updating W, learn a low-rank update B·A. At r=16 on all seven projections across 28 layers that is about 40M parameters, 0.5% of the model; 392 tensors = 28 × 7 × 2, and the 161.5 MB file matches 40M fp32 values. QLoRA: the frozen base is stored in 4-bit NF4, cutting base memory from about 15 GB to about 4-5 GB so 16k-token rows fit on one 40 GB A100.' },

  { section: 'Fine-tuning', title: 'Training run', steps: 1, body: <div className="pz-two">
      <div><h2>The run.</h2><dl className="pz-facts">
        <div><dt>Base</dt><dd>Qwen2.5-7B-Instruct<small>unsloth bnb-4bit, frozen</small></dd></div>
        <div><dt>Adapter</dt><dd>r 16 · α 32 · dropout 0<small>q k v o gate up down</small></dd></div>
        <div><dt>Optimiser</dt><dd>lr 1e-4 linear · AdamW 8-bit<small>batch 1 × accumulation 4 · 2 epochs · bf16</small></dd></div>
        <div><dt>Context</dt><dd>16,384 tokens<small>rows: median 8,521 · max 15,599 · no truncation</small></dd></div>
        <div><dt>Hardware</dt><dd>A100 40 GB · ≈1 hour<small>3,569 s · final loss 0.100</small></dd></div></dl></div>
      <B at={1}><div className="pz-card"><p className="pz-eyebrow">Answer-only loss</p><p>Each row is ~8.5k tokens of observation and ~50 tokens of action JSON. Only the answer is scored; the prompt is context.</p><p className="pz-eyebrow">Frozen for reproducibility</p><p>Base revision, chat-template hash, dataset hash, package versions and adapter hash are saved with the run.</p></div></B>
    </div>,
    notes: 'Unsloth on Colab. Best checkpoint chosen by validation loss every 50 steps. Honest hindsight: plain LoRA on a bf16 base would be more portable, because I also serve the adapter on a Mac with a different quantisation.' },

  { section: 'Fine-tuning', title: 'Offline vs online', steps: 2, body: <div className="pz-two">
      <div><h2>Offline: big gains.</h2><p className="pz-caption">Same 88 validation rows, before and after.</p>
        <BeforeAfter rows={[['Step agreement with teacher', 0.227, 0.864], ['Impulse decisions', 0.288, 0.818], ['Checkout', 0, 1], ['Reply valid for the state', 0.818, 0.989]]}/></div>
      <div><B at={1}><h2>Online: modest gains.</h2><p className="pz-caption">Full trips, ten unseen benchmark shoppers.</p>
          <BeforeAfter rows={[['List bought · A', 0.283, 0.358], ['List bought · B', 0.321, 0.396], ['Finished · A', 0.6, 0.9]]}/></B>
        <B at={2}><p className="pz-note">Offline scores one step from the teacher’s states. In a real trip the model makes its own states, small navigation errors compound, and it runs into the 120-action limit (≈93–99 actions per trip, 35 / 66 invalid replies).</p></B></div>
    </div>,
    notes: 'Impulse grab rate went 0% → 57.6% vs teacher 63.6% on the offline subset (66 of 88 rows are impulse moments, so it mostly measures impulse decisions). Online improved over the base but stays far below Luna/Terra at 96-100%. Fixes: more movement and recovery data, DAgger-style training on the model\'s own rollouts, then re-measure full trips.' },

  // ── Evals ────────────────────────────────────────────────────────────────
  { section: 'Evals', title: 'divider', body: <div className="pz-divider"><p className="pz-eyebrow">Part 5</p><h1>How do I know it worked?</h1><p>Guardrails, stability and sensitivity, without ground truth.</p></div>, notes: 'Transition to evals.' },

  { section: 'Evals', title: 'Guardrails', steps: 2, body: <div className="pz-two">
      <div><h2>Steer during, audit after.</h2>
        <p><b>Steer:</b> the assist changes actions during the run, openly.</p>
        <p><b>Audit:</b> guardrails read the finished recording and flag. They change nothing.</p>
        <B at={1}><ul className="pz-rules"><li><span className="is-fail">fail</span> no checkout · provider error · allergen in an unplanned buy · &gt;20% invalid actions</li><li><span className="is-review">review</span> impulse cap or price · diet mismatch · over budget · list incomplete · loop · stuck 30+ turns</li></ul></B>
        <B at={2}><p className="pz-note">Pass is not proof of realism. Several thresholds, like the impulse cap, are my own conventions.</p></B></div>
      <RunCheckBars/>
    </div>,
    notes: 'In an evaluation harness you observe and flag; blocking an allergen would hide the model\'s mistake. In production you would block. The impulse cap comes from the fine-tuning teacher; if the prompt never stated it, Terra is graded on a rule it was not shown, so it is only ever review.' },

  { section: 'Evals', title: 'Isabella', steps: 3, body: <div className="pz-two">
      <div><h2>12 extra items. Bug or behaviour?</h2>
        <div className="pz-dots"><div><b>Terra</b><span>12</span><span>12</span><span>11</span></div><div><b>Luna</b><span className="is-zero">0</span><span className="is-zero">0</span><span className="is-zero">0</span></div></div>
        <p className="pz-caption">Off-list units for Isabella across runs (A, B, A replicate / A, B, B re-run).</p></div>
      <div><B at={1}><p><b>Stability:</b> same input, same output? Terra repeats within about one unit.</p></B>
        <B at={2}><p><b>Sensitivity:</b> change one field, does behaviour move? Impulse probability 0.45 → 0.05 gave <b>0</b> off-list units (one run: direction only).</p></B>
        <B at={3}><p className="pz-note">Per stop Terra is close to her stated 45% (4 of 8 stops; ≈3.6 expected). Neither model is the baseline: there is no real Isabella.</p></B></div>
    </div>,
    notes: 'Most of the 12 was nine grabs in a row just before checkout: several units at one stop, not more stops. Her chance of doing as well or better by luck is 0.52 on A (4 of 8 stops) and 0.26 on B (5 of 8), so she is not a statistical outlier. Rule of three: 20 of 20 matching runs bounds the failure rate below about 15%; three runs show reproduction, not a rate.' },

  { section: 'Evals', title: 'Claims', steps: 1, body: <div className="pz-two">
      <div className="pz-card is-yes"><p className="pz-eyebrow">I can say</p><ul><li>On ten fixed synthetic shoppers, Terra takes more impulse buys than Luna on both layouts.</li><li>Luna is ≈9× cheaper per checkout with slightly lower fulfilment.</li><li>Fine-tuning improved Qwen offline a lot and in full trips a little.</li><li>Every number traces to a replayable, verified recording.</li></ul></div>
      <B at={1}><div className="pz-card is-no"><p className="pz-eyebrow">I cannot say</p><ul><li>Real customers would behave this way.</li><li>Layout B raises real revenue.</li><li>Any difference is statistically significant (one run per cell).</li><li>Which model is “right” about Isabella.</li></ul></div></B>
    </div>,
    notes: 'This slide pre-empts the hardest questions. Be explicit about synthetic data and sample size.' },

  { section: 'Next', title: 'Next steps', steps: 4, body: <div><h2>Next.</h2><ol className="pz-steps">
      <B at={1} as="li"><b>Sensitivity tests:</b> change one profile field at a time, a few repeats per model.</B>
      <B at={2} as="li"><b>Distil Terra</b> on new, non-benchmark shoppers and compare a rule-taught and a Terra-taught student.</B>
      <B at={3} as="li"><b>Better student:</b> more movement and recovery data, training on its own rollouts, plain LoRA on a bf16 base.</B>
      <B at={4} as="li"><b>Shelf visibility rule:</b> products visible only from adjacent cells, as a new frozen rule version, plus more repetitions per cell.</B>
    </ol></div>,
    notes: 'Each next step is a controlled test with a stated variable. Paid runs need explicit authorisation.' },

  { section: 'Simply', title: 'end', body: <div className="pz-title"><p className="pz-eyebrow">Thank you</p><h1>A model proposes.<br/>Python decides.<br/>Every decision is evidence.</h1><p className="pz-lede">Questions?</p></div>,
    notes: 'Keep the replay slide ready for Q&A.' },
];

export default function Deck() {
  return <DeckShell slides={slides} draft="Overview"/>;
}
