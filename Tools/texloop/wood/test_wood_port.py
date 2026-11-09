"""Texture loop, wood: fails if wood_port.py (the numpy mirror the scores come from) and BOAT_CODE's wood block drift.

    python3 Tools/texloop/wood/test_wood_port.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# Each expression as it is written in the HLSL; the Python must carry the same with D/T/sat in place of dirtK/timeK/saturate.
SHARED = [
    "0.68, 0.56, 0.48", "1.03, 0.97, 0.84", "0.62, 0.50, 0.34", "0.125, 0.105, 0.08", "0.24, 0.21, 0.17",
    "0.215, 0.205, 0.19", "1.12, 0.98, 0.82",
    "1.4 * pow(saturate(dirtK - 0.24), 2.0)", "0.725 - 0.62 * cover + 0.14 * cover * cover",
    "0.05 + 0.10 * (1.0 - saturate((dirtK - 0.24) * 2.0))", "saturate((dirtK - 0.5) * 2.5)", "saturate((dirtK - 0.6) * 2.5)",
    "saturate((dirtK - 0.2) * 2.0)", "saturate((dirtK - 0.3) * 3.0)", "saturate(timeK * 6.0)", "saturate(timeK * 3.0)",
    "saturate((dirtK - 0.45) * 2.0) * (0.68 + 0.2 * pn + 0.12 * (1.0 - ring))", "saturate((dirtK - 0.6) * 3.0)",
    "0.72 + 0.28 * saturate(pn * 2.0 - 0.3)", "smoothstep(0.5, 0.9,", "pn * 0.75 + 0.25 * (1.0 - ring) + 0.06 * (fl - 0.5)",
    "0.72 - 0.10 *", "1.15 - 0.06 *", "lerp(0.70, 1.16,", "0.45, 0.8 * satin", "0.75 + 0.06", "0.2 * lift",
    "1.0 - 0.25 * satin", "1.0 - 0.2 * ", "0.12 + 0.18 *", "0.8 + 0.4 *", "lerp(0.84, 1.05, ring)",
    "0.4 * saturate(timeK * 1.5 - 0.3)", "0.65 * dings", "thr - 0.22", "0.5 * dull", "1.0 - 0.6 * dull", "1.0 - 0.6 * oldK",
    "smoothstep(0.0, 0.035,", "lerp(0.70, 1.15,", "lerp(1.10, 0.86, ring)", "0.4 * sv * (1.0 - ring)", "smoothstep(0.45, 0.8,", "0.4 + 0.6 *",
    "0.9 * ms", "* 1.18", "col * 0.8",
]


def norm_py(s):
    s = re.sub(r"\bsat\(", "saturate(", s)
    s = re.sub(r"\bD\b", "dirtK", s)
    s = re.sub(r"\bT\b", "timeK", s)
    s = re.sub(r"\*\* 2\.0", "POW2", s)
    s = s.replace("(1 - ring)", "(1.0 - ring)")
    return s


def main():
    mm = open(os.path.join(ROOT, "scripts", "make_materials.py")).read()
    a = mm.index("else if (surf == 6 || surf == 7)")
    hl = mm[a:mm.index("float cav = 0.0;", a)] + mm[mm.index("else if (surf == 6)                  // varnished wood"):mm.index("else if (surf == 1 || surf == 5)")]
    py = norm_py(open(os.path.join(HERE, "wood_port.py")).read())
    py = py.replace("1.4 * saturate(dirtK - 0.24) POW2", "1.4 * pow(saturate(dirtK - 0.24), 2.0)")
    bad = [s for s in SHARED if s not in hl or s not in py]
    for s in bad:
        print("DRIFT:", s, "| hlsl" if s not in hl else "", "| python" if s not in py else "")
    # the detail maps' tile and the shader's
    js = json.load(open(os.path.join(ROOT, "Inputs", "boat-detail", "detail_textures.json")))
    for k in ("WoodVarnish", "TeakWeathered"):
        if js[k]["tile_m"] != [0.25, 0.125]:
            bad.append(k)
            print("DRIFT: detail_textures.json", k, js[k]["tile_m"])
    if "(surf == 6 || surf == 7) ? float2(0.25, 0.125)" not in mm:
        bad.append("tile")
        print("DRIFT: BOAT_CODE wood tile is not 0.25 x 0.125")
    print("ok" if not bad else f"{len(bad)} drift(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
