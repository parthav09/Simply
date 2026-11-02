import 'server-only';
import type { Question, QuizQuestion } from './types';

// Authored distractors target specific misconceptions; no model calls are used.
// Correct choices start first here and are shuffled before each quiz begins.
const items: Record<string, [string, string, string, string, string]> = {
'agent': ['Which sequence describes one Simply shopper decision?', 'Observe → model proposal → validation/assistance → Python application → canonical recording.', 'Model proposal → browser route generation → Python summary → recording.', 'Observe → model directly updates the cart → schema validation → recording.', 'Generate a complete shopping plan once → animate it → infer outcomes from the animation.'],
'personas': ['What changes when Simply conditions a shopper on a persona?', 'The request context includes profile preferences and task facts; the model weights need not change.', 'A separate fine-tuned checkpoint is loaded for every profile.', 'The engine turns every spending preference into a hard purchase constraint.', 'The persona replaces current observations so the model relies only on personality.'],
'multiagent': ['Which description accurately captures Simply’s current multi-agent behavior?', 'Independent persistent shoppers have concurrent decision loops, without shopper-to-shopper negotiation.', 'A manager shopper delegates items to specialist shoppers through messages.', 'Shoppers coordinate through scarce stock reservations and checkout queues.', 'Each API response creates a new agent without persistent task identity.'],
'orchestration': ['Which responsibility belongs to RoundCoordinator rather than the provider or browser?', 'Schedule and resolve proposals, then send ready decisions through authoritative execution.', 'Change model weights based on each shopper’s reward.', 'Compute paid purchases from the map animation.', 'Let provider worker threads mutate carts as soon as responses arrive.'],
'concurrency': ['Shopper A’s call takes 20 seconds; B’s takes one second. What does the coordinator permit?', 'B’s ready result can commit while A remains pending; provider workers do not mutate state.', 'All shoppers wait for A because every round has an all-worker barrier.', 'B’s provider worker commits the cart independently of the session owner.', 'B’s next nineteen actions are inferred without new observations to match A’s wait.'],
'snapshots': ['Why detach the observation before asynchronous inference?', 'To bind a proposal to consistent inputs rather than mutable state that can change while work is pending.', 'To make the Python GIL guarantee business-level transaction isolation.', 'To guarantee another shopper cannot invalidate scarce inventory in a future extension.', 'To ensure hosted-model outputs are identical across fresh runs.'],
'validation': ['A response is valid action JSON but names an unreachable product. Which conclusion is justified?', 'Schema success does not establish physical validity; execution can reject the pickup.', 'Structured output guarantees the pickup is physically valid.', 'The browser should move the shopper next to that product before applying the pickup.', 'The product should count as purchased because the model expressed an intent to buy it.'],
'authority': ['Which rule applies to new unique_single_checkout_v1 runs?', 'One unit per SKU, duplicate pickups rejected, and one valid checkout action pays.', 'Repeated pickups are allowed whenever the shopper remains under budget.', 'The first checkout action enters a payment state and the second always pays.', 'A browser checkout animation is sufficient evidence of a paid purchase.'],
'assist': ['The model proposes moving, but gary2_v2 replaces it with a reachable target pickup. How should success be attributed?', 'To the assisted model-plus-policy system, preserving both proposed and applied actions.', 'Entirely to the model, because the model initiated the request.', 'Entirely to the browser, because it displays the pickup.', 'To unassisted model intelligence, provided both arms use gary2_v2.'],
'plans': ['Could the reported 19.5% request reduction be explained as one arm using multi-action batching?', 'No: the reported study matched a single-action interface across arms.', 'Yes: all gary2_v2 studies execute up to eight actions per response.', 'Yes: concurrent inference is another name for action batching.', 'No: request counts are mathematically identical to successful move counts.'],
'providers': ['Which practice preserves a valid provider/model comparison?', 'Freeze provider, model identity and price snapshot per run, and keep the OpenRouter collection separate.', 'Pool runs whenever their dropdown display labels match.', 'Change the model during a run if the replacement belongs to the same family.', 'Replace historical provider identities with the current default to simplify the table.'],
'lifecycle': ['The browser disconnects while a model call is pending. What should reconnect do?', 'Restore the same identified Python session without silently starting another run.', 'Launch a new session and merge its events with the old run.', 'Reapply every streamed action to ensure no action was missed.', 'Clear unknown-charge reservations because the browser did not receive a response.'],
'log': ['Why stop further execution if canonical recording fails?', 'Continuing would create transitions without the required auditable evidence.', 'JSONL logging is what physically moves the shopper.', 'A logging failure proves the provider returned invalid JSON.', 'The browser can reconstruct any missing transition from shopper intent.'],
'determinism': ['What does deterministic replay guarantee?', 'The same valid saved recording reconstructs the same recorded states and metrics.', 'Fresh hosted-model calls generate exactly the same proposals.', 'Concurrent requests finish in the same order on every new run.', 'A fixed temperature eliminates all serving and scheduling variability.'],
'sse': ['A reconnect delivers a duplicated SSE event. Which response preserves the authority boundary?', 'Validate identity/sequence and handle it as transport data, without executing the shopping action again.', 'Apply the action again because every message is an execution command.', 'Recompute the purchase in React and overwrite Python’s totals.', 'Start a new model run so sequence numbers restart at one.'],
'money': ['A valid pickup exceeds a shopper budget and a provider request has unknown usage. What is correct?', 'Record valid overspending and preserve the unknown-charge reservation separately.', 'Reject the pickup and report the provider charge as zero.', 'Count basket dollars as API charges until the provider responds.', 'Apply a historical campaign spending cap to every manual session.'],
'errors': ['Why is Luna Layout B’s all-attempt 10/20 checkout result not a clean model-quality finding?', 'One run was provider-credit interrupted, preventing payment; the interruption remains visible.', 'The comparison used twenty independently sampled human customers.', 'The failed run is a statistical outlier and should be deleted.', 'Every unfinished basket proves the layout caused a navigation failure.'],
'frozen': ['To isolate layout placement within a model, which comparison is appropriate?', 'Match cohort, lists, prices, prompts, limits and assistance; change placement.', 'Change placement and assistance together so both conditions are optimized.', 'Compare Luna on A against Terra on B and label the difference a layout effect.', 'Choose a different cohort in each layout to eliminate repeated profiles.'],
'metrics': ['How can checkout completion be 100% while purchased-list fulfillment is below 100%?', 'Every shopper can pay for a basket that omits some requested products.', 'Reaching the checkout cell counts as payment even with an empty cart.', 'Fulfillment includes unpaid baskets while completion includes only paid baskets.', 'Completion and fulfillment use the same numerator and denominator, so they must match.'],
'pairing': ['The Terra contrast has ten profiles executed twice per layout. What is the correct sample interpretation?', 'Twenty trip observations per layout from ten repeated synthetic profiles in two paired blocks.', 'Twenty independently sampled people per layout.', 'Forty independent repetition blocks because there are forty trips overall.', 'Nine hundred seventy-five independent samples because A submitted that many requests.'],
'cost': ['Which formula defines estimated API cost per completed trip for a stated included subset?', 'Included estimated API costs divided by completed paid checkouts, with unknown costs disclosed.', 'Included estimated API costs divided by all attempts, regardless of the label.', 'Basket sales divided by submitted model requests.', 'Mean token count divided by shopper dollar budgets.'],
'uncertainty': ['What does the trip-level interquartile range establish?', 'Descriptive spread of the recorded trip outcomes, not a confidence interval for a general layout effect.', 'A 95% confidence interval for the population layout improvement.', 'Statistical significance if the two medians differ.', 'Independence of repeated profiles when there are at least twenty trips.'],
'verification': ['What does Python/TypeScript replay-equivalence testing directly support?', 'Both readers reconstruct matching saved states under the evidence contract.', 'Synthetic personas predict real customer behavior.', 'A fresh model run must produce the original result.', 'The observed layout difference generalizes to any retailer.'],
'boundaries': ['Which claim is supported at the documented project stage?', 'Agent execution and controlled evaluation exist; Qwen baseline/tuned outcome rows remain N/A.', 'A trained Qwen policy has replaced the hosted models in live production.', 'Persona conditioning has validated human purchasing realism.', 'Concurrent calls implement inter-agent negotiation and reinforcement learning.'],
'harness': ['What makes Simply a harness rather than merely a model wrapper?', 'It defines tasks, execution/state contracts, records and evaluation around model proposals.', 'It supplies a universal domain-independent action validator without additional work.', 'It changes model weights during every shopper decision.', 'It treats React’s animation state as the source of outcome truth.'],
'context-memory': ['What does the informed prompt provide for navigation history?', 'Explicit recent action/position windows, visit counts and a last public plan reason.', 'An internal learned memory that persists inside the hosted model between all shoppers.', 'A shortest path guaranteed by the Manhattan checkout-distance value.', 'Permission to grab every product visible anywhere on the map.'],
'synthetic-teacher': ['Who produced the supervised demo labels?', 'A deterministic scripted_test teacher, with real Python execution validating its actions.', 'Luna and Terra model calls enrolled from the paid main matrix.', 'Human shoppers observed in a real store.', 'A completed fine-tuned Qwen policy using reinforcement learning.'],
'group-split': ['Which split reduces leakage between related route states in the demo?', 'Keep both layouts of each mission together: missions 1–4 train, 5 validate, 6 test.', 'Randomly split every action row independently across all three sets.', 'Train on Layout A and test on the same mission’s Layout B while claiming unseen missions.', 'Use the test set to choose settings, then report that same test as untouched.'],
'qlora': ['Which explanation of QLoRA SFT is correct?', 'Supervised response prediction with trainable low-rank adapters and a frozen quantized base.', 'Reinforcement learning that updates every base weight using checkout rewards.', 'Training every model weight directly in four-bit precision without adapters.', 'A standalone adapter that runs without its compatible base model or tokenizer.'],
'mask-context': ['What should assistant-only loss do for these training examples?', 'Retain the full observation as context while masking user tokens from the response-prediction loss.', 'Remove the user observation from the model input entirely.', 'Optimize primarily for reproducing the long user prompt.', 'Truncate every example to 2,048 tokens even when this removes the target.'],
'resume': ['Which statement most precisely defends the resume result?', 'Terra’s two paired synthetic repetitions showed fewer requests and lower estimated cost in B under matched assistance.', 'A completed five-repetition study proved all shoppers need 19.5% fewer calls.', 'Independent human trials showed an 18.0% reduction in retail operating costs.', 'The result isolates unassisted model intelligence across every provider.'],
'arithmetic': ['A submitted 975 requests and B 785, with 20 completions each. Which calculation gives the request reduction?', '100 × (1 − 785/975) ≈ 19.49%; 48.75 versus 39.25 requests per completion.', '100 × (1 − 975/785) ≈ 19.49%; 39.25 versus 48.75 requests per completion.', '100 × (975 − 785)/785 ≈ 19.49%; B is the baseline.', '(975 − 785)/20 = 9.5%, so the resume figure is a percentage-point difference.'],
'movement': ['Why does the move reduction (42.00 → 32.95) differ from the request reduction?', 'Successful moves are a subset of decision outcomes; requests can also produce grabs, checkout or failures.', 'All requests are successful moves, but the denominator is rounded.', 'The two percentages refer to different shopper cohorts in the Terra pairs.', 'React adds movement frames that count as billable inference requests.'],
'matrix': ['Which accounting matches the historical main matrix?', '200 planned trips; 80 attempted; 70 paid checkouts; twelve planned runs not collected.', '200 completed trips plus two pilots, with failures removed.', '80 independently sampled people and 70 statistically significant successes.', '130 comparable headline trips after pooling pilots, historical and OpenRouter recordings.'],
'views': ['Which subset supports the resume’s Terra layout numbers?', 'Two intact paired Terra repetitions, rather than the default four-run single-repetition table.', 'All thirteen recordings pooled without grouping.', 'Only the earliest Luna recording on each layout.', 'The full planned five-repetition matrix, including twelve imputed runs.'],
'quality': ['Luna’s Layout A estimate is lower, but its fulfillment is 96.2264% versus Terra’s 99.0566%. What follows?', 'An observed cost-quality tradeoff: 87.8% lower estimated cost and a 2.8302 percentage-point fulfillment gap.', 'Model equivalence because both have 20/20 checkouts.', 'An 87.8 percentage-point improvement in fulfillment.', 'A universal ranking that applies to unassisted models and unseen stores.'],
'ablation': ['Which new experiment would isolate the contribution of navigation assistance?', 'Compare model_only and gary2_v2 in matched paired blocks while fixing model, tasks and other controls.', 'Compare Terra assisted on A with Luna model_only on B.', 'Treat each adjusted action as an independent causal effect estimate.', 'Relabel existing assisted recordings as model_only and recompute the summary.'],
'scale': ['Which proposed design best preserves correctness at much larger scale?', 'Bounded queues, per-shopper ordering, authoritative partition owners and durable auditable commits.', 'Let every inference worker update the same cart directly to avoid an owner bottleneck.', 'Assume distributed queues guarantee exactly-once provider charging.', 'Use browser event arrival order as the only global transaction protocol.'],
'retry': ['A provider call times out after possibly completing. Which response is justified?', 'Preserve the unknown-charge reservation; retry may cause another charge and needs explicit handling.', 'Declare it free because no response reached the browser.', 'Replay the same action twice to compensate for uncertain delivery.', 'Assume cancelling the local future reverses any provider billing.'],
'tamper': ['A replay summary counts an unpaid basket as purchased fulfillment. What should an audit do?', 'Reconstruct paid outcomes from the validated canonical chain and frozen shopping rules.', 'Accept the summary if the JSON parses.', 'Trust a regenerated hash as proof that the author recorded reality.', 'Use the visible cart animation as the primary financial record.'],
'shared': ['Two shoppers propose buying the last unit in a future scarce-stock extension. What is needed?', 'An authoritative atomic stock/cart commit check, recording the conflict and re-observing after rejection.', 'Only a stricter JSON schema; current observations cannot become stale.', 'No change, because the GIL prevents business-level conflicts automatically.', 'Accept both grabs because their proposals were valid when submitted.'],
'training': ['What would support a credible base-versus-tuned Qwen result?', 'Real held-out full-trip runs under matched prompts, limits and assistance, retaining failures.', 'A prepared notebook alone, without training or rollout.', 'Reusing training routes as the only evaluation set.', 'Higher agreement with a rule teacher, labeled as measured human realism.'],
'promptinjection': ['A future product description contains an instruction to ignore the task. Which statement is accurate?', 'Schema and physical validation constrain actions but cannot prevent every legal yet undesirable decision.', 'Valid JSON proves the model followed the user’s intended task.', 'A physically legal checkout always means full shopping-list success.', 'Soft shopper budgets should silently become hard security limits.'],
'ownership': ['Which description gives accurate credit to Gary-2?', 'It inspired navigation and run/record/replay; Simply adds its own React SSE bridge, contracts, accounting and evaluation.', 'Simply invented recorded LLM shopping and Gary-2’s browser streaming protocol.', 'Gary-2’s local live view is the same React SSE implementation copied without adaptation.', 'Every subsystem in Simply is a new model architecture trained from scratch.'],
'walkthrough': ['Which end-to-end ordering preserves the intended architecture?', 'Browser lifecycle request → Python session → proposal → validated commit/record → SSE or explicit replay export.', 'Browser shopping action → React cart mutation → provider confirmation → Python display update.', 'Provider cart mutation → browser checkout calculation → optional canonical recording.', 'Replay seek → fresh model decision → new paid purchase → shared final summary.'],
'claim': ['An interviewer challenges whether B is generally better. Which answer is strongest?', 'The matched fixed-cohort observation is inspectable, but two stochastic paired blocks and policy interactions limit generalization.', 'The 20/20 checkouts prove statistical significance for every store.', 'Matching navigation policy removes every possible source of causal uncertainty.', 'The planned but uncollected repetitions can be treated as confirming the observed trend.'],
 'training-status': ['What is the documented Qwen training status?', 'Dataset and QLoRA notebook prepared; completed GPU training and full-trip evaluation remain pending.', 'The three-step smoke model has been deployed as the production shopper.', 'A full tuned-versus-base study has already established layout generalization.', 'The synthetic fixture teacher is the fine-tuned Qwen checkpoint.'],
'accuracy-trap': ['210 of 234 training labels are movements. What does an approximately 90% coarse move/non-move score establish?', 'Little by itself: always predicting the movement category already reaches about 89.74%.', 'The model chooses the correct movement direction on 90% of held-out states.', 'The model completes 90% of full trips.', 'The dataset contains 234 independent shopping missions.'],
'offline-online': ['Why might better one-step teacher agreement still lead to worse full-trip completion?', 'Rollout creates self-generated states where errors compound and differ from teacher-state evaluation.', 'Schema compliance automatically implies all future states are teacher-distributed.', 'Every route differing from the teacher is physically invalid.', 'One-step agreement and paid completion are the same metric with different units.'],
'observation-debug': ['A shopper loops between two cells. Which intervention would contaminate an existing placement-only comparison?', 'Change history length or assistance only for one layout while retaining the same study label.', 'Inspect raw proposals, applied adjustments and recent positions.', 'Compare failure reasons against the legal-destination facts in recorded prompts.', 'Reconstruct the same recording offline without making model calls.'],
};

const conceptQuestions: QuizQuestion[] = [
  {
    "id": "concept-inference",
    "area": "LLM fundamentals",
    "title": "Inference versus training",
    "prompt": "Simply sends a persona and current state to a hosted model. Which process is taking place?",
    "options": [
      "Inference conditioned on a prompt, without updating model weights.",
      "Fine-tuning a separate model for each shopper.",
      "Reinforcement learning from each checkout.",
      "Retraining the tokenizer on each store layout."
    ],
    "correctIndex": 0,
    "explanation": "Inference uses existing weights to produce a response. Persona instructions change the context, not the weights. Simply supplies observations during each decision; its separate Qwen training workflow remains preparation rather than a completed trained-model result.",
    "source": "simulation/agents/prompts.py · simulation/agents/openai_provider.py"
  },
  {
    "id": "concept-tokens",
    "area": "LLM fundamentals",
    "title": "Tokens and context",
    "prompt": "Why can two shopper decisions with equally short JSON answers have different token costs?",
    "options": [
      "Their input observations and history can have different token lengths and cache treatment.",
      "Only successful actions consume tokens.",
      "Every request has exactly one input token.",
      "Shopper basket prices determine token counts."
    ],
    "correctIndex": 0,
    "explanation": "Tokens are model input/output units, not necessarily whole words. Long observations can dominate a short answer. Simply records provider usage and frozen price estimates separately from basket dollars and reported charges.",
    "source": "simulation/agents/prompts.py · simulation/core/accounting.py"
  },
  {
    "id": "concept-temperature",
    "area": "LLM fundamentals",
    "title": "Sampling and reproducibility",
    "prompt": "Does reducing sampling randomness prove fresh hosted-model runs will exactly reproduce a saved trip?",
    "options": [
      "No; exact replay comes from saved records, while fresh inference can still vary.",
      "Yes; a fixed temperature makes network scheduling deterministic.",
      "Yes; the same model label guarantees identical serving conditions.",
      "No; saved replay must call the model again too."
    ],
    "correctIndex": 0,
    "explanation": "Sampling settings influence generation but do not establish end-to-end determinism across serving and scheduling. Simply freezes run settings and reconstructs recorded transitions for replay rather than asking the model to repeat them.",
    "source": "simulation/agents/openai_provider.py · simulation/core/run_log.py"
  },
  {
    "id": "concept-schema",
    "area": "LLM fundamentals",
    "title": "Syntax versus semantics",
    "prompt": "Which distinction explains why structured output still needs an action validator?",
    "options": [
      "A schema checks response shape; domain validation checks whether the action is legal in the current state.",
      "Valid JSON guarantees the shopper chose the best route.",
      "A JSON schema proves a product is within reach.",
      "Domain validation only changes the answer formatting."
    ],
    "correctIndex": 0,
    "explanation": "Syntactic correctness is separate from state-dependent legality and task success. In Simply, a well-formed grab can still fail physical reachability, and a legal checkout can still omit requested items.",
    "source": "simulation/agents/schema.py · simulation/core/actions.py"
  },
  {
    "id": "concept-memory",
    "area": "LLM fundamentals",
    "title": "Explicit agent memory",
    "prompt": "How can a shopper use previous decisions when each request supplies its own context?",
    "options": [
      "The application includes selected history and state in the next observation.",
      "The model automatically retains every shopper session forever.",
      "The tokenizer stores the previous cart.",
      "The browser animation trains persistent model memory."
    ],
    "correctIndex": 0,
    "explanation": "Application-managed memory means explicitly supplying relevant past facts. Simply includes recent positions/actions and visit information; that differs from changing weights or assuming hidden cross-request memory.",
    "source": "simulation/agents/prompts.py"
  },
  {
    "id": "concept-state-machine",
    "area": "Systems fundamentals",
    "title": "State transitions",
    "prompt": "What is a state-machine view of a shopping simulation?",
    "options": [
      "Actions cause validated transitions between states with defined invariants.",
      "The map animation alone determines whether payment occurred.",
      "A model reason is sufficient proof of a state transition.",
      "Every action must succeed regardless of the starting state."
    ],
    "correctIndex": 0,
    "explanation": "A state machine defines state, allowed transitions and conditions. Simply lets Python validate and apply transitions; React displays the resulting state. New shopping rules enforce unique SKU pickups and one valid payment action.",
    "source": "simulation/core/session.py · simulation/core/actions.py · simulation/core/shopping.py"
  },
  {
    "id": "concept-concurrency",
    "area": "Systems fundamentals",
    "title": "Concurrency versus parallelism",
    "prompt": "Several provider requests are in flight while one Python owner applies ready decisions. What does this illustrate?",
    "options": [
      "Overlapping work can improve responsiveness without giving workers authority to mutate business state.",
      "Concurrency requires every worker to update the same cart directly.",
      "Overlapping requests guarantee CPU execution at exactly the same instant.",
      "Concurrent inference is equivalent to executing many actions from one response."
    ],
    "correctIndex": 0,
    "explanation": "Concurrency concerns overlapping progress; parallelism concerns simultaneous execution. Simply overlaps slow provider calls while keeping state application under authoritative execution. Neither implies multi-action batching.",
    "source": "simulation/core/rounds.py"
  },
  {
    "id": "concept-stale-state",
    "area": "Systems fundamentals",
    "title": "Stale observations",
    "prompt": "A decision was legal when its request started. Why might an authoritative commit still need to check preconditions?",
    "options": [
      "Relevant state may have changed while inference was pending.",
      "A detached snapshot automatically locks all future shared resources.",
      "Valid JSON makes every old observation current again.",
      "The Python GIL proves business preconditions cannot change."
    ],
    "correctIndex": 0,
    "explanation": "A snapshot preserves what was observed; it does not guarantee the world stays unchanged. Simply validates application in Python. A future scarce-stock extension would need an atomic availability check and conflict handling; current shoppers do not compete for scarce stock.",
    "source": "simulation/core/rounds.py · simulation/core/actions.py"
  },
  {
    "id": "concept-idempotency",
    "area": "Systems fundamentals",
    "title": "Idempotency and reconnects",
    "prompt": "What does idempotency mean when handling a repeated request or event?",
    "options": [
      "Repeating an operation has the same intended effect as performing it once.",
      "Every repeated delivery should create another purchase.",
      "Messages can never be duplicated on a network.",
      "A reconnect must start a fresh run with a new bill."
    ],
    "correctIndex": 0,
    "explanation": "Idempotency is an effect property, not a promise of duplicate-free transport. Simply reconnects to the same identified recording and validates event identity/sequence; receiving saved events must not execute shopper actions again.",
    "source": "simulation/live/protocol.py · landing/lib/live.ts"
  },
  {
    "id": "concept-sse",
    "area": "Systems fundamentals",
    "title": "Server-sent events",
    "prompt": "Why do server-sent events fit a live view of Python-authored transitions?",
    "options": [
      "They stream server-to-browser updates over HTTP while controls can use separate requests.",
      "They require the browser to calculate shopping outcomes.",
      "They guarantee exactly-once payment and provider billing.",
      "They replace durable recording with browser memory."
    ],
    "correctIndex": 0,
    "explanation": "SSE carries a one-way event stream; it does not define business authority, durable storage or exactly-once effects. Simply sends lifecycle controls separately and projects flushed canonical records into browser updates.",
    "source": "simulation/live/server.py · simulation/live/protocol.py"
  },
  {
    "id": "concept-hash",
    "area": "Systems fundamentals",
    "title": "Integrity versus authenticity",
    "prompt": "A downloaded record has a matching SHA-256 hash. What does that establish against a trusted reference?",
    "options": [
      "Its bytes match that reference; the hash alone does not prove the author or scientific validity.",
      "Every metric is scientifically valid.",
      "The author must be the claimed person.",
      "An attacker cannot replace both a file and its untrusted hash."
    ],
    "correctIndex": 0,
    "explanation": "Hash comparison detects byte changes relative to a trusted digest. Authenticity needs a trusted identity or signature boundary; semantic validity needs reconstruction and checks. Simply combines hash-bound exports with transition and metric validation.",
    "source": "simulation/core/integrity.py · simulation/core/export_replay.py"
  },
  {
    "id": "concept-auth",
    "area": "Systems fundamentals",
    "title": "Authentication versus origin checks",
    "prompt": "Would accepting only same-origin browser POSTs identify which visitor is allowed to start a paid run?",
    "options": [
      "No; request-origin checks and user authentication/authorization solve different problems.",
      "Yes; every visitor on the website is automatically its owner.",
      "Yes; an absent Origin header is a verified identity.",
      "No; authentication requires exposing the provider key to the browser."
    ],
    "correctIndex": 0,
    "explanation": "Authentication establishes identity; authorization determines allowed actions. Origin checks constrain request context, but ordinary site visitors can still use same-origin controls. Simply currently has a loopback-oriented live proxy, so public paid controls need an access boundary.",
    "source": "landing/app/api/simulation/[...path]/route.ts · simulation/live/server.py"
  },
  {
    "id": "concept-confounding",
    "area": "Evaluation fundamentals",
    "title": "Confounding",
    "prompt": "A study changes both store layout and navigation assistance between arms. Why is the layout claim ambiguous?",
    "options": [
      "The outcome difference may reflect either change or their interaction.",
      "Changing two factors always doubles confidence in a layout effect.",
      "A larger request count removes all confounding automatically.",
      "The cheaper arm proves layout was the only cause."
    ],
    "correctIndex": 0,
    "explanation": "Confounding prevents assigning an observed difference to a single intended factor. Simply freezes cohort, prompts, limits and assistance for its layout comparisons. Assistance ablations require separately declared conditions.",
    "source": "simulation/evaluation/study.py · simulation/evaluation/matrix.py"
  },
  {
    "id": "concept-paired",
    "area": "Evaluation fundamentals",
    "title": "Paired experimental design",
    "prompt": "Why run the same frozen shopper profiles on both layouts?",
    "options": [
      "Matching tasks reduces variation from different shopper composition in the comparison.",
      "It turns synthetic profiles into independently sampled humans.",
      "It guarantees both layouts produce identical model decisions.",
      "It makes every model request an independent experimental repetition."
    ],
    "correctIndex": 0,
    "explanation": "Pairing compares related units under both conditions, helping control task differences. Repeated profiles remain related observations; Simply reports repetition structure rather than treating all actions as independent people.",
    "source": "simulation/evaluation/study.py · simulation/evaluation/matrix.py"
  },
  {
    "id": "concept-selection",
    "area": "Evaluation fundamentals",
    "title": "Selection bias from failures",
    "prompt": "What can go wrong if cost per completion silently excludes all spending from failed attempts?",
    "options": [
      "The estimate can make a system look cheaper by hiding resources spent without a successful outcome.",
      "Failure costs are always zero by definition.",
      "Excluding failures makes every model comparison unbiased.",
      "A completed-only subset is invalid even when explicitly labeled."
    ],
    "correctIndex": 0,
    "explanation": "The included subset and denominator define a metric. Completed-only reporting can be useful if clearly labeled, but all-attempt reporting reveals wasted effort and operational interruptions. Simply retains failed attempts and distinguishes these views.",
    "source": "simulation/core/metrics.py · simulation/evaluation/matrix.py"
  },
  {
    "id": "concept-percentage",
    "area": "Evaluation fundamentals",
    "title": "Percent versus percentage points",
    "prompt": "Fulfillment rises from 90% to 95%. Which description is correct?",
    "options": [
      "An increase of 5 percentage points, or about 5.56% relative to the original 90%.",
      "An increase of 5.56 percentage points.",
      "A relative increase of 95%.",
      "A 5% relative increase because 95 minus 90 is 5."
    ],
    "correctIndex": 0,
    "explanation": "Percentage points subtract rates directly. Relative percent change divides their difference by the baseline: (95 - 90) / 90 × 100. Simply comparisons need to distinguish fulfillment gaps from relative cost/request reductions.",
    "source": "landing/lib/dashboard.ts · simulation/core/metrics.py"
  },
  {
    "id": "concept-generalization",
    "area": "Evaluation fundamentals",
    "title": "Internal versus external validity",
    "prompt": "A matched synthetic cohort performs better on Layout B. What additional claim needs separate evidence?",
    "options": [
      "That the same improvement applies to real customers or unseen stores.",
      "That the saved events can be inspected.",
      "That the included synthetic runs used their recorded layouts.",
      "That a recorded request count can be recomputed."
    ],
    "correctIndex": 0,
    "explanation": "Internal validity concerns the comparison under its controls; external validity concerns transfer beyond those conditions. Simply offers inspectable synthetic evidence, not validation that personas predict human shopping behavior.",
    "source": "simulation/docs/resume-evidence.md · simulation/evaluation/study.py"
  },
  {
    "id": "concept-sft",
    "area": "Training fundamentals",
    "title": "Supervised fine-tuning versus reinforcement learning",
    "prompt": "Learning to predict teacher-provided action responses is which training objective?",
    "options": [
      "Supervised fine-tuning on labeled examples.",
      "Reinforcement learning from checkout rewards by definition.",
      "Inference-time persona prompting alone.",
      "Automatic human preference optimization without feedback."
    ],
    "correctIndex": 0,
    "explanation": "SFT trains against target responses; reinforcement learning optimizes a reward-driven objective through a distinct learning setup. Simply prepares synthetic action demonstrations for SFT, which does not establish learned human preferences or a completed reinforcement-learning system.",
    "source": "data/finetuning_demo/README.md · notebooks/README.md"
  },
  {
    "id": "concept-lora",
    "area": "Training fundamentals",
    "title": "LoRA and quantization",
    "prompt": "What roles do low-rank adapters and base-model quantization play in QLoRA?",
    "options": [
      "Adapters provide trainable updates while a frozen lower-precision base reduces memory requirements.",
      "Quantization removes the need for a compatible base model.",
      "LoRA trains every base parameter and discards the adapters.",
      "A four-bit base guarantees higher shopping accuracy."
    ],
    "correctIndex": 0,
    "explanation": "LoRA parameterizes a comparatively small update; quantization stores the frozen base at reduced precision. These reduce training resource needs without guaranteeing task quality. Simply has a prepared QLoRA workflow; trained-model and rollout results remain pending.",
    "source": "notebooks/README.md"
  },
  {
    "id": "concept-leakage",
    "area": "Training fundamentals",
    "title": "Leakage and distribution shift",
    "prompt": "Why keep related mission routes together when splitting train, validation and test examples?",
    "options": [
      "Near-related states across splits can inflate apparent generalization to unseen tasks.",
      "Randomly splitting adjacent route steps guarantees independent missions.",
      "A test split should be reused to choose every training setting.",
      "Keeping missions grouped proves performance on every unseen store."
    ],
    "correctIndex": 0,
    "explanation": "Leakage occurs when evaluation benefits from information too close to training or tuning inputs. Grouping related routes reduces this risk, but shared layouts and few missions still limit generalization. Simply groups both layouts of each mission and still requires held-out full-trip evaluation.",
    "source": "data/finetuning_demo/README.md · notebooks/README.md"
  }
];

export function buildQuiz(questions: Question[]): QuizQuestion[] {
  const projectQuestions = questions.map(q => {
    const item = items[q.id];
    if (!item) throw new Error(`Missing quiz item: ${q.id}`);
    return { id: q.id, area: q.area, title: q.title, prompt: item[0], options: item.slice(1), correctIndex: 0, explanation: q.answer, source: q.source };
  });
  return [...projectQuestions, ...conceptQuestions];
}
