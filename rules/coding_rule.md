# Quy Chuẩn Lập Trình & Thiết Kế Phần Mềm (Senior AI Coding Standards)

> **Phạm vi áp dụng:** Tài liệu này là hợp đồng tiêu chuẩn kỹ thuật (Engineering Standards) bắt buộc cho mọi kỹ sư và mô hình AI tham gia phát triển mã nguồn trong dự án **Hermes Business Agent**.

---

## 1. Nguyên Tắc Cốt Lõi (Core Principles)

1. **PEP 8 là Luật Tuyệt Đối:** Mọi file Python phải tuân thủ chuẩn PEP 8.
2. **KISS & YAGNI (Đơn giản là trên hết):** Không xây dựng trừu tượng dự phòng (speculative abstractions), không tạo interface/factory chỉ cho 1 đối tượng, không thêm dependency mới khi thư viện chuẩn (stdlib) hoặc module hiện có giải quyết được.
3. **Mã Nguồn Tự Giải Thích (Self-Documenting):** Đặt tên biến, hàm rõ ràng theo đúng ngữ cảnh nghiệp vụ; dùng Type Hints đầy đủ cho các hàm công khai; chỉ viết docstring/comment khi giải thích lý do ("tại sao làm vậy") chứ không diễn giải lại cú pháp hiển nhiên.
4. **Xóa Bỏ Trước Khi Thêm Mới (Deletion Over Addition):** Ưu tiên rút gọn mã nguồn, loại bỏ dead code, giữ diff nhỏ nhất có thể (**Minimum Working Diff**).

---

## 2. Chuẩn Hóa Kiến Trúc Import (Import Architecture & Anti-Pattern Bans)

### ⛔ CẤM TUYỆT ĐỐI: Import Bên Trong Thân Hàm (In-Function Imports)
* **Quy tắc:** Mọi câu lệnh `import` và `from ... import ...` **bắt buộc phải nằm ở đầu file (module top-level)**.
* **Lý do:**
  - Import trong hàm gây lỗi nghiêm trọng về tầm vực biến (`NameError` khi hàm helper khác cần dùng module).
  - Làm chậm hiệu năng runtime do phải tra cứu import lặp đi lặp lại ở mỗi lượt gọi.
  - Phá vỡ khả năng kiểm tra tĩnh (static analysis) và công cụ format tự động (Ruff, Flake8).

### Thứ Tự Import Chuẩn (Import Ordering)
Theo chuẩn PEP 8, các khối import ở đầu file phải cách nhau đúng 1 dòng trống:
1. **Khối 1:** Thư viện chuẩn Python (Standard Library: `os`, `sys`, `json`, `pathlib`, `typing`, `dataclasses`, `datetime`,...).
2. **Khối 2:** Thư viện bên thứ ba (Third-party packages: `composio`, `pydantic`, `pytest`,...).
3. **Khối 3:** Module nội bộ của dự án (Local/Project modules: `tools.composio.*`, `tools.calendar.*`,...).

```python
# CHUẨN (DO THIS):
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import composio
from pydantic import BaseModel

from tools.composio.bridge import call_google

# SAI (DON'T DO THIS):
def fetch_data():
    import os          # ❌ CẤM: Import stdlib trong hàm
    from tools import x # ❌ CẤM: Import module trong hàm
```

### Xử Lý Optional Dependency & Dynamic Bridge Ở Phạm Vi Module
Khi một module phụ thuộc vào môi trường hoặc thư viện tùy chọn, xử lý tại **module level** bằng khối `try...except ImportError`:
```python
# CHUẨN: Xử lý ở module scope một lần duy nhất khi nạp file
_composio_bridge = None
try:
    from tools.composio import bridge as _composio_bridge
except (ImportError, ModuleNotFoundError):
    # Tìm kiếm đường dẫn dự án dự phòng (chỉ chạy ở module level)
    for cand in _candidate_src_dirs():
        target = cand / "tools" / "composio" / "bridge.py"
        if target.is_file():
            # Nạp động một lần duy nhất
            ...
```

### Hỗ Trợ Monkeypatching Trong Kiểm Thử
Tránh import trực tiếp các hàm có thể bị mock trong test theo kiểu `from module import func`. Hãy import theo tên module (`import module as mod`) để khi test dùng `monkeypatch.setattr(module, "func", mock_func)`, mã nguồn luôn trỏ tới mock handler chính xác.

---

## 3. Quản Lý Lỗi & An Toàn Biên (Error Handling & Fail-Closed Boundaries)

1. **Không Nuốt Lỗi (Never Swallow Exceptions):**
   - ❌ Tuyệt đối không viết `except Exception: pass` hoặc `except: pass` làm mất dấu vết lỗi.
   - ✅ Nếu bắt ngoại lệ không nghiêm trọng, **phải ghi log chẩn đoán** (`logger.debug(...)` hoặc `logger.warning(...)`).
2. **Đóng Chặt Khi Thiếu Quyền (Fail-Closed Security):**
   - Khi không xác định được danh tính người gọi (`principal_id`), token ủy quyền, hoặc quyền truy cập hòm thư/lịch: **bắt buộc phải từ chối (deny/raise) ngay lập tức**.
   - Không tự ý fallback về tài khoản mặc định, không đoán mò danh tính người dùng.
3. **Bảo Vệ Quyền Riêng Tư Trên Nền Tảng Nhắn Tin (DM-Only Enforcement):**
   - Các thao tác xem email, quản lý lịch, đọc thông tin cá nhân chỉ được phép thực thi trong chat riêng tư (Direct Message).
   - Kiểm tra trực tiếp qua thuộc tính ngữ cảnh: `getattr(source, "chat_type", "") != "dm"` và chuyển hướng về DM, không phụ thuộc vào whitelist tên nền tảng cứng nhắc.
4. **Khử Nhạy Cảm Dữ Liệu (Secret Scrubbing):**
   - Mọi token, API key, mật khẩu, Bearer header phải được lọc sạch (redacted) trước khi ghi log hoặc gửi về giao diện chat.

---

## 4. Thiết Kế Hướng Module Sâu (Deep Module Design)

1. **Giao Diện Đơn Giản, Triển Khai Mạnh Mẽ (Deep Modules):**
   - Interface bên ngoài của tool hoặc service càng ngắn gọn, dễ hiểu càng tốt.
   - Toàn bộ sự phức tạp (chuẩn hóa múi giờ, tra cứu kết nối, fallback toolkit `googlesuper` / `googlecalendar`, chuyển đổi ID) phải được đóng gói bên trong module.
2. **Bất Biến Theo Mặc Định (Immutability by Default):**
   - Ưu tiên sử dụng `@dataclass(frozen=True)` cho các cấu trúc dữ liệu hợp đồng nghiệp vụ (contracts, DTOs).
   - Đảm bảo dữ liệu không bị thay đổi ngầm (side-effects) khi truyền qua các tầng kiến trúc.

---

## 5. Quy Trình Kiểm Chứng 3 Lớp (Three-Layer Verification)

Không có tính năng hay bản sửa lỗi nào được coi là hoàn thành nếu chưa có bằng chứng kiểm thử cụ thể:

* **Layer 1: Kiểm Tra Cú Pháp & Schema (Static Check)**
  - Chạy `ruff check` hoặc kiểm tra cú pháp AST toàn diện.
  - Không có lỗi type, không còn biến hoặc import chưa sử dụng.
* **Layer 2: Kiểm Thử Hành Vi & Unit Test (Artifact Behavior)**
  - Chạy toàn bộ bộ test `pytest tests/` (100% test cases phải PASS).
  - Kiểm tra cả kịch bản thành công (happy paths) lẫn kịch bản biên/lỗi (edge cases).
* **Layer 3: Kiểm Chứng Thực Tế Biên Hệ Thống (System Boundary Verification)**
  - Chạy kiểm thử trực tiếp trên engine runtime thực tế (`hermes` host CLI / Desktop / Telegram Gateway).
  - Ghi nhận đầy đủ: Lệnh chạy, Timestamp UTC, Mã trạng thái (exit status), và kết quả trả về thực tế.

---

## 6. Checklist Tự Rà Soát Trước Khi Đưa Code Lên (Pre-Flight Checklist)

Trước khi commit hoặc bàn giao bất kỳ task nào, hãy tự trả lời 5 câu hỏi:
- [ ] 1. Toàn bộ `import` có nằm ở đầu file (top-level) không? Có câu lệnh `import` nào bị giấu trong hàm không?
- [ ] 2. Đoạn mã này có thực sự cần thiết không, hay thư viện chuẩn/code có sẵn đã làm được?
- [ ] 3. Có khối `try...except` nào đang âm thầm nuốt lỗi mà không có log không?
- [ ] 4. Khi gặp lỗi xác thực hoặc thiếu quyền, code có Fail-Closed an toàn không?
- [ ] 5. Toàn bộ test suite (`pytest`) có PASS 100% không?
