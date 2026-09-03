"""Telegram slash command handlers for Composio Google Workspace integration."""

from typing import Union, Dict, List
from .auth import (
    initiate_google_connection,
    check_connection_status,
    disconnect_user,
    list_user_connections,
    get_user_email,
    get_user_emails,
)


def handle_connect_google(telegram_user_id: Union[int, str]) -> str:
    """Generate response containing a single all-in-one Google Workspace authorization link (Gmail, Calendar, Drive)."""
    try:
        url_super = initiate_google_connection(telegram_user_id, toolkit="googlesuper")
        return (
            "🔗 **Liên kết Tài khoản Google Trọn Gói (Gmail & Calendar)**\n\n"
            "Vui lòng nhấn vào đường link bên dưới để cấp quyền trọn gói 1 lần duy nhất cho Hermes:\n\n"
            f"👉 {url_super}\n\n"
            "💡 *Chỉ cần đăng nhập 1 lần duy nhất, tài khoản của bạn sẽ được kích hoạt đồng thời "
            "cả Gmail (đọc, gửi, soạn nháp) và Google Calendar (tra cứu, lên lịch họp)!*"
        )
    except Exception as exc:
        return f"❌ Lỗi khi tạo link liên kết tài khoản: {str(exc)}"


def handle_connect_calendar(telegram_user_id: Union[int, str]) -> str:
    """Generate response containing the magic authorization link specifically for Google Calendar."""
    try:
        url_cal = initiate_google_connection(telegram_user_id, toolkit="googlecalendar")
        return (
            "📅 **Liên kết Google Calendar**\n\n"
            "Vui lòng nhấn vào đường link bảo mật bên dưới để kết nối Calendar cho Hermes:\n"
            f"{url_cal}\n\n"
            "💡 *Sau khi đăng nhập tài khoản Google bạn muốn dùng cho Calendar, "
            "Hermes sẽ tự động kích hoạt tính năng tra cứu và quản lý lịch trình cho riêng bạn!*"
        )
    except Exception as exc:
        return f"❌ Lỗi khi tạo link liên kết Calendar: {str(exc)}"


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
    """Disconnect and revoke Google access for the user with interactive selection menu."""

    account_emails = get_user_emails(telegram_user_id)
    if not account_emails:
        return "⚠️ Bạn chưa kết nối tài khoản Google nào với Hermes."

    distinct_emails = list(dict.fromkeys(account_emails.values()))
    target_clean = target.strip().lower()

    # If no target specified and multiple distinct accounts exist -> present interactive selection menu
    if not target_clean and len(distinct_emails) > 1:
        lines = [
            f"📋 **Bạn đang kết nối {len(distinct_emails)} hòm thư Google:**",
        ]
        for idx, em in enumerate(distinct_emails, 1):
            lines.append(f"  {idx}. `{em}`")
        lines.extend([
            "\n👉 **Vui lòng chọn hòm thư bạn muốn ngắt kết nối:**",
            f"• Gõ: `/disconnect-google 1` hoặc `/disconnect-google {distinct_emails[0]}`",
            f"• Gõ: `/disconnect-google 2` hoặc `/disconnect-google {distinct_emails[1]}`",
            "\n👉 **Hoặc nếu muốn ngắt kết nối TẤT CẢ các tài khoản cùng lúc:**",
            "• Gõ: `/disconnect-google all`"
        ])
        return "\n".join(lines)

    # Perform disconnection
    try:
        success, disconnected = disconnect_user(telegram_user_id, app="", target_identifier=target_clean)
        if not success:
            return "❌ Lỗi khi ngắt kết nối tài khoản. Vui lòng thử lại sau."

        if target_clean and target_clean != "all":
            disc_label = ", ".join(f"`{d}`" for d in disconnected) if disconnected else f"`{target.strip()}`"
            remaining = [em for em in distinct_emails if em not in disconnected]
            rem_msg = (
                f"\n💡 *Tài khoản còn lại:* {', '.join(f'`{r}`' for r in remaining)} vẫn đang hoạt động bình thường."
                if remaining else "\n💡 *Bạn đã ngắt kết nối hết toàn bộ tài khoản Google.*"
            )
            return f"🔒 **Đã ngắt kết nối thành công tài khoản:** {disc_label}\n{rem_msg}"

        return (
            "🔒 **Đã ngắt kết nối TOÀN BỘ tài khoản Google thành công!**\n\n"
            "Toàn bộ phiên ủy quyền Gmail và Google Calendar của bạn đã được xóa khỏi hệ thống. "
            "Hermes sẽ không thể truy cập email hay lịch của bạn nữa trừ khi bạn cấp quyền lại qua `/connect-google`."
        )
    except Exception as exc:
        return f"❌ Lỗi khi ngắt kết nối tài khoản: {str(exc)}"
