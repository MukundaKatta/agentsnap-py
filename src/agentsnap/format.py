"""Render a :class:`DiffResult` as a colored terminal block.

Honours ``NO_COLOR`` and TTY detection. Used internally by the
``AgentSnapshotMismatch`` error message.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

from .diff import DiffResult

_RESET = "\x1b[0m"
_RED = "\x1b[31m"
_GREEN = "\x1b[32m"
_YELLOW = "\x1b[33m"
_CYAN = "\x1b[36m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"

_STATUS_COLOR = {
    "PASSED": _GREEN,
    "OUTPUT_DRIFT": _YELLOW,
    "TOOLS_REORDERED": _YELLOW,
    "TOOLS_CHANGED": _RED,
    "REGRESSION": _RED,
}


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _c(color: str, text: str) -> str:
    if not _use_color():
        return text
    return color + text + _RESET


def format_diff(result: DiffResult, path: Optional[str] = None) -> str:
    """Render a :class:`DiffResult` as a human-readable terminal block."""
    lines = []
    header_color = _STATUS_COLOR.get(result.status, _RED)
    lines.append(_c(header_color + _BOLD, "agentsnap: " + result.status))
    if path:
        lines.append(_c(_DIM, "  snapshot: " + path))
    lines.append("")

    if not result.changes:
        lines.append(_c(_DIM, "  (no diff details)"))
        return "\n".join(lines)

    for change in result.changes:
        lines.append(_c(_BOLD, "  - " + change.path))
        lines.append(_c(_RED, "    - " + _display(change.from_)))
        lines.append(_c(_GREEN, "    + " + _display(change.to)))
        lines.append("")

    if result.status != "PASSED":
        lines.append(
            _c(_DIM, "  Regenerate with: AGENTSNAP_UPDATE=1 <test command>")
        )

    return "\n".join(lines)


def _display(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(v, str) for v in value):
            return "[" + ", ".join(json.dumps(v) for v in value) + "]"
        try:
            return json.dumps(value, default=str)
        except Exception:
            return str(value)
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)
