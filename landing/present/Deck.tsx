'use client';

import { B, DeckShell, type Slide } from './kit';
import { AgentFlow, LiveReplay, LoraLab, LossCurve, OfflineOnline, PersonaDial, RecordSnapshot, ResultsTable, RunCheckBars, Shot, ToolCallFlow } from './widgets';

/**
 * The presentation: one technical deck, 17 slides.
 * Story: formulation → architecture → demo → system internals → results → fine-tuning → evals →
 * what broke → scaling. Numbers are quoted from Python-written
 * sources (evidence-dashboard.json, run-checks.json, the adapter ZIP's experiment.json and offline
 * evals, impulse_v3/manifest.json, recorded runs). Code is condensed from the named files.
 * "nav_support" is the deck's name for the navigation assist (policy id guided_nav_v3 in code).
 */

const slides: Slide[] = [
  // ── 1 · Opening ──────────────────────────────────────────────────────────
  { section: 'Overview', title: 'title', body: <div className="pz-two">
      <div><p className="pz-eyebrow">Simply · technical walkthrough · Parthav Joshi</p>
        <h1>Simulating human shopping decisions with LLM agents.</h1>
        <p className="pz-lede">A multi-agent store simulation: each shopper is an LLM agent with a persona and a list. The agent proposes its next step; Python decides what happens and records every decision.</p>
        <div className="pz-chips"><span>Python simulation core</span><span>OpenRouter + local MPS</span><span>React replay over SSE</span><span>4 models × 2 layouts</span><span>QLoRA Qwen 7B</span><span>Guardrails + evals</span></div></div>
      <Shot src="/present/layouts-compare.png" url="localhost:3000/replays · compare" alt="Replay of Terra shoppers in Layout A and Layout B side by side, with impulse pick-ups outlined in amber." caption="Real recording: the same 10 Terra shoppers in Layout A and B, decision 281."/>
    </div>,
    notes: 'Thirty-second version: personas become LLM agents, the agent proposes, Python decides, and every number can be replayed. I built all of it: core, inference, replay UI, studies, fine-tune and evals. Order: formulation, architecture and demo, internals, results, fine-tuning, evals, scaling.' },

  { section: 'Overview', title: 'Formulation', steps: 1, body: <div><h2>The problem, as a decision loop with one owner of the truth.</h2>
      <div className="pz-two">
        <div>
          <p>Same frozen shoppers, two store layouts: what do LLM shoppers <b className="pz-impulse">buy off-list</b>, and do they finish the trip?</p>
          <table className="pz-table"><tbody>
            <tr><th>State</th><td>position, cart, turns used + frozen store and persona</td></tr>
            <tr><th>Observation</th><td>persona text + state JSON + legal steps</td></tr>
            <tr><th>Action</th><td>move · grab(id) · remove(id) · checkout</td></tr>
            <tr><th>Transition</th><td>deterministic, owned by Python</td></tr>
            <tr><th>Horizon</th><td>120 actions, or until checkout</td></tr></tbody></table></div>
        <div><h3>What I measure</h3>
          <dl className="pz-kv">
            <div><dt>Completion</dt><dd>trips finished</dd></div>
            <div><dt>Fulfilment</dt><dd>list units paid for</dd></div>
            <div><dt>Impulse / trip</dt><dd className="pz-impulse">off-list units paid</dd></div>
            <div><dt>Cost</dt><dd>$ per checkout</dd></div></dl>
          <p className="pz-note">Scored from what shoppers <b>paid for</b>, never the model’s stated reasons. No RL: personas are in-context; the fine-tune is supervised.</p></div></div>
      <B at={1}><div className="pz-authority" style={{ marginTop: 20 }}>
        <div className="pz-actor"><b>LLM agent</b><span>proposes one action</span><small>Luna · Terra · Qwen 7B (base / tuned)</small></div>
        <span className="pz-arrow" aria-hidden="true">→</span>
        <div className="pz-actor is-core"><b>Python core</b><span>validates · fixes bad moves (nav_support) · applies · records · scores</span><small>simulation/core · no UI imports</small></div>
        <span className="pz-arrow" aria-hidden="true">→</span>
        <div className="pz-actor"><b>React</b><span>replays and streams, display only</span><small>Next.js · SSE · hash-checked</small></div>
      </div></B>
    </div>,
    notes: 'Finite-horizon decision problem with a Python-owned transition. Formulas if asked: completion = finished trips / trips; fulfilment = paid listed units / requested units; impulse per trip = off-list units in checked-out carts / trips; cost per checkout = provider charge / finished trips; adjusted = assist-changed decisions / decisions. Completion is not fulfilment: you can pay for a partial list. Why one authority: two places that can change state means two truths. The browser never creates a purchase; live view, replay and dashboard all read the same Python records. Evidence numbers are computed in Python (evaluation/dashboard.py), never in React. Facts if asked: store 22 x 14, 15 shelf groups, 303 products; cohort of 10 frozen shoppers; about 8k input tokens and 35 output per request; latest study 4 models x 2 layouts, Nov 17.' },

  { section: 'Overview', title: 'Demo', wide: true, body: <div><h2 className="pz-inline">Live demo: recorded trips, replayed. <small>Pick a model; both layouts advance one recorded decision per tick.</small></h2><LiveReplay/></div>,
    notes: 'Show Terra first: impulse flashes for items not on the list. Then Qwen tuned to show wandering. Nothing calls a model; this replays hash-verified JSONL. Under a minute.' },

  // ── 2 · How it works ─────────────────────────────────────────────────────
  { section: 'How it works', title: 'Agent architecture', wide: true, body: <div><h2 className="pz-inline">From CSV rows to an agent loop. <small>Synthetic, frozen inputs; the same 10 shoppers on every model and layout.</small></h2>
      <AgentFlow/></div>,
    notes: 'Walk left to right. Four files: 50 personas with about 40 fields, their shopping lists, the product catalogue, and the two layouts with the frozen cohort. The persona builder turns a profile and list into prompt text; nothing about the persona changes model weights. Then the loop: Python builds the observation, the agent proposes one action, Python validates, may adjust it with nav_support, applies it, and the new state feeds the next observation. Everything lands in the run log, which drives metrics and replay. If asked: lists were trimmed to fit budget and a greedy route proved every trip finishable in 96 turns; runs store input, layout, engine and provider fingerprints. Layout A puts staples at the back and treats near the entrance; B puts daily essentials near the entrance.' },

  { section: 'How it works', title: 'Tool call and scheduler', wide: true, body: <div><h2 className="pz-inline">One reply, one action. <small>The model never touches state; it proposes a call and Python decides.</small></h2>
      <ToolCallFlow/>
      <B at={1}><ul className="pz-sched">
        <li><b>Many shoppers at once.</b> One pending request each; commit whatever is ready, so a slow call never stalls a fast one.</li>
        <li><b>Single writer.</b> Workers only return proposals, so there are no locks.</li>
        <li><b>Snapshot first.</b> The observation is frozen before the call, so the reply matches what the shopper saw.</li></ul></B></div>,
    steps: 1,
    notes: 'Scheduler (from the old pipeline slide): Default 10 workers; OpenRouter runs used 2 at 60 requests a minute. Threads, not asyncio: provider SDK calls block and the work is network-bound. The observation is snapshotted before submit. Shoppers are independent today (no shared stock), so commit order does not change outcomes. Shared inventory would need reservations. Tool call: This is our tool call, without a provider tool-calling API. Python lists the legal steps in the prompt, which act as the tool list. The model replies with one strict JSON call: step, product_id, reason. Python parses it and checks the step is allowed and the item reachable; failures are recorded as invalid_decision. nav_support may swap the action; we record both the original and the adjusted one. Python then executes it on the grid, and a rejected action is grid_rejected. Every outcome goes to the run log and into the next observation. The model has no side effects of its own.' },


  { section: 'How it works', title: 'Model call: interface and cost', steps: 1, body: <div className="pz-two">
      <div><h2>One model call: observe, propose, validate.</h2>
        <p>Each call is stateless; the shopper’s memory lives in Python. Every turn Python rebuilds one prompt: persona, position, cart, budget, reachable products, map, plus the last 8 actions and 12 positions. Output is strict JSON, max 256 tokens, reasoning off.</p>
        <B at={1}><table className="pz-table"><thead><tr><th>Gate</th><th>Fails as</th><th>Luna A / B</th><th>Tuned Qwen A / B</th></tr></thead><tbody>
          <tr><th>Schema + legal step + reachable item</th><td>invalid_decision</td><td>12 / 9</td><td>35 / 66</td></tr>
          <tr><th>Apply on the grid</th><td>grid_rejected</td><td>1 / 0</td><td>1 / 1</td></tr>
          <tr><th>Transport / API</th><td>provider_exception</td><td>0 / 0</td><td>0 / 0</td></tr></tbody></table>
          <p className="pz-caption">Terra: zero invalid, zero rejected. Every failure still costs a turn.</p></B></div>
      <div><h2>Cost, latency and serving identity.</h2>
        <table className="pz-table"><thead><tr><th>Per request</th><th>In tok</th><th>Out tok</th><th>p50 / p95</th></tr></thead><tbody>
          <tr><th>Terra A</th><td>7,994</td><td>34.3</td><td>1.98 / 2.91 s</td></tr>
          <tr><th>Luna A</th><td>7,769</td><td>39.4</td><td>1.24 / 1.98 s</td></tr>
          <tr><th>Qwen tuned A</th><td>6,050</td><td>30.7</td><td>0.97 / 1.39 s</td></tr></tbody></table>
        <B at={1}><ul><li><b>Pinned:</b> dated model IDs, one provider, no fallbacks, no plugins.</li>
          <li><b>Two ledgers:</b> token estimate vs what OpenRouter billed.</li>
          <li>Unknown usage is reserved, never zeroed.</li></ul></B></div>
    </div>,
    notes: 'Schema validity is not physical validity. Separate failure classes tell you which system failed: model, physics or infrastructure. About 8k input vs 35 output tokens means cost is driven by the observation. Cost and serving: Without pinning, a router can silently serve a different backend and change the system under test. Estimate = tokens × price snapshot frozen per run; Terra A estimate and billed both $5.1832. Simulated basket dollars never mix with API dollars. Input dominates cost, so a cached stable prefix is the first cost lever.' },

  { section: 'How it works', title: 'nav_support', steps: 2, body: <div className="pz-two">
      <div><h2>nav_support: fixed rules that correct bad navigation.</h2>
        <p>LLMs walk a grid badly: they wander and run out of turns. nav_support checks each proposed step and replaces it only when a simple rule says so.</p>
        <div className="pz-override"><p className="pz-eyebrow">Recorded · Terra · Layout A · decision 140 · Mia</p>
          <p><span className="pz-tag">Model proposed</span> <code>move_down</code> “continue down the aisle toward checkout”</p>
          <p><span className="pz-tag is-assist">Applied</span> <code>move_right</code> “head toward checkout”</p></div>
        <B at={1}><table className="pz-table"><thead><tr><th>Decisions adjusted</th><th>A</th><th>B</th></tr></thead><tbody>
          <tr><th>Terra</th><td>6.1%</td><td>5.4%</td></tr><tr><th>Luna</th><td>8.4%</td><td>4.7%</td></tr>
          <tr><th>Qwen base / tuned</th><td>38.7% / 13.1%</td><td>35.6% / 14.3%</td></tr></tbody></table></B>
        <B at={2}><p className="pz-note"><b>Bug I caught:</b> v1/v2 swapped a model’s impulse grab for a list item, erasing what I was measuring. v3 keeps it.</p></B></div>
      <div className="pz-card"><p className="pz-eyebrow">Rules, first match wins</p><ol className="pz-steps">
        <li><b>≤ 15 turns left</b>, cart not empty → check out.</li>
        <li><b>Impulse grab</b> within reach → keep it (v3).</li>
        <li><b>List item</b> within reach → grab it.</li>
        <li><b>Already owned</b> → step to the least-visited cell.</li>
        <li><b>List done or &lt; 30% turns</b> → head to checkout.</li>
        <li><b>Nothing in reach</b>, busy cell → pick a fresher one.</li></ol></div>
    </div>,
    notes: 'In code the policy id is guided_nav_v3; nav_support is the plain name. Without it, models waste their 120 actions wandering and the comparison becomes about navigation. The adjusted share is itself a quality signal: base Qwen 36-39%, Terra 6% (31 of 510). choose() keeps the proposal when it already matches, otherwise records both. Honest confound: no model-only ablation yet, so results are model + nav_support. v1 and v2 stay in code because old recordings verify against them.' },

  { section: 'How it works', title: 'Recording and verification', steps: 1, body: <div className="pz-two">
      <div><h2>The recording is the evidence, and it is re-checked.</h2>
        <RecordSnapshot/></div>
      <B at={1}><div className="pz-card"><p className="pz-eyebrow">How it is re-checked</p><ol className="pz-steps">
        <li><b>Integrity:</b> SHA-256 on every file.</li>
        <li><b>Re-check:</b> re-run nav_support on every recorded state.</li>
        <li><b>Cross-language:</b> Python and TypeScript rebuild identical frames.</li>
        <li><b>Replay ≠ re-inference:</b> a fresh run is a new sample.</li></ol></div></B>
    </div>,
    notes: 'Recompute, do not trust. Works because adjusted_action is a pure function of saved inputs. run_start stores config, layout, catalogue, shoppers, frozen pricing and fingerprints. Storing prompt and raw reply lets me re-score offline without API calls. Live SSE streams only flushed lines, so live and replay read the same bytes. No request seeds, so re-running is not replay.' },


  // ── 3 · Results ──────────────────────────────────────────────────────────
  { section: 'Results', title: 'Results', wide: true, steps: 2, body: <div><h2 className="pz-inline">Same 10 shoppers, four models, two layouts. <small>Nov 17 · each model ran once per layout</small></h2>
      <ResultsTable/>
      <B at={1}><div className="pz-two" style={{ marginTop: 12 }}>
        <p><b>Models:</b> Luna and Terra finish every trip. Terra buys more off-list (2.2 vs 1.5 per trip on A) at ≈ 8–9× Luna’s cost per checkout. A trade-off, not a ranking.</p>
        <p><b>Layouts:</b> B needs fewer requests for both (Terra 51 → 41, Luna 61 → 51) and fewer impulse buys. One run each, so directional only.</p></div></B>
      <B at={2}><div className="pz-card" style={{ marginTop: 12 }}>
        <p className="pz-eyebrow">Earlier study · Oct 29 · Terra via OpenAI · 10 shoppers × 2 repetitions</p>
        <dl className="pz-kv">
          <div><dt>Requests, B vs A</dt><dd>−19.5%<small>975 → 785</small></dd></div>
          <div><dt>Cost / trip</dt><dd>−18.0%<small>$9.38 → $7.69 over 20 trips</small></dd></div>
          <div><dt>Moves / shopper</dt><dd>−21.5%<small>42.0 → 33.0</small></dd></div>
          <div><dt>Checkouts</dt><dd>20 / 20<small>both layouts</small></dd></div></dl>
        <p className="pz-caption">Not 20 people: 10 profiles × 2 runs, so compare pairs. 80 trips attempted, 70 completed; failed runs are kept. Not pooled with Nov 17: different transport and nav_support version.</p></div></B></div>,
    notes: 'Fulfilment: Luna 96/100, Terra 100/100, Qwen base 28/32, tuned 36/40. Completion: base 60/90, tuned 90/100. Impulse per trip A/B: Luna 1.5/0.4, Terra 2.2/2.0. Cost per checkout: Terra $0.52/$0.40, Luna $0.06/$0.05. Qwen base is an earlier run (Nov 3, older nav_support v2). Descriptive, no intervals, no significance claim. Earlier study (the resume result): 100 x (1 - 785/975) = 19.487%; $9.380412 vs $7.688224 is 18.04%; moves 42.00 vs 32.95 is 21.55%. Moves differ from requests because requests include grabs, checkout and invalid replies. Fulfilment 99.06% vs 100%. Planned 200 trips, attempted 80, completed 70. Estimated cost uses frozen token prices.' },

  // ── 4 · Fine-tuning ──────────────────────────────────────────────────────
  { section: 'Fine-tuning', title: 'Teacher and data', steps: 2, body: <div className="pz-two">
      <div><h2>Can a free local 7B model learn the policy?</h2>
        <p>Untuned Qwen2.5 7B bought <b>28–32%</b> of the list, finished <b>60–90%</b> of trips, and made 0 impulse buys.</p>
        <B at={1}><p><b>Labels from a deterministic rule teacher</b> run through the real core. Only actions the core applied unchanged became training rows. Behaviour cloning, not distillation.</p>
          <table className="pz-table"><thead><tr><th>Tier</th><th>p</th><th>Cap</th><th>Max price</th></tr></thead><tbody>
            <tr><th>impulsive</th><td>≥ 0.40</td><td>2</td><td>$8.00</td></tr><tr><th>mixed</th><td>≥ 0.20</td><td>1</td><td>$4.00</td></tr>
            <tr><th>planner</th><td>≥ 0.10</td><td>1</td><td>$2.50</td></tr></tbody></table></B></div>
      <B at={2}><div><table className="pz-table"><thead><tr><th>Label</th><th>Available</th><th>Trained</th></tr></thead><tbody>
          <tr><th>move</th><td>291</td><td>250</td></tr><tr><th>impulse_pass</th><td>767</td><td>200</td></tr>
          <tr><th>impulse_grab</th><td>125</td><td>125</td></tr><tr><th>list_grab</th><td>444</td><td>120</td></tr>
          <tr><th>checkout</th><td>126</td><td>50</td></tr><tr><th>total</th><td>1,753</td><td>745</td></tr></tbody></table>
        <p><b>Split by shopper</b>, benchmark shoppers excluded. The first adapter had 60 move rows and got lost; the retrain used 250.</p></div></B>
    </div>,
    notes: 'Impulse probability only selects a tier; within a tier the teacher takes the cheapest eligible item, no sampling. Grab rates: 23 / 12 / 4%. 210 teacher trips: 35 non-benchmark shoppers × 3 styles × 2 layouts. Splits 1,753 / 292 / 284. Split by shopper because rows in one trip are near-duplicates. Why a rule teacher: free, clean, controllable labels; Terra would bake in its quirks, cost money, and my Terra recordings use the benchmark shoppers, so training on them would leak the test set. Distilling Terra on new shoppers is next.' },

  { section: 'Fine-tuning', title: 'QLoRA', wide: true, steps: 1, body: <div><h2 className="pz-inline">QLoRA: a frozen 4-bit base plus small trainable adapters. <small>Drag the rank.</small></h2>
      <div className="pz-two"><LoraLab/>
        <div><code className="pz-formula">h = W₀x + (α/r)·BAx</code>
          <p>W₀ stays frozen in 4-bit; only the low-rank A and B train. At r = 16 that is <b>40.4M parameters (0.53%)</b>, a 161.5 MB file.</p>
          <LossCurve/>
          <B at={1}><dl className="pz-kv">
            <div><dt>Base</dt><dd>Qwen2.5 7B<small>4-bit NF4, frozen</small></dd></div>
            <div><dt>Adapter</dt><dd>r 16 · α 32<small>all 7 projections</small></dd></div>
            <div><dt>Optimiser</dt><dd>AdamW 8-bit<small>lr 1e-4 · 2 epochs</small></dd></div>
            <div><dt>Loss</dt><dd>answer-only<small>~35 target tokens</small></dd></div>
</dl></B></div></div></div>,
    notes: 'Run: about 1 hour on an A100 40 GB, 374 steps, reported training loss 0.100 (average over the run), best checkpoint by validation loss. Context 16,384 tokens; rows median 8,521, max 15,599. B starts at zero so training starts from the base model. Per layer 16 × 90,112 = 1,441,792; × 28 layers = 40.4M; 392 tensors = 28 × 7 × 2; × 4 bytes = 161.5 MB. k/v are small because of grouped-query attention. Why QLoRA: 4-bit base cuts weights from ~15 GB to 4-5 GB, leaving room for 16k-token activations on one 40 GB A100; full fine-tuning would overfit 745 rows. Hindsight: plain LoRA on bf16 would be more portable since I serve on Mac MPS/MLX.' },


  // ── 5 · Evals ────────────────────────────────────────────────────────────

  { section: 'Fine-tuning', title: 'Serving, results and fixes', steps: 1, body: <div>
      <h2 className="pz-inline">Fine-tuned model: served on a Mac, strong offline, modest online. <small>Then four fixes.</small></h2>
      <div className="pz-two">
        <div><h3>Trained on a cloud GPU, made to run on a Mac</h3>
          <ol className="pz-steps">
            <li><b>Train:</b> Colab A100, 4-bit NF4 base → 161.5 MB adapter.</li>
            <li><b>Problem:</b> NF4 only runs on NVIDIA GPUs, so it would not load on my Mac.</li>
            <li><b>Fix:</b> re-quantize the base for Apple’s GPU (MPS) and attach the adapter.</li>
            <li><b>Result:</b> works, but ≈ 114 s per decision.</li></ol>
          <table className="pz-table"><thead><tr><th>Where it ran</th><th>Per decision</th><th>Used for</th></tr></thead><tbody>
            <tr><th>Colab A100 · NF4</th><td>0.97 s</td><td>recorded A/B results</td></tr>
            <tr><th>Mac · MPS int4</th><td>≈ 114 s</td><td>local pilot</td></tr>
            <tr><th>Mac · MLX int4</th><td>≈ 21 s</td><td>faster local</td></tr></tbody></table>
          <p className="pz-caption">Each setup is a <b>separate model</b>; I never mix their results.</p></div>
        <div><h3>One tuned model, two tests</h3>
          <OfflineOnline groups={[
            { title: 'Offline: big gains', sub: 'one decision at a time · 88 validation rows', rows: [['Step agreement', 0.227, 0.864], ['Impulse decisions (66)', 0.288, 0.818], ['Checkout (8)', 0, 1]] },
            { title: 'Online: modest gains', sub: 'full trips · 10 unseen shoppers', rows: [['Fulfilment A', 0.283, 0.358], ['Fulfilment B', 0.321, 0.396], ['Completion A', 0.6, 0.9]] }]}/>
          <p className="pz-caption"><b>Why:</b> offline it sees the teacher’s states; online it visits its own, so errors compound (≈ 95 actions per trip vs 46).</p></div></div>
      <B at={1}><div className="pz-grid4 pz-fixes">
        <div className="pz-card"><p><b>1 · Train on its own mistakes.</b> The teacher labels the states the student reaches (DAgger).</p></div>
        <div className="pz-card"><p><b>2 · Teach recovery.</b> Examples that start off-route or stuck.</p></div>
        <div className="pz-card"><p><b>3 · Constrain the output.</b> Only legal JSON and steps.</p></div>
        <div className="pz-card"><p><b>4 · Train how you serve.</b> bf16 LoRA, same precision, shorter prompt.</p></div></div></B></div>,
    notes: 'Offline also: reply valid for state 81.8% → 98.9%. Serving: Training and serving precision did not match: bitsandbytes NF4 is CUDA-only. These timings are from the pilot adapter. On the Mac the official base was quantized to int4 (Quanto for MPS, MLX q4 group 64) and the unchanged adapter loaded on top; adapter hash, base revision, tokenizer and package versions are saved in every run. MPS and MLX timings were each measured once on an M3 Pro. That mismatch is why LoRA on a bf16 base would have been more portable. The local server listens only on 127.0.0.1, one generation at a time, and never falls back to a paid API. Results: The key ML lesson: per-step agreement is necessary but not sufficient; the task metric is the finished trip. Impulse grab rate 0% → 57.6% vs teacher 63.6%. Only 4 move rows in the offline subset. 35 / 66 invalid replies each burn a turn. Base row is an earlier run under v2, so not perfectly matched. Four fixes: Order by expected payoff. 1 attacks the core problem from the offline vs online slide: the student drifts into states the teacher never visited. 2 is cheap data generation with the same rule teacher. 3 is grammar-constrained decoding (JSON schema plus the allowed-step enum for this state); it cannot make a bad move good, but it stops wasted turns. 4 removes the NF4 vs int4 mismatch and cuts input tokens; median training row was 8.5k tokens. Then a matched base-vs-tuned rerun on the same day and serving setup. Distilling Terra on non-benchmark shoppers is a separate experiment.' },



  { section: 'Evals', title: 'Guardrails and the persona dial', wide: true, steps: 1, body: <div>
      <h2 className="pz-inline">Checking the agents. <small>Does a shopper follow its persona, and did the run stay clean?</small></h2>
      <PersonaDial/>
      <B at={1}><div className="pz-two pz-guard">
        <div><p><b>During the run (steer):</b> nav_support swaps a bad step for a better one; both are saved.</p>
          <p><b>After the run (audit):</b> a checker reads the finished recording and flags problems, such as an allergen bought or a shopper stuck in a loop. It never changes the result.</p>
          <ul className="pz-rules"><li><span className="is-fail">fail</span> no checkout · provider error · allergen bought · &gt; 20% invalid</li>
            <li><span className="is-review">review</span> over impulse cap · diet mismatch · over budget · loops · stuck</li></ul>
          <p className="pz-caption">In an eval, blocking an allergen would hide the mistake, so I flag it. In production I would block.</p></div>
        <RunCheckBars/></div></B></div>,
    notes: 'Persona dial: Each dot is one shopper in one recorded Nov 17 trip: x is the impulse_buy_probability in the profile, y is paid off-list units (Python). Terra: higher settings buy more (Isabella, 0.45, bought 12); Luna mostly stays near zero; the tuned Qwen is mostly flat, so it barely responds to the dial. The slider only highlights shoppers at or above a setting; it does not change any run. The probe on the right is the real one-field test: Isabella on Terra, Layout A, setting 0.45 gave 12 and 11 impulse units, setting 0.05 gave 0 (one completed run). One run per cell, ten shoppers: direction only, not a rate. Not a model of real customers. Guardrails: Thresholds like impulse caps and 5% / 20% are my own conventions, so a pass is not proof of realism. The impulse cap is a teacher rule the prompt may never have stated, so tripping it is only ever a review. Qwen runs fail on unfinished checkout, incomplete lists, loops and stuck shoppers.' },

  { section: 'Evals', title: 'Isabella', steps: 2, body: <div className="pz-two">
      <div><h2>Debugging a surprising behaviour: Isabella.</h2>
        <table className="pz-table"><thead><tr><th>Off-list units</th><th>Run 1</th><th>Run 2</th><th>Run 3</th></tr></thead><tbody>
          <tr><th>Terra</th><td>12</td><td>12</td><td>11</td></tr><tr><th>Luna</th><td>0</td><td>0</td><td>0</td></tr>
          <tr><th>Terra, p = 0.05</th><td colSpan={3}>0 (one-field probe)</td></tr></tbody></table>
        <B at={1}><p>Per stop, Terra matches her 45% impulse rate. The volume comes from several units at one stop just before checkout.</p></B>
        <B at={2}><p className="pz-note"><b>Eval loop:</b> reproduce → repeat (≈ 1 unit spread over 3 runs) → change one field (0.45 → 0.05 moved 12 → 0).</p></B></div>
      <B at={1}><Shot src="/present/isabella-trip.png" url="localhost:3000/replays · Terra · Layout A" alt="End of Isabella Rossi's Terra trip: 12 impulse items outlined in amber on the map, $111.97 spent of a $113.13 budget." caption="Real recording: Isabella’s Terra trip ends with 12 impulse items, $111.97 of $113.13."/></B>
    </div>,
    notes: 'Debugging non-determinism story. Point at the amber outlines clustered in Snacks and Bakery near checkout. Binomial(8 stops, 0.45): expected 3.6; P(X ≥ 4) = 0.52, P(X ≥ 5) = 0.26; Terra grabbed at 4 of 8 and 5 of 8 stops. Rule of three: 0 failures in n runs means rate < 3/n at 95%, so three runs show reproduction, not a rate. Predict direction first and add a null control. Do not say Terra over-buys or Luna is more realistic.' },

  { section: 'Evals', title: 'What broke', steps: 1, body: <div className="pz-two">
      <div className="pz-card"><p className="pz-eyebrow">What broke, and the fix</p>
        <p><b>Fine-tuning</b></p><ul>
          <li>First adapter got lost in the store: only 60 movement examples → retrained with 250.</li>
          <li>Adapter would not load on a Mac (NVIDIA-only 4-bit) → re-quantized the base for MPS.</li></ul>
        <p><b>Simulation</b></p><ul>
          <li>nav_support v1/v2 swapped out impulse grabs, the thing I measure → v3 keeps them.</li>
          <li>Provider failures (content filter, credit ran out, model removed) → runs kept, never silently retried or swapped.</li></ul></div>
      <B at={1}><div className="pz-card is-no"><p className="pz-eyebrow">Limits, in plain words</p><ul>
        <li><b>One run per model per layout:</b> no error bars yet.</li>
        <li><b>No ablation:</b> I haven’t re-run with nav_support switched off, so results are model + nav_support.</li>
        <li><b>No seeds:</b> the APIs can’t fix their randomness, so a re-run can differ. That is why every reply is saved.</li>
        <li><b>Synthetic shoppers:</b> impulse rates are chosen, not measured.</li>
        <li><b>The student</b> can at best learn my rules.</li></ul></div></B>
    </div>,
    notes: 'Ablation means removing one component and re-running to see what it contributed; here, a model-only run without nav_support. A seed fixes the random sampling so the same input gives the same output; OpenRouter and these models do not support request seeds, so replay of the recording is exact but re-running is a new sample. Details if asked: the content filter aborted Luna B after 548 actions on an ordinary prompt and is excluded from the headline; the Qwen base endpoint returned 404 on OpenRouter, so the base row is an earlier Nov 3 run. Stating limits first is the strongest move.' },

  // ── 6 · Scale ────────────────────────────────────────────────────────────
  { section: 'Scale', title: 'Scaling', steps: 1, body: <div className="pz-two">
      <div><h2>Scaling it: what breaks first.</h2>
        <table className="pz-table"><thead><tr><th>1,000 shoppers per layout</th><th>Terra</th><th>Luna</th></tr></thead><tbody>
          <tr><th>Requests per layout</th><td>≈ 46k</td><td>≈ 56k</td></tr>
          <tr><th>Wall time at 60 req/min</th><td>≈ 13 h</td><td>≈ 16 h</td></tr>
          <tr><th>Cost, both layouts</th><td>≈ $900</td><td>≈ $110</td></tr></tbody></table>
        <p className="pz-caption">From recorded per-trip figures. Rate limits, not compute, are the bottleneck.</p></div>
      <B at={1}><div><h3>What I would change</h3>
        <ul><li><b>Throughput:</b> higher rate tier or sharded keys.</li>
          <li><b>Cost:</b> cache the stable prompt prefix; trim the observation.</li>
          <li><b>Shared stock:</b> atomic reserve, still one writer.</li>
          <li><b>Workers:</b> a queue with idempotent request IDs.</li>
          <li><b>Stats:</b> ≥ 5 runs per cell with bootstrap intervals.</li></ul></div></B>
    </div>,
    notes: 'Terra ≈ 46 requests per trip (A 51, B 41), Luna ≈ 56 (60.7 / 51.3). Cost uses Luna ≈ $0.056 and Terra ≈ $0.46 per checkout. Idempotent IDs stop retries after ambiguous timeouts from double-charging or double-applying. JSONL per run is fine for tens of runs; hundreds need an index or columnar store. For real stores: planogram → grid, product master → catalogue, calibrate impulse on real baskets. The local tuned 7B is ≈ 0.97 s p50 with no API fee, but needs better navigation first.' },

  { section: 'Scale', title: 'Close', steps: 1, body: <div className="pz-two">
      <div><p className="pz-eyebrow">Summary</p><h1>The agent proposes. Python decides, records and verifies.</h1>
        <p className="pz-lede">Built end to end; measured honestly; every number replayable.</p></div>
      <B at={1}><div className="pz-card"><p className="pz-eyebrow">Next experiments, one variable each</p><ol>
        <li><b>Ablation:</b> model only vs model + nav_support.</li>
        <li><b>Sensitivity grid:</b> one persona field at a time.</li>
        <li><b>≥ 5 runs per model and layout</b> with intervals.</li>
        <li><b>Distil Terra</b> on non-benchmark shoppers.</li>
        <li><b>Better student:</b> the four steps on slide 12.</li></ol>
        <p>Questions? Demo (slide 3) and LoRA (slide 11) are good places to go deeper.</p></div></B>
    </div>,
    notes: 'End on the one-line architecture and what you would do next. Keep the replay and QLoRA slides ready for questions.' },
];

export default function Deck() {
  return <DeckShell slides={slides} dense/>;
}
