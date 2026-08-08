#!/usr/bin/env python3
"""Verification visuelle de l'insertion de slides EI dans un fichier neuf.

Ce controle ne peut pas etre un test unitaire: il faut un vrai navigateur pour
executer editor.js dans l'iframe. Il est donc hors de `make check` et se lance a
la main apres toute modification de:

  - templates/bootstrap/slides-ei-empty.html (ou de la reference qui le genere)
  - static/slide-layouts.js (LAYOUT_SETS.ei)
  - static/editor.js (resolveTemplateAssets, renumberSlides)

Ce qu'il verifie, sur un fichier cree par `mcp-htmleditor new ei`:
  1. le logo de pied d'une slide inseree a bien un data URI (repli
     data-asset-chevrons) et le wrapper .logo-disc qui le dimensionne;
  2. l'eyebrow et .slide-foot-page sont numerotes, y compris apres suppression;
  3. captures PNG des slides inserees, a relire visuellement (l'anneau bleu doit
     contenir les chevrons, sans debordement).

Prerequis: playwright (`pip install playwright && playwright install chromium`).
Usage: python3 tools/check_ei_insert.py [dossier_de_sortie]
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
# Toujours tester les fichiers du repo, jamais la copie installee dans ~/.config,
# qui reste figee jusqu'au prochain `make install`.
os.environ["HTMLEDITOR_TEMPLATES_DIR"] = str(REPO / "templates")

from mcp_htmleditor.http_server import start_http_server, stop_http_server  # noqa: E402
from mcp_htmleditor.templates import template_path  # noqa: E402

PORT = 7896
PROBE = (
    "[...frame.contentDocument.querySelectorAll('article[data-type=\"slide\"]')]"
    ".map(s => ({id: s.id, type: s.getAttribute('data-slide-type'),"
    " eyebrow: (s.querySelector('.slide-eyebrow')||{}).textContent || null,"
    " footPage: (s.querySelector('.slide-foot-page')||{}).textContent || null,"
    " logoDisc: !!s.querySelector('.slide-foot-logo .logo-disc img'),"
    " logoSrcLen: (s.querySelector('.slide-foot-logo img')||{}).src ?"
    " s.querySelector('.slide-foot-logo img').src.length : 0}))"
)


def main() -> None:
    from playwright.sync_api import sync_playwright

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="ei-insert-"))
    out.mkdir(parents=True, exist_ok=True)
    work = out / "neuf.html"
    shutil.copyfile(template_path("ei"), work)

    start_http_server(str(work), PORT)
    time.sleep(1.0)
    failures: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(f"http://localhost:{PORT}/")
            page.wait_for_timeout(2500)

            for layout in ("content", "agenda", "diagram"):
                page.evaluate(f"insertSlide('{layout}', 'after')")
                page.wait_for_timeout(700)

            slides = page.evaluate(PROBE)
            print(json.dumps(slides, indent=2, ensure_ascii=False))

            for i, s in enumerate(slides[1:], start=1):
                if s["logoSrcLen"] < 100:
                    failures.append(f"slide {i} ({s['type']}): logo de pied vide")
                if not s["logoDisc"]:
                    failures.append(f"slide {i} ({s['type']}): wrapper .logo-disc absent")
                if s["footPage"] != str(i + 1):
                    failures.append(f"slide {i} ({s['type']}): .slide-foot-page = {s['footPage']}, attendu {i + 1}")
                if "{{" in (s["eyebrow"] or ""):
                    failures.append(f"slide {i} ({s['type']}): placeholder non resolu dans l'eyebrow")
                page.evaluate(f"frame.contentWindow.goToSlide({i})")
                page.wait_for_timeout(400)
                shot = out / f"insert-{i}-{s['type']}.png"
                page.frame_locator("#content-frame").locator(f"#slide-{i}").screenshot(path=str(shot))
                print(f"capture: {shot}")

            # Suppression de la slide 1: les pieds suivants doivent se decaler.
            page.evaluate(
                "(() => { const d = frame.contentDocument;"
                " d.querySelectorAll('article[data-type=\"slide\"]')[1].remove();"
                " renumberSlides(d); })()"
            )
            page.wait_for_timeout(500)
            after = page.evaluate(PROBE)
            for i, s in enumerate(after[1:], start=1):
                if s["footPage"] != str(i + 1):
                    failures.append(
                        f"apres suppression, slide {i}: .slide-foot-page = {s['footPage']}, attendu {i + 1}"
                    )
            browser.close()
    finally:
        stop_http_server()

    if failures:
        print("\nECHEC:")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)
    print("\nOK: logos resolus, .logo-disc present, numerotation coherente.")
    print(f"Relire les captures dans {out} (chevrons contenus dans le disque blanc).")


if __name__ == "__main__":
    main()
