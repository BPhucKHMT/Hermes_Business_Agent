from __future__ import annotations

import os
import re
import shlex
from pathlib import Path


_PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"
_EMAIL_ENV_NAMES = frozenset(
    {
        "AZURE_KEY_VAULT_URL",
        "EMAIL_GOOGLE_CLIENT_ID",
        "EMAIL_GOOGLE_CLIENT_SECRET_REF",
        "EMAIL_OAUTH_REDIRECT_URI",
        "EMAIL_CONNECTOR_SHARED_SECRET",
        "EMAIL_STATE_DB_PATH",
        "EMAIL_OPERATOR_USER_IDS",
    }
)
_KEY_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class EmailEnvError(ValueError):
    pass


def _parse_value(raw: str) -> str:
    lexer = shlex.shlex(raw, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError:
        raise EmailEnvError("malformed_project_email_env") from None
    if len(tokens) > 1:
        raise EmailEnvError("malformed_project_email_env")
    return tokens[0] if tokens else ""


def load_project_email_env() -> frozenset[str]:
    if not _PROJECT_ENV.is_file():
        return frozenset()
    try:
        text = _PROJECT_ENV.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise EmailEnvError("malformed_project_email_env") from None

    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise EmailEnvError("malformed_project_email_env")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not _KEY_PATTERN.fullmatch(key) or key in parsed:
            raise EmailEnvError("malformed_project_email_env")
        parsed[key] = _parse_value(raw_value.strip())

    loaded = frozenset(_EMAIL_ENV_NAMES.intersection(parsed))
    for key in loaded:
        os.environ.setdefault(key, parsed[key])
    return loaded
