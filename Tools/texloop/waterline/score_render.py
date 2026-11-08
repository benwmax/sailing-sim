"""Score the hero renders' waterline the way the reference photo was measured (measure_waterline.trace), against the
render targets in Tools/texloop/refs/waterline.json.

    python3 Tools/texloop/waterline/score_render.py <render_dir>

Uses the `close` view (render_hero.py), where the bottom paint's edge sits at row 371; the line is searched in the 52 px
above it. L0 must show nothing; L4's band is taller than the window, so it is judged by the swatch and the reviewers.
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

EDGE = 371


def score(d):
    t = json.load(open(os.path.join(HERE, "..", "refs", "waterline.json")))["targets"]
    out = {}
    for lv in ("L0", "L1", "L2", "L3"):
        a = np.asarray(Image.open(os.path.join(d, "after_%s_close.png" % lv)).convert("RGB")).astype(float) / 255.0
        lab = color.rgb2lab(a)
        s = [q for q in mw.trace(lab, (40, EDGE - 30), (1160, EDGE - 30), half=26) if q["y"] < EDGE - 2]
        m = mw.summarise(s, 8.0)
        lo, hi = t[lv]["render_Y_ratio"]
        out[lv] = {"line_Y_ratio": m["line_Y_ratio"], "line_dLab": m["line_dLab"], "target": [lo, hi],
                   "pass": bool(lo <= m["line_Y_ratio"] <= hi)}
        print(lv, out[lv])
    json.dump(out, open(os.path.join(d, "render_score.json"), "w"), indent=1)
    return out


if __name__ == "__main__":
    score(sys.argv[1])
