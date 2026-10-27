"""Near-shore phase 2 (docs/near-shore-audit/phase-2): the wooded shore's understory, built from code like the trees
(build_trees.py's skeleton and leaf cards, the same atlas and materials), placed by ALakeTerrainActor::PlaceUnderstory
under and around the lidar crowns along the water.

  SM_Shrub_0, _1   yaupon holly: an evergreen clump of 5 to 8 thin stems, 2 to 3.5 m, small leaves, dense
  SM_Shrub_2, _3   roughleaf dogwood and coralberry: a lower deciduous thicket, 1 to 2.2 m, broad leaves, spreading
  SM_Sapling_0     a cedar elm sapling, one stem, about 4 m
  SM_Sapling_1     a young red cedar, a ragged cone, about 2.5 m
  SM_Deadfall_0    a fallen trunk 8 m long with its broken limbs and root plate
  SM_Deadfall_1    a tangle of dead limbs (brush pile), 3 m across
  SM_Snag_0        a standing dead trunk, 6 m, a few broken limbs, no leaves

Vertex colours as the trees' (R sway, G flutter phase, B tint); slots Bark and Leaves. Prints "Understory: <name> <tris>".
    blender -b --factory-startup -P Tools/blender/build_understory.py -- <out dir>
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_trees as bt  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1]

SHRUBS = {
    # The trees' spec keys (build_trees.SPECIES); leaf tiles from the shared atlas: 2 the elm's small leaves, 4 the
    # sugarberry's broad ones.
    "Shrub_0": dict(stem_r=0.03, h=(2.6, 3.4), w=0.9, trunk=0.7, limbs=(2, 3), rise=(45, 75), levels=2, leaf=0.55, dens=1.6, droop=0.12, kind="stemmed",
                    stems=(6, 8), splay=(10, 30), lean=0, tiles=(2,)),
    "Shrub_1": dict(stem_r=0.028, h=(2.0, 2.8), w=1.1, trunk=0.5, limbs=(2, 3), rise=(35, 65), levels=2, leaf=0.5, dens=1.6, droop=0.15, kind="stemmed",
                    stems=(5, 7), splay=(15, 35), lean=0, tiles=(2,)),
    "Shrub_2": dict(stem_r=0.022, h=(1.6, 2.2), w=1.5, trunk=0.35, limbs=(2, 3), rise=(25, 55), levels=2, leaf=0.55, dens=1.4, droop=0.2, kind="stemmed",
                    stems=(6, 9), splay=(25, 50), lean=0, tiles=(4,)),
    "Shrub_3": dict(stem_r=0.012, h=(0.9, 1.3), w=1.8, trunk=0.2, limbs=(2, 2), rise=(15, 40), levels=1, leaf=0.42, dens=1.8, droop=0.25, kind="stemmed",
                    stems=(7, 10), splay=(35, 60), lean=0, tiles=(4,)),
    "Sapling_0": dict(stem_r=0.06, h=(3.6, 4.4), w=0.55, trunk=1.4, limbs=(4, 5), rise=(50, 70), levels=2, leaf=0.6, dens=1.0, droop=0.05, kind="stemmed",
                      stems=(1, 1), splay=(0, 4), lean=2, tiles=(2,)),
    "Sapling_1": dict(h=(2.3, 2.7), w=0.55, trunk=0.3, limbs=(0, 0), rise=(0, 0), levels=0, leaf=0.5, dens=0.35, droop=0.0, kind="cone", tiles=(3,), leader_r=0.05),
}


def dead_limb(b, start, direction, length, radius, rng, depth):
    """A bare, broken limb: the trees' bent tube, snapped short, with a stub or two off it."""
    pts = bt.bent(start, direction, length, 4, 0.18, 0.05)
    b.tube(pts, [radius * (1.0 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], sides=6 if radius > 0.06 else 4)
    if depth > 0:
        for _ in range(rng.randint(1, 2)):
            at = pts[rng.randint(1, len(pts) - 2)]
            d = (direction + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 0.8)))).normalized()
            dead_limb(b, at, d, length * rng.uniform(0.3, 0.5), radius * 0.5, rng, depth - 1)


def deadfall():
    """A fallen trunk along +X, half sunk in the leaf litter, its limbs splayed (the downslope ones broken off at the
    ground) and the root plate torn up at the butt."""
    rng = random.Random(41)
    random.seed(41)
    b = bt.Builder("SM_Deadfall_0")
    b.height = 100.0   # no sway
    pts = [Vector((x, 0.12 * math.sin(x * 0.7), 0.16 - 0.012 * x + 0.04 * math.sin(x * 1.3))) for x in (0.0, 1.5, 3.0, 4.5, 6.0, 7.2, 8.0)]
    b.tube(pts, [0.28 * (1.0 - 0.55 * i / (len(pts) - 1)) for i in range(len(pts))], sides=10)
    for k in range(5):
        at = pts[2 + k % 4]
        side = 1 if k % 2 else -1
        d = Vector((rng.uniform(0.3, 0.9), side * rng.uniform(0.4, 1.0), rng.uniform(0.2, 0.9))).normalized()
        dead_limb(b, at, d, rng.uniform(1.2, 2.6), 0.07, rng, 1)
    # The root plate: a ragged disc of earth and roots standing up at the butt.
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.2, 0.2)
        d = Vector((-0.35, math.cos(a), math.sin(a) * 0.9 + 0.3)).normalized()
        dead_limb(b, Vector((0.0, 0.0, 0.2)), d, rng.uniform(0.7, 1.3), 0.06, rng, 0)
    return b


def brush_pile():
    """Dead limbs fallen in a heap, the way the cross timbers' shores are littered after a storm."""
    rng = random.Random(53)
    random.seed(53)
    b = bt.Builder("SM_Deadfall_1")
    b.height = 100.0
    for k in range(9):
        a = rng.uniform(0, 2 * math.pi)
        start = Vector((math.cos(a) * rng.uniform(0.0, 1.2), math.sin(a) * rng.uniform(0.0, 1.2), rng.uniform(0.05, 0.5)))
        d = Vector((math.cos(a + 2.5), math.sin(a + 2.5), rng.uniform(-0.1, 0.25))).normalized()
        dead_limb(b, start, d, rng.uniform(1.6, 3.0), rng.uniform(0.04, 0.09), rng, 1)
    return b


def snag():
    """A standing dead tree: the trunk snapped at about 6 m, three or four limbs broken short, bark only."""
    rng = random.Random(67)
    random.seed(67)
    b = bt.Builder("SM_Snag_0")
    b.height = 100.0
    trunk = bt.bent(Vector((0, 0, -0.3)), Vector((0.05, 0, 1)), 6.3, 5, 0.05, 0.0)
    b.tube(trunk, [0.24 * (1.0 - 0.5 * i / (len(trunk) - 1)) for i in range(len(trunk))], sides=8)
    for k in range(4):
        at = trunk[2 + k % 3]
        a = 2 * math.pi * k / 4 + rng.uniform(-0.4, 0.4)
        d = Vector((math.cos(a), math.sin(a), rng.uniform(0.3, 0.9))).normalized()
        dead_limb(b, at, d, rng.uniform(1.0, 2.2), 0.08, rng, 1)
    return b


def export(b, name):
    obj, tris = bt.finish(b, name)
    bt.export(obj, os.path.join(OUT, name + ".fbx"))
    bpy.data.objects.remove(obj)
    print(f"Understory: {name} {tris}")


def main():
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Shrubs branch from the ground: their limbs may run low (the trees' floor is head height).
    bt.LIMB_FLOOR = 0.15
    for name, spec in SHRUBS.items():
        seed = sum(ord(ch) for ch in name) * 31
        export({"cone": bt.cone_tree, "stemmed": bt.stemmed_tree}.get(spec["kind"], bt.broad_tree)(name, spec, seed), "SM_" + name)
    bt.LIMB_FLOOR = -10.0   # dead wood lies where it fell
    export(deadfall(), "SM_Deadfall_0")
    export(brush_pile(), "SM_Deadfall_1")
    export(snag(), "SM_Snag_0")


main()
