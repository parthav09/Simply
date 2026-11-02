"""Run the Python simulation and export its evidence to the React web lab."""
import argparse
import sys
from pathlib import Path

SIMULATION_DIR=Path(__file__).resolve().parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0,str(SIMULATION_DIR))


def main(argv=None):
    from core.config import ACTIVE_LAYOUT_IDS, DEFAULT_CONCURRENCY, DEFAULT_SHOPPER_COUNT, MAX_SHOPPER_COUNT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--headless',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--replay',type=Path,help='Inspect a saved run in the terminal without model calls')
    parser.add_argument('--layout',choices=ACTIVE_LAYOUT_IDS,default=ACTIVE_LAYOUT_IDS[0])
    parser.add_argument('--shoppers',type=int,choices=range(1,MAX_SHOPPER_COUNT+1),default=DEFAULT_SHOPPER_COUNT,help='10–15 shoppers for model runs; smaller counts are reserved for offline tests')
    parser.add_argument('--max-rounds',type=int,default=120)
    parser.add_argument('--turn-budget',type=int,default=120)
    parser.add_argument('--concurrency',type=int,default=DEFAULT_CONCURRENCY)
    parser.add_argument('--provider',choices=('openrouter','openai','gemini','fake'),default='openrouter')
    parser.add_argument('--model',choices=('gpt-6-luna','gpt-6.1-terra'),help='Shopper model (default: gpt-6-luna); provider is frozen per run')
    parser.add_argument('--prompt',choices=('baseline','informed'),default='informed')
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--requests-per-minute',type=int,help='Admission pacing (OpenRouter default 18/min; other providers 0)')
    parser.add_argument('--ledger',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--export-web',action='store_true',help='Export the saved run into the React replay catalogue')
    parser.add_argument('--allow-test-export',action='store_true',help='Explicitly publish a clearly labeled test fixture')
    parser.add_argument('--allow-partial-export',action='store_true',help='Explicitly publish partial evidence with its status')
    args=parser.parse_args(argv)
    if args.requests_per_minute is None:
        args.requests_per_minute=18 if args.provider=='openrouter' else 0
    if not args.replay and args.provider!='fake' and args.shoppers<DEFAULT_SHOPPER_COUNT:
        parser.error('Model runs require 10–15 shoppers; --provider fake permits smaller offline fixtures')
    try:
        if args.replay:
            from replay.__main__ import replay_text
            from core.run_log import read_run
            print(replay_text(read_run(args.replay)))
            path=args.replay
        else:
            from agents.providers import FakeDecisionProvider
            from core.session import SimulationSession
            from core.shopping import SIMPLE_SHOPPING
            from core.run_log import summary_text
            session=SimulationSession(args.layout,args.shoppers,args.max_rounds,args.turn_budget,args.concurrency,
                     decide=FakeDecisionProvider() if args.provider=='fake' else None,output_path=args.output,
                     prompt_variant=args.prompt,seed=args.seed,ledger_path=args.ledger,
                     requests_per_minute=args.requests_per_minute,provider_name=args.provider,model_name=args.model,
                     shopping_rules=SIMPLE_SHOPPING)
            path=session.run()
            print(f'Saved run: {path}');print(summary_text(session.summary))
        if args.export_web:
            from core.export_replay import export_run
            target=export_run(path,SIMULATION_DIR.parent/'landing/public/replays',
                              allow_partial=args.allow_partial_export,allow_test=args.allow_test_export)
            print(f'Exported: {target}')
            print('React lab: npm run dev --prefix landing, then open http://localhost:3000/lab')
    except (ValueError,OSError,RuntimeError) as e:
        parser.exit(2,f'Run failed: {e}\n')
    except KeyboardInterrupt:
        parser.exit(130,'Interrupted; recorded evidence retained.\n')

if __name__=='__main__':main()
