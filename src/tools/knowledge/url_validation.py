from __future__ import annotations

from ipaddress import ip_address
import socket
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMETERS = {
    "fbclid", "gclid", "mc_cid", "mc_eid",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}


def normalize_public_url(value: str) -> str:
    parts = urlsplit((value or "").strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("website URL must use http or https")
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError("website URL must contain a public host without credentials")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("website URL contains an invalid port") from error

    scheme = parts.scheme.lower()
    host = parts.hostname.lower().rstrip(".")
    default = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default else f"{host}:{port}"
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMETERS
        ),
        doseq=True,
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def validate_public_target(value: str, resolver: Callable = socket.getaddrinfo) -> str:
    normalized = normalize_public_url(value)
    parts = urlsplit(normalized)
    try:
        answers = resolver(
            parts.hostname,
            parts.port or (443 if parts.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        raise ValueError("website hostname could not be resolved") from error

    addresses = {answer[4][0].split("%", 1)[0] for answer in answers}
    if not addresses or any(not ip_address(address).is_global for address in addresses):
        raise ValueError("website hostname resolves to a non-public address")
    return normalized
