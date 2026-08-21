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
 source=SourceEvent('telegram:-1003835812097:11:42','protein-bar','telegram','2026-08-21T03:00:00Z','actor',hashlib.sha256(b'TEST_ENTITY_A').hexdigest(),{'chat_id':'-1003835812097','thread_id':'11','message_id':'42'})
 context=ResolutionContext('protein-bar',{'test-entity-a':'TEST_ENTITY_A'},'progress-report-v1','owner-a')
 result=build_flow_a(source,{'supplier_key':'test-entity-a','summary':'Entity status changed.','task_summary':'Review entity status','due_at':'2026-08-24','draft':'Request a status update.'},context)
 assert result.missing_field is None and result.proposal.risk_tier==2 and result.draft_sent is False and result.task.owner=='owner-a'
 assert build_flow_a(source,{'summary':'Status changed'},context).proposal is None
 with tempfile.TemporaryDirectory() as td:
  runtime=Path(td); db=runtime/'state.sqlite3'; c=open_store(db); migrate(c); identity,created=append_source(c,source); assert created and append_source(c,source)==(identity,False); save_flow_result(c,result); c.close()
  target=ReportTarget('progress-report-v1','protein-bar',fixture,'## Blockers',hashlib.sha256(original).hexdigest()); assert 'Entity status changed' in preview_markdown(target,result.proposal).after
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
    result=sync_verified_report(content=b'revision: abc123\nEntity status changed.',workspace='protein-bar',source_path='workspaces/protein-bar/progress/progress-report-v1.md',revision='abc123',text_container=blob,indexers=indexers,text_indexer='text',wait=lambda *_a,**_k:{'status':'success'},search=lambda **kw:seen.append(kw) or [{'content':'revision: abc123'}])
    assert result.status=='verified' and len(blob.uploads)==1 and indexers.runs==['text'] and 'source_path eq' in seen[0]['filter']

def test_current_answer_prefers_new_state():
    from tools.progress.answer import compose_current_answer
    answer=compose_current_answer('Entity status changed.','abc123',[],'progress-report-v1.md'); assert 'Entity status changed' in answer.text and answer.sync_status=='pending'
    fresh=compose_current_answer('Entity status changed.','abc123',[{'content':'revision: abc123','source_path':'workspaces/protein-bar/progress/progress-report-v1.md'}],'progress-report-v1.md'); assert fresh.sync_status=='verified' and fresh.citation




def test_ambiguous_input_returns_typed_missing_field():
    from tools.progress.flow import build_flow_a,ResolutionContext
    from tools.progress.contracts import SourceEvent
    source=SourceEvent('ambiguous-entity','protein-bar','telegram','2026-08-21T00:00:00Z','user','abc',{'message_id':'m-amb'})
    result=build_flow_a(source,{'summary':'Entity status changed','task_summary':'Follow up next week','due_at':'2026-08-31','draft':'Following up.'},ResolutionContext('protein-bar',{},'protein-bar-progress-v1','Klaus'))
    assert result.missing_field=='entity'
    assert result.task is None and result.proposal is None and result.draft is None
    resolver=(SRC/'tools/progress/flow.py').read_text(encoding='utf-8')
    assert '?' not in resolver
if __name__=='__main__':
 test_ambiguous_input_returns_typed_missing_field()
 main()
