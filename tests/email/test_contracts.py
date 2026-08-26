import os
import sys
from pathlib import Path
from dataclasses import FrozenInstanceError
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.email.contracts import (
    GMAIL_READONLY_SCOPE,
    MAX_CONNECTIONS_PER_PRINCIPAL,
    MailboxType,
    MailConnection,
    Destination,
    OAuthLinkRequest,
    SharedGrantRequest,
    SharedGrant,
    SearchHit,
    ThreadResult,
    DeliveryDecision,
)


def test_personal_connection_is_immutable():
    connection = MailConnection(
        connection_id="conn-1",
        owner_principal_id="telegram:bot:111",
        mailbox_type=MailboxType.PERSONAL,
        masked_address="u***@gmail.com",
        provider_subject_hash="abc123hash",
        secret_ref="keyvault://gmail-conn-1",
        granted_scopes=(GMAIL_READONLY_SCOPE,),
        status="connected",
    )
    with pytest.raises(FrozenInstanceError):
        connection.owner_principal_id = "telegram:bot:222"


def test_contracts_constants():
    assert GMAIL_READONLY_SCOPE == "https://www.googleapis.com/auth/gmail.readonly"
    assert MAX_CONNECTIONS_PER_PRINCIPAL == 3
