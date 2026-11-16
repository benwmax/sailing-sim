"""Track F's "before": today's private pier and boathouse rebuilt in Blender exactly as the game draws them, so the
blind rounds compare like with like (same renderer, same preview looks). Read from main at 4320a45:
  SM_Before_Pier       WorldKit.cpp BuildShoreGeometry: an OSM private pier, 1.8 m deck slab 0.45-0.6 m over the pool
                       (0.3 m past each end), 6-sided 0.12 m pilings every 3 m both sides, 3.4 m tall from -2.5 m
  SM_Before_Boathouse  HouseKit.cpp (pc/shore-residential): a 6 m walk, a U of decking round a slip, 0.12-0.13 m
                       piles, posts, a gable roof of plain planes (metal or shingle look), lift cradle bars and the
                       covered runabout from CoveredBoat()
Usage: python3 Tools/envloop/docks/build_before.py <out dir>
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import shorekit  # noqa: E402
from shorekit import Part  # noqa: E402

import bpy  # noqa: E402


def quad(p, slot, a, b, c, d):
    vs = [p.bm.verts.new(v) for v in (a, b, c, d)]
    p._faces([p.bm.faces.new(vs)], slot)


def pier(length=14.6):
    p = Part("SM_Before_Pier")
    W = 1.8
    p.box("Decking", (length / 2, 0, 0.525), (length / 2 + 0.3, W / 2, 0.075), segments=1)
    x = 0.0
    while x <= length + 1e-6:
        for s in (-1, 1):
            p.tube("Wood", (x, s * (W / 2 - 0.1), -2.5), (x, s * (W / 2 - 0.1), 0.9), 0.12, sides=6)
        x += 3.0
    p.socket("boat_0", (length + 1.4, -1.0, -0.3), 90.0)
    return p


def boathouse():
    """HouseKit.cpp lines 721-768 at Zd = 1.0, with Water = +X and Across = +Y."""
    p = Part("SM_Before_Boathouse")
    Zd = 1.0
    p.box("Decking", (3.0, 0, Zd - 0.06), (3.0, 0.7, 0.06), segments=1)
    B0 = 6.0
    p.box("Decking", (B0 + 0.7, 0, Zd - 0.06), (0.7, 3.8, 0.06), segments=1)
    for s in (-1, 1):
        p.box("Decking", (B0 + 5.4, s * 3.2, Zd - 0.06), (4.0, 0.6, 0.06), segments=1)
    D = 0.6
    while D < 9.5:
        for s in (-1, 1):
            p.tube("Wood", (min(D, 5.6), s * 0.6, -2.0), (min(D, 5.6), s * 0.6, Zd - 0.06), 0.12, sides=6)
            p.tube("Wood", (B0 + D + 0.3, s * 3.5, -2.0), (B0 + D + 0.3, s * 3.5, Zd - 0.06), 0.13, sides=6)
        D += 3.0
    Zr, Rise, Wr, Lr = Zd + 2.9, 1.5, 4.2, 9.6
    for d in (0.2, 0.5 * Lr, Lr - 0.2):
        for s in (-1, 1):
            p.box("Trim", (B0 + d, s * 3.6, 0.5 * (Zd + Zr)), (0.09, 0.09, 0.5 * (Zr - Zd)), segments=1)
    RA, RB = (B0 - 0.3, -Wr, Zr), (B0 + Lr, -Wr, Zr)
    RC, RD = (B0 + Lr, Wr, Zr), (B0 - 0.3, Wr, Zr)
    R0, R1 = (B0 - 0.3, 0, Zr + Rise), (B0 + Lr, 0, Zr + Rise)
    quad(p, "Roof", RA, RB, R1, R0)
    quad(p, "Roof", RC, RD, R0, R1)
    quad(p, "Roof", RA, R0, R1, RB)       # the game's planes are two-sided in the material; give the underside here
    quad(p, "Roof", RC, R1, R0, RD)
    for s in (-1, 1):
        p.box("Trim", (B0 + 0.5 * (Lr - 0.3), s * Wr, Zr - 0.1), (0.5 * (Lr + 0.3), 0.01, 0.1), segments=1)
    Zk = Zd - 0.15
    for d in (2.0, 6.0):
        p.box("Steel", (B0 + 1.5 + d, 0, Zk - 0.075), (0.075, 2.6, 0.075), segments=1)
    # CoveredBoat(Pale, Roof, B0 + Water * 1.6, Water, 6.8, 2.4, Zk, 1.35)
    L, Beam, Z0, Hgt = 6.8, 2.4, Zk, 1.35
    X = (0.0, 0.62 * L, 0.88 * L, L)
    WG = (0.5 * Beam, 0.5 * Beam, 0.36 * Beam, 0.04)
    WC = (0.4 * Beam, 0.38 * Beam, 0.22 * Beam, 0.02)
    ZG, ZC, ZT = Z0 + 0.75, Z0 + 0.25, Z0 + Hgt
    bx = B0 + 1.6
    for i in range(3):
        for sd in (-1, 1):
            quad(p, "Gelcoat", (bx + X[i], sd * WC[i], ZC), (bx + X[i + 1], sd * WC[i + 1], ZC), (bx + X[i + 1], sd * WG[i + 1], ZG), (bx + X[i], sd * WG[i], ZG))
            quad(p, "Gelcoat", (bx + X[i], 0, Z0 + 0.1 * i), (bx + X[i + 1], 0, Z0 + 0.1 * (i + 1)), (bx + X[i + 1], sd * WC[i + 1], ZC), (bx + X[i], sd * WC[i], ZC))
            zti = ZT + (ZG + 0.05 - ZT) * (X[i] / L) ** 2
            ztj = ZT + (ZG + 0.05 - ZT) * (X[i + 1] / L) ** 2
            quad(p, "Canvas", (bx + X[i], sd * (WG[i] + 0.04), ZG - 0.08), (bx + X[i + 1], sd * (WG[i + 1] + 0.04), ZG - 0.08), (bx + X[i + 1], 0, ztj), (bx + X[i], 0, zti))
    quad(p, "Gelcoat", (bx, -WC[0], ZC), (bx, WC[0], ZC), (bx, WG[0], ZG), (bx, -WG[0], ZG))
    return p


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = os.path.abspath(a[0])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(out, exist_ok=True)
    stats = {}
    for fn in (pier, boathouse):
        p = fn()
        stats[p.name] = p.export(out)
    shorekit.write_manifest(out, "before", stats)


if __name__ == "__main__":
    main()
