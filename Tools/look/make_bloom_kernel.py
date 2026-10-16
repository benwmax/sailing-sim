#!/usr/bin/env python3
"""Cinematic look, Ultra (graphics-8/cinematic): the FFT convolution bloom's kernel, generated.

    python3 Tools/look/make_bloom_kernel.py [--out Inputs/look/T_BloomKernel.png] [--size 512]

A lens's point spread, as one image: a bright core, the glare's 1/r^2 skirt (veiling glare from the glass and the
sensor), a faint six-pointed star from a hexagonal aperture, and a faint horizontal streak (the anamorphic flare of
the reference frames). 16-bit grey PNG, centred; Unreal normalises the kernel's energy, so only the shape matters.
Each term's weight is a named constant below. The kernel's energy is normalised, so what counts is each term's share:
with the skirt at 0.02 the core kept 31% and the Ultra frame washed out (docs/graphics-8/cinematic); now it keeps 84%.
"""
import argparse
import os

import numpy as np
from PIL import Image

CORE = 1.0          # the core, a Gaussian a few texels wide
CORE_SIGMA = 1.5
GLARE = 0.0015      # the skirt: GLARE / (1 + (r / GLARE_R)^2)
GLARE_R = 6.0
STAR = 0.0004       # six spikes, falling off as 1/r
STAR_WIDTH = 0.6
STREAK = 0.0012     # horizontal streak, falling off along x, a texel or two tall
STREAK_LEN = 0.35   # fraction of the half-size where the streak has fallen to 1/e


def kernel(n):
    c = (n - 1) / 2.0
    y, x = np.mgrid[0:n, 0:n].astype(np.float64)
    dx, dy = x - c, y - c
    r = np.hypot(dx, dy) + 1e-6
    k = CORE * np.exp(-(r / CORE_SIGMA) ** 2)
    k += GLARE / (1.0 + (r / GLARE_R) ** 2)
    ang = np.arctan2(dy, dx)
    for i in range(6):                      # spikes 30 degrees off the streak, so the streak stands alone
        a = np.pi / 6 + i * np.pi / 3
        d = np.abs(np.sin(ang - a)) * r     # distance from the spike's line
        along = np.cos(ang - a) > 0
        k += STAR * along * np.exp(-(d / STAR_WIDTH) ** 2) / (1.0 + r / 8.0)
    k += STREAK * np.exp(-(dy / 1.2) ** 2) * np.exp(-np.abs(dx) / (STREAK_LEN * c))
    return k / k.max()


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(root, "Inputs", "look", "T_BloomKernel.png"))
    ap.add_argument("--size", type=int, default=512)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    k = kernel(a.size)
    # Perceptual headroom: the skirt and streak are 1e-3 of the core; 16 bits keeps them.
    Image.fromarray((k * 65535.0 + 0.5).astype(np.uint16)).save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
