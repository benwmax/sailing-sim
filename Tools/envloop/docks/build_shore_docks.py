"""Track F (shore plan, Nov 16 2026): private docks, boathouses, covered marina sheds and the boats that sit in them,
built by script in Blender so every one can be rebuilt and changed. Cloud half only: nothing here is loaded by the game
until Track I's integration pull request places them (docs/envloop/docks/README.md).

Meshes (origin on the bank's bulkhead line at the pool, Z = 0 at 435.5 ft, +X out over the water; the walk's axis is
Y = 0; deck tops at Z = DECK, as HouseKit.cpp's boathouses today):
  SM_ShoreDock_A..F       six private dock layouts (cards.json: what each is for)
  SM_Boathouse_A..C       three open-sided covered slips with a lift (the Rockwall takeline rule: covered, not enclosed)
  SM_MarinaShed_Bay/_End  a covered-slip module for the lake's other marinas, tiled along +Y every BAY_W metres
  SM_ShoreBoat_*          runabout (covered, open), pontoon, personal watercraft: origin under the hull at the lift's
                          cradle contact, +X to the bow; placed at the docks' sockets
Each mesh records sockets (where boats, PWCs, kayaks and umbrellas go) in docks_manifest.json beside the FBX files.

Usage: python3 Tools/envloop/docks/build_shore_docks.py <out dir> [--only A,BH1]
       (Python with the bpy module, or blender -b --factory-startup -P <this> -- <out dir>)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import shorekit  # noqa: E402
from shorekit import Part, club  # noqa: E402

import bpy  # noqa: E402

DECK = 1.0          # deck top above the pool (HouseKit.cpp Zd); Ray Hubbard runs 0.3 to 1.2 m below pool in a dry autumn
WALK_W = 1.22       # 4 ft walks
SLIP_W = 3.66       # 12 ft slips: a 20-22 ft runabout or a pontoon
FINGER_W = 1.22
CLEAR = 3.05        # eave height over the deck: 10 ft, clears a runabout's tower and a pontoon's bimini down
BAY_W = SLIP_W + 0.92


# -- shared pieces ---------------------------------------------------------------------------------------------------
def walk(p, x0, x1, y0, y1, piles=True, spacing=3.05, rails=False):
    """A fixed deck over [x0,x1] x [y0,y1]: boards across its long axis, framing, pipe pilings in pairs and bents."""
    along_x = (x1 - x0) >= (y1 - y0)
    p.decking(x0, x1, y0, y1, DECK, across=along_x)
    p.frame(x0, x1, y0, y1, DECK, along_x=along_x)
    if not piles:
        return
    if along_x:
        n = max(1, int(math.ceil((x1 - x0 - 0.3) / spacing)))
        for i in range(n + 1):
            x = x0 + 0.15 + (x1 - x0 - 0.3) * i / n
            ys = (y0 - 0.11, y1 + 0.11)
            for y in ys:
                p.piling(x, y, DECK + 0.05)
            p.bent(x - 0.13, ys, DECK)
    else:
        n = max(1, int(math.ceil((y1 - y0 - 0.3) / spacing)))
        for i in range(n + 1):
            y = y0 + 0.15 + (y1 - y0 - 0.3) * i / n
            for x in (x0 - 0.11, x1 + 0.11):
                p.piling(x, y, DECK + 0.05)


def cleat(p, x, y, yaw=0.0):
    p.drop(club.cleat, (x, y, DECK), yaw)


def light(p, x, y, kind="post"):
    """Dock lights: a 4x4 post light with a lantern head (most private piers), or a low bollard."""
    if kind == "post":
        p.box("Wood", (x, y, DECK + 0.6), (0.0445, 0.0445, 0.6), bevel=0.004, segments=1)
        p.box("Dark", (x, y, DECK + 1.23), (0.08, 0.08, 0.03), bevel=0.006)
        p.box("LampGlow", (x, y, DECK + 1.33), (0.06, 0.06, 0.08), bevel=0.003)
        for sx in (-1, 1):
            for sy in (-1, 1):
                p.box("Dark", (x + sx * 0.062, y + sy * 0.062, DECK + 1.33), (0.008, 0.008, 0.085))
        p.lathe("Dark", (x, y, DECK + 1.41), [(0.1, 0.0), (0.1, 0.01), (0.03, 0.07), (0.0, 0.08)], sides=4)
    else:
        p.lathe("Dark", (x, y, DECK), [(0.07, 0.0), (0.07, 0.42), (0.075, 0.42), (0.075, 0.47), (0.0, 0.5)], sides=12)
        p.lathe("LampGlow", (x, y, DECK + 0.32), [(0.072, 0.0), (0.072, 0.08), (0.0, 0.08)], sides=12)


def fender(p, x, y, face=1.0, axis="X"):
    """A 6.5 x 22 in fender hung off a deck edge on a line from a cleat (the club kit's size)."""
    top = DECK - 0.15
    off = (face * 0.12, 0.0) if axis == "X" else (0.0, face * 0.12)
    cx, cy = x + off[0], y + off[1]
    p.tube("White", (cx, cy, DECK + 0.02), (cx, cy, top), 0.006, sides=5, caps=False)
    p.lathe("White", (cx, cy, top - 0.56), [(0.0, 0.0), (0.04, 0.005), (0.075, 0.06), (0.083, 0.28), (0.075, 0.5), (0.04, 0.555), (0.0, 0.56)], sides=14)


def bumper_strip(p, a, b, z=DECK - 0.12):
    """White vinyl dock edge bumper along a slip's edge (on the rim board's face)."""
    p.sweep("Vinyl", [(a[0], a[1], z), (b[0], b[1], z)], [(0.03, 0.06)] * 2, sides=8)


def ladder(p, x, y, yaw=0.0):
    """The club kit's stainless swim ladder, hung off a fixed deck's end (its float standoffs reach the pilings)."""
    p.drop(club.ladder, (x, y, DECK), yaw)


def lift(p, x0, x1, y0, y1, raised=0.55):
    """A four-post pile-mount boat lift in a slip [x0,x1] x [y0,y1]: two galvanized I-beams across the slip on the
    pilings' tops 1.9 m over the deck, a drive motor and wheel on one, cable drums, cables down to a cradle of two
    cross beams and two carpeted bunks. `raised`: the cradle's bunks above the pool (the boat lifted clear)."""
    zb = DECK + 1.9
    ya, yb = y0 - 0.16, y1 + 0.16
    for x in (x0 + 1.0, x1 - 1.4):
        for y in (ya, yb):
            p.piling(x, y, zb - 0.12, r=0.1095)
            p.box("Galv", (x, y, zb - 0.13), (0.13, 0.13, 0.012), segments=1)                 # saddle plate
            for s_ in (-1, 1):                                                                  # bolted side straps
                p.box("Galv", (x + s_ * 0.115, y, zb - 0.2), (0.006, 0.08, 0.1), segments=1)
        p.box("Galv", (x, (ya + yb) / 2, zb), (0.05, (yb - ya) / 2 + 0.2, 0.1), segments=1)     # W6 beam
        p.box("Galv", (x, (ya + yb) / 2, zb + 0.095), (0.075, (yb - ya) / 2 + 0.2, 0.006), segments=1)
        p.box("Galv", (x, (ya + yb) / 2, zb - 0.095), (0.075, (yb - ya) / 2 + 0.2, 0.006), segments=1)
        for y in (y0 + 0.75, y1 - 0.75):
            p.lathe("Galv", (x, y, zb - 0.1), [(0.09, 0.0), (0.09, -0.12), (0.0, -0.12)], sides=12)          # cable drum
            zc = raised - 0.05
            p.tube("Steel", (x, y, zb - 0.2), (x, y, zc + 0.12), 0.006, sides=5, caps=False)     # cable
        p.box("Galv", (x, (y0 + y1) / 2, raised - 0.12), (0.06, (y1 - y0) / 2 - 0.25, 0.08), segments=1)  # cradle beam
    xm = x0 + 1.0
    p.box("White", (xm - 0.25, yb + 0.05, zb + 0.15), (0.22, 0.16, 0.18), bevel=0.02)          # motor cover
    p.lathe("Steel", (xm - 0.25, yb - 0.05, zb + 0.15), [(0.0, 0.0), (0.22, 0.0), (0.22, 0.02), (0.0, 0.02)], sides=18, axis="-Y")
    p.tube("Galv", (x0 + 1.0, yb, zb + 0.05), (x1 - 1.4, yb, zb + 0.05), 0.02, sides=8)        # drive shaft
    for y in (y0 + 0.95, y1 - 0.95):                                                            # bunks, carpeted
        p.box("Galv", ((x0 + x1) / 2 - 0.2, y, raised - 0.03), ((x1 - x0) / 2 - 0.6, 0.035, 0.06), segments=1)
        p.box("Carpet", ((x0 + x1) / 2 - 0.2, y, raised + 0.04), ((x1 - x0) / 2 - 0.6, 0.05, 0.03), bevel=0.01)


def roof_lights(p, xs, y):
    for x in xs:
        p.lathe("Dark", (x, y, DECK + CLEAR - 0.15), [(0.0, 0.0), (0.09, 0.0), (0.09, -0.04), (0.0, -0.04)], sides=12)
        p.lathe("LampGlow", (x, y, DECK + CLEAR - 0.19), [(0.08, 0.0), (0.075, -0.02), (0.0, -0.025)], sides=12)


def posts(p, pts, z_top):
    """Roof posts: the pilings carried up to the roof beam (the usual Ray Hubbard covered slip)."""
    for x, y in pts:
        p.piling(x, y, z_top, cap=False)


# -- private docks ---------------------------------------------------------------------------------------------------
def dock_a():
    """A: a straight pier 4 x 40 ft with an 8 x 24 ft T head. Swim ladder off the end, post lights at the head's
    corners, cleats on the head's face. The commonest private pier on a seawalled lot."""
    p = Part("SM_ShoreDock_A", seed=11)
    h = WALK_W / 2
    walk(p, 0.0, 12.2, -h, h)
    walk(p, 12.2, 14.64, -3.66, 3.66)
    ladder(p, 14.64, 0.0)
    for s in (-1, 1):
        light(p, 14.4, s * 3.42)
        cleat(p, 14.4, s * 2.2, 90)
        cleat(p, 12.45, s * 3.4, 0)
        bumper_strip(p, (14.67, s * 0.45), (14.67, s * 3.6))
    for y in (-2.6, -0.6, 1.4):
        fender(p, 14.64, y)
    p.socket("boat_0", (16.0, -1.2, -0.3), 90.0)
    return p


def dock_b():
    """B: an L pier: a 30 ft walk ending in a 10 x 12 ft side platform, a drive-on PWC port tied alongside the walk."""
    p = Part("SM_ShoreDock_B", seed=12)
    h = WALK_W / 2
    walk(p, 0.0, 9.15, -h, h)
    walk(p, 9.15, 12.2, -h, h + 2.44)
    light(p, 11.95, h + 2.2)
    light(p, 4.6, h - 0.1, kind="bollard")
    for x in (6.0, 8.6):
        cleat(p, x, -h + 0.1, 90)
    cleat(p, 11.95, -h + 0.15, 90)
    bumper_strip(p, (5.4, -h - 0.04), (9.1, -h - 0.04))
    p.socket("pwc_port_0", (7.0, -h - 1.1, 0.0), 0.0)
    p.socket("pwc_0", (7.0, -h - 1.1, 0.36), 0.0)
    p.socket("chairs_0", (10.7, h + 1.2, DECK), 200.0)
    return p


def dock_c():
    """C: a walk to an open slip with a four-post lift (no roof): fingers each side of the slip, the boat lifted."""
    p = Part("SM_ShoreDock_C", seed=13)
    h = WALK_W / 2
    walk(p, 0.0, 5.0, -h, h)
    y0, y1 = -SLIP_W / 2, SLIP_W / 2
    walk(p, 5.0, 6.22, y0 - FINGER_W, y1 + FINGER_W)
    for s in (-1, 1):
        yc = s * (SLIP_W / 2 + FINGER_W / 2)
        walk(p, 6.22, 13.5, yc - FINGER_W / 2, yc + FINGER_W / 2)
        cleat(p, 13.2, yc - s * 0.45, 0)
        cleat(p, 6.6, yc - s * 0.45, 0)
        bumper_strip(p, (6.3, s * (SLIP_W / 2 + 0.04)), (13.45, s * (SLIP_W / 2 + 0.04)))
    lift(p, 6.4, 13.5, y0 + 0.1, y1 - 0.1)
    light(p, 13.25, y1 + FINGER_W - 0.2)
    p.socket("boat_0", (10.1, 0.0, 0.62), 0.0)
    return p


def dock_d():
    """D: a fixed landing, an aluminium gangway down to a floating 8 x 20 ft dock held by two pilings with sliding
    hoops (it rides the lake's swings), a kayak rack and the club kit's ladder off its end."""
    p = Part("SM_ShoreDock_D", seed=14)
    walk(p, 0.0, 1.6, -0.9, 0.9)
    zf = 0.38                                              # the float's deck: 15 in freeboard
    x0, x1 = 7.6, 13.7
    # gangway: two aluminium side trusses, treads, handrails, a hinge at the top and rollers on the float
    for s in (-1, 1):
        y = s * 0.48
        p.sweep("Steel", [(1.55, y, DECK + 0.05), (7.7, y, zf + 0.05)], [(0.02, 0.09)] * 2, sides=4, up=(0, 0, 1))
        p.sweep("Steel", [(1.55, y, DECK + 0.95), (7.7, y, zf + 0.95)], [(0.022, 0.022)] * 2, sides=10)
        for k in range(7):
            f = k / 6
            x = 1.6 + 6.05 * f
            z = DECK + (zf - DECK) * f
            p.tube("Steel", (x, y, z + 0.08), (x, y, z + 0.95), 0.017, sides=8)
        p.lathe("Dark", (7.7, y, zf), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.07), (0.0, 0.07)], sides=12, axis="Z")
    gw = 6.1
    n = int(gw / 0.3)
    for k in range(n):
        f = (k + 0.5) / n
        x = 1.6 + gw * f
        z = DECK + (zf - DECK) * f
        p.box("Steel", (x, 0, z + 0.06), (0.12, 0.44, 0.015), segments=1, pitch=math.degrees(math.atan2(DECK - zf, gw)))
    # the float: boards on a frame on black polyethylene float drums
    p.decking(x0, x1, -1.22, 1.22, zf, across=False)
    p.frame(x0, x1, -1.22, 1.22, zf, along_x=False)
    for x in (x0 + 0.9, (x0 + x1) / 2, x1 - 0.9):
        for y in (-0.62, 0.62):
            p.box("Floats", (x, y, zf - 0.21 - 0.2), (0.6, 0.5, 0.2), bevel=0.05)
    for y in (-1.22 - 0.25, 1.22 + 0.25):
        p.piling(x0 + 2.0, y, DECK + 1.6)
        p.drop(club.hoop, (x0 + 2.0, y, zf), 90.0 if y > 0 else -90.0)
    p.drop(club.ladder, (x1, 0.0, zf), 0.0)
    for y in (-1.0, 1.0):
        p.drop(club.cleat, (x1 - 0.25, y, zf), 90.0)
    # a kayak rack: two treated 4x4 uprights with arms for two boats
    for x in (x0 + 0.4, x0 + 2.4):
        p.box("Wood", (x, 1.05, zf + 0.6), (0.0445, 0.0445, 0.6), bevel=0.004, segments=1)
        for z in (0.45, 0.95):
            p.box("Wood", (x, 0.85, zf + z), (0.0445, 0.22, 0.019), segments=1)
            p.box("Carpet", (x, 0.82, zf + z + 0.022), (0.05, 0.2, 0.006))
    p.socket("kayak_0", (x0 + 1.4, 0.82, zf + 0.53), 0.0)
    p.socket("kayak_1", (x0 + 1.4, 0.82, zf + 1.03), 0.0)
    p.socket("boat_0", ((x0 + x1) / 2, -2.65, -0.3), 0.0)
    return p


def dock_e():
    """E: a sundeck pier: a walk to a 16 x 16 ft deck with a rail on three sides, a built-in bench and lights."""
    p = Part("SM_ShoreDock_E", seed=15)
    h = WALK_W / 2
    walk(p, 0.0, 8.0, -h, h)
    x0, x1, y0, y1 = 8.0, 12.88, -2.44, 2.44
    walk(p, x0, x1, y0, y1)
    p.rail([(x0 + 0.05, y0 + 0.05), (x1 - 0.05, y0 + 0.05)], DECK)
    p.rail([(x1 - 0.05, y0 + 0.05), (x1 - 0.05, -0.5)], DECK)
    p.rail([(x1 - 0.05, 0.5), (x1 - 0.05, y1 - 0.05)], DECK)
    p.rail([(x1 - 0.05, y1 - 0.05), (x0 + 0.05, y1 - 0.05)], DECK)
    ladder(p, x1, 0.0)
    # a bench along the +Y rail: 2x6 seat boards on 4x4 legs, 0.45 m high, 0.45 m deep
    for k in range(3):
        p.box("Wood", (x0 + 2.4, y1 - 0.18 - k * 0.15, DECK + 0.45), (2.0, 0.07, 0.019), segments=1)
    for x in (x0 + 0.6, x0 + 2.4, x0 + 4.2):
        p.box("Wood", (x, y1 - 0.33, DECK + 0.21), (0.0445, 0.0445, 0.21), segments=1)
    for s in (-1, 1):
        light(p, x0 + 0.3, s * (y1 - 0.25), kind="bollard")
    p.socket("umbrella_0", ((x0 + x1) / 2, -0.8, DECK), 0.0)
    p.socket("chairs_0", ((x0 + x1) / 2 - 0.6, -1.2, DECK), 30.0)
    p.socket("boat_0", (x1 + 1.4, -1.0, -0.3), 90.0)
    return p


def dock_f():
    """F: a short stub pier with a 8 x 13 ft head and drive-on PWC ports on both sides (two jet skis)."""
    p = Part("SM_ShoreDock_F", seed=16)
    h = WALK_W / 2
    walk(p, 0.0, 5.5, -h, h)
    walk(p, 5.5, 9.5, -1.22, 1.22)
    for s in (-1, 1):
        cleat(p, 6.1, s * 1.1, 0)
        cleat(p, 9.2, s * 1.1, 0)
        p.socket(f"pwc_port_{(s + 1) // 2}", (7.5, s * (1.22 + 1.1), 0.0), 0.0)
        p.socket(f"pwc_{(s + 1) // 2}", (7.5, s * (1.22 + 1.1), 0.36), 0.0)
    light(p, 9.3, 0.0, kind="bollard")
    return p


# -- boathouses ------------------------------------------------------------------------------------------------------
def slip_u(p, x_back, x_end, slips, fingers_w=FINGER_W, roof=True, rise=1.2):
    """The U of decking round one or more slips: a back walk across, fingers between and either side; with `roof`, a
    gable roof (ridge along X) on the pilings carried up as posts. Returns (y0, y1) of the slips' outer fingers and the
    slips' centres."""
    total = slips * SLIP_W + (slips + 1) * fingers_w
    ya = -total / 2
    walk(p, x_back, x_back + fingers_w, ya, -ya)
    centres = []
    y = ya
    post_pts = []
    for k in range(slips + 1):
        walk(p, x_back + fingers_w, x_end, y, y + fingers_w, piles=False)
        for x in (x_back + fingers_w + 0.2, (x_back + x_end) / 2 + 0.3, x_end - 0.2):
            for yy in ((y - 0.11,) if k == 0 else ()) + ((y + fingers_w + 0.11,) if k == slips else ()) + ((y + fingers_w / 2,) if 0 < k < slips else ()):
                post_pts.append((x, yy))
        # inner pilings that don't carry the roof, every 3 m along the fingers
        for x in (x_back + fingers_w + 1.7, x_end - 1.7):
            for yy in (y - 0.11, y + fingers_w + 0.11):
                p.piling(x, yy, DECK + 0.05)
        if k < slips:
            centres.append(y + fingers_w + SLIP_W / 2)
            bumper_strip(p, (x_back + fingers_w + 0.2, y + fingers_w + 0.04), (x_end - 0.1, y + fingers_w + 0.04))
            bumper_strip(p, (x_back + fingers_w + 0.2, y + fingers_w + SLIP_W - 0.04), (x_end - 0.1, y + fingers_w + SLIP_W - 0.04))
        y += fingers_w + SLIP_W
    if roof:
        posts(p, post_pts, DECK + CLEAR)
        xs = sorted({x for x, _ in post_pts})
        for x, y in post_pts:
            # knee braces (2 1/2 in pipe) from each post up to the eave beam, toward its neighbours along X
            for d in (-1, 1):
                if (d < 0 and x == xs[0]) or (d > 0 and x == xs[-1]):
                    continue
                p.tube("Galv", (x, y, DECK + CLEAR - 0.85), (x + d * 0.7, y, DECK + CLEAR - 0.2), 0.037, sides=8)
                p.box("Galv", (x + d * 0.7, y, DECK + CLEAR - 0.2), (0.05, 0.07, 0.008), segments=1)
        for s in (-1, 1):
            p.box("Galv", ((x_back + x_end) / 2 + 0.3, s * (-ya + 0.11), DECK + CLEAR - 0.1), ((x_end - x_back) / 2 + 0.2, 0.06, 0.1), segments=1)
        p.gable_roof(x_back + fingers_w + 0.1, x_end, ya - 0.11, -ya + 0.11, DECK + CLEAR, rise)
    return ya, -ya, centres


def boathouse_a():
    """BH-A: a single covered slip at the end of a 20 ft walk (Rockwall's takeline rule: a boathouse needs a fixed pier,
    a roof over every stored boat and a lift inside), gable roof of ribbed steel, the lift, two lights under the roof."""
    p = Part("SM_Boathouse_A", seed=21)
    h = WALK_W / 2
    walk(p, 0.0, 6.1, -h, h)
    ya, yb, cs = slip_u(p, 6.1, 14.6, 1, rise=1.1)
    lift(p, 7.6, 14.5, cs[0] - SLIP_W / 2 + 0.1, cs[0] + SLIP_W / 2 - 0.1)
    roof_lights(p, (9.0, 12.5), 0.0)
    for s in (-1, 1):
        cleat(p, 14.3, s * (SLIP_W / 2 + 0.4), 0)
        light(p, 6.5, s * (yb - 0.25), kind="bollard")
    p.socket("boat_0", (11.0, cs[0], 0.62), 0.0)
    return p


def boathouse_b():
    """BH-B: two covered slips side by side (a centre finger), one wide gable roof, two lifts, a PWC port off the
    outer finger and a sundeck-less storage box. The bigger lots' boathouse."""
    p = Part("SM_Boathouse_B", seed=22)
    h = WALK_W / 2
    walk(p, 0.0, 6.1, -h, h)
    ya, yb, cs = slip_u(p, 6.1, 14.6, 2, rise=1.6)
    for c in cs:
        lift(p, 7.6, 14.5, c - SLIP_W / 2 + 0.1, c + SLIP_W / 2 - 0.1)
    roof_lights(p, (9.0, 12.5), 0.0)
    p.drop(club.dock_box, (7.6, yb - 0.6, DECK), 0.0)
    p.socket("boat_0", (11.0, cs[0], 0.62), 0.0)
    p.socket("boat_1", (11.0, cs[1], 0.62), 0.0)
    p.socket("pwc_port_0", (10.9, yb + 1.15, 0.0), 0.0)
    p.socket("pwc_0", (10.9, yb + 1.15, 0.36), 0.0)
    return p


def boathouse_c():
    """BH-C: a covered slip with a sundeck on its roof (one storey, flat deck with a rail) and a stair up from the
    walk: the Texas lake classic. The roof deck drains to the lake side."""
    p = Part("SM_Boathouse_C", seed=23)
    h = WALK_W / 2
    walk(p, 0.0, 6.1, -h, h)
    ya, yb, cs = slip_u(p, 6.1, 14.6, 1, roof=False)
    zt = DECK + CLEAR
    pts = []
    for x in (6.3, 10.4, 14.4):
        for y in (ya - 0.11, yb + 0.11):
            pts.append((x, y))
    posts(p, pts, zt - 0.2)
    for x in (6.3, 10.4, 14.4):
        p.box("Galv", (x, 0, zt - 0.25), (0.08, yb + 0.2, 0.15), segments=1)
    p.frame(6.1, 14.6, ya - 0.2, yb + 0.2, zt + 0.03, along_x=True, joist=0.4)
    p.decking(6.1, 14.6, ya - 0.2, yb + 0.2, zt + 0.03, across=True)
    # an underside soffit so the roof deck isn't see-through from the boat
    p.box("MetalRoof", (10.35, 0, zt - 0.205), (4.25, yb + 0.2, 0.006), segments=1)
    p.rail([(6.15, ya - 0.15), (14.55, ya - 0.15), (14.55, yb + 0.15), (7.6, yb + 0.15)], zt + 0.03)
    # stair: a straight run up along the +Y finger's outer side from the back walk
    rise = zt + 0.03 - DECK
    nst = int(round(rise / 0.18))
    run = 0.26
    sy = yb + 0.75
    for k in range(nst):
        z = DECK + rise * (k + 1) / nst
        x = 14.0 - (nst - 1 - k) * run - 0.4
        p.box("Decking", (x, sy, z - 0.02), (0.15, 0.5, 0.02), segments=1)
    for s in (-1, 1):
        y = sy + s * 0.5
        x_lo, x_hi = 14.0 - nst * run - 0.4, 14.0 - 0.4
        p.sweep("Wood", [(x_lo, y, DECK - 0.1), (x_hi, y, zt)], [(0.019, 0.14)] * 2, sides=4, up=(0, 0, 1))
        p.sweep("Wood", [(x_lo, y, DECK + 0.9), (x_hi, y, zt + 0.9)], [(0.035, 0.035)] * 2, sides=6)
    walk(p, 6.1 + 7.0 - nst * run, 14.6, yb + 0.22, yb + 1.25)
    lift(p, 7.6, 14.5, cs[0] - SLIP_W / 2 + 0.1, cs[0] + SLIP_W / 2 - 0.1)
    roof_lights(p, (9.0, 12.5), 0.0)
    p.socket("boat_0", (11.0, cs[0], 0.62), 0.0)
    p.socket("umbrella_0", (11.5, -0.5, zt + 0.03), 0.0)
    p.socket("chairs_0", (10.5, 0.8, zt + 0.03), 160.0)
    return p


# -- covered marina sheds --------------------------------------------------------------------------------------------
def marina_bay(end=False):
    """A covered-slip module for the lake's commercial marinas (floating): one slip and one finger, BAY_W wide along
    +Y, the main walk across X = 0..1.8, a single-slope ribbed roof falling toward the fairway on steel columns.
    _End adds the closing finger and gable trim."""
    name = "SM_MarinaShed_End" if end else "SM_MarinaShed_Bay"
    p = Part(name, seed=31 + int(end))
    zf = 0.5
    L = 10.4
    w = BAY_W

    def float_deck(x0, x1, y0, y1):
        p.decking(x0, x1, y0, y1, zf, across=(x1 - x0) >= (y1 - y0))
        p.box("Floats", ((x0 + x1) / 2, (y0 + y1) / 2, zf - 0.25), ((x1 - x0) / 2 - 0.08, (y1 - y0) / 2 - 0.08, 0.2), bevel=0.04)
        p.box("Wood", ((x0 + x1) / 2, y0 + 0.02, zf - 0.1), ((x1 - x0) / 2, 0.02, 0.09), segments=1)
        p.box("Wood", ((x0 + x1) / 2, y1 - 0.02, zf - 0.1), ((x1 - x0) / 2, 0.02, 0.09), segments=1)

    float_deck(0.0, 1.8, 0.0, w)
    float_deck(1.8, L, w - 0.92, w)
    if end:
        float_deck(1.8, L, 0.0, 0.92)
    za, zb = zf + 3.6, zf + 3.0                    # roof high over the main walk, low at the slip ends
    cols = [(0.3, w - 0.46), (L - 0.3, w - 0.46)] + ([(0.3, 0.46), (L - 0.3, 0.46)] if end else [])
    for x, y in cols:
        z = za + (zb - za) * (x / L)
        p.tube("Galv", (x, y, zf), (x, y, z - 0.2), 0.076, sides=10)
        p.box("Galv", (x, y, zf + 0.01), (0.15, 0.15, 0.01), segments=1)
    for x in (0.3, L - 0.3):
        z = za + (zb - za) * (x / L)
        p.box("Galv", (x, w / 2, z - 0.15), (0.05, w / 2 + 0.02, 0.12), segments=1)      # beams across the bay
    p.ribbed_plane("MetalRoof", (-0.4, 0.0, za + 0.03), (-0.4, w, za + 0.03), (L + 0.4, w, zb - 0.02), (L + 0.4, 0.0, zb - 0.02), None)
    for y in (0.6, w / 2, w - 0.6):
        p.sweep("Galv", [(-0.3, y, za - 0.1), (L + 0.3, y, zb - 0.15)], [(0.03, 0.1)] * 2, sides=4, up=(0, 0, 1))
    p.box("MetalRoof", (L + 0.42, w / 2, zb - 0.1), (0.02, w / 2, 0.12), segments=1)               # fascia
    if end:
        p.sweep("MetalRoof", [(-0.4, -0.02, za - 0.05), (L + 0.4, -0.02, zb - 0.1)], [(0.02, 0.12)] * 2, sides=4, up=(0, 0, 1))
    for x in (2.6, L - 0.5):
        p.drop(club.cleat, (x, w - 0.75, zf), 0.0)
    p.lathe("LampGlow", (0.9, w / 2, za - 0.3), [(0.12, 0.0), (0.1, -0.03), (0.0, -0.035)], sides=12)
    p.socket("boat_0", (5.6, (w - 0.92) / 2 + (0.46 if end else 0.0), -0.3), 0.0)
    return p


# -- boats -----------------------------------------------------------------------------------------------------------
def hull(p, L, B, slot="Gelcoat", deadrise=18.0, sheer_z=0.95, chine=0.36, bow_rise=0.25, transom_w=0.86):
    """A planing runabout hull (deep V, flat sheer rising to the bow): stations along X from the transom (x=0) to the
    stem (x=L), each section keel - chine - gunwale. Origin: x=0 transom, z=0 keel at the cradle contact."""
    import bmesh
    from mathutils import Vector
    bm = p.bm
    n = 14
    rings = []
    for i in range(n + 1):
        f = i / n
        x = L * f
        hb = 0.5 * B * (transom_w + (1 - transom_w) * min(1.0, f / 0.45)) if f < 0.6 else 0.5 * B * math.sqrt(max(0.0, 1 - ((f - 0.6) / 0.4) ** 1.6))
        hb = max(hb, 0.015)
        zk = 0.0 if f < 0.65 else 0.45 * ((f - 0.65) / 0.35) ** 1.7
        zg = sheer_z + bow_rise * f ** 2
        hc = hb * 0.82
        zc = zk + hc * math.tan(math.radians(deadrise)) if f < 0.9 else zk + (zg - zk) * 0.35
        zc = min(zc, zg - 0.1)
        pts = [(x, -hb, zg), (x, -hc, zc), (x, 0.0, zk), (x, hc, zc), (x, hb, zg)]
        rings.append([bm.verts.new(v) for v in pts])
    faces = []
    for ra, rb in zip(rings, rings[1:]):
        for k in range(4):
            faces.append(bm.faces.new((ra[k], ra[k + 1], rb[k + 1], rb[k])))
    faces.append(bm.faces.new((rings[0][4], rings[0][3], rings[0][2], rings[0][1], rings[0][0])))
    p._faces(faces, slot)
    # rub rail along the sheer
    for s in (-1, 1):
        pts = [r[0 if s < 0 else 4].co.copy() for r in rings]
        p.sweep("Dark", [(v.x, v.y + s * 0.012, v.z - 0.01) for v in pts], [(0.02, 0.025)] * len(pts), sides=6)
    return rings


def deck_top(p, rings, slot="Gelcoat", z_off=0.0):
    """Close the hull's top: a deck from gunwale to gunwale (a cockpit is cut by the caller with seats/cover)."""
    bm = p.bm
    faces = []
    for ra, rb in zip(rings, rings[1:]):
        faces.append(bm.faces.new((ra[4], ra[0], rb[0], rb[4])) if ra[0] != rb[0] else None)
    p._faces([f for f in faces if f], slot)


def outboard(p, x, z, hp_big=True):
    """An outboard tilted up (as on a lift): cowl, midsection, lower unit and prop."""
    s = 1.0 if hp_big else 0.7
    p.box("White", (x - 0.35 * s, 0, z + 0.55 * s), (0.3 * s, 0.22 * s, 0.32 * s), bevel=0.06 * s, pitch=-30)
    p.box("Dark", (x - 0.55 * s, 0, z + 0.05 * s), (0.08 * s, 0.1 * s, 0.4 * s), bevel=0.02, pitch=-60)
    p.box("Dark", (x - 0.95 * s, 0, z - 0.05 * s), (0.12 * s, 0.05 * s, 0.1 * s), bevel=0.02, pitch=-60)
    p.box("Steel", (x - 0.12, 0, z + 0.25), (0.1, 0.25, 0.12), bevel=0.01)


def boat_runabout(covered):
    """A 21 ft bowrider (6.4 x 2.44 m), the commonest boat on a Ray Hubbard lift: white gelcoat hull, a walk-through
    windshield, seats; covered = the fitted canvas cover snapped over the gunwale (as most sit between outings)."""
    name = "SM_ShoreBoat_RunaboutCovered" if covered else "SM_ShoreBoat_RunaboutOpen"
    p = Part(name, seed=41)
    L, B = 6.4, 2.44
    rings = hull(p, L, B)
    zg = 0.95
    if covered:
        bm = p.bm
        rows = []
        for i, r in enumerate(rings):
            f = i / (len(rings) - 1)
            a, b = r[0].co, r[4].co
            crown = 0.38 * math.sin(math.pi * min(1.0, (f + 0.05) / 0.8)) if f < 0.85 else 0.05
            row = []
            for k in range(7):
                t = k / 6
                y = a.y + (b.y - a.y) * t
                z = a.z + 0.02 + crown * math.sin(math.pi * t) ** 0.7
                row.append(bm.verts.new((a.x - 0.01, y * 1.02, z)))
            rows.append(row)
        faces = []
        for ra, rb in zip(rows, rows[1:]):
            for k in range(6):
                faces.append(bm.faces.new((ra[k], ra[k + 1], rb[k + 1], rb[k])))
        faces.append(bm.faces.new(list(reversed(rows[0]))))
        p._faces(faces, "Canvas")
        for i in range(1, len(rings) - 1, 2):
            for s in (0, 4):
                v = rings[i][s].co
                p.box("Steel", (v.x, v.y * 1.03, v.z - 0.03), (0.012, 0.004, 0.012))      # snaps
    else:
        deck_top(p, rings[9:])
        for x in (2.6,):   # noqa: B007
            # windshield: two wings of tinted acrylic on an aluminium frame, open at the walk-through
            for s in (-1, 1):
                p.sweep("Glass", [(x + 0.2, s * 0.25, zg + 0.05), (x, s * 1.05, zg + 0.05)], [(0.006, 0.18)] * 2, sides=4, up=(0.4, 0, 1))
                p.sweep("Steel", [(x + 0.2, s * 0.25, zg + 0.42), (x, s * 1.05, zg + 0.42)], [(0.012, 0.012)] * 2, sides=6)
        p.box("Gelcoat", (2.4, 0.62, zg - 0.2), (0.35, 0.38, 0.32), bevel=0.05)              # helm console
        p.box("Dark", (2.62, 0.62, zg + 0.1), (0.15, 0.3, 0.02), pitch=-25)
        p.lathe("Dark", (2.45, 0.55, zg + 0.18), [(0.18, 0.0), (0.18, 0.02), (0.0, 0.02)], sides=16, axis="X")
        for x, y in ((1.85, 0.62), (1.85, -0.62)):
            p.box("Cushion", (x, y, zg - 0.38), (0.25, 0.25, 0.08), bevel=0.04)
            p.box("Cushion", (x - 0.24, y, zg - 0.1), (0.05, 0.25, 0.25), bevel=0.04)
        p.box("Cushion", (0.6, 0, zg - 0.35), (0.25, 1.0, 0.1), bevel=0.04)                 # stern bench
        p.box("Cushion", (4.3, 0, zg - 0.35), (0.6, 0.55, 0.09), bevel=0.04)                # bow seating
        p.box("Deck", (2.8, 0, 0.32), (2.6, 0.95, 0.02))                                      # sole
    outboard(p, 0.0, 0.25)
    p.shift(-0.45 * L)
    return p


def boat_pontoon():
    """A 24 ft pontoon (7.3 x 2.6 m): two 25 in aluminium tubes, a deck, fence panels with a bow gate, couches and a
    bimini top folded down. Very common on Ray Hubbard lifts and in the marinas."""
    p = Part("SM_ShoreBoat_Pontoon", seed=42)
    L = 7.3
    r = 0.32
    for y in (-0.8, 0.8):
        p.tube("Steel", (0.4, y, r), (L - 0.9, y, r), r, sides=18, caps=False)
        p.lathe("Steel", (L - 0.9, y, r), [(r, 0.0), (r * 0.92, 0.35), (r * 0.6, 0.7), (0.0, 0.85)], sides=18, axis="X")
        p.lathe("Steel", (0.4, y, r), [(r, 0.0), (r, -0.02), (0.0, -0.03)], sides=18, axis="-X")
        p.box("Steel", (L / 2 - 0.2, y, 2 * r + 0.04), (L / 2 - 0.7, 0.05, 0.04))
    zd = 2 * r + 0.1
    p.box("Deck", (L / 2 - 0.1, 0, zd), (L / 2 - 0.2, 1.3, 0.025))
    p.box("Steel", (L / 2 - 0.1, 0, zd - 0.06), (L / 2 - 0.2, 1.32, 0.04))
    # fence: panels 0.76 m high round the deck, a gate at the bow and at the stern-port
    zf = zd + 0.78
    outline = [(0.4, -1.28), (L - 0.4, -1.28), (L - 0.4, -0.45), None, (L - 0.4, 0.45), (L - 0.4, 1.28), (0.9, 1.28), None, (0.4, 0.6), (0.4, -1.28)]
    segs, cur = [], []
    for q in outline:
        if q is None:
            segs.append(cur)
            cur = []
        else:
            cur.append(q)
    segs.append(cur)
    for seg in segs:
        if len(seg) < 2:
            continue
        pts3 = [(x, y, zf) for x, y in seg]
        p.sweep("Steel", pts3, [(0.019, 0.019)] * len(pts3), sides=8)
        for (xa, ya), (xb, yb) in zip(seg, seg[1:]):
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            ln = math.hypot(xb - xa, yb - ya)
            yaw = math.degrees(math.atan2(yb - ya, xb - xa))
            p.box("White", (mx, my, zd + 0.4), (ln / 2, 0.012, 0.32), yaw=yaw, segments=1)
            p.box("TrimGreen", (mx, my, zd + 0.6), (ln / 2, 0.014, 0.04), yaw=yaw, segments=1)
    for x, y, w, d, yaw in ((1.2, 0.95, 1.7, 0.33, 0), (1.2, -0.95, 1.7, 0.33, 0), (L - 1.8, 0.95, 1.2, 0.33, 0), (L - 1.8, -0.95, 1.2, 0.33, 0)):
        p.box("Cushion", (x + w / 2 - 0.4, y, zd + 0.24), (w / 2, d, 0.2), bevel=0.05)
        p.box("Cushion", (x + w / 2 - 0.4, y + math.copysign(0.28, y), zd + 0.55), (w / 2, 0.07, 0.25), bevel=0.04)
    p.box("White", (3.5, 1.0, zd + 0.5), (0.35, 0.28, 0.5), bevel=0.04)                     # helm pod
    p.lathe("Dark", (3.4, 0.95, zd + 1.05), [(0.17, 0.0), (0.17, 0.02), (0.0, 0.02)], sides=16, axis="-X")
    # bimini folded down over the stern: two hoops and the bundled canvas
    for x in (1.6, 1.75):
        p.sweep("Steel", [(x, -1.25, zd + 0.85), (x - 0.3, -1.1, zd + 1.0), (x - 0.35, 1.1, zd + 1.0), (x, 1.25, zd + 0.85)], [(0.012, 0.012)] * 4, sides=6)
    p.sweep("Canvas", [(1.32, -1.1, zd + 1.02), (1.32, 1.1, zd + 1.02)], [(0.1, 0.07)] * 2, sides=10)
    outboard(p, 0.35, zd - 0.25)
    p.shift(-0.5 * L, 0.0, 0.0)
    return p


def boat_pwc():
    """A three-seat personal watercraft (3.35 x 1.25 m), sitting on a drive-on port."""
    p = Part("SM_ShoreBoat_PWC", seed=43)
    st = [(0.0, 0.1, 0.62, 0.48), (0.5, 0.0, 0.7, 0.6), (1.6, 0.0, 0.78, 0.62), (2.5, 0.08, 0.86, 0.5), (3.05, 0.22, 0.78, 0.3), (3.35, 0.45, 0.62, 0.05)]
    p.loft("Plastic", st, n=2.6, sides=20)
    p.loft("Dark", [(0.3, 0.72, 0.78, 0.18), (0.5, 0.72, 0.9, 0.2), (1.6, 0.74, 0.97, 0.22), (1.9, 0.76, 0.93, 0.18)], n=3.0, sides=14)
    p.box("Plastic", (2.3, 0, 0.95), (0.18, 0.2, 0.12), bevel=0.05, pitch=20)
    p.sweep("Dark", [(2.15, -0.38, 1.12), (2.25, 0.0, 1.08), (2.15, 0.38, 1.12)], [(0.015, 0.015)] * 3, sides=8)
    p.box("Dark", (0.05, 0, 0.32), (0.08, 0.16, 0.12), bevel=0.02)                            # jet nozzle
    p.shift(-1.6)
    return p


def pwc_port():
    """A drive-on PWC port (EZ Port 280 class: 156 x 80 x 15 in, 3.96 x 2.03 x 0.38 m), grey polyethylene: two
    side floats with a cupped keel trough between, bow stop, rollers at the entry. Origin at its stern on the water,
    +X toward the dock along the walk; tied alongside by its hinge couplers."""
    p = Part("SM_ShorePWCPort", seed=44)
    L, W, H = 3.96, 2.03, 0.38
    for s in (-1, 1):
        y = s * (W / 2 - 0.3)
        p.loft("Trim", [(0.0, -0.1, H - 0.08, 0.28), (0.3, -0.12, H, 0.3), (L - 0.3, -0.12, H, 0.3), (L, -0.1, H - 0.05, 0.28)], n=4.0, sides=16)
        p.bm.verts.ensure_lookup_table()
        for v in p.bm.verts[-16 * 4:]:
            v.co.y += y
        for x in (0.4, 1.4, 2.4, 3.4):                         # the moulded traction pads
            p.box("Trim", (x, y, H + 0.005), (0.3, 0.22, 0.006))
    p.loft("Trim", [(0.0, 0.02, 0.22, 0.42), (L - 0.4, 0.06, 0.26, 0.42), (L - 0.15, 0.12, 0.38, 0.4)], n=2.0, sides=14)
    for x in (0.25, 0.75, 1.25):                               # entry rollers
        p.tube("Dark", (x, -0.3, 0.2), (x, 0.3, 0.2), 0.05, sides=10)
    p.box("Trim", (L - 0.1, 0, H + 0.12), (0.08, 0.35, 0.12), bevel=0.04)                  # bow stop
    for x in (0.6, L - 0.6):                                   # hinge couplers to the dock side
        p.box("Dark", (x, W / 2 + 0.08, H - 0.12), (0.12, 0.1, 0.07), bevel=0.02)
    p.shift(-L / 2)
    return p


DOCKS = {"A": dock_a, "B": dock_b, "C": dock_c, "D": dock_d, "E": dock_e, "F": dock_f,
         "BH1": boathouse_a, "BH2": boathouse_b, "BH3": boathouse_c,
         "ShedBay": lambda: marina_bay(False), "ShedEnd": lambda: marina_bay(True),
         "RunaboutCovered": lambda: boat_runabout(True), "RunaboutOpen": lambda: boat_runabout(False),
         "Pontoon": boat_pontoon, "PWC": boat_pwc, "PWCPort": pwc_port}


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = os.path.abspath(a[0])
    only = a[a.index("--only") + 1].split(",") if "--only" in a else None
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(out, exist_ok=True)
    stats = {}
    for key, fn in DOCKS.items():
        if only and key not in only:
            continue
        p = fn()
        stats[p.name] = p.export(out)
    shorekit.write_manifest(out, "docks", stats)


if __name__ == "__main__":
    main()
