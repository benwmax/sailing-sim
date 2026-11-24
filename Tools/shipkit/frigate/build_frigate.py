"""Builds the frigate Commonwealth in Blender (docs/shipkit-1 to docs/shipkit-13).

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
stanchions, the hatchways with their coamings, gratings and ladders (down onto the berth deck), the gun deck's capstan
(its head on its own frame), the chain and brake pumps, the riding bitts, the galley's stove, the manger and the cable
scuttles (the cables led in from the hawse holes over the manger and down the scuttles), the captain's great cabin aft
(the bulkhead and its two doors, each on its own frame, the state rooms, the after wall with the stern windows opened
through it and the transom cut for them, the window seat, the floor cloth and the furniture), the rudder's head up
through the window seat and the iron tiller overhead in the great cabin (one object on its own frame, turning with the
helm), the tiller ropes from the wheel's legs under the quarterdeck round their sheaves to the tiller's end (the parts that
move with the helm each on its own frame, posed every degree) and the horn lanterns (each a light in gundeck.json); and
the sheet anchor, stowed outside abaft the starboard fore channel (anchors.py). After the
guns, their own gear (gungear.py): a tompion and an apron on each housed long gun (copies, in Guns_Housed), each gun's
implements hung over it, its shot in a garland, each lid's lanyards (the rings on the lid, built into it; the bushes and
cleats, LanyardFittings; the rope inside, LidLanyards; the lanyards outside lying down the shut lids, LidLanyards_Shut,
or taut to the open ones, LidLanyards_Open, hidden). gundeck_room checks every part against the rest of the ship and
each other, the meetings by design in gundeck_1797.json's meets; tiller_swing turns the tiller and its ropes hard over
each way against the rest and each other, door_helm the cabin's doors through their swings against them.
Slice 13 (berthdeck.py, berthdeck_1797.json, the stores kit's stores.py) builds the berth deck under the gun deck, with
it (the gun deck's ladders land on its planks and the cables go on down through its scuttles to the tiers): the planked
deck 7 ft 2 in under the gun deck's, its waterways, the side's ceiling, the gun deck's beams, ledges and carlings over
it on their clamp and hanging and lodging knees, the stanchions, the hatchways down to the orlop with their coamings
and ladders (onto the orlop's platforms), what comes down through the gun deck (the capstan's spindle on its step, the riding bitts' posts, the
pumps' tubes, the masts in their wedges, the cable scuttles), the wardroom aft with its state rooms and furniture, the
steerage and the officers' rooms, the crew's deck with their hammocks slung by night (BerthDeck_Hammocks, hidden) and
their messes by day (BerthDeck_Messes: the tables hung at the side, the benches, kids and sea chests), the sick bay
forward with its cots, and the horn lanterns (each a light in berthdeck.json). The hammocks, hooks and the messes' gear
are linked copies of the stores kit's items. Its objects are made after every other check, which see the ship as slice
12 left it; berthdeck_room checks them against the whole ship and each other, the meetings by design in
berthdeck_1797.json's meets.

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
gangways' room), <out>/gundeck.json (the gun deck's layout, the capstan's, the cabin doors' and the tiller's frames, the
tiller ropes' poses by the helm's angle, the lanterns' lights, the gear's places and the lanyards' poses), <out>/berthdeck.json (the berth deck's layout, the lanterns'
lights and zones, the hammocks', hooks' and messes' copies) and <out>/berth_deck.json (the berth deck's hand-over to the
orlop slice: its line, its own beams' stations, the openings and ladders down, what passes through it). Units are metres in Unreal's body frame (X forward, Y
starboard, Z up), origin on the centreline at midships on the load waterline. The moulded hull stays in the .blend as
"Hull", hidden from renders: the shape tools measure it. Edit loft.py, skin.py, offsets.json and
specs_1795.json, spars.py and spars_1795.json, rigging.py and standing_1797.json, sails.py and sails_1797.json,
running.py and running_1797.json, deck.py and deck_1797.json, guns.py and guns_1797.json, head.py, stern.py, carve.py
and decor_1797.json (make_figure.py remakes figure_hope.npz from the scan), anchors.py and anchors_1797.json, boats.py
and boats_1797.json, gundeck.py, gungear.py and gundeck_1797.json, berthdeck.py, berthdeck_1797.json, stores.py and
stores_1797.json, never the .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anchors  # noqa: E402
import berthdeck  # noqa: E402
import boats  # noqa: E402
import carve  # noqa: E402
import deck  # noqa: E402
import guns  # noqa: E402
import gundeck  # noqa: E402
import gungear  # noqa: E402
import orlop  # noqa: E402
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
    "Ceiling": ((0.36, 0.26, 0.15), 0.8, 0.0),          # the hold's ceiling and the orlop's planks (slice 14)
    "OrlopPlanks": ((0.52, 0.43, 0.31), 0.8, 0.0),
    "Deal": ((0.62, 0.52, 0.37), 0.75, 0.0),            # the orlop's partitions, the pump well's and lockers' boards
    "Shingle": ((0.33, 0.31, 0.28), 0.95, 0.0),
    "CaskWood": ((0.40, 0.28, 0.16), 0.75, 0.0),
    "Powder": ((0.30, 0.24, 0.17), 0.8, 0.0),           # the powder barrels' staves (their hoops copper)
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
# the transom for the stern windows and leads the cables in from the hawse holes over the manger and down the cable
# scuttles (its waterways stop short of the holes' linings). Each lid's two lanyard rings (gungear.py) are built into
# the starboard lids, before the lids are made, so they turn with them. It is built over the berth deck (berth: its
# hatchways' ladders go down onto the berth deck's planks with no wells under them, and the cables on down through the
# berth deck's own scuttles to the tiers)
DK = deck.Deck(SK, RIG).build()
GD = gundeck.GunDeck(SK, RIG, DK, SKIN, hawse_x=float(np.asarray(AN.parts()["HawseLining"][0], float)[:, 0].min()),
                     berth=os.path.join(HERE, "berthdeck_1797.json")).build()
# the berth deck (slice 13, berthdeck.py and berthdeck_1797.json) under it: the planked deck, the side's ceiling, the
# gun deck's framing over it, the openings down to the orlop, what comes down through the gun deck, the wardroom, the
# steerage, the officers' rooms, the crew's hammocks and messes, the sick bay and the lanterns. Its objects are made
# after every other check (below), which see the ship as slice 12 left it
BD = berthdeck.BerthDeck(GD)
BD.orlop_levels = orlop.Orlop(SK, RIG, DK, GD).platform_levels()    # its ladders down land on the orlop's platforms
BD = BD.build()
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
# ones mirrored; their X points aft so the frame stays right-handed and opens the same way (Y points down on both).
# LID_FRAMES keeps each lid's frame for guns.json (the game swings the lids about it)
LID_FRAMES = {}
for name in LIDS:
    V, F, M, _ = SKIN[name]
    o, xa, za = SK.lid_frame(name)
    for suffix, sgn in (("S", 1.0), ("P", -1.0)):
        flip = np.array([1.0, sgn, 1.0])
        oo, xx, zz = o * flip, xa * flip * sgn, za * flip
        yy = np.cross(zz, xx)
        R = np.stack([xx, yy, zz], 1)                 # columns: the lid's axes in the ship
        LID_FRAMES[f"{name}_{suffix}"] = {"origin_m": np.round(oo, 5).tolist(),
                                          **{k: np.round(v, 6).tolist() for k, v in (("x", xx), ("y", yy), ("z", zz))}}
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
LANTERN_LIGHTS = []
for li in GD.lights:
    ld = bpy.data.lights.new(li["name"], "POINT")
    ld.color = li["colour_rgb"]
    ld.energy = GD.c["lanterns"]["light"]["blender_watts"]
    ld.shadow_soft_size = 0.04
    ld.use_shadow = li["cast_shadows"]
    lo = bpy.data.objects.new(li["name"], ld)
    lo.location = li["pos_m"]
    SC.collection.objects.link(lo)
    LANTERN_LIGHTS.append(lo)
# the orlop and the hold (slice 14, orlop.py and orlop_1797.json): the berth deck's beams overhead, the orlop's platforms,
# rooms and cable tiers, the hold's ceiling, keelson, mast steps, bulkheads, magazines, ballast and casks; each part in
# place; the light rooms' and the cockpit's lanterns (orlop.json's lights)
OB = orlop.Orlop(SK, RIG, DK, GD, berth=BD.handover()).build()      # under the berth deck as built (its hand-over)
if any(abs(a - b) > 1e-3 for p, q in zip(OB.platform_levels(), BD.orlop_levels) for a, b in zip(p, q)):
    raise SystemExit("the berth deck's ladders land on orlop levels that are not the orlop's as built: " +
                     json.dumps({"orlop": OB.platform_levels(), "berth_deck": BD.orlop_levels}))
ORLOP = {}
for name, (V, F, M, frame, uv) in OB.parts().items():
    if name in bpy.data.objects:            # a clash would be renamed .001 and the card's meets would miss it
        raise SystemExit("an orlop part's name is already taken in the scene: " + name)
    ORLOP[name] = make_deck_part(name, V, F, M, frame, uv)
ORLOP_LIGHTS = []
for li in OB.lights:
    ld = bpy.data.lights.new(li["name"], "POINT")
    ld.color = li["colour_rgb"]
    ld.energy = GD.c["lanterns"]["light"]["blender_watts"]
    ld.shadow_soft_size = 0.04
    ld.use_shadow = li["cast_shadows"]
    lo = bpy.data.objects.new(li["name"], ld)
    lo.location = li["at_m"]
    SC.collection.objects.link(lo)
    ORLOP_LIGHTS.append(lo)
# the game loads each deck below by its collection (slice 13's ask): Orlop (the berth deck's overhead, the platforms and
# their rooms, the ceiling, the lanterns) and Hold (everything under the orlop: orlop_1797.json collections)
HOLD_PARTS = OB.c["collections"]["Hold"]
for cname, members in (("Orlop", [n for n in ORLOP if n not in HOLD_PARTS] + [lo.name for lo in ORLOP_LIGHTS]),
                       ("Hold", [n for n in ORLOP if n in HOLD_PARTS])):
    col = bpy.data.collections.new(cname)
    SC.collection.children.link(col)
    for n in members:
        ob = bpy.data.objects[n]
        col.objects.link(ob)
        SC.collection.objects.unlink(ob)
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
# lanyards: the bushes and cleats (LanyardFittings), the rope inside and the bridle ports' (LidLanyards), the parts
# outside down the shut lids (LidLanyards_Shut, in Guns_Housed) and taut to the lids opened as far as each gun needs to run out (LidLanyards_Open, in
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
# slice 12's own objects in a collection of their own, GunDeck (the parts, the guns' gear but the lid lanyards outside,
# which go with the lids' pose in the guns' pose collections, and the lanterns' lights), for the game to load when below
# (gundeck.json below); the long guns stay in their pose collections, the gear's copies in Guns_Housed
GD_COL = bpy.data.collections.new("GunDeck")
SC.collection.children.link(GD_COL)
for ob in list(GUNDECK.values()) + [GEAR[n] for n in sorted(GEAR) if n not in ("LidLanyards_Shut", "LidLanyards_Open")] \
        + LANTERN_LIGHTS:
    SC.collection.objects.unlink(ob)
    GD_COL.objects.link(ob)
CABIN_ONLY = ("AfterWall", "WindowReveals", "StateRooms", "WindowSeat", "FloorCloth", "CabinFurniture", "Tiller",
              "TillerEye_S", "TillerEye_P", "TillerRun_S", "TillerRun_P", "TillerWrap_S", "TillerWrap_P")


def below_zones():
    """which lights' zones (gundeck.json lights' zone) each object facing into the gun deck is in: slice 12's own (the
    cabin's furniture, walls and floor cloth the great cabin's only, the bulkhead, its doors, the lanterns and the
    deck's planks and framing, which run aft into the cabin, both, the rest the gun deck's), the long guns, and the
    other slices' objects seen from below (the side's inner face, the linings, the spar deck's underside and the waist's
    beams, the masts, the lids, the cables, the stern and side windows and the transom)"""
    both = ["gun_deck", "great_cabin"]
    xb = GD.c["cabin"]["bulkhead_x_m"]
    out = {}
    for n in sorted(GUNDECK) + sorted(GEAR):
        if n in ("LidLanyards_Shut", "LidLanyards_Open"):
            continue
        if n in CABIN_ONLY:
            out[n] = ["great_cabin"]
            continue
        V = world_tris(bpy.data.objects[n])[0]
        out[n] = both if V[:, 0].min() < xb else ["gun_deck"]
    out["Gun24_*"] = ["gun_deck"]
    out["Lid_*"] = ["gun_deck"]
    for names, zones in ((("GunWall", "PortLinings", "SparDeck"), both),
                         (("WaistFrame", "Mast_Fore", "Mast_Main", "Mast_Mizzen", "Cable", "HawseLining", "HawsePlug"),
                          ["gun_deck"]),
                         (("Transom", "SternFrame", "SternGlass", "SternSash", "CabinWindowFrame", "CabinWindowGlass",
                           "CabinWindowSash"), ["great_cabin"])):
        for n in names:
            if n not in bpy.data.objects:
                raise SystemExit(f"below_zones: no object {n}")
            out[n] = zones
    return out


BELOW_ZONES = below_zones()


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
    return deck.room(ship_tris(BELOW | set(ORLOP)), set(DECOR), None, meets=meets_of(HD.cfg, "decor_1797.json"))


DECOR_ROOM = decor_room()


def anchors_room():
    """every part of the anchors and their gear (slice 10) against everything else in the ship (the sails, running
    rigging and guns in every state and pose too) and each other: the pairs whose surfaces meet, less those that meet
    by design (anchors_1797.json's meets: the cathead let into the rail cap, a bill on its billboard, the cable bent to
    the ring...) as deep as allowed (deck.room, without the deck's standing check). The gun deck's parts and the guns'
    gear (slice 12) are gundeck_room's to check against these (the cables led in over the manger and down the cable
    scuttles)"""
    return deck.room(ship_tris(BELOW | set(ORLOP)), set(ANCHOR), None, meets=meets_of(AN.card, "anchors_1797.json"))


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
    return deck.room(ship_tris(BELOW | set(ORLOP)), set(BOAT), None, meets=meets_of(BT.st, "boats_1797.json"))


BOAT_ROOM = boats_room()


def folds(objs):
    """each connected piece of each object against itself: {name: [pairs of its faces that cross, sharing no corner,
    a point on the first]} (a rope bent tighter than its radius, or anything folded back through itself; the room
    checks see only parts against other parts). Corners in the same place (to a tenth of a micron) count as one: a
    turned piece's doubled seam, which the export welds, or a deck's two halves meeting at the middle line, where the
    faces either side touch along the seam without crossing"""
    out = {}
    for name, (V, T) in objs.items():
        T = np.asarray(T, np.int64)
        lab = deck.islands(T, len(V))[T[:, 0]]
        W = np.unique(np.round(np.asarray(V, float) * 1e7).astype(np.int64), axis=0, return_inverse=True)[1].reshape(-1)
        bad = []
        for k in np.unique(lab):
            Tk = T[lab == k]
            tree = BVHTree.FromPolygons(V.tolist(), Tk.tolist(), all_triangles=True)
            bad += [np.round(V[Tk[i]].mean(0), 3).tolist() for i, j in tree.overlap(tree)
                    if i < j and not set(W[Tk[i]].tolist()) & set(W[Tk[j]].tolist())]
        out[name] = {"pairs": len(bad), "at": bad[:5]}
    return out


BOAT_FOLDS = folds(BT.world())


POSE_GROUPS = (("Guns_Housed", "Guns_RunIn", "Guns_RunOut"), ("Carronades_RunOut", "Carronades_Recoil"),
               ("BerthDeck_Hammocks", "BerthDeck_Messes"))


def apart(a, b):
    """objects a and b are never shown together: each is in one or more of a group's pose collections (the long guns
    housed, run in or run out; the carronades run out or recoiled; the berth deck's hammocks slung by night or its
    messes laid by day) and they share none of that group's"""
    ca = {c.name for c in bpy.data.objects[a].users_collection}
    cb = {c.name for c in bpy.data.objects[b].users_collection}
    for g in POSE_GROUPS:
        sa, sb = ca & set(g), cb & set(g)
        if sa and sb and not sa & sb:
            return True
    return False


ROOM_NAMES = {}                                         # the objects each deck's room check saw (unmet's patterns)


def gundeck_room():
    """the gun deck's parts and the guns' gear (slice 12) against everything else in the ship (the sails, running
    rigging and guns in every state and pose too) and each other: the pairs whose surfaces meet, less those that meet by
    design (gundeck_1797.json's meets: a beam's end on its clamp, a coaming in its opening, a ladder in its well,
    a lanyard's cleat let into the side...) as deep as allowed, and every fitting standing on the gun deck as it rises along the
    sheer (deck.room, with the gun deck's height). A gun deck part against a gun is gun_room's (the guns' own meets,
    with the gun deck in place); the gear against the guns is checked here, but for two things never shown together
    (apart: a housed gun's tompion and the same gun run out)"""
    objs = ship_tris(set(ORLOP))           # a pair with an orlop part is orlop_room's
    gun_parts = {n for n in objs if n.startswith(("Gun24_", "Carr32_")) and n not in GEAR_COPIES}
    out = deck.room(objs, BELOW, GD.zg, meets=meets_of(GD.c, "gundeck_1797.json", sorted(objs)), flat=("GunDeck",))
    ROOM_NAMES["gundeck"] = sorted(objs)
    out["meet"] = [m for m in out["meet"] if not ({m[0], m[1]} & set(GUNDECK) and {m[0], m[1]} & gun_parts)
                   and not apart(m[0], m[1])]
    out["by_design"] = [m for m in out["by_design"] if not apart(m[0], m[1])]
    return out


GUNDECK_ROOM = gundeck_room()


def door_swings(step=5.0):
    """each cabin door (gundeck.json cabin_doors) turned on its hinge pins from shut to its open_deg, step by step,
    against everything near its sweep (the deck rising aft and the floor cloth under it, the sill, the jambs, casing and
    hinges, the furniture): the last angle it turns to clear and what it meets past that, and the least gap it keeps
    on the way (from its corners to their faces and theirs to its)"""
    out = {}
    for name, fr in GD.door_frames.items():
        ob = GUNDECK[name]
        V, T = world_tris(ob)
        o, R = GD.frames[name]
        o, ax = np.asarray(o, float), np.asarray(R, float)[:, 2]
        posed, lo, hi = [], None, None
        for k in range(int(round(fr["open_deg"] / step)) + 1):
            th = math.radians(fr["open_sign"] * k * step)
            Rm = np.array(Matrix.Rotation(th, 3, list(ax)))
            P = (V - o) @ Rm.T + o
            posed.append((k * step, P))
            lo = P.min(0) if lo is None else np.minimum(lo, P.min(0))
            hi = P.max(0) if hi is None else np.maximum(hi, P.max(0))
        lo, hi = lo - 0.05, hi + 0.05
        near = {}
        for other in SC.objects:
            if other.type != "MESH" or other.name == name or other.name in REFERENCE:
                continue
            Mw = np.array(other.matrix_world)
            bb = np.array([tuple(c) for c in other.bound_box]) @ Mw[:3, :3].T + Mw[:3, 3]
            if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
                continue
            Vo, To = world_tris(other)
            if not len(To):
                continue
            keep = (Vo[To].min(1) <= hi).all(1) & (Vo[To].max(1) >= lo).all(1)      # each face's box in the sweep's
            if keep.any():
                near[other.name] = (Vo, To[keep])
        trees = {n: BVHTree.FromPolygons(Vo.tolist(), To.tolist(), all_triangles=True) for n, (Vo, To) in near.items()}
        clear_to, meets, least = None, None, 9.0
        for deg, P in posed:
            tree = BVHTree.FromPolygons(P.tolist(), T.tolist(), all_triangles=True)
            hit = sorted(n for n, t in trees.items() if tree.overlap(t))
            if hit:
                meets = [deg, hit]
                break
            clear_to = deg
            for n, t in trees.items():
                for p in P:
                    h = t.find_nearest(p.tolist(), 0.05)
                    if h[0] is not None:
                        least = min(least, h[3])
                Vo, To = near[n]
                for p in Vo[np.unique(To)]:
                    h = tree.find_nearest(p.tolist(), 0.05)
                    if h[0] is not None:
                        least = min(least, h[3])
        out[name] = {"open_deg": fr["open_deg"], "clear_to_deg": clear_to, "meets_past_it": meets,
                     "least_gap_in": round(least / 0.0254, 3), "near": sorted(near)}
    return out


DOOR_SWINGS = door_swings()


def door_helm(step=5.0):
    """each cabin door at every opening it swings through (as door_swings, step by step) against the parts that move with
    the helm at every whole degree each way (HELM; gundeck.door_helm): the doors open aft into the cabin, under the
    tiller's sweep and beside the ropes' runs: the least gap between any door and any of them, and where"""
    doors = {}
    for name, fr in GD.door_frames.items():
        V, T = world_tris(GUNDECK[name])
        o, R = GD.frames[name]
        o, ax = np.asarray(o, float), np.asarray(R, float)[:, 2]
        ps = []
        for k in range(int(round(fr["open_deg"] / step)) + 1):
            c, Rm = gundeck.turned(o, ax, fr["open_sign"] * k * step)
            ps.append((k * step, (V - c) @ Rm.T + c))
        doors[name] = (T, ps)
    hard = int(round(GD.c["tiller"]["hard_over_deg"]))
    return gundeck.door_helm(doors, HELM, [float(d) for d in range(-hard, hard + 1)])


# the parts that move with the helm: the rudder's head and the tiller (one object, Tiller, on its own frame), the tiller
# ropes' eyes on the tiller's end ring, the runs from the after sheaves to them and the rope round those sheaves
# (gundeck.json frames and tiller_ropes poses: the game sets them every degree)
HELM_PARTS = ("Tiller", "TillerEye_S", "TillerEye_P", "TillerRun_S", "TillerRun_P", "TillerWrap_S", "TillerWrap_P")


def helm_bodies():
    """{name: (triangles, posed)} for each part that moves with the helm, posed(deg) its vertices in the ship's frame
    with the helm deg over (whole degrees; positive: the tiller to starboard): the tiller turned about the head's axis
    (its frame's Z), the ropes' parts set on their frames for that degree (gundeck.json tiller_ropes poses), the runs
    stretched along their own X"""
    poses = {p["helm_deg"]: p for p in GD.info["tiller_ropes"]["poses"]}
    out = {}
    for n in HELM_PARTS:
        V, T = world_tris(GUNDECK[n])
        o, R = (np.asarray(v, float) for v in GD.frames[n])
        if n == "Tiller":
            def posed(deg, V=V, o=o, ax=R[:, 2]):
                c, Rm = gundeck.turned(o, ax, deg)
                return (V - c) @ Rm.T + c
        else:
            def posed(deg, L=(V - o) @ R, n=n):
                p = poses[int(round(deg))][n]
                return np.asarray(p["o"], float) + (L * [p.get("scale_x", 1.0), 1.0, 1.0]) @ np.asarray(p["R"], float).T
        out[n] = (T, posed)
    return out


HELM = helm_bodies()


def tiller_swing(step=1.0):
    """the parts that move with the helm (HELM_PARTS) turned together from amidships to hard over each way, step by step,
    against everything near their sweeps but the rudder's blade and its irons (the head stands on the blade's top: the
    same timber, which the game leaves as built) and against each other (gundeck.swing_set): the last angle they all
    turn to clear each way, what meets past that and the least gap kept on the way. Joined (one rope where they meet:
    not checked against each other): each run with its eye, the fixed leads and its wrap, each wrap with the fixed
    leads; of those, each wrap with the leads and its run and each run with its eye must keep meeting at every step (the
    rope never comes apart: joins_most_apart_in). Close by design (checked for a touch only): the eyes with the tiller's
    ring and each other, the runs and the wraps with the sheaves they lie in"""
    n = int(round(GD.c["tiller"]["hard_over_deg"] / step))
    steps = {"to_starboard": [k * step for k in range(n + 1)], "to_port": [-k * step for k in range(n + 1)]}
    lo, hi = None, None
    for degs in steps.values():
        for d in degs:
            for _, f in HELM.values():
                P = f(d)
                lo = P.min(0) if lo is None else np.minimum(lo, P.min(0))
                hi = P.max(0) if hi is None else np.maximum(hi, P.max(0))
    lo, hi = lo - 0.05, hi + 0.05
    near = {}
    for other in SC.objects:
        if other.type != "MESH" or other.name in HELM or other.name in ("Rudder", "RudderIrons") or \
                other.name in REFERENCE:
            continue
        Mw = np.array(other.matrix_world)
        bb = np.array([tuple(c) for c in other.bound_box]) @ Mw[:3, :3].T + Mw[:3, 3]
        if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
            continue
        Vo, To = world_tris(other)
        if len(To):
            near[other.name] = (Vo, To)
    joined = [(f"TillerRun_{s}", f"TillerEye_{s}") for s in "SP"] + \
        [(f"TillerRun_{s}", "TillerRopeLeads") for s in "SP"] + [(f"TillerWrap_{s}", "TillerRopeLeads") for s in "SP"] + \
        [(f"TillerWrap_{s}", f"TillerRun_{s}") for s in "SP"]
    close = [("TillerEye_S", "Tiller"), ("TillerEye_P", "Tiller"), ("TillerEye_S", "TillerEye_P")] + \
        [(f"Tiller{k}_{s}", "TillerSheaves") for k in ("Run", "Wrap") for s in "SP"]
    stay = [p for s in "SP" for p in ((f"TillerWrap_{s}", "TillerRopeLeads"), (f"TillerWrap_{s}", f"TillerRun_{s}"),
                                       (f"TillerRun_{s}", f"TillerEye_{s}"))]
    return gundeck.swing_set(HELM, steps, near, joined, close, stay=stay)


TILLER_SWING = tiller_swing()
DOOR_HELM = door_helm()


def lid_light(along=0.004, across=0.001, perp=0.8, tilts=(15.0, 30.0, 45.0, 60.0)):
    """the shut lids keep the daylight out (gundeck.json port_stops): from inside the ship, rays to points across the
    slit round each shut lid on the side's outside face (from a hundredth of an inch off the lining onto the lid's edge
    by a twentieth, every `across` m; every `along` m round the port), starting perp m in along the side's normal,
    square out and tilted each of `tilts` degrees off it eight ways, against the side (Skin, GunWall, PortLinings), the
    stops and the lids, both sides. A ray that reaches its point without meeting anything is daylight through the slit:
    a leak. Per side and port: the leaks by tilt/heading (none when tight)"""
    names = ["Skin", "GunWall", "PortLinings", "PortStops"] + sorted(o.name for o in SC.objects
                                                                     if o.type == "MESH" and o.name.startswith("Lid_"))
    Vs, Ts, nv = [], [], 0
    for n in names:
        V, T = world_tris(SC.objects[n])
        Vs.append(V)
        Ts.append(T + nv)
        nv += len(V)
    tree = BVHTree.FromPolygons(np.concatenate(Vs).tolist(), np.concatenate(Ts).tolist(), all_triangles=True)
    pr = SK.pr
    pin = pr.pxin
    e, m, tiny = SK.inset, 0.05 * pin, 0.01 * pin
    w = e + m - tiny
    ga, gc = along / 0.0254 * pin, across / 0.0254 * pin
    nx = max(int(round(w / gc)), 1)
    heads = [(0.0, 0.0)] + [(t, h) for t in tilts for h in range(0, 360, 45)]
    rays, leaks, ports = 0, 0, {}
    for k, (a, b, _, _) in enumerate(pr.gun):
        X, Z = [], []
        xs = np.arange(a + tiny, b - tiny + 1e-9, ga)
        for f in np.linspace(0.0, 1.0, nx + 1):
            X += [xs, xs]
            Z += [pr.S(xs) + tiny + f * w, pr.Shd(xs) - tiny - f * w]
        for x0, sg in ((a + tiny, 1.0), (b - tiny, -1.0)):
            for f in np.linspace(0.0, 1.0, nx + 1):
                x = np.array([x0 + sg * f * w])
                zs = np.arange(float(pr.S(x)[0]) + tiny, float(pr.Shd(x)[0]) - tiny + 1e-9, ga)
                X.append(np.full(len(zs), x[0]))
                Z.append(zs)
        P, _ = SK.surf(np.concatenate(X), np.concatenate(Z), True, 0, skin.OUT)
        c = np.array([0.5 * (a + b)])
        _, n0 = SK.surf(c, 0.5 * (pr.S(c) + pr.Shd(c)), True, 0, skin.OUT)
        n0 = n0[0]
        up = np.array([0.0, 0.0, 1.0]) - n0[2] * n0
        up /= np.linalg.norm(up)
        fwd = np.cross(n0, up)
        for sd, fl in (("S", np.array([1.0, 1.0, 1.0])), ("P", np.array([1.0, -1.0, 1.0]))):
            out = {}
            for t, h in heads:
                tr_, hr = math.radians(t), math.radians(h)
                d = (math.cos(tr_) * n0 + math.sin(tr_) * (math.cos(hr) * up + math.sin(hr) * fwd)) * fl
                L = perp / math.cos(tr_)
                n_leak = 0
                for q in P * fl:
                    hit = tree.ray_cast((q - d * L).tolist(), d.tolist(), L + 0.01)
                    if hit[0] is None or hit[3] > L - 1e-4:
                        n_leak += 1
                rays += len(P)
                leaks += n_leak
                if n_leak:
                    out[f"{t:g}/{h}"] = n_leak
            ports[f"Lid_{k + 1:02d}_{sd}"] = out
    return {"rays": rays, "leaks": leaks, "tilts_deg": [0.0] + list(tilts), "headings": 8,
            "leaking": {k: v for k, v in ports.items() if v}}


LID_LIGHT = lid_light()
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

# the berth deck's objects (slice 13, built above with the gun deck), after every other check: its parts in place in a
# collection of their own, BerthDeck (berthdeck.json below), with the hooks under the beams (the hammocks' and the sick
# bay's cots', copies of the stores kit's hook) and the lanterns' lights; the crew's hammocks slung by night
# (BerthDeck_Hammocks, hidden) and their messes laid by day (BerthDeck_Messes: the tables let down, the benches, kids
# and chests; shown), each a linked copy of the stores kit's item (stores.py: berthdeck.json copies, by its mesh's
# name).
# The deck's top carries 'Planking' and 'Margin' UVs as the gun deck's (its own planks' pattern, BD.planking()); the
# lanterns' horn glows and casts no shadow, so their lights shine out through it
MATS["BerthDeckPlanks"] = deck.planks_material(bpy, "BerthDeckPlanks", BD.planking(), DECK_PLANK, DECK_PITCH,
                                               PAINT["Oak"][0])
DECK_UV.update(BD.UV_PARTS)
BERTH_COLS = {}
for cn in ("BerthDeck", "BerthDeck_Hammocks", "BerthDeck_Messes"):
    BERTH_COLS[cn] = bpy.data.collections.new(cn)
    SC.collection.children.link(BERTH_COLS[cn])
BERTHDECK = {}
for name, (V, F, M, frame, uv) in BD.parts().items():
    if name in bpy.data.objects:
        raise SystemExit(f"the berth deck's part {name} is named as an object already made")
    ob = make_deck_part(name, V, F, M, frame, uv)
    SC.collection.objects.unlink(ob)
    BERTH_COLS["BerthDeck"].objects.link(ob)
    BERTHDECK[name] = ob
BERTHDECK["BerthLanterns"].visible_shadow = False
BERTH_MESHES = {}
for name, item in BD.copy_items.items():
    if name in bpy.data.meshes:
        raise SystemExit(f"the berth deck's copied mesh {name} is named as a mesh already made")
    V, F, M, _ = item.merged().arrays()
    ob = make_painted(name, V, F, M)                # smoothed on an object of its own, then shared by every copy
    smooth_soft(ob, 35, {"Hemp": 60, "Canvas": 60})
    BERTH_MESHES[name] = ob.data
    bpy.data.objects.remove(ob)
BERTH_COPIES = {}
for c in BD.copies_:
    if c["name"] in bpy.data.objects or c["name"] in BERTH_COPIES:
        raise SystemExit(f"the berth deck's copy {c['name']} is named as an object already made")
    ob = bpy.data.objects.new(c["name"], BERTH_MESHES[c["item"]])
    ob.matrix_world = Matrix([list(map(float, r)) for r in np.asarray(c["matrix"], float)])
    BERTH_COLS[c["collection"]].objects.link(ob)
    BERTH_COPIES[c["name"]] = ob
BERTH_COLS["BerthDeck_Hammocks"].hide_render = True
bpy.context.view_layer.layer_collection.children["BerthDeck_Hammocks"].hide_viewport = True
BERTH_LIGHTS = []
for li in BD.lights:
    if li["name"] in bpy.data.objects:
        raise SystemExit(f"the berth deck's light {li['name']} is named as an object already made")
    ld = bpy.data.lights.new(li["name"], "POINT")
    ld.color = li["colour_rgb"]
    ld.energy = BD.c["lanterns"]["light"]["blender_watts"]
    ld.shadow_soft_size = 0.04
    ld.use_shadow = li["cast_shadows"]
    lo = bpy.data.objects.new(li["name"], ld)
    lo.location = li["pos_m"]
    BERTH_COLS["BerthDeck"].objects.link(lo)
    BERTH_LIGHTS.append(lo)
BERTH = set(BERTHDECK) | set(BERTH_COPIES)


def berthdeck_room():
    """the berth deck's parts and copies (slice 13) against everything else in the ship (the sails, running rigging
    and guns in every state and pose too) and each other: the pairs whose surfaces meet, less those that meet by design
    (berthdeck_1797.json's meets: a beam's end on its clamp, a partition let into the deck, a hammock on its hooks...)
    as deep as allowed, and every fitting standing on the berth deck as it rises along the sheer (deck.room, with the
    berth deck's height); but for two things never shown together (apart: a hammock slung and a mess laid under it)"""
    objs = ship_tris(set(ORLOP))           # a pair with an orlop part is orlop_room's
    out = deck.room(objs, BERTH, BD.zg, meets=meets_of(BD.c, "berthdeck_1797.json", sorted(objs)), flat=("BerthDeck",))
    ROOM_NAMES["berthdeck"] = sorted(objs)
    out["meet"] = [m for m in out["meet"] if not apart(m[0], m[1])]
    out["by_design"] = [m for m in out["by_design"] if not apart(m[0], m[1])]
    return out


BERTHDECK_ROOM = berthdeck_room()


def orlop_room():
    """the orlop's and the hold's parts (slice 14) against everything else in the ship and each other: the pairs whose
    surfaces meet, less those that meet by design (orlop_1797.json's meets: a beam's end let into the ceiling, a
    partition on the planks, a cask bedded in the shingle...) as deep as allowed. No standing check: the platforms and
    the hold's floors are its own parts (the meets hold what stands on them)"""
    objs = ship_tris()
    return deck.room(objs, set(ORLOP), None, meets=meets_of(OB.c, "orlop_1797.json", sorted(objs)))


ORLOP_ROOM = orlop_room()
ORLOP_FOLDS = folds({n: world_tris(o) for n, o in ORLOP.items()})
# each part, and each copied mesh once (every copy of it is the same mesh), against itself
BERTH_FOLDS = folds(dict({n: world_tris(o) for n, o in BERTHDECK.items()},
                         **{c["item"]: world_tris(BERTH_COPIES[c["name"]]) for c in BD.copies_}))


def copy_kind(name):
    """a berth deck copy's kind as a pattern for all of them (Hammock_017: Hammock_*)"""
    return name.split("_")[0] + "_*"


def berth_zones():
    """which lights' zones (berthdeck.json lights' zone) each object facing into the berth deck is in, by where along
    the ship its faces there lie: the wardroom between its bulkheads, the sick bay between its, the berth deck's own
    zone the rest (the tiller room, the steerage, the officers' rooms, the crew's deck and the bow). The berth deck's
    parts, its copies (each kind together: names ending in * are prefixes) and every other object with a corner inside
    the berth deck's room (over its planks, up to the gun deck planks' underside, inside the ceiling and the clamp: the
    gun deck's underside, the masts, the cables, the gun deck's ladders...)"""
    X = BD.room_x
    spans = {"wardroom": [(X["wardroom_aft"], X["wardroom_fore"])],
             "sick_bay": [(X["sick_bay_aft"], X["sick_bay_fore"])],
             "berth_deck": [(-1e9, X["wardroom_aft"]), (X["wardroom_fore"], X["sick_bay_aft"]),
                            (X["sick_bay_fore"], 1e9)]}
    if {li["zone"] for li in BD.lights} != set(spans):
        raise SystemExit("berth_zones: the lanterns' zones are not the berth deck's three")

    def zones_of(xs):
        return [z for z in ("berth_deck", "wardroom", "sick_bay")
                if any(((xs > a) & (xs < b)).any() for a, b in spans[z])]
    out = {n: zones_of(world_tris(o)[0][:, 0]) for n, o in sorted(BERTHDECK.items())}
    kinds = {}
    for n, o in BERTH_COPIES.items():
        kinds.setdefault(copy_kind(n), []).append(world_tris(o)[0][:, 0])
    for k, xs in sorted(kinds.items()):
        out[k] = zones_of(np.concatenate(xs))
    z_lo = float(np.min(BD.deck_line[:, 1])) - 0.05
    z_hi = float(np.max(GD.deck_line[:, 1]))
    for o in SC.objects:
        if o.type != "MESH" or o.name in REFERENCE or o.name in BERTH:
            continue
        bb = np.array([list(o.matrix_world @ Vector(c)) for c in o.bound_box])
        if bb[:, 2].max() < z_lo or bb[:, 2].min() > z_hi:
            continue
        V = world_tris(o)[0]
        z0, z1 = BD.zg(V[:, 0]), GD.zg(V[:, 0]) - BD.t_gun
        sel = (V[:, 2] > z0 + 0.001) & (V[:, 2] < z1 + 0.001)
        if not sel.any():
            continue
        lim, ok = BD.side_limit(V[sel, 0], V[sel, 2])
        inside = ok & (np.abs(V[sel, 1]) < lim - 0.001)
        if inside.any():
            key = o.name if not o.name.startswith(("Gun24_", "Carr32_")) else o.name.split("_")[0] + "_*"
            out[key] = sorted(set(out.get(key, [])) | set(zones_of(V[sel][inside, 0])),
                              key=["berth_deck", "wardroom", "sick_bay"].index)
    return out


BERTH_ZONES = berth_zones()

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
                     if o.type == "MESH" and not o.name.startswith(("Gun24_", "Carr32_"))
                     and o.name not in BERTH_COPIES}}
GUN_TRIS = GN.triangles()


def mesh_tris(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


# the tompions and aprons, a pair on each housed long gun (shown with the guns housed)
GEAR_COPY_TRIS = {m: mesh_tris(GUN_MESHES[m]) for m in GG.meshes}
GEAR_COPY_TOTAL = sum(GEAR_COPY_TRIS[m] for _, m, _, _ in GG.instances())
# the berth deck's copies (slice 13): the hooks (BerthDeck, always shown), the hammocks slung (BerthDeck_Hammocks, by
# night) and the messes laid (BerthDeck_Messes, by day)
BERTH_COPY_TRIS = {m: mesh_tris(me) for m, me in BERTH_MESHES.items()}
BERTH_COPY_BY_COL = {cn: sum(BERTH_COPY_TRIS[c["item"]] for c in BD.copies_ if c["collection"] == cn)
                     for cn in BERTH_COLS}
stats["triangles_model"] = sum(v["triangles"] for k, v in stats["objects"].items()
                               if k not in REFERENCE and SAIL_STATE.get(k) not in ("Clewed", "Furled")
                               and RUN_STATE.get(k) not in ("Clewed", "Furled") and k != "LidLanyards_Open") + \
    GUN_TRIS["as_drawn"]["total"] + GEAR_COPY_TOTAL + BERTH_COPY_BY_COL["BerthDeck"] + \
    BERTH_COPY_BY_COL["BerthDeck_Messes"]
stats["triangles_model_note"] = ("as drawn, with the sails set: the hidden Clewed and Furled sails and running rigging "
                                 "are in triangles_sails and running.triangles (one state shows at a time); the guns "
                                 "as drawn (housed long guns, run-out carronades: guns.triangles) are counted in, their "
                                 "copies left out of objects, and so are the housed guns' tompions and aprons "
                                 "(gundeck.triangles_copies) and the lids' lanyards shut (LidLanyards_Open, hidden, "
                                 "is not); the gun deck below is in it (gundeck.triangles_below: the game loads it only "
                                 "below), and so is the berth deck under it (berthdeck.triangles_below) with its hooks "
                                 "and its messes laid by day (BerthDeck_Messes, shown; its copies left out of objects "
                                 "like the guns': the hammocks slung by night, BerthDeck_Hammocks, hidden, are not)")
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
                        door_swings=DOOR_SWINGS, tiller_swing=TILLER_SWING, door_helm=DOOR_HELM,
                        lid_light=LID_LIGHT,
                        folds={n: v["pairs"] for n, v in list(GUNDECK_FOLDS.items()) + list(GEAR_FOLDS.items())},
                        triangles=dict(GD_TRIS, **GEAR_TRIS), triangles_copies={"each": GEAR_COPY_TRIS,
                                                                               "total": GEAR_COPY_TOTAL},
                        triangles_below=BELOW_TRIS, budget_tris=GD.c["budget_tris"],
                        share_of_budget=round(BELOW_TRIS / GD.c["budget_tris"], 3),
                        triangles_below_note="the gun deck's parts, the implements, garlands, the lanyards' bushes, "
                                             "inside parts and cleats, and the tompions and aprons: what the game loads "
                                             "when below (the lanyards outside go with the lids)")
OB_TRIS = {n: stats["objects"][n]["triangles"] for n in ORLOP}
stats["orlop"] = dict(OB.info, lights=OB.lights, room=ORLOP_ROOM,
                      folds={n: v["pairs"] for n, v in ORLOP_FOLDS.items()}, triangles=OB_TRIS,
                      triangles_total=sum(OB_TRIS.values()), budget_triangles=OB.c["budget_triangles"],
                      share_of_budget=round(sum(OB_TRIS.values()) / OB.c["budget_triangles"], 3))
BD_TRIS = {n: stats["objects"][n]["triangles"] for n in BERTHDECK}
BERTH_BELOW_TRIS = sum(BD_TRIS.values()) + BERTH_COPY_BY_COL["BerthDeck"] + \
    max(BERTH_COPY_BY_COL["BerthDeck_Hammocks"], BERTH_COPY_BY_COL["BerthDeck_Messes"])
stats["berthdeck"] = dict(BD.info, lights=BD.lights, room=BERTHDECK_ROOM,
                          folds={n: v["pairs"] for n, v in BERTH_FOLDS.items()}, triangles=BD_TRIS,
                          triangles_copies={"each": BERTH_COPY_TRIS, "by_collection": BERTH_COPY_BY_COL,
                                            "copies": {cn: sum(1 for c in BD.copies_ if c["collection"] == cn)
                                                       for cn in BERTH_COLS}},
                          triangles_below=BERTH_BELOW_TRIS, budget_tris=BD.c["budget_tris"],
                          share_of_budget=round(BERTH_BELOW_TRIS / BD.c["budget_tris"], 3),
                          triangles_below_note="the berth deck's parts, the hooks under its beams and the more of its "
                                               "two poses (the hammocks slung by night, the messes laid by day: one "
                                               "shows at a time): what the game loads when below")
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
GUNS_DATA = GN.game_data()
for rec in GUNS_DATA["long24"]["guns"]:
    rec["lid_frame"] = LID_FRAMES[rec["lid"]]
GUNS_DATA["long24"]["lid_frame_note"] = (
    "lid_frame: the lid object's own frame (its origin and axes in the ship), the same for the lid's mesh: origin on "
    "the hinge axis midway between the hinges' knuckles, x along the axis (forward on the starboard side, aft on the "
    "port side, so both frames are right-handed and y points down), z out of the side; a turn of lid_open_deg about +x "
    "opens it. shut_lids: the lids with no gun behind them (the bridle ports), shut always, with their frames")
GUNS_DATA["long24"]["shut_lids"] = {n: {"lid_frame": f} for n, f in sorted(LID_FRAMES.items())
                                    if n not in {rec["lid"] for rec in GUNS_DATA["long24"]["guns"]}}
json.dump(dict({"note": GUNS_NOTE}, **GUNS_DATA), open(os.path.join(OUT, "guns.json"), "w"), indent=1)
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
    "side abaft the fore chains (its frame as the bower's; its shank rising forward from the crown, low over its "
    "billboard under the moulding, to its eye at the fore channel, over the hinges of the lids under it (lids_under); "
    "heel, its lowest point's height over the sea with her heeled heel.deg to starboard; its inner bill on its "
    "billboard, the lower end of its stock against the side, its ring lashed to an eyebolt in the fore channel's after "
    "end (lash_m, the lashing's length between the ring's bar and the eye); painter, from two eyebolts in the waist "
    "rail's cap down to the shank, its legs' angles over the level and each leg's load were it to take her whole "
    "weight, against the rope's breaking strain). "
    "The parts are the objects Cathead, Bower, Billboard, HawseBolster, HawseLining, HawsePlug (the unused holes' "
    "plugs), Cable (led in over the manger and down the cable scuttles on the gun deck), CatStopper, ShankPainter and AnchorEyebolts (the "
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
    "cabin_doors says; the rudder's head and the tiller, Tiller, origin on the head's axis in the tiller's middle plane, "
    "z up the axis, x forward square to it, turning about z with the helm: a positive turn takes the tiller to "
    "starboard, tiller.hard_over_deg each way; the tiller ropes' parts that move with it, TillerEye_S and _P, TillerRun_S "
    "and _P and TillerWrap_S and _P, set for each whole degree of the helm from tiller_ropes.poses as tiller_ropes.moves "
    "says, their frames here the helm amidships); layout, where each fitting stands (x of its centre, its inside "
    "size); lights, the lanterns' "
    "lights (a point light in each lantern's body: its zone, colour, kelvin, lumens, radius and whether it casts "
    "shadows) within light_budget, light_zones_note and lumens_note saying how to light by zone and why so bright; "
    "below, what the game loads when below: the collection GunDeck (objects, its meshes; lights, the lanterns' lights), "
    "the long guns' copies in their pose collections with the lid lanyards that go with each pose, and zones, which "
    "lights' zones each object facing into the gun deck is in (names ending in * are prefixes); "
    "planking, the deck's planks drawn from its 'Planking' and 'Margin' UVs as the spar deck's (deck.json), and the "
    "floor cloth's squares from its 'Cloth' UV (a square a unit); cables, the cables' course on the deck from the "
    "hawse holes over the manger to the cable scuttles; gear, the guns' own gear: the implements over each gun, the shot garlands, the lids' lanyards "
    "(LanyardFittings, the bushes and cleats, and LidLanyards, the rope inside and the bridle ports' lanyards, always "
    "shown; outside, LidLanyards_Shut with the lids shut "
    "and the guns housed, LidLanyards_Open with them opened lid_open_deg as the guns run in and out: show the one that "
    "goes with the lids; each lid's two rings are built into it and turn with it); copies, each housed gun's tompion "
    "and apron (mesh, 4x4 in the ship's frame; shown with the guns housed, as guns.json's housed pose); the rest are "
    "the builder's records of where its parts fell (among them knees_x_m and lodging_knees, the hanging and lodging "
    "knees; capstan_bars, the bars stowed in racks overhead; galley; window_seat; after_wall with its panelling)")
BELOW_GAME = {
    "collection": GD_COL.name,
    "objects": sorted(o.name for o in GD_COL.objects if o.type == "MESH"),
    "lights": sorted(o.name for o in GD_COL.objects if o.type == "LIGHT"),
    "pose_collections": {
        "Guns_Housed": "the long guns housed for sea, the lids shut, with LidLanyards_Shut and the copies' tompions and "
                       "aprons (copies)",
        "Guns_RunIn": "the long guns run in, the lids open lid_open_deg, with LidLanyards_Open",
        "Guns_RunOut": "the long guns run out, the lids open as for Guns_RunIn, with LidLanyards_Open"},
    "irons": "each long gun's irons (Gun24_<side><port>_Irons) are in the collection Guns with the carronades' slides",
    "seen_from_outside": "the waist and the hatchways look down into it from the spar deck, and the open ports and the "
                         "stern and side windows into it from close alongside: the export lane's light copy covers those "
                         "views",
    "zones": BELOW_ZONES}
GD_GAME = dict(GD.info, lights=GD.lights, light_budget=GD.c["lanterns"]["light_budget"], planking=GD.planking(),
               light_zones_note=GD.c["lanterns"]["zones_note"], lumens_note=GD.c["lanterns"]["light"]["lumens_note"],
               below=BELOW_GAME,
               floor_cloth_square_m=GD.c["cabin"]["floor_cloth"]["square_in"] * loft.FT / 12,
               frames={n: {"origin_m": np.round(o, 5).tolist(), "x": np.round(R[:, 0], 6).tolist(),
                           "y": np.round(R[:, 1], 6).tolist(), "z": np.round(R[:, 2], 6).tolist()}
                       for n, (o, R) in GD.frames.items()},
               gear=GG.info, lid_open_deg=LID_OPEN,
               copies=[{"name": n, "mesh": m, "matrix": np.round(np.asarray(Mx, float), 6).tolist(), "collection": cn}
                       for n, m, Mx, cn in GG.instances()])
json.dump(dict({"note": GUNDECK_NOTE}, **GD_GAME), open(os.path.join(OUT, "gundeck.json"), "w"), indent=1,
          default=str)
ORLOP_NOTE = ("the orlop and the hold (docs/shipkit-14): every part in place in the ship's frame; lights, the light rooms' "
              "and the cockpit's lanterns (a warm point light each); mast_heels, where each lower mast bears on the "
              "keelson; heights_m, the decks' and the hold's heights amidships; collections, the Blender collections "
              "the game loads each deck below by")
json.dump(dict({"note": ORLOP_NOTE}, **OB.info, lights=OB.lights, parts=sorted(ORLOP),
               collections={c.name: sorted(o.name for o in c.objects) for c in SC.collection.children
                            if c.name in ("Orlop", "Hold")}),
          open(os.path.join(OUT, "orlop.json"), "w"), indent=1, default=str)
BERTHDECK_NOTE = (
    "the berth deck (docs/shipkit-13), in the ship's frame (metres): layout and the builder's records of where its "
    "parts fell (room_x, the bulkheads' places along the ship; berthing, the hammocks' rows and span; messes, the "
    "tables' places; sick_bay, the cots; knees_x_m and lodging_knees, the hanging and lodging knees; and the rest); "
    "lights, the lanterns' lights (a point light in each lantern's body: its zone, colour, kelvin, lumens, radius and "
    "whether it casts shadows) within light_budget, light_zones_note saying how to light by zone; below, what the game "
    "loads when below: the collection BerthDeck (objects, its parts; lights, the lanterns' lights; and the hooks under "
    "the beams, copies shown day and night), the two pose collections (show one: the hammocks slung by night or the "
    "messes laid by day), and zones, which lights' zones each object facing into the berth deck is in (names ending "
    "in * are prefixes); planking, the deck's planks drawn from its 'Planking' and 'Margin' UVs as the gun deck's "
    "(gundeck.json); copies, every linked copy of the stores kit's items (name, mesh, 4x4 in the ship's frame, "
    "collection)")
BERTH_BELOW = {
    "collection": "BerthDeck",
    "objects": sorted(BERTHDECK),
    "lights": sorted(o.name for o in BERTH_LIGHTS),
    "hooks": "the hammocks' and the cots' hooks (HammockHook_*, BerthCotHook_*) are copies in BerthDeck, shown day and "
             "night",
    "pose_collections": {
        "BerthDeck_Hammocks": "the crew's hammocks slung, by night (hidden as built)",
        "BerthDeck_Messes": "the crew's messes laid, by day: the tables let down on their slings, the benches, the "
                            "mess kids and the sea chests (shown as built)"},
    "seen_from_above": "the gun deck's hatchways and ladders look down onto it: near an open hatchway on the gun deck "
                       "the deck under it is in view",
    "zones": BERTH_ZONES}
BD_GAME = dict(BD.info, lights=BD.lights, light_budget=BD.c["lanterns"]["light_budget"], planking=BD.planking(),
               light_zones_note=BD.c["lanterns"]["zones_note"], room_x=BD.room_x, below=BERTH_BELOW,
               copies=[{"name": c["name"], "mesh": c["item"],
                        "matrix": np.round(np.asarray(c["matrix"], float), 6).tolist(), "collection": c["collection"]}
                       for c in BD.copies_])
json.dump(dict({"note": BERTHDECK_NOTE}, **BD_GAME), open(os.path.join(OUT, "berthdeck.json"), "w"), indent=1,
          default=str)
# the berth deck's hand-over to the orlop slice (14), from the deck as built (BerthDeck.handover; its notes are
# berthdeck_1797.json's handover)
json.dump(BD.handover(), open(os.path.join(OUT, "berth_deck.json"), "w"), indent=1)
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


def unmet(card, by_design, names=None):
    """the whys of a card's meets pairs whose parts no longer meet (by_design: a room check's pairs that meet by
    design): a part meant to rest on, be let into or driven into another that no longer reaches it hangs clear of what
    holds it. A pattern (Lid_*_S) stands for every part it matches, and with names (the objects the room check saw)
    each of those must meet the other side: one hammock's hook hanging clear of its beam fails as all of them would
    (the why then names the parts that don't meet)"""
    import fnmatch

    def hit(n, A):
        return any(fnmatch.fnmatchcase(n, a) for a in A)
    out = []
    for A, B, why, _ in card["meets"]["pairs"]:
        rows = [m for m in by_design if (hit(m[0], A) and hit(m[1], B)) or (hit(m[1], A) and hit(m[0], B))]
        if not rows:
            out.append(why)
            continue
        if names is None:
            continue
        met = {n for m in rows for n in m[:2]}
        clear = sorted({n for side in (A, B) for a in side if any(ch in a for ch in "*?[")
                        for n in fnmatch.filter(names, a) if n not in met})
        if clear:
            out.append(f"{why} (not {', '.join(clear[:8])}{' and more' if len(clear) > 8 else ''})")
    return out


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
SHUT_DOORS = {n: v for n, v in DOOR_SWINGS.items() if v["clear_to_deg"] is None or v["clear_to_deg"] < v["open_deg"]
              or v["least_gap_in"] < 0.1}
if SHUT_DOORS:
    raise SystemExit("a cabin door can't swing open clear of the floor, the sill, its jambs and casing or the furniture, "
                     "or comes within 0.1 in of them (build.json gundeck.door_swings): " + json.dumps(SHUT_DOORS))
TILLER_FOUL = {w: v for w, v in TILLER_SWING.items() if w.startswith("to_") and (v["clear_to_deg"] != v["to_deg"] or
                                                                                v["least_gap_in"] < 0.5 or
                                                                                v["joins_most_apart_in"] > 0.05)}
if TILLER_FOUL:
    raise SystemExit("the rudder's head, the tiller and its ropes can't swing hard over each way clear of the beams, the "
                     "window seat, the after wall, the cabin's lantern, the sheaves and each other, or come within half "
                     "an inch of them, or a tiller rope's parts come more than a twentieth of an inch apart "
                     "(build.json gundeck.tiller_swing): " + json.dumps(TILLER_FOUL))
if DOOR_HELM["touch"] or DOOR_HELM["least_gap_in"] < 0.5:
    raise SystemExit("a cabin door meets the tiller or its ropes, or comes within half an inch of them, at some opening "
                     "and angle of the helm (build.json gundeck.door_helm): " +
                     json.dumps({k: DOOR_HELM[k] for k in ("least_gap_in", "least_gap_at", "touch")}))
if LID_LIGHT["leaks"]:
    raise SystemExit("daylight shows round a shut port lid: rays from inside reach the slit round it (build.json "
                     "gundeck.lid_light): " + json.dumps(LID_LIGHT["leaking"]))
GUNDECK_UNMET = unmet(GD.c, GUNDECK_ROOM["by_design"], ROOM_NAMES["gundeck"])
if GUNDECK_UNMET:
    raise SystemExit("a designed contact of the gun deck's parts no longer meets: a part hangs clear of what holds it "
                     "(gundeck_1797.json meets, build.json gundeck.room): " + json.dumps(GUNDECK_UNMET))
GEAR_FOLDED = {n: v for n, v in list(GEAR_FOLDS.items()) + list(GUNDECK_FOLDS.items()) + list(DECK_FOLDS.items())
               if v["pairs"]}
if GEAR_FOLDED:
    raise SystemExit("a part of either deck or a piece of the guns' gear crosses itself (build.json gundeck.folds, "
                     "deck.folds): " + json.dumps(GEAR_FOLDED))
if ORLOP_ROOM["meet"]:
    raise SystemExit("the orlop's or the hold's parts meet the ship or each other (build.json orlop.room): " +
                     json.dumps(ORLOP_ROOM["meet"][:30]))
ORLOP_UNMET = unmet(OB.c, ORLOP_ROOM["by_design"])
if ORLOP_UNMET:
    raise SystemExit("a designed contact of the orlop's or the hold's parts no longer meets: a part hangs clear of what "
                     "holds it (orlop_1797.json meets, build.json orlop.room): " + json.dumps(ORLOP_UNMET))
ORLOP_FOLDED = {n: v for n, v in ORLOP_FOLDS.items() if v["pairs"]}
if ORLOP_FOLDED:
    raise SystemExit("a part of the orlop or the hold crosses itself (build.json orlop.folds): " +
                     json.dumps(ORLOP_FOLDED))
if GD.info["layout_close"]:
    raise SystemExit("two of the gun deck's fittings stand closer in plan than 0.15 m (build.json "
                     "gundeck.layout_close): " + json.dumps(GD.info["layout_close"]))
if BERTHDECK_ROOM["meet"] or BERTHDECK_ROOM["floats"]:
    raise SystemExit("the berth deck's parts or copies meet the ship or each other, or stand off the deck (build.json "
                     "berthdeck.room): " +
                     json.dumps({"meet": BERTHDECK_ROOM["meet"][:30], "floats": BERTHDECK_ROOM["floats"][:30]}))
BERTHDECK_UNMET = unmet(BD.c, BERTHDECK_ROOM["by_design"], ROOM_NAMES["berthdeck"])
if BERTHDECK_UNMET:
    raise SystemExit("a designed contact of the berth deck's parts no longer meets: a part hangs clear of what holds "
                     "it (berthdeck_1797.json meets, build.json berthdeck.room): " + json.dumps(BERTHDECK_UNMET))
BERTH_FOLDED = {n: v for n, v in BERTH_FOLDS.items() if v["pairs"]}
if BERTH_FOLDED:
    raise SystemExit("a part of the berth deck or a copied item crosses itself (build.json berthdeck.folds): " +
                     json.dumps(BERTH_FOLDED))
if BD.info["layout_close"]:
    raise SystemExit("two of the berth deck's fittings stand closer in plan than 0.15 m (build.json "
                     "berthdeck.layout_close): " + json.dumps(BD.info["layout_close"]))
if BT.failures():
    raise SystemExit("the boats fail their own checks (build.json boats.checks): " +
                     json.dumps(BT.failures(), default=str))
if AN.info["cable"]["least_bend_of_diameter"] < AN.card["cable"]["bend_min_of_diameter"] - 0.005:
    raise SystemExit("the cable bends tighter than anchors_1797.json's bend_min_of_diameter outside the clinch "
                     "(build.json anchors.cable.least_bend_of_diameter)")
if "sheet" in AN.info and abs(AN.info["sheet"]["stock_end_over_side_m"] - AN.card["sheet_stow"]["stock_gap_m"]) > 0.005:
    raise SystemExit("the sheet anchor's stock does not bear on the side (build.json anchors.sheet.stock_end_over_side_m, "
                     "against anchors_1797.json's sheet_stow.stock_gap_m)")
if "sheet" in AN.info and AN.info["sheet"]["heel"]["lowest_over_sea_m"] < AN.card["sheet_stow"]["heel_clear_m"] - 0.005:
    raise SystemExit("the sheet anchor would dip in the sea with her heeled (build.json anchors.sheet.heel, against "
                     "anchors_1797.json's sheet_stow.heel_clear_m)")
if "sheet" in AN.info and AN.info["sheet"]["painter"]["safety"] < AN.card["sheet_stow"]["painter"]["min_safety"]:
    raise SystemExit("the sheet anchor's painter is too weak for its legs' lead (build.json anchors.sheet.painter.safety, "
                     "against anchors_1797.json's sheet_stow.painter.min_safety)")
UNSEATED = {n: r for n, r in DECOR_SEATED.items() if r["loose"] or r["rims_standing"]}
if UNSEATED:
    raise SystemExit("carving stands off what it is carved on (build.json decor.seated): " + json.dumps(UNSEATED))
if SAIL_ROOM["through"] or SAIL_ROOM["set_sails_meet"]:
    raise SystemExit("sails meet the ship or each other (build.json sails.room): " +
                     json.dumps({"through": SAIL_ROOM["through"], "set_sails_meet": SAIL_ROOM["set_sails_meet"]}))
