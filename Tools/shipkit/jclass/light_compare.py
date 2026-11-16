"""Measures slice 12's light copy against the detailed boat in render_jclass.py's light shots (docs/jclass-12).

    python light_compare.py <renders dir> [<docs dir>]

For each view (light_<dist>_<bearing>), the detailed boat's render and the light copy's are compared pixel by pixel
over the boat: the pixels either id shot marks as the boat (any material; the sea and the sky are black there), grown
by two pixels so that an outline moved by a pixel counts. Each pixel's difference is its largest channel's (0 to 255,
the rendered sRGB); the measure is the mean, the 95th and 99th percentiles, the share of the boat's pixels differing
by more than 16 (a step most people see side by side) and, from the id shots, the share showing another material or
none. The renderer's own noise is measured alike: the detailed boat rendered twice with two seeds (light_noise against
light_100_abeam_hero), which no copy can beat. Writes compare.json beside the renders and, with a docs dir, for each
view a JPEG of the two side by side over their difference (amplified four times, black where they agree) and a crop at
the screen's own pixels where they differ most (each under 290 KB: docs images are plain git).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

STEP = 16          # a difference most people see side by side (of 255)
GROW = 2           # pixels the boat's outline is grown by: an edge moved by a pixel counts
LIMIT = 290_000    # docs images are plain git (not LFS): each JPEG under this many bytes


def save(im, path, quality=(90, 84, 78, 72, 66, 60)):
    """A JPEG under LIMIT bytes, at the best quality that fits (4:4:4, so a pixel's colour stays its own)."""
    for q in quality:
        im.save(path, quality=q, subsampling=0, optimize=True)
        if os.path.getsize(path) < LIMIT:
            return
    raise SystemExit(f"{path} is still over {LIMIT} bytes")


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def mask(ids):
    m = Image.fromarray(((ids.max(2) > 0) * 255).astype(np.uint8))
    return np.asarray(m.filter(ImageFilter.MaxFilter(2 * GROW + 1))) > 0


def measure(a, b, ia, ib):
    """a, b: the two renders; ia, ib: their id shots. Over the boat's pixels (either id shot, grown)."""
    m = mask(ia) | mask(ib)
    d = np.abs(a - b).max(2)[m].astype(float)
    ida, idb = ia.max(2) > 0, ib.max(2) > 0
    either = ida | idb
    other = (np.abs(ia - ib).max(2) > 0) & either
    return {"pixels": int(m.sum()), "mean": round(float(d.mean()), 2), "p95": float(np.percentile(d, 95)),
            "p99": float(np.percentile(d, 99)), "max": float(d.max()),
            "share_over_step": round(float((d > STEP).mean()), 4),
            "id_other_share": round(float(other.sum() / max(1, either.sum())), 4),
            "outline_moved_share": round(float((ida ^ idb).sum() / max(1, either.sum())), 4)}


def side_by_side(a, b, path, height=900):
    """The two renders side by side over their difference, amplified four times."""
    d = np.clip(np.abs(a - b).max(2) * 4, 0, 255).astype(np.uint8)
    h, w = a.shape[:2]
    out = Image.new("RGB", (2 * w, 2 * h), (0, 0, 0))
    out.paste(Image.fromarray(a.astype(np.uint8)), (0, 0))
    out.paste(Image.fromarray(b.astype(np.uint8)), (w, 0))
    out.paste(Image.fromarray(np.stack([d] * 3, 2)), (w // 2, h))
    s = height / (2 * h)
    save(out.resize((max(1, int(2 * w * s)), height), Image.LANCZOS), path)


def worst_box(a, b, w=480, h=200):
    """The w x h window (or the whole frame, if smaller) with the most pixels differing by more than STEP: the place
    where the two differ most, shown at the screen's own pixels."""
    H, W = a.shape[:2]
    w, h = min(w, W), min(h, H)
    over = (np.abs(a - b).max(2) > STEP).astype(np.int64)
    s = np.zeros((H + 1, W + 1), np.int64)
    s[1:, 1:] = over.cumsum(0).cumsum(1)
    win = s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]
    y0, x0 = np.unravel_index(int(np.argmax(win)), win.shape)
    return int(x0), int(y0), int(x0) + w, int(y0) + h


def crop_pair(a, b, path, box):
    """A crop at the screen's own pixels (box: x0, y0, x1, y1), detailed above the light copy, shown at 2x."""
    x0, y0, x1, y1 = box
    ca = Image.fromarray(a[y0:y1, x0:x1].astype(np.uint8))
    cb = Image.fromarray(b[y0:y1, x0:x1].astype(np.uint8))
    out = Image.new("RGB", (x1 - x0, 2 * (y1 - y0) + 4), (255, 255, 255))
    out.paste(ca, (0, 0))
    out.paste(cb, (0, y1 - y0 + 4))
    save(out.resize((2 * out.width, 2 * out.height), Image.NEAREST), path, quality=(95, 90, 85, 80))


def main(src, docs=None):
    views = sorted({f[:-len("_hero.png")] for f in os.listdir(src)
                    if f.startswith("light_") and f.endswith("_hero.png") and not f.startswith("light_wire")})
    rep = {"step": STEP, "grow_px": GROW, "views": {}}
    for v in views:
        a, b = load(os.path.join(src, v + "_hero.png")), load(os.path.join(src, v + "_light.png"))
        ia, ib = load(os.path.join(src, v + "_hero_id.png")), load(os.path.join(src, v + "_light_id.png"))
        if not (a.shape == b.shape == ia.shape == ib.shape):
            raise SystemExit(f"{v}: the shots differ in size ({a.shape}, {b.shape}, {ia.shape}, {ib.shape})")
        rep["views"][v] = measure(a, b, ia, ib)
        if docs:
            side_by_side(a, b, os.path.join(docs, v + ".jpg"))
            crop_pair(a, b, os.path.join(docs, v + "_px.jpg"), worst_box(a, b))
    noise = os.path.join(src, "light_noise.png")
    if os.path.exists(noise) and "light_100_abeam" in rep["views"]:
        a, b = load(os.path.join(src, "light_100_abeam_hero.png")), load(noise)
        ia = load(os.path.join(src, "light_100_abeam_hero_id.png"))
        if a.shape != b.shape:
            raise SystemExit(f"light_noise differs in size from light_100_abeam_hero ({b.shape}, {a.shape})")
        rep["noise_100_abeam"] = measure(a, b, ia, ia)
    for v in sorted(os.listdir(src)):
        if v.startswith("light_wire_") and v.endswith("_hero.png") and docs:
            a, b = load(os.path.join(src, v)), load(os.path.join(src, v.replace("_hero", "_light")))
            h, w = a.shape[:2]
            out = Image.new("RGB", (2 * w + 8, h), (255, 255, 255))
            out.paste(Image.fromarray(a.astype(np.uint8)), (0, 0))
            out.paste(Image.fromarray(b.astype(np.uint8)), (w + 8, 0))
            save(out, os.path.join(docs, v.replace("_hero.png", ".jpg")))
    with open(os.path.join(src, "compare.json"), "w") as f:
        json.dump(rep, f, indent=1)
    return rep


if __name__ == "__main__":
    r = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    for k, v in r["views"].items():
        print(f"{k:22s} {v}")
    if "noise_100_abeam" in r:
        print(f"{'noise (two seeds)':22s} {r['noise_100_abeam']}")
