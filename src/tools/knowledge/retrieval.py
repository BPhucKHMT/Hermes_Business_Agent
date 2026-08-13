from typing import Optional

from azure.search.documents.models import VectorizableTextQuery

from contracts import Evidence, EvidenceResult

SELECT_FIELDS = [
    "chunk_id", "content", "title", "source_path", "document_version",
    "effective_date", "page_number", "section_heading", "slide_number",
    "sheet_name", "cell_range",
]


def knowledge_search(client, query: str, access_group: str, top_k: int = 8, semantic_configuration: Optional[str] = None) -> EvidenceResult:
    query = query.strip()
    group = access_group.strip()
    if not query or not group or top_k < 1:
        raise ValueError("query, access group, and positive top_k are required")
    escaped_group = group.replace("'", "''")
    options = {
        "search_text": query,
        "vector_queries": [VectorizableTextQuery(text=query, k_nearest_neighbors=top_k, fields="content_vector")],
        "filter": "access_groups/any(g: g eq '%s')" % escaped_group,
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


def _evidence(item) -> Evidence:
    return Evidence(
        chunk_id=item["chunk_id"],
        content=item["content"],
        source=item.get("title") or item["source_path"].rsplit("/", 1)[-1],
        source_path=item["source_path"],
        document_version=item.get("document_version"),
        effective_date=item.get("effective_date"),
        page_number=item.get("page_number"),
        section_heading=item.get("section_heading"),
        slide_number=item.get("slide_number"),
        sheet_name=item.get("sheet_name"),
        cell_range=item.get("cell_range"),
        retrieval={
            "rrf_score": item.get("@search.score"),
            "reranker_score": item.get("@search.reranker_score"),
        },
    )
