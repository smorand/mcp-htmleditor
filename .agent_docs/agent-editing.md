# Agent editing tools (SPEC-0007)

Service layer in `src/mcp_htmleditor/deck/`; it never prints, `cli.py` turns `DeckError` into
`error: <message>` on stderr and exit status 1 (`deck_command`).

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

- Operations are a JSON list; the five names are parsed and validated, only `set_text` runs for now
  (the other four fail with `operation "<op>" is not supported yet` once their ids exist):
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
- Working copy (`Working`): atoms of raw gaps and slides; a slide atom starts at its `pre` (spaces, tabs,
  one line break) so it travels with the slide. Output is the join; equal to the input means no write.
- Write: `fileio.atomic_write` (mkstemp in the directory, fsync, mode copied, `Path.replace`, temp removed on
  failure, symlinks followed, `file.write` span). The update flag is an injected callback, True only around
  the write, never on dry run or no change. UTF-8 BOM and CRLF are kept.
- Tests: `assert_only_region_changed(before, after, marker)` in `tests/deck_support.py` proves byte identity
  outside the element found by plain substring search.

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
