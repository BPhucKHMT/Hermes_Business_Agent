# Hướng Dẫn Triển Khai Production & Quản Lý File Hermes Agent

Tài liệu này cung cấp hướng dẫn từng bước từ việc **Push mã nguồn từ Local lên GitHub**, **Pull và cập nhật trên Production VPS**, **Cấu hình lưu trữ tệp tải lên vĩnh viễn (Upload Retention)**, và **Cách tải tệp/báo cáo từ Production VPS về máy tính cá nhân**.

---

## 📑 Mục Lục
1. [Chuẩn bị & Push từ máy Local (Dev)](#1-chuẩn-bị--push-từ-máy-local-dev)
2. [Pull và Cập nhật trên Production VPS](#2-pull-và-cập-nhật-trên-production-vps)
3. [Cơ chế Lưu trữ Uploads & Ảnh Vĩnh Viễn](#3-cơ-chế-lưu-trữ-uploads--ảnh-vĩnh-viễn)
4. [Hướng dẫn Tải file & Deliverables từ VPS về máy cá nhân](#4-hướng-dẫn-tải-file--deliverables-từ-vps-về-máy-cá-nhân)
5. [Kiểm tra Trạng thái & Giám sát Live Logs](#5-kiểm-tra-trạng-thái--giám-sát-live-logs)

---

## 1. Chuẩn bị & Push từ máy Local (Dev)

Trước khi đẩy code lên production, chạy bộ kiểm chứng để đảm bảo 100% không có lỗi hồi quy:

```bash
# 1. Chạy toàn bộ 16 bộ test kiểm chứng
"C:/Hermes-Business-Agent/src/.venv/Scripts/python.exe" -c "
import subprocess, sys
py = sys.executable
cmds = [
    [py, 'tests/verify_calendar.py', '--layer', '1'],
    [py, 'tests/verify_calendar.py', '--layer', '2'],
    [py, 'tests/verify_youtube.py', '--layer', '1'],
    [py, 'tests/verify_youtube.py', '--layer', '2'],
    [py, 'tests/verify_tiktok.py', '--layer', '1'],
    [py, 'tests/verify_tiktok.py', '--layer', '2'],
    [py, 'tests/verify_email_intake.py', '--layer', '1'],
    [py, 'tests/verify_email_intake.py', '--layer', '2'],
    [py, 'tests/verify_research.py', '--layer', '1'],
    [py, 'tests/verify_research.py', '--layer', '2'],
    [py, 'tests/verify_progress.py', '--layer', '1'],
    [py, 'tests/verify_progress.py', '--layer', '2'],
    [py, 'tests/verify_knowledge.py', '--layer', '1'],
    [py, 'tests/verify_knowledge.py', '--layer', '2'],
    [py, 'tests/verify_telegram_album.py', '--layer', '1'],
    [py, 'tests/verify_telegram_album.py', '--layer', '2'],
]
for c in cmds:
    res = subprocess.run(c, capture_output=True, text=True)
    if res.returncode != 0:
        print('FAIL:', ' '.join(c)); sys.exit(1)
print('ALL 16 TEST SUITES PASSED 100%!')
"

# 2. Stage và Push lên GitHub
git add .
git commit -m "feat(release): deploy senior audit, multi-channel tools, and permanent upload retention"
git push origin feature/h013-calendar-youtube-tiktok
```

---

## 2. Pull và Cập nhật trên Production VPS

Kết nối SSH vào VPS và cập nhật hệ thống:

```bash
# 1. Đăng nhập SSH vào VPS
ssh -i "C:\Users\ADMIN\Downloads\hermes-agent-VM_key.pem" azureuser@<IP_VPS_CUA_BAN>

# 2. Chuyển vào thư mục repo và kéo code mới nhất
cd ~/Hermes-Business-Agent
git fetch origin
git checkout feature/h013-calendar-youtube-tiktok
git pull origin feature/h013-calendar-youtube-tiktok

# 3. Đồng bộ SOUL.md và Plugins mới sang thư mục Runtime
cp src/SOUL.md ~/.hermes/SOUL.md
cp -r src/.hermes/plugins/* ~/.hermes/plugins/

# 4. Cập nhật thư viện Python (nếu có bổ sung dependencies)
cd ~/Hermes-Business-Agent/src
~/.local/bin/uv sync --frozen

# 5. Khởi động lại Hermes Gateway
sudo systemctl restart hermes-gateway 2>/dev/null || hermes gateway restart

# 6. Kiểm tra gateway đã online
hermes gateway status
```

---

## 3. Cơ chế Lưu trữ Uploads & Ảnh Vĩnh Viễn

Mặc định, Hermes tự dọn dẹp các ảnh tạm sau 24h. Để **lưu trữ dài hạn (90 ngày hoặc vĩnh viễn)** và tự động lưu trữ tài liệu khách gửi:

### 3.1. Cấu hình thời gian lưu trữ trong `~/.hermes/.env` (hoặc `src/.env`):
Thêm các dòng sau vào file `.env` trên VPS:
```bash
# Thời gian lưu trữ cache ảnh/tài liệu (tính bằng giờ: 2160 = 90 ngày; 0 = vĩnh viễn không xoá)
HERMES_MEDIA_CACHE_MAX_AGE_HOURS=2160

# Thư mục lưu trữ tài liệu khách gửi vĩnh viễn
HERMES_PERMANENT_UPLOADS_DIR=/home/azureuser/.hermes/uploads
```

### 3.2. Cấu hình thư mục phân loại:
- **Ảnh khách gửi qua Telegram:** Lưu tại `~/.hermes/cache/images/`
- **File tài liệu khách gửi (.xlsx, .pdf, .docx):** Lưu tại `~/.hermes/cache/documents/` và `~/.hermes/uploads/`
- **File báo cáo/kết quả do Bot tạo ra:** Lưu tại `~/.hermes/deliverables/general/` (cách ly hoàn toàn khỏi các folder nội bộ).

---

## 4. Hướng dẫn Tải file & Deliverables từ VPS về máy cá nhân

Khi Bot tạo file Excel (.xlsx), Slide (.pptx), Báo cáo (.html) hoặc khách gửi ảnh quan trọng lên VPS, bạn có 3 cách kéo file về máy tính:

### 🔹 Cách 1: Dùng lệnh SCP trên PowerShell / Terminal (Nhanh nhất)

Chạy trực tiếp trên máy tính cá nhân của bạn:

```powershell
# 1. Tải 1 file Excel cụ thể từ VPS về thư mục Downloads của máy bạn:
scp -i "C:\Users\ADMIN\Downloads\hermes-agent-VM_key.pem" azureuser@<IP_VPS>:~/.hermes/deliverables/general/report.xlsx "C:\Users\ADMIN\Downloads\"

# 2. Tải toàn bộ ảnh do người dùng gửi trên Telegram về máy bạn:
scp -r -i "C:\Users\ADMIN\Downloads\hermes-agent-VM_key.pem" azureuser@<IP_VPS>:~/.hermes/cache/images/ "C:\Users\ADMIN\Downloads\Telegram_Images\"

# 3. Tải toàn bộ file tài liệu / báo cáo đã tạo về máy bạn:
scp -r -i "C:\Users\ADMIN\Downloads\hermes-agent-VM_key.pem" azureuser@<IP_VPS>:~/.hermes/deliverables/ "C:\Users\ADMIN\Downloads\Hermes_Deliverables\"
```

---

### 🔹 Cách 2: Dùng WinSCP / FileZilla (Giao diện đồ họa kéo-thả)

1. Mở **WinSCP** hoặc **FileZilla**.
2. **Host name:** `<IP_VPS>` | **Port:** `22` | **User name:** `azureuser`
3. Trong phần **Advanced $\rightarrow$ Authentication $\rightarrow$ Private key file**: Chọn file `hermes-agent-VM_key.pem` (hoặc chuyển sang `.ppk` nếu WinSCP yêu cầu).
4. **Bật hiển thị file ẩn:** Nhấn `Ctrl + Alt + H` (trên WinSCP) để thấy thư mục ẩn `.hermes/`.
5. Duyệt đến thư mục:
   - `~/.hermes/cache/images/` (ảnh khách gửi)
   - `~/.hermes/deliverables/general/` (báo cáo, slide, excel do bot tạo)
   - Kéo thả file về máy tính cực kỳ thuận tiện.

---

### 🔹 Cách 3: Nhận file trực tiếp qua Telegram (Tự động)

- Khi bot hoàn thành báo cáo (Excel/Slide/Word), bot sẽ phát directive:
  `MEDIA:/home/azureuser/.hermes/deliverables/general/Ten_File.xlsx`
- **Hermes Gateway sẽ tự động upload và gửi file đính kèm trực tiếp vào khung chat Telegram cho bạn và khách hàng tải về bằng 1 click.**

---

## 5. Kiểm tra Trạng thái & Giám sát Live Logs

Sau khi deploy, theo dõi hoạt động thực tế trên VPS bằng các lệnh sau:

```bash
# 1. Xem nhật ký hoạt động thời gian thực (Live Stream Logs)
sudo journalctl -u hermes-gateway -f
# (hoặc: hermes logs -f)

# 2. Liệt kê các phiên chat Telegram mới nhất
hermes sessions list --limit 15

# 3. Đọc chi tiết nội dung phiên chat của một khách hàng
hermes sessions export - --session-id <SESSION_ID>
```
