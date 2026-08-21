"""Registered Markdown target projection."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from .contracts import MutationProposal
@dataclass(frozen=True)
class ReportTarget: target_id:str; workspace:str; source:Path; heading:str; base_sha256:str
@dataclass(frozen=True)
class DocumentPreview: before:str; after:str

def preview_markdown(target:ReportTarget,proposal:MutationProposal):
 if target.workspace!=proposal.workspace or target.target_id!=proposal.target_id: raise ValueError('target mismatch')
 raw=target.source.read_bytes()
 if sha256(raw).hexdigest()!=target.base_sha256: raise ValueError('stale base')
 text=raw.decode('utf-8-sig'); count=text.count(target.heading)
 if count!=1: raise ValueError('heading must match exactly once')
 start=text.index(target.heading); body=start+len(target.heading); end=text.find('\n## ',body); end=len(text) if end<0 else end
 replacement=f"{target.heading}\n\n- {proposal.summary}\n"; return DocumentPreview(text,text[:start]+replacement+text[end:].lstrip('\n'))
def apply_markdown(target,preview,output_dir,proposal_id):
 output_dir.mkdir(parents=True,exist_ok=True); path=output_dir/f'{target.target_id}-{proposal_id}.md'; tmp=path.with_suffix('.tmp'); tmp.write_text(preview.after,encoding='utf-8'); tmp.replace(path); return path
