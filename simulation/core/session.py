"""One authoritative execution session; the React lab consumes its records."""
import copy
import hashlib
import json
import queue
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from agents.llm import MODEL, GeminiProvider
from agents.state import FinishedState
from core.budget import CampaignLedger, PRICING
from core.config import DECISION_RUNS_DIR, SIMULATION_DIR
from core.customers import instantiate_agents
from core.grid import LAYOUTS, build_store
from core.config import DEFAULT_CONCURRENCY, DEFAULT_SHOPPER_COUNT, MAX_SHOPPER_COUNT
from core.rounds import RoundCoordinator, state_snapshot
from core.run_log import SCHEMA_VERSION, RunWriter
from core.navigation import MODEL_ONLY, GARY2_CURRENT, POLICIES


from core.integrity import fingerprint
from core.shopping import LEGACY_SHOPPING, SIMPLE_SHOPPING, SHOPPING_RULES, configure_shopper


def snapshot_shoppers(grid, shoppers):
    return [{'agent_id': s.customer_id, 'state': state_snapshot(s, grid.observe(s))} for s in shoppers]


def build_run_start(grid, shoppers, *, run_id, provider, model, max_rounds, concurrency,
                    propose_only, prompt_variant='baseline', seed=42, experiment=None, requests_per_minute=8, generation_settings=None, pricing=None, navigation_policy=MODEL_ONLY, shopping_rules=None):
    digest = hashlib.sha256()
    for filename in ('shopper.py', 'customer.py', 'schema.py', 'steps.py', 'prompts.py'):
        digest.update(filename.encode())
        digest.update((SIMULATION_DIR / 'agents' / filename).read_bytes())
    catalogue = [{k:v for k,v in p.items() if k not in ('x','y')} for _,p in sorted(grid.products.items())]
    profiles = [asdict(s.customer) for s in shoppers]
    header = {
        'type': 'run_start', 'schema_version': SCHEMA_VERSION, 'metrics_version': 2,
        'run_id': run_id, 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'provider': provider, 'model': model,
        'prompt_variant': prompt_variant, 'prompt_version': f'{prompt_variant}:{digest.hexdigest()}',
        'config': {'mode': 'proposals' if propose_only else 'actions',
                   'navigation_policy': navigation_policy,
                   'turn_budget': shoppers[0].turn_budget, 'max_rounds': max_rounds,
                   'concurrency': concurrency, 'seed': seed, 'requests_per_minute': requests_per_minute,
                   'generation': generation_settings if generation_settings is not None else GeminiProvider.generation_settings,
                   'environment': {'inventory': 'replenished', 'crowd_blocking': False, 'checkout_queues': False,
                                   'information': 'department map and checkout known; nearby product details'}},
        'layout': {'id': grid.layout_name, 'width': grid.width, 'height': grid.height,
                   'entrance': grid.entrance, 'checkout': grid.checkout, 'exit': grid.exit,
                   'shelves': [asdict(s) for s in grid.shelves]},
        'catalogue': catalogue,
        'shoppers': [{**snapshot, 'customer': profile,
                      'presentation': {'sprite_index': int(''.join(c for c in s.customer_id if c.isdigit()) or '0') % 20}}
                     for s,profile,snapshot in zip(shoppers,profiles,snapshot_shoppers(grid,shoppers))],
        'input_fingerprints': {'catalogue': fingerprint(catalogue), 'shoppers': fingerprint(profiles)},
        'pricing': pricing or PRICING, 'experiment': experiment,
    }
    header['layout_fingerprint'] = fingerprint(header['layout'])
    if shopping_rules is not None:
        header['config']['shopping_rules'] = shopping_rules
    code = hashlib.sha256()
    for path in sorted((SIMULATION_DIR/'core').glob('*.py')):
        code.update(path.name.encode()); code.update(path.read_bytes())
    header['engine_fingerprint'] = code.hexdigest()
    return header


class SimulationSession:
    """The caller or one background worker owns execution, never the display."""
    def __init__(self, layout_name='costco_back_anchor', shopper_count=DEFAULT_SHOPPER_COUNT, max_rounds=120,
                 turn_budget=120, concurrency=DEFAULT_CONCURRENCY, propose_only=False, decide=None,
                 output_path=None, prompt_variant='informed', seed=42, grid=None,
                 shoppers=None, experiment=None, ledger_path=None, requests_per_minute=0, provider_name="openai",model_name=None,
                 navigation_policy=None, enforce_api_budget=False, allow_action_plans=True, shopping_rules=None):
        if type(enforce_api_budget) is not bool:
            raise ValueError('enforce_api_budget must be a boolean')
        if type(allow_action_plans) is not bool:
            raise ValueError('allow_action_plans must be a boolean')
        for name,value in [('shopper_count',shopper_count),('max_rounds',max_rounds),('turn_budget',turn_budget),('concurrency',concurrency)]:
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if type(requests_per_minute) is not int or requests_per_minute < 0:
            raise ValueError('requests_per_minute must be a nonnegative integer (0 disables pacing)')
        if not 1 <= shopper_count <= MAX_SHOPPER_COUNT:
            raise ValueError('shopper_count must be 1–15 (use 10–15 for model runs)')
        if layout_name not in LAYOUTS or prompt_variant not in ('baseline','informed'):
            raise ValueError('Unknown layout or prompt variant')
        if navigation_policy is None:
            navigation_policy = GARY2_CURRENT if decide is None and not propose_only else MODEL_ONLY
        if navigation_policy not in POLICIES:
            raise ValueError('Unknown navigation policy')
        if shopping_rules is None:
            shopping_rules = SIMPLE_SHOPPING if decide is None and not propose_only else LEGACY_SHOPPING
        if shopping_rules not in SHOPPING_RULES:
            raise ValueError('Unknown shopping rules')
        self.grid = grid if grid is not None else build_store(layout_name)
        self.shoppers = shoppers if shoppers is not None else self.grid.spawn(instantiate_agents(count=shopper_count,turn_budget=turn_budget))
        if len(self.shoppers) != shopper_count:
            raise ValueError('Requested shopper population is unavailable')
        for s in self.shoppers:
            s._grid = self.grid
            s.prompt_variant = prompt_variant
            configure_shopper(s, shopping_rules, self.grid)
        self.run_id = uuid.uuid4().hex
        self.path = Path(output_path) if output_path is not None else DECISION_RUNS_DIR/f'trip_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{self.run_id[:8]}.jsonl'
        self.ledger = CampaignLedger(ledger_path or DECISION_RUNS_DIR/'gemini_campaign.sqlite3',
                                     enforce_limit=enforce_api_budget) if decide is None else None
        from agents.providers import build_provider
        self.provider = decide if decide is not None else build_provider(provider_name,self.ledger,self.run_id,seed,
            (experiment or {}).get('stage','manual'),(experiment or {}).get('stage_limit_usd'),requests_per_minute,model=model_name)
        self.header = build_run_start(self.grid,self.shoppers,run_id=self.run_id,
                        provider=getattr(self.provider,'provider_id',getattr(self.provider,'model','custom')),
                        model=getattr(self.provider,'model','custom'),
                        max_rounds=max_rounds,concurrency=concurrency,propose_only=propose_only,
                        prompt_variant=prompt_variant,seed=seed,experiment=experiment,requests_per_minute=requests_per_minute,
                        generation_settings=getattr(self.provider,'generation_settings',{'decision_source':'explicit_fixture'}),
                        pricing=getattr(self.provider,'pricing',PRICING),navigation_policy=navigation_policy,
                        shopping_rules=shopping_rules if shopping_rules == SIMPLE_SHOPPING else None)
        active_ledger = self.ledger or getattr(self.provider, 'ledger', None)
        self.header['config']['api_budget_enforced'] = bool(getattr(active_ledger, 'enforce_limit', False))
        if not allow_action_plans:
            self.header['config']['decision_mode'] = 'single_action'
        self.action_limit = None if propose_only else min(max_rounds, self.header['config']['turn_budget'])
        for shopper in self.shoppers:
            shopper._action_limit = self.action_limit
        scheduler_limit = max_rounds if propose_only else max_rounds * max(1, len(self.shoppers))
        if allow_action_plans and navigation_policy == MODEL_ONLY and prompt_variant == 'informed' and getattr(self.provider, 'supports_action_plans', False):
            from agents.schema import MAX_PLAN_ACTIONS
            self.header['config']['generation'] = {**self.header['config']['generation'], 'max_output_tokens': 512}
            self.header['config']['action_planning'] = {
                'max_actions': MAX_PLAN_ACTIONS, 'source': 'explicit_model_actions',
                'execution': 'one_validated_action_per_shopper_commit',
                'scheduling': 'independent_async',
                'interrupt_on': ['new_grabbable_products', 'action_failed', 'unexpected_state', 'finished_or_turn_limit'],
            }
            if not propose_only:
                # Independent commits must not spend a peer's action allowance.
                # Recorded max_rounds stays requested*8 so historical logs validate.
                self.header['config']['action_planning']['action_limit'] = self.action_limit
                self.header['config']['action_planning']['requested_max_rounds'] = max_rounds
                scheduler_limit *= MAX_PLAN_ACTIONS
        if self.action_limit is not None:
            self.header['config']['action_limit'] = self.action_limit
        self.header['config']['max_rounds'] = scheduler_limit
        import inspect
        try:
            source_file = inspect.getsourcefile(self.provider if inspect.isfunction(self.provider) else type(self.provider))
        except TypeError:
            source_file = None
        self.header['provider_fingerprint'] = hashlib.sha256(Path(source_file).read_bytes()).hexdigest() if source_file else None
        self.coordinator = RoundCoordinator(self.provider, max_workers=concurrency,
                                            navigation_policy=navigation_policy,layout=self.header['layout'],
                                            action_limit=self.action_limit,allow_action_plans=allow_action_plans)
        self.writer = RunWriter(self.path,self.header)
        self.updates = queue.SimpleQueue()
        self.updates.put(copy.deepcopy(self.header))
        self.rounds_completed = 0
        self._ticks = 0
        self.max_rounds, self.propose_only = scheduler_limit, propose_only
        self.summary, self.error, self.status = None, None, 'ready'
        self._condition = threading.Condition()
        self._paused = False
        self._stop = False
        self._steps = 0
        self._thread = None
        self._closed = False
        self._round_in_flight = False
        self._started = perf_counter()

    def active(self):
        return [s for s in self.shoppers if not isinstance(s.state,FinishedState)
                and not s.out_of_turns and (self.action_limit is None or s.turns_used < self.action_limit)
                and self.grid.observe(s).allowed_steps]

    def _record(self, event, round_number):
        event['elapsed_ms'] = (perf_counter()-self._started)*1000
        self.writer.append(event,round_number)
        self.writer.flush()
        self.updates.put(copy.deepcopy(self.writer.events[-1]))

    def step(self):
        if self._closed:
            return False
        active = self.active()
        if (not active and not self.coordinator.in_flight) or self._ticks >= self.max_rounds:
            self.finish()
            return False
        tick = self._ticks + 1
        if hasattr(self.provider,'round_number'):
            self.provider.round_number = tick
        self.status = 'waiting'
        self._round_in_flight = True
        try:
            outcomes = self.coordinator.tick(self.grid,active,apply_decisions=not self.propose_only,
                                 event_callback=lambda e:self._record(e, tick), wait_all=self.propose_only)
        finally:
            self._round_in_flight = False
        if not outcomes:
            if not self.coordinator.in_flight:
                self.finish()
                return False
            return True
        self._ticks = tick
        self.rounds_completed = tick
        if any(o.failure and o.failure.startswith('Campaign budget exhausted') for o in outcomes):
            self.finish_pending('budget_exhausted','Campaign budget exhausted')
        elif any(e['failure'] and e['failure'].startswith(('Gemini HTTP 400','Gemini HTTP 403','Gemini HTTP 404','Gemini HTTP 429','OpenAI HTTP 400','OpenAI HTTP 401','OpenAI HTTP 403','OpenAI HTTP 404','OpenAI HTTP 429',
                    'OpenRouter HTTP 400','OpenRouter HTTP 401','OpenRouter HTTP 402','OpenRouter HTTP 403','OpenRouter HTTP 404','OpenRouter HTTP 429'))
                 and not (e['failure'].startswith('OpenAI HTTP 400') and e.get('telemetry',{}).get('provider_error_code')=='invalid_prompt')
                 for e in self.writer.events[-len(outcomes):]):
            self.finish_pending('aborted','Provider configuration or quota unavailable')
        elif (not self.active() and not self.coordinator.in_flight) or self._ticks >= self.max_rounds:
            self.finish()
        return True

    def finish_pending(self, status, error):
        """Stop new admissions and record already-submitted work before ending."""
        self._stop = True
        if hasattr(self.provider, 'cancelled'):
            self.provider.cancelled.set()
        self._round_in_flight = True
        try:
            self.coordinator.settle(self.grid, not self.propose_only,
                                    lambda event: self._record(event, self._ticks))
        finally:
            self._round_in_flight = False
        self.finish(status, error)

    def finish(self, status='completed', error=None):
        if self._closed:
            return
        # Never assert a state transition that did not reach the log.
        final = snapshot_shoppers(self.grid,self.shoppers)
        recorded = {s['agent_id']:s['state'] for s in self.header['shoppers']}
        recorded.update({e['agent_id']:e['after'] for e in self.writer.events})
        intact = all(s['state'] == recorded[s['agent_id']] for s in final)
        try:
            if not self.writer.failed and intact:
                self.summary = self.writer.finish(final,self.rounds_completed,status,error)
                self.updates.put({'type':'run_end','status':status,'error':error,
                                  'rounds_completed':self.rounds_completed,'shoppers':final,
                                  'summary':copy.deepcopy(self.summary)})
        finally:
            self.writer.close()
            self.coordinator.close()
            self._closed = True
            self.status = status if intact and not self.writer.failed else 'incomplete'

    def run(self):
        try:
            while not self._closed:
                with self._condition:
                    self._condition.wait_for(lambda:not self._paused or self._steps or self._stop)
                    if self._stop:
                        if self.coordinator.in_flight and not self._closed:
                            self._round_in_flight = True
                            try:
                                settled = self.coordinator.settle(
                                    self.grid, not self.propose_only,
                                    lambda e: self._record(e, self._ticks + 1))
                                if settled:
                                    self.rounds_completed = max(self.rounds_completed, self._ticks + 1)
                            finally:
                                self._round_in_flight = False
                        self.finish('cancelled','Stopped by user')
                        break
                    if self._steps:
                        self._steps -= 1
                if not self.step():
                    break
        except BaseException as error:
            self.error = error
            self.finish('cancelled' if isinstance(error,KeyboardInterrupt) else 'aborted',type(error).__name__)
            raise
        return self.path

    def start(self, paused=False):
        if self._thread is not None or self._closed:
            raise RuntimeError('A session can be started only once')
        self._paused = paused
        def work():
            try:
                self.run()
            except BaseException:
                pass  # error/status are surfaced by the UI, never a policy fallback.
        self._thread = threading.Thread(target=work,name='simply-session',daemon=False)
        self._thread.start()

    def pause(self):
        with self._condition:
            self._paused = True

    def resume(self):
        with self._condition:
            self._paused = False
            self._condition.notify_all()

    def advance(self):
        with self._condition:
            self._paused = True
            self._steps += 1
            self._condition.notify_all()

    def stop(self):
        if hasattr(self.provider,'cancelled'):
            self.provider.cancelled.set()
        with self._condition:
            self._stop = True
            self._condition.notify_all()

    @property
    def closed(self):
        return self._closed

    @property
    def control_status(self):
        if self.closed:return self.status
        if self._stop:return 'stopping'
        if self._paused:return 'pausing' if self._round_in_flight else 'paused'
        return 'waiting_for_model' if self._round_in_flight else 'running'

    def join(self,timeout=None):
        if self._thread:self._thread.join(timeout)
        return self.closed


def preview_configuration(layout_name, count=DEFAULT_SHOPPER_COUNT, turn_budget=120, max_rounds=120, concurrency=DEFAULT_CONCURRENCY, prompt_variant='informed'):
    """Prepare detached presentation data without creating a run or provider."""
    if layout_name not in LAYOUTS or type(count) is not int or not 1 <= count <= MAX_SHOPPER_COUNT:
        raise ValueError('Preview needs an existing layout and 1–15 shoppers')
    grid=build_store(layout_name)
    shoppers=grid.spawn(instantiate_agents(count=count,turn_budget=turn_budget))
    return build_run_start(grid,shoppers,run_id='preview',provider='not-started',model='not-started',
                max_rounds=max_rounds,concurrency=concurrency,propose_only=False,prompt_variant=prompt_variant)
