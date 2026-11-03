# US-0052: Store, queue endpoints and the requests command

> Spec: SPEC-0010 (sdlc/specs/SPEC-0010-request-loop/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0051
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Introduce the shared request record (one JSON file per user file under the SPEC-0009 state directory, changed under an exclusive lock), the rules to queue, list and delete requests, the three HTTP routes the editor will call, the change marker in `/status`, and the `requests` command. After this story a request can be queued over HTTP and listed from the command line; no editor UI and no agent tool yet.

## Requirements covered

- SPEC-0010/FR-NEW-001 (partial: storage, rules, limits and HTTP endpoints; the Ask AI panel is US-0055): WHEN the user clicks `Queue request` in the `Ask AI` panel THE Editor SHALL store a pending request and confirm it.
- SPEC-0010/FR-NEW-002 (partial: the `requests` command; the `list_requests` tool is US-0053): WHEN an agent calls `list_requests` or a user runs `mcp-htmleditor requests <file>` THE Editor SHALL list the requests of that file, oldest first.
- SPEC-0010/FR-NEW-008 (partial: requests are stored under the state directory and kept per file; the end to end folder check is US-0059): The Editor SHALL NOT create any file or folder next to the user's file for requests or the review, and SHALL NOT mix requests of different files.

## Independent Test

`make test ARGS='-k requests_core'` (the whole of `make check` for the gate): a request posted to `POST /requests` on a served deck is returned by `GET /requests`, printed by `mcp-htmleditor requests deck.html` as `R-0001  pending  slide-3  Shorten the title`, and the deck folder still holds only `deck.html`.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0010): "One JSON record per file, not one file per request and not SQLite." A single write holds the counter, the requests and the review, so id allocation, request creation and the applied mark cannot disagree after a crash.
- DEC-002 (SPEC-0010): "Exclusive `fcntl.flock` on a sibling `record.lock` around read, change, atomic rename; readers lock free." `flock` belongs to the open file description, so it excludes other processes and other threads of the threaded editor server (each `update` opens its own descriptor).
- DEC-003 (SPEC-0010): "Record directory `<state_dir>/files/<sha256(realpath)[:32]>/requests/`, inside the SPEC-0009 per file directory." `realpath` implements the symlink rule; a renamed or moved file has another key and starts empty.
- DEC-005 (SPEC-0010): "Rules and messages live only in `RequestService`; surfaces translate (`RequestError.kind` to HTTP status, `ToolError`, `error: ` line)." One source of text makes parity structural (FR-NEW-004).
- DEC-007 (SPEC-0010): "Whitespace" is the Unicode `White_Space` set via one compiled regex (`\t\n\v\f\r`, space, U+0085, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F, U+3000), used for the empty request, the empty reason and the empty suggestion fields; `str.strip()` also strips U+001C to U+001F, which are not `White_Space`.
- DEC-009 (SPEC-0010): "The four editor endpoints are GET and POST only, inside the existing dispatch." The SPEC-0005 gate runs before dispatch, so a new route cannot bypass it; deletion is a POST because `do_OPTIONS` advertises `Allow: GET, POST`.
- DEC-010 (SPEC-0010): "Storage failure seam is a regular file created at `record_dir(file)`." `mkdir` fails with an `OSError` for every user including root; `chmod` does not (the suite also runs as root in the container).
- DEC-011 (SPEC-0010): "`update` writes only when the serialized record changed, and bumps `revision` only then." A no op (deleting an unknown id) must not look like a change to other tabs.
- DEC-014 (SPEC-0010): "The new POST routes cap the body at 1 MiB and check `Content-Length`." The header goes through SPEC-0009's `parse_content_length`; the 50 MiB cap of the save route is not used here.
- DEC-015 (SPEC-0010): "`fcntl` only (macOS, Linux, Docker)." A Windows run raises `ModuleNotFoundError` at import of `request_store`; accepted.
- DEC-016 (SPEC-0010): "An invalid record raises a storage error and is never reset." Resetting to an empty record would give `R-0001` again.

### Data model

Request (JSON object, exactly these keys, in this order): `id` (`R-` plus the counter on at least 4 digits, `f"R-{n:04d}"`), `slide` (string or null, never checked against the file), `title` (instruction with each `\r\n`, `\n` or `\r` replaced by one space, then the first 60 code points, not trimmed), `queued` (`datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` taken inside the lock), `instruction` (exactly as typed), `status` (`pending`, `done`, `skipped`), `reason` (null unless `skipped`, stored as given).

Suggestion: `{"id","slide","title","why","change","applied"}`; the five input keys are the only ones kept, `applied` is stored.

Record file `<state_dir>/files/<key>/requests/record.json` (lock file `record.lock` beside it, empty, only locked); `<state_dir>` is `get_settings().state_dir`; `<key>` is `hashlib.sha256(os.path.realpath(file).encode("utf-8")).hexdigest()[:32]`, the key SPEC-0009 uses for `server.json`, `update.json` and `history/`:

```json
{"version":1,"file":"/abs/path/deck.html","revision":7,"next_id":4,
 "requests":[{"id":"R-0001","slide":"slide-3","title":"Shorten the title","queued":"2026-11-03T10:15:00Z","instruction":"Shorten the title","status":"pending","reason":null}],
 "review":[{"id":"s1","slide":"slide-1","title":"Tighten the agenda","why":"...","change":"Cut to 5 lines","applied":false}]}
```

`next_id` only increases (incremented on creation, never on deletion). `revision` increases by 1 on every write that changes the record; a change that leaves the serialized record identical writes nothing and does not bump it. `review` is null when never written (distinct from `[]`). A missing record file is an empty record (`next_id` 1, `revision` 0); read only operations never create the state directory. A record that exists but is unreadable or invalid JSON raises `RequestError(kind="storage")` with `Requests record of <file> is unreadable: <reason>` and is never reset. Limits: `INSTRUCTION_MAX = 4000`, `PENDING_MAX = 50`, `TITLE_MAX = 60`, `REVIEW_MAX = 6`, `BODY_MAX_BYTES = 1_048_576`.

Rules of `queue` in order: `is_blank(instruction)` gives `Write a request first` (kind `invalid`); `len(instruction) > 4000` gives `Request too long (max 4000 characters)` (`invalid`); inside the lock, 50 pending already gives `Too many pending requests (max 50)` (`conflict`); any `OSError` from the store gives `Could not queue the request: <error>` (`storage`). `RequestError.kind` to HTTP status: `invalid` 400, `conflict` 409, `not_found` 404, `storage` 500.

### Contracts

#### Python

```python
# request_store.py (new)
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
        # mkdir(mode=0o700, parents=True, exist_ok=True); flock EX on record.lock; read; change(record);
        # if the serialized form changed: revision += 1 and atomic_write(record.json, bytes) (fileio, no reason);
        # JSON written with ensure_ascii=False, UTF 8; span "requests.update" (record path and operation name, never the text);
        # any exception from change() writes nothing

    def revision(self, file: Path) -> int: ...  # 0 when absent or unreadable (logs a warning), used by /status
```

```python
# request_service.py (new; this story: queue, list_requests, delete, snapshot and helpers)
ErrorKind = Literal["invalid", "conflict", "not_found", "storage"]
class RequestError(Exception): kind: ErrorKind; message: str       # str(exc) == message
class RequestService:
    def __init__(self, store: RequestStore, clock: Callable[[], datetime] = utc_now) -> None: ...
    def queue(self, file: Path, instruction: str, slide: str | None) -> Request
    def list_requests(self, file: Path) -> list[Request]           # oldest first, all statuses
    def delete(self, file: Path, request_id: str) -> None          # unknown id is a no op; OSError -> "Could not delete the request: <error>"
    def snapshot(self, file: Path) -> Snapshot                     # (revision, pending, requests, suggestions) for GET /requests
def require_file(file: str) -> Path       # Path(file).resolve(); RequestError("not_found", f"File not found: {file}") if not a file ("as typed")
def build_request_service() -> RequestService   # RequestStore(get_settings().state_dir)
def is_blank(text: str) -> bool
def request_to_dict(r: Request) -> dict[str, Any]       # 7 keys in order id, slide, title, queued, instruction, status, reason
def suggestion_to_dict(s: Suggestion) -> dict[str, Any]
```

#### HTTP

| Method, path | Body | Success | Errors |
|---|---|---|---|
| `GET /requests` | none | 200 `{"revision":7,"pending":2,"requests":[7 keys each],"suggestions":[{"id","slide","title","why","change","applied"}]}` | 404 `{"error":"No file loaded"}`; 500 `{"error":"<record error>"}` |
| `POST /requests` | `{"instruction":str,"slide":str\|null}` | 200 `{"ok":true,"request":{...}}` | 400 `{"ok":false,"error":"Write a request first"}`, `Request too long (max 4000 characters)`, `Invalid request body`; 409 `Too many pending requests (max 50)`; 500 `Could not queue the request: <error>` |
| `POST /requests/delete` | `{"id":str}` | 200 `{"ok":true}` | 400 `Invalid request body`; 500 `Could not delete the request: <error>` |
| `GET /status` | none | existing payload plus `"requests_revision": <int>` (`RequestStore.revision`, 0 when none) | unchanged |

The routes sit inside the existing `do_GET` / `do_POST` dispatch, so the SPEC-0005 gate (`_refuse_untrusted_request`) runs first. Helper `_read_json_object(self) -> dict[str, Any] | None` implements: `Content-Type` other than `application/json` gives 415 `{"error":"unsupported content type"}`; invalid `Content-Length` gives 400 `{"error":"Invalid Content-Length"}` (via SPEC-0009 `parse_content_length`); a length above `BODY_MAX_BYTES` gives 413 `{"error":"Request too large"}` before reading; invalid JSON gives 400 `{"error":"Invalid JSON body"}`; a body that is not a JSON object, or fields of the wrong type (`instruction` not a string, `slide` neither string nor null, `id` not a string), gives 400 `{"ok":false,"error":"Invalid request body"}`. The file is `get_state().current_file`; none gives 404 `{"error":"No file loaded"}`. `do_OPTIONS` is unchanged (405). The fourth route of the design (`POST /review/apply`) belongs to US-0058.

#### Command line

```python
# cli.py: private _request_fail(message: str) -> NoReturn  (click.echo(f"error: {message}", err=True); raise SystemExit(1); stdout stays empty)
@main.command("requests")  @click.argument("file")    # lines "<id>  <status>  <slide or ->  <title>" (two spaces), or "No requests for <file>"
```
`<file>` is shown as typed in `No requests for <file>` and in `File not found: <file>`; the record is looked up through `Path(file).resolve()`.

Tracing: span `requests.update` (path of the record and the operation name, never the instruction text). No `print`; no `os.environ` (the state directory comes from `get_settings().state_dir`); `%` logging, never the instruction text in a log line.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/request_store.py` | create |
| `src/mcp_htmleditor/request_service.py` | create |
| `src/mcp_htmleditor/http_server.py` | modify: routes `GET /requests`, `POST /requests`, `POST /requests/delete`, helper `_read_json_object`, `requests_revision` in `_serve_status` |
| `src/mcp_htmleditor/cli.py` | modify: add `requests` and `_request_fail` |
| `tests/test_requests_core.py` | create |

### Existing patterns
- `fileio.atomic_write(path, data, *, reason=None, history=None) -> bool` (SPEC-0009 section 5.2): used with no reason; it does not create the parent directory, so `update` creates it (mode 0700) first.
- `config.py`: `get_settings().state_dir` (SPEC-0009 DEC-005); `tests/conftest.py` autouse `isolate_state_dir` (SPEC-0009) gives each test its own state directory.
- `http_server.py`: `_refuse_untrusted_request` gate, `_receive_content`, `parse_content_length` / `SaveRefusal` (SPEC-0009), `_serve_status`, `get_state().current_file` (absolute).
- `cli.py`: lazy imports inside commands, `error: <message>` on stderr and exit 1 as in the SPEC-0009 `history` and `restore` commands.
- Real server harness: `tests/test_autosave_focus_e2e.py:35-80` (`start_http_server` on a free port, `reset_state` fixture); `tests/test_http_origin_e2e.py` (US-0002) for the raw request helpers.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0010/UT-A01: Store round trip and unreadable record
- Level UT; Driver `RequestStore` and `RequestService` in process; Location `tests/test_requests_core.py`
- Given an empty state directory (`tmp_path`) and a file `deck.html`
- When `queue("Mettre « Résumé » en gras\r\npuis centrer", "slide-3")` is called then `list_requests` is read by a second `RequestStore` instance
- Then the stored `instruction` equals the typed text exactly, `record.json` bytes contain `R\xc3\xa9sum\xc3\xa9` (UTF 8, not `\u00e9`), and `store.record_dir(file)` equals `<state_dir>/files/<sha256(os.path.realpath(file).encode("utf-8")).hexdigest()[:32]>/requests`
- And when `record.json` is replaced by the bytes `{not json`, `list_requests` and `queue` both raise `RequestError` of kind `storage` whose message starts with `Requests record of ` and contains `is unreadable: `, and the bytes of `record.json` are unchanged afterwards

### SPEC-0010/UT-A02: Three processes, no lost request, no duplicate id
- Level UT; Driver two `subprocess.run([sys.executable, "-c", script])` with `HTMLEDITOR_STATE_DIR` and `PYTHONPATH=src`, plus the parent; Location `tests/test_requests_core.py`
- Given one state directory and one file
- When the parent and the two subprocesses each queue 15 requests (`slide` null) against it
- Then `list_requests` returns 45 requests, the 45 ids are distinct, they are exactly `R-0001` to `R-0045`, and `record.json` has `next_id` 46

### SPEC-0010/UT-A03: Rule order and limits
- Level UT; Driver `RequestService`; Location `tests/test_requests_core.py`
- When `queue` receives `""`, `"   "`, `"\u3000"`, `"\u00a0"`, or 4001 spaces
- Then each raises `RequestError` kind `invalid` with message `Write a request first` (blank is checked before length)
- And `"a" * 4000` is accepted (stored untrimmed), `"a" * 4001` raises kind `invalid` `Request too long (max 4000 characters)`
- And with 49 pending requests the 50th is accepted and the 51st raises kind `conflict` `Too many pending requests (max 50)`; when one of the 50 is set to `done` through `store.update`, the next `queue` is accepted

### SPEC-0010/UT-A04: Storage failure seam
- Level UT; Driver `RequestService`; Location `tests/test_requests_core.py`
- Given a regular file created at `store.record_dir(file)` (so `mkdir` fails whatever the user id)
- When `queue("x", None)` is called
- Then it raises kind `storage` with a message that starts with `Could not queue the request: `, whose suffix is non empty and equals `str(e)` of the `OSError` raised by `Path.mkdir(parents=True, exist_ok=True)` on that same path, and no `record.json` exists. `delete("R-0001")` in the same state raises kind `storage` with prefix `Could not delete the request: `

### SPEC-0010/UT-A05: Title and id formatting
- Level UT; Driver `RequestService`; Location `tests/test_requests_core.py`
- Then `"a\r\nb"` gives title `a b`; `"a\n\nb"` gives `a  b` (one space per break); `"a\rb"` gives `a b`; `" hi"` keeps its leading space; `"x" * 70` gives a 60 character title; 59 `x`, then `😀`, then `yyyy` gives a title of 60 code points ending with `😀`
- And after seeding `next_id` to 9999 through `store.update`, two `queue` calls return ids `R-9999` then `R-10000`
- And `queued` matches `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` and comes from the injected `clock` at storage time

### SPEC-0010/UT-A06: HTTP queue and list
- Level UT; Driver `http.client` and a raw socket against a real `start_http_server` on a free port; Location `tests/test_requests_core.py`
- Given the server serves `deck.html`
- When `POST /requests` `Content-Type: application/json` body `{"instruction":"Shorten the title","slide":"slide-3"}`
- Then 200 `{"ok":true,"request":{"id":"R-0001","slide":"slide-3","title":"Shorten the title","queued":"<UTC time>","instruction":"Shorten the title","status":"pending","reason":null}}` and `GET /requests` answers 200 `{"revision":1,"pending":1,"requests":[<that request>],"suggestions":[]}`
- And `Content-Type: text/plain` gives 415 `{"error":"unsupported content type"}`; body `{` gives 400 `{"error":"Invalid JSON body"}`; `Content-Length: abc` (raw socket) gives 400 `{"error":"Invalid Content-Length"}`; a declared length of 1048577 gives 413 `{"error":"Request too large"}`; body `[]`, `{"instruction":5,"slide":null}` and `{"instruction":"x","slide":3}` give 400 `{"ok":false,"error":"Invalid request body"}`
- And a blank instruction gives 400 `{"ok":false,"error":"Write a request first"}`; 4001 characters gives 400 `Request too long (max 4000 characters)`; the 51st pending gives 409 `Too many pending requests (max 50)`; with no file loaded `GET /requests` gives 404 `{"error":"No file loaded"}`

### SPEC-0010/UT-A07: SPEC-0005 gate on the new routes
- Level UT; Driver `http.client`; Location `tests/test_requests_core.py`
- When `GET /requests`, `POST /requests` and `POST /requests/delete` are sent with `Origin: https://evil.example`, then with `Host: evil.example`
- Then each answers 403 and no record directory exists under the state directory; `OPTIONS /requests` answers 405 with `Allow: GET, POST`

### SPEC-0010/UT-A08: Delete
- Level UT; Driver `http.client`; Location `tests/test_requests_core.py`
- Given R-0001 and R-0002 pending, revision 2
- When `POST /requests/delete` `{"id":"R-0009"}`
- Then 200 `{"ok":true}`, `GET /requests` still shows revision 2 and both requests (a no op does not bump the revision)
- And deleting `R-0002` gives 200, revision 3, one request left; the next queued request is `R-0003`; with 50 pending, a delete frees a slot so the next queue is accepted

### SPEC-0010/UT-A09: `requests` command, isolation and aliases
- Level UT; Driver `click.testing.CliRunner` (separate stdout and stderr); Location `tests/test_requests_core.py`
- Given R-0001 queued on `deck.html` with slide `slide-3` and instruction `Shorten the title`, and a second request with slide null and instruction `Fix footer`
- When `requests deck.html` runs
- Then stdout is `R-0001  pending  slide-3  Shorten the title\nR-0002  pending  -  Fix footer\n`, exit 0
- And `requests deck2.html` (existing file, no requests) prints `No requests for deck2.html`; `requests ghost.html` prints nothing on stdout and `error: File not found: ghost.html` on stderr with exit 1
- And a symlink `alias.html` to `deck.html` shows the same two lines (same record), and after renaming `deck.html` to `moved.html` the command on `moved.html` prints `No requests for moved.html`

### SPEC-0010/UT-A10: `requests_revision` and no file next to the deck
- Level UT; Driver `http.client`; Location `tests/test_requests_core.py`
- When `GET /status` is read before any request, after a queue, and after a delete
- Then `requests_revision` is 0, 1, 2; and after queueing, `os.listdir` of the deck folder is exactly `["deck.html"]`

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/mcp_server.py`, `skill/*`, `fileio.py`, `config.py`, existing test files.
- Dependencies not to add: none allowed (`fcntl`, `hashlib`, `json` are stdlib).
- Patterns to avoid: `str.strip()` for the blank test (use the `White_Space` regex of DEC-007); resetting an unreadable record; writing the record without the lock; logging the instruction text; creating anything next to the user's file.
- Scope boundary: no tool, no `complete`, no review, no editor UI in this story. Only the key SPEC-0009 formula is used; no new setting.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_http_origin_e2e.py`, `tests/test_state.py` and the SPEC-0009 save tests pass unmodified; `/status` keeps every existing key.
- [ ] Docs updated: none in this story (the closing story US-0059 documents the feature).
- [ ] Self review: full (tier 2).
- [ ] If the story registers an MCP tool: not applicable, this story registers none.
- [ ] One commit `US-0052: Store, queue endpoints and the requests command`, body `Spec: SPEC-0010` and the requirement ids FR-NEW-001, FR-NEW-002, FR-NEW-008.
