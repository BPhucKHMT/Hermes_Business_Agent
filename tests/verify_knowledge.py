from argparse import ArgumentParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "src/tools/knowledge"


def load_module(name: str, path: Path):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def expect_error(fn, text: str) -> None:
    try:
        fn()
    except (KeyError, ValueError) as exc:
        assert text.lower() in str(exc).lower(), exc
    else:
        raise AssertionError(f"expected error containing {text!r}")


def layer_1() -> None:
    state = json.loads((ROOT / "feature-list.json").read_text(encoding="utf-8"))
    assert state["allowed_states"] == ["not_started", "active", "blocked", "passing"]
    active = [feature["id"] for feature in state["features"] if feature["state"] == "active"]
    assert active == ["H006"], active
    h006 = next(feature for feature in state["features"] if feature["id"] == "H006")
    assert h006["depends_on"] == ["H005"] and h006["evidence"] is None
    assert h006["verification"] == {
        "layer_1": "python tests/verify_knowledge.py --layer 1",
        "layer_2": "python tests/verify_knowledge.py --layer 2",
        "layer_3": "fresh Hermes process, approved Azure resources, and approved Telegram chat complete docs/plan/Rag.md End-to-End Release Checklist A-G",
    }
    required = (TOOLS / "contracts.py", TOOLS / "manifest.py")
    assert all(path.is_file() for path in required), "knowledge contract files missing"
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "src/.runtime/" in ignored and ".env" in ignored
    tracked_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts and ".worktrees" not in path.parts)
    secret_patterns = (r"(?i)api[_-]?key\s*=\s*['\"][^'\"]+", r"(?i)authorization:\s*bearer\s+\S+", r"DefaultEndpointsProtocol=https;AccountName=")
    assert not any(re.search(pattern, tracked_text) for pattern in secret_patterns), "possible committed secret"


def layer_2() -> None:
    contracts = load_module("contracts", TOOLS / "contracts.py")
    manifest_module = load_module("manifest", TOOLS / "manifest.py")

    for bad in ("", "../x.pdf", "a/../x.pdf", "C:/x.pdf", "x.exe", "a\\x.pdf"):
        expect_error(lambda value=bad: contracts.validate_source_path(value), "source" if bad != "x.exe" else "unsupported")

    evidence = contracts.Evidence(
        chunk_id="doc:g1:c1", content="Refunds require approval.", source="Policy.pdf",
        source_path="policies/Policy.pdf", page_number=2,
    )
    result = contracts.EvidenceResult(status="ok", evidence=(evidence,))
    payload = result.to_dict()
    assert payload["has_valid_evidence"] is True and "answer" not in payload
    expect_error(lambda: contracts.EvidenceResult(status="ok"), "contain evidence")
    expect_error(lambda: contracts.EvidenceResult(status="invalid"), "status")
    expect_error(lambda: contracts.Evidence(chunk_id="x", content="x", source="Doc.docx", source_path="Doc.docx", page_number=1), "DOCX")

    content_v1 = b"price=79"
    content_v2 = b"price=99"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "manifest.json"
        manifest = manifest_module.Manifest.load(path)
        first = manifest.begin_generation("pricing/Pricing.pdf", manifest.content_hash(content_v1), ["c2", "c1"])
        assert first.active_generation is None and first.pending_generation == 1
        expect_error(lambda: manifest.activate(first.document_id, ["c1"]), "chunk set")
        assert manifest.active_snapshot() == {}
        activated = manifest.activate(first.document_id, ["c1", "c2"])
        assert activated.active_generation == 1 and manifest.active_snapshot() == {first.document_id: 1}
        assert manifest.begin_generation("pricing/Pricing.pdf", manifest.content_hash(content_v1), ["c1", "c2"]) is None

        second = manifest.begin_generation("pricing/Pricing.pdf", manifest.content_hash(content_v2), ["n1", "n2"])
        assert second.active_generation == 1 and second.pending_generation == 2
        assert manifest.active_snapshot() == {first.document_id: 1}
        failed = manifest.fail(second.document_id, "search_timeout")
        assert failed.state == "indexed" and failed.active_generation == 1
        assert manifest.active_snapshot() == {first.document_id: 1}

        retry = manifest.begin_generation("pricing/Pricing.pdf", manifest.content_hash(content_v2), ["n1", "n2"])
        assert retry.pending_generation == 2
        activated_v2 = manifest.activate(retry.document_id, (item for item in ["n1", "n2"]))
        assert activated_v2.active_generation == 2 and activated_v2.previous_generation == 1
        loaded = manifest_module.Manifest.load(path)
        assert loaded.active_snapshot() == {first.document_id: 2}
        assert not path.with_name(f".{path.name}.tmp").exists()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
    print(f"knowledge layer {args.layer}: pass")
