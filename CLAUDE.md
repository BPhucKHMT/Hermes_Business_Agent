# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## Project Operating Contract

Read `AGENTS.md` before project work. Follow its startup workflow, state artifacts, Definition of Done, verification gates, and end-of-session handoff.

### Approved Google Action Policy (H018, D028)

Google account consent grants capabilities, not blanket unattended execution.
Preserve caller/account/workspace isolation and enforce resource permissions.
A trusted user's explicit send-now/skip-preview email request is approval for
that specific email when material inputs are complete; do not require a redundant
draft preview. Draft-only requests do not authorize sending. Keep landlord
draft-only, Tier 3, outbound kill switch and destructive/sharing approval rules.
Verify effects and report unknown outcomes without blindly retrying a write.
This is approved target policy; runtime enforcement remains H018 implementation
work, not a claim that current production already complies.

## Unified Workflow: Claude Plugins (Superpowers) + Antigravity Kit

This project merges Claude Code's installed plugin ecosystem with the Antigravity Kit (`.agents/`):

1. **Senior AI Workflow: 6-Phase Competitive Skill Combination**:

| Giai đoạn | Các skill ứng viên trong kho | Skill chiến thắng được chọn | Lý do tuyển chọn kỹ thuật |
| :--- | :--- | :--- | :--- |
| **1. Làm rõ & Phản biện** | `grill-me`, `grilling`, `brainstorming`, `loop-me`, `to-spec` | **`grilling` + `grill-me`** | `brainstorming` chỉ hỏi chung. `grilling` (bộ Matt Pocock) mạnh hơn hẳn nhờ thuật toán Design Tree + chia câu hỏi theo Frontier Rounds (những câu hỏi đã đủ tiền đề) và BẮT BUỘC đưa kèm câu trả lời gợi ý (➡️) thay vì đùn đẩy việc suy nghĩ cho user. |
| **2. Kiến trúc module** | `codebase-design`, `architecture`, `domain-modeling` | **`codebase-design`** | Triết lý Deep Modules (năng lực xử lý lớn ẩn sau interface hẹp, đường cắt seam rõ ràng, testable cao). Tránh việc đẻ ra các class/interface nông (shallow module) gây phân mảnh code. |
| **3. Kế hoạch thực thi** | `writing-plans`, `plan-writing`, `wayfinder`, `to-tickets` | **`writing-plans`** | Chia nhỏ task theo dạng 3–5 milestone kèm tiêu chí kiểm chứng (verification criteria) độc lập cho từng bước. |
| **4. Chất lượng code & Tinh gọn** | `clean-code`, `simplify-code`, `code-review-excellence` | **`clean-code` + `simplify-code` + `# ponytail:`** | `clean-code` triệt tiêu over-engineering (KISS, YAGNI, DRY, PEP 8). `simplify-code` làm phẳng logic, dọn dead-code. Bắt buộc gắn `# ponytail: [ceiling], upgrade when [trigger]` cho các đoạn code tối giản có chủ ý. |
| **5. Chẩn đoán & Debug** | `diagnosing-bugs`, `systematic-debugging` | **`diagnosing-bugs` + `systematic-debugging`** | Kết hợp 2 kỷ luật thép: 1) Redact First (không để lộ secret/token ra log); 2) 4 pha nghiêm ngặt: Tái hiện deterministic ➔ Tìm root cause bằng bằng chứng ➔ Sửa tối thiểu ➔ Chạy kiểm tra hồi quy. Cấm đoán mò hoặc sửa thử sai. |
| **6. Kiểm chứng hoàn thành** | `verification-before-completion`, `verify-changes`, `lint-and-validate` | **`verification-before-completion` + `verify-changes`** | Nguyên tắc cốt lõi: Evidence before assertion. Tuyệt đối cấm LLM tự tuyên bố "đã xong", "đã fix" nếu chưa tự chạy terminal command ra kết quả exit code 0. |

2. **Domain Architecture & Standards (Antigravity Kit)**:
   - `.agents/` is the canonical domain kit containing domain skills, rules, and memory.
   - Always apply `.agents/skills/clean-code/SKILL.md` (PEP 8, KISS, YAGNI, SRP, DRY, surgical diffs).
   - Load domain specialist skills (`python-patterns`, `api-patterns`, `database-design`, `mcp-builder`, `security-audit`, `architecture`) based on the task domain.
   - Read `.agents/memory/MEMORY.md` for project-specific persistent conventions.

3. **Coexistence & Operating Rules**:
   - Superpowers drives the *how* of task orchestration, TDD, planning, subagents, and verification.
   - Antigravity Kit drives the *what* of code quality, architecture patterns, domain rules, and project memory.
   - Neither ecosystem overrides or disables the other; they operate in synergy.
## Coding Contract

Before any code change, read and apply `.agents/skills/clean-code/SKILL.md`.
Read and apply `rules/coding_rule.md` before writing, modifying, or reviewing
code; it owns project-specific import, exception, suppression, and evidence gates.
Python code and tests must follow PEP 8. Keep changes minimal, direct, and
self-documenting; prefer deletion and standard-library or existing-native
capabilities over new abstractions or dependencies. Preserve input validation,
security, data-loss prevention, accessibility, and explicitly required behavior.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
