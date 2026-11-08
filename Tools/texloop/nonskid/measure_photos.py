"""Non-skid reference measurements (texture loop steps 2-3): colour against nearby white gelcoat, and pattern pitch.

    python3 Tools/texloop/nonskid/measure_photos.py [photo dir]

The photos are Bean's J/22 lesson photos (git-ignored, Data/Reference/raw/j22-lessons/ on the Mac, project files in the
cloud). Each patch below is a box in the full-size photo. Colour: both patches go to linear light, the white gelcoat
patch is made neutral and set to sRGB 215 (white gelcoat albedo, plan's sanity limit 200-225), and the non-skid patch
takes the same gain; so the numbers are "this non-skid next to a white gelcoat of 215", not absolute. Pitch: the
strongest peak of a windowed FFT of a 256 px patch, converted with the cam cleat's 38 mm axle spacing (128 px at the
coaming). The results are written into Tools/texloop/refs/nonskid.json by hand.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

DIR = sys.argv[1] if len(sys.argv) > 1 else "/mnt/project-files/sailing-sim-ref/j22-lessons"
WHITE_SRGB = 215

# photo, white gelcoat box, non-skid box, what it is
COLOUR = [
    ("1000032822.jpg", (700, 3400, 1300, 3480), (780, 3240, 980, 3370), "L2 foredeck, clean side, overcast"),
    ("1000032822.jpg", (700, 3400, 1300, 3480), (1120, 3230, 1380, 3380), "L2 foredeck, foot path, overcast"),
    ("IMG_9224.jpg", (1933, 2216, 2367, 2266), (2951, 2475, 3713, 2570), "L2 side deck from the dock, overcast"),
    ("IMG_9272.jpg", (1632, 3040, 2244, 3223), (1224, 3468, 2856, 4080), "L2 cockpit seat, low sun (white ref is the shaded coaming)"),
]
PITCH = [("IMG_9272.jpg", (x, y)) for x, y in ((1250, 3400), (1600, 3420), (1300, 3700), (2400, 3600))]
PX_PER_MM = 128 / 38.0      # cam cleat axle spacing on the coaming just above the seat


def srgb2lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2lab(rgb):
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = rgb @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def patch(im, box):
    return np.asarray(im.crop(box).convert("RGB"), float).reshape(-1, 3)


def colour(photo, wbox, nbox):
    im = Image.open(os.path.join(DIR, photo))
    w = srgb2lin(patch(im, wbox)).mean(0)
    n = srgb2lin(patch(im, nbox))
    gain = srgb2lin(np.array([WHITE_SRGB] * 3, float)) / w
    lab = lin2lab(np.clip(n * gain, 0, 1))
    L = lab[:, 0]
    lum = np.array([0.2126, 0.7152, 0.0722])
    return {"lab": [round(float(v), 1) for v in lab.mean(0)], "L_std": round(float(L.std()), 1),
            "dark_cover": round(float((L < np.median(L) - 6).mean()), 3),
            "lum_ratio_to_white": round(float(n.mean(0) @ lum / (w @ lum)), 3),
            "clipped_pct": round(float((patch(im, nbox) >= 250).any(1).mean() * 100), 1)}


def pitch(photo, xy, n=256):
    im = np.asarray(Image.open(os.path.join(DIR, photo)).convert("L"), float)
    x0, y0 = xy
    p = im[y0:y0 + n, x0:x0 + n]
    p = p - p.mean()
    w = np.hanning(n)
    f = np.abs(np.fft.fftshift(np.fft.fft2(p * w[:, None] * w[None, :])))
    c = n // 2
    yy, xx = np.mgrid[-c:c, -c:c]
    f[np.hypot(xx, yy) < n / 40] = 0
    peaks = []
    for _ in range(2):
        iy, ix = np.unravel_index(f.argmax(), f.shape)
        fy, fx = (iy - c) / n, (ix - c) / n
        peaks.append({"period_px": round(float(1 / np.hypot(fx, fy)), 2), "freq_dir_deg": round(float(np.degrees(np.arctan2(fy, fx)) % 180), 1),
                      "power": round(float(f.max()))})
        for sy, sx in ((iy, ix), (2 * c - iy, 2 * c - ix)):
            f[max(sy - 4, 0):sy + 5, max(sx - 4, 0):sx + 5] = 0
    peaks[0]["period_mm"] = round(peaks[0]["period_px"] / PX_PER_MM, 2)
    return peaks


if __name__ == "__main__":
    out = {"colour": [dict(photo=p, what=t, **colour(p, w, b)) for p, w, b, t in COLOUR],
           "pitch": [dict(photo=p, at=xy, peaks=pitch(p, xy)) for p, xy in PITCH]}
    print(json.dumps(out, indent=1))
