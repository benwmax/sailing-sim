"""Track A: turn the raw CC0 ground scans (fetch_ground.py) into the material's maps, calibrated to a region pack.

    python3 -I Tools/envloop/ground/prep_ground.py [--pack north-texas-lake] [--res 2048,1024,512]

For each surface and tier size writes Data/Ground/prep/<pack>/<role>_<res>.npz (git-ignored) with
  albedo  linear RGB, float16: the scan's own detail (its colour over a wide wrap-around blur, so the light it was shot
          in and any slow gradient drop out) times the card's summer albedo, so the mean is exactly the card's colour
  normal  tangent-space XY (OpenGL, +Y up), float16; Z is rebuilt in the shader
  rha     roughness (the card's mean, the scan's variation), height (0..1, mean 0.5) and ambient occlusion, float16
and Data/Ground/prep/<surface>_<res>_{albedo,normal,rha}.png for the editor's import (sRGB colour, linear rest).
The numbers that decide the colour check are written to Data/Ground/prep/prep.json.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage

import pack as packs

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def load(path, res, mode):
    im = Image.open(path)
    if im.mode in ("I;16", "I;16B", "I"):
        a = np.asarray(im, dtype=np.float32) / 65535.0
        im = Image.fromarray(a, mode="F")
    elif mode == "L":
        im = im.convert("L")
    else:
        im = im.convert("RGB")
    if im.size != (res, res):
        im = im.resize((res, res), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32)
    return a / 255.0 if a.max() > 1.5 else a


def find(folder, key):
    for f in os.listdir(folder):
        if f.startswith(key + "."):
            return os.path.join(folder, f)
    return None


def wrap_blur(a, sigma):
    if a.ndim == 3:
        return np.stack([ndimage.gaussian_filter(a[..., i], sigma, mode="wrap") for i in range(a.shape[2])], -1)
    return ndimage.gaussian_filter(a, sigma, mode="wrap")


def prep_surface(s, res, raw):
    folder = os.path.join(raw, s["id"])
    col = srgb_to_linear(load(find(folder, "color"), res, "RGB"))
    # Detail: the scan over its own wide blur (an eighth of the tile), so shading and slow colour drift go and only the
    # surface's own pattern stays; the wide blur's mean then becomes the card's colour.
    low = wrap_blur(col, res / 8.0)
    detail = col / np.maximum(low, 1e-4)
    # Keep the scan's slow variation at a third (it is real: patches of moss, damp, thatch) but not its lighting.
    slow = (low / low.mean(axis=(0, 1))) ** 0.33
    detail = np.clip(detail * slow, 0.15, 3.0)
    target = np.array(s["albedo_linear"]["summer"], np.float32)
    alb = detail * (target / detail.mean(axis=(0, 1)))
    nrm = load(find(folder, "normal"), res, "RGB")[..., :2] * 2.0 - 1.0
    rough = load(find(folder, "rough"), res, "L")
    rough = np.clip(rough - rough.mean() + s["roughness"], 0.05, 1.0)
    height = load(find(folder, "height"), res, "L")
    lo, hi = np.percentile(height, [1, 99])
    height = np.clip((height - lo) / max(hi - lo, 1e-4), 0, 1)
    height = np.clip(height - height.mean() + 0.5, 0, 1)
    aop = find(folder, "ao")
    ao = load(aop, res, "L") if aop else np.ones_like(rough)
    rha = np.stack([rough, height, ao], -1)
    return alb.astype(np.float16), nrm.astype(np.float16), rha.astype(np.float16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=None)
    ap.add_argument("--res", default="2048,1024,512")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()
    card = packs.load(args.pack)
    PREP = packs.prep_dir(args.pack)
    raw = packs.raw_dir(args.pack)
    os.makedirs(PREP, exist_ok=True)
    only = set(filter(None, args.only.split(",")))
    report = {}
    for s in card["surfaces"]:
        if only and s["id"] not in only:
            continue
        for res in [int(r) for r in args.res.split(",")]:
            alb, nrm, rha = prep_surface(s, res, raw)
            base = os.path.join(PREP, f"{s['id']}_{res}")
            np.savez_compressed(base + ".npz", albedo=alb, normal=nrm, rha=rha)
            if not args.no_png:
                Image.fromarray((linear_to_srgb(alb.astype(np.float32)) * 255 + 0.5).astype(np.uint8)).save(base + "_albedo.png")
                n = nrm.astype(np.float32)
                nz = np.sqrt(np.clip(1 - (n ** 2).sum(-1, keepdims=True), 0, 1))
                Image.fromarray(((np.concatenate([n, nz], -1) * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)).save(base + "_normal.png")
                Image.fromarray((rha.astype(np.float32) * 255 + 0.5).astype(np.uint8)).save(base + "_rha.png")
            report.setdefault(s["id"], {})[res] = {
                "albedo_mean": [round(float(x), 4) for x in alb.astype(np.float32).mean(axis=(0, 1))],
                "albedo_p05_p95_lum": [round(float(x), 4) for x in np.percentile(alb.astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722]), [5, 95])],
                "rough_mean": round(float(rha[..., 0].astype(np.float32).mean()), 3),
                "px_per_m": round(res / s["tile_m"], 1),
            }
            print(s["id"], res, report[s["id"]][res])
    json.dump(report, open(os.path.join(PREP, "prep.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
