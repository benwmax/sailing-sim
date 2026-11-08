"""Measure the lake waterline line on a reference photo, relative to the clean gelcoat just above it.

    python3 Tools/texloop/waterline/measure_waterline.py <photo.jpg> --crop x0 y0 x1 y1 --line x0 y0 x1 y1 --scale <px per cm>

The photo stays in the git-ignored Data/Reference/raw/textures/Waterline/ (Bean's photos show people and are never
committed). --crop is the hull region in photo pixels; --line is two points on the line inside the crop (it is traced
within +-20 px of that segment); --scale comes from an object of known size (Texas registration letters are 3 in, 7.6 cm).

Prints the line's colour difference to the gelcoat above it (Lab, D65), its height in cm (full width at half depth,
along the vertical) and the bottom's darkening just below it. Everything is relative to the hull next to it, so it holds
under any light or exposure; the swatch renders are measured the same way (score_waterline.py).
"""
import argparse
import json

import numpy as np
from PIL import Image
from skimage import color


def trace(lab, p0, p1, step=20, half=20, col=4):
    L = lab[..., 0]
    out = []
    slope = (p1[1] - p0[1]) / max(1, p1[0] - p0[0])
    for x in range(int(p0[0]), int(p1[0]) + 1, step):
        yp = int(p0[1] + (x - p0[0]) * slope)
        if yp - half - 24 < 0 or yp + half + 16 > L.shape[0]:
            continue
        prof = L[yp - half:yp + half, x - col:x + col].mean(1)
        y = yp - half + int(np.argmin(prof))
        above = lab[y - 22:y - 8, x - col:x + col].reshape(-1, 3).mean(0)
        below = lab[y + 6:y + 14, x - col:x + col].reshape(-1, 3).mean(0)
        depth = prof.max() - prof.min()
        inside = prof < prof.min() + 0.5 * depth
        width = int(inside.sum())
        # the line's colour: the mean over its full width at half depth (not just its darkest rows), so a thin crisp
        # line and a soft wide one are compared fairly
        rows = np.where(inside)[0] + (yp - half)
        line = lab[rows.min():rows.max() + 1, x - col:x + col].reshape(-1, 3).mean(0)
        out.append(dict(x=x, y=y, above=above, line=line, below=below, width=width))
    return out


def summarise(samples, px_per_cm, cos_slope=1.0):
    A = np.array([s["above"] for s in samples])
    Ln = np.array([s["line"] for s in samples])
    B = np.array([s["below"] for s in samples])
    W = np.array([s["width"] for s in samples], float)
    d = Ln - A
    return {
        "samples": len(samples),
        "line_dE": round(float(np.linalg.norm(d, axis=1).mean()), 2),
        "line_dE_spread": round(float(np.linalg.norm(d, axis=1).std()), 2),
        "line_dLab": [round(float(v), 2) for v in d.mean(0)],
        "line_height_cm": round(float(np.median(W) * cos_slope / px_per_cm), 2),
        "below_dLab": [round(float(v), 2) for v in (B - A).mean(0)],
        "gelcoat_L_in_photo": round(float(A[:, 0].mean()), 1),
        # exposure-free: how much light the line and the bottom reflect against the gelcoat beside them (CIE Y ratio)
        "line_Y_ratio": round(float(np.mean(_Y(Ln[:, 0]) / _Y(A[:, 0]))), 3),
        "below_Y_ratio": round(float(np.mean(_Y(B[:, 0]) / _Y(A[:, 0]))), 3),
    }


def _Y(L):
    """CIE relative luminance from L*."""
    L = np.asarray(L, float)
    f = (L + 16.0) / 116.0
    return np.where(L > 8.0, f ** 3, L / 903.3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--crop", nargs=4, type=int, required=True)
    ap.add_argument("--line", nargs=4, type=int, required=True)
    ap.add_argument("--scale", type=float, required=True, help="pixels per cm at the line")
    a = ap.parse_args()
    im = np.asarray(Image.open(a.photo).convert("RGB")).astype(float) / 255.0
    x0, y0, x1, y1 = a.crop
    lab = color.rgb2lab(im[y0:y1, x0:x1])
    p0, p1 = a.line[:2], a.line[2:]
    slope = (p1[1] - p0[1]) / max(1, p1[0] - p0[0])
    s = trace(lab, p0, p1)
    print(json.dumps(summarise(s, a.scale, cos_slope=1.0 / np.sqrt(1 + slope * slope)), indent=1))


if __name__ == "__main__":
    main()
