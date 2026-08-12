from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
import json
import os
from typing import Dict, Iterable, List, Optional

from contracts import VALID_STATES, validate_source_path


@dataclass
class DocumentRecord:
    document_id: str
    source_path: str
    sha256: str
    state: str = "pending"
    active_generation: Optional[int] = None
    previous_generation: Optional[int] = None
    pending_generation: Optional[int] = None
    expected_chunk_ids: List[str] = field(default_factory=list)
    pending_sha256: Optional[str] = None
    error_code: Optional[str] = None

    def validate(self) -> None:
        validate_source_path(self.source_path)
        if not self.document_id or self.state not in VALID_STATES:
            raise ValueError("invalid document record")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("invalid sha256")
        if self.pending_generation is None and (self.expected_chunk_ids or self.pending_sha256 is not None):
            raise ValueError("chunk expectations and pending hash require pending generation")
        if self.pending_sha256 is not None and (len(self.pending_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.pending_sha256)):
            raise ValueError("invalid pending sha256")
        if len(self.expected_chunk_ids) != len(set(self.expected_chunk_ids)):
            raise ValueError("duplicate expected chunk id")


class Manifest:
    def __init__(self, path: Path, records: Optional[Dict[str, DocumentRecord]] = None):
        self.path = path
        self.records = records or {}

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.exists():
            return cls(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        records = {key: DocumentRecord(**value) for key, value in data.get("documents", {}).items()}
        for record in records.values():
            record.validate()
        return cls(path, records)

    def save(self) -> None:
        for record in self.records.values():
            record.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(json.dumps({"schema_version": 1, "documents": {key: asdict(value) for key, value in sorted(self.records.items())}}, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def content_hash(content: bytes) -> str:
        return sha256(content).hexdigest()

    @staticmethod
    def document_id(source_path: str) -> str:
        normalized = validate_source_path(source_path)
        return sha256(normalized.encode("utf-8")).hexdigest()[:24]

    def begin_generation(self, source_path: str, content_hash: str, expected_chunk_ids: Iterable[str]) -> Optional[DocumentRecord]:
        normalized = validate_source_path(source_path)
        document_id = self.document_id(normalized)
        current = self.records.get(document_id)
        if current and current.sha256 == content_hash and current.state == "indexed":
            return None
        generation = (current.active_generation or 0) + 1 if current else 1
        record = DocumentRecord(
            document_id=document_id,
            source_path=normalized,
            sha256=current.sha256 if current and current.active_generation is not None else content_hash,
            state="pending",
            active_generation=current.active_generation if current else None,
            previous_generation=current.previous_generation if current else None,
            pending_generation=generation,
            expected_chunk_ids=sorted(expected_chunk_ids),
            pending_sha256=content_hash,
        )
        record.validate()
        self.records[document_id] = record
        self.save()
        return record

    def activate(self, document_id: str, indexed_chunk_ids: Iterable[str]) -> DocumentRecord:
        record = self.records[document_id]
        expected = set(record.expected_chunk_ids)
        indexed_list = list(indexed_chunk_ids)
        indexed = set(indexed_list)
        if len(indexed) != len(indexed_list) or indexed != expected:
            raise ValueError("indexed chunk set does not match expected chunk set")
        if record.pending_generation is None:
            raise ValueError("no pending generation")
        old_active = record.active_generation
        record.previous_generation = old_active
        record.active_generation = record.pending_generation
        record.pending_generation = None
        record.expected_chunk_ids = []
        record.sha256 = record.pending_sha256
        record.pending_sha256 = None
        record.state = "indexed"
        record.error_code = None
        self.save()
        return record

    def fail(self, document_id: str, error_code: str) -> DocumentRecord:
        if not error_code or any(secret in error_code.lower() for secret in ("key=", "authorization", "connectionstring")):
            raise ValueError("error code must be redacted")
        record = self.records[document_id]
        record.state = "indexed" if record.active_generation is not None else "failed"
        record.pending_generation = None
        record.expected_chunk_ids = []
        record.pending_sha256 = None
        record.error_code = error_code
        self.save()
        return record

    def active_snapshot(self) -> Dict[str, int]:
        return {
            key: record.active_generation
            for key, record in self.records.items()
            if record.state != "deleted" and record.active_generation is not None
        }
