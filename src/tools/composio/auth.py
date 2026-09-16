"""Google authentication, account targeting, and capability helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any

from .capabilities import SERVICES, assess_service, extract_scopes
from .client import (
    format_user_id,
    get_composio_client,
    get_response_data,
    get_response_error,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountServiceState:
    """Per-service readiness for one connected account."""

    account_id: str
    email: str
    service: str
    state: str  # ready | needs_scope | unsupported
    reason: str = ""
    scope: str = ""


def _connected_accounts(user_id: str) -> list[Any]:
    """Return raw connected-account items for one Composio user."""
    client = get_composio_client()
    accounts = client.connected_accounts.list(user_ids=[user_id])
    items = getattr(accounts, "items", accounts)
    return list(items or [])


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
    return (
        Path(__file__).resolve().parents[2]
        / ".runtime"
        / "google"
        / "account-emails.json"
    )


def _payload(response: Any) -> dict[str, Any]:
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
    telegram_user_id: int | str,
    toolkit: str = "googlesuper",
    callback_url: str | None = None,
) -> str:
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    session = client.create(user_id=user_id, multi_account={"enable": True})

    app_name = toolkit.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    kwargs: dict[str, Any] = {}
    if callback_url:
        kwargs["callback_url"] = callback_url
    connection_request = session.authorize(app_name, **kwargs)
    return getattr(
        connection_request,
        "redirect_url",
        getattr(connection_request, "redirectUrl", ""),
    )


def check_connection_status(
    telegram_user_id: int | str,
    app: str = "gmail",
) -> bool:
    """Check whether the caller has an ACTIVE account for an application."""
    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()

    app_name = app.lower()
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"

    accounts = client.connected_accounts.list(user_ids=[user_id])
    items = getattr(accounts, "items", accounts)
    for item in items:
        status = str(_item_value(item, "status", "") or "")
        slug = _toolkit_slug(item).lower()
        if status.upper() == "ACTIVE" and (
            slug == "googlesuper"
            or not app_name
            or slug == app_name
            or app_name in slug
        ):
            return True
    return False


def _execute_account_probe(
    session: Any, tool_slug: str, **kwargs: Any
) -> dict[str, Any]:
    try:
        response = session.execute(tool_slug=tool_slug, **kwargs)
    except Exception as exc:  # noqa: BLE001 -- probe failure means empty payload
        logger.debug("Account probe %s failed: %s", tool_slug, exc)
        return {}
    return _payload(response)


def get_user_emails(telegram_user_id: int | str) -> dict[str, str]:
    """Retrieve active Composio account IDs and their verified email addresses."""
    cache_path = _account_email_cache_path()
    cache: dict[str, str] = {}
    if cache_path.is_file():
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cache = {str(key): str(value) for key, value in loaded.items() if value}
        except (OSError, ValueError, TypeError):
            cache = {}

    user_id = format_user_id(telegram_user_id)
    client = get_composio_client()
    account_emails: dict[str, str] = {}

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

            email_found: str | None = None
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
                mail_profile = _execute_account_probe(
                    session,
                    "GMAIL_GET_PROFILE",
                    arguments={"user_id": "me"},
                    account=account_id,
                )
                if mail_profile.get("emailAddress"):
                    email_found = str(mail_profile["emailAddress"])

            if not email_found:
                events = _execute_account_probe(
                    session,
                    "GOOGLESUPER_EVENTS_LIST",
                    arguments={"calendar_id": "primary", "max_results": 1},
                    account=account_id,
                )
                summary = str(events.get("summary", "")).strip()
                if "@" in summary and " " not in summary:
                    email_found = summary

            if email_found:
                cache[account_id] = email_found
                account_emails[account_id] = email_found
                cache_updated = True

        if cache_updated:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(cache, ensure_ascii=False), encoding="utf-8"
                )
            except OSError as exc:
                logger.warning(
                    "Failed to write account email cache at %s: %s", cache_path, exc
                )
    except Exception as exc:  # noqa: BLE001 -- listing degrades to empty with a log line
        logger.error(
            "Failed to retrieve connected account emails for %s: %s", user_id, exc
        )
    return account_emails


def _target_error(kind: str, target: str) -> ValueError:
    return ValueError(f"account_target_{kind}:{target}")


def _matches_newest_first(
    account_emails: dict[str, str], predicate
) -> list[tuple[str, str]]:
    """Return (account_id, email) matches, newest connection first.

    Composio may hold several ACTIVE sessions for the same mailbox after a
    re-login; the newest grant supersedes older ones, so it sorts first.
    """
    order = {item.id: idx for idx, item in enumerate(_account_order_cache())}
    matches = [
        (account_id, email)
        for account_id, email in account_emails.items()
        if predicate(email.casefold())
    ]
    matches.sort(key=lambda pair: order.get(pair[0], len(order)))
    return matches


def _account_order_cache():
    try:
        client = get_composio_client()
        accounts = client.connected_accounts.list()
        items = getattr(accounts, "items", accounts) or []
        # Composio returns newest first; preserve that ordering.
        return list(items)
    except Exception:  # noqa: BLE001 -- ordering degrades to insertion order
        return []


def resolve_account_target(
    telegram_user_id: int | str,
    account_target: str | None = None,
) -> tuple[str | None, str | None]:
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
        distinct_accounts: list[tuple[str, str]] = []
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

    email_matches = _matches_newest_first(account_emails, lambda e: e == clean_target)
    if email_matches:
        return email_matches[0]

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


def get_user_email(telegram_user_id: int | str) -> str | None:
    """Retrieve the first active email address or ``None``."""
    emails = get_user_emails(telegram_user_id)
    return next(iter(emails.values()), None)


def list_user_connections(telegram_user_id: int | str) -> list[dict]:
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
    except Exception as exc:  # noqa: BLE001 -- listing degrades to empty with a log line
        logger.error("Failed to list active connections for %s: %s", user_id, exc)
    return results


def disconnect_user(
    telegram_user_id: int | str,
    app: str = "gmail",
    target_identifier: str | None = None,
) -> tuple[bool, list[str]]:
    """Revoke active accounts, optionally selecting one explicit target."""
    user_id = format_user_id(telegram_user_id)
    target = str(target_identifier).strip() if target_identifier is not None else ""
    account_emails = get_user_emails(telegram_user_id)
    target_acc_id: str | None = None
    target_email: str | None = None
    if target and target.casefold() != "all":
        target_acc_id, target_email = resolve_account_target(telegram_user_id, target)

    client = get_composio_client()
    app_name = app.lower() if app else ""
    if app_name in ("google_calendar", "calendar"):
        app_name = "googlecalendar"
    disconnected_emails: list[str] = []

    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
        items = getattr(accounts, "items", accounts)
        deleted_ids: set[str] = set()
        for item in items:
            item_id = str(_item_value(item, "id", "") or "")
            if not item_id:
                continue
            item_email = account_emails.get(item_id, "")
            if (
                target
                and target.casefold() != "all"
                and item_id != target_acc_id
                and item_email.casefold() != (target_email or "").casefold()
            ):
                continue
            slug = _toolkit_slug(item).lower()
            if app_name and slug != app_name and app_name not in slug:
                continue
            try:
                client.connected_accounts.delete(item_id)
                deleted_ids.add(item_id)
                if item_email and item_email not in disconnected_emails:
                    disconnected_emails.append(item_email)
            except Exception as exc:  # noqa: BLE001 -- one failed revoke must not abort the batch
                logger.warning(
                    "Failed to delete connected account %s: %s", item_id, exc
                )

        cache_path = _account_email_cache_path()
        if cache_path.is_file():
            try:
                if not target or target.casefold() == "all":
                    cache_path.unlink(missing_ok=True)
                else:
                    cache = json.loads(cache_path.read_text(encoding="utf-8"))
                    if isinstance(cache, dict):
                        cache = {
                            key: value
                            for key, value in cache.items()
                            if key not in deleted_ids
                        }
                        cache_path.write_text(
                            json.dumps(cache, ensure_ascii=False), encoding="utf-8"
                        )
            except (OSError, ValueError, TypeError) as exc:
                logger.warning("Failed to update email cache on disconnect: %s", exc)
        return True, disconnected_emails
    except Exception as exc:  # noqa: BLE001 -- disconnect degrades to False with a log line
        logger.error("Failed to disconnect user %s: %s", user_id, exc)
        return False, []


def get_account_service_states(telegram_user_id: int | str) -> dict[str, dict]:
    """Assess all six Google services for every active connection.

    Returns {service: {"state": ..., "accounts": [{account_id, email, state,
    reason, scope}]}}. A service is ready if at least one active account can
    exercise it; needs_scope when accounts exist but scopes do not cover it.
    """
    user_id = format_user_id(telegram_user_id)
    account_emails = get_user_emails(telegram_user_id)
    result: dict[str, dict] = {}
    try:
        items = [
            item
            for item in _connected_accounts(user_id)
            if str(_item_value(item, "status", "") or "").upper() == "ACTIVE"
        ]
    except Exception as exc:  # noqa: BLE001 -- assessment degrades with a log line
        logger.error("Failed to assess Google services for %s: %s", user_id, exc)
        items = []
    for service in SERVICES:
        rows = []
        for item in items:
            account_id = str(_item_value(item, "id", "") or "")
            assessment = assess_service(item, service)
            rows.append(
                {
                    "account_id": account_id,
                    "email": account_emails.get(account_id, ""),
                    "state": assessment["state"],
                    "reason": assessment.get("reason", ""),
                    "scope": assessment.get("scope", ""),
                }
            )
        ready = [row for row in rows if row["state"] == "ready"]
        result[service] = {
            "state": "ready" if ready else ("needs_scope" if rows else "not_connected"),
            "accounts": rows,
        }
    return result


def has_service_capability(telegram_user_id: int | str, service: str) -> bool:
    """Return True only when an active account holds the service's scope."""
    user_id = format_user_id(telegram_user_id)
    try:
        items = [
            item
            for item in _connected_accounts(user_id)
            if str(_item_value(item, "status", "") or "").upper() == "ACTIVE"
        ]
    except Exception as exc:  # noqa: BLE001 -- check degrades to False with a log line
        logger.error("Failed checking %s capability for %s: %s", service, user_id, exc)
        return False
    return any(assess_service(item, service)["state"] == "ready" for item in items)


def select_service_account(
    telegram_user_id: int | str,
    service: str,
    account_email: str | None = None,
) -> dict[str, Any]:
    """Select the account to use for a service call without guessing.

    Resolution order: explicit email -> single ready account -> error naming
    candidates. Never falls back to the first account when multiple exist.
    """
    user_id = format_user_id(telegram_user_id)
    account_emails = get_user_emails(telegram_user_id)
    try:
        items = [
            item
            for item in _connected_accounts(user_id)
            if str(_item_value(item, "status", "") or "").upper() == "ACTIVE"
        ]
    except Exception as exc:
        raise ValueError(f"account_lookup_failed:{exc}") from exc
    ready = [
        (str(_item_value(item, "id", "") or ""), item)
        for item in items
        if assess_service(item, service)["state"] == "ready"
    ]
    # Newest connection first so a re-login of the same mailbox supersedes the
    # previous session (its scopes/token replace the older grant) instead of
    # the stale one shadowing it.
    ready.sort(
        key=lambda pair: str(_item_value(pair[1], "created_at", "") or ""), reverse=True
    )
    if account_email:
        wanted = account_email.strip().casefold()
        matches = [
            (account_id, item)
            for account_id, item in ready
            if account_emails.get(account_id, "").casefold() == wanted
        ]
        if not matches:
            raise ValueError(f"account_target_not_found:{account_email}")
        # Newest-first (sorted above): a re-login supersedes older sessions.
        account_id, item = matches[0]
        return {
            "account_id": account_id,
            "email": account_emails[account_id],
            "scopes": sorted(extract_scopes(item)),
        }
    distinct = []
    seen: set[str] = set()
    for account_id, _item in ready:
        email = account_emails.get(account_id, "")
        if email and email.casefold() in seen:
            continue
        seen.add(email.casefold())
        distinct.append((account_id, email))
    if len(distinct) == 1:
        account_id, email = distinct[0]
        return {"account_id": account_id, "email": email, "scopes": []}
    if not distinct:
        raise ValueError(f"service_not_ready:{service}")
    raise ValueError(
        "account_selection_required:"
        + ",".join(email or account_id for account_id, email in distinct)
    )
