#!/usr/bin/env python3
"""Regenere templates/bootstrap/slides-ei-empty.html depuis la reference EI.

La reference `templates/reference/slides/euro-information.html` est la source
unique du CSS et du markup de la charte Euro-Information. Le bootstrap en est
derive: meme CSS integral (regles title / agenda / section / content / diagram),
une seule slide titre, compteurs remis a 1.

Le data URI des chevrons EI est en plus recopie sur `<html data-asset-chevrons>`,
ce qui permet a l'editeur de resoudre `{{CHEVRONS}}` quand le document ne
contient encore aucune slide a pied de page (voir resolveTemplateAssets dans
static/editor.js).

Usage: python3 tools/gen_ei_bootstrap.py   (ou `make bootstrap-ei`)
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "templates/reference/slides/euro-information.html"
OUT = ROOT / "templates/bootstrap/slides-ei-empty.html"

HEADER_OLD = "<!--\n  Euro-Information Slides \u2014 Template de r\u00e9f\u00e9rence"
HEADER_NEW = (
    "<!--\n"
    "  Euro-Information Slides \u2014 Template bootstrap (1 slide titre)\n"
    "  GENERE depuis templates/reference/slides/euro-information.html par\n"
    "  tools/gen_ei_bootstrap.py: ne pas editer a la main, relancer la generation\n"
    "  si la reference change (le CSS doit rester identique aux deux endroits).\n"
    "  Usage: copier ce fichier, ajouter des slides via le picker ou dupliquer un <article>."
)
TYPES_LINE = "  5 types de slides: title, agenda, section, content, diagram.\n-->"
TYPES_LINE_NEW = (
    "  5 types de slides: title, agenda, section, content, diagram.\n"
    "  data-asset-chevrons sur <html>: repli du logo de pied pour les slides inserees.\n-->"
)


def main() -> None:
    src = REF.read_text(encoding="utf-8")

    match = re.search(r'<div class="slide-foot-logo"><span class="logo-disc"><img src="([^"]+)"', src)
    if not match:
        raise SystemExit(f"chevrons data URI introuvable dans {REF}")
    chevrons = match.group(1)

    # Ne garder que la slide titre: couper de la slide 2 a la fermeture de .slide-frame.
    start = src.index("    <!-- \u2550\u2550\u2550 SLIDE 2")
    end = src.index('  </div>\n\n  <button class="nav-arrow" id="nav-next"')
    out = src[:start] + src[end:]

    out = out.replace(HEADER_OLD, HEADER_NEW, 1)
    out = out.replace(TYPES_LINE, TYPES_LINE_NEW, 1)
    out = out.replace(
        '<html lang="fr" data-doc-type="presentation">',
        f'<html lang="fr" data-doc-type="presentation" data-asset-chevrons="{chevrons}">',
        1,
    )
    out = re.sub(r'(<span class="cds-tag" id="progress-tag">)\d+ / \d+(</span>)', r"\g<1>1 / 1\g<2>", out, count=1)
    out = re.sub(r"const TOTAL = \d+;", "const TOTAL = 1;", out, count=1)
    out = re.sub(
        r"const slideNames = \[[\s\S]*?\];",
        'const slideNames = [\n    "Titre de la pr\u00e9sentation",\n  ];',
        out,
        count=1,
    )

    OUT.write_text(out, encoding="utf-8")
    print(f"ecrit {OUT.relative_to(ROOT)} ({len(out)} caracteres, chevrons {len(chevrons)} caracteres)")


if __name__ == "__main__":
    main()
