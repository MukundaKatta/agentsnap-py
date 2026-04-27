"""Trace recorder.

Uses :mod:`contextvars` (Python's native AsyncLocalStorage equivalent) so a
``trace_tool``-wrapped function knows whether it's running inside a
``record(...)`` block. Outside ``record``, wrapped tools are transparent
pass-throughs.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import hashlib
import inspect
import json
import platform
import sys
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, Union

T = TypeVar("T")

_recorder_var: contextvars.ContextVar[Optional["_Recorder"]] = contextvars.ContextVar(
    "agentsnap_recorder", default=None
)


@dataclass
class _Recorder:
    tools: List[Dict[str, Any]] = field(default_factory=list)
    capture_results: bool = False


# ``Trace`` is just a typed dict-shaped dataclass we serialize as JSON. Using a
# dict (not a dataclass instance) is intentional so users can mutate / inspect
# trace dicts inline in tests without ceremony.
Trace = Dict[str, Any]


def record(
    fn: Callable[[], T],
    *,
    input: Optional[str] = None,
    model: Optional[str] = None,
    capture_results: bool = False,
) -> Trace:
    """Run ``fn`` (sync) and capture every ``trace_tool``-wrapped call inside it.

    For async agents use :func:`arecord` instead. Returns a JSON-serializable
    trace dict.
    """
    if not callable(fn):
        raise TypeError("record: fn must be callable")
    recorder = _Recorder(capture_results=capture_results)
    token = _recorder_var.set(recorder)
    output: Any = None
    error: Optional[Dict[str, str]] = None
    try:
        output = fn()
        if inspect.isawaitable(output):
            raise TypeError(
                "record: fn returned an awaitable; use arecord(fn) for async agents."
            )
    except Exception as exc:
        error = _serialize_error(exc)
    finally:
        _recorder_var.reset(token)

    return _build_trace(
        recorder=recorder,
        output=output,
        error=error,
        input=input,
        model=model,
    )


async def arecord(
    fn: Callable[[], Awaitable[T]],
    *,
    input: Optional[str] = None,
    model: Optional[str] = None,
    capture_results: bool = False,
) -> Trace:
    """Run ``fn`` (async) and capture every ``trace_tool``-wrapped call.

    The async variant of :func:`record`. ``fn`` should be a zero-arg async
    callable (typically a lambda wrapping your real agent call).
    """
    if not callable(fn):
        raise TypeError("arecord: fn must be callable")
    recorder = _Recorder(capture_results=capture_results)
    token = _recorder_var.set(recorder)
    output: Any = None
    error: Optional[Dict[str, str]] = None
    try:
        coro_or_value = fn()
        if inspect.isawaitable(coro_or_value):
            output = await coro_or_value
        else:
            output = coro_or_value
    except Exception as exc:
        error = _serialize_error(exc)
    finally:
        _recorder_var.reset(token)

    return _build_trace(
        recorder=recorder,
        output=output,
        error=error,
        input=input,
        model=model,
    )


def trace_tool(name: str, fn: Callable[..., T]) -> Callable[..., T]:
    """Wrap a tool function so calls inside ``record`` are appended to the trace.

    Outside ``record`` the wrapper is a transparent pass-through.

    Works with both sync and async tools; the wrapped callable returns the
    same shape (sync result for sync tools, coroutine for async ones).
    """
    if not isinstance(name, str) or not name:
        raise TypeError("trace_tool: name must be a non-empty string")
    if not callable(fn):
        raise TypeError("trace_tool: fn must be callable")

    is_coroutine = asyncio.iscoroutinefunction(fn)

    if is_coroutine:

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            recorder = _recorder_var.get()
            if recorder is None:
                return await fn(*args, **kwargs)
            entry: Dict[str, Any] = {
                "name": name,
                "args": _normalize_args(args, kwargs),
            }
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                entry["error"] = _serialize_error(exc)
                recorder.tools.append(entry)
                raise
            entry["result_hash"] = _hash_result(result)
            if recorder.capture_results:
                entry["result"] = result
            recorder.tools.append(entry)
            return result

        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args, **kwargs):
        recorder = _recorder_var.get()
        if recorder is None:
            return fn(*args, **kwargs)
        entry: Dict[str, Any] = {
            "name": name,
            "args": _normalize_args(args, kwargs),
        }
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            entry["error"] = _serialize_error(exc)
            recorder.tools.append(entry)
            raise
        entry["result_hash"] = _hash_result(result)
        if recorder.capture_results:
            entry["result"] = result
        recorder.tools.append(entry)
        return result

    return sync_wrapper


# --- helpers --------------------------------------------------------------


def _normalize_args(args: tuple, kwargs: dict) -> Any:
    """Mirror the JS rule: single positional arg -> the value; otherwise a list/dict.

    Python adds keyword args, which JS doesn't have. If kwargs are present, we
    record them as a dict alongside args.
    """
    if not kwargs:
        if len(args) == 1:
            return args[0]
        return list(args)
    if not args:
        return dict(kwargs)
    return {"args": list(args), "kwargs": dict(kwargs)}


def _normalize_output(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except Exception:
        return str(value)


def _serialize_error(err: BaseException) -> Dict[str, str]:
    return {
        "name": type(err).__name__,
        "message": str(err),
    }


def _hash_result(value: Any) -> str:
    if isinstance(value, str):
        s = value
    else:
        try:
            s = json.dumps(value, default=str, sort_keys=True)
        except Exception:
            s = str(value)
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def _build_trace(
    *,
    recorder: _Recorder,
    output: Any,
    error: Optional[Dict[str, str]],
    input: Optional[str],
    model: Optional[str],
) -> Trace:
    return {
        "version": 1,
        "model": model,
        "input": input,
        "output": None if error else _normalize_output(output),
        "tools": recorder.tools,
        "error": error,
        "fingerprint": {
            "python": platform.python_version(),
            "agentsnap": "0.1.0",
        },
    }
