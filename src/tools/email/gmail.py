from __future__ import annotations

import base64
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional

try:
    from google.auth.exceptions import RefreshError
except ImportError:
    class RefreshError(Exception):
        pass

try:
    from googleapiclient.errors import HttpError
except ImportError:
    class HttpError(Exception):
        resp = type("Response", (), {"status": 500})()

from tools.email.contracts import (
    AttachmentInfo,
    EmailMessage,
    SearchHit,
    ThreadResult,
)

logger = logging.getLogger(__name__)


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts: List[str] = []

    def handle_data(self, data: str):
        self.text_parts.append(data)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def _strip_html(raw_html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(raw_html)
    text = stripper.get_text()
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _decode_b64(raw_b64: str) -> str:
    try:
        # Standard or URL-safe base64 padding correction
        padded = raw_b64 + "=" * (-len(raw_b64) % 4)
        data = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_parts(payload: Dict[str, Any]) -> tuple[str, list[AttachmentInfo]]:
    texts: List[str] = []
    attachments: List[AttachmentInfo] = []

    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    body_data = body.get("data")
    filename = payload.get("filename", "")
    attachment_id = body.get("attachmentId") or payload.get("attachmentId") or ""
    size_bytes = body.get("size") or payload.get("size") or 0

    if filename or attachment_id:
        attachments.append(
            AttachmentInfo(
                attachment_id=attachment_id,
                filename=filename,
                mime_type=mime or "application/octet-stream",
                size_bytes=int(size_bytes),
            )
        )
    elif mime == "text/plain" and body_data:
        texts.append(_decode_b64(body_data))
    elif mime == "text/html" and body_data:
        texts.append(_strip_html(_decode_b64(body_data)))

    for part in payload.get("parts", []):
        sub_text, sub_attachments = _extract_parts(part)
        if sub_text:
            texts.append(sub_text)
        attachments.extend(sub_attachments)

    return "\n".join(texts).strip(), attachments


def _extract_body_parts(payload: Dict[str, Any]) -> str:
    text, _ = _extract_parts(payload)
    return text


def _handle_gmail_error(exc: Exception) -> None:
    if isinstance(exc, RefreshError):
        logger.warning("Token refresh error for Gmail request: %s", exc)
        raise exc
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", None) or getattr(exc, "status_code", None)
        if status in (400, 401):
            logger.warning("Gmail API authentication error (%s): %s", status, exc)
            raise RefreshError(f"invalid_grant: {exc}") from exc
        logger.error("Gmail API HTTP error (%s): %s", status, exc)
        raise exc
    if "invalid_grant" in str(exc).lower():
        raise RefreshError(f"invalid_grant: {exc}") from exc


class GmailReader:
    def __init__(
        self, service_builder: Optional[Callable[[Dict[str, Any]], Any]] = None
    ) -> None:
        self._service_builder = service_builder or self._default_service_builder

    @staticmethod
    def _default_service_builder(token_data: Dict[str, Any]) -> Any:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get(
                "token_uri", "https://oauth2.googleapis.com/token"
            ),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get(
                "scopes", ["https://www.googleapis.com/auth/gmail.readonly"]
            ),
        )
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def search_threads(
        self, token_data: Dict[str, Any], query: str, limit: int = 10
    ) -> tuple[SearchHit, ...]:
        service = self._service_builder(token_data)
        safe_limit = max(1, min(limit, 20))
        try:
            resp = (
                service.users()
                .threads()
                .list(userId="me", q=query, maxResults=safe_limit)
                .execute()
            )
        except Exception as exc:
            _handle_gmail_error(exc)
            raise

        threads = resp.get("threads", [])

        hits: List[SearchHit] = []
        for t in threads:
            t_id = t["id"]
            snippet = html.unescape(t.get("snippet", ""))
            hits.append(
                SearchHit(
                    thread_id=t_id,
                    subject="",  # Subject is populated on get_thread or top message snippet
                    snippet=snippet,
                    last_message_date="",
                    from_address="",
                    attachments=(),
                )
            )
        return tuple(hits)

    def get_thread(
        self, token_data: Dict[str, Any], thread_id: str, text_bytes_max: int = 65536
    ) -> ThreadResult:
        service = self._service_builder(token_data)
        try:
            t = (
                service.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
        except Exception as exc:
            _handle_gmail_error(exc)
            raise

        messages = t.get("messages", [])

        subject = ""
        collected_texts: List[str] = []
        all_attachments: List[AttachmentInfo] = []

        for msg in messages:
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            for h in headers:
                if h.get("name", "").lower() == "subject" and not subject:
                    subject = h.get("value", "")

            body_text, attachments = _extract_parts(payload)
            if body_text:
                collected_texts.append(body_text)
            all_attachments.extend(attachments)

        full_text = "\n\n---\n\n".join(collected_texts)
        encoded = full_text.encode("utf-8")
        truncated = False
        if len(encoded) > text_bytes_max:
            truncated = True
            full_text = encoded[:text_bytes_max].decode("utf-8", errors="ignore")

        return ThreadResult(
            thread_id=thread_id,
            subject=subject,
            text=full_text,
            truncated=truncated,
            attachments=tuple(all_attachments),
        )

    def get_message(
        self,
        token_data: Dict[str, Any],
        message_id: str,
        text_bytes_max: int = 65536,
    ) -> EmailMessage:
        service = self._service_builder(token_data)
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except Exception as exc:
            _handle_gmail_error(exc)
            raise

        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        subject = ""
        from_address = ""
        to_address = ""
        date = ""

        for h in headers:
            name = h.get("name", "").lower()
            val = h.get("value", "")
            if name == "subject":
                subject = val
            elif name == "from":
                from_address = val
            elif name == "to":
                to_address = val
            elif name == "date":
                date = val

        body_text, attachments = _extract_parts(payload)
        encoded = body_text.encode("utf-8")
        if len(encoded) > text_bytes_max:
            body_text = encoded[:text_bytes_max].decode("utf-8", errors="ignore")

        return EmailMessage(
            message_id=message_id,
            thread_id=msg.get("threadId", ""),
            subject=subject,
            from_address=from_address,
            to_address=to_address,
            date=date,
            body_text=body_text,
            attachments=tuple(attachments),
        )

    def search_messages(
        self, token_data: Dict[str, Any], query: str, limit: int = 10
    ) -> tuple[EmailMessage, ...]:
        service = self._service_builder(token_data)
        safe_limit = max(1, min(limit, 20))
        try:
            resp = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=safe_limit)
                .execute()
            )
        except Exception as exc:
            _handle_gmail_error(exc)
            raise

        messages_meta = resp.get("messages", [])
        if not messages_meta:
            return ()

        msg_ids = [m["id"] for m in messages_meta if "id" in m]
        if not msg_ids:
            return ()

        if len(msg_ids) == 1:
            return (self.get_message(token_data, msg_ids[0]),)

        def _fetch(m_id: str) -> EmailMessage:
            return self.get_message(token_data, m_id)

        with ThreadPoolExecutor(max_workers=min(len(msg_ids), 10)) as executor:
            messages = list(executor.map(_fetch, msg_ids))

        return tuple(messages)

    def get_attachment(
        self, token_data: Dict[str, Any], message_id: str, attachment_id: str
    ) -> bytes:
        service = self._service_builder(token_data)
        try:
            resp = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
        except Exception as exc:
            _handle_gmail_error(exc)
            raise

        raw_data = resp.get("data", "")
        if not raw_data:
            return b""
        padded = raw_data + "=" * (-len(raw_data) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8"))
