# US-0083: Port range tests independent of the machine

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective

`tests/test_port_range.py` binds every port of 7839 to 7849 itself and treats a refused bind as an error, so
`make check` is red on a developer machine with an editor open (BUG-004). This story makes a port held by another
process count as taken, keeps every assertion, and proves the verdict with listeners held by a separate process.

## Requirements covered

- SPEC-0014/BR-015: `tests/test_port_range.py` SHALL give the same verdict whatever other process listens, with or without `SO_REUSEADDR`, on any of the ports 7839 to 7849 of any local interface.
- SPEC-0014/BR-016: WHEN every port 7839 to 7849 of `127.0.0.1` is unavailable, whether held by the test or by another process THE test SHALL assert that `find_free_port("127.0.0.1", 7839)` raises `RuntimeError` with the message `No free port available (tried 7839 and 7840-7849): 10 presentations already running? Stop one or pass an explicit --port.`

Business rules (spec): a port held by another process counts as taken; the tests never skip because of it.

## Independent Test

`make test ARGS='-k port_range'` (part of `make check`): with a separate process listening without
`SO_REUSEADDR` on `127.0.0.1:7840` and `127.0.0.1:7842`, a child run of `tests/test_port_range.py` reports
`4 passed` (red today: `OSError: [Errno 48] Address already in use` at `tests/test_port_range.py:25` and `:55`).

## Design excerpt

### Decisions
- DEC-015 (SPEC-0014): "`tests/test_port_range.py`: the whole range test binds each port 7839 to 7849 of `127.0.0.1` without `SO_REUSEADDR`, counts a refused bind as taken, and asserts the exact BR-016 message; the fallback test and the two presentations test monkeypatch the module constants `mcp_htmleditor.http_server.PORT_RANGE_START` and `PORT_RANGE_END` to a block of 10 consecutive ports found free at run time in 30000 to 32000 (preferred port just below the block), keeping their assertions; the preferred port test is unchanged. The foreign holder tests BT-004 and BT-018 live in `tests/test_port_range_foreign.py` (a holder child binds without `SO_REUSEADDR`, a port it cannot bind is already held, which serves the same purpose) and run `tests/test_port_range.py` in a child runner." The spec's section 4.4 lists the two presentations test as Kept; with the whole range held (BT-018) it cannot pass, so BR-015 governs (non blocking note in `design-issues.md`).
- Child runner (pattern of DEC-008, SPEC-0014): `[sys.executable, "-m", "pytest", "-c", REPO/"pyproject.toml", "--rootdir", REPO, "-p", "no:cacheprovider", "tests/test_port_range.py"]`, `cwd=REPO`, `subprocess.run(..., timeout=60)`; no `-p tests.conftest` needed (no `slow` test involved).

### Contracts
`find_free_port(host, preferred)` (`src/mcp_htmleditor/http_server.py:978`) reads `PORT_RANGE_START` and
`PORT_RANGE_END` from its module globals at call time, so `monkeypatch.setattr(http_server, "PORT_RANGE_START", base)`
redirects it. Message (exact, `:1003` to `:1006`):
`No free port available (tried 7839 and 7840-7849): 10 presentations already running? Stop one or pass an explicit --port.`

Holder child (inline string in `tests/test_port_range_foreign.py`), started with `subprocess.Popen([sys.executable,
"-c", HOLDER, *ports], stdin=PIPE, stdout=PIPE, text=True)`: for each port, a socket without `SO_REUSEADDR`
`bind(("127.0.0.1", port))` and `listen(1)`, an `OSError` skipped (already held by someone else); prints `ready`;
blocks on `sys.stdin.read()`; the test closes stdin and waits for it at teardown (`wait(timeout=10)`, then
`kill`). The `ready` line is read through a reader thread and `queue.get(timeout=10)`, never a bare
`readline()` (BR-014 spirit; the guard of US-0081 checks only the three stdio files).

### Paths
| Path | Action |
|---|---|
| `tests/test_port_range.py` | modify: `test_falls_back_into_the_range_when_preferred_is_taken`, `test_two_presentations_get_two_different_ports`, `test_raises_a_clear_error_when_the_whole_range_is_taken` |
| `tests/test_port_range_foreign.py` | create: BT-004, BT-018 |

### Existing patterns
- Current tests: `tests/test_port_range.py:21` to `:61`; `_port_is_free` at `src/mcp_htmleditor/http_server.py:967` (binds with `SO_REUSEADDR`, refused means taken).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0014/BT-004: Port range tests with an editor running
- Level / Driver / Location: functional e2e; child runner on `tests/test_port_range.py` with listeners held by another process; `tests/test_port_range_foreign.py`
- Red before the fix because: the test binds every port itself and treats `Errno 48` as an error (E18).
- Given a separate process listens without `SO_REUSEADDR` on `127.0.0.1:7840` and `127.0.0.1:7842`
- When `tests/test_port_range.py` runs
- Then `4 passed`, and `test_raises_a_clear_error_when_the_whole_range_is_taken` asserted the exact BR-016 message (it uses `pytest.raises(RuntimeError)` and compares `str(excinfo.value)` for equality with the message above)

### SPEC-0014/BT-018: Whole range held by other processes
- Level / Driver / Location: functional e2e; same driver; `tests/test_port_range_foreign.py`
- Given a separate process holds `127.0.0.1` ports 7839 to 7849, without `SO_REUSEADDR`
- When `tests/test_port_range.py` runs
- Then `4 passed`

### Default run checks inside `tests/test_port_range.py` (assertions unchanged)
- `test_returns_the_preferred_port_when_free`: unchanged.
- `test_falls_back_into_the_range_when_preferred_is_taken`: on the free block, holding `base` (the patched `PORT_RANGE_START`): result `!= base` and `base <= result <= base + 9`.
- `test_two_presentations_get_two_different_ports`: on the free block: `port_b != port_a`, both inside the block.
- `test_raises_a_clear_error_when_the_whole_range_is_taken`: real 7839 to 7849, refused bind counted as taken, exact message.

## Constraints

- Files not to touch: `src/mcp_htmleditor/http_server.py`, `src/mcp_htmleditor/config.py` (no product change).
- Dependencies not to add: none.
- Patterns to avoid: `pytest.skip` when a port is held; faking `_port_is_free`; ports at or above 32768 for the free block.
- Scope boundary: nothing else.

## Definition of done

- [ ] RED evidence recorded for BT-004 and BT-018 before the test changes.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: SPEC-0001/E2E-044 (the whole range test) is green on any machine.
- [ ] Docs updated: `.agent_docs/testing.md` is updated by US-0088 (files table entry for `test_port_range_foreign.py`); nothing here.
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0083: Port range tests independent of the machine`, body `Spec: SPEC-0014` and BR-015, BR-016.
