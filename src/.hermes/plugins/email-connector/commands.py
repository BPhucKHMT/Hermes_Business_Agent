from __future__ import annotations

import logging
from caller import DM_REDIRECT_TEXT

logger = logging.getLogger(__name__)


def handle_connect_gmail(raw_args: str = "") -> str:
    return "Để kết nối Gmail, vui lòng mở liên kết xác thực an toàn được cấp riêng cho bạn."


def handle_mail_status(raw_args: str = "") -> str:
    return "Trạng thái hòm thư: Đang hoạt động và bảo vệ phân quyền riêng tư."


def handle_disconnect_gmail(raw_args: str = "") -> str:
    return "Đã ngắt kết nối hòm thư thành công."
