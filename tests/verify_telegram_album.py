import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "src/.hermes/plugins/telegram-album"
UPSTREAM = Path(os.environ["LOCALAPPDATA"]) / "hermes/hermes-agent"
for path in (PLUGIN, UPSTREAM):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

if (PLUGIN / "__init__.py").is_file():
    from __init__ import ReliableTelegramAdapter
else:
    from plugins.platforms.telegram.adapter import TelegramAdapter as ReliableTelegramAdapter
from gateway.config import PlatformConfig


def message(index, count, release, caption=None):
    async def download():
        if index == count - 1:
            await release.wait()
        return bytearray(("pdf-%d" % index).encode())

    file_obj = SimpleNamespace(download_as_bytearray=download, file_path="documents/%d.pdf" % index)
    document = SimpleNamespace(
        file_name="%d.pdf" % index,
        mime_type="application/pdf",
        file_size=64,
        get_file=AsyncMock(return_value=file_obj),
    )
    user = SimpleNamespace(id=1, full_name="Test User")
    chat = SimpleNamespace(id=100, type="private", title=None, full_name="Test User")
    return SimpleNamespace(
        message_id=index,
        text=caption or "",
        caption=caption,
        photo=None,
        video=None,
        audio=None,
        voice=None,
        sticker=None,
        document=document,
        media_group_id="album",
        chat=chat,
        from_user=user,
        message_thread_id=None,
        reply_to_message=None,
        date=None,
        reply_text=AsyncMock(),
    )


async def check_album(count):
    adapter = ReliableTelegramAdapter(PlatformConfig(enabled=True, token="fake"))
    adapter.MEDIA_GROUP_WAIT_SECONDS = 0.02
    adapter.handle_message = AsyncMock()
    adapter._is_callback_user_authorized = lambda user_id, **kwargs: True
    release = asyncio.Event()
    updates = [SimpleNamespace(message=message(i, count, release, "retain these documents" if i == 0 else None), update_id=i) for i in range(count)]

    with patch("plugins.platforms.telegram.adapter.cache_document_from_bytes", side_effect=lambda data, name: "/cache/" + name, create=True), \
         patch("gateway.platforms.base.cache_media_bytes", side_effect=lambda data, filename, mime_type: SimpleNamespace(path="/cache/" + filename, media_type="application/pdf", kind="document"), create=True):
        tasks = [asyncio.create_task(adapter._handle_media_message(update, MagicMock())) for update in updates]
        await asyncio.sleep(adapter.MEDIA_GROUP_WAIT_SECONDS * 3)
        assert adapter.handle_message.await_count == 0, "album dispatched while a sibling download remained in flight"
        release.set()
        await asyncio.gather(*tasks)
        for _ in range(50):
            if adapter.handle_message.await_count:
                break
            await asyncio.sleep(0.01)

    assert adapter.handle_message.await_count == 1, "one media group must create one agent turn"
    event = adapter.handle_message.await_args.args[0]
    assert event.text == "retain these documents"
    assert sorted(event.media_urls) == ["/cache/%d.pdf" % i for i in range(count)]


async def main():
    for count in (3, 5, 10):
        await check_album(count)
    print("telegram album regression: pass")


if __name__ == "__main__":
    asyncio.run(main())
