"""Measure a sailcloth reference photo: white-balance on a known white or grey patch in the same light, then the cloth's
mean and spread in CIELAB. Boxes are x0,y0,x1,y1 in the photo's pixels.

    python3 -I sailcloth_measure.py PHOTO --cloth x0,y0,x1,y1 --white x0,y0,x1,y1 [--white-albedo 0.80]

The white patch's albedo is an assumption (white paint on a boom about 0.80); it sets the lightness, so a target's L*
is only as good as that number. The hue (a*, b*) does not depend on it.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sailcloth_lab import lin_to_lab, lin_to_srgb, srgb_to_lin  # noqa: E402


def box(s):
    return [int(v) for v in s.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--cloth", type=box, required=True)
    ap.add_argument("--white", type=box, required=True)
    ap.add_argument("--white-albedo", type=float, default=0.80)
    a = ap.parse_args()
    im = np.asarray(Image.open(a.photo).convert("RGB")).astype(float) / 255.0
    x0, y0, x1, y1 = a.cloth
    cl = srgb_to_lin(im[y0:y1, x0:x1].reshape(-1, 3))
    x0, y0, x1, y1 = a.white
    wh = srgb_to_lin(im[y0:y1, x0:x1].reshape(-1, 3)).mean(0)
    lin = cl * (a.white_albedo / wh)
    lab = lin_to_lab(lin)
    y = np.array([0.2126, 0.7152, 0.0722])
    out = {"lab_mean": [round(float(v), 2) for v in lab.mean(0)], "lab_sd": [round(float(v), 2) for v in lab.std(0)],
           "srgb_mean": [round(float(v) * 255, 1) for v in lin_to_srgb(lin.mean(0))],
           "cloth_over_white_luminance": round(float((cl @ y).mean() / (wh @ y)), 3), "white_albedo": a.white_albedo}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
