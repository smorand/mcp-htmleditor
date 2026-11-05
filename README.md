# mcp-htmleditor

WYSIWYG HTML editor for LLM-assisted document creation. A browser editor renders
the HTML file as-is in an iframe (all styles/JS intact), with lightweight in-place
editing; a FastMCP server lets AI agents create, modify, and export HTML
presentations and documents.

## Stack

- Python 3.13+, uv, FastMCP, python-pptx, BeautifulSoup4, Click
- pydantic-settings for configuration, rich for logging, OpenTelemetry for tracing
- No Node.js, no build step (iframe renderer + vanilla JS)
- pandoc for DOCX export
- stdlib `http.server` for the HTTP server

## Installation

Everything goes through `make` (uv under the hood, never `pip`).

### System install (XDG compliant)

```bash
make install
```

`make install` performs:
1. Installs the CLI as a **uv tool** in its own isolated environment and links
   `mcp-htmleditor` into `~/.local/bin/` (ensure it is on your PATH). A legacy
   `pip install --user` copy is removed when found, because its console script
   used to shadow both the tool and the sources.
2. Copies templates into `~/.config/mcp-htmleditor/templates/`
3. Creates the log dir `~/.cache/mcp-htmleditor/logs/`
4. Installs the dynamic Pi skill into `~/.pi/agent/dynamic-skills/html-editor/`
   (then add the routing rule to `~/.pi/agent/dynamic_prompt.yaml`, see
   `dynamic-skills/README.md`, zero overlap with the `pptx`/`docx` skills via the
   word "html")

The tool environment is a snapshot: run `make install` again after changing the
sources. All install targets are overridable via env vars (see below).
`make uninstall` reverses everything.

### Development

```bash
make sync     # uv sync: .venv from the committed uv.lock, dev group included
make check    # lint + format-check + typecheck + security + tests with coverage
make run ARGS='export pptx pres.html /tmp/out.pptx'
make run-dev ARGS='-v serve doc.html'
```

### Docker

```bash
make docker-build            # image mcp-htmleditor:latest, version from the git tag
make run-up                  # docker compose up -d, editor on http://localhost:7842/
make run-down
```

The image is multi stage (`python:3.13-slim`), installs from `uv.lock`, ships pandoc,
runs as a non root user and exposes `GET /health`. Documents live in the `./data`
volume mounted on `/data`. The image has no home directory, so it sets
`HTMLEDITOR_STATE_DIR=/var/lib/mcp-htmleditor` (history and server records, a named volume in
`docker-compose.yml`); without a writable state directory every save would fail.
Details in `.agent_docs/docker.md`.

### Version

```bash
mcp-htmleditor --version      # or: curl localhost:7842/health
```

`src/mcp_htmleditor/version.py` holds `dev` in the working tree; `make build` and
`make docker-build` overwrite it from `git describe --tags --always --dirty`.

## Usage

### Create from a template (recommended)

```bash
mcp-htmleditor templates                          # list templates: ei, carbon, medical, doc, doc-perso, doc-ei, mail, website
mcp-htmleditor new ei ma-presentation.html --serve # create + open editor
mcp-htmleditor new medical talk.html --serve       # medical deck (congress, staff, teaching)
```

### Visual editor

```bash
mcp-htmleditor serve path/to/file.html            # open existing file
mcp-htmleditor serve file.html --port 7842 --poll 500
mcp-htmleditor -v serve file.html                 # DEBUG logs (-q for errors only)
mcp-htmleditor serve file.html --host 0.0.0.0 --no-browser   # remote or container
```

Without `--port`, a free port is auto-picked (7842 first, then 7840-7849), so several
presentations can be served at once (one process per file) without colliding on the
default port — see [Multiple presentations at once](#multiple-presentations-at-once).
An explicit `--port` is used as-is and fails with a clear error if it is already taken.

Global options come before the subcommand: `-v` / `--verbose` raises the log level,
`-q` / `--quiet` keeps errors only, `-V` / `--version` prints the version.

Edit mode toggle (top-right "Édition"): in-place rich-text editing, format toolbar
on selection (bold/italic/underline/strike, superscript/subscript, align, size,
color), insert image (local file picker or drag-drop, embedded as base64), insert
table, slide insert/delete (presentation mode) with a template-aware picker (5 layouts for
the `carbon` and `ei` charters, 16 for `medical`), and
document block insert before/after (document mode) via "＋ Bloc avant / Bloc après"
pickers (title, subtitle, h1-h5, paragraph, table, list). Drag-and-drop editing:
reorder top-level document blocks with a left-side grip handle (DOM order = visual
order, no attribute added), and move arch-diagram nodes with the mouse (position
written as readable `data-x`/`data-y` percentages plus inline `left`/`top` in %).
Declarative arch-diagrams (with at least one `arch-row`) also support add/remove
node and add-edge via right-click (see `skill/topics/arch-diagram.md` § Édition à
la souris): every structural change saves then calls the server's `arch-layout`
engine, the browser never computes a position itself.

Undo/redo (Ctrl+Z / Cmd+Z, Ctrl+Shift+Z / Cmd+Shift+Z or Ctrl+Y), active in edit mode:
covers every structural mutation above (node move, node/edge/table/gantt-task
add/remove, slide insert/delete, document block insert/reorder) with a 50-deep
undo/redo stack. Plain text edits inside a text zone keep using the browser's own
native undo, untouched by this feature — see `.agent_docs/html-conventions.md` §
Undo / redo for the exact scope and the native-vs-structural interaction.

### Saving, conflicts and history

The editor saves the whole document. Each save carries the modification time the browser last saw; if the
file changed on disk since (an agent wrote it), the server answers 409 and the page offers **Reload** (show
the disk version, drop the unsaved edits) or **Keep mine** (overwrite). Every write is atomic (temporary
file, then rename): the file holds the complete old or the complete new content, and no other file is left
next to it. The check and the replace are serialized per process only, not against an agent writing the file
directly or against another process.

Before a browser save, a `patch`, a **Keep mine** or a `restore` changes a file's bytes, the previous content
is kept in the history (20 versions per file, oldest dropped first). Each version is `{id, bytes, reason}`,
`reason` one of `browser-save`, `keep-mine`, `patch`, `restore`. A write that changes nothing keeps nothing.

```bash
mcp-htmleditor history deck.html            # <id>  <bytes> bytes  <reason>, newest first
mcp-htmleditor restore deck.html <id>       # put it back; the replaced content is kept as a new version
```

The same operations are the MCP tools `history(file)` and `restore(file, id)`. Templates under `templates/`
are never modified by a save or a restore.

The "modification in progress" flag (`update_start`) expires by itself 120 seconds after the last
`update_start`, so a crashed agent never leaves the overlay up. Flags, server records and the history live in
the state directory (`HTMLEDITOR_STATE_DIR`, default `$XDG_STATE_HOME/mcp-htmleditor`, else
`~/.local/state/mcp-htmleditor`), never next to the edited file; `.mcp_state.json` files left by older
versions are ignored and can be deleted.

### Request loop

The person asks the agent for a change from the editor, and the agent reads, does and closes it.

- **Ask AI** (toolbar button) opens a panel: describe the change, the current slide is attached, **Queue request**
  stores it. Up to 50 requests can be pending, 4 000 characters each.
- The side list **Requests (n)** shows every request of the open file with its status (`pending`, `done`,
  `skipped`); a request can be deleted from the list. `n` counts the pending ones.
- The agent works with the tools `list_requests(file)`, `complete_request(file, id, status, reason=None)` and
  `write_review(file, suggestions)`, or the same operations by command:

```bash
mcp-htmleditor requests deck.html                          # <id>  <status>  <slide>  <title>, oldest first
mcp-htmleditor request-done deck.html R-0001               # mark done
mcp-htmleditor request-skip deck.html R-0002 --reason "Out of scope"   # a reason is required
mcp-htmleditor review deck.html                            # <id>  <slide>  <title> of each suggestion
mcp-htmleditor review deck.html --write review.json        # replace the review (- reads stdin, at most 6)
```

A tool error carries the text of the command line `error:` line without its prefix.

Where the state lives: `<state_dir>/files/<key>/requests/record.json` (plus `record.lock`), where `<state_dir>` is
`HTMLEDITOR_STATE_DIR` (see Environment variables) and `<key>` identifies the file by its real path. Nothing is
created next to the edited file, and two files never share requests. Removing the state directory removes the
requests and the review.

### MCP server (stdio)

```bash
mcp-htmleditor mcp
```

Connect your LLM agent via stdin/stdout (e.g. Claude Desktop, Cursor, pi).

### Skill content

```bash
mcp-htmleditor skill                 # the core: rules, workflow, tools and the topic index
mcp-htmleditor skill --type <topic>  # one of the 15 topics (arch-qa also prints the resolved checklist)
mcp-htmleditor skill --all           # the core then every topic
mcp-htmleditor skill-audit [--json]  # sizes, budgets, tool list and stale statements; exit 0 when clean
```

The skill is progressive: the core (`skill/core.md`, at most 7000 bytes) is read first,
then the agent loads only the topics its task needs (`skill/topics/<topic>.md`, at most
8000 bytes each). `skill-audit` prints one line per item (core, then the 15 topics in index
order), one `PROBLEM` line per issue, and `skill-audit: OK` or `skill-audit: FAIL (N problems)`.
The same content is available to agents through the `get_skill` MCP tool. The previous
monolithic skill is kept for reference in `docs/skill-archive/`.

The dynamic Pi skill triggers on "html powerpoint", "html edition", "html doc" and
instructs the agent to run `mcp-htmleditor skill` and then `mcp-htmleditor skill --type <topic>`
for what the task needs, keeping the skill content in sync with the installed tool. Routing is disjoint from the native `pptx`/`docx`
skills (the word "html" is the exclusive discriminant). See `dynamic-skills/README.md`.

### Export

```bash
mcp-htmleditor export pptx input.html output.pptx
mcp-htmleditor export docx input.html output.docx
```

### Visual render

See a slide as a picture and find layout problems without opening the editor. It needs Chromium,
which is an optional extra: `make install` installs the `render` extra (`uv sync --extra render`
does the same in a checkout), then `make install-browser` downloads the browser. Without it the
command stops with `Rendering needs Chromium. Install it with: make install-browser`. The Docker
image has no browser, so `render` is not available in the container.

```bash
mcp-htmleditor render pres.html                          # first slide, 480x270 PNG
mcp-htmleditor render pres.html --slide slide-3 --scale 1   # 960x540
mcp-htmleditor render pres.html --slide slide-3 --report    # picture plus its layout problems
mcp-htmleditor render pres.html --report-only               # every slide, no picture
mcp-htmleditor render pres.html --report-only --json        # one compact JSON object
```

| Option | Effect |
|--------|--------|
| `--slide TEXT` | Id of the slide to render (default: the first). An unknown id lists the valid ids. |
| `--scale TEXT` | Scale of the picture, 0.1 to 1 (default 0.5). |
| `--report` | Also print the layout problems of the rendered slide. |
| `--report-only` | Print the layout problems of every slide and write no picture. Cannot be combined with `--slide`, `--scale` or `--report`. |
| `--json` | Print the result as one compact JSON object only. |

The picture is written to `<temporary directory>/htmleditor-render/<file stem>-<slide id>.png` and
the command prints `Rendered <slide id> to <path> (<width>x<height>)`. After a successful render,
older pictures of the same presentation's other slides are removed; pictures of other files stay.
The HTML file is never modified. A `--report-only` run of a 40 slide presentation finishes in under 30 seconds.

With `--report` or `--report-only` each problem prints as `<kind> <slide>: <message>`, in slide
order, then a final line `report: OK`, `report: 1 problem` or `report: N problems`.

| Kind | Message |
|------|---------|
| `overflow` | `content is <n>px tall, the slide is 540px` |
| `clipped` | `<selector> is outside the slide frame` |
| `font` | `"<name>" is not available, fallback used` |
| `script` | `<Error name>: <message>`, a script error raised while the slide was shown (slide `-` before any slide is shown) |
| `image` | `<source> did not load` (a long data address is cut to 40 characters plus `...`) |

Exit statuses: `0` nothing to report, `1` at least one problem found or an error (`error: <message>`
on stderr), `2` conflicting options (`Error: --report-only cannot be used with --slide, --scale or --report`).

The MCP tool `render(file, slide=None, scale=0.5, report=False, report_only=False)` does the same
and returns `{ok, path, width, height, problems}` with `problems` as a list of `{kind, slide, message}`.

### Read, check and edit a file without touching its images

```bash
mcp-htmleditor outline input.html           # JSON: charter, type, slides, headings
mcp-htmleditor get-slide input.html slide-3 # HTML of one slide, large images as data:ref:img-N
mcp-htmleditor patch input.html --ops ops.json [--dry-run]  # atomic slide operations, counters renumbered
mcp-htmleditor lint input.html [--json]     # structure and charter rules, exit 1 on an error
```

### The seven agent operations

Each one is a command and an MCP tool with the same result and the same error text; the tool error is the
command line error line without its `error: ` prefix.

| Operation | Command | Tool |
|---|---|---|
| Read the structure | `outline FILE` | `outline(file)` |
| Read one slide | `get-slide FILE ID` | `get_slide(file, id)` |
| Edit slides | `patch FILE --ops PATH` | `patch(file, ops, dry_run)` |
| Check a file | `lint FILE [--json]` | `lint(file)` |
| List templates | `templates` | `list_templates()` |
| Create a file | `new TEMPLATE FILE` (without `--serve`) | `new_file(template, file)` |
| Export | `export FORMAT FILE OUTPUT` | `export(file, format, output)` |

`new` and `export` errors are now English `error: ...` lines on the error output with exit status 1, for
example `error: File already exists: a.html` or `error: Unknown export format "foo". Valid formats: pptx, docx`.
`new_file` never starts the server or opens a browser: call `start_server` to edit the created file.

### Architecture diagram layout

```bash
mcp-htmleditor arch-layout input.html [--diagram-id ID]
```

Computes and writes the positions of every declarative architecture diagram
(`data-type="arch-diagram"` with at least one `arch-row` child) in the file: the LLM
authors topology only (rows, nodes, edges, optional lanes), never `%` coordinates, and
this command derives them deterministically — no collision between nodes, straight
connectors on aligned columns, labels centered on their segment, lane boxes sized from
the union of the rows they declare. Diagrams with no `arch-row` (legacy, hand authored
`data-x`/`data-y`) are left untouched, so both formats coexist. See
`skill/topics/arch-diagram.md`.

The PPTX export writes one 16:9 slide (13.333 x 7.5 in) per element carrying
`data-type="slide"`, with a fallback on `article.slide` for older templates. The
navigation shell, `<script>` and `<style>` are never exported. It detects the
charter of the document (Euro-Information, IBM Carbon, medical, generic), draws the slide
chrome (frames, footers, logo ring, header rule), then flows the content: text at
the typographic scale of the template, tile grids, callouts, native tables with
`colspan` / `rowspan` merges, real Gantt bars, diagram nodes as autoshapes with
their connectors, annotated images with the annotations placed in the image frame.
Base64 images are embedded and relative paths resolve against the HTML file. The
command prints the slide count, lists every skipped item and exits non zero when
no slide could be written. Full breakdown of what is faithful, approximated or
lost: `skill/topics/export.md`.

### Architecture diagram QA

```bash
mcp-htmleditor arch-checklist   # print the resolved checklist + where it lives
```

After every `arch-layout` run, the agent workflow spawns a dedicated review
sub-agent that checks the rendered diagram against this checklist (screenshot,
compare, fix, re-layout, bounded to 2 passes) so the main conversation is not
polluted by iteration: see `skill/topics/arch-qa.md`. The checklist itself
lives at `~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md`
(seeded once by `make install`, never overwritten on reinstall): add or change
a control by editing that file directly, no code change or reinstall needed. A checklist
seeded by an earlier install keeps its size and content: `skill --type arch-qa` prints the
topic followed by your checklist when one exists, the shipped one otherwise.

The DOCX export carries the document charter into Word. The charter is read from
`data-doc-template` on the document `<article>` (`perso`, `ei`), a matching
`reference.docx` is generated from pandoc's own default (fonts, heading sizes and
colours, underlines, table header fill) and cached in
`~/.cache/mcp-htmleditor/reference/`. A document without that attribute keeps the
default pandoc styles. The title is emitted once (Word `Title`, then `Subtitle`),
not duplicated as a `Heading1`. SVG figures and pandoc warnings are reported:
figures must be PNG, never SVG.

## MCP Tools

| Tool | Description |
|------|-------------|
| `start_server(file, port=None)` | Start HTTP server + open browser. Idempotent. Without `port`, a free one is auto-picked (7842 first, then 7840-7849) — always read the `port` field of the response, never assume 7842. |
| `stop_server()` | Stop the HTTP server. |
| `get_status()` | Current state: file, port, pid, mtime, running. |
| `open_file(file)` | Switch to a different HTML file. |
| `update_start()` | Signal modification start (shows overlay in browser). |
| `update_end()` | Signal modification complete (browser reloads). |
| `get_skill(type=None)` | Return the skill core, or one topic when `type` is given (same text as `mcp-htmleditor skill [--type <topic>]`). |
| `layout_arch_diagram(file, diagram_id=None)` | Compute and write positions for every declarative architecture diagram in `file` (see [Architecture diagram layout](#architecture-diagram-layout)). |
| `outline(file)` | Structure of a file (charter, type, slides, headings) as a JSON object, without any image data. Same object as `mcp-htmleditor outline`. |
| `get_slide(file, id)` | HTML of one slide, every image with a data address over 1 000 characters replaced by `data:ref:img-N`. Same text as `mcp-htmleditor get-slide`. |
| `patch(file, ops, dry_run=False)` | Apply validated, atomic, self renumbering slide operations (`set_text`, `replace_slide`, `insert_slide`, `delete_slide`, `move_slide`) in one write. `update_in_progress` is true only around the write; a dry run or a no change patch touches neither the flag nor the modification time. Same result as `mcp-htmleditor patch`; errors carry the command line error text without `error: `. |
| `lint(file)` | Check a file against the structure and charter rules; returns `{problems, errors, warnings}`, the same object as `mcp-htmleditor lint --json`. |
| `list_templates()` | The template keys with their description, `[{key, description}]`, in the order of `mcp-htmleditor templates`. |
| `new_file(template, file)` | Create a file from a template key; refuses an existing target; does not serve it. Returns `{ok, file}`. |
| `export(file, format, output)` | Export a presentation to `pptx` or a document to `docx`. Returns `{ok, output, warnings}`. |
| `history(file)` | List the saved previous versions of a file, newest first: `{file, versions: [{id, bytes, reason}]}`. Same list as `mcp-htmleditor history`. |
| `restore(file, id)` | Put a previous version back by id; the replaced content is kept in the history. Returns `{ok, file, id}`. Refuses templates. |
| `list_requests(file)` | The requests the person queued in the editor, oldest first: `{file, requests: [{id, slide, title, queued, instruction, status, reason}]}`. Same list as `mcp-htmleditor requests`. |
| `complete_request(file, id, status, reason=None)` | Mark a request `done`, or `skipped` with a reason. Returns `{ok, id, status}`. |
| `write_review(file, suggestions)` | Replace the AI suggestions shown in the editor (at most 6). Returns `{ok, count}`. |
| `render(file, slide=None, scale=0.5, report=False, report_only=False)` | PNG of one slide plus, on request, its layout problems (see [Visual render](#visual-render)). Needs Chromium. Returns `{ok, path, width, height, problems}`. |

### Multiple presentations at once

Each `mcp-htmleditor serve <file>` (CLI) or `mcp-htmleditor mcp` (one per agent session) is
an independent process. Without an explicit port, it tries 7842 then scans 7840-7849 for a
free one, so up to 10 presentations can coexist (one file each) without any manual port
juggling. Within a *single* agent session (one `mcp-htmleditor mcp` process), only one
server runs at a time: calling `start_server` on a second file switches the served file
(use `open_file` for that) rather than opening a second server — run a separate agent
session per presentation if you need several displayed simultaneously.

## Templates

Templates are resolved in priority order:
1. `HTMLEDITOR_TEMPLATES_DIR` (env override)
2. `~/.config/mcp-htmleditor/templates/` (installed by `make install`)
3. `<repo>/templates/` (development / bundled fallback)

```
templates/
├── bootstrap/                     starters copied by `new`
│   ├── slides-ei-empty.html       key: ei        (Euro-Information)
│   ├── slides-empty.html          key: carbon    (IBM Carbon)
│   ├── slides-medical-empty.html  key: medical   (medical deck, single source of the charter CSS)
│   ├── document-empty.html        key: doc       (Word-like document)
│   ├── document-perso-empty.html  key: doc-perso (Perso charter, Arial)
│   ├── document-ei-empty.html     key: doc-ei    (Euro-Information, Segoe UI)
│   ├── mail-empty.html            key: mail      (HTML email, light Carbon charter)
│   └── website-empty.html         key: website   (Carbon website: nav, hero, tabs, cards, footer)
└── reference/                     rich examples to clone (read-only via server)
    ├── slides/
    │   ├── euro-information.html   EI: title + agenda + content, embedded logos (CSS source of the `ei` bootstrap)
    │   ├── example-ei-complete.html EI: 9 slides, gantt, arch diagram, table, annotated image
    │   ├── ibm-carbon.html         IBM Carbon: 9 slides, all components
    │   ├── medical.html            medical charter catalogue, one slide per `data-slide-type` (16)
    │   ├── example-medical-complete.html medical: full talk, dark imaging slides, clinical case, bibliography
    │   ├── presentation-standard.html
    │   └── roadmap-one-pager.html
    ├── documents/
    │   ├── report-standard.html    generic standard report
    │   ├── perso.html              Perso charter: title/subtitle + h1-h5 + table + list
    │   ├── euro-information.html    EI document: blue header + logo, blue headings
    │   └── mail-carbon-example.html rich HTML email example, light Carbon charter, inline CSS
    └── websites/
        └── ibm-carbon.html          full component catalogue: nav, tabs, cards, footer variants
```

Add your own templates by dropping files into `~/.config/mcp-htmleditor/templates/`
or by committing to `templates/` in this repo.

`bootstrap/slides-ei-empty.html` is **generated**, not hand written: it is derived from
`reference/slides/euro-information.html` by `tools/gen_ei_bootstrap.py` (`make bootstrap-ei`),
which keeps the reference as the single source of the EI charter CSS, trims the deck down to
the title slide, and copies the EI chevrons data URI onto `<html data-asset-chevrons>` so a
slide inserted into a brand new file still gets its footer logo. Edit the reference, then
run `make bootstrap-ei`; never patch the bootstrap directly.

`make check-generated` verifies that both generated families (the EI bootstrap and the two
medical reference decks) are fresh. It runs `--check` on both tools, prints one
`<path>: fresh` or `stale (first difference at line N); run: make <target>` line per file,
fails when any is stale or missing, and writes nothing. It is the first step of `make check`.

The `medical` charter works the other way round: `bootstrap/slides-medical-empty.html` is the
single source of its CSS, and the two reference decks (`reference/slides/medical.html`,
`reference/slides/example-medical-complete.html`) embed an exact copy so they open on their
own. Edit the bootstrap `<style>`, then run `make sync-medical-css`. That charter targets
medical presentations (congress, staff meeting, teaching, interventional pulmonology): teal
`#159984` plus orange `#EE5A02`, Trebuchet MS / Arial, grey top band and two segment rule
under the title, bibliographic source band in the footer, dark surface for imaging slides,
and 16 insertable slide layouts (the other slide charters expose 5). Every third party image
must carry a source line and every patient image must be anonymized: see
`skill/topics/medical.md`.

## HTML data-types

| `data-type` | Description |
|-------------|-------------|
| `slide` | Presentation slide section |
| `gantt` | Gantt chart container |
| `gantt-task` | Single Gantt task bar |
| `arch-diagram` | Architecture diagram container |
| `arch-node` | Architecture diagram node |
| `arch-row` | Declarative layout row (input to `arch-layout`, inert to every exporter) |
| `arch-lane` | Declarative layout lane/swimlane (input to `arch-layout`, box computed automatically) |
| `annotation` | Image annotation callout |
| `annotated-image` | Image + annotations container |
| `table` | HTML table |
| `document` | Word-like document article |

## Environment variables

Every variable is read through the `Settings` class (pydantic-settings,
`src/mcp_htmleditor/config.py`). A local `.env` file is loaded automatically; see
`.env.example`.

| Variable | Default | Description |
|----------|---------|-------------|
| `HTMLEDITOR_HOST` | `localhost` | HTTP bind address (`0.0.0.0` in a container) |
| `HTMLEDITOR_PORT` | `7842` | Preferred HTTP port, tried first before auto-picking a free one in 7840-7849 |
| `HTMLEDITOR_POLL_INTERVAL` | `1000` | Browser polling interval in ms |
| `HTMLEDITOR_TEMPLATES_DIR` | `~/.config/mcp-htmleditor/templates` | Templates directory |
| `HTMLEDITOR_ARCH_CHECKS_DIR` | `~/.config/mcp-htmleditor/arch-checks` | Arch-diagram QA checklist directory (edit in place to add/change a control, see `mcp-htmleditor arch-checklist`) |
| `HTMLEDITOR_STATE_DIR` | `$XDG_STATE_HOME/mcp-htmleditor`, else `~/.local/state/mcp-htmleditor` | File history and server records (set to a writable path in a container) |
| `HTMLEDITOR_CACHE_DIR` | `~/.cache/mcp-htmleditor` | Cache base (logs, generated `reference.docx`) |
| `HTMLEDITOR_LOG_DIR` | `<cache>/logs` | Log directory (`HTMLEDITOR_LOGS` is an accepted alias) |
| `HTMLEDITOR_BIN_DIR` | `~/.local/bin` | CLI install target |
| `HTMLEDITOR_OTEL_DESTINATION` | unset | OTLP/HTTP endpoint for spans; unset means local JSONL |
| `HTMLEDITOR_OTEL_API_KEY` | unset | Sent as `Authorization: Bearer <key>` on OTLP exports |
| `XDG_CONFIG_HOME` | `~/.config` | Base for config |
| `XDG_CACHE_HOME` | `~/.cache` | Base for cache |

A malformed `HTMLEDITOR_PORT` or `HTMLEDITOR_POLL_INTERVAL` falls back to its default
instead of aborting; a blank path variable means "unset", not the current directory.

## Security model

The preview server is for one local user. It has no authentication, so it only answers requests
it can trust as coming from its own editor page:

- the `Host` name must be `localhost`, `127.0.0.1`, `[::1]` or the host given with `--host` /
  `HTMLEDITOR_HOST` (never `0.0.0.0`); any port is accepted, so a published container port such
  as `-p 7999:7842` works;
- a request carrying an `Origin` header must come from that same `http://<host>:<port>`;
- no CORS header is ever sent, preflight `OPTIONS` answers `405`, and saves must be
  `Content-Type: application/json`.

Anything else answers `403 {"error": "forbidden host"}`, `403 {"error": "forbidden origin"}` or
`415 {"error": "unsupported content type"}`, and is logged as a warning. `GET /health` stays open
for health checks. Limitation: in a container bound to `0.0.0.0`, a client on the network that sets
`Host: localhost` is not stopped; do not publish the port beyond the machine (tracked as BL-0019).

The server also protects itself from malformed or stalled requests. A request with a duplicated or
ambiguous `Host`, `Origin`, `Content-Length` or `Content-Type` header, a `Transfer-Encoding` header or a folded
header answers `400`. A client that stays silent for 30 seconds while the server waits for the request line, a
header or the body, or that takes more than 5 minutes to send one request, answers `408 {"error": "Request
timeout"}` and is disconnected; a connection that never sends a byte is closed without an answer. A
`/arch-layout` request above 1 MiB answers `413`. Text or file names that cannot be encoded are refused with one
line instead of a traceback. Every refusal is logged as one `Refused <METHOD> <path>: <error>` warning.

## Logs and tracing

| File | Content |
|------|---------|
| `<log dir>/mcp-htmleditor.log` | Application log, rotating (2 MB, 3 backups) |
| `<log dir>/mcp-htmleditor-otel.log` | One JSON object per finished span (JSONL) |

Console logs go to stderr (stdout carries the MCP protocol and the CLI output) and every
line carries its own timestamp. Spans are named `category.operation`: `mcp.*` for tool
calls, `export.pptx` / `export.docx` with slide count, charter and duration,
`tool.pandoc` for pandoc runs, `file.write` for file mutations. Document content,
prompts and credentials are never traced. Details in `.agent_docs/observability.md`.

## Project structure

```
src/mcp_htmleditor/
├── cli.py           CLI: templates, new, serve, skill, skill-audit, mcp, export, outline, get-slide, patch, lint (-v/-q, --version)
├── config.py        Settings (pydantic-settings): XDG paths, ports, OTel
├── logging_config.py setup_logging(): rich console on stderr + rotating file
├── tracing.py       configure_tracing(), trace_span(), JSONL span exporter
├── version.py       __version__, written at build time from the git tag
├── templates.py     template registry + search-path resolution
├── skill_content.py assembles `mcp-htmleditor skill` output (core, topics, --all)
├── skill_audit.py   `mcp-htmleditor skill-audit`: sizes, budgets, tool list, stale statements
├── arch_layout.py   declarative arch-diagram layout engine (rows/nodes/edges/lanes → %)
├── mcp_server.py    FastMCP server with 21 tools
├── http_server.py   stdlib HTTP server (routes /, /static, /content, /status, /health)
├── fileio.py        atomic_write: the one writer (temp file, rename, history snapshot)
├── history.py       HistoryStore, list_versions, restore_version (history and restore)
├── state.py         singleton state + records in the state directory
├── export/
│   ├── charters.py  REGISTRY of CharterSpec: the eight charters (templates, detectors, DOCX keys)
│   ├── to_pptx.py   HTML to PPTX entry: to_pptx, find_slides, ExportReport re-export, composed _SlideBuilder
│   ├── pptx_model.py      shared model: ExportReport, block types, _BuilderBase (mixin base class)
│   ├── pptx_text.py       text and paragraph rendering, rectangle and textbox primitives
│   ├── pptx_images.py     annotated images, images and picture primitives
│   ├── pptx_arch.py       arch diagram renderer (nodes, edges, tips, badges, labels)
│   ├── pptx_gantt.py      Gantt renderer, inline Gantt detection
│   ├── pptx_blocks.py     block measurement and renderers (grid, panel, rule, hbar, table)
│   ├── pptx_flow.py       block flow and flex row logic
│   ├── pptx_chrome.py     per charter chrome (EI, Carbon, medical, generic)
│   ├── pptx_style.py      Box geometry, CSS/colour parsing, themes, typographic scale
│   ├── pptx_components.py table grid (spans), Gantt maths, low level pptx helpers
│   ├── to_docx.py   HTML to DOCX via pandoc (single title, charter, diagnostics)
│   ├── reference_docx.py  generates/caches a charter reference.docx for pandoc
│   ├── docx_header_footer.py  repeated Word header/footer parts of a charter
│   └── docx_assets.py     base64 assets embedded in the reference documents
└── static/
    ├── editor.html      iframe shell + toolbar
    ├── editor-undo.js   undo and redo snapshots
    ├── editor-edit.js   edit mode injection and removal
    ├── editor-format.js format bar, insert bar, image embed, table and link insert
    ├── editor-menus.js  context menus, table row and column actions, arch node actions
    ├── editor-save.js   client side save
    ├── editor-slides.js slide picker, insert, delete, renumbering
    ├── editor-blocks.js document block picker and insert
    ├── editor-drag.js   drag-reorder of document blocks, mouse move of arch nodes
    ├── editor.js        state, start up, polling (loaded last)
    ├── slide-layouts.js per-template slide layouts (carbon / ei / medical)
    ├── doc-blocks.js    document block definitions (title, subtitle, h1-h5, paragraph, table, list)
    └── editor.css       toolbar, overlay, picker styles
templates/          versioned templates (bootstrap + reference)
tests/              pytest suite (see .agent_docs/testing.md)
tools/              maintenance scripts
                    gen_ei_bootstrap.py  regenerate the EI bootstrap from the EI reference
                    check_ei_insert.py   browser check of EI slide insertion (logo + numbering)
                    sync_medical_css.py  propagate the medical charter CSS to the reference decks
                    gen_medical_placeholders.py  synthetic placeholder images for the medical decks
skill/              core.md, topics/ (15), checks/ (served by `mcp-htmleditor skill`)
docs/skill-archive/ previous monolithic skill, reference only
dynamic-skills/     dynamic Pi skill + routing doc (installed to ~/.pi/agent/dynamic-skills)
.agent_docs/        detailed docs for AI agents (python, makefile, architecture, ...)
Dockerfile, docker-compose.yml, docker-compose.prod.yml
Makefile            single entry point for every operation
```

## Documentation

- `AGENTS.md`: compact index for AI agents (commands, conventions, doc index)
- `.agent_docs/python.md`: Python standards and documented deviations
- `.agent_docs/makefile.md`: every make target and install override
- `.agent_docs/architecture.md`: module map, save path, export pipeline
- `.agent_docs/observability.md`: logs, span inventory, OTLP export
- `.agent_docs/testing.md`: test map, coverage, export regression set
- `.agent_docs/docker.md`: image, compose, container checks
- `.agent_docs/html-conventions.md`: invariants the exporters rely on

## How it works

1. The HTTP server serves the editor shell at `http://localhost:<port>/` (7842 if free, otherwise an auto-picked free port in 7840-7849, or whatever `--port` was given explicitly)
2. The target HTML file is rendered as-is inside an iframe (`GET /content-frame`)
3. In edit mode, editable zones become contenteditable; saves go via `POST /content`
   (the server strips editor artifacts before writing, keeping the file clean)
4. The browser polls `GET /status` every `poll_interval` ms
5. If the file mtime changes (LLM wrote to it), the iframe reloads
6. `update_start()` / `update_end()` show/hide a "modification en cours" overlay

## Skill documentation

Run `mcp-htmleditor skill` for the core, then `mcp-htmleditor skill --type <topic>` for a
topic (`--all` prints everything). Source files live in `skill/core.md` and `skill/topics/`. The dynamic Pi skill in `.pi/skills/mcp-htmleditor/`
triggers on "html powerpoint" / "html edition" / "html doc" and defers to the CLI.
