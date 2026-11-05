# US-0076: Deck services refuse unencodable path arguments

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P2
> Depends on: US-0075
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

A path argument holding an unpaired surrogate (a JSON `\ud800`, or an undecodable command line byte arriving as
`\udcXX`) reaches the operating system file name encoder or a strict UTF-8 key hash: `new_file` raises
`UnicodeEncodeError`, `export` prints an `OSError` traceback, `history`, `outline`, `lint` and `render` say
`File not found` (BUG-004). This story refuses such a path at each deck service entry point, so every command
and tool built on them answers `File name cannot be encoded` and creates or changes nothing.

## Requirements covered

- SPEC-0013/BR-018 (partial: the deck services, so the commands `new`, `outline`, `render`, `get-slide`, `lint`, `patch`, `history`, `restore`, `export` and the tools `outline`, `get_slide`, `patch`, `lint`, `new_file`, `export`, `history`, `restore`; the record tools and commands, `render` tool span, `start_server`, `open_file`, `layout_arch_diagram`, `serve` and `arch-layout` are US-0077): IF a path argument of an agent tool or of a command (`file`, `output`, the target of `new_file` and `new`, the output of `export`) holds text that cannot be encoded THEN THE agent tool SHALL raise a tool error with message `File name cannot be encoded`, and THE command SHALL print `error: File name cannot be encoded` on standard error with exit status 1, both creating, changing and recording nothing and printing no traceback.

Business rules (spec): `render` answers this refusal with status 1, not with its usage status 2 (status 2 stays
reserved to its option errors). On the command line an undecodable byte of an argument arrives as a code point
U+DC80 to U+DCFF and is refused the same way: file names that are not valid UTF-8 are not supported. The message
names no path. A valid non ASCII name (`/tmp/x😀.html`) is handled as any other path.

## Independent Test

`make test ARGS='-k unencodable_paths'`: `new_file(template="carbon", file="<tmp_path>/n\ud800.html")` raises the
tool error `File name cannot be encoded`, `os.listdir(tmp_path)` is unchanged and the captured log holds no
`Traceback` (red today: `UnicodeEncodeError`).

## Design excerpt

### Decisions
- DEC-009 (SPEC-0013, the part this story implements): "The path refusal sits at the service entry points that every command and tool reach: `deck.load_deck` and `deck.patch.check_target` raise `DeckError(UNENCODABLE_FILE_NAME)`; `deck.tools.create_file` (after its template check) and `deck.tools.export_file` (after its format check, for `file` then `output`) raise the same; `history.list_versions` and `history.restore_version` raise `HistoryError(UNENCODABLE_FILE_NAME)` (a `DeckError`)." One check per service gives the command and the tool the same text by construction; the existing order "unknown template, unknown format before the file" is kept. `render` gets status 1 because its refusal comes from `load_deck` inside `deck_command`, not from `RenderUsageError`.
- DEC-001 (SPEC-0013): predicate and message from `src/mcp_htmleditor/textcheck.py` (US-0073): `is_utf8_encodable(text) -> bool`, `UNENCODABLE_FILE_NAME = "File name cannot be encoded"`. Strict UTF-8 also refuses U+DC80 to U+DCFF, which `os.fsencode` would accept.

### Contracts
| Entry point | Where the check goes | Error |
|---|---|---|
| `deck.load_deck(file)` (`deck/__init__.py:42`) | first statement | `DeckError(UNENCODABLE_FILE_NAME)` |
| `deck.patch.check_target(file)` (`deck/patch.py:174`) | first statement | `DeckError(UNENCODABLE_FILE_NAME)` |
| `deck.tools.create_file(template, file)` (`deck/tools.py:41`) | after the unknown template check, before reading the template | `DeckError(UNENCODABLE_FILE_NAME)` |
| `deck.tools.export_file(file, fmt, output)` (`deck/tools.py:72`) | after the unknown format check: `file`, then `output` | `DeckError(UNENCODABLE_FILE_NAME)` |
| `history.list_versions(file)` (`history.py:149`), `history.restore_version(file, id)` (`history.py:157`) | first statement, before `Path(file).resolve()` | `HistoryError(UNENCODABLE_FILE_NAME)` |

Surfaces unchanged: commands under `deck_command` (`cli.py:34`) print `error: <message>` and exit 1; deck tools
raise `ToolError(str(exc))`. The tool spans of `outline`, `get_slide`, `patch`, `lint`, `new_file`, `export`,
`history`, `restore` already use the raw `file` text as `file.path` (`mcp_server.py:241` to `:414`), which US-0075
writes escaped.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/__init__.py` | modify: `load_deck` |
| `src/mcp_htmleditor/deck/patch.py` | modify: `check_target` |
| `src/mcp_htmleditor/deck/tools.py` | modify: `create_file`, `export_file` |
| `src/mcp_htmleditor/history.py` | modify: `list_versions`, `restore_version` |
| `tests/test_unencodable_paths.py` | create |

### Existing patterns
- `tests/deck_support.py:252` `call_tool`, `:244` `run_cli`; byte arguments need a subprocess: `subprocess.run([sys.executable, "-m", "mcp_htmleditor", "new", "carbon", os.fsencode(str(tmp_path)) + b"/n\xff.html"], env={"PYTHONPATH": "src", "HTMLEDITOR_STATE_DIR": ..., "HTMLEDITOR_LOG_DIR": ..., ...})`.
- `history.py` imports `fileio` lazily because `fileio` imports it; `textcheck` has no such cycle and can be imported at the top of every module above.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Conventions: agent tool tests set `HTMLEDITOR_STATE_DIR` and the log and cache folders to `tmp_path`;
`deck.html` is a copy of the carbon bootstrap. Location `tests/test_unencodable_paths.py`.

### SPEC-0013/BT-033: Creating a file under an unencodable name gets a tool error
- Reproduces BUG-004 (also validates BR-018). Level exploit; Driver: the agent tool `new_file` through the in process client. Red before because: the file name encoder raises `UnicodeEncodeError`.
- When `new_file(template="carbon", file="<tmp_path>/n\ud800.html")`
- Then a tool error is raised with message exactly `File name cannot be encoded`
- And the listing of `tmp_path` (read with `os.listdir`) is the same as before the call, and the captured log holds no `Traceback`

### Story level checks of BR-018 (part of this story's own tests, not spec ids)
- Parametrized over the commands `outline`, `lint`, `get-slide <file> slide-0`, `patch <file> --ops ops.json` (ops `[]`), `history`, `restore <file> 20260101T000000Z`, `render <file>` with the byte argument `x\xff.html` (subprocess), and `new carbon` with `n\xff.html`, `export pptx deck.html` with output `o\xff.pptx`: each prints exactly `error: File name cannot be encoded` on stderr, nothing on stdout, exit 1 (`render` included, not 2), no `Traceback`; `os.listdir(tmp_path)`, `deck.html` and the recursive listing of the state folder are unchanged.
- Parametrized over the tools `outline`, `get_slide` (`id="slide-0"`), `patch` (`ops=[]`), `lint`, `history`, `restore` (`id="x"`) with `file="<tmp_path>/x\ud800.html"`, and `export(file=<deck.html>, format="pptx", output="<tmp_path>/o\ud800.pptx")`: each raises `File name cannot be encoded`, nothing is created.
- Order kept: `new_file(template="nope", file="<tmp_path>/n\ud800.html")` answers `Unknown template "nope". ...`; `export(file=<deck.html>, format="nope", output="<tmp_path>/o\ud800.pptx")` answers `Unknown export format "nope". ...`.
- Valid non ASCII names still work through these services: `new_file(template="carbon", file="<tmp_path>/n é😀.html")` creates the file; `outline` and `history` on it answer as usual.

## Constraints

- Files not to touch: `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/cli.py`, `src/mcp_htmleditor/request_service.py`, `src/mcp_htmleditor/render/*`, `src/mcp_htmleditor/textcheck.py`.
- Dependencies not to add: none.
- Patterns to avoid: catching `UnicodeEncodeError` or `ValueError` around file operations; printing the path in the message; checking after `Path(file).resolve()` (resolving an unencodable path raises).
- Scope boundary: request tools and commands, `render` tool span, server tools, `serve`, `arch-layout`, bind address are US-0077; BT-037 and BT-047 (all surfaces) are asserted there.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_deck_tools*.py`, `tests/test_deck_outline.py`, `tests/test_deck_get_slide.py`, `tests/test_deck_lint*.py`, `tests/test_history_tools.py`, `tests/test_history_e2e.py`, `tests/test_render_picture.py::test_path_with_spaces_and_accents` pass unmodified.
- [ ] Docs updated: none in this story.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0076: Deck services refuse unencodable path arguments`, body `Spec: SPEC-0013` and BR-018.
