# Focused shopper prompt revision

This describes the preceding `focused-v2` prompt. The current
`observe-plan-v3` revision and execution review are documented in
[gary2-agent-optimization.md](gary2-agent-optimization.md).

Reviewed Gary-2's current `simulation/agents/llm.py` on October 27, 2026:
https://github.com/ved-2004/Gary-2/blob/main/simulation/agents/llm.py

`LLMAgent.build_system_prompt` and `build_state_snapshot` provide persona context,
a previous public plan, recent actions/positions, destination visit counts,
remaining targets, visible target markers, and explicit checkout reminders.
Those structures help the model keep a destination across individual moves.

Gary-2 also uses `adjust_llm_action` to replace some proposals with programmed
pickups, less-visited movement, checkout navigation or checkout itself. Simply
does not adopt those overrides: its applied actions remain the validated model
proposals, including poor choices. A prompt can ask the shopper to focus; it
cannot guarantee that the model will comply.

Simply's informed `focused-v2` prompt adds:

- A concrete shopping mission, one target at a time, and the previous public plan.
- Needed-unit, price-limit and affordability facts for currently reachable items.
- The same full department map for every layout, with walkable shelf-access cells
  and an ASCII floor map. It exposes no remote product assortment or prices.
- Recorded destination visit counts and instructions to reconsider oscillation.
- Explicit two-action checkout semantics and a reminder to reserve return time.

No route solver runs in the prompt builder. Checkout distance is explicitly a
Manhattan lower bound, not a traversable route or a selected action. New facts
are observations, not automatic movement, buying or budget enforcement.
The original baseline is unchanged and its nine historical prompt fixtures
remain authoritative. The preceding informed builder is archived in
`prompts/informed-before-focused-v2.py.txt`; original recordings keep their full
saved prompts and hashes. The v4 campaign was cancelled before changing prompts,
so its observations must not be combined with a new prompt as one fixed study.

The map's emoji signs and badges are presentation only. They never move shelves,
shopper positions or change purchases. Historical recordings display the same
saved department geometry with the improved signs.
