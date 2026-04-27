"""pytest plugin -- exposes ``record``, ``trace_tool``, and ``expect_snapshot`` as fixtures.

Loaded automatically when ``pytest`` is installed via the
``pytest11`` entry point in ``pyproject.toml``. To use::

    def test_my_agent(agentsnap_record, expect_snapshot):
        trace = agentsnap_record(lambda: my_agent.run())
        expect_snapshot(trace, "tests/__snapshots__/my_agent.snap.json")
"""

from __future__ import annotations

try:
    import pytest
except ImportError:  # pragma: no cover -- pytest is optional at runtime
    pytest = None  # type: ignore[assignment]

from .recorder import record as _record
from .recorder import trace_tool as _trace_tool
from .snapshot import expect_snapshot as _expect_snapshot

if pytest is not None:

    @pytest.fixture
    def agentsnap_record():
        """Pytest fixture exposing ``record`` (the sync recorder)."""
        return _record

    @pytest.fixture
    def trace_tool():
        """Pytest fixture exposing ``trace_tool``."""
        return _trace_tool

    @pytest.fixture
    def expect_snapshot():
        """Pytest fixture exposing ``expect_snapshot``."""
        return _expect_snapshot
