from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def layer_1() -> None:
    policy = json.loads((SRC / "config/progress_policy.json").read_text(encoding="utf-8"))
    targets = json.loads((SRC / "config/progress_targets/protein_bar_progress.json").read_text(encoding="utf-8"))

    assert policy["workspace"] == "protein-bar"
    assert policy["actions"]["report.apply"]["tier"] == 2
    assert policy["actions"]["external_message.send"]["enabled"] is False
    assert not Path(policy["runtime_root"]).is_absolute()

    assert targets["workspace"] == "protein-bar"
    assert targets["format"] == "markdown"
    assert ".." not in Path(targets["source"]).parts

    required_files = (
        "contracts.py",
        "store.py",
        "flow.py",
        "documents.py",
        "executor.py",
        "progress.py",
    )
    assert all((SRC / "tools/progress" / f).is_file() for f in required_files)
    assert (SRC / "skills/progress-report/SKILL.md").is_file()
    print("progress layer 1: pass")


def layer_2() -> None:
    from tools.progress.contracts import SourceEvent
    from tools.progress.documents import ReportTarget, preview_markdown
    from tools.progress.executor import approve_and_execute, record_approval
    from tools.progress.flow import ResolutionContext, build_flow_a
    from tools.progress.store import append_source, migrate, open_store, save_flow_result

    fixture = ROOT / "tests/fixtures/progress/protein_bar_weekly.md"
    original = fixture.read_bytes()

    source = SourceEvent(
        "telegram:-1003835812097:11:42",
        "protein-bar",
        "telegram",
        "2026-08-21T03:00:00Z",
        "actor",
        hashlib.sha256(b"TEST_ENTITY_A").hexdigest(),
        {"chat_id": "-1003835812097", "thread_id": "11", "message_id": "42"},
    )
    context = ResolutionContext(
        "protein-bar",
        {"test-entity-a": "TEST_ENTITY_A"},
        "progress-report-v1",
        "owner-a",
    )

    result = build_flow_a(
        source,
        {
            "supplier_key": "test-entity-a",
            "summary": "Entity status changed.",
            "task_summary": "Review entity status",
            "due_at": "2026-08-24",
            "draft": "Request a status update.",
        },
        context,
    )

    assert result.missing_field is None
    assert result.proposal is not None and result.proposal.risk_tier == 2
    assert result.draft_sent is False
    assert result.task is not None and result.task.owner == "owner-a"

    unmatched = build_flow_a(source, {"summary": "Status changed"}, context)
    assert unmatched.proposal is None

    with tempfile.TemporaryDirectory() as td:
        runtime = Path(td)
        db = runtime / "state.sqlite3"
        connection = open_store(db)
        migrate(connection)

        identity, created = append_source(connection, source)
        assert created
        assert append_source(connection, source) == (identity, False)

        save_flow_result(connection, result)
        connection.close()

        target = ReportTarget(
            "progress-report-v1",
            "protein-bar",
            fixture,
            "## Blockers",
            hashlib.sha256(original).hexdigest(),
        )
        preview = preview_markdown(target, result.proposal)
        assert "Entity status changed" in preview.after

        connection = open_store(db)
        record_approval(
            connection,
            result.proposal.proposal_id,
            "approval-1",
            "Klaus",
            datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        connection.close()

        execution = approve_and_execute(
            db,
            target,
            result.proposal.proposal_id,
            "approval-1",
            "Klaus",
            runtime / "outputs",
        )
        assert execution.status == "verified"
        assert execution.output_path.is_file()
        assert fixture.read_bytes() == original

        repeated = approve_and_execute(
            db,
            target,
            result.proposal.proposal_id,
            "approval-1",
            "Klaus",
            runtime / "outputs",
        )
        assert repeated.output_path == execution.output_path

        connection = open_store(db)
        evidence_count = connection.execute(
            "SELECT count(*) FROM evidence WHERE kind = 'report_output'"
        ).fetchone()[0]
        assert evidence_count == 1
        connection.close()

    test_progress_sync_contract()
    test_current_answer_prefers_new_state()
    print("progress layer 2: pass")


def test_progress_sync_contract() -> None:
    from tools.progress.knowledge_sync import sync_verified_report

    class MockBlob:
        def __init__(self):
            self.uploads = []

        def upload_blob(self, *args, **kwargs):
            self.uploads.append((args, kwargs))

    class MockIndexers:
        def __init__(self):
            self.runs = []

        def run_indexer(self, name: str):
            self.runs.append(name)

    blob = MockBlob()
    indexers = MockIndexers()
    seen = []

    result = sync_verified_report(
        content=b"revision: abc123\nEntity status changed.",
        workspace="protein-bar",
        source_path="workspaces/protein-bar/progress/progress-report-v1.md",
        revision="abc123",
        text_container=blob,
        indexers=indexers,
        text_indexer="text",
        wait=lambda *_a, **_k: {"status": "success"},
        search=lambda **kw: seen.append(kw) or [{"content": "revision: abc123"}],
    )

    assert result.status == "verified"
    assert len(blob.uploads) == 1
    assert indexers.runs == ["text"]
    assert "source_path eq" in seen[0]["filter"]


def test_current_answer_prefers_new_state() -> None:
    from tools.progress.answer import compose_current_answer

    pending_answer = compose_current_answer(
        "Entity status changed.",
        "abc123",
        [],
        "progress-report-v1.md",
    )
    assert "Entity status changed" in pending_answer.text
    assert pending_answer.sync_status == "pending"

    verified_answer = compose_current_answer(
        "Entity status changed.",
        "abc123",
        [{"content": "revision: abc123", "source_path": "workspaces/protein-bar/progress/progress-report-v1.md"}],
        "progress-report-v1.md",
    )
    assert verified_answer.sync_status == "verified"
    assert verified_answer.citation is not None


def test_ambiguous_input_returns_typed_missing_field() -> None:
    from tools.progress.contracts import SourceEvent
    from tools.progress.flow import ResolutionContext, build_flow_a

    source = SourceEvent(
        "ambiguous-entity",
        "protein-bar",
        "telegram",
        "2026-08-21T00:00:00Z",
        "user",
        "abc",
        {"message_id": "m-amb"},
    )
    result = build_flow_a(
        source,
        {
            "summary": "Entity status changed",
            "task_summary": "Follow up next week",
            "due_at": "2026-08-31",
            "draft": "Following up.",
        },
        ResolutionContext("protein-bar", {}, "protein-bar-progress-v1", "Klaus"),
    )
    assert result.missing_field == "entity"
    assert result.task is None
    assert result.proposal is None
    assert result.draft is None

    resolver = (SRC / "tools/progress/flow.py").read_text(encoding="utf-8")
    assert "?" not in resolver


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Progress Layer Gates")
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()

    if args.layer == 1:
        layer_1()
    else:
        layer_2()


if __name__ == "__main__":
    test_ambiguous_input_returns_typed_missing_field()
    main()
