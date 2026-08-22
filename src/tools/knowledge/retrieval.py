from typing import Iterable, Optional

from azure.search.documents.models import VectorizableTextQuery

from contracts import Evidence, EvidenceResult

SELECT_FIELDS = [
    "chunk_id", "content", "title", "source_path", "source_url", "website_id",
    "page_id", "asset_id", "generation", "evidence_type", "document_version",
    "effective_date", "page_number", "section_heading", "slide_number",
    "sheet_name", "cell_range",
]


def knowledge_search(
    client,
    query: str,
    access_groups: Iterable[str],
    top_k: int = 8,
    semantic_configuration: str = "knowledge-semantic",
    source_path: Optional[str] = None,
    website_id: Optional[str] = None,
    generation: Optional[str] = None,
    workspace: Optional[str] = None,
) -> EvidenceResult:
    query = query.strip()
    groups = sorted({group.strip() for group in access_groups if group.strip()})
    if not query or not groups or top_k < 1 or (source_path and website_id) or (generation and not website_id):
        raise ValueError("query, access groups, valid top_k, and at most one valid source scope are required")

    filters = ["access_groups/any(g: %s)" % " or ".join("g eq '%s'" % group.replace("'", "''") for group in groups)]
    if source_path:
        filters.append("source_path eq '%s'" % source_path.replace("'", "''"))
    if website_id:
        filters.append("website_id eq '%s'" % website_id.replace("'", "''"))
    if generation:
        filters.append("generation eq '%s'" % generation.replace("'", "''"))
    if workspace:
        filters.append("search.ismatch('%s', 'source_path')" % workspace.strip().lower().replace("'", "''"))

    options = {
        "search_text": query,
        "vector_queries": [VectorizableTextQuery(text=query, k_nearest_neighbors=top_k, fields="content_vector")],
        "filter": " and ".join(filters),
        "select": SELECT_FIELDS,
        "top": top_k,
    }
    if semantic_configuration:
        options.update({
            "query_type": "semantic",
            "semantic_configuration_name": semantic_configuration,
            "query_caption": "extractive",
        })

    evidence = tuple(_evidence(item) for item in client.search(**options))
    return EvidenceResult(status="ok", evidence=evidence) if evidence else EvidenceResult(status="no_evidence")


def knowledge_search_many(
    client,
    queries: Iterable[str],
    access_groups: Iterable[str],
    top_k: int = 8,
    semantic_configuration: str = "knowledge-semantic",
    source_path: Optional[str] = None,
    website_id: Optional[str] = None,
    generation: Optional[str] = None,
    workspace: Optional[str] = None,
) -> EvidenceResult:
    variants = list(dict.fromkeys(query.strip() for query in queries if query and query.strip()))
    if not 1 <= len(variants) <= 3:
        raise ValueError("one to three query variants are required")

    merged = {}
    warnings = []
    for query in variants:
        result = knowledge_search(
            client,
            query,
            access_groups,
            top_k=top_k,
            semantic_configuration=semantic_configuration,
            source_path=source_path,
            website_id=website_id,
            generation=generation,
            workspace=workspace,
        )
        warnings.extend(result.warnings)
        for item in result.evidence:
            merged.setdefault(item.chunk_id, item)

    if not merged:
        return EvidenceResult(status="no_evidence")

    return EvidenceResult(
        status="ok",
        evidence=tuple(merged.values()),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _evidence(item) -> Evidence:
    return Evidence(
        chunk_id=item["chunk_id"],
        content=item["content"],
        source=item.get("title") or item["source_path"].rsplit("/", 1)[-1],
        source_path=item["source_path"],
        source_url=item.get("source_url"),
        website_id=item.get("website_id"),
        page_id=item.get("page_id"),
        asset_id=item.get("asset_id"),
        generation=item.get("generation"),
        evidence_type=item.get("evidence_type"),
        document_version=item.get("document_version"),
        effective_date=item.get("effective_date"),
        page_number=None if item.get("source_path", "").lower().endswith(".docx") else item.get("page_number"),
        section_heading=item.get("section_heading"),
        slide_number=item.get("slide_number"),
        sheet_name=item.get("sheet_name"),
        cell_range=item.get("cell_range"),
        retrieval={
            "rrf_score": item.get("@search.score"),
            "reranker_score": item.get("@search.reranker_score"),
        },
    )
