"""Checks for the club-dock texture loop (docs/texloop-dock). Run: python Tools/texloop/dock/test_dock.py

1. M_WorldSurface's dkT/dkD lines are the boats' time/dirt split (Tools/texloop/wear.py) at every level.
2. Every dock pattern (deck 1, pilings 9, floats 11, the ramp) runs at every level with finite, in-range output.
3. MI_World_Floats (WORLD_LIBRARY) matches KitLook's Floats in WorldKit.cpp (pattern 11, colour, roughness).
"""
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import hlsl_np as H  # noqa: E402
import render_levels as R  # noqa: E402
import wear  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def test_split():
    code = H.world_code()
    lines = [l for l in code.splitlines() if l.startswith("float dkT") or l.startswith("float dkD")]
    assert len(lines) == 2, lines
    for lv, (age, care) in R.LV.items():
        ns = H.run("\n".join(lines), dict(uv=np.zeros((1, 1, 2)), age=age, care=care))
        assert abs(float(np.ravel(ns["dkT"])[0]) - wear.time_k(age, care)) < 1e-6, lv
        assert abs(float(np.ravel(ns["dkD"])[0]) - wear.dirt_k(age, care)) < 1e-6, lv


def test_patterns():
    code = H.world_code()
    x = (np.arange(64) + 0.5) / 64 * 2.0
    U, V = np.meshgrid(x, x)
    uv = np.stack([U, V], -1)
    for look, flag in (("Decking", 0.0), ("Pilings", 0.0), ("Floats", 0.0), ("Concrete", 4.0)):
        for zcm in (-20.0, 5.0, 35.0, 150.0):
            wp = np.stack([U * 100, V * 100, np.full(U.shape, zcm)], -1)
            for lv in R.LV:
                c, r, bump = R.surface(code, R.LOOK_NEW[look], uv, wp, lv, flag=flag)
                assert np.isfinite(c).all() and np.isfinite(r).all() and np.isfinite(bump).all(), (look, lv, zcm)
                assert c.min() >= 0.0 and c.max() <= 1.0 and r.min() >= 0.0 and r.max() <= 1.0, (look, lv, zcm)


def test_floats_look():
    src = open(os.path.join(REPO, "scripts", "make_materials.py"), encoding="utf-8").read()
    m = re.search(r'"Floats": \(\(([\d.]+), ([\d.]+), ([\d.]+)\), ([\d.]+), ([\d.]+),', src)
    py = [float(v) for v in m.groups()]
    cpp = open(os.path.join(REPO, "Source", "SailingSim", "Private", "WorldKit.cpp"), encoding="utf-8").read()
    m2 = re.search(r'TEXT\("Floats"\), FLinearColor\(([\d.]+)f, ([\d.]+)f, ([\d.]+)f\), ([\d.]+)f, ([\d.]+)f,', cpp)
    assert [float(v) for v in m2.groups()] == py, (py, m2.groups())
    assert py[4] == 11.0


if __name__ == "__main__":
    for t in (test_split, test_patterns, test_floats_look):
        t()
        print("ok", t.__name__)
