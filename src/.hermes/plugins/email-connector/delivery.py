from .caller import CallerContext, CallerContextRegistry
from gateway.config import Platform


class PrivateDelivery:
    def __init__(self, gateway, registry: CallerContextRegistry):
        self._gateway = gateway
        self._registry = registry

    async def send_dm(self, caller: CallerContext, text: str) -> str:
        self._registry.require_issued(caller)
        if caller.platform != "telegram" or caller.chat_type != "dm":
            raise ValueError("Private delivery requires a captured Telegram DM caller")
        if not caller.chat_id or not caller.user_id:
            raise ValueError("Private delivery requires a Telegram DM destination")

        adapter = self._gateway.adapters[Platform.TELEGRAM]
        result = await adapter.send(caller.chat_id, text)
        if not result.success or not result.message_id:
            raise RuntimeError(result.error or "Telegram DM delivery failed")
        return str(result.message_id)
