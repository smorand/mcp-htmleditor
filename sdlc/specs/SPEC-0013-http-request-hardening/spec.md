# Malformed, ambiguous or stalled requests get no clean answer: Bug Specification

> Generated on: 2026-11-05
> Id: SPEC-0013
> Nature: BUG
> Depth: M
> Depth evidence: 3 surfaces (editor HTTP server, command line, agent tools), one module family (request handling, the record writers, path and bind address arguments and trace export); 22 requirements; public HTTP contract changes (new 400, 408 and 413 answers); no data model change
> Status: designed
> Verdict: authority exists
> Defect class: n/a (code violates a clear authority)
> Severity: Low
> From backlog: BL-0020, BL-0023, BL-0027, BL-0033 (BL-0015 consumed as a non regression statement, already fixed by SPEC-0009)
> Security: internal finding
> CVSS: not scored (self assessed Low: needs a non browser client on the machine, a server side request forgery, or a proxy in front)
> Affected: every version up to 8652a5b (main, 2026-11-05)
> Fixed in: unreleased

`--security` obligations applied (request smuggling, resource exhaustion and unencodable text
classes). Five defects of one family: an unacceptable request, argument or text gets no prompt,
precise and side effect free answer. File and line citations, searches and reproductions are in the Evidence appendix.

## 1. Defect

### BUG-001: Duplicated or ambiguous identity and framing headers are read first occurrence only

- **Observed behavior:** reproduced on 2026-11-05, real server on `127.0.0.1:P`, raw TCP client:
  1. `GET /content` with `Host: 127.0.0.1:P` then `Host: evil.example` answers `200` with the
     document; the reverse order answers `403 {"error":"forbidden host"}`.
  2. The same two `Host` lines on `POST /content`, `Content-Type: application/json`, body
     `{"html":"<html><body>PWNED</body></html>"}` answer `200`; the file on disk then holds `PWNED`.
  3. `Origin: http://127.0.0.1:P` then `Origin: https://evil.example` on `GET /content`: `200`.
  4. `Content-Length: 42` (true length) then `Content-Length: 5` on a save: `200`, `PWNED` written.
  5. `Host: evil@127.0.0.1:P`: `200`, the part before `@` dropped.
  6. `Transfer-Encoding: chunked`, no `Content-Length`: `400 {"error":"Invalid JSON body"}`; the
     framing header is ignored rather than refused.
  7. A folded `Host` or `Origin` answers `403`, a refusal naming the wrong problem.
- **Expected per authority:** RFC 9112 section 3.2 ("A server MUST respond with a 400 (Bad Request)
  status code to any HTTP/1.1 request message that lacks a Host header field and to any request
  message that contains more than one Host header field line or a Host header field with an invalid
  field value"), 6.3 (differing `Content-Length` values: 400), 6.1 (unsupported transfer coding, or
  `Transfer-Encoding` with `Content-Length`: an error), 5.2 (obsolete folding: reject with 400 or
  unfold); SPEC-0005/BR-001, BR-002 (the gate must judge the headers the request really carries).
- **Reproduction:** as item 2 above. Expected: `400`, file unchanged. Actual: `200`, file overwritten.
- **Root cause:** the request gate reads the `Host` and `Origin` headers with a single value lookup,
  which returns the first occurrence and ignores the others (E1, E2); the save and request routes do
  the same for `Content-Length` and `Content-Type` (E3 to E6); nothing reads `Transfer-Encoding`
  (search S2, zero hits); the host parser accepts and discards a userinfo part (E7).
- **Contributing factors:** SPEC-0005 tests always send one header of each kind (E18); the standard
  library parser keeps every occurrence but exposes the first by default (E8).
- **Impact:** browsers cannot forge duplicated headers, so SPEC-0005 holds for web pages. A local non
  browser client, a header controlling server side request forgery, or a proxy reading another `Host`
  or `Content-Length` than the gate, passes the host check or desynchronizes framing. Answers are
  HTTP/1.0 and close the connection (E9), limiting smuggling to one request per connection. Low.
- **Rollback posture:** a revert restores today's behavior; no file or record format changes.

### BUG-002: The layout route trusts its length header, and no route bounds a stalled read

- **Observed behavior:** reproduced on 2026-11-05:
  1. `POST /arch-layout` with `Content-Length: abc`, `-5` or `99999999999999999999` closes the
     connection with no answer and logs a traceback.
  2. `POST /arch-layout` declaring `Content-Length: 2000000` and sending nothing: no answer, ever.
  3. `POST /content` declaring 100 bytes and sending one holds the handler forever; 50 such
     connections were held at once while `GET /health` still answered.
- **Expected per authority:** SPEC-0009/FR-NEW-007 (`Invalid Content-Length` 400, `Request too large`
  413 before reading, "These length and size checks apply to the save endpoint only"); SPEC-0010 the
  same with a 1 MiB cap (E10). The layout route was left out by scope (BL-0023). RFC 9110 section
  15.5.9 (`408 Request Timeout`). The bound itself is decided here (BR-008).
- **Reproduction:** item 1. Expected: `400 {"error":"Invalid Content-Length"}`. Actual: no answer.
- **Root cause:** the layout route converts the raw header with an integer conversion and reads that
  many bytes, with no validation and no cap (E11); the request handler class keeps the standard
  library default of no socket timeout (E12), so every body read and header read waits forever.
- **Contributing factors:** the one existing test of the route's body sends a valid `{}` and asserts
  `200` (E19).
- **Impact:** a local client can tie up handler threads and memory; the editor keeps serving other
  requests (one thread per connection). Robustness, Low.
- **Rollback posture:** a revert restores today's behavior.

### BUG-003: Text that cannot be encoded as UTF-8 crashes the write instead of being refused

- **Observed behavior:** reproduced on 2026-11-05. JSON allows an unpaired surrogate escape
  (`"\ud800"`); the decoded string cannot be written as UTF-8.
  1. `POST /content` with body `{"html":"<html>\ud800"}` (or `\udc00`) closes the connection with no
     answer (`RemoteDisconnected`) and logs a `UnicodeEncodeError` traceback. The file is untouched.
  2. `mcp-htmleditor patch deck.html --ops ops.json` with
     `[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\ud800"}]` prints a Python traceback,
     exit status 1, file untouched. `--dry-run` fails the same way.
  3. The agent tool `patch` with the same operations raises `UnicodeEncodeError`, not a tool error.
  4. The agent tool `write_review` with a suggestion title `t\ud800`, and the command
     `mcp-htmleditor review deck.html --write rev.json` with that list, raise `UnicodeEncodeError`
     (traceback on the command line).
  5. The agent tool `complete_request` with `reason` `because \ud800`, and
     `mcp-htmleditor request-skip deck.html R-0001 --reason $'bad \xff'` (an undecodable argument byte
     arrives as `\udcff`), raise `UnicodeEncodeError` (traceback on the command line).
  A valid pair (`\ud83d\ude00`) and `\u0000` are written normally. The HTTP request routes
  `POST /requests`, `POST /requests/delete` and `POST /review/apply` already answer
  `400 {"ok":false,"error":"Invalid request body"}` (E13).
- **Expected per authority:** SPEC-0009/FR-NEW-007 ("refuse it with a precise status and leave the
  file unchanged"; 500 only on an operating system failure); SPEC-0007 (patch errors are
  `error: <message>`, exit status 1, the tool error carries the same text); SPEC-0010 (record errors
  are `RequestError` lines on every surface).
- **Reproduction:** item 1 above. Expected: a 400 answer, file unchanged. Actual: no answer.
- **Root cause:** the save body parser accepts any JSON string as `html` (E14); the encoding happens
  later in the atomic writer (E15), whose `UnicodeEncodeError` is not an operating system error and is
  not caught by the save route (E16); `patch` encodes the new document outside its error handling (E17);
  the record writer encodes the record (E13b) and only operating system errors are translated.
- **Contributing factors:** the request routes were protected one by one (E13), not at the write.
- **Impact:** robustness only, no data loss: every observed failure leaves the file or record intact.
- **Rollback posture:** a revert restores today's behavior.

### BUG-004: A path argument holding an unpaired surrogate crashes the tool or command

- **Observed behavior:** reproduced on 2026-11-05 at 8652a5b, `HTMLEDITOR_STATE_DIR` in a
  temporary folder:
  1. The agent tool `new_file` with `file` `<tmp>/n\ud800.html`, and the tool `export` with `output`
     `<tmp>/o\ud800.pptx`, raise `UnicodeEncodeError`, not a tool error. Nothing is created.
  2. The tools `write_review`, `get_slide` and `patch` with `file` `/tmp/x\ud800.html` raise
     `UnicodeEncodeError` (former BL-0033).
  3. On the command line an undecodable byte arrives as `\udcXX`: `mcp-htmleditor export pptx deck.html
     $'o\xff.pptx'` prints an `OSError` traceback, exit 1; `mcp-htmleditor new carbon $'n\xff.html'`
     prints its `error: Cannot write ...: Illegal byte sequence` line after a logging traceback;
     `history`, `outline`, `lint` and `render` print `error: File not found: ...`.
- **Expected per authority:** SPEC-0007 (tool and command failures are `error: <message>` lines, exit
  status 1, the tool error carries the same text); SPEC-0010 (record errors are `RequestError` lines).
- **Reproduction:** item 1. Expected: a tool error, nothing created. Actual: `UnicodeEncodeError`.
- **Root cause:** path text reaches the operating system file name encoder and two strict UTF-8 key
  hashes with no check that it is encodable (E29); the encoder's `UnicodeEncodeError` is neither an
  operating system error nor a `DeckError`, so no surface translates it.
- **Contributing factors:** the path class was first deferred (BL-0033) and only the `file` argument
  was listed; `output` and `new_file`'s `file` were missed by the first sweep.
- **Impact:** robustness only, nothing is written. Low.
- **Rollback posture:** a revert restores today's behavior.

### BUG-005: An argument that cannot be encoded breaks the trace export with a traceback

- **Observed behavior:** reproduced on 2026-11-05, local JSONL trace export (no
  `HTMLEDITOR_OTEL_DESTINATION`): `get_slide(file=<deck>, id="\ud800")` raises its usual tool error
  `Unknown slide id "\ud800". Valid ids: slide-0`, but the span is not written to the trace file and
  `Exception while exporting Span.` is logged with a `UnicodeEncodeError` traceback, followed by a
  `--- Logging error ---` block on standard error. The same happens for `get_skill(type="\ud800")`,
  `new_file(template="\ud800")`, `export(format="\ud800")`, `restore(id="\ud800")`, and on the
  command line for every path of BUG-004 item 3. With an OTLP destination the encoder logs
  `Failed to encode key ...` with a traceback and drops the attribute (E22).
- **Expected per authority:** SPEC-0009/FR-NEW-007 and the orchestrator mandate ("never a
  traceback"); the tool or command answer itself is already the right one.
- **Reproduction:** as above. Expected: the tool error only, the span in the trace file, no
  traceback. Actual: span lost, traceback logged.
- **Root cause:** tool arguments become span attributes as given (E23); the trace file writer encodes
  them as UTF-8 and handles only operating system errors (E21); the processor then logs the failure
  with its traceback (E21b).
- **Contributing factors:** no test sends an unencodable argument with tracing on.
- **Impact:** lost telemetry and noisy logs; the tool answer is unchanged. Low.
- **Rollback posture:** a revert restores today's behavior.

## 1bis. Class Sweep

**Class A (BUG-001):** request header fields from an untrusted network client reach a request authorization or message framing decision through a single valued lookup, so a repeated, folded or malformed field is judged on one of its values only (CWE-444 inconsistent interpretation of HTTP requests, CWE-20 improper input validation).

**Class B (BUG-002):** a length declared by an untrusted network client, or its absence of data, reaches a blocking read of the request stream with no validation, no cap or no time bound (CWE-400 uncontrolled resource consumption, CWE-770 allocation without limits, CWE-1284 improper validation of specified quantity).

**Class C (BUG-003, BUG-004, BUG-005):** text decoded from untrusted JSON or a command line argument reaches a UTF-8 encoding step (a file, record, trace or log write, a file name handed to the operating system, or a hash key) without a check that it is encodable (CWE-176 improper handling of Unicode encoding, CWE-755 improper handling of exceptional conditions).

**Searches run:** S1 to S10, quoted in the Evidence appendix. S7 and S8 are the full sink sweep of
class C: every hit is a row below.

| Occurrence | Class | Verdict | Disposition |
|---|---|---|---|
| Host read by the request gate (E1) | A | vulnerable: first `Host` wins, userinfo dropped (E7) | BR-001, BR-003 |
| Origin read by the request gate (E2) | A | vulnerable: first `Origin` wins | BR-001 |
| Content-Length read by the request routes (E3) | A | vulnerable: first value wins | BR-001 |
| Content-Type read by the request routes (E4) | A | vulnerable: first value wins | BR-001 |
| Content-Length read by the save route (E5) | A | vulnerable: first value wins, file overwritten | BR-001 |
| Content-Type read by the save route (E6) | A | vulnerable: first value wins | BR-001 |
| Content-Length read by the layout route (E11) | A, B | vulnerable: unvalidated, uncapped | BR-001, BR-006, BR-007 |
| Transfer-Encoding (no reader, S2) | A | vulnerable: ignored instead of refused | BR-002 |
| Folded header lines (no check, E8) | A | vulnerable: value judged with the fold inside | BR-004 |
| Body read of the save route (E5) | B | safe on length: validated and capped at E10b; vulnerable on time: no bound (E12) | BR-008 |
| Body read of the request routes (E3) | B | safe on length: validated and capped at 1 MiB (E10); vulnerable on time (E12) | BR-008 |
| Request line and header read (standard library, E12) | B | vulnerable on time: no bound | BR-008 |
| Save route, `html` text (E14, E15, E16) | C | vulnerable | BR-010 |
| `patch`, command line and agent tool, new document text (E17) | C | vulnerable | BR-011 |
| Request record writer (E13b) via agent tool `write_review` and command `review --write` | C | vulnerable | BR-012 |
| Request record writer via agent tool `complete_request` and command `request-skip --reason` | C | vulnerable | BR-012 |
| Request record writer via `POST /requests`, `/requests/delete`, `/review/apply` | C | safe: every text field checked at E13 before the service is called | BT-032 |
| `restore` write (E15c) | C | safe: content is bytes read back from the history store (E15d) | none |
| Layout write (E15e) | C | safe: the document text was read from disk as strict UTF-8 (E15f) | none |
| Picture write (E15g) | C | safe: bytes from the renderer | none |
| Response encodes of the editor server (E15h) | C | safe: document text read from disk as strict UTF-8 (E15f, E15i); JSON answers use ASCII escapes (E15h) | none |
| State and record keys hash the file path (E15j, E29) | C | vulnerable: a path argument holding an unpaired surrogate raises before any file check | BR-018 |
| File names handed to the operating system: `file`, `output`, `new_file` target, render picture name built from `file` (E29) | C | vulnerable: the file name encoder raises `UnicodeEncodeError` | BR-018 |
| Trace file writer, span attributes from tool arguments (E21, E21b, E23) | C | vulnerable: span lost, traceback logged; the tool answer is intact (the processor catches) | BR-019 |
| OTLP trace encoder (E22) | C | vulnerable: attribute dropped, traceback logged | BR-019 |
| Log handlers (E30b) | C | safe on outcome: the standard library swallows the error in `handleError` and never raises to the caller; the only observed trigger is the span export message, closed by BR-019 | BR-019 |
| State record writer (E24) | C | safe: `json.dump` with its default ASCII escapes writes only ASCII; its `file` value was hashed first (E15j), which BR-018 guards | none |
| Export staging write (E25) | C | safe: the source is read with replacement of undecodable bytes, so it holds no lone surrogate | none |
| Skill size audit encode (E26) | C | safe: texts read strictly from the bundled skill files; topic names from a constant | none |
| Reference document and header parts (E27) | C | safe: built from charter constants and parts decoded strictly from pandoc's reference document | none |
| Byte writes: history versions, new file, atomic writer, save route, patch, record writer (E28) | C | safe at the write: bytes; their encode steps are the rows above (E15, E17, E13b) | covered above |
| Encodability check of the request routes (E13) | C | the control itself | none |
| `outline` output, `click.echo(json.dumps(..., ensure_ascii=False))` (E32) | C | safe once BR-018 holds: every value comes from the document decoded as strict UTF-8 (E15f) except `file`, the path argument itself, which BR-018 refuses before the document is read | BR-018 (BT-037) |
| `render --json` output (E32) | C | safe once BR-018 holds: `path` is built from the file stem (E29), BR-018 guarded; `slide` and `message` come from the strictly decoded document and constants | BR-018 (BT-037) |
| `lint --json` output (E32) | C | safe: `code`, `severity`, `slide`, `message` come from the strictly decoded document and constants; the path is not printed | none |
| `patch` output (E32) | C | safe: printed only after the whole new text was encoded at E17, so every `problems` message is encodable; the path is not printed | none |
| Skill size audit JSON (E33) | C | safe: names from the constant `TOPICS`, problems from bundled files read as strict UTF-8 (E26) | none |
| Reference document cache key (E34) | C | safe: `json.dumps` with default ASCII escapes of charter constants, a version constant and pandoc's version line | none |
| Browser opening of the agent tool `start_server` (E35) | C | safe: the address is the constant `localhost` and an integer port | none |
| Browser opening of `serve` and `new --serve` (E35) | C | vulnerable upstream: the bind address from `--host` or `HTMLEDITOR_HOST` reaches the socket bind first, which raises `TypeError: encoding of hostname failed` with a traceback before the browser call (E36); the agent tool `start_server` reads the same `HTMLEDITOR_HOST` | BR-021 (BT-041) |
| History claim file `os.open` (E37) | C | safe: the name is built from a generated version id and a constant suffix inside the history folder, whose name is a hash (E15j) | none |
| Request record lock `os.open` (E37) | C | safe: the path is the record folder, named by the hash of E15j, plus a constant name; the hash is BR-018 guarded | none |

## 2. Expected Behavior

Casing: header names in their canonical wire casing (`Host`, `Origin`, `Content-Length`, `Content-Type`, `Transfer-Encoding`), header name comparison case insensitive, JSON keys lowercase, as in the existing answers. "Protected route" means every `GET` and `POST` request except `GET /health`, including unknown paths (answered `404` today after the gate); `OPTIONS` on any path and methods other than `GET`, `POST` and `OPTIONS` are not protected routes (BR-005). "Cannot be encoded" means the text holds a code point between U+D800 and U+DFFF not part of a valid pair. "No side effect" means: the served file, its history and its request record are byte for byte unchanged, and nothing is computed or written for the request.

#### BR-001 [EARS-O]: Repeated identity or framing header refused
> IF a request to a protected route carries more than one `Host`, `Origin`, `Content-Length` or `Content-Type` header field line THEN THE editor server SHALL answer `400` with body `{"error":"Duplicate <Name> header"}` and no side effect.

- **Source:** restored from RFC 9112 section 3.2 (Host) and 6.3 (Content-Length); extended to `Origin`
  and `Content-Type` decided here (orchestrator mandate: "duplicate/ambiguous framing or identity
  headers are refused with 400 before any state change").
- **Business Rules:** `<Name>` is the canonical name above, whatever casing the client sent. Repeated
  lines are refused even when their values are identical. When several names repeat, the first in the
  order `Host`, `Origin`, `Content-Length`, `Content-Type` is named. Applies to every `GET` and `POST`
  request to a protected route; never to `OPTIONS` or the other methods (BR-005).
- **Exact names:** `{"error":"Duplicate Host header"}`, `{"error":"Duplicate Origin header"}`,
  `{"error":"Duplicate Content-Length header"}`, `{"error":"Duplicate Content-Type header"}`.

#### BR-002 [EARS-O]: Transfer coding refused
> IF a request to a protected route carries a `Transfer-Encoding` header field, whatever its value THEN THE editor server SHALL answer `400` with body `{"error":"Transfer-Encoding not supported"}` and no side effect.

- **Source:** restored from RFC 9112 section 6.1 (an unsupported transfer coding, or a message with
  both `Transfer-Encoding` and `Content-Length`, is an error); status `400` rather than `501` decided
  here (orchestrator mandate, one status for every ambiguous framing).
- **Business Rules:** the body is not read.
#### BR-003 [EARS-O]: Invalid Host value refused
> IF a request to a protected route carries a single `Host` header whose value contains `@` THEN THE editor server SHALL answer `400` with body `{"error":"Invalid Host header"}` and no side effect.

- **Source:** restored from RFC 9112 section 3.2 ("a Host header field with an invalid field value")
  and RFC 9110 section 7.2 (`Host = uri-host [ ":" port ]`, no userinfo).
- **Business Rules:** every other `Host` value keeps the SPEC-0005/BR-002 behavior, including the
  `403 {"error":"forbidden host"}` answer to a missing `Host` and to a foreign name.

#### BR-004 [EARS-O]: Folded header refused
> IF a request to a protected route carries a header field line folded onto a following line that starts with a space or a tab THEN THE editor server SHALL answer `400` with body `{"error":"Invalid header folding"}` and no side effect.

- **Source:** restored from RFC 9112 section 5.2 (reject obsolete line folding with 400); the choice
  of rejection over replacement decided here.

#### BR-005 [EARS-U]: Header checks come first
> The editor server SHALL evaluate BR-004, then BR-001, then BR-002, then BR-003 on every request to a protected route, before the SPEC-0005 host and origin checks and before any other check of SPEC-0009/FR-NEW-007.

- **Source:** decided here: an ambiguous request cannot be judged by the host and origin gate.
- **Business Rules:** the first failing check answers. `GET /health` is answered before every check
  of this spec, as SPEC-0005/BR-006 requires ("whatever the `Origin` and `Host` headers"). `OPTIONS`
  keeps its SPEC-0005/BR-005 answer `405` with `Allow: GET, POST`. Any other method (`HEAD`, `PUT`,
  `DELETE`, ...) keeps the standard library answer `501` sent before any route runs (E30), whatever
  its headers: BR-001 to BR-004 do not apply to it, BR-008 and BR-020 do (its line and headers are
  read like any other).

#### BR-006 [EARS-O]: Layout length validated
> IF `POST /arch-layout` carries a `Content-Length` that is not a non empty string of ASCII digits THEN THE editor server SHALL answer `400` with body `{"error":"Invalid Content-Length"}` and no side effect.

- **Source:** restored from SPEC-0009/FR-NEW-007 (the same rule and the same message as the save
  route), extended to this route as BL-0023 asks.
- **Business Rules:** an absent `Content-Length` is length 0 and is served, as today: the bundled
  editor sends `POST /arch-layout` with no body and no `Content-Type`, and that request keeps working.
  The route still ignores its body and still does not check `Content-Type`.

#### BR-007 [EARS-O]: Layout length capped
> IF `POST /arch-layout` declares a `Content-Length` greater than 1 048 576 THEN THE editor server SHALL answer `413` with body `{"error":"Request too large"}` without reading the body and with no side effect.

- **Source:** message restored from SPEC-0009/FR-NEW-007; cap decided here: the request route cap of
  SPEC-0010 (1 048 576 bytes), because the body is unused.
- **Business Rules:** a declared length up to 1 048 576 is read and discarded, then the layout runs.
#### BR-008 [EARS-E]: Stalled request bounded
> WHEN 30 seconds pass without any byte received while the editor server waits for a request line, a header line or a declared body THE editor server SHALL answer `408` with body `{"error":"Request timeout"}`, close the connection, and leave no side effect.

- **Source:** decided here: 30 seconds per wait, fixed for users (orchestrator mandate "prefer a
  constant"): no user visible setting changes it; only the test suite may shorten it (BR-022).
  Status from RFC 9110 section 15.5.9.
- **Business Rules:** the 30 seconds restart at each byte received (a slow but progressing upload is
  not cut, within the total bound of BR-020). The answer is best effort: when the client already
  closed, nothing is sent. Other connections are served normally during and after the wait. A
  connection that sent zero bytes (an idle or speculative browser connection) is closed with no answer
  and no log line. The same 30 seconds apply to sending an answer: a client that reads nothing of an
  answer for 30 seconds has its connection closed, with no further answer possible and no traceback.
#### BR-009 [EARS-UB]: No request ends without an answer
> The editor server SHALL NOT close a connection without an HTTP answer, or write a traceback to its log, because of the content of a request's line, headers or body.

- **Source:** restored from SPEC-0009/FR-NEW-007 ("refuse it with a precise status") and the
  orchestrator mandate ("never a dropped connection with a traceback").
- **Business Rules:** covers every case of BR-001 to BR-008, BR-010 and BR-020; an unexpected failure
  while handling a request answers `500` with `{"error":"<message>"}` as SPEC-0009/FR-NEW-001 does
  for write failures. The two closes without answer that BR-008 states (zero byte connection, client
  not reading) are the only exceptions.

#### BR-010 [EARS-O]: Save of unencodable text refused
> IF `POST /content` carries an `html` string that cannot be encoded as UTF-8 THEN THE editor server SHALL answer `400` with body `{"error":"Text cannot be encoded as UTF-8"}`, leave the file unchanged, and add no history version.

- **Source:** restored from SPEC-0009/FR-NEW-007 (precise refusal, file unchanged); message decided
  here (`Invalid JSON body` would name the wrong problem: the JSON is valid).
- **Business Rules:** "cannot be encoded" means the string holds a code point between U+D800 and
  U+DFFF not part of a valid pair. A valid pair and U+0000 are accepted. Position in the
  SPEC-0009/FR-NEW-007 order: right after `Invalid JSON body`, before the template check.

#### BR-011 [EARS-O]: Patch of unencodable text refused
> IF the operations given to `patch` put text that cannot be encoded as UTF-8 into the document THEN THE `patch` command SHALL print `error: Text cannot be encoded as UTF-8` on standard error with exit status 1, and THE `patch` agent tool SHALL raise a tool error with message `Text cannot be encoded as UTF-8`, both leaving the file and its history unchanged.

- **Source:** restored from SPEC-0007 (patch failures are `error: <message>` lines, exit status 1; the
  tool error carries the line without `error: `); message decided here.
- **Business Rules:** same answer with `--dry-run` (tool `dry_run: true`). Standard output stays
  empty on the command line.

#### BR-012 [EARS-O]: Record text that cannot be encoded refused
> IF the command `review --write`, the command `request-skip --reason`, the agent tool `write_review` or the agent tool `complete_request` receives text that cannot be encoded as UTF-8 THEN THE command SHALL print `error: Text cannot be encoded as UTF-8` with exit status 1, and THE agent tool SHALL raise a tool error with message `Text cannot be encoded as UTF-8`, both leaving the request record unchanged.

- **Source:** restored from SPEC-0010 (record errors are `RequestError` lines on every surface, kind
  `invalid`); message decided here.
- **Business Rules:** the HTTP request routes keep their existing answer
  `400 {"ok":false,"error":"Invalid request body"}` (exact existing message kept).

#### BR-013 [EARS-O]: Refusals logged without content
> IF a request is refused by BR-001 to BR-004, BR-006 to BR-008 or BR-010 THEN THE editor server SHALL log exactly one warning line starting `Refused <METHOD> <path>: ` followed by the error text of the answer, and SHALL NOT log the request body or a traceback.

- **Source:** restored from SPEC-0005/BR-008 (refusals logged without content), applied to the new
  refusals. A timeout on a connection that sent part of a request line but not all of it logs
  `Refused - -: Request timeout`; a connection that sent zero bytes logs nothing (BR-008). Also
  applies to BR-020.

#### BR-014 [EARS-U]: Single, well formed requests unchanged
> The editor server SHALL answer requests carrying at most one line of each header named in BR-001, no `Transfer-Encoding`, no folding and a body sent in full within the bounds of BR-008 and BR-020, exactly as it does today.

- **Source:** restored from SPEC-0005, SPEC-0009, SPEC-0010 (every existing answer and message kept).
#### BR-015 [EARS-U]: Non object save body still refused
> The editor server SHALL answer `POST /content` whose body is valid JSON but not an object with `400 {"error":"Invalid JSON body"}` and leave the file unchanged.

- **Source:** restored from SPEC-0009/FR-NEW-007; BL-0015 is fixed (E14) and becomes this non
  regression statement.

#### BR-016 [EARS-UB]: No partial write on refusal
> The editor, the `patch` command and the agent tools SHALL NOT leave a temporary file next to the user's file, a new history version or a changed request revision after a refusal of this spec.

- **Source:** restored from SPEC-0009/FR-NEW-001 (atomic write, no other file next to it).
#### BR-017 [EARS-U]: Valid Unicode text written unchanged
> The editor server, `patch` and the record writers SHALL write text holding valid surrogate pairs, U+0000 or any other encodable code point as its UTF-8 bytes, as today.

- **Source:** restored from SPEC-0009, SPEC-0007, SPEC-0010 (current behavior, verified on
  2026-11-05 with `<html>😀</html>`).

#### BR-018 [EARS-O]: Path that cannot be encoded refused
> IF a path argument of an agent tool or of a command (`file`, `output`, the target of `new_file` and `new`, the output of `export`) holds text that cannot be encoded THEN THE agent tool SHALL raise a tool error with message `File name cannot be encoded`, and THE command SHALL print `error: File name cannot be encoded` on standard error with exit status 1, both creating, changing and recording nothing and printing no traceback.

- **Source:** restored from SPEC-0007 and SPEC-0010 (failures are one error line, exit 1, the tool
  error carries the same text); refusal and message decided here (BL-0033 brought in scope).
- **Business Rules:** applies to every agent tool and command taking a path, the record tools and
  commands included. Exact answer per command:

  | Commands | Standard error | Exit status |
  |---|---|---|
  | `new`, `outline`, `render`, `get-slide`, `lint`, `patch`, `history`, `restore`, `export` | `error: File name cannot be encoded` | 1 |
  | `requests`, `request-done`, `request-skip`, `review` | `error: File name cannot be encoded` | 1 |
  | `serve`, `arch-layout` (their `FILE` must exist) | `Error: File name cannot be encoded` when the name exists; otherwise the existing usage answer `Error: Invalid value for 'FILE': ...` | 1 when the name exists; 2 otherwise (existing usage status) |

  `render` answers this refusal with status 1, not with its usage status 2: status 2 stays reserved
  to its option errors (`--slide`, `--scale`, conflicting flags), which are unchanged. The `Error: `
  form of `serve` and `arch-layout` is the click error line those two commands already print
  (E35). On the command line an undecodable byte of an argument arrives as a code point
  U+DC80 to U+DCFF and is refused the same way: file names that are not valid UTF-8 are not supported.
  The message names no path (the path itself cannot be printed safely).

#### BR-019 [EARS-UB]: Tracing never breaks an answer or logs a traceback
> The agent tools, the commands and the editor server SHALL NOT change their answer, drop a span, or write a traceback to standard error or to a log, because a span attribute holds text that cannot be encoded.

- **Source:** decided here from the orchestrator mandate ("never a traceback") and SPEC-0009/FR-NEW-007
  (the answer is the precise one); the tool answers themselves are already right (BUG-005).
- **Business Rules:** in the local trace file the span is written as one line of valid UTF-8 JSON
  where each unencodable code point appears as its JSON escape (`\ud800`, six ASCII characters). With
  an OTLP destination the span is sent with that attribute's value holding U+FFFD in place of each
  unencodable code point. A trace export failure of any kind is at most one warning line, never a
  traceback. In the editor server the only text attribute is the served file path (spans
  `file.write`, `export.pptx`, `export.docx`, `mcp.layout_arch_diagram`, `history.restore`, E23,
  E38), which BR-018 keeps encodable; its spans are written like the tool spans, any valid Unicode
  of the path kept as is.

#### BR-020 [EARS-E]: Total request time bounded
> WHEN 5 minutes pass after the first byte of a connection without the request line, the headers and the declared body being received in full THE editor server SHALL answer `408` with body `{"error":"Request timeout"}`, close the connection, and leave no side effect.

- **Source:** decided here, closing the residual risk of BR-008 (a client sending one byte every
  29 seconds holds a handler thread forever); 5 minutes is ten times the slowest legitimate save
  observed by BT-022, fixed for users like the bound of BR-008 (only the test suite may shorten it,
  BR-022). Status from RFC 9110 section 15.5.9.
- **Business Rules:** the bound covers receiving the request only, not running it nor sending the
  answer. Logged as BR-013 states.

#### BR-021 [EARS-O]: Bind address that cannot be encoded refused
> IF the bind address given by the `--host` option of `serve` or of `new --serve`, or by `HTMLEDITOR_HOST`, holds text that cannot be encoded THEN THE command SHALL print `Error: Bind address cannot be encoded` on standard error with exit status 1, and THE agent tool `start_server` SHALL raise a tool error with message `Bind address cannot be encoded`, all starting no server, opening no browser and printing no traceback.

- **Source:** restored from SPEC-0007 (one error line, exit 1, the tool error carries the same text);
  the `Error: ` form is the existing error line of `serve` (E35); message decided here. Found by
  the sweep (E36).
- **Business Rules:** an undecodable byte of the option or of the variable arrives as U+DC80 to
  U+DCFF and is refused the same way. `new --serve` has already created its file when it reaches the
  bind: the file stays, as for any other start failure of `new --serve` today. The message names no
  address.

#### BR-022 [EARS-U]: Time bounds shortenable by the test suite only
> The editor server SHALL let the test suite run it with shorter wait and total bounds than 30 seconds and 5 minutes, and SHALL then behave exactly as BR-008, BR-009, BR-013 and BR-020 state, with the shorter values in place of the real ones.

- **Source:** decided here: the time bound requirements need a check in the default `make check`,
  which cannot wait 30 seconds or 5 minutes per test.
- **Business Rules:** shortening the bounds never changes any other behavior (statuses, bodies, log
  lines, which connections are cut). It is not a user visible setting: no command option, no entry
  of `--help`, no line of the user documentation or of the configuration listing names it; a user
  run always has 30 seconds and 5 minutes. How the suite shortens them is not specified here.

## 3. Edge Cases (beyond those the tests of section 4 exercise)

| Case | Expected behavior | Requirement |
|---|---|---|
| two identical `Content-Length: 42` lines | 400 `Duplicate Content-Length header` | BR-001 |
| two `Host` lines and two `Content-Length` lines | 400 `Duplicate Host header` (first in order) | BR-001 |
| `Transfer-Encoding: identity` with a valid `Content-Length` | 400 `Transfer-Encoding not supported` | BR-002 |
| `POST /arch-layout` with `Content-Length: 007` and 7 bytes | served (digits only, leading zeros allowed as on the save route) | BR-006 |
| `{"html":"<html>\u0000</html>"}` | saved as today | BR-017 |
| `patch --dry-run` with a lone surrogate | `error: Text cannot be encoded as UTF-8`, exit 1 | BR-011 |
| `HEAD /content` or `PUT /content` with two `Host` lines | `501` from the standard library, no header check | BR-005 |
| `GET /export/pptx` whose client stops reading the answer | connection closed after 30 seconds without reading, no traceback, file unchanged | BR-008 |
| a valid pair in a path (`/tmp/x😀.html`) | handled as any other path | BR-018 |

## 4. Tests

Driver unless stated: pytest with a real editor server started on a free port of `127.0.0.1`, as in
the existing save safety tests, serving `deck.html` in `tmp_path`, a copy of the `carbon` slide
bootstrap whose title holds `ORIGINAL-SECRET`. The HTTP client is a raw TCP socket that sends the exact
bytes written in the test (a standard HTTP client merges or rejects duplicated headers and would
neutralize the payload). "Unchanged" means: `deck.html` read from disk equals its bytes before the
request, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and the `revision` of
`GET /requests` is unchanged. `P` is the bound port; `L` is `127.0.0.1:P`. A JSON answer "is" a body
when the parsed JSON equals the parsed expected body (key order and spacing are not compared); a
status line, a log line and a command output line are compared as exact text. Agent tool tests set
`HTMLEDITOR_STATE_DIR` and the log and cache folders to `tmp_path`.

Time bounds: BT-003, BT-015, BT-022, BT-023 and BT-040 observe the real bounds (30 seconds, 5
minutes) and carry a `slow` marker that the default `make check` does not select; they are the
checks of the real values. BT-042 to BT-046 run in the default `make check` and check the same
behaviors with the bounds shortened as BR-022 allows: wait bound `W` = 1 second, total bound `T` =
4 seconds. Budget: each of BT-042 to BT-046 takes less than 7 seconds, and together they add less
than 25 seconds to the default run, measured as the sum of their durations printed by
`pytest --durations=0`; the rest of the new tests are bounded by their own `within 2 seconds`
clauses or need no wait.

### 4.1 End to end reproduction (mandatory)

#### BT-001: A save with a local then a foreign Host does not overwrite the document
- **Reproduces:** BUG-001
- **Driver:** raw TCP socket
- **Fails today because:** the gate reads only the first `Host` and the save runs (E1).
- Given the server serves `deck.html`
- When the client sends `POST /content HTTP/1.1\r\nHost: L\r\nHost: evil.example\r\nContent-Type: application/json\r\nContent-Length: 42\r\n\r\n{"html":"<html><body>PWNED</body></html>"}`
- Then the status is `400` and the body is `{"error": "Duplicate Host header"}`
- And `deck.html` on disk is unchanged and does not contain `PWNED`, and `os.listdir` of the folder of `deck.html` is the same as before the request (no temporary file, BR-016)
#### BT-002: An invalid layout length gets an answer
- **Reproduces:** BUG-002 (also validates BR-009)
- **Driver:** raw TCP socket
- **Fails today because:** the layout route converts the header with no validation and the error closes the connection (E11).
- When the client sends `POST /arch-layout HTTP/1.1\r\nHost: L\r\nContent-Length: abc\r\n\r\n`
- Then within 2 seconds the status is `400` and the body is `{"error": "Invalid Content-Length"}`
- And `deck.html` is unchanged, and the captured server log holds no line containing `Traceback`
#### BT-003: A stalled body is answered and released (slow)
- **Reproduces:** BUG-002
- **Driver:** raw TCP socket
- **Fails today because:** no socket timeout exists (E12).
- When the client sends `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{` and then nothing
- Then between 30 and 35 seconds after the last byte the status is `408` and the body is `{"error": "Request timeout"}`, and the server then closes the connection
- And `deck.html` is unchanged
#### BT-004: A save of a lone surrogate gets an answer
- **Reproduces:** BUG-003 (also validates BR-009, BR-016: the folder of `deck.html` holds only `deck.html` afterwards)
- **Driver:** raw TCP socket
- **Fails today because:** the encode error escapes the save route (E15, E16).
- When the client sends `POST /content` with `Host: L`, `Content-Type: application/json`, a correct `Content-Length` and the body bytes `{"html":"<html>\ud800"}` (the six ASCII characters backslash, `u`, `d`, `8`, `0`, `0`)
- Then the status is `400` and the body is `{"error": "Text cannot be encoded as UTF-8"}`
- And `deck.html` is unchanged and the captured log holds no `Traceback`
#### BT-033: Creating a file under an unencodable name gets a tool error
- **Reproduces:** BUG-004 (also validates BR-018)
- **Driver:** the agent tool `new_file` through the tool server's in process client
- **Fails today because:** the file name encoder raises `UnicodeEncodeError` (E29).
- When `new_file(template="carbon", file="<tmp_path>/n\ud800.html")`
- Then a tool error is raised with message exactly `File name cannot be encoded`
- And the listing of `tmp_path` (read with `os.listdir`) is the same as before the call, and the captured log holds no `Traceback`
#### BT-034: An unencodable tool argument keeps its span and logs no traceback
- **Reproduces:** BUG-005 (also validates BR-019)
- **Driver:** the agent tool `get_slide` through the in process client, local trace file under `tmp_path` (no `HTMLEDITOR_OTEL_DESTINATION`)
- **Fails today because:** the trace file writer raises on the attribute and the processor logs the traceback (E21, E21b).
- When `get_slide(file="<deck.html>", id="\ud800")`
- Then a tool error is raised whose message equals `Unknown slide id "\ud800". Valid ids: slide-0`
- And the trace file read as strict UTF-8 holds one more line, a JSON object with `name` `mcp.get_slide` whose raw text contains the six characters `\ud800`, and captured standard error and logs hold no `Traceback` and no `Logging error`

### 4.1bis Exploit tests

Each is red today (behavior observed in section 1). Driver: raw TCP socket, unless stated.

#### BT-005: Reverse Host order cannot read the document
- **Covers:** Host read by the gate (E1), read path
- **Red before the fix because:** `GET /content` with local then foreign `Host` answers 200 with the document.
- When `GET /content HTTP/1.1\r\nHost: L\r\nHost: evil.example\r\n\r\n`
- Then status `400`, body `{"error": "Duplicate Host header"}`
- And the response bytes do not contain `ORIGINAL-SECRET`, and a following `GET /status` with `Host: L` reports the same `mtime` as before
#### BT-006: Duplicated Origin refused
- **Covers:** Origin read by the gate (E2)
- **Red before the fix because:** answers 200 with the document.
- When `POST /content HTTP/1.1\r\nHost: L\r\nOrigin: http://L\r\nOrigin: https://evil.example\r\nContent-Type: application/json\r\nContent-Length: 42\r\n\r\n{"html":"<html><body>PWNED</body></html>"}`
- Then status `400`, body `{"error": "Duplicate Origin header"}`
- And `deck.html` is unchanged
#### BT-007: Duplicated Content-Length on the save refused
- **Covers:** Content-Length read by the save route (E5)
- **Red before the fix because:** first length wins, `PWNED` written.
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 42\r\nContent-Length: 5\r\n\r\n{"html":"<html><body>PWNED</body></html>"}`
- Then status `400`, body `{"error": "Duplicate Content-Length header"}`
- And `deck.html` is unchanged
#### BT-008: Duplicated Content-Length on a request route refused
- **Covers:** Content-Length read by the request routes (E3)
- **Red before the fix because:** first length wins and the request is queued.
- When `POST /requests HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 23\r\nContent-Length: 2\r\n\r\n{"instruction":"PWNED"}`
- Then status `400`, body `{"error": "Duplicate Content-Length header"}`
- And `GET /requests` with `Host: L` lists no request whose instruction is `PWNED`, and `mcp-htmleditor requests deck.html` prints no `PWNED`
#### BT-009: Duplicated Content-Type refused on both body readers
- **Covers:** Content-Type reads (E4, E6); parametrized over `POST /content` with `{"html":"<html><body>PWNED</body></html>"}` and `POST /requests` with `{"instruction":"PWNED"}`
- **Red before the fix because:** the first `Content-Type` is checked, the second ignored, the write happens.
- When the route is sent with `Content-Type: application/json\r\nContent-Type: text/plain` and a correct single `Content-Length`
- Then status `400`, body `{"error": "Duplicate Content-Type header"}`
- And `deck.html` and the request list are unchanged
#### BT-010: Chunked body refused
- **Covers:** Transfer-Encoding (S2, no reader)
- **Red before the fix because:** answers `400 Invalid JSON body`, a different status body than required.
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n2a\r\n{"html":"<html><body>PWNED</body></html>"}\r\n0\r\n\r\n`
- Then status `400`, body `{"error": "Transfer-Encoding not supported"}`
- And `deck.html` is unchanged
- And the same request with `Content-Length: 42` added before `Transfer-Encoding` and the raw JSON body gets the same answer and leaves `deck.html` unchanged
#### BT-011: Host with userinfo refused
- **Covers:** host parser (E7)
- **Red before the fix because:** answers 200 with the document.
- When `GET /content HTTP/1.1\r\nHost: evil@L\r\n\r\n`
- Then status `400`, body `{"error": "Invalid Host header"}`
- And the response bytes do not contain `ORIGINAL-SECRET`
#### BT-012: Folded Host refused as folding
- **Covers:** folded lines (E8); validates BR-004
- **Red before the fix because:** answers `403 forbidden host`.
- When `GET /content HTTP/1.1\r\nHost: L\r\n evil.example\r\n\r\n`
- Then status `400`, body `{"error": "Invalid header folding"}`
- And the response bytes do not contain `ORIGINAL-SECRET`
#### BT-013: Negative and huge layout lengths answered
- **Covers:** layout route length (E11); parametrized over `-5` and `99999999999999999999`
- **Red before the fix because:** each closes the connection with a traceback.
- Given `deck.html` holds a declarative diagram (one `arch-row` with two `arch-node`, no positions)
- When `POST /arch-layout HTTP/1.1\r\nHost: L\r\nContent-Length: <value>\r\n\r\n`
- Then `-5` answers `400 {"error": "Invalid Content-Length"}` and `99999999999999999999` answers `413 {"error": "Request too large"}`, each within 2 seconds
- And `deck.html` is unchanged (no `data-x` attribute appeared) and the log holds no `Traceback`
#### BT-014: Declared large layout body refused without waiting
- **Covers:** layout route cap (E11)
- **Red before the fix because:** the handler waits for 2 000 000 bytes that never come.
- When `POST /arch-layout HTTP/1.1\r\nHost: L\r\nContent-Length: 2000000\r\n\r\n` and nothing else
- Then within 2 seconds the status is `413`, body `{"error": "Request too large"}`
- And `deck.html` is unchanged
#### BT-015: Stalled connections do not block others
- **Covers:** time bound on every read (E12)
- **Red before the fix because:** the stalled connections are held forever.
- Given 20 connections each sent `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{`
- When a normal `GET /content` with `Host: L` is sent while they stall, and again 35 seconds later
- Then both normal requests answer `200` with `ORIGINAL-SECRET`, and every stalled connection has received `408 {"error": "Request timeout"}` and been closed by the server at the second request
- And `deck.html` is unchanged
#### BT-016: Patch command refuses a lone surrogate
- **Covers:** `patch` encode (E17), command line; validates BR-011
- **Driver:** CLI subprocess
- **Red before the fix because:** prints a Python traceback.
- Given `ops.json` holding the bytes `[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\ud800"}]`
- When `mcp-htmleditor patch deck.html --ops ops.json`, then the same with `--dry-run`
- Then each prints exactly `error: Text cannot be encoded as UTF-8` on standard error, nothing on standard output, exit status 1, and standard error contains no `Traceback`
- And `deck.html` is unchanged, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and `os.listdir` of the folder of `deck.html` is the same as before (BR-016)
#### BT-017: Patch tool refuses a lone surrogate
- **Covers:** `patch` encode (E17), agent tool; validates BR-011
- **Driver:** the agent tool `patch` called through the tool server's in process client
- **Red before the fix because:** raises `UnicodeEncodeError`.
- When `patch(file="<deck.html>", ops=[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\ud800"}])`
- Then a tool error is raised with message exactly `Text cannot be encoded as UTF-8`
- And `deck.html` read from disk is unchanged, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and `os.listdir` of the folder of `deck.html` is the same as before (BR-016)
#### BT-018: Review writes refuse a lone surrogate
- **Covers:** record writer (E13b) via `write_review` and `review --write`
- **Driver:** agent tool in process client; CLI subprocess
- **Red before the fix because:** both raise `UnicodeEncodeError`.
- Given `rev.json` holding `[{"id":"a","slide":null,"title":"t\ud800","why":"w","change":"c"}]`
- When `write_review(file="<deck.html>", suggestions=<the same list decoded>)`, then `mcp-htmleditor review deck.html --write rev.json`
- Then the tool raises a tool error with message `Text cannot be encoded as UTF-8`; the command prints `error: Text cannot be encoded as UTF-8`, exit status 1, no `Traceback`
- And `mcp-htmleditor review deck.html` then prints `No review for deck.html`, and the listings of the folder of `deck.html` and of the state folder (recursive) are the same as before (no temporary record file, BR-016)
#### BT-019: Request completion refuses unencodable reason
- **Covers:** record writer via `complete_request` and `request-skip`
- **Driver:** agent tool in process client; CLI subprocess with a raw byte argument
- **Red before the fix because:** both raise `UnicodeEncodeError`.
- Given two requests queued through `POST /requests` with instructions `one` and `two` (ids `R-0001`, `R-0002`)
- When `complete_request(file="<deck.html>", id="R-0001", status="skipped", reason="because \ud800")`, then `mcp-htmleditor request-skip deck.html R-0002 --reason` followed by the byte argument `bad \xff`
- Then the tool raises a tool error `Text cannot be encoded as UTF-8`; the command prints `error: Text cannot be encoded as UTF-8`, exit status 1, no `Traceback`
- And `GET /requests` lists both requests with `status` `"pending"` and the same revision as before, and the recursive listing of the state folder is the same as before the two calls (BR-016)
#### BT-035: Every protected route refuses each ambiguous header
- **Covers:** Host (E1), Origin (E2), Content-Length (E3, E5, E11), Content-Type (E4, E6), Transfer-Encoding (S2), host parser (E7), each at every route
- **Red before the fix because:** each route reads the first value or ignores the field: the write, the layout, the queue, the deletion or the read happens (section 1, BUG-001).
- Given `deck.html` holds the diagram of BT-013, a pending request `R-0001` queued through `POST /requests` with instruction `keep`, and a review written with `mcp-htmleditor review deck.html --write rev.json` holding `[{"id":"a","slide":null,"title":"t","why":"w","change":"c"}]`
- And the routes, each with its literal body `B` and its correct length `N`: `POST /content` `{"html":"<html><body>PWNED</body></html>"}`; `POST /arch-layout` `{}`; `POST /requests` `{"instruction":"PWNED"}`; `POST /requests/delete` `{"id":"R-0001"}`; `POST /review/apply` `{"id":"a"}`; and, with no body, `GET /`, `GET /static/editor.js`, `GET /content`, `GET /content-frame`, `GET /status`, `GET /export/pptx`, `GET /export/docx`, `GET /requests`, `GET /nope`
- When, parametrized over every route and each of these six header blocks (POST routes add `Content-Type: application/json`, `Content-Length: N` and `B` unless the block replaces them; GET routes send no body): `Host: L\r\nHost: evil.example`; `Host: L\r\nOrigin: http://L\r\nOrigin: https://evil.example`; `Host: L\r\nContent-Length: N\r\nContent-Length: 0` (GET: `Content-Length: 0` twice); `Host: L\r\nContent-Type: application/json\r\nContent-Type: text/plain`; `Host: L\r\nTransfer-Encoding: chunked`; `Host: evil@L`
- Then the answers are, in that order, `400` with `{"error": "Duplicate Host header"}`, `{"error": "Duplicate Origin header"}`, `{"error": "Duplicate Content-Length header"}`, `{"error": "Duplicate Content-Type header"}`, `{"error": "Transfer-Encoding not supported"}`, `{"error": "Invalid Host header"}`
- And `deck.html` is unchanged (no `PWNED`, no `data-x`), `mcp-htmleditor requests deck.html` lists exactly `R-0001` pending with instruction `keep`, `mcp-htmleditor review deck.html` still lists suggestion `a`, the response bytes contain neither `ORIGINAL-SECRET` nor the bytes `PK`, and `tmp_path` holds no new file
#### BT-036: Slide replacement and insertion refuse a lone surrogate
- **Covers:** `patch` encode (E17) through `replace_slide` and `insert_slide`, command line and agent tool
- **Driver:** CLI subprocess; agent tool in process client
- **Red before the fix because:** both raise `UnicodeEncodeError` (reproduced on 2026-11-05).
- Given `A` is `<article class="slide" data-type="slide" data-id="slide-9" data-title="T\ud800"><h1>X\ud800</h1></article>` written in the JSON with the escapes as six ASCII characters each
- When, parametrized over `[{"op":"replace_slide","id":"slide-0","html":"A"}]` and `[{"op":"insert_slide","after":"slide-0","html":"A"}]`: `mcp-htmleditor patch deck.html --ops ops.json`, then `patch(file="<deck.html>", ops=<the same list decoded>)`
- Then the command prints exactly `error: Text cannot be encoded as UTF-8`, nothing on standard output, exit status 1, no `Traceback`; the tool raises a tool error `Text cannot be encoded as UTF-8`
- And `deck.html` is unchanged, `mcp-htmleditor history deck.html` prints `No history for deck.html`, and `os.listdir` of the folder of `deck.html` is the same as before (BR-016)
#### BT-037: Every path argument refuses an unencodable name
- **Covers:** file names handed to the operating system and the key hashes (E29), each path argument
- **Driver:** agent tools in process client; CLI subprocess with raw byte arguments
- **Red before the fix because:** the tools raise `UnicodeEncodeError`; `export` prints an `OSError` traceback (BUG-004).
- When, parametrized: `export(file="<deck.html>", format="pptx", output="<tmp_path>/o\ud800.pptx")`; `new_file(template="carbon", file="<tmp_path>/n\ud800.html")`; `patch(file="<tmp_path>/x\ud800.html", ops=[])`; `get_slide(file="<tmp_path>/x\ud800.html", id="slide-0")`; `write_review(file="<tmp_path>/x\ud800.html", suggestions=[])`; `complete_request(file="<tmp_path>/x\ud800.html", id="R-0001", status="skipped")`; `render(file="<tmp_path>/x\ud800.html")`; and the commands `mcp-htmleditor export pptx deck.html` with the byte argument `o\xff.pptx`, `mcp-htmleditor new carbon` with `n\xff.html`, `mcp-htmleditor request-skip` with `x\xff.html` then `R-0001`, `mcp-htmleditor render` with `x\xff.html`, `mcp-htmleditor outline` with `x\xff.html`
- Then each tool raises a tool error `File name cannot be encoded`; each command prints exactly `error: File name cannot be encoded` on standard error, exit status 1 (`render` included, not 2), no `Traceback`, no `Logging error`
- And `os.listdir(tmp_path)` and `deck.html` are unchanged, and the state folder holds no new file
- And, with the local trace file under `tmp_path`, every tool case whose `file` is the unencodable name adds one line, read as strict UTF-8, for the span `mcp.<tool name>` whose `file.path` attribute raw text contains the six characters `\ud800` (BR-019: the span is kept although `file.path` cannot be encoded)
#### BT-038: OTLP export keeps the span and logs no traceback
- **Covers:** OTLP trace encoder (E22)
- **Driver:** agent tool `get_slide` in process client; `HTMLEDITOR_OTEL_DESTINATION` set to a test HTTP listener on `127.0.0.1` that records every request body and answers `200`
- **Red before the fix because:** the encoder logs `Failed to encode key slide.id` with a traceback and drops the attribute (E22).
- When `get_slide(file="<deck.html>", id="\ud800")` and the tracer provider is flushed
- Then the tool error message equals `Unknown slide id "\ud800". Valid ids: slide-0`
- And the listener received a span named `mcp.get_slide` whose `slide.id` attribute is the string U+FFFD, and the captured logs hold no `Traceback`
#### BT-039: Every argument that becomes a span attribute keeps its span
- **Covers:** span attributes from tool arguments (E23), one case per attribute other than `slide.id` (BT-034)
- **Driver:** agent tools in process client, local trace file under `tmp_path`
- **Red before the fix because:** each span is lost and a traceback logged (reproduced on 2026-11-05).
- When, parametrized: `get_skill(type="\ud800")` (`skill.topic`); `new_file(template="\ud800", file="<tmp_path>/n.html")` (`template.key`); `export(file="<deck.html>", format="\ud800", output="<tmp_path>/o.pptx")` (`export.format`); `restore(file="<deck.html>", id="\ud800")` (`history.id`)
- Then each raises its usual tool error, whose message starts, in turn, `Unknown skill topic "`, `Unknown template "`, `Unknown export format "`, `Unknown history id "`
- And the trace file read as strict UTF-8 gains one line per call whose raw text contains the six characters `\ud800`, captured logs hold no `Traceback`, and `tmp_path` holds no `n.html` nor `o.pptx`
#### BT-041: A bind address that cannot be encoded is refused
- **Covers:** bind address to the socket (E36), through `serve --host`, `new --serve --host`, `HTMLEDITOR_HOST` and the agent tool `start_server`; validates BR-021
- **Driver:** CLI subprocess with a raw byte argument or environment value, each run with a 10 second timeout and `--no-browser`; agent tool `start_server` in process with `HTMLEDITOR_HOST` set to `a\udcff`
- **Red before the fix because:** each prints `TypeError: encoding of hostname failed` with a traceback (E36).
- When `mcp-htmleditor serve deck.html --no-browser --host` with the byte argument `a\xff`; `mcp-htmleditor serve deck.html --no-browser` with `HTMLEDITOR_HOST` holding the bytes `a\xff`; `mcp-htmleditor new carbon <tmp_path>/n.html --serve --no-browser --host` with `a\xff`; `start_server(file="<deck.html>")`
- Then each command exits within the timeout with status 1 and its standard error ends with the line `Error: Bind address cannot be encoded` and holds no `Traceback`; the tool raises a tool error `Bind address cannot be encoded`
- And `get_status()` reports `running` false, no port of 7840 to 7849 accepts a connection, `deck.html` is unchanged, and `<tmp_path>/n.html` exists (created before the bind, BR-021)

### 4.2 New behavior

#### BT-020: Header check details
- **Validates:** BR-001, BR-003, BR-005
- When, in turn: `GET /content` with `host: L` then `HOST: L`; `GET /content` with `Host: L`, `Host: L`, `Origin: https://evil.example`; `POST /content` with a folded `Origin` and two `Host` lines; `GET /health` with two `Host` lines; `OPTIONS /content` with two `Host` lines; `GET /content HTTP/1.1\r\n\r\n` (no `Host`); `PUT /content HTTP/1.1\r\nHost: L\r\nHost: evil.example\r\n\r\n`
- Then the answers are, in turn: `400 Duplicate Host header`; `400 Duplicate Host header` (not 403); `400 Invalid header folding`; `200` with keys exactly `status`, `version`, `file`, `port`; `405` with `Allow: GET, POST` and an empty body; `403 {"error": "forbidden host"}`; `501`
- And `deck.html` is unchanged
#### BT-021: Layout length boundaries
- **Validates:** BR-006, BR-007
- Given the diagram of BT-013
- When `POST /arch-layout` with no `Content-Length`; with `Content-Length: 0`; with `007` and 7 bytes `{"a":1}`; with `1048576` and that many `x`; with `1048577` and nothing sent
- Then the first four answer `200` with keys `ok` (true), `diagrams_updated`, `warnings`; the last answers `413 {"error": "Request too large"}` within 2 seconds
#### BT-022: Progressing slow upload is not cut (slow)
- **Validates:** BR-008
- When a valid save body of 60 bytes is sent 10 bytes at a time, 10 seconds apart (50 seconds in total)
- Then the answer is `200 {"ok": true, "mtime": <number>}` and `deck.html` holds the new content
#### BT-040: A trickling request is cut by the total bound (slow)
- **Validates:** BR-020, BR-013
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n` is sent, then one byte `{` every 20 seconds
- Then between 300 and 305 seconds after the first byte the status is `408` and the body is `{"error": "Request timeout"}`, the server closes the connection, and one warning line equals `Refused POST /content: Request timeout`
- And `deck.html` is unchanged
#### BT-023: Idle connection closed (slow)
- **Validates:** BR-008, BR-013
- When a connection is opened and nothing is sent
- Then between 30 and 35 seconds later the server closes it without sending any byte
- And no log line was added; a second connection that sent `GET /con` and then nothing receives `408 {"error": "Request timeout"}` 30 to 35 seconds later, and exactly one warning log line equals `Refused - -: Request timeout`
#### BT-024: Unencodable save variants and order
- **Validates:** BR-010
- When saves are sent with bodies `{"html":"<html>\udc00"}` and `{"html":"<html>\ud83dX</html>"}`, then `{"html":"<html>\ud800"}` while the served file lies under a folder `templates/bootstrap/`
- Then each answers `400 {"error": "Text cannot be encoded as UTF-8"}` (the last not 403) and the file is unchanged
#### BT-025: Refusal log lines
- **Validates:** BR-013
- Given log capture at WARNING on the editor server logger
- When the requests of BT-001, BT-002 and BT-004 are sent
- Then exactly three warning records were added, equal to `Refused POST /content: Duplicate Host header`, `Refused POST /arch-layout: Invalid Content-Length` and `Refused POST /content: Text cannot be encoded as UTF-8`, and no record contains `PWNED`, `\ud800` or `Traceback`

#### BT-042: A stalled body is answered and released, short bounds
- **Validates:** BR-008, BR-009, BR-022 (default run counterpart of BT-003 and BT-015)
- Given the server runs with the bounds shortened to `W` and `T`
- When 5 connections each send `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{` and then nothing, and a normal `GET /content` with `Host: L` is sent 0.2 seconds later
- Then the normal request answers `200` with `ORIGINAL-SECRET` before any stalled connection is answered
- And each stalled connection receives, between 1 and 3 seconds after its last byte, status `408` with body `{"error": "Request timeout"}`, then the server closes it
- And `deck.html` is unchanged, `os.listdir` of its folder is the same as before, and the log holds no `Traceback`
- And `mcp-htmleditor serve --help` and `mcp-htmleditor new --help` contain no option naming a time bound (no `timeout`, case insensitive)
#### BT-043: Idle and partial connections, short bounds
- **Validates:** BR-008, BR-013, BR-022 (default run counterpart of BT-023)
- Given the server runs with the bounds shortened to `W` and `T`, and log capture at WARNING on the editor server logger
- When a connection is opened and nothing is sent; and a second connection sends `GET /con` and then nothing
- Then the first is closed by the server between 1 and 3 seconds later without any byte received, and adds no log record
- And the second receives `408 {"error": "Request timeout"}` between 1 and 3 seconds after its last byte, and exactly one warning record was added, equal to `Refused - -: Request timeout`
#### BT-044: A trickling request is cut by the total bound, short bounds
- **Validates:** BR-020, BR-013, BR-022 (default run counterpart of BT-040)
- Given the server runs with the bounds shortened to `W` and `T`, and log capture at WARNING
- When `POST /content HTTP/1.1\r\nHost: L\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n` is sent, then one byte `{` every 0.6 seconds (each gap shorter than `W`)
- Then between 4 and 6 seconds after the first byte the status is `408` and the body is `{"error": "Request timeout"}`, the server closes the connection, and exactly one warning record equals `Refused POST /content: Request timeout`
- And `deck.html` is unchanged and `os.listdir` of its folder is the same as before
#### BT-045: A progressing upload is not cut, short bounds
- **Validates:** BR-008, BR-020, BR-022 (default run counterpart of BT-022)
- Given the server runs with the bounds shortened to `W` and `T`
- When a valid save body of 60 bytes, `{"html":"<!DOCTYPE html><html><body><p>SLOW</p></body></html>"}` padded with spaces after the closing brace to 60 bytes, is sent 10 bytes at a time, 0.5 seconds apart (2.5 seconds in total, under `T`), with the headers sent first and a correct `Content-Length`
- Then the answer is `200 {"ok": true, "mtime": <number>}` and `deck.html` contains `<p>SLOW</p>`
#### BT-046: A client that stops reading an answer is released, short bounds
- **Validates:** BR-008 (send side), BR-009, BR-022
- Given the server runs with the bounds shortened to `W` and `T`, and `deck.html` holds, after its body, an HTML comment of 16 MiB of `x` (larger than any socket buffer)
- When a client sends `GET /content HTTP/1.1\r\nHost: L\r\n\r\n`, reads nothing for 4 seconds, then reads until the end of the stream
- Then the bytes read are fewer than the full answer and the stream ends (the server closed the connection)
- And a following `GET /health` answers `200`, `deck.html` is unchanged, and the log holds no `Traceback`

### 4.3 Non regression

#### BT-026: Single headers served as today
- **Protects:** BR-014, SPEC-0005/BR-001, BR-002, BR-007
- When `GET /content` with `Host: L`; with `Host: localhost:P` and `Origin: http://localhost:P`; then a save with one of each header and body `{"html":"<!DOCTYPE html><html><body><p>X</p></body></html>"}`
- Then the reads answer `200` with `ORIGINAL-SECRET`, the save answers `200 {"ok": true, "mtime": <number>}` and `deck.html` contains `<p>X</p>`
#### BT-027: Existing refusal messages unchanged
- **Protects:** BR-014, SPEC-0005, SPEC-0009/FR-NEW-007
- When the save route receives `Content-Length: abc`; `Content-Length: 52428801` with nothing sent; `Content-Type: text/plain` with a correct length; body `not json`; and `GET /content` with `Host: attacker.example:P`; and `Origin: https://evil.example`
- Then the answers are exactly `400 {"error":"Invalid Content-Length"}`, `413 {"error":"Request too large"}`, `415 {"error":"unsupported content type"}`, `400 {"error":"Invalid JSON body"}`, `403 {"error":"forbidden host"}`, `403 {"error":"forbidden origin"}`
#### BT-028: Non object save body (former BL-0015)
- **Protects:** BR-015
- When saves are sent with bodies `[]`, `"text"` and `{"html": 5}`
- Then each answers `400 {"error": "Invalid JSON body"}` and `deck.html` is unchanged
#### BT-029: Bundled editor layout call still works
- **Protects:** BR-006, SPEC-0003 (layout from the browser)
- **Driver:** Playwright Chromium on `http://127.0.0.1:P/`, diagram of BT-013
- When the editor page runs `fetch('/arch-layout', {method: 'POST'}).then(r => r.status)`
- Then the result is `200` and `deck.html` now holds `data-x` attributes on both nodes
#### BT-030: Valid Unicode written
- **Protects:** BR-017
- When a save with body `{"html":"<html>\ud83d\ude00\u0000</html>"}` is sent; and `patch` sets the title to `T\ud83d\ude00`
- Then the save answers `200` and the file bytes contain `F0 9F 98 80`; the patch prints its usual JSON result with `"changed":true`
#### BT-031: Browser editor keeps saving
- **Protects:** BR-014, SPEC-0002, SPEC-0009
- **Driver:** Playwright Chromium, as in the existing SPEC-0005 non regression test
- When edit mode is on, the first editable zone is clicked, End pressed, `AAA` typed, 1500 ms waited
- Then `deck.html` contains `AAA`
#### BT-032: HTTP request routes keep their message
- **Protects:** BR-012
- When `POST /requests` with `{"instruction":"\ud800"}`, `POST /requests/delete` with `{"id":"\ud800"}`, `POST /review/apply` with `{"id":"\ud800"}`
- Then each answers `400 {"ok": false, "error": "Invalid request body"}` and the request list is unchanged
#### BT-047: Valid non ASCII file names still work on every surface
- **Protects:** BR-018, BR-017 (the refusal is limited to unencodable names), SPEC-0007, SPEC-0010
- **Driver:** agent tools in process client, with names passed as Python strings decoded from JSON that writes the emoji as the valid pair `\ud83d\ude00`; CLI subprocess with the names as UTF-8 bytes
- Given `N` is `Présentation été 😀.html`, a copy of `deck.html` under `tmp_path`, and `O` is `sortie été 😀.pptx`
- When, in turn: `new_file(template="carbon", file="<tmp_path>/n é😀.html")`; `get_slide(file="<tmp_path>/N", id="slide-0")`; `patch(file="<tmp_path>/N", ops=[{"op":"set_text","id":"slide-0","selector":"h1","text":"T"}])`; `write_review(file="<tmp_path>/N", suggestions=[{"id":"a","slide":null,"title":"t","why":"w","change":"c"}])`; `export(file="<tmp_path>/N", format="pptx", output="<tmp_path>/O")`; `render(file="<tmp_path>/N")`; and the commands `mcp-htmleditor outline <tmp_path>/N`, `mcp-htmleditor history <tmp_path>/N`, `mcp-htmleditor review <tmp_path>/N`, `mcp-htmleditor render <tmp_path>/N`
- Then every call succeeds with its usual answer: `n é😀.html` and `O` exist, the title of `N` is `T`, `history` lists one version, `review` lists suggestion `a`, the render picture is named `Présentation été 😀-slide-0.png`, and `outline` prints JSON whose `file` equals the path given
- And no output holds `File name cannot be encoded` or `Traceback`
#### BT-048: The editor server writes its spans for a non ASCII served path
- **Protects:** BR-019 (editor server), BR-018
- **Driver:** real editor server serving `<tmp_path>/Présentation été 😀.html` (a copy of `deck.html`), local trace file under `tmp_path`; raw TCP socket
- When a valid save `{"html":"<!DOCTYPE html><html><body><p>X</p></body></html>"}` and then `GET /export/pptx` are sent with `Host: L`
- Then both answer `200`
- And the trace file, read as strict UTF-8, gains one line for the span `file.write` and one for `export.pptx`, each a JSON object whose `file.path` attribute equals the served path, and the captured standard error and logs hold no `Traceback` and no `Logging error`

### 4.4 Existing tests asserting the current behavior

| Test file | Test name | Action | Reason |
|---|---|---|---|
| `tests/test_save_safety_e2e.py` | `test_length_checks_apply_to_the_save_endpoint_only` | Modified | its docstring states the old scope; the assertion (`POST /arch-layout` with `{}` answers 200) is kept, the docstring must say the layout route now validates its length |
| `tests/test_save_safety_e2e.py` | `test_e2e_011_too_large`, `test_e2e_012_invalid_length`, `test_missing_content_length_is_length_zero`, `test_length_is_checked_before_the_content_type`, `test_invalid_json_bodies_are_400`, `test_parse_content_length_*`, `test_check_content_type_*` | Kept | single headers, behavior unchanged (BR-014) |
| `tests/test_http_origin_e2e.py` | all 17 tests | Kept | single `Host` and `Origin` per request (BR-014) |
| `tests/test_requests_core.py` | `test_ut_a06_text_the_record_cannot_hold_is_an_invalid_body` | Kept | its answers are the ones BT-032 protects |
| `tests/test_deck_patch*.py`, `tests/test_deck_patch_tool.py` | all | Kept | no test sends unencodable text (`rg -n 'ud800' tests` hits only `test_requests_core.py`) |
| `tests/test_review_write.py`, `tests/test_requests_cli.py`, `tests/test_requests_tools.py` | all | Kept | encodable text only |
| `tests/test_http_health.py`, `tests/test_http_caching.py`, `tests/test_http_export.py`, every browser e2e file | all | Kept | well formed requests (BR-014) |
| `tests/test_render_picture.py` | `test_path_with_spaces_and_accents` | Kept | writes `Présentation été.html` and asserts the picture name `Présentation été-slide-0.png`: a valid non ASCII name, protected with BT-047 (BR-018 refuses unencodable names only) |
| `tests/test_deck_tools*.py`, `tests/test_deck_patch_tool.py`, `tests/test_history_tools.py`, `tests/test_render_tool.py`, `tests/test_skill_tool.py`, `tests/test_requests_cli.py`, `tests/test_requests_tools.py`, `tests/test_tracing.py` | all | Kept | `rg -n 'ud800\|udcff\|\\xff' tests`: the only unencodable text sent is in `test_requests_core.py`; the other hits are undecodable file contents or picture bytes, not paths or arguments; no test sends an unencodable path or span attribute (BR-018, BR-019) |

## 5. Existing Specs Affected

Existing specs are not modified; this spec supersedes the statements below.

- SPEC-0005/BR-001, BR-002: unchanged in substance; they now apply to the single `Host` and `Origin` that BR-001 to BR-005 guarantee. BR-005 here inserts four checks before them.
- SPEC-0009/FR-NEW-007: "These length and size checks apply to the save endpoint only" is superseded for `POST /arch-layout` (BR-006, BR-007). Its check order gains, at its head, the checks of BR-005, and, after `Invalid JSON body`, the check of BR-010.
- SPEC-0010: its request routes keep every answer; the command `review --write`, the command `request-skip` and the tools `write_review`, `complete_request` gain the BR-012 refusal.
- SPEC-0007: `patch` gains the BR-011 refusal; every tool and command taking a path gains the BR-018 refusal.
- Tracing (no spec of its own, behavior of `src` today, E21): BR-019 adds that an unencodable attribute is kept escaped and never logs a traceback.

## 6. Assumptions

Decisions taken without asking (the user said "go" with the orchestrator defaults):

- **Decision:** duplicated `Origin` and `Content-Type` refused like `Host` and `Content-Length`, and identical duplicates refused too (BR-001). RFC 9112 tolerates identical `Content-Length` values; strict refusal is simpler and no legitimate client of this server sends them.
- **Decision:** any `Transfer-Encoding` refused with `400`, not `501` (BR-002).
- **Decision:** folded lines rejected rather than unfolded (BR-004).
- **Decision:** a missing `Host` keeps `403 forbidden host` (SPEC-0005 message kept), although RFC 9112 asks for `400` (BR-003).
- **Decision:** `GET /health` and `OPTIONS` stay exempt from the new header checks (BR-005); methods other than `GET`, `POST`, `OPTIONS` keep the standard library `501` and are not header checked, since no route runs for them (E30).
- **Decision (path class, BL-0033):** brought in scope (BR-018) rather than deferred: it is the same class as BUG-003 (unencodable text reaching an encoder), the refusal is one message on every surface, and the audit found the deferred entry too narrow (`output`, `new_file`, `new`, `export` were missing). The behavior question BL-0033 left open (refuse or keep the bytes of a non UTF-8 command line file name) is decided as refuse: macOS already rejects such names (`Illegal byte sequence`, reproduced), the record and state keys cannot hold them, and keeping them would need a second naming scheme. Residual: on Linux a file whose name is not valid UTF-8 cannot be opened with these tools; rename it.
- **Decision (tracing):** a trace or log failure never changes an answer and never prints a traceback (BR-019). The span is kept with the text escaped rather than dropped, so a trace of a refused call stays observable.
- **Decision (BR-008 residual):** the 30 second bound restarts at each byte, so a client sending one byte every 29 seconds would hold a thread forever; a total bound of 5 minutes per request (BR-020) closes it. Residual accepted: up to 5 minutes per held thread, one thread per connection, local clients only.
- **Decision (idle and send side):** a connection that sent zero bytes is closed silently after 30 seconds (browsers open speculative connections; a warning per such connection would be noise), and the 30 seconds also cut a client that stops reading an answer (BR-008).
- **Decision (tests):** the real bounds are exercised only by `slow` tests not selected by the default `make check` (none exists today, E31); the default run exercises the same behaviors with bounds of 1 second and 4 seconds (BT-042 to BT-046, under 25 seconds in total). This is the only way the bounds of BR-008 and BR-020 change: a test only means (BR-022), never a user visible setting, so "fixed for users" holds.
- **Decision (bind address):** an unencodable `--host` or `HTMLEDITOR_HOST` is refused with `Error: Bind address cannot be encoded` (BR-021): found by the sweep of this amendment, same class C, one message on every surface.
- **Decision:** layout route cap is 1 048 576 bytes, the request route cap, since its body is unused (BR-007); absent length still served (BR-006).
- **Decision:** 30 seconds without a byte, fixed for users (only the test suite shortens it, BR-022); answer `408 {"error":"Request timeout"}` (BR-008).
- **Decision:** one new message `Text cannot be encoded as UTF-8` on every surface except the HTTP request routes, which keep `Invalid request body` (BR-010 to BR-012).
- **Assumption:** the in process client of the agent tool server reports a tool error as an error whose message is the tool error text (as the existing tool tests do).
- **Backlog entries:** BL-0033 was created by the first run of this analysis, then consumed by this amendment (its scope widened to every path argument and brought in as BUG-004, BR-018). Consumed: BL-0015, BL-0020, BL-0023, BL-0027, BL-0033. None created.

## 7. Implementability Checklist

| # | Item | Result |
|---|---|---|
| 1 | No technical decision | PASS: no mechanism, file list or order; root causes point to Evidence lines |
| 2 | No buried requirement | PASS: each header check, the order, both time bounds, logging, each surface, paths and tracing have their own BR |
| 3 | Names spelled | PASS: routes, statuses, JSON bodies, header names, CLI flags, tool names, log line formats |
| 4 | No forced choice | PASS: order, casing, identical duplicates, absent length, cap, bound reset, total bound, idle and send side, health, OPTIONS and other methods, dry run, non UTF-8 file names, escaped span attribute stated |
| 5 | Tests specified | PASS: BT-001 to BT-048 with literal inputs, JSON compared parsed; slow tests marked and bounded, every time bound also checked in the default run by BT-042 to BT-046 with a stated budget (section 4); 4.4 covers every HTTP, patch, request, render, tool and tracing test file |
| 6 | Reproduction end to end | PASS: BT-001, BT-002 (with BT-003), BT-004 drive the server over a socket; BT-033 and BT-034 drive the agent tools; each asserts the answer and a second channel |
| 7ante | Security classification | PASS: `Security: internal finding` |
| 7bis | Sweep real | PASS after amendment. An independent read only audit of the first version returned FAIL (3 major, 7 minor findings: omitted class C sinks, BL-0033 too narrow, exploit tests missing per route and per operation, plus definitions, bounds and claims); this amendment closes every finding. (a) three classes, ten searches over different idioms; (b) S7 and S8 rerun on 8652a5b, every hit is a row of 1bis with its verdict; (c) source side searches S6 and S9 found the path arguments and the span attributes, added (BUG-004, BUG-005) and reproduced; (d) safe verdicts cite E13, E15d, E15f, E15h, E15i, E24 to E28, E30b, each opened; (e) every kept occurrence has an exploit test at its own location: each route and header in BT-035, each patch operation in BT-016, BT-017, BT-036, each record surface in BT-018, BT-019, each path argument in BT-037, each span attribute and destination in BT-034, BT-038, BT-039, each with a literal payload and a second channel (disk, folder listing, history, request list, review, trace file, log); (f) no deferral remains: BL-0033 opened, widened and consumed; (g) class statements name a source and a sink, no module |
| 8 | No hidden prerequisite | PASS: server, file, record state in every Given |
| 9 | EARS clean | PASS |
| 10 | Right tool | PASS: behavior changes, no new capability |
| 11 | Length | PASS: within the M budget |
| 12 | Claims cited | PASS: Evidence appendix, lines reread on 8652a5b |
| 13 | Round trip | PASS: writer and reader read for each message and for the record (E13, E13b), the editor layout call (E20), and the trace file writer and its JSON reader (E21) |
| 14 | Verdict consistent | PASS: authority exists (RFC 9112, SPEC-0005, 0007, 0009, 0010); `decided here` limited to messages, bounds and edge cases the authority leaves open |

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 2 (BL-0027 cited the encode at a moved line, now E15; BL-0023 cited lines 358-360, now E11); moved to backlog: none |
| Audit round 2 | second independent audit (FAIL, 1 major, 6 minor), closed by the second amendment: MAJOR by BR-022 and the default run BT-042 to BT-046 with a budget, BR-008, BR-020 and section 6 reworded to "fixed for users"; MINOR 1 by BR-001 ("every `GET` and `POST`"); MINOR 2 by the S11 rerun, every hit a row of 1bis, one new vulnerable row (bind address) closed by BR-021 and BT-041; MINOR 3 by the per command table of BR-018 and the `render` case of BT-037; MINOR 4 by BT-047 and the kept row of `tests/test_render_picture.py`; MINOR 5 by BR-019's editor server rule, BT-048 and the span clause of BT-037; MINOR 6 by the BR-016 listing clause added to BT-001, BT-016 to BT-019, BT-036 and the short bound tests |
| Audit round | 1 independent audit (FAIL), closed by this amendment: MAJOR-1 by BUG-005, BR-019 and the full sink rows; MAJOR-2 by BUG-004, BR-018; MAJOR-3 by BT-035 to BT-039; minors by the definitions of section 2, BR-005, BR-008, BR-020, section 4 and section 6 |

## Evidence

All lines read on commit 8652a5b (2026-11-05), Python 3.14.2.

- E1 `src/mcp_htmleditor/http_server.py:116` `host = self.headers.get("Host", "")`
- E2 `src/mcp_htmleditor/http_server.py:121` `origin = self.headers.get("Origin")`
- E3 `src/mcp_htmleditor/http_server.py:423` Content-Length of the request routes; body read at `:429`
- E4 `src/mcp_htmleditor/http_server.py:421` Content-Type of the request routes
- E5 `src/mcp_htmleditor/http_server.py:459` Content-Length of the save route; body read at `:460`
- E6 `src/mcp_htmleditor/http_server.py:461` Content-Type of the save route
- E7 `src/mcp_htmleditor/http_server.py:837` to `:843` `_split_host` parses `//<host>` with `urlsplit` and keeps only `hostname`, so `evil@127.0.0.1` yields `127.0.0.1`
- E8 standard library `http/client.py:250` `parse_headers` keeps every field line; `.get` returns the first; continuation lines are kept inside the value
- E9 standard library `http/server.py:694` `protocol_version = "HTTP/1.0"`; the handler does not override it (`rg -n protocol_version src` returns nothing); every answer observed is `HTTP/1.0`
- E10 `src/mcp_htmleditor/request_service.py:38` `BODY_MAX_BYTES = 1_048_576`, checked at `src/mcp_htmleditor/http_server.py:424`
- E10b `src/mcp_htmleditor/http_server.py:596` to `:605` `parse_content_length` (absent 0, ASCII digits only else 400, cap `MAX_SAVE_BYTES` 52 428 800 at `:75` else 413)
- E11 `src/mcp_htmleditor/http_server.py:481` `int(self.headers.get("Content-Length", 0))`, read at `:483`
- E12 standard library `socketserver.py:803` `timeout = None`, applied at `:809` to `:812` only when not None; `_EditorHandler` (`src/mcp_htmleditor/http_server.py:97`) sets no timeout (`rg -n settimeout src` returns nothing)
- E13 `src/mcp_htmleditor/http_server.py:585` to `:593` `_is_text`, used at `:343`, `:357`, `:374`; answer `Invalid request body` at `:434`
- E13b `src/mcp_htmleditor/request_store.py:174` `json.dumps(..., ensure_ascii=False).encode("utf-8")`; `_write` at `:153` to `:157` translates only `WriteError`; `RequestError` kinds at `:40`
- E14 `src/mcp_htmleditor/http_server.py:614` to `:628` `parse_save_body`: non object or non string `html` is `Invalid JSON body` (BL-0015 fixed), any string accepted
- E15 `src/mcp_htmleditor/fileio.py:57` `data.encode("utf-8")`, outside the `OSError` handler at `:60` to `:63`
- E15c `src/mcp_htmleditor/history.py:170` restore write; E15d `src/mcp_htmleditor/history.py:139` content read with `read_bytes`
- E15e `src/mcp_htmleditor/arch_layout.py:1203` layout write; E15f `src/mcp_htmleditor/arch_layout.py:1188` `read_text(encoding="utf-8")`, and `src/mcp_htmleditor/deck/__init__.py:45` strict decode of the document
- E15g `src/mcp_htmleditor/render/files.py:35` picture write of bytes
- E15h `src/mcp_htmleditor/http_server.py:537` `json.dumps(payload)` (ASCII escapes by default); E15i `:227`, `:247` encode of document text read from disk
- E15j `src/mcp_htmleditor/request_store.py:89` and `src/mcp_htmleditor/state.py:223` hash the path with `.encode("utf-8")`; `src/mcp_htmleditor/request_service.py:235` to `:240` `require_file`
- E16 `src/mcp_htmleditor/http_server.py:451` save route catches only `(OSError, WriteError)`
- E17 `src/mcp_htmleditor/deck/patch.py:206` `text.encode("utf-8")`, outside the `OperationError` handler at `:199` to `:202`; command wrapper `src/mcp_htmleditor/cli.py:34` to `:45` catches only `DeckError`; tool `src/mcp_htmleditor/mcp_server.py:303` catches only `DeckError`
- E17b `src/mcp_htmleditor/mcp_server.py:515` (`write_review`) and `:487` (`complete_request`) catch only `RequestError`; `src/mcp_htmleditor/cli.py:446` to `:470` (`review`), `:437` to `:443` and `:484` to `:497` (`request-skip`)
- E18 `tests/test_http_origin_e2e.py:180` to `:385`: 17 tests, one `Host` and at most one `Origin` each
- E19 `tests/test_save_safety_e2e.py:269` to `:271` `test_length_checks_apply_to_the_save_endpoint_only`
- E20 `src/mcp_htmleditor/static/editor-menus.js:39` `fetch('/arch-layout', { method: 'POST' })` (no body, no `Content-Type`)
- E21 `src/mcp_htmleditor/tracing.py:75` `json.dumps(..., ensure_ascii=False)` of every attribute, `:77` file opened with `encoding="utf-8"`, `:78` write; `:79` catches only `OSError`; `:164` local export uses `SimpleSpanProcessor`, `:162` OTLP uses `BatchSpanProcessor`
- E21b `opentelemetry/sdk/trace/export/__init__.py:133` (installed SDK) `logger.exception("Exception while exporting Span.")` inside a broad `except Exception`: the tool answer survives, the span is lost, a traceback is logged
- E22 `opentelemetry/exporter/otlp/proto/common/_internal/__init__.py:103` `_logger.exception("Failed to encode key %s: %s", ...)`; the attribute is dropped and the span still encoded (reproduced: 282 bytes)
- E23 span attributes from tool arguments: `src/mcp_htmleditor/mcp_server.py:232` `skill.topic`, `:272` `slide.id`, `:353` `template.key`, `:378` `export.format`, `:430` `history.id`; `file.path` at `:72`, `:136`, `:198`, `:252`, `:272`, `:300`, `:323`, `:353`, `:378`, `:402`, `:430`, `:454`, `:483`, `:511`, `:549`; and `src/mcp_htmleditor/deck/tools.py:51`, `src/mcp_htmleditor/fileio.py:59`, `src/mcp_htmleditor/history.py:168`
- E24 `src/mcp_htmleditor/state.py:261` to `:262` `json.dump(record, handle)` with the default `ensure_ascii=True`; the record's `file` is hashed first at `:223` through `:99`
- E25 `src/mcp_htmleditor/export/to_docx.py:115` source read with `errors="replace"`; staged at `:134`
- E26 `src/mcp_htmleditor/skill_audit.py:87` encodes texts read by `src/mcp_htmleditor/skill_content.py:89` and `:99` (strict UTF-8, bundled files); topic names from the constant `TOPICS` (`skill_audit.py:77`)
- E27 `src/mcp_htmleditor/export/reference_docx.py:489`, `:570` (parts decoded strictly at `:567`, charter constants), `:707` (charter dataclass); `src/mcp_htmleditor/export/docx_header_footer.py:239`, `:336` (constants and charter fields)
- E28 byte writes: `src/mcp_htmleditor/history.py:68`, `:96`; `src/mcp_htmleditor/deck/tools.py:66` (bytes read at `:47`); `src/mcp_htmleditor/fileio.py:75` (bytes from `:57`); `src/mcp_htmleditor/http_server.py:663`; `src/mcp_htmleditor/deck/patch.py:272`, `:276` (bytes from `:206`); `src/mcp_htmleditor/request_store.py:155` (bytes from `:174`); `src/mcp_htmleditor/render/files.py:35`
- E29 path sinks: `src/mcp_htmleditor/request_store.py:89` and `src/mcp_htmleditor/state.py:223` strict UTF-8 hash; `src/mcp_htmleditor/request_service.py:237` to `:238` `resolve` and `is_file` (file name encoder); `src/mcp_htmleditor/deck/tools.py:61` and `:65` (`new_file`, `new`); `src/mcp_htmleditor/deck/tools.py:88` to `src/mcp_htmleditor/export/to_pptx.py:123` (`export` output); `src/mcp_htmleditor/render/files.py:24` to `:29` (picture name from the file stem). Reproduced: `new_file(file="<tmp>/n\ud800.html")` and `export(output="<tmp>/o\ud800.pptx")` raise `UnicodeEncodeError`; `export pptx deck.html $'o\xff.pptx'` prints `OSError: [Errno 92] Illegal byte sequence` with a traceback
- E30 standard library `http/server.py:464` reads the request line, `:478` to `:481` answers `501 Unsupported method` before any `do_` method; E30b `logging/__init__.py:1060` `handleError` prints `--- Logging error ---` and does not raise
- E31 `rg -n 'markers|slow|addopts' pyproject.toml Makefile` returns nothing: no slow marker exists today
- E32 `src/mcp_htmleditor/cli.py:289` (`outline`, the dict of `src/mcp_htmleditor/deck/read.py:19` to `:30`, `file` included, document from `src/mcp_htmleditor/deck/__init__.py:45`), `:316` (`render --json`, `src/mcp_htmleditor/render/problems.py:63` to `:74`), `:353` (`lint --json`, `src/mcp_htmleditor/deck/lint.py:101` to `:109`), `:371` (`patch`, result built at `src/mcp_htmleditor/deck/patch.py:210` to `:218` after the encode at `:206`): `click.echo(json.dumps(..., ensure_ascii=False))`
- E33 `src/mcp_htmleditor/skill_audit.py:218` `json.dumps(payload, ensure_ascii=False)`, payload at `:205` to `:217`
- E34 `src/mcp_htmleditor/export/reference_docx.py:705` `json.dumps(dataclasses.asdict(charter), sort_keys=True)`, hashed at `:707`
- E35 `src/mcp_htmleditor/mcp_server.py:81` to `:82` `webbrowser.open("http://localhost:<port>/")`; `src/mcp_htmleditor/cli.py:229` to `:230` `webbrowser.open(f"http://{host}:{bound_port}/")` after the bind at `:221` to `:226`, whose `OSError` and `RuntimeError` become `click.ClickException` (`Error: <message>`, exit 1); `--host` at `:127` (`new`) and `:173` (`serve`); `HTMLEDITOR_HOST` at `src/mcp_htmleditor/config.py:338`
- E36 `src/mcp_htmleditor/http_server.py:874` `probe.bind((host, port))` catches only `OSError`. Reproduced on 2026-11-05: `mcp-htmleditor serve deck.html --host $'a\xff' --no-browser` and the same with `HTMLEDITOR_HOST=$'a\xff'` print `TypeError: encoding of hostname failed` with a traceback
- E37 `src/mcp_htmleditor/history.py:55` `os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)`, claim name at `:53`; `src/mcp_htmleditor/request_store.py:145` `os.open(path, os.O_RDWR | os.O_CREAT, LOCK_MODE)`
- E38 editor server spans: `src/mcp_htmleditor/http_server.py:262` `export.pptx`, `:293` `export.docx`, `:486` `mcp.layout_arch_diagram`, each with `file.path` of the served file only; `src/mcp_htmleditor/fileio.py:59` `file.write` (`file.path`, `file.size`)
- Live reproductions: scripts `/tmp/spec13/repro.py`, `/tmp/spec13/repro2.py`, `/tmp/spec13b/repro3.py`, `/tmp/spec13b/otlp.py`, `/tmp/spec13b/p.py` (outside the repository, `HTMLEDITOR_STATE_DIR` in a temporary folder), outputs quoted in section 1.

### Searches (8652a5b, `src`, `tools`, `Dockerfile`, `docker-compose.yml`)

- S1 `rg -n 'self\.headers|headers\.get\(|headers\[' src tools`: every header read (idiom: single value lookup). Seven hits, all in the editor server (E1 to E6, E11).
- S2 `rg -n -i 'transfer-encoding|get_all\(|chunked' src tools`: multi value reads and transfer coding (idiom: framing). Zero hits.
- S3 `rg -n 'rfile\.|\.read\(length|recv\(|makefile' src`: every read of the request stream (idiom: body read). Three hits (E3, E5, E11).
- S4 `rg -n 'settimeout|timeout\s*=|HTTPServer|socketserver|BaseHTTPRequestHandler|uvicorn|websocket' src Dockerfile docker-compose.yml`: listeners and time bounds (idiom: a second server, a timeout). One listener, no timeout (E12); the agent tool server uses standard input and output, not a socket.
- S5 `rg -n '\.encode\("utf-8"\)|\.encode\(\)|write_text\(|atomic_write\(' src`: every UTF-8 encode and file write (idiom: encode at the sink). Hits listed in the table.
- S6 `rg -n 'json\.loads|click\.argument|click\.option|def .*\(file: str' src/mcp_htmleditor/cli.py src/mcp_htmleditor/mcp_server.py src/mcp_htmleditor/http_server.py`: every untrusted text source (idiom: the source side), cross checked against S5.
- S7 `rg -n 'encode\(|write_text\(|json\.dump\(|atomic_write\(|open\([^)]*(encoding|"w|"a)' src`: every UTF-8 encode, text write and JSON dump (idiom: encode at the sink). 29 hits, each a row of 1bis (E13, E13b, E15, E15c, E15e, E15h, E15i, E15j, E17, E21, E24 to E28).
- S8 `rg -n 'open\(|\.write\(' src`: every raw write (idiom: write through a handle). 27 hits: the editor's JavaScript (`doc.open`, `doc.write`, comments, not a file), the response writes (E15h), two descriptor opens that write nothing (`history.py:55` claim file, `request_store.py:145` lock), the trace file writer (E21), and the byte writes of E28.
- S9 `rg -n 'trace_span\(|set_attribute\(' src`: every telemetry sink (idiom: argument copied into a span). 40 and 16 hits, the argument fed ones in E23.
- S10 `rg -n 'click\.Path|def .*\((file|output)' src/mcp_htmleditor/cli.py src/mcp_htmleditor/mcp_server.py`: every path argument (idiom: file name to the operating system), 39 hits, cross checked against E29.
- S11 `rg -n "encode\(|write_text|json\.dump|atomic_write|fsencode|open\(|webbrowser" src/mcp_htmleditor --glob '!*.js'` (second audit's sweep, rerun on 8652a5b): 54 hits. Imports, docstrings and definitions aside, each hit is a row of 1bis: E13, E13b, E15, E15c, E15e, E15h, E15i, E15j, E17, E21, E24 to E28, E32 to E35, E37. The single JavaScript hit is the editor's `doc.open`, not a file.
- Not searched: response headers (the server writes them itself), cookies (none exist, SPEC-0005).
