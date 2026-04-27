"""Diff a baseline trace against a current run.

Returns one of five statuses:

* ``PASSED`` -- bytewise structural match (fingerprint ignored).
* ``REGRESSION`` -- current run has a new error, or a tool errored.
* ``TOOLS_CHANGED`` -- set of tool names called differs, or args differ.
* ``TOOLS_REORDERED`` -- same names + args, different order.
* ``OUTPUT_DRIFT`` -- tool sequence + args identical; only output text or
  result hashes differ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Mapping


@dataclass
class Change:
    path: str
    from_: Any  # ``from`` is a Python keyword
    to: Any

    def to_dict(self) -> dict:
        return {"path": self.path, "from": self.from_, "to": self.to}


@dataclass
class DiffResult:
    status: str
    changes: List[Change] = field(default_factory=list)


def diff(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> DiffResult:
    """Compare two traces. Returns a :class:`DiffResult`."""
    if not isinstance(baseline, Mapping):
        raise TypeError("diff: baseline must be a trace dict")
    if not isinstance(current, Mapping):
        raise TypeError("diff: current must be a trace dict")

    if _canonical(baseline) == _canonical(current):
        return DiffResult(status="PASSED", changes=[])

    # New top-level error -> REGRESSION (highest severity).
    if not baseline.get("error") and current.get("error"):
        return DiffResult(
            status="REGRESSION",
            changes=[Change(path="error", from_=None, to=current["error"])],
        )

    base_tools = list(baseline.get("tools") or [])
    cur_tools = list(current.get("tools") or [])

    base_tool_errors = any(t.get("error") for t in base_tools)
    cur_tool_errors = any(t.get("error") for t in cur_tools)
    if not base_tool_errors and cur_tool_errors:
        i = next(
            (idx for idx, t in enumerate(cur_tools) if t.get("error")), -1
        )
        return DiffResult(
            status="REGRESSION",
            changes=[
                Change(
                    path="tools[" + str(i) + "].error",
                    from_=None,
                    to=cur_tools[i].get("error"),
                )
            ],
        )

    base_names = [t.get("name") for t in base_tools]
    cur_names = [t.get("name") for t in cur_tools]

    # Tool name multiset comparison.
    if not _same_multiset(base_names, cur_names):
        return DiffResult(
            status="TOOLS_CHANGED",
            changes=[
                Change(path="tools[].name", from_=base_names, to=cur_names)
            ],
        )

    # Same multiset, different order -> TOOLS_REORDERED.
    if base_names != cur_names:
        return DiffResult(
            status="TOOLS_REORDERED",
            changes=[
                Change(path="tools[].order", from_=base_names, to=cur_names)
            ],
        )

    # Same names + order. Check args, then result_hash.
    changes: List[Change] = []
    for i, (b, c) in enumerate(zip(base_tools, cur_tools)):
        if _canonical_value(b.get("args")) != _canonical_value(c.get("args")):
            changes.append(
                Change(
                    path="tools[" + str(i) + "].args",
                    from_=b.get("args"),
                    to=c.get("args"),
                )
            )
    if changes:
        return DiffResult(status="TOOLS_CHANGED", changes=changes)

    for i, (b, c) in enumerate(zip(base_tools, cur_tools)):
        if b.get("result_hash") != c.get("result_hash"):
            changes.append(
                Change(
                    path="tools[" + str(i) + "].result_hash",
                    from_=b.get("result_hash"),
                    to=c.get("result_hash"),
                )
            )

    if baseline.get("output") != current.get("output"):
        changes.append(
            Change(
                path="output",
                from_=baseline.get("output"),
                to=current.get("output"),
            )
        )

    if baseline.get("model") != current.get("model"):
        changes.append(
            Change(
                path="model",
                from_=baseline.get("model"),
                to=current.get("model"),
            )
        )

    if changes:
        return DiffResult(status="OUTPUT_DRIFT", changes=changes)

    return DiffResult(status="PASSED", changes=[])


def _canonical(trace: Mapping[str, Any]) -> str:
    rest = {k: v for k, v in trace.items() if k != "fingerprint"}
    return _canonical_value(rest)


def _canonical_value(value: Any) -> str:
    return json.dumps(_sort_keys(value), default=str)


def _sort_keys(value: Any) -> Any:
    if isinstance(value, list):
        return [_sort_keys(v) for v in value]
    if isinstance(value, Mapping):
        return {k: _sort_keys(value[k]) for k in sorted(value.keys())}
    return value


def _same_multiset(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    return sorted(a, key=str) == sorted(b, key=str)
