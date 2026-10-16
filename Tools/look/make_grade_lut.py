#!/usr/bin/env python3
"""Cinematic look (graphics-8/cinematic): the colour grade as Unreal's 256x16 colour-grading LUT, generated, not painted.

    python3 Tools/look/make_grade_lut.py [--out Inputs/look/T_CinematicLUT.png] [--neutral]

Layout: 16 slices of 16x16 side by side; within a slice red runs along x and green down y, blue picks the slice. The
LUT is applied after the tone curve, on display-referred values, so every operation here is on 0..1 sRGB-encoded
colour. The grade (each step a named constant below, tuned against the before/after stills):

- lifted blacks: the toe never quite reaches black (film's base density), LIFT;
- split toning: shadows pushed toward cool blue-teal, highlights toward warm amber, weighted by luminance so the
  midtones keep their hue (SHADOW_TINT, HIGHLIGHT_TINT, SPLIT);
- a gentle S around the middle grey for contrast (CONTRAST), rolled off so it can't clip the highlights;
- saturation a little down in the shadows and up in the warm midtones (SAT_SHADOW, SAT_MID).

Vignette and film grain are spatial and live in the post-process settings, not here. --neutral writes the identity LUT
(a check that the layout is right: graded with it the frame must be unchanged).
"""
import argparse
import os

import numpy as np
from PIL import Image

N = 16
LIFT = 0.025
SHADOW_TINT = np.array([-0.012, 0.004, 0.022])      # added at full shadow
HIGHLIGHT_TINT = np.array([0.030, 0.010, -0.028])   # added at full highlight
SPLIT = 0.45                                        # luminance where shadows hand over to highlights
CONTRAST = 0.10
SAT_SHADOW = 0.90
SAT_MID = 1.06
LUMA = np.array([0.2126, 0.7152, 0.0722])


def grade(c):
    """c: (..., 3) display-referred 0..1. Returns the graded colour."""
    y = (c @ LUMA)[..., None]
    # saturation: less in the shadows, a touch more in the midtones
    s = np.where(y < SPLIT, SAT_SHADOW + (1.0 - SAT_SHADOW) * (y / SPLIT), SAT_MID - (SAT_MID - 1.0) * ((y - SPLIT) / (1 - SPLIT)))
    c = y + (c - y) * s
    # split toning, weighted by luminance (smoothstep either side of SPLIT)
    t = np.clip((y - 0.1) / 0.8, 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    c = c + (1 - t) * SHADOW_TINT * (1 - y) + t * HIGHLIGHT_TINT * y
    # S-curve about 0.5, scaled down toward both ends so black and white stay put
    c = c + CONTRAST * (c - 0.5) * 4 * c * (1 - c)
    # lifted blacks
    c = LIFT + (1 - LIFT) * c
    return np.clip(c, 0.0, 1.0)


def lut(neutral=False):
    v = np.arange(N) / (N - 1)
    b, g, r = np.meshgrid(v, v, v, indexing="ij")      # [blue slice, green row, red column]
    c = np.stack([r, g, b], axis=-1)
    if not neutral:
        c = grade(c)
    img = np.concatenate([c[k] for k in range(N)], axis=1)   # 16 x 256
    return (img * 255.0 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ap.add_argument("--out", default=os.path.join(root, "Inputs", "look", "T_CinematicLUT.png"))
    ap.add_argument("--neutral", action="store_true")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    Image.fromarray(lut(a.neutral), "RGB").save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
