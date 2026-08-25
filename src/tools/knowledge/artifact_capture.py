from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import time
from urllib.parse import urlsplit

from web import validate_public_target


@dataclass(frozen=True)
class BrowserArtifact:
    event: dict
    page: dict
    actionable_links: tuple[str, ...]
    artifact_path: Path


def _field(value, name: str, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _markdown(result) -> tuple[str, str]:
    value = _field(result, "markdown")
    fit = str(_field(value, "fit_markdown", "") or "").strip()
    raw = str(_field(value, "raw_markdown", value if isinstance(value, str) else "") or "").strip()
    selected = fit or raw
    if not selected:
        raise ValueError("Crawl4AI returned no meaningful content")
    return selected, "fit_markdown" if fit else "raw_markdown"


def _normalize_disclosures(value) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("disclosure evidence must be a list")
    result = []
    for item in value:
        question = " ".join(str(_field(item, "question", "")).split())
        answer = " ".join(str(_field(item, "answer", "")).split())
        if not question or not answer or len(question) > 500 or len(answer) > 20000:
            raise ValueError("disclosure evidence is malformed")
        pair = {"question": question, "answer": answer}
        if pair not in result:
            result.append(pair)
    return result


def _canonical_url(html: str, final: str, origin: str, validator) -> str:
    match = re.search(
        r"<link\b[^>]*\brel=['\"]canonical['\"][^>]*\bhref=['\"]([^'\"]+)",
        html,
        re.I,
    )
    canonical = validator(match.group(1) if match else final)
    if urlsplit(canonical).netloc != urlsplit(origin).netloc:
        raise ValueError("canonical URL left approved origin")
    return canonical


def _internal_links(result, origin: str, validator) -> list[str]:
    links = []
    for item in (_field(result, "links", {}) or {}).get("internal", []):
        try:
            checked = validator(_field(item, "href", ""))
        except ValueError:
            continue
        if urlsplit(checked).netloc == urlsplit(origin).netloc and checked not in links:
            links.append(checked)
    return links


def _screenshot(result, required: bool) -> bytes:
    value = str(_field(result, "screenshot", "") or "")
    content = base64.b64decode(value, validate=True) if value else b""
    if required and not content:
        raise ValueError("Crawl4AI returned no screenshot")
    return content


def map_crawl_result(
    result,
    requested_url: str,
    origin: str,
    artifact_dir: Path,
    event_id: str,
    parent_event_id: str | None = None,
    resolver=None,
    disclosures=None,
    assets=None,
    require_screenshot: bool = True,
) -> BrowserArtifact:
    if not _field(result, "success", False):
        raise RuntimeError(str(_field(result, "error_message", "Crawl4AI crawl failed")))

    def validator(value: str) -> str:
        return validate_public_target(value, resolver) if resolver else validate_public_target(value)

    requested = validator(requested_url)
    final = validator(str(_field(result, "url", requested)))
    if urlsplit(final).netloc != urlsplit(origin).netloc:
        raise ValueError("browser left approved origin")

    html = str(_field(result, "cleaned_html", "") or _field(result, "html", ""))
    if not html:
        raise ValueError("Crawl4AI returned no HTML")

    rendered, markdown_kind = _markdown(result)
    disclosure_pairs = _normalize_disclosures(disclosures)
    asset_records = list(assets or [])
    if disclosure_pairs:
        expanded = "\n\n".join(f"### {item['question']}\n{item['answer']}" for item in disclosure_pairs)
        rendered += "\n\n## Expanded disclosure content\n\n" + expanded

    canonical = _canonical_url(html, final, origin, validator)
    links = _internal_links(result, origin, validator)
    screenshot_bytes = _screenshot(result, require_screenshot)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshot = artifact_dir / f"{event_id}.png" if screenshot_bytes else None
    markdown_path = artifact_dir / f"{event_id}.md"
    html_path = artifact_dir / f"{event_id}.html"

    if screenshot:
        screenshot.write_bytes(screenshot_bytes)
    markdown_path.write_text(rendered, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    asset_manifest = json.dumps(asset_records, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = sha256(html.encode("utf-8") + rendered.encode("utf-8") + screenshot_bytes + asset_manifest).hexdigest()
    artifact = {
        "schema_version": 1,
        "executor": "hermes-crawl4ai",
        "digest": digest,
        "html": str(html_path.resolve()),
        "markdown": str(markdown_path.resolve()),
        "markdown_kind": markdown_kind,
        "screenshot": str(screenshot.resolve()) if screenshot else None,
        "disclosures": disclosure_pairs,
        "assets": asset_records,
    }
    artifact_path = artifact_dir / f"{event_id}.artifact.json"
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    started = time()
    finished = max(time(), started + 0.000001)
    semantic = " ".join(rendered.split()).encode("utf-8")
    event = {
        "event_id": event_id,
        "parent_event_id": parent_event_id,
        "capability": "trusted_crawl4ai",
        "requested_url": requested,
        "final_url": final,
        "canonical_url": canonical,
        "started_at": started,
        "finished_at": finished,
        "download_bytes": len(html.encode("utf-8")) + len(rendered.encode("utf-8")),
        "content_asset_bytes": sum(int(item.get("byte_count", 0)) for item in asset_records),
        "screenshot_bytes": len(screenshot_bytes),
        "semantic_fingerprint": sha256(semantic).hexdigest(),
        "links": links,
        "artifacts": [{"path": str(artifact_path.resolve()), "digest": digest}],
        "executor": "hermes-crawl4ai",
    }

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    page = {
        "event_id": event_id,
        "canonical_url": canonical,
        "title": re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else canonical,
        "rendered_text": rendered,
        "semantic_structure": [],
        "minimal_html": html,
        "assets": asset_records,
        "media": (_field(result, "media", {}) or {}).get("images", []),
        "capture_screenshot": str(screenshot.resolve()) if screenshot else None,
        "coverage": {"crawler": "crawl4ai", "disclosures": len(disclosure_pairs)},
    }
    return BrowserArtifact(event, page, tuple(links), artifact_path)
