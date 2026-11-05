# US-0077: Record, server and bind address arguments refused

> Spec: SPEC-0013 (sdlc/specs/SPEC-0013-http-request-hardening/)
> Nature: BUG
> Priority: P2
> Depends on: US-0076
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Finish the path class on the surfaces the deck services do not cover: the record tools and commands
(`requests`, `request-done`, `request-skip`, `review`, `list_requests`, `complete_request`, `write_review`), the
`render` tool, the server tools (`start_server`, `open_file`, `layout_arch_diagram`) and the commands `serve` and
`arch-layout`; and refuse a bind address that cannot be encoded (`serve --host $'a\xff'` prints
`TypeError: encoding of hostname failed` with a traceback today, E36). Every surface then answers one line, and
the span of a refused call is still written.

## Requirements covered

- SPEC-0013/BR-018 (partial: record tools and commands, `render` tool, server tools, `serve`, `arch-layout`; and the all surface checks BT-037, BT-047): IF a path argument of an agent tool or of a command (`file`, `output`, the target of `new_file` and `new`, the output of `export`) holds text that cannot be encoded THEN THE agent tool SHALL raise a tool error with message `File name cannot be encoded`, and THE command SHALL print `error: File name cannot be encoded` on standard error with exit status 1, both creating, changing and recording nothing and printing no traceback.
- SPEC-0013/BR-019 (partial: the span of a call refused for its path is kept): The agent tools, the commands and the editor server SHALL NOT change their answer, drop a span, or write a traceback to standard error or to a log, because a span attribute holds text that cannot be encoded.
- SPEC-0013/BR-021: IF the bind address given by the `--host` option of `serve` or of `new --serve`, or by `HTMLEDITOR_HOST`, holds text that cannot be encoded THEN THE command SHALL print `Error: Bind address cannot be encoded` on standard error with exit status 1, and THE agent tool `start_server` SHALL raise a tool error with message `Bind address cannot be encoded`, all starting no server, opening no browser and printing no traceback.

Per command answers (spec BR-018 table):

| Commands | Standard error | Exit status |
|---|---|---|
| `new`, `outline`, `render`, `get-slide`, `lint`, `patch`, `history`, `restore`, `export` | `error: File name cannot be encoded` | 1 |
| `requests`, `request-done`, `request-skip`, `review` | `error: File name cannot be encoded` | 1 |
| `serve`, `arch-layout` (their `FILE` must exist) | `Error: File name cannot be encoded` when the name exists; otherwise the existing usage answer `Error: Invalid value for 'FILE': ...` | 1 when the name exists; 2 otherwise (existing usage status) |

Business rules (spec): an undecodable byte of an argument, of `--host` or of `HTMLEDITOR_HOST` arrives as U+DC80
to U+DCFF and is refused the same way. The messages name no path and no address. `new --serve` has already
created its file when it reaches the bind: the file stays.

## Independent Test

`make test ARGS='-k unencodable_surfaces'`: `mcp-htmleditor serve deck.html --no-browser --host` with the byte
argument `a\xff` (subprocess, 10 second timeout) exits 1 with standard error ending in the line
`Error: Bind address cannot be encoded` and no `Traceback`, and no port of 7840 to 7849 accepts a connection
(red today: `TypeError` traceback).

## Design excerpt

### Decisions
- DEC-009 (SPEC-0013, the part this story implements): "`request_service.require_file` raises `RequestError("invalid", UNENCODABLE_FILE_NAME)`; the tools `start_server`, `open_file`, `layout_arch_diagram` check before resolving and raise `ToolError`; the commands `serve` and `arch-layout` raise `click.ClickException(UNENCODABLE_FILE_NAME)` first. Tools whose span attribute is `str(Path(file).resolve())` compute it with a private `_span_path(file)` that returns `file` unchanged when it is not encodable (resolving would raise `UnicodeEncodeError`)."
- DEC-010 (SPEC-0013): "The bind address is checked before any port probe, state save or bind: in `cli._serve_file` (it serves `serve` and `new --serve`) raising `click.ClickException(UNENCODABLE_BIND_ADDRESS)`, and in the tool `start_server` on `default_host()` raising `ToolError(UNENCODABLE_BIND_ADDRESS)`. `start_http_server` is not changed." `start_http_server` saves the state and probes ports before the bind (`http_server.py:950` to `:955`), and `_serve_file` catches only `OSError` and `RuntimeError`.
- DEC-016 (SPEC-0013): trace assertions run in a subprocess with its own tracer (`tests/trace_support.py`, US-0075: `run_traced_tool(tmp_path, tool, arguments, env=...) -> TracedRun(ok, data, stdout, stderr, trace_lines)`).

### Contracts
```python
# src/mcp_htmleditor/request_service.py
def require_file(file: str) -> Path:   # first: not is_utf8_encodable(file) -> RequestError("invalid", UNENCODABLE_FILE_NAME)

# src/mcp_htmleditor/mcp_server.py
def _span_path(file: str) -> str:      # str(Path(file).resolve()) when encodable, else file unchanged
# start_server: file check, then bind address check on default_host(), both before Path(file).resolve() and start_http_server
# open_file, layout_arch_diagram: file check first -> ToolError(UNENCODABLE_FILE_NAME)
# list_requests, complete_request, write_review, render, start_server, open_file, layout_arch_diagram: span "file.path" via _span_path

# src/mcp_htmleditor/cli.py
# serve_cmd, arch_layout_cmd: first statement, not is_utf8_encodable(file) -> click.ClickException(UNENCODABLE_FILE_NAME)
# _serve_file: first statement, not is_utf8_encodable(host) -> click.ClickException(UNENCODABLE_BIND_ADDRESS)
```
Messages from `src/mcp_htmleditor/textcheck.py` (US-0073). The request commands already print
`error: <RequestError.message>` with exit 1 (`cli.py` `_request_fail`), the request tools `ToolError(exc.message)`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/request_service.py` | modify: `require_file` |
| `src/mcp_htmleditor/mcp_server.py` | modify: `_span_path`, checks in `start_server`, `open_file`, `layout_arch_diagram`, bind check in `start_server`, span paths of the seven tools |
| `src/mcp_htmleditor/cli.py` | modify: `serve_cmd`, `arch_layout_cmd`, `_serve_file` |
| `tests/test_unencodable_surfaces.py` | create |

### Existing patterns
- `src/mcp_htmleditor/request_service.py:235` `require_file`; `src/mcp_htmleditor/mcp_server.py:47` `start_server`, `:122` `open_file`, `:177` `layout_arch_diagram`, `:439` `list_requests`, `:464` `complete_request`, `:493` `write_review`, `:521` `render`; `src/mcp_htmleditor/cli.py:181` `serve_cmd`, `:198` `_serve_file`, `:261` arch-layout command.
- `tests/deck_support.py:252` `call_tool`; byte arguments and environment values through `subprocess.run([sys.executable, "-m", "mcp_htmleditor", ...], env=..., timeout=10)` with `bytes` items (POSIX).
- `tests/conftest.py` `reset_settings` (autouse) so a `monkeypatch.setenv("HTMLEDITOR_HOST", "a\udcff")` is read by the in process `start_server`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Conventions: agent tool tests set `HTMLEDITOR_STATE_DIR`, the log and cache folders to `tmp_path`; `deck.html` is
a copy of the carbon bootstrap in `tmp_path`. Location `tests/test_unencodable_surfaces.py`.

### SPEC-0013/BT-037: Every path argument refuses an unencodable name
- Level exploit; Driver: agent tools (in process client, and the subprocess of `tests/trace_support.py` for the span clause); CLI subprocess with raw byte arguments. Red before because: the tools raise `UnicodeEncodeError`; `export` prints an `OSError` traceback.
- When, parametrized: `export(file="<deck.html>", format="pptx", output="<tmp_path>/o\ud800.pptx")`; `new_file(template="carbon", file="<tmp_path>/n\ud800.html")`; `patch(file="<tmp_path>/x\ud800.html", ops=[])`; `get_slide(file="<tmp_path>/x\ud800.html", id="slide-0")`; `write_review(file="<tmp_path>/x\ud800.html", suggestions=[])`; `complete_request(file="<tmp_path>/x\ud800.html", id="R-0001", status="skipped")`; `render(file="<tmp_path>/x\ud800.html")`; and the commands `mcp-htmleditor export pptx deck.html` with the byte argument `o\xff.pptx`, `mcp-htmleditor new carbon` with `n\xff.html`, `mcp-htmleditor request-skip` with `x\xff.html` then `R-0001`, `mcp-htmleditor render` with `x\xff.html`, `mcp-htmleditor outline` with `x\xff.html`
- Then each tool raises a tool error `File name cannot be encoded`; each command prints exactly `error: File name cannot be encoded` on standard error, exit status 1 (`render` included, not 2), no `Traceback`, no `Logging error`
- And `os.listdir(tmp_path)` and `deck.html` are unchanged, and the state folder holds no new file
- And, with the local trace file under `tmp_path`, every tool case whose `file` is the unencodable name adds one line, read as strict UTF-8, for the span `mcp.<tool name>` whose `file.path` attribute raw text contains the six characters `\ud800` (BR-019: the span is kept although `file.path` cannot be encoded)

### SPEC-0013/BT-041: A bind address that cannot be encoded is refused
- Level exploit; Driver: CLI subprocess with a raw byte argument or environment value, each run with a 10 second timeout and `--no-browser`; agent tool `start_server` in process with `HTMLEDITOR_HOST` set to `a\udcff`. Red before because: each prints `TypeError: encoding of hostname failed` with a traceback.
- When `mcp-htmleditor serve deck.html --no-browser --host` with the byte argument `a\xff`; `mcp-htmleditor serve deck.html --no-browser` with `HTMLEDITOR_HOST` holding the bytes `a\xff`; `mcp-htmleditor new carbon <tmp_path>/n.html --serve --no-browser --host` with `a\xff`; `start_server(file="<deck.html>")`
- Then each command exits within the timeout with status 1 and its standard error ends with the line `Error: Bind address cannot be encoded` and holds no `Traceback`; the tool raises a tool error `Bind address cannot be encoded`
- And `get_status()` reports `running` false, no port of 7840 to 7849 accepts a connection, `deck.html` is unchanged, and `<tmp_path>/n.html` exists (created before the bind, BR-021)

### SPEC-0013/BT-047: Valid non ASCII file names still work on every surface
- Protects BR-018, BR-017, SPEC-0007, SPEC-0010. Driver: agent tools in process client, with names passed as Python strings decoded from JSON that writes the emoji as the valid pair `\ud83d\ude00`; CLI with the names as UTF-8 bytes.
- Given `N` is `Présentation été 😀.html`, a copy of `deck.html` under `tmp_path`, and `O` is `sortie été 😀.pptx`
- When, in turn: `new_file(template="carbon", file="<tmp_path>/n é😀.html")`; `get_slide(file="<tmp_path>/N", id="slide-0")`; `patch(file="<tmp_path>/N", ops=[{"op":"set_text","id":"slide-0","selector":"h1","text":"T"}])`; `write_review(file="<tmp_path>/N", suggestions=[{"id":"a","slide":null,"title":"t","why":"w","change":"c"}])`; `export(file="<tmp_path>/N", format="pptx", output="<tmp_path>/O")`; `render(file="<tmp_path>/N")`; and the commands `mcp-htmleditor outline <tmp_path>/N`, `mcp-htmleditor history <tmp_path>/N`, `mcp-htmleditor review <tmp_path>/N`, `mcp-htmleditor render <tmp_path>/N`
- Then every call succeeds with its usual answer: `n é😀.html` and `O` exist, the title of `N` is `T`, `history` lists one version, `review` lists suggestion `a`, the render picture is named `Présentation été 😀-slide-0.png`, and `outline` prints JSON whose `file` equals the path given
- And no output holds `File name cannot be encoded` or `Traceback`
- (`render` needs the render extra and Chromium: guard those two calls exactly as `tests/test_render_picture.py` does.)

### Story level checks (part of this story's own tests, not spec ids)
- `serve` and `arch-layout` on an existing file whose name is the bytes `x\xff.html` (created with `os.open(os.fsencode(...))` where the file system allows it; skip on `EILSEQ`, as macOS refuses such names) print `Error: File name cannot be encoded`, exit 1; on a missing such name, the existing usage answer `Error: Invalid value for 'FILE': ...`, exit 2.
- `open_file(file="<tmp_path>/x\ud800.html")`, `layout_arch_diagram(file="<tmp_path>/x\ud800.html")`, `list_requests(file=...)`, `start_server(file="<tmp_path>/x\ud800.html")` raise `File name cannot be encoded`; `requests`, `request-done`, `review` with the byte name print `error: File name cannot be encoded`, exit 1.

## Constraints

- Files not to touch: `src/mcp_htmleditor/http_server.py` (`start_http_server` unchanged, DEC-010), `src/mcp_htmleditor/deck/*`, `src/mcp_htmleditor/history.py`, `src/mcp_htmleditor/textcheck.py`, `src/mcp_htmleditor/tracing.py`.
- Dependencies not to add: none.
- Patterns to avoid: a `Settings` validator for the host (every command would fail); catching `TypeError` around the bind; resolving a path before checking it; naming the path or the address in a message.
- Scope boundary: this story completes BR-018 and BR-021; nothing of the HTTP handler.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_requests_cli.py`, `tests/test_requests_tools.py`, `tests/test_review_write.py`, `tests/test_render_tool.py`, `tests/test_port_range.py`, `tests/test_deck_tools_mcp.py`, US-0076 tests pass unmodified; `mcp-htmleditor skill-audit` stays green.
- [ ] Docs updated: none in this story.
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none (no tool is added or renamed).
- [ ] One commit `US-0077: Record, server and bind address arguments refused`, body `Spec: SPEC-0013` and BR-018, BR-019, BR-021.
