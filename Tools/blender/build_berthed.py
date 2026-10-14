"""Visual V7: what a boat in its slip wears, for the marina's neighbours (AMarinaActor): the standing rigging (the
sailing boat draws its own, live), the jib furled on its forestay with its sun strip, the main flaked on the boom under
a sail cover, halyards along the mast, fenders over the side and dock lines to the finger and the dock. Built from the
class model's own sockets (<Tag>_sockets.json from build_j22.py / build_fleet.py) so it fits the hull and mast exactly.

    blender -b --factory-startup -P Tools/blender/build_berthed.py -- <Tag> <boat.json> <models dir> [variant]

Writes <models>/SM_<Tag>_Berthed.fbx (variant 0; also the player's boat tied up) or SM_<Tag>_Berthed_<v>.fbx in the boat
frame (origin at the hull's), slots as SLOTS. Prints "Berthed: <Tag> <variant> <tris>".

Graphics G6: round 7's "all the boats are exactly the same". Variants 1 to 5 each dress a boat differently, the way a club
marina looks: the cover's colour (navy, burgundy, forest green, sun-faded tan), or no cover and the main flaked under sail
ties, or a grey canvas cover tented over the boom; the jib rolled on its stay or bagged on the foredeck; a dodger on the
Catalinas; fenders (two to six, bare or in navy covers, at different heights); and gear: a cooler, a bucket, a boat hook,
a tiller cover, cushions, an outboard on its stern bracket, a burgee on the backstay.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
TAG, CFG_PATH, MODELS = ARGS[:3]
V = int(ARGS[3]) if len(ARGS) > 3 else 0
CFG = json.load(open(CFG_PATH))
META = json.load(open(os.path.join(MODELS, f"{TAG}_sockets.json")))
S = {k: Vector(v) / 100.0 for k, v in META["sockets"].items()}       # boat frame, metres (Unreal axes)
SLOTS = ["Stainless", "SailCover", "Deck", "Rope", "BlackPlastic", "Aluminium",
         "SailCoverRed", "SailCoverGreen", "SailCoverTan", "Tarp", "Dacron", "FenderBlue", "CoolerLid", "CabinWindow"]
# Per variant: cover slot (None: main flaked under ties), jib ("roll" or "bag"), fenders per side, covered fenders, tarp.
VARIANTS = [
    dict(cover="SailCover", jib="roll", fenders=2, fcover=False, tarp=False, gear=()),
    dict(cover="SailCoverRed", jib="bag", fenders=1, fcover=True, tarp=False, gear=("cooler", "outboard", "dodger")),
    dict(cover="SailCoverGreen", jib="roll", fenders=3, fcover=False, tarp=False, gear=("tillercover", "boathook", "bucket", "burgee")),
    dict(cover=None, jib="roll", fenders=2, fcover=True, tarp=False, gear=("cushions", "outboard", "dodger")),
    dict(cover="SailCover", jib="bag", fenders=2, fcover=False, tarp=True, gear=("burgee",)),
    dict(cover="SailCoverTan", jib="roll", fenders=2, fcover=False, tarp=False, gear=("cooler", "boathook", "tillercover")),
]
VAR = dict(VARIANTS[V % len(VARIANTS)])
# A furler's sun strip is navy on most boats (faded tan on one); a J/22's hank-on jib is bagged on deck or taken below.
JIB_SLOT = "SailCoverTan" if V == 3 else "SailCover"
if TAG == "J22" and V:
    VAR["jib"] = "bag" if V % 2 else "none"

bm = bmesh.new()


def P(v):
    return (v[0], -v[1], v[2])                                        # Unreal's starboard +Y -> Blender's -Y


def tube(path, radius, slot, sides=6, radius_end=None):
    pts = [Vector(p) for p in path]
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(a).normalized()
        w = t.cross(u).normalized()
        r = radius if radius_end is None else radius + (radius_end - radius) * i / max(len(pts) - 1, 1)
        rings.append([bm.verts.new(P(p + (u * math.cos(2 * math.pi * k / sides) + w * math.sin(2 * math.pi * k / sides)) * r)) for k in range(sides)])
    m = SLOTS.index(slot)
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            f = bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
            f.material_index = m
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        f = bm.faces.new(list(reversed(ring)) if rev else ring)
        f.material_index = m


def sag(a, b, droop, n=10):
    a, b = Vector(a), Vector(b)
    return [a + (b - a) * (k / n) - Vector((0, 0, droop * 4 * (k / n) * (1 - k / n))) for k in range(n + 1)]


wire = 0.004 if CFG["rig"]["masthead_z"] < 10 else 0.006
# Standing rigging (straight, under tension).
if "Hounds" in S and "ForestayTack" in S:
    tube([S["ForestayTack"], S["Hounds"]], wire, "Stainless")
    for tag in ("S", "P"):
        up, tip = S.get(f"ChainplateUpper_{tag}"), S.get(f"SpreaderTip_{tag}")
        if up is None:
            continue
        if tip is not None:
            tube([up, tip, S["Hounds"]], wire, "Stainless")
            tube([S[f"ChainplateLower_{tag}"], S["LowerTang"]], wire, "Stainless")
        else:
            tube([up, S["Hounds"]], wire, "Stainless")
    if "BackstayPlate" in S:
        tube([S["BackstayPlate"], S["MastheadAft"]], wire * 0.9, "Stainless")
    # The jib rolled on its forestay: a tapering spiral roll with the sun strip outermost.
    a, b = S["ForestayTack"], S["Hounds"]
    roll = [a + (b - a) * t for t in [0.06 + 0.86 * k / 16 for k in range(17)]]
    if VAR["jib"] == "roll":
        tube(roll, 0.075 if CFG["loa"] > 8 else 0.055, JIB_SLOT, 10, 0.02)
# The mast itself (the sailing boat's bends, so it is not Nanite; at rest a straight tube in this Nanite mesh will do),
# with its spreaders, so the marina draws no non-Nanite masts.
if "MastStep" in S:
    top = CFG["rig"]["masthead_z"]
    d = CFG["rig"]["mast_diameter"]
    tube([S["MastStep"], Vector((S["MastStep"].x, 0.0, top))], 0.5 * d, "Aluminium", 10, 0.35 * d)
    for tag in ("S", "P"):
        if f"SpreaderTip_{tag}" in S:
            tube([Vector((S["MastStep"].x, 0.0, S[f"SpreaderTip_{tag}"].z)), S[f"SpreaderTip_{tag}"]], 0.012, "Aluminium", 6)
# Halyards along the mast, slapping distance off it, cleated at the base.
if "MastStep" in S:
    top = S["MastStep"].z + (CFG["rig"]["masthead_z"] - S["MastStep"].z) * 0.98
    for dy in (0.03, -0.03):
        base = S["MastStep"] + Vector((0.08, dy, 0.6))
        tube(sag(base, Vector((S["MastStep"].x - 0.05, dy, top)), -0.12 if dy > 0 else -0.06, 8), 0.004, "Rope", 4)
# Main flaked on the boom under a cover, from the gooseneck to near the clew.
gx, gz = CFG["rig"]["main_luff_x"], CFG["rig"]["boom_z"]
clew = S.get("Boom_Clew", Vector((gx - CFG["rig"]["main_foot_chord"], 0, gz)))
L = gx - clew.x
cover = [Vector((gx - 0.05 - L * 0.88 * k / 10, 0, gz + 0.1 - 0.05 * k / 10)) for k in range(11)]
big = CFG["loa"] > 8
if VAR["cover"]:
    tube(cover, 0.15 if big else 0.11, VAR["cover"], 10, 0.07 if big else 0.05)
else:
    # No cover: the main flaked on the boom in folds, lashed with sail ties.
    flake = [Vector((p.x, 0.03 * math.sin(k * 2.1), p.z - 0.01)) for k, p in enumerate(cover)]
    tube(flake, 0.13 if big else 0.095, "Dacron", 8, 0.06 if big else 0.045)
    for k in (2, 5, 8):
        p = cover[k]
        r = (0.13 if big else 0.095) * (1 - 0.55 * k / 10) + 0.012
        tube([p + Vector((0, r * math.cos(2 * math.pi * j / 10), r * math.sin(2 * math.pi * j / 10))) for j in range(11)], 0.008, "SailCoverRed", 4)
# Fenders over both sides (the side against a finger and the side toward the neighbour), on their lines.
H = CFG["hulls"][0]


def half_beam(x):
    if x > H["max_beam_x"]:
        u = (x - H["max_beam_x"]) / (H["bow_x"] - H["max_beam_x"] + 0.02)
        return H["max_half_beam"] * math.sqrt(max(0.0, 1 - u * u))
    u = (H["max_beam_x"] - x) / H["aft_length"]
    return max(H["max_half_beam"] - H["transom_beam_loss"] * u * u, 0.02)


sheer = H["sheer_z"]
fr = 0.09 if CFG["loa"] > 8 else 0.07
FENDER_X = {1: (H["max_beam_x"] + 0.3,), 2: (H["max_beam_x"] + 0.9, H["max_beam_x"] - 0.6),
            3: (H["max_beam_x"] + 1.3, H["max_beam_x"] + 0.2, H["max_beam_x"] - 0.9)}
for side in (1, -1):
    for i, x in enumerate(FENDER_X[VAR["fenders"]]):
        drop = 0.25 + (0.08 * ((V + i) % 3) if V else 0.0)   # tied at different heights on the variants
        y = side * (half_beam(x) + fr + 0.01)
        tube([Vector((x, y, sheer - drop - 0.5)), Vector((x, y, sheer - drop))], fr * (1.15 if VAR["fcover"] else 1.0), "FenderBlue" if VAR["fcover"] else "Deck", 10)
        tube([Vector((x, side * (half_beam(x) - 0.05), sheer + 0.02)), Vector((x, y, sheer - drop))], 0.004, "Rope", 4)
# Dock lines: bow lines forward and out to the dock's cleats, stern lines aft to the finger ends, all with a little sag.
bow, stern = H["bow_x"], H["stern_x"]
for side in (1, -1):
    tube(sag((bow - 0.25, side * 0.2, sheer + 0.06), (bow + 0.7, side * 1.25, 0.5), 0.12), 0.006, "Rope", 5)
    tube(sag((stern + 0.3, side * (half_beam(stern + 0.3) - 0.08), sheer + 0.05), (stern - 0.35, side * 1.75, 0.5), 0.1), 0.006, "Rope", 5)
    tube(sag((bow - 0.6, side * (half_beam(bow - 0.6) - 0.05), sheer + 0.08), (stern + 1.2, side * 1.75, 0.5), 0.15, 12), 0.006, "Rope", 5)  # spring

# ---------------------------------------------------------------- Graphics G6: the variants' dress and gear
# The cockpit per class: aft and forward ends, half width, sole height (build_j22.py, build_fleet.py SPECS); the cabin top.
COCKPIT = {"J22": (-3.27, -0.72, 0.62, 0.30), "Catalina22": (-3.05, -0.78, 0.63, sheer + 0.03 - 0.42),
           "Catalina30": (-4.05, -1.32, 0.82, sheer + 0.04 - 0.5)}[TAG]
CABIN_TOP = S["LazySheetVia"].z - 0.065 if "LazySheetVia" in S else sheer + 0.3


def box(c, h, slot, yaw=0.0):
    cs, sn = math.cos(yaw), math.sin(yaw)
    vs = []
    for dz in (-1, 1):
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x, y = dx * h[0], dy * h[1]
            vs.append(bm.verts.new(P((c[0] + x * cs - y * sn, c[1] + x * sn + y * cs, c[2] + dz * h[2]))))
    m = SLOTS.index(slot)
    for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        f = bm.faces.new([vs[i] for i in q])
        f.material_index = m


def sheet(pts, slot):
    """A two-sided panel (canvas, tarp, flag): each side its own face."""
    m = SLOTS.index(slot)
    for seq in (pts, list(reversed(pts))):
        f = bm.faces.new([bm.verts.new(P(v)) for v in seq])
        f.material_index = m


x0, x1, hw, sole = COCKPIT
gear = VAR["gear"]
if VAR["jib"] == "bag" and "ForestayTack" in S:
    # The jib in its bag on the foredeck, lashed down behind the stay.
    a = S["ForestayTack"]
    bag = [Vector((a.x - 0.25 - 1.3 * k / 6, 0.04 * math.sin(k), sheer + 0.12 + 0.02 * math.sin(k * 1.3))) for k in range(7)]
    tube(bag, 0.14 if big else 0.11, JIB_SLOT, 10, 0.09 if big else 0.07)
if VAR["tarp"]:
    # A grey canvas cover tented over the boom from the mast to the stern, tied off to the toe rails.
    for k in range(9):
        xa = gx - 0.2 - (gx - 0.2 - x0) * k / 9
        xb = gx - 0.2 - (gx - 0.2 - x0) * (k + 1) / 9
        za, zb = gz + 0.12 - 0.06 * k / 9, gz + 0.12 - 0.06 * (k + 1) / 9
        for side in (1, -1):
            ya, yb = side * half_beam(xa) * 0.97, side * half_beam(xb) * 0.97
            sheet([(xa, 0, za), (xb, 0, zb), (xb, yb, sheer + 0.12), (xa, ya, sheer + 0.12)], "Tarp")
if "dodger" in gear and TAG != "J22":
    # A dodger over the companionway: canvas on a stainless frame, a clear window across its front.
    dx0 = x1 + 0.05
    hwd = hw + 0.08
    arch = lambda x, rise: [(x, hwd * math.cos(math.pi * k / 10), sheer + 0.05 + rise * math.sin(math.pi * k / 10)) for k in range(11)]
    rise = 0.7 if big else 0.55
    pa, pb = arch(dx0, rise), arch(dx0 + 0.55, rise * 0.92)
    for k in range(10):
        sheet([pa[k], pa[k + 1], pb[k + 1], pb[k]], VAR["cover"] or "SailCover")
    tube(arch(dx0, rise), 0.012, "Stainless", 6)
    tube(arch(dx0 + 0.55, rise * 0.92), 0.012, "Stainless", 6)
    # The window panel across the front, set into the canvas.
    pf = arch(dx0 + 0.552, rise * 0.92)
    for k in (3, 4, 5, 6):
        sheet([(v[0] + 0.004, v[1], v[2] - 0.01) for v in (pf[k], pf[k + 1], (pf[k + 1][0], pf[k + 1][1] * 0.9, pf[k + 1][2] - 0.18), (pf[k][0], pf[k][1] * 0.9, pf[k][2] - 0.18))], "CabinWindow")
if "cooler" in gear:
    cx = x0 + 0.35 * (x1 - x0)
    box((cx, 0.12, sole + 0.17), (0.25, 0.17, 0.17), "Deck", 0.15)
    box((cx, 0.12, sole + 0.355), (0.26, 0.18, 0.025), "CoolerLid", 0.15)
if "bucket" in gear:
    bx = x0 + 0.6 * (x1 - x0)
    tube([(bx, -0.2, sole), (bx, -0.2, sole + 0.3)], 0.13, "BlackPlastic", 12, 0.15)
if "cushions" in gear:
    for side in (1, -1):
        box((0.5 * (x0 + x1), side * (hw - 0.17), sole + 0.2 + 0.03), (0.4 * (x1 - x0), 0.16, 0.03), "SailCoverTan")
if "tillercover" in gear and "TillerEnd" in S and "RudderStock" in S:
    a, b = S["RudderStock"], S["TillerEnd"]
    tube([a + (b - a) * (0.15 + 0.85 * k / 6) + Vector((0, 0, 0.03)) for k in range(7)], 0.04, VAR["cover"] or "SailCover", 8, 0.03)
if "boathook" in gear:
    tube([(x1 + 0.1, 0.35, CABIN_TOP + 0.03), (x1 + 2.0, 0.42, CABIN_TOP + 0.03)], 0.014, "Aluminium", 6)
    box((x1 + 2.05, 0.42, CABIN_TOP + 0.03), (0.06, 0.02, 0.02), "BlackPlastic")
if "outboard" in gear:
    # A Mercury outboard tilted up on its bracket off the transom (port side, clear of the rudder).
    sx = H["stern_x"] - 0.12
    box((sx, -0.42, sheer - 0.05), (0.06, 0.16, 0.12), "Stainless")                         # the bracket
    box((sx - 0.22, -0.42, sheer + 0.18), (0.22, 0.15, 0.17), "BlackPlastic", 0.0)         # the cowl
    tube([(sx - 0.2, -0.42, sheer + 0.02), (sx - 0.62, -0.42, sheer - 0.12)], 0.045, "BlackPlastic", 8, 0.03)  # leg, tilted
    tube([(sx - 0.62, -0.42, sheer - 0.12), (sx - 0.7, -0.42, sheer - 0.14)], 0.05, "Aluminium", 8)            # lower unit
    tube([(sx - 0.05, -0.32, sheer + 0.16), (sx + 0.35, -0.32, sheer + 0.12)], 0.012, "Aluminium", 6)        # tiller arm
if "burgee" in gear and "BackstayPlate" in S and "MastheadAft" in S:
    a, b = S["BackstayPlate"], S["MastheadAft"]
    p = a + (b - a) * 0.25
    sheet([(p.x, p.y, p.z + 0.25), (p.x, p.y, p.z), (p.x - 0.4, p.y + 0.04, p.z + 0.11)], "SailCoverRed")

mesh = bpy.data.meshes.new(f"SM_{TAG}_Berthed" + (f"_{V}" if V else ""))
bm.to_mesh(mesh)
tris = sum(len(f.verts) - 2 for f in bm.faces)
bm.free()
for s in SLOTS:
    mesh.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
obj = bpy.data.objects.new(mesh.name, mesh)
bpy.context.scene.collection.objects.link(obj)
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.fbx(filepath=os.path.join(MODELS, mesh.name + ".fbx"), use_selection=True, axis_forward="X", axis_up="Z",
                         apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE", add_leaf_bones=False, bake_space_transform=True)
print(f"Berthed: {TAG} {V} {tris}")
