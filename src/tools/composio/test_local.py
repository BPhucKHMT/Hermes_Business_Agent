"""Interactive local tester for Composio Google Workspace integration.

Run this script to test the complete OAuth login, Gmail search, and Calendar retrieval locally.
Usage:
    python -m tools.composio.test_local
"""

import os
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tools.composio.client import get_composio_client, format_user_id
from tools.composio.auth import initiate_google_connection, check_connection_status
from tools.composio.mail_tools import composio_mail_search
from tools.composio.calendar_tools import composio_calendar_list_events


def run_interactive_test():
    print("=" * 65)
    print("🚀 BẮT ĐẦU KIỂM TRA TÍCH HỢP COMPOSIO (GMAIL & CALENDAR) CỤC BỘ")
    print("=" * 65)

    # 1. Kiểm tra API Key
    try:
        client = get_composio_client()
        print("✅ [1/4] Đã tìm thấy cấu hình COMPOSIO_API_KEY.")
    except RuntimeError as e:
        print(f"\n❌ [LỖI CẤU HÌNH] {e}")
        print("💡 Hướng dẫn lấy key:")
        print("   1. Vào https://dashboard.composio.dev tạo tài khoản miễn phí.")
        print("   2. Vào mục 'Settings' -> 'API Keys' -> Bấm 'Generate New Key'.")
        print("   3. Dán key vào file ~/.hermes/.env:\n      COMPOSIO_API_KEY=comp_xxxx\n")
        return

    # 2. Giả lập ID người dùng Telegram
    test_user_id = 7275339077
    print(f"\n👤 [2/4] Kiểm tra tài khoản cho người dùng Telegram ID: {test_user_id} ({format_user_id(test_user_id)})")

    try:
        is_connected = check_connection_status(test_user_id, app="gmail")
    except Exception as e:
        print(f"\n❌ [LỖI XÁC THỰC API KEY VỚI COMPOSIO] {e}")
        print("💡 Mã key hiện tại trong file .env có thể đã hết hạn hoặc không còn hiệu lực.")
        print("   Vui lòng vào https://dashboard.composio.dev tạo key mới rồi cập nhật lại nhé!\n")
        return

    if not is_connected:
        print("   ⚠️ Tài khoản CHƯA KẾT NỐI Google.")
        print("   🔗 Đang tạo đường link đăng nhập Magic Link...")
        try:
            auth_url = initiate_google_connection(test_user_id, toolkit="gmail")
        except Exception as e:
            print(f"\n❌ [LỖI TẠO LINK] {e}")
            print("💡 Vui lòng kiểm tra lại key trên https://dashboard.composio.dev\n")
            return

        print("\n" + "-" * 65)
        print("👉 HÃY COPY ĐƯỜNG LINK NÀY VÀ MỞ TRÊN TRÌNH DUYỆT ĐỂ ĐĂNG NHẬP:")
        print(f"\n   {auth_url}\n")
        print("-" * 65)
        print("⏳ Đang đợi bạn bấm 'Cho phép' trên trình duyệt (tối đa 60 giây)...")

        for _ in range(30):
            time.sleep(2)
            try:
                if check_connection_status(test_user_id, app="gmail"):
                    is_connected = True
                    print("\n🎉 ĐĂNG NHẬP THÀNH CÔNG! Token đã được lưu an toàn vào Composio.")
                    break
            except Exception:
                pass
            print(".", end="", flush=True)

        if not is_connected:
            print("\n⚠️ Hết thời gian chờ. Bạn có thể mở link trên để đăng nhập rồi chạy lại lệnh này sau.")
            return
    else:
        print("   ✅ Tài khoản ĐÃ KẾT NỐI Google từ trước!")

    # 3. Test đọc Gmail
    print("\n📬 [3/4] Đang thử đọc 3 email mới nhất trong hộp thư đến...")
    mail_res = composio_mail_search(test_user_id, query="label:inbox", max_results=3)
    if mail_res.get("status") == "success":
        print("   ✅ ĐỌC GMAIL THÀNH CÔNG!")
        data = mail_res.get("data", {})
        print(f"   Kết quả: {data}")
    else:
        print(f"   ❌ Lỗi đọc mail: {mail_res.get('message')}")

    # 4. Test đọc Calendar
    print("\n📅 [4/4] Đang thử kiểm tra lịch trình Google Calendar...")
    cal_res = composio_calendar_list_events(test_user_id)
    if cal_res.get("status") == "success":
        print("   ✅ ĐỌC GOOGLE CALENDAR THÀNH CÔNG!")
        data = cal_res.get("data", {})
        print(f"   Kết quả: {data}")
    else:
        print(f"   ❌ Lỗi đọc lịch: {cal_res.get('message')}")

    print("\n" + "=" * 65)
    print("🎉 HOÀN TẤT KIỂM TRA CỤC BỘ!")
    print("=" * 65)


if __name__ == "__main__":
    run_interactive_test()
