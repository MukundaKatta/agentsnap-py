# agentsnap-py

[![PyPI](https://img.shields.io/pypi/v/agentsnap-py.svg)](https://pypi.org/project/agentsnap-py/)
[![Python](https://img.shields.io/pypi/pyversions/agentsnap-py.svg)](https://pypi.org/project/agentsnap-py/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Snapshot tests for AI agents.** Record an agent's tool-call trace, diff it against a baseline, fail CI on regressions. Zero runtime dependencies. Drops into pytest or any test runner.

Python port of [@mukundakatta/agentsnap](https://github.com/MukundaKatta/agentsnap).

## Install

```bash
pip install agentsnap-py
```

## Usage

```python
from agentsnap import record, trace_tool, expect_snapshot

search = trace_tool("search", lambda q: fetch_results(q))
summarize = trace_tool("summarize", lambda docs: llm_summarize(docs))

def agent(question):
    docs = search(question)
    return summarize(docs)

def test_research_agent_stays_on_rails():
    trace = record(lambda: agent("What is RLHF?"))
    expect_snapshot(trace, "tests/__snapshots__/research.snap.json")
```

First run writes the snapshot. Every run after that diffs against it. If the agent calls a different tool, calls them in a different order, or starts erroring, the test fails with a readable diff. Regenerate with `AGENTSNAP_UPDATE=1`.

## Async agents

```python
import asyncio
from agentsnap import arecord, trace_tool, expect_snapshot

asearch = trace_tool("search", async_fetch)

async def agent(q):
    return await asearch(q)

def test_async_agent():
    trace = asyncio.run(arecord(lambda: agent("hello")))
    expect_snapshot(trace, "tests/__snapshots__/async.snap.json")
```

## Diff statuses

| Status | When | Default action |
|---|---|---|
| `PASSED` | Bytewise match | green |
| `OUTPUT_DRIFT` | Tools + args identical, only output text or external result hashes differ | warn (non-failing) |
| `TOOLS_REORDERED` | Same tool names, different order | **fail** |
| `TOOLS_CHANGED` | Different tool names called, or different args | **fail** |
| `REGRESSION` | New error in the trace, or a tool that used to work now throws | **fail** |

Override per snapshot via `expect_snapshot(trace, path, fail_on=[...])`.

## API

### `record(fn, *, input=None, model=None, capture_results=False) -> Trace`

Run `fn` (sync) and capture every `trace_tool`-wrapped call inside it. Returns a JSON-serializable dict.

### `arecord(fn, ...) -> Trace`

Async variant for `async def` agents. Use with `asyncio.run(arecord(lambda: agent()))` or inside an async test.

### `trace_tool(name, fn) -> wrapped_fn`

Wraps a tool. Inside `record`, calls go into the trace; outside, transparent pass-through. Works with sync and async tools (returns the same shape).

### `expect_snapshot(trace, path, *, update=False, fail_on=None) -> dict`

Compare against an on-disk JSON baseline. Writes if missing, regenerates if `AGENTSNAP_UPDATE=1` (or `update=True`), otherwise diffs and raises `AgentSnapshotMismatch` on a failing status.

### `diff(baseline, current) -> DiffResult`

Low-level diff engine. Returns a `DiffResult(status=..., changes=[Change(...)])`.

### `format_diff(result, path=None) -> str`

Render a colored terminal block for the diff (used in the failure message).

## pytest plugin

Installing this package registers a pytest plugin that exposes the same API as fixtures:

```python
def test_my_agent(agentsnap_record, trace_tool, expect_snapshot):
    fn = trace_tool("hello", lambda: "world")
    trace = agentsnap_record(lambda: fn())
    expect_snapshot(trace, "tests/__snapshots__/hello.snap.json")
```

## API differences from the JS sibling

* Tracing uses `contextvars` (Python's `AsyncLocalStorage` equivalent) instead of `node:async_hooks`.
* Sync agents use `record()`; async agents use `arecord()` -- Python doesn't have JS's "async by default" assumption.
* `Trace` is a dict (not a class) so it serializes / inspects naturally.
* `Change.to_dict()` produces the JS-style `{"path": ..., "from": ..., "to": ...}` -- the dataclass uses `from_` because `from` is a Python keyword.
* Adds a pytest plugin (`pyproject.toml` ``pytest11`` entry point).

See the JS sibling's [README](https://github.com/MukundaKatta/agentsnap) for the full design notes.
