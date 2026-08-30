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
    source_text = "Tavily publishes a web research API."
    source_fingerprint = "sha256:" + __import__("hashlib").sha256(source_text.encode("utf-8")).hexdigest()
    return {
        "schema_version": 2,
        "dossier_id": "tavily-research-2026",
        "session_id": "telegram-research-session",
        "mode": mode,
        "question": "How should Hermes research the public web?",
        "scope": "Tavily-first public research",
        "created_at": "2026-08-27T00:00:00Z",
        "updated_at": "2026-08-27T00:00:00Z",
        "executive_answer": "Use Tavily with direct evidence verification.",
        "sources": [{
            "id": "s1", "title": "Tavily Research", "publisher": "Tavily",
            "retrieved_at": "2026-08-27T00:00:00Z",
            "url": "https://docs.tavily.com/documentation/api-reference/endpoint/research",
            "access_status": "read", "classification": "primary",
            "independence": "vendor", "acquisition_method": "tavily-extract",
            "freshness": "unknown", "fingerprint": source_fingerprint
        }],
        "evidence": [{
            "id": "e1", "source_id": "s1", "kind": "text",
            "value": source_text, "fingerprint": source_fingerprint
        }],
        "claims": [{
            "id": "c1", "type": "fact", "text": "Tavily publishes a web research API.",
            "evidence_ids": ["e1"], "counter_evidence_ids": [],
            "confidence": "high", "confidence_rationale": "Direct documentation."
        }],
        "contradictions": [], "gaps": [], "unknowns": [], "next_questions": [],
        "method": "Opened primary documentation.", "limitations": []
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
    for setup_text in (setup_cmd, setup_sh):
        assert "tavily-cli==0.1.6" in setup_text
        assert "agent-browser@0.35.1" in setup_text
        assert "browser-harness" not in setup_text
    assert "%LOCALAPPDATA%\\hermes\\.env" in readme
    assert "TAVILY_API_KEY" in readme
    assert "tvly login --api-key" not in readme
    policy_path = ROOT / "src/config/research_policy.json"
    assert policy_path.is_file(), f"missing policy: {policy_path}"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy == {
        "schema_version": 1,
        "quick": {"search_calls": 2, "extract_calls": 2, "extract_urls": 5, "browser_navigations": 1, "source_bytes": 2097152, "seconds": 120},
        "deep": {"research_runs": 1, "research_model": "mini", "status_polls": 60, "search_calls": 2, "extract_urls": 10, "browser_navigations": 3, "network_responses": 10, "source_bytes": 2097152, "seconds": 900},
        "site": {"map_calls": 1, "map_urls": 50, "crawl_calls": 1, "crawl_pages": 20, "crawl_depth": 2, "extract_calls": 2, "extract_urls": 5, "browser_navigations": 2, "network_requests": 50, "network_responses": 10, "response_bytes": 5242880, "seconds": 300},
        "temporary_bytes": 20971520,
        "pro_requires_confirmation": True
    }
    contract = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [SKILL, *sorted((SKILL.parent / "references").glob("*.md"))]
    ).lower()
    contract = re.sub(r"\s+", " ", contract)
    required_phrases = (
        "quick",
        "deep",
        "site intelligence",
        "tvly research",
        "capture-only",
        "official_domain",
        "grounded-citations",
        "deck-guizang-editorial",
        "built-in `powerpoint`",
        "built-in `xlsx`",
        "report.html",
        "16:9 structure",
        "keyboard navigation",
        "do not send `media`",
        "agent-browser wait --load networkidle",
        "agent-browser wait <selector>",
        "accessibility tree",
        "screenshot only as a fallback",
        "agent-browser tab list --json",
        "agent-browser tab close",
        "after each browser action",
        "agent-browser trace start",
        "agent-browser trace stop",
        "do not add another browser runtime",
        "--session <research-run-id>",
        "--pin-tab",
        "--allowed-domains",
        "--content-boundaries",
        "--max-output 50000",
        "do not use `--profile`",
        "`--state`, `--restore`, `--auto-connect`",
        "cloud browser provider",
    )
    for phrase in required_phrases:
        assert phrase in contract, f"missing phrase: {phrase}"
    for forbidden_token in (
        "camofox",
        "captcha solver",
        "browser use cloud",
        "posthog",
    ):
        assert forbidden_token not in contract, f"forbidden token found: {forbidden_token}"


def layer_2() -> None:
    store = load_module("research_store", SCRIPTS / "research_store.py")
    renderer = load_module("render_report", SCRIPTS / "render_report.py")
    good_deck = """<style>.slide{aspect-ratio:16/9}</style>
    <section class="slide"></section><section class="slide"></section>
    <div id="current-slide" aria-live="polite">1 / 2</div>
    <button id="prev" aria-label="Previous slide"></button>
    <button id="next" aria-label="Next slide"></button>
    <script>
    prev.addEventListener('click', () => show(-1));
    next.addEventListener('click', () => show(1));
    addEventListener('hashchange', () => show(location.hash));
    addEventListener('keydown', e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') show(1); });
    </script>"""
    renderer.validate_deck_html(good_deck)
    for missing in (
        good_deck.replace("    <button id=\"next\" aria-label=\"Next slide\"></button>\n", ""),
        good_deck.replace("aspect-ratio:16/9", "width:100%"),
        good_deck.replace("id=\"current-slide\" aria-live=\"polite\"", "id=\"not-an-indicator\""),
        good_deck.replace("addEventListener('hashchange'", "addEventListener('load'").replace("location.hash", "location.href"),
        good_deck.replace("prev.addEventListener('click'", "prev.addEventListener('change'").replace("next.addEventListener('click'", "next.addEventListener('change'"),
    ):
        expect_error(lambda value=missing: renderer.validate_deck_html(value), "deck")
    data = fixture()
    store.validate_dossier(data)
    renderer.validate_dossier(data)

    for bad_id in ("../x", "a/b", "C:x", ".", ""):
        expect_error(lambda value=bad_id: store.safe_id(value), "id")

    bad = fixture(); bad["sources"].append(dict(bad["sources"][0]))
    expect_error(lambda: store.validate_dossier(bad), "duplicate")
    bad = fixture(); bad["evidence"] = []
    expect_error(lambda: store.validate_dossier(bad), "missing evidence")
    bad = fixture(); bad["evidence"][0]["value"] = "changed"
    expect_error(lambda: store.validate_dossier(bad), "fingerprint")
    bad = fixture(); bad["claims"][0]["evidence_ids"] = ["missing"]
    expect_error(lambda: store.validate_dossier(bad), "missing")
    bad = fixture(); bad["sources"][0]["classification"] = "candidate"
    expect_error(lambda: store.validate_dossier(bad), "candidate")
    bad = fixture(); bad["sources"][0]["url"] = "javascript:alert(1)"
    expect_error(lambda: store.validate_dossier(bad), "http")
    bad = fixture("watch")
    expect_error(lambda: store.validate_dossier(bad), "watch_intent")

    store.validate_first_party_endpoint("thecoffeehouse.com", "https://order.thecoffeehouse.com/api/v5/menu")
    store.validate_first_party_endpoint("thecoffeehouse.com", "https://thecoffeehouse.com/order")
    expect_error(
        lambda: store.validate_first_party_endpoint("thecoffeehouse.com", "https://analytics.example.net/menu"),
        "first-party"
    )
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        temporary = store.write_temporary(workspace, data["session_id"], data)
        assert temporary.name == "dossier.json" and json.loads(temporary.read_text(encoding="utf-8"))["question"] == data["question"]
        report = renderer.write_report(temporary, temporary.with_name("report.html"))
        html = report.read_text(encoding="utf-8")
        assert data["question"] in html and "https://docs.tavily.com" in html
        assert "Tavily publishes a web research API." in html
        assert "tavily-extract" in html
        assert "unknown" in html
        assert "2026-08-27T00:00:00Z" in html
        assert "[e1]" in html
        assert not any(token in html.lower() for token in ("<script", "<iframe", "<form", "onerror="))

        # Test legacy v1 archive
        legacy_dir = workspace / ".runtime/research/saved/legacy-item"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        (legacy_dir / "dossier.json").write_text(json.dumps({"schema_version": 1, "dossier_id": "legacy-item"}), encoding="utf-8")
        archived = store.archive_legacy_dossiers(workspace)
        assert "legacy-item" in archived
        assert (workspace / ".runtime/research/legacy-v1/legacy-item/dossier.json").is_file()
        assert not legacy_dir.exists()

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

    escaped = fixture()
    escaped["question"] = "<script>alert(1)</script>"
    escaped_ev_text = "<img src=x onerror=alert(1)>"
    escaped_fp = store.fingerprint(store.normalize_text(escaped_ev_text))
    escaped["sources"][0]["fingerprint"] = escaped_fp
    escaped["evidence"][0]["value"] = escaped_ev_text
    escaped["evidence"][0]["fingerprint"] = escaped_fp
    escaped["claims"][0]["text"] = "Safety check: <script>alert(2)</script>"
    html = renderer.render_html(escaped)
    assert "&lt;script&gt;" in html and "<script" not in html.lower()
    assert "&lt;img" in html and "<img" not in html.lower()
    # Test Site-Intelligence Menu Projection Fixture
    fixture_path = ROOT / "tests/fixtures/research/coffee_house_menu_sanitized.json"
    expected_path = ROOT / "tests/fixtures/research/coffee_house_menu_expected.json"
    assert fixture_path.is_file() and expected_path.is_file()
    raw_fix = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    store.validate_first_party_endpoint(raw_fix["official_domain"], raw_fix["visible_page_url"])

    cats = []
    prods = []
    for c in raw_fix["response"]["menu"]:
        cats.append({"id": c["id"], "name": c["name"], "product_count": len(c.get("products", []))})
        for p in c.get("products", []):
            prod_entry = {
                "id": p["id"], "name": p["name"], "category_id": c["id"],
                "base_price": p["price"], "sizes": []
            }
            assert isinstance(p["price"], int) and p["price"] >= 0
            for opt in p.get("options", []):
                if opt.get("name") == "Size":
                    for s in opt.get("items", []):
                        assert isinstance(s["price"], int) and s["price"] >= 0
                        prod_entry["sizes"].append({"id": s["id"], "name": s["name"], "price": s["price"]})
                elif opt.get("name") == "Topping":
                    prod_entry.setdefault("toppings", [])
                    for t in opt.get("items", []):
                        assert isinstance(t["price"], int) and t["price"] >= 0
                        prod_entry["toppings"].append({"id": t["id"], "name": t["name"], "price": t["price"]})
            prods.append(prod_entry)

    assert len(cats) == expected["total_categories"]
    assert len(prods) == expected["total_products"]
    assert cats == expected["categories"]
    assert prods == expected["products"]

    # Ensure zero hardcoded site names, product IDs, or endpoints in production skill files
    skill_corpus = (
        SKILL.read_text(encoding="utf-8") + "\n" +
        (SCRIPTS / "research_store.py").read_text(encoding="utf-8") + "\n" +
        (SCRIPTS / "render_report.py").read_text(encoding="utf-8")
    ).lower()
    for forbidden_brand in ("api.thecoffeehouse.com", "699eafedbde92e0012ac3304", "pizza tomyum hải sản"):
        assert forbidden_brand.lower() not in skill_corpus, f"found hardcoded brand data in skill: {forbidden_brand}"
    # Test Tavily Fixtures & Candidate Source Safety Boundary
    tav_search_path = ROOT / "tests/fixtures/research/tavily_search_success.json"
    tav_res_path = ROOT / "tests/fixtures/research/tavily_research_candidate.json"
    tav_fail_path = ROOT / "tests/fixtures/research/tavily_failure.json"
    assert tav_search_path.is_file() and tav_res_path.is_file() and tav_fail_path.is_file()
    tav_search = json.loads(tav_search_path.read_text(encoding="utf-8"))
    tav_res = json.loads(tav_res_path.read_text(encoding="utf-8"))
    tav_fail = json.loads(tav_fail_path.read_text(encoding="utf-8"))
    assert tav_search["results"] and tav_res["status"] == "completed" and tav_fail["exit_code"] == 4

    candidate_fp = store.fingerprint(store.normalize_text(tav_res["output"]))
    cand_dossier = {
        "schema_version": 2,
        "dossier_id": "candidate-test-2026",
        "session_id": "telegram-cand-session",
        "mode": "temporary",
        "question": "Candidate synthesis test",
        "scope": "Candidate testing",
        "created_at": "2026-08-27T00:00:00Z",
        "updated_at": "2026-08-27T00:00:00Z",
        "executive_answer": "Candidate answer.",
        "sources": [{
            "id": "cand-s1", "title": "Tavily Candidate", "publisher": "Tavily Research",
            "retrieved_at": "2026-08-27T00:00:00Z", "url": "https://docs.tavily.com/documentation/api-reference/endpoint/research",
            "access_status": "read", "classification": "candidate",
            "independence": "vendor", "acquisition_method": "tavily-research",
            "freshness": "unknown", "fingerprint": candidate_fp
        }],
        "evidence": [{
            "id": "cand-e1", "source_id": "cand-s1", "kind": "text",
            "value": tav_res["output"], "fingerprint": candidate_fp
        }],
        "claims": [{
            "id": "c1", "type": "fact", "text": "Factual claim cannot use candidate evidence directly.",
            "evidence_ids": ["cand-e1"], "counter_evidence_ids": [],
            "confidence": "low", "confidence_rationale": "Unverified candidate synthesis."
        }],
        "contradictions": [], "gaps": [], "unknowns": [], "next_questions": [],
        "method": "Tavily research run.", "limitations": []
    }
    expect_error(lambda: store.validate_dossier(cand_dossier), "candidate")

    # Now add direct verified primary evidence to satisfy factual claim
    direct_text = "Verified primary documentation text."
    direct_fp = store.fingerprint(store.normalize_text(direct_text))
    cand_dossier["sources"].append({
        "id": "direct-s1", "title": "Official Direct Docs", "publisher": "Docs Publisher",
        "retrieved_at": "2026-08-27T00:00:00Z", "url": "https://docs.tavily.com/documentation/api-reference/endpoint/research",
        "access_status": "read", "classification": "primary",
        "independence": "vendor", "acquisition_method": "tavily-extract",
        "freshness": "unknown", "fingerprint": direct_fp
    })
    cand_dossier["evidence"].append({
        "id": "direct-e1", "source_id": "direct-s1", "kind": "text",
        "value": direct_text, "fingerprint": direct_fp
    })
    cand_dossier["claims"][0]["evidence_ids"] = ["direct-e1"]
    store.validate_dossier(cand_dossier)

    # Assert protocol failure taxonomy
    protocol_text = (SKILL.parent / "references/research-protocol.md").read_text(encoding="utf-8")
    for fail_tax in ("provider_unavailable", "rate_limited", "waf_interstitial", "authentication_required", "incomplete_extraction", "timeout", "unsafe_url"):
        assert fail_tax in protocol_text, f"missing failure taxonomy term: {fail_tax}"
    files = [SKILL, *sorted((SKILL.parent / "references").glob("*.md"))]
    contract = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
    for value in (".runtime/research/temporary", ".runtime/research/saved", ".runtime/deliverables/<workspace>/<name>", "dossier.json", "cleanup", "media:<absolute-path>"):
        assert value in contract, f"research contract missing {value}"


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
    print(f"research layer {args.layer}: pass")
