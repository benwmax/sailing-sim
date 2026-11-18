"""The "no visible repeat in a 40 m frame" check (docs/env-loop/README.md, check 3).

    python3 Tools/envloop/repeat_check.py tile <texture.png> <tile_m> [--macro <macro.png> <macro_tile_m>] [--out lay.png]
    python3 Tools/envloop/repeat_check.py image <render.png> [--box x0,y0,x1,y1]

`tile` lays the texture (and an optional large-scale colour wash multiplied over it, the way the layered ground material
breaks tiling) over 40 x 40 m seen from above at 5 cm a pixel, then measures repeat: the strongest peak of the
autocorrelation away from its centre lobe. A plain tile repeats perfectly (peak near 1). `image` measures the same on a
render or still (a crop of ground, a wall). Pass: peak under 0.35 for ground and walls (the texture loop used 0.5 inside
one tile; a 40 m frame is stricter because the eye sees the grid).
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image

FRAME_M, RES_M = 40.0, 0.05
PASS = 0.35


def grey(path):
    return np.asarray(Image.open(path).convert("L"), np.float64) / 255.0


def lay(tex, tile_m, macro=None, macro_tile_m=None):
    n = int(FRAME_M / RES_M)
    u = (np.arange(n) * RES_M / tile_m) % 1.0
    h, w = tex.shape
    out = tex[(u[:, None] * h).astype(int) % h, (u[None, :] * w).astype(int) % w]
    if macro is not None:
        um = (np.arange(n) * RES_M / macro_tile_m) % 1.0
        mh, mw = macro.shape
        m = macro[(um[:, None] * mh).astype(int) % mh, (um[None, :] * mw).astype(int) % mw]
        out = out * (0.5 + m)
    return out


def repeat_peak(a, exclude_frac=0.04):
    """Strongest normalised autocorrelation off the centre (wrap-free: zero padded), ignoring a lobe of exclude_frac."""
    a = a - a.mean()
    if a.std() < 1e-6:
        return 1.0
    a = a / a.std()
    h, w = a.shape
    f = np.fft.rfft2(a, s=(2 * h, 2 * w))
    ac = np.fft.irfft2(f * np.conj(f), s=(2 * h, 2 * w))
    # normalise by overlap so far lags aren't favoured or punished
    ov = np.fft.irfft2(np.abs(np.fft.rfft2(np.ones_like(a), s=(2 * h, 2 * w))) ** 2, s=(2 * h, 2 * w))
    ac = ac / np.maximum(ov, 1.0)
    ac /= ac[0, 0]
    ac = np.fft.fftshift(ac)
    cy, cx = h, w
    ry, rx = max(2, int(h * exclude_frac)), max(2, int(w * exclude_frac))
    ac[cy - ry:cy + ry + 1, cx - rx:cx + rx + 1] = -1
    # only lags up to half the frame (enough overlap to mean something)
    win = ac[cy - h // 2:cy + h // 2, cx - w // 2:cx + w // 2]
    return float(win.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["tile", "image"])
    ap.add_argument("path")
    ap.add_argument("tile_m", nargs="?", type=float)
    ap.add_argument("--macro", nargs=2)
    ap.add_argument("--box")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.mode == "tile":
        m = (grey(a.macro[0]), float(a.macro[1])) if a.macro else (None, None)
        img = lay(grey(a.path), a.tile_m, *m)
        if a.out:
            Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(a.out)
        img = np.asarray(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((400, 400), Image.BILINEAR), float)
    else:
        img = grey(a.path)
        if a.box:
            x0, y0, x1, y1 = (float(v) for v in a.box.split(","))
            h, w = img.shape
            img = img[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        img = np.asarray(Image.fromarray((img * 255).astype(np.uint8)).resize((400, int(400 * img.shape[0] / img.shape[1])), Image.BILINEAR), float)
    p = repeat_peak(img)
    print(json.dumps(dict(ok=p < PASS, repeat_peak=round(p, 3), pass_under=PASS)))
    sys.exit(0)


if __name__ == "__main__":
    main()
