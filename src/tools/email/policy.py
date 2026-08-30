from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Any, Optional

from tools.email.contracts import (
    DeliveryDecision,
    Destination,
    GrantRequestStatus,
    MailConnection,
    MailboxType,
    SharedGrantRequest,
)
from tools.email.store import MailStore

logger = logging.getLogger(__name__)

DM_REDIRECT_TEXT = "Mở chat riêng với Hermes để xem Gmail cá nhân."


@dataclass(frozen=True)
class PolicyCaller:
    principal_id: str
    platform: str
    user_id: str
    chat_id: str
    thread_id: Optional[str] = None
    chat_type: str = "dm"
    profile: str = "default"
    session_key: str = ""


class MailPolicy:
    def __init__(
        self, store: MailStore, operator_allowlist: tuple[str, ...] = ()
    ) -> None:
        self.store = store
        self.operator_allowlist = operator_allowlist

    def readable_connections(self, caller: Any) -> tuple[MailConnection, ...]:
        # Personal mailboxes owned by caller
        personal = self.store.list_connections(caller.principal_id)
        return tuple(personal)

    def authorize_source(self, caller: Any, connection_id: str) -> MailConnection:
        conn = self.store.get_authorized_connection(caller.principal_id, connection_id)
        if conn.mailbox_type == MailboxType.PERSONAL:
            if conn.owner_principal_id != caller.principal_id:
                raise PermissionError("not_authorized: personal mailbox is owner-only")
        elif conn.mailbox_type == MailboxType.SHARED:
            # Check destination grant if in group
            if caller.chat_type != "dm":
                dest = Destination(
                    platform=caller.platform,
                    chat_id=caller.chat_id,
                    thread_id=caller.thread_id,
                )
                grant = self.store.destination_grant(connection_id, dest)
                if grant is None:
                    raise PermissionError(
                        "not_authorized: shared mailbox not allowed in this destination"
                    )
        return conn

    def decide_delivery(
        self, caller: Any, connection: MailConnection
    ) -> DeliveryDecision:
        if connection.mailbox_type == MailboxType.PERSONAL:
            if caller.chat_type == "dm":
                return DeliveryDecision(mode="dm")
            else:
                return DeliveryDecision(
                    mode="redirect_to_dm", public_text=DM_REDIRECT_TEXT
                )

        if connection.mailbox_type == MailboxType.SHARED:
            if caller.chat_type == "dm":
                return DeliveryDecision(mode="dm")
            dest = Destination(
                platform=caller.platform,
                chat_id=caller.chat_id,
                thread_id=caller.thread_id,
            )
            grant = self.store.destination_grant(connection.connection_id, dest)
            if grant is None:
                raise PermissionError(
                    "not_authorized: destination is not in allowed destinations"
                )
            return DeliveryDecision(mode="group")

        raise ValueError(f"unknown_mailbox_type: {connection.mailbox_type}")

    def propose_shared_grant(
        self,
        caller: Any,
        connection_id: str,
        destination: Destination,
        expires_at: str,
    ) -> SharedGrantRequest:
        conn = self.store.get_authorized_connection(caller.principal_id, connection_id)
        if conn.owner_principal_id != caller.principal_id:
            raise PermissionError("only_mailbox_owner_can_propose_shared_grant")

        req_id = f"grant-{secrets.token_hex(16)}"
        req = SharedGrantRequest(
            request_id=req_id,
            connection_id=connection_id,
            requested_by=caller.principal_id,
            destination=destination,
            status=GrantRequestStatus.PENDING,
            expires_at=expires_at,
        )
        self.store.create_grant_request(req)
        return req

    def decide_shared_grant(
        self,
        operator: Any,
        request_id: str,
        approve: bool,
    ) -> SharedGrantRequest:
        is_operator = (
            operator.principal_id in self.operator_allowlist
            or operator.user_id in self.operator_allowlist
        )
        return self.store.decide_grant_request(
            request_id=request_id,
            operator_principal_id=operator.principal_id,
            operator_allowlist=(operator.principal_id,) if is_operator else (),
            approve=approve,
        )
