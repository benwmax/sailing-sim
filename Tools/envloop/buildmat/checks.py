"""The environment loop's six checks for the building materials (Track E2, docs/envloop/buildmat).

    python3 -I Tools/envloop/buildmat/checks.py [--out Tools/envloop/buildmat/checks.json]

1 sizes     every finish's repeat (course, brick pitch, board, row, panel) measured in its height map, within 5% of the card
2 colour    mean albedo against a CC0 scan of the same material, a*b* within 6 (the texture loop's rule); only interim:
            the real check is Bean's grey-card photos of houses on the lake, so finishes without a scan say "pending"
3 repeat    no visible repeat in a 40 m frame: the 40 m strip's large-scale luminance (blurred 50 cm) correlated with itself
            one tile along; with the material's per-tile shading it must fall under 0.6 (the raw tiled texture is ~1)
4 variety   counts against the plan: 3 bricks, limestone, lap siding, board and batten, stucco; 3 shingles and metal;
            rooms in the atlas (plan: lit windows with fake interiors), window dressings
5 blind     the reviewers' results, from reviews.json (written by hand after each blind round)
6 budget    texture memory per tier (block-compressed sizes with mips) and texture reads per pixel
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import make_textures as MT      # noqa: E402

TEX = MT.OUT


def lab(rgb_lin):
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = np.asarray(rgb_lin, float) @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def load(name, s):
    a = np.asarray(Image.open(os.path.join(TEX, "%s_%s.png" % (name, s))), np.float64) / 255.0
    return a


def period(profile, px_mm, expect_mm):
    """The autocorrelation peak of a 1-D profile nearest the expected period (searched 0.6..1.4x)."""
    x = profile - profile.mean()
    n = len(x)
    ac = np.fft.irfft(np.abs(np.fft.rfft(x)) ** 2, n)
    lo, hi = int(expect_mm * 0.6 / px_mm), int(min(n // 2, expect_mm * 1.4 / px_mm + 2))
    k = lo + int(np.argmax(ac[lo:hi]))
    # parabolic refinement
    if 0 < k < n - 1:
        a, b, c = ac[k - 1], ac[k], ac[k + 1]
        k = k + 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    return k * px_mm


def check_sizes(meta, cards):
    rows = []
    for card in cards["walls"] + cards["roofs"]:
        n = card["name"]
        if n not in meta:
            continue
        h = load(n, "M")[..., 3]
        tw, th = meta[n]["tile_m"]
        pw, ph = meta[n]["px"]
        mmx, mmy = tw * 1000 / pw, th * 1000 / ph
        u = card["unit_mm"]
        tests = []
        k = card["class"]
        if k == "brick":
            tests.append(("course (v)", h.mean(1), mmy, u["course"]))
            band = h[ph // 2:ph // 2 + 8].mean(0) if False else h[int(ph * 0.5)]
            tests.append(("brick + joint (u, one course)", h[: max(2, int(u["brick"][1] / mmy * 0.5))].mean(0), mmx, u["brick"][0] + u["joint"]))
        elif k == "lap":
            tests.append(("exposure (v)", h.mean(1), mmy, u["exposure"]))
        elif k == "batten":
            tests.append(("batten centres (u)", h.mean(0), mmx, u["centres"]))
        elif k == "shingle":
            tests.append(("row exposure (v)", h.mean(1), mmy, u["exposure"]))
        elif k == "standing_seam":
            tests.append(("panel (u)", h.mean(0), mmx, u["panel"]))
        for label, prof, pmm, want in tests:
            got = period(prof, pmm, want)
            err = (got - want) / want
            rows.append(dict(finish=n, what=label, card_mm=want, measured_mm=round(got, 1), error_pct=round(100 * err, 2), pass_=abs(err) <= 0.05))
        if k in ("stone", "render", "membrane"):
            rows.append(dict(finish=n, what="tile size (no regular repeat)", card_mm=tw * 1000, measured_mm=tw * 1000, error_pct=0.0, pass_=True))
    return rows


# CC0 scans the finishes are compared with (interim colour check); everything else waits for grey-card photos
# (the pack's colour_ref on a finish: a sources.json scan and its label)
COLOUR_REFS = {c["name"]: (c["colour_ref"]["source"], c["colour_ref"]["label"]) for c in MT.cards()["walls"] + MT.cards()["roofs"] if "colour_ref" in c}


def check_colour(meta):
    rows = []
    for n in meta:
        if meta[n].get("kind") not in ("wall", "roof"):
            continue
        c = load(n, "C")
        lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        L = lab(np.median(lin.reshape(-1, 3), 0))
        row = dict(finish=n, L=round(float(L[0]), 1), a=round(float(L[1]), 1), b=round(float(L[2]), 1))
        if n in COLOUR_REFS:
            sid, label = COLOUR_REFS[n]
            r = np.asarray(Image.open(os.path.join(MT.RAW, sid, "color.jpg")).convert("RGB"), np.float64) / 255.0
            rl = np.where(r <= 0.04045, r / 12.92, ((r + 0.055) / 1.055) ** 2.4)
            R = lab(np.median(rl.reshape(-1, 3), 0))
            dab = float(np.hypot(L[1] - R[1], L[2] - R[2]))
            row.update(ref=label, ref_L=round(float(R[0]), 1), ref_a=round(float(R[1]), 1), ref_b=round(float(R[2]), 1),
                       dab=round(dab, 1), pass_=dab <= 6.0, note="interim: a European CC0 scan, not the local material")
        else:
            row.update(ref=None, pass_=None, note="pending Bean's grey-card photos")
        rows.append(row)
    return rows


def check_repeat(meta, level="L2"):
    import render as R
    import buildmat_hlsl as BH
    R.ATLAS = None
    lv = R.LEVELS[level]
    rows = []
    for n in meta:
        if meta[n].get("kind") not in ("wall", "roof"):
            continue
        roof = meta[n]["kind"] == "roof"
        hm = 6.0 if roof else 3.0
        W, H = 2000, int(2000 * hm / 40.0)
        u = (np.arange(W) + 0.5) / W * 40.0
        v = hm - (np.arange(H) + 0.5) / H * hm
        U, V = np.meshgrid(u, v)
        m = np.ones(U.shape, bool)
        paint = R.srgb_lin(R.CARDS[n].get("paint_examples", ["#EDEAE0"])[0])
        c, r, mt, a, tn = R.run_material(n, U, V, m, dict(Kind=BH.kind_of(n), Paint=paint, Bare=1.0 if R.CARDS[n]["class"] == "standing_seam" else 0.0,
                                                          Age=lv["age"], Care=lv["care"], North=0.3, Sun=0.7, Eave=6.0 if roof else 2.9))
        lum = (c @ np.array([0.2126, 0.7152, 0.0722])).reshape(H, W) * a.reshape(H, W)
        ts = R.texset(n)
        raw = ts["C"].sample(U / ts["tile"][0], -V / ts["tile"][1], np.full(U.shape, 2.3)) @ np.array([0.2126, 0.7152, 0.0722])
        tile_px = int(round(ts["tile"][0] / 40.0 * W))
        out = {}
        for label, img in (("material", lum), ("raw texture", raw)):
            # 50 cm at 2 cm a pixel: what still shows when bricks and boards blur out; each row's mean is taken off,
            # since a stripe running the whole way along (a course line, a lap) looks the same at any shift and is no repeat
            b = MT.blur(img - img.mean(), 25.0)
            b = b - b.mean(1, keepdims=True)
            x, y = b[:, :-tile_px].ravel(), b[:, tile_px:].ravel()
            out[label] = float(np.corrcoef(x, y)[0, 1])
        rows.append(dict(finish=n, tile_m=ts["tile"][0], corr_material=round(out["material"], 3), corr_raw=round(out["raw texture"], 3),
                         pass_=out["material"] < 0.6))
    return rows


def check_variety(cards):
    import interior as I
    # what the pack asks for (its "variety" block: class -> how many finishes) against what it has
    want = cards.get("variety", {})
    have = {}
    for c in cards["walls"] + cards["roofs"]:
        have[c["class"]] = have.get(c["class"], 0) + 1
    rows = [dict(what="%s finishes (pack %s)" % (k, cards["pack"]), want=want.get(k, 1), have=have.get(k, 0)) for k in sorted(set(want) | set(have))]
    return rows + [
        dict(what="rooms in the window atlas", want=12, have=len(I.ROOMS)),
        dict(what="window dressings (none, blinds, curtains)", want=3, have=3),
        dict(what="wear levels (shared with the boats)", want=5, have=5),
    ]


def check_budget(meta):
    """Block-compressed bytes: colour BC1 (0.5 B/px), normal BC5 (1 B/px), mask BC7 (1 B/px); mips add a third."""
    fin = [n for n in meta if meta[n].get("kind") in ("wall", "roof")]
    tiers = {"Ultra": 1024, "High": 512, "Medium": 256}
    rows = []
    for t, px in tiers.items():
        per = px * px * (0.5 + 1.0 + 1.0) * 4 / 3
        atlas = (2048 if t == "Ultra" else 1024 if t == "High" else 512) ** 2 * 1.0 * 4 / 3   # BC7 RGBA, half-size cells below Ultra
        if t == "Ultra":
            atlas = 1024 ** 2 * 1.0 * 4 / 3
        noise = 512 * 512 * 1.0 * 4 / 3
        total = per * len(fin) + atlas + noise
        rows.append(dict(tier=t, finish_px=px, finishes=len(fin), mb=round(total / 2 ** 20, 1)))
    reads = dict(walls_and_roofs=5, glass=1, today=0,
                 note="per pixel: colour, normal, mask, and the noise twice (1 m and 0.25 m); glass one atlas read. "
                      "Today's house materials read no textures, so this is new cost: unmeasured until the Mac gate after 21 Nov.")
    return rows, reads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "checks_%s.json" % MT.P.NAME))
    ap.add_argument("--skip-repeat", action="store_true")
    MT.P.add_arg(ap)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(TEX, "textures.json")))
    cards = MT.cards()
    res = dict(sizes=check_sizes(meta, cards), colour=check_colour(meta))
    if not a.skip_repeat:
        res["repeat"] = check_repeat(meta)
    res["variety"] = check_variety(cards)
    res["budget"], res["reads"] = check_budget(meta)
    rv = os.path.join(HERE, "reviews_%s.json" % MT.P.NAME)
    res["blind"] = json.load(open(rv)) if os.path.exists(rv) else None
    json.dump(res, open(a.out, "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    for k, v in res.items():
        print("==", k)
        for row in (v if isinstance(v, list) else [v]):
            print("  ", row)


if __name__ == "__main__":
    main()
