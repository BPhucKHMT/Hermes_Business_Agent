---
name: code-rules
version: 1.0.0
priority: P0
trigger: model_decision
description: Apply when writing, building, refactoring, or fixing code — project-type agent routing, the Socratic Gate, Plan Mode phases, and the final checklist/scripts. Skip for pure questions or text-only responses.
---

# Code Rules (TIER 1) - AG Kit

> Loaded when the request involves writing or modifying code.

---

## 📱 Project Type Routing

| Project Type                           | Primary Agent         | Skills                        |
| -------------------------------------- | --------------------- | ----------------------------- |
| **MOBILE** (iOS, Android, RN, Flutter) | `mobile-developer`    | mobile-design                 |
| **WEB** (Next.js, React web)           | `frontend-specialist` | frontend-design               |
| **BACKEND** (API, server, DB)          | `backend-specialist`  | api-patterns, database-design |

> 🔴 **Mobile + frontend-specialist = WRONG.** Mobile = mobile-developer ONLY.

---

## 🏆 Senior Coding Agent Workflow: 6-Phase Competitive Skill Matrix

| Giai đoạn | Các skill ứng viên trong kho | Skill chiến thắng được chọn | Lý do tuyển chọn kỹ thuật |
| :--- | :--- | :--- | :--- |
| **1. Làm rõ & Phản biện** | `grill-me`, `grilling`, `brainstorming`, `loop-me`, `to-spec` | **`grilling` + `grill-me`** | `brainstorming` chỉ hỏi chung. `grilling` (bộ Matt Pocock) mạnh hơn hẳn nhờ thuật toán Design Tree + chia câu hỏi theo Frontier Rounds (những câu hỏi đã đủ tiền đề) và BẮT BUỘC đưa kèm câu trả lời gợi ý (➡️) thay vì đùn đẩy việc suy nghĩ cho user. |
| **2. Kiến trúc module** | `codebase-design`, `architecture`, `domain-modeling` | **`codebase-design`** | Triết lý Deep Modules (năng lực xử lý lớn ẩn sau interface hẹp, đường cắt seam rõ ràng, testable cao). Tránh việc đẻ ra các class/interface nông (shallow module) gây phân mảnh code. |
| **3. Kế hoạch thực thi** | `writing-plans`, `plan-writing`, `wayfinder`, `to-tickets` | **`writing-plans`** | Chia nhỏ task theo dạng 3–5 milestone kèm tiêu chí kiểm chứng (verification criteria) độc lập cho từng bước. |
| **4. Chất lượng code & Tinh gọn** | `clean-code`, `simplify-code`, `code-review-excellence` | **`clean-code` + `simplify-code` + `# ponytail:`** | `clean-code` triệt tiêu over-engineering (KISS, YAGNI, DRY, PEP 8). `simplify-code` làm phẳng logic, dọn dead-code. Bắt buộc gắn `# ponytail: [ceiling], upgrade when [trigger]` cho các đoạn code tối giản có chủ ý. |
| **5. Chẩn đoán & Debug** | `diagnosing-bugs`, `systematic-debugging` | **`diagnosing-bugs` + `systematic-debugging`** | Kết hợp 2 kỷ luật thép: 1) Redact First (không để lộ secret/token ra log); 2) 4 pha nghiêm ngặt: Tái hiện deterministic ➔ Tìm root cause bằng bằng chứng ➔ Sửa tối thiểu ➔ Chạy kiểm tra hồi quy. Cấm đoán mò hoặc sửa thử sai. |
| **6. Kiểm chứng hoàn thành** | `verification-before-completion`, `verify-changes`, `lint-and-validate` | **`verification-before-completion` + `verify-changes`** | Nguyên tắc cốt lõi: Evidence before assertion. Tuyệt đối cấm LLM tự tuyên bố "đã xong", "đã fix" nếu chưa tự chạy terminal command ra kết quả exit code 0. |

---

## 🛑 GLOBAL SOCRATIC GATE (Grilling Protocol)

**MANDATORY: Every user request must pass through the Grilling Protocol before ANY tool use or implementation.**

| Request Type            | Strategy       | Required Action                                                   |
| :--- | :--- | :--- |
| **New Feature / Build** | Deep Discovery | Design Tree + Frontier Rounds, kèm câu trả lời đề xuất (➡️)       |
| **Code Edit / Bug Fix** | Context Check  | Confirm understanding + ask impact questions kèm lựa chọn          |
| **Vague / Simple**      | Clarification  | Ask Purpose, Users, and Scope + provide default recommendations   |
| **Full Orchestration**  | Gatekeeper     | **STOP** subagents until user confirms plan details               |
| **Direct "Proceed"**    | Validation     | **STOP** → Ask 2 critical edge-case questions with suggested answers|

**Protocol Rules:**
1. **Never Assume:** If even 1% is unclear, ASK via Frontier Rounds.
2. **Always Recommend:** Every question MUST provide a concrete suggested answer/option (➡️) so the user can easily confirm instead of having to draft solutions from scratch.
3. **Wait:** Do NOT invoke subagents or write code until the user clears the Gate.
4. **Reference:** Full protocol in `@[skills/grilling]`.

---

## 🐴 The Ponytail Contract (Deliberate Simplification)

Mọi đoạn code được tối giản có chủ đích (để tránh over-engineering hoặc chưa cần mở rộng) **BẮT BUỘC** phải có comment đánh dấu trần giới hạn và điều kiện nâng cấp:

```python
# ponytail: [trần giới hạn của giải pháp hiện tại], upgrade when [điều kiện kích hoạt nâng cấp]
```

Ví dụ:
```python
# ponytail: simple dictionary-based session routing with global lock; upgrade when concurrent requests exceed 50 RPS.
```

---

## 🏁 Execution Planning Mode (`writing-plans`)

1. **ANALYSIS** → Nghiên cứu hiện trạng, xác định seam và interface (`codebase-design`).
2. **PLANNING** → Tạo kế hoạch chia nhỏ thành 3–5 milestone độc lập kèm tiêu chí kiểm chứng cho từng bước (`writing-plans`).
3. **IMPLEMENTATION** → Viết code tối giản, phẳng, sạch sẽ (`clean-code + simplify-code`).
4. **VERIFICATION** → Kiểm chứng bằng chứng thực tế trước khi hoàn thành (`verification-before-completion + verify-changes`).

## 🏁 Final Checklist Protocol

**Trigger:** When the user says "run the final checks", "final checks", "run all the tests", or similar phrases.

| Task Stage       | Command                                            | Purpose                        |
| ---------------- | -------------------------------------------------- | ------------------------------ |
| **Manual Audit** | `python .agents/scripts/checklist.py .`             | Priority-based project audit   |
| **Pre-Deploy**   | `python .agents/scripts/checklist.py . --url <URL>` | Full Suite + Performance + E2E |

**Priority Execution Order:**

1. **Security** → 2. **Lint** → 3. **Schema** → 4. **Tests** → 5. **UX** → 6. **Seo** → 7. **Lighthouse/E2E**

**Rules:**

- **Completion:** A task is NOT finished until `checklist.py` returns success.
- **Reporting:** If it fails, fix the **Critical** blockers first (Security/Lint).

**Available Scripts (10 total):**

| Script                     | Skill                 | When to Use         |
| -------------------------- | --------------------- | ------------------- |
| `security_scan.py`         | vulnerability-scanner | Always on deploy    |
| `lint_runner.py`           | lint-and-validate     | Every code change   |
| `test_runner.py`           | testing-patterns      | After logic change  |
| `schema_validator.py`      | database-design       | After DB change     |
| `ux_audit.py`              | frontend-design       | After UI change     |
| `accessibility_checker.py` | frontend-design       | After UI change     |
| `seo_checker.py`           | seo-fundamentals      | After page change   |
| `mobile_audit.py`          | mobile-design         | After mobile change |
| `lighthouse_audit.py`      | performance-profiling | Before deploy       |
| `playwright_runner.py`     | webapp-testing        | Before deploy       |

> 🔴 **Agents & Skills can invoke ANY script** via `python .agents/skills/<skill>/scripts/<script>.py`

---
