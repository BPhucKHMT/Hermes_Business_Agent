from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlsplit

from tools.social_browser.contracts import normalize_text


_ROOT_KEYS = {
    "schema_version",
    "browser_harness_version",
    "telemetry",
    "cloud",
    "max_screenshot_bytes",
    "evidence_ttl_seconds",
    "platforms",
}
_PLATFORM_KEYS = {
    "origins",
    "audiences",
    "allowed_operations",
    "terminal_names",
    "composer_names",
    "max_text_chars",
    "max_media_files",
}


@dataclass(frozen=True)
class PlatformPolicy:
    origins: tuple[str, ...]
    audiences: frozenset[str]
    allowed_operations: frozenset[str]
    terminal_names: frozenset[str]
    composer_names: frozenset[str]
    max_text_chars: int
    max_media_files: int


@dataclass(frozen=True)
class SocialBrowserPolicy:
    browser_harness_version: str
    telemetry: bool
    cloud: bool
    max_screenshot_bytes: int
    evidence_ttl_seconds: int
    platforms: dict[str, PlatformPolicy]

    def platform(self, name: str) -> PlatformPolicy:
        try:
            return self.platforms[name]
        except KeyError as exc:
            raise ValueError("platform_not_supported") from exc

    def allows_operation(self, platform: str, operation: str) -> bool:
        return normalize_text(operation).casefold() in self.platform(
            platform
        ).allowed_operations

    def require_origin(self, platform: str, url: str) -> None:
        parts = urlsplit(url)
        origin = f"{parts.scheme.lower()}://{(parts.hostname or '').lower()}"
        if parts.scheme.lower() != "https" or origin not in self.platform(platform).origins:
            raise PermissionError("origin_not_allowed")

    def require_audience(self, platform: str, audience: str) -> None:
        if audience.casefold() not in self.platform(platform).audiences:
            raise PermissionError("audience_not_allowed")

    def is_terminal_name(self, platform: str, name: str) -> bool:
        normalized = normalize_text(name).casefold()
        return normalized in self.platform(platform).terminal_names


def _require_exact_keys(data: dict, expected: set[str], label: str) -> None:
    if set(data) != expected:
        raise ValueError(f"invalid_{label}_keys")


def _platform_policy(data: dict) -> PlatformPolicy:
    _require_exact_keys(data, _PLATFORM_KEYS, "platform")
    origins = tuple(data["origins"])
    allowed = frozenset(data["allowed_operations"])
    terminal = frozenset(normalize_text(name).casefold() for name in data["terminal_names"])
    if not origins or not terminal:
        raise ValueError("platform_policy_incomplete")
    if allowed & terminal:
        raise ValueError("terminal_operation_allowed")
    return PlatformPolicy(
        origins=origins,
        audiences=frozenset(data["audiences"]),
        allowed_operations=allowed,
        terminal_names=terminal,
        composer_names=frozenset(
            normalize_text(name).casefold() for name in data["composer_names"]
        ),
        max_text_chars=int(data["max_text_chars"]),
        max_media_files=int(data["max_media_files"]),
    )


def load_policy(path: Path) -> SocialBrowserPolicy:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_social_browser_policy") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid_social_browser_policy")
    _require_exact_keys(data, _ROOT_KEYS, "root")
    if data["schema_version"] != 1:
        raise ValueError("unsupported_policy_version")
    if data["telemetry"] or data["cloud"]:
        raise ValueError("external_browser_service_forbidden")
    platforms = {
        name: _platform_policy(value)
        for name, value in data["platforms"].items()
    }
    return SocialBrowserPolicy(
        browser_harness_version=str(data["browser_harness_version"]),
        telemetry=False,
        cloud=False,
        max_screenshot_bytes=int(data["max_screenshot_bytes"]),
        evidence_ttl_seconds=int(data["evidence_ttl_seconds"]),
        platforms=platforms,
    )
