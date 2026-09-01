from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import secrets
from typing import Any, Dict, Optional, Tuple
import urllib.parse

from tools.calendar.contracts import CalendarConnection, CalendarConnectionStatus
from tools.calendar.store import CalendarStore

CALENDAR_SCOPES = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly"


@dataclass(frozen=True)
class CalendarAuthorizationStart:
    url: str
    state: str
    request_id: str


class CalendarOAuthManager:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        store: CalendarStore,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.store = store

    def create_authorization_start(self, principal_id: str) -> CalendarAuthorizationStart:
        request_id = f"link-cal-{secrets.token_hex(16)}"
        verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        state_nonce = secrets.token_urlsafe(32)

        state_payload = json.dumps(
            {"req": request_id, "nonce": state_nonce, "principal": principal_id},
            separators=(",", ":"),
        )
        state_b64 = base64.urlsafe_b64encode(state_payload.encode("utf-8")).decode("utf-8")

        client_id = self.client_id or os.environ.get("EMAIL_GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID") or "mock-client-id.apps.googleusercontent.com"
        redirect_uri = self.redirect_uri or os.environ.get("EMAIL_OAUTH_REDIRECT_URI") or "http://127.0.0.1:8766/gmail/oauth/callback"

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": CALENDAR_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state_b64,
        }
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        return CalendarAuthorizationStart(url=auth_url, state=state_b64, request_id=request_id)
