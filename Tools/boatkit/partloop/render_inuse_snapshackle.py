"""Part detail loop: the snap shackle's two "in use" stills (docs/part-detail-loop/snapshackle.md), added to a round
render_views.py made: a 10 mm spinnaker sheet eye-spliced round the fixed eye and a sail's clew ring in the bail, with a
corner of sailcloth. Render-only dressing, never exported (render_views.py dresses blocks and cleats the same way).

    python3 Tools/boatkit/partloop/render_inuse_snapshackle.py <round dir> [--samples N] [--part ShackleD]
    (or blender -b --factory-startup -P Tools/boatkit/partloop/render_inuse_snapshackle.py -- <round dir> ...)

--part ShackleD dresses the old D-shackle the same way (the "before" stand-in): the sheet round its pin, the clew ring
on its bow.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402
import render_views as RV  # noqa: E402


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 32
    part = a[a.index("--part") + 1] if "--part" in a else "SnapShackle"
    return os.path.abspath(a[0]), samples, part


def mat(name, rgb, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def catmull(key, per=8):
    k = [Vector(p) for p in key]
    out = []
    for i in range(len(k) - 1):
        p0, p1, p2, p3 = k[max(i - 1, 0)], k[i], k[i + 1], k[min(i + 2, len(k) - 1)]
        for j in range(per):
            t = j / per
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(k[-1])
    return [tuple(p) for p in out]


def dressing(bar, top, sheet_r=0.005, clew_r=0.010):
    """The sheet's eye splice round a bar (centre `bar`, the bar running along X) and a clew ring hanging from `top`
    (the load point), its plane square to the part's (YZ), with a corner of sailcloth."""
    rope_m = mat("SheetMat", (0.02, 0.12, 0.25), 0.8)
    cloth_m = mat("ClothMat", (0.85, 0.85, 0.82), 0.6)
    ring_m = mat("ClewRingMat", (0.6, 0.6, 0.62), 0.3, 1.0)
    bx, bz = bar[0], bar[2]
    w = 0.0042 + sheet_r                       # round the bar's thickness
    key = [(bx, 0, bz - 0.11), (bx, 0, bz - 0.06), (bx, -0.004, bz - 0.030), (bx, -w, bz - 0.010), (bx, -w * 0.9, bz + 0.002),
           (bx, 0, bz + 0.0065), (bx, w * 0.9, bz + 0.002), (bx, w, bz - 0.010), (bx, 0.004, bz - 0.030), (bx, 0.0, bz - 0.052)]
    pts = catmull(key)
    radii = []
    for i in range(len(pts)):
        t = i / (len(pts) - 1)
        radii.append(1.0 if t < 0.82 else 1.0 - 0.45 * (t - 0.82) / 0.18)   # the splice's tucked tail tapers into the standing part
    rope = G.sweep("RenderSheet", pts, G.ellipse(sheet_r, sheet_r, 16), rope_m, radii=radii)
    # clew ring: torus in the YZ plane hanging from the load point
    rc = Vector(top) + Vector((0, 0, clew_r + 0.0022))
    ring = G.tube("RenderClew", [(rc.x, rc.y + clew_r * math.cos(G.TAU * i / 48), rc.z + clew_r * math.sin(G.TAU * i / 48)) for i in range(48)],
                  0.0022, ring_m, 12, closed=True)
    # sailcloth corner: a thin triangle through the ring, opening upward and away from the part
    tri = [(0, -0.002), (0.004, 0.0), (0.090, 0.050), (0.030, 0.095), (0, 0.010)]
    cloth = G.prism("RenderCloth", [(y, z) for y, z in tri], -0.0006, 0.0006, cloth_m)
    cloth.matrix_world = Matrix.Translation(rc + Vector((0, 0.004, 0.004))) @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "Z")
    G.bake_xform(cloth)
    return [rope, ring, cloth]


def main():
    out, samples, part = args()
    G.clear_scene()
    ob = P.build(part)
    socks = {c.name.split(".")[0][7:]: Vector(c.location) for c in ob.children}
    if part == "SnapShackle":
        import bk_part_snapshackle as S
        bar = Vector(S._xz(*S.eye_bottom()))
        top = socks["Bail"]
    else:                                   # ShackleD: pin along Y at the origin, bow up
        bar = Vector((0, 0, 0))
        top = socks["Bow"]
        ob.data.transform(Matrix.Rotation(math.radians(90), 4, "Z"))   # pin along X, like the snap shackle's eye bar
    extra = dressing(bar, top)
    for view, d in (("in_use_side", (0.0, -1.0, 0.15)), ("in_use", (1.0, -1.0, 0.7))):
        c, size = RV.studio(ob, 900, 900, samples)
        R._camera(c + Vector(d).normalized() * size * 2.2 * 1.9, c, 85)
        RV.shoot(os.path.join(out, f"{view}.png"))
    for e in extra:
        bpy.data.objects.remove(e, do_unlink=True)
    print(f"Loop: in-use stills -> {out}")


if __name__ == "__main__":
    main()
