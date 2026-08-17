from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
import json


@dataclass(frozen=True)
class CrawlBudget:
    wall_clock_seconds: int
    download_bytes: int
    content_asset_bytes: int
    screenshot_bytes: int
    consecutive_no_progress: int
    navigation_actions: int
    network_requests: int


@dataclass(frozen=True)
class WebsitePolicy:
    schema_version: int
    crawl_budget: CrawlBudget
    capture: Mapping[str, str]

    def as_dict(self) -> dict:
        return {"schema_version": self.schema_version, "crawl_budget": self.crawl_budget.__dict__.copy(), "capture": dict(self.capture)}


def load_website_policy(path: Path) -> WebsitePolicy:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or set(value) != {"schema_version", "crawl_budget", "capture"}:
        raise ValueError("website policy contains unknown or missing keys")
    if value["schema_version"] != 1: raise ValueError("unsupported website policy schema")
    budget = value["crawl_budget"]
    required = {"wall_clock_seconds", "download_bytes", "content_asset_bytes", "screenshot_bytes", "consecutive_no_progress", "navigation_actions", "network_requests"}
    if not isinstance(budget, dict) or set(budget) != required: raise ValueError("crawl budget contains unknown or missing keys")
    if any(type(budget[key]) is not int or budget[key] <= 0 for key in required): raise ValueError("crawl budget values must be positive integers")
    capture = value["capture"]
    if not isinstance(capture, dict) or capture != {"images": "relevant", "canvas": "when_semantic", "media": "metadata_only"}: raise ValueError("unsupported capture policy")
    return WebsitePolicy(1, CrawlBudget(**budget), MappingProxyType(dict(capture)))
