"""Measure a surface's colour and finish in reference photos or in our renders, the same way for both (docs/texture-loop).

    python Tools/texloop/measure.py gelcoat                 # every reference with boxes -> Tools/texloop/targets/gelcoat.json
    python Tools/texloop/measure.py --image a.png --box 0.1,0.2,0.4,0.5 [--neutral x0,y0,x1,y1]

A box is fractions of the image (x0, y0, x1, y1, top-left origin). The neutral box (clouds on an overcast day, a grey
card, bare concrete) white-balances the photo first: its mean is scaled to grey, so a yellow cast from the light isn't
read as yellow gelcoat. Without one the photo is used as shot and the row says so.

Numbers (CIE Lab, D65, from sRGB):
  a, b        mean a* and b* (b* > 0 is yellow): the colour, independent of exposure
  chroma      mean sqrt(a*^2 + b*^2)
  mottle      standard deviation of L* after a 1/20-of-the-box blur is taken off: blotchy chalk and grime, not shading
  gloss       L* 99th minus 50th percentile: how bright the sky's reflection stands above the body colour
  L           mean L* after scaling the box's 95th percentile to 95 (exposure-normalised: comparable between shots)
Exposure differs between photos, so L is normalised and the checks lean on a, b, mottle and gloss.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(REPO, "Data", "Reference", "raw", "textures")


def srgb_to_lab(rgb):
    """rgb: float array (..., 3) in 0..1 sRGB -> Lab (D65)."""
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def crop(img, box):
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    return img[int(y0 * h):max(int(y1 * h), int(y0 * h) + 2), int(x0 * w):max(int(x1 * w), int(x0 * w) + 2)]


def box_blur(a, k):
    from scipy.ndimage import uniform_filter
    return uniform_filter(a, size=max(1, k), mode="reflect")


def measure(img, box, neutral=None):
    """img: float sRGB 0..1 (h, w, 3). Returns the numbers above for the box."""
    rgb = img
    balanced = False
    if neutral is not None:
        n = crop(img, neutral).reshape(-1, 3)
        lin = np.where(n <= 0.04045, n / 12.92, ((n + 0.055) / 1.055) ** 2.4).mean(0)
        gain = lin.mean() / np.maximum(lin, 1e-4)
        lin_img = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4) * gain
        lin_img = np.clip(lin_img, 0, 1)
        rgb = np.where(lin_img <= 0.0031308, lin_img * 12.92, 1.055 * lin_img ** (1 / 2.4) - 0.055)
        balanced = True
    p = crop(rgb, box)
    lab = srgb_to_lab(p)
    L = lab[..., 0]
    k = max(3, int(min(L.shape) / 20))
    hp = L - box_blur(L, k)
    p95 = np.percentile(L, 95)
    return dict(
        a=round(float(lab[..., 1].mean()), 2),
        b=round(float(lab[..., 2].mean()), 2),
        chroma=round(float(np.hypot(lab[..., 1], lab[..., 2]).mean()), 2),
        mottle=round(float(hp.std()), 2),
        gloss=round(float(np.percentile(L, 99) - np.percentile(L, 50)), 2),
        L=round(float(L.mean() * 95.0 / max(p95, 1.0)), 2),
        px=int(L.size),
        balanced=balanced,
    )


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def ref_path(surface, ref):
    return os.path.join(RAW, surface.capitalize(), ref["level"], ref["id"] + ".jpg")


def measure_surface(surface):
    refs = json.load(open(os.path.join(HERE, "refs", surface + ".json")))
    rows, missing = [], []
    for r in refs["refs"]:
        if not r.get("box"):
            continue
        path = ref_path(surface, r)
        if not os.path.exists(path):
            missing.append(r["id"])
            continue
        m = measure(load(path), r["box"], r.get("neutral"))
        rows.append(dict(id=r["id"], level=r["level"], **m))
    targets = {}
    for lv in sorted({row["level"] for row in rows}):
        sel = [row for row in rows if row["level"] == lv]
        bal = [row for row in sel if row["balanced"]] or sel
        targets[lv] = dict(
            n=len(sel),
            a=round(float(np.median([x["a"] for x in bal])), 2),
            b=round(float(np.median([x["b"] for x in bal])), 2),
            mottle=round(float(np.median([x["mottle"] for x in sel])), 2),
            gloss=round(float(np.median([x["gloss"] for x in sel])), 2),
            b_range=[min(x["b"] for x in bal), max(x["b"] for x in bal)],
            mottle_range=[min(x["mottle"] for x in sel), max(x["mottle"] for x in sel)],
            gloss_range=[min(x["gloss"] for x in sel), max(x["gloss"] for x in sel)],
        )
    out = dict(surface=surface, rows=rows, targets=targets, missing=missing)
    os.makedirs(os.path.join(HERE, "targets"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "targets", surface + ".json"), "w"), indent=1)
    return out


def _box(s):
    return [float(v) for v in s.split(",")] if s else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("surface", nargs="?")
    ap.add_argument("--image")
    ap.add_argument("--box")
    ap.add_argument("--neutral")
    a = ap.parse_args()
    if a.image:
        print(json.dumps(measure(load(a.image), _box(a.box), _box(a.neutral))))
    elif a.surface:
        out = measure_surface(a.surface)
        for lv, t in out["targets"].items():
            print(lv, t)
        if out["missing"]:
            print("missing photos (run fetch_refs.py):", ", ".join(out["missing"]), file=sys.stderr)
    else:
        ap.print_help()
