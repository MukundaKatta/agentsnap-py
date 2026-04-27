"""Tests for :func:`agentsnap.expect_snapshot`."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agentsnap import AgentSnapshotMismatch, expect_snapshot, record, trace_tool


def _agent_trace():
    fn = trace_tool("hello", lambda: "world")
    return record(lambda: fn())


def test_first_run_creates_snapshot(tmp_path_factory=None):
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "snap.json")
        trace = _agent_trace()
        result = expect_snapshot(trace, path)
        assert result["status"] == "CREATED"
        assert Path(path).exists()


def test_second_run_with_same_trace_passes():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "snap.json")
        trace = _agent_trace()
        expect_snapshot(trace, path)  # CREATE
        result = expect_snapshot(_agent_trace(), path)  # PASS
        assert result["status"] == "PASSED"


def test_run_with_different_tool_names_raises():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "snap.json")
        baseline = record(lambda: trace_tool("a", lambda: 1)())
        expect_snapshot(baseline, path)

        current = record(lambda: trace_tool("b", lambda: 1)())
        with pytest.raises(AgentSnapshotMismatch) as exc:
            expect_snapshot(current, path)
        assert exc.value.status == "TOOLS_CHANGED"


def test_update_overwrites_baseline():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "snap.json")
        expect_snapshot(record(lambda: trace_tool("a", lambda: 1)()), path)
        new_trace = record(lambda: trace_tool("b", lambda: 2)())
        result = expect_snapshot(new_trace, path, update=True)
        assert result["status"] == "UPDATED"
        with open(path) as f:
            on_disk = json.load(f)
        assert on_disk["tools"][0]["name"] == "b"


def test_fail_on_can_be_overridden_to_pass_on_changed():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "snap.json")
        expect_snapshot(record(lambda: trace_tool("a", lambda: 1)()), path)
        current = record(lambda: trace_tool("b", lambda: 1)())
        # By overriding fail_on to a status the diff won't produce, no raise.
        result = expect_snapshot(current, path, fail_on=["REGRESSION"])
        assert result["status"] == "TOOLS_CHANGED"
        assert "changes" in result


def test_invalid_path_raises():
    with pytest.raises(TypeError):
        expect_snapshot({"version": 1}, "")


def test_invalid_trace_raises():
    with pytest.raises(TypeError):
        expect_snapshot("not a dict", "/tmp/x.json")  # type: ignore[arg-type]
