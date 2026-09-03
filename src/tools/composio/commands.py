"""Telegram slash command handlers for Composio Google Workspace integration."""

from typing import Union
from .auth import (
    initiate_google_connection,
    check_connection_status,
    disconnect_user,
    list_user_connections,
)


def handle_connect_google(telegram_user_id: Union[int, str]) -> str:
    """Generate a response containing the magic authorization link for the user."""
    try:
        url = initiate_google_connection(telegram_user_id, toolkit="gmail")
        return (
            "🔗 **Liên kết Tài khoản Google (Gmail & Google Calendar)**\n\n"
            "Vui lòng nhấn vào đường link bảo mật bên dưới để cấp quyền cho Hermes:\n"
            f"{url}\n\n"
            "💡 *Sau khi đăng nhập thành công trên điện thoại hoặc trình duyệt, "
            "Hermes sẽ tự động kích hoạt tính năng đọc/gửi email và quản lý lịch trình cho riêng bạn!*"
        )
    except Exception as exc:
        return f"❌ Lỗi khi tạo link liên kết tài khoản: {str(exc)}"


def handle_google_status(telegram_user_id: Union[int, str]) -> str:
    """Report the current Google connection status for the user with connected accounts list."""
    connections = list_user_connections(telegram_user_id)

    if connections:
        lines = [
            f"✅ **Trạng thái Tài khoản Google:** ĐÃ KẾT NỐI ({len(connections)} tài khoản hoạt động)\n",
            "📋 **Danh sách kết nối của bạn:**"
        ]
        for idx, conn in enumerate(connections, 1):
            tk = conn.get("toolkit", "Google Workspace").capitalize()
            cid = conn.get("id", "")
            lines.append(f"  {idx}. **{tk}** (Mã kết nối: `{cid}`)")

        lines.extend([
            "\n• **Gmail:** Sẵn sàng đọc/gửi/soạn nháp thư.",
            "• **Google Calendar:** Sẵn sàng tra cứu và lên lịch họp.",
            "\n💡 *Bạn có thể ngắt kết nối bất kỳ lúc nào bằng lệnh `/disconnect-google`.*"
        ])
        return "\n".join(lines)

    return (
        "⚠️ **Trạng thái Tài khoản Google:** CHƯA KẾT NỐI (DISCONNECTED)\n\n"
        "Hiện tại bạn chưa liên kết tài khoản Google nào với Hermes.\n"
        "Hãy gửi lệnh `/connect-google` để nhận đường link đăng nhập nhanh chóng!"
    )


def handle_disconnect_google(telegram_user_id: Union[int, str]) -> str:
    """Disconnect and revoke Google access for the user."""
    try:
        disconnect_user(telegram_user_id, app="gmail")
        disconnect_user(telegram_user_id, app="googlecalendar")
        return (
            "🔒 **Đã ngắt kết nối Google thành công!**\n\n"
            "Toàn bộ phiên ủy quyền Gmail và Google Calendar của bạn đã được xóa khỏi hệ thống. "
            "Hermes sẽ không thể truy cập email hay lịch của bạn nữa trừ khi bạn cấp quyền lại qua `/connect-google`."
        )
    except Exception as exc:
        return f"❌ Lỗi khi ngắt kết nối tài khoản: {str(exc)}"
