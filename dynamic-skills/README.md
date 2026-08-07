# Dynamic skill routing (Pi)

The dynamic Pi skill for `html-editor` lives in `dynamic-skills/html-editor/SKILL.md`.
It is intentionally tiny: it tells the agent to run `mcp-htmleditor skill`, so the
real skill content stays in the CLI and never drifts.

## Install

`make install` copies the skill to `~/.pi/agent/dynamic-skills/html-editor/`.

Then add the routing rule to `~/.pi/agent/dynamic_prompt.yaml` (once), and add a
negative lookahead to the existing `pptx` and `docx` rules so there is **zero
overlap** (the word "html" routes exclusively to `html-editor`).

## Routing rules (zero overlap by the word "html")

Add this rule under `rules:` in `dynamic_prompt.yaml`:

```yaml
  - id: html-editor
    type: skill
    skill_path: "~/.pi/agent/dynamic-skills/html-editor/SKILL.md"
    match: '(?i)\bmcp-?htmleditor\b|\b[ée]diteur html\b|html.?editor\b|\bhtml\b.{0,20}\b(powerpoint|pptx|slides?|pr[ée]sentations?|diaporama|slide.?deck|doc|document|wysiwyg|[ée]di(?:tion|ter|te))\b|\b(powerpoint|pptx|slides?|pr[ée]sentations?|diaporama|slide.?deck|document|wysiwyg)\b.{0,20}\bhtml\b'
```

Replace the `pptx` and `docx` `match:` values with the lookahead variants:

```yaml
  - id: docx
    match: '(?is)^(?!.*\bhtml\b).*?(?:\bdocx\b|document word\b|word document\b|\.docx\b)'

  - id: pptx
    match: '(?is)^(?!.*\bhtml\b).*?(?:\bpptx\b|powerpoint|diaporama|\.pptx\b|\bpr[ée]sentations?\b|\bslides?\b|slide.?deck|slide show|slideshow)'
```

## Trigger matrix (verified, zero overlap)

| Prompt | Routes to |
|--------|-----------|
| "html powerpoint", "html slides", "html doc", "html edition" | html-editor |
| "présentation html", "un powerpoint en html", "slide deck html" | html-editor |
| "éditeur html wysiwyg", "html editor", "mcp-htmleditor" | html-editor |
| "fais un powerpoint", "diaporama", "slide deck", "ajoute 3 slides" | pptx |
| "édite ce pptx", "présentation pour lundi" | pptx |
| "fais un docx", "document word", "édite ce .docx" | docx |
| "code html", "une page html simple" | none |

The discriminant is the word **html**: its presence disables `pptx`/`docx` and
enables `html-editor`; its absence keeps `pptx`/`docx` behaving as before.

Distinction of purpose:
- `pptx` / `docx`: produce or edit native `.pptx` / `.docx` files (OOXML, pptxgenjs).
- `html-editor`: edit HTML WYSIWYG (single-page source of truth), export to PPTX/DOCX at the end.
