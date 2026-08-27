from argparse import ArgumentParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import re
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src/skills/research/SKILL.md"
SCRIPTS = SKILL.parent / "scripts"


def load_module(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixture(mode="temporary"):
    return {
        "schema_version": 1,
        "dossier_id": "firecrawl-2026",
        "session_id": "telegram-7275339077",
        "mode": mode,
        "question": "Có nên dùng Firecrawl?",
        "scope": "Giá và rủi ro năm 2026",
        "created_at": "2026-08-12T03:00:00Z",
        "updated_at": "2026-08-12T03:00:00Z",
        "executive_answer": "Phù hợp cho AI research nếu kiểm soát chi phí.",
        "sources": [{
            "id": "s1", "title": "Firecrawl Pricing", "publisher": "Firecrawl",
            "retrieved_at": "2026-08-12T03:00:00Z", "url": "https://firecrawl.dev/pricing",
            "access_status": "read", "classification": "primary",
            "independence": "vendor", "fingerprint": "sha256:abc"
        }],
        "claims": [{
            "id": "c1", "type": "fact", "text": "Firecrawl publishes usage plans.",
            "evidence_ids": ["s1"], "counter_evidence_ids": [],
            "confidence": "high", "confidence_rationale": "Direct vendor pricing page."
        }],
        "contradictions": [], "gaps": ["Enterprise negotiated price"],
        "method": "Opened primary pricing page.", "limitations": ["Prices may change."],
    }


def expect_error(fn, text):
    try:
        fn()
    except (ValueError, FileNotFoundError) as exc:
        assert text.lower() in str(exc).lower(), exc
    else:
        raise AssertionError(f"expected error containing {text!r}")


def layer_1() -> None:
    required = (
        SKILL,
        SKILL.parent / "references/research-protocol.md",
        SKILL.parent / "references/source-quality.md",
        SKILL.parent / "references/report-contract.md",
        SCRIPTS / "research_store.py",
        SCRIPTS / "render_report.py",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing research files: {missing}"
    raw = SKILL.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "invalid frontmatter start"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    assert re.match(r"---\n(.*?)\n---\n(.+)", text, re.DOTALL), "frontmatter/body missing"
    assert "src/.runtime/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    forbidden = ("C:/Hermes agent", "DECISIONS.md", "PROGRESS.md", "feature-list.json", ".hermes.md")
    assert not any(value in text for value in forbidden), "runtime boundary leak"
    setup_cmd = (ROOT / "src/setup.cmd").read_text(encoding="utf-8")
    setup_sh = (ROOT / "src/setup.sh").read_text(encoding="utf-8")
    readme = (ROOT / "src/README.md").read_text(encoding="utf-8")
    for text in (setup_cmd, setup_sh):
        assert "tavily-cli==0.1.6" in text
        assert "agent-browser@0.35.1" in text
    assert "%LOCALAPPDATA%\\hermes\\.env" in readme
    assert "TAVILY_API_KEY" in readme
    assert "tvly login --api-key" not in readme


def layer_2() -> None:
    store = load_module("research_store", SCRIPTS / "research_store.py")
    renderer = load_module("render_report", SCRIPTS / "render_report.py")
    data = fixture()
    store.validate_dossier(data)
    renderer.validate_dossier(data)

    for bad_id in ("../x", "a/b", "C:x", ".", ""):
        expect_error(lambda value=bad_id: store.safe_id(value), "id")

    bad = fixture(); bad["sources"].append(dict(bad["sources"][0]))
    expect_error(lambda: store.validate_dossier(bad), "duplicate")
    bad = fixture(); bad["claims"][0]["evidence_ids"] = ["missing"]
    expect_error(lambda: store.validate_dossier(bad), "missing")
    bad = fixture(); bad["sources"][0]["url"] = "javascript:alert(1)"
    expect_error(lambda: store.validate_dossier(bad), "http")
    bad = fixture("watch")
    expect_error(lambda: store.validate_dossier(bad), "watch_intent")

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        temporary = store.write_temporary(workspace, data["session_id"], data)
        assert temporary.name == "dossier.json" and json.loads(temporary.read_text(encoding="utf-8"))["question"] == data["question"]
        report = renderer.write_report(temporary, temporary.with_name("report.html"))
        html = report.read_text(encoding="utf-8")
        assert data["question"] in html and "https://firecrawl.dev/pricing" in html
        assert not any(token in html.lower() for token in ("<script", "<iframe", "<form", "onerror="))

        saved = store.save_dossier(workspace, data["dossier_id"], data, "save")
        assert store.load_dossier(workspace, data["dossier_id"])["mode"] == "save"
        store.delete_dossier(workspace, data["dossier_id"])
        expect_error(lambda: store.load_dossier(workspace, data["dossier_id"]), "not found")

        old_dir = temporary.parent
        old = time.time() - 7200
        old_dir.touch()
        import os
        os.utime(old_dir, (old, old))
        removed = store.cleanup_temporary(workspace, 3600)
        assert data["session_id"] in removed and not old_dir.exists()

    escaped = fixture(); escaped["question"] = "<script>alert(1)</script>"
    html = renderer.render_html(escaped)
    assert "&lt;script&gt;" in html and "<script" not in html.lower()

    files = [SKILL, *sorted((SKILL.parent / "references").glob("*.md"))]
    contract = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
    for value in (".runtime/research/temporary", ".runtime/research/saved", "dossier.json", "cleanup", "media:<absolute-path>"):
        assert value in contract, f"research contract missing {value}"


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
    print(f"research layer {args.layer}: pass")
