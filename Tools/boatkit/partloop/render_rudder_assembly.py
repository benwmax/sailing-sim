"""Part detail loop: the J/22's rudder fittings in place on the hero's blade and transom (docs/part-detail-loop/rudder.md).

    python3 Tools/boatkit/partloop/render_rudder_assembly.py <out dir> [--before] [--samples N]
    (or blender -b --factory-startup -P Tools/boatkit/partloop/render_rudder_assembly.py -- <out dir> ...)

After: at each of the hero's two pintle heights, the kit's Pintle on the blade and two kit Gudgeons (50 mm offset, the
J/22's) on the transom, one above and one below it. Before (--before): the hero's own pintles and gudgeons as built today
(Inputs/j22-hero/j22_steering.py build_pintles, build_gudgeons). Both on the same context: the hero's blade
(j22_steering.build_blade) and a slab of transom, in the hero's materials, so only the hardware differs. Views: quarter
(from aft and above on the starboard quarter, where the crew sees it), side (square to the boat's side at the upper
station), aft (from astern, looking forward), close (the lower station), clay (shape only). Writes stats.json.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "Inputs", "j22-hero"))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402
import render_views as RV  # noqa: E402
import render_assembly as RA  # noqa: E402

UP = 0.47          # j22_steering.PINTLE_Z
LO = 0.05

VIEWS = {
    "quarter": ((-1.0, -0.9, 0.55), (-3.47, 0, 0.30), 1.10, 50),
    "side":    ((0.0, -1.0, 0.02), (-3.50, 0, UP), 0.42, 50),
    "aft":     ((-1.0, -0.25, 0.20), (-3.47, 0, UP), 0.40, 50),
    "close":   ((-0.7, -1.0, 0.35), (-3.47, 0, LO), 0.30, 85),
}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 32
    return os.path.abspath(a[0]), "--before" in a, samples


def context(MAT, S):
    blade = S.build_blade(MAT["CabinGelcoat"])
    tr = G.box("transom", (S.TRANSOM_X + 0.03, 0, 0.30), (0.06, 0.80, 0.90), MAT["CabinGelcoat"])
    return [blade, tr]


def kit_place(ob, x, z, flip=True):
    """Kit frame (+X aft) into the hero's (aft is -X): turn half round Z about the origin, then place."""
    ob.matrix_world = Matrix.Translation((x, 0, z)) @ (Matrix.Rotation(math.pi, 4, "Z") if flip else Matrix.Identity(4))
    for c in ob.children:
        c.hide_render = True
    return ob


def hero_slots(ob, MAT):
    """Give a kit part the hero's materials of the same names, so before and after differ only in shape."""
    for i, m in enumerate(ob.data.materials):
        if m is not None and m.name.split(".")[0] in MAT:
            ob.data.materials[i] = MAT[m.name.split(".")[0]]
    return ob


def after(MAT, S):
    objs = []
    off = S.TRANSOM_X - S.PIVOT_X
    for z in S.PINTLE_Z:
        objs.append(kit_place(P.build("Pintle", blade=0.036, chord=0.35, length=0.27), S.PIVOT_X, z))
        for dz in (0.028, -0.028):
            objs.append(kit_place(P.build("Gudgeon", offset=off), S.TRANSOM_X, z + dz))
    return [hero_slots(o, MAT) for o in objs]


def before(MAT, S):
    return S.build_pintles(MAT) + S.build_gudgeons(MAT)


def studio(c, size, samples):
    RV.reset_studio()
    R.SAMPLES = samples
    R._engine(1200, 900)
    bpy.context.scene.cycles.samples = samples
    R._floor(-1.05, 20)
    for nm, off, k, spread in (("Key", (-1, -1.2, 1.6), 26, 2.0), ("Rim", (1.5, 1.2, 0.8), 12, 1.5), ("Fill", (1.2, -2.0, -0.3), 5, 3.0)):
        pos = c + Vector(off) * size * 3
        R._light(nm, "AREA", pos, c, k * (pos - c).length_squared, size * spread)


def main():
    out, is_before, samples = args()
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    MAT = RA.hero_materials(out)
    import j22_steering as S
    ctx = context(MAT, S)
    hard = before(MAT, S) if is_before else after(MAT, S)
    stats = {"assembly": "rudder", "round": "before" if is_before else "after", "hardware_tris": RA.tris(hard),
             "hardware": sorted({o.name.split(".")[0] for o in hard})[:40]}
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print(f"Assembly: rudder {stats['round']} {stats['hardware_tris']} hardware tris")
    for view, (d, look, dist, lens) in VIEWS.items():
        c = Vector(look)
        studio(c, dist * 0.5, samples)
        R._camera(c + Vector(d).normalized() * dist * (lens / 50), c, lens)
        RV.shoot(os.path.join(out, f"{view}.png"))
    clay = bpy.data.materials.new("Clay")
    clay.use_nodes = True
    clay.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
    for o in hard:
        for i in range(len(o.data.materials)):
            o.data.materials[i] = clay
    d, look, dist, lens = VIEWS["side"]
    studio(Vector(look), dist * 0.5, samples)
    R._camera(Vector(look) + Vector(d).normalized() * dist, Vector(look), lens)
    RV.shoot(os.path.join(out, "clay.png"))
    print(f"Assembly: views -> {out}")


if __name__ == "__main__":
    main()
