from typing import Iterable, Mapping


def run_indexers(client, indexer_names: Iterable[str]) -> Mapping[str, object]:
    names = [name.strip() for name in indexer_names if name and name.strip()]
    if not names:
        raise ValueError("at least one indexer name is required")
    for name in names:
        client.run_indexer(name)
    return {"status": "submitted", "indexers": names}


def indexer_status(client, indexer_name: str) -> Mapping[str, object]:
    if not indexer_name.strip():
        raise ValueError("indexer name is required")
    latest = client.get_indexer_status(indexer_name).last_result
    if latest is None:
        return {"status": "never_run", "error": None}
    value = str(getattr(latest.status, "value", latest.status)).lower()
    return {"status": value, "error": "indexer_failed" if value in {"error", "transientfailure"} else None}
