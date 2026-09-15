"""Official Zalo Bot Platform adapter for private and group messages."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

try:
    import httpx
except ImportError:  # pragma: no cover - the plugin registry checks this dependency
    httpx = None  # type: ignore[assignment]

from agent.redact import redact_sensitive_text
from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    _AUDIO_MIME_TYPES,
    SUPPORTED_IMAGE_DOCUMENT_TYPES,
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_audio_from_url,
    cache_image_from_url,
)

from . import media_publish

_HTTPX_ERROR = httpx.HTTPError if httpx is not None else RuntimeError


logger = logging.getLogger(__name__)

API_ORIGIN = "https://bot-api.zaloplatforms.com"
MAX_MESSAGE_LENGTH = 2000
POLL_TIMEOUT = "30"
POLL_BACKOFF_INITIAL = 1.0
POLL_BACKOFF_MAX = 30.0
POLL_IDLE_DELAY = 0.1
_SUPPORTED_METHODS = frozenset(
    {
        "getMe",
        "getWebhookInfo",
        "getUpdates",
        "sendMessage",
        "sendChatAction",
        "sendPhoto",
    }
)
_MEDIA_PLACEHOLDER = "(The user sent a message with no text content)"
_BOT_DISPLAY_NAME_ENV = "ZALO_BOT_DISPLAY_NAME"


def _normalize_group_command_text(text: str, chat_type: str) -> str:
    """Rewrite a leading exact configured bot mention into a slash command.

    Zalo delivers group texts with the mention rendered as
    ``@<display name>``. ``MessageEvent.get_command`` only recognizes text
    that starts with ``/``, so the gateway would otherwise treat
    ``@Bot <name> /help`` as ordinary prose. Only an exact
    ``@<ZALO_BOT_DISPLAY_NAME>`` prefix followed by whitespace is rewritten,
    and only for group messages; everything else passes through untouched.
    """
    if chat_type != "group":
        return text
    display_name = os.environ.get(_BOT_DISPLAY_NAME_ENV, "").strip()
    if not display_name:
        return text
    mention = f"@{display_name}"
    if not text.startswith(mention):
        return text
    remainder = text[len(mention) :]
    if not remainder[:1].isspace():
        return text
    return remainder.lstrip()


_SUPPORTED_CHAT_TYPES = {"PRIVATE": "dm", "GROUP": "group"}
_MAX_OBSERVED_CHATS = 512


def _undownloadable_note(label: str) -> str:
    """Text the agent sees when inbound media could not be cached locally."""
    return f"[The user sent {label}, but it could not be downloaded]"


async def _cache_remote_media(
    url: str,
    fetch,
    supported: dict[str, str],
    default_ext: str,
    label: str,
) -> tuple[str, str] | None:
    """Download *url* into the local media cache.

    Returns ``(path, mime_type)``, or ``None`` when the URL is missing or the
    download is refused/fails — the caller then falls back to a text note.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    normalized_url = url.strip()
    try:
        extension = Path(urlparse(normalized_url).path).suffix.lower()
        if extension not in supported:
            extension = default_ext
        path = await fetch(normalized_url, extension)
    except (ValueError, OSError, RuntimeError, _HTTPX_ERROR) as exc:
        logger.warning("[zalo] inbound %s unavailable (%s)", label, type(exc).__name__)
        return None
    return path, supported.get(Path(path).suffix.lower(), supported[extension])


async def _cache_zalo_image(url: str) -> tuple[str, str] | None:
    return await _cache_remote_media(
        url, cache_image_from_url, SUPPORTED_IMAGE_DOCUMENT_TYPES, ".jpg", "image"
    )


async def _cache_zalo_voice(url: str) -> tuple[str, str] | None:
    return await _cache_remote_media(
        url, cache_audio_from_url, _AUDIO_MIME_TYPES, ".ogg", "voice message"
    )


class ZaloAPIError(Exception):
    """Sanitized Zalo API failure with a numeric provider/status code."""

    def __init__(self, message: str, *, code: int = 0, retryable: bool = False):
        self.code = code if isinstance(code, int) and not isinstance(code, bool) else 0
        self.retryable = bool(retryable)
        super().__init__(message)


class _TokenLogFilter(logging.Filter):
    """Remove this adapter's token from HTTPX/HTTPCore records."""

    def __init__(self, token: str):
        super().__init__()
        self._token = token
        self._encoded_token = quote(token, safe="")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            if self._token:
                message = message.replace(self._token, "[redacted]")
            if self._encoded_token and self._encoded_token != self._token:
                message = message.replace(self._encoded_token, "[redacted]")
            record.msg = redact_sensitive_text(
                message,
                force=True,
                redact_url_credentials=True,
            )
            record.args = ()
        except (TypeError, ValueError):
            record.msg = "HTTP transport log suppressed"
            record.args = ()
        return True


class ZaloAdapter(BasePlatformAdapter):
    """Long-polling adapter for official Zalo Bot Platform private and group messages."""

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH
    splits_long_messages = True

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform("zalo"))
        self._token = self._configured_token(config)
        self._client: httpx.AsyncClient | None = None
        self._poll_task: asyncio.Task | None = None
        self._bot_id: str | None = None
        self._lock_acquired = False
        self._http_log_filter: _TokenLogFilter | None = None
        self._http_loggers: list[logging.Logger] = []
        self._observed_chat_types: dict[str, str] = {}

    @staticmethod
    def _configured_token(config: PlatformConfig) -> str:
        return str(os.environ.get("ZALO_BOT_TOKEN") or config.token or "").strip()

    @staticmethod
    def _error_code(payload: Any) -> int:
        if isinstance(payload, dict):
            code = payload.get("error_code")
            if isinstance(code, int) and not isinstance(code, bool):
                return code
        return 0

    @staticmethod
    def _retryable_code(code: int) -> bool:
        return code == 0 or code in {408, 429} or code >= 500

    @staticmethod
    def _split_text(content: str) -> list[str]:
        """Split without adding markers, preserving every original code point."""
        if not content:
            return []
        chunks: list[str] = []
        start = 0
        units = 0
        for index, character in enumerate(content):
            width = 2 if ord(character) > 0xFFFF else 1
            if units and units + width > MAX_MESSAGE_LENGTH:
                chunks.append(content[start:index])
                start = index
                units = 0
            units += width
        if start < len(content):
            chunks.append(content[start:])
        return chunks

    def _install_http_log_filter(self) -> None:
        if self._http_log_filter is not None:
            return
        if not self._token:
            return
        log_filter = _TokenLogFilter(self._token)
        logger_names = (
            "httpx",
            "httpcore",
            "httpcore.connection",
            "httpcore.http11",
            "httpcore.http2",
            "httpcore.proxy",
            "httpcore.socks",
        )
        for name in logger_names:
            transport_logger = logging.getLogger(name)
            transport_logger.addFilter(log_filter)
            self._http_loggers.append(transport_logger)
        self._http_log_filter = log_filter

    def _remove_http_log_filter(self) -> None:
        log_filter = self._http_log_filter
        if log_filter is None:
            return
        for transport_logger in self._http_loggers:
            transport_logger.removeFilter(log_filter)
        self._http_loggers.clear()
        self._http_log_filter = None

    async def _close_client(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.aclose()
            except (RuntimeError, _HTTPX_ERROR) as error:
                logger.warning("[zalo] client close failed (%s)", type(error).__name__)
        self._remove_http_log_filter()

    async def _rollback_connect(self) -> None:
        self._running = False
        await self._close_client()
        if self._lock_acquired:
            self._release_platform_lock()
            self._lock_acquired = False
        self._bot_id = None
        self._mark_disconnected()

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        """Authenticate, reject configured webhooks, and start long polling."""
        del is_reconnect
        if (
            self.is_connected
            and self._client is not None
            and self._poll_task is not None
            and not self._poll_task.done()
        ):
            return True
        if self._poll_task is not None and self._poll_task.done():
            self._poll_task = None
            await self._close_client()
            if self._lock_acquired:
                self._release_platform_lock()
                self._lock_acquired = False
            self._bot_id = None
            self._running = False
        if httpx is None:
            message = "Zalo startup failed: httpx is required"
            self._set_fatal_error("zalo_missing_dependency", message, retryable=False)
            logger.warning("[zalo] %s", message)
            return False

        self._token = self._configured_token(self.config)
        if not self._token:
            message = "Zalo startup failed: ZALO_BOT_TOKEN is required"
            self._set_fatal_error("zalo_missing_token", message, retryable=False)
            logger.warning("[zalo] %s", message)
            return False

        if not self._acquire_platform_lock("zalo", self._token, "Zalo bot token"):
            return False
        self._lock_acquired = True
        try:
            self._install_http_log_filter()
            self._client = httpx.AsyncClient(timeout=40.0)

            me = await self._request("getMe")
            bot_id = me.get("id") if isinstance(me, dict) else None
            if not isinstance(bot_id, str) or not bot_id.strip():
                self._set_fatal_error(
                    "zalo_invalid_identity",
                    "Zalo getMe returned no bot id",
                    retryable=False,
                )
                logger.warning("[zalo] getMe returned no bot id")
                await self._rollback_connect()
                return False
            self._bot_id = bot_id.strip()

            try:
                webhook = await self._request("getWebhookInfo")
                webhook_url = webhook.get("url") if isinstance(webhook, dict) else None
            except ZaloAPIError as exc:
                if exc.code == 404:
                    webhook_url = None
                else:
                    raise
            if webhook_url is not None and not isinstance(webhook_url, str):
                self._set_fatal_error(
                    "zalo_invalid_webhook_info",
                    "Zalo webhook information was malformed",
                    retryable=False,
                )
                logger.warning("[zalo] webhook information was malformed")
                await self._rollback_connect()
                return False
            if isinstance(webhook_url, str) and webhook_url.strip():
                self._set_fatal_error(
                    "zalo_webhook_configured",
                    "Zalo webhook is configured; remove it before enabling polling",
                    retryable=False,
                )
                logger.error("[zalo] webhook is configured; polling was not started")
                await self._rollback_connect()
                return False

            self._mark_connected()
            self._poll_task = asyncio.create_task(self._poll_loop(), name="zalo-poll")
            logger.info("[zalo] connected with long polling")
            return True
        except asyncio.CancelledError:
            await self._rollback_connect()
            raise
        except ZaloAPIError as exc:
            retryable = exc.retryable
            code = exc.code
            self._set_fatal_error(
                "zalo_auth_failed" if not retryable else "zalo_connect_error",
                "Zalo authentication failed"
                if not retryable
                else "Zalo connection failed",
                retryable=retryable,
            )
            logger.warning("[zalo] connection failed (code=%d)", code)
            await self._rollback_connect()
            return False
        except (RuntimeError, httpx.HTTPError):
            self._set_fatal_error(
                "zalo_connect_error",
                "Zalo connection failed",
                retryable=True,
            )
            logger.warning("[zalo] connection failed")
            await self._rollback_connect()
            return False

    async def disconnect(self) -> None:
        """Stop polling, cancel base work, close HTTPX, and release the lock."""
        self._running = False
        poll_task = self._poll_task
        self._poll_task = None
        if (
            poll_task is not None
            and poll_task is not asyncio.current_task()
            and not poll_task.done()
        ):
            poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poll_task
        await self.cancel_background_tasks()
        await self._close_client()
        if self._lock_acquired:
            self._release_platform_lock()
            self._lock_acquired = False
        self._bot_id = None
        self._mark_disconnected()

    async def _request(
        self, method: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST one official Zalo method and return its result object."""
        if self._client is None or not self._token:
            raise ZaloAPIError("Zalo client is not connected", code=0, retryable=True)
        if method not in _SUPPORTED_METHODS:
            raise ZaloAPIError("Unsupported Zalo method", code=0, retryable=False)
        if data is not None and not isinstance(data, dict):
            raise ZaloAPIError(
                "Zalo request data was malformed", code=0, retryable=False
            )

        url = f"{API_ORIGIN}/bot{quote(self._token, safe=':')}/{method}"
        try:
            response = await self._client.post(url, json=data or {})
        except httpx.TimeoutException:
            raise ZaloAPIError(
                "Zalo request timed out", code=0, retryable=True
            ) from None
        except httpx.HTTPError:
            raise ZaloAPIError("Zalo request failed", code=0, retryable=True) from None
        except (RuntimeError, TypeError, ValueError):
            raise ZaloAPIError("Zalo request failed", code=0, retryable=True) from None

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise ZaloAPIError("Zalo response was malformed", code=0, retryable=True)
        if status_code < 200 or status_code >= 300:
            code = status_code
            raise ZaloAPIError(
                "Zalo request failed",
                code=code,
                retryable=self._retryable_code(code),
            )
        try:
            payload = response.json()
        except (TypeError, ValueError):
            raise ZaloAPIError(
                "Zalo response was malformed", code=0, retryable=True
            ) from None
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            code = self._error_code(payload)
            raise ZaloAPIError(
                "Zalo API returned an error",
                code=code,
                retryable=self._retryable_code(code),
            )
        if method == "sendChatAction" and "result" not in payload:
            return {}
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ZaloAPIError("Zalo response was malformed", code=0, retryable=True)
        return result

    async def _dispatch_update(self, result: dict[str, Any]) -> None:
        event_name = result.get("event_name")
        message = result.get("message")
        if not isinstance(message, dict):
            logger.debug("[zalo] ignoring malformed update without message")
            return

        sender = message.get("from")
        chat = message.get("chat")
        if not isinstance(sender, dict) or not isinstance(chat, dict):
            logger.debug("[zalo] ignoring malformed update without sender/chat")
            return

        sender_id = sender.get("id")
        chat_id = chat.get("id")
        display_name = sender.get("display_name")
        message_id = message.get("message_id")
        raw_chat_type = chat.get("chat_type")
        source_chat_type = (
            _SUPPORTED_CHAT_TYPES.get(raw_chat_type)
            if isinstance(raw_chat_type, str)
            else None
        )
        if (
            not isinstance(sender_id, str)
            or not sender_id.strip()
            or not isinstance(chat_id, str)
            or not chat_id.strip()
            or not isinstance(display_name, str)
            or not isinstance(message_id, str)
            or not message_id.strip()
            or source_chat_type is None
            or sender.get("is_bot") is not False
        ):
            logger.debug("[zalo] ignoring malformed or unsupported update")
            return

        if self._bot_id and sender_id.strip() == self._bot_id:
            logger.debug("[zalo] ignoring self update")
            return

        normalized_chat_id = chat_id.strip()
        normalized_user_id = sender_id.strip()
        user_name = display_name.strip()
        normalized_message_id = message_id.strip()
        self._remember_chat_type(normalized_chat_id, source_chat_type)

        def make_event(
            text: str,
            message_type: MessageType,
            cached: tuple[str, str] | None,
        ) -> MessageEvent:
            return MessageEvent(
                text=text,
                message_type=message_type,
                user_id=normalized_user_id,
                user_name=user_name or None,
                source=self.build_source(
                    chat_id=normalized_chat_id,
                    user_id=normalized_user_id,
                    user_name=user_name or None,
                    chat_type=source_chat_type,
                    message_id=normalized_message_id,
                ),
                raw_message=result,
                message_id=normalized_message_id,
                media_urls=[cached[0]] if cached else [],
                media_types=[cached[1]] if cached else [],
            )

        # Route unsupported events through the gateway so normal authorization applies.
        if event_name == "message.unsupported.received":
            unsupported_text = (
                "⚠️ Zalo Bot Platform hiện tại chưa hỗ trợ nhận tệp đính kèm "
                "trong chat bot. Vui lòng dán nội dung văn bản trực tiếp hoặc "
                "gửi tài liệu qua kênh Telegram của Hermes."
            )
            await self.handle_message(
                make_event(unsupported_text, MessageType.TEXT, None)
            )
            return

        if event_name == "message.sticker.received":
            cached = await _cache_zalo_image(str(message.get("url") or ""))
            text = (
                "[The user reacted with a sticker — reply to its intent in one "
                "short natural sentence, do not describe the sticker]"
                if cached
                else _undownloadable_note("a sticker")
            )
            await self.handle_message(make_event(text, MessageType.STICKER, cached))
            return

        if event_name == "message.image.received":
            caption = str(message.get("caption") or "").strip()
            photo_url = str(message.get("photo_url") or message.get("photo") or "")
            cached = await _cache_zalo_image(photo_url)
            text = caption or (
                _MEDIA_PLACEHOLDER if cached else _undownloadable_note("an image")
            )
            await self.handle_message(make_event(text, MessageType.PHOTO, cached))
            return

        if event_name == "message.voice.received":
            cached = await _cache_zalo_voice(str(message.get("voice_url") or ""))
            text = (
                _MEDIA_PLACEHOLDER
                if cached
                else _undownloadable_note("a voice message")
            )
            await self.handle_message(make_event(text, MessageType.VOICE, cached))
            return

        if event_name != "message.text.received":
            logger.debug("[zalo] ignoring unknown update: %s", event_name)
            return

        text = message.get("text")
        if not isinstance(text, str) or not text:
            logger.debug("[zalo] ignoring empty text update")
            return
        text = _normalize_group_command_text(text, source_chat_type)
        if not text:
            logger.debug("[zalo] ignoring empty text update")
            return

        await self.handle_message(make_event(text, MessageType.TEXT, None))

    async def _notify_fatal_failure(self) -> None:
        """Report a fatal polling error, tolerating notification failures."""
        try:
            await self._notify_fatal_error()
        except asyncio.CancelledError:
            raise
        except Exception as notify_error:  # noqa: BLE001 -- polling must survive notify failure
            logger.error(
                "[zalo] fatal notification failed (%s)",
                type(notify_error).__name__,
            )

    async def _poll_loop(self) -> None:
        """Poll until disconnected, backing off transient failures."""
        backoff = POLL_BACKOFF_INITIAL
        while self._running:
            try:
                result = await self._request("getUpdates", {"timeout": POLL_TIMEOUT})
                await self._dispatch_update(result)
                backoff = POLL_BACKOFF_INITIAL
            except asyncio.CancelledError:
                raise
            except ZaloAPIError as exc:
                if not self._running:
                    break
                if exc.code == 408:
                    await asyncio.sleep(POLL_IDLE_DELAY)
                    continue
                if not exc.retryable:
                    self._running = False
                    self._set_fatal_error(
                        "zalo_poll_rejected",
                        "Zalo polling was rejected",
                        retryable=False,
                    )
                    logger.error("[zalo] polling rejected (code=%d)", exc.code)
                    await self._notify_fatal_failure()
                    break
                logger.warning(
                    "[zalo] transient polling failure (code=%d); retrying in %.1fs",
                    exc.code,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, POLL_BACKOFF_MAX)
            except Exception as error:  # noqa: BLE001 -- poll loop crash boundary sets fatal state
                self._running = False
                self._set_fatal_error(
                    "zalo_poll_crashed",
                    "Zalo polling stopped unexpectedly",
                    retryable=True,
                )
                logger.error("[zalo] polling stopped (%s)", type(error).__name__)
                await self._notify_fatal_failure()
                break

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        """Send plain text chunks without retrying ambiguous deliveries."""
        del reply_to, metadata
        if self._client is None or not self.is_connected:
            return SendResult(success=False, error="Not connected", retryable=False)
        if not isinstance(chat_id, str) or not chat_id.strip():
            return SendResult(success=False, error="Invalid chat id", retryable=False)
        if not isinstance(content, str) or not content:
            return SendResult(
                success=False, error="Message content is empty", retryable=False
            )

        message_ids: list[str] = []
        for chunk in self._split_text(content):
            try:
                result = await self._request(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": "markdown",
                    },
                )
            except ZaloAPIError as exc:
                logger.warning("[zalo] send failed (code=%d)", exc.code)
                return SendResult(
                    success=False,
                    message_id=message_ids[-1] if message_ids else None,
                    continuation_message_ids=tuple(message_ids[:-1]),
                    error=f"Zalo send failed (code {exc.code})",
                    retryable=False,
                )
            message_id = result.get("message_id") if isinstance(result, dict) else None
            if isinstance(message_id, bool) or not isinstance(message_id, (str, int)):
                logger.warning("[zalo] send returned no message id")
                return SendResult(
                    success=False,
                    message_id=message_ids[-1] if message_ids else None,
                    error="Zalo send returned no message id",
                    retryable=False,
                )
            normalized_id = str(message_id).strip()
            if not normalized_id:
                logger.warning("[zalo] send returned no message id")
                return SendResult(
                    success=False,
                    message_id=message_ids[-1] if message_ids else None,
                    error="Zalo send returned no message id",
                    retryable=False,
                )
            message_ids.append(normalized_id)

        return SendResult(
            success=True,
            message_id=message_ids[-1],
            continuation_message_ids=tuple(message_ids[:-1]),
        )

    async def _send_photo(
        self, chat_id: str, photo: str, caption: str | None
    ) -> SendResult:
        try:
            result = await self._request(
                "sendPhoto",
                {
                    "chat_id": str(chat_id),
                    "photo": photo,
                    **({"caption": caption} if caption else {}),
                },
            )
        except ZaloAPIError as exc:
            logger.warning("[zalo] sendPhoto failed (code=%d)", exc.code)
            return SendResult(
                success=False,
                error=f"Zalo sendPhoto failed (code {exc.code})",
                retryable=exc.retryable,
            )
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if (
            isinstance(message_id, bool)
            or not isinstance(message_id, (str, int))
            or not str(message_id).strip()
        ):
            return SendResult(
                success=False, error="Zalo sendPhoto returned no message id"
            )
        return SendResult(success=True, message_id=str(message_id).strip())

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        del reply_to, metadata
        if self._client is None or not self.is_connected:
            return SendResult(success=False, error="Not connected", retryable=False)
        if not isinstance(image_url, str) or not image_url.lower().startswith(
            ("http://", "https://")
        ):
            return await super().send_image(chat_id, image_url, caption=caption)
        return await self._send_photo(chat_id, image_url.strip(), caption)

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> SendResult:
        del reply_to, metadata, kwargs
        if self._client is None or not self.is_connected:
            return SendResult(success=False, error="Not connected", retryable=False)
        try:
            url = media_publish.publish_image(image_path)
        except media_publish.PhotoPublishError as exc:
            logger.warning("[zalo] local image publish failed: %s", exc)
            return SendResult(
                success=False, error=f"Image publish failed: {exc}", retryable=False
            )
        result = await self._send_photo(chat_id, url, caption)
        if not result.success:
            logger.warning(
                "[zalo] photo delivery failed after publish: %s", result.error
            )
        return result

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        del metadata
        if self._client is None or not self.is_connected:
            return
        try:
            await self._request(
                "sendChatAction", {"chat_id": str(chat_id), "action": "typing"}
            )
        except (ZaloAPIError, RuntimeError, _HTTPX_ERROR) as exc:
            logger.debug("[zalo] send_typing failed: %s", type(exc).__name__)

    def _remember_chat_type(self, chat_id: str, chat_type: str) -> None:
        observed = self._observed_chat_types
        if chat_id not in observed and len(observed) >= _MAX_OBSERVED_CHATS:
            observed.pop(next(iter(observed)))
        observed[chat_id] = chat_type

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        observed_type = self._observed_chat_types.get(chat_id)
        if not isinstance(observed_type, str) or observed_type not in {"dm", "group"}:
            observed_type = "unknown"
        return {
            "name": chat_id,
            "type": observed_type,
            "chat_id": chat_id,
        }


def check_zalo_requirements() -> bool:
    """Return whether the required HTTP client dependency is importable."""
    return httpx is not None and hasattr(httpx, "AsyncClient")


def validate_config(config: PlatformConfig) -> bool:
    """Return whether a real token is available from env or config."""
    return bool(ZaloAdapter._configured_token(config))
