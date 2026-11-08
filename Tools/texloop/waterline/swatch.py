"""Swatches of the lake waterline at the five wear levels, measured the way the reference photo was.

    python3 Tools/texloop/waterline/swatch.py [out_dir]

Draws a 100 x 50 cm hull patch per level (gelcoat over grey bottom paint, the waterline 20 cm from the bottom) at the
photo's scale (13.8 px/cm), runs measure_waterline's trace on it and checks heights, colour and L4's band against the
targets in Tools/texloop/refs/waterline.json (the line's brightness is judged on the hero render: score_render.py). Writes swatch_L0..L4.png, swatches.png and score.json.

Levels: each level's Age and Care (Tools/texloop/levels.json) through the shared split (Tools/texloop/wear.py).
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from skimage import color

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import measure_waterline as mw  # noqa: E402
import waterline as wl  # noqa: E402

PX_PER_CM = 13.8
GEL = (0.949, 0.941, 0.918)     # #F2F0EA, the hero J/22's gelcoat
BOTTOM = (0.557, 0.569, 0.561)  # #8E918F, grey bottom paint (Bean)


def levels():
    """{level: (dirt, time)} from the shared Tools/texloop/wear.py and levels.json."""
    sys.path.insert(0, os.path.join(HERE, ".."))
    import wear
    return {v["id"]: (round(float(wear.dirt_k(v["age"], v["care"])), 3), round(float(wear.time_k(v["age"], v["care"])), 3))
            for v in wear.levels()}, "Tools/texloop/wear.py"


def render(dirt, time, w_cm=100.0, h_cm=50.0, z0=-20.0, seed=3.0):
    w, h = int(w_cm * PX_PER_CM), int(h_cm * PX_PER_CM)
    x = np.arange(w)[None, :] / PX_PER_CM + np.zeros((h, 1))
    z = (h - 1 - np.arange(h))[:, None] / PX_PER_CM + z0 + np.zeros((1, w))
    return wl.shade(GEL, BOTTOM, x, z, dirt, time, seed), z0, h


def measure(img, z0, h, p):
    """The photo's trace, with its search window over the gelcoat side only (z from 0 to 1.6x the line's height)."""
    lab = color.rgb2lab(img)
    zr = lambda zc: int(h - 1 - (zc - z0) * PX_PER_CM)  # noqa: E731
    lo, hi = zr(0.05), zr(1.6 * p["line_h"] + 0.5)
    mid, half = (lo + hi) // 2, max(6, (lo - hi) // 2)
    s = mw.trace(lab, (30, mid), (img.shape[1] - 30, mid), half=half)
    return mw.summarise(s, PX_PER_CM) if s else None


def check(m, t):
    if m is None:
        return {"line_Y_ratio": None, "pass": t["line_Y_ratio"][0] >= 0.98}
    r, hcm = m["line_Y_ratio"], m["line_height_cm"]
    # flat albedo reads darker than the lit render, so only L4's band (no render target) is judged on brightness here
    ok = True if "line_Y_ratio" not in t else t["line_Y_ratio"][0] - 0.01 <= r <= t["line_Y_ratio"][1] + 0.01
    if t["line_height_cm"][1] > 0:
        ok = ok and t["line_height_cm"][0] * 0.9 <= hcm <= t["line_height_cm"][1] * 1.1
    if "line_dLab_max_chroma" in t:
        ok = ok and float(np.hypot(*m["line_dLab"][1:])) <= t["line_dLab_max_chroma"]
    if "line_dLab_chroma" in t:
        c = float(np.hypot(*m["line_dLab"][1:]))
        ok = ok and t["line_dLab_chroma"][0] <= c <= t["line_dLab_chroma"][1]
    return {"pass": bool(ok)}


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "Artifacts/texloop/waterline"
    os.makedirs(out, exist_ok=True)
    targets = json.load(open(os.path.join(HERE, "..", "refs", "waterline.json")))["targets"]
    lv, src = levels()
    res, tiles = {"levels_from": src}, []
    for k, (d, t) in lv.items():
        img, z0, h = render(d, t)
        Image.fromarray((img * 255).round().astype(np.uint8)).save(os.path.join(out, "swatch_%s.png" % k))
        tiles.append(img)
        m = None if d <= 0 else measure(img, z0, h, wl.params(d, t))
        res[k] = {"dirt": d, "time": t, "measured": m, **check(m, targets[k])}
        print(k, d, t, json.dumps(m and {kk: m[kk] for kk in ("line_Y_ratio", "line_height_cm", "line_dLab", "below_Y_ratio")}), res[k]["pass"])
    strip = np.concatenate([np.pad(ti, ((0, 0), (0, 12), (0, 0)), constant_values=1.0) for ti in tiles], 1)
    Image.fromarray((strip * 255).round().astype(np.uint8)).resize((strip.shape[1] // 3, strip.shape[0] // 3)).save(os.path.join(out, "swatches.png"))
    json.dump(res, open(os.path.join(out, "score.json"), "w"), indent=1)
