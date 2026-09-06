# Hướng Dẫn Triển Khai Production & Vận Hành Hermes Agent (Chuẩn DevOps)

Tài liệu này cung cấp hướng dẫn toàn diện từ việc **Dựng mới một máy ảo Linux VPS (Zero-Friction Bootstrap)**, **Cập nhật mã nguồn 1-Click**, **Triển khai qua Docker**, **Cấu hình lưu trữ Uploads vĩnh viễn**, và **Giám sát hệ thống**.

---

## Mục Lục
1. [Khởi tạo VPS Linux Mới từ Con số 0 (1-Click Bootstrap)](#1-khởi-tạo-vps-linux-mới-từ-con-số-0-1-click-bootstrap)
2. [Triển khai thay thế bằng Docker Compose (Khuyên dùng đa đám mây)](#2-triển-khai-thay-thế-bằng-docker-compose)
3. [Quy trình Cập nhật Code Hàng Ngày (1-Click Update)](#3-quy-trình-cập-nhật-code-hàng-ngày-1-click-update)
4. [Cơ chế Lưu trữ Uploads & Ảnh Vĩnh Viễn](#4-cơ-chế-lưu-trữ-uploads--ảnh-vĩnh-viễn)
5. [Tải Deliverables (.xlsx, .pptx, .html) từ VPS về máy tính](#5-tải-deliverables-từ-vps-về-máy-tính)
6. [Giám sát Trạng thái & Live Logs](#6-giám-sát-trạng-thái--live-logs)

---

## 1. Khởi tạo VPS Linux Mới từ Con số 0 (1-Click Bootstrap)

Khi bạn vừa tạo một máy ảo Linux mới (Ubuntu 22.04 hoặc 24.04 LTS trên Azure, AWS, Hetzner, DigitalOcean), quy trình gồm 3 bước:

### Bước 1: SSH vào VPS và Clone Repository
```bash
ssh -i /path/to/key.pem <USER>@<IP_VPS>

git clone https://github.com/BPhucKHMT/Hermes_Business_Agent.git ~/Hermes-Business-Agent
cd ~/Hermes-Business-Agent
```

### Bước 2: Tạo file `.env` chứa API Keys bí mật
```bash
cp .env.example ~/.hermes.env
nano ~/.hermes.env
```
*(Điền các khóa bí mật của bạn: `TELEGRAM_BOT_TOKEN`, `AZURE_FOUNDRY_API_KEY`, `TAVILY_API_KEY`, `COMPOSIO_API_KEY`)*

### Bước 3: Chạy script tự động hóa toàn bộ
```bash
bash deploy_vm.sh
```

**Script `deploy_vm.sh` sẽ tự động thực hiện 100%:**
- Cài đặt toàn bộ apt packages & hơn 20 thư viện C cho Playwright/Chromium headless.
- Cài đặt Node.js 20 LTS và global `agent-browser`.
- Cài đặt `uv` và Python 3.12 cô lập.
- Cài đặt upstream `hermes-agent` CLI.
- Đồng bộ thư viện Python của dự án qua `uv sync --frozen`.
- Tạo **Symlink** tự động cho 4 plugins (`email`, `calendar`, `youtube`, `tiktok`) và `SOUL.md`.
- Sinh cấu hình `config.yaml` chuẩn Linux (không còn bất kỳ đường dẫn Windows hardcode nào).
- Đăng ký `systemd` service (`hermes-gateway.service`), kích hoạt `enable-linger` và khởi động bot ngầm 24/7.
- Tự chạy bộ self-test kiểm tra toàn bộ dịch vụ.

---

## 2. Triển khai thay thế bằng Docker Compose

Nếu bạn muốn chạy dạng container để độc lập 100% với hệ điều hành của máy ảo:

```bash
cd ~/Hermes-Business-Agent
cp .env.example .env
nano .env  # Điền các API keys

# Khởi động container
docker compose up -d

# Xem log live
docker compose logs -f
```

---

## 3. Quy trình Cập nhật Code Hàng Ngày (1-Click Update)

Mỗi khi bạn sửa code trên laptop và `git push` lên GitHub, để cập nhật VPS bạn chỉ cần:

```bash
cd ~/Hermes-Business-Agent
bash update_vm.sh
```

Script sẽ tự động:
1. `git pull` kéo code mới nhất.
2. `uv sync --frozen` cập nhật thư viện nếu có thay đổi.
3. Tự restart service `hermes-gateway` qua systemctl.
4. Hiển thị trạng thái gateway đang chạy.
*(Toàn bộ diễn ra trong vài giây, không cần copy thủ công plugin hay sửa bất kỳ file config nào!)*

---

## 4. Cơ chế Lưu trữ Uploads & Ảnh Vĩnh Viễn

Mặc định, Hermes tự dọn dẹp các ảnh tạm sau 24h. Để lưu trữ dài hạn (90 ngày hoặc vĩnh viễn):

Trong `~/.hermes/.env` (hoặc `.env`):
```bash
# Thời gian lưu trữ cache ảnh/tài liệu (giờ: 2160 = 90 ngày; 0 = vĩnh viễn)
HERMES_MEDIA_CACHE_MAX_AGE_HOURS=2160

# Thư mục lưu trữ tài liệu khách gửi vĩnh viễn
HERMES_PERMANENT_UPLOADS_DIR=/home/<USER>/.hermes/uploads
```

---

## 5. Tải Deliverables từ VPS về máy tính

Khi Bot tạo file Excel (.xlsx), Slide (.pptx), Báo cáo (.html) hoặc khách gửi ảnh quan trọng lên VPS:

```powershell
# Tải 1 file cụ thể về Downloads trên máy tính:
scp -i "C:\path\key.pem" <USER>@<IP_VPS>:~/.hermes/deliverables/general/report.xlsx "C:\Users\ADMIN\Downloads\"

# Tải toàn bộ ảnh khách gửi trên Telegram về máy:
scp -r -i "C:\path\key.pem" <USER>@<IP_VPS>:~/.hermes/cache/images/ "C:\Users\ADMIN\Downloads\Telegram_Images\"
```

---

## 6. Giám sát Trạng thái & Live Logs

```bash
# Kiểm tra trạng thái gateway
hermes gateway status

# Xem log trực tiếp thời gian thực
journalctl -u hermes-gateway -f

# Khởi động lại dịch vụ thủ công nếu cần
sudo systemctl restart hermes-gateway
```
