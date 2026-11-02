# Saved results and comparison

The earlier cleanup retained the newest successful historical recording for A
and B. Their bytes and identities remain unchanged. The newly authorized
October 29 experiments additionally retain every study attempt and two separate
pilots; older deleted archives have not been restored. API accounting stays in
its persistent ledger independently of recording retention.

The Evidence page opens with four model/layout conditions, paired differences,
and collection coverage. Its incomplete banner explains the OpenAI credit
interruption: seven complete runs, one stopped attempt and twelve uncollected
slots. All attempts remain in arm averages; only intact pairs enter differences.
Individual-run cards and their six primary measures are collapsed below:

- Checkout completion across all shoppers.
- Requested items actually purchased at checkout.
- Successful moves per shopper, including unfinished shoppers.
- Simulated checkout sales.
- Known API estimate, marked partial when charges are unknown.
- API cost per completed trip, unknown if no shopper finished or costs are incomplete.

The Python service computes values and comparison differences. React formats
them and draws checkout progress. It never recalculates shopping outcomes.
Diagnostics, source identities and downloads are collapsed. Controlled-study
reports are in a separate collapsed section. Current contrasts have only one or
two complete repetitions, so differences are descriptive without intervals.

Local results refresh every 15 seconds while visible, without model calls.
The integrity-bound published snapshot works when Python is offline:

```bash
.venv/bin/python -m simulation.core.evidence --root simulation/runs --destination landing/public/replays
npm run verify:history --prefix landing
```

The raw input logs are validated, duplicate copies deduplicated, and conflicting
identities excluded. Missing measurements remain unknown. The regression suite
keeps its own offline fixtures in `simulation/tests/fixtures`; those are software
test inputs and do not appear as retained model runs.
