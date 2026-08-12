from dataclasses import asdict
from typing import Callable, Iterable, List, Mapping, Optional

from extract import Chunk, Unit, chunk_units, extract
from manifest import Manifest

Embedder = Callable[[List[str]], List[List[float]]]
Uploader = Callable[[List[Mapping[str, object]]], None]
Verifier = Callable[[str, int], Iterable[str]]
Deleter = Callable[[str, int], None]


class IngestionService:
    def __init__(self, manifest: Manifest, embed: Embedder, upload: Uploader, verify: Verifier, delete: Deleter):
        self.manifest = manifest
        self.embed = embed
        self.upload = upload
        self.verify = verify
        self.delete = delete

    def ingest(self, source_path: str, content: bytes, access_groups: Iterable[str], ocr: Optional[Callable[[bytes], Iterable[Unit]]] = None) -> Mapping[str, object]:
        groups = sorted(set(group.strip() for group in access_groups if group and group.strip()))
        if not groups:
            raise ValueError("at least one access group is required")
        document_id = self.manifest.document_id(source_path)
        current = self.manifest.records.get(document_id)
        generation = (current.active_generation or 0) + 1 if current else 1
        units = extract(source_path, content, ocr)
        chunks = chunk_units(document_id, generation, units)
        if not chunks:
            raise ValueError("document produced no searchable chunks")
        expected = [chunk.chunk_id for chunk in chunks]
        record = self.manifest.begin_generation(source_path, self.manifest.content_hash(content), expected)
        if record is None:
            return {"status": "unchanged", "document_id": document_id, "generation": current.active_generation, "chunks": 0}
        old_generation = record.active_generation
        try:
            vectors = self.embed([chunk.content for chunk in chunks])
            if len(vectors) != len(chunks) or any(not vector for vector in vectors):
                raise ValueError("embedding count does not match chunk count")
            documents = [self._search_document(document_id, generation, chunk, vector, groups, source_path) for chunk, vector in zip(chunks, vectors)]
            self.upload(documents)
            indexed = list(self.verify(document_id, generation))
            self.manifest.activate(document_id, indexed)
            if old_generation is not None:
                self.delete(document_id, old_generation)
            return {"status": "indexed", "document_id": document_id, "generation": generation, "chunks": len(chunks)}
        except Exception:
            self.manifest.fail(document_id, "ingestion_failed")
            raise

    @staticmethod
    def _search_document(document_id: str, generation: int, chunk: Chunk, vector: List[float], groups: List[str], source_path: str) -> Mapping[str, object]:
        data = asdict(chunk)
        data.update({
            "@search.action": "upload", "document_id": document_id, "generation": generation,
            "content_vector": vector, "source_path": source_path, "access_groups": groups,
        })
        return data
