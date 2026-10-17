"""Broadside profile match: the hero's side silhouette drawn over a photo taken square to the boat.

A broadside photo has no depth to solve, so this needs no camera: two picked points (the stem top and the transom top
on the near sheer) give the scale, and the hero's outline (every polygon of its Hull and Deck collections, projected on
the centreplane) is laid over the photo about the stem top, turned by an optional pitch. Distances read at one station
(keel depth, freeboard) hardly move with pitch; parts on the centreline (cabin, keel) sit a half-beam further away than
the near sheer, so in a photo from closer than about 10 m their ends close toward the image centre by a few percent.

    python3 profile_match.py matches/<photo>.profile.json <hero.blend> <photo.jpg> <out.png> [pitch_deg]

Runs under Blender or the `bpy` module. The match file holds only picked pixel numbers and the photo's source and
licence, never the photo (docs/boatkit-3).
"""
import json
import math
import sys

import bpy
from PIL import Image, ImageDraw

BOW, STERN = 3.45, -3.41          # hero frame: x forward, z up, origin on the design waterline amidships


def silhouette(blend, s=100.0, x0=-3.8, z0=1.6):
    """Hull and deck seen from the side, rasterised at s px/m with the image's left edge at x0 and top at z0."""
    bpy.ops.wm.open_mainfile(filepath=blend)
    im = Image.new("L", (int(7.6 * s), int(3.2 * s)), 0)
    d = ImageDraw.Draw(im)
    dg = bpy.context.evaluated_depsgraph_get()
    for cn in ("Hull", "Deck"):
        for o in bpy.data.collections[cn].objects:
            if o.type != "MESH":
                continue
            me = o.evaluated_get(dg).to_mesh()
            vs = [o.matrix_world @ v.co for v in me.vertices]
            for p in me.polygons:
                d.polygon([((vs[i].x - x0) * s, (z0 - vs[i].z) * s) for i in p.vertices], fill=255)
    return im, s, x0, z0


def main(argv):
    match, blend, photo, out = argv[:4]
    pitch = math.radians(float(argv[4])) if len(argv) > 4 else 0.0
    m = json.load(open(match))
    (bx, by), (sx, sy) = m["stem_top_px"], m["transom_top_px"]
    zb = m.get("stem_top_z", 0.79)
    bow_left = bx < sx
    scale = math.hypot(sx - bx, sy - by) / (BOW - STERN)
    sil, s, x0, z0 = silhouette(blend)
    edge = sil.filter(__import__("PIL.ImageFilter", fromlist=["FIND_EDGES"]).FIND_EDGES)
    pix = edge.load()
    img = Image.open(photo).convert("RGB")
    out_px = img.load()
    c, sn = math.cos(pitch), math.sin(pitch)
    for j in range(edge.size[1]):
        for i in range(edge.size[0]):
            if not pix[i, j]:
                continue
            dx, dz = (x0 + i / s) - BOW, (z0 - j / s) - zb
            rx, rz = dx * c - dz * sn, dx * sn + dz * c
            px = bx + (-rx if bow_left else rx) * scale
            py = by - rz * scale
            if 0 <= px < img.size[0] and 0 <= py < img.size[1]:
                out_px[int(px), int(py)] = (255, 0, 0)
    img.save(out)
    # the picked stations, back in hero metres, for the README's table
    for name, (u, v) in m.get("points", {}).items():
        x = BOW - (u - bx) / scale * (1 if bow_left else -1)
        z = zb - (v - by) / scale
        print(f"{name:24s} x {x:+.3f}  z {z:+.3f}")
    print(f"scale {scale:.2f} px/m; outline in red over {out}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
