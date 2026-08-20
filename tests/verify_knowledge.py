from argparse import ArgumentParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "src/tools/knowledge"
RESOURCES = TOOLS / "azure_resources"
KNOWLEDGE_SKILL = ROOT / "src/skills/hermes-azure-rag/SKILL.md"


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
    except (KeyError, PermissionError, RuntimeError, ValueError) as error:
        assert contains.lower() in str(error).lower(), error
    else:
        raise AssertionError("expected error containing %r" % contains)


def layer_1():
    state = json.loads((ROOT / "feature-list.json").read_text(encoding="utf-8"))
    features = state["features"]
    assert all(item["state"] in {"not_started", "active", "blocked", "passing"} for item in features)
    assert [item["id"] for item in features if item["state"] == "active"] == ["H007"]
    assert next(item for item in features if item["id"] == "H006")["state"] == "blocked"
    required = ["clients.py", "contracts.py", "storage.py", "indexing.py", "retrieval.py", "provision.py", "knowledge.py", "policy.py", "web.py", "browser_executor.py", "crawl.py", "command_guard.py"]
    assert all((TOOLS / name).is_file() for name in required)
    assert all(not (TOOLS / name).exists() for name in ("authorization.py", "extract.py", "ingest.py", "manifest.py"))
    pyproject = (ROOT / "src/pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12,<3.13"' in pyproject
    assert '"crawl4ai>=0.9,<0.10"' in pyproject
    assert (ROOT / "src/uv.lock").is_file()
    assert (ROOT / "src/.python-version").read_text(encoding="utf-8").strip() == "3.12"
    assert not (ROOT / "src/requirements.txt").exists()
    knowledge_code = "\n".join((TOOLS / name).read_text(encoding="utf-8") for name in required)
    assert all(token not in knowledge_code.lower() for token in ("selenium", "firecrawl", "max_pages", "max_depth", "adaptivecrawler"))
    crawl_code = (TOOLS / "crawl.py").read_text(encoding="utf-8")
    assert "async with Crawl4AISession" in crawl_code
    assert crawl_code.count("time() >= session[\"deadline\"]") >= 2
    assert "range(3)" not in knowledge_code and "depth <= 2" not in knowledge_code
    policy_data = json.loads((ROOT / "src/config/website_policy.json").read_text(encoding="utf-8"))
    assert set(policy_data["crawl_budget"]) == {"wall_clock_seconds", "download_bytes", "content_asset_bytes", "screenshot_bytes", "consecutive_no_progress", "navigation_actions", "network_requests"}
    env = {line.split("=", 1)[0] for line in (ROOT / "src/.env.example").read_text(encoding="utf-8").splitlines() if "=" in line}
    assert env == {
        "AZURE_STORAGE_CONNECTION_STRING", "AZURE_STORAGE_LAYOUT_CONTAINER", "AZURE_STORAGE_TEXT_CONTAINER", "AZURE_STORAGE_IMAGE_CONTAINER",
        "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_ADMIN_KEY", "AZURE_SEARCH_QUERY_KEY", "AZURE_SEARCH_INDEX",
        "AZURE_SEARCH_LAYOUT_INDEXER", "AZURE_SEARCH_TEXT_INDEXER", "AZURE_SEARCH_IMAGE_INDEXER", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "AZURE_OPENAI_EMBEDDING_MODEL", "AZURE_OPENAI_EMBEDDING_DIMENSIONS",
        "AZURE_OPENAI_MULTIMODAL_DEPLOYMENT", "HERMES_IMAGE_INDEXER",
    }
    skill = KNOWLEDGE_SKILL.read_text(encoding="utf-8")
    required_skill = (
        "name: hermes-azure-rag", "shared `internal`", "no_evidence", "one bounded requery",
        "prompt injection", "effective_date", "Choose by data lifecycle", "current response",
        "remain available beyond", "follow-up questions about retained documents", "positive:",
        "negative:", "upload every original", "each relevant indexer once", "every intended source",
        "generic memory", "OCR", "Telegram cache presence", "MEDIA:<absolute-path>",
        "own line", "must not be wrapped", "verify that the file exists", "Do not claim delivery",
        "recreated diagram",
    )
    assert all(value in skill for value in required_skill)
    assert "uv run --frozen python tools/knowledge/knowledge.py" in skill
    assert "python tools/knowledge/knowledge.py" not in skill.replace("uv run --frozen python tools/knowledge/knowledge.py", "")
    assert all(value in skill for value in ("Azure evidence is the exclusive default source", "Do not call `web_extract`", "--query-variant", "generic uploaded Markdown file", "`source_url` for website evidence", "--generation"))
    assert all(value in skill for value in (
        'web-crawl "<public-url>" --scope <page|site>',
        "ambiguous scope",
        "must ask one scope clarification question",
        "never infer or assume `page` or `site`",
    ))
    assert skill.count("    - \"") == 6
    coordinator = (ROOT / "src/skills/hermes-project/SKILL.md").read_text(encoding="utf-8")
    agents = (ROOT / "src/AGENTS.md").read_text(encoding="utf-8")
    readme = (ROOT / "src/README.md").read_text(encoding="utf-8")
    assert all(value in coordinator for value in (
        "data lifecycle", "current-response", "outlive the current response",
        "Follow-ups stay with retained knowledge", "generic memory", "Telegram cache",
    ))
    assert "`hermes-azure-rag`" in coordinator
    assert all(value in coordinator for value in ("must use the `hermes-azure-rag` Website Lifecycle", "never convert the page into a generic Markdown upload", "retrieval gap does not change routing"))
    routing_contract = (
        "first matching route wins", "fresh session", "retained-knowledge candidate",
        "public website", "today", "current", "latest", "recently updated",
        "stable general knowledge", "transform the supplied input", "one bounded KB attempt",
        "explicit consent before web", "wrong facet", "document_version", "effective_date",
    )
    assert all(value in coordinator + skill for value in routing_contract)
    assert all(value in coordinator for value in (
        "How much does a typical project cost at Titan AI", "Latest Titan AI pricing today",
        "What is RAG?", "Translate this section",
    ))
    assert all(value in skill for value in (
        "original query", "at most two short query variants", "Merge evidence by `chunk_id`",
        "no_evidence", "requested facet", "ask whether the user wants live web research",
    ))
    assert "/hermes-azure-rag" in agents and "/hermes-azure-rag" in readme
    agents_routing = (
        "Source Routing", "first matching route wins", "fresh session",
        "retained-knowledge candidate", "today", "current", "latest", "recently updated",
        "stable general knowledge", "no silent web fallback",
        "How much does a typical project cost at Titan AI", "Latest Titan AI pricing today",
        "What is RAG?", "Translate this section",
        "no_evidence", "wrong facet", "explicit consent before web",
        "retrieval gap does not change routing",
    )
    assert all(value in agents for value in agents_routing), \
        [v for v in agents_routing if v not in agents]
    cli = (TOOLS / "knowledge.py").read_text(encoding="utf-8")
    assert 'add_argument("--access-group"' not in cli
    assert 'INTERNAL_GROUP = "internal"' in cli
    retrieval_text = (TOOLS / "retrieval.py").read_text(encoding="utf-8")
    storage_text = (TOOLS / "storage.py").read_text(encoding="utf-8")
    assert "workspace" in retrieval_text, "retrieval.py must support workspace filter"
    assert "workspace" in storage_text, "storage.py must include workspace in blob metadata"
    assert "--workspace" in cli, "knowledge.py CLI must support --workspace flag"
    definitions = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in RESOURCES.glob("*.json")}
    assert set(definitions) == {"index", "layout-datasource", "text-datasource", "image-datasource", "layout-skillset", "text-skillset", "image-skillset", "layout-indexer", "text-indexer", "image-indexer"}
    fields = {field["name"]: field for field in definitions["index"]["fields"]}
    assert fields["chunk_id"]["key"] and fields["content_vector"]["dimensions"] == "${AZURE_OPENAI_EMBEDDING_DIMENSIONS}"
    assert all(fields[name]["filterable"] for name in ("source_url", "website_id", "page_id", "asset_id", "generation", "content_hash", "evidence_type"))
    assert definitions["layout-skillset"]["skills"][0]["@odata.type"].endswith("DocumentIntelligenceLayoutSkill")
    assert definitions["text-skillset"]["skills"][0]["@odata.type"].endswith("SplitSkill")
    assert definitions["image-skillset"]["skills"][0]["@odata.type"].endswith("OcrSkill")
    assert definitions["image-indexer"]["parameters"]["configuration"]["imageAction"] == "generateNormalizedImages"
    assert definitions["layout-indexer"]["parameters"]["configuration"]["allowSkillsetToReadFileData"] is True
    for name in ("layout-datasource", "text-datasource", "image-datasource"):
        assert definitions[name]["dataDeletionDetectionPolicy"]["@odata.type"].endswith("NativeBlobSoftDeleteDeletionDetectionPolicy")
    for name in ("layout-skillset", "text-skillset"):
        mappings = {item["name"]: item["source"] for item in definitions[name]["indexProjections"]["selectors"][0]["mappings"]}
        assert mappings["source_path"] == "/document/source_path"
        assert mappings["access_groups"] == "/document/access_groups"
    for name in ("layout-indexer", "text-indexer"):
        mappings = {item["targetFieldName"]: item["sourceFieldName"] for item in definitions[name]["fieldMappings"]}
        assert mappings["source_path"] == "source_path"
        assert mappings["access_groups"] == "access_groups"
    text_mappings = {item["name"]: item["source"] for item in definitions["text-skillset"]["indexProjections"]["selectors"][0]["mappings"]}
    for name in ("source_url", "website_id", "page_id", "generation", "content_hash", "evidence_type"):
        assert text_mappings[name] == "/document/" + name
        assert any(item["targetFieldName"] == name for item in definitions["text-indexer"]["fieldMappings"])


def layer_2():
    contracts = load("contracts", "contracts.py")
    azure = load("azure_boundary", "clients.py")
    storage = load("storage", "storage.py")
    indexing = load("indexing", "indexing.py")
    retrieval = load("retrieval", "retrieval.py")
    provision = load("provision", "provision.py")
    policy_module = load("knowledge_policy", "policy.py")
    web = load("knowledge_web", "web.py")

    datasource_config = {
        "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",
        "AZURE_STORAGE_LAYOUT_CONTAINER": "layout",
    }
    datasource = provision._definition("layout-datasource", datasource_config)
    assert datasource.data_deletion_detection_policy.as_dict()["odata_type"].endswith("NativeBlobSoftDeleteDeletionDetectionPolicy")
    indexer = provision._definition("layout-indexer", {
        "AZURE_SEARCH_LAYOUT_INDEXER": "layout-indexer",
        "AZURE_SEARCH_INDEX": "chunks",
    })
    assert (indexer.name, indexer.data_source_name, indexer.target_index_name) == ("layout-indexer", "knowledge-layout-source", "chunks")
    image_datasource = provision._definition("image-datasource", {
        "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",
        "AZURE_STORAGE_IMAGE_CONTAINER": "images",
    })
    assert image_datasource.data_deletion_detection_policy.as_dict()["odata_type"].endswith("NativeBlobSoftDeleteDeletionDetectionPolicy")
    image_indexer = provision._definition("image-indexer", {"AZURE_SEARCH_IMAGE_INDEXER": "images", "AZURE_SEARCH_INDEX": "chunks"})
    assert image_indexer.parameters.configuration.image_action == "generateNormalizedImages"

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
        def __init__(self, blobs=()): self.calls = []; self.blobs = [type("Blob", (), {"name": name})() for name in blobs]
        def upload_blob(self, *args, **kwargs): self.calls.append((args, kwargs))
        def delete_blob(self, *args, **kwargs): self.calls.append((args, kwargs))
        def list_blobs(self, name_starts_with): return [blob for blob in self.blobs if blob.name.startswith(name_starts_with)]
    layout, text = Container(), Container()
    result = storage.upload_source(layout, text, "policy/rule.pdf", b"pdf", ["internal", "internal"])
    assert result["pipeline"] == "layout" and layout.calls[0][1]["metadata"]["access_groups"] == '["internal"]'
    result = storage.upload_source(layout, text, "notes/rule.md", b"text", ["internal"])
    assert result["pipeline"] == "text" and text.calls
    expect_error(lambda: storage.upload_source(layout, text, "x.pdf", b"x", []), "access group")

    public = lambda host, port, type=0: [(2, 1, 6, "", ("93.184.216.34", port))]
    assert web.normalize_public_url("HTTPS://Example.COM/a/?utm_source=x#part") == "https://example.com/a"
    assert web.validate_public_target("https://example.com", public) == "https://example.com/"
    private = lambda host, port, type=0: [(2, 1, 6, "", ("127.0.0.1", port))]
    mixed = lambda host, port, type=0: public(host, port, type) + private(host, port, type)
    expect_error(lambda: web.validate_public_target("https://example.com", mixed), "non-public")
    expect_error(lambda: web.normalize_public_url("https://u:p@example.com"), "credentials")

    policy = policy_module.load_website_policy(ROOT / "src/config/website_policy.json")
    expect_error(lambda: web.start_session("https://example.com", policy, "invalid", public, now=1000), "scope")
    page_session = web.start_session("https://example.com/#part", policy, "page", public, now=1000)
    site_session = web.start_session("https://example.com", policy, "site", public, now=1000)
    assert page_session["scope"] == "page" and page_session["root_url"] == "https://example.com/"
    assert site_session["scope"] == "site"
    session = page_session
    assert session["policy_digest"] and session["resource_ledger"]["download_bytes"] == 0
    assert session["resource_ledger"] == {"download_bytes": 0, "content_asset_bytes": 0, "screenshot_bytes": 0}
    with tempfile.TemporaryDirectory() as trusted:
        trusted_artifact = Path(trusted) / "root.artifact.json"; trusted_artifact.write_text("{}", encoding="utf-8")
        first = {
            "event_id": "root", "parent_event_id": None, "capability": "trusted_crawl4ai",
            "requested_url": "https://example.com", "final_url": "https://example.com/",
            "canonical_url": "https://example.com/", "started_at": 1001, "finished_at": 1002,
            "download_bytes": 100, "content_asset_bytes": 0, "screenshot_bytes": 0, "semantic_fingerprint": "root-v1",
            "links": ["https://example.com/a"], "artifacts": [{"path": str(trusted_artifact), "digest": "abc"}],
            "executor": "hermes-crawl4ai",
        }
        session = web.accept_observation(session, first, public)
        deep = dict(first, event_id="deep", parent_event_id="root", requested_url="https://example.com/a/b/c/d", final_url="https://example.com/a/b/c/d", canonical_url="https://example.com/a/b/c/d", semantic_fingerprint="deep-v1", started_at=1003, finished_at=1004)
        session = web.accept_observation(session, deep, public)
        assert len(session["events"]) == 2 and session["no_progress_count"] == 0
        replay = dict(deep)
        expect_error(lambda: web.accept_observation(session, replay, public), "duplicate")
        no_progress = dict(deep, event_id="same", parent_event_id="deep", started_at=1005, finished_at=1006)
        session = web.accept_observation(session, no_progress, public)
        assert session["no_progress_count"] == 1
        oversized = dict(deep, event_id="huge", parent_event_id="same", started_at=1007, finished_at=1008, download_bytes=policy.crawl_budget.download_bytes)
        expect_error(lambda: web.accept_observation(session, oversized, public), "budget")
        redirected = dict(deep, event_id="private", parent_event_id="same", final_url="http://localhost", canonical_url="http://localhost", started_at=1007, finished_at=1008)
        expect_error(lambda: web.accept_observation(session, redirected, private), "non-public")

    forged = dict(first, event_id="forged", parent_event_id="deep", started_at=1007, finished_at=1007, download_bytes=0, artifacts=[], executor="agent")
    expect_error(lambda: web.accept_observation(session, forged, public), "trusted artifact")
    report = web.finalize_session(session, "frontier_exhausted", unresolved_frontier=[])
    assert report["completion"]["stop_reason"] == "frontier_exhausted"
    expect_error(lambda: web.finalize_session(session, "frontier_exhausted", ["https://example.com/a"]), "unresolved frontier")
    with tempfile.TemporaryDirectory() as runtime:
        asset_path = Path(runtime) / "diagram.png"; asset_path.write_bytes(b"png")
        asset_record = {"asset_id": "asset-diagram", "source_url": "https://example.com/diagram.png",
                        "path": str(asset_path), "sha256": hashlib.sha256(b"png").hexdigest(),
                        "mime_type": "image/png", "byte_count": 3, "alt": "", "caption": "Diagram"}
        capture = {"session_id": session["session_id"], "generation": "g1", "pages": [{
            "event_id": "deep", "canonical_url": "https://example.com/a/b/c/d", "title": "Deep",
            "rendered_text": "Deep documentation", "semantic_structure": [], "assets": [asset_record], "media": [],
        }]}
        validated = web.validate_capture(report, capture, Path(runtime), public)
        assert validated["captures"][0]["page_id"] and validated["captures"][0]["content_hash"]
        assert validated["captures"][0]["assets"][0]["sha256"] == asset_record["sha256"]
        tampered = dict(capture, pages=[dict(capture["pages"][0], assets=[dict(asset_record, sha256="0" * 64)])])
        expect_error(lambda: web.validate_capture(report, tampered, Path(runtime), public), "digest")
        bad_capture = dict(capture, session_id="wrong")
        expect_error(lambda: web.validate_capture(report, bad_capture, Path(runtime), public), "bound")

    crawl_module = load("knowledge_crawl", "crawl.py")
    ranked = crawl_module.prioritize_links("https://example.com/engineering/article", [
        "https://example.com/jobs", "https://example.com/engineering/related", "https://example.com/legal",
    ])
    assert ranked == ["https://example.com/engineering/related", "https://example.com/jobs", "https://example.com/legal"]
    assert set(ranked) == {"https://example.com/jobs", "https://example.com/engineering/related", "https://example.com/legal"}

    command_guard = load("knowledge_command_guard", "command_guard.py")
    assert command_guard.block_reason("python tools/knowledge/knowledge.py search x")
    assert command_guard.block_reason("py tools/knowledge/knowledge.py search x")
    assert command_guard.block_reason("pip install crawl4ai")
    assert command_guard.block_reason("uv sync")
    assert command_guard.block_reason("uv run --frozen python tools/knowledge/knowledge.py search x --json")
    assert command_guard.block_reason("uv run --frozen python tools/knowledge/knowledge.py search x") is None
    assert command_guard.block_reason("git status") is None

    browser_executor = load("knowledge_browser_executor", "browser_executor.py")
    image_html = '''
    <div class="hero"><img alt="" width="2554" height="2554" src="https://cdn.example/hero.svg"></div>
    <figure><img width="2400" height="1666" src="https://cdn.example/coding.png"><figcaption>High-level flow of a coding agent</figcaption></figure>
    <img alt="Company logo" width="200" height="80" src="https://cdn.example/logo.png">
    '''
    selected_images = browser_executor.select_relevant_images(image_html, "https://example.com/article")
    assert selected_images == [{
        "source_url": "https://cdn.example/coding.png", "alt": "", "caption": "High-level flow of a coding agent",
        "width": 2400, "height": 1666,
    }]
    class ImageResponse:
        headers = {"Content-Type": "image/png", "Content-Length": "3"}
        def read(self, size=-1):
            if getattr(self, "done", False): return b""
            self.done = True; return b"png"
        def geturl(self): return "https://cdn.example/coding.png"
        def __enter__(self): return self
        def __exit__(self, *args): pass
    with tempfile.TemporaryDirectory() as directory:
        asset = browser_executor.download_asset(
            selected_images[0], Path(directory), public, 1024, opener=lambda request, timeout: ImageResponse()
        )
        assert asset["mime_type"] == "image/png" and asset["byte_count"] == 3
        assert asset["sha256"] == hashlib.sha256(b"png").hexdigest()
        assert Path(asset["path"]).is_absolute() and Path(asset["path"]).read_bytes() == b"png"
        assert asset["caption"] == "High-level flow of a coding agent" and asset["source_url"] == "https://cdn.example/coding.png"
    from crawl4ai import BrowserConfig
    manager = browser_executor.WebGLSafeBrowserManager(BrowserConfig(browser_type="chromium", headless=True))
    launch_args = manager._build_browser_args()["args"]
    assert not {"--disable-gpu", "--disable-gpu-compositing", "--disable-software-rasterizer"} & set(launch_args)
    assert "--no-sandbox" in launch_args
    class Markdown:
        fit_markdown = "# Main\nUseful policy"
        raw_markdown = "Menu\n# Main\nUseful policy\nFooter"
    class CrawlResult:
        success = True
        url = "https://example.com/docs"
        html = "<html><head><title>Docs</title><link rel='canonical' href='https://example.com/docs'></head><body><h1>Main</h1></body></html>"
        cleaned_html = html
        markdown = Markdown()
        links = {"internal": [{"href": "https://example.com/a"}], "external": [{"href": "https://other.example/x"}]}
        media = {"images": []}
        screenshot = "c2NyZWVuc2hvdA=="
        error_message = ""
    disclosures = [
        {"question": "What does it cost?", "answer": "Pricing depends on scope."},
        {"question": "Where are you based?", "answer": "Vietnam, Singapore, and the UK."},
    ]
    with tempfile.TemporaryDirectory() as directory:
        mapped_asset_path = Path(directory) / "diagram.png"; mapped_asset_path.write_bytes(b"png")
        mapped_asset = {"asset_id": "asset-diagram", "source_url": "https://example.com/diagram.png",
                        "path": str(mapped_asset_path.resolve()), "sha256": hashlib.sha256(b"png").hexdigest(),
                        "mime_type": "image/png", "byte_count": 3, "alt": "Diagram", "caption": "Flow",
                        "describe_image": False}
        mapped = browser_executor.map_crawl_result(
            CrawlResult(), "https://example.com/docs", "https://example.com", Path(directory), "evt-1", None, public,
            disclosures, [mapped_asset],
        )
        assert mapped.page["assets"] == [mapped_asset]
        assert mapped.page["rendered_text"].endswith("## Expanded disclosure content\n\n### What does it cost?\nPricing depends on scope.\n\n### Where are you based?\nVietnam, Singapore, and the UK.")
        assert mapped.page["coverage"]["disclosures"] == 2
        assert mapped.actionable_links == ("https://example.com/a",)
        assert mapped.event["executor"] == "hermes-crawl4ai"
        artifact = json.loads(Path(mapped.artifact_path).read_text(encoding="utf-8"))
        assert artifact["disclosures"] == disclosures and artifact["assets"] == [mapped_asset]
        assert Path(mapped.artifact_path).is_file() and mapped.event["artifacts"][0]["digest"]
        assert Path(mapped.page["capture_screenshot"]).read_bytes() == b"screenshot"
    with tempfile.TemporaryDirectory() as directory:
        expect_error(lambda: browser_executor.map_crawl_result(CrawlResult(), CrawlResult.url, "https://example.com", Path(directory), "evt-bad", None, public, [{"question": "", "answer": "x"}]), "disclosure")
    raw_result = CrawlResult(); raw_result.markdown = type("Markdown", (), {"fit_markdown": "", "raw_markdown": "Raw useful"})()
    with tempfile.TemporaryDirectory() as directory:
        assert browser_executor.map_crawl_result(raw_result, raw_result.url, "https://example.com", Path(directory), "evt-2", None, public).page["rendered_text"] == "Raw useful"
    child_result = CrawlResult(); child_result.screenshot = ""
    with tempfile.TemporaryDirectory() as directory:
        child = browser_executor.map_crawl_result(child_result, child_result.url, "https://example.com", Path(directory), "evt-child", "evt-1", public, require_screenshot=False)
        assert child.page["capture_screenshot"] is None and child.event["screenshot_bytes"] == 0
    failed = CrawlResult(); failed.success = False; failed.error_message = "navigation failed"
    with tempfile.TemporaryDirectory() as directory:
        expect_error(lambda: browser_executor.map_crawl_result(failed, failed.url, "https://example.com", Path(directory), "evt-3", None, public), "navigation failed")

    previous_capture = {"website_id": "site", "captures": [{"page_id": "same", "content_hash": "a"}, {"page_id": "changed", "content_hash": "old"}, {"page_id": "missing", "content_hash": "m"}]}
    current_capture = {"website_id": "site", "captures": [{"page_id": "same", "content_hash": "a"}, {"page_id": "changed", "content_hash": "new"}, {"page_id": "added", "content_hash": "n"}]}
    assert web.capture_diff(previous_capture, current_capture) == {"unchanged": ["same"], "changed": ["changed"], "added": ["added"], "missing": ["missing"]}
    expect_error(lambda: web.capture_diff(previous_capture, dict(current_capture, website_id="other")), "different websites")

    text_web, image_web = Container(("websites/site/generation/pages/page.md",)), Container(("websites/site/generation/assets/chart.png",))
    capture = {"website_id": "site", "page_id": "page", "generation": "generation", "canonical_url": "https://example.com/", "content_hash": "hash", "title": "Site — Việt", "rendered_text": "Rendered"}
    uploaded = storage.upload_website_capture(text_web, image_web, capture, ["internal"])
    assert uploaded["status"] == "uploaded" and text_web.calls[-1][1]["metadata"]["evidence_type"] == "page_text"
    assert text_web.calls[-1][1]["metadata"]["display_name"].isascii() and "Site — Việt".encode("utf-8") in text_web.calls[-1][0][1]
    with tempfile.TemporaryDirectory() as directory:
        image_path = Path(directory) / "chart.webp"; image_path.write_bytes(b"webp")
        capture_with_asset = dict(capture, assets=[{
            "asset_id": "chart", "path": str(image_path), "describe_image": False,
            "source_url": "https://cdn.example/chart.webp", "sha256": hashlib.sha256(b"webp").hexdigest(),
            "mime_type": "image/webp", "byte_count": 4, "alt": "Architecture", "caption": "Agent flow",
        }])
        asset_result = storage.upload_website_capture(text_web, image_web, capture_with_asset, ["internal"])
        assert asset_result["status"] == "uploaded" and image_web.calls[-1][0][1] == b"webp"
        asset_metadata = image_web.calls[-1][1]["metadata"]
        assert asset_metadata["asset_source_url"] == "https://cdn.example/chart.webp"
        assert asset_metadata["asset_sha256"] == hashlib.sha256(b"webp").hexdigest()
        assert asset_metadata["asset_mime_type"] == "image/webp" and asset_metadata["asset_caption"] == "Agent%20flow"
    deleted = storage.delete_website_capture(text_web, image_web, "site", "generation")
    assert len(deleted["deleted"]) == 2

    # Verify HERMES_IMAGE_INDEXER=false mode: image_container=None must skip asset uploads silently
    with tempfile.TemporaryDirectory() as directory:
        image_path_disabled = Path(directory) / "chart.webp"; image_path_disabled.write_bytes(b"webp")
        capture_disabled = dict(capture, assets=[{
            "asset_id": "chart", "path": str(image_path_disabled), "describe_image": False,
            "source_url": "https://cdn.example/chart.webp", "sha256": hashlib.sha256(b"webp").hexdigest(),
            "mime_type": "image/webp", "byte_count": 4, "alt": "Architecture", "caption": "Agent flow",
        }])
        text_disabled = Container(); image_calls_before = len(image_web.calls)
        disabled_result = storage.upload_website_capture(text_disabled, None, capture_disabled, ["internal"])
        assert disabled_result["status"] == "uploaded", "image disabled upload must succeed"
        assert disabled_result["failures"] == [], "no failures expected when image indexer is disabled"
        assert len(image_web.calls) == image_calls_before, "image_container.upload_blob must NOT be called when image_container=None"
        assert len(disabled_result["uploaded"]) == 1, "only the page text blob should be uploaded"

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

    class ReadinessSearch:
        def __init__(self, rows): self.rows = rows; self.filters = []
        def search(self, **options): self.filters.append(options["filter"]); return self.rows
    expected_pages = [
        {"page_id": "p1", "canonical_url": "https://example.com/a", "assets": [{"asset_id": "chart"}]},
        {"page_id": "p2", "canonical_url": "https://example.com/b", "assets": []},
    ]
    ready_search = ReadinessSearch([
        {"page_id": "p1", "source_url": "https://example.com/a", "asset_id": None, "evidence_type": "page_text"},
        {"page_id": "p2", "source_url": "https://example.com/b", "asset_id": None, "evidence_type": "page_text"},
        {"page_id": "p1", "source_url": "https://example.com/a", "asset_id": "chart", "evidence_type": "image_ocr"},
    ])
    ready = indexing.website_readiness(ready_search, "site", "g1", expected_pages)
    assert ready["status"] == "ready" and ready["ready_url_count"] == 2 and ready["ready_asset_count"] == 1
    assert "website_id eq 'site'" in ready_search.filters[0] and "generation eq 'g1'" in ready_search.filters[0]
    partial = indexing.website_readiness(ReadinessSearch([{"page_id": "p1", "source_url": "https://example.com/a", "asset_id": None, "evidence_type": "page_text"}]), "site", "g1", expected_pages)
    assert partial["status"] == "partial" and partial["missing_page_ids"] == ["p2"] and partial["missing_asset_ids"] == ["chart"]
    assert indexing.website_absent(ReadinessSearch([]), "site") is True
    assert indexing.website_absent(ReadinessSearch([{"page_id": "p1"}]), "site") is False

    class Search:
        def __init__(self): self.options = None
        def search(self, **options):
            self.options = options
            return [{
                "chunk_id": "1", "content": "Refund in 14 days", "title": "Policy", "source_path": "policy/rule.pdf",
                "page_number": 2, "@search.score": 0.03,
            }]
    search = Search()
    result = retrieval.knowledge_search(search, "refund", ["team'o", "sales"], 4)
    assert result.has_valid_evidence and result.evidence[0].page_number == 2
    assert search.options["search_text"] == "refund" and search.options["vector_queries"]
    assert "team''o" in search.options["filter"] and "sales" in search.options["filter"]
    scoped = Search(); retrieval.knowledge_search(scoped, "projects", ["internal"], source_path="titanai_services.md")
    assert "source_path eq 'titanai_services.md'" in scoped.options["filter"]
    site_scoped = Search(); retrieval.knowledge_search(site_scoped, "projects", ["internal"], website_id="site-1", generation="gen-current")
    assert "website_id eq 'site-1'" in site_scoped.options["filter"] and "generation eq 'gen-current'" in site_scoped.options["filter"]
    expect_error(lambda: retrieval.knowledge_search(Search(), "projects", ["internal"], generation="orphan"), "valid source scope")
    expect_error(lambda: retrieval.knowledge_search(Search(), "projects", ["internal"], source_path="x.md", website_id="site"), "at most one")
    empty = Search(); empty.search = lambda **options: []
    assert retrieval.knowledge_search(empty, "unknown", ["internal"]).status == "no_evidence"

    website_search = Search()
    def image_search(**options):
        website_search.options = options
        return [{"chunk_id": "web-1", "content": "High-level coding agent flow", "title": "Diagram", "source_path": "websites/site/g1/assets/chart.webp", "source_url": "https://titanai.space/", "website_id": "site", "page_id": "p1", "asset_id": "chart", "generation": "g1", "evidence_type": "image_ocr", "@search.score": 0.1}]
    website_search.search = image_search
    website_result = retrieval.knowledge_search(website_search, "coding agent flow", ["internal"])
    item = website_result.evidence[0]
    assert (item.source_url, item.website_id, item.page_id, item.asset_id, item.generation, item.evidence_type) == ("https://titanai.space/", "site", "p1", "chart", "g1", "image_ocr")
    assert item.source_path == "websites/site/g1/assets/chart.webp" and "asset_id" in website_search.options["select"]

    class MultiSearch:
        def __init__(self): self.queries = []; self.filters = []
        def search(self, **options):
            self.queries.append(options["search_text"]); self.filters.append(options["filter"])
            return [{"chunk_id": "same", "content": "Project details", "title": "Titan", "source_path": "notes/titan.md", "@search.score": 0.1}]
    multi = MultiSearch()
    merged = retrieval.knowledge_search_many(multi, ["các dự án", "Real Projects", "case studies"], ["internal"], source_path="titanai_services.md")
    assert multi.queries == ["các dự án", "Real Projects", "case studies"] and len(merged.evidence) == 1
    assert all("source_path eq 'titanai_services.md'" in query_filter for query_filter in multi.filters)
    expect_error(lambda: retrieval.knowledge_search_many(multi, ["1", "2", "3", "4"], ["internal"]), "one to three")

    with tempfile.TemporaryDirectory() as directory:
        script = Path(directory) / "unicode_output.py"
        script.write_text(
            "import json\nprint(json.dumps({'status':'ok','content':'Chính sách hoàn tiền'}, ensure_ascii=False))\n",
            encoding="utf-8",
        )
        environment = dict(os.environ, PYTHONIOENCODING="utf-8")
        completed = subprocess.run(
            [sys.executable, str(script)], capture_output=True, env=environment, check=True
        )
        decoded = json.loads(completed.stdout.decode("utf-8"))
        assert decoded["content"] == "Chính sách hoàn tiền"


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    (layer_1 if args.layer == 1 else layer_2)()
    print("knowledge layer %d: pass" % args.layer)
