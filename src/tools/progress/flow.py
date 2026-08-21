from __future__ import annotations
"""Small explicit Flow A resolver."""
from dataclasses import dataclass
from hashlib import sha256
from .contracts import MutationProposal,SourceEvent,TaskRecord
@dataclass(frozen=True)
class ResolutionContext: workspace:str; suppliers:dict[str,str]; report_target_id:str; default_owner:str
@dataclass(frozen=True)
class FlowAResult: observation:dict|None; task:TaskRecord|None; proposal:MutationProposal|None; draft:str|None; draft_sent:bool; clarification:str|None
def build_flow_a(source:SourceEvent, extracted:dict, context:ResolutionContext)->FlowAResult:
 if source.workspace!=context.workspace: return FlowAResult(None,None,None,None,False,'Which workspace should this update?')
 key=extracted.get('supplier_key')
 if not key or key not in context.suppliers: return FlowAResult(None,None,None,None,False,'Which supplier did not reply?')
 if not extracted.get('summary'): return FlowAResult(None,None,None,None,False,'What progress change should I record?')
 if not extracted.get('task_summary'): return FlowAResult(None,None,None,None,False,'What follow-up task should I add?')
 if not extracted.get('due_at'): return FlowAResult(None,None,None,None,False,'When is the follow-up due?')
 if not extracted.get('draft'): return FlowAResult(None,None,None,None,False,'Should I prepare an unsent supplier follow-up draft?')
 seed=sha256((source.source_id+key).encode()).hexdigest()[:20]
 task=TaskRecord('task-'+seed,source.workspace,extracted['task_summary'],context.default_owner,extracted['due_at'])
 proposal=MutationProposal('proposal-'+seed,source.workspace,context.report_target_id,extracted['summary'])
 return FlowAResult({'type':'progress','summary':extracted['summary']},task,proposal,extracted['draft'],False,None)
