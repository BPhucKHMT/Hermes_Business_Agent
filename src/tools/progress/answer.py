"""Compose current progress truth with optional matching KB citation."""
from dataclasses import dataclass
@dataclass(frozen=True)
class CurrentAnswer: text:str; sync_status:str; citation:str|None
def compose_current_answer(current_text,revision,evidence,display_name):
 matching=next((row for row in evidence if revision in str(row.get('content','')) or row.get('document_version')==revision),None)
 if matching:return CurrentAnswer(current_text,'verified',f"{display_name} — {matching.get('source_path')}")
 return CurrentAnswer(current_text+' Knowledge sync pending.','pending',None)
