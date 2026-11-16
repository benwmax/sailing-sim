"""Texture sharpness rule for the environment loop (docs/env-loop/README.md; numbers in size_card.json "texture").

    python3 Tools/envloop/texel.py need <tile_m> [band]          # pixels a texture needs for a tile size, per tier
    python3 Tools/envloop/texel.py check <px> <tile_m> [band]    # does a texture of <px> over <tile_m> metres pass?
    python3 Tools/envloop/texel.py screen <distance_m>           # metres one screen pixel covers at that distance

Bands: hero (0-30 m, 1 cm a pixel), near (30-150 m, 2 cm), mid (150-600 m, 8 cm: light copies). Ultra loads the full
size, High half, Medium a quarter (size_card.json tier_scale). Sizes round up to a power of two.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CARD = json.load(open(os.path.join(HERE, "size_card.json")))
T = CARD["texture"]
FOV_DEG, SCREEN_PX = 80.0, 1920


def density(band="hero"):
    return T[band + "_px_per_m"]


def pow2(n):
    return 1 << max(0, math.ceil(math.log2(max(1, n))))


def need(tile_m, band="hero"):
    """Pixels across a texture covering tile_m metres, per tier."""
    full = pow2(tile_m * density(band))
    return {tier: (int(full * s) if s else 0) for tier, s in T["tier_scale"].items()}


def check(px, tile_m, band="hero"):
    got = px / float(tile_m)
    return dict(ok=got >= density(band) * 0.999, px_per_m=round(got, 1), want_px_per_m=density(band), band=band)


def screen_m(distance_m, fov_deg=FOV_DEG, px=SCREEN_PX):
    return 2.0 * distance_m * math.tan(math.radians(fov_deg / 2.0)) / px


def megabytes(px, channels_bc=1.0, mips=True):
    """GPU bytes of a square texture of px with BC compression: ~1 byte a texel for BC7/BC5 (channels_bc 1), 0.5 for
    BC1/BC4; mips add a third."""
    return px * px * channels_bc * (4.0 / 3.0 if mips else 1.0) / 1e6


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "need":
        print(json.dumps(need(float(a[1]), a[2] if len(a) > 2 else "hero")))
    elif a[0] == "check":
        print(json.dumps(check(int(a[1]), float(a[2]), a[3] if len(a) > 3 else "hero")))
    elif a[0] == "screen":
        d = float(a[1])
        print("one screen pixel at %.1f m: %.1f mm (1920 px, 80 deg)" % (d, 1000 * screen_m(d)))
