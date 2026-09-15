from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".txt",
    ".md",
    ".html",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".webp",
}
VALID_STATES = {"pending", "indexed", "failed", "delete_pending", "deleted"}


def normalize_workspace(value: str) -> str:
    workspace = value.strip().lower()
    if not workspace:
        raise ValueError("workspace must not be empty")
    return workspace


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
    source_url: str | None = None
    website_id: str | None = None
    page_id: str | None = None
    asset_id: str | None = None
    generation: str | None = None
    evidence_type: str | None = None
    document_version: str | None = None
    effective_date: str | None = None
    page_number: int | None = None
    section_heading: str | None = None
    slide_number: int | None = None
    sheet_name: str | None = None
    cell_range: str | None = None
    line_range: str | None = None
    workspace: str | None = None
    retrieval: dict[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_source_path(self.source_path)
        if not self.chunk_id or not self.content.strip() or not self.source.strip():
            raise ValueError("evidence fields must not be empty")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page number must be positive")
        if self.evidence_type is not None and self.evidence_type not in {
            "page_text",
            "image_ocr",
            "image_description",
        }:
            raise ValueError("invalid evidence type")
        if self.website_id and (
            not self.source_url
            or not self.page_id
            or not self.generation
            or not self.evidence_type
        ):
            raise ValueError("website evidence provenance is incomplete")
        if (
            self.evidence_type in {"image_ocr", "image_description"}
            and not self.asset_id
        ):
            raise ValueError("website image evidence asset id is required")
        suffix = PurePosixPath(self.source_path).suffix.lower()
        if suffix == ".docx" and self.page_number is not None:
            raise ValueError("DOCX page number is not supported")


@dataclass(frozen=True)
class EvidenceResult:
    status: str
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[str, ...] = ()

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "has_valid_evidence": self.has_valid_evidence,
            "evidence": [asdict(item) for item in self.evidence],
            "warnings": list(self.warnings),
        }
