from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Callable

from tools.social_browser.contracts import (
    PreparationResult,
    RunStatus,
    SocialActionManifest,
    create_manifest,
)
from tools.social_browser.facebook import FacebookPersonalAdapter
from tools.social_browser.gateway import SafeBrowserGateway
from tools.social_browser.policy import SocialBrowserPolicy
from tools.social_browser.store import SocialBrowserStore, StoredRun


@dataclass(frozen=True)
class PrepareFacebookRequest:
    account_label: str
    text: str
    media_paths: tuple[Path, ...]
    audience: str


class SocialBrowserService:
    def __init__(
        self,
        policy: SocialBrowserPolicy,
        store: SocialBrowserStore,
        gateway_factory: Callable[[str], SafeBrowserGateway],
        adapter_factory: Callable[
            [SafeBrowserGateway], FacebookPersonalAdapter
        ] = FacebookPersonalAdapter,
    ):
        self.policy = policy
        self.store = store
        self.gateway_factory = gateway_factory
        self.adapter_factory = adapter_factory

    def prepare(self, request: PrepareFacebookRequest) -> PreparationResult:
        manifest = create_manifest(
            "facebook-personal",
            request.account_label,
            request.text,
            list(request.media_paths),
            request.audience,
        )
        self.policy.require_audience(manifest.platform, manifest.audience)
        stored = self._expire_if_needed(self.store.create_or_get(manifest))
        if stored.status is not RunStatus.REQUESTED:
            return self._stored_result(stored)
        self.store.transition(
            stored.run_id, RunStatus.REQUESTED, RunStatus.PREPARING
        )
        try:
            gateway = self.gateway_factory(stored.run_id)
            adapter = self.adapter_factory(gateway)
            result = adapter.prepare(stored.manifest)
        except (PermissionError, RuntimeError, ValueError) as exc:
            self.store.transition(
                stored.run_id,
                RunStatus.PREPARING,
                RunStatus.FAILED_UI_DRIFT,
                failure_code=type(exc).__name__,
            )
            raise
        transitioned = self.store.transition(
            stored.run_id,
            RunStatus.PREPARING,
            result.status,
            failure_code=result.failure_code,
        )
        return self._stored_result(transitioned, result.evidence_paths)

    def status(self, run_id: str) -> PreparationResult:
        return self._stored_result(self._expire_if_needed(self.store.get_run(run_id)))


    def verify_after_human(self, run_id: str) -> PreparationResult:
        stored = self._expire_if_needed(self.store.get_run(run_id))
        if stored.status is RunStatus.PUBLISHED:
            return self._stored_result(stored)
        if stored.status is not RunStatus.READY_FOR_HUMAN:
            raise ValueError("run_not_ready_for_verification")
        gateway = self.gateway_factory(stored.run_id)
        post_id = self.adapter_factory(gateway).verify_published(stored.manifest)
        if post_id is None:
            return self._stored_result(stored)
        published = self.store.transition(
            stored.run_id,
            RunStatus.READY_FOR_HUMAN,
            RunStatus.PUBLISHED,
            verified_post_id=post_id,
        )
        return self._stored_result(published)

    def _expire_if_needed(self, stored: StoredRun) -> StoredRun:
        if stored.status not in {RunStatus.REQUESTED, RunStatus.READY_FOR_HUMAN}:
            return stored
        try:
            expires_at = datetime.fromisoformat(
                stored.manifest.expires_at.replace("Z", "+00:00")
            )
        except ValueError:
            return stored
        if datetime.now(timezone.utc) < expires_at:
            return stored
        return self.store.transition(
            stored.run_id, stored.status, RunStatus.EXPIRED
        )

    def _stored_result(
        self, stored: StoredRun, evidence_paths: tuple[str, ...] = ()
    ) -> PreparationResult:
        manifest = stored.manifest
        text_digest = hashlib.sha256(manifest.text.encode("utf-8")).hexdigest()
        return PreparationResult(
            run_id=stored.run_id,
            status=stored.status,
            account_label=manifest.account_label,
            text_digest=text_digest,
            media_digests=tuple(item.sha256 for item in manifest.media),
            audience=manifest.audience,
            evidence_paths=evidence_paths,
            verified_post_id=stored.verified_post_id,
            failure_code=stored.failure_code,
        )
