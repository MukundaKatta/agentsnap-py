"""Tests for :func:`agentsnap.diff`."""

from __future__ import annotations

import copy

from agentsnap import diff


def _trace(tools, *, output="ok", model=None, error=None):
    return {
        "version": 1,
        "model": model,
        "input": "hello",
        "output": output,
        "tools": tools,
        "error": error,
        "fingerprint": {"python": "3.x", "agentsnap": "0.1.0"},
    }


def _tool(name, args, result_hash="sha256:aaa"):
    return {"name": name, "args": args, "result_hash": result_hash}


def test_diff_passed_when_traces_match():
    a = _trace([_tool("search", "x")])
    b = copy.deepcopy(a)
    b["fingerprint"] = {"python": "different", "agentsnap": "9.9.9"}
    r = diff(a, b)
    assert r.status == "PASSED"
    assert r.changes == []


def test_diff_regression_when_new_top_level_error():
    base = _trace([])
    cur = _trace([], error={"name": "Boom", "message": "bad"})
    r = diff(base, cur)
    assert r.status == "REGRESSION"
    assert r.changes[0].path == "error"


def test_diff_regression_when_tool_errors():
    base = _trace([_tool("a", "x")])
    cur_tool = _tool("a", "x")
    cur_tool["error"] = {"name": "X", "message": "y"}
    cur = _trace([cur_tool])
    r = diff(base, cur)
    assert r.status == "REGRESSION"
    assert r.changes[0].path == "tools[0].error"


def test_diff_tools_changed_when_names_differ():
    base = _trace([_tool("a", "x")])
    cur = _trace([_tool("b", "x")])
    r = diff(base, cur)
    assert r.status == "TOOLS_CHANGED"
    assert r.changes[0].path == "tools[].name"


def test_diff_tools_reordered_when_only_order_differs():
    base = _trace([_tool("a", "x"), _tool("b", "y")])
    cur = _trace([_tool("b", "y"), _tool("a", "x")])
    r = diff(base, cur)
    assert r.status == "TOOLS_REORDERED"


def test_diff_tools_changed_when_args_differ():
    base = _trace([_tool("a", "x")])
    cur = _trace([_tool("a", "y")])
    r = diff(base, cur)
    assert r.status == "TOOLS_CHANGED"
    assert r.changes[0].path == "tools[0].args"


def test_diff_output_drift_when_only_result_hash_changes():
    base = _trace([_tool("a", "x", "sha256:aaa")])
    cur = _trace([_tool("a", "x", "sha256:bbb")])
    r = diff(base, cur)
    assert r.status == "OUTPUT_DRIFT"
    assert any("result_hash" in c.path for c in r.changes)


def test_diff_output_drift_when_only_output_text_changes():
    base = _trace([_tool("a", "x")], output="hello")
    cur = _trace([_tool("a", "x")], output="HELLO")
    r = diff(base, cur)
    assert r.status == "OUTPUT_DRIFT"
    assert any(c.path == "output" for c in r.changes)


def test_diff_output_drift_when_only_model_changes():
    base = _trace([_tool("a", "x")], model="claude")
    cur = _trace([_tool("a", "x")], model="gpt")
    r = diff(base, cur)
    assert r.status == "OUTPUT_DRIFT"
    assert any(c.path == "model" for c in r.changes)


def test_diff_dataclass_changes_are_serializable_via_to_dict():
    base = _trace([_tool("a", "x", "sha256:aaa")])
    cur = _trace([_tool("a", "x", "sha256:bbb")])
    r = diff(base, cur)
    assert r.changes[0].to_dict() == {
        "path": "tools[0].result_hash",
        "from": "sha256:aaa",
        "to": "sha256:bbb",
    }
