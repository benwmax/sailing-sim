"""Texture loop, wood: the round's renders (from wood_port, no Unreal): for each kind and level a lit close-up of a
tiller-like bar (a 40 mm rounded section seen from 0.5 m under an overcast sky with a soft sun), a flat 1 m swatch, a 3x3
tile sheet, and the blind review packs.

    python3 Tools/texloop/wood/render_wood.py <out dir> [--before]

Writes <out>/<kind>_<level>_bar.png, _flat.png, <kind>_tiles.png, <kind>_ladder.png (levels in order, labelled) and
<kind>_ladder_shuffled.png with key.json (the order, for scoring the ladder review).
"""
import json
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wood_port as wp  # noqa: E402

LEVELS = {"L0": (0.0, 1.0), "L1": (0.3, 0.9), "L2": (6.0, 0.5), "L3": (30.0, 0.9), "L4": (20.0, 0.1)}


def l2s(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def lit(o, curve=True):
    """Shade a face: across Y the bar's section bends (normal tilts from -60 to +60 degrees about X) when curve."""
    alb, rough, coat = o["albedo"], o["rough"], o["coat"]
    h, w = rough.shape
    a = np.linspace(-1.05, 1.05, h)[:, None] * np.ones((1, w)) if curve else np.zeros((h, w))
    n = np.stack([np.zeros_like(a), np.sin(a), np.cos(a)], -1)
    sun = np.array([0.35, -0.45, 0.82])
    sun /= np.linalg.norm(sun)
    ndl = np.clip((n * sun).sum(-1), 0, 1)
    sky = 0.55 + 0.45 * n[..., 2]                           # overcast dome: brighter overhead
    diffuse = alb * (0.65 * sky + 0.55 * ndl)[..., None]
    v = np.array([0.0, -0.35, 0.94])
    v /= np.linalg.norm(v)
    hv = sun + v
    hv /= np.linalg.norm(hv)
    ndh = np.clip((n * hv).sum(-1), 0, 1)
    r2 = np.maximum(rough, 0.04) ** 2
    d = ndh * ndh * (r2 * r2 - 1) + 1
    ggx = r2 * r2 / (np.pi * d * d)
    base_spec = 0.04 * ggx * ndl * 0.25
    # the clear film: a sharp sky reflection band and the sun's glint
    cr = 0.06
    d2 = ndh * ndh * (cr ** 4 - 1) + 1
    coat_spec = coat * (0.05 * cr ** 4 / (np.pi * d2 * d2) * ndl * 0.25 + 0.04 * sky)
    # the bright horizon sky mirrored as a band along the bar: narrow on a glossy film, spread and faint on a dull one
    width = 0.07 + 0.5 * rough * (1.0 - 0.7 * coat)
    band = np.exp(-((a + 0.45) / width) ** 2) * (0.07 / width)
    coat_spec = coat_spec + (0.35 * coat + 0.08 * (1.0 - coat)) * band * (1.0 if curve else 0.0)
    rgb = diffuse + (base_spec + coat_spec)[..., None]
    rgb = rgb / (1 + rgb * 0.35)                             # gentle tone map
    return (l2s(rgb * 1.25) * 255).astype(np.uint8)


def label(img, text):
    im = Image.fromarray(img) if isinstance(img, np.ndarray) else img
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 8 * len(text) + 8, 16), fill=(255, 255, 255))
    d.text((4, 2), text, fill=(0, 0, 0))
    return im


def main():
    out = sys.argv[1]
    new = "--before" not in sys.argv
    os.makedirs(out, exist_ok=True)
    key = {}
    for kind in ("varnish", "teak"):
        bars = []
        for lv, (age, care) in LEVELS.items():
            # close-up: 0.30 m of bar, 40 mm across, at 3 px/mm (the helm's eye at 0.5 m on a 1080p screen is ~1.5 px/mm)
            o = wp.shade(kind, age, care, (0.30, 0.04), 3.0, True, origin_cm=(37.0, 11.0, 0.0), new=new)
            bar = lit(o)
            Image.fromarray(bar).save(os.path.join(out, f"{kind}_{lv}_bar.png"))
            bars.append((lv, bar))
            f = wp.shade(kind, age, care, (1.0, 0.25), 0.6, True, new=new)
            Image.fromarray(lit(f, curve=False)).save(os.path.join(out, f"{kind}_{lv}_flat.png"))
        gap = np.full((10, bars[0][1].shape[1], 3), 255, np.uint8)
        ladder = np.concatenate(sum([[b, gap] for _, b in bars], [])[:-1], 0)
        im = Image.fromarray(ladder)
        y = 0
        for lv, b in bars:
            label_img = label(im.crop((0, y, im.width, y + b.shape[0])), lv)
            im.paste(label_img, (0, y))
            y += b.shape[0] + 10
        im.save(os.path.join(out, f"{kind}_ladder.png"))
        order = list(range(5))
        random.Random(f"{kind}{new}{os.path.basename(out.rstrip('/'))}").shuffle(order)
        letters = "ABCDE"
        shuf = np.concatenate(sum([[bars[i][1], gap] for i in order], [])[:-1], 0)
        im = Image.fromarray(shuf)
        y = 0
        for k, i in enumerate(order):
            im.paste(label(im.crop((0, y, im.width, y + bars[i][1].shape[0])), letters[k]), (0, y))
            y += bars[i][1].shape[0] + 10
        im.save(os.path.join(out, f"{kind}_ladder_shuffled.png"))
        key[kind] = {letters[k]: list(LEVELS)[i] for k, i in enumerate(order)}
        # 3x3 tiles of the detail map's period (0.75 x 0.375 m) at L2, flat
        t = wp.shade(kind, 6.0, 0.5, (0.75, 0.375), 1.4, True, new=new)
        Image.fromarray(lit(t, curve=False)).save(os.path.join(out, f"{kind}_tiles.png"))
    json.dump(key, open(os.path.join(out, "key.json"), "w"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
