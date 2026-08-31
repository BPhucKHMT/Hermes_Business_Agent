from pathlib import Path

from tools.social_browser.contracts import PreparationResult, RunStatus
from tools.social_browser.policy import load_policy
from tools.social_browser.service import PrepareFacebookRequest, SocialBrowserService
from tools.social_browser.store import SocialBrowserStore


ROOT = Path(__file__).resolve().parents[2]


class FakeAdapter:
    def __init__(self) -> None:
        self.prepare_count = 0
        self.published_id = None

    def prepare(self, manifest):
        self.prepare_count += 1
        return PreparationResult(
            run_id=manifest.run_id,
            status=RunStatus.READY_FOR_HUMAN,
            account_label=manifest.account_label,
            text_digest="digest",
            media_digests=(),
            audience=manifest.audience,
            evidence_paths=(),
        )

    def verify_published(self, manifest):
        return self.published_id


class FakeGateway:
    pass


def service(tmp_path: Path):
    adapter = FakeAdapter()
    instance = SocialBrowserService(
        policy=load_policy(ROOT / "src/config/social_browser_policy.json"),
        store=SocialBrowserStore(tmp_path / "social.sqlite3"),
        gateway_factory=lambda run_id: FakeGateway(),
        adapter_factory=lambda gateway: adapter,
    )
    return instance, adapter


def request() -> PrepareFacebookRequest:
    return PrepareFacebookRequest(
        account_label="test-account",
        text="Hermes social browser fixture",
        media_paths=(),
        audience="friends",
    )


def test_prepare_persists_ready_for_human(tmp_path: Path) -> None:
    instance, adapter = service(tmp_path)

    result = instance.prepare(request())
    stored = instance.store.get_run(result.run_id)

    assert result.status is RunStatus.READY_FOR_HUMAN
    assert stored.status is RunStatus.READY_FOR_HUMAN
    assert adapter.prepare_count == 1


def test_duplicate_prepare_reuses_existing_run(tmp_path: Path) -> None:
    instance, adapter = service(tmp_path)

    first = instance.prepare(request())
    second = instance.prepare(request())

    assert first.run_id == second.run_id
    assert adapter.prepare_count == 1


def test_verify_without_post_keeps_ready_for_human(tmp_path: Path) -> None:
    instance, _ = service(tmp_path)
    prepared = instance.prepare(request())

    result = instance.verify_after_human(prepared.run_id)

    assert result.status is RunStatus.READY_FOR_HUMAN


def test_verify_with_post_id_marks_published(tmp_path: Path) -> None:
    instance, adapter = service(tmp_path)
    prepared = instance.prepare(request())
    adapter.published_id = "https://www.facebook.com/test-account/posts/123456789"

    result = instance.verify_after_human(prepared.run_id)

    assert result.status is RunStatus.PUBLISHED
    assert result.verified_post_id.endswith("123456789")
