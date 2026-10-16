"""Rope and wire textures, built from the braid's own geometry (numpy, no photos), tileable in both directions.

    python3 Tools/rope/make_rope_textures.py [out dir] [--res 1024]

Double-braid polyester (sheets, halyards, control lines): the cover is N carriers, half spiralling one way (S) and half
the other (Z), each a flat ribbon of a few yarns, woven two over and two under (a 2/2 twill, as on almost every
yacht braid). One tile is one turn of a carrier round the rope: U runs along the rope over one lay length, V once round
it. With the cover's helix at about 32 degrees to the axis a turn is about 5 rope diameters long, so a line's UVs are
U = arc length / (5 d) and V = angle / 2 pi (see rope_uv_scale in colourways.json).

Writes, for the 24-carrier cover (the usual 6-12 mm sheet):
  T_Rope_Braid24_N.png   tangent-space normal (OpenGL, green up), 8-bit
  T_Rope_Braid24_H.png   height, 16-bit (cinematics and Blender displacement)
  T_Rope_Braid24_M.png   R cavity (1 open, 0 deep in the weave), G tracer mask "fleck" (two carriers each way),
                         B tracer mask "spiral" (two neighbouring S carriers), A tracer mask "mix" (every other S carrier)
and the same three for a 16-carrier cover (T_Rope_Braid16_*: thick mooring and dock lines, coarser weave), plus
  T_Wire_1x19_N.png / _M.png   1x19 stainless rigging wire: 12 outer strands laid at about 17 degrees (lay ~ 11 d).

The tracer masks are carrier selections, so a colourway is just base colour, tracer colour and which mask
(colourways.json): white with red flecks, red with white flecks, blue/white mix, and so on, all from one texture.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

ARGS = sys.argv[1:]
OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Inputs", "rope")
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1024
SS = 2                     # supersampling for the masks and height
os.makedirs(OUT, exist_ok=True)


def hash01(*ints):
    """Deterministic 0..1 per integer tuple (vectorised)."""
    h = np.uint64(1469598103934665603)
    out = np.full(np.broadcast(*ints).shape, h, dtype=np.uint64)
    for k in ints:
        out ^= np.asarray(k, dtype=np.int64).astype(np.uint64)
        out *= np.uint64(1099511628211)
        out ^= out >> np.uint64(29)
    return (out & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF)


def smooth_noise_1d(x, period, seed):
    """Periodic value noise along x (x in cells, wraps every `period` cells)."""
    i0 = np.floor(x).astype(np.int64)
    f = x - i0
    f = f * f * (3 - 2 * f)
    a = hash01(i0 % period, seed)
    b = hash01((i0 + 1) % period, seed)
    return a + (b - a) * f


def braid(n_carriers, yarns, res, seed=1):
    """Height, cavity and tracer masks of a 2/2 twill braid cover. Returns float arrays (res x res), V down rows."""
    n = n_carriers // 2
    r = res * SS
    v, u = np.meshgrid((np.arange(r) + 0.5) / r, (np.arange(r) + 0.5) / r, indexing="ij")
    # a little waviness in the carriers' paths (tension and yarn bunching), periodic so the tile still wraps
    wob = 0.07 * np.sin(2 * np.pi * (3 * u + 2 * v) + 1.3) + 0.05 * np.sin(2 * np.pi * (5 * u - 4 * v) + 0.4)
    s = (v - u) * n + wob                # across the S carriers (constant along an S carrier)
    z = (v + u) * n - wob                # across the Z carriers
    i_s, f_s = np.floor(s).astype(np.int64), s - np.floor(s)
    i_z, f_z = np.floor(z).astype(np.int64), z - np.floor(z)
    i_s %= n
    i_z %= n
    s_top = ((i_s - i_z) % 4) < 2      # 2 over 2 under: along a carrier the crossing flips every two cells

    def ribbon(across, along_cell, along_frac, phase_sign, cid):
        """Height of a carrier at the top of a crossing: a flat-topped ribbon of `yarns` yarns, rising out of the
        crossing before its float and sinking after it (the float spans two cells)."""
        prof = np.clip(1 - (2 * across - 1) ** 2, 0, 1) ** 0.55
        grooves = 1 - 0.18 * (0.5 + 0.5 * np.cos(2 * np.pi * yarns * across))
        k = (phase_sign * along_cell) % 4          # 0 or 1 inside the float when on top
        t = (np.where(k < 2, k, k - 2) + along_frac) / 2.0
        hump = np.sin(np.pi * np.clip(t, 0, 1)) ** 0.8
        # filaments: fine streaks along the carrier, a little fuzz
        fil = smooth_noise_1d(across * yarns * 7 + cid * 13.0, 10 ** 6, seed + cid)
        return prof * grooves * (0.35 + 0.65 * hump) * (0.92 + 0.08 * fil)

    h_s = ribbon(f_s, i_z - i_s, f_z, 1, i_s)
    h_z = ribbon(f_z, i_s - i_z, f_s, 1, n + i_z)
    # the carrier underneath shows a little at the ribbon edges (gaps between top carriers)
    h = np.where(s_top, h_s, h_z)
    under = np.where(s_top, h_z, h_s) * 0.45
    h = np.maximum(h, under)
    # a slight unevenness per carrier (tension differences) and per float
    jitter = 0.06 * (hash01(np.where(s_top, i_s, n + i_z), np.where(s_top, i_z, i_s), seed) - 0.5)
    h = np.clip(h + jitter, 0, None)
    top_id = np.where(s_top, i_s, n + i_z)          # 0..n-1 S carriers, n..2n-1 Z carriers
    is_top_s = s_top
    fleck = np.isin(top_id, [0, n // 2, n, n + n // 2]).astype(np.float64)
    spiral = (is_top_s & np.isin(i_s, [0, 1])).astype(np.float64)
    mix = (is_top_s & (i_s % 2 == 0)).astype(np.float64)
    # tracers only where the carrier really shows (not in the deep gaps)
    vis = np.clip((h - 0.15) / 0.35, 0, 1)
    fleck, spiral, mix = fleck * vis, spiral * vis, mix * vis
    return [down(a) for a in (h, fleck, spiral, mix)]


def wire_1x19(res, seed=3):
    """1x19 strand: 12 outer wires laid round the core, seen from outside: 12 parallel helical cylinders per turn."""
    r = res * SS
    v, u = np.meshgrid((np.arange(r) + 0.5) / r, (np.arange(r) + 0.5) / r, indexing="ij")
    w = (v - u) * 12
    f = w - np.floor(w)
    h = np.sqrt(np.clip(1 - (2 * f - 1) ** 2, 0, 1))
    draw = 0.97 + 0.03 * smooth_noise_1d(u * 400 + np.floor(w) * 31, 400, seed)   # drawing marks along each wire
    h = h * draw
    return [down(h)]


def down(a):
    rr = a.shape[0] // SS
    return a.reshape(rr, SS, rr, SS).mean(axis=(1, 3))


def normal_from_height(h, amp_mm, tile_u_mm, tile_v_mm):
    """Tangent-space normal from a wrapped height field. U along the rope = texture X, V round it = texture Y."""
    res = h.shape[0]
    hh = h * amp_mm
    dx = (np.roll(hh, -1, axis=1) - np.roll(hh, 1, axis=1)) / (2 * tile_u_mm / res)
    dy = (np.roll(hh, -1, axis=0) - np.roll(hh, 1, axis=0)) / (2 * tile_v_mm / res)
    n = np.stack([-dx, dy, np.ones_like(hh)], axis=-1)        # OpenGL: green up (+V up the image)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255 + 0.5).clip(0, 255).astype(np.uint8)


def cavity(h):
    """Open (1) on the carrier tops, dark in the gaps: height against its local mean, softened."""
    k = max(3, h.shape[0] // 128)
    m = h.copy()
    for ax in (0, 1):
        acc = np.zeros_like(m)
        for d in range(-k, k + 1):
            acc += np.roll(m, d, axis=ax)
        m = acc / (2 * k + 1)
    c = np.clip(0.55 + 1.6 * (h - m), 0, 1)
    return np.clip(0.35 + 0.65 * c * np.clip(h / 0.5, 0, 1) ** 0.4, 0, 1)


def save8(a, path):
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def save16(a, path):
    Image.fromarray((np.clip(a, 0, 1) * 65535 + 0.5).astype(np.uint16)).save(path)


def write_braid(tag, carriers, yarns, d_mm, amp_frac):
    h, fleck, spiral, mix = braid(carriers, yarns, RES)
    h = h / max(h.max(), 1e-6)
    lay = 5.0 * d_mm
    Image.fromarray(normal_from_height(h, amp_frac * d_mm, lay, math.pi * d_mm)).save(os.path.join(OUT, f"T_Rope_{tag}_N.png"))
    save16(h, os.path.join(OUT, f"T_Rope_{tag}_H.png"))
    m = np.stack([cavity(h), fleck, spiral, mix], axis=-1)
    Image.fromarray((m * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, f"T_Rope_{tag}_M.png"))
    print("wrote", tag)


write_braid("Braid24", 24, 4, 9.0, 0.09)
write_braid("Braid16", 16, 5, 16.0, 0.10)
(hw,) = wire_1x19(RES // 2)
hw = hw / hw.max()
d = 4.0
Image.fromarray(normal_from_height(hw, 0.06 * d, 11 * d, math.pi * d)).save(os.path.join(OUT, "T_Wire_1x19_N.png"))
save8(np.stack([cavity(hw)] * 3, axis=-1), os.path.join(OUT, "T_Wire_1x19_M.png"))
print("wrote Wire_1x19")

# colourways: what TX 7295 EC and the club fleet carry (Bean's lesson photos, Oct 2026), plus common chandlery stock.
# pattern = which tracer mask in T_Rope_*_M (G fleck, B spiral, A mix, none); sRGB hex.
COLOURWAYS = [
    dict(name="white_red_fleck", base="#ECEAE2", tracer="#B5231C", pattern="fleck", use="mainsheet, backstay bridle, spinnaker sheets"),
    dict(name="red_white_fleck", base="#B01F1A", tracer="#EAE8E0", pattern="fleck", use="port jib sheet"),
    dict(name="green_white_fleck", base="#1E5E33", tracer="#E6E6DE", pattern="fleck", use="starboard jib sheet"),
    dict(name="white_green_fleck", base="#ECEAE2", tracer="#1E6A34", pattern="fleck", use="jib sheets (white pairs)"),
    dict(name="white_blue_fleck", base="#ECEAE2", tracer="#1D3F8F", pattern="fleck", use="halyards"),
    dict(name="blue_white_mix", base="#1D3F8F", tracer="#E8E8E2", pattern="mix", use="vang, cunningham"),
    dict(name="black_white_fleck", base="#1B1B1B", tracer="#D6D6D0", pattern="fleck", use="mainsheet (race boats)"),
    dict(name="blue_solid", base="#22468F", tracer="#1A3570", pattern="spiral", use="mooring and dock lines"),
    dict(name="white_spiral_red", base="#ECEAE2", tracer="#B5231C", pattern="spiral", use="outhaul, reef lines"),
    dict(name="grey_red_fleck", base="#9C9C98", tracer="#B5231C", pattern="fleck", use="mainsheet (older boats)"),
    dict(name="yellow_black_fleck", base="#D6B01F", tracer="#1A1A1A", pattern="fleck", use="jib halyard, control lines"),
]
json.dump({"rope_uv_scale": "U = arc length / (5 x diameter) for Braid24 and Braid16, V = angle / 2pi; wire: U = arc length / (11 x d)",
           "masks": {"fleck": "G", "spiral": "B", "mix": "A", "cavity": "R"},
           "colourways": COLOURWAYS}, open(os.path.join(OUT, "colourways.json"), "w"), indent=1)

# a strip of swatches for review: each colourway on the 24-carrier cover, lit by its normal from the upper left
n_img = np.asarray(Image.open(os.path.join(OUT, "T_Rope_Braid24_N.png"))).astype(np.float64) / 127.5 - 1
m_img = np.asarray(Image.open(os.path.join(OUT, "T_Rope_Braid24_M.png"))).astype(np.float64) / 255
L = np.array([-0.45, 0.45, 0.77])
shade = np.clip((n_img * L).sum(-1), 0, 1) * 0.8 + 0.2
tiles = []
for cw in COLOURWAYS:
    base = np.array([int(cw["base"][i:i + 2], 16) for i in (1, 3, 5)]) / 255
    tr = np.array([int(cw["tracer"][i:i + 2], 16) for i in (1, 3, 5)]) / 255
    mk = m_img[..., {"fleck": 1, "spiral": 2, "mix": 3}[cw["pattern"]]][..., None]
    col = base * (1 - mk) + tr * mk
    col = col * m_img[..., :1] * shade[..., None]
    tiles.append(np.tile(col[: RES // 2, : RES // 2], (1, 2, 1)))
save8(np.concatenate(tiles, axis=0), os.path.join(OUT, "rope_swatches.png"))
print("wrote swatches")

# the colourway table the game's M_RigRope reads (16 x 4, nearest, no mips): row 0 base colour (sRGB), row 1 tracer
# (sRGB), row 2 which tracer mask (R fleck, G spiral, B mix; linear), row 3 spare. Column = the rope's look, which
# BoatModelVisuals.cpp writes into each live line's vertex colour (RopeLook: 0 mainsheet, 1 jib port, 2 jib starboard...).
lut = np.zeros((4, 16, 3), dtype=np.uint8)
for i, cw in enumerate(COLOURWAYS[:16]):
    lut[0, i] = [int(cw["base"][k:k + 2], 16) for k in (1, 3, 5)]
    lut[1, i] = [int(cw["tracer"][k:k + 2], 16) for k in (1, 3, 5)]
    lut[2, i] = {"fleck": (255, 0, 0), "spiral": (0, 255, 0), "mix": (0, 0, 255)}[cw["pattern"]]
Image.fromarray(lut, "RGB").save(os.path.join(OUT, "T_RopeColourways.png"))
print("wrote colourway table:", ", ".join(f"{i} {cw['name']}" for i, cw in enumerate(COLOURWAYS[:16])))
