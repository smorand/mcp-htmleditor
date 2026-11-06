# US-0081: Bounded stdio reads in tests

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P1
> Depends on: US-0080
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Three tests read an `mcp-htmleditor mcp` child's output with an unbounded `readline()` and kill the child only
after it (E15): a silent child blocks the run forever. This story moves the three copies into one shared stdio
session whose every line read is bounded by 30 seconds; a silent child fails its test with
`the server did not answer within 30 s` and is killed and reaped. US-0082 reuses the session for the lifecycle tests.

## Requirements covered

- SPEC-0014/BR-014: IF a child process started by a test writes no complete line on its standard output within 30 seconds of being waited for THEN the test SHALL fail with the message `the server did not answer within 30 s`, and the child SHALL be killed and reaped.

Business rules (spec): applies to the three stdio helpers of E15, and to any test reading a child's output line by line.

## Independent Test

`make test ARGS='-k stdio_support'` (part of `make check`): with `stdio_support.LINE_TIMEOUT_SECONDS`
monkeypatched to 1.0, `run_session` on the silent child `python -c "import time; time.sleep(3600)"` fails within
3 seconds with `the server did not answer within 1 s`, and the child's `poll()` is not `None` afterwards (red
before: the module does not exist; with today's inline loop the read blocks until the per test limit of US-0080).

## Design excerpt

### Decisions
- DEC-010 (SPEC-0014): "`tests/stdio_support.py` holds `StdioSession` and `run_session`; a daemon reader thread pushes each stdout line into a `queue.Queue`, `read_message` waits `queue.get(timeout=...)` with `stdio_support.LINE_TIMEOUT_SECONDS` read at call time; on timeout it kills the child, waits for it, and calls `pytest.fail(silence_message())`. The three call sites (E15) and the new lifecycle stdio tests use it; no `readline()` on a child's stdout remains in a test." A text mode pipe buffers ahead, so `select` on the descriptor can miss a line already buffered.
- DEC-008 (SPEC-0014): child runner tests load the project hooks with `-p tests.conftest`, cwd at the repository root and `-c pyproject.toml`.
- DEC-009 (SPEC-0014): BT-003 and BT-017 (literal 30 s) carry `@pytest.mark.slow`; the default run proves the mechanism with `stdio_support.LINE_TIMEOUT_SECONDS` monkeypatched to 1.0.

### Contracts
```python
# tests/stdio_support.py (new)
LINE_TIMEOUT_SECONDS: float = 30.0
SILENT_CHILD = [sys.executable, "-c", "import time; time.sleep(3600)"]


def mcp_command() -> list[str]: ...  # [sys.executable, "-m", "mcp_htmleditor", "mcp"]
def silence_message() -> str: ...  # f"the server did not answer within {LINE_TIMEOUT_SECONDS:g} s"


class StdioSession:  # context manager; __exit__ kills the child and wait(timeout=10)
    def __init__(self, command: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> None:
        ...
        # Popen(stdin=PIPE, stdout=PIPE, stderr=DEVNULL, text=True); env None means os.environ

    def send(self, message: dict[str, Any]) -> None: ...  # json.dumps + "\n", flush
    def read_message(self) -> dict[str, Any]:
        ...  # one bounded line, json.loads
        # empty line (stdout closed): assert fails with "the server closed stdout before answering" (today's text)
        # no line within the bound: kill, wait, pytest.fail(silence_message())

    def initialize(self) -> None: ...  # initialize id 1 (protocolVersion "2024-11-05"), notifications/initialized
    def call_tool(
        self, request_id: int, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...  # reads until the id, returns "result"
    @property
    def messages(self) -> list[dict[str, Any]]: ...


def run_session(
    requests: Sequence[dict[str, Any]],
    wanted_ids: set[int],
    *,
    command: Sequence[str] | None = None,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    ...
    # sends every request at once (as the three tests do today), reads until every wanted id was seen
```

### Paths
| Path | Action |
|---|---|
| `tests/stdio_support.py` | create |
| `tests/test_stdio_support.py` | create: BT-003, BT-017, counterparts, source check |
| `tests/test_render_tool.py` | modify: `_stdio_call` uses `run_session` (`:59` to `:95`) |
| `tests/test_deck_tools_mcp.py` | modify: `test_mcp_process_writes_only_protocol_lines_on_stdout` uses `run_session` (`:120` to `:150`) |
| `tests/test_deck_tools_surface.py` | modify: `test_the_new_tools_write_only_protocol_lines_on_stdout` uses `run_session` (`:225` to `:250`) |

### Existing patterns
- The three loops to replace: `tests/test_render_tool.py:87`, `tests/test_deck_tools_mcp.py:143`, `tests/test_deck_tools_surface.py:243` (same shape: write all requests, read until ids 1 and 2, `json.loads` each line so a stray text line fails, kill in `finally`). Keep `TMPDIR` in the env of the render tool call.
- Child runner command: as US-0080 (`tests/test_suite_time_limit.py` helper): `[sys.executable, "-m", "pytest", "-c", REPO/"pyproject.toml", "--rootdir", REPO, "-p", "tests.conftest", "-p", "no:cacheprovider", file]`, `cwd=REPO`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_stdio_support.py`.

### SPEC-0014/BT-003: A silent stdio server fails its test, the run ends
- Level / Driver / Location: functional e2e, `slow`; test runner as a child process on a file under `tmp_path`, with the project's test configuration; `tests/test_stdio_support.py`
- Red before the fix because: `readline()` has no bound and no per test limit exists (E15, E16); today the child run never ends.
- Given that file holds `test_silent`, which calls `tests.stdio_support.run_session` (the helper `tests/test_render_tool.py` now uses) with `command=SILENT_CHILD`, and `test_ok`, which asserts `True`
- When the runner is started (no `-o timeout`, real values)
- Then it exits with status 1 within 45 seconds, its output contains `test_silent` and `the server did not answer within 30 s`, and `1 passed`
- And no `python -c "import time; time.sleep(3600)"` process remains (read with `ps -axo command`, filtered on that exact text)
- This test carries `@pytest.mark.slow` (DEC-009).

### SPEC-0014/BT-017: Every stdio helper is bounded
- Level / Driver / Location: functional e2e, `slow`; direct call; `tests/test_stdio_support.py`
- Given `run_session` and `StdioSession.read_message`, each fed by `SILENT_CHILD`
- Then each fails within 35 seconds with `the server did not answer within 30 s` (`pytest.fail` raises `Failed`, caught with `pytest.raises(pytest.fail.Exception)`), and the child's `poll()` is not `None`
- And a source check (default run): `tests/test_render_tool.py`, `tests/test_deck_tools_mcp.py` and `tests/test_deck_tools_surface.py` contain `stdio_support` and no `.readline()`
- The two timing cases carry `@pytest.mark.slow` (DEC-009); the source check does not.

### Default run counterparts (support tests of this story, not spec ids)
- `test_silent_child_short_bound`: `monkeypatch.setattr(stdio_support, "LINE_TIMEOUT_SECONDS", 1.0)`; `run_session` on `SILENT_CHILD` fails within 3 seconds with `the server did not answer within 1 s`; the child is reaped.
- `test_closed_stdout_keeps_its_message`: a child `python -c "pass"` gives `the server closed stdout before answering`.
- `test_a_real_session_answers`: `StdioSession(mcp_command(), cwd=REPO)` then `initialize()` and `call_tool(2, "list_templates", {})` returns a result without `isError`.

## Constraints

- Files not to touch: product code under `src/`; `pyproject.toml` (the limit is US-0080).
- Dependencies not to add: none.
- Patterns to avoid: `select` or `selectors` on the text pipe; a second copy of the loop in any test; reading `LINE_TIMEOUT_SECONDS` with `from tests.stdio_support import LINE_TIMEOUT_SECONDS` (the monkeypatch seam needs the module attribute at call time).
- Scope boundary: the lifecycle stdio tests (BT-001, BT-013, BT-020, BT-021) are US-0082.

## Definition of done

- [ ] RED evidence recorded for every new test before the production change.
- [ ] Every acceptance test above green (`make check`; BT-003 and BT-017 timing cases with `make test ARGS='-m slow -k stdio_support'`); main stays green after the squash.
- [ ] Non regression: `test_e2e_005_tool_call_over_stdio`, `test_mcp_process_writes_only_protocol_lines_on_stdout`, `test_the_new_tools_write_only_protocol_lines_on_stdout` pass with their assertions unchanged.
- [ ] Docs updated: `.agent_docs/testing.md` (files table: `stdio_support.py`, `test_stdio_support.py`; the 30 s bound and its seam).
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0081: Bounded stdio reads in tests`, body `Spec: SPEC-0014` and BR-014.
