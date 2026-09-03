"""Multi-user authentication management using Composio."""

from typing import Union, Optional
from .client import format_user_id, get_composio_client


def initiate_google_connection(
    telegram_user_id: Union[int, str],
    toolkit: str = "gmail",
    callback_url: Optional[str] = None,
) -> str:
    """Generate a magic OAuth authorization URL for a specific Telegram user."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    entity = client.get_entity(id=user_id)

    app_name = toolkit.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    kwargs = {}
    if callback_url:
        kwargs["redirect_url"] = callback_url

    connection_request = entity.initiate_connection(app_name=app_name, **kwargs)
    return getattr(connection_request, "redirect_url", getattr(connection_request, "redirectUrl", ""))


def check_connection_status(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
) -> bool:
    """Check if the given user currently has an ACTIVE connected account for the app."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    entity = client.get_entity(id=user_id)

    app_name = app.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    try:
        conn = entity.get_connection(app=app_name)
        if not conn:
            return False
        status = getattr(conn, "status", getattr(conn, "connectionStatus", None))
        if isinstance(status, str) and status.upper() == "ACTIVE":
            return True
        if isinstance(conn, dict) and conn.get("status", "").upper() == "ACTIVE":
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
    entity = client.get_entity(id=user_id)

    app_name = app.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    try:
        conn = entity.get_connection(app=app_name)
        if not conn:
            return True
        conn_id = getattr(conn, "id", getattr(conn, "connectedAccountId", None))
        if conn_id:
            client.connected_accounts.delete(connected_account_id=conn_id)
        return True
    except Exception:
        return False
