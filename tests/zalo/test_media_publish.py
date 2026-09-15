"""Regression tests for Zalo outbound photo delivery via Azure Blob SAS."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gateway.platforms.base import (
    SendResult,
)
from test_adapter import (
    _response,
    _run,
    _using_client,
)

pytest_plugins = ["test_adapter"]


@pytest.fixture
def media_pub(zalo_module):
    return zalo_module.media_publish


@pytest.fixture
def image_file(tmp_path):
    path = tmp_path / "out.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return path


def test_send_image_url_uses_sendphoto(adapter, zalo_module):
    async def handler(request):
        assert request.url.path.endswith("/sendPhoto")
        body = _request_body_safe(request)
        assert body["chat_id"] == "photo-chat"
        assert body["photo"] == "https://example.com/cat.jpg"
        assert body["caption"] == "Meo"
        return _response(request, {"ok": True, "result": {"message_id": "p-1"}})

    result = _run(
        _using_client(
            adapter,
            handler,
            lambda: adapter.send_image(
                "photo-chat", "https://example.com/cat.jpg", caption="Meo"
            ),
        )
    )
    assert result.success is True
    assert result.message_id == "p-1"


def test_send_image_rejects_non_url_via_text_fallback(adapter):
    adapter._running = True
    adapter._client = httpx.AsyncClient()
    sent = []

    async def fake_send(chat_id, content, reply_to=None, metadata=None):
        sent.append(content)
        return SendResult(success=True, message_id="t-1")

    adapter.send = fake_send
    result = _run(adapter.send_image("chat-x", "C:/local/path.png"))
    assert result.success is True
    assert result.message_id == "t-1"


def test_sendphoto_api_error_is_reported(adapter):
    async def handler(request):
        return _response(
            request, {"ok": False, "error_code": 400, "description": "bad"}, 400
        )

    result = _run(
        _using_client(
            adapter,
            handler,
            lambda: adapter.send_image("chat-x", "https://x.test/a.png"),
        )
    )
    assert result.success is False
    assert result.retryable is False
    assert "code 400" in result.error


def _request_body_safe(request):
    return json.loads(request.content.decode("utf-8"))


def test_send_image_file_publishes_and_sends(
    adapter, zalo_module, image_file, monkeypatch
):
    published = {}

    def fake_publish(path):
        published["path"] = Path(path)
        return "https://acct.blob.core.windows.net/hermes-zalo-media/zalo-1.png?sig=abc"

    monkeypatch.setattr(zalo_module.media_publish, "publish_image", fake_publish)

    async def handler(request):
        body = _request_body_safe(request)
        assert body["photo"].startswith("https://acct.blob.core.windows.net/")
        return _response(request, {"ok": True, "result": {"message_id": "p-2"}})

    result = _run(
        _using_client(
            adapter,
            handler,
            lambda: adapter.send_image_file(
                "photo-chat", str(image_file), caption="Anh AI"
            ),
        )
    )
    assert result.success is True
    assert result.message_id == "p-2"


def test_send_image_file_publish_failure_is_contained(
    adapter, zalo_module, monkeypatch
):
    adapter._running = True
    adapter._client = httpx.AsyncClient()

    def fake_publish(path):
        raise zalo_module.media_publish.PhotoPublishError("image file does not exist")

    monkeypatch.setattr(zalo_module.media_publish, "publish_image", fake_publish)
    adapter._send_photo = AsyncMock(side_effect=AssertionError("must not be called"))

    result = _run(adapter.send_image_file("chat-x", "/nonexistent/x.png"))
    assert result.success is False
    assert "Image publish failed" in result.error
    assert result.retryable is False


def test_publish_image_uploads_and_returns_sas_url(media_pub, image_file, monkeypatch):
    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=acc;AccountKey=a2V5;EndpointSuffix=core.windows.net",
    )
    monkeypatch.delenv("ZALO_MEDIA_CONTAINER", raising=False)

    uploaded = {}
    captured = {}

    container = MagicMock()
    container.create_container.return_value = None

    def fake_upload_blob(name, data, overwrite, content_settings):
        uploaded["name"] = name
        uploaded["content_type"] = content_settings.content_type

    container.upload_blob.side_effect = fake_upload_blob
    service = MagicMock()
    service.account_name = "acc"
    service.get_container_client.return_value = container
    monkeypatch.setattr(
        media_pub,
        "BlobServiceClient",
        MagicMock(from_connection_string=MagicMock(return_value=service)),
    )

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return "sas-token"

    monkeypatch.setattr("azure.storage.blob.generate_blob_sas", fake_generate)
    monkeypatch.setattr(media_pub, "generate_blob_sas", fake_generate)

    url = media_pub.publish_image(image_file)

    assert (
        url
        == "https://acc.blob.core.windows.net/hermes-zalo-media/"
        + uploaded["name"]
        + "?sas-token"
    )
    assert captured["permission"].read is True
    assert captured["expiry"] > captured["expiry"].replace(hour=0)


def test_publish_image_rejects_unsupported_type(media_pub, tmp_path):
    bad = tmp_path / "doc.pdf"
    bad.write_bytes(b"%PDF")
    with pytest.raises(media_pub.PhotoPublishError):
        media_pub.publish_image(bad)


def test_publish_image_requires_connection_string(media_pub, image_file, monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    with pytest.raises(media_pub.PhotoPublishError):
        media_pub.publish_image(image_file)
