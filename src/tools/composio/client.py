"""Composio client helpers with lazy provider loading."""

from __future__ import annotations

from collections.abc import Mapping
import importlib
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

_client_instance: Any | None = None
_FAILURE_STATUSES = frozenset(
    {
        "error",
        "failed",
        "failure",
        "fail",
        "rejected",
        "declined",
        "denied",
        "unauthorized",
        "unauthenticated",
        "tool_not_found",
        "unknown_tool",
        "unsupported_tool",
        "tool_unavailable",
        "tool-not-found",
        "unknown-tool",
        "unsupported-tool",
        "tool-unavailable",
        "not_found",
        "unavailable",
        "unsupported",
    }
)
_SUCCESS_STATUSES = frozenset({"success", "ok", "confirmed", "active", "connected"})
_UNAVAILABLE_TOOL_MARKERS = (
    "tool_not_found",
    "tool-not-found",
    "tool not found",
    "unknown_tool",
    "unknown-tool",
    "unknown tool",
    "unsupported_tool",
    "unsupported-tool",
    "unsupported tool",
    "tool_unavailable",
    "tool-unavailable",
    "tool unavailable",
)


class ComposioExecutionError(RuntimeError):
    """Raised when the SDK reports a failed tool execution."""

    def __init__(self, message: str, *, unavailable_tool: bool = False) -> None:
        super().__init__(message)
        self.unavailable_tool = unavailable_tool


def format_user_id(
    user_identifier: int | str | None, platform: str = "telegram"
) -> str:
    """Format a Hermes identifier as a stable Composio entity ID."""
    if user_identifier is None:
        raise ValueError("user_identifier cannot be None")
    raw = str(user_identifier).strip()
    if not raw:
        raise ValueError("user_identifier cannot be empty")

    if ":" in raw:
        parts = raw.split(":", 2)
        plat = parts[0].strip().lower()
        uid = parts[2] if len(parts) == 3 else parts[1]
        if not plat or not uid.strip():
            raise ValueError("invalid user identifier")
        return f"{plat}_{uid.strip()}"

    if "_" in raw and not raw.isdigit():
        return raw.lower()

    plat = str(platform).strip().lower() if platform else "telegram"
    if not plat:
        plat = "telegram"
    return f"{plat}_{raw}"


def _load_sdk() -> tuple[Any, type[BaseException]]:
    try:
        module = importlib.import_module("composio")
    except ImportError as exc:
        raise RuntimeError(
            "Composio SDK is required only when a provider operation runs."
        ) from exc

    composio_class = getattr(module, "Composio", None)
    if composio_class is None:
        from importlib.metadata import version

        try:
            installed = version("composio")
        except Exception:  # noqa: BLE001 -- version lookup is best-effort
            installed = "unknown"
        raise RuntimeError(
            f"Installed Composio SDK {installed} does not expose Composio. "
            "The gateway Python environment needs composio>=0.21: run "
            "'uv pip install --python \"$(command -v python3)\" "
            "\"composio>=0.21.0,<1\"' inside the gateway's venv, or reinstall "
            "the hermes CLI so its tool venv picks up the current dependency."
        )

    try:
        exceptions = importlib.import_module("composio.exceptions")
    except ImportError:
        return composio_class, RuntimeError
    return composio_class, getattr(exceptions, "ApiKeyError", RuntimeError)


def get_response_data(result: Any) -> Any:
    """Return the SDK response payload without importing the provider SDK."""
    if isinstance(result, Mapping):
        return result
    return getattr(result, "data", result)


def _is_present(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, list, tuple, set)):
        return bool(value)
    return not value.__class__.__module__.startswith("unittest.mock")


def _error_text(value: Any) -> str | None:
    if not _is_present(value):
        return None
    if isinstance(value, BaseException):
        return str(value) or value.__class__.__name__
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping):
        for key in ("message", "detail", "reason", "description", "code"):
            text = _error_text(value.get(key))
            if text:
                return text
        status = value.get("status")
        if status is not None:
            status_text = str(status).strip()
            if status_text.casefold() not in _SUCCESS_STATUSES:
                return status_text or None
        for key in ("error", "failure", "errors"):
            text = _error_text(value.get(key))
            if text:
                return text
        return None

    for attr in ("message", "detail", "reason", "description", "code"):
        text = _error_text(getattr(value, attr, None))
        if text:
            return text
    status = getattr(value, "status", None)
    if status is not None:
        status_text = str(status).strip()
        if status_text.casefold() not in _SUCCESS_STATUSES:
            return status_text or None
    return str(value)


def _payload_error(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None

    error = _error_text(payload.get("error"))
    if error:
        return error
    for key in ("failure", "failures", "errors"):
        error = _error_text(payload.get(key))
        if error:
            return error

    status = payload.get("status")
    if isinstance(status, str) and status.strip().lower() in _FAILURE_STATUSES:
        return status.strip()

    for key in ("response_data", "result", "data"):
        error = _payload_error(payload.get(key))
        if error:
            return error
    return None


def get_response_error(result: Any) -> str | None:
    """Extract SDK and nested provider failure envelopes before success handling."""
    if isinstance(result, Mapping):
        return _payload_error(result)

    error = _error_text(getattr(result, "error", None))
    if error:
        return error
    return _payload_error(get_response_data(result))


def is_unavailable_tool_error(error: Any) -> bool:
    """Return true only for errors proving that a tool slug is unavailable."""
    if isinstance(error, ComposioExecutionError):
        if error.unavailable_tool:
            return True
        error = str(error)
    class_name = re.sub(r"(?<!^)(?=[A-Z])", " ", error.__class__.__name__).casefold()
    text = _error_text(error) or ""
    lowered = re.sub(r"[\s:/]+", " ", f"{class_name} {text}".casefold())
    if any(
        marker.replace("_", " ").replace("-", " ") in lowered
        for marker in _UNAVAILABLE_TOOL_MARKERS
    ):
        return True
    return bool(
        "tool" in lowered
        and any(
            phrase in lowered
            for phrase in ("not found", "does not exist", "unavailable", "unsupported")
        )
    )


_SERVICE_TOOLKIT_PREFIXES = (
    "GMAIL_",
    "GOOGLEDRIVE_",
    "GOOGLEDOCS_",
    "GOOGLESHEETS_",
    "GOOGLESLIDES_",
)


def rewrite_slug_for_account(tool_slug: str, account: str | None) -> str:
    """Rewrite service-prefixed slugs to the account's toolkit slug.

    Composio routes tool execution by the account's toolkit, not by the
    service prefix in the slug. A googlesuper session rejects
    ``GOOGLEDOCS_GET_DOCUMENT_BY_ID`` with "No active connection found for
    toolkit 'googledocs'" even when the account holds full Workspace scopes;
    the same action executes as ``GOOGLESUPER_GET_DOCUMENT_BY_ID``.
    """
    if not account:
        return tool_slug
    prefix = next(
        (p for p in _SERVICE_TOOLKIT_PREFIXES if tool_slug.startswith(p)),
        None,
    )
    if prefix is None:
        return tool_slug
    toolkit = _toolkit_for_account(account)
    if not toolkit or toolkit.lower() == prefix.removesuffix("_").lower():
        return tool_slug
    return f"{toolkit.upper()}_{tool_slug.removeprefix(prefix)}"


def _toolkit_for_account(account: str) -> str | None:
    try:
        selected = get_composio_client().connected_accounts.get(account)
    except Exception:  # noqa: BLE001 -- unknown account keeps the original slug
        return None
    toolkit = getattr(getattr(selected, "toolkit", None), "slug", None)
    if not toolkit and isinstance(selected, Mapping):
        toolkit = _error_text(selected.get("toolkit"))
    return toolkit


def execute_composio_tool(
    session: Any,
    tool_slug: str,
    *,
    fallback_slug: str | None = None,
    **kwargs: Any,
) -> Any:
    """Execute a tool and retry a second slug only after a proven slug miss."""
    account = kwargs.get("account")
    if isinstance(account, str):
        tool_slug = rewrite_slug_for_account(tool_slug, account)

    def execute_once(slug: str) -> Any:
        try:
            result = session.execute(tool_slug=slug, **kwargs)
        except Exception as exc:
            if is_unavailable_tool_error(exc):
                raise ComposioExecutionError(str(exc), unavailable_tool=True) from exc
            raise
        error = get_response_error(result)
        if error:
            raise ComposioExecutionError(
                error,
                unavailable_tool=is_unavailable_tool_error(error),
            )
        return result

    try:
        return execute_once(tool_slug)
    except ComposioExecutionError as exc:
        if not fallback_slug or not exc.unavailable_tool:
            raise
        return execute_once(fallback_slug)


def get_composio_client(force_refresh: bool = False) -> Any:
    """Retrieve or initialize the Composio client singleton lazily."""
    global _client_instance
    if _client_instance is not None and not force_refresh:
        return _client_instance

    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        env_locations = [
            os.path.expanduser("~/.hermes/.env"),
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
            ),
        ]
        for env_path in env_locations:
            if os.path.isfile(env_path):
                try:
                    with open(env_path, encoding="utf-8") as env_file:
                        for line in env_file:
                            if line.strip().startswith("COMPOSIO_API_KEY="):
                                candidate = (
                                    line.strip()
                                    .split("=", 1)[1]
                                    .strip()
                                    .strip('"')
                                    .strip("'")
                                )
                                if candidate:
                                    api_key = candidate
                                    break
                except OSError as exc:
                    logger.debug("Failed to read env file %s: %s", env_path, exc)
            if api_key:
                break

    if not api_key:
        raise RuntimeError(
            "COMPOSIO_API_KEY is not configured. "
            "Please add COMPOSIO_API_KEY to ~/.hermes/.env or your environment."
        )

    composio_class, api_key_error = _load_sdk()
    try:
        _client_instance = composio_class(api_key=api_key)
    except api_key_error as exc:
        raise RuntimeError(
            f"COMPOSIO_API_KEY is invalid or expired ({str(exc)}). "
            "Get a fresh API key from https://dashboard.composio.dev and update ~/.hermes/.env."
        ) from exc

    return _client_instance
