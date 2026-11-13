"""Copies a build's checks and renders into the docs page's baseline folder (docs/jclass-1).

    python docs_jclass.py <out dir> <docs baseline dir>

<out dir> is where loft.py, build_jclass.py, fairness.py and render_jclass.py wrote (renders in <out>/renders). Copies
build.json, hydrostatics.json, sections.json and fairness.json, and writes each render, the lines drawing and a contact
sheet of the renders as JPEGs under 300 KB (docs images are plain git, not LFS). Needs Pillow.
"""
import os
import shutil
import sys

from PIL import Image

OUT, DOCS = sys.argv[1], sys.argv[2]
RENDERS = ["clay_profile", "clay_plan", "clay_bow34", "clay_stern34", "clay_bow", "clay_stern", "clay_under",
           "zebra_bow34", "zebra_under", "zebra_profile", "afloat_34", "afloat_profile"]
LIMIT = 290_000


def save(im, path, width):
    im = im.convert("RGB")
    im = im.resize((width, round(width * im.size[1] / im.size[0])), Image.LANCZOS)
    for q in (88, 82, 76, 70, 64, 58):
        im.save(path, quality=q, optimize=True)
        if os.path.getsize(path) < LIMIT:
            return
    raise SystemExit(f"{path} is still over {LIMIT} bytes")


def main():
    os.makedirs(DOCS, exist_ok=True)
    for name in ("build.json", "hydrostatics.json", "sections.json", "fairness.json"):
        shutil.copy(os.path.join(OUT, name), os.path.join(DOCS, name))
    for n in RENDERS:
        save(Image.open(os.path.join(OUT, "renders", n + ".png")), os.path.join(DOCS, n + ".jpg"), 1200)
    save(Image.open(os.path.join(OUT, "lines.png")), os.path.join(DOCS, "lines.jpg"), 1800)
    sheet = Image.new("RGB", (1800, 337 * 4), "white")
    for k, n in enumerate(RENDERS):
        im = Image.open(os.path.join(OUT, "renders", n + ".png")).convert("RGB").resize((600, 337), Image.LANCZOS)
        sheet.paste(im, ((k % 3) * 600, (k // 3) * 337))
    save(sheet, os.path.join(DOCS, "sheet.jpg"), 1800)
    print("docs_jclass: wrote", DOCS)


main()
