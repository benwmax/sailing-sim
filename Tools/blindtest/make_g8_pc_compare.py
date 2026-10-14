"""Graphics G8 (PC): docs/graphics-8/compare/<scene>.jpg puts each scene's capture before the round's changes
(docs/graphics-8/before/) beside the final one (docs/graphics-8/game/), half size, and <scene>-<part>.jpg crops of the
parts each fix is about at full size.
Usage: python Tools/blindtest/make_g8_pc_compare.py"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs", "graphics-8")
OUT = os.path.join(DOCS, "compare")
# Crops (x0, y0, x1, y1 in the 1440x1080 frame) of what each fix changed.
CROPS = {
    "game-01": {"fleet": (500, 250, 1440, 560)},
    "game-04": {"storm": (0, 0, 900, 420)},
    "game-05": {"cumulus": (0, 0, 1440, 460)},
    "game-07": {"dock": (780, 600, 1440, 1080)},
    "game-08": {"storm": (700, 0, 1440, 480)},
    "game-09": {"trees": (60, 280, 1300, 600)},
}


def side(a, b):
    w = Image.new("RGB", (a.width + b.width + 8, max(a.height, b.height)), (255, 255, 255))
    w.paste(a, (0, 0))
    w.paste(b, (a.width + 8, 0))
    return w


os.makedirs(OUT, exist_ok=True)
for k in range(1, 11):
    scene = f"game-{k:02d}"
    a = Image.open(os.path.join(DOCS, "before", scene + ".png")).convert("RGB")
    b = Image.open(os.path.join(DOCS, "game", scene + ".png")).convert("RGB")
    side(a.resize((a.width // 2, a.height // 2)), b.resize((b.width // 2, b.height // 2))).save(os.path.join(OUT, scene + ".jpg"), quality=88)
    for part, box in CROPS.get(scene, {}).items():
        side(a.crop(box), b.crop(box)).save(os.path.join(OUT, f"{scene}-{part}.jpg"), quality=90)
print("compare pages in", OUT)
