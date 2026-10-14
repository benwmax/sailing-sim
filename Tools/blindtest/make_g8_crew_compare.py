#!/usr/bin/env python3
"""Graphics G8 (crew): before/after images for the people scenes. For each scene, the G6 frame (round 8,
docs/graphics-6/game/) beside the G8 frame (docs/graphics-8-crew/game/, the same arguments from
docs/graphics-5/game/final.csv), full frame at half size, then the crew cropped and enlarged so the change is visible at
the size Bean marks them. Writes docs/graphics-8-crew/compare/<scene>.jpg and <scene>-crew.jpg.
Usage: Tools/venv/bin/python -I Tools/blindtest/make_g8_crew_compare.py"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BEFORE = os.path.join(ROOT, "docs", "graphics-6", "game")
AFTER = os.path.join(ROOT, "docs", "graphics-8-crew", "game")
OUT = os.path.join(ROOT, "docs", "graphics-8-crew", "compare")
# The crew's box in the 1440x1080 capture (left, top, right, bottom).
CROPS = {"game-05": (560, 480, 1040, 840), "game-06": (600, 420, 1300, 945)}


def label(im, text):
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except OSError:
        font = ImageFont.load_default()
    w = int(d.textlength(text, font=font)) + 20
    d.rectangle((0, 0, w, 28), fill=(0, 0, 0))
    d.text((10, 4), text, fill=(255, 255, 255), font=font)


def pair(a, b, size):
    out = Image.new("RGB", (2 * size[0], size[1]))
    for i, (im, text) in enumerate(((a, "G6 (round 8)"), (b, "G8 crew"))):
        im = im.resize(size, Image.LANCZOS)
        label(im, text)
        out.paste(im, (i * size[0], 0))
    return out


os.makedirs(OUT, exist_ok=True)
for scene, box in CROPS.items():
    a = Image.open(os.path.join(BEFORE, scene + ".png")).convert("RGB")
    b = Image.open(os.path.join(AFTER, scene + ".png")).convert("RGB")
    pair(a, b, (720, 540)).save(os.path.join(OUT, scene + ".jpg"), quality=88)
    w, h = box[2] - box[0], box[3] - box[1]
    scale = 720 / w
    pair(a.crop(box), b.crop(box), (720, int(h * scale))).save(os.path.join(OUT, scene + "-crew.jpg"), quality=90)
    print(scene, "ok")
