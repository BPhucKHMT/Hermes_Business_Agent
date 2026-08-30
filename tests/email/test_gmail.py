import base64
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.email.gmail import GmailReader, _extract_parts


class FakeGmailService:
    def __init__(self):
        self.calls = []
        self._thread_active = set()
        self.max_concurrent_threads = 0
        self._lock = threading.Lock()

    def users(self):
        return self

    def threads(self):
        return self

    def messages(self):
        return self

    def attachments(self):
        return self

    def list(self, userId="me", q="", maxResults=10):
        self.calls.append(("list", userId, q, maxResults))
        return SimpleNamespace(
            execute=lambda: {
                "threads": [
                    {
                        "id": "thread-123",
                        "snippet": "Báo giá Whey Protein 2026",
                        "historyId": "1001",
                    }
                ],
                "messages": [
                    {"id": f"msg-{i}", "threadId": f"thread-{i}"}
                    for i in range(1, 6)
                ],
            }
        )

    def get(self, userId="me", id="", format="full", messageId=None):
        with self._lock:
            self.calls.append(("get", userId, id, format, messageId))

        def _exec():
            cur_thread = threading.current_thread().ident
            with self._lock:
                self._thread_active.add(cur_thread)
                if len(self._thread_active) > self.max_concurrent_threads:
                    self.max_concurrent_threads = len(self._thread_active)
            time.sleep(0.01)
            with self._lock:
                self._thread_active.discard(cur_thread)

            if messageId and id:
                # Attachment get call
                return {
                    "size": 24,
                    "data": base64.urlsafe_b64encode(b"sample attachment content").decode("utf-8"),
                }

            return {
                "id": id or "thread-123",
                "threadId": f"thread-{id}",
                "snippet": f"Snippet for {id}",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": f"Subject for {id}"},
                        {"name": "From", "value": "supplier@whey.vn"},
                        {"name": "To", "value": "customer@example.com"},
                        {"name": "Date", "value": "Wed, 26 Aug 2026 10:00:00 +0700"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {
                                "data": (
                                    "R2nDoSA1NSwwMDAsMDAwIFZORCBjaG8gMTAwa2cg"
                                    "V2hleSBJc29sYXRlLg=="
                                )
                            },
                        },
                        {
                            "mimeType": "application/pdf",
                            "filename": "quote.pdf",
                            "body": {
                                "attachmentId": "att-pdf-123",
                                "size": 2048,
                            },
                        },
                    ],
                },
                "messages": [
                    {
                        "id": "msg-1",
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Báo giá Whey"},
                                {"name": "From", "value": "supplier@whey.vn"},
                                {"name": "Date", "value": "Wed, 26 Aug 2026 10:00:00 +0700"},
                            ],
                            "parts": [
                                {
                                    "mimeType": "text/plain",
                                    "body": {
                                        "data": (
                                            "R2nDoSA1NSwwMDAsMDAwIFZORCBjaG8gMTAwa2cg"
                                            "V2hleSBJc29sYXRlLg=="
                                        )
                                    },
                                },
                                {
                                    "mimeType": "application/pdf",
                                    "filename": "quote.pdf",
                                    "body": {
                                        "attachmentId": "att-pdf-123",
                                        "size": 2048,
                                    },
                                },
                            ],
                        },
                    }
                ],
            }

        return SimpleNamespace(execute=_exec)


def test_gmail_reader_search_threads():
    fake = FakeGmailService()
    reader = GmailReader(service_builder=lambda creds: fake)
    hits = reader.search_threads({"token": "fake"}, query="newer_than:7d", limit=5)
    assert len(hits) == 1
    assert hits[0].thread_id == "thread-123"
    assert "Whey" in hits[0].snippet
    assert hits[0].attachments == ()
    assert fake.calls[0] == ("list", "me", "newer_than:7d", 5)


def test_gmail_reader_get_thread_bounded():
    fake = FakeGmailService()
    reader = GmailReader(service_builder=lambda creds: fake)
    result = reader.get_thread(
        {"token": "fake"}, thread_id="thread-123", text_bytes_max=30
    )
    assert result.thread_id == "thread-123"
    assert result.subject == "Báo giá Whey"
    assert result.truncated is True
    assert len(result.text.encode("utf-8")) <= 30
    assert len(result.attachments) == 1
    assert result.attachments[0].filename == "quote.pdf"
    assert result.attachments[0].attachment_id == "att-pdf-123"
    assert result.attachments[0].mime_type == "application/pdf"
    assert result.attachments[0].size_bytes == 2048


def test_gmail_reader_search_messages_concurrent_ranking():
    fake = FakeGmailService()
    reader = GmailReader(service_builder=lambda creds: fake)
    messages = reader.search_messages({"token": "fake"}, query="label:INBOX", limit=5)

    assert len(messages) == 5
    # Must maintain original ranking order
    for idx, msg in enumerate(messages, start=1):
        assert msg.message_id == f"msg-{idx}"
        assert msg.subject == f"Subject for msg-{idx}"
        assert len(msg.attachments) == 1
        assert msg.attachments[0].attachment_id == "att-pdf-123"
    assert fake.max_concurrent_threads > 1


def test_gmail_reader_get_attachment():
    fake = FakeGmailService()
    reader = GmailReader(service_builder=lambda creds: fake)
    raw_data = reader.get_attachment(
        {"token": "fake"}, message_id="msg-1", attachment_id="att-pdf-123"
    )
    assert raw_data == b"sample attachment content"


def test_extract_parts_helper():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {
                    "data": base64.urlsafe_b64encode(b"Hello world").decode("utf-8")
                },
            },
            {
                "mimeType": "application/pdf",
                "filename": "doc.pdf",
                "body": {"attachmentId": "att-999", "size": 5000},
            },
            {
                "mimeType": "image/png",
                "filename": "screenshot.png",
                "body": {"attachmentId": "att-img", "size": 12000},
            },
        ],
    }
    text, attachments = _extract_parts(payload)
    assert text == "Hello world"
    assert len(attachments) == 2
    assert attachments[0].filename == "doc.pdf"
    assert attachments[0].size_bytes == 5000
    assert attachments[1].filename == "screenshot.png"
    assert attachments[1].mime_type == "image/png"


def test_gmail_reader_refresh_error_handling():
    class FailingService:
        def users(self):
            return self

        def threads(self):
            return self

        def messages(self):
            return self

        def attachments(self):
            return self

        def list(self, **kwargs):
            raise RefreshError("invalid_grant: Bad Request")

        def get(self, **kwargs):
            resp = SimpleNamespace(status=401, reason="Unauthorized")
            raise HttpError(resp=resp, content=b"Unauthorized")

    reader = GmailReader(service_builder=lambda creds: FailingService())

    with pytest.raises(RefreshError):
        reader.search_messages({"token": "fake"}, query="test")

    with pytest.raises(RefreshError):
        reader.search_threads({"token": "fake"}, query="test")

    with pytest.raises(RefreshError):
        reader.get_thread({"token": "fake"}, thread_id="t-1")

    with pytest.raises(RefreshError):
        reader.get_message({"token": "fake"}, message_id="m-1")

    with pytest.raises(RefreshError):
        reader.get_attachment({"token": "fake"}, message_id="m-1", attachment_id="a-1")
