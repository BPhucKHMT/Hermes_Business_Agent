"""Multi-user authentication management using Composio v3 SDK."""

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
    session = client.create(user_id=user_id)

    app_name = toolkit.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    kwargs = {}
    if callback_url:
        kwargs["callback_url"] = callback_url

    connection_request = session.authorize(app_name, **kwargs)
    return getattr(connection_request, "redirect_url", getattr(connection_request, "redirectUrl", ""))


def check_connection_status(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
) -> bool:
    """Check if the given user currently has an ACTIVE connected account for the app."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()

    app_name = app.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        for item in items:
            status = getattr(item, "status", "")
            toolkit = getattr(item, "toolkit", None)
            slug = getattr(toolkit, "slug", "") if toolkit else ""
            if isinstance(status, str) and status.upper() == "ACTIVE":
                if not app_name or slug.lower() == app_name or app_name in slug.lower():
                    return True
        return False
    except Exception:
        return False
def list_user_connections(telegram_user_id: Union[int, str]) -> list[dict]:
    """Retrieve detailed list of active connected accounts for the user."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    results = []

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        for item in items:
            status = getattr(item, "status", "")
            if isinstance(status, str) and status.upper() == "ACTIVE":
                toolkit = getattr(item, "toolkit", None)
                slug = getattr(toolkit, "slug", "") if toolkit else ""
                results.append({
                    "id": getattr(item, "id", ""),
                    "toolkit": slug,
                    "status": status,
                    "created_at": getattr(item, "created_at", ""),
                })
    except Exception:
        pass

    return results


def disconnect_user(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
) -> bool:
    """Revoke and delete connected accounts for a specific user."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()

    app_name = app.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        for item in items:
            toolkit = getattr(item, "toolkit", None)
            slug = getattr(toolkit, "slug", "") if toolkit else ""
            if not app_name or slug.lower() == app_name or app_name in slug.lower():
                item_id = getattr(item, "id", None)
                if item_id:
                    client.connected_accounts.delete(connected_account_id=item_id)
        return True
    except Exception:
        return False
