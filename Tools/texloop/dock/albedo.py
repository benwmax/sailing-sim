"""The dock surfaces' albedo (before lighting) per level, as Lab, beside the CC0 scans' targets (docs/texloop-dock).

    python Tools/texloop/dock/albedo.py [--rev main]

Each surface on a flat 2 x 2 m patch in its own UV metres, measured where the reference scans were (deck: dry boards,
gaps included; piling: dry wood above the band; float: the strip above the water; concrete: the ramp's dry upper part).
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import hlsl_np as H  # noqa: E402
import render_levels as R  # noqa: E402
from measure import srgb_to_lab  # noqa: E402

PATCH = {"deck": ("Decking", 45.0, 0.0), "piling": ("Pilings", 150.0, 0.0), "piling_band": ("Pilings", 20.0, 0.0),
         "float": ("Floats", 35.0, 0.0), "float_line": ("Floats", 5.0, 0.0), "concrete": ("Concrete", 100.0, 4.0),
         "ramp_wet": ("Concrete", 5.0, 4.0)}
TARGET_KEY = {"deck": "deck", "piling": "piling", "float": "float", "concrete": "concrete"}


def lab_of(lin):
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, 1), 1 / 2.4) - 0.055)
    return srgb_to_lab(np.clip(srgb, 0, 1))


def measure(code, looks, level, n=400):
    out = {}
    x = (np.arange(n) + 0.5) / n * 2.0
    U, V = np.meshgrid(x, x)
    uv = np.stack([U + 3.1, V + 2.3], -1)
    for k, (look, zcm, flag) in PATCH.items():
        wp = np.stack([uv[..., 0] * 100, uv[..., 1] * 100, np.full(U.shape, zcm)], -1)
        c, r, _ = R.surface(code, looks[look], uv, wp, level, flag=flag)
        lab = lab_of(np.clip(c, 0, 1))
        out[k] = [round(float(lab[..., i].mean()), 1) for i in range(3)] + [round(float(r.mean()), 2)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev")
    a = ap.parse_args()
    code = H.world_code(a.rev)
    looks = R.LOOK_OLD if a.rev else R.LOOK_NEW
    tg = json.load(open(os.path.join(os.path.dirname(HERE), "targets", "dock.json")))["targets"]
    res = {}
    for lv in ("L0", "L1", "L2", "L3", "L4"):
        res[lv] = measure(code, looks, lv)
        row = []
        for k, v in res[lv].items():
            t = tg.get(TARGET_KEY.get(k, ""), {}).get(lv)
            dab = f" dab={np.hypot(v[1]-t['a'], v[2]-t['b']):.1f} (L{t['L']} a{t['a']} b{t['b']})" if t else ""
            row.append(f"{k}: L{v[0]} a{v[1]} b{v[2]} r{v[3]}{dab}")
        print(lv, "\n   " + "\n   ".join(row))
    return res


if __name__ == "__main__":
    main()
