# Quy chuẩn coding — Hermes Business Agent

## 1. Mục đích và phạm vi

Áp dụng cho mọi thay đổi production code, test code, script và review trong
repository. Đây là chuẩn kỹ thuật dành cho coding agent; không phải runtime
context của Hermes.

Thứ tự ưu tiên khi có xung đột:

1. Acceptance criteria và guardrail trong feature đang thực hiện.
2. [`AGENTS.md`](../AGENTS.md) — workflow, phạm vi `src/`, feature state và ba lớp
   kiểm chứng.
3. [`CLAUDE.md`](../CLAUDE.md) — hành vi và quy trình coding.
4. [Canonical clean-code skill](../.agents/skills/clean-code/SKILL.md) — KISS,
   YAGNI, SRP, DRY và build-or-reuse gate.
5. Tài liệu này — quy tắc Python, import, exception, suppression và evidence.
6. [`ruff.toml`](../ruff.toml) và [`src/pyproject.toml`](../src/pyproject.toml) —
   cấu hình tool, phiên bản Python và dependency đã pin.

Code mới phải sạch ngay từ lần viết đầu. “Không refactor trước khi core behavior
được kiểm chứng” chỉ ngăn thay đổi ngoài phạm vi; không cho phép tạo nợ kỹ thuật
có chủ ý.

## 2. Nguyên tắc bắt buộc

### 2.1 Correctness trước, đơn giản sau

- Implement đúng contract đã được xác minh; không tự mở rộng yêu cầu.
- Giữ nguyên authentication, authorization, workspace isolation, approval,
  evidence, data-loss prevention và secret redaction.
- Sửa nguyên nhân gốc. Không che lỗi bằng fallback giả, success rỗng, mock data,
  tài khoản khác hoặc nhánh riêng cho input gây lỗi.
- Khi thay đổi public/exported contract, cập nhật toàn bộ caller, test và tài liệu
  liên quan trong cùng một cutover. Không giữ alias hoặc compatibility shim nếu
  không còn consumer đã xác minh.

### 2.2 Build-or-reuse gate

Dừng tại lựa chọn đầu tiên đáp ứng đầy đủ yêu cầu:

1. Loại bỏ hành vi nếu sản phẩm không cần.
2. Dùng Python standard library.
3. Dùng behavior native của platform/framework.
4. Tái sử dụng code hiện có trong repository.
5. Dùng API được tài liệu hóa của dependency đang cài.
6. Chỉ viết lượng custom code tối thiểu cho invariant Hermes sở hữu.

Trước khi viết parser, crawler, retry loop, cache, serializer, validator, state
machine, repository wrapper hoặc framework mới, phải kiểm tra API của dependency
đúng phiên bản đã lock và ghi rõ thiếu sót khiến custom code thực sự cần thiết.

### 2.3 Thiết kế và cấu trúc

- Một module sở hữu một miền trách nhiệm rõ; một hàm thực hiện một công việc.
- Ưu tiên guard clause và luồng phẳng. Tách hàm khi tên gọi tạo ra abstraction có
  nghĩa, không tách chỉ để đạt số dòng tùy ý.
- Tên biểu đạt domain intent. Boolean dùng dạng câu hỏi như `is_ready`,
  `has_access`, `can_publish`; constant dùng `UPPER_SNAKE_CASE`.
- Type hint chính xác tại boundary và API dùng chung. Không thêm `Any`, `cast()`,
  `# type: ignore` hoặc wrapper chỉ để làm checker im lặng.
- Tránh mutable global state và side effect ẩn. Side effect phải nằm ở boundary
  có tên rõ và có thể kiểm chứng.
- Không tạo interface/factory/plugin framework cho một implementation giả định.
  Chỉ tạo seam khi có ít nhất hai implementation thật hoặc một trust boundary cần
  cô lập.
- Comment giải thích invariant, lý do hoặc trade-off không thể hiện từ code.
  Code tự giải thích cú pháp và luồng hiển nhiên.
- `# ponytail:` chỉ ghi một giới hạn tối giản có chủ ý cùng upgrade trigger có thể
  đo được; không dùng như comment trang trí hoặc giấy phép bỏ acceptance criteria.

## 3. Python và PEP 8

- Production và test code tuân thủ PEP 8 cùng baseline trong `ruff.toml`.
- Target hiện tại là Python 3.12: dùng built-in generics (`list[str]`), union `|`
  và interface collection từ `collections.abc`.
- Formatter dùng double quotes và line length mục tiêu 88. `E501` bị loại khỏi
  baseline vì formatter không thể bảo đảm mọi dòng đạt ngưỡng; điều này không cho
  phép viết dòng khó đọc khi có thể xuống dòng tự nhiên.
- Dùng pathlib, context manager, dataclass, enum, timezone-aware datetime và API
  standard library khi chúng giải quyết đúng bài toán; không dựng helper tương
  đương.
- Tránh allocation/copy/compute trong hot path khi có lựa chọn rõ ràng không tạo
  thêm độ phức tạp. Không tối ưu sớm khi chưa có bằng chứng profiling.

### 3.1 Import

Import production đặt ở module level theo PEP 8 và D026:

```python
import json
from pathlib import Path

from composio import Composio

from tools.composio.bridge import execute_tool
```

Quy tắc:

- Thứ tự: standard library → third-party → local; mỗi nhóm cách nhau một dòng.
- Không chen constant, logger hoặc executable statement giữa các nhóm import.
- Không dùng `import *`.
- Không import trong function/method để né circular dependency, startup cost hoặc
  tổ chức module. Sửa dependency direction hoặc module ownership ở nguồn.
- Không bọc import bằng `try/except` tùy tiện. Dependency bắt buộc thiếu phải fail
  rõ với lỗi import gốc.
- Optional dependency chỉ được xử lý như optional khi product contract xác nhận
  feature có thể vắng mặt. Bắt đúng `ModuleNotFoundError` của package dự kiến;
  không nuốt lỗi từ dependency con hay lỗi khởi tạo.
- Test/probe có thể trì hoãn import khi cần thiết lập environment, fixture hoặc
  host stub trước khi module được load. Ghi lý do cụ thể tại import và suppression
  đúng mã. Ngoại lệ test không trở thành pattern production.
- Module-level bootstrap sau một executable setup liên quan `E402`; import trong
  function liên quan `PLC0415`. Không dùng suppression của rule này để che rule kia.

Import trong function vẫn là Python hợp lệ và được cache; quy định module-level là
kỷ luật dependency của Hermes, không phải tuyên bố sai về cơ chế Python.

### 3.2 Exception

```python
try:
    event = client.create_event(payload)
except ProviderRequestError as exc:
    raise CalendarWriteError("Google Calendar rejected the event") from exc
```

Quy tắc:

- Giữ `try` nhỏ, chỉ bao quanh operation có thể phát sinh lỗi cần xử lý.
- Bắt loại exception cụ thể được API tài liệu hóa hoặc đã quan sát trong test.
- Chỉ bắt lỗi khi tầng hiện tại có hành động đúng: recover, translate sang domain
  error, fail closed, cleanup rồi re-raise, hoặc trả error result theo contract.
- `except Exception` chỉ hợp lệ ở process/task/API boundary chịu trách nhiệm ngăn
  crash lan rộng. Boundary phải ghi log đã redact, trả trạng thái lỗi thật và có
  test cho error path. Dùng `# noqa: BLE001` kèm lý do cụ thể tại dòng đó.
- Không dùng bare `except`, `except BaseException` hoặc suppression rộng; chúng có
  thể nuốt `KeyboardInterrupt`, `SystemExit`, cancellation và lỗi lập trình.
- Dùng bare `raise` để re-raise. Dùng `raise DomainError(...) from exc` khi đổi
  abstraction. `from None` chỉ khi intentionally ẩn context không hữu ích và có
  lý do rõ.
- `contextlib.suppress(SpecificError)` chỉ dùng khi lỗi cụ thể đó được contract
  xác nhận là an toàn để bỏ qua.
- Cleanup phải dùng context manager hoặc `finally` khi tài nguyên cần được giải
  phóng bất kể operation thành công hay thất bại.

### 3.3 Logging và dữ liệu nhạy cảm

- Log event, trạng thái và identifier tối thiểu cần cho vận hành; log ở boundary
  sở hữu lỗi, không lặp cùng exception qua nhiều tầng.
- Redact token, API key, authorization header, signed URL, OAuth code, raw email,
  private payload, customer PII và exception text có thể chứa dữ liệu nhạy cảm.
- Không ghi secret vào source, test fixture, snapshot, command output, `PROGRESS.md`
  hoặc Git history.
- Provider timeout/error phải được báo là lỗi thật; “không có dữ liệu” chỉ dùng khi
  provider đã trả một kết quả rỗng hợp lệ.

## 4. Dữ liệu, API và trust boundary

- Validate input bên ngoài tại boundary: kiểu, required field, enum, độ dài, path,
  URL, identity và quyền thực thi.
- Workspace/profile/chat binding phải được xác định trước inference. Model input
  không được chọn identity, workspace hoặc authorization scope.
- Query SQL dùng parameter binding. OData, shell argument, URL và filesystem path
  phải được encode/validate bằng API đúng miền; không nội suy trực tiếp dữ liệu
  không tin cậy.
- Side effect phải idempotent khi contract yêu cầu. Approval denial, timeout hoặc
  im lặng không bao giờ là approval.
- External communication, invoice, booking và landlord negotiation tuân thủ tier
  hiện hành. Money movement, payment và legal signing là human-only.
- Success chỉ được trả khi target system cung cấp evidence tương ứng và verifier
  đọc lại được trạng thái cần thiết.

## 5. Test

Test phải bảo vệ observable contract và thất bại với một bug hợp lý:

- Behavior, boundary, invariant, state transition, precedence, isolation và error
  path là mục tiêu test phù hợp.
- Không test source text, field copy, argument forwarding, mock echo, default ngẫu
  nhiên hoặc chi tiết implementation không thuộc contract.
- Mock network/SDK tại boundary nơi code gọi dependency; production code không
  được nhận diện mock, dò test runner hoặc chọn nhánh dành riêng cho test.
- Patch symbol tại namespace nơi consumer tra cứu symbol.
- Bugfix cần red-green: reproduction phải fail trước fix và pass sau fix. Nếu
  regression test lâu dài không xứng đáng, dùng throwaway smoke probe rồi xóa.
- Test deterministic, isolated, không dùng secret thật và chạy an toàn trong full
  suite.
- Không thêm nhiều parameter row chạy cùng một path chỉ để tăng test count.
- Test cũ chỉ pin wording/implementation và không bảo vệ behavior phải được xóa,
  không sửa lại expected text để tiếp tục duy trì test vô nghĩa.

## 6. Suppression và modernization

### 6.1 Suppression

- Sửa nguyên nhân trước. Mỗi `noqa` phải có mã rule hẹp và lý do cụ thể có thể
  review.
- Không dùng blanket `noqa`, bulk `--add-noqa`, file-wide ignore hoặc giảm rule set
  chỉ để checker xanh.
- `# type: ignore[...]` phải chỉ rõ mã và giới hạn thiếu sót thật của dependency.
- Xóa suppression hết hiệu lực; `RUF100` là gate bắt buộc.
- “0 diagnostics” không đồng nghĩa code đúng nếu lỗi đã bị suppress.

### 6.2 Modernization

Autofix chỉ được áp dụng khi giữ nguyên semantics:

- `%` → f-string: giữ escaping, quoting và kiểu dữ liệu; không biến parameterized
  SQL thành string interpolation.
- `Enum` → `StrEnum`: kiểm tra `str()`, formatting, equality và serialization ở
  caller.
- `zip(strict=...)`: chọn từ invariant độ dài; không thêm `strict=False` chỉ để
  hết lint.
- Không chạy `--unsafe-fixes` hàng loạt nếu chưa review từng loại rewrite.

## 7. Workflow bắt buộc

### 7.1 Trước khi sửa

1. Đọc feature, acceptance criteria, file liên quan và code lân cận.
2. Xác định callers, side effects, trust boundaries và evidence cần có.
3. Với exported symbol, dùng LSP references trước khi đổi contract.
4. Áp dụng build-or-reuse gate và chọn minimum working diff.
5. Xác định command chứng minh behavior trước khi viết.

### 7.2 Trong khi sửa

1. Giữ diff trong scope; không format hoặc refactor file không liên quan.
2. Cập nhật mọi caller bị ảnh hưởng trong cùng cutover.
3. Thêm test chỉ khi nó bảo vệ contract lâu dài; nếu không, dùng smoke probe.
4. Không sửa operator config, deploy, gửi email hoặc tạo external side effect nếu
   task không yêu cầu rõ.

### 7.3 Sau khi sửa

Ba lớp chạy theo thứ tự; lớp trước fail thì dừng và sửa trước khi chạy lớp sau.

#### Layer 1 — static và schema

Chạy từ repository root bằng môi trường operator:

```text
uv tool run ruff --version
uv tool run ruff check --config ruff.toml src tests
uv tool run ruff check --config ruff.toml --extend-select RUF100 src tests
uv tool run ruff format --check --config ruff.toml src tests
```

Bổ sung compile/schema/type checker áp dụng cho feature. Ruff không phải type
checker. Lệnh `--select` hẹp chỉ là chẩn đoán partial, không thay baseline cấu hình.
Không pipe checker qua command khác làm mất exit status.

#### Layer 2 — artifact behavior

```text
uv run --project src --frozen python -B -m pytest tests/ -q -p no:cacheprovider
```

Chạy thêm verifier Layer 1/2 được khai báo trong `feature-list.json`. Một suite có
`--ignore`, deselection hoặc skip phải báo đúng exclusion; không gọi là full-suite
pass.

#### Layer 3 — system boundary

Chạy scenario thật tại CLI, gateway hoặc provider tương ứng acceptance criteria.
Mock test không chứng minh deployment, OAuth, delivery hoặc target-system state.
UI phải được kiểm tra trên surface thật; external mutation phải tuân thủ approval.

## 8. Evidence và bàn giao

Mỗi kết luận kiểm chứng phải ghi:

- command/scenario đã chạy;
- UTC timestamp;
- exit status;
- kết quả quan sát được;
- phạm vi và exclusion.

Báo riêng ba nhóm: static/format, behavior và live boundary. Không suy rộng bằng
chứng partial thành kết luận toàn hệ thống.

Khi gate fail:

- giữ trạng thái chưa đạt;
- ghi finding, owner và unblock condition cụ thể;
- sửa code hoặc contract gốc, không giảm chuẩn để tự chấm xanh.

Chỉ independent verifier được chuyển feature sang `passing`. Cập nhật
`PROGRESS.md`, `DECISIONS.md` và `feature-list.json` khi workflow của feature yêu
cầu; không dùng số dòng sửa hoặc số warning giảm làm bằng chứng hoàn thành.

## 9. Checklist review

### Standards

- [ ] Diff tối thiểu và mọi dòng thay đổi truy ngược được về yêu cầu.
- [ ] Không tái hiện capability đã có trong stdlib, platform, repository hoặc SDK.
- [ ] Import ở module level, đúng nhóm; optional import có contract thật.
- [ ] Exception cụ thể; broad catch chỉ ở tested boundary.
- [ ] Không fallback giả, mock-aware production branch hoặc suppression vô cớ.
- [ ] Type hint, naming, ownership và side effect rõ ràng.
- [ ] Secret/PII được redact; authorization và workspace isolation được giữ.

### Spec

- [ ] Mọi acceptance criterion được đáp ứng end-to-end.
- [ ] Tất cả caller, test và tài liệu bị ảnh hưởng đã được xử lý.
- [ ] Layer 1, Layer 2 và Layer 3 có evidence đúng phạm vi.
- [ ] Không có stub, placeholder, dead compatibility path hoặc task artifact sót lại.
- [ ] Feature state phản ánh đúng authority và verifier evidence.

## 10. Tài liệu tham chiếu

- [PEP 8 — Imports](https://peps.python.org/pep-0008/#imports)
- [Python — Errors and Exceptions](https://docs.python.org/3/tutorial/errors.html)
- [Python — Exception chaining](https://docs.python.org/3/tutorial/errors.html#exception-chaining)
- [Ruff — Rule selection](https://docs.astral.sh/ruff/linter/)
- [Ruff — Formatter](https://docs.astral.sh/ruff/formatter/)
- [Ruff PLC0415 — import-outside-top-level](https://docs.astral.sh/ruff/rules/import-outside-top-level/)
- [Ruff BLE001 — blind-except](https://docs.astral.sh/ruff/rules/blind-except/)
- [Ruff B036 — except BaseException](https://docs.astral.sh/ruff/rules/except-base-exception/)
- [Ruff RUF100 — unused-noqa](https://docs.astral.sh/ruff/rules/unused-noqa/)
