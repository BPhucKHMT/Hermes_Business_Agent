"""Multi-user authentication management using Composio."""

from typing import Union, Optional
from .client import format_user_id, get_composio_client


def initiate_google_connection(
    telegram_user_id: Union[int, str],
    toolkit: str = "gmail",
    callback_url: Optional[str] = None,
) -> str:
    """Generate a magic OAuth authorization URL for a specific Telegram user.

    The user will tap this link on mobile or desktop to link their Google account.
    """
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id)

    kwargs = {}
    if callback_url:
        kwargs["callback_url"] = callback_url

    connection_request = session.authorize(toolkit, **kwargs)
    return connection_request.redirect_url


def check_connection_status(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
) -> bool:
    """Check if the given user currently has an ACTIVE connected account for the app."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()

    try:
        accounts = client.connected_accounts.get(user_id=user_id, app=app)
        if not accounts:
            return False
        for acc in accounts:
            status = getattr(acc, "status", None)
            if isinstance(status, str) and status.upper() == "ACTIVE":
                return True
            if isinstance(acc, dict) and acc.get("status", "").upper() == "ACTIVE":
                return True
        return False
    except Exception:
        return False


def disconnect_user(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
) -> bool:
    """Revoke and delete connected accounts for a specific user."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()

    try:
        accounts = client.connected_accounts.get(user_id=user_id, app=app)
        if not accounts:
            return True
        for acc in accounts:
            acc_id = getattr(acc, "id", None) or (acc.get("id") if isinstance(acc, dict) else None)
            if acc_id:
                client.connected_accounts.delete(connected_account_id=acc_id)
        return True
    except Exception:
        return False
