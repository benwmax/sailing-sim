"""Self-tests for the environment loop tools (docs/env-loop/README.md). python3 Tools/envloop/test_envloop.py

The station and lot tests need the lake bakes (git lfs pull --include "Content/TerrainData/RayHubbard.*"); they are
skipped, and say so, when the files are LFS pointers.
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lake  # noqa: E402
import repeat_check  # noqa: E402
import texel  # noqa: E402

FAILS = []


def ok(cond, what):
    print(("pass  " if cond else "FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def house_hash_u32(k, salt):
    """HouseKit.cpp HouseHash again, in numpy uint32 (wraps like C++), to hold lake.house_hash to it."""
    with np.errstate(over="ignore"):
        h = np.uint32(k) * np.uint32(0x9E3779B1) + np.uint32(salt) * np.uint32(0x85EBCA77)
        h ^= h >> np.uint32(15)
        h *= np.uint32(0x2C1B3C6D)
        h ^= h >> np.uint32(12)
        h *= np.uint32(0x297A2D39)
        h ^= h >> np.uint32(15)
    return int(h)


def main():
    ok(all(lake.house_hash(k, s) == house_hash_u32(k, s) for k in (0, 1, 7, 26893, 35164, 4294967295) for s in (0, 1, 51, 54)),
       "lake.house_hash matches the C++ uint32 arithmetic")
    ok(texel.need(2.0)["Ultra"] == 256 and texel.need(2.0)["High"] == 128 and texel.need(2.0)["Medium"] == 64,
       "texel: a 2 m tile wants 256 px on Ultra, 128 High, 64 Medium")
    ok(texel.check(4096, 4.0, "near")["ok"] and not texel.check(256, 4.0, "hero")["ok"], "texel: sharpness check")
    ok(abs(texel.screen_m(15.0) - 0.0131) < 0.0003, "texel: one screen pixel at 15 m is 13 mm")
    rng = np.random.default_rng(3)
    tiled = repeat_check.lay(rng.random((64, 64)), 2.0)
    from PIL import Image
    small = np.asarray(Image.fromarray((tiled * 255).astype(np.uint8)).resize((400, 400), Image.BILINEAR), float)
    ok(repeat_check.repeat_peak(small) > 0.9, "repeat: a plain 2 m tile over 40 m repeats")
    ok(repeat_check.repeat_peak(rng.random((400, 400))) < 0.1, "repeat: noise does not")
    r = subprocess.run([sys.executable, os.path.join(HERE, "check_card.py"), os.path.join(HERE, "cards", "_template.json")], capture_output=True, text=True)
    ok(r.returncode == 0, "check_card: the template card passes")
    sc = json.load(open(os.path.join(HERE, "size_card.json")))
    ok(all("source" in v and "value" in v for v in sc["sizes"].values()), "size card: every row has a value and a source")
    st = json.load(open(os.path.join(HERE, "stations.json")))
    ok(len(st["stations"]) == 10 and all(len(s["cameras"]) == 3 for s in st["stations"]), "stations: ten, three cameras each")
    ok(all(not c["problems"] for s in st["stations"] for c in s["cameras"]), "stations: every camera clear")
    rows = list(csv.DictReader(open(os.path.join(HERE, "stations.csv"))))
    ok(len(rows) == 30 and all('"' not in r["args"] for r in rows), "stations.csv: 30 scenes, no quotes in args (capture-scenes.sh splits on spaces)")
    for s in st["stations"]:
        for c in s["cameras"]:
            a = c["args"]
            sa = [float(v) for v in a.split("-SailingStartAt=")[1].split()[0].split(",")]
            cw = [float(v) for v in a.split("-SailingCamWorld=")[1].split()[0].split(",")]
            cam = (sa[0] + cw[0], sa[1] + cw[1])
            if abs(cam[0] - c["camera_map"][0]) > 0.2 or abs(cam[1] - c["camera_map"][1]) > 0.2:
                ok(False, "stations: %s start + CamWorld lands on its camera" % c["scene"])
                break
    else:
        ok(True, "stations: every start + CamWorld lands on its camera")
    try:
        L = lake.Lake()
    except SystemExit as e:
        print("skip  lake bakes not pulled:", e)
        L = None
    if L is not None:
        ok(abs(float(L.height_at(5.5, -37.5)) + 8.2) < 0.2, "lake: launch spot 0 is 8.2 m deep (RayHubbard.json)")
        lt = L.lot(26893)
        ok(lt is not None and lt["bank"] == "bulkhead" and lt["boathouse"],
           "lake: house 26893's lot has a bulkhead and a boathouse (the PC's before still 04 shows both)")
        for s in st["stations"]:
            for c in s["cameras"]:
                if float(L.height_at(*c["camera_map"])) > -0.3:
                    ok(False, "lake: %s is over water" % c["scene"])
                    break
        ok(True, "lake: every station camera is over water")
    print("%d failing" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
