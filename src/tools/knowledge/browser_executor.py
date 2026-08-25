from __future__ import annotations

import socket
from pathlib import Path

from artifact_capture import (
    BrowserArtifact,
    _field,
    _normalize_disclosures,
    map_crawl_result,
)
from asset_download import download_asset, select_relevant_images
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.browser_manager import BrowserManager
from web import validate_public_target


class WebGLSafeBrowserManager(BrowserManager):
    _INCOMPATIBLE_FLAGS = {"--disable-gpu", "--disable-gpu-compositing", "--disable-software-rasterizer"}

    def _build_browser_args(self) -> dict:
        result = super()._build_browser_args()
        result["args"] = [arg for arg in result["args"] if arg not in self._INCOMPATIBLE_FLAGS]
        return result


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

        media = _field(result, "media", {}) or {}
        media_images = media.get("images", [])
        for image in select_relevant_images(
            raw_html,
            str(_field(result, "url", url)),
            media_images,
        ):
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
