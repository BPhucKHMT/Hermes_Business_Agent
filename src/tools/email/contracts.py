from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
MAX_CONNECTIONS_PER_PRINCIPAL = 3


class MailboxType(StrEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    RECONNECT_REQUIRED = "reconnect_required"
    REVOKED = "revoked"


class GrantRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Destination:
    platform: str
    chat_id: str
    thread_id: Optional[str] = None


@dataclass(frozen=True)
class MailConnection:
    connection_id: str
    owner_principal_id: str
    mailbox_type: MailboxType
    masked_address: str
    provider_subject_hash: str
    secret_ref: str
    granted_scopes: tuple[str, ...]
    status: ConnectionStatus | str


@dataclass(frozen=True)
class OAuthLinkRequest:
    request_id: str
    principal_id: str
    nonce_hash: str
    pkce_secret_ref: str
    expires_at: str
    used_at: Optional[str] = None


@dataclass(frozen=True)
class SharedGrantRequest:
    request_id: str
    connection_id: str
    requested_by: str
    destination: Destination
    status: GrantRequestStatus | str
    expires_at: str
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None


@dataclass(frozen=True)
class SharedGrant:
    request_id: str
    connection_id: str
    destination: Destination
    revoked_at: Optional[str] = None



@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    principal_id: str
    connection_id: Optional[str]
    destination_hash: Optional[str]
    query_hash: Optional[str]
    occurred_at: str
    outcome: str

@dataclass(frozen=True)
class SearchHit:
    thread_id: str
    subject: str
    snippet: str
    last_message_date: str
    from_address: str


@dataclass(frozen=True)
class ThreadResult:
    thread_id: str
    subject: str
    text: str
    truncated: bool = False


@dataclass(frozen=True)
class DeliveryDecision:
    mode: str
    public_text: Optional[str] = None
