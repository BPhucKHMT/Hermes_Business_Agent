from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def layer_1() -> None:
    assert not (SRC / "tools/progress").exists(), "Custom progress tool directory must be removed"
    assert not (SRC / "config/progress_policy.json").exists(), "Obsolete progress_policy.json must be removed"
    assert not (SRC / "config/progress_targets").exists(), "Obsolete progress_targets directory must be removed"

    skill_file = SRC / "skills/progress-report/SKILL.md"
    assert skill_file.is_file(), "progress-report/SKILL.md must exist"
    skill_text = skill_file.read_text(encoding="utf-8")
    required = (
        "name: progress-report",
        "Domain Owner Resolution",
        "Ask exactly one short clarification question",
        "Never infer an owner from a filename",
        "Landlord communication remains draft-only",
        "Payments, transfers, money movement, and legal signing remain human-only",
        "Denial, timeout, silence, or no response is never approval",
        "Do not send customer PII to third-party tools",
        "Planning Intent",
        "Reminder Intent",
        "Follow-Up Intent",
        "Read-Before-Write and Read-Back",
        "Serial Replay and Concurrent Delivery",
        "Cold-Session Query Routing",
        "Partial Failure Matrix",
        "Layer 3 Release Gates",
        "--workspace protein-bar",
    )
    assert all(value in skill_text for value in required), [
        value for value in required if value not in skill_text
    ]
    forbidden = (
        "progress.sqlite3",
        "tools.progress",
        "src/tools/progress",
        "tests/fixtures",
    )
    assert not any(value in skill_text for value in forbidden)

    agents_file = SRC / "AGENTS.md"
    assert agents_file.is_file()
    agents_text = agents_file.read_text(encoding="utf-8")
    routing = (
        "/progress-report",
        "Hermes Kanban owns operational task state",
        "registered business documents own business narratives",
        "--workspace protein-bar",
    )
    assert all(value in agents_text for value in routing), [
        value for value in routing if value not in agents_text
    ]

    for py_file in (SRC / "tools").glob("**/*.py"):
        code = py_file.read_text(encoding="utf-8")
        assert "tools.progress" not in code
        assert "progress_policy" not in code

    features = json.loads((ROOT / "feature-list.json").read_text(encoding="utf-8"))
    progress_feature = next(
        feature for feature in features["features"] if feature["id"] == "H008"
    )
    assert progress_feature["state"] in {"active", "passing"}
    assert "native Hermes Kanban" in progress_feature["behavior"]
    assert "registered business document" in progress_feature["behavior"]
    assert "docs/superpowers/specs/2026-08-22-progress-native-redesign.md" in (
        progress_feature["verification"]["layer_3"]
    )

    print("progress layer 1: pass")


def layer_2() -> None:
    skill_text = (SRC / "skills/progress-report/SKILL.md").read_text(
        encoding="utf-8"
    )
    ordered_steps = (
        "Resolve owners and capture current evidence.",
        "Write requested business artifact domains in deterministic role order.",
        "Read back each changed artifact immediately.",
        "Create or reuse the Kanban operational task.",
        "Create or reuse Cron only when scheduling intent exists.",
        "Project only verified changed documents through `hermes-azure-rag`.",
    )
    positions = [skill_text.index(step) for step in ordered_steps]
    assert positions == sorted(positions)

    outcomes = (
        "Owner resolution fails",
        "Artifact write fails",
        "Read-back mismatches",
        "Artifact verified, Kanban fails",
        "Kanban succeeds, requested Cron fails",
        "Azure fails or remains stale",
        "Kanban-only success does not depend on Azure",
    )
    assert all(value in skill_text for value in outcomes), [
        value for value in outcomes if value not in skill_text
    ]

    layer_3_scenarios = (
        "fresh Hermes process",
        "Telegram profile exposes required Kanban tools",
        "dispatcher observation proves no worker starts",
        "concurrent duplicate delivery",
        "cold session with no prior chat context",
        "Cron list and manual run",
        "wrong-workspace retrieval and mutation",
    )
    assert all(value in skill_text for value in layer_3_scenarios), [
        value for value in layer_3_scenarios if value not in skill_text
    ]

    print("progress layer 2: pass")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Progress Layer Gates")
    parser.add_argument("--layer", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()

    if args.layer == 1:
        layer_1()
    else:
        layer_2()


if __name__ == "__main__":
    main()
