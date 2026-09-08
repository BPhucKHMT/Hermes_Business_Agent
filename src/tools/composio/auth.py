"""Google authentication and account targeting helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from .client import (
    format_user_id,
    get_composio_client,
    get_response_data,
    get_response_error,
)

logger = logging.getLogger(__name__)


def _item_value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _toolkit_slug(item: Any) -> str:
    toolkit = _item_value(item, "toolkit", None)
    slug = _item_value(toolkit, "slug", "") if toolkit else ""
    return str(slug or "")


def _account_email_cache_path() -> Path:
    """Keep derived account metadata inside this deployed project."""
    return Path(__file__).resolve().parents[2] / ".runtime" / "google" / "account-emails.json"


def _payload(response: Any) -> Dict[str, Any]:
    if get_response_error(response):
        return {}
    data = get_response_data(response)
    if isinstance(data, dict) and isinstance(data.get("response_data"), dict):
        merged = dict(data["response_data"])
        for key, value in data.items():
            if key != "response_data":
                merged.setdefault(key, value)
        return merged
    return data if isinstance(data, dict) else {}


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

    kwargs: Dict[str, Any] = {}
    if callback_url:
        kwargs["callback_url"] = callback_url
    connection_request = session.authorize(app_name, **kwargs)
    return getattr(connection_request, "redirect_url", getattr(connection_request, "redirectUrl", ""))


def check_connection_status(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
) -> bool:
    """Check whether the caller has an ACTIVE account for an application."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()

    app_name = app.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        for item in items:
            status = str(_item_value(item, "status", "") or "")
            slug = _toolkit_slug(item).lower()
            if status.upper() == "ACTIVE" and (
                slug == "googlesuper" or not app_name or slug == app_name or app_name in slug
            ):
                return True
        return False
    except Exception as exc:
        logger.warning("Failed to check connection status for %s (%s): %s", user_id, app, exc)
        return False


def _execute_account_probe(session: Any, tool_slug: str, **kwargs: Any) -> Dict[str, Any]:
    try:
        response = session.execute(tool_slug=tool_slug, **kwargs)
    except Exception as exc:
        logger.debug("Account probe %s failed: %s", tool_slug, exc)
        return {}
    return _payload(response)


def get_user_emails(telegram_user_id: Union[int, str]) -> Dict[str, str]:
    """Retrieve active Composio account IDs and their verified email addresses."""
    cache_path = _account_email_cache_path()
    cache: Dict[str, str] = {}
    if cache_path.is_file():
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cache = {str(key): str(value) for key, value in loaded.items() if value}
        except (OSError, ValueError, TypeError):
            cache = {}

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    account_emails: Dict[str, str] = {}

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        cache_updated = False
        for item in items:
            status = str(_item_value(item, "status", "") or "")
            if status.upper() != "ACTIVE":
                continue
            account_id = str(_item_value(item, "id", "") or "")
            if not account_id:
                continue
            if account_id in cache:
                account_emails[account_id] = cache[account_id]
                continue

            email_found: Optional[str] = None
            session = client.create(
                user_id=user_id,
                toolkits=["googlesuper"],
                multi_account={"enable": True},
            )
            profile = _execute_account_probe(
                session,
                "GOOGLESUPER_GET_PROFILE",
                arguments={"user_id": "me"},
                account=account_id,
            )
            if profile.get("emailAddress"):
                email_found = str(profile["emailAddress"])

            if not email_found:
                events = _execute_account_probe(
                    session,
                    "GOOGLESUPER_EVENTS_LIST",
                    arguments={"calendar_id": "primary", "max_results": 1},
                    account=account_id,
                )
                summary = str(events.get("summary", ""))
                if "@" in summary:
                    email_found = summary

            if not email_found:
                mail_session = client.create(
                    user_id=user_id,
                    toolkits=["gmail"],
                    multi_account={"enable": True},
                )
                messages = _execute_account_probe(
                    mail_session,
                    "GMAIL_FETCH_EMAILS",
                    arguments={"max_results": 1},
                    account=account_id,
                ).get("messages", [])
                if messages and isinstance(messages[0], dict) and messages[0].get("to"):
                    email_found = str(messages[0]["to"])

            if email_found:
                cache[account_id] = email_found
                account_emails[account_id] = email_found
                cache_updated = True

        if cache_updated:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to write account email cache at %s: %s", cache_path, exc)
    except Exception as exc:
        logger.error("Failed to retrieve connected account emails for %s: %s", user_id, exc)
    return account_emails


def _target_error(kind: str, target: str) -> ValueError:
    return ValueError(f"account_target_{kind}:{target}")


def resolve_account_target(
    telegram_user_id: Union[int, str],
    account_target: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve an optional account target without guessing explicit input."""
    account_emails = get_user_emails(telegram_user_id)
    target = str(account_target).strip() if account_target is not None else ""
    if not account_emails:
        if target:
            raise _target_error("not_found", target)
        return None, None
    if not target:
        return next(iter(account_emails.items()))

    if target.isdigit():
        index = int(target) - 1
        distinct_accounts: List[Tuple[str, str]] = []
        seen_emails: set[str] = set()
        for account_id, email in account_emails.items():
            normalized_email = email.casefold()
            if normalized_email not in seen_emails:
                seen_emails.add(normalized_email)
                distinct_accounts.append((account_id, email))
        if 0 <= index < len(distinct_accounts):
            return distinct_accounts[index]
        raise _target_error("index_out_of_range", target)

    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", target)
    clean_target = email_match.group(0).casefold() if email_match else target.casefold()

    id_matches = [
        (account_id, email)
        for account_id, email in account_emails.items()
        if clean_target == account_id.casefold()
    ]
    if len(id_matches) == 1:
        return id_matches[0]
    if len(id_matches) > 1:
        raise _target_error("ambiguous", target)

    email_matches = [
        (account_id, email)
        for account_id, email in account_emails.items()
        if clean_target == email.casefold()
    ]
    if len(email_matches) == 1:
        return email_matches[0]
    if len(email_matches) > 1:
        raise _target_error("ambiguous", target)

    clean_keyword = re.sub(r"[^a-zA-Z0-9_.-]", "", clean_target)
    candidates = []
    for account_id, email in account_emails.items():
        email_user = email.split("@", 1)[0].casefold()
        if clean_keyword and (
            clean_keyword in email_user
            or email_user in clean_keyword
            or clean_keyword in email.casefold()
            or clean_keyword in account_id.casefold()
        ):
            candidates.append((account_id, email))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise _target_error("ambiguous", target)
    raise _target_error("not_found", target)


def get_user_email(telegram_user_id: Union[int, str]) -> Optional[str]:
    """Retrieve the first active email address or ``None``."""
    emails = get_user_emails(telegram_user_id)
    return next(iter(emails.values()), None)


def list_user_connections(telegram_user_id: Union[int, str]) -> list[dict]:
    """Retrieve active connection metadata for the caller."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    account_emails = get_user_emails(telegram_user_id)
    results: list[dict] = []

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        for item in items:
            status = str(_item_value(item, "status", "") or "")
            if status.upper() != "ACTIVE":
                continue
            account_id = str(_item_value(item, "id", "") or "")
            slug = _toolkit_slug(item)
            results.append(
                {
                    "id": account_id,
                    "toolkit": (
                        "Google Workspace (Gmail & Calendar)"
                        if slug.lower() == "googlesuper"
                        else slug
                    ),
                    "status": status,
                    "created_at": _item_value(item, "created_at", ""),
                    "email": account_emails.get(account_id, ""),
                }
            )
    except Exception as exc:
        logger.error("Failed to list active connections for %s: %s", user_id, exc)
    return results


def disconnect_user(
    telegram_user_id: Union[int, str],
    app: str = "gmail",
    target_identifier: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """Revoke active accounts, optionally selecting one explicit target."""
    user_id = format_user_id(telegram_user_id)
    target = str(target_identifier).strip() if target_identifier is not None else ""
    account_emails = get_user_emails(telegram_user_id)
    target_acc_id: Optional[str] = None
    target_email: Optional[str] = None
    if target and target.casefold() != "all":
        target_acc_id, target_email = resolve_account_target(telegram_user_id, target)

    client = get_composio_client()
    app_name = app.lower() if app else ""
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"
    disconnected_emails: List[str] = []

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        deleted_ids: set[str] = set()
        for item in items:
            item_id = str(_item_value(item, "id", "") or "")
            if not item_id:
                continue
            item_email = account_emails.get(item_id, "")
            if target and target.casefold() != "all":
                if item_id != target_acc_id and item_email.casefold() != (target_email or "").casefold():
                    continue
            slug = _toolkit_slug(item).lower()
            if app_name and slug != app_name and app_name not in slug:
                continue
            try:
                client.connected_accounts.delete(item_id)
                deleted_ids.add(item_id)
                if item_email and item_email not in disconnected_emails:
                    disconnected_emails.append(item_email)
            except Exception as exc:
                logger.warning("Failed to delete connected account %s: %s", item_id, exc)

        cache_path = _account_email_cache_path()
        if cache_path.is_file():
            try:
                if not target or target.casefold() == "all":
                    cache_path.unlink(missing_ok=True)
                else:
                    cache = json.loads(cache_path.read_text(encoding="utf-8"))
                    if isinstance(cache, dict):
                        cache = {key: value for key, value in cache.items() if key not in deleted_ids}
                        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            except (OSError, ValueError, TypeError) as exc:
                logger.warning("Failed to update email cache on disconnect: %s", exc)
        return True, disconnected_emails
    except Exception as exc:
        logger.error("Failed to disconnect user %s: %s", user_id, exc)
        return False, []
