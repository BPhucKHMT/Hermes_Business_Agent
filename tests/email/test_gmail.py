import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.email.gmail import GmailReader


class FakeGmailService:
    def __init__(self):
        self.calls = []

    def users(self):
        return self

    def threads(self):
        return self

    def list(self, userId="me", q="", maxResults=10):
        self.calls.append(("threads.list", userId, q, maxResults))
        return SimpleNamespace(
            execute=lambda: {
                "threads": [
                    {
                        "id": "thread-123",
                        "snippet": "Báo giá Whey Protein 2026",
                        "historyId": "1001",
                    }
                ]
            }
        )

    def get(self, userId="me", id="", format="full"):
        self.calls.append(("threads.get", userId, id, format))
        return SimpleNamespace(
            execute=lambda: {
                "id": "thread-123",
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
                                        # Base64 encoded 'Giá 55,000,000 VND cho 100kg Whey Isolate.'
                                        "data": "R2nDoSA1NSwwMDAsMDAwIFZORCBjaG8gMTAwa2cgV2hleSBJc29sYXRlLg=="
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        )


def test_gmail_reader_search_threads():
    fake = FakeGmailService()
    reader = GmailReader(service_builder=lambda creds: fake)
    hits = reader.search_threads({"token": "fake"}, query="newer_than:7d", limit=5)
    assert len(hits) == 1
    assert hits[0].thread_id == "thread-123"
    assert "Whey" in hits[0].snippet
    assert fake.calls[0] == ("threads.list", "me", "newer_than:7d", 5)


def test_gmail_reader_get_thread_bounded():
    fake = FakeGmailService()
    reader = GmailReader(service_builder=lambda creds: fake)
    result = reader.get_thread({"token": "fake"}, thread_id="thread-123", text_bytes_max=30)
    assert result.thread_id == "thread-123"
    assert result.subject == "Báo giá Whey"
    assert result.truncated is True
    assert len(result.text.encode("utf-8")) <= 30
