"""Compare a trace against a JSON baseline file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional

from .diff import diff as _diff
from .format import format_diff

_DEFAULT_FAILING = ("TOOLS_CHANGED", "TOOLS_REORDERED", "REGRESSION")


class AgentSnapshotMismatch(AssertionError):
    """Raised by :func:`expect_snapshot` when the diff status is in ``fail_on``.

    Subclasses ``AssertionError`` so it integrates cleanly with pytest /
    unittest reporting (treated as a normal test failure).
    """

    def __init__(
        self,
        message: str,
        *,
        status: str,
        changes,
        snapshot_path: str,
    ) -> None:
        super().__init__(message)
        self.name = "AgentSnapshotMismatch"
        self.status = status
        self.changes = changes
        self.snapshot_path = snapshot_path


def expect_snapshot(
    trace: Mapping[str, Any],
    path: str,
    *,
    update: bool = False,
    fail_on: Optional[Iterable[str]] = None,
) -> dict:
    """Compare ``trace`` against ``path``.

    * If the file doesn't exist -> write it (status ``"CREATED"``).
    * If ``update`` is True (or env ``AGENTSNAP_UPDATE=1``) -> overwrite
      (status ``"UPDATED"``).
    * Otherwise diff. If the diff status is in ``fail_on`` (default:
      ``TOOLS_CHANGED | TOOLS_REORDERED | REGRESSION``), raise
      :class:`AgentSnapshotMismatch`.

    Returns a dict ``{"status": ..., "path": ..., "changes": [...]?}``.
    """
    return _expect_snapshot_impl(trace, path, update=update, fail_on=fail_on)


async def aexpect_snapshot(
    trace: Mapping[str, Any],
    path: str,
    *,
    update: bool = False,
    fail_on: Optional[Iterable[str]] = None,
) -> dict:
    """Async-flavored alias for :func:`expect_snapshot`.

    The implementation is sync; the alias just lets you ``await`` it from an
    async test without an extra wrapper.
    """
    return _expect_snapshot_impl(trace, path, update=update, fail_on=fail_on)


def _expect_snapshot_impl(
    trace: Mapping[str, Any],
    path: str,
    *,
    update: bool,
    fail_on: Optional[Iterable[str]],
) -> dict:
    if not isinstance(trace, Mapping):
        raise TypeError("expect_snapshot: trace must be a dict (returned by record())")
    if not isinstance(path, str) or not path:
        raise TypeError("expect_snapshot: path must be a non-empty string")

    file_path = Path(path)
    do_update = update or os.environ.get("AGENTSNAP_UPDATE") == "1"
    fail_on_set = set(fail_on) if fail_on is not None else set(_DEFAULT_FAILING)

    if not file_path.exists():
        _write_snapshot(file_path, trace)
        return {"status": "CREATED", "path": path}

    if do_update:
        _write_snapshot(file_path, trace)
        return {"status": "UPDATED", "path": path}

    with file_path.open("r", encoding="utf-8") as f:
        baseline = json.load(f)

    result = _diff(baseline, trace)

    if result.status in fail_on_set:
        raise AgentSnapshotMismatch(
            format_diff(result, path),
            status=result.status,
            changes=[c.to_dict() for c in result.changes],
            snapshot_path=path,
        )

    return {
        "status": result.status,
        "path": path,
        "changes": [c.to_dict() for c in result.changes],
    }


def _write_snapshot(file_path: Path, trace: Mapping[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, default=str)
        f.write("\n")
