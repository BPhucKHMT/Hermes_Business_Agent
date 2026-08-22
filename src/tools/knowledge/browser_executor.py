from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from time import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.browser_manager import BrowserManager
from web import validate_public_target


class WebGLSafeBrowserManager(BrowserManager):
    _INCOMPATIBLE_FLAGS = {"--disable-gpu", "--disable-gpu-compositing", "--disable-software-rasterizer"}

    def _build_browser_args(self) -> dict:
        result = super()._build_browser_args()
        result["args"] = [arg for arg in result["args"] if arg not in self._INCOMPATIBLE_FLAGS]
        return result


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


class _ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.figure_depth = 0
        self.current = []
        self.images = []
        self.caption = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "figure":
            self.figure_depth += 1
            self.current = []
        elif tag == "img":
            item = {
                "source_url": values.get("src", ""),
                "alt": values.get("alt", ""),
                "caption": "",
                "width": int(values.get("width", 0) or 0),
                "height": int(values.get("height", 0) or 0),
                "in_figure": self.figure_depth > 0,
            }
            self.images.append(item)
            if self.figure_depth:
                self.current.append(item)
        elif tag == "figcaption" and self.figure_depth:
            self.caption = True

    def handle_data(self, data):
        if self.caption:
            text = " ".join(data.split())
            for item in self.current:
                item["caption"] = " ".join(filter(None, (item["caption"], text)))

    def handle_endtag(self, tag):
        if tag == "figcaption":
            self.caption = False
        elif tag == "figure":
            self.figure_depth = max(0, self.figure_depth - 1)
            self.current = []


def select_relevant_images(html: str, page_url: str) -> list[dict]:
    parser = _ImageParser()
    parser.feed(html)
    selected = []
    for item in parser.images:
        source = urljoin(page_url, item.pop("source_url"))
        label = " ".join((item["alt"] + " " + item["caption"]).lower().split())
        decorative = any(word in label for word in ("avatar", "icon", "logo", "sprite"))
        meaningful = item.pop("in_figure") and bool(item["caption"]) or bool(item["alt"] and not decorative)
        if meaningful and not decorative and item["width"] >= 100 and item["height"] >= 100:
            selected.append({"source_url": source, **item})
    return selected


def download_asset(
    image: dict,
    artifact_dir: Path,
    resolver,
    byte_limit: int,
    opener=urlopen,
) -> dict:
    source = validate_public_target(str(image.get("source_url", "")), resolver)
    request = Request(source, headers={"User-Agent": "Hermes-Crawl4AI/1.0"})
    with opener(request, timeout=30) as response:
        final = validate_public_target(response.geturl(), resolver)
        mime = str(response.headers.get("Content-Type", "")).split(";", 1)[0].lower()
        suffixes = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/svg+xml": ".svg",
            "image/webp": ".webp",
        }
        if mime not in suffixes:
            raise ValueError("website asset has unsupported image MIME type")
        declared = int(response.headers.get("Content-Length", 0) or 0)
        if declared > byte_limit:
            raise ValueError("website asset exceeds byte budget")
        chunks, total = [], 0
        while True:
            chunk = response.read(min(65536, byte_limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > byte_limit:
                raise ValueError("website asset exceeds byte budget")
            chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise ValueError("website asset is empty")
    digest = sha256(content).hexdigest()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = (artifact_dir / (f"asset-{digest[:20]}{suffixes[mime]}")).resolve()
    path.write_bytes(content)
    return {
        "asset_id": f"asset-{digest[:20]}",
        "source_url": final,
        "path": str(path),
        "sha256": digest,
        "mime_type": mime,
        "byte_count": total,
        "alt": str(image.get("alt", "")),
        "caption": str(image.get("caption", "")),
        "describe_image": False,
    }


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

    canonical_match = re.search(r"<link\b[^>]*\brel=['\"]canonical['\"][^>]*\bhref=['\"]([^'\"]+)", html, re.I)
    canonical = validator(canonical_match.group(1) if canonical_match else final)
    if urlsplit(canonical).netloc != urlsplit(origin).netloc:
        raise ValueError("canonical URL left approved origin")

    links = []
    for item in (_field(result, "links", {}) or {}).get("internal", []):
        href = _field(item, "href", "")
        try:
            checked = validator(href)
            if urlsplit(checked).netloc == urlsplit(origin).netloc and checked not in links:
                links.append(checked)
        except ValueError:
            continue

    screenshot_value = str(_field(result, "screenshot", "") or "")
    screenshot_bytes = base64.b64decode(screenshot_value, validate=True) if screenshot_value else b""
    if require_screenshot and not screenshot_bytes:
        raise ValueError("Crawl4AI returned no screenshot")

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


class Crawl4AISession:
    def __init__(self, session: dict, artifact_dir: Path, resolver=None, allow_private: bool = False):
        if allow_private:
            raise ValueError("private browser targets are unsupported")
        self.session, self.artifact_dir, self.resolver = session, artifact_dir, resolver
        self.crawler = None

    async def __aenter__(self):
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig
        except ImportError as error:
            raise RuntimeError("Crawl4AI is required; run operator setup") from error

        browser_config = BrowserConfig(browser_type="chromium", headless=True)
        strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_config)
        strategy.browser_manager = WebGLSafeBrowserManager(browser_config=browser_config, logger=strategy.logger)
        self.disclosures = []

        async def capture_disclosures(page, context, config, **kwargs):
            pairs = []
            controls = page.locator('button[type="button"][aria-controls][aria-expanded]')
            for index in range(await controls.count()):
                control = controls.nth(index)
                if await control.is_disabled():
                    continue
                if await control.get_attribute("aria-expanded") != "true":
                    await control.click()
                    await page.wait_for_timeout(250)
                question = (await control.inner_text()).strip()
                control_id = await control.get_attribute("aria-controls")
                answer = (
                    await page.evaluate(
                        '(id) => { const element = id ? document.getElementById(id) : null; return (element?.innerText || element?.textContent || "").trim(); }',
                        control_id,
                    )
                    if control_id
                    else ""
                )
                if question and answer:
                    pairs.append({"question": question, "answer": answer})
            self.disclosures = _normalize_disclosures(pairs)
            return page

        strategy.set_hook("before_retrieve_html", capture_disclosures)
        self.crawler = AsyncWebCrawler(crawler_strategy=strategy, config=browser_config)
        await self.crawler.start()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if self.crawler is not None:
            await self.crawler.close()

    async def capture(self, url: str, event_id: str, parent_event_id: str | None = None) -> BrowserArtifact:
        from crawl4ai import CacheMode, CrawlerRunConfig
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

        require_screenshot = parent_event_id is None
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            scan_full_page=require_screenshot,
            screenshot=require_screenshot,
            exclude_external_images=True,
            process_iframes=False,
            remove_overlay_elements=True,
            markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilter()),
        )
        self.disclosures = []
        result = await self.crawler.arun(url=url, config=config)
        raw_html = str(_field(result, "html", "") or _field(result, "cleaned_html", ""))
        resolver = self.resolver
        validate = (lambda value: validate_public_target(value, resolver)) if resolver else validate_public_target

        assets = []
        remaining = self.session["policy"]["crawl_budget"]["content_asset_bytes"]
        seen = set()

        for image in select_relevant_images(raw_html, str(_field(result, "url", url))):
            if image["source_url"] in seen:
                continue
            seen.add(image["source_url"])
            checked = validate(image["source_url"])
            item = (
                download_asset(dict(image, source_url=checked), self.artifact_dir, resolver, remaining)
                if resolver
                else download_asset(dict(image, source_url=checked), self.artifact_dir, socket.getaddrinfo, remaining)
            )
            assets.append(item)
            remaining -= item["byte_count"]

        return map_crawl_result(
            result,
            url,
            self.session["root_origin"],
            self.artifact_dir,
            event_id,
            parent_event_id,
            self.resolver,
            self.disclosures,
            assets,
            require_screenshot,
        )
