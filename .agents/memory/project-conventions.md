---
type: project
created: 2026-05-25
updated: 2026-07-12
---

# Project Conventions

## Git Workflow
- Always create a new dedicated branch for major code changes.
- Branch name format should follow: `feature/[task-slug]` or `fix/[bug-slug]`.

## Supported AI platforms (AG Kit)
- `.agents/` is the canonical AG Kit source for Google Antigravity and Gemini-compatible discovery.
- Claude Code is supported through generated thin adapters under `.claude/` plus `.mcp.json` and `CLAUDE.md` routing references.
- Adapters must not duplicate canonical workflow bodies. Unsupported runtime primitives map to safe semantic equivalents or fail closed.
- Do not claim support for other assistants unless the user explicitly expands scope and executable compatibility evidence exists.

## Master Senior Coding & Debugging Workflow (OMP + Ponytail)
1. **Pre-flight & Grilling (`using-superpowers`, `grilling`, `brainstorming`, `plan-writing`)**:
   - Check skills first.
   - Khi nhận plan, kiến trúc mới, hoặc khi user muốn phản biện: dùng `grilling` dựng decision tree, phỏng vấn user theo rounds qua decision frontier kèm phương án đề xuất; tra cứu fact bằng tools, không hỏi user cái mình tự tra được.
   - Yêu cầu mơ hồ: brainstorming; đa bước: lập plan, quản lý todo chặt chẽ.
2. **Deep Architecture & Seam Design (`codebase-design`, `architecture`)**:
   - Thiết kế deep module: interface nhỏ, hành vi sâu, đòn bẩy cao, tập trung rủi ro (locality).
   - Quy tắc Seam: 2 adapters mới tạo 1 seam thật; 1 adapter là seam giả định (tránh xa).
   - Deletion test: xóa module mà complexity biến mất = pass-through thừa thãi (xóa thẳng tay).
3. **Ponytail Coding Engine (`clean-code`, `simplify-code`)**:
   - Thang 6 bậc: Xóa bỏ nhu cầu > Stdlib > Native platform > Dependency có sẵn > 1-liner > Code tối thiểu.
   - Xóa bỏ mọi wrapper, factory, pass-through vô nghĩa. Shortest diff wins.
   - Đánh dấu đơn giản hóa: `# ponytail: [ceiling], upgrade path: [path]`.
   - Báo cáo chuẩn: `[code] → skipped: [X], add when [Y].`
   - Bất biến: Không bao giờ cắt giảm bảo mật, SSRF/auth guards, data-loss checks, trust boundaries.
4. **Forensic Debugging (`diagnosing-bugs`, `systematic-debugging`)**:
   - Cấm đoán mò hoặc đọc code suy đoán khi chưa có red loop.
   - Tạo tight feedback loop (<2s, deterministic, red-capable) tái hiện chính xác triệu chứng.
   - Thu nhỏ repro về mức tối thiểu chịu tải (load-bearing).
   - Đưa ra 3-5 giả thuyết có thể bác bỏ (falsifiable).
   - Đặt probes có tag `[DEBUG-...]` hoặc dùng debugger.
   - Sửa đúng seam, kiểm tra loop chuyển GREEN, dọn sạch probe tags, để lại 1 runnable check.
5. **Adversarial Audit & Security (`security-audit`, `red-team-tactics`, `vulnerability-scanner`)**:
   - Rà soát bề mặt tấn công, ranh giới tin cậy, OWASP, SSRF, injection trước khi chốt code.
6. **3-Layer Verification & Review (`verify-changes`, `lint-and-validate`, `receiving-code-review`)**:
   - Layer 1 (syntax/lint/PEP 8) -> Layer 2 (artifact behavior/smoke test) -> Layer 3 (system boundary).
   - Đánh giá review theo giá trị kỹ thuật thực tế, không đồng thuận hình thức.
7. **Handoff & Retention (`code-review-checklist`, `memory-system`, `retain`)**:
   - Dọn sạch file tạm/probes. Cập nhật `PROGRESS.md`, `DECISIONS.md`, lưu kinh nghiệm vào memory.
