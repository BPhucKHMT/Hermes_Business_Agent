"""Composio client singleton and user formatting utilities."""

import os
from typing import Optional, Union
from composio import Composio

try:
    from composio.exceptions import ApiKeyError
except ImportError:
    ApiKeyError = RuntimeError

_client_instance: Optional[Composio] = None


def format_user_id(user_identifier: Union[int, str, None], platform: str = "telegram") -> str:
    """Format and validate a user identifier into a safe, platform-scoped Composio entity user_id.

    Supports multiple messaging platforms (Telegram, WhatsApp, Discord, Slack) and prevents cross-platform collision.
    """
    if user_identifier is None:
        raise ValueError("user_identifier cannot be None")
    uid_str = str(user_identifier).strip()
    if not uid_str:
        raise ValueError("user_identifier cannot be empty")

    detected_platform = platform
    if ":" in uid_str:
        parts = uid_str.split(":")
        if parts[0].lower() in {"telegram", "whatsapp", "discord", "slack", "signal"}:
            detected_platform = parts[0].lower()
            uid_str = parts[-1]
    elif "_" in uid_str:
        parts = uid_str.split("_", 1)
        if parts[0].lower() in {"telegram", "whatsapp", "discord", "slack", "signal"}:
            detected_platform = parts[0].lower()
            uid_str = parts[1]

    import re
    clean_id = re.sub(r'[^a-zA-Z0-9_-]', '', uid_str)
    return f"{detected_platform}_{clean_id}"

def get_composio_client(force_refresh: bool = False) -> Composio:
    """Retrieve or initialize the Composio client singleton.

    Raises RuntimeError if COMPOSIO_API_KEY is absent or invalid.
    """
    global _client_instance
    if _client_instance is not None and not force_refresh:
        return _client_instance

    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        env_locations = [
            os.path.expanduser("~/.hermes/.env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        ]
        for env_path in env_locations:
            if os.path.isfile(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("COMPOSIO_API_KEY="):
                                candidate = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                                if candidate:
                                    api_key = candidate
                                    break
                except Exception:
                    pass
            if api_key:
                break

    if not api_key:
        raise RuntimeError(
            "COMPOSIO_API_KEY is not configured. "
            "Please add COMPOSIO_API_KEY to ~/.hermes/.env or your environment."
        )

    try:
        _client_instance = Composio(api_key=api_key)
    except ApiKeyError as exc:
        raise RuntimeError(
            f"Mã COMPOSIO_API_KEY không hợp lệ hoặc đã hết hạn ({str(exc)}). "
            "Vui lòng lấy API key mới từ https://dashboard.composio.dev và cập nhật vào ~/.hermes/.env."
        ) from exc

    return _client_instance
