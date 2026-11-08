"""Part detail loop, JibHank extras (docs/part-detail-loop/jibhank.md): the "before" part, the hank in use and its fit.

    python3 Tools/boatkit/partloop/render_hank.py before <out dir>    # render_views.py's views of the J/22 hero's old hank
    python3 Tools/boatkit/partloop/render_hank.py in_use <out dir>    # on a 6.4 mm forestay with the luff in its slot
    python3 Tools/boatkit/partloop/render_hank.py in_use_before <out dir>   # the old hank on the same stay and luff
    python3 Tools/boatkit/partloop/render_hank.py fit <out dir>       # fit.json: the eye and mouth against the wire

(bpy module, or blender -b --factory-startup -P ... -- <mode> <out dir>.) The before part is registered here only, never
in the kit: it is the proof of concept's hank from Inputs/j22-hero/build_j22_hero.py (a 28 mm cylinder and a 16 mm pin,
both bronze), rebuilt in the part's frame (stay along Y). The in-use stills add a forestay and a patch of luff,
render-only like render_views.py's lines.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_part_jibhank as H  # noqa: E402
import bk_render as R  # noqa: E402
import render_views as RV  # noqa: E402


def before_hank():
    """The J/22 hero proof of concept's hank, as it was (Oct 2026): hero frame (stay ~Z) turned to the part's (stay Y)."""
    br = P.M("Brass")
    body = G.cyl("Hank", (-0.014, -0.010, 0.0), (0.014, 0.010, 0.0), 0.0065, br, 12)
    pin = G.cyl("HankPiston", (0.004, 0.012, 0.0), (0.004, 0.028, 0.0), 0.0025, br, 8)
    return P.done("JibHankBefore", [body, pin], [("Stay", (0.0, 0.0, 0.0))])


def _mat(name, col, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def in_use(out, name="JibHank"):
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    ob = P.build(name)
    # forestay: 7x19-looking stainless wire, 6.4 mm, along Y through the eye
    wire = G.cyl("RenderStay", (0, -0.05, 0), (0, 0.05, 0), H.WIRE / 2000, None, 24)
    wire.data.materials.append(_mat("RenderStayMat", (0.55, 0.56, 0.58), 0.35, 1.0))
    # luff: a patch of sailcloth in the XY plane, its edge in the slot, with a reinforcing patch round the hank
    luff_x = (H.TAIL_X[0] + H.TAIL_X[1]) / 2000 - 0.003
    sail = G.box("RenderSail", (luff_x - 0.06, 0, H.SAIL_Z / 1000), (0.12, 0.18, 0.0009))
    sail.data.materials.append(_mat("RenderSailMat", (0.80, 0.79, 0.74), 0.6))
    patch = G.box("RenderPatch", (luff_x - 0.012, 0, H.SAIL_Z / 1000), (0.026, 0.032, 0.0018))
    patch.data.materials.append(_mat("RenderPatchMat", (0.72, 0.71, 0.66), 0.5))
    sail.data.transform(Matrix.Diagonal((1.0, 0.56, 1.0, 1.0)))
    dress = [wire, sail, patch]
    # stand the stay up as on the boat: the part's Y (the stay) becomes Z, the sail's plane becomes upright (XZ)
    up = Matrix.Rotation(math.radians(90), 4, "X")
    for o in [ob] + dress:
        o.data.transform(up)
        o.data.update()
    # abeam (looking square at the sail, as from the cockpit), from forward and above, and from forward low on the stay
    for view, d, dist in (("in_use_side", (0.12, -1.0, 0.12), 1.7), ("in_use", (1.0, -0.75, 0.55), 1.7),
                          ("in_use_along", (0.9, -0.3, -0.3), 1.8)):
        c, size = RV.studio(ob, 900, 900, 32)
        R._camera(c + Vector(d).normalized() * size * 2.2 * dist, c, 85)
        RV.shoot(os.path.join(out, f"{view}.png"))
    for o in dress:
        bpy.data.objects.remove(o, do_unlink=True)


def fit(out):
    """Measure, on the built mesh at y = 0 (the J's mid-plane): the eye's clear radius round the stay's centre and the
    mouth's clear gap along the piston's line with the piston drawn back."""
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    ob = P.build("JibHank")
    me = ob.data
    bm_verts = [v.co.copy() for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles] if me.loop_triangles else None
    if tris is None:
        me.calc_loop_triangles()
        tris = [tuple(t.vertices) for t in me.loop_triangles]
    # body only: the moulding's faces carry the WhitePlastic slot
    wp = [i for i, m in enumerate(me.materials) if m and m.name.startswith("WhitePlastic")]
    body_tris = [tuple(t.vertices) for t in me.loop_triangles if t.material_index in wp]
    bvh = BVHTree.FromPolygons(bm_verts, body_tris)
    clear = 1e9
    for k in range(360):
        a = math.radians(k)
        d = Vector((math.cos(a), 0, math.sin(a)))
        hit = bvh.ray_cast(Vector((0, 0, 0)), d, 0.05)
        if hit[0] is not None:
            clear = min(clear, hit[3])
    rc = H.EYE_R + H.HOOK_W / 2
    zp = rc * math.sin(math.radians(H.TIP_DEG)) / 1000
    # the mouth: from just aft of the tip, along -X on the piston's line, to the body's front face
    tip_x = rc * math.cos(math.radians(H.TIP_DEG)) / 1000
    start = Vector((tip_x - 0.0002, 0, zp))
    hit = bvh.ray_cast(start, Vector((-1, 0, 0)), 0.05)
    # ...and the tip's own end face: cast forward from inside the gap
    mid = Vector((tip_x - 0.004, 0, zp))
    tip_hit = bvh.ray_cast(mid, Vector((1, 0, 0)), 0.05)
    back_hit = bvh.ray_cast(mid, Vector((-1, 0, 0)), 0.05)
    # the mouth's narrowest clear gap is across from the tip's end to the body, at any height in the gap
    gaps = []
    for dz in range(-30, 31):
        p = Vector((tip_x - 0.004, 0, zp + dz * 0.0001))
        f, b = bvh.ray_cast(p, Vector((1, 0, 0)), 0.05), bvh.ray_cast(p, Vector((-1, 0, 0)), 0.05)
        if f[0] is not None and b[0] is not None:
            gaps.append(f[3] + b[3])
    res = {"wire_mm": H.WIRE, "eye_clear_diameter_mm": round(2 * clear * 1000, 2),
           "mouth_gap_on_piston_line_mm": round((tip_hit[3] + back_hit[3]) * 1000, 2) if tip_hit[0] and back_hit[0] else None,
           "mouth_gap_min_mm": round(min(gaps) * 1000, 2) if gaps else None,
           "eye_ok": 2 * clear * 1000 >= H.WIRE + 1.0,
           "mouth_ok": bool(gaps) and min(gaps) * 1000 >= H.WIRE + 0.3}
    json.dump(res, open(os.path.join(out, "fit.json"), "w"), indent=1)
    print("Fit:", res)


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    mode, out = a[0], os.path.abspath(a[1])
    if mode == "before":
        P.PARTS["JibHankBefore"] = (before_hank, {"category": "rigging", "note": "loop only: the hero PoC's hank"})
        sys.argv = [sys.argv[0], "JibHankBefore", out] + a[2:]
        RV.main()
    elif mode == "in_use":
        in_use(out)
    elif mode == "in_use_before":
        P.PARTS["JibHankBefore"] = (before_hank, {"category": "rigging", "note": "loop only: the hero PoC's hank"})
        in_use(out, "JibHankBefore")
    elif mode == "fit":
        fit(out)
    else:
        raise SystemExit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
