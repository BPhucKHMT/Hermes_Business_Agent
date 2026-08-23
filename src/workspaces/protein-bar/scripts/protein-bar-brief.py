#!/usr/bin/env python3
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BOARD = "protein-bar"
OUT = Path(__file__).resolve().parent.parent / "reports"
OUT.mkdir(exist_ok=True)


def run(args: list[str]) -> str:
    p = subprocess.run(["hermes", "kanban"] + args, capture_output=True, text=True, check=True)
    return p.stdout


def extract_waiting(body: str | None) -> tuple[str, str]:
    if not body:
        return "—", "—"
    for line in body.splitlines():
        if line.strip().lower().startswith("waiting on:"):
            value = line.split(":", 1)[1].strip()
            return value, "—"
    return "—", "—"


def main() -> int:
    raw = run(["list", "--json"])
    tasks = json.loads(raw)
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    lines = []
    lines.append("# 📋 Daily Brief — Protein Bar Thao Dien")
    lines.append(f"> Generated: {now.isoformat()}")
    lines.append("")

    lines.append("## 1. 🎯 Top 3 hôm nay")
    top3 = [t for t in tasks if t.get("status") != "completed"][:3]
    for i, t in enumerate(top3, 1):
        lines.append(f"- {i}. {t.get('title','(no title)')}")
    if not top3:
        lines.append("- _không có việc cần làm ưu tiên_")
    lines.append("")

    lines.append("## 2. 📅 Deadline / Việc ưu tiên trong 14 ngày tới")
    lines.append("| # | Task | Trạng thái |")
    lines.append("|---|------|------------|")
    upcoming = [t for t in tasks if t.get("status") != "completed"][:14]
    for i, t in enumerate(upcoming, 1):
        lines.append(f"| {i} | {t.get('title','(no title)')} | {t.get('status','?')} |")
    lines.append("")

    lines.append("## 3. ⏳ Đang chờ hồi đáp")
    lines.append("| Task | Đang chờ |")
    lines.append("|------|----------|")
    waiting_shown = 0
    for t in tasks:
        who, _ = extract_waiting(t.get("body"))
        if who != "—":
            waiting_shown += 1
            lines.append(f"| {t.get('title','(no title)')} | {who} |")
    if not waiting_shown:
        lines.append("| _chưa có_ | _—_ |")
    lines.append("")

    lines.append("## 4. ✅ Hoàn thành kể từ brief trước")
    done = [t for t in tasks if t.get("status") == "completed"]
    if done:
        for t in done:
            lines.append(f"- {t.get('title','(no title)')}")
    else:
        lines.append("- _chưa có_")
    lines.append("")

    lines.append("## 5. 🔔 Đang chờ phê duyệt")
    pending = [t for t in tasks if t.get("status") in {"ready", "blocked"}]
    if pending:
        for t in pending:
            lines.append(f"- {t.get('title','(no title)')}")
    else:
        lines.append("- _không có_")
    lines.append("")

    text = "\n".join(lines)
    path = OUT / f"brief-{today.isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
