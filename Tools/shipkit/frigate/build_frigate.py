"""Builds the frigate Commonwealth in Blender (docs/shipkit-1 to docs/shipkit-12).

Slice 1 lofted the moulded hull (the frames' outside, as the 1927 lines give it). Slice 2 planks it (skin.py): copper
to the main wale, the wales, black strakes, the ochre port band, the bulwarks to the rail, the gun deck and spar deck
ports with their linings and lids, the rail cap, the plankshear moulding, the channels, the entry steps, the rudder
and its irons, and placeholders for the gun deck and the bulkheads for the later slices. Slice 3 (spars.py, spars_1795.json) masts
her: lower masts, tops, caps, topmasts, topgallant masts, every yard, the spanker boom and gaff, the bowsprit and
jibbooms. Each yard, the boom, the gaff and the spritsail yard is its own object with its origin on the axis it turns
about (local Z up that axis): <out>/rig.json lists how far each one braces and hoists. Slice 4 (rigging.py,
standing_1797.json) sets up the standing rigging: shrouds, deadeyes, lanyards, chains, ratlines, futtock shrouds,
backstays, stays and the bowsprit's shrouds, martingales and guys; then each moving spar is swung against it (and the
masts and hull) to find how far it braces, hoisted, lowered and between (brace_limits). Slice 5 (sails.py,
sails_1797.json) bends on the sails, each set, clewed up (or hauled down) and furled, a collection per state, and
checks them against the ship (sail_room): each state clear of the spars and rigging, the set sails clear of each
other, and how far each yard braces before its sail meets the rigging. Slice 6 (running.py, running_1797.json) reeves
the running rigging: every lift, halyard, tye, brace, sheet, tack, clew garnet, clewline and buntline of the square
sails, the fore-and-aft sails' sheets, the spanker's and the spritsail yard's gear, the footropes and stirrups, with their
blocks (each hung along the pull of its ropes), bull's eyes, thimbles and the sheaves in the side, belayed to pins in
the pin and fife rails or to kevels; a collection per sail state like the sails, checked against the ship, the sails
and each other (running_room). The bull's eyes' places and the pins given out are kept in running_places_1797.json so a
build starts from them; --place-running places them all afresh (about half an hour) and rewrites that file. Slice 7
(deck.py, deck_1797.json) lays the spar deck before the brace limits, the sails and the ropes, which must clear it: the
planked quarterdeck, gangways and forecastle round the open waist, the waterways, the waist's beams, the breast rails
and ladders, the hatchways and gratings, the companion, the skylights, the capstan's head and the double wheel (each on
its own frame), the binnacle, the belfry, the galley's chimney, the bowsprit's step and the mast coats; then, after the
ropes, the hammock nettings on the rail caps, narrowing wherever something comes near them; deck_room checks every
deck part against the rest of the ship. Slice 8 (guns.py, guns_1797.json) arms her: a long 24-pounder on its truck
carriage at each of the gun deck's 28 ports and a 32-pounder carronade on its slide at each of the spar deck's 22, two
models placed as copies (linked meshes), each gun turned to its port, its gear rigged and its ringbolts fitted to the
side and deck there, the long guns housed for sea, run in and run out and the carronades run out and recoiled, a
collection per pose; gun_room checks every gun against the ship, the others and its own port's lid (how far each lid
swings, how far it must open for its gun to run out and elevate), and each carronade trained across its port. Slice 9
(head.py, stern.py, carve.py, decor_1797.json) decorates her ends, right after the planking so that the ropes and the
deck's checks see them: the head (the knee, the cheeks, the trailboards and their carving, the head rails and timbers,
the gratings and the knightheads, with the bow opened between the knightheads and the bowsprit bedded there), the
figurehead on its console (from make_figure.py's figure_hope.npz), the gammoning and the bobstays (rigging.py, through
the knee), and the stern: the taffrail, the carved frieze, the spar deck's stern ports, the arch, the stern windows
with their sashes and glass, the name, the quarter pieces, the quarter galleries with their lights, roofs and drops,
the cabin light in each side and the quarter lanterns (held clear of the spanker boom swung to its brace limits);
decor_room checks every new part against the rest of the ship and the others, the meetings that are by design listed,
with how deep, in decor_1797.json's meets, and decor_seated that every piece of the carving reaches into what it is
carved on, the open rims of its leaves and berries sunk. Slice 10 (anchors.py, anchors_1797.json) fits her anchors and
cables, also right after the planking: a cathead each side over the rail at the head rail's after end, the bowers (5,300
lb each, built to their weight) catted and fished, the bill of each inner fluke on its billboard, the hawse holes (two a
side through the bow, lined with lead, in an oak bolster; cut through the planking) and the 22 in hemp cables bent to
the bowers' rings and led in through them, with the cat stoppers and the shank painters; the sheet, stream and kedge
anchors are sized here and stowed by the slices that build where they go (the boats; the sheet outside the fore
chains, slice 12). anchors_room checks
every part against the rest of the ship and the others, the meetings by design in anchors_1797.json's meets. Slice 11
(boats.py, boats_1797.json) builds the ship's boats, each a small hull lofted from her own lines and fitted out (keel,
stem and sternpost, frames, planking, risings, gunwales, thwarts and knees, breasthook, stern benches, bottom boards,
rowlocks, oars, masts and sails, rudder and tiller, painter): a 34 ft launch (carvel), two 26 ft cutters and a 22 ft gig
(clinker). They are stowed after the deck, over the open waist on its beams, before the ropes, which must clear them:
the launch amidships and a cutter either side, each on two cradles across her own two spare spars (on saddles on the
beams), the gig nested in the starboard cutter, the stream anchor and the large kedge across the launch's gunwales and
the small kedge across the port cutter's, and a gripe over each boat at each cradle, spliced to eyebolts in its ends.
boats_room checks them against the rest of the ship (the sails, running rigging and guns in every state and pose) and
each other, the meetings by design in boats_1797.json's meets; each boat checks her own parts against each other as she
is built, and every piece of them is checked for faces crossing themselves (a rope bent tighter than its radius).
Slice 12 (gundeck.py, gungear.py, gundeck_1797.json) builds the gun deck, right after the anchors (the spar deck is
built with it; its objects come later): the planked deck under the long guns (its 'Planking' and 'Margin' UVs as the
spar deck's), its waterways, the spar deck's beams, ledges and carlings over it on their clamps and hanging knees, the
stanchions, the hatchways with their coamings, gratings, wells and ladders, the gun deck's capstan (its head on its own
frame), the chain and brake pumps, the riding bitts, the galley's stove, the manger and the cable scuttles (the cables
led in from the hawse holes to the bitts), the captain's great cabin aft (the bulkhead and its two doors, each on its
own frame, the state rooms, the after wall with the stern windows opened through it and the transom cut for them, the
window seat, the floor cloth and the furniture) and the horn lanterns (each a light in gundeck.json); and the sheet
anchor, stowed outside abaft the starboard fore channel (anchors.py). After the guns, their own gear (gungear.py): a
tompion and an apron on each housed long gun (copies, in Guns_Housed), each gun's implements hung over it, its shot in a
garland, each lid's lanyards (the rings on the lid, built into it; the lanyards outside lying down the shut lids,
LidLanyards_Shut, or taut to the open ones, LidLanyards_Open, hidden). gundeck_room checks every part against the rest
of the ship and each other, the meetings by design in gundeck_1797.json's meets.

    python build_frigate.py <out dir> [--place-running]
                                             (Blender's Python: pip bpy, or blender -b -P build_frigate.py -- <out>)

Writes <out>/frigate.blend, <out>/frigate.obj (the moulded hull, transom and backbone, for lines_check.py),
<out>/build.json (triangles per object, main dimensions, displacement, the rig's heights, the sails' checks, the
deck's layout and checks, the guns' placing and checks, the head's and stern's layout and checks, the anchors' sizes,
places and checks, the boats' stowage and checks), <out>/rig.json, <out>/sails.json (each sail's objects, parent and
sizes), <out>/running.json (each line's path and stations, each block's pose, in each state; the pins and kevels),
<out>/deck.json (the deck's fittings, the capstan's and wheel's frames, the nettings, the planking pattern),
<out>/guns.json (each gun's frame and pose, its lid, the unique meshes and what moves on each), <out>/anchors.json (each
anchor's size, the bowers' hang, the catheads, the hawse holes, the cables, the stoppers' holes and the painters' eyes)
<out>/boats.json (each boat's frame, cradles and gripes, the gig's nest, the spare spars, the anchors' places, the
gangways' room) and <out>/gundeck.json (the gun deck's layout, the capstan's and the cabin doors' frames, the lanterns'
lights, the gear's places and the lanyards' poses). Units are metres in Unreal's body frame (X forward, Y starboard, Z up), origin on the centreline at
midships on the load waterline. The moulded hull stays in
the .blend as "Hull", hidden from renders: the shape tools measure it. Edit loft.py, skin.py, offsets.json and
specs_1795.json, spars.py and spars_1795.json, rigging.py and standing_1797.json, sails.py and sails_1797.json,
running.py and running_1797.json, deck.py and deck_1797.json, guns.py and guns_1797.json, head.py, stern.py, carve.py
and decor_1797.json (make_figure.py remakes figure_hope.npz from the scan), anchors.py and anchors_1797.json, boats.py
and boats_1797.json, gundeck.py, gungear.py and gundeck_1797.json, never the .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anchors  # noqa: E402
import boats  # noqa: E402
import carve  # noqa: E402
import deck  # noqa: E402
import guns  # noqa: E402
import gundeck  # noqa: E402
import gungear  # noqa: E402
import head  # noqa: E402
import loft  # noqa: E402
import rigging  # noqa: E402
import running  # noqa: E402
import sails  # noqa: E402
import skin  # noqa: E402
import spars  # noqa: E402
import stern  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.unit_settings.system = "METRIC"


def material(name, rgb, rough=0.6):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def make(name, V, F, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def weld(ob, dist=0.0005):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=dist)
    bm.to_mesh(ob.data)
    bm.free()


def smooth(ob, angle=30):
    me = ob.data
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(angle))


L = loft.Lines()
H = loft.Hull(L).build()
parts = loft.mesh(L, H)

# paint as built (1797): a black side with an ochre band along the gun ports and black lids (the chequer of the
# period), copper to the main wale, red inside the bulwarks and ports. Plain colours: textures are the texture loop's
PAINT = {
    "Copper": ((0.62, 0.36, 0.22), 0.35, 1.0),
    "HullBlack": ((0.03, 0.028, 0.026), 0.55, 0.0),
    "HullOchre": ((0.60, 0.44, 0.17), 0.6, 0.0),
    "HullRed": ((0.40, 0.07, 0.045), 0.6, 0.0),
    "Interior": ((0.66, 0.60, 0.50), 0.7, 0.0),
    "Deck": ((0.58, 0.52, 0.42), 0.75, 0.0),
    "Iron": ((0.05, 0.05, 0.05), 0.5, 0.6),
    "Bronze": ((0.55, 0.40, 0.22), 0.35, 1.0),
    "Spar": ((0.50, 0.36, 0.20), 0.5, 0.0),
    # the standing rigging (slice 4): tarred hemp, untarred lanyards, elm deadeyes and hearts, their holes in shadow
    "Tarred": ((0.055, 0.045, 0.035), 0.75, 0.0),
    "Hemp": ((0.35, 0.28, 0.18), 0.85, 0.0),
    "Deadeye": ((0.16, 0.10, 0.055), 0.6, 0.0),
    "Shadow": ((0.008, 0.007, 0.006), 0.9, 0.0),
    # the running rigging (slice 6): elm blocks, lignum vitae sheaves and belaying pins, oak rails and kevels
    "Block": ((0.33, 0.22, 0.12), 0.7, 0.0),
    "Sheave": ((0.13, 0.08, 0.045), 0.5, 0.0),
    "Pin": ((0.17, 0.10, 0.055), 0.45, 0.0),
    "Rail": ((0.40, 0.28, 0.16), 0.7, 0.0),
    # the spar deck (slice 7): unpainted oak (waterways, coamings, gratings, the capstan, the wheel), glass, the
    # hammocks' canvas and their tarred cloth, the compass cards (the planks and the nettings' mesh: deck.py's
    # materials, below)
    "Oak": ((0.30, 0.20, 0.11), 0.7, 0.0),
    "Glass": ((0.05, 0.07, 0.07), 0.05, 0.0),
    "Canvas": ((0.55, 0.50, 0.40), 0.9, 0.0),
    "Tarpaulin": ((0.06, 0.055, 0.05), 0.6, 0.0),
    "CompassCard": ((0.75, 0.72, 0.62), 0.6, 0.0),
    # the guns (slice 8): the carriages, beds and slides red ochre, a shade darker than the bulwarks' red; the barrels
    # blacked (lamp black in oil over the cast iron: a dull black, not bare metal)
    "Carriage": ((0.33, 0.11, 0.055), 0.65, 0.0),
    "Blacking": ((0.035, 0.035, 0.037), 0.55, 0.0),
    # the head and stern (slice 9): the carved work gilt (gold leaf, a warm metal); the figure and the window sashes in
    # a stone white (FigurePaint); the windows' and the lanterns' panes are the spar deck's Glass
    "Gilt": ((0.80, 0.58, 0.24), 0.32, 1.0),
    "FigurePaint": ((0.80, 0.78, 0.72), 0.55, 0.0),
    # the anchors (slice 10): the hawse holes' lead linings, the cables' weathered tarred hemp (lighter than the
    # standing rigging's fresh tar); the anchors' iron is the guns' Blacking, the catheads and bolsters HullBlack (painted
    # with the side), the billboards' and stock's oak Oak
    "Lead": ((0.36, 0.36, 0.37), 0.65, 0.3),
    "Cable": ((0.15, 0.105, 0.065), 0.8, 0.0),
    # the gun deck (slice 12): the great cabin's mahogany, the galley's brick hearth, the lanterns' tin and horn (the horn
    # glows: below), the implements' ash staffs and the sponges' sheepskin, clear glass in the stern windows, the cabin's
    # side lights and the skylights (daylight comes in through it: below), and Dim, the dark down a well
    "Mahogany": ((0.25, 0.10, 0.06), 0.45, 0.0),
    "Brick": ((0.42, 0.20, 0.13), 0.85, 0.0),
    "Tin": ((0.55, 0.55, 0.56), 0.4, 1.0),
    "Horn": ((0.80, 0.55, 0.25), 0.5, 0.0),
    "Ash": ((0.55, 0.45, 0.32), 0.6, 0.0),
    "Fleece": ((0.70, 0.66, 0.58), 0.95, 0.0),
    "ClearGlass": ((0.95, 0.97, 0.96), 0.02, 0.0),
    "Dim": ((0.09, 0.07, 0.05), 0.9, 0.0),
}
DECK_PLANK = (0.42, 0.36, 0.27)       # holystoned pine (Blender's look only: the game draws the deck from the same UVs)
DECK_PITCH = (0.012, 0.010, 0.008)    # the seams
NET_ROPE = (0.30, 0.24, 0.15)
MATS = {}
for name, (rgb, rough, metal) in PAINT.items():
    m = material(name, rgb, rough)
    m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = metal
    MATS[name] = m
_b = MATS["ClearGlass"].node_tree.nodes["Principled BSDF"]
(_b.inputs.get("Transmission Weight") or _b.inputs["Transmission"]).default_value = 1.0
_b.inputs["IOR"].default_value = 1.52
_b = MATS["Horn"].node_tree.nodes["Principled BSDF"]
_b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.3, 1.0)
_b.inputs["Emission Strength"].default_value = 3.0
CLAY = material("Clay_Hull", (0.55, 0.53, 0.5))


def make_painted(name, V, F, M):
    """One object, a material slot per paint used, each face on its paint's slot."""
    names = sorted(set(M))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    for n in names:
        me.materials.append(MATS[n])
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [idx[m] for m in M])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    return ob


def mirrored(V, F, M):
    """A starboard part and its port twin as one mesh (y flipped, faces turned so they still face out)."""
    V = np.asarray(V, float)
    Vp = V * np.array([1.0, -1.0, 1.0])
    n = len(V)
    return np.concatenate([V, Vp]), list(F) + [tuple(n + i for i in f[::-1]) for f in F], list(M) + list(M)


# the moulded hull: both sides and the wing transom's underside as one welded surface. It is the drawing's line and
# what lines_check and the shape tools measure; the planking covers it, so it is hidden from renders
objs = [make(n, *parts[n], CLAY) for n in ("Hull_Stbd", "Hull_Port")]
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
hull = bpy.context.view_layer.objects.active
hull.name = hull.data.name = "Hull"
weld(hull)
smooth(hull)
hull.hide_render = True
hull.hide_set(True)

# the planked ship
# the rig first: the stem head is cut down to the bowsprit's bed
RIG = spars.Rig(L, json.load(open(os.path.join(HERE, "specs_1795.json")))).build()
SK = skin.Skin(L, stem_bed=RIG.stem_bed).build()
SKIN = SK.parts()
# the head and the stern (slice 9, head.py, stern.py and decor_1797.json), built on the skin: the head's knee, cheeks,
# trailboards and their carving, rails, timbers, gratings, the knightheads and the figure; the bow's bulwark cut open
# between the knightheads down to the bowsprit's bed, and the bed made to take the cut (open_bow), before the skin's
# objects are made (and the running rigging's world is this opened skin). The stern's taffrail and
# its carved board, ports, arch, stars, windows, pilasters and the name, the quarter pieces, a quarter gallery and a cabin
# light each side and the quarter lanterns
HD = head.Head(L, RIG, SK).build()
HD.open_bow(SKIN)
SN = stern.Stern(L, RIG, SK).build()
# the anchors (slice 10, anchors.py and anchors_1797.json), on the opened bow: the catheads let into the rail cap, the
# bowers catted and fished on their billboards, the hawse holes in their bolsters (cut through the planking here, before
# the skin's objects are made), the cables, the cat stoppers and the shank painters
AN = anchors.Anchors(L, RIG, SK, HD, SKIN).build()
AN.cut_hawse(SKIN)
# the gun deck (slice 12, gundeck.py and gundeck_1797.json), on the cut skin, under the spar deck (slice 7's deck.py:
# built here so that the gun deck frames it, its objects made further down, before the brace limits): the planked deck,
# its waterways, the spar deck's beams over it, the hatchways, capstan, pumps, bitts, galley, manger, the great cabin
# and the lanterns. It replaces the skin's placeholder deck (the guns stand on its own GunDeck, with the same top), cuts
# the transom for the stern windows and leads the cables in from the hawse holes to the bitts (its waterways stop short
# of the holes' linings). Each lid's two lanyard rings (gungear.py) are built into the starboard lids, before the lids
# are made, so they turn with them
DK = deck.Deck(SK, RIG).build()
GD = gundeck.GunDeck(SK, RIG, DK, SKIN, hawse_x=float(np.asarray(AN.parts()["HawseLining"][0], float)[:, 0].min())).build()
AN.lead_inboard(GD.cable_course(AN))
SKIN.pop("GunDeck")
GG = gungear.GunGear(GD, None)
for name, (rv, rf, rm) in GG.lid_rings().items():
    V, F, M, side = SKIN[name]
    n = len(V)
    SKIN[name] = (np.concatenate([np.asarray(V, float), rv]), list(F) + [tuple(int(i) + n for i in f) for f in rf],
                  list(M) + list(rm), side)

# the transom (moulded, black; slice 9's stern windows and carvings on it), cut for the windows (slice 12)
transom = make("Transom", *GD.holed_transom(*parts["Transom"][:2]), MATS["HullBlack"])
weld(transom)
smooth(transom)
LIDS = []
for name, (V, F, M, side) in SKIN.items():
    if name.startswith("Lid_"):
        LIDS.append(name)
        continue
    if side == "stbd":
        V, F, M = mirrored(V, F, M)
    ob = make_painted(name, V, F, M)
    smooth(ob, 40 if name in ("Backbone", "Rudder") else 30)

# the gun port lids: an object each side, its origin on the hinge axis (through the knuckles) with X along it and Z out
# of the side, so on either side a positive turn about the lid's own X opens it outward. Port lids are the starboard
# ones mirrored; their X points aft so the frame stays right-handed and opens the same way (Y points down on both)
for name in LIDS:
    V, F, M, _ = SKIN[name]
    o, xa, za = SK.lid_frame(name)
    for suffix, sgn in (("S", 1.0), ("P", -1.0)):
        flip = np.array([1.0, sgn, 1.0])
        oo, xx, zz = o * flip, xa * flip * sgn, za * flip
        yy = np.cross(zz, xx)
        R = np.stack([xx, yy, zz], 1)                 # columns: the lid's axes in the ship
        Vw = np.asarray(V, float) * flip
        Vl = (Vw - oo) @ R
        Fs = list(F) if sgn > 0 else [f[::-1] for f in F]
        ob = make_painted(f"{name}_{suffix}", Vl, Fs, M)
        ob.matrix_world = Matrix(((*R[0], oo[0]), (*R[1], oo[1]), (*R[2], oo[2]), (0, 0, 0, 1)))
        smooth(ob, 30)

# the head and the stern (slice 9): each part one object, both sides in it
DECOR = {}
for name, (V, F, M, side) in list(HD.parts().items()) + list(SN.parts().items()):
    assert name not in DECOR and name not in SKIN, name
    if side == "stbd":
        V, F, M = mirrored(V, F, M)
    smooth(make_painted(name, V, F, M), 35)
    DECOR[name] = (np.asarray(V, float), F)

# the anchors and their gear (slice 10): each part one object, both sides in it. Smoothed at 35 deg, so the shank's
# chamfers stay crisp (45 deg) and the 12-sided ring rounds; the ropes and eyebolts (8-sided, as the running rigging's
# ropes) at 50 deg
ANCHOR = {}
for name, (V, F, M, side) in AN.parts().items():
    assert name not in ANCHOR and name not in SKIN and name not in DECOR, name
    if side == "stbd":
        V, F, M = mirrored(V, F, M)
    smooth(make_painted(name, V, F, M), 50 if name in ("Cable", "CatStopper", "ShankPainter", "AnchorEyebolts",
                                                       "SheetPainter", "SheetEyebolts", "SheetLashing") else 35)
    ANCHOR[name] = (np.asarray(V, float), F)

# the masts and yards (slice 3): masts, tops and the bowsprit where they stand; each yard, the spanker boom and gaff on
# its own frame, origin on the axis it turns about
for name, (V, F, M, frame) in RIG.parts().items():
    ob = make_painted(name, V, F, M)
    if frame is not None:
        o, R = frame
        ob.matrix_world = Matrix(((*R[0], o[0]), (*R[1], o[1]), (*R[2], o[2]), (0, 0, 0, 1)))
    smooth(ob, 35)

# the standing rigging (slice 4): built in place, both sides in each object; the bowsprit's gammoning and bobstays
# through the head's knee (slice 9); a chain's plate over a gun port stops above its lid's lanyard hole (slice 12)
ST = rigging.Standing(RIG, SK, holes=GG.holes_out()).build().head_rigging(HD)
for name, (V, F, M, _) in ST.parts().items():
    smooth(make_painted(name, V, F, M), 40)
for name, low in ST.yard_rests().items():          # a royal yard lowered rests on the topgallant rigging's eyes
    RIG.meta[name]["hoist_m"][0] = low

# the spar deck (slice 7, deck.py and deck_1797.json): the planked quarterdeck, gangways and forecastle round the open
# waist, and what stands on them, each where it stands; the capstan's head and the wheel on frames of their own (origin
# on the axis each turns about: deck.json). Built before the brace limits, the sails and the ropes, which must clear it.
# The deck's top carries two UV maps the planks are drawn from: 'Planking' (u, v = x, y in metres) and 'Margin' (the
# waterway's inner edge's half-breadth less |y|, and its slope along x: the nibs); deck.planking_terms is the pattern.
# The hammock nettings go on last, round the running rigging (below)
MATS["DeckPlanks"] = deck.planks_material(bpy, "DeckPlanks", DK.planking(), DECK_PLANK, DECK_PITCH, PAINT["Oak"][0])
MATS["Netting"] = deck.netting_material(bpy, "Netting", NET_ROPE, DK.c["nettings"]["mesh_in"] * loft.FT / 12,
                                        DK.c["nettings"]["cord_in"] * loft.FT / 12)
DECK_UV = {"SparDeck": ("Planking", "Margin"), "Nettings": ("Netting",)}


def make_deck_part(name, V, F, M, frame, uv):
    """a deck part: in place, or on its own frame (the vertices are in it); its UV maps (DECK_UV) from uv's columns"""
    ob = make_painted(name, V, F, M)
    if uv is not None:
        me = ob.data
        vi = np.zeros(len(me.loops), dtype=np.int32)
        me.loops.foreach_get("vertex_index", vi)
        for k, nm in enumerate(DECK_UV[name]):
            lay = me.uv_layers.new(name=nm)
            lay.data.foreach_set("uv", np.ascontiguousarray(np.asarray(uv)[vi][:, 2 * k:2 * k + 2],
                                                            dtype=np.float32).ravel())
    if frame is not None:
        o, R = frame
        ob.matrix_world = Matrix(((*R[0], o[0]), (*R[1], o[1]), (*R[2], o[2]), (0, 0, 0, 1)))
    smooth(ob, 35)
    return ob


DECK_OBJS = []
for name, (V, F, M, frame, uv) in DK.parts().items():
    make_deck_part(name, V, F, M, frame, uv)
    DECK_OBJS.append(name)


def floor_cloth_material(name, dark, light):
    """the great cabin's painted floor cloth: squares of two colours from its 'Cloth' UV (a square a unit)"""
    mt = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mt.use_nodes = True
    N, Lk = mt.node_tree.nodes, mt.node_tree.links
    b = N.get("Principled BSDF")
    uv = N.new("ShaderNodeUVMap")
    uv.uv_map = "Cloth"
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(uv.outputs["UV"], sep.inputs[0])
    fl = []
    for k in (0, 1):
        f = N.new("ShaderNodeMath")
        f.operation = "FLOOR"
        Lk.new(sep.outputs[k], f.inputs[0])
        fl.append(f)
    add = N.new("ShaderNodeMath")
    add.operation = "ADD"
    Lk.new(fl[0].outputs[0], add.inputs[0])
    Lk.new(fl[1].outputs[0], add.inputs[1])
    md = N.new("ShaderNodeMath")
    md.operation = "MODULO"
    Lk.new(add.outputs[0], md.inputs[0])
    md.inputs[1].default_value = 2.0
    ab = N.new("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    Lk.new(md.outputs[0], ab.inputs[0])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    Lk.new(ab.outputs[0], mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*dark, 1.0)
    mix.inputs["B"].default_value = (*light, 1.0)
    Lk.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    return mt


# the gun deck's parts (slice 12, built above): each in place but the capstan's head and the cabin's doors (each on its own
# frame: gundeck.json). The deck's top carries the spar deck's two UV maps ('Planking', 'Margin': its own planks'
# pattern, GD.planking()), the floor cloth a 'Cloth' map (a square a unit). The lanterns' horn glows and casts no shadow,
# so their lights (gundeck.json's, a point light in each in Blender) shine out through it
MATS["GunDeckPlanks"] = deck.planks_material(bpy, "GunDeckPlanks", GD.planking(), DECK_PLANK, DECK_PITCH,
                                             PAINT["Oak"][0])
MATS["FloorCloth"] = floor_cloth_material("FloorCloth", (0.025, 0.024, 0.022), (0.72, 0.70, 0.64))
DECK_UV.update(GD.UV_PARTS)
GUNDECK = {}
for name, (V, F, M, frame, uv) in GD.parts().items():
    assert name not in SKIN and name not in DK.parts() and name not in DECOR and name not in ANCHOR, name
    GUNDECK[name] = make_deck_part(name, V, F, M, frame, uv)
GUNDECK["HornLanterns"].visible_shadow = False
for li in GD.lights:
    ld = bpy.data.lights.new(li["name"], "POINT")
    ld.color = li["colour_rgb"]
    ld.energy = GD.c["lanterns"]["light"]["blender_watts"]
    ld.shadow_soft_size = 0.04
    ld.use_shadow = li["cast_shadows"]
    lo = bpy.data.objects.new(li["name"], ld)
    lo.location = li["pos_m"]
    SC.collection.objects.link(lo)
DECK_STATIC = [(name, *DK.world(name)) for name in DK.parts()]       # for the running rigging's clearances
DECK_STATIC = [(name, V, running.tris_of(F)) for name, V, F in DECK_STATIC]


def smooth_soft(ob, angle, soft):
    """smooth(ob, angle), then each edge between two faces of one of soft's paints sharp only past that paint's angle:
    a rope's or an oar's facets rounded where a boat's planks, frames and fittings keep their edges"""
    smooth(ob, angle)
    me = ob.data
    names = [m.name for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        p = names[f1.material_index]
        if p == names[f2.material_index] and p in soft:
            e.smooth = e.calc_face_angle(0.0) < math.radians(soft[p])
    bm.to_mesh(me)
    bm.free()


# the boats (slice 11, boats.py and boats_1797.json), stowed over the open waist: the spare spars on saddles on the
# waist's beams, the launch amidships and a cutter either side, each on two cradles across her own two spars, the gig
# nested in the starboard cutter on chocks across its thwarts, the stream anchor and the large kedge in the launch and
# the small kedge in the port cutter (their stocks across the gunwales), a gripe over each boat at each cradle. Each
# boat is an object on her own frame (origin at her transom's top aft edge on her middle line, at her base: boats.json);
# the rest are objects in place. Built after the deck (they lie on its beams) and before the brace limits, the sails and
# the ropes, which must clear them
BT = boats.Boats(SK, RIG, DK).build()
BOAT = {}
for name, (V, F, M, frame) in BT.parts().items():
    assert name not in SKIN and name not in DECOR and name not in ANCHOR and name not in DK.parts(), name
    ob = make_painted(name, V, F, M)
    if frame is not None:
        o, R = frame
        ob.matrix_world = Matrix(((*R[0], o[0]), (*R[1], o[1]), (*R[2], o[2]), (0, 0, 0, 1)))
    smooth_soft(ob, 35, {"Hemp": 60, "Spar": 50})
    BOAT[name] = ob
BOAT_STATIC = [(name, V, T) for name, (V, T) in BT.world().items()]


def brace_limits(cfg):
    """How far each yard, the spanker boom and gaff and the spritsail yard braces before it touches the standing
    rigging, a mast, a top or the hull (cfg: standing_1797.json's "brace"). Each part is turned about its axis in
    steps from square, each way, at each hoist (0 lowered, 1 hoisted). A lower yard's truss and a topsail yard's
    parrel let it come forward as it braces (to cfg's ease_max_ft): at each step it is eased forward, an inch at a
    time, until it clears. Its limit at a hoist is the last clear angle less the margin, at most cfg's top. Then the
    ease the part needs at each angle and hoist (the more either side needs, taken a step early) is tried again at
    the angles between the steps, and between the hoists (interpolated, against the smaller of the two limits), and a
    limit is cut back where that ease fails. Returns {part: {"by_hoist": [[hoist, lo, hi], ...], "ease_m": [[deg,
    m], ...] (hoisted), "ease_m_by_hoist": [[hoist, [[deg, m], ...]], ...], "touches": [[hoist, sign, object, deg],
    ...]}}."""
    step, top, margin = cfg["step_deg"], cfg["top_deg"], cfg["margin_deg"]
    e_step = cfg["ease_step_in"] * loft.FT / 12
    still = [o for o in SC.objects if o.type == "MESH" and o.name not in RIG.meta and o.name != "Hull"]
    Vs, Fs, owner = [], [], []
    n0 = 0
    for o in still:
        Mw = np.array(o.matrix_world)
        V = np.array([v.co for v in o.data.vertices]) @ Mw[:3, :3].T + Mw[:3, 3]
        o.data.calc_loop_triangles()
        T = np.array([t.vertices for t in o.data.loop_triangles], int)
        Vs.append(V)
        Fs.append(T + n0)
        owner += [o.name] * len(T)
        n0 += len(V)
    V_all, F_all = np.concatenate(Vs), np.concatenate(Fs)
    still_tree = BVHTree.FromPolygons(V_all.tolist(), F_all.tolist(), all_triangles=True)

    def kind(name):
        for k in ("Topsail", "Topgallant", "Royal", "Spanker", "Spritsail"):
            if k in name:
                return k.lower()
        return "lower"
    out, square = {}, []
    for name, m in RIG.meta.items():
        o = SC.objects[name]
        o.data.calc_loop_triangles()
        T = np.array([t.vertices for t in o.data.loop_triangles], int).tolist()
        Mw = np.array(o.matrix_world)
        Vl = np.array([v.co for v in o.data.vertices]) @ Mw[:3, :3].T          # about the origin, in the ship's axes
        org, ax, fwd = Mw[:3, 3], np.array(m["axis"], float), Mw[:3, 0] / np.linalg.norm(Mw[:3, 0])
        K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        e_max = cfg["ease_max_ft"][kind(name)] * loft.FT

        def touch(o_h, deg, e):
            th = math.radians(deg)
            Rm = np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)
            ov = BVHTree.FromPolygons((Vl @ Rm.T + o_h + fwd * e).tolist(), T, all_triangles=True).overlap(still_tree)
            return ov[0][1] if ov else None
        hs = cfg["hoists"] if m["hoist_m"][0] != 0.0 else [1.0]
        lims, need, touches = {}, [], []
        for h in hs:
            o_h = org + ax * (1.0 - h) * m["hoist_m"][0]
            for sgn in (1, -1):
                a, e, hit = 0.0, 0.0, None
                while a <= top + margin + 1e-9:
                    t = touch(o_h, sgn * a, e)
                    while t is not None and e + e_step <= e_max + 1e-9:
                        e += e_step
                        t = touch(o_h, sgn * a, e)
                    if t is not None:
                        hit = owner[t]
                        if a == 0.0:
                            where = V_all[list(F_all[t])].mean(0) / loft.FT
                            square.append(f"{name} at hoist {h} touches {hit} at {np.round(where, 2).tolist()} ft")
                        break
                    need.append((h, a, e))
                    a += step
                lims[(h, sgn)] = round(min(top, a - step - margin), 1) if hit else top
                if hit:
                    touches.append([h, sgn, hit, round(a, 1)])
        # each hoist's ease (both sides), a step ahead of where it was needed, kept where it grows
        grid = np.arange(0.0, top + step / 2, step)
        tables = {}
        for h in hs:
            e_of = np.array([max([e for hh, a, e in need if hh == h and abs(a - g - step) < 1e-6] + [0.0]) for g in grid])
            e_of = np.maximum.accumulate(e_of)
            tb = [[0.0, 0.0]] + [[float(g), round(float(e), 4)] for k, (g, e) in enumerate(zip(grid, e_of))
                                 if k > 0 and e > e_of[k - 1]]
            if tb[-1][1] > 0.0:
                tb.append([float(top), round(float(e_of[-1]), 4)])
            tables[h] = tb
        if any(tb[-1][1] > 0.0 for tb in tables.values()):
            def ease(deg, h):
                """the ease at |deg| and hoist h: each table's value, interpolated between the two hoists either side"""
                ev = [float(np.interp(abs(deg), [a for a, _ in tables[k]], [e for _, e in tables[k]])) for k in hs]
                return float(np.interp(h, hs, ev))
            # each hoist's limit again at half steps, then between hoists (taking the smaller limit) at quarter
            # hoists: a limit is cut back where the ease fails
            checks = [(h, h, h) for h in hs] + [(h0 + (h1 - h0) * q, h0, h1) for h0, h1 in zip(hs[:-1], hs[1:])
                                               for q in (0.25, 0.5, 0.75)]
            for hc, h0, h1 in checks:
                o_h = org + ax * (1.0 - hc) * m["hoist_m"][0]
                for sgn in (1, -1):
                    lim = min(lims[(h0, sgn)], lims[(h1, sgn)])
                    for a in np.arange(step / 2, lim + margin + 1e-9, step / 2):
                        t = touch(o_h, sgn * a, ease(a, hc))
                        if t is not None:
                            cut = round(max(0.0, a - step / 2 - margin), 1)
                            for hk in {h0, h1}:
                                lims[(hk, sgn)] = min(lims[(hk, sgn)], cut)
                            touches.append([round(hc, 3), sgn, owner[t] + " (eased)", round(float(a), 2)])
                            break
        else:
            tables = {}
        out[name] = {"by_hoist": [[h, -lims[(h, -1)], lims[(h, 1)]] for h in hs],
                     "ease_m": tables.get(hs[-1], []),
                     "ease_m_by_hoist": [[h, tables[h]] for h in hs] if len(hs) > 1 and tables else [],
                     "touches": touches}
    if square:
        raise RuntimeError("touching when square:\n" + "\n".join(square))
    return out


def span_room(end_m=0.3, every_m=0.02):
    """Each free straight run of standing rigging (Standing.spans: a shroud's or stay's leg between its head and its
    deadeye, heart or collar) against everything that isn't rigging: the hull, masts, tops, yards squared and hoisted,
    the bowsprit. Points every_m along it, less end_m at each end (where it is made fast), and the room between the
    rope's surface and the nearest surface; a run whose room goes under zero passes through something."""
    rig_objs = set(ST.meshes)
    Vs, Fs, n0 = [], [], 0
    for o in SC.objects:
        if o.type != "MESH" or o.name in rig_objs or o.name == "Hull":
            continue
        Mw = np.array(o.matrix_world)
        V = np.array([v.co for v in o.data.vertices]) @ Mw[:3, :3].T + Mw[:3, 3]
        o.data.calc_loop_triangles()
        Vs.append(V)
        Fs.append(np.array([t.vertices for t in o.data.loop_triangles], int) + n0)
        n0 += len(V)
    tree = BVHTree.FromPolygons(np.concatenate(Vs).tolist(), np.concatenate(Fs).tolist(), all_triangles=True)
    least, through = [], []
    for name, a, b, r in ST.spans:
        L = float(np.linalg.norm(b - a))
        if L < 2 * end_m + every_m:
            continue
        room = min(tree.find_nearest(a + (b - a) * t)[3] for t in np.arange(end_m, L - end_m, every_m) / L) - r
        least.append((room, name))
        if room < 0:
            through.append([name, round(room / 0.0254, 1)])
    least.sort()
    return {"spans": len(ST.spans), "through": through,
            "closest_in": [[n, round(c / 0.0254, 1)] for c, n in least[:8]]}


SPAN_ROOM = span_room()
BRACE = brace_limits(ST.sp["brace"])
for name, b in BRACE.items():
    hoisted = b["by_hoist"][-1]
    RIG.meta[name]["brace_deg"] = [hoisted[1], hoisted[2]]
    if len(b["by_hoist"]) > 1:
        RIG.meta[name]["brace_deg_by_hoist"] = b["by_hoist"]
    if b["ease_m"]:
        RIG.meta[name]["ease_m"] = b["ease_m"]
    if any(t[-1][1] > 0.0 for _, t in b["ease_m_by_hoist"]):
        RIG.meta[name]["ease_m_by_hoist"] = b["ease_m_by_hoist"]
SN.boom_check()                                     # the quarter lanterns under the spanker boom at its final limits

# the sails (slice 5, sails.py and sails_1797.json), built after the brace limits and the rope's clearance: those
# measure the ship without sails (a square sail goes where its yard goes). Each sail has an object for each state in
# the collection of that name: Sails_Set is shown, Sails_Clewed and Sails_Furled are hidden from the viewport and
# renders, and Sails_Head (a square sail's head rope, robands and earings, the spanker's lacing) shows in every state.
# A square sail's objects are parented to its yard, the spanker's to the gaff, so they brace and hoist with it; the
# headsails' and staysails' stay in the ship's frame. The cloth carries FSailCloth's three UV layers (UV0 to UV2)
SV = sails.Sails(RIG, ST).build()
CANVAS = (0.66, 0.60, 0.48)           # unbleached duck (Blender's look only: in the game the cloth is M_SailCloth's)


def sail_material(name, uv):
    """Canvas for the Blender renders: a darker seam where two cloths overlap, every cloth's width less the seam along
    uv's x (UV0 on a square sail, whose cloths run up and down it; UV2 on a fore-and-aft sail, parallel to its leech),
    and a quarter of the light through it, so a sail against the sun glows and its seams show dark"""
    cv = SV.sp["canvas"]
    pitch = (cv["cloth_in"] - cv["seam_in"]) * loft.FT / 12
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, Lk = m.node_tree.nodes, m.node_tree.links
    bsdf = N["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    uvn = N.new("ShaderNodeUVMap")
    uvn.uv_map = uv
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(uvn.outputs["UV"], sep.inputs[0])
    div = N.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = pitch
    Lk.new(sep.outputs["X"], div.inputs[0])
    fr = N.new("ShaderNodeMath")
    fr.operation = "FRACT"
    Lk.new(div.outputs[0], fr.inputs[0])
    seam = N.new("ShaderNodeMath")
    seam.operation = "LESS_THAN"
    seam.inputs[1].default_value = cv["seam_in"] / (cv["cloth_in"] - cv["seam_in"])
    Lk.new(fr.outputs[0], seam.inputs[0])
    shade = N.new("ShaderNodeMath")
    shade.operation = "MULTIPLY_ADD"                  # 1 - 0.18 on the seam
    shade.inputs[1].default_value = -0.18
    shade.inputs[2].default_value = 1.0
    Lk.new(seam.outputs[0], shade.inputs[0])
    col = N.new("ShaderNodeVectorMath")
    col.operation = "SCALE"
    col.inputs[0].default_value = CANVAS
    Lk.new(shade.outputs[0], col.inputs["Scale"])
    Lk.new(col.outputs["Vector"], bsdf.inputs["Base Color"])
    tr = N.new("ShaderNodeBsdfTranslucent")
    Lk.new(col.outputs["Vector"], tr.inputs["Color"])
    mix = N.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.25
    Lk.new(bsdf.outputs[0], mix.inputs[1])
    Lk.new(tr.outputs[0], mix.inputs[2])
    Lk.new(mix.outputs[0], N["Material Output"].inputs["Surface"])
    return m


MATS[sails.CLOTH] = sail_material(sails.CLOTH, "UV0")
MATS[sails.CLOTH_FA] = sail_material(sails.CLOTH_FA, "UV2")
SAIL_COLS = {}
for state in ("Head",) + sails.STATES:
    SAIL_COLS[state] = bpy.data.collections.new("Sails_" + state)
    SC.collection.children.link(SAIL_COLS[state])
for name, (V, F, M, U, frame, parent, key, state) in SV.objects().items():
    ob = make_painted(name, V, F, M)
    SC.collection.objects.unlink(ob)
    SAIL_COLS[state].objects.link(ob)
    me = ob.data
    vi = np.zeros(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", vi)
    for k in range(3):
        lay = me.uv_layers.new(name=f"UV{k}")
        lay.data.foreach_set("uv", np.ascontiguousarray(U[vi][:, 2 * k:2 * k + 2], dtype=np.float32).ravel())
    if frame is not None:
        o, R = frame
        ob.parent = SC.objects[parent]
        ob.matrix_world = Matrix(((*R[0], o[0]), (*R[1], o[1]), (*R[2], o[2]), (0, 0, 0, 1)))
    smooth(ob, 50)
for state in ("Clewed", "Furled"):
    SAIL_COLS[state].hide_render = True
    bpy.context.view_layer.layer_collection.children[SAIL_COLS[state].name].hide_viewport = True


def world_tris(ob, mats=None):
    """an object's vertices in the ship's frame and its triangles (those on the named materials, if given)"""
    me = ob.data
    Mw = np.array(ob.matrix_world)
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    V = co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
    me.calc_loop_triangles()
    T = np.zeros(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", T)
    T = T.reshape(-1, 3)
    if mats is not None:
        mi = np.zeros(len(me.loop_triangles), dtype=np.int64)
        me.loop_triangles.foreach_get("material_index", mi)
        keep = [i for i, m in enumerate(me.materials) if m.name in mats]
        T = T[np.isin(mi, keep)]
    return V, T


def sail_room(cfg):
    """Every sail object, all of it (cloth, bolt ropes, cringles, robands, reef points, hanks, gaskets, lacing), in
    each state, against the ship: the hull's fittings, masts, tops, yards (squared and hoisted), the standing rigging
    and each stay as its own rope (the Stays object's triangles go to the stay whose straight run they lie on). Nothing
    is excused: a sail must clear its own yard, stay, boom and gaff too (it lies on them, it doesn't pass through
    them). A furled topsail, topgallant or royal is tried with every yard lowered on its cap instead (they are furled
    with the yard down: hoisted, the stay leaving the masthead just above it runs through the bunt); a clewed-up sail
    hangs from its hoisted yard. The headsails, staysails and spanker are tried set on the starboard tack too (their
    Set mirrored about info's starboard_tack_mirror plane). Then the set sails against each other, on either tack, and
    each square sail set on its braced yard: the last angle each way where the sail (with its head) clears the masts,
    tops, hull and standing rigging, less cfg's margin (the other yards brace with it). As brace_limits does for the
    bare yard, the yard is eased forward on its truss or parrel as it braces, from rig.json's ease_m an inch at a time
    up to cfg's ease_max (by kind), at each of cfg's step_deg steps to top_deg; the ease the sail needs (a step early,
    kept where it grows) is its ease_m, and the limit is cut back where that table fails at a quarter degree.
    Returns {"through": {object: {what: triangles}}, "set_sails_meet": [[a, b, triangles]], "brace_contact": {sail:
    {"deg": [lo, hi], "yard_limit_deg": [lo, hi], "meets": [lo's, hi's], "brace_deg": [lo, hi], "ease_m": [[deg,
    m], ...]}}}."""
    hoist = {n: np.array(m["axis"], float) * m["hoist_m"][0] for n, m in RIG.meta.items() if m["hoist_m"][0] != 0.0}
    sail_names = set(SV.objs)
    runs = [(nm, a, b, r) for nm, a, b, r in ST.spans if nm.endswith(" stay")]
    statics = [o for o in SC.objects if o.type == "MESH" and o.name not in sail_names and o.name != "Hull"]

    def owners(o, V, T):
        if o.name != "Stays":
            return [o.name] * len(T)
        C = V[T].mean(1)
        lab, best = np.array(["Stays"] * len(C), dtype=object), np.full(len(C), np.inf)
        for nm, a, b, r in runs:
            d = b - a
            t = np.clip((C - a) @ d / (d @ d), 0.0, 1.0)
            dist = np.linalg.norm(C - (a + t[:, None] * d), axis=1) - r
            m = (dist < 2 * loft.FT / 12) & (dist < best)
            best[m], lab[m] = dist[m], nm
        return list(lab)

    def tree(objs, lowered=False):
        Vs, Ts, owner, n0 = [], [], [], 0
        for o in objs:
            V, T = world_tris(o)
            if lowered and o.name in hoist:
                V = V + hoist[o.name]
            Vs.append(V)
            Ts.append(T + n0)
            owner += owners(o, V, T)
            n0 += len(V)
        return BVHTree.FromPolygons(np.concatenate(Vs).tolist(), np.concatenate(Ts).tolist(), all_triangles=True), owner

    def mirror_of(key):
        mi = SV.info[key].get("starboard_tack_mirror")
        if mi is None:
            return None
        p, n = np.array(mi["point_m"], float), np.array(mi["normal"], float)
        if "frame" in mi:
            o_, R_ = RIG.parts_[mi["frame"]]["frame"]
            p, n = o_ + R_ @ p, R_ @ n
        return p, n / np.linalg.norm(n)

    trees = {False: tree(statics), True: tree(statics, True)}
    through, set_trees = {}, {False: {}, True: {}}            # set sails' BVHs by tack (True: starboard)
    for name, d in SV.objs.items():
        V, T = world_tris(SC.objects[name])
        if not len(T):
            continue
        key, state = d["sail"], d["state"]
        cases = [(name, V, False)]
        if state == "Furled" and d["parent"] in hoist:
            cases = [(name + " (yards lowered)", V + hoist[d["parent"]], True)]
        if state == "Set" and mirror_of(key) is not None:
            p, n = mirror_of(key)
            cases.append((name + " (starboard tack)", V - 2 * ((V - p) @ n)[:, None] * n[None], False))
        for label, Vq, lowered in cases:
            t_s = BVHTree.FromPolygons(Vq.tolist(), T.tolist(), all_triangles=True)
            tr, owner = trees[lowered]
            hits = {}
            for _, j in t_s.overlap(tr):
                hits[owner[j]] = hits.get(owner[j], 0) + 1
            if hits:
                through[label] = hits
            if state == "Set":
                stbd = label.endswith("(starboard tack)")
                set_trees[stbd][key] = t_s
                if mirror_of(key) is None:
                    set_trees[True][key] = t_s
    meet = []
    for stbd, ts in set_trees.items():
        keys = list(ts)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                n = len(ts[a].overlap(ts[b]))
                if n:
                    meet.append([a, b, n, "starboard tack" if stbd else "port tack"])
    # braced: against the masts, tops, bowsprit, hull and standing rigging (the yards, boom and gaff brace too)
    still = [o for o in statics if o.name not in RIG.meta]
    tr_b, owner_b = tree(still)
    step, top, margin, e_step = cfg["step_deg"], cfg["top_deg"], cfg["margin_deg"], cfg["ease_step_m"]
    sq = SV.sp["square"]["sails"]
    contact = {}
    for key, spec in sq.items():
        yn = spec["yard"]
        m = RIG.meta[yn]
        org, ax = np.array(m["origin_m"], float), np.array(m["axis"], float)
        fwd = np.array(SC.objects[yn].matrix_world)[:3, 0]
        fwd /= np.linalg.norm(fwd)
        Vs, Ts, n0 = [], [], 0
        for nm in ("Sail_" + sails.camel(key) + "_Set", "Sail_" + sails.camel(key) + "_Head"):
            V, T = world_tris(SC.objects[nm])
            Vs.append(V - org)
            Ts.append(T + n0)
            n0 += len(V)
        Vl, Tl = np.concatenate(Vs), np.concatenate(Ts).tolist()
        K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        ease_y = np.array(m.get("ease_m", [[0.0, 0.0]]), float)
        kind = next((k.lower() for k in ("Topsail", "Topgallant", "Royal") if k in yn), "lower")
        e_max = max(cfg["ease_max_ft"][kind] * loft.FT, float(ease_y[:, 1].max()))

        def hit_at(a, sgn, e):
            th = math.radians(sgn * a)
            Rm = np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)
            ov = BVHTree.FromPolygons((Vl @ Rm.T + org + fwd * e).tolist(), Tl, all_triangles=True).overlap(tr_b)
            return owner_b[ov[0][1]] if ov else None

        def eased(a, sgn, e0):
            """the least ease from e0 (at least the yard's own), an inch at a time, that clears at a: (ease, what it
            still meets at the most ease)"""
            e = max(e0, float(np.interp(a, ease_y[:, 0], ease_y[:, 1])))
            hit = hit_at(a, sgn, e)
            while hit and e + e_step <= e_max + 1e-9:
                e += e_step
                hit = hit_at(a, sgn, e)
            return e, hit
        need, coarse, what = [], {}, {}
        for sgn in (-1, 1):
            a, e, hit = 0.0, 0.0, None
            while a <= top + margin + 1e-9:
                e, hit = eased(a, sgn, e)
                if hit:
                    break
                need.append((a, e))
                a += step
            coarse[sgn], what[sgn] = (a if hit else None), hit
        # the ease table: each angle's need (the more either side needs) a step early, kept where it grows
        grid = np.arange(0.0, top + step / 2, step)
        e_of = np.maximum.accumulate(np.array([max([e for g2, e in need if abs(g2 - g - step) < 1e-6] +
                                                   [float(np.interp(g, ease_y[:, 0], ease_y[:, 1]))]) for g in grid]))
        tb = [[0.0, 0.0]] + [[float(g), round(float(e), 4)] for k, (g, e) in enumerate(zip(grid, e_of))
                             if k > 0 and e > e_of[k - 1]]
        if tb[-1][1] > 0.0:
            tb.append([float(top), round(float(e_of[-1]), 4)])
        tba = np.array(tb, float)
        deg = []
        for sgn in (-1, 1):
            # every quarter degree with the table, to the last whole degree that cleared (or top): the limit is the
            # last quarter that clears, less the margin
            end = (coarse[sgn] - 0.25) if coarse[sgn] is not None else top + margin
            last = 0.0
            for q in np.arange(0.25, end + 1e-9, 0.25):
                h = hit_at(q, sgn, float(np.interp(q, tba[:, 0], tba[:, 1])))
                if h:
                    what[sgn] = h + " (eased)" if what[sgn] is None or h != what[sgn] else h
                    break
                last = float(q)
            lim = min(top, last - margin) if (coarse[sgn] is not None or last < end - 1e-9) else top
            deg.append(sgn * round(max(0.0, lim), 2))
        contact[key] = {"deg": deg, "yard_limit_deg": m["brace_deg"], "meets": [what[-1], what[1]],
                        "brace_deg": [max(deg[0], m["brace_deg"][0]), min(deg[1], m["brace_deg"][1])],
                        "ease_m": tb if tb[-1][1] > 0.0 else []}
    return {"through": through, "set_sails_meet": meet, "brace_contact": contact}


SAIL_ROOM = sail_room({"step_deg": 1.0, **{k: ST.sp["brace"][k] for k in ("top_deg", "margin_deg", "ease_max_ft")},
                       "ease_step_m": ST.sp["brace"]["ease_step_in"] * loft.FT / 12})

# the running rigging (slice 6, running.py and running_1797.json), solved in each sail state (the yards square, the
# upper yards lowered when furled): each state's ropes and its blocks, bull's eyes, thimbles and side sheaves are
# objects in the collection Running_<State> (Running_Set shown, the others hidden like the sails'); the pin rails,
# pins, kevels, eyebolts and coils never move ("PinRails"). running_room: every rope and block, every bull's eye and
# thimble and its strop, and every coil clear by the build gap of the ship, the sails and the other ropes, except where
# it is made fast or led (the build fails otherwise)
RN = running.Running(RIG, SK, ST, SV, taffrail_z=SN.taffrail_top).gear()
DECOR_STATIC = [(name, V, running.tris_of(F)) for name, (V, F) in list(DECOR.items()) + list(ANCHOR.items())]
RW = running.World(RIG, SK, ST, SV, extra_static=DECK_STATIC + DECOR_STATIC + BOAT_STATIC, skin_parts=SKIN)
RCX = {S: running.Clearance(RW.soup(running.Pose(RIG, S), extra=RN.extras())) for S in running.STATES}
RUN_MISSING = RN.settle(RCX, os.path.join(HERE, "running_places_1797.json"), replace="--place-running" in ARGS)
RN.place_coils(RCX)                                         # each coil hung clear of the rail, the ropes and its neighbours
RN.seat_fairleads(RCX)                                      # each bull's eye and thimble on a strop to what holds it
RUN_GAP = RN.cfg["check"]["build_gap_in"] * loft.FT / 12
RUN_NEAR = (RN.check(RCX, gap=0.012) + RN.check_blocks(RCX, gap=0.012) + RN.check_fittings(RCX, gap=0.012) +
            [("All", w, "coil", d, p_) for w, d, p_ in RN.check_coils(RCX, gap=0.012)])   # within 12 mm, for the record
RUN_AIM = RN.cfg["check"]["gap_in"] * loft.FT / 12
RUN_ROOM = {"gap_in": RN.cfg["check"]["build_gap_in"],
            "lines": [[s_, ln, what, round(float(d), 4)] for s_, ln, what, d, _ in RN.check(RCX, gap=RUN_GAP)],
            "blocks": [[s_, b, what, round(float(d), 4)] for s_, b, what, d, _ in RN.check_blocks(RCX, gap=RUN_GAP)],
            "fittings": [[s_, ln, what, round(float(d), 4)] for s_, ln, what, d, _ in RN.check_fittings(RCX, gap=RUN_GAP)],
            "coils": [[w, round(float(d), 4)] for w, d, _ in RN.check_coils(RCX, gap=RUN_GAP)],
            "aim_gap_in": RN.cfg["check"]["gap_in"],
            "under_aim": [[s_, ln, what, round(float(d), 4)] for s_, ln, what, d, _ in RUN_NEAR if d < RUN_AIM],
            "closest": [[s_, ln, what, round(float(d), 4)] for s_, ln, what, d, _ in sorted(RUN_NEAR, key=lambda b: b[3])[:10]],
            "crossings": RN.crossings(),                    # falls crossing just above a side rail (a foul lead; listed)
            "placement_missing": RUN_MISSING or "placed afresh"}
RUN_COLS = {}
for state in running.STATES:
    RUN_COLS[state] = bpy.data.collections.new("Running_" + state)
    SC.collection.children.link(RUN_COLS[state])
RUN_OBJS = RN.objects()
for name, (V, F, M, state) in RUN_OBJS.items():
    ob = make_painted(name, V, F, M)
    if state is not None:
        SC.collection.objects.unlink(ob)
        RUN_COLS[state].objects.link(ob)
    smooth(ob, 50)
for state in ("Clewed", "Furled"):
    RUN_COLS[state].hide_render = True
    bpy.context.view_layer.layer_collection.children[RUN_COLS[state].name].hide_viewport = True


# the hammock nettings (slice 7): on the rail caps, each run narrowing (or breaking) wherever something comes near it
def netting_obstacles(step_deg=0.5):
    """what the nettings must stand clear of: every running line's path in every state (every 3 cm, its radius), every
    other object's vertices (the blocks, bull's eyes, pins and coils, the standing rigging, the sails in every state,
    the spars), and a moving spar low enough to come near the rails swung between its brace limits. The hull's parts
    (the rail caps they stand on) and the deck's own parts (inboard of the rails: deck_room checks them) are left out"""
    obs = []
    for ln in RN.lines:
        for S, P in ln.path.items():
            P = np.asarray(P, float)
            seg = np.diff(P, axis=0)
            n = np.maximum(1, np.ceil(np.linalg.norm(seg, axis=1) / 0.03).astype(int))
            pts = [P[:1]] + [P[i] + seg[i] * (np.arange(1, n[i] + 1) / n[i])[:, None] for i in range(len(seg))]
            obs.append((np.concatenate(pts), ln.r, ln.name))
    skip = set(SKIN) | {"Hull", "Transom"} | set(DK.parts())
    box = DK.netting_box()
    for o in SC.objects:
        if o.type != "MESH" or o.name in skip or o.name.startswith(("Lid_", "Running_")):
            continue
        V, T = world_tris(o)
        if not len(T):
            continue
        if o.name in RIG.meta:
            if V[:, 2].min() > 9.0:                                # a yard aloft never comes near the rails
                continue
            # its surface every 4 cm (each point's radius grown by the spacing's reach), swung through its brace limits
            P = deck.surface_points(V, T, 0.04)
            lo, hi = RIG.meta[o.name]["brace_deg"]
            obs += [(Q, R + 0.6 * 0.04, lab) for Q, R, lab in
                    deck.swept(P, np.array(o.matrix_world)[:3, 3], RIG.meta[o.name]["axis"], lo, hi, step_deg,
                               o.name + " swung")]
            continue
        # its surface every 2 cm where it passes near the rails (a shroud or lanyard between its vertices too)
        P = deck.surface_points(V, T, 0.02, *box)
        if len(P):
            obs.append((P, 0.6 * 0.02, o.name))
    return obs


DK.nettings(netting_obstacles())
make_deck_part("Nettings", *DK.parts()["Nettings"])


def deck_room():
    """every deck part against everything else in the ship (the sails and running rigging in every state too) and
    against the deck's other parts: the pairs whose surfaces meet, less those that meet by design (deck.MEETS: a
    ladder's foot on the gun deck, a netting on its rail cap, a fitting let into the deck...) as deep as allowed; and
    every fitting standing on the deck's top as it rises along the sheer (deck.room). Ropes, blocks and coils are also
    held clear of the deck by running_room, the sails by sail_room, the standing rigging by span_room and the moving
    spars by brace_limits, each with its own gap; the head's and the stern's parts by decor_room, the boats and their
    stowage by boats_room and the gun deck's parts by gundeck_room (against the deck's parts too, with their own meets)"""
    objs = {}
    for o in SC.objects:
        if o.type != "MESH" or o.name in REFERENCE or o.name in DECOR or o.name in BOAT or o.name in GUNDECK:
            continue
        V, T = world_tris(o)
        if len(T):
            objs[o.name] = (V, T)
    return deck.room(objs, set(DK.parts()), DK.z)


REFERENCE = {"Hull"}           # measured, never drawn
DECK_ROOM = deck_room()

# the guns (slice 8, guns.py and guns_1797.json), after everything they must clear: a long 24-pounder on its truck
# carriage in each gun deck port but the bridle port and a 32-pounder carronade on its slide in each quarterdeck and
# forecastle port but the foremost, with their breechings, tackles, ringbolts and coiled falls. Each kind is one set of
# meshes copied to every port as linked duplicates (the game instances them; guns.json gives each port's frame and how
# the parts stand in each pose), each gun's gear and irons its own: the housed long guns and the run-out carronades are
# shown (collections Guns_Housed and Carronades_RunOut, with Guns: the irons, the slides and the chocks fitted to each
# port's waterway), the other poses hidden (Guns_RunIn, Guns_RunOut, Carronades_Recoil). gun_room checks them against
# the ship and each other
GN = guns.Guns(SK, DK, dict(SKIN, GunDeck=GD.parts()["GunDeck"][:3] + ("both",))).build()
GUN_COLS = {}
for cn in ("Guns", "Guns_Housed", "Guns_RunIn", "Guns_RunOut", "Carronades_RunOut", "Carronades_Recoil"):
    GUN_COLS[cn] = bpy.data.collections.new(cn)
    SC.collection.children.link(GUN_COLS[cn])
GUN_MESHES = {}


def gun_meshes(meshes):
    """a mesh (no object) for each of meshes' parts (guns.GPart), smoothed at 40 deg: the guns' copies share them"""
    for name, part in meshes.items():
        V, F, M, _ = part.arrays()
        used = sorted(set(M))
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
        for n in used:
            me.materials.append(MATS[n])
        me.polygons.foreach_set("material_index", [used.index(m) for m in M])
        me.validate()
        me.shade_smooth()
        if hasattr(me, "set_sharp_from_angle"):
            me.set_sharp_from_angle(angle=math.radians(40))
        GUN_MESHES[name] = me


def gun_copies(instances):
    """an object for each copy (name, mesh, 4x4 in the ship, collection), linked into its collection"""
    for name, mesh, Mx, cn in instances:
        ob = bpy.data.objects.new(name, GUN_MESHES[mesh])
        ob.matrix_world = Matrix([list(map(float, r)) for r in Mx])
        GUN_COLS[cn].objects.link(ob)


gun_meshes(GN.meshes)
gun_copies(GN.instances())
for cn in ("Guns_RunIn", "Guns_RunOut", "Carronades_Recoil"):
    GUN_COLS[cn].hide_render = True
    bpy.context.view_layer.layer_collection.children[cn].hide_viewport = True


def gun_room():
    """the guns against everything else in the ship (the sails and running rigging in every state too) and each
    other, the carronades trained, and how far each lid must open for its gun to run out (guns.Guns.room)"""
    objs, lids = {}, {}
    for o in SC.objects:
        if o.type != "MESH" or o.name in REFERENCE or o.name.startswith(("Gun24_", "Carr32_")):
            continue
        V, T = world_tris(o)
        if len(T):
            objs[o.name] = (V, T)
        if o.name.startswith("Lid_"):
            me = o.data
            co = np.zeros(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            lids[o.name] = (co.reshape(-1, 3), T, np.array(o.matrix_world))
    return GN.room(objs, lids)


GUN_ROOM = gun_room()

# the guns' own gear (slice 12, gungear.py), after the guns' room check finds how far each lid opens: a tompion and an
# apron on each housed long gun (copies of two meshes, in Guns_Housed), the implements hung over each gun from the beams
# (the overhead: the spar deck's underside, the gun deck's beams and the waist's), the shot garlands, and the lids'
# lanyards: the bushes, the parts inside and the cleats (LidLanyards), the parts outside down the shut lids
# (LidLanyards_Shut, in Guns_Housed) and taut to the lids opened as far as each gun needs to run out (LidLanyards_Open, in
# Guns_RunIn and Guns_RunOut, hidden)
OVERHEAD = [GD.world("DeckBeams"), DK.world("SparDeck"), DK.world("WaistFrame")]
OV_V = np.concatenate([np.asarray(V, float) for V, _ in OVERHEAD])
OV_F, _n = [], 0
for V, F in OVERHEAD:
    OV_F += [tuple(int(i) + _n for i in f) for f in F]
    _n += len(V)
GG.build((OV_V, OV_F), gn=GN)
LID_OPEN = {k: v["lid_open_deg"] for k, v in GUN_ROOM["lids"].items() if v.get("lid_open_deg") is not None}
GG.lanyards_open(LID_OPEN)
GEAR = {}
for name, (V, F, M, _, _) in GG.parts().items():
    ob = make_painted(name, V, F, M)
    smooth_soft(ob, 35, {"Hemp": 60})
    GEAR[name] = ob
for name, cns in (("LidLanyards_Shut", ("Guns_Housed",)), ("LidLanyards_Open", ("Guns_RunIn", "Guns_RunOut"))):
    ob = GEAR[name]
    SC.collection.objects.unlink(ob)
    for cn in cns:
        GUN_COLS[cn].objects.link(ob)
gun_meshes(GG.meshes)
GEAR_COPIES = {name for name, _, _, _ in GG.instances()}
gun_copies(GG.instances())
BELOW = set(GUNDECK) | set(GEAR) | GEAR_COPIES          # slice 12's: gundeck_room checks them against the rest


def meets_of(card, path, names=None):
    """{(a, b): (why, depth_in)} from a card's meets' pairs (the parts on one side, those on the other, why, the depth
    allowed); a pair named twice fails the build. With names (the objects there are), a name with * or ? in it is a
    pattern (fnmatch) for every object it matches (the gun deck's card: Lid_*_S, Gun24_*_Barrel), and one matching
    nothing fails the build"""
    import fnmatch

    def expand(A):
        out = []
        for a in A:
            if names is None or not any(ch in a for ch in "*?["):
                out.append(a)
                continue
            hit = fnmatch.filter(names, a)
            if not hit:
                raise SystemExit(f"{path}'s meets pattern {a} matches nothing")
            out += hit
        return out
    meets = {}
    for A, B, why, depth_in in card["meets"]["pairs"]:
        for a in expand(A):
            for b in expand(B):
                if (a, b) in meets or (b, a) in meets:
                    raise SystemExit(f"{path}'s meets name {a} with {b} twice")
                meets[(a, b)] = (why, depth_in)
    return meets


def ship_tris(skip=()):
    """every mesh of the ship as built (the sails, running rigging and guns in every state and pose too) but the
    measured reference (and skip's): {name: (V, T)} in the ship's frame"""
    objs = {}
    for o in SC.objects:
        if o.type != "MESH" or o.name in REFERENCE or o.name in skip:
            continue
        V, T = world_tris(o)
        if len(T):
            objs[o.name] = (V, T)
    return objs


def decor_room():
    """every part of the head and the stern (slice 9) against everything else in the ship (the sails, running rigging,
    guns and anchors in every state and pose too) and each other: the pairs whose surfaces meet, less those that meet by
    design (decor_1797.json's meets: a gallery's back let into the planking, a sash in its casing...) as deep as allowed
    (deck.room, without the deck's standing check). The gun deck's parts and the guns' gear (slice 12) are gundeck_room's
    to check against these"""
    return deck.room(ship_tris(BELOW), set(DECOR), None, meets=meets_of(HD.cfg, "decor_1797.json"))


DECOR_ROOM = decor_room()


def anchors_room():
    """every part of the anchors and their gear (slice 10) against everything else in the ship (the sails, running
    rigging and guns in every state and pose too) and each other: the pairs whose surfaces meet, less those that meet
    by design (anchors_1797.json's meets: the cathead let into the rail cap, a bill on its billboard, the cable bent to
    the ring...) as deep as allowed (deck.room, without the deck's standing check). The gun deck's parts and the guns'
    gear (slice 12) are gundeck_room's to check against these (the cables led in to the bitts)"""
    return deck.room(ship_tris(BELOW), set(ANCHOR), None, meets=meets_of(AN.card, "anchors_1797.json"))


ANCHOR_ROOM = anchors_room()


def anchors_folds():
    """each connected piece of each anchors part against itself: {name: [pairs of its faces that cross, sharing no
    corner, a point on the first]} (a rope bent tighter than its radius, or anything folded back through itself; the
    room check sees only parts against other parts)"""
    out = {}
    for name, (V, F) in ANCHOR.items():
        T = np.asarray(running.tris_of(F), np.int64)
        lab = deck.islands(T, len(V))[T[:, 0]]
        bad = []
        for k in np.unique(lab):
            Tk = T[lab == k]
            tree = BVHTree.FromPolygons(V.tolist(), Tk.tolist(), all_triangles=True)
            bad += [np.round(V[Tk[i]].mean(0), 3).tolist() for i, j in tree.overlap(tree)
                    if i < j and not set(Tk[i].tolist()) & set(Tk[j].tolist())]
        out[name] = {"pairs": len(bad), "at": bad[:5]}
    return out


ANCHOR_FOLDS = anchors_folds()


def boats_room():
    """the boats and their stowage (slice 11) against everything else in the ship (the sails, running rigging and guns
    in every state and pose too) and each other: the pairs whose surfaces meet, less those that meet by design
    (boats_1797.json's stowage meets: a saddle on its beam, a boat on her cradles, a gripe over her...) as deep as
    allowed (deck.room, without the deck's standing check). Each boat's own parts are checked against each other by
    boats.py (build.json boats.checks.inside). The gun deck's parts and the guns' gear (slice 12) are gundeck_room's"""
    return deck.room(ship_tris(BELOW), set(BOAT), None, meets=meets_of(BT.st, "boats_1797.json"))


BOAT_ROOM = boats_room()


def folds(objs):
    """each connected piece of each object against itself: {name: [pairs of its faces that cross, sharing no corner,
    a point on the first]} (a rope bent tighter than its radius, or anything folded back through itself; the room
    checks see only parts against other parts)"""
    out = {}
    for name, (V, T) in objs.items():
        T = np.asarray(T, np.int64)
        lab = deck.islands(T, len(V))[T[:, 0]]
        bad = []
        for k in np.unique(lab):
            Tk = T[lab == k]
            tree = BVHTree.FromPolygons(V.tolist(), Tk.tolist(), all_triangles=True)
            bad += [np.round(V[Tk[i]].mean(0), 3).tolist() for i, j in tree.overlap(tree)
                    if i < j and not set(Tk[i].tolist()) & set(Tk[j].tolist())]
        out[name] = {"pairs": len(bad), "at": bad[:5]}
    return out


BOAT_FOLDS = folds(BT.world())


POSE_GROUPS = (("Guns_Housed", "Guns_RunIn", "Guns_RunOut"), ("Carronades_RunOut", "Carronades_Recoil"))


def apart(a, b):
    """objects a and b are never shown together: each is in one or more of a group's pose collections (the long guns
    housed, run in or run out; the carronades run out or recoiled) and they share none of that group's"""
    ca = {c.name for c in bpy.data.objects[a].users_collection}
    cb = {c.name for c in bpy.data.objects[b].users_collection}
    for g in POSE_GROUPS:
        sa, sb = ca & set(g), cb & set(g)
        if sa and sb and not sa & sb:
            return True
    return False


def gundeck_room():
    """the gun deck's parts and the guns' gear (slice 12) against everything else in the ship (the sails, running
    rigging and guns in every state and pose too) and each other: the pairs whose surfaces meet, less those that meet by
    design (gundeck_1797.json's meets: a beam's end on its clamp, a coaming in its opening, the cable round the bitts,
    a tompion in its gun's bore...) as deep as allowed, and every fitting standing on the gun deck as it rises along the
    sheer (deck.room, with the gun deck's height). A gun deck part against a gun is gun_room's (the guns' own meets,
    with the gun deck in place); the gear against the guns is checked here, but for two things never shown together
    (apart: a housed gun's tompion and the same gun run out)"""
    objs = ship_tris()
    gun_parts = {n for n in objs if n.startswith(("Gun24_", "Carr32_")) and n not in GEAR_COPIES}
    out = deck.room(objs, BELOW, GD.zg, meets=meets_of(GD.c, "gundeck_1797.json", sorted(objs)), flat=("GunDeck",))
    out["meet"] = [m for m in out["meet"] if not ({m[0], m[1]} & set(GUNDECK) and {m[0], m[1]} & gun_parts)
                   and not apart(m[0], m[1])]
    out["by_design"] = [m for m in out["by_design"] if not apart(m[0], m[1])]
    return out


GUNDECK_ROOM = gundeck_room()
GEAR_FOLDS = folds({n: world_tris(o) for n, o in GEAR.items()})
GUNDECK_FOLDS = folds({n: world_tris(o) for n, o in GUNDECK.items()})
DECK_FOLDS = folds({n: world_tris(bpy.data.objects[n]) for n in DECK_OBJS})      # (the spar deck's, slice 7, the same)


def decor_seated():
    """the carving (decor_1797.json's meets' seated) on what it meets by design: every piece of it reaching in, every
    open rim of a leaf or a berry in it (carve.seated)"""
    seat = HD.cfg["meets"]["seated"]
    on = {name: set() for name in seat}
    for A, B, _, _ in HD.cfg["meets"]["pairs"]:
        for name in seat:
            on[name] |= (set(B) if name in A else set()) | (set(A) if name in B else set())
    tris_of = {n: world_tris(SC.objects[n]) for n in set(seat) | set().union(*on.values())}
    return carve.seated({n: tris_of[n] for n in seat}, {n: [tris_of[c] for c in sorted(on[n] - set(seat))] for n in seat})


DECOR_SEATED = decor_seated()

# a sun and sky so a quick look in Blender isn't black (render_set.py brings its own)
SC.world = bpy.data.worlds.new("World")
SC.world.color = (0.6, 0.65, 0.7)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "frigate.blend"))
# the lines check reads the moulded surfaces only: the drawing's lines are the frames' outside, not the planking
loft.write_obj(os.path.join(OUT, "frigate.obj"), {n: parts[n] for n in ("Hull_Stbd", "Hull_Port", "Transom", "Backbone")})


def tris(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def bounds(ob):
    P = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    return P.min(0).round(3).tolist(), P.max(0).round(3).tolist()


def displacement(L):
    """Moulded volume below the load waterline: each section's area (both sides, from the rabbet up to A) plus the
    keel and deadwood below the rabbet (the keel's siding), summed along x at 1 px."""
    k = L.k
    xa, xf = L.wl_ends["A"]
    vol_px = 0.0
    for x in np.arange(xa + 0.5, xf, 1.0):
        zb = L.rabbet_z(x)
        if zb >= 0:
            continue
        sec = L.section(x, "lower")
        zs = np.linspace(zb, 0, 200)
        vol_px += 2 * np.trapezoid(np.maximum(sec(zs), k), zs)
    keel = L.P["keel_bottom_z_px"]
    kx, kz = [p[0] for p in keel], [p[1] for p in keel]
    for x in np.arange(max(kx[0], xa), kx[-1], 1.0):
        zr = min(L.rabbet_z(x), 0.0)
        vol_px += 2 * k * max(0.0, zr - float(np.interp(x, kx, kz)))
    return vol_px / (L.ppf * L.ppf_y ** 2) * loft.FT ** 3     # x across the sheet, half-breadths and heights down it


SAIL_STATE = {n: d["state"] for n, d in SV.objs.items()}
RUN_STATE = {n: d[3] for n, d in RUN_OBJS.items()}
stats = {"objects": {o.name: {"triangles": tris(o), "bounds_m": bounds(o)} for o in SC.objects
                     if o.type == "MESH" and not o.name.startswith(("Gun24_", "Carr32_"))}}
GUN_TRIS = GN.triangles()


def mesh_tris(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


# the tompions and aprons, a pair on each housed long gun (shown with the guns housed)
GEAR_COPY_TRIS = {m: mesh_tris(GUN_MESHES[m]) for m in GG.meshes}
GEAR_COPY_TOTAL = sum(GEAR_COPY_TRIS[m] for _, m, _, _ in GG.instances())
stats["triangles_model"] = sum(v["triangles"] for k, v in stats["objects"].items()
                               if k not in REFERENCE and SAIL_STATE.get(k) not in ("Clewed", "Furled")
                               and RUN_STATE.get(k) not in ("Clewed", "Furled") and k != "LidLanyards_Open") + \
    GUN_TRIS["as_drawn"]["total"] + GEAR_COPY_TOTAL
stats["triangles_model_note"] = ("as drawn, with the sails set: the hidden Clewed and Furled sails and running rigging "
                                 "are in triangles_sails and running.triangles (one state shows at a time); the guns "
                                 "as drawn (housed long guns, run-out carronades: guns.triangles) are counted in, their "
                                 "copies left out of objects, and so are the housed guns' tompions and aprons "
                                 "(gundeck.triangles_copies) and the lids' lanyards shut (LidLanyards_Open, hidden, "
                                 "is not); the gun deck below is in it (gundeck.triangles_below: the game loads it only "
                                 "below)")
tri_state = {s: sum(stats["objects"][n]["triangles"] for n, st_ in SAIL_STATE.items() if st_ == s)
             for s in ("Head",) + sails.STATES}
stats["triangles_sails"] = {"set": tri_state["Set"] + tri_state["Head"], "clewed": tri_state["Clewed"] + tri_state["Head"],
                            "furled": tri_state["Furled"] + tri_state["Head"], "all_states": sum(tri_state.values())}
stats["triangles_reference"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in REFERENCE)
stats["dimensions"] = loft.summary(L, H)
sk_ob = SC.objects["Skin"]
P = np.array([v.co for v in sk_ob.data.vertices])
stats["dimensions"]["extreme_breadth_planked_ft"] = round(float(2 * P[:, 1].max()) / loft.FT, 2)
stats["dimensions"]["extreme_breadth_note"] = "outside the main wales: the moulded 43 ft 5 in plus two 7 in wales (specs_1795.json)"
vol = displacement(L)
stats["displacement"] = {"moulded_volume_m3": round(vol, 1), "seawater_tonnes": round(vol * 1.025, 0),
                         "long_tons": round(vol * 1.025 / 1.016, 0),
                         "note": "moulded (inside the planking); the planking and copper add about 3-4%. Constitution: about 2,200 long tons at 21 ft (designed)"}
stats["rig"] = RIG.summary()
stats["triangles_rig"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in RIG.parts_)
stats["standing"] = ST.summary()
stats["triangles_rigging"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in ST.meshes)
stats["brace"] = BRACE
stats["span_room"] = SPAN_ROOM
area = {g: round(sum(SV.info[k]["area_ft2"] for k in SV.sp["sail_list"][g]), 0) for g in SV.sp["sail_list"] if g != "note"}
stats["sails"] = {"area_ft2": dict(area, total=sum(area.values())), "room": SAIL_ROOM}
run_tri = {s: sum(stats["objects"][n]["triangles"] for n, st_ in RUN_STATE.items() if st_ == s)
           for s in (None,) + running.STATES}
stats["running"] = dict(RN.summary(), room=RUN_ROOM,
                        triangles={"set": run_tri["Set"] + run_tri[None], "clewed": run_tri["Clewed"] + run_tri[None],
                                   "furled": run_tri["Furled"] + run_tri[None], "pin_rails": run_tri[None],
                                   "all_states": sum(run_tri.values()),
                                   "blocks_per_state": {s: sum(stats["objects"][n]["triangles"] for n, st_ in
                                                               RUN_STATE.items() if st_ == s and n.startswith("Blocks_"))
                                                        for s in running.STATES}})
stats["deck"] = dict(DK.info, room=DECK_ROOM, folds={n: v["pairs"] for n, v in DECK_FOLDS.items()},
                     triangles={n: stats["objects"][n]["triangles"] for n in DK.parts()},
                     triangles_total=sum(stats["objects"][n]["triangles"] for n in DK.parts()))
stats["guns"] = dict(GN.info, room=GUN_ROOM, triangles=GUN_TRIS, **GN.rig_stats())
stats["decor"] = {"head": HD.info, "stern": SN.info, "room": DECOR_ROOM, "seated": DECOR_SEATED,
                  "triangles": {n: stats["objects"][n]["triangles"] for n in DECOR},
                  "triangles_total": sum(stats["objects"][n]["triangles"] for n in DECOR)}
stats["anchors"] = dict(AN.info, room=ANCHOR_ROOM, folds={n: v["pairs"] for n, v in ANCHOR_FOLDS.items()},
                        triangles={n: stats["objects"][n]["triangles"] for n in ANCHOR},
                        triangles_total=sum(stats["objects"][n]["triangles"] for n in ANCHOR))
stats["boats"] = dict(BT.info, room=BOAT_ROOM, folds={n: v["pairs"] for n, v in BOAT_FOLDS.items()},
                      triangles={n: stats["objects"][n]["triangles"] for n in BOAT},
                      triangles_total=sum(stats["objects"][n]["triangles"] for n in BOAT))
GD_TRIS = {n: stats["objects"][n]["triangles"] for n in GUNDECK}
GEAR_TRIS = {n: stats["objects"][n]["triangles"] for n in GEAR}
BELOW_TRIS = sum(GD_TRIS.values()) + sum(v for n, v in GEAR_TRIS.items() if not n.startswith("LidLanyards_")) + \
    GEAR_COPY_TOTAL
stats["gundeck"] = dict(GD.info, gear=GG.info, lights=GD.lights, lid_open_deg=LID_OPEN, room=GUNDECK_ROOM,
                        folds={n: v["pairs"] for n, v in list(GUNDECK_FOLDS.items()) + list(GEAR_FOLDS.items())},
                        triangles=dict(GD_TRIS, **GEAR_TRIS), triangles_copies={"each": GEAR_COPY_TRIS,
                                                                               "total": GEAR_COPY_TOTAL},
                        triangles_below=BELOW_TRIS, budget_tris=GD.c["budget_tris"],
                        share_of_budget=round(BELOW_TRIS / GD.c["budget_tris"], 3),
                        triangles_below_note="the gun deck's parts, the implements, garlands, the lanyards' bushes, "
                                             "inside parts and cleats, and the tompions and aprons: what the game loads "
                                             "when below (the lanyards outside go with the lids)")
json.dump(stats, open(os.path.join(OUT, "build.json"), "w"), indent=1, default=str)
SAILS_NOTE = (
    "the sails (docs/shipkit-5): each sail's objects, one per state (Set, Clewed, Furled: show one, hide the others) and "
    "a Head shown in every state (square sails and the spanker). parent: the spar the objects ride on (their origin and "
    "axes are its own: they hoist with it), or null (in the ship's frame). Set is full of wind with the yards square "
    "and the wind aft (square sails) and on the port tack (the others). The starboard tack is the Set mirrored about "
    "info's starboard_tack_mirror plane (point_m, normal; in the ship's frame, or the named frame's): the vertical "
    "plane through the sail's stay, which keeps its luff on the stay (the stays' feet are off the centreline), or the "
    "gaff's for the spanker. Clewed hangs from the yard hoisted; Furled lies on it lowered for a topsail, topgallant or "
    "royal (rig.json's hoist_m[0]: hoisted, its stay runs through the bunt) and where it is for a course. A square "
    "sail's clews belong at the yard below's sheaves (a course's at the ship's side): braced, the Set turned rigidly "
    "with its yard is only near (its clews part from the yard below by up to 28 in at 30 deg), so the game must draw "
    "the foot to the yard below. brace_deg: how far its yard braces with this sail set (rig.json's limit, or less where "
    "the set sail meets the rigging first, less 1 deg); ease_m [[deg, m]] (lower and topsail yards): how far forward its yard's truss or parrel lets it come as it braces with this sail set, used as rig.json's ease_m (the same or more: a sail's head, robands and earings stand a little off the yard). info: each sail's size and corners (metres, the ship's frame "
    "or, for *_local_m, the yard's; clew_cut_local_m is the clew as the sail is cut and the draught draws it)")
BC = SAIL_ROOM["brace_contact"]
json.dump({"note": SAILS_NOTE,
           "sails": {k: {"objects": {d["state"]: n for n, d in SV.objs.items() if d["sail"] == k},
                         "parent": next((d["parent"] for d in SV.objs.values() if d["sail"] == k), None),
                         **({"brace_deg": BC[k]["brace_deg"]} if k in BC else {}),
                         **({"ease_m": BC[k]["ease_m"]} if BC.get(k, {}).get("ease_m") else {}),
                         "info": SV.info[k]} for k in SV.info}},
          open(os.path.join(OUT, "sails.json"), "w"), indent=1)
json.dump({"note": "each moving spar (docs/shipkit-3): origin_m on the axis it turns about (metres, ship frame) and that "
                   "axis (the object's local +Z); parent, the object it rides on; hoist_m, its offset along the axis "
                   "[lowered, hoisted] (negative is down; the model hangs it hoisted); brace_deg, the limits of a turn "
                   "about local +Z (right-handed: positive swings a square yard's starboard arm aft and the spanker "
                   "boom and gaff to port); port_tack_sign, the sign of the turn that trims it for the wind on the "
                   "port side (each yard's lee arm aft, the boom and gaff to leeward). Since slice 4 the limits are the standing "
                   "rigging's: brace_deg is the hoisted part's, brace_deg_by_hoist [hoist, lo, hi] the limits from "
                   "lowered (0) to hoisted (1) (between two, take the smaller); each is the last clear angle less 1 deg. ease_m "
                   "[[deg, m]] (lower and topsail yards, hoisted): as it braces, a yard's truss or parrel lets it come "
                   "forward: move its origin along its own +X by the table's value at |brace| (interpolated), then turn "
                   "it. ease_m_by_hoist [[hoist, [[deg, m]]]] (topsail yards): the same table at each hoist; between two "
                   "hoists, interpolate between their tables' values",
           "parts": RIG.meta}, open(os.path.join(OUT, "rig.json"), "w"), indent=1)
RUN_NOTE = (
    "the running rigging (docs/shipkit-6), in the ship's frame (metres): lines, each with its group (a mast's square "
    "gear, Headsails, Staysails, Spanker, Spritsail), size (circumference, in) and, for each state it is rove in (a "
    "headsail's or staysail's sheet only when the sail is set), its centre line (points) and stations (end: made fast; "
    "sheave: round a block's sheave; thru: through a bull's eye, thimble or a sheave in the side, a bull's eye's or "
    "thimble's with its strop from its rim to the point it is seized to and what holds it; pin or kevel: belayed); "
    "a station's p is in its frame (a spar's own, as rig.json's, or the ship's). blocks: each block's sheaves, length, "
    "how it is held in each state (held: hangs_from a frame and point on pendant_m, or fixed to a frame) and its pose "
    "in each state (centre, crown_to_tail, pin: the block's axes; drawn false: a sheave let into a spar). pins and "
    "kevels: where each fall belays. coils: the coil on each pin or kevel, as fitted (shift_m along the rail, width "
    "the share of its full width, off_rail_m further off the rail where it lies over its neighbour's). The "
    "states are sails.json's: the yards square, the wind aft for the square sails and on the port tack for the others "
    "(their sheets lead to starboard: on the starboard tack mirror a fore-and-aft sail's sheet with its sail, about "
    "sails.json's starboard_tack_mirror plane, to the same pin rail on the other side). Braced, a yard's gear must be "
    "laid again between its stations (the game's drawing code, a later pass): the blocks on a yard go with it, the "
    "others hang along their ropes' pull")
json.dump(dict({"note": RUN_NOTE}, **RN.game_data()), open(os.path.join(OUT, "running.json"), "w"), indent=1)
DECK_NOTE = (
    "the spar deck (docs/shipkit-7), in the ship's frame (metres): frames, the parts that turn (the capstan's head, the "
    "double wheel) with their origin on the axis they turn about and their axes (the object's local axes in the ship; "
    "the vertices are in that frame) and how they turn; layout, where each fitting stands (x of its centre, its inside "
    "size); waist, the open waist's ends and half-width; ladders, each ladder's top and foot; beams_x_m, the waist's "
    "beams; nettings, each rail's netting runs and where they narrow or break and for what; planking, the pattern's "
    "sizes: the material draws the planks from the deck's two UV maps, 'Planking' (x, y) and 'Margin' (the waterway's "
    "inner edge's half-breadth less |y|, and its slope along x), as deck.planking_terms does: planks w wide with one "
    "on the middle line, seams 'seam' wide, butts every Lb beams from x0 (beam pitch bp) shifted by 'stagger' beams "
    "over four strakes, plugs plug_r at every beam, nibbed into the waterway where nib of a plank's width is left. The "
    "nettings' mesh is the 'Netting' UV (along, up; metres) cut in diamonds")
json.dump(dict({"note": DECK_NOTE}, **DK.game_data()), open(os.path.join(OUT, "deck.json"), "w"), indent=1)
GUNS_NOTE = (
    "the guns (docs/shipkit-8), in the ship's frame (metres): meshes, each in its own frame (the barrels, carriages, "
    "quoin, trucks, beds and slides shared: copy them to every gun; each gun's gear and irons its own); for each gun "
    "its port's frame and how its parts stand in each pose: the long 24-pounders housed for sea, run in and run out "
    "(carriage_x_m along the port's X, the barrel on its trunnions at the pose's elevation, the quoin, the trucks, the "
    "gun's gear mesh for the pose; run out, the lid's opening and the elevations it allows), the carronades on their "
    "slides (the fighting bolt's place, train_deg, the bed run out or recoiled along the slide, the barrel on its "
    "loop's bolt). The gear is drawn at rest in each pose (the game moves between them; slice 17 fires the guns, "
    "the flash at pan_in_barrel_m and the muzzle). The housed guns' tompions and aprons and the lids' lanyards are "
    "gundeck.json's (slice 12)")
json.dump(dict({"note": GUNS_NOTE}, **GN.game_data()), open(os.path.join(OUT, "guns.json"), "w"), indent=1)
ANCHORS_NOTE = (
    "the anchors and their gear (docs/shipkit-10), in the ship's frame (metres), starboard (port: negate the y of every "
    "point and direction, and then the bower frame's y axis as well, so the port frame stays right-handed): anchors, "
    "each anchor's weight, where it is stowed (cathead: the bowers; fore_channel: the sheet anchor, abaft the starboard "
    "fore chains, slice 12; boats: the stream anchor and the kedges, built by slice 11) and its sizes as built to that "
    "weight; bower, the best bower catted and fished (the small bower is its "
    "mirror): frame is the anchor's own (origin at the crown, z up the shank, x toward the inner arm, whose bill rests "
    "on the billboard, y along the stock) for moving it, with its ring's top under the cathead and its bill; cathead, "
    "its end and heel; hawse, the holes' mouths on the planking, the bolster's face and the bores' inboard axis; "
    "billboard, cable (the hawse hole it leads through, its length and where it is clinched), stopper (its holes in the "
    "cathead, knotted on top) and painter (its eyebolts), where each lies; sheet, the sheet anchor on the starboard "
    "side (its frame as the bower's, its shank level over the lids under it, its inner bill on its billboard, the lower "
    "end of its stock against the side, its ring lashed to an eyebolt in the fore channel's after end, its painter). "
    "The parts are the objects Cathead, Bower, Billboard, HawseBolster, HawseLining, HawsePlug (the unused holes' "
    "plugs), Cable (led in to the riding bitts on the gun deck), CatStopper, ShankPainter and AnchorEyebolts (the "
    "painters' eyebolts), both sides in each, and SheetAnchor, SheetBillboard, SheetPainter, SheetEyebolts and "
    "SheetLashing, starboard only")
json.dump(dict({"note": ANCHORS_NOTE}, **AN.info), open(os.path.join(OUT, "anchors.json"), "w"), indent=1)
BOATS_NOTE = (
    "the boats and their stowage (docs/shipkit-11), in the ship's frame (metres): boats, each boat's kind, her origin "
    "(her own frame's: x forward from her transom's top aft edge, y to her starboard, z up from her base, the rabbet "
    "line amidships; axes the ship's), her keel's bottom, her cradles and gripes; gig, where she lies in the starboard "
    "cutter; spars, each spare spar's boat, kind, size, axis height and its saddles' thickness; anchors, where each "
    "anchor's stock lies across its boat's gunwales and how far it is turned down; gaps, the cutters' places; checks, "
    "the gangways' and ladders' room and each boat's own clash check. The objects: Launch, Cutter_S, Cutter_P, Gig (each "
    "on her own frame), SpareSpars, SparSaddles, BoatCradles, GigChocks, StreamAnchor, KedgeLarge, KedgeSmall, "
    "BoatGripes and GripeEyebolts (in place)")
json.dump(dict({"note": BOATS_NOTE}, **BT.info), open(os.path.join(OUT, "boats.json"), "w"), indent=1, default=str)
GUNDECK_NOTE = (
    "the gun deck (docs/shipkit-12), in the ship's frame (metres): frames, the parts on frames of their own (the "
    "capstan's head GunCapstan, origin on its axis at the deck, z up, turning about it; the great cabin's doors "
    "CabinDoor_S and CabinDoor_P, origin on the hinge at the deck, x across the leaf toward the latch, z up, opening as "
    "cabin_doors says); layout, where each fitting stands (x of its centre, its inside size); lights, the lanterns' "
    "lights (a point light in each lantern's body: colour, kelvin, lumens, radius, unshadowed) within light_budget; "
    "planking, the deck's planks drawn from its 'Planking' and 'Margin' UVs as the spar deck's (deck.json), and the "
    "floor cloth's squares from its 'Cloth' UV (a square a unit); cables, the cables' course on the deck from the "
    "hawse to the bitts; gear, the guns' own gear: the implements over each gun, the shot garlands, the lids' lanyards "
    "(LidLanyards: the bushes, the inside and the cleats, always shown; outside, LidLanyards_Shut with the lids shut "
    "and the guns housed, LidLanyards_Open with them opened lid_open_deg as the guns run in and out: show the one that "
    "goes with the lids; each lid's two rings are built into it and turn with it); copies, each housed gun's tompion "
    "and apron (mesh, 4x4 in the ship's frame; shown with the guns housed, as guns.json's housed pose)")
GD_GAME = dict(GD.info, lights=GD.lights, light_budget=GD.c["lanterns"]["light_budget"], planking=GD.planking(),
               floor_cloth_square_m=GD.c["cabin"]["floor_cloth"]["square_in"] * loft.FT / 12,
               frames={n: {"origin_m": np.round(o, 5).tolist(), "x": np.round(R[:, 0], 6).tolist(),
                           "y": np.round(R[:, 1], 6).tolist(), "z": np.round(R[:, 2], 6).tolist()}
                       for n, (o, R) in GD.frames.items()},
               gear=GG.info, lid_open_deg=LID_OPEN,
               copies=[{"name": n, "mesh": m, "matrix": np.round(np.asarray(Mx, float), 6).tolist(), "collection": cn}
                       for n, m, Mx, cn in GG.instances()])
json.dump(dict({"note": GUNDECK_NOTE}, **GD_GAME), open(os.path.join(OUT, "gundeck.json"), "w"), indent=1,
          default=str)
print(json.dumps(stats, indent=1))
if RUN_ROOM["lines"] or RUN_ROOM["blocks"] or RUN_ROOM["fittings"] or RUN_ROOM["coils"]:
    raise SystemExit("the running rigging fouls the ship, the sails or itself (build.json running.room): " +
                     json.dumps({k: RUN_ROOM[k][:20] for k in ("lines", "blocks", "fittings", "coils")}))
if DECK_ROOM["meet"] or DECK_ROOM["floats"]:
    raise SystemExit("the deck's parts meet the ship or each other, or stand off the deck (build.json deck.room): " +
                     json.dumps({"meet": DECK_ROOM["meet"][:30], "floats": DECK_ROOM["floats"][:30]}))
CLOSE = [[n["rail"], n["side"], n["least_clear_in"], n["closest"]] for n in DK.info["nettings"]
         if n["least_clear_in"] is not None and n["least_clear_in"] < 0.98]
if CLOSE:
    raise SystemExit("something comes within 1 in of a netting as built (build.json deck.nettings): " + json.dumps(CLOSE))
BAD_LIDS = {k: v for k, v in GUN_ROOM["lids"].items() if v.get("lid_max_deg") is None or v.get("lid_open_deg") is None
            or not v.get("run_out_elevation_deg")
            or (v.get("meets_past_it") and v["meets_past_it"][1] in ANCHOR)}      # no lid's swing stopped by an anchor
if GUN_ROOM["local"]["meet"] or GUN_ROOM["ship"] or GUN_ROOM["elevated"] or GUN_ROOM["guns"] or GUN_ROOM["train"] or \
        BAD_LIDS:
    raise SystemExit("the guns meet the ship, each other or themselves (build.json guns.room): " +
                     json.dumps({k: GUN_ROOM[k][:30] for k in ("ship", "elevated", "guns", "train")} |
                                {"local": GUN_ROOM["local"]["meet"][:30], "lids": BAD_LIDS}, default=str))
OFF_DECK = {k: {kk: vv for kk, vv in v.items() if kk != "by_gun"} for k, v in GN.info["coils_on_deck"].items()
            if v["least_in"] < -0.08 or v["most_in"] > 0.08}
if OFF_DECK:
    raise SystemExit("a coil lies more than 0.08 in off its gun's deck (build.json guns.coils_on_deck): " +
                     json.dumps(OFF_DECK))
# a breeching is one rope: as drawn, as long in every pose (its hanging legs take up what its middle gives)
STRETCHED = {f"{kind} {gid}": {p: v["length_in"] for p, v in by_pose.items()}
             for kind, by_gun in stats["guns"]["breeching_in"].items() for gid, by_pose in by_gun.items()
             if max(v["length_in"] for v in by_pose.values()) - min(v["length_in"] for v in by_pose.values()) > 0.3}
if STRETCHED:
    raise SystemExit("a breeching is drawn more than 0.3 in longer in one pose than another (build.json "
                     "guns.breeching_in): " + json.dumps(STRETCHED))
if DECOR_ROOM["meet"]:
    raise SystemExit("the head's or the stern's parts meet the ship or each other (build.json decor.room): " +
                     json.dumps(DECOR_ROOM["meet"][:30]))
if ANCHOR_ROOM["meet"]:
    raise SystemExit("the anchors' parts meet the ship or each other (build.json anchors.room): " +
                     json.dumps(ANCHOR_ROOM["meet"][:30]))


def unmet(card, by_design):
    """the whys of a card's meets pairs whose parts no longer meet (by_design: a room check's pairs that meet by
    design): a part meant to rest on, be let into or driven into another that no longer reaches it hangs clear of what
    holds it. A pattern (Lid_*_S) stands for every part it matches"""
    import fnmatch

    def hit(n, A):
        return any(fnmatch.fnmatchcase(n, a) for a in A)
    return [why for A, B, why, _ in card["meets"]["pairs"]
            if not any((hit(m[0], A) and hit(m[1], B)) or (hit(m[1], A) and hit(m[0], B)) for m in by_design)]


ANCHOR_UNMET = unmet(AN.card, ANCHOR_ROOM["by_design"])
if ANCHOR_UNMET:
    raise SystemExit("a designed contact of the anchors' parts no longer meets: a part hangs clear of what holds it "
                     "(anchors_1797.json meets, build.json anchors.room): " + json.dumps(ANCHOR_UNMET))
FOLDED = {n: v for n, v in ANCHOR_FOLDS.items() if v["pairs"]}
if FOLDED:
    raise SystemExit("an anchors part crosses itself (build.json anchors.folds): " + json.dumps(FOLDED))
if BOAT_ROOM["meet"]:
    raise SystemExit("the boats or their stowage meet the ship or each other (build.json boats.room): " +
                     json.dumps(BOAT_ROOM["meet"][:30]))
BOAT_FOLDED = {n: v for n, v in BOAT_FOLDS.items() if v["pairs"]}
if BOAT_FOLDED:
    raise SystemExit("a boat or a part of their stowage crosses itself (build.json boats.folds): " +
                     json.dumps(BOAT_FOLDED))
if GUNDECK_ROOM["meet"] or GUNDECK_ROOM["floats"]:
    raise SystemExit("the gun deck's parts or the guns' gear meet the ship or each other, or stand off the deck "
                     "(build.json gundeck.room): " +
                     json.dumps({"meet": GUNDECK_ROOM["meet"][:30], "floats": GUNDECK_ROOM["floats"][:30]}))
GUNDECK_UNMET = unmet(GD.c, GUNDECK_ROOM["by_design"])
if GUNDECK_UNMET:
    raise SystemExit("a designed contact of the gun deck's parts no longer meets: a part hangs clear of what holds it "
                     "(gundeck_1797.json meets, build.json gundeck.room): " + json.dumps(GUNDECK_UNMET))
GEAR_FOLDED = {n: v for n, v in list(GEAR_FOLDS.items()) + list(GUNDECK_FOLDS.items()) + list(DECK_FOLDS.items())
               if v["pairs"]}
if GEAR_FOLDED:
    raise SystemExit("a part of either deck or a piece of the guns' gear crosses itself (build.json gundeck.folds, "
                     "deck.folds): " + json.dumps(GEAR_FOLDED))
if GD.info["layout_close"]:
    raise SystemExit("two of the gun deck's fittings stand closer in plan than 0.15 m (build.json "
                     "gundeck.layout_close): " + json.dumps(GD.info["layout_close"]))
if BT.failures():
    raise SystemExit("the boats fail their own checks (build.json boats.checks): " +
                     json.dumps(BT.failures(), default=str))
if AN.info["cable"]["least_bend_of_diameter"] < AN.card["cable"]["bend_min_of_diameter"] - 0.005:
    raise SystemExit("the cable bends tighter than anchors_1797.json's bend_min_of_diameter outside the clinch "
                     "(build.json anchors.cable.least_bend_of_diameter)")
if "sheet" in AN.info and abs(AN.info["sheet"]["stock_end_over_side_m"] - AN.card["sheet_stow"]["stock_gap_m"]) > 0.005:
    raise SystemExit("the sheet anchor's stock does not bear on the side (build.json anchors.sheet.stock_end_over_side_m, "
                     "against anchors_1797.json's sheet_stow.stock_gap_m)")
UNSEATED = {n: r for n, r in DECOR_SEATED.items() if r["loose"] or r["rims_standing"]}
if UNSEATED:
    raise SystemExit("carving stands off what it is carved on (build.json decor.seated): " + json.dumps(UNSEATED))
if SAIL_ROOM["through"] or SAIL_ROOM["set_sails_meet"]:
    raise SystemExit("sails meet the ship or each other (build.json sails.room): " +
                     json.dumps({"through": SAIL_ROOM["through"], "set_sails_meet": SAIL_ROOM["set_sails_meet"]}))
