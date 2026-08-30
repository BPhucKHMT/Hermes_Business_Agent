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
    AttachmentInfo,
    EmailMessage,
    MailboxType,
    MailConnection,
    SearchHit,
    ThreadResult,
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


def test_attachment_info_and_contracts_defaults():
    att = AttachmentInfo(
        attachment_id="att-1",
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
    )
    assert att.attachment_id == "att-1"
    assert att.filename == "invoice.pdf"
    assert att.mime_type == "application/pdf"
    assert att.size_bytes == 1024

    with pytest.raises(FrozenInstanceError):
        att.filename = "other.pdf"

    att_default_size = AttachmentInfo(
        attachment_id="att-2",
        filename="doc.txt",
        mime_type="text/plain",
    )
    assert att_default_size.size_bytes == 0

    hit = SearchHit(
        thread_id="t-1",
        subject="Test",
        snippet="Hello",
        last_message_date="2026-08-26",
        from_address="a@b.com",
    )
    assert hit.attachments == ()

    thread = ThreadResult(
        thread_id="t-1",
        subject="Test",
        text="Hello",
    )
    assert thread.attachments == ()

    msg = EmailMessage(
        message_id="msg-1",
        thread_id="t-1",
        subject="Test",
        from_address="a@b.com",
        to_address="c@d.com",
        date="2026-08-26",
        body_text="Hello",
        attachments=(att,),
    )
    assert msg.message_id == "msg-1"
    assert msg.attachments == (att,)

    with pytest.raises(FrozenInstanceError):
        msg.body_text = "Mutated"
