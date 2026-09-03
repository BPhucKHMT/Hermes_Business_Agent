"""Composio client singleton and user formatting utilities."""

import os
from typing import Optional, Union
from composio import Composio

_client_instance: Optional[Composio] = None


def format_user_id(telegram_user_id: Union[int, str, None]) -> str:
    """Format and validate a Telegram user ID into a safe Composio entity user_id.

    Prevents empty values and guarantees proper scoping prefix.
    """
    if telegram_user_id is None:
        raise ValueError("telegram_user_id cannot be None")
    uid_str = str(telegram_user_id).strip()
    if not uid_str:
        raise ValueError("telegram_user_id cannot be empty")
    return f"telegram_{uid_str}"


def get_composio_client(force_refresh: bool = False) -> Composio:
    """Retrieve or initialize the Composio client singleton.

    Raises RuntimeError if COMPOSIO_API_KEY is absent.
    """
    global _client_instance
    if _client_instance is not None and not force_refresh:
        return _client_instance

    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        # Check standard hermes .env locations as fallback
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
                                api_key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                                if api_key:
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

    _client_instance = Composio(api_key=api_key)
    return _client_instance
