#!/usr/bin/env python3
"""Phase 8, step 5: the blind test pack. Takes the 10 game stills (docs/phase-8/blind-test/scenes.csv, captured with
scripts/capture-scenes.sh) and the 10 Commons photos they pair with, crops each to 4:3, resizes to 1200x900, saves a
plain JPEG (no EXIF or other metadata, so nothing gives the source away) and shuffles them into still01..still20.
Writes stills/, answer-key.csv (do not open before marking) and credits.md.
Usage: Tools/venv/bin/python Tools/blindtest/make_blind_pack.py <game dir> <commons dir with credits.json> [out dir] [seed]
(the out dir defaults to docs/phase-8/blind-test; each visual phase writes its own pack, e.g. docs/visual-3/blind, with a
new shuffle)"""
import csv, json, os, random, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "phase-8", "blind-test")


def fit(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    if w / h > 4 / 3:
        nw = int(h * 4 / 3); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w * 3 / 4); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((1200, 900), Image.LANCZOS)


def main(game_dir, commons_dir, out=OUT, seed=8):
    scenes = list(csv.DictReader(open(os.path.join(OUT, "scenes.csv"))))
    os.makedirs(out, exist_ok=True)
    credits = {os.path.splitext(os.path.basename(c["local"]))[0]: c for c in json.load(open(os.path.join(commons_dir, "credits.json")))}
    items = []
    for s in scenes:
        items.append({"source": "game", "file": os.path.join(game_dir, s["scene"] + ".png"), "name": s["scene"], "pair": s["pairs_with"]})
        c = credits[s["pairs_with"]]
        items.append({"source": "real", "file": os.path.join(commons_dir, os.path.basename(c["local"])), "name": s["pairs_with"],
                      "pair": s["scene"], "credit": c})
    random.Random(seed).shuffle(items)
    os.makedirs(os.path.join(out, "stills"), exist_ok=True)
    with open(os.path.join(out, "answer-key.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["still", "source", "name", "pairs_with", "title", "author", "license", "page"])
        for i, it in enumerate(items, 1):
            sid = f"still{i:02d}"
            fit(it["file"]).save(os.path.join(out, "stills", sid + ".jpg"), "JPEG", quality=88, optimize=True)
            c = it.get("credit", {})
            w.writerow([sid, it["source"], it["name"], it["pair"], c.get("file", ""), c.get("author", ""), c.get("license", ""), c.get("page", "")])
    used = [it["credit"] for it in items if it["source"] == "real"]
    with open(os.path.join(out, "credits.md"), "w") as f:
        f.write("# Blind test photo credits\n\nThe ten real photos come from Wikimedia Commons, cropped to 4:3 and resized "
                "(\"changes were made\"). Listed alphabetically, so the list does not say which still is which.\n\n")
        for c in sorted(used, key=lambda c: c["file"].lower()):
            f.write(f"- [{c['file']}]({c['page']}) by {c['author']}, [{c['license']}]({c['license_url']})\n")
    print("wrote", len(items), "stills")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else OUT, int(sys.argv[4]) if len(sys.argv) > 4 else 8)
