"""Project a verified progress report to Azure and prove indexed revision."""
from dataclasses import dataclass
import json
from time import monotonic, sleep
@dataclass(frozen=True)
class KnowledgeSyncResult: status:str; source_path:str; revision:str
def _escape(value): return value.replace("'","''")
def sync_verified_report(*,content,workspace,source_path,revision,text_container,indexers,text_indexer,wait,search,timeout_seconds=60,interval_seconds=2,clock=monotonic,pause=sleep):
 if not content or not workspace or not source_path.startswith(f'workspaces/{workspace}/progress/') or not revision: raise ValueError('verified scoped report required')
 metadata={'workspace':workspace,'source_path':source_path,'document_version':revision,'access_groups':json.dumps(['internal'],separators=(',',':'))}
 text_container.upload_blob(source_path,content,overwrite=True,metadata=metadata); indexers.run_indexer(text_indexer)
 waited=wait(indexers,[text_indexer])
 if waited.get('status')!='success': return KnowledgeSyncResult('pending',source_path,revision)
 deadline=clock()+timeout_seconds
 while True:
  rows=list(search(search_text=revision,filter="source_path eq '%s' and search.ismatch('%s', 'source_path')"%(_escape(source_path),_escape(workspace)),select=['content','source_path','document_version'],top=8))
  if any(revision in str(row.get('content','')) or row.get('document_version')==revision for row in rows): return KnowledgeSyncResult('verified',source_path,revision)
  if clock()>=deadline:return KnowledgeSyncResult('pending',source_path,revision)
  pause(interval_seconds)
