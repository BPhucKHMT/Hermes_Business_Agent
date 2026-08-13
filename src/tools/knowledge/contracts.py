from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Tuple

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".html", ".csv"}
VALID_STATES = {"pending", "indexed", "failed", "delete_pending", "deleted"}


def validate_source_path(value: str) -> str:
    if not value or "\\" in value or Path(value).is_absolute():
        raise ValueError("source path must be relative")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("source path contains traversal")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("unsupported source type")
    return path.as_posix()


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    content: str
    source: str
    source_path: str
    document_version: Optional[str] = None
    effective_date: Optional[str] = None
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    slide_number: Optional[int] = None
    sheet_name: Optional[str] = None
    cell_range: Optional[str] = None
    line_range: Optional[str] = None
    retrieval: Dict[str, Optional[float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_source_path(self.source_path)
        if not self.chunk_id or not self.content.strip() or not self.source.strip():
            raise ValueError("evidence fields must not be empty")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page number must be positive")
        suffix = PurePosixPath(self.source_path).suffix.lower()
        if suffix == ".docx" and self.page_number is not None:
            raise ValueError("DOCX page number is not supported")


@dataclass(frozen=True)
class EvidenceResult:
    status: str
    evidence: Tuple[Evidence, ...] = ()
    warnings: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"ok", "no_evidence", "error"}:
            raise ValueError("invalid evidence status")
        if self.status == "ok" and not self.evidence:
            raise ValueError("ok evidence result must contain evidence")
        if self.status == "no_evidence" and self.evidence:
            raise ValueError("no_evidence result cannot contain evidence")

    @property
    def has_valid_evidence(self) -> bool:
        return bool(self.evidence)

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return {
            "status": self.status,
            "has_valid_evidence": self.has_valid_evidence,
            "evidence": [asdict(item) for item in self.evidence],
            "warnings": list(self.warnings),
        }
