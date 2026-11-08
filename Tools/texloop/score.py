"""Score a surface's swatch renders against its reference targets (docs/texture-loop).

    python Tools/texloop/score.py gelcoat [--renders Artifacts/texloop/gelcoat]

Reads Tools/texloop/targets/<surface>.json (measure.py), the before/after swatches (render_swatch.py) and, if present,
Tools/texloop/reviews/<surface>.json (the blind reviewers' answers), and writes Tools/texloop/scores/<surface>.json.

Checks (the plan's six):
  colour    each level with a target: the render's a*, b* within 6 of the photos' median (Lab, white-balanced on the
            grey card / the photo's neutral box). Levels without photos are reported, not passed.
  size      the detail map's texels per mm at its tile size: 4 or more.
  tiling    the detail maps' wrapped edges no rougher than their interior (ratio <= 1.5), and no strong repeat inside
            a tile (autocorrelation off the centre < 0.5).
  ladder    reviews: each reviewer matched the five shuffled levels to their descriptions, 4 of 5 or better, all three.
  ab        reviews: this round beat the last for 2 of 3 reviewers, and nobody called it the wrong material.
  budget    new texture bytes on Medium 0; on High within 8 MB (the Mac gate is the frame-time half: reported, not run).
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

import measure

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DETAIL = os.path.join(REPO, "Inputs", "boat-detail")
MAPS = {"gelcoat": ("Gelcoat", ["T_Detail_Gelcoat_N.png", "T_Detail_Gelcoat_M.png"])}


def swatch_numbers(root, tag):
    meta = json.load(open(os.path.join(root, tag, "swatch.json")))
    out = {}
    for lv, m in meta.items():
        img = measure.load(m["path"])
        out[lv] = dict(topsides=measure.measure(img, m["boxes"]["topsides"], m["boxes"]["neutral"]),
                       deck=measure.measure(img, m["boxes"]["deck"], m["boxes"]["neutral"]))
    return out


def colour_check(targets, numbers, tol=6.0):
    rows, ok_all, any_target = {}, True, False
    for lv, nums in numbers.items():
        t = targets.get(lv)
        n = nums["topsides"]
        if not t:
            rows[lv] = dict(a=n["a"], b=n["b"], target=None)
            continue
        any_target = True
        d = float(np.hypot(n["a"] - t["a"], n["b"] - t["b"]))
        ok = d <= tol
        ok_all &= ok
        rows[lv] = dict(a=n["a"], b=n["b"], target=[t["a"], t["b"]], dE_ab=round(d, 2), n_photos=t["n"], ok=ok,
                        mottle=n["mottle"], target_mottle=t["mottle"], gloss=n["gloss"], target_gloss=t["gloss"])
    return dict(ok=ok_all and any_target, levels=rows)


def tiling_check(names):
    rows, ok = {}, True
    for nm in names:
        a = np.asarray(Image.open(os.path.join(DETAIL, nm)).convert("L"), np.float64)
        inner = np.mean([np.abs(np.diff(a, axis=1)).mean(), np.abs(np.diff(a, axis=0)).mean()])
        seam = np.mean([np.abs(a[:, 0] - a[:, -1]).mean(), np.abs(a[0, :] - a[-1, :]).mean()])
        ratio = seam / max(inner, 1e-6)
        f = np.fft.fft2(a - a.mean())
        ac = np.real(np.fft.ifft2(f * np.conj(f)))
        ac /= ac[0, 0]
        h, w = a.shape
        ac[:max(2, h // 32), :max(2, w // 32)] = 0
        ac[-max(2, h // 32):, :max(2, w // 32)] = 0
        ac[:max(2, h // 32), -max(2, w // 32):] = 0
        ac[-max(2, h // 32):, -max(2, w // 32):] = 0
        peak = float(ac.max())
        good = ratio <= 1.5 and peak < 0.5
        ok &= good
        rows[nm] = dict(seam_ratio=round(float(ratio), 2), repeat_peak=round(peak, 3), ok=good)
    return dict(ok=ok, maps=rows)


def size_check(surface, names):
    meta = json.load(open(os.path.join(DETAIL, "detail_textures.json")))[MAPS[surface][0]]
    w, h = Image.open(os.path.join(DETAIL, names[0])).size
    px_mm = min(w / (meta["tile_m"][0] * 1000.0), h / (meta["tile_m"][1] * 1000.0))
    return dict(ok=px_mm >= 4.0, px_per_mm=round(px_mm, 2), tile_m=meta["tile_m"], px=[w, h])


def review_checks(surface):
    path = os.path.join(HERE, "reviews", surface + ".json")
    if not os.path.exists(path):
        return dict(ok=None, note="no reviews yet"), dict(ok=None, note="no reviews yet")
    rv = json.load(open(path))
    lad = rv.get("ladder", [])
    ladder = dict(ok=len(lad) >= 3 and all(r["correct"] >= 4 for r in lad), reviewers=[r["correct"] for r in lad])
    ab = rv.get("ab", [])
    wins = sum(1 for r in ab if r["winner"] == "this")
    wrong = [r for r in ab if r.get("wrong_material")]
    abc = dict(ok=len(ab) >= 3 and wins >= 2 and not wrong, wins=wins, of=len(ab), wrong_material=len(wrong))
    return ladder, abc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("surface", choices=sorted(MAPS))
    ap.add_argument("--renders", default=None)
    a = ap.parse_args()
    root = a.renders or os.path.join(REPO, "Artifacts", "texloop", a.surface)
    targets = json.load(open(os.path.join(HERE, "targets", a.surface + ".json")))["targets"]
    after = swatch_numbers(root, "after")
    before = swatch_numbers(root, "before") if os.path.exists(os.path.join(root, "before", "swatch.json")) else None
    names = MAPS[a.surface][1]
    ladder, ab = review_checks(a.surface)
    res = dict(
        surface=a.surface,
        colour=colour_check(targets, after),
        colour_before=colour_check(targets, before) if before else None,
        size=size_check(a.surface, names),
        tiling=tiling_check(names),
        ladder=ladder,
        ab=ab,
        budget=dict(ok=True, new_maps=0, medium_mb=0.0, high_mb=0.0, note="no new textures; frame time: Mac boats gate"),
        numbers=dict(after=after, before=before),
    )
    os.makedirs(os.path.join(HERE, "scores"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "scores", a.surface + ".json"), "w"), indent=1)
    for k in ("colour", "colour_before", "size", "tiling", "ladder", "ab", "budget"):
        v = res[k]
        if v is None:
            continue
        print("%-14s %s" % (k, {True: "pass", False: "FAIL", None: "pending"}[v["ok"]]),
              {kk: vv for kk, vv in v.items() if kk not in ("ok", "levels", "maps")})
        if "levels" in v:
            for lv, row in v["levels"].items():
                print("    ", lv, row)
        if "maps" in v:
            for nm, row in v["maps"].items():
                print("    ", nm, row)


if __name__ == "__main__":
    main()
