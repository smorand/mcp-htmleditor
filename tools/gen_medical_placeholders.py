#!/usr/bin/env python3
"""Generate the synthetic medical placeholder images of the 'medical' template.

The medical slide template ships image slots (CT, EBUS, bronchoscopy, histology).
Real clinical images cannot be committed: they carry patient data and, when taken
from the literature, third party copyright. This script draws *synthetic*
look-alikes so the reference/demo decks are self contained, anonymous and
copyright clean, while still showing the intended contrast and framing.

Usage:
    python tools/gen_medical_placeholders.py [OUT_DIR]

Writes ``ct.png``, ``ebus.png``, ``bronchoscopy.png``, ``histology.png`` into
OUT_DIR (default: ``/tmp/medical-placeholders``) and prints, for each file, the
``data:image/png;base64,...`` URI to paste into a template.
"""

from __future__ import annotations

import base64
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = (320, 240)
"""Placeholder size in pixels: enough for a 704px wide slide panel, small
enough that four base64 data URIs stay a few hundred kilobytes in total."""

SECTOR = (-72, -136, 392, 240)
"""Bounding box of the EBUS sector arc (wider than the canvas on purpose)."""


def _noise(size: tuple[int, int], sigma: float, seed: int) -> Image.Image:
    """Return a grayscale noise layer (deterministic for a given seed)."""
    random.seed(seed)
    img = Image.effect_noise(size, sigma)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def ct() -> Image.Image:
    """Draw a fake axial chest CT: body ellipse, two lung fields, a nodule."""
    img = Image.new("L", SIZE, 8)
    d = ImageDraw.Draw(img)
    d.ellipse((22, 14, 298, 226), fill=90)  # soft tissue
    d.ellipse((27, 19, 293, 221), fill=105)
    d.ellipse((42, 37, 154, 206), fill=22)  # right lung
    d.ellipse((166, 37, 278, 206), fill=22)  # left lung
    d.ellipse((134, 74, 186, 171), fill=118)  # mediastinum
    d.ellipse((149, 96, 171, 120), fill=150)  # vessel
    d.ellipse((120, 186, 200, 219), fill=132)  # vertebra + paraspinal
    d.ellipse((83, 96, 112, 125), fill=96)  # nodule (right upper field)
    img = Image.blend(img, _noise(SIZE, 14, 1), 0.18).filter(ImageFilter.GaussianBlur(0.8))
    d = ImageDraw.Draw(img)
    d.text((8, 6), "R", fill=210)
    d.text((302, 6), "L", fill=210)
    d.line((262, 229, 306, 229), fill=210, width=2)
    return img


def ebus() -> Image.Image:
    """Draw a fake radial EBUS view: dark speckled sector with a target node.

    The speckle is composited *through the sector mask*: blending noise over
    the whole canvas and re-blacking the sides leaves a lit rectangle above
    the arc, which reads as a rendering artefact rather than an ultrasound.
    """
    sector = Image.new("L", SIZE, 0)
    d = ImageDraw.Draw(sector)
    d.pieslice(SECTOR, start=35, end=145, fill=255)

    body = Image.new("L", SIZE, 40)
    d = ImageDraw.Draw(body)
    d.pieslice(SECTOR, start=55, end=125, fill=58)
    d.ellipse((120, 77, 214, 152), fill=96)  # lymph node
    d.ellipse((141, 94, 194, 134), fill=74)
    d.line((48, 32, 152, 112), fill=190, width=3)  # needle
    body = Image.blend(body, _noise(SIZE, 34, 7), 0.42).filter(ImageFilter.GaussianBlur(0.5))

    img = Image.new("L", SIZE, 6)
    img.paste(body, (0, 0), sector)
    d = ImageDraw.Draw(img)
    for i in range(5):
        d.line((298, 48 + i * 24, 308, 48 + i * 24), fill=200, width=1)
    d.text((8, 222), "EBUS  7.5 MHz", fill=190)
    return img


def bronchoscopy() -> Image.Image:
    """Draw a fake white light bronchoscopy view: carina between two orifices."""
    img = Image.new("RGB", SIZE, (6, 4, 4))
    d = ImageDraw.Draw(img)
    d.ellipse((35, 3, 285, 237), fill=(196, 118, 108))  # mucosa
    d.ellipse((56, 21, 264, 219), fill=(178, 100, 92))
    d.ellipse((77, 59, 149, 168), fill=(96, 44, 44))  # right main
    d.ellipse((171, 59, 243, 168), fill=(88, 40, 40))  # left main
    d.polygon([(160, 48), (141, 179), (179, 179)], fill=(214, 140, 130))  # carina
    layer = img.filter(ImageFilter.GaussianBlur(2.4))
    img = Image.blend(img, layer, 0.45)
    grain = _noise(SIZE, 10, 3).convert("RGB")
    img = Image.blend(img, grain, 0.10)
    d = ImageDraw.Draw(img)
    d.ellipse((120, 32, 142, 53), fill=(255, 244, 232))  # specular highlight
    return img


def histology() -> Image.Image:
    """Draw a fake H&E slide: pink stroma with purple nuclear clusters."""
    img = Image.new("RGB", SIZE, (238, 208, 224))
    d = ImageDraw.Draw(img)
    random.seed(11)
    for _ in range(200):
        x, y = random.randint(0, SIZE[0]), random.randint(0, SIZE[1])
        r = random.randint(3, 8)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(126, 46, 132))
    for _ in range(50):
        x, y = random.randint(0, SIZE[0]), random.randint(0, SIZE[1])
        r = random.randint(9, 22)
        d.ellipse((x - r, y - r, x + r, y + r), outline=(198, 132, 176), width=3)
    img = img.filter(ImageFilter.GaussianBlur(1.1))
    grain = _noise(SIZE, 12, 5).convert("RGB")
    # Quantized: a smooth H&E field costs about 3x more as truecolor PNG for no
    # visible gain once embedded as a base64 data URI in a template.
    return Image.blend(img, grain, 0.12).quantize(colors=64).convert("RGB")


IMAGES = {"ct": ct, "ebus": ebus, "bronchoscopy": bronchoscopy, "histology": histology}


def main(argv: list[str]) -> int:
    """Write every placeholder PNG and print its data URI."""
    out_dir = Path(argv[1]) if len(argv) > 1 else Path("/tmp/medical-placeholders")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, factory in IMAGES.items():
        path = out_dir / f"{name}.png"
        factory().save(path, optimize=True)
        uri = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
        print(f"{name}\t{len(path.read_bytes())} bytes\t{uri[:60]}...")
        (out_dir / f"{name}.b64.txt").write_text(uri, encoding="utf-8")
    print(f"\nWritten to {out_dir} (PNG + .b64.txt data URIs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
