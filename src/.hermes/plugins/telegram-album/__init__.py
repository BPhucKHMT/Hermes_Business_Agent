import asyncio
from collections import defaultdict

from plugins.platforms.telegram import adapter as upstream


class ReliableTelegramAdapter(upstream.TelegramAdapter):
    """Keep received album siblings together while their downloads are in flight."""

    MAX_MEDIA_GROUP_WAIT_SECONDS = 30

    def __init__(self, config):
        super().__init__(config)
        self._media_group_in_flight = defaultdict(int)
        self._media_group_downloads_done = {}

    async def _handle_media_message(self, update, context):
        media_group_id = getattr(update.message, "media_group_id", None)
        if not media_group_id:
            return await super()._handle_media_message(update, context)

        group = str(media_group_id)
        done = self._media_group_downloads_done.setdefault(group, asyncio.Event())
        done.clear()
        self._media_group_in_flight[group] += 1
        try:
            return await super()._handle_media_message(update, context)
        finally:
            self._media_group_in_flight[group] -= 1
            if self._media_group_in_flight[group] == 0:
                done.set()

    async def _flush_media_group_event(self, media_group_id):
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(self.MEDIA_GROUP_WAIT_SECONDS)
            done = self._media_group_downloads_done.get(media_group_id)
            if done is not None:
                try:
                    await asyncio.wait_for(done.wait(), self.MAX_MEDIA_GROUP_WAIT_SECONDS)
                except asyncio.TimeoutError:
                    pass
            event = self._media_group_events.pop(media_group_id, None)
            if event is not None and not self._should_drop_delayed_delivery():
                await self.handle_message(event)
        except asyncio.CancelledError:
            return
        finally:
            if self._media_group_tasks.get(media_group_id) is current_task:
                self._media_group_tasks.pop(media_group_id, None)
                self._media_group_in_flight.pop(media_group_id, None)
                self._media_group_downloads_done.pop(media_group_id, None)


def _build_adapter(config):
    adapter = ReliableTelegramAdapter(config)
    try:
        adapter._notifications_mode = upstream._resolve_notifications_mode()
    except Exception:
        adapter._notifications_mode = "important"
    return adapter


def register(ctx):
    ctx.register_platform(
        name="telegram",
        label="Telegram",
        adapter_factory=_build_adapter,
        check_fn=upstream.check_telegram_requirements,
        is_connected=upstream._is_connected,
        required_env=["TELEGRAM_BOT_TOKEN"],
        install_hint="pip install 'hermes-agent[telegram]'",
        setup_fn=upstream.interactive_setup,
        apply_yaml_config_fn=upstream._apply_yaml_config,
        allowed_users_env="TELEGRAM_ALLOWED_USERS",
        allow_all_env="TELEGRAM_ALLOW_ALL_USERS",
        cron_deliver_env_var="TELEGRAM_HOME_CHANNEL",
        standalone_sender_fn=upstream._standalone_send,
        max_message_length=4096,
        emoji="✈️",
        allow_update_command=True,
    )
