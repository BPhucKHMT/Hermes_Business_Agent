from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from typing import Callable

from tools.social_browser.contracts import (
    AccessibleNode,
    BrowserObservation,
    PreparationResult,
    RunStatus,
    SocialActionManifest,
    normalize_text,
)
from tools.social_browser.gateway import SafeBrowserGateway


_FACEBOOK_HOME = "https://www.facebook.com/"
_TEXTBOX_SELECTOR = "[role='textbox'][contenteditable='true']"
_FILE_SELECTOR = "input[type='file']"
_AUDIENCE_LABELS = {
    "friends": {"friends", "bạn bè"},
    "only-me": {"only me", "chỉ mình tôi"},
}
_CHALLENGE_CODES = {"captcha", "checkpoint", "suspicious_login"}
_LOGIN_CODES = {"login", "mfa", "password", "account_chooser"}


class FacebookPersonalAdapter:
    def __init__(self, gateway: SafeBrowserGateway):
        self.gateway = gateway
        self.platform_policy = gateway.policy.platform("facebook-personal")

    def prepare(self, manifest: SocialActionManifest) -> PreparationResult:
        if manifest.platform != "facebook-personal":
            raise ValueError("platform_not_supported")
        self._validate_manifest(manifest)
        self.gateway.open(_FACEBOOK_HOME)
        observation = self._observe_until(self._has_composer)
        if observation is None:
            return self._result(manifest, RunStatus.FAILED_UI_DRIFT, "composer_missing")
        blocker = self._blocker_status(observation)
        if blocker is not None:
            return self._result(manifest, blocker, "browser_challenge")
        if not self._account_matches(observation, manifest.account_label):
            return self._result(
                manifest,
                RunStatus.BLOCKED_ACCOUNT_MISMATCH,
                "account_mismatch",
            )
        composer = self._find_composer(observation)
        if composer is None:
            return self._result(manifest, RunStatus.FAILED_UI_DRIFT, "composer_missing")
        self.gateway.activate_control(composer)
        self.gateway.fill(_TEXTBOX_SELECTOR, manifest.text)
        if manifest.media:
            self.gateway.upload(_FILE_SELECTOR, Path(manifest.media[0].path))
        preview = self._observe_until(
            lambda value: self._preview_matches(value, manifest)
        )
        if preview is None:
            return self._result(manifest, RunStatus.FAILED_UI_DRIFT, "preview_mismatch")
        self.gateway.handoff()
        return self._result(manifest, RunStatus.READY_FOR_HUMAN)

    def verify_published(self, manifest: SocialActionManifest) -> str | None:
        observation = self.gateway.observe()
        if not self._account_matches(observation, manifest.account_label):
            return None
        if not manifest.text:
            return None
        page_text = " ".join(
            normalize_text(node.name) for node in observation.accessible_nodes
        ).casefold()
        if manifest.text.casefold() not in page_text:
            return None
        for node in observation.accessible_nodes:
            parsed = urlsplit(node.url)
            if "/posts/" not in parsed.path.casefold():
                continue
            try:
                self.gateway.policy.require_origin("facebook-personal", node.url)
            except PermissionError:
                continue
            if not parsed.netloc or not parsed.path.rstrip("/").split("/")[-1]:
                continue
            return node.url
        return None

    def _validate_manifest(self, manifest: SocialActionManifest) -> None:
        manifest.verify_media()
        self.gateway.policy.require_audience(
            "facebook-personal", manifest.audience
        )
        if len(manifest.text) > self.platform_policy.max_text_chars:
            raise ValueError("text_too_long")
        if len(manifest.media) > self.platform_policy.max_media_files:
            raise ValueError("too_many_media_files")

    def _observe_until(
        self, predicate: Callable[[BrowserObservation], bool]
    ) -> BrowserObservation | None:
        for _ in range(2):
            observation = self.gateway.observe()
            if predicate(observation):
                return observation
        return None

    def _has_composer(self, observation: BrowserObservation) -> bool:
        return self._find_composer(observation) is not None

    def _find_composer(
        self, observation: BrowserObservation
    ) -> AccessibleNode | None:
        for node in observation.accessible_nodes:
            if normalize_text(node.name).casefold() in self.platform_policy.composer_names:
                return node
        return None

    def _account_matches(
        self, observation: BrowserObservation, account_label: str
    ) -> bool:
        expected = normalize_text(account_label).casefold()
        if normalize_text(observation.account_label).casefold() == expected:
            return True
        return any(
            normalize_text(node.name).casefold() == expected
            for node in observation.accessible_nodes
        )

    def _preview_matches(
        self, observation: BrowserObservation, manifest: SocialActionManifest
    ) -> bool:
        names = {
            normalize_text(node.name).casefold()
            for node in observation.accessible_nodes
        }
        text_found = manifest.text.casefold() in names
        audience_found = bool(names & _AUDIENCE_LABELS[manifest.audience])
        return text_found and audience_found

    def _blocker_status(
        self, observation: BrowserObservation
    ) -> RunStatus | None:
        codes = {code.casefold() for code in observation.warning_codes}
        if codes & _CHALLENGE_CODES:
            return RunStatus.BLOCKED_CHALLENGE
        if codes & _LOGIN_CODES:
            return RunStatus.BLOCKED_LOGIN
        return None

    def _result(
        self,
        manifest: SocialActionManifest,
        status: RunStatus,
        failure_code: str | None = None,
    ) -> PreparationResult:
        text_digest = hashlib.sha256(manifest.text.encode("utf-8")).hexdigest()
        return PreparationResult(
            run_id=manifest.run_id,
            status=status,
            account_label=manifest.account_label,
            text_digest=text_digest,
            media_digests=tuple(item.sha256 for item in manifest.media),
            audience=manifest.audience,
            evidence_paths=(),
            failure_code=failure_code,
        )
