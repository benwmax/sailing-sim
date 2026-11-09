"""Texture loop, wood: score a round against Tools/texloop/refs/wood.json (colour, roughness, failed share, size).

    python3 Tools/texloop/wood/score_wood.py [--before] [--out <dir>]

Prints one line per kind and level and writes <out>/score.json. Colour: the mean albedo of a 1 m x 0.25 m top face
(High: with the detail map) against the level's Lab target, pass at dE76 <= target dE. Roughness and coat: the
face's mean inside the target range. Failed: the share of failed film (varnish) inside the range. Size: the grain's
spectral centroid across the grain, from a 0.3 x 0.15 m close-up at 4 px/mm.
Needs numpy, Pillow, scikit-image.
"""
import json
import os
import sys

import numpy as np
from skimage import color

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wood_port as wp  # noqa: E402

LEVELS = {"L0": (0.0, 1.0), "L1": (0.3, 0.9), "L2": (6.0, 0.5), "L3": (30.0, 0.9), "L4": (20.0, 0.1)}
REFS = os.path.join(wp.ROOT, "Tools", "texloop", "refs", "wood.json")


def l2s(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def lab_of(lin):
    return color.rgb2lab(l2s(lin).reshape(-1, 1, 3)).reshape(-1, 3)


def grain_centroid_mm(lum, mm_across):
    prof = lum - lum.mean()
    F = np.abs(np.fft.rfft(prof - prof.mean(0), axis=0)).mean(1)
    freqs = np.arange(len(F))
    band = (freqs >= mm_across / 20) & (freqs <= mm_across / 1.5)
    return mm_across / ((F[band] * freqs[band]).sum() / F[band].sum())


def score(new=True, detail=True):
    tg = json.load(open(REFS))["targets"]
    rows = []
    for kind in ("varnish", "teak"):
        for lv, (age, care) in LEVELS.items():
            t = tg[kind][lv]
            o = wp.shade(kind, age, care, (1.0, 0.25), 1.0, detail, new=new)
            lab = lab_of(o["albedo"].reshape(-1, 3))
            m = lab.mean(0)
            dE = float(np.linalg.norm(m - np.array(t["lab"])))
            r = float(o["rough"].mean())
            c = float(o["coat"].mean())
            fs = float((o["failed"] > 0.5).mean())
            row = dict(kind=kind, level=lv, lab=[round(float(v), 1) for v in m], target=t["lab"], dE=round(dE, 1),
                       colour=bool(dE <= t["dE"]), rough=round(r, 2), rough_ok=bool(t["rough"][0] - 0.02 <= r <= t["rough"][1] + 0.02),
                       L_sd=round(float(lab[:, 0].std()), 1))
            if "coat" in t:
                row.update(coat=round(c, 2), coat_ok=bool(t["coat"][0] - 0.02 <= c <= t["coat"][1] + 0.02))
            if "failed" in t:
                row.update(failed=round(fs, 3), failed_ok=bool(t["failed"][0] - 0.01 <= fs <= t["failed"][1] + 0.01))
            rows.append(row)
    size = {}
    for kind in ("varnish", "teak"):
        o = wp.shade(kind, 0.0, 1.0, (0.3, 0.15), 4.0, True, new=new)
        lum = (o["albedo"] * np.array([0.3, 0.59, 0.11])).sum(-1)
        cen = grain_centroid_mm(lum, 150.0)
        tgt, tol = tg["size"][f"{kind}_grain_centroid_mm"]
        size[kind] = dict(centroid_mm=round(float(cen), 2), target=tgt, ok=bool(abs(cen - tgt) <= tol * tgt))
    return rows, size


def main():
    new = "--before" not in sys.argv
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    res = {}
    for tier, det in (("High", True), ("Medium", False)):
        rows, size = score(new, det)
        res[tier] = dict(levels=rows, size=size)
        print(f"== {tier} ({'this round' if new else 'before'})")
        for r in rows:
            flags = " ".join(k for k in ("colour", "rough_ok", "coat_ok", "failed_ok") if k in r and not r[k])
            print(f"{r['kind']:8s} {r['level']}  Lab {r['lab']} target {r['target']}  dE {r['dE']:5.1f}  rough {r['rough']}"
                  + (f"  coat {r['coat']}" if 'coat' in r else "") + (f"  failed {r['failed']}" if 'failed' in r else "")
                  + (f"  FAIL: {flags}" if flags else "  ok"))
        print("size", size)
    if out:
        os.makedirs(out, exist_ok=True)
        json.dump(res, open(os.path.join(out, "score.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
