# Báo Cáo Triển Khai Tính Năng: Google Calendar, YouTube Channel & TikTok Posting API

- **Ngày thực hiện:** 31/08/2026
- **Tác giả:** Hermes Engineering Agent
- **Nhánh Git:** `feature/h013-calendar-youtube-tiktok`
- **Mã tính năng:** `H013` (Google Calendar), `H014` (YouTube Channel), `H015` (TikTok Posting API)
- **Trạng thái kiểm thử:** 100% PASS (56 unit & integration tests mới, zero regression)

---

## 1. Tổng quan mục tiêu và phạm vi

Theo yêu cầu nghiệp vụ của khách hàng, hệ thống Hermes Agent được mở rộng bổ sung 3 module kết nối kênh chính thức (Official Connectors) hoạt động trực tiếp qua Telegram DM với cơ chế phân quyền theo caller (`CallerContextRegistry`), bảo đảm nguyên tắc Tier 2 (Draft-Before-Commit), không lưu trữ thông tin đăng nhập trong Git và không sử dụng grey automation / browser bot đối với tài khoản mạng xã hội.

---

## 2. Chi tiết 3 tính năng đã hoàn thành

### 📅 Mục 3: Google Calendar Integration (`H013`)

#### 1. Chức năng chính
- **Tra cứu lịch trình (`calendar_list_events`):** Liệt kê các sự kiện, cuộc hẹn trong ngày hoặc khoảng thời gian tuỳ chọn (ISO 8601), trả về tiêu đề, thời gian bắt đầu/kết thúc, địa điểm, danh sách người tham gia.
- **Tìm slot trống tự động (`calendar_find_free_slots`):** Tính toán các khoảng thời gian trống khả dụng trong ngày dựa trên giờ làm việc cấu hình (mặc định `09:00 - 18:00 ICT`), tự động loại trừ các sự kiện bận (busy intervals), lọc theo thời lượng cuộc họp tối thiểu (mặc định 30 phút).
- **Soạn bản nháp sự kiện Tier 2 (`calendar_create_draft_event`):** Chuẩn bị bản nháp cuộc hẹn với tiêu đề, thời gian, mô tả, người tham dự và mã chống trùng lặp (`idempotency_key`). Không tạo sự kiện trên Google Calendar khi chưa có sự xác nhận của người dùng.
- **Xác nhận tạo lịch (`calendar_confirm_event`):** Khi người dùng duyệt trên Telegram, hệ thống gọi Google Calendar REST API (`https://www.googleapis.com/auth/calendar.events`) để tạo sự kiện chính thức, lưu mã sự kiện (`Google Event ID`) và đường dẫn Google Calendar làm bằng chứng máy (machine-verifiable evidence).
- **Trạng thái kết nối (`calendar_status`):** Kiểm tra tình trạng kết nối lịch và tên lịch chính (`primary calendar`).

#### 2. Cấu trúc mã nguồn
- `src/config/calendar_policy.json`: Cấu hình giới hạn thời gian (tối đa 30 ngày lookahead, 15 - 480 phút thời lượng sự kiện, giờ làm việc).
- `src/tools/calendar/contracts.py`: Dataclasses `CalendarEvent`, `EventDraft`, `FreeSlot`, `CalendarConnection`, `EventVerification`.
- `src/tools/calendar/policy.py`: Bộ kiểm tra tính hợp lệ của thời gian, thời lượng và giới hạn tương lai.
- `src/tools/calendar/google_calendar.py`: Client tương tác với Google Calendar REST API v3 (hỗ trợ chế độ offline mock determinism).
- `src/tools/calendar/store.py`: Cơ sở dữ liệu SQLite (`.runtime/calendar/calendar.sqlite3`) lưu trữ bản nháp, trạng thái chuyển đổi và audit log.
- `src/tools/calendar/service.py`: Service điều phối logic nghiệp vụ, tìm slot trống và quản lý vòng đời bản nháp.
- `src/tools/calendar/cli.py`: Giao diện dòng lệnh phục vụ kiểm thử độc lập.
- `src/.hermes/plugins/calendar-connector/`: Plugin độc lập đăng ký 5 công cụ và các hook bảo vệ Telegram DM.
- `src/skills/calendar/SKILL.md`: Tài liệu hướng dẫn runtime skill và quy tắc Tier 2.

---

### 🎥 Mục 4: YouTube Channel Video Automation (`H014`)

#### 1. Chức năng chính
- **Kiểm tra trạng thái kênh (`youtube_channel_status`):** Đọc thông tin kênh YouTube chính thức của người dùng: tên kênh, ID kênh, custom URL, số lượng người đăng ký (subscriber count) và tổng số video.
- **Danh sách video gần nhất (`youtube_list_videos`):** Liệt kê các video trên kênh kèm tiêu đề, lượt xem, ngày xuất bản và chế độ hiển thị (`public`, `unlisted`, `private`).
- **Soạn bản nháp video Tier 2 (`youtube_create_draft_video`):** Chuẩn bị tiêu đề, mô tả, danh sách tags/keywords, chế độ hiển thị mặc định (`unlisted`), đường dẫn file video (.mp4, .mov, .webm) và ảnh thumbnail.
- **Tải video lên YouTube (`youtube_upload_video`):** Sau khi người dùng duyệt trên Telegram, hệ thống thực hiện upload video lên YouTube thông qua giao thức upload chính thức của Google YouTube Data API v3, trả về Video ID và đường dẫn xem video (`https://www.youtube.com/watch?v=...`).
- **Cập nhật metadata (`youtube_update_video_metadata`):** Chỉnh sửa tiêu đề, mô tả, tags hoặc quyền riêng tư của video đã tồn tại.

#### 2. Cấu trúc mã nguồn
- `src/config/youtube_policy.json`: Cấu hình giới hạn video (dung lượng tối đa 1GB, đuôi file cho phép, tiêu đề <= 100 ký tự, mô tả <= 5000 ký tự, tags <= 30).
- `src/tools/youtube/contracts.py`: Dataclasses `YouTubeVideo`, `VideoDraft`, `ChannelInfo`, `VideoVerification`.
- `src/tools/youtube/policy.py`: Bộ xác thực metadata và file video.
- `src/tools/youtube/youtube_client.py`: Client gọi Google YouTube Data API v3.
- `src/tools/youtube/store.py`: Cơ sở dữ liệu SQLite (`.runtime/youtube/youtube.sqlite3`) lưu trữ video drafts và audit log.
- `src/tools/youtube/service.py`: Service điều phối staging metadata và upload video.
- `src/tools/youtube/cli.py`: Giao diện dòng lệnh phục vụ kiểm thử.
- `src/.hermes/plugins/youtube-connector/`: Plugin đăng ký 5 công cụ YouTube.
- `src/skills/youtube/SKILL.md`: Runtime skill hướng dẫn agent.

---

### 📱 Mục 5: TikTok Content Posting API Integration (`H015`)

#### 1. Chức năng chính
- **Thông tin Creator (`tiktok_creator_info`):** Truy vấn thông tin tài khoản TikTok Creator kết nối chính thức qua endpoint `/v2/post/publish/creator_info/query/`: nickname, username, avatar, thời lượng video tối đa, các quyền riêng tư được phép.
- **Soạn bản nháp bài đăng TikTok Tier 2 (`tiktok_create_draft_post`):** Chuẩn bị caption, hashtags (tối đa 2200 ký tự), đường dẫn file video, mức độ riêng tư (`PUBLIC_TO_EVERYONE`, `MUTUAL_FOLLOW_FRIENDS`, `SELF_ONLY`, `FOLLOWER_OF_CREATOR`), tuỳ chọn bật/tắt comment, duet, stitch và gắn nhãn nội dung thương mại.
- **Khởi tạo đăng video (`tiktok_publish_video`):** Khởi tạo tiến trình xuất bản video qua official Content Posting API (`/v2/post/publish/video/init/`), trả về `publish_id`.
- **Theo dõi tiến độ đăng (`tiktok_post_status`):** Truy vấn trạng thái xử lý video (`/v2/post/publish/status/fetch/`): `PROCESSING_UPLOAD`, `SUCCESS`, `FAILED` và trả về post ID khi hoàn tất.

#### 2. Cấu trúc mã nguồn
- `src/config/tiktok_policy.json`: Cấu hình giới hạn TikTok (caption <= 2200 ký tự, dung lượng tối đa 1GB, đuôi file cho phép).
- `src/tools/tiktok/contracts.py`: Dataclasses `TikTokCreatorInfo`, `TikTokPostDraft`, `TikTokPostResult`.
- `src/tools/tiktok/policy.py`: Bộ kiểm tra định dạng và quyền riêng tư TikTok.
- `src/tools/tiktok/tiktok_client.py`: Client gọi TikTok Content Posting API v2.
- `src/tools/tiktok/store.py`: Cơ sở dữ liệu SQLite (`.runtime/tiktok/tiktok.sqlite3`) lưu trữ post drafts và audit log.
- `src/tools/tiktok/service.py`: Service điều phối staging và publishing.
- `src/tools/tiktok/cli.py`: Giao diện dòng lệnh kiểm thử.
- `src/.hermes/plugins/tiktok-connector/`: Plugin đăng ký 4 công cụ TikTok.
- `src/skills/tiktok/SKILL.md`: Runtime skill hướng dẫn agent.

---

## 3. Danh sách các file tạo mới và sửa đổi

### Files tạo mới (33 files)
```text
src/config/
├── calendar_policy.json
├── youtube_policy.json
└── tiktok_policy.json

src/tools/
├── calendar/
│   ├── __init__.py
│   ├── contracts.py
│   ├── policy.py
│   ├── google_calendar.py
│   ├── store.py
│   ├── service.py
│   └── cli.py
├── youtube/
│   ├── __init__.py
│   ├── contracts.py
│   ├── policy.py
│   ├── youtube_client.py
│   ├── store.py
│   ├── service.py
│   └── cli.py
└── tiktok/
    ├── __init__.py
    ├── contracts.py
    ├── policy.py
    ├── tiktok_client.py
    ├── store.py
    ├── service.py
    └── cli.py

src/.hermes/plugins/
├── calendar-connector/
│   ├── plugin.yaml
│   ├── schemas.py
│   ├── caller.py
│   ├── guard.py
│   ├── client.py
│   ├── plugin_tools.py
│   └── __init__.py
├── youtube-connector/
│   ├── plugin.yaml
│   ├── schemas.py
│   ├── caller.py
│   ├── guard.py
│   ├── client.py
│   ├── plugin_tools.py
│   └── __init__.py
└── tiktok-connector/
    ├── plugin.yaml
    ├── schemas.py
    ├── caller.py
    ├── guard.py
    ├── client.py
    ├── plugin_tools.py
    └── __init__.py

src/skills/
├── calendar/SKILL.md
├── youtube/SKILL.md
└── tiktok/SKILL.md

tests/
├── google_calendar/
│   ├── __init__.py
│   ├── test_contracts.py
│   ├── test_policy.py
│   ├── test_store.py
│   ├── test_google_client.py
│   ├── test_service.py
│   └── test_plugin.py
├── youtube_tool/
│   ├── __init__.py
│   ├── test_contracts.py
│   ├── test_policy.py
│   ├── test_store.py
│   ├── test_client.py
│   ├── test_service.py
│   └── test_plugin.py
├── tiktok_tool/
│   ├── __init__.py
│   ├── test_contracts.py
│   ├── test_policy.py
│   ├── test_store.py
│   ├── test_client.py
│   ├── test_service.py
│   └── test_plugin.py
├── verify_calendar.py
├── verify_youtube.py
└── verify_tiktok.py
```

### Files cập nhật (2 files)
- `src/AGENTS.md`: Khai báo 3 năng lực mới `/calendar`, `/youtube`, `/tiktok`.
- `feature-list.json`: Khai báo các tính năng `H013`, `H014`, `H015` với đầy đủ lệnh kiểm thử Layer 1/2 và điều kiện mở khoá Layer 3.
- `PROGRESS.md`: Ghi nhận tiến độ chi tiết.

---

## 4. Hướng dẫn chạy và kiểm thử (How to Run & Verify)

### 1. Chạy bộ kiểm thử tự động Layer 1 và Layer 2
Từ thư mục gốc dự án:

```bash
# 1. Kiểm thử Google Calendar (21 tests)
python tests/verify_calendar.py --layer 1
python tests/verify_calendar.py --layer 2

# 2. Kiểm thử YouTube Channel (18 tests)
python tests/verify_youtube.py --layer 1
python tests/verify_youtube.py --layer 2

# 3. Kiểm thử TikTok Posting API (17 tests)
python tests/verify_tiktok.py --layer 1
python tests/verify_tiktok.py --layer 2
```

### 2. Chạy hồi quy toàn bộ hệ thống (Zero Regressions)
```bash
# Kiểm thử toàn bộ các bộ test hiện có (Email, Research, Knowledge, Progress, Calendar, YouTube, TikTok)
cd src
C:/Users/ADMIN/.local/bin/uv.exe run --frozen python ../tests/verify_email_intake.py --layer 2
C:/Users/ADMIN/.local/bin/uv.exe run --frozen python ../tests/verify_research.py --layer 1
C:/Users/ADMIN/.local/bin/uv.exe run --frozen python ../tests/verify_research.py --layer 2
C:/Users/ADMIN/.local/bin/uv.exe run --frozen python ../tests/verify_knowledge.py --layer 1
C:/Users/ADMIN/.local/bin/uv.exe run --frozen python ../tests/verify_knowledge.py --layer 2
C:/Users/ADMIN/.local/bin/uv.exe run --frozen python ../tests/verify_progress.py --layer 1
C:/Users/ADMIN/.local/bin/uv.exe run --frozen python ../tests/verify_progress.py --layer 2
```

### 3. Kiểm thử qua CLI độc lập
```bash
# Calendar CLI:
python src/tools/calendar/cli.py status
python src/tools/calendar/cli.py free --date 2026-09-01 --duration 30

# YouTube CLI:
python src/tools/youtube/cli.py status
python src/tools/youtube/cli.py list --limit 5

# TikTok CLI:
python src/tools/tiktok/cli.py creator
```

---

## 5. Kết quả kiểm tra chất lượng (Quality Gates)

- **Cú pháp & Định dạng:** `git diff --check` sạch hoàn toàn, không có lỗi whitespace hay conflict.
- **Biên dịch Python:** `uv run --frozen python -m compileall -q tools .hermes/plugins` pass 100% trên Python 3.12.
- **Bảo mật & Phân quyền:** Tất cả các công cụ đều cưỡng chế chạy qua `CallerContextRegistry` (chỉ nhận lệnh trong Telegram DM, không cho phép truy cập chéo giữa các user).
- **Trạng thái tính năng:** Các tính năng `H013`, `H014`, `H015` tuân thủ đúng quy tắc WIP=1, sẵn sàng cho bước kiểm thử thực tế Layer 3 khi có tài khoản thật.
