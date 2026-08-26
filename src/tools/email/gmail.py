from __future__ import annotations

import base64
import html
import logging
import re
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.email.contracts import SearchHit, ThreadResult

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


def _extract_body_parts(payload: Dict[str, Any]) -> str:
    texts: List[str] = []
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime == "text/plain" and body_data:
        texts.append(_decode_b64(body_data))
    elif mime == "text/html" and body_data:
        texts.append(_strip_html(_decode_b64(body_data)))

    parts = payload.get("parts", [])
    for part in parts:
        part_text = _extract_body_parts(part)
        if part_text:
            texts.append(part_text)

    return "\n".join(texts).strip()


class GmailReader:
    def __init__(self, service_builder: Optional[Callable[[Dict[str, Any]], Any]] = None) -> None:
        self._service_builder = service_builder or self._default_service_builder

    @staticmethod
    def _default_service_builder(token_data: Dict[str, Any]) -> Any:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", ["https://www.googleapis.com/auth/gmail.readonly"]),
        )
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def search_threads(self, token_data: Dict[str, Any], query: str, limit: int = 10) -> tuple[SearchHit, ...]:
        service = self._service_builder(token_data)
        safe_limit = max(1, min(limit, 20))
        resp = service.users().threads().list(userId="me", q=query, maxResults=safe_limit).execute()
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
                )
            )
        return tuple(hits)

    def get_thread(self, token_data: Dict[str, Any], thread_id: str, text_bytes_max: int = 65536) -> ThreadResult:
        service = self._service_builder(token_data)
        t = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
        messages = t.get("messages", [])

        subject = ""
        collected_texts: List[str] = []

        for msg in messages:
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            for h in headers:
                if h.get("name", "").lower() == "subject" and not subject:
                    subject = h.get("value", "")

            body_text = _extract_body_parts(payload)
            if body_text:
                collected_texts.append(body_text)

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
        )
