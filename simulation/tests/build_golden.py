"""Build explicitly scripted cross-runtime evidence, never a model benchmark."""
import json
import sys
from dataclasses import replace
from pathlib import Path

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))
from agents.base import Decision,ProposalResult
from agents.shopper import Shopper
from core.customers import load_customers
from core.export_replay import build_bundle
from core.grid import build_store
from core.recording import RecordingView
from core.run_log import read_run
from core.session import SimulationSession


def build(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    grid=build_store();profiles=load_customers()
    item=replace(profiles[0].shopping_list[0],quantity=2,max_acceptable_unit_price=.01)
    first=replace(profiles[0],shopping_list=(item,),budget_per_trip_usd=.01)
    shoppers=grid.spawn([Shopper(first),Shopper(profiles[1])])
    product=grid.products[item.product_id]
    shoppers[0].state.x,shoppers[0].state.y=grid.stand_cells_for((product['x'],product['y']))[0]
    grid.refresh(shoppers[0])
    position=(shoppers[0].state.x,shoppers[0].state.y)
    path=grid.find_path(position,grid.checkout)
    moves=[]
    for cell in path:
        delta=cell[0]-position[0],cell[1]-position[1]
        moves.append(Decision({(-1,0):'move_left',(1,0):'move_right',(0,-1):'move_up',(0,1):'move_down'}[delta],reason='Explicit scripted fixture route'))
        position=cell
    script=[Decision('grab',item.product_id,'Fixture purchase')]*3
    script += [Decision('remove',item.product_id,'Fixture removes one unit'),Decision('remove','unknown','Fixture rejection'),
               ProposalResult('malformed response',None),TimeoutError('Fixture timeout')]
    script += moves+[Decision('checkout',reason='Fixture checkout')]*2
    actions=iter(script)
    class Script:
        model='scripted_test'
        def request(self,prompt,allowed_steps,shopper_id):
            value=next(actions) if shopper_id==first.customer_id else Decision(allowed_steps[0],reason='Fixture unfinished shopper')
            if isinstance(value,Exception):raise value
            if isinstance(value,ProposalResult):return value
            return ProposalResult(json.dumps(value.to_dict()),value,{'request_submitted':False,'estimated_cost_micros':0})
    path=folder/'golden.jsonl'
    if path.exists():path.unlink()
    session=SimulationSession(grid.layout_name,2,len(script),120,1,decide=Script(),output_path=path,grid=grid,shoppers=shoppers)
    session.run();run=read_run(path)
    (folder/'golden.bundle.json').write_text(json.dumps(build_bundle(path,allow_test=True),ensure_ascii=False,separators=(',',':')))
    view=RecordingView(run['start']);frames=[view.snapshot()]
    for e in run['events']:view.append(e);frames.append(view.snapshot())
    view.append(run['end']);frames[-1]=view.snapshot()
    # Expectations are backend-produced views, checked against the independent
    # TypeScript replay projection at every sequence.
    (folder/'golden.expected.json').write_text(json.dumps(frames,ensure_ascii=False,separators=(',',':')))
    return path

if __name__=='__main__':print(build(SIMULATION_DIR/'tests/fixtures'))
