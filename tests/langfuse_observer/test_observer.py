from __future__ import annotations

from collections.abc import Callable
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "src/.hermes/plugins/langfuse-observer"

upstream_env = os.environ.get("HERMES_UPSTREAM_PATH")
if not upstream_env:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidate = Path(local_app_data) / "hermes/hermes-agent"
    if candidate.is_dir():
        upstream_env = str(candidate)
if upstream_env:
    upstream_path = Path(upstream_env)
    if upstream_path.is_dir() and str(upstream_path) not in sys.path:
        sys.path.insert(0, str(upstream_path))
import httpx  # noqa: E402 -- imports follow optional upstream path bootstrap
from langfuse import (  # noqa: E402 -- imports follow optional upstream path bootstrap
    Langfuse as RealLangfuse,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: E402 -- imports follow optional upstream path bootstrap
    OTLPSpanExporter,
)
from opentelemetry.sdk.trace import (  # noqa: E402 -- imports follow optional upstream path bootstrap
    TracerProvider,
)
from opentelemetry.sdk.trace.export import (  # noqa: E402 -- imports follow optional upstream path bootstrap
    SimpleSpanProcessor,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402 -- imports follow optional upstream path bootstrap
    InMemorySpanExporter,
)


class CallbackContext:
    """Small boundary fixture matching the host callback registry."""

    def __init__(self) -> None:
        self.hooks: dict[str, list[Callable[..., Any]]] = {}
        self.enabled_plugins: set[str] = set()

    def register_hook(self, name: str, callback: Callable[..., Any]) -> None:
        self.hooks.setdefault(name, []).append(callback)

    def has_plugin(self, name: str) -> bool:
        return name in self.enabled_plugins


def load_observer() -> Any:
    name = "h016_langfuse_observer_under_test"
    path = PLUGIN / "__init__.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load observer plugin from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def emit(context: CallbackContext, hook: str, **payload: Any) -> list[Any]:
    return [callback(**payload) for callback in context.hooks.get(hook, [])]


def status_of(module: Any, registration: Any) -> dict[str, Any]:
    getter = getattr(registration, "get_status", None)
    module_getter = getattr(module, "get_status", None)
    if callable(getter):
        status = getter()
    elif callable(module_getter):
        status = module_getter()
    elif isinstance(registration, dict):
        status = registration
    else:
        raise AssertionError("register(ctx) exposed no status API")
    assert isinstance(status, dict)
    return status


def api_payload(
    *,
    session_id: str,
    turn_id: str,
    api_request_id: str,
    api_call_count: int,
    message: Any = "synthetic request",
) -> dict[str, Any]:
    messages = [{"role": "user", "content": message}]
    return {
        "task_id": "task-example-com",
        "session_id": session_id,
        "turn_id": turn_id,
        "api_request_id": api_request_id,
        "api_call_count": api_call_count,
        "retry_count": max(0, api_call_count - 1),
        "max_retries": 2,
        "platform": "telegram",
        "model": "synthetic-model",
        "provider": "synthetic-provider",
        "base_url": "https://example.com/v1",
        "api_mode": "chat_completion",
        "request_messages": messages,
        "request": {"body": {"messages": messages}},
        "conversation_history": [],
        "message_count": len(messages),
        "tool_count": 0,
        "started_at": 100.0 + api_call_count,
    }


def post_payload(base: dict[str, Any], content: Any) -> dict[str, Any]:
    result = dict(base)
    result.update(
        {
            "api_duration": 0.125,
            "ended_at": result["started_at"] + 0.125,
            "finish_reason": "stop",
            "response_model": "synthetic-model",
            "assistant_message": {
                "role": "assistant",
                "content": content,
                "tool_calls": [],
            },
            "response": {
                "assistant_message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [],
                }
            },
            "usage": {"input_tokens": 12, "output_tokens": 7},
            "assistant_content_chars": len(str(content)),
            "assistant_tool_call_count": 0,
        }
    )
    return result


def span_text(span: Any) -> str:
    return repr(dict(span.attributes))


def span_type(span: Any) -> str:
    return str(span.attributes.get("langfuse.observation.type", ""))


def decode(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def trace_roots(exporter: InMemorySpanExporter) -> list[Any]:
    return [
        span
        for span in exporter.get_finished_spans()
        if "session.id" in span.attributes
        or "langfuse.trace.session.id" in span.attributes
    ]


def root_for_session(roots: list[Any], session_id: str) -> Any:
    matches = []
    for root in roots:
        meta_sess = str(
            root.attributes.get("langfuse.observation.metadata.session_id") or ""
        )
        attrs_text = repr(dict(root.attributes))
        if session_id in meta_sess or session_id in attrs_text:
            matches.append(root)
    assert len(matches) == 1, f"Expected 1 root for {session_id}, found {len(matches)}"
    return matches[0]


def configure_environment(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    monkeypatch.setenv("HERMES_REDACT_SECRETS", "true")
    monkeypatch.setenv("HERMES_LANGFUSE_PUBLIC_KEY", f"pk-lf-h016-{request.node.name}")
    monkeypatch.setenv("HERMES_LANGFUSE_SECRET_KEY", "sk-lf-h016-synthetic-secret")
    monkeypatch.setenv("HERMES_LANGFUSE_BASE_URL", "https://example.com")
    monkeypatch.setenv("HERMES_LANGFUSE_CAPTURE", "sanitized")
    monkeypatch.setenv("LANGFUSE_MEDIA_UPLOAD_ENABLED", "false")


@pytest.fixture
def registered_observer(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
):
    configure_environment(monkeypatch, request)
    monkeypatch.setattr(
        OTLPSpanExporter,
        "export",
        lambda self, spans, *args, **kwargs: SpanExportResult.SUCCESS,
        raising=False,
    )
    observer = load_observer()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    transport = httpx.MockTransport(
        lambda http_request: httpx.Response(
            200,
            request=http_request,
            json={"data": [], "success": True},
        )
    )

    class TestLangfuse(RealLangfuse):
        def __init__(self, **kwargs: Any) -> None:
            options = dict(kwargs)
            options.update(
                {
                    "tracer_provider": provider,
                    "tracing_enabled": True,
                    "httpx_client": httpx.Client(transport=transport),
                    "flush_at": 1000,
                    "flush_interval": 0.1,
                }
            )
            super().__init__(**options)

    monkeypatch.setattr(observer, "_load_sdk", lambda: TestLangfuse)
    context = CallbackContext()
    registration = observer.register(context)
    yield observer, context, registration, exporter

    client = getattr(observer, "_CLIENT", None)
    if client not in (None, getattr(observer, "_INIT_FAILED", object())):
        shutdown = getattr(client, "shutdown", None)
        if callable(shutdown):
            shutdown()


@pytest.fixture
def inactive_observer(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    configure_environment(monkeypatch, request)
    observer = load_observer()
    monkeypatch.setattr(observer, "_load_sdk", lambda: None)
    context = CallbackContext()
    registration = observer.register(context)
    return observer, context, registration, InMemorySpanExporter()


@pytest.fixture
def missing_key_observer(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
):
    configure_environment(monkeypatch, request)
    monkeypatch.delenv("HERMES_LANGFUSE_SECRET_KEY", raising=False)
    observer = load_observer()
    context = CallbackContext()
    registration = observer.register(context)
    return observer, context, registration, InMemorySpanExporter()


def test_register_exposes_standard_callbacks_and_safe_status(
    registered_observer,
) -> None:
    observer, context, registration, _ = registered_observer

    required_hooks = {
        "pre_api_request",
        "post_api_request",
        "api_request_error",
        "pre_tool_call",
        "post_tool_call",
        "on_session_finalize",
    }
    assert required_hooks <= set(context.hooks)

    status = status_of(observer, registration)
    assert {"active", "inactive_reason", "health", "ttft_supported"} <= status.keys()
    assert status["ttft_supported"] is False
    assert "pk-lf-" not in json.dumps(status)
    assert "sk-lf-" not in json.dumps(status)


def test_two_sessions_and_turns_keep_roots_and_outputs_separate(
    registered_observer,
) -> None:
    _, context, _, exporter = registered_observer

    first = api_payload(
        session_id="session-example-a",
        turn_id="turn-example-a",
        api_request_id="api-example-a",
        api_call_count=1,
        message="request-a",
    )
    second = api_payload(
        session_id="session-example-b",
        turn_id="turn-example-b",
        api_request_id="api-example-b",
        api_call_count=1,
        message="request-b",
    )
    emit(context, "pre_api_request", **first)
    emit(context, "pre_api_request", **second)
    emit(context, "post_api_request", **post_payload(first, "answer-a"))
    emit(context, "post_api_request", **post_payload(second, "answer-b"))

    roots = trace_roots(exporter)
    assert len(roots) == 2
    first_root = root_for_session(roots, "session-example-a")
    second_root = root_for_session(roots, "session-example-b")
    assert "answer-a" in span_text(first_root)
    assert "answer-b" in span_text(second_root)
    assert "answer-b" not in span_text(first_root)
    assert "answer-a" not in span_text(second_root)
    assert len({root.context.trace_id for root in roots}) == 2


def test_retry_creates_distinct_generations_under_one_root(registered_observer) -> None:
    _, context, _, exporter = registered_observer

    first = api_payload(
        session_id="session-retry",
        turn_id="turn-retry",
        api_request_id="api-retry-1",
        api_call_count=1,
    )
    second = api_payload(
        session_id="session-retry",
        turn_id="turn-retry",
        api_request_id="api-retry-2",
        api_call_count=2,
    )
    emit(context, "pre_api_request", **first)
    emit(
        context,
        "api_request_error",
        **first,
        error={"type": "RateLimitError", "message": "temporary example.com failure"},
        error_type="RateLimitError",
        error_message="temporary example.com failure",
        status_code=429,
        retryable=True,
        reason="rate_limit",
    )
    emit(context, "pre_api_request", **second)
    emit(context, "post_api_request", **post_payload(second, "retry-success"))

    spans = list(exporter.get_finished_spans())
    roots = trace_roots(exporter)
    generations = [span for span in spans if span_type(span) == "generation"]
    assert len(roots) == 1
    assert len(generations) == 2
    assert {span.context.trace_id for span in generations} == {
        roots[0].context.trace_id
    }
    assert all(span.end_time is not None for span in spans)
    assert "retry-success" in span_text(roots[0])


def test_terminal_tool_error_captures_transport_and_nested_provider_failure(
    registered_observer,
) -> None:
    _, context, _, exporter = registered_observer

    base = api_payload(
        session_id="session-tool-error",
        turn_id="turn-tool-error",
        api_request_id="api-tool-error",
        api_call_count=1,
        message="invoke synthetic tool",
    )
    emit(context, "pre_api_request", **base)
    emit(
        context,
        "post_api_request",
        **dict(
            base,
            assistant_message={
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call-example", "name": "example_tool"}],
            },
            response={
                "assistant_message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "call-example", "name": "example_tool"}],
                }
            },
            usage={"input_tokens": 5, "output_tokens": 2},
            api_duration=0.1,
            assistant_tool_call_count=1,
        ),
    )
    emit(
        context,
        "pre_tool_call",
        task_id=base["task_id"],
        session_id=base["session_id"],
        turn_id=base["turn_id"],
        api_request_id=base["api_request_id"],
        tool_name="example_tool",
        tool_call_id="call-example",
        args={
            "url": "https://example.com/resource",
            "user_id": "caller-supplied-must-not-become-identity",
        },
    )
    emit(
        context,
        "post_tool_call",
        task_id=base["task_id"],
        session_id=base["session_id"],
        turn_id=base["turn_id"],
        api_request_id=base["api_request_id"],
        tool_name="example_tool",
        tool_call_id="call-example",
        args={"url": "https://example.com/resource"},
        result={
            "result": {
                "response": {
                    "ok": False,
                    "status": "error",
                    "error": {
                        "type": "ProviderRejected",
                        "message": "provider rejected synthetic request",
                    },
                }
            }
        },
        status="ok",
        duration_ms=11,
    )
    emit(
        context,
        "on_session_finalize",
        session_id=base["session_id"],
        reason="completed",
    )

    tools = [
        span for span in exporter.get_finished_spans() if span_type(span) == "tool"
    ]
    assert len(tools) == 1
    tool = tools[0]
    assert tool.status.is_ok is False
    assert tool.status.description == "ProviderRejected"
    meta_err_kind = tool.attributes.get("langfuse.observation.metadata.error_kind")
    if not meta_err_kind and "langfuse.observation.metadata" in tool.attributes:
        metadata = decode(tool.attributes["langfuse.observation.metadata"])
        meta_err_kind = metadata.get("error_kind")
    assert meta_err_kind == "tool_result"
    roots = trace_roots(exporter)
    assert len(roots) == 1
    assert "user.id" not in roots[0].attributes
    assert "caller-supplied-must-not-become-identity" not in span_text(roots[0])
    assert "provider rejected synthetic request" in span_text(tool)


def test_full_capture_setting_cannot_bypass_canary_redaction(
    registered_observer, monkeypatch
) -> None:
    observer, context, registration, exporter = registered_observer
    canary = "sk-test-canary-0123456789abcdef"
    monkeypatch.setenv("HERMES_LANGFUSE_CAPTURE", "full")

    output_case = api_payload(
        session_id="session-redact-output",
        turn_id="turn-redact-output",
        api_request_id="api-redact-output",
        api_call_count=1,
        message=f"input {canary}",
    )
    emit(context, "pre_api_request", **output_case)
    emit(context, "post_api_request", **post_payload(output_case, f"output {canary}"))

    error_case = api_payload(
        session_id="session-redact-error",
        turn_id="turn-redact-error",
        api_request_id="api-redact-error",
        api_call_count=1,
        message=f"input {canary}",
    )
    emit(context, "pre_api_request", **error_case)
    emit(
        context,
        "api_request_error",
        **error_case,
        error={"type": "SyntheticError", "message": f"error {canary}"},
        error_type="SyntheticError",
        error_message=f"error {canary}",
        status_code=400,
        retryable=False,
        reason="terminal",
    )

    status = status_of(observer, registration)
    assert status["capture_mode"] == "sanitized"
    finished_text = "\n".join(span_text(span) for span in exporter.get_finished_spans())
    assert canary not in finished_text
    assert any("input" in span_text(span) for span in exporter.get_finished_spans())
    assert any("output" in span_text(span) for span in exporter.get_finished_spans())
    assert any("error" in span_text(span) for span in exporter.get_finished_spans())


def test_duplicate_exporter_detected_when_loaded_after_registration(
    registered_observer,
) -> None:
    observer, context, registration, exporter = registered_observer
    context.enabled_plugins.add("langfuse")

    payload = api_payload(
        session_id="session-duplicate",
        turn_id="turn-duplicate",
        api_request_id="api-duplicate",
        api_call_count=1,
    )
    emit(context, "pre_api_request", **payload)

    status = status_of(observer, registration)
    assert status["active"] is False
    assert "native langfuse exporter" in status["inactive_reason"].lower()
    assert exporter.get_finished_spans() == ()


def test_missing_sdk_reports_clear_inactive_reason(inactive_observer) -> None:
    observer, context, registration, exporter = inactive_observer

    payload = api_payload(
        session_id="session-no-sdk",
        turn_id="turn-no-sdk",
        api_request_id="api-no-sdk",
        api_call_count=1,
    )
    emit(context, "pre_api_request", **payload)

    status = status_of(observer, registration)
    assert status["active"] is False
    assert "sdk" in status["inactive_reason"].lower()


def test_missing_key_reports_clear_inactive_reason(missing_key_observer) -> None:
    observer, context, registration, exporter = missing_key_observer

    payload = api_payload(
        session_id="session-no-key",
        turn_id="turn-no-key",
        api_request_id="api-no-key",
        api_call_count=1,
    )
    emit(context, "pre_api_request", **payload)

    status = status_of(observer, registration)
    assert status["active"] is False
    assert "credential" in status["inactive_reason"].lower()
    assert exporter.get_finished_spans() == ()


def test_session_finalize_closes_bounded_pending_state_once(
    registered_observer,
) -> None:
    _, context, _, exporter = registered_observer

    sessions = [f"session-teardown-{index}" for index in range(8)]
    for index, session_id in enumerate(sessions):
        payload = api_payload(
            session_id=session_id,
            turn_id=f"turn-teardown-{index}",
            api_request_id=f"api-teardown-{index}",
            api_call_count=1,
        )
        emit(context, "pre_api_request", **payload)
        emit(
            context,
            "post_api_request",
            **dict(
                payload,
                assistant_message={
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": f"call-teardown-{index}", "name": "example_tool"}
                    ],
                },
                response={
                    "assistant_message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"id": f"call-teardown-{index}", "name": "example_tool"}
                        ],
                    }
                },
                assistant_tool_call_count=1,
            ),
        )
        emit(
            context,
            "pre_tool_call",
            task_id=payload["task_id"],
            session_id=session_id,
            turn_id=payload["turn_id"],
            api_request_id=payload["api_request_id"],
            tool_name="example_tool",
            tool_call_id=f"call-teardown-{index}",
            args={"id": index, "user_id": "caller-supplied-must-not-become-identity"},
        )

    for session_id in sessions:
        emit(context, "on_session_finalize", session_id=session_id, reason="reset")

    roots = trace_roots(exporter)
    assert all(root_for_session(roots, session_id) for session_id in sessions)
    finished_before_repeat = exporter.get_finished_spans()
    assert all(span.end_time is not None for span in finished_before_repeat)
    for s in sessions:
        assert root_for_session(roots, s) is not None

    for session_id in sessions:
        emit(context, "on_session_finalize", session_id=session_id, reason="reset")
    assert exporter.get_finished_spans() == finished_before_repeat


def test_real_langfuse_otel_exporter_receives_callback_spans_without_network(
    registered_observer,
) -> None:
    _, context, _, exporter = registered_observer
    payload = api_payload(
        session_id="session-otel",
        turn_id="turn-otel",
        api_request_id="api-otel",
        api_call_count=1,
    )

    emit(context, "pre_api_request", **payload)
    emit(context, "post_api_request", **post_payload(payload, "otel-success"))

    finished = exporter.get_finished_spans()
    assert finished
    assert any(span_type(span) == "generation" for span in finished)
    roots = trace_roots(exporter)
    assert len(roots) == 1
    assert "otel-success" in span_text(roots[0])
