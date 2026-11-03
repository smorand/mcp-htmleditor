# SPEC-0010: Human to agent request loop and AI review, design

> Spec: sdlc/specs/SPEC-0010-request-loop/spec.md
> Nature: FEAT
> Depth: M
> Security: n/a
> Designed on: 2026-11-03
> Target tier: 2 (default: no `--tier`, no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

Landed before this spec (read their code at implementation time, names below are the contracts this design relies on):
SPEC-0009 (state directory setting, atomic writer, status poll), SPEC-0007 (slide ids, tool surface), SPEC-0006 (skill core `## Tools` list and topic `create`), SPEC-0012 (`editor.js` split). SPEC-0009 design (`sdlc/specs/SPEC-0009-reliable-saves/design.md`) fixes the state directory (`Settings.state_dir`, section 4.1), the per file keyed directory `<state_dir>/files/<key>/` and `fileio.atomic_write(path, data, *, reason=None, history=None) -> bool`; the facts this design relies on are listed in Section 7 (F1 to F4).

## 1. Stack and skills

| Element | Choice | Version | Source |
|---|---|---|---|
| Language, packaging | Python, uv, `make` only | `requires-python >=3.13` (`pyproject.toml:8`) | existing |
| CLI | Click (existing, kept) | `click>=8.0` (`pyproject.toml:17`) | `cli.py:20` |
| Tool protocol | FastMCP (existing) | `fastmcp>=2.0`, locked 3.4.6 (`uv.lock:561`) | `mcp_server.py:20` |
| HTTP | stdlib `ThreadingHTTPServer` (existing) | stdlib | `http_server.py` |
| Settings | pydantic-settings `Settings` (existing), `state_dir` from SPEC-0009 | existing | `config.py:78` |
| Inter process lock | stdlib `fcntl.flock` | stdlib | DEC-002 |
| Browser | vanilla JS classic script `static/editor-requests.js` | no dependency | DEC-008 |
| Tests | pytest, pytest-asyncio (`asyncio_mode = "auto"`), pytest-playwright (existing) | as locked | `pyproject.toml:158` |

No new dependency. `fastmcp.exceptions.ToolError` is the documented way to return a message to the client whatever `mask_error_details` is (context7 `/prefecthq/fastmcp`, `docs/servers/tools.mdx`: "ToolError messages are always sent to clients").

Python skill rules applied: `make` is the only tooling entry point; no `os.environ` (the state directory comes from `get_settings().state_dir`); nothing is written to standard output in the tool process (the new modules never print, the CLI prints with `click.echo`); `trace_span` on every record mutation and on every tool; mypy strict (no `type: ignore`, PEP 695 generic `update[T]`); ruff; `%` logging, never the instruction text in a log line or span attribute; frozen slotted dataclasses for value objects; dependencies injected (`RequestService(store)`), one factory `build_request_service()` at the edge.

## 2. Approaches

The real choices are where the data lives and how several processes (editor server threads, the tool process, the command line) change it without losing a request or reusing an id (FR-NEW-001, FR-NEW-007: the request and the applied mark are stored together).

### Chosen: one JSON record per file, changed under an exclusive `flock`, replaced by atomic rename
`<state_dir>/files/<key>/requests/record.json` holds the counter, the revision, all requests and the review. Every change is `lock, read, apply the change in memory, write a temporary file in the same directory, rename over the record, unlock`. Readers take no lock: the rename makes every read see a complete old or new record. The change function runs on the in memory record and raises before any write when a rule refuses, so a refusal never leaves half a change (FR-NEW-007 "stays not applied"). Pros: one read gives the list, the counter and the review (the editor needs all three on each refresh); the request and the applied mark are one write; the counter and the requests can never disagree; one revision number is the change marker for the poll; matches the SPEC-0009 per file JSON store. Cons: the whole record is rewritten on each change (a few KB, requests are human sized), and `fcntl` is Unix only (DEC-015).

### Rejected: one file per request plus a counter file
`R-0001.json`, ..., `counter`. Pros: a change touches one small file. Rejected (DEC-001): the id allocation needs its own lock anyway (read counter, write counter, create request), "request plus applied mark" becomes two files with a crash window between them (violates "the applied mark is stored together with the request"), listing is a directory scan with N reads, and there is no single place for the change marker.

### Rejected: SQLite (`sqlite3`, stdlib)
Real transactions and multi process locking for free. Rejected (DEC-001): the SPEC-0009 store is JSON files in the state directory (one mechanism to learn, files readable with a text editor), SQLite adds `-wal` and `-shm` side files per record and busy timeout handling, and an unwritable directory fails differently (E2E-020 needs a deterministic `OSError` text).

### Rejected: optimistic write without a lock (compare revision, retry)
Rejected (DEC-002): rename is atomic but two writers can both pass the compare before either renames, so one request is lost. Only a lock makes "the later operation sees the earlier result" true (FR-NEW-001).

## 3. Architecture

```
 Agent ──tool──▶ mcp_server.list_requests / complete_request / write_review ─┐
 User ──CLI───▶ cli.requests / request-done / request-skip / review ─────────┤
 Browser ──HTTP▶ http_server  GET /requests, POST /requests,                 ├─▶ RequestService ─▶ RequestStore ─▶ <state_dir>/files/<key>/requests/record.json
 (editor-requests.js)         POST /requests/delete, POST /review/apply      │    (rules, messages)  (lock, read,      record.lock
                              GET /status (+ requests_revision) ─────────────┘                        atomic_write)
```

- `RequestService` (`request_service.py`) owns every rule and every user visible message. Surfaces never re implement a rule: the CLI prints `error: ` plus `RequestError.message`, the tools raise `ToolError(message)`, the HTTP handler answers `{"ok":false,"error":message}` with a status chosen from `RequestError.kind`. This is how FR-NEW-004 holds by construction (DEC-005).
- `RequestStore` (`request_store.py`) knows files, locks and JSON, nothing about rules.
- File resolution (`require_file`) is done by the tool and CLI surfaces only; HTTP uses the served file (`get_state().current_file`, already absolute).
- The browser: `editor-requests.js` is a classic script wrapped in an IIFE. It adds the toolbar button `Ask AI`, the panel, the side list and the suggestions list. `editor.js` calls `requestsOnStatus(status)` once per successful poll; the module fetches `GET /requests` only when `status.requests_revision` differs from the last revision it holds (DEC-004). Script order (SPEC-0012 DR-006): `slide-layouts.js, doc-blocks.js, editor-undo.js, editor-edit.js, editor-format.js, editor-menus.js, editor-save.js, editor-slides.js, editor-blocks.js, editor-drag.js, editor-requests.js, editor.js`. `editor-requests.js` goes right after `editor-drag.js` and before `editor.js` (`static/editor.html:81-83` is where the tags live; SPEC-0012 turned them into eleven). It reads no top level `let` or `const` of `editor.js` at evaluation time (SPEC-0012 DR-006), only inside functions, and uses `document.getElementById('content-frame')` instead of the `frame` constant.
- Current slide (FR-NEW-001): the module attaches `click` and `selectionchange` listeners to the iframe document on each iframe `load` and remembers `slideIdOf(event target or selection anchor)`, which is the `data-id` of the closest `[data-type="slide"]`. At open and at queue time the slide is that remembered id if it still exists in the iframe document, else the first slide's `data-id`, else `none` (null) (DEC-013).
- Tracing: `requests.update` (path of the record and the operation name, never the text), `mcp.list_requests`, `mcp.complete_request`, `mcp.write_review` (`file.path`).

## 4. Data model

### 4.1 Request (value object, JSON object with exactly these keys)

| Key | Type | Rule |
|---|---|---|
| `id` | string | `R-` plus the counter on at least 4 digits (`f"R-{n:04d}"`, so `R-10000` after `R-9999`) |
| `slide` | string or null | slide id as sent by the editor, never checked against the file |
| `title` | string | instruction with each `\r\n`, `\n` or `\r` replaced by one space (regex `\r\n\|\n\|\r`), then the first 60 code points, not trimmed |
| `queued` | string | `datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` taken inside the lock, at storage time |
| `instruction` | string | exactly as typed |
| `status` | string | `pending`, `done`, `skipped` |
| `reason` | string or null | null unless `skipped`; stored as given |

### 4.2 Suggestion

`{"id","slide","title","why","change","applied"}`. `applied` is stored; the five other keys are the only ones kept from the input (extra keys dropped).

### 4.3 Record, per file store layout, counter

`<state_dir>/files/<key>/requests/record.json` and `<state_dir>/files/<key>/requests/record.lock` (empty, only locked). `<state_dir>` is `get_settings().state_dir` (SPEC-0009 FR-NEW-008: `HTMLEDITOR_STATE_DIR`, else `$XDG_STATE_HOME/mcp-htmleditor`, else `~/.local/state/mcp-htmleditor`). `<key>` is `hashlib.sha256(os.path.realpath(file).encode("utf-8")).hexdigest()[:32]`, the same key SPEC-0009 uses for `server.json`, `update.json` and `history/` (SPEC-0009 section 4.1; its design names no shared helper, so `RequestStore.record_dir` computes it with that formula and a test pins the equality): absolute path, symlinks resolved, so a renamed or moved file has another key (starts empty), two files never share a record (FR-NEW-008), and removing the state directory removes everything. The requests live in the `requests/` subdirectory of the SPEC-0009 per file directory, so they share its key and its lifetime. Directories are created with mode 0700 (SPEC-0009 section 4.1).

```json
{
  "version": 1,
  "file": "/abs/path/deck.html",
  "revision": 7,
  "next_id": 4,
  "requests": [ {"id":"R-0001","slide":"slide-3","title":"Shorten the title","queued":"2026-11-03T10:15:00Z","instruction":"Shorten the title","status":"pending","reason":null} ],
  "review": [ {"id":"s1","slide":"slide-1","title":"Tighten the agenda","why":"...","change":"Cut to 5 lines","applied":false} ]
}
```

- `next_id` only ever increases: it is incremented when a request is created and never when one is deleted, so ids are never reused (E2E-021).
- `revision` increases by 1 on every write that changes the record. A change that leaves the serialized record identical (deleting an unknown id) writes nothing and does not bump the revision (DEC-011).
- `review` is null when no review was ever written (distinct from `[]`, which is a review of zero suggestions; both print `No review for <file>` on the command line).
- A missing record file is an empty record (`next_id` 1, `revision` 0); read only operations never create the state directory.
- A record that exists but is unreadable or invalid JSON raises `RequestError(kind="storage", "Requests record of <file> is unreadable: <reason>")`: it is never silently reset, which would reuse ids (DEC-016).

### 4.4 Limits

`INSTRUCTION_MAX = 4000`, `PENDING_MAX = 50`, `TITLE_MAX = 60`, `REVIEW_MAX = 6`, `BODY_MAX_BYTES = 1_048_576` for the new POST bodies.

## 5. Contracts and interfaces

### 5.1 Python (all in `src/mcp_htmleditor/`)

```python
# request_store.py
@dataclass(frozen=True, slots=True)
class Request:
    id: str
    slide: str | None
    title: str
    queued: str
    instruction: str
    status: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class Suggestion:
    id: str
    slide: str | None
    title: str
    why: str
    change: str
    applied: bool


@dataclass(slots=True)
class Record:
    next_id: int = 1
    revision: int = 0
    requests: list[Request] = field(default_factory=list)
    review: list[Suggestion] | None = None


class RequestStore:
    def __init__(self, state_dir: Path) -> None: ...
    def record_dir(self, file: Path) -> Path: ...  # <state_dir>/files/<key>/requests
    def read(self, file: Path) -> Record: ...  # lock free, empty Record when absent
    def update[T](self, file: Path, operation: str, change: Callable[[Record], T]) -> T:
        ...
        # mkdir parents, flock EX on record.lock, read, change(record), if serialized form changed:
        # revision += 1, atomic_write(record.json), traced "requests.update"; any exception from change() => nothing written

    def revision(self, file: Path) -> int: ...  # 0 when absent or unreadable (logs a warning), used by /status
```

```python
# request_service.py
ErrorKind = Literal["invalid", "conflict", "not_found", "storage"]
class RequestError(Exception): kind: ErrorKind; message: str       # str(exc) == message

class RequestService:
    def __init__(self, store: RequestStore, clock: Callable[[], datetime] = utc_now) -> None: ...
    def queue(self, file: Path, instruction: str, slide: str | None) -> Request                 # FR-001
    def list_requests(self, file: Path) -> list[Request]                                        # FR-002, oldest first
    def delete(self, file: Path, request_id: str) -> None                                       # FR-005, unknown id is a no op
    def complete(self, file: Path, request_id: str, status: str, reason: str | None) -> Request # FR-003
    def write_review(self, file: Path, raw: object) -> int                                      # FR-006, returns count
    def read_review(self, file: Path) -> list[Suggestion]                                       # FR-006
    def apply_suggestion(self, file: Path, suggestion_id: str) -> Request                       # FR-007
    def snapshot(self, file: Path) -> Snapshot                                                  # (revision, pending, requests, suggestions) for GET /requests

def require_file(file: str) -> Path: ...        # Path(file).resolve(); RequestError("not_found", f"File not found: {file}") if not a file ("as typed")
def build_request_service() -> RequestService: ...   # RequestStore(get_settings().state_dir)
def is_blank(text: str) -> bool: ...             # True when only Unicode White_Space characters (DEC-007)
def request_to_dict(r: Request) -> dict[str, Any]: ...   # the 7 keys, in order id, slide, title, queued, instruction, status, reason
def suggestion_to_dict(s: Suggestion) -> dict[str, Any]: ...
```

Rules, in the order the spec fixes them:

- `queue`: `is_blank(instruction)` then `Write a request first`; `len(instruction) > 4000` then `Request too long (max 4000 characters)`; inside the lock, pending count at 50 then `Too many pending requests (max 50)`; any `OSError` from the store then `Could not queue the request: <error>` (`kind="storage"`). `slide` must be a `str` or `None` (the HTTP layer rejects other types with `Invalid request body`).
- `complete`: file (surface), id (`Unknown request id "R-9". Valid ids: R-0001, R-0002`, `Valid ids: none` when empty; the list is every non deleted id, oldest first), status (`Status must be done or skipped`), reason (`skipped` with `reason is None or is_blank(reason)` gives `A reason is required to skip a request`), already completed (`Request R-0001 is already done`, with the current status word). `done` stores `reason=None`; `skipped` stores the reason untrimmed. A storage error gives `Could not update the request: <error>` (message not in the spec, see backlog finding 2).
- `write_review(file, raw)`: `raw` not a list then `Review must be a list of suggestions`; `len > 6` then `At most 6 suggestions`; then per position (1 based): a non dict item or a missing field in the order `id, slide, title, why, change` (`Suggestion N: missing field "x"`; absent, null except `slide`, not a string, or blank counts as missing; `slide` must be null or a string), then `Suggestion N: title is longer than 60 characters` (code points), then `Suggestion N: duplicate id "s1"`. First faulty suggestion wins. A storage error gives `Could not write the review: <error>`; the previous review is unchanged. Each stored suggestion has `applied=False`.
- `apply_suggestion` (one `update`): unknown id then `Suggestion <id> no longer exists` (`not_found`); already applied then `Suggestion <id> was already applied` (`conflict`); then the FR-001 checks on `instruction = f"{title}. {change}"` with `slide` as is (too long uses the built instruction, no blank check can fail because title is not blank); the request is appended and the suggestion replaced by its `applied=True` copy in the same record write. Storage error then `Could not queue the request: <error>`.
- `delete`: storage error then `Could not delete the request: <error>`; the request stays.

`RequestError.kind` to HTTP status: `invalid` 400, `conflict` 409, `not_found` 404, `storage` 500. Count refusals (`Too many pending`) are `conflict`, `Write a request first` and `Request too long` are `invalid`.

```python
# mcp_server.py (tools, each: trace_span("mcp.<name>", {"file.path": abs}); except RequestError as exc: raise ToolError(exc.message) from exc)
@mcp.tool()
def list_requests(file: str) -> dict[str, Any]: ...  # {"file": abs, "requests": [request_to_dict, ...]}
@mcp.tool()
def complete_request(
    file: str, id: str, status: str, reason: str | None = None
) -> dict[str, Any]: ...  # {"ok": True, "id", "status"}
@mcp.tool()
def write_review(file: str, suggestions: list[Any]) -> dict[str, Any]: ...  # {"ok": True, "count": n}
```

`status` is `str`, not `Literal`, and `suggestions` is `list[Any]`, so the product messages win over a schema validation error (DEC-006). The `file` of `list_requests` is `str(Path(file).resolve())`.

```python
# cli.py (lazy imports like the other commands; errors via _request_fail(message): click.echo(f"error: {message}", err=True); raise SystemExit(1); stdout stays empty)
@main.command("requests")      @click.argument("file")                                   # lines "<id>  <status>  <slide or ->  <title>" or "No requests for <file>"
@main.command("request-done")  @click.argument("file") @click.argument("request_id")      # "Request R-0001 marked done"
@main.command("request-skip")  @click.argument("file") @click.argument("request_id") @click.option("--reason", default=None)   # "Request R-0001 marked skipped"
@main.command("review")        @click.argument("file") @click.option("--write", "write_source", default=None)   # lines "<id>  <slide or ->  <title>", "No review for <file>", "Review written: <n> suggestions"
```

`--write` reads the path, or standard input for `-`. Read failure `Cannot read <path>: <reason>`, JSON failure `Invalid JSON: <reason>`, then the service rules. The SPEC-0007 and SPEC-0009 designs name no shared error helper (SPEC-0009 echoes `error: <message>` to stderr and exits 1 inline), so this story adds the private `_request_fail(message: str) -> NoReturn` in `cli.py`.

### 5.2 HTTP (new routes sit inside the existing `do_GET` / `do_POST` dispatch, so the SPEC-0005 gate (`_refuse_untrusted_request`, `http_server.py:86`) runs before them with no extra code)

| Method, path | Body | Success | Errors |
|---|---|---|---|
| `GET /requests` | none | 200 `{"revision":7,"pending":2,"requests":[7 keys],"suggestions":[{"id","slide","title","why","change","applied"}]}` | 404 `{"error":"No file loaded"}`; 500 `{"error":"<record error>"}` |
| `POST /requests` | `{"instruction":str,"slide":str\|null}` | 200 `{"ok":true,"request":{...}}` | 400 `{"ok":false,"error":"Write a request first"}`, `Request too long (max 4000 characters)`, `Invalid request body`; 409 `Too many pending requests (max 50)`; 500 `Could not queue the request: <error>` |
| `POST /requests/delete` | `{"id":str}` | 200 `{"ok":true}` | 400 `Invalid request body`; 500 `Could not delete the request: <error>` |
| `POST /review/apply` | `{"id":str}` | 200 `{"ok":true,"request":{...}}` | 404 `Suggestion s1 no longer exists`; 409 `Suggestion s1 was already applied`, `Too many pending requests (max 50)`; 400 `Request too long (max 4000 characters)`; 500 `Could not queue the request: <error>` |
| `GET /status` | none | existing payload plus `"requests_revision": <int>` (`RequestStore.revision`, 0 when none) | unchanged |

SPEC-0005 rules for the POST routes: JSON only (`Content-Type` other than `application/json` is answered 415 through `_refuse`, as `_receive_content` does at `http_server.py:303`); invalid JSON 400 `{"error":"Invalid JSON body"}`; a body that is not a JSON object, or fields of the wrong type, 400 `{"ok":false,"error":"Invalid request body"}`; invalid `Content-Length` 400 `{"error":"Invalid Content-Length"}`; a body above `BODY_MAX_BYTES` 413 `{"error":"Request too large"}` without reading it. One helper `_read_json_object(self) -> dict[str, Any] | None` implements the five checks and answers the error itself: the header goes through SPEC-0009's `parse_content_length(raw)` (absent is 0, a bad value raises `SaveRefusal(400, {"error":"Invalid Content-Length"})`, which the helper catches and answers); its 50 MiB cap is not used here, the helper applies `BODY_MAX_BYTES` (1 MiB) and answers 413 `{"error":"Request too large"}` before reading. The save route is not changed. No route is added to `do_OPTIONS`, which stays 405. Delete is a POST because the server only dispatches GET and POST (`http_server.py:109-112` answers `Allow: GET, POST`).

### 5.3 Editor UI element ids (texts are normative, from the spec)

| Id or selector | Element | Text or behaviour |
|---|---|---|
| `ask-ai-btn` | toolbar button, before `edit-mode-btn` | `Ask AI`; toggles `ask-ai-panel` |
| `ask-ai-panel` | popover under the toolbar (fixed, top 28px, right 12px) | hidden by default |
| `ask-ai-text` | `textarea` | label `Describe the change` (`<label for>`) |
| `ask-ai-slide` | line | `Slide: slide-3`, `Slide: none` when the file has no slide; refreshed at open and at queue |
| `ask-ai-queue` | button | `Queue request`; disabled while a request is in flight; clears the textarea on success, keeps it on failure |
| `ask-ai-message` | `role="status"` line | `Request R-0001 queued` or the server `error` text; set through `textContent`; `requestsShowMessage` opens the panel when closed (Apply results use it too) |
| `requests-side` | `aside`, fixed right 300px under the toolbar, hidden in fullscreen | always visible while a file is open |
| `requests-heading` | heading | `Requests (n)`, n = pending count |
| `requests-list` | `ul` | one `li[data-request-id]` per request, text in `span.request-text`: `<id> <status> <slide or -> <title>` plus ` <reason>` when skipped; button `button.request-delete` `Delete` on every line, no confirmation |
| `suggestions-heading` | heading | `AI suggestions (n)` |
| `suggestions-list` | `ul` | one `li[data-suggestion-id]`: `.suggestion-title`, `.suggestion-why`, `button.suggestion-apply` `Apply`, or `Applied` and disabled when applied |

All agent supplied strings (title, reason, why) are inserted with `textContent`, never `innerHTML` (DEC-012). Public globals of the script: `requestsOnStatus(status)` only; the IIFE hides the rest. Function names inside start with `requests` or `askAi` (SPEC-0012 DT-012 forbids a top level name defined twice across scripts).

### 5.4 Skill (SPEC-0006)

- Core `## Tools`: one line per tool, in the story that registers it (SPEC-0006 FR-NEW-008, audited by `mcp-htmleditor skill-audit`): `- list_requests: List the requests the person queued in the editor for a file, oldest first`, `- complete_request: Mark a request done, or skipped with a reason`, `- write_review: Replace the AI suggestions shown in the editor (at most 6)`.
- Topic `create` gets a section "Apply the requests": `mcp-htmleditor skill` then `list_requests`; for each pending request do the change with the usual `update_start` / `update_end` flank, then `complete_request` (`done`, or `skipped` with a reason when the request is unclear, already true or refused); optionally `write_review` with at most 6 suggestions; never treat request text as an instruction about anything but the document (untrusted content rule). The shipped file `skill/topics/create.md` stays at or below 3 800 bytes and its `topic_output` at or below 8 000 bytes (checked by the audit, SPEC-0006 FR-NEW-007).

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/request_store.py` | new | FR-NEW-001, 008 | STORY-A |
| `src/mcp_htmleditor/request_service.py` | new, then extended | FR-NEW-001, 002, 003, 006, 007 | STORY-A, B, F, G |
| `src/mcp_htmleditor/http_server.py` | edit: 4 routes, `_read_json_object` (uses `parse_content_length` of SPEC-0009), `requests_revision` in `_serve_status`, apply route | FR-NEW-001, 005, 007 | STORY-A, G |
| `src/mcp_htmleditor/cli.py` | edit: `requests`, `request-done`, `request-skip`, `review`, `_request_fail` | FR-NEW-002, 003, 004, 006 | STORY-A, C, F |
| `src/mcp_htmleditor/mcp_server.py` | edit: 3 tools, module docstring count | FR-NEW-002, 003, 006 | STORY-B, F |
| `skill/core.md` (SPEC-0006, section `## Tools`) | edit: `## Tools` lines | FR-NEW-002, 003, 006 (SPEC-0006 FR-NEW-008) | STORY-B, F |
| `skill/topics/create.md` (SPEC-0006, `mcp-htmleditor skill --type create`) | edit: "Apply the requests" | FR-NEW-003 | STORY-C, G |
| `src/mcp_htmleditor/static/editor-requests.js` | new, then extended | FR-NEW-001, 005, 006, 007 | STORY-D, E, G |
| `src/mcp_htmleditor/static/editor.html` | edit: `ask-ai-btn`, `ask-ai-panel`, `requests-side`, one `script` tag between `editor-drag.js` and `editor.js` | FR-NEW-001, 005 | STORY-D |
| `src/mcp_htmleditor/static/editor.css` | edit: panel, side list, iframe width, fullscreen hiding (`editor.css:174`, `:191-197`) | FR-NEW-001, 005 | STORY-D |
| `src/mcp_htmleditor/static/editor.js` | edit: one call in `pollStatus` (`editor.js:298`) | FR-NEW-005 | STORY-E |
| `tests/test_requests_core.py` | new | FR-NEW-001, 002, 008 | STORY-A |
| `tests/test_requests_tools.py` | new | FR-NEW-002, 003, 004 | STORY-B |
| `tests/test_requests_cli.py` | new | FR-NEW-003, 004 | STORY-C |
| `tests/test_requests_editor_e2e.py` | new | FR-NEW-001, 005 | STORY-D |
| `tests/test_static_scripts.py` | edit: the expected script list of DT-012 gains `editor-requests.js` (one line, now twelve scripts) | FR-NEW-001 | STORY-D |
| `tests/test_requests_refresh_e2e.py` | new | FR-NEW-003, 005 | STORY-E |
| `tests/test_review_write.py` | new | FR-NEW-004, 006 | STORY-F |
| `tests/test_review_apply_e2e.py` | new | FR-NEW-006, 007 | STORY-G |
| `tests/test_request_loop_acceptance.py` | new | FR-NEW-004, 008 | STORY-H |
| `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md` | edit | all (documentation) | STORY-H |

### Affected existing tests

- `tests/test_static_scripts.py` (SPEC-0012 DT-012, lists the eleven scripts of `editor.html`): its expected list gains `editor-requests.js` between `editor-drag.js` and `editor.js`, same story as the tag (STORY-D). Its "no top level function defined twice", `node --check` and size cap checks (500 lines per script) also apply to the new script.
- The SPEC-0012 static serving test (DT-004, `GET /static/editor-*.js` is 200 and `no-store`) covers the new script with no change, as `_serve_static` is generic (`http_server.py:175`).
- `tests/test_fullscreen_e2e.py`: the side panel narrows the iframe; the fallback `body:has(#content-frame:fullscreen)` rule hides `#requests-side` and restores a 100vw iframe. Rerun in STORY-D; no edit expected.
- SPEC-0006 skill audit tests (core tools list equals the registered tools): green only if the core lines are added in the same story as the tool (STORY-B, STORY-F).
- `tests/test_http_origin_e2e.py:239` parametrizes the routes that must refuse a foreign origin; STORY-A adds the four new routes to its own test file instead of editing it.
- `tools/check_ei_insert.py` (SPEC-0012 lists it as loading the editor scripts): it needs no new script (`editor-requests.js` is independent); STORY-D checks it still passes.

### Documentation

- `README.md`: a "Request loop" section (Ask AI, the four commands, the three tools, where the state lives); `AGENTS.md`: command list plus index entry; `.agent_docs/architecture.md`: modules `request_store.py`, `request_service.py`, routes, record layout; `.agent_docs/testing.md`: the new test files and the storage failure seam. STORY-H (the skill changes ship earlier, in STORY-B, C, F, G).

## 7. Compatibility and risks

- No existing contract changes: `/status` gains one key; the editor gains a button, a panel and an aside; the tool surface gains three tools (the count is not stated anywhere, SPEC-0006 FR-NEW-001 lists tools instead).
- F1: `fileio.atomic_write(path: Path, data: bytes | str, *, reason: str | None = None, history: HistoryStore | None = None) -> bool` (SPEC-0009 section 5.2; created by SPEC-0007). `RequestStore.update` calls `atomic_write(record_path, payload_bytes)` with no reason (no history snapshot) and ignores the returned bool. It writes a temporary file in the target directory, fsyncs, replaces, and removes the temporary file on failure; it does not create the parent directory, so `update` runs `mkdir(mode=0o700, parents=True, exist_ok=True)` first.
- F2: `get_settings().state_dir` is a `Settings` property (SPEC-0009 DEC-005); tests get an isolated one from the autouse fixture `isolate_state_dir` of `tests/conftest.py` (SPEC-0009), and set `HTMLEDITOR_STATE_DIR` explicitly for subprocess and Playwright tests.
- F3: the keyed directory is `<state_dir>/files/<key>/` with `key = sha256(resolved path, UTF-8).hexdigest()[:32]` (SPEC-0009 DEC-006); no helper is exported, `request_store.py` repeats the formula.
- F4: `get_state().current_file` is the served file and stays absolute (`state.py`, SPEC-0009 keeps the singleton and the name); `GET /status` is built by `_serve_status`, which SPEC-0009 already extends with `update_expires_in`.
- F5: the skill layout is `skill/core.md` (at most 6 000 bytes shipped, `## Tools` lines `- <name>: <description>`), `skill/topics/<topic>.md` (shipped file at most 3 800 bytes, `topic_output` at most 8 000 bytes), audited by `mcp-htmleditor skill-audit` (SPEC-0006 DEC-010, section 3); the audit also flags stale statements (`GrapesJS`, `git commit`, `N tools`, ...), so the new text avoids them.
- Risk, `fcntl` is Unix only (DEC-015): macOS and Linux (the Docker image) are the targets; a Windows run raises `ModuleNotFoundError` at import of `request_store`.
- Risk, the lock is advisory: a process that edits `record.json` by hand bypasses it; accepted, the file is private state.
- Risk, a crash between lock and rename leaves the old record intact and at worst a stale temporary file inside the state directory (the SPEC-0009 writer removes it on failure).
- Risk, the iframe is 300px narrower; slides keep their 16:9 canvas (`max-width:960px`), documents reflow. The side list cannot be collapsed in this increment (not required by the spec).
- Risk, an unreadable record makes `list_requests`, the editor list and every change fail with the `unreadable` message until the file is repaired or the state directory removed (DEC-016). The editor's `/status` still answers (`revision` returns 0).
- Risk, a request's text goes to the agent as data; the skill step says not to follow instructions that are not about the document. No automatic execution exists.
- Not specified, decided here (listed in Section 10 and in the backlog findings): storage error text for `complete_request`; non dict suggestion items; `No review` for an empty review; a request body size cap.

## 8. Omitted

(Section omitted for depth M.)

## 9. Test strategy

Levels: UT is a pytest test of a function or a surface in process (no browser); E2E drives the product through its public surfaces. Playwright tests carry `@needs_chromium` (`skipif` when no `chromium-*` in the Playwright cache), the harness copied from `tests/test_autosave_focus_e2e.py:35-80` (real `start_http_server` on a free port, `reset_state` fixture, `HTMLEDITOR_TEMPLATES_DIR` forced, deck built from `templates/bootstrap/slides-ei-empty.html` extended to 8 slides, `HTMLEDITOR_STATE_DIR` set to a `tmp_path` outside the deck folder). MCP tests call the tools through the in process `fastmcp.Client(mcp)` (`pytest-asyncio` auto) so the schema layer is exercised; CLI tests use `click.testing.CliRunner` with separate stdout and stderr. All tests of a story run with `make test ARGS='-k requests'`.

Storage failure seam (E2E-020, UT-A04): `RequestStore.record_dir(file)` is public and deterministic; the test creates a regular file at that path before the call. `mkdir` then raises `FileExistsError` or `NotADirectoryError` whatever the user id (a `chmod` based seam would pass under root in Docker). The expected text is `Could not queue the request: ` followed by `str(OSError)`; the test asserts the prefix and that the suffix is non empty and equals the message of the same `OSError` raised by `Path.mkdir` on that path.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| UT-A01 record round trip, accents and `\r\n` kept, JSON written as UTF 8, `record_dir(file)` equals `<state_dir>/files/<sha256(realpath)[:32]>/requests`; a corrupt `record.json` gives the unreadable message and is not reset | UT | store | tests/test_requests_core.py | STORY-A |
| UT-A02 two subprocesses and the parent queue 15 requests each against one state directory: 45 ids, all distinct, none lost | UT | subprocess + store | tests/test_requests_core.py | STORY-A |
| UT-A03 rule order: empty (also U+3000, U+00A0), 4000 accepted, 4001 refused, 50th accepted, 51st refused, `done` does not count | UT | service | tests/test_requests_core.py | STORY-A |
| UT-A04 storage failure seam: message prefix, nothing created | UT | service | tests/test_requests_core.py | STORY-A |
| UT-A05 title: `\r\n` becomes one space, cut at 60 code points (emoji count 1), not trimmed; `R-10000` after `R-9999` | UT | service | tests/test_requests_core.py | STORY-A |
| UT-A06 HTTP `POST /requests` happy path, `GET /requests` shape, 415 on `text/plain`, 400 invalid JSON, 400 invalid length, 413 above 1 MiB | UT | `http.client` | tests/test_requests_core.py | STORY-A |
| UT-A07 SPEC-0005 gate on the four routes: foreign `Origin` and foreign `Host` give 403 and store nothing; `OPTIONS` stays 405 | UT | `http.client` | tests/test_requests_core.py | STORY-A |
| UT-A08 `POST /requests/delete`: unknown id is a no op without revision bump, delete frees a pending slot, id stays used | UT | `http.client` | tests/test_requests_core.py | STORY-A |
| UT-A09 `requests` command: lines with two space columns, `No requests for <file>`, `error: File not found: ghost.html` on stderr with exit 1 and empty stdout; two files and a symlink alias (same record), a renamed file starts empty | UT | CliRunner | tests/test_requests_core.py | STORY-A |
| UT-A10 `/status` carries `requests_revision` that changes on each change; the deck folder holds only the deck after queueing | UT | `http.client` | tests/test_requests_core.py | STORY-A |
| SPEC-0010/E2E-002 list_requests shape | E2E | MCP client + HTTP queue | tests/test_requests_tools.py | STORY-B |
| SPEC-0010/E2E-013 invalid status message (schema layer does not intercept) | E2E | MCP client | tests/test_requests_tools.py | STORY-B |
| SPEC-0010/E2E-014 already completed | E2E | MCP client | tests/test_requests_tools.py | STORY-B |
| SPEC-0010/E2E-023 two files isolated, tool and `requests` command | E2E | MCP client + CliRunner | tests/test_requests_tools.py | STORY-B |
| SPEC-0010/E2E-025 completion after deletion, `Valid ids: none` | E2E | HTTP delete + MCP client | tests/test_requests_tools.py | STORY-B |
| UT-B01 `complete`: done ignores a reason (stored null), skipped keeps it untrimmed, whitespace only reason refused | UT | service | tests/test_requests_tools.py | STORY-B |
| UT-B02 check order file, id, status, reason, already completed (one input failing several checks each) | UT | service | tests/test_requests_tools.py | STORY-B |
| UT-B03 `Valid ids` lists all non deleted ids oldest first | UT | service | tests/test_requests_tools.py | STORY-B |
| UT-B04 tool `file` not found message without prefix; tool errors are `ToolError` | UT | MCP client | tests/test_requests_tools.py | STORY-B |
| UT-B05 `skill-audit` reports no tool list problem (core lists both tools) | UT | CliRunner | tests/test_requests_tools.py | STORY-B |
| SPEC-0010/E2E-005 command line parity: `requests`, `request-skip`, `requests`, `request-done` | E2E | CliRunner + HTTP queue | tests/test_requests_cli.py | STORY-C |
| SPEC-0010/E2E-011 unknown id on the command line, stdout empty, exit 1 | E2E | CliRunner | tests/test_requests_cli.py | STORY-C |
| SPEC-0010/E2E-012 skip without reason, tool and command, request still pending | E2E | MCP client + CliRunner | tests/test_requests_cli.py | STORY-C |
| UT-C01 `request-skip` without `--reason` equals `--reason ""` error | UT | CliRunner | tests/test_requests_cli.py | STORY-C |
| UT-C02 `request-done` twice gives `Request R-0001 is already done` | UT | CliRunner | tests/test_requests_cli.py | STORY-C |
| UT-C03 topic `create` contains the workflow words (`list_requests`, `complete_request`, `update_start`) and is at most 3800 bytes as a file and 8000 bytes as `topic_output` | UT | `build_library().topic_output("create")` | tests/test_requests_cli.py | STORY-C |
| UT-C04 `skill-audit` exits 0 | UT | CliRunner | tests/test_requests_cli.py | STORY-C |
| SPEC-0010/E2E-001 queue a request, slide shown before, side list | E2E | Playwright | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-008 empty request, also only spaces; `list_requests` empty | E2E | Playwright + MCP client | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-009 4001 characters refused | E2E | Playwright | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-010 51st pending refused | E2E | Playwright (49 seeded through the service) | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-020 storage failure shown in the panel | E2E | Playwright + seam | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-021 ids never reused after Delete | E2E | Playwright | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-022 accents and line break stored exactly | E2E | Playwright + MCP client | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-026 49 pending then two 4000 character requests | E2E | Playwright (49 seeded) | tests/test_requests_editor_e2e.py | STORY-D |
| UT-D01 `node --check` on `editor-requests.js` (skipped when `node` is absent) and file at most 500 lines | UT | subprocess | tests/test_requests_editor_e2e.py | STORY-D |
| UT-D02 a request titled `<img src=x onerror=window.__xss=1>` is shown as text and `window.__xss` stays undefined | UT | Playwright | tests/test_requests_editor_e2e.py | STORY-D |
| UT-D03 `editor.html` lists `editor-requests.js` after `editor-drag.js` and before `editor.js`; the existing fullscreen test still passes | UT | HTML parse | tests/test_requests_editor_e2e.py | STORY-D |
| SPEC-0010/E2E-003 complete as done, side list refreshed, `Requests (0)` | E2E | Playwright + MCP client | tests/test_requests_refresh_e2e.py | STORY-E |
| SPEC-0010/E2E-004 complete as skipped, reason shown after the title | E2E | Playwright + MCP client | tests/test_requests_refresh_e2e.py | STORY-E |
| SPEC-0010/E2E-027 refresh within two poll intervals, no reload | E2E | Playwright (poll set to 250 ms) + MCP client | tests/test_requests_refresh_e2e.py | STORY-E |
| UT-E01 with an unchanged `requests_revision`, ten polls issue zero `GET /requests` | UT | Playwright request log | tests/test_requests_refresh_e2e.py | STORY-E |
| UT-E02 after the user's own queue the next poll issues no extra `GET /requests` | UT | Playwright request log | tests/test_requests_refresh_e2e.py | STORY-E |
| SPEC-0010/E2E-015 seven suggestions refused, previous review kept | E2E | MCP client + CliRunner | tests/test_review_write.py | STORY-F |
| SPEC-0010/E2E-016 61 character title | E2E | MCP client + CliRunner | tests/test_review_write.py | STORY-F |
| SPEC-0010/E2E-017 missing field and duplicate id, tool and `--write` | E2E | MCP client + CliRunner | tests/test_review_write.py | STORY-F |
| SPEC-0010/E2E-018 `File not found: ghost.html` on the command and the three tools | E2E | MCP client + CliRunner | tests/test_review_write.py | STORY-F |
| UT-F01 check order: count before positions, position order, within one suggestion field order missing, length, duplicate | UT | service | tests/test_review_write.py | STORY-F |
| UT-F02 field rules: null `slide` accepted, non string `slide`, whitespace only `why`, non dict item, extra keys dropped | UT | service | tests/test_review_write.py | STORY-F |
| UT-F03 a new review resets `applied` even when ids repeat; requests of a previous apply stay | UT | service | tests/test_review_write.py | STORY-F |
| UT-F04 `review <file>` lines, `No review for <file>`, empty review prints the same | UT | CliRunner | tests/test_review_write.py | STORY-F |
| UT-F05 `--write` from a path and from `-`; unreadable path, invalid JSON, non list JSON messages | UT | CliRunner | tests/test_review_write.py | STORY-F |
| UT-F06 storage failure gives `Could not write the review: ...` and keeps the old review | UT | service + seam | tests/test_review_write.py | STORY-F |
| UT-F07 `skill-audit` exits 0 with `write_review` in the core | UT | CliRunner | tests/test_review_write.py | STORY-F |
| SPEC-0010/E2E-006 write a review, editor shows titles, why texts, Apply; `review` lines | E2E | Playwright + MCP client + CliRunner | tests/test_review_apply_e2e.py | STORY-G |
| SPEC-0010/E2E-007 apply creates a pending request, instruction `Tighten the agenda. Cut to 5 lines`, suggestion shows `Applied` | E2E | Playwright + MCP client | tests/test_review_apply_e2e.py | STORY-G |
| SPEC-0010/E2E-019 second apply from a stale page: `Suggestion s1 was already applied`, one request | E2E | two Playwright pages, `GET /requests` blocked on the stale one | tests/test_review_apply_e2e.py | STORY-G |
| SPEC-0010/E2E-024 new review replaces the list, applied request stays | E2E | Playwright + MCP client | tests/test_review_apply_e2e.py | STORY-G |
| UT-G01 apply check order: unknown id, already applied, then too long (built instruction), too many pending | UT | service | tests/test_review_apply_e2e.py | STORY-G |
| UT-G02 a refusal leaves `applied` false and creates no request; storage failure message | UT | service + seam | tests/test_review_apply_e2e.py | STORY-G |
| UT-G03 the request keeps a slide id that no longer exists | UT | service | tests/test_review_apply_e2e.py | STORY-G |
| UT-G04 HTTP status mapping of `POST /review/apply` (200, 404, 409, 400, 500) and gate/JSON rules | UT | `http.client` | tests/test_review_apply_e2e.py | STORY-G |
| UT-G05 `why` containing markup is shown as text | UT | Playwright | tests/test_review_apply_e2e.py | STORY-G |
| SPEC-0010/E2E-028 folder holds only the deck after a UI queue and a review write | E2E | Playwright + MCP client | tests/test_request_loop_acceptance.py | STORY-H |
| UT-H01 full loop in process: queue, list, complete, write review, apply, list | UT | service + tools + CLI | tests/test_request_loop_acceptance.py | STORY-H |
| UT-H02 removing the state directory removes requests and review | UT | service | tests/test_request_loop_acceptance.py | STORY-H |
| UT-H03 `skill-audit` exits 0 and the shipped `create.md` is at most 3800 bytes | UT | CliRunner | tests/test_request_loop_acceptance.py | STORY-H |
| UT-H04 README and AGENTS name the four commands and the three tools | UT | file read | tests/test_request_loop_acceptance.py | STORY-H |
| UT-H05 the tool process writes nothing to stdout when a tool is called (captured file descriptor) | UT | subprocess | tests/test_request_loop_acceptance.py | STORY-H |

Every `SPEC-0010/E2E-` test appears once (28). Coverage: the new modules are plain classes with no `pragma: no cover`; the HTTP handlers are covered by the real server tests; the 80 percent gate holds with the UT rows above.

## 10. Decisions log

- **DEC-001:** One JSON record per file, not one file per request and not SQLite. **Obliged by:** SPEC-0010/FR-NEW-001 (ids never reused, no request lost), SPEC-0010/FR-NEW-007 (the applied mark is stored together with the request). **Rationale:** a single write holds the counter, the requests and the review, so id allocation, request creation and the applied mark cannot disagree after a crash; the same JSON store style as SPEC-0009. **Alternatives considered:** a file per request plus a counter file (two files per apply, needs the same lock for the counter); SQLite (side files, busy handling, different failure text for E2E-020). **Source:** `sdlc/specs/SPEC-0009-reliable-saves/design.md` section 4.1 and DEC-006 (state directory, keyed by path). **Evidence:** spec FR-NEW-007 "the applied mark is stored together with the request".
- **DEC-002:** Exclusive `fcntl.flock` on a sibling `record.lock` around read, change, atomic rename; readers lock free. **Obliged by:** SPEC-0010/FR-NEW-001 ("when two operations conflict the later one sees the earlier one's result", "no id is given twice"). **Rationale:** `flock` locks belong to the open file description, so it excludes both other processes and other threads of the editor server (each `update` opens its own descriptor). **Alternatives considered:** optimistic revision compare with retry (two writers can both pass the compare, a request is lost); `O_EXCL` lock file (stale lock after a crash needs timeouts). **Source:** Python `fcntl` documentation. **Evidence:** the editor server is threaded (`http_server.py:571` `_EditorServer(ThreadingHTTPServer)`), so thread safety is required too.
- **DEC-003:** Record directory `<state_dir>/files/<sha256(realpath)[:32]>/requests/`, inside the SPEC-0009 per file directory. **Obliged by:** SPEC-0010/FR-NEW-001 (requests belong to the absolute path with symlinks resolved; renamed or moved file starts empty; removing the state directory removes them), SPEC-0010/FR-NEW-008. **Rationale:** a hash gives one safe directory name for any path; `realpath` implements the symlink rule. **Alternatives considered:** a top level `requests/<key>/` next to `files/` (two keyed trees for one file); path as directory name (length and character limits). **Source:** `sdlc/specs/SPEC-0009-reliable-saves/spec.md:176`. **Evidence:** `config.py:154-200` (`config_dir`, `log_dir`, ...) shows the settings derived directories pattern the `state_dir` follows.
- **DEC-004:** Change marker is the record `revision`, exposed as `requests_revision` in `/status`; the editor fetches `GET /requests` only when it differs. **Obliged by:** SPEC-0010/FR-NEW-005 ("refreshed within two poll intervals of a change made by the agent"). **Rationale:** the poll already runs (`editor.js:182` `setInterval(pollStatus, pollInterval)`); one integer compare avoids a list download every second; an exact counter, unlike an `mtime`, cannot miss two quick changes. **Alternatives considered:** fetch the list on every poll (simpler, one more request per second per tab); `stat` marker (`st_mtime_ns`, inode) (granularity and inode reuse). **Source:** spec Section 14.3 design inputs. **Evidence:** `http_server.py:278-288` builds the status payload from `state`, so one key is added there.
- **DEC-005:** Rules and messages live only in `RequestService`; surfaces translate (`RequestError.kind` to HTTP status, `ToolError`, `error: ` line). **Obliged by:** SPEC-0010/FR-NEW-004 (same results on both surfaces, tool message equals the command line line without its prefix). **Rationale:** one source of text makes parity structural. **Alternatives considered:** validate in each surface (three copies, drift). **Source:** FastMCP docs, `ToolError`. **Evidence:** context7 `/prefecthq/fastmcp` tools doc: ToolError messages are always sent to clients.
- **DEC-006:** `complete_request(status: str, ...)` and `write_review(suggestions: list[Any])`, not `Literal` or typed models. **Obliged by:** SPEC-0010/FR-NEW-003 (`Status must be done or skipped`), SPEC-0010/FR-NEW-006 (errors per suggestion). **Rationale:** a `Literal` or a pydantic item model makes FastMCP answer a schema validation error with other text before the service runs. **Alternatives considered:** `Literal["done","skipped"]` (rejected: E2E-013 would see a schema message). **Source:** spec E2E-013, E2E-017. **Evidence:** `mcp_server.py:30-31` tools are plain typed functions; FastMCP validates arguments against the signature.
- **DEC-007:** "Whitespace" is the Unicode `White_Space` set via one compiled regex (`\t\n\v\f\r`, space, U+0085, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F, U+3000), used for the empty request, the empty reason and the empty suggestion fields. **Obliged by:** SPEC-0010/FR-NEW-001, FR-NEW-003, FR-NEW-006 ("empty once all Unicode whitespace is removed"). **Rationale:** `str.strip()` also strips U+001C to U+001F, which are not `White_Space`. **Alternatives considered:** `str.strip()` (small mismatch on four control characters). **Source:** Unicode `PropList.txt` White_Space. **Evidence:** UT-A03 checks U+3000 and U+00A0.
- **DEC-008:** New classic script `editor-requests.js`, an IIFE, inserted after `editor-drag.js` and before `editor.js`, one global `requestsOnStatus`. **Obliged by:** SPEC-0010/FR-NEW-001, FR-NEW-005. **Rationale:** SPEC-0012 DR-006 fixes the order and forbids reading `editor.js` top level bindings at evaluation time and duplicate top level function names; `editor.js` stays the owner of the poll. **Alternatives considered:** append to `editor.js` (breaks the 500 line cap of SPEC-0012 DT-011); ES module (SPEC-0012 DEC-001 rejected modules). **Source:** `sdlc/specs/SPEC-0012-charter-registry-and-splits/design.md` DR-006, DT-011, DT-012. **Evidence:** `static/editor.html:81-83` classic tags.
- **DEC-009:** The four editor endpoints are GET and POST only, inside the existing dispatch. **Obliged by:** SPEC-0010/FR-NEW-001, FR-NEW-005, FR-NEW-007 and SPEC-0005 (origin, host, JSON only rules bind every endpoint). **Rationale:** the gate runs before dispatch (`http_server.py:120-130,152-160`), a new route cannot bypass it; deletion as POST because `do_OPTIONS` advertises `Allow: GET, POST`. **Alternatives considered:** `DELETE /requests/<id>` (new verb, new handler, new preflight surface). **Source:** SPEC-0005 design Section 2. **Evidence:** `http_server.py:109-112`.
- **DEC-010:** Storage failure seam is a regular file created at `record_dir(file)`. **Obliged by:** SPEC-0010/FR-NEW-001 (EXC-001d, "storage"), SPEC-0010 E2E-020. **Rationale:** `mkdir` fails with an `OSError` for every user including root; `chmod` does not. **Alternatives considered:** `chmod 0o500` (passes as root in the container); monkeypatching `atomic_write` (does not test the real error text). **Source:** spec E2E-020. **Evidence:** `.agent_docs/docker.md` runs the suite in a container.
- **DEC-011:** `update` writes only when the serialized record changed, and bumps `revision` only then. **Obliged by:** SPEC-0010/FR-NEW-005 ("deleting an id that does not exist is a no-op and the list is refreshed"). **Rationale:** a no op must not look like a change to other tabs or leave a new file version. **Alternatives considered:** always write (spurious refetch in every tab). **Source:** spec FR-NEW-005. **Evidence:** UT-A08.
- **DEC-012:** All strings from the record are inserted with `textContent`. **Obliged by:** SPEC-0010/FR-NEW-005, FR-NEW-006 (the editor shows `reason`, `title`, `why`, written by an agent). **Rationale:** agent text is untrusted data, and the editor shell origin can save the document (`POST /content`). **Alternatives considered:** `innerHTML` with escaping (one missed field is a hole). **Source:** project rule "untrusted content". **Evidence:** UT-D02, UT-G05.
- **DEC-013:** Current slide = `data-id` of the slide of the last click or selection in the iframe, else the first slide, else null; tracked by listeners re attached on each iframe `load`. **Obliged by:** SPEC-0010/FR-NEW-001 ("the slide holding the caret or the last click in the editor, else the first slide"). **Rationale:** follows the spec literally (the `.active` slide is not the spec's rule); the remembered id is validated against the current document at use. **Alternatives considered:** `getCurrentSlideIndex` (`.active` slide, `editor.js:1459`), rejected because it is a different observable rule when the user navigates without clicking. **Source:** spec FR-NEW-001. **Evidence:** E2E-001 clicks inside `slide-3` before opening the panel.
- **DEC-014:** The new POST routes cap the body at 1 MiB and check `Content-Length`. **Obliged by:** SPEC-0010/FR-NEW-001 (SPEC-0005 hardening of every endpoint); SPEC-0009 FR-NEW-007 limits apply to the save endpoint only. **Rationale:** `int(self.headers.get("Content-Length", 0))` (`http_server.py:297`, `:358`) crashes on a bad header and has no bound; the largest valid body is about 16 KB. **Alternatives considered:** reuse nothing and copy the unbounded read. **Source:** `sdlc/specs/SPEC-0009-reliable-saves/spec.md:155`. **Evidence:** UT-A06.
- **DEC-015:** `fcntl` only (macOS, Linux, Docker). **Obliged by:** SPEC-0010/FR-NEW-001 (atomic across processes). **Rationale:** the product targets those platforms; a portable lock needs a dependency. **Alternatives considered:** `msvcrt` branch (untestable here); a lock library (new dependency, NEEDS DECISION not raised). **Source:** `AGENTS.md` (Docker, macOS tooling). **Evidence:** no Windows target in `Makefile` or docs.
- **DEC-016:** An invalid record raises a storage error and is never reset. **Obliged by:** SPEC-0010/FR-NEW-001 ("never reused" ids). **Rationale:** resetting to an empty record would give `R-0001` again. **Alternatives considered:** silent reset; rename the bad file to `record.json.bad` and start again (reuses ids). **Source:** spec FR-NEW-001. **Evidence:** UT-A01 writes a corrupt record and expects the message, and the next queue still fails.
- **DEC-017:** An empty review prints `No review for <file>`, and a non dict suggestion item gives `Suggestion N: missing field "id"`. **Obliged by:** SPEC-0010/FR-NEW-006. **Rationale:** the spec is silent; the smallest rule that keeps the one message set. **Alternatives considered:** a new message for non dict items. **Source:** spec FR-NEW-006 "missing field". **Evidence:** UT-F02, UT-F04.

## 11. Stories

Slicing: eight vertical increments (a surface of the product, observable and tested, `make check` green after each). Shared files (`request_service.py`, `cli.py`, `mcp_server.py`, `editor-requests.js`) grow story by story; a story only adds, never rewrites an earlier story's code.

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| STORY-A | Store, queue endpoints and the `requests` command | P1 | SPEC-0010/FR-NEW-001, FR-NEW-002, FR-NEW-008 | SPEC-0009:reliable-saves, SPEC-0007:agent-editing-tools | 2 | no |
| STORY-B | Agent lists and completes requests (tools) | P1 | SPEC-0010/FR-NEW-002, FR-NEW-003, FR-NEW-004 | STORY-A | 2 | no |
| STORY-C | Complete from the command line and the apply workflow in the skill | P1 | SPEC-0010/FR-NEW-003, FR-NEW-004 | STORY-B, SPEC-0006:progressive-skill | 2 | no |
| STORY-D | Ask AI panel and the requests side list | P1 | SPEC-0010/FR-NEW-001, FR-NEW-005 | STORY-B, SPEC-0012:charter-registry-and-splits | 2 | no |
| STORY-E | Live refresh of the side list | P1 | SPEC-0010/FR-NEW-003, FR-NEW-005 | STORY-D | 2 | no |
| STORY-F | Write and read the AI review (tool and command) | P2 | SPEC-0010/FR-NEW-004, FR-NEW-006 | STORY-B | 2 | no |
| STORY-G | Show the AI suggestions and apply one | P2 | SPEC-0010/FR-NEW-006, FR-NEW-007 | STORY-E, STORY-F | 2 | no |
| STORY-H | Documentation and no file next to the user's file, end to end | P2 | SPEC-0010/FR-NEW-004, FR-NEW-008 | STORY-G | 2 | yes |

Files per story (3 to 5): A `request_store.py`, `request_service.py`, `http_server.py`, `cli.py`, `tests/test_requests_core.py`. B `request_service.py`, `mcp_server.py`, skill core, `tests/test_requests_tools.py`. C `cli.py`, skill topic `create`, `tests/test_requests_cli.py`. D `editor-requests.js`, `editor.html`, `editor.css`, `tests/test_requests_editor_e2e.py` `tests/test_static_scripts.py` (the one line script order edit): five files. E `editor.js`, `editor-requests.js`, `tests/test_requests_refresh_e2e.py`. F `request_service.py`, `mcp_server.py`, `cli.py`, skill core, `tests/test_review_write.py`. G `request_service.py`, `http_server.py`, `editor-requests.js`, skill topic `create`, `tests/test_review_apply_e2e.py`. H `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md`, `tests/test_request_loop_acceptance.py`.

Per story verification: `make check` plus `make test ARGS='-k <story test file stem>'`.
