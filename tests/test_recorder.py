"""Tests for :func:`agentsnap.record` and :func:`agentsnap.trace_tool`."""

from __future__ import annotations

import asyncio

import pytest

from agentsnap import arecord, record, trace_tool


def test_record_captures_tool_calls():
    search = trace_tool("search", lambda q: ["hit-1", "hit-2"])
    summarize = trace_tool("summarize", lambda docs: "summary of " + str(len(docs)))

    def agent():
        docs = search("rlhf")
        return summarize(docs)

    trace = record(agent)
    assert trace["error"] is None
    assert [t["name"] for t in trace["tools"]] == ["search", "summarize"]
    assert trace["tools"][0]["args"] == "rlhf"
    assert trace["output"] == "summary of 2"


def test_trace_tool_outside_record_is_passthrough():
    fn = trace_tool("noop", lambda x: x * 2)
    assert fn(21) == 42  # nothing recorded; just runs


def test_record_capture_results_stores_raw_value():
    fn = trace_tool("echo", lambda x: {"value": x})
    trace = record(lambda: fn(7), capture_results=True)
    assert trace["tools"][0]["result"] == {"value": 7}
    assert trace["tools"][0]["result_hash"].startswith("sha256:")


def test_record_default_does_not_store_raw_results():
    fn = trace_tool("echo", lambda x: {"value": x})
    trace = record(lambda: fn(7))
    assert "result" not in trace["tools"][0]
    assert trace["tools"][0]["result_hash"].startswith("sha256:")


def test_record_records_top_level_error():
    def boom():
        raise RuntimeError("nope")

    trace = record(boom)
    assert trace["error"] == {"name": "RuntimeError", "message": "nope"}
    assert trace["output"] is None


def test_trace_tool_records_tool_error_then_reraises():
    def bad_tool(_):
        raise ValueError("bad arg")

    bad = trace_tool("bad", bad_tool)

    def agent():
        return bad(1)

    trace = record(agent)
    assert trace["error"]["name"] == "ValueError"
    assert trace["tools"][0]["error"] == {"name": "ValueError", "message": "bad arg"}


def test_record_input_and_model_passthrough():
    trace = record(lambda: "ok", input="hello", model="claude-sonnet-4-6")
    assert trace["input"] == "hello"
    assert trace["model"] == "claude-sonnet-4-6"


def test_record_rejects_async_fn():
    async def agent():
        return 1

    with pytest.raises(TypeError):
        record(agent)


def test_arecord_works_with_async_agent():
    async def search_impl(q):
        return [q + "-1"]

    asearch = trace_tool("search", search_impl)

    async def agent():
        return await asearch("alpha")

    trace = asyncio.run(arecord(agent))
    assert trace["tools"][0]["name"] == "search"
    assert trace["tools"][0]["args"] == "alpha"
    assert trace["error"] is None


def test_trace_tool_normalizes_multiple_args_as_list():
    fn = trace_tool("two-args", lambda a, b: a + b)
    trace = record(lambda: fn(1, 2))
    assert trace["tools"][0]["args"] == [1, 2]


def test_trace_tool_kwargs_recorded_as_dict():
    fn = trace_tool("kw", lambda **kw: sum(kw.values()))
    trace = record(lambda: fn(a=1, b=2))
    assert trace["tools"][0]["args"] == {"a": 1, "b": 2}


def test_trace_tool_invalid_name_raises():
    with pytest.raises(TypeError):
        trace_tool("", lambda: None)


def test_trace_tool_invalid_fn_raises():
    with pytest.raises(TypeError):
        trace_tool("x", "not a function")  # type: ignore[arg-type]
