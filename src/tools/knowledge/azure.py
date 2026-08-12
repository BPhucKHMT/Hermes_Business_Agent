from dataclasses import dataclass
from email.message import Message
import json
import os
import random
import socket
import time
from typing import Callable, Dict, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUIRED_ENV = (
    "AZURE_STORAGE_CONNECTION_STRING",
    "AZURE_STORAGE_CONTAINER",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_ADMIN_KEY",
    "AZURE_SEARCH_QUERY_KEY",
    "AZURE_SEARCH_INDEX",
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
    "AZURE_DOCUMENT_INTELLIGENCE_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
)
SECRET_ENV = tuple(name for name in REQUIRED_ENV if name.endswith("_KEY") or name.endswith("_CONNECTION_STRING"))
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class AzureError(RuntimeError):
    def __init__(self, code: str, status: Optional[int] = None):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> object:
        if not self.body:
            return None
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise AzureError("invalid_json_response", self.status)


Transport = Callable[[str, str, Mapping[str, str], Optional[bytes], float], Response]
Sleeper = Callable[[float], None]


def load_config(environ: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    source = os.environ if environ is None else environ
    missing = [name for name in REQUIRED_ENV if not source.get(name, "").strip()]
    if missing:
        raise ValueError("missing Azure configuration: " + ", ".join(missing))
    config = {name: source[name].strip() for name in REQUIRED_ENV}
    for name in ("AZURE_SEARCH_ENDPOINT", "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "AZURE_OPENAI_ENDPOINT"):
        if not config[name].startswith("https://"):
            raise ValueError(name + " must use https")
    for name in ("AZURE_STORAGE_CONTAINER", "AZURE_SEARCH_INDEX", "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"):
        if any(character in config[name] for character in "\\/\r\n"):
            raise ValueError(name + " contains invalid characters")
    return config


def redact(text: str, config: Mapping[str, str]) -> str:
    sanitized = text
    for name in SECRET_ENV:
        value = config.get(name, "")
        if value:
            sanitized = sanitized.replace(value, "[REDACTED]")
    return sanitized


def urllib_transport(method: str, url: str, headers: Mapping[str, str], body: Optional[bytes], timeout: float) -> Response:
    request = Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urlopen(request, timeout=timeout) as result:
            return Response(result.status, dict(result.headers.items()), result.read())
    except HTTPError as exc:
        return Response(exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read())
    except (socket.timeout, TimeoutError):
        raise AzureError("azure_timeout")
    except URLError as exc:
        raise AzureError("azure_unavailable") from exc


class AzureClient:
    def __init__(
        self,
        transport: Transport = urllib_transport,
        timeout: float = 30.0,
        max_attempts: int = 3,
        sleeper: Sleeper = time.sleep,
        jitter: Callable[[], float] = random.random,
    ):
        if timeout <= 0 or max_attempts < 1:
            raise ValueError("invalid Azure client limits")
        self.transport = transport
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.sleeper = sleeper
        self.jitter = jitter

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        json_body: Optional[object] = None,
    ) -> Response:
        request_headers = dict(headers or {})
        body = None
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.transport(method, url, request_headers, body, self.timeout)
            except AzureError as exc:
                if exc.code not in {"azure_timeout", "azure_unavailable"} or attempt == self.max_attempts:
                    raise
                self.sleeper(self._delay(attempt, {}))
                continue
            if 200 <= response.status < 300:
                return response
            if response.status in {401, 403}:
                raise AzureError("azure_unauthorized", response.status)
            if response.status not in RETRYABLE_STATUS or attempt == self.max_attempts:
                code = "azure_retry_exhausted" if response.status in RETRYABLE_STATUS else "azure_request_failed"
                raise AzureError(code, response.status)
            self.sleeper(self._delay(attempt, response.headers))
        raise AzureError("azure_retry_exhausted")

    def _delay(self, attempt: int, headers: Mapping[str, str]) -> float:
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                pass
        return min((2 ** (attempt - 1)) + self.jitter(), 30.0)


class SearchClients:
    def __init__(self, config: Mapping[str, str], client: AzureClient):
        self.endpoint = config["AZURE_SEARCH_ENDPOINT"].rstrip("/")
        self.index = config["AZURE_SEARCH_INDEX"]
        self.query_key = config["AZURE_SEARCH_QUERY_KEY"]
        self._admin_key = config["AZURE_SEARCH_ADMIN_KEY"]
        self.client = client

    def query(self, payload: object) -> Response:
        return self.client.request(
            "POST",
            "%s/indexes/%s/docs/search?api-version=2024-07-01" % (self.endpoint, self.index),
            {"api-key": self.query_key},
            payload,
        )

    def mutate(self, payload: object) -> Response:
        return self.client.request(
            "POST",
            "%s/indexes/%s/docs/index?api-version=2024-07-01" % (self.endpoint, self.index),
            {"api-key": self._admin_key},
            payload,
        )
