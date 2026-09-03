"""Telegram slash command handlers for Composio Google Workspace integration."""

from typing import Union, Dict, List
from .auth import (
    initiate_google_connection,
    check_connection_status,
    disconnect_user,
    list_user_connections,
    get_user_email,
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
    """Report the current Google connection status for the user with all connected emails."""
    connections = list_user_connections(telegram_user_id)

    if connections:
        # Group accounts by email
        email_map: Dict[str, list[str]] = {}
        for conn in connections:
            em = conn.get("email") or "Chưa xác định địa chỉ"
            cid = conn.get("id", "")
            email_map.setdefault(em, []).append(cid)

        lines = [
            f"✅ **Trạng thái Tài khoản Google:** ĐÃ KẾT NỐI ({len(email_map)} hòm thư)\n",
            "📧 **Danh sách các tài khoản Email đã liên kết:**"
        ]
        for idx, (em, cids) in enumerate(email_map.items(), 1):
            cids_str = ", ".join(f"`{c}`" for c in cids)
            lines.append(f"  {idx}. **`{em}`** (Phiên: {cids_str})")

        lines.extend([
            "\n📋 **Dịch vụ đang hoạt động:**",
            "  • **Gmail:** Sẵn sàng đọc, gửi và soạn nháp thư.",
            "  • **Google Calendar:** Sẵn sàng tra cứu và lên lịch họp.",
            f"\n*(Tổng số phiên kết nối: {len(connections)})*",
            "\n💡 *Bạn có thể ngắt kết nối bất kỳ lúc nào bằng lệnh `/disconnect-google`.*"
        ])
        return "\n".join(lines)
    return (
        "⚠️ **Trạng thái Tài khoản Google:** CHƯA KẾT NỐI (DISCONNECTED)\n\n"
        "Hiện tại bạn chưa liên kết tài khoản Google nào với Hermes.\n"
        "Hãy gửi lệnh `/connect-google` để nhận đường link đăng nhập nhanh chóng!"
    )


def handle_disconnect_google(
    telegram_user_id: Union[int, str],
    target: str = "",
) -> str:
    """Disconnect and revoke Google access for the user, optionally targeting an email or connection ID."""
    target_clean = target.strip()
    try:
        disconnect_user(telegram_user_id, app="", target_identifier=target_clean)
        if target_clean and target_clean.lower() != "all":
            return (
                f"🔒 **Đã ngắt kết nối tài khoản `{target_clean}` thành công!**\n\n"
                "Phiên ủy quyền của tài khoản này đã được xóa khỏi hệ thống. "
                "Các tài khoản khác (nếu có) vẫn tiếp tục hoạt động bình thường."
            )
        return (
            "🔒 **Đã ngắt kết nối toàn bộ tài khoản Google thành công!**\n\n"
            "Toàn bộ phiên ủy quyền Gmail và Google Calendar của bạn đã được xóa khỏi hệ thống. "
            "Hermes sẽ không thể truy cập email hay lịch của bạn nữa trừ khi bạn cấp quyền lại qua `/connect-google`."
        )
    except Exception as exc:
        return f"❌ Lỗi khi ngắt kết nối tài khoản: {str(exc)}"
