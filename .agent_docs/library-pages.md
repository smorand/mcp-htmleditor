# Web library pages (SPEC-0025)

Home page, folder page, administration, folder deletion and members of the web library mode; the module map, gate order,
storage and test support are in `.agent_docs/library.md`.

## Home page and roles (US-0127, DEC-018, DEC-029, DEC-023)

- The administrator is decided in `store.py` only: `Library.is_admin(email)` compares `normalize_email(email)`
  (`strip().lower()`, nothing else: no dot removal, no `googlemail.com` rewriting) with `access.ADMIN_EMAIL`;
  `role_in` returns `Role.ADMIN` before reading `members`, so a member row (even RO for the administrator) never
  changes it (FR-NEW-014), and `members.role` is `CHECK (role IN ('RW','RO'))` (FR-NEW-012). Roles are read at every
  request, so a role given later shows at the next page.
- `folders_for(email)`: every folder with `Role.ADMIN` for the administrator, the member rows otherwise, sorted in
  Python by `names.order_key(name)`: NFD, drop `Mn`, `lower()`, NFC, compared by code point (digits, Latin letters,
  other alphabets), then the exact name (`Cafe` before `Café`). Never `casefold`: `ß` is not `ss`. O(n log n) per page.
- `GET /`: `home_page(folders, is_admin=)`: `<nav><a href="/admin">Administration</a></nav>` for the administrator
  only; rows `<li><a href="/f/<id>">name</a> <span>role label</span></li>` in a `ul.folders`; no folder: the
  administrator gets `<p>You have no access to any folder yet.</p>` (200), anyone else `403` `Access denied.`
  (FR-NEW-003).
- Any path in no row: `Access denied.` for a signed in person, the sign in page for a visitor (`next` = the path).
- `/lib/library.css` (`text/css`) and `/lib/library.js` (`application/javascript`) are the two public rows; a missing
  file is `404 {"error": "Not found"}`; any other `/lib/...` is no row.
  `static/library.css` uses logical properties only (RTL names) and `unicode-bidi: plaintext` on folder links.

## Folder page (US-0129, DEC-020, DEC-023, DEC-031, DEC-052)

- `GET /f/<fid>`: VIEW checked by the dispatcher; the handler `folder` reads `folder_name` (None: `Access denied.`,
  the administrator's role does not prove the folder exists) then `presentations_in`. Unknown id, no role and a
  malformed id (no row) give the same bytes, status and headers (only `Date` differs).
- Page: `<nav><a href="/">All folders</a></nav><h1>name</h1>`, then `<ul class="presentations">` rows
  `<li><span class="name">n</span> <time datetime="2026-11-12T16:40:59Z">12 Nov 2026 16:40</time> <span
  class="size">1.1 KB</span></li>` or `<p>This folder has no presentations yet.</p>` (no list at all), then Sign out.
  The `<time>` text is UTC, computed with `time.gmtime` (no wall clock read); `library.js` rewrites it from `Date`
  getters, so the zone is the browser's (Playwright `timezone_id`).
- Order: `-(math.floor(st_mtime) // 60)` (a time before 1970 rounds down), then `order_key(name)` (accents and case ignored, then the exact name), sorted in
  Python. `format_size`: integer half up `(count * 20 + unit) // (2 * unit)` tenths (`round` is half even: 1 280 bytes
  would read 1.2 KB).
- Cost: `role_in` (primary key), `folder_name` (primary key), one `SELECT id, name FROM presentations WHERE folder_id`
  (prefix of the `UNIQUE (folder_id, name_key)` index), one `stat` per row, O(n log n) sort. A row whose file is gone
  is an `OSError`, a row whose id is malformed a `sqlite3.DatabaseError`: the whole page is the unavailable page.

## Administration (US-0130, DEC-019, DEC-029, DEC-030)

- `GET /admin`: `admin_page(folders_for(admin), activity())`: `All folders`, `<h1>Administration</h1>`, `<section
  id="folders">` (rows as on the home page, `ul.folders`; the form `#create-folder` with `<label for="folder-name">`,
  the input and `Create folder`; a hidden `p#create-folder-alert role="alert"` carrying `data-denied` and
  `data-unavailable` so the JS fallbacks stay in `pages.py`), `<section id="activity">` (`ol.activity` rows `<li><time
  datetime>..</time> <span class="actor">..</span> <span class="text">..</span></li>` or `No activity yet.`), Sign out.
- `POST /api/folders {"name"}`: a name that is not a string is `Invalid request body`; `check_folder_name`
  (`compose(raw.strip())`, 1 to 60 characters, each `L*`, `M*`, `Nd`, U+0020 or U+002D) else 400 with the name rule;
  `create_folder` inserts the row and the line in one `BEGIN IMMEDIATE`; the `name_key` unique constraint
  (`IntegrityError`) is `NameTaken`, 400 `A folder named "<trimmed composed name>" already exists.`; success `201
  {"ok": true, "id"}`. `library.js` sends it with `fetch` (JSON), reloads on success, writes the error with
  `textContent` into the alert (a non JSON answer: the alert's data text for 403, else the unavailable text).
- Activity (migration 3): `activity(id AUTOINCREMENT, at, actor, text)`; `record` inserts (actor lower cased, `at` from
  the clock) then `DELETE ... WHERE id <= MAX(id) - 500` in the caller's transaction; `activity()` is `ORDER BY id DESC
  LIMIT 500`. Only successful actions call `record` (refusals, sign ins and saves never do). AUTOINCREMENT adds the
  `sqlite_sequence` table. Cost per creation: one insert, one indexed delete; the page is O(folders log folders + 500).

## Folder deletion (US-0131, DEC-023, DEC-026, DEC-029)

- Admin page: each folder row ends with `<button class="delete-folder" data-folder-id>Delete folder</button>` (admin
  rows only, `_folder_rows(has_delete=True)`; the home rows and `FOLDER_ROW` are unchanged). One `<dialog
  id="delete-folder">`: the field labelled by the prompt `Type the folder name to confirm.` (not `Folder name`: that
  would make `get_by_label("Folder name")` ambiguous), its alert (`data-denied`, `data-unavailable`), `Delete folder`
  (submit) and `Cancel`. `library.js` opens it with `showModal()` and focuses the field; `Cancel` or Escape closes it
  with no request and focus goes back to the row's button; submit sends `{"confirm": typed}`.
- `POST /api/folders/<fid>/delete`: `confirm` not a string is `Invalid request body`; unknown id `Access denied.`
  (`FolderMissing`, DEC-023); `compose(confirm) != name` (no trim, case and accents count) 400 `The name does not
  match. Nothing was deleted.` (`NameMismatch`, nothing written); success `200 {"ok": true}`.
- Order in `Library.delete_folder` (never reverse it): one `BEGIN IMMEDIATE` (read the name, check, collect the
  presentation ids, `record` `Deleted folder "<name>"`, `DELETE FROM folders` and the cascade of `members` and
  `presentations`), commit; then, inside `trace_span("library.delete_folder", {"presentations": n})`, `rmtree` of
  `files/<fid>/` and of `<state_dir>/files/<key>/` per presentation (key = `RequestStore.record_dir(path).parent`, the
  SPEC-0009 key of the resolved path: history, requests, AI suggestions, update flag). Paths come only from ids that
  match `^[0-9a-f]{32}$` (a malformed stored id is skipped with a warning). A removal failure is one WARNING `Could
  not remove a directory of a deleted folder: <ExcType>`, never an error answer: the rows are gone, ids are never
  reused, so a leftover is unreachable. Former members get `Access denied.` at their next request (no row).
- Cost: one transaction (primary key read, one indexed select of the ids, one delete with cascade), then O(files)
  removal (E2E-104: 100 presentations with history and requests).

## Members (US-0132, DEC-018, DEC-019, DEC-029, DEC-030)

- Admin page: each folder row (`_admin_row`) ends with `<section class="members" id="members-<fid>">`: `<h3>Members`,
  `<ul class="members">` rows `<li><span class="email">..</span> <select class="member-role" aria-label="Role of <email>"
  data-folder-id data-email>` (options `RW` `Read and write`, `RO` `Read only`, the member's `selected`) `<button
  class="remove-member">Remove</button></li>`, then `form.add-member` (`Email address`, `Role` with the same two options,
  `Add member`) and the alert `members-alert-<fid>`. `members_by_folder()` is one `SELECT ... ORDER BY email` (BINARY
  collation: code point order, the `members_email` index) grouped in Python: O(m) for the whole page, no query per folder.
- `POST /api/folders/<fid>/members {"email", "role"}` and `.../members/remove {"email"}` (ADMINISTER, so a RW member
  posting `Admin` gets `Access denied.` before the role is read). Handler order: `folder_name` None is `Access denied.`;
  `check_email` (`strip()`, fullmatch `[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+`, ASCII only, `lower()`; not a
  string too) else 400 `This is not a valid email address.`; the role exactly `RW` or `RO` (`pages.MEMBER_ROLES`) else
  400 `This is not a valid role.`. Success `200 {"ok": true}`.
- `set_member`: one `BEGIN IMMEDIATE` (folder name, current role, upsert `ON CONFLICT(folder_id, email) DO UPDATE`, line
  `Added <email> as RW to "<folder>"` or `Changed <email> to RO in "<folder>"`); the same role returns before writing.
  `remove_member` writes `Removed <email> from "<folder>"` only when a row went. A folder deleted between the handler's
  read and the transaction is `FolderMissing`, `Access denied.`. The `CHECK (role IN ('RW','RO'))` is the last guard.
- The administrator's address may be stored as a member: `role_in` answers Admin before reading `members` (DEC-006).
  Roles are read at every request, so a change applies to the person's next page without a new sign in (DEC-018).

## Upload (US-0141, DEC-033, DEC-034, DEC-054)

- Folder page: for `RW` or `Admin` a section `#upload` (label `Upload`, `<input type=file id=upload-file>`, `role=status`
  area `#upload-status`); `library.js` sends the chosen file with `XMLHttpRequest` to `POST /api/folders/<fid>/presentations`
  (raw body, `X-File-Name` percent encoded) and writes the answer with `textContent`; success swaps the list for the server's.
- Route (`routes_library.upload_presentation`, `Route.is_upload`, `EDIT`): Origin rule and `X-File-Name` in the dispatcher, then
  folder exists, extension (`.html` in any case), name, size (26 214 400), body read by `Context.read_body`, validity
  (`uploads.check_validity`: UTF-8, declared, one slide, first lint error message only), collision (`409 {"collision"}`).
- `Library.add_presentation`: file first (`atomic_write`, mode 0600, new random id), then one `BEGIN IMMEDIATE` (name key,
  row, activity line); a taken name or any failure removes the new file. Span `library.upload` (size only).
- An answer given before the body was read ends with `shutdown(SHUT_WR)` and a bounded `recv` discard (1 MiB or 2 s).
- File names (US-0142, DEC-029): `names.check_file_name` runs after the extension check: composed (NFC) stem, 1 to 100
  characters, no edge space, no leading dot, only Latin script letters (`unicodedata.name` starts with `LATIN`: `ł ø œ ß`
  and accented letters pass, Cyrillic and fullwidth do not), ASCII digits, space and `. _ - ( ) '` (straight apostrophe only);
  a combining mark only after such a letter. A name that is not percent encoded UTF-8 is refused the same way. The name is
  never a path: the file is `files/<fid>/<new id>.html`; the order of the checks is observable with `Browser.upload_declaring`.

## Upload limits, progress and failure (US-0143, DEC-033, DEC-054)

- Size: declared `Content-Length` above 26 214 400 is `413 The file is larger than 25 MB.` before any byte is read; no
  length and no encoding is an empty body (then "not declared"); extra bytes beyond the declared length are never read
  (`rfile` counter test). Chunked: `LibraryHandler._accepts_chunked_body` lifts the inherited `Transfer-Encoding` refusal for
  `POST /api/folders/<fid>/presentations` only, exactly `chunked`, never with a length; `uploads.read_chunked` stops at
  26 214 401 bytes (size line 32 bytes, trailers 8 KiB). Four upload slots (`BoundedSemaphore`, never waited for): a fifth is `503`.
- Right: re checked after the body arrived (`role_in` then `authorize(EDIT)`): removed or lowered meanwhile gives `Access
  denied.` and nothing is stored. A disk error (`fileio.replace_file`) gives `500 The upload failed. Nothing was changed.`
- An answer given before the body was read ends with `shutdown(SHUT_WR)` and a `recv` discard bounded by 1 MiB and ten quiet
  steps of 0.2 s (no clock is read in `server.py`, a test greps for it).
- Page: `progressText(name, loaded, total)` (on `window`) is `<name> <percent>%`, percent floored and at most 99; the
  extension and 25 MB are checked before sending; a second choice during an upload is ignored.
- Tests: `test_library_limits_http.py` (raw socket helpers `Browser.upload_streaming`, `UploadPlan`, `disk_full`,
  `CountingReader`), `test_library_limits_e2e.py` (CDP throttle 10 Mbit), `test_library_limits_slow.py` (`-m slow`).

