"""Exact approval and restart-safe execution."""
import json
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from .contracts import ExecutionResult,MutationProposal
from .documents import apply_markdown,preview_markdown
from .store import open_store,request_knowledge_sync
def record_approval(c,proposal_id,approval_id,actor,expires_at):
 row=c.execute('SELECT workspace FROM events WHERE id=?',(proposal_id,)).fetchone()
 if not row: raise ValueError('unknown proposal')
 with c:c.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?)',(approval_id,row['workspace'],proposal_id,actor,expires_at.isoformat(),'approved'))
def approve_and_execute(db,target,proposal_id,approval_id,actor,output_dir):
 c=open_store(db); prior=c.execute("SELECT payload FROM evidence WHERE id=?",('output:'+proposal_id,)).fetchone()
 if prior:c.close(); p=json.loads(prior['payload']); return ExecutionResult('verified',Path(p['path']))
 row=c.execute('SELECT a.*,e.payload FROM approvals a JOIN events e ON e.id=a.proposal_id WHERE a.id=? AND a.proposal_id=?',(approval_id,proposal_id)).fetchone()
 if not row or row['actor']!=actor or row['status']!='approved' or datetime.fromisoformat(row['expires_at'])<=datetime.now(timezone.utc): c.close(); raise PermissionError('exact live approval required')
 payload=json.loads(row['payload']); proposal=MutationProposal(payload['proposal_id'],payload['workspace'],payload['target_id'],payload['summary'],payload['risk_tier']); preview=preview_markdown(target,proposal); path=apply_markdown(target,preview,output_dir,proposal_id)
 if proposal.summary not in path.read_text(encoding='utf-8'): c.close(); raise RuntimeError('read-back failed')
 evidence=json.dumps({'path':str(path.resolve()),'sha256':sha256(path.read_bytes()).hexdigest()},sort_keys=True)
 with c:
  c.execute('INSERT INTO evidence VALUES(?,?,?,?)',('output:'+proposal_id,proposal.workspace,'report_output',evidence))
  request_knowledge_sync(c,proposal_id,proposal.workspace,'output:'+proposal_id,'workspaces/'+proposal.workspace+'/progress/'+target.target_id+'.md',json.loads(evidence)['sha256'])
 c.close(); return ExecutionResult('verified',path)
