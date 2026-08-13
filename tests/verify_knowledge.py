from argparse import ArgumentParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "src/tools/knowledge"
RESOURCES = TOOLS / "azure_resources"


def load(name, filename):
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    spec = spec_from_file_location(name, TOOLS / filename)
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def expect_error(call, contains):
    try:
        call()
    except (KeyError, RuntimeError, ValueError) as error:
        assert contains.lower() in str(error).lower(), error
    else:
        raise AssertionError("expected error containing %r" % contains)


def layer_1():
    state = json.loads((ROOT / "feature-list.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in state["features"] if item["state"] == "active"] == ["H006"]
    required = ["clients.py", "contracts.py", "storage.py", "indexing.py", "retrieval.py", "provision.py", "knowledge.py"]
    assert all((TOOLS / name).is_file() for name in required)
    assert all(not (TOOLS / name).exists() for name in ("extract.py", "ingest.py", "manifest.py"))
    assert (ROOT / "src/requirements.txt").read_text(encoding="utf-8").splitlines() == [
        "azure-search-documents>=11.6,<12", "azure-storage-blob>=12.25,<13"
    ]
    env = {line.split("=", 1)[0] for line in (ROOT / "src/.env.example").read_text(encoding="utf-8").splitlines() if "=" in line}
    assert env == {
        "AZURE_STORAGE_CONNECTION_STRING", "AZURE_STORAGE_LAYOUT_CONTAINER", "AZURE_STORAGE_TEXT_CONTAINER",
        "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_ADMIN_KEY", "AZURE_SEARCH_QUERY_KEY", "AZURE_SEARCH_INDEX",
        "AZURE_SEARCH_LAYOUT_INDEXER", "AZURE_SEARCH_TEXT_INDEXER", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "AZURE_OPENAI_EMBEDDING_MODEL", "AZURE_OPENAI_EMBEDDING_DIMENSIONS",
    }
    definitions = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in RESOURCES.glob("*.json")}
    assert set(definitions) == {"index", "layout-datasource", "text-datasource", "layout-skillset", "text-skillset", "layout-indexer", "text-indexer"}
    fields = {field["name"]: field for field in definitions["index"]["fields"]}
    assert fields["chunk_id"]["key"] and fields["content_vector"]["dimensions"] == "${AZURE_OPENAI_EMBEDDING_DIMENSIONS}"
    assert definitions["layout-skillset"]["skills"][0]["@odata.type"].endswith("DocumentIntelligenceLayoutSkill")
    assert definitions["text-skillset"]["skills"][0]["@odata.type"].endswith("SplitSkill")
    assert definitions["layout-indexer"]["parameters"]["configuration"]["allowSkillsetToReadFileData"] is True
    for name in ("layout-datasource", "text-datasource"):
        assert definitions[name]["dataDeletionDetectionPolicy"]["@odata.type"].endswith("NativeBlobSoftDeleteDeletionDetectionPolicy")


def layer_2():
    contracts = load("contracts", "contracts.py")
    azure = load("azure_boundary", "clients.py")
    storage = load("storage", "storage.py")
    indexing = load("indexing", "indexing.py")
    retrieval = load("retrieval", "retrieval.py")

    for bad in ("", "../x.pdf", "C:/x.pdf", "x.exe", "a\\x.pdf"):
        expect_error(lambda value=bad: contracts.validate_source_path(value), "source" if bad != "x.exe" else "unsupported")

    config = {name: "value" for name in azure.REQUIRED_ENV}
    config.update({
        "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",
        "AZURE_SEARCH_ENDPOINT": "https://search.example",
        "AZURE_OPENAI_ENDPOINT": "https://openai.example",
        "AZURE_OPENAI_EMBEDDING_DIMENSIONS": "1536",
    })
    assert azure.load_config(config)["AZURE_SEARCH_ENDPOINT"] == "https://search.example"
    missing = dict(config); del missing["AZURE_SEARCH_QUERY_KEY"]
    expect_error(lambda: azure.load_config(missing), "AZURE_SEARCH_QUERY_KEY")

    class Container:
        def __init__(self): self.calls = []
        def upload_blob(self, *args, **kwargs): self.calls.append((args, kwargs))
        def delete_blob(self, *args, **kwargs): self.calls.append((args, kwargs))
    layout, text = Container(), Container()
    result = storage.upload_source(layout, text, "policy/rule.pdf", b"pdf", ["internal", "internal"])
    assert result["pipeline"] == "layout" and layout.calls[0][1]["metadata"]["access_groups"] == "internal"
    result = storage.upload_source(layout, text, "notes/rule.md", b"text", ["internal"])
    assert result["pipeline"] == "text" and text.calls
    expect_error(lambda: storage.upload_source(layout, text, "x.pdf", b"x", []), "access group")

    class Indexer:
        def __init__(self): self.runs = []
        def run_indexer(self, name): self.runs.append(name)
        def get_indexer_status(self, name):
            status = type("Status", (), {"value": "success"})()
            return type("Result", (), {"last_result": type("Last", (), {"status": status})()})()
    indexer = Indexer()
    assert indexing.run_indexers(indexer, ["layout", "text"])["status"] == "submitted"
    assert indexer.runs == ["layout", "text"]
    assert indexing.indexer_status(indexer, "layout")["status"] == "success"

    class Search:
        def __init__(self): self.options = None
        def search(self, **options):
            self.options = options
            return [{
                "chunk_id": "1", "content": "Refund in 14 days", "title": "Policy", "source_path": "policy/rule.pdf",
                "page_number": 2, "@search.score": 0.03,
            }]
    search = Search()
    result = retrieval.knowledge_search(search, "refund", "team'o", 4)
    assert result.has_valid_evidence and result.evidence[0].page_number == 2
    assert search.options["search_text"] == "refund" and search.options["vector_queries"]
    assert "team''o" in search.options["filter"]
    empty = Search(); empty.search = lambda **options: []
    assert retrieval.knowledge_search(empty, "unknown", "internal").status == "no_evidence"


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
    print("knowledge layer %d: pass" % args.layer)
