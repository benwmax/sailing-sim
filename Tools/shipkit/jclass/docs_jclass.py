"""Copies a build's checks and renders into a docs page's baseline folder (docs/jclass-1, docs/jclass-2).

    python docs_jclass.py <out dir> <docs baseline dir> [--slice 2]

<out dir> is where loft.py, build_jclass.py, fairness.py and render_jclass.py wrote (renders in <out>/renders). Slice 1
(the default) copies build.json, hydrostatics.json, sections.json and fairness.json and writes the clay, zebra and
afloat renders and the lines drawing. Slice 2 copies build.json, fairness.json (the moulded hull, as slice 1) and
<out>/shell/fairness.json as fairness_shell.json (the finished shell), and writes the paint renders and the build's
two drawings (plating.png, rudder_sections.png). Each image is a JPEG under 300 KB (docs images are plain git, not
LFS), with a contact sheet of the renders. Needs Pillow.
"""
import os
import shutil
import sys

from PIL import Image

ARGS, SLICE = [], 1
_it = iter(sys.argv[1:])
for _a in _it:
    if _a == "--slice":
        SLICE = int(next(_it))
    elif _a.startswith("--slice="):
        SLICE = int(_a.split("=", 1)[1])
    elif _a.startswith("--"):
        raise SystemExit(f"docs_jclass.py: unknown option {_a}")
    else:
        ARGS.append(_a)
if len(ARGS) != 2 or SLICE not in (1, 2):
    raise SystemExit("usage: docs_jclass.py <out dir> <docs baseline dir> [--slice 1|2]")
OUT, DOCS = ARGS
RENDERS = {
    1: ["clay_profile", "clay_plan", "clay_bow34", "clay_stern34", "clay_bow", "clay_stern", "clay_under",
        "zebra_bow34", "zebra_under", "zebra_profile", "afloat_34", "afloat_profile"],
    2: ["paint_profile", "paint_bow34", "paint_stern34", "paint_under", "paint_afloat34", "paint_bowline",
        "paint_rudder", "paint_slot", "paint_transom", "paint_plating"],
}[SLICE]
JSONS = {1: [("build.json", "build.json"), ("hydrostatics.json", "hydrostatics.json"),
             ("sections.json", "sections.json"), ("fairness.json", "fairness.json")],
         2: [("build.json", "build.json"), ("fairness.json", "fairness.json"),
             (os.path.join("shell", "fairness.json"), "fairness_shell.json")]}[SLICE]
DRAWINGS = {1: [("lines.png", "lines.jpg", 1800)],
            2: [("plating.png", "plating.jpg", 1800), ("rudder_sections.png", "rudder_sections.jpg", 1600)]}[SLICE]
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
    for src, dst in JSONS:
        shutil.copy(os.path.join(OUT, src), os.path.join(DOCS, dst))
    for n in RENDERS:
        save(Image.open(os.path.join(OUT, "renders", n + ".png")), os.path.join(DOCS, n + ".jpg"), 1200)
    for src, dst, width in DRAWINGS:
        save(Image.open(os.path.join(OUT, src)), os.path.join(DOCS, dst), width)
    rows = (len(RENDERS) + 2) // 3
    sheet = Image.new("RGB", (1800, 337 * rows), "white")
    for k, n in enumerate(RENDERS):
        im = Image.open(os.path.join(OUT, "renders", n + ".png")).convert("RGB").resize((600, 337), Image.LANCZOS)
        sheet.paste(im, ((k % 3) * 600, (k // 3) * 337))
    save(sheet, os.path.join(DOCS, "sheet.jpg"), 1800)
    print("docs_jclass: wrote", DOCS)


main()
