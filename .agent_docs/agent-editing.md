# Agent editing tools (SPEC-0007, closed by US-0046)

Service layer in `src/mcp_htmleditor/deck/`; it never prints. `cli.py` echoes the results and turns
`DeckError` into `error: <message>` on stderr and exit status 1 (`deck_command`). `mcp_server.py` calls the
same functions and turns `DeckError` into `ToolError(<message>)`, so a tool error is the command line error
line without its `error: ` prefix. Never a second implementation of a rule in a tool.

## Formats

- `outline FILE`: one line of compact JSON `{file, charter, doc_type, total, slides, headings}`;
  a slide is `{index, id, title, slide_type, words, images, problems}`. Never image data.
- `get-slide FILE ID`: the raw text of the slide, `click.echo` adds one trailing `\n`. A large image
  is an `img` whose `src` is a `data:` address longer than 1 000 characters (exactly 1 000 stays); its
  `src` value alone becomes `data:ref:img-N`, N from 1 in document order within the slide. Everything
  else is byte identical to the file (CRLF kept).
- Slide ids are the ones of the outline: `data-id`, else `id`, else `slide-<index>`.
- Errors: `Unknown slide id "x". Valid ids: slide-0, slide-1`, `get_slide needs a presentation: <file>`
  (a file with no slide), `File not found: <file>`.

## `patch FILE --ops PATH|- [--dry-run]` (`deck/patch.py`, US-0038)

- Operations are a JSON list; the five names are parsed, validated and run (US-0040 added the last three):
  `set_text{id,selector,text}`, `replace_slide{id,html}`, `insert_slide{after,html}`, `delete_slide{id}`,
  `move_slide{id,after}`. Result, compact: `{"ok","changed","slides","problems"}` plus a last `dry_run`.
- Check order: template guard (resolved path holds `templates/bootstrap` or `templates/reference`), file
  exists, ops is a list, then each operation IN ORDER: name, fields, needs a presentation, semantics. Any failure is
  `patch failed at operation N: <reason> (nothing written)`. The command reads the ops after the first two
  checks (`check_target`), so a missing FILE wins over a missing ops file.
  The first failing operation stops the run, so an early semantic failure wins over a later shape error.
  Nothing is written until every operation passed. The guard compares path parts casefolded (macOS is case
  insensitive).
- `set_text`: soupsieve selector (CSS 3) on the slide, the slide element itself first; the byte range
  between start tag and end tag of the first match is replaced by the text with only `&`, `<`, `>` escaped.
  Void element: `has no content`. Each `set_text` rescans and reparses its own slide atom, so several edits
  of one slide stack correctly.
- Working copy (`Working`): `Atom(pre, body, orig_id, touched, is_slide)` for raw gaps and slides; a slide's `pre`
  (spaces, tabs, one line break before it) travels with the slide, `body` is its range. Output is the join of
  `pre + body`; equal to the input means no write. `orig_id` is the id in the ORIGINAL file, kept through move
  and replace, `None` for an inserted slide (it cannot be designated) and for gaps; lookups scan the list.
- Write: `fileio.atomic_write` (mkstemp in the directory, fsync, mode copied, `Path.replace`, temp removed on
  failure, symlinks followed, `file.write` span). The update flag is an injected callback, True only around
  the write, never on dry run or no change. UTF-8 BOM and CRLF are kept.
- `delete_slide{id}` (US-0039): drops the slide atom (its `pre` goes with it, so deleting the last slide leaves
  the text after it as is). Order: `unknown slide id` (also for an id deleted earlier in the patch, ids always
  designate the ORIGINAL slides), then `cannot delete the last slide` when the working copy holds one slide.
  Sets `Working.is_structural`.
- `replace_slide{id,html}` (US-0040): checks in order `unknown slide id`, html shape, image reference. Writes the
  html verbatim over the slide range (the `pre` is untouched, renumbering edits it later). Each token
  `data:ref:img-(\d+)` becomes the full `src` of the Nth large image of the slide's CURRENT text in the working
  copy (so a second replace of the same slide still finds the image); N = 0 or beyond the count (or more than 9
  digits) fails with the token as written. No image in the html: the old image is simply gone.
- `insert_slide{after,html}`: `after` is an original id or `start`. Same html rule; any token fails with the first
  one found. After the reference slide: `eol + lead` of the reference's `pre` (`\r\n` when that `pre` holds it),
  then the html, before any comment gap that follows. At `start`: the html takes the first slide's `pre`, the old
  first slide gets `eol + lead` (no blank line). The new atom has `touched` and no `orig_id`.
- `move_slide{id,after}`: `id` checked before `after`. The atom (own `pre` included) goes right after the
  reference; at `start` it takes the first slide's `pre` and the old first slide gets `eol + lead`. Gaps (comments)
  stay where they are. `after == id`, or `start` for the first slide, is a no-op that does not even mark the patch
  structural. After a pop the reference is looked up again, so ids stay the original ones.
- HTML check (`_check_slide_html`): BeautifulSoup `html.parser` for validation only, never serialization; one top
  level Tag, comments and blank strings ignored, any other text, doctype or second element fails;
  `data-type="slide"` and a non empty `data-id`. The root must also be closed (`scan(html)[0]` has
  `end_start < end_end`, not the unclosed shape `end_start == end_end == len(html)`) and only whitespace and
  comments may follow its end tag, so an unclosed fragment or a stray trailing `</div>` gets the same shape reason
  (2026-11, review defect: the next slide used to be nested in the unclosed one, counters not renumbered).
- Dry run (`dry_run=True`, `--dry-run`): the whole pipeline runs, only the write is skipped; errors identical.

## Renumbering (`deck/renumber.py`, US-0039)

- `renumber_edits(text) -> list[Edit]`, `apply_edits(text, edits)` (from the end). Runs ONCE on the assembled
  text after all operations, only if the patch held a structural operation; `set_text` alone never renumbers.
  Cost: one scan, one parse, one linear pass over the slides.
- Idempotence: an edit whose replacement equals the current bytes is dropped; a consistent file gives `[]`
  and stays byte identical (tests on the three presentation fixtures and after a delete).
- Rules (same observable result as `renumberSlides` in `static/editor-slides.js`): slides from `find_slides`;
  `id` and `data-id` set to `slide-N` (appended after the last attribute when missing, `id` first); `active`
  removed everywhere and added on slide 0 (other classes and their order kept, an existing `active` on slide 0
  stays where it is); eyebrow pattern `Slide <n> / <total>` becomes `Slide 0N / TT`; Carbon
  `.slide-footer-right` pattern becomes `Slide N / TT`, other charters `.slide-foot-page` content becomes `N`
  (charter from `detect_charter`); absent elements are never created; first element of each kind only.
- Script: `const TOTAL = <n>;` only its digits change; `const slideNames = [...];` is rewritten one entry per
  line, first entry's indent, trailing comma, closing `];` at the `const` line's indent, line ending of the
  existing block (CRLF kept). Entries: `data-title` decoded, `\` `"` newline escaped, `</` written `<\/`;
  a slide with no `data-title` gets `Slide` (as the editor does). Nothing is created when a constant is
  missing; `slideNames.forEach` is not matched. The list ends at the first `]` outside a string.
- Limits: a duplicated attribute is edited on its first occurrence only; a counter written through an entity
  is not recognised.

- Tests: `assert_only_region_changed(before, after, marker)` in `tests/deck_support.py` proves byte identity
  outside the element found by plain substring search.

## `lint FILE [--json]` (`deck/lint.py`, US-0042)

- Output: one line per problem `<severity> <code> <slide> <message>` (`-` for the whole file, else the
  slide id: `data-id`, `id`, `slide-<index>`), then `lint: OK|FAIL (N errors, M warnings)` (`1 error`
  singular). Order: whole file, slide index, code, stable inside a code. `--json` prints only
  `{"problems":[{code,severity,slide,message}],"errors":n,"warnings":n}`, compact, `ensure_ascii` off.
  Exit 1 when an error exists, warnings alone exit 0. Structure and charter rules apply to presentations
  only; every other file type gets L010 alone (slide `-`).
- Rules are functions in two tables keyed by code (`FILE_RULES`, `SLIDE_RULES`): L002 TOTAL, L003
  `slideNames` length, L004 duplicate beats out of order, L001 missing attributes, L005 counters (only
  an existing one; eyebrow, then Carbon footer or page element), L006 template text (scripts, styles
  and comments excluded, whitespace collapsed). Absent `TOTAL` or `slideNames` is not a problem.
- `count_literals` counts the top level entries of the `slideNames` list: string literals in `"`, `'`
  and backtick with `\` escapes, `//` and `/* */` comments skipped, a nested group counts as one entry.
- Gotchas: a slide without `data-type` is only found by `find_slides` when no slide has it, so L001
  `data-type` fires on decks where none has it. `tests/deck_support.py` mutators find slides by
  `<article\s`, because the bootstrap comments mention a bare `<article>`.

## Charter rules L007 to L011 (`deck/charter_rules.py`, US-0043)

- `lint_deck` adds per slide `charter_problems(slide, charter)` (L007, L008, L009, L011 with their
  severity, from the `deck.charter` key; unknown key: nothing) and L010 (`remote_image_problems`). The
  class tables (`FOREIGN_CLASSES`), flex rows, width classes and `PALETTES` live in that module only.
- L007: `class` attribute of every element, the slide itself included (bs4 splits on any whitespace),
  names compared as written (case sensitive), one problem per distinct class per slide, first occurrence
  order. Message names the charter key.
- L008 (medical): one problem per direct child element of a flex row without a `w-25|30|33|40|50|60|70`
  class; the message names the row class (first one in the element's class list). L009 (medical): exempt
  `data-slide-type` `title` and `thanks`; any `img` needs a `.med-source` with non blank text.
- L010: `src` of `img` (stripped, scheme case insensitive, shown stripped). Presentation: per slide, an
  image outside every slide gets slide `-`; other types: all images, slide `-`. `//host` is not remote.
- L011: hex colours of `style` attributes only (never `<style>`), after removing `url(...)` and `/* */`
  (a data URI or fragment id is not a colour). One warning per distinct colour per slide, identity is the
  upper case 6 digit form (`#abc` and `#AABBCC` are one), shown as first written. Accepted: palette,
  white, black, any R=G=B. `rgb()`, `var()`, names, 4 and 8 digit hex are ignored (regex lookahead).
- Mutators `replace_in_slide` and `add_style` in `tests/deck_support.py`. DECK-CARBON cover no longer
  keeps `Contenu de la slide…` (replaced by the same text as the other slides), so it is lint clean.

## Lint inside `outline` and `patch` (US-0044)

- `outline`: `lint_deck` runs once; `slides[i].problems` counts the problems with `slide_index == i`
  (warnings and errors). Whole file problems (slide `-`) are counted nowhere.
- `patch`: the assembled and renumbered text is parsed with `deck_from_text` (not read back from disk)
  and linted once. `Working.touched_indexes()` maps touched atoms (set_text even when the text is
  unchanged, replaced, inserted) to final slide indexes, so flags follow moves and deletes. Result
  `problems` = `{code,severity,slide,message}` of those slides, slide order then code, ids after
  renumbering. Same list on `--dry-run`. Lint never blocks the write. No touched slide: no lint run.

## Scanner (`deck/scan.py`)

- `scan(text)` returns `Node(tag, start, start_end, end_start, end_end, line, col)` in document order,
  from an `HTMLParser` subclass (`convert_charrefs=False`). Offsets come from `getpos()` through a line
  start table (`\n` only, like `HTMLParser`). The end tag end is the next `>`.
- Void elements and `<x/>` have no end: `end_start == end_end == start_end`.
- Closing rule: an end tag closes the nearest open element of the same name and every element opened
  after it (they end at that end tag's `</`); an end tag with no open element is ignored. So an unclosed
  `<p>` does not move the slide end. Elements still open at the end of text end at `len(text)`.
- `<script>` and `<style>` content is raw text (`</article>` in a script string is not an end tag);
  comments are skipped and belong to no range.
- Bridge: a BeautifulSoup `Tag` maps to the node with `(line, col) == (tag.sourceline, tag.sourcepos)`
  (DEC-002). Tests check this for every tag of every `templates/**/*.html`.
- Cost: one pass over the text, linear in its size; closing walks the open stack, bounded by nesting
  depth.

## Gotchas

- Never output `str(tag)` or any BeautifulSoup serialization: it reformats the file. Slice the text.
- Never find a slide end with a regular expression; use the scanner. The only regex is the attribute
  tokenizer inside one start tag, where quoted values are consumed whole so `data-src=` or an `alt`
  holding `src=` is never taken for `src`.
- `click.testing.CliRunner` translates `\r\n` in captured output; the real command does not. Test
  CRLF on `deck.read.get_slide`.
- `slide_range(nodes, node)` keeps `nodes` only because the story contract fixes the signature.
- `fastmcp.Client` calls from a test must not run in the caller's thread (the e2e suite keeps an event loop
  alive): `call_tool` uses its own thread.
- Nothing may reach the process stdout in the MCP process: it carries the protocol frames. Log to stderr only.

## Tool surface (19 tools, US-0037, US-0041, US-0046, US-0051, US-0053)

| Tool | Service call | Result |
|---|---|---|
| `outline(file)` | `read.outline` | same object as `outline` |
| `get_slide(file, id)` | `read.get_slide` | same text as `get-slide` |
| `patch(file, ops, dry_run)` | `patch.apply_patch` with `set_update_flag` | same object as `patch` |
| `lint(file)` | `lint.lint_file` | same object as `lint --json`; errors in the report are a result, not a `ToolError` |
| `list_templates()` | `tools.template_listing` | `[{"key","description"}]`, registry order |
| `new_file(template, file)` | `tools.create_file` | `{"ok":true,"file":<as given>}`; never serves, never opens a browser |
| `export(file, format, output)` | `tools.export_file` | `{"ok":true,"output","warnings":[...]}` |
| `history(file)` | `history.list_versions` | `{"file":<abs>,"versions":[{"id","bytes","reason"}]}`, newest first |
| `restore(file, id)` | `history.restore_version` | `{"ok":true,"file":<abs>,"id"}`; the replaced content is kept first |
| `list_requests(file)` | `RequestService.list_requests` | `{"file":<abs>,"requests":[...]}`, oldest first, all statuses |
| `complete_request(file, id, status, reason=None)` | `RequestService.complete` | `{"ok":true,"id","status"}`; `status` is a plain `str` (DEC-006); errors are `ToolError(exc.message)` |

- The set is start_server, stop_server, get_status, open_file, update_start, update_end, layout_arch_diagram,
  get_skill plus the eleven above. Each body runs in `trace_span("mcp.<tool>")`. A new tool needs its
  `- <name>: <description>` line in `## Tools` of `skill/core.md` (core budget 7 000 bytes, `skill-audit`).
- `export` and `get_skill`/`get_slide` parameters shadow builtins (`format`, `type`, `id`): `noqa: A002`.
- `deck/tools.py` (US-0045): `export_file` checks the format first (`Unknown export format "x". Valid formats:
  pptx, docx`, exact lower case), `create_file` checks the template key before the target and writes with
  exclusive creation (`File already exists: <file>`, never overwrites even when the file appears late). The
  exporters are imported lazily. `new` and `export` errors are the English `error: ...` lines since US-0045.
- Tests: `tests/deck_support.py` `call_tool` (in process `fastmcp.Client`, own thread) and `run_cli`;
  `tests/test_deck_tools_surface.py` holds E2E-010, 011, 028, tool vs CLI equality, the 19 name equality between
  server and core, stdout cleanliness of a real `mcp-htmleditor mcp` process, and the spec closure test.
- Closure test: acceptance ids E2E-001 to E2E-041 are read by `ast` from `tests/test_deck_*.py`, in the test
  function name, its docstring or the comment lines right above it (the older tests carry the id in a docstring or
  comment, not in the name; renaming them was more invasive). A new test of the spec must carry its id there.
