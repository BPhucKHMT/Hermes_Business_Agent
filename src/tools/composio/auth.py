"""Multi-user authentication management using Composio v3 SDK."""

import os
import re
import json
from pathlib import Path
from typing import Union, Optional, Dict, List, Tuple
from .client import format_user_id, get_composio_client


def initiate_google_connection(
    telegram_user_id: Union[int, str],
    toolkit: str = "googlesuper",
    callback_url: Optional[str] = None,
) -> str:
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})

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
                if slug.lower() == "googlesuper":
                    return True
                if not app_name or slug.lower() == app_name or app_name in slug.lower():
                    return True
        return False
    except Exception:
        return False


def get_user_emails(telegram_user_id: Union[int, str]) -> Dict[str, str]:
    """Retrieve mapping of {account_id: email_address} for all active accounts."""
    cache_path = Path(os.path.expanduser("~/.hermes/composio_account_emails.json"))
    cache: Dict[str, str] = {}
    if cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    account_emails: Dict[str, str] = {}

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        session = None

        cache_updated = False
        for item in items:
            status = getattr(item, "status", "")
            if isinstance(status, str) and status.upper() == "ACTIVE":
                acc_id = getattr(item, "id", "")
                if acc_id in cache:
                    account_emails[acc_id] = cache[acc_id]
                else:
                    if session is None:
                        session = client.create(user_id=user_id, multi_account={"enable": True})
                    try:
                        res = session.execute(tool_slug="GMAIL_FETCH_EMAILS", arguments={"max_results": 1}, account=acc_id)
                        data = getattr(res, "data", res)
                        msgs = data.get("messages", []) if isinstance(data, dict) else []
                        if msgs and msgs[0].get("to"):
                            em = msgs[0]["to"]
                            cache[acc_id] = em
                            account_emails[acc_id] = em
                            cache_updated = True
                    except Exception:
                        pass

        if cache_updated:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass

    return account_emails


def resolve_account_target(
    telegram_user_id: Union[int, str],
    account_target: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve an account target (email, username, index, or nanoid) to (account_id, resolved_email)."""
    account_emails = get_user_emails(telegram_user_id)
    if not account_emails:
        return None, None

    if not account_target or not str(account_target).strip():
        first_id, first_em = next(iter(account_emails.items()))
        return first_id, first_em

    target = str(account_target).strip()

    # 1. Check if target is a 1-based index (e.g. '1', '2')
    if target.isdigit():
        idx = int(target) - 1
        distinct_map = {}
        for acc_id, em in account_emails.items():
            if em not in distinct_map:
                distinct_map[em] = acc_id
        items = list(distinct_map.items())
        if 0 <= idx < len(items):
            return items[idx][1], items[idx][0]

    # 2. Extract clean email via regex if surrounded by operators or braces
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', target)
    clean_target = email_match.group(0).lower() if email_match else target.lower()

    # 3. Exact match on account ID (nanoid)
    for acc_id, em in account_emails.items():
        if clean_target == acc_id.lower():
            return acc_id, em

    # 4. Exact match on full email
    for acc_id, em in account_emails.items():
        if clean_target == em.lower():
            return acc_id, em

    # 5. Username or substring match
    clean_keyword = re.sub(r'[^a-zA-Z0-9_.-]', '', clean_target)
    for acc_id, em in account_emails.items():
        em_user = em.split('@')[0].lower()
        if clean_keyword and (clean_keyword in em_user or em_user in clean_keyword or clean_keyword in em.lower()):
            return acc_id, em

    # Default fallback to first available if target not found
    first_id, first_em = next(iter(account_emails.items()))
    return first_id, first_em


def get_user_email(telegram_user_id: Union[int, str]) -> Optional[str]:
    """Retrieve primary email address or None."""
    emails = get_user_emails(telegram_user_id)
    if emails:
        return list(emails.values())[0]
    return None


def list_user_connections(telegram_user_id: Union[int, str]) -> list[dict]:
    """Retrieve detailed list of active connected accounts for the user including emails."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    account_emails = get_user_emails(telegram_user_id)
    results = []

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        for item in items:
            status = getattr(item, "status", "")
            if isinstance(status, str) and status.upper() == "ACTIVE":
                acc_id = getattr(item, "id", "")
                toolkit = getattr(item, "toolkit", None)
                slug = getattr(toolkit, "slug", "") if toolkit else ""
                tk_label = "Google Workspace (Gmail & Calendar)" if slug.lower() == "googlesuper" else slug
                results.append({
                    "id": acc_id,
                    "toolkit": tk_label,
                    "status": status,
                    "created_at": getattr(item, "created_at", ""),
                    "email": account_emails.get(acc_id, ""),
                })
    except Exception:
        pass

    return results


def disconnect_user(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
    target_identifier: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """Revoke and delete connected accounts for a specific user, optionally targeting an email or connection ID.

    Returns (success, list_of_disconnected_emails).
    """
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()

    app_name = app.lower() if app else ""
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    target = target_identifier.lower().strip() if target_identifier else ""
    account_emails = get_user_emails(telegram_user_id)
    disconnected_emails: List[str] = []

    target_acc_id = None
    target_email = None
    if target and target != "all":
        target_acc_id, target_email = resolve_account_target(telegram_user_id, target)

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)

        for item in items:
            item_id = getattr(item, "id", None)
            if not item_id:
                continue

            item_email = account_emails.get(item_id, "")
            if target and target != "all":
                if target_acc_id and item_id != target_acc_id and (not target_email or target_email.lower() != item_email.lower()):
                    continue
                elif not target_acc_id:
                    if target != item_id.lower() and target not in item_email.lower():
                        continue

            toolkit = getattr(item, "toolkit", None)
            slug = getattr(toolkit, "slug", "") if toolkit else ""
            if not app_name or slug.lower() == app_name or app_name in slug.lower():
                try:
                    client.connected_accounts.delete(item_id)
                    if item_email and item_email not in disconnected_emails:
                        disconnected_emails.append(item_email)
                except Exception:
                    pass

        # Clear cache for deleted accounts
        cache_path = Path(os.path.expanduser("~/.hermes/composio_account_emails.json"))
        if cache_path.is_file():
            try:
                if not target or target == "all":
                    cache_path.unlink(missing_ok=True)
                else:
                    cache = json.loads(cache_path.read_text(encoding="utf-8"))
                    new_cache = {
                        k: v for k, v in cache.items()
                        if (target_acc_id and k != target_acc_id) and (not target_email or v.lower() != target_email.lower())
                    }
                    cache_path.write_text(json.dumps(new_cache, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        return True, disconnected_emails
    except Exception:
        return False, []
