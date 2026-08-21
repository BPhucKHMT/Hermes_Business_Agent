from __future__ import annotations
import argparse, hashlib, json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'src'; sys.path.insert(0,str(SRC))
def layer_1():
 p=json.loads((SRC/'config/progress_policy.json').read_text(encoding='utf-8')); t=json.loads((SRC/'config/progress_targets/protein_bar_progress.json').read_text(encoding='utf-8'))
 assert p['workspace']=='protein-bar' and p['actions']['report.apply']['tier']==2 and p['actions']['external_message.send']['enabled'] is False
 assert not Path(p['runtime_root']).is_absolute() and t['workspace']=='protein-bar' and t['format']=='markdown' and '..' not in Path(t['source']).parts
 required=('contracts.py','store.py','flow.py','documents.py','executor.py','progress.py'); assert all((SRC/'tools/progress'/x).is_file() for x in required)
 assert (SRC/'skills/progress-report/SKILL.md').is_file(); print('progress layer 1: pass')
def layer_2():
 from tools.progress.contracts import SourceEvent
 from tools.progress.documents import ReportTarget, preview_markdown
 from tools.progress.executor import approve_and_execute, record_approval
 from tools.progress.flow import ResolutionContext, build_flow_a
 from tools.progress.store import append_source, migrate, open_store, save_flow_result
 fixture=ROOT/'tests/fixtures/progress/protein_bar_weekly.md'; original=fixture.read_bytes()
 source=SourceEvent('telegram:-1003835812097:11:42','protein-bar','telegram','2026-08-21T03:00:00Z','klaus',hashlib.sha256(b'WheyCo').hexdigest(),{'chat_id':'-1003835812097','thread_id':'11','message_id':'42'})
 context=ResolutionContext('protein-bar',{'wheyco':'WheyCo'},'protein-bar-weekly-v1','Klaus')
 result=build_flow_a(source,{'supplier_key':'wheyco','summary':'WheyCo has not replied this week.','task_summary':'Follow up with WheyCo','due_at':'2026-08-24','draft':'Hi WheyCo, following up on our request. Please share an update.'},context)
 assert result.clarification is None and result.proposal.risk_tier==2 and result.draft_sent is False and result.task.owner=='Klaus'
 assert build_flow_a(source,{'summary':'Supplier silent'},context).proposal is None
 with tempfile.TemporaryDirectory() as td:
  runtime=Path(td); db=runtime/'state.sqlite3'; c=open_store(db); migrate(c); identity,created=append_source(c,source); assert created and append_source(c,source)==(identity,False); save_flow_result(c,result); c.close()
  target=ReportTarget('protein-bar-weekly-v1','protein-bar',fixture,'## Blockers',hashlib.sha256(original).hexdigest()); assert 'WheyCo has not replied' in preview_markdown(target,result.proposal).after
  c=open_store(db); record_approval(c,result.proposal.proposal_id,'approval-1','Klaus',datetime.now(timezone.utc)+timedelta(minutes=15)); c.close()
  execution=approve_and_execute(db,target,result.proposal.proposal_id,'approval-1','Klaus',runtime/'outputs'); assert execution.status=='verified' and execution.output_path.is_file() and fixture.read_bytes()==original
  repeated=approve_and_execute(db,target,result.proposal.proposal_id,'approval-1','Klaus',runtime/'outputs'); assert repeated.output_path==execution.output_path
  c=open_store(db); assert c.execute("select count(*) from evidence where kind='report_output'").fetchone()[0]==1; c.close()
 test_progress_sync_contract()
 test_current_answer_prefers_new_state()
 print('progress layer 2: pass')
def main():
 p=argparse.ArgumentParser(); p.add_argument('--layer',type=int,choices=(1,2),required=True); a=p.parse_args(); (layer_1 if a.layer==1 else layer_2)()


def test_progress_sync_contract():
    from tools.progress.knowledge_sync import sync_verified_report
    class Blob:
        def __init__(self): self.uploads=[]
        def upload_blob(self,*args,**kwargs): self.uploads.append((args,kwargs))
    class Indexers:
        def __init__(self): self.runs=[]
        def run_indexer(self,name): self.runs.append(name)
    blob=Blob(); indexers=Indexers(); seen=[]
    result=sync_verified_report(content=b'revision: abc123\nWheyCo replied.',workspace='protein-bar',source_path='workspaces/protein-bar/progress/protein-bar-weekly-v1.md',revision='abc123',text_container=blob,indexers=indexers,text_indexer='text',wait=lambda *_a,**_k:{'status':'success'},search=lambda **kw:seen.append(kw) or [{'content':'revision: abc123'}])
    assert result.status=='verified' and len(blob.uploads)==1 and indexers.runs==['text'] and 'source_path eq' in seen[0]['filter']

def test_current_answer_prefers_new_state():
    from tools.progress.answer import compose_current_answer
    answer=compose_current_answer('WheyCo has replied.','abc123',[],'protein-bar-weekly-v1.md'); assert 'WheyCo has replied' in answer.text and answer.sync_status=='pending'
    fresh=compose_current_answer('WheyCo has replied.','abc123',[{'content':'revision: abc123','source_path':'workspaces/protein-bar/progress/protein-bar-weekly-v1.md'}],'protein-bar-weekly-v1.md'); assert fresh.sync_status=='verified' and fresh.citation




def test_ambiguous_supplier_has_zero_side_effect():
    from tools.progress.flow import build_flow_a,ResolutionContext
    from tools.progress.contracts import SourceEvent
    source=SourceEvent('ambiguous-supplier','protein-bar','telegram','2026-08-21T00:00:00Z','user','abc',{'message_id':'m-amb'})
    result=build_flow_a(source,{'summary':'Supplier did not reply this week','task_summary':'Follow up next week','due_at':'2026-08-31','draft':'Following up.'},ResolutionContext('protein-bar',{},'protein-bar-progress-v1','Klaus'))
    assert result.clarification=='Which supplier did not reply?'
    assert result.task is None and result.proposal is None and result.draft is None
if __name__=='__main__':
 test_ambiguous_supplier_has_zero_side_effect()
 main()
