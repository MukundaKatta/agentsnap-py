"""agentsnap -- snapshot tests for AI agents.

Public surface (mirrors the JS sibling):

* ``record(fn, ...)`` -- run an agent fn and capture every traced tool call.
* ``trace_tool(name, fn)`` -- wrap a tool fn so calls inside ``record`` are recorded.
* ``expect_snapshot(trace, path, ...)`` -- compare against a JSON baseline on disk.
* ``diff(baseline, current)`` -- low-level diff returning a ``DiffResult``.
* ``format_diff(result, path=None)`` -- render a colored terminal block.
* ``AgentSnapshotMismatch`` -- raised by ``expect_snapshot`` on a failing status.

Both sync and async versions of ``record`` are provided. Use ``arecord`` /
``aexpect_snapshot`` for async agents; ``record`` / ``expect_snapshot`` for
sync ones. Tracing uses ``contextvars`` so it composes cleanly with asyncio.
"""

from .diff import Change, DiffResult, diff
from .format import format_diff
from .recorder import (
    Trace,
    arecord,
    record,
    trace_tool,
)
from .snapshot import AgentSnapshotMismatch, aexpect_snapshot, expect_snapshot

__version__ = "0.1.0"
VERSION = __version__

__all__ = [
    "VERSION",
    "AgentSnapshotMismatch",
    "Change",
    "DiffResult",
    "Trace",
    "aexpect_snapshot",
    "arecord",
    "diff",
    "expect_snapshot",
    "format_diff",
    "record",
    "trace_tool",
]
