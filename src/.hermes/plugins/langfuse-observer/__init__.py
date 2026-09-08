"""Opt-in, lightweight Langfuse observer for Hermes lifecycle hooks.

# ponytail: simple dictionary-based session routing with global lock.
# Single observer adapter bridging Hermes hooks directly to Langfuse SDK.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
import json
import logging
import os
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

_PLUGIN_ID = "langfuse-observer"
_NATIVE_PLUGIN_IDS = ("observability/langfuse", "langfuse")
_MAX_STATES = 128
_MAX_CHARS = 12000
_FLUSH_TIMEOUT_MILLIS = 5000
_MISSING = object()
_INIT_FAILED = object()

_STATE_LOCK = threading.RLock()
_TRACE_STATE: Dict[str, "_TraceState"] = {}
_CONTEXT: Any = None
_CLIENT: Any = None
_REDACTOR: Optional[Callable[[str], str]] = None
_CURRENT_IDENTITY: ContextVar[Optional["_HostIdentity"]] = ContextVar("identity", default=None)
_STATUS: Dict[str, Any] = {
    "active": False,
    "inactive_reason": "not initialized",
    "health": "unknown",
    "capture_mode": "sanitized",
    "ttft_supported": False,
    "flush_timeout_supported": False,
    "observed_fields": [],
    "capability_gaps": [
        "verified profile identity requires a host pre_gateway_dispatch source or context",
        "verified user identity requires a host pre_gateway_dispatch source or context",
        "TTFT unavailable: on_stream_delta has no event timestamp",
    ],
}


@dataclass(frozen=True)
class _HostIdentity:
    environment: str
    profile: str
    platform: str
    user_id: str
    session_id: str
    session_key: str = ""
    task_id: str = ""


@dataclass
class _TraceState:
    key: str
    root: Any
    session_id: str
    turn_id: str
    task_id: str
    identity: Optional[_HostIdentity]
    generations: Dict[str, Any] = field(default_factory=dict)
    tools: Dict[str, Any] = field(default_factory=dict)
    pending_tools: Dict[str, List[Any]] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    closed: bool = False


class _Observer:
    def get_status(self) -> Dict[str, Any]:
        return get_status()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _set_status(**updates: Any) -> None:
    with _STATE_LOCK:
        _STATUS.update(updates)


def get_status() -> Dict[str, Any]:
    with _STATE_LOCK:
        return dict(_STATUS)


def _load_redactor() -> Optional[Callable[[str], str]]:
    global _REDACTOR
    if _REDACTOR is not None:
        return _REDACTOR
    try:
        from agent.redact import redact_sensitive_text

        def redact(val: str) -> str:
            try:
                return str(redact_sensitive_text(val, force=True))
            except TypeError:
                return str(redact_sensitive_text(val))

        _REDACTOR = redact
    except Exception:
        _REDACTOR = None
    return _REDACTOR


def _redact(val: str) -> str:
    redactor = _load_redactor()
    if redactor is None:
        return "[content omitted: sanitizer unavailable]"
    try:
        res = redactor(val)
        return res if res else "[content omitted: sanitizer unavailable]"
    except Exception:
        return "[content omitted: sanitizer unavailable]"


def _safe_text(val: Any, limit: int = _MAX_CHARS) -> str:
    text = val if isinstance(val, str) else str(val or "")
    redacted = _redact(text)
    if len(redacted) <= limit:
        return redacted
    return redacted[:limit] + f"... [truncated {len(redacted) - limit} chars]"


def _safe_value(val: Any, depth: int = 0) -> Any:
    # ponytail: simple recursive serializer with depth limit
    if depth > 4:
        return "<max-depth>"
    if val is None or isinstance(val, (int, float, bool)):
        return val
    if isinstance(val, str):
        return _safe_text(val)
    if isinstance(val, Mapping):
        return {str(k)[:64]: _safe_value(v, depth + 1) for k, v in list(val.items())[:32]}
    if isinstance(val, (list, tuple)):
        return [_safe_value(x, depth + 1) for x in val[:50]]
    return _safe_text(str(val))


def _capture_content(val: Any) -> Any:
    if isinstance(val, str):
        val = val.strip()
        if (val.startswith("{") and val.endswith("}")) or (val.startswith("[") and val.endswith("]")):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, (dict, list)):
                    return _safe_value(parsed)
            except Exception:
                pass
    return _safe_value(val)


def _digest(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8", "replace")).hexdigest()[:16]


def _opaque_id(prefix: str, *parts: Any) -> str:
    raw = json.dumps([prefix, *[str(p or "") for p in parts]], ensure_ascii=True, separators=(",", ":"))
    return prefix + ":" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_sdk():
    try:
        from langfuse import Langfuse
        return Langfuse
    except Exception:
        return None


def _native_exporter_enabled() -> bool:
    checker = getattr(_CONTEXT, "has_plugin", None)
    if callable(checker):
        try:
            return any(checker(p) for p in _NATIVE_PLUGIN_IDS)
        except Exception:
            return True
    return False


def _get_client() -> Any:
    global _CLIENT
    if _native_exporter_enabled():
        _set_status(active=False, inactive_reason="native Langfuse exporter is enabled", health="inactive")
        return None
    if _CLIENT is _INIT_FAILED:
        return None
    if _CLIENT is not None:
        return _CLIENT

    with _STATE_LOCK:
        if _CLIENT is not None:
            return _CLIENT if _CLIENT is not _INIT_FAILED else None
        pk = _env("HERMES_LANGFUSE_PUBLIC_KEY")
        sk = _env("HERMES_LANGFUSE_SECRET_KEY")
        if not pk or not sk or not (pk.startswith("pk-lf-") and sk.startswith("sk-lf-")):
            _set_status(active=False, inactive_reason="Langfuse credentials missing", health="inactive")
            _CLIENT = _INIT_FAILED
            return None

        sdk_cls = _load_sdk()
        if sdk_cls is None:
            _set_status(active=False, inactive_reason="Langfuse SDK unavailable", health="inactive")
            _CLIENT = _INIT_FAILED
            return None

        try:
            client = sdk_cls(
                public_key=pk,
                secret_key=sk,
                host=_env("HERMES_LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
                environment=_env("HERMES_LANGFUSE_ENV") or None,
                release=_env("HERMES_LANGFUSE_RELEASE") or None,
                sample_rate=float(_env("HERMES_LANGFUSE_SAMPLE_RATE", "1.0")),
                debug=_env("HERMES_LANGFUSE_DEBUG").lower() in {"1", "true", "yes"},
            )
            if not callable(getattr(client, "start_observation", None)):
                _set_status(active=False, inactive_reason="Langfuse SDK lacks start_observation", health="inactive")
                _CLIENT = _INIT_FAILED
                return None
            _CLIENT = client
            _load_redactor()
            health = "ready" if _REDACTOR is not None else "degraded"
            _set_status(active=True, inactive_reason="", health=health, flush_timeout_supported=True)
            return _CLIENT
        except Exception:
            _set_status(active=False, inactive_reason="Langfuse client initialization failed", health="inactive")
            _CLIENT = _INIT_FAILED
            return None


def _start_root(client: Any, key: str, identity: Optional[_HostIdentity], s_id: str, t_id: str, task_id: str, inp: Any) -> Optional[_TraceState]:
    meta = {
        "environment": identity.environment if identity else _env("HERMES_LANGFUSE_ENV", "default"),
        "profile": identity.profile if identity else "unavailable",
        "platform": identity.platform if identity else "unavailable",
        "session_id": s_id or _opaque_id("hermes-session", identity.environment if identity else "default", identity.profile if identity else "", identity.platform if identity else ""),
        "raw_session_id": s_id or "unavailable",
        "turn_id": t_id or "unavailable",
        "identity_source": "host_event" if identity else "unavailable",
        "ttft_supported": False,
        "source": "hermes",
        "capture_mode": "sanitized",
    }
    if identity and identity.user_id:
        meta["user_id"] = _opaque_id("hermes-user", identity.platform or "unknown", identity.profile or "unknown", identity.user_id)

    root_args = {
        "name": "Hermes turn",
        "as_type": "chain",
        "input": _capture_content(inp),
        "metadata": _safe_value(meta),
    }
    fn_trace_id = getattr(client, "create_trace_id", None)
    if callable(fn_trace_id):
        try:
            tid = fn_trace_id(seed=key)
            if tid:
                root_args["trace_context"] = {"trace_id": tid}
        except Exception:
            pass

    try:
        try:
            from langfuse import propagate_attributes
            propagate_ctx = propagate_attributes(
                session_id=meta["session_id"],
                user_id=meta.get("user_id"),
                metadata=_safe_value(meta),
            )
        except Exception:
            propagate_ctx = None

        if propagate_ctx is not None:
            with propagate_ctx:
                root = client.start_observation(**root_args)
        else:
            root = client.start_observation(**root_args)

        if root is None:
            return None

        # v4 / v3 dual update compatibility
        up_dict = {"session_id": meta["session_id"]}
        if "user_id" in meta:
            up_dict["user_id"] = meta["user_id"]
        for fn_name in ("update_trace", "update"):
            up_fn = getattr(root, fn_name, None)
            if callable(up_fn):
                try:
                    up_fn(**up_dict)
                except Exception:
                    pass
        return _TraceState(key=key, root=root, session_id=s_id, turn_id=t_id, task_id=task_id, identity=identity)
    except Exception:
        return None


def _end_obs(obs: Any, output: Any = _MISSING, metadata: Any = None, usage: Any = None, cost: Any = None, error: bool = False, status_message: str = "") -> None:
    if obs is None:
        return
    up: Dict[str, Any] = {}
    if output is not _MISSING:
        up["output"] = _capture_content(output)
    if metadata:
        up["metadata"] = _safe_value(metadata)
    if usage:
        up["usage_details"] = usage
    if cost:
        up["cost_details"] = cost
    if error:
        up["level"] = "ERROR"
        if status_message:
            up["status_message"] = _safe_text(status_message, limit=120)
    fn_up = getattr(obs, "update", None)
    if callable(fn_up):
        try:
            fn_up(**up)
        except Exception:
            pass
    fn_end = getattr(obs, "end", None)
    if callable(fn_end):
        try:
            fn_end()
        except Exception:
            pass


def _close_state(state: _TraceState, output: Any = _MISSING) -> None:
    if state.closed:
        return
    state.closed = True
    for gen in state.generations.values():
        _end_obs(gen)
    for t in state.tools.values():
        _end_obs(t)
    for q in state.pending_tools.values():
        for t in q:
            _end_obs(t)
    state.generations.clear()
    state.tools.clear()
    state.pending_tools.clear()

    safe_out = _capture_content(output) if output is not _MISSING else None
    if safe_out is not None:
        for m in ("update_trace", "update"):
            fn = getattr(state.root, m, None)
            if callable(fn):
                try:
                    fn(output=safe_out)
                except Exception:
                    pass
    fn_end = getattr(state.root, "end", None)
    if callable(fn_end):
        try:
            fn_end()
        except Exception:
            pass


def _ensure_state(kw: Mapping[str, Any], client: Any) -> Optional[_TraceState]:
    ident = _CURRENT_IDENTITY.get()
    s_id = str(kw.get("session_id") or (ident.session_id if ident else "")).strip()
    t_id = str(kw.get("turn_id") or "").strip()
    task_id = str(kw.get("task_id") or (ident.task_id if ident else "")).strip()
    key = "|".join([ident.environment if ident else "default", ident.profile if ident else "", ident.platform if ident else "", s_id, t_id, task_id])

    with _STATE_LOCK:
        if key in _TRACE_STATE:
            return _TRACE_STATE[key]
        while len(_TRACE_STATE) >= _MAX_STATES:
            _, old = _TRACE_STATE.popitem()
            _close_state(old)
        req = kw.get("request_messages") or kw.get("request") or kw.get("message")
        st = _start_root(client, key, ident, s_id, t_id, task_id, req)
        if st:
            _TRACE_STATE[key] = st
        return st


def _on_pre_api_request(**kw: Any) -> None:
    cl = _get_client()
    if not cl:
        return
    st = _ensure_state(kw, cl)
    if not st:
        return
    r_id = str(kw.get("api_request_id") or "0")
    fn_child = getattr(st.root, "start_observation", None)
    if callable(fn_child):
        try:
            gen = fn_child(
                name=f"LLM call {r_id}:attempt:{kw.get('retry_count', 0)}",
                as_type="generation",
                input=_capture_content(kw.get("request_messages") or kw.get("request")),
                model=_safe_text(kw.get("model") or ""),
                metadata=_safe_value({k: kw.get(k) for k in ("api_request_id", "provider", "model", "api_mode", "base_url", "api_call_count") if kw.get(k) is not None}),
            )
            st.generations[r_id] = gen
        except Exception:
            pass


def _on_post_api_request(**kw: Any) -> None:
    cl = _get_client()
    if not cl:
        return
    st = _ensure_state(kw, cl)
    if not st:
        return
    r_id = str(kw.get("api_request_id") or "0")
    with _STATE_LOCK:
        gen = st.generations.pop(r_id, None)
    resp = kw.get("response") or kw.get("assistant_message")
    out = resp.get("content") if isinstance(resp, Mapping) else resp
    usage = kw.get("usage")
    u_det = {"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0)} if isinstance(usage, Mapping) else None
    dur = kw.get("api_duration")
    meta = {"api_duration_s": round(float(dur), 3)} if isinstance(dur, (int, float)) and dur > 0 else None
    _end_obs(gen, output=resp or out, usage=u_det, metadata=meta)

    # If terminal assistant message without tool calls, close turn
    has_tools = False
    if isinstance(resp, Mapping) and resp.get("tool_calls"):
        has_tools = True
    if not has_tools:
        with _STATE_LOCK:
            _TRACE_STATE.pop(st.key, None)
        _close_state(st, output=resp or out)


def _on_api_request_error(**kw: Any) -> None:
    cl = _get_client()
    if not cl:
        return
    st = _ensure_state(kw, cl)
    if not st:
        return
    r_id = str(kw.get("api_request_id") or "0")
    with _STATE_LOCK:
        gen = st.generations.pop(r_id, None)
    err = kw.get("error") or kw.get("error_message") or "api_error"
    _end_obs(gen, error=True, status_message=str(err), metadata=_safe_value(kw))
    if kw.get("retryable") is False:
        with _STATE_LOCK:
            _TRACE_STATE.pop(st.key, None)
        _close_state(st, output={"error": str(err)})


def _nested_tool_error(val: Any) -> Optional[Tuple[str, str]]:
    if isinstance(val, Mapping):
        status = str(val.get("status") or "").lower()
        if val.get("ok") is False or status in {"error", "failed", "failure"}:
            err_obj = val.get("error")
            t = str(err_obj.get("type") if isinstance(err_obj, Mapping) else val.get("error_type") or "tool_error")
            m = str(err_obj.get("message") if isinstance(err_obj, Mapping) else val.get("error_message") or "")
            return (t, m)
        for sub in ("result", "data", "output", "response"):
            res = _nested_tool_error(val.get(sub))
            if res:
                return res
    elif isinstance(val, (list, tuple)):
        for x in val[:10]:
            res = _nested_tool_error(x)
            if res:
                return res
    return None


def _on_pre_tool_call(**kw: Any) -> None:
    cl = _get_client()
    if not cl:
        return
    st = _ensure_state(kw, cl)
    if not st:
        return
    t_name = str(kw.get("tool_name") or "tool")
    cid = str(kw.get("tool_call_id") or "")
    fn_child = getattr(st.root, "start_observation", None)
    if callable(fn_child):
        try:
            tool_obs = fn_child(
                name=f"Tool: {t_name}",
                as_type="tool",
                input=_capture_content(kw.get("args")),
                metadata={"tool_name": t_name, "tool_call_id": cid},
            )
            if cid:
                st.tools[cid] = tool_obs
            else:
                st.pending_tools.setdefault(t_name, []).append(tool_obs)
        except Exception:
            pass


def _on_post_tool_call(**kw: Any) -> None:
    cl = _get_client()
    if not cl:
        return
    st = _ensure_state(kw, cl)
    if not st:
        return
    t_name = str(kw.get("tool_name") or "tool")
    cid = str(kw.get("tool_call_id") or "")
    with _STATE_LOCK:
        obs = st.tools.pop(cid, None) if cid else None
        if not obs and t_name in st.pending_tools and st.pending_tools[t_name]:
            obs = st.pending_tools[t_name].pop(0)

    res = kw.get("result")
    err_info = _nested_tool_error(res) or (("tool_transport", str(kw.get("error") or "tool error")) if kw.get("status") in {"error", "failed"} or kw.get("error") else None)
    meta = {"tool_name": t_name, "tool_call_id": cid}
    if err_info:
        meta["error_kind"] = "tool_result" if _nested_tool_error(res) else "tool_transport"
        meta["error_type"] = err_info[0]
        meta["error_message"] = err_info[1]
    _end_obs(obs, output=res, metadata=meta, error=bool(err_info), status_message=err_info[0] if err_info else "")


def _on_session_finalize(*, session_id: str = "", reason: str = "", **_: Any) -> None:
    with _STATE_LOCK:
        keys = [k for k, v in _TRACE_STATE.items() if not session_id or v.session_id == session_id]
        for k in keys:
            st = _TRACE_STATE.pop(k, None)
            if st:
                _close_state(st)
    cl = _CLIENT
    if cl and cl is not _INIT_FAILED:
        fn_flush = getattr(cl, "flush", None)
        if callable(fn_flush):
            try:
                fn_flush()
            except Exception:
                pass


def _on_pre_gateway_dispatch(event: Any = None, gateway: Any = None, session_store: Any = None, **kw: Any) -> None:
    del gateway, session_store
    src = getattr(event, "source", event)
    s_id = str(kw.get("session_id") or getattr(src, "session_id", "") or "").strip()
    if not s_id:
        return
    _CURRENT_IDENTITY.set(_HostIdentity(
        environment=_env("HERMES_LANGFUSE_ENV", "default"),
        profile=str(getattr(src, "profile", "") or "").strip(),
        platform=str(getattr(getattr(src, "platform", None), "value", getattr(src, "platform", "")) or "").strip(),
        user_id=str(getattr(src, "user_id", "") or "").strip(),
        session_id=s_id,
        task_id=str(kw.get("task_id") or getattr(src, "task_id", "") or "").strip(),
    ))


def register(ctx: Any) -> _Observer:
    global _CONTEXT, _CLIENT
    with _STATE_LOCK:
        _CONTEXT = ctx
        _CLIENT = None
    if _native_exporter_enabled():
        return _Observer()
    _get_client()

    fn_reg = getattr(ctx, "register_hook", None)
    if callable(fn_reg):
        for h, cb in (
            ("pre_gateway_dispatch", _on_pre_gateway_dispatch),
            ("pre_api_request", _on_pre_api_request),
            ("post_api_request", _on_post_api_request),
            ("api_request_error", _on_api_request_error),
            ("pre_tool_call", _on_pre_tool_call),
            ("post_tool_call", _on_post_tool_call),
            ("on_session_finalize", _on_session_finalize),
        ):
            try:
                fn_reg(h, cb)
            except Exception:
                pass
    return _Observer()


__all__ = ["get_status", "register"]
