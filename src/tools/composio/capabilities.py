"""Google service capability mapping for connected accounts.

Capability reflects granted OAuth scopes on the selected connection, not merely
an ACTIVE account. ``googlesuper`` accounts carry all Google scopes; service
toolkits (gmail, googlecalendar) may appear as separate connections.
"""

from __future__ import annotations

from dataclasses import dataclass

GMAIL_SCOPE = "https://mail.google.com/"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DOCS_SCOPE = "https://www.googleapis.com/auth/documents"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SLIDES_SCOPE = "https://www.googleapis.com/auth/presentations"


@dataclass(frozen=True)
class ServiceCapability:
    """Scope requirements and Composio toolkit slugs for one Google service."""

    service: str
    read_scope: str
    write_scope: str
    toolkits: tuple[str, ...]

    @property
    def read_scope_fallbacks(self) -> tuple[str, ...]:
        return _READ_FALLBACKS.get(self.service, ())


_READ_FALLBACKS: dict[str, tuple[str, ...]] = {
    "gmail": (GMAIL_SCOPE,),
    "calendar": (CALENDAR_SCOPE,),
    "drive": (DRIVE_SCOPE,),
    "docs": (DOCS_SCOPE,),
    "sheets": (SHEETS_SCOPE,),
    "slides": (SLIDES_SCOPE,),
}

SERVICES: dict[str, ServiceCapability] = {
    "gmail": ServiceCapability(
        "gmail", GMAIL_SCOPE, GMAIL_SCOPE, ("gmail", "googlesuper")
    ),
    "calendar": ServiceCapability(
        "calendar", CALENDAR_SCOPE, CALENDAR_SCOPE, ("googlecalendar", "googlesuper")
    ),
    "drive": ServiceCapability(
        "drive", DRIVE_SCOPE, DRIVE_SCOPE, ("googledrive", "googlesuper")
    ),
    "docs": ServiceCapability(
        "docs", DOCS_SCOPE, DOCS_SCOPE, ("googledocs", "googlesuper")
    ),
    "sheets": ServiceCapability(
        "sheets", SHEETS_SCOPE, SHEETS_SCOPE, ("googlesheets", "googlesuper")
    ),
    "slides": ServiceCapability(
        "slides", SLIDES_SCOPE, SLIDES_SCOPE, ("googleslides", "googlesuper")
    ),
}


def normalize_toolkit_slug(slug: str) -> str:
    """Map toolkit spellings to their canonical Composio slug."""
    lowered = slug.strip().lower()
    if lowered in ("google_calendar", "calendar"):
        return "googlecalendar"
    return lowered


def extract_scopes(account: object) -> frozenset[str]:
    """Return granted scope strings from a connected-account object or dict."""
    data = (
        account.get("data")
        if isinstance(account, dict)
        else getattr(account, "data", None)
    )
    raw = ""
    if isinstance(data, dict):
        raw = str(data.get("scope") or "")
    if not raw:
        raw = str(getattr(account, "scope", "") or "")
    return frozenset(s for s in raw.split() if s)


def account_toolkit(account: object) -> str:
    """Return the account's toolkit slug without guessing."""
    if isinstance(account, dict):
        toolkit = account.get("toolkit")
        if isinstance(toolkit, dict):
            return normalize_toolkit_slug(str(toolkit.get("slug") or ""))
        return normalize_toolkit_slug(str(toolkit or ""))
    toolkit = getattr(account, "toolkit", None)
    slug = getattr(toolkit, "slug", None) if toolkit is not None else None
    return normalize_toolkit_slug(str(slug or ""))


def assess_service(account: object, service: str) -> dict[str, str]:
    """Assess one service against one connection.

    Returns {"state": ready|needs_scope|unsupported, ...}. Unknown accounts
    report needs_scope rather than silently claiming readiness.
    """
    cap = SERVICES.get(service)
    if cap is None:
        return {"state": "unsupported", "service": service, "reason": "unknown_service"}
    slug = account_toolkit(account)
    if slug not in cap.toolkits:
        return {
            "state": "unsupported",
            "service": service,
            "reason": "toolkit_mismatch",
            "toolkit": slug,
        }
    granted = extract_scopes(account)
    if not granted:
        return {
            "state": "needs_scope",
            "service": service,
            "reason": "scope_unknown",
            "scope": cap.read_scope,
        }
    if cap.read_scope in granted:
        return {"state": "ready", "service": service, "scope": cap.read_scope}
    return {
        "state": "needs_scope",
        "service": service,
        "reason": "scope_missing",
        "scope": cap.read_scope,
    }
