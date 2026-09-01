from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

from tools.email.contracts import (
    GMAIL_READONLY_SCOPE,
    UNIFIED_GOOGLE_SCOPES,
    ConnectionStatus,
    MailConnection,
    MailboxType,
    OAuthLinkRequest,
)
from tools.email.secrets import SecretStore
from tools.email.store import MailStore

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _b64url_sha256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


@dataclass(frozen=True)
class AuthorizationStart:
    url: str
    state: str
    request_id: str


class GmailOAuthManager:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        store: MailStore,
        secret_store: SecretStore,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.store = store
        self.secret_store = secret_store

    def create_authorization_start(self, principal_id: str) -> AuthorizationStart:
        request_id = f"link-{secrets.token_hex(16)}"
        verifier = secrets.token_urlsafe(64)[:128]
        challenge = _b64url_sha256(verifier)
        state_nonce = secrets.token_urlsafe(32)
        nonce_hash = hashlib.sha256(state_nonce.encode("utf-8")).hexdigest()

        pkce_ref = self.secret_store.put_json(
            f"pkce-{request_id}",
            {"verifier": verifier, "principal_id": principal_id},
        )

        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        req = OAuthLinkRequest(
            request_id=request_id,
            principal_id=principal_id,
            nonce_hash=nonce_hash,
            pkce_secret_ref=pkce_ref,
            expires_at=expires_at,
        )
        self.store.create_link_request(req)

        # State encodes request_id and state_nonce
        state_payload = json.dumps(
            {"req": request_id, "nonce": state_nonce}, separators=(",", ":")
        )
        state_b64 = base64.urlsafe_b64encode(state_payload.encode("utf-8")).decode(
            "utf-8"
        )

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(UNIFIED_GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state_b64,
        }
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        return AuthorizationStart(url=auth_url, state=state_b64, request_id=request_id)

    def _exchange_code(
        self, code: str, verifier: str
    ) -> Tuple[Dict[str, Any], str, str]:
        # Production exchange using google_auth_oauthlib / requests
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build

        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
        flow = Flow.from_client_config(
            client_config,
            scopes=list(UNIFIED_GOOGLE_SCOPES),
            redirect_uri=self.redirect_uri,
            code_verifier=verifier,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes or [GMAIL_READONLY_SCOPE]),
        }

        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "unknown@gmail.com")
        sub_id = hashlib.sha256(email_address.encode("utf-8")).hexdigest()
        return token_data, email_address, sub_id

    @staticmethod
    def _parse_state(state: str) -> tuple[str, str]:
        try:
            raw_state = base64.urlsafe_b64decode(state.encode("utf-8")).decode("utf-8")
            parsed_state = json.loads(raw_state)
            return parsed_state["req"], parsed_state["nonce"]
        except Exception:
            raise ValueError("invalid_oauth_state") from None

    def complete_callback(self, state: str, code: str) -> MailConnection:
        request_id, _ = self._parse_state(state)
        request = self.store.get_link_request(request_id)
        return self.complete_authorization(state, code, request.principal_id)

    def complete_authorization(
        self,
        state: str,
        code: str,
        principal_id: str,
    ) -> MailConnection:
        request_id, state_nonce = self._parse_state(state)

        nonce_hash = hashlib.sha256(state_nonce.encode("utf-8")).hexdigest()
        link_req = self.store.consume_link_request(request_id, nonce_hash, principal_id)

        pkce_data = self.secret_store.get_json(link_req.pkce_secret_ref)
        verifier = pkce_data["verifier"]

        token_data, email_address, sub_hash = self._exchange_code(code, verifier)

        conn_id = f"conn-{secrets.token_hex(12)}"
        token_ref = self.secret_store.put_json(f"gmail-token-{conn_id}", token_data)

        masked = _mask_email(email_address)
        conn = MailConnection(
            connection_id=conn_id,
            owner_principal_id=principal_id,
            mailbox_type=MailboxType.PERSONAL,
            masked_address=masked,
            provider_subject_hash=sub_hash,
            secret_ref=token_ref,
            granted_scopes=UNIFIED_GOOGLE_SCOPES,
            status=ConnectionStatus.CONNECTED,
        )

        try:
            self.store.add_connection(conn)
        except Exception:
            self.secret_store.delete(token_ref)
            raise

        # Provision connections across Calendar and YouTube stores
        try:
            from pathlib import Path
            from tools.calendar.contracts import (
                CalendarConnection,
                CalendarConnectionStatus,
            )
            from tools.calendar.store import CalendarStore
            from tools.youtube.store import YouTubeStore

            src_dir = Path(__file__).resolve().parents[2]
            cal_db = src_dir / ".runtime" / "calendar" / "calendar.sqlite3"
            CalendarStore(cal_db).upsert_connection(
                CalendarConnection(
                    connection_id=f"conn-cal-{conn_id[5:]}",
                    principal_id=principal_id,
                    email=email_address,
                    calendar_id="primary",
                    calendar_name="Primary Calendar",
                    status=CalendarConnectionStatus.CONNECTED,
                )
            )
            yt_db = src_dir / ".runtime" / "youtube" / "youtube.sqlite3"
            YouTubeStore(yt_db).upsert_connection(
                principal_id=principal_id,
                channel_id="mine",
                channel_title=f"{email_address}'s Channel",
            )
        except Exception as sync_err:
            logger.warning("Auto-syncing multi-service connections failed: %s", sync_err)

        # Clean up temporary PKCE secret
        self.secret_store.delete(link_req.pkce_secret_ref)
        return conn
