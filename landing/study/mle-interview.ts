import 'server-only';
import type { Question, QuizQuestion } from './types';

// Interview prompts describe implemented behavior separately from proposed extensions.
const drills = [
  {
    "id": "mle-baseline",
    "area": "ML problem framing",
    "title": "Why use an LLM at all?",
    "prompt": "Why is an LLM appropriate here? What would you compare it against before defending the added cost?",
    "answer": "I would first separate two objectives: completing a known shopping list efficiently and studying behavior conditioned on textual preferences. For the first, a deterministic route planner or rule policy could be cheaper and more reliable. An LLM is a candidate for interpreting flexible preferences, but that benefit must be measured.\n\nSimply has explicit fixture teachers and model-only/assisted policy distinctions. I would compare a declared heuristic baseline, the hosted models and assistance ablations under matched tasks, using paid fulfillment, completion, requests, latency and cost. Task completion alone would not establish human behavioral realism.",
    "rubric": [
      "Separate task optimization from behavioral simulation.",
      "Name a cheap non-LLM baseline.",
      "Use matched task and assistance conditions.",
      "Require evidence for the extra complexity."
    ],
    "followup": "If a shortest-path planner wins every task metric, what would still justify the project?",
    "source": "simulation/core/navigation.py · simulation/evaluation/study.py",
    "check": "What is the strongest reason to include a heuristic baseline?",
    "options": [
      "To measure whether the learned system adds value beyond a cheaper declared policy.",
      "To prove all heuristics generalize to human behavior.",
      "To remove the need for matched evaluation.",
      "To treat fixture results as hosted-model evidence."
    ],
    "followupAnswer": "It could still be useful as an auditable platform for testing language-conditioned policies, provided that is the stated goal. To justify behavioral simulation, I would need independent evidence that the generated choices match the target behavior. I would use the planner for pure route optimization if it wins the relevant objectives."
  },
  {
    "id": "mle-mdp",
    "area": "ML problem framing",
    "title": "MDPs, observations and rewards",
    "prompt": "Formulate Simply as a sequential decision problem. Does that mean it currently uses reinforcement learning?",
    "answer": "A state includes position, cart, task and payment/lifecycle facts; an action is a supported move, pickup or checkout. Python defines transitions, while an observation exposes selected state and history to the policy. A finite action horizon bounds the episode. If the observation omits relevant facts, the policy may face partial observability.\n\nI could define a reward for paid fulfillment, completion and resource use in a future RL formulation, but a sequential environment does not imply reward-based training. Simply currently uses hosted inference and has a prepared supervised Qwen workflow, not a completed RL learner.",
    "rubric": [
      "Define state, actions, transitions and horizon.",
      "Distinguish state from observation.",
      "Explain a possible reward without claiming it exists.",
      "Separate sequential inference from RL training."
    ],
    "followup": "Could a reward for fewer requests encourage premature checkout?",
    "source": "simulation/core/session.py · simulation/agents/prompts.py · simulation/core/actions.py",
    "check": "Does having states, actions and episodes prove a model was trained with RL?",
    "options": [
      "No; the deployed policy can act sequentially without any reward-based weight update.",
      "Yes; every agent loop is reinforcement learning.",
      "Yes; payment automatically updates model weights.",
      "No; RL cannot operate in simulations."
    ],
    "followupAnswer": "Yes. A request penalty can favor stopping early even when the list is incomplete. I would make paid task outcomes primary, inspect premature-checkout failures, and evaluate several declared tradeoffs. Reward design must not replace environment validation or silently harden soft shopper preferences."
  },
  {
    "id": "mle-reward",
    "area": "ML problem framing",
    "title": "Reward hacking and metric design",
    "prompt": "Design a future reward, then explain how the policy could exploit it.",
    "answer": "A reward that only penalizes requests could favor immediate checkout or quitting. A reward for cart additions could favor unpaid baskets; repeated pickup rewards could encourage duplicates unless the environment prevents them. I would define success around validated paid fulfillment and completion, then treat request effort and cost as secondary objectives or constrained tradeoffs.\n\nSimply already distinguishes paid outcomes from cart contents and freezes shopping rules. A proposed reward would need adversarial fixtures, a matched baseline and full-trip evaluation. I would not silently turn soft shopper budgets into physical rejection rules.",
    "rubric": [
      "Give a concrete reward exploit.",
      "Anchor success in paid outcomes.",
      "Distinguish reward design from environment invariants.",
      "Validate tradeoffs with full episodes."
    ],
    "followup": "How would you distinguish a useful shortcut from reward hacking?",
    "source": "simulation/core/metrics.py · simulation/core/shopping.py",
    "check": "What is a likely failure of rewarding cart additions alone?",
    "options": [
      "The policy can earn reward without ever paying for the basket.",
      "It guarantees full paid fulfillment.",
      "It makes duplicate invariants unnecessary.",
      "It directly minimizes provider charges."
    ],
    "followupAnswer": "A shortcut is useful if it improves the intended outcome under the declared constraints; reward hacking improves the proxy while undermining that outcome. I would inspect paid fulfillment, completion and failure slices, then construct counterexamples where the proxy and intended goal disagree."
  },
  {
    "id": "mle-attention",
    "area": "Model fundamentals",
    "title": "Explain transformer attention",
    "prompt": "Explain causal self-attention and why long observations affect inference resources.",
    "answer": "Attention projects token representations into queries, keys and values, forms scaled query-key scores, normalizes them and combines values. A causal mask prevents a position from attending to future positions during next-token prediction. Position information lets the model distinguish order.\n\nDense attention considers token pairs, so long prompts raise compute and potentially memory use; actual implementations change what is materialized. Autoregressive decoding can reuse cached keys and values, but the cache also consumes memory. For Simply I would measure prompt-length and latency distributions before shortening observations, since removing task facts can degrade decisions.",
    "rubric": [
      "Explain queries, keys, values and normalized scores.",
      "State the purpose of causal masking.",
      "Distinguish prefill from cached decoding.",
      "Connect context reduction to measured quality."
    ],
    "followup": "Why does a KV cache reduce repeated work without making long context free?",
    "source": "simulation/agents/prompts.py · simulation/agents/openai_provider.py",
    "check": "What does a causal attention mask prevent?",
    "options": [
      "A token position from using future token positions during next-token prediction.",
      "The model from using any previous token.",
      "All inference nondeterminism.",
      "Every physically invalid shopper action."
    ],
    "followupAnswer": "A KV cache reuses previous key/value projections during autoregressive decoding. New tokens still attend over the retained context, and cache storage grows with retained sequence length, layers and relevant head dimensions. Prompt prefill and serving overhead also remain."
  },
  {
    "id": "mle-crossentropy",
    "area": "Model fundamentals",
    "title": "Cross-entropy and perplexity",
    "prompt": "What loss does assistant-only SFT optimize, and why can lower validation loss fail to improve shopper completion?",
    "answer": "Token cross-entropy is the average negative log probability assigned to target tokens over the positions included in the loss. Assistant-only masking keeps observations as conditioning context while excluding their tokens from the target loss. Perplexity is the exponential of an appropriately averaged natural-log token loss; comparisons require compatible tokenization and evaluation conditions.\n\nLower loss can mean better imitation on teacher states, without fixing rollout loops or payment decisions. Simply must therefore pair token metrics with schema checks, exact action diagnostics and held-out full-trip outcomes. A prepared notebook is not a measured improvement.",
    "rubric": [
      "Explain negative log target probability.",
      "Explain input context versus supervised positions.",
      "Qualify perplexity comparisons.",
      "Separate teacher-state loss from rollout success."
    ],
    "followup": "How could long repetitive responses dominate loss while rare checkout decisions remain poor?",
    "source": "notebooks/README.md · notebooks/Simply_Qwen3_4B_QLoRA_Colab.ipynb",
    "check": "What does lower teacher-forced token loss directly measure?",
    "options": [
      "Better target-token prediction on the evaluated examples, not guaranteed rollout completion.",
      "Guaranteed higher human realism.",
      "Guaranteed lower API cost per paid trip.",
      "Proof the model learned an optimal policy."
    ],
    "followupAnswer": "If many supervised tokens encode repeated formatting or movement explanations, their loss contribution can overwhelm rare action decisions. I would inspect supervised-token counts and action-stratified loss/errors, then measure checkout behavior in full trips rather than optimize one pooled token average."
  },
  {
    "id": "mle-optimization",
    "area": "Training practice",
    "title": "Learning rate and unstable training",
    "prompt": "Your QLoRA training loss becomes NaN. How do you debug it before launching a longer run?",
    "answer": "I would reproduce the first bad step and inspect data, finite inputs/losses, nonempty supervised spans, padding labels and sequence lengths. Then I would check precision support, gradients, learning rate, clipping and optimizer configuration. A batch with no supervised targets is a data or masking problem; blindly reducing learning rate would hide the cause.\n\nFor Simply I would start with the existing no-update memory check and smoke workflow, verify only intended adapter parameters train, and preserve the failing configuration. After a fix I would restart a clean pilot rather than continue a corrupted optimizer state.",
    "rubric": [
      "Inspect masking and data before tuning blindly.",
      "Check finite losses, gradients and precision.",
      "Use a minimal reproducible step.",
      "Restart cleanly after a validated fix."
    ],
    "followup": "What would you inspect if loss is finite but every decoded action is malformed?",
    "source": "notebooks/Simply_Qwen3_4B_QLoRA_Colab.ipynb · notebooks/README.md",
    "check": "What is the best first response to a NaN loss?",
    "options": [
      "Reproduce the failing step and inspect data, supervised spans and numerical conditions.",
      "Increase epochs until it disappears.",
      "Treat missing supervised tokens as a successful zero-loss batch.",
      "Report the best earlier batch as final model quality."
    ],
    "followupAnswer": "Check the exact chat template, assistant-prefix boundaries, tokenizer revision, masked label spans, truncation, decoding limits and parser assumptions. Decode representative training inputs and targets, then compare the same observation in training and serving. Finite loss alone does not prove the intended output contract was learned."
  },
  {
    "id": "mle-batch",
    "area": "Training practice",
    "title": "Gradient accumulation and effective batch size",
    "prompt": "With microbatch size 1, accumulation 8 and one device, what is the effective example batch? What changes when examples have different lengths?",
    "answer": "The nominal effective batch is 1 × 8 × 1 = 8 examples per optimizer step, assuming the training loop accumulates and scales gradients as intended. Accumulation trades extra steps in time for lower activation memory per microbatch; it does not reduce the memory for model parameters or optimizer state.\n\nExamples can have different supervised token counts, so example-level batching does not by itself imply equal token weighting. I would inspect the loss reduction and accumulation behavior of the chosen trainer. Simply configures accumulation for its pilot, but has not demonstrated a completed training result.",
    "rubric": [
      "Compute microbatch × accumulation × devices.",
      "Distinguish optimizer steps from microsteps.",
      "Name memory that accumulation does not remove.",
      "Consider token weighting for variable lengths."
    ],
    "followup": "Would doubling accumulation automatically justify doubling learning rate?",
    "source": "notebooks/Simply_Qwen3_4B_QLoRA_Colab.ipynb",
    "check": "What is the nominal effective example batch for microbatch 1, accumulation 8, one device?",
    "options": [
      "8 examples per optimizer step.",
      "1 example per optimizer step regardless of accumulation.",
      "8 optimizer steps per example.",
      "The number of tokens in the longest example."
    ],
    "followupAnswer": "Not automatically. Learning-rate scaling is an empirical heuristic with assumptions about optimizer, noise and training regime. Accumulation changes update frequency and may change token weighting. I would compare a small declared validation sweep rather than apply linear scaling blindly."
  },
  {
    "id": "mle-gpu-memory",
    "area": "Training practice",
    "title": "Estimate GPU memory before training",
    "prompt": "Why can a four-bit 4B base still run out of GPU memory?",
    "answer": "A rough packed weight-only lower bound is four billion parameters × four bits / eight, about two billion bytes. That excludes quantization metadata, higher-precision components, adapters, gradients, optimizer state, activations, temporary workspaces and allocator overhead. Sequence length and batch size can dominate activation memory.\n\nI would measure peak allocated/reserved memory on the longest supported observation, then use shorter validated contexts, smaller microbatches, checkpointing or more memory as appropriate. Simply has a no-update memory preflight; it must not silently truncate away action targets to make the experiment fit.",
    "rubric": [
      "Compute a weight-only lower bound.",
      "List non-weight memory contributors.",
      "Measure peak memory at representative worst-case length.",
      "Avoid silently truncating labels or task facts."
    ],
    "followup": "What does gradient checkpointing trade for reduced activation memory?",
    "source": "notebooks/Simply_Qwen3_4B_QLoRA_Colab.ipynb",
    "check": "Why is a four-bit weight estimate not a total GPU memory estimate?",
    "options": [
      "Training also needs activations, adapter/optimizer state, metadata and temporary memory.",
      "Quantization makes every tensor exactly four bits.",
      "GPU memory depends only on shopper count.",
      "Adapter training never computes activations."
    ],
    "followupAnswer": "It trades extra forward recomputation during backpropagation for storing fewer intermediate activations. It does not eliminate model weights, optimizer state or all activations. I would measure peak memory and step time to decide whether the tradeoff meets the training constraints."
  },
  {
    "id": "mle-overfit",
    "area": "Training practice",
    "title": "Overfitting and hyperparameter selection",
    "prompt": "Training loss falls while validation loss rises. What would you do with this small mission-grouped dataset?",
    "answer": "That pattern is consistent with overfitting, but I would first verify split integrity, preprocessing and comparable loss accounting. I would inspect per-mission/action errors and evaluate checkpoints using a declared validation procedure. Lower learning rate, fewer epochs, smaller adapter capacity or better data may help, but I would not choose a fix using the held-out test.\n\nSimply has very few independent mission groups and movement-heavy labels. More duplicates of those routes may improve memorization without adding coverage. I would expand distinct missions and evaluate full trips before claiming generalization.",
    "rubric": [
      "Check split and preprocessing integrity.",
      "Use validation for model selection.",
      "Keep test separate from repeated tuning.",
      "Prioritize independent mission diversity."
    ],
    "followup": "What do you do after the test set has influenced several design choices?",
    "source": "data/finetuning_demo/README.md · notebooks/README.md",
    "check": "Which dataset should choose checkpoints and hyperparameters?",
    "options": [
      "Validation data, while the held-out test remains reserved for final evaluation.",
      "The test set after every training step.",
      "Only training loss, regardless of rollout quality.",
      "Whichever split gives the highest reported score."
    ],
    "followupAnswer": "That set has become part of development evidence. I would disclose the reuse and reserve a new independent final evaluation if possible. Calling the same repeatedly consulted test untouched would overstate generalization; the old results can still be reported with their limitations."
  },
  {
    "id": "mle-lora-rank",
    "area": "Training practice",
    "title": "LoRA rank and capacity",
    "prompt": "What does LoRA rank control, and how would you choose it?",
    "answer": "LoRA represents an update to a selected weight matrix as a scaled product of two smaller trainable matrices. Rank bounds the update capacity and influences trainable parameter count, memory and compute. Increasing rank is not guaranteed to improve held-out behavior and can make overfitting easier on narrow data.\n\nI would choose target modules, rank, scaling, learning rate and epochs through a small declared validation sweep, with matched data and inference settings. For Simply this remains an experiment plan, not evidence that its prepared adapter settings are optimal.",
    "rubric": [
      "Describe the low-rank matrix update.",
      "Connect rank to capacity and resources.",
      "Avoid assuming more rank always improves quality.",
      "Use validation under a declared comparison budget."
    ],
    "followup": "Why must an adapter be paired with a compatible base and tokenizer?",
    "source": "notebooks/Simply_Qwen3_4B_QLoRA_Colab.ipynb",
    "check": "What does increasing LoRA rank directly increase?",
    "options": [
      "The capacity and parameter count of the adapter update.",
      "The number of independent training missions.",
      "Guaranteed held-out completion rate.",
      "The quantization precision of all base weights."
    ],
    "followupAnswer": "The adapter update is defined for particular parameter shapes and learned base representations. A different base revision, target-module mapping or tokenizer/template can change its meaning or make it incompatible. I would pin these identities and validate decoded outputs after loading."
  },
  {
    "id": "mle-tokenizer",
    "area": "Training practice",
    "title": "Chat templates and train/serve skew",
    "prompt": "The adapter loads, but actions degrade only in serving. Which input-contract differences would you check?",
    "answer": "I would compare the exact base/tokenizer revision, chat template, role boundaries, special tokens, generation prefix, observation serialization and decoding settings. A model can learn the wrong boundary if training examples and serving prompts use different formatting. I would also compare output parsing and any assistance policy.\n\nSimply should freeze these artifacts and run an identical serialized observation through both paths, checking token IDs and raw outputs before investigating downstream metrics. Successful adapter loading does not prove train/serve equivalence.",
    "rubric": [
      "Compare tokenizer/base revisions and templates.",
      "Check role boundaries and generation prefix.",
      "Use a shared serialized observation to isolate skew.",
      "Inspect raw output before parsed/applied behavior."
    ],
    "followup": "How would you detect accidental training on assistant delimiters or truncated targets?",
    "source": "notebooks/Simply_Qwen3_4B_QLoRA_Colab.ipynb · simulation/agents/prompts.py",
    "check": "What can cause train/serve skew despite a successfully loaded adapter?",
    "options": [
      "Different tokenization, chat templates or observation serialization between training and serving.",
      "A fixed test split alone.",
      "Recording original proposals.",
      "Keeping the same action schema."
    ],
    "followupAnswer": "Inspect decoded token/label pairs and assistant-mask boundaries for each supported example format, including long cases. Confirm there are supervised response tokens, the expected role delimiters, the complete target JSON and termination tokens. Use the actual tokenizer rather than character-position guesses."
  },
  {
    "id": "mle-imbalance",
    "area": "ML evaluation",
    "title": "Precision, recall and action imbalance",
    "prompt": "A model almost never predicts checkout. How would you evaluate the rare action instead of reporting one accuracy?",
    "answer": "I would build a per-action confusion matrix on a declared labeled set. Checkout precision is correct checkout predictions divided by all checkout predictions; recall is correct checkout predictions divided by all labeled checkout cases. Macro averages give each class equal weight, while micro aggregates can be dominated by movement.\n\nTeacher labels may specify one of several valid actions, so I would also measure observation-valid actions and full-trip paid outcomes. Simply has a movement-heavy synthetic dataset; a high overall action-category score could hide failure to finish.",
    "rubric": [
      "Define precision and recall with denominators.",
      "Use per-class and macro diagnostics.",
      "Acknowledge alternative valid actions.",
      "Require end-to-end completion and fulfillment."
    ],
    "followup": "Could higher checkout recall make the shopper worse by checking out too early?",
    "source": "data/finetuning_demo/manifest.json · simulation/core/metrics.py",
    "check": "Which metric directly asks how many labeled checkout cases the model identifies?",
    "options": [
      "Checkout recall.",
      "Checkout precision.",
      "Overall movement accuracy.",
      "Mean input token count."
    ],
    "followupAnswer": "Yes. Predicting checkout too frequently can increase recall on labeled checkout states while triggering early payment elsewhere. Precision, state validity, remaining-list context and paid fulfillment expose that regression. I would evaluate the sequential policy rather than optimize recall in isolation."
  },
  {
    "id": "mle-calibration",
    "area": "ML evaluation",
    "title": "Calibration and abstention",
    "prompt": "If a shopper model reports 90% confidence, what would make that number trustworthy?",
    "answer": "I would first define the event being predicted, such as physical action validity or eventual task success. Calibration means that predictions near 0.9 succeed about 90% of the time on a relevant held-out distribution. I would examine reliability bins and a proper scoring rule such as Brier score, with uncertainty and subgroup coverage.\n\nA verbal confidence string is not a calibrated probability. Simply does not currently establish calibrated confidence or an abstention system. A future routing policy could abstain or escalate at a validation-selected threshold, then measure coverage, errors and cost.",
    "rubric": [
      "Define the event attached to confidence.",
      "Explain calibration as empirical frequency agreement.",
      "Use held-out reliability and proper scoring diagnostics.",
      "Label confidence routing as proposed work."
    ],
    "followup": "How can a perfectly calibrated constant predictor still be unhelpful?",
    "source": "simulation/agents/schema.py · simulation/evaluation/study.py",
    "check": "What does calibration of a 0.9 score mean?",
    "options": [
      "Cases assigned about 0.9 succeed about 90% of the time for the defined event and distribution.",
      "Every case assigned 0.9 is guaranteed correct.",
      "The model is 90% better than all baselines.",
      "A confident public reason proves calibration."
    ],
    "followupAnswer": "A model predicting the same base success rate for every case can be calibrated yet fail to rank easy and difficult cases. Calibration and discrimination are different. For routing I would check both, plus the utility and coverage of the chosen threshold."
  },
  {
    "id": "mle-threshold",
    "area": "ML evaluation",
    "title": "Thresholds and asymmetric error costs",
    "prompt": "Suppose you add a failure detector to decide when to escalate to a stronger model. How do you pick its threshold?",
    "answer": "I would define a failure label and the costs of missed failures, unnecessary escalations, latency and extra model calls. A threshold should be selected on representative validation data using those costs or an operational constraint, then evaluated once on held-out episodes. Precision-recall behavior is useful when the positive failure class is rare; a good ranking metric alone does not pick an operating threshold.\n\nSimply has selectable fixed models, not an evaluated per-step router. A routing study would be a separately frozen policy, preserving serving identity and all charges.",
    "rubric": [
      "Define labels and asymmetric error costs.",
      "Select an operating threshold on validation data.",
      "Evaluate precision/recall plus episode and cost outcomes.",
      "Version routing separately from fixed-model evidence."
    ],
    "followup": "Why could a router with good ROC-AUC still generate too many costly escalations?",
    "source": "simulation/agents/providers.py · simulation/evaluation/study.py",
    "check": "What should determine an escalation threshold?",
    "options": [
      "Validation evidence plus the costs and constraints of missed failures and extra escalations.",
      "A universal threshold of 0.5 for every task.",
      "The highest test score after repeated adjustments.",
      "Only the display name of the cheaper model."
    ],
    "followupAnswer": "ROC-AUC summarizes ranking over thresholds and does not set the deployed operating point. With a rare positive class, even a modest false-positive rate can yield many unnecessary escalations. I would inspect precision-recall and expected costs at the selected validation threshold."
  },
  {
    "id": "mle-uncertainty",
    "area": "Experiment design",
    "title": "Uncertainty with repeated profiles",
    "prompt": "How would you estimate uncertainty without pretending every action or repeated trip is independent?",
    "answer": "I would define the estimand and unit of replication before choosing an interval. Profiles recur within paired repetition blocks, and actions are nested within trips. Resampling individual requests would create pseudoreplication. With a sufficiently replicated design I could analyze paired block differences or use a justified clustered/hierarchical method matching the sampling assumptions.\n\nSimply has too few intact repetitions for a strong general effect claim. I would show the observed paired differences and descriptive spread, disclose the incomplete collection, and collect more independent blocks before claiming reliable population uncertainty.",
    "rubric": [
      "State the estimand and independent unit.",
      "Identify repeated/nested observations.",
      "Avoid request-level pseudoreplication.",
      "Acknowledge the small number of intact blocks."
    ],
    "followup": "What population would a bootstrap over the same ten fixed profiles actually describe?",
    "source": "simulation/evaluation/matrix.py · simulation/docs/resume-evidence.md",
    "check": "Why is bootstrapping individual requests a weak basis for a layout-effect interval?",
    "options": [
      "Requests are dependent within trips and repeated conditions, so they are not independent replications.",
      "Request counts cannot be measured.",
      "Bootstrap methods always require human data.",
      "A larger number of actions guarantees unbiased uncertainty."
    ],
    "followupAnswer": "It depends on the assumed sampling process. Resampling fixed profiles may describe variation within that empirical task distribution, but does not automatically generalize to new people, new layouts or independent repetitions. I would state that target and preserve the paired/nested structure in the analysis."
  },
  {
    "id": "mle-power",
    "area": "Experiment design",
    "title": "Power and minimum detectable effect",
    "prompt": "Before collecting a larger layout study, how would you decide how many repetitions to run?",
    "answer": "I would choose the primary metric, smallest practically meaningful effect, comparison unit, error rates and analysis plan. Variance must reflect paired repetition-level differences rather than the apparent number of actions. A pilot can inform a power simulation or sample-size calculation under explicit assumptions, including failures and multiple comparisons.\n\nSimply does not have a completed powered matrix. I would not invent a required repetition count from the current headline alone or launch paid collection without authorization. A collection plan would freeze its budget, stopping rule and retention of failed attempts.",
    "rubric": [
      "Choose a practical effect and primary metric.",
      "Use variance at the right replication level.",
      "Account for failures and comparison multiplicity.",
      "Predefine collection and stopping rules."
    ],
    "followup": "Why can an effect estimate from a tiny pilot lead to an overoptimistic power plan?",
    "source": "simulation/evaluation/study.py · simulation/evaluation/matrix.py",
    "check": "What is needed before defending a sample-size target?",
    "options": [
      "A primary estimand, meaningful effect, variance assumptions and declared error/stopping criteria.",
      "Only the total number of tokens already generated.",
      "A fixed universal rule of ten shoppers.",
      "The most favorable observed run."
    ],
    "followupAnswer": "A tiny pilot gives noisy variance and effect estimates; selecting an impressive effect can exaggerate the expected gain. I would use a practically meaningful effect, sensitivity analyses over plausible variances, and an appropriate replication unit instead of powering only for the observed best result."
  },
  {
    "id": "mle-failure-taxonomy",
    "area": "Experiment design",
    "title": "Separate infrastructure from policy failures",
    "prompt": "A trip fails. How do you determine whether the model, layout or serving system was responsible?",
    "answer": "I would inspect the canonical failure stage: request submission, provider response/error, parsing, schema validation, assistance, physical action application, horizon exhaustion and payment outcome. A provider-credit interruption differs from repeated legal but unhelpful moves. Neither should be silently deleted.\n\nSimply preserves proposals, adjustments, errors, telemetry and final state. I would report both an operational all-attempt result and any clearly labeled policy-quality subset with its exclusion rules. Diagnosis narrows the mechanism; it does not prove a layout caused an isolated failure.",
    "rubric": [
      "Use a stage-based failure taxonomy.",
      "Inspect raw and applied decisions plus telemetry.",
      "Retain infrastructure failures in operational reporting.",
      "Avoid automatic causal blame."
    ],
    "followup": "When is excluding an infrastructure failure defensible, and how must it be labeled?",
    "source": "simulation/core/decision_log.py · simulation/core/metrics.py · simulation/docs/resume-evidence.md",
    "check": "What is the best first step in diagnosing an unfinished trip?",
    "options": [
      "Identify the failure stage from canonical events and provider/execution telemetry.",
      "Assume every failure proves poor model reasoning.",
      "Remove it before computing all-attempt metrics.",
      "Infer payment from the animation."
    ],
    "followupAnswer": "A predefined policy-quality analysis can exclude clearly identified infrastructure interruptions if the exclusion addresses its estimand and is applied consistently. It must disclose the rule, counts and affected conditions, and appear alongside all-attempt operational results so failures remain visible."
  },
  {
    "id": "mle-ab-testing",
    "area": "Experiment design",
    "title": "Offline evidence versus online A/B testing",
    "prompt": "If Simply were used by a retailer, what would a real online experiment need beyond these synthetic runs?",
    "answer": "I would define a real decision and safe outcome metrics, an appropriate randomization unit, exposure logging, guardrails and a consent/privacy-aware data plan. Depending on the intervention, shopper, session or store-level randomization may have different interference risks. I would predefine duration and analysis rather than repeatedly stop on a favorable result.\n\nThe current synthetic study can test execution and controlled hypotheses; it cannot establish customer revenue uplift or behavioral validity. A retailer experiment would be a new study with real operational constraints and no substitution of synthetic sample counts for human evidence.",
    "rubric": [
      "Choose the randomization/exposure unit.",
      "Consider interference and operational guardrails.",
      "Predefine duration and analysis.",
      "Separate synthetic findings from human effects."
    ],
    "followup": "What would go wrong if shoppers in both arms share the same changing store inventory?",
    "source": "simulation/docs/resume-evidence.md · simulation/evaluation/study.py",
    "check": "What claim requires new evidence beyond synthetic Simply runs?",
    "options": [
      "A causal improvement in real customer or retailer outcomes.",
      "That a saved simulation has an identified run ID.",
      "That replay seeking preserves recorded state.",
      "That a Python metric can be audited."
    ],
    "followupAnswer": "Shared stock can create interference: purchases or shortages caused by one arm change what the other arm can do. I would consider store/time-cluster randomization or another interference-aware design, log stock exposure, and account for the reduced number of independent clusters."
  },
  {
    "id": "mle-reproducibility",
    "area": "MLOps",
    "title": "What belongs in a model artifact?",
    "prompt": "What must you version to reproduce a future tuned shopper deployment?",
    "answer": "I would version the base model and tokenizer revisions, adapter weights/configuration, chat template, training data hashes and splits, code/dependency versions, masking and optimization settings, seeds, generation settings, action schema and assistance policy. The release should include held-out rollout results and known limitations.\n\nSimply already freezes run configuration and price snapshots for evidence. A future tuned release would need the additional training artifacts. Seeds help controlled experiments but do not guarantee bitwise reproducibility across hardware, kernels or hosted serving revisions.",
    "rubric": [
      "Include model, tokenizer, template and adapter identity.",
      "Version data/splits and training environment.",
      "Bind inference schema and assistance policy.",
      "Qualify what seeds can reproduce."
    ],
    "followup": "Which artifacts are needed for inference versus reproducing the entire training run?",
    "source": "notebooks/README.md · simulation/core/run_log.py · simulation/agents/openrouter_provider.py",
    "check": "Which release package best supports reproducibility?",
    "options": [
      "Model/tokenizer/template identity, adapter/data/configuration versions and matched evaluation evidence.",
      "Only an adapter filename.",
      "Only the model dropdown label.",
      "Only a random seed without data or environment versions."
    ],
    "followupAnswer": "Inference needs the compatible base/tokenizer, adapter, chat template, generation settings and execution contract. Reproducing training additionally needs the exact data and splits, preprocessing/masks, optimizer and schedule, environment, seeds, and possibly checkpointed optimizer/RNG state. Neither set alone guarantees identical hosted outputs."
  },
  {
    "id": "mle-monitoring",
    "area": "MLOps",
    "title": "Monitor quality, cost and drift",
    "prompt": "What would you monitor after deploying a shopper policy, and how would you distinguish drift from an outage?",
    "answer": "I would track availability, provider errors, queue depth, request latency, schema/physical rejection rates, assistance frequency, loop indicators, paid completion/fulfillment and cost per declared unit. I would segment by model, layout, cohort and policy version, and monitor changes in prompt length, product/task coverage and observation distributions.\n\nAn outage can cause an abrupt serving failure without a changed task distribution; drift can degrade decisions while HTTP succeeds. Simply records many underlying facts, but a production alerting/drift service is future work. Thresholds should use a baseline, sustained evidence and an actionable response.",
    "rubric": [
      "Cover serving, decision and business metrics.",
      "Segment by frozen version and task conditions.",
      "Distinguish distribution shift from service failure.",
      "Define alerts with an owner and response."
    ],
    "followup": "What could a rising assistance rate hide while paid completion remains stable?",
    "source": "simulation/core/decision_log.py · simulation/core/accounting.py · simulation/core/metrics.py",
    "check": "Which signal can reveal model degradation hidden by stable completion?",
    "options": [
      "A rising rate of recorded policy assistance or rejected proposals under matched conditions.",
      "Only the page color theme.",
      "A constant model display label.",
      "Replay animation frame rate alone."
    ],
    "followupAnswer": "Assistance may be compensating for increasingly poor proposals. Inspect raw validity, override reasons, policy version and task distribution before blaming the model. Compare assisted and proposal-level diagnostics under matched conditions; stable paid outcomes do not establish unchanged unassisted capability."
  },
  {
    "id": "mle-rollout",
    "area": "MLOps",
    "title": "Shadow, canary and rollback",
    "prompt": "How would you release a tuned policy without risking all users or corrupting historical comparisons?",
    "answer": "I would first validate offline full trips, then consider a shadow mode whose proposals are recorded but cannot mutate authoritative state. A controlled canary could assign a small declared share of new sessions to the candidate, with pinned versions, operational guardrails and a rollback plan. Shadow requests still cost resources and need authorization.\n\nSimply must keep one authoritative executor. A rollback should route future runs to the previous release; it should not relabel or switch the model inside existing identified runs. A production rollout system is proposed work, not currently established behavior.",
    "rubric": [
      "Validate offline before exposure.",
      "Keep shadow proposals non-mutating.",
      "Pin candidate/control versions and guardrails.",
      "Rollback new assignments without rewriting active/history identity."
    ],
    "followup": "What bias appears if you send only easy tasks to the canary?",
    "source": "simulation/core/session.py · simulation/core/run_log.py · simulation/agents/providers.py",
    "check": "How should rollback preserve run identity?",
    "options": [
      "Change future session assignment while preserving the frozen model of active and historical runs.",
      "Relabel old candidate runs as the previous model.",
      "Change an active run model without recording a new condition.",
      "Let both shadow and live models apply purchases."
    ],
    "followupAnswer": "The canary would face a different task distribution, so apparent quality or cost differences could reflect selection rather than the candidate. Randomize within the intended eligible population or use a declared stratified design, and report exposure balance and task slices."
  },
  {
    "id": "mle-latency",
    "area": "ML serving",
    "title": "Latency and throughput are different",
    "prompt": "How would you make the live lab faster without changing the scientific question?",
    "answer": "I would measure time in queue, provider latency, prompt prefill/output generation, parsing, validation, recording and browser transport. Report median and tail latency plus throughput; increasing concurrency can improve throughput while worsening tails, provider throttling or contention.\n\nSimply overlaps independent provider requests and keeps per-shopper ordering. I would use bounded concurrency and backpressure, then measure quality and cost under the same frozen policy. Prompt reduction, caching or batching can change conditions, so I would version and compare them deliberately rather than call every speedup a layout improvement.",
    "rubric": [
      "Profile stages before optimizing.",
      "Separate throughput from per-request/tail latency.",
      "Use bounded concurrency and backpressure.",
      "Preserve or explicitly version experimental conditions."
    ],
    "followup": "How would you diagnose better average latency but worse p99?",
    "source": "simulation/core/rounds.py · simulation/agents/openrouter_provider.py · simulation/live/server.py",
    "check": "Can increasing concurrency raise throughput while worsening tail latency?",
    "options": [
      "Yes; queueing, contention and provider throttling can change the tradeoff.",
      "No; throughput and tail latency are the same metric.",
      "No; concurrency removes all provider limits.",
      "Yes; because the browser starts applying model actions directly."
    ],
    "followupAnswer": "Inspect latency histograms by stage and load, queue depth, provider throttles, retries and slow task/model segments. A faster majority can lower the mean while contention or a small failure class worsens the tail. Use enough observations and a declared measurement window for tail estimates."
  },
  {
    "id": "mle-retries",
    "area": "ML serving",
    "title": "Retries, timeouts and unknown charges",
    "prompt": "A request times out after the provider may have processed it. How do you retry safely?",
    "answer": "I would distinguish a known pre-submission failure from ambiguous completion. An ambiguous timeout may already have incurred cost, so I would retain an unknown-charge reservation and avoid treating cancellation as a refund. Retry only under a defined bounded policy with backoff/jitter for retryable failures, accounting for another possible charge and the provider contract.\n\nSimply must bind each proposal to its observation/run and apply at most the accepted result through Python. Retrying transport is not permission to apply duplicate actions, and a quota/credit failure is not automatically a reason for rapid retries.",
    "rubric": [
      "Distinguish pre-submit failure from ambiguous completion.",
      "Preserve unknown-charge accounting.",
      "Bound retries by failure class and policy.",
      "Prevent duplicate state application."
    ],
    "followup": "Where would an idempotency key help, and what if the provider does not support one?",
    "source": "simulation/core/budget.py · simulation/agents/openrouter_provider.py · simulation/core/rounds.py",
    "check": "What is correct after an ambiguous provider timeout?",
    "options": [
      "Retain possible charges and handle retry and duplicate-result application explicitly.",
      "Declare the original request free.",
      "Assume local future cancellation reversed provider billing.",
      "Apply both answers if a retry returns before the first call."
    ],
    "followupAnswer": "An idempotency key can help deduplicate an operation only if the receiving service supports and honors that contract. Local IDs alone cannot guarantee provider charge deduplication. Without provider support, preserve ambiguous accounting, bound retries and ensure only one accepted proposal mutates the run."
  },
  {
    "id": "mle-cache",
    "area": "ML serving",
    "title": "Caching versus experimental contamination",
    "prompt": "Which parts could you cache, and when would a cache invalidate a comparison?",
    "answer": "Static catalogues and display assets can be cached without inventing simulation outcomes. Provider prefix caching may reduce billed input work, but its use and pricing should remain visible. Caching a decision response requires a complete key covering observation, profile, model/version, prompt, schema, generation settings and policy assumptions; even then reuse changes the effective stochastic policy.\n\nFor Simply I would distinguish provider token-cache accounting from application answer caching. A fresh-inference study must not silently reuse old proposals. Benchmark any cache policy as a declared condition and retain cache-related usage telemetry.",
    "rubric": [
      "Distinguish asset, prefix and response caches.",
      "Define complete decision-cache identity.",
      "Recognize changed sampling/cost semantics.",
      "Freeze and disclose cache policy in studies."
    ],
    "followup": "Why is a cache keyed only by shopper position unsafe?",
    "source": "simulation/agents/openai_provider.py · simulation/agents/openrouter_provider.py · simulation/core/accounting.py",
    "check": "Why is response reuse different from provider prefix caching?",
    "options": [
      "It can skip a fresh policy sample, changing decision and experiment semantics.",
      "Both always execute a new model sample.",
      "Prefix caching proves an action is physically valid.",
      "Neither can affect reported costs."
    ],
    "followupAnswer": "Position omits the shopper list, cart, history, remaining horizon, prices, legal neighbors, model and prompt/policy versions. Two states at the same cell can require different actions. Even a complete cache key needs declared sampling and freshness semantics before responses can be reused in a study."
  },
  {
    "id": "mle-routing",
    "area": "ML serving",
    "title": "Cost-quality model routing",
    "prompt": "How would you test a cheap-first, strong-model-on-failure router?",
    "answer": "I would define the trigger from information available at decision time, such as repeated invalid proposals, schema failures or a separately validated risk score. Compare the router against always-cheap and always-strong baselines on the same frozen tasks, counting both calls when an escalation occurs. Measure paid outcomes, latency, assistance and total known/unknown costs.\n\nSimply currently freezes one model per run. A multi-model router would need a new explicit policy/recording contract with per-decision serving identities, not a silent dropdown switch or a relabeling of the fixed-model historical matrix.",
    "rubric": [
      "Define non-leaky escalation triggers.",
      "Compare always-cheap and always-strong baselines.",
      "Count escalation cost and latency.",
      "Create a new auditable policy instead of changing historical identity."
    ],
    "followup": "Could a router improve average cost while making the hardest shopper profiles much worse?",
    "source": "simulation/agents/providers.py · simulation/core/session.py · simulation/evaluation/study.py",
    "check": "What must a routing evaluation count?",
    "options": [
      "All initial and escalation calls, episode outcomes and per-decision serving identities.",
      "Only the final successful model call.",
      "Only the cheaper model price snapshot.",
      "A single display label regardless of actual serving."
    ],
    "followupAnswer": "Yes. Aggregate savings can conceal poor treatment of long lists or difficult navigation tasks. I would examine predeclared difficulty slices, completion/fulfillment and escalation coverage, then decide whether the router meets minimum quality requirements rather than selecting it on cost alone."
  },
  {
    "id": "mle-security",
    "area": "Production system design",
    "title": "Public access and paid execution",
    "prompt": "What blocks this local lab from safely becoming a public paid simulation service?",
    "answer": "The live proxy checks origin and forwards to a loopback Python service, but it does not establish an authorized user identity. Public visitors could use same-origin controls if the service is deployed with credentials. I would add authenticated authorization, per-user/run ownership, admission control and abuse-rate controls while keeping provider keys server-side.\n\nA replay-only launch can disable live mutation endpoints. Paid live hosting additionally needs durable recordings/ledger storage, supervised processes and streaming support. I would keep access controls separate from soft shopper budgets and would not silently impose historical study caps on manual sessions.",
    "rubric": [
      "Identify missing authentication and run ownership.",
      "Keep provider secrets server-side.",
      "Separate admission controls from shopper preferences.",
      "Name persistent runtime/storage and streaming needs."
    ],
    "followup": "How would authorization prevent one signed-in user from stopping another user’s run?",
    "source": "landing/app/api/simulation/[...path]/route.ts · simulation/live/server.py",
    "check": "Which boundary is missing from a same-origin check alone?",
    "options": [
      "Identity-based authorization to start or control a particular paid run.",
      "JSON response formatting.",
      "A browser request Origin header.",
      "A layout display name."
    ],
    "followupAnswer": "Bind authenticated identity to a server-owned run record, then authorize every read/control/export operation against ownership or an explicit shared role. A run ID is an identifier, not sufficient permission. Check authorization at the server boundary, not only by hiding UI buttons."
  },
  {
    "id": "mle-durability",
    "area": "Production system design",
    "title": "Crash recovery and durability",
    "prompt": "Python crashes after changing state but before the browser sees an event. How would you reason about recovery?",
    "answer": "I would locate the durability boundary and inspect whether the transition was recorded completely. Simply stops when canonical recording fails and streams flushed records; a browser reconnect reconstructs the same run rather than creating purchases. A successful buffer flush alone is not a full guarantee against machine power loss, and the current local design is not a distributed transaction system.\n\nFor stronger production guarantees I would specify atomic commit/recovery semantics, handle partial tails, persist accounting independently and test injected crashes at each boundary. I would never replay shopper actions merely because a browser missed a notification.",
    "rubric": [
      "Identify state/record/transport boundaries.",
      "Distinguish flush from power-loss durability.",
      "Recover only validated committed evidence.",
      "Propose crash injection and durable accounting."
    ],
    "followup": "What changes if the process crashes after a provider charge but before logging its response?",
    "source": "simulation/core/run_log.py · simulation/core/session.py · simulation/live/protocol.py",
    "check": "Does flushing a JSONL record alone guarantee durability through machine power loss?",
    "options": [
      "No; durability depends on filesystem/storage synchronization and a specified recovery contract.",
      "Yes; flush and durable distributed commit are identical.",
      "Yes; SSE acknowledgment guarantees disk persistence.",
      "No; therefore the browser should invent the missing purchase."
    ],
    "followupAnswer": "That call may be billable even if no response was durably recorded. Keep or reconstruct its pending reservation and mark the charge unresolved instead of treating it as free or fabricating a proposal. Stronger recovery needs a durable submission/response journal and reconciliation under the provider contract."
  },
  {
    "id": "mle-testing",
    "area": "Production system design",
    "title": "Test the contracts, not the model mood",
    "prompt": "What tests give useful confidence without making CI depend on paid stochastic responses?",
    "answer": "I would test action invariants, schema/physical rejection paths, per-shopper ordering, replay reconstruction, lifecycle control, accounting and corruption handling with explicit deterministic providers and fixtures. Inject slow calls, duplicate delivery, malformed responses, ledger ambiguity and interrupted records. Property-based tests could generate action sequences to check invariants, as a proposed extension.\n\nSimply already has offline contract and replay-equivalence checks. These verify implementation behavior, not human realism or fresh model quality. Paid evaluations belong in a separate versioned study with retained failures and controlled inputs.",
    "rubric": [
      "Use explicit offline fixtures and injected failures.",
      "Test invariants and independent readers.",
      "Separate deterministic CI from stochastic evaluation.",
      "State what those tests cannot establish."
    ],
    "followup": "How would you test a race that appears only when responses return out of order?",
    "source": "simulation/tests/test_shared_engine.py · simulation/tests/test_live_stream.py · landing/scripts/verify-replay.cjs",
    "check": "What can offline replay-equivalence tests establish?",
    "options": [
      "Independent readers match recorded state under the evidence contract.",
      "A fresh hosted model always repeats the recording.",
      "Synthetic personas are validated human surrogates.",
      "All unseen deployment tasks will succeed."
    ],
    "followupAnswer": "Use injected providers coordinated by test barriers/events so B completes before A on purpose. Assert per-shopper ordering, owner-only mutation, correct observation binding and identical recorded/streamed outcomes. Avoid sleep-based assumptions; repeat interleavings only when they test a distinct contract."
  },
  {
    "id": "mle-retrieval",
    "area": "ML problem framing",
    "title": "RAG versus fine-tuning versus prompting",
    "prompt": "If the catalogue grows dramatically, would you use RAG, fine-tuning or a longer prompt?",
    "answer": "I would start from the failure: missing current product facts suggests retrieval, poor response format or learned decision patterns may motivate SFT, and a small instruction/context gap may be solved by prompting. Retrieval supplies facts without updating weights, while fine-tuning changes behavior and can still use retrieved context. Neither replaces physical validation.\n\nSimply currently supplies catalogue/map/task facts through its prompt; it has no evaluated RAG subsystem. A future retriever would need recall@k for reachable task-relevant products, stale-data handling, latency/cost measurements and full-trip comparisons. Retrieval must not hide legal options unevenly across layout arms.",
    "rubric": [
      "Choose an intervention from a diagnosed failure.",
      "Separate dynamic knowledge from learned behavior.",
      "Evaluate retrieval coverage as well as rollout outcomes.",
      "Avoid claiming an existing RAG system."
    ],
    "followup": "How could a retriever with high average recall still systematically hurt one layout?",
    "source": "simulation/agents/prompts.py · simulation/core/perception.py · simulation/evaluation/study.py",
    "check": "Which intervention most directly supplies changing catalogue facts without updating weights?",
    "options": [
      "Retrieval of relevant current catalogue data into the observation.",
      "Reusing old model weights as a live inventory database.",
      "Treating all tokenizer vocabulary as current product stock.",
      "Increasing LoRA rank without supplying current facts."
    ],
    "followupAnswer": "Average recall can hide misses on particular shelf placements, long lists or product categories. Retrieval based on distance or candidate truncation could expose different useful options by layout. Inspect task-relevant recall by arm and freeze the retrieval policy as part of the experimental condition."
  },
  {
    "id": "mle-fairness",
    "area": "Responsible evaluation",
    "title": "Slices, fairness and synthetic personas",
    "prompt": "How would you check whether aggregate improvements hide worse outcomes for some shoppers?",
    "answer": "I would predefine relevant task slices such as list length, navigation difficulty and preference constraints, then report paid completion, fulfillment, assistance and cost distributions by slice with sample counts. A strong overall average can hide regressions for a subgroup, and small slices need uncertainty rather than confident rankings.\n\nSynthetic personas are not validated demographic groups. Simply cannot claim real-world fairness or human representativeness from these profiles. Those claims require an appropriate population, careful data governance and new evidence; any future personalization must avoid inventing sensitive traits.",
    "rubric": [
      "Inspect task-relevant slices and sample counts.",
      "Consider aggregate/subgroup tradeoffs.",
      "Acknowledge sparse-slice uncertainty.",
      "Separate synthetic personas from real demographic validity."
    ],
    "followup": "What would you do if a cheaper policy saves money overall but fails long shopping lists?",
    "source": "simulation/agents/state.py · simulation/evaluation/benchmark.py · simulation/core/metrics.py",
    "check": "What follows from better aggregate performance alone?",
    "options": [
      "Subgroup regressions may still exist and require slice-level evaluation.",
      "Every shopper profile improved.",
      "Synthetic personas establish demographic fairness.",
      "Small slices require no uncertainty."
    ],
    "followupAnswer": "I would quantify the long-list regression, check task balance and inspect failure causes before accepting the average gain. Depending on the product objective, require a quality floor, revise routing or retain the stronger policy for that declared segment. Validate the revised policy on fresh held-out tasks."
  },
  {
    "id": "mle-ownership",
    "area": "Interview defense",
    "title": "Your contribution and a hard tradeoff",
    "prompt": "What did you personally contribute, what came from references/tools, and what would you redesign?",
    "answer": "I would describe only work I can substantiate, using a concrete artifact or commit for each contribution. Gary-2 inspired run/record/replay and navigation; Simply has its own Python execution/evidence boundaries, React bridge and evaluation. I would distinguish assisted coding, design decisions, debugging and validation without claiming I invented reference concepts.\n\nFor a redesign answer, I would choose a real constraint, such as separating a public replay service from authorized paid execution, and explain migration and verification. I would prepare a specific incident and measured result from my own experience rather than inventing a behavioral story.",
    "rubric": [
      "Attribute reference patterns and tool assistance accurately.",
      "Tie personal claims to artifacts you can explain.",
      "Choose one concrete tradeoff and redesign.",
      "Use an authentic incident instead of an invented story."
    ],
    "followup": "Walk me through a bug you diagnosed: evidence, hypothesis, fix and verification.",
    "source": "simulation/docs/architecture.md · simulation/docs/gary2-live-reference.md · .github/workflows/offline-evaluation.yml",
    "check": "What makes an ownership answer credible?",
    "options": [
      "Specific explainable artifacts, accurate attribution and a real decision or debugging example.",
      "Claiming every technique was invented for this project.",
      "Inventing an outage story to sound experienced.",
      "Naming frameworks without explaining any tradeoff."
    ],
    "followupAnswer": "Use a real incident: describe the observed symptom, your role, the evidence that narrowed it, the hypothesis you tested, the smallest effective fix and the verification. If you have not handled a production outage, say so and use an authentic local failure. Do not present generated examples as personal experience."
  },
  {
    "id": "mle-coding",
    "area": "Coding and algorithms",
    "title": "Implement a legal-action baseline",
    "prompt": "On a grid with blocked cells and unit-cost moves, how would you find a shortest route? Does solving each next destination optimize a whole shopping trip?",
    "answer": "Breadth-first search visits reachable cells in nondecreasing step distance on an unweighted grid. With a queue and visited/predecessor maps its complexity is O(V + E); reconstruct the path from predecessors. Dijkstra is appropriate for nonnegative unequal edge costs; A* can exploit an admissible heuristic under the corresponding search assumptions.\n\nChoosing the nearest remaining product repeatedly is a greedy route heuristic, not proof of the best multi-target tour. In Simply a baseline must respect pickup reachability, checkout and action semantics, and remain an explicit comparison policy rather than browser shopping logic.",
    "rubric": [
      "Give BFS data structures and complexity.",
      "Distinguish unweighted from weighted search.",
      "Separate point-to-point optimality from multi-target ordering.",
      "Respect authoritative action semantics."
    ],
    "followup": "When is Manhattan distance only a lower bound rather than the actual shortest path?",
    "source": "simulation/core/grid.py · simulation/core/navigation.py · simulation/core/actions.py",
    "check": "Does greedily visiting the nearest item guarantee the shortest multi-item shopping route?",
    "options": [
      "No; optimal point-to-point paths do not guarantee optimal ordering of all targets.",
      "Yes; BFS makes every target order optimal.",
      "Yes; Manhattan distance includes all obstacles.",
      "No; therefore legal paths cannot be computed."
    ],
    "followupAnswer": "For axis-aligned unit-cost grid movement, Manhattan distance ignores obstacles, so it lower-bounds path length when a path exists. It is exact only when an obstacle-free shortest monotone route is available. Pickup adjacency and required checkout can further change the relevant route objective."
  },
  {
    "id": "mle-regression",
    "area": "Coding and algorithms",
    "title": "Compute trustworthy streaming metrics",
    "prompt": "How would you calculate cost per completed trip online without making empty or unknown values misleading?",
    "answer": "Maintain separate totals for attempted/completed trips, known costs and unknown-charge reservations, scoped to an explicitly defined run subset. Cost per completion is the included cost total divided by paid completions, with a clear undefined state when the denominator is zero. Unknown cost is not zero and should remain disclosed alongside any partial estimate.\n\nFor Simply, compute in Python from canonical outcomes and retain currency units and frozen pricing identity. React displays those metrics. I would test zero completions, partial tails, failures, unknown usage and duplicate transport so the same event is never counted twice.",
    "rubric": [
      "Define included subset and numerator/denominator.",
      "Preserve zero-denominator and unknown-value semantics.",
      "Keep currency units and serving/price identity.",
      "Avoid double counting duplicated events."
    ],
    "followup": "Why is averaging per-run ratios different from dividing pooled totals?",
    "source": "simulation/core/metrics.py · simulation/core/accounting.py · simulation/core/evidence.py",
    "check": "How should cost per completed trip appear when there are no completed trips?",
    "options": [
      "Undefined/N/A with attempts and costs disclosed, rather than a fabricated zero.",
      "Zero, because no successful trip was charged.",
      "Equal to basket sales.",
      "The mean shopper budget."
    ],
    "followupAnswer": "A mean of run ratios weights each run equally, while pooled totals weight by the denominator. For example, costs/completions 10/1 and 10/10 yield a mean of 5.5 but pooled 20/11, about 1.82. Choose the estimand explicitly and preserve zero/unknown cases rather than switching formulas silently."
  },
  {
    "id": "mle-compression",
    "area": "Model fundamentals",
    "title": "Distillation and teacher limitations",
    "prompt": "Would training Qwen on a teacher automatically reproduce the teacher’s abilities or remove the need for assistance?",
    "answer": "No. Distillation or imitation transfers signals from selected teacher examples under a training objective; it cannot guarantee the teacher’s full capability, independent task coverage or rollout recovery. A scripted teacher also encodes its own heuristics and errors. Labels produced after assistance teach the assisted action unless original/proposed targets are distinguished.\n\nSimply’s synthetic teacher is an explicit fixture, not a Luna/Terra or human demonstration corpus. I would record label provenance, evaluate the exact base versus candidate on held-out missions, and measure behavior with and without assistance in separately controlled arms.",
    "rubric": [
      "Explain the limits of imitation/distillation.",
      "Track teacher and assistance provenance.",
      "Avoid mislabeling synthetic fixtures as hosted/human data.",
      "Evaluate base/tuned full trips under declared assistance."
    ],
    "followup": "What would you do when two different legal routes are equally good but only one is labeled?",
    "source": "data/finetuning_demo/README.md · simulation/core/navigation.py · notebooks/README.md",
    "check": "What policy do post-assistance action labels most directly teach?",
    "options": [
      "The demonstrated assisted behavior, which must be distinguished from raw model proposals.",
      "Pure unassisted model intelligence by definition.",
      "A validated human shopping distribution.",
      "An optimal policy for every unseen store."
    ],
    "followupAnswer": "Teacher exact-match will mark an alternative route wrong even when it is legal and equally good. I would keep exact agreement as an imitation diagnostic, add physical/task-level validation and full-trip outcomes, and consider multiple valid targets or preference labels if the training objective warrants them."
  }
];

export const mleQuestions: Question[] = drills.map(({ id, area, title, prompt, answer, rubric, followup, followupAnswer, source }) => ({ id, area, title, prompt, answer, rubric, followup, followupAnswer, source }));
export const mleQuiz: QuizQuestion[] = drills.map(q => ({ id: q.id, area: q.area, title: q.title, prompt: q.check, options: q.options, correctIndex: 0, explanation: `${q.options[0]}\n\n${q.answer}\n\nInterviewer follow-up: ${q.followup}\n\n${q.followupAnswer}`, source: q.source }));
