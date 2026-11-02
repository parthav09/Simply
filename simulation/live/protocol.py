"""Incremental, validated projections of flushed canonical records."""
import copy
import hashlib
import json

from core.recording import RecordingView, display_profile, display_state, totals
from core.run_log import _start, _event, _end, _reject_constant


class LiveProjection:
    def __init__(self):
        self.view=None
        self.frames=[]
        self.digest=hashlib.sha256()
        self.initial=None

    def append(self, line):
        if not line.endswith(b'\n'):raise ValueError('Unflushed record')
        record=json.loads(line.decode('utf-8'),parse_constant=_reject_constant)
        if self.view is None:
            _start(record)
            if record['config']['mode']!='actions':raise ValueError('Live lab requires action records')
            self.view=RecordingView(record);self.initial=self.view.snapshot()
        elif self.view.end is not None:raise ValueError('Record after run end')
        elif record['type']=='decision':
            _event(record,self.view.start,self.view.events,self.view.states)
            self.view.append(record)
            aid=record['agent_id'];catalogue=self.view.start['catalogue']
            self.frames.append({'sequence':record['sequence'],'round':record['round'],'agent_id':aid,
                'before':display_state(record['before'],catalogue),'after':display_state(record['after'],catalogue),
                'action':record['action'],'outcome':record['outcome'],'failure':record['failure'],
                'totals':totals(self.view.summary),
                'shopper_metrics':next(s for s in self.view.summary['shoppers'] if s['agent_id']==aid)})
        elif record['type']=='run_end':
            _end(record,self.view.start,self.view.events,self.view.states);self.view.append(record)
        else:raise ValueError('Unknown canonical record')
        self.digest.update(line)
        return record['type']

    def source(self):
        h=self.view.start
        return {'run_id':h['run_id'],'sha256':self.digest.hexdigest(),'provider':h['provider'],'model':h['model'],
                'recorded_at':h['recorded_at'],'prompt_variant':h.get('prompt_variant','legacy'),
                'prompt_version':h['prompt_version'],'warnings':[], 'status':self.view.summary['status']}

    def snapshot(self):
        h=self.view.start
        return {'schema_version':1,'source':self.source(),'layout':copy.deepcopy(h['layout']),
                'catalogue':copy.deepcopy(h['catalogue']),'shoppers':[display_profile(s) for s in h['shoppers']],
                'initial':copy.deepcopy(self.initial),'events':copy.deepcopy(self.frames),
                'summary':copy.deepcopy(self.view.summary),'final':self.view.snapshot(),'config':h['config']}

    def transition(self, terminal=False):
        return {'stream_version':1,'source':self.source(),'frame':self.view.snapshot(),
                'event':None if terminal else copy.deepcopy(self.frames[-1])}
