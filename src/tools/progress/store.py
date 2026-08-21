"""SQLite state using customer-owned nine-table model."""
import json,sqlite3
from pathlib import Path
from .contracts import SourceEvent
def open_store(path:Path):
 path.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(path); c.row_factory=sqlite3.Row; return c
def migrate(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY); CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY,workspace TEXT NOT NULL); CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,workspace TEXT NOT NULL,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS threads(id TEXT PRIMARY KEY,workspace TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,workspace TEXT NOT NULL,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,workspace TEXT NOT NULL,proposal_id TEXT UNIQUE NOT NULL,actor TEXT,expires_at TEXT,status TEXT NOT NULL); CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,workspace TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY,workspace TEXT NOT NULL); CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY,workspace TEXT NOT NULL,event TEXT NOT NULL);'''); c.commit()
def append_source(c,source):
 row=c.execute('SELECT id FROM events WHERE id=?',(source.source_id,)).fetchone()
 if row:return row['id'],False
 c.execute('INSERT INTO events VALUES(?,?,?)',(source.source_id,source.workspace,json.dumps(source.__dict__,sort_keys=True))); c.commit(); return source.source_id,True
def save_flow_result(c,result):
 with c:
  c.execute('INSERT OR IGNORE INTO tasks VALUES(?,?,?)',(result.task.task_id,result.task.workspace,json.dumps(result.task.__dict__,sort_keys=True)))
  c.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',(result.proposal.proposal_id,result.proposal.workspace,json.dumps({'kind':'proposal',**result.proposal.__dict__},sort_keys=True)))
def request_knowledge_sync(c,proposal_id,workspace,evidence_id,source_path,revision):
 key='knowledge-sync:'+proposal_id+':'+revision
 rows=c.execute("SELECT id,event FROM audit_log WHERE workspace=?",(workspace,)).fetchall()
 for row in rows:
  try:
   if json.loads(row['event']).get('idempotency_key')==key:return row['id'],False
  except (ValueError,TypeError):pass
 payload=json.dumps({'idempotency_key':key,'status':'requested','proposal_id':proposal_id,'evidence_id':evidence_id,'source_path':source_path,'revision':revision},sort_keys=True)
 cursor=c.execute('INSERT INTO audit_log(workspace,event) VALUES(?,?)',(workspace,payload)); return cursor.lastrowid,True
def pending_knowledge_sync(c):
 result=[]
 for row in c.execute('SELECT * FROM audit_log ORDER BY id'):
  try:
   if json.loads(row['event']).get('status') in {'requested','failed'}:result.append(dict(row))
  except (ValueError,TypeError):pass
 return result
