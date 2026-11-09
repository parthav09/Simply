"""Generate one real shopper proposal without applying an action or saving a run."""
import json
from pathlib import Path

from agents.mps_provider import MPSProvider
from core.grid import build_store
from core.shopping import SIMPLE_SHOPPING,configure_shopper
from evaluation.benchmark import instantiate_benchmark,load_benchmark


def main():
    grid=build_store('costco_back_anchor')
    data=load_benchmark(Path(__file__).parent/'benchmarks/two_layouts_15_v2.json')
    shopper=instantiate_benchmark(data,10,grid,shopping_rules=SIMPLE_SHOPPING)[0]
    shopper._grid=grid;shopper.prompt_variant='informed';shopper._action_limit=120
    configure_shopper(shopper,SIMPLE_SHOPPING,grid)
    observation=grid.observe(shopper)
    provider=MPSProvider(None,'inference-check')
    print('Generating one full shopper observation on MPS; no action will be applied.',flush=True)
    result=provider.request(shopper.prompt(observation),observation.allowed_steps,shopper.customer_id)
    output={'check':'inference_only_no_run','model':provider.model,'identity':provider.identity,
        'valid_action':result.decision is not None,'raw_response':result.raw_response,'telemetry':result.telemetry}
    path=Path(__file__).parent/'models/pilot-inference-check.json';path.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'valid_action':output['valid_action'],'raw_response':result.raw_response,
        'usage':result.telemetry['usage'],'inference_ms':result.telemetry['inference_ms']},indent=2))
    if not result.decision:raise SystemExit('The model returned an invalid action; inspect the saved inference check')


if __name__=='__main__':main()
