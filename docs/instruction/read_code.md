# Hướng dẫn Đọc Hiểu Mã Nguồn Hermes Business Agent

Tài liệu này cung cấp bản đồ kiến trúc toàn diện và lộ trình từng bước để đọc hiểu mã nguồn dự án **Hermes Business Agent**, đặc biệt tập trung vào hệ thống tích hợp **Google Workspace (Gmail & Google Calendar)** và cơ chế kết nối giữa mã nguồn nghiệp vụ với **Hermes Engine** tại `AppData\Local\hermes`.

---

## 1. 🏗️ Kiến Trúc Hệ Thống 2 Tầng (Two-Tier Architecture)

Hệ thống được tổ chức phân tầng rõ rệt giữa **Host Runtime (Động cơ máy chủ)** và **Business Plugins (Plugin nghiệp vụ)**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ TẦNG 1: HERMES ENGINE / GATEWAY (Host Runtime)                          │
│ Vị trí: %LOCALAPPDATA%\hermes\hermes-agent                             │
│                                                                         │
│  • Quản lý kết nối các nền tảng chat: Telegram, WhatsApp, Discord...    │
│  • Điều phối vòng lặp Agentic Loop (LLM chat completion, reasoning)     │
│  • Quản lý phiên làm việc & lịch sử hội thoại (gateway/session.py)      │
│  • Quản lý nạp plugin động (Dynamic Plugin Loader)                      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Tải động qua config.yaml
┌────────────────────────────────────▼────────────────────────────────────┐
│ TẦNG 2: MÃ NGUỒN NGHIỆP VỤ (Hermes Business Agent)                      │
│ Vị trí: C:\Hermes-Business-Agent\src                                   │
│                                                                         │
│  • Plugins: src/.hermes/plugins/ (email-connector, calendar-connector) │
│  • SDK Tích hợp: src/tools/composio/ (Gmail, Google Calendar)           │
│  • Bộ não chỉ dẫn: src/skills/ (prompt kỹ thuật cho LLM)               │
│  • Cấu hình & Chính sách: src/config/ (giờ làm việc, lookahead...)     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Nguyên tắc tương tác cốt lõi:
1. **Engine không chứa code nghiệp vụ cứng:** `hermes-agent` chỉ đóng vai trò khung điều phối.
2. **Nghiệp vụ nằm trong Plugins:** Toàn bộ code gửi mail, đọc lịch, tạo sự kiện nằm tại `src/` và được Hermes Gateway nạp vào lúc khởi động.
3. **Môi trường thực thi:** Khi deploy, CWD của Hermes là thư mục `src/` đã triển khai, không chạy từ thư mục gốc của repository.

---

## 2. 🔄 Dòng Chảy Dữ Liệu Thực Tế (End-to-End Execution Flow)

Ví dụ khi người dùng gửi tin nhắn trên Telegram:  
> *"Dời lịch Project web hôm nay từ 14:00 sang 14:30 đi"*

```
[1. Telegram DM] 
       │ 
       ▼
[2. Gateway Engine: hermes-agent] ── Bóc tách event, xác định nền tảng (telegram)
       │
       ▼
[3. Plugin Guard & Caller Context] ── `calendar-connector/calendar_caller.py`
       │                               - Xác thực chat riêng 1-1 (DM-only)
       │                               - Lấy principal_id: "telegram:default:7275339077"
       ▼
[4. AI Prompting (Skill)] ─────────── `src/skills/calendar/SKILL.md`
       │                               - LLM nhận diện ý định "dời lịch"
       │                               - Chọn tool `calendar_update_event`
       ▼
[5. Plugin Tool Dispatcher] ───────── `calendar_plugin_tools.py`
       │                               - Kiểm tra schema JSON
       │                               - Gọi `composio_calendar_patch_event()`
       ▼
[6. Composio Integration Core] ────── `src/tools/composio/calendar_tools.py`
       │                               - `format_user_id`: "telegram_7275339077"
       │                               - `resolve_account_target`: xác định hòm thư đích
       │                               - Kích hoạt multi_account session
       ▼
[7. Composio Cloud SDK & Google API] ─ Thực thi `GOOGLESUPER_PATCH_EVENT`
       │                               - Patch trực tiếp trên Google Calendar
       ▼
[8. Gateway Feedback Loop] ────────── Nhận Google Event ID & URL Google Meet thật,
                                       định dạng câu trả lời gửi về Telegram.
```

---

## 3. 🗺️ Lộ Trình Đọc Code Chi Tiết (Reading Roadmap)

Để nắm bắt toàn diện hệ thống từ ngoài vào trong, hãy đọc theo 6 bước tuần tự dưới đây:

### 📍 Bước 1: Bộ não chỉ dẫn cho AI (Prompt & Skill Layer)
Đọc để hiểu AI được huấn luyện cách nhận diện công cụ ra sao:
- `src/skills/email/SKILL.md`:
  - Quy tắc Tier 2 (Draft-Before-Commit): Soạn nháp trước khi gửi mail thật.
  - Các công cụ: `email_search`, `email_get_thread`, `email_create_draft`, `email_send`, `email_reply`.
- `src/skills/calendar/SKILL.md`:
  - Hướng dẫn dời lịch (`calendar_update_event`), tra cứu (`calendar_list_events`), xem chi tiết (`calendar_get_event`), tạo trực tiếp (`calendar_create_event`), và xóa lịch (`calendar_delete_event`).

### 📍 Bước 2: Khai báo Plugin (Plugin Registration)
Đọc để biết plugin được Hermes Gateway nạp như thế nào:
- `src/.hermes/plugins/email-connector/plugin.yaml`: Khai báo metadata, danh sách công cụ cung cấp (`provides_tools`), và hooks vòng đời.
- `src/.hermes/plugins/email-connector/__init__.py`: Hàm `register(ctx)` đăng ký công cụ và lệnh gạch chéo (`/connect-google`, `/mail_status`, `/disconnect-google`).
- `src/.hermes/plugins/calendar-connector/plugin.yaml` & `__init__.py`: Khai báo 9 công cụ lịch hoàn chỉnh.

### 📍 Bước 3: Tầng Định Danh & Bảo Vệ Quyền Riêng Tư (Caller Context)
Đọc để hiểu cách hệ thống bảo vệ dữ liệu cá nhân:
- `src/.hermes/plugins/email-connector/caller.py` & `calendar-connector/calendar_caller.py`:
  - `CallerContext`: Dataclass chứa `principal_id`, `platform`, `user_id`, `chat_id`.
  - Hàm `capture(event)`: Chỉ cho phép truy cập email và lịch trong **Chat riêng 1-1 (`chat_type == "dm"`)**. Nếu gọi trong Group Chat sẽ lập tức ném lỗi `DmOnlyError` và chuyển hướng người dùng về chat riêng.

### 📍 Bước 4: Tầng Schema & Xử Lý Tham Số (Schemas & Handlers)
Đọc để xem cách dữ liệu từ LLM được validate:
- `src/.hermes/plugins/email-connector/schemas.py` & `plugin_tools.py`:
  - `EMAIL_SEARCH_SCHEMA`: Hỗ trợ lọc theo query, số lượng, và `account_email`.
  - `EMAIL_SEND_SCHEMA`, `EMAIL_CREATE_DRAFT_SCHEMA`, `EMAIL_REPLY_SCHEMA`.
- `src/.hermes/plugins/calendar-connector/calendar_schemas.py` & `calendar_plugin_tools.py`:
  - `CALENDAR_LIST_EVENTS_SCHEMA`, `CALENDAR_GET_EVENT_SCHEMA`.
  - `CALENDAR_CREATE_DRAFT_EVENT_SCHEMA`: Lưu trữ `account_email` ngay từ lúc tạo nháp.
  - `CALENDAR_UPDATE_EVENT_SCHEMA`: Dời lịch và sửa thông tin sự kiện linh hoạt bằng patch semantics.
  - `CALENDAR_DELETE_EVENT_SCHEMA`: Hủy/xóa sự kiện.

### 📍 Bước 5: Tầng Thực Thi Tích Hợp Composio SDK v3 (Integration Core)
Đây là **trái tim kỹ thuật** của toàn bộ kết nối Google Workspace:
- `src/tools/composio/client.py`:
  - `get_composio_client()`: Singleton quản lý kết nối Composio.
  - `format_user_id()`: Chuyển đổi định danh `principal_id` sang Composio Entity ID (`telegram_7275339077`, `whatsapp_849...`, `discord_...`).
- `src/tools/composio/auth.py`:
  - `initiate_google_connection()`: Sinh liên kết xác thực Google OAuth 2.0 đa dịch vụ (Gmail + Calendar qua toolkit `googlesuper`).
  - `get_user_emails()`: Truy vấn danh sách hòm thư đã liên kết qua `GOOGLESUPER_GET_PROFILE` (lưu cache tại `~/.hermes/composio_account_emails.json`).
  - `resolve_account_target()`: Tự động phân giải mục tiêu tài khoản (theo email chính xác, username, hoặc số thứ tự).
  - `disconnect_user()`: Thu hồi và xóa tài khoản liên kết (hỗ trợ xóa đơn lẻ hoặc xóa tất cả).
- `src/tools/composio/mail_tools.py`:
  - `composio_mail_search()`: Sử dụng `GMAIL_FETCH_EMAILS`.
  - `composio_mail_send()`: Sử dụng `GMAIL_SEND_EMAIL`.
  - `composio_mail_create_draft()`: Sử dụng `GMAIL_CREATE_EMAIL_DRAFT`.
  - `composio_mail_reply()`: Sử dụng `GMAIL_REPLY_TO_THREAD`.
- `src/tools/composio/calendar_tools.py`:
  - `_normalize_event_data()`: Chuẩn hóa payload trả về từ `response_data`, lấy chính xác Google Event ID và URL Google Meet.
  - `composio_calendar_list_events()`: Sử dụng `GOOGLESUPER_EVENTS_LIST`.
  - `composio_calendar_get_event()`: Sử dụng `GOOGLESUPER_EVENTS_GET`.
  - `composio_calendar_create_event()`: Sử dụng `GOOGLESUPER_CREATE_EVENT`.
  - `composio_calendar_patch_event()`: Sử dụng `GOOGLESUPER_PATCH_EVENT` (dời lịch, sửa địa điểm/tiêu đề).
  - `composio_calendar_delete_event()`: Sử dụng `GOOGLESUPER_DELETE_EVENT`.
  - `composio_calendar_find_free_slots()`: Sử dụng `GOOGLESUPER_FIND_FREE_SLOTS`.

### 📍 Bước 6: Tầng Kiểm Thử & Verification Gates
Đọc để biết cách hệ thống tự kiểm tra và bảo đảm chất lượng:
- `tests/verify_email_intake.py`: Kiểm thử 2 lớp cho luồng Email.
- `tests/verify_calendar.py`: Kiểm thử 2 lớp cho luồng Calendar (38 tests).
- `tests/verify_composio.py`: Kiểm thử các adapter Composio (25 tests).

---

## 4. 🔑 Các Khái Niệm Kỹ Thuật Quan Trọng

| Khái niệm | Ý nghĩa trong hệ thống |
| :--- | :--- |
| **`principal_id`** | Chuỗi định danh chuẩn quốc tế của Hermes: `<platform>:<profile>:<user_id>`. Giúp phân tách tuyệt đối giữa người dùng của các nền tảng khác nhau. |
| **Dual-Slug Fallback** | Cơ chế gọi `GOOGLESUPER_*` trước, nếu tài khoản liên kết theo gói rời thì tự động fallback sang `GOOGLECALENDAR_*` / `GMAIL_*` mà không làm gián đoạn người dùng. |
| **Multi-Account Routing** | Cho phép 1 người dùng liên kết cùng lúc nhiều email Google (vd: 1 email công việc, 1 email cá nhân). Mọi tool đều nhận `account_email` để chọn đúng hòm thư thao tác. |
| **Draft Idempotency** | Bản nháp lịch được tính toán hash `idempotency_key` (dựa trên principal_id, thời gian, tiêu đề) để chống việc người dùng bấm xác nhận 2 lần gây trùng lặp sự kiện. |
| **Three-Layer Verification** | Tiêu chuẩn kiểm thử nghiêm ngặt của Hermes: Layer 1 (Static/Contract check) -> Layer 2 (Mock/Behavioral test) -> Layer 3 (System/Live integration test). |

---

## 5. 🛠️ Cẩm Nang Vận Hành & Gỡ Lỗi (Troubleshooting)

### Cache lưu ở đâu?
- Danh sách mapping giữa mã kết nối Composio và email được lưu tại:
  `~/.hermes/composio_account_emails.json` (Windows: `C:\Users\ADMIN\.hermes\composio_account_emails.json`).

### Kiểm tra Gateway đang chạy:
```bash
# Xem tiến trình Gateway:
powershell -Command "Get-CimInstance Win32_Process -Filter \"CommandLine like '%gateway%run%'\" | Select-Object ProcessId, CommandLine"
```

### Chạy kiểm thử xác thực:
```bash
# Kiểm tra Email:
src/.venv/Scripts/python.exe tests/verify_email_intake.py --layer 1
src/.venv/Scripts/python.exe tests/verify_email_intake.py --layer 2

# Kiểm tra Calendar:
src/.venv/Scripts/python.exe tests/verify_calendar.py --layer 1
src/.venv/Scripts/python.exe tests/verify_calendar.py --layer 2

# Kiểm tra Composio:
src/.venv/Scripts/python.exe tests/verify_composio.py --layer 1
src/.venv/Scripts/python.exe tests/verify_composio.py --layer 2
```

---
*Tài liệu được cập nhật chuẩn xác theo phiên bản kiến trúc Composio v3 SDK và Hermes Gateway Protocol (Tháng 09/2026).*
