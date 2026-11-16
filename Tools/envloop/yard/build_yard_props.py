"""Track H (shore plan, Nov 16 2026): yard and shore clutter, about thirty small props that lakefront lots, docks and the
club's boat yard are dressed with, sparse and placed by seed (Bean's choice on Oct 16 2026). Cloud half only: the game
does not load them until Track I's integration places them (docs/envloop/yard/README.md).

Every mesh: origin on the ground at its footprint's centre, +X its front, Z up, metres. Real sizes from catalogues and
common practice are in cards.json (checked by Tools/envloop/docks/checks.py). Colours that vary per yard are per-instance
(slots Plastic, Canvas, Paint); generic only: no logos, badges, plates or brand shapes.

Usage: python3 Tools/envloop/yard/build_yard_props.py <out dir> [--only Kayak,GasGrill]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "docks"))
import shorekit  # noqa: E402
from shorekit import Part  # noqa: E402

import bpy  # noqa: E402


def leg_pair(p, slot, x, y0, y1, z0, z1, r=0.012):
    for y in (y0, y1):
        p.tube(slot, (x, y, z0), (x, y, z1), r, sides=8)


def chair_alu(p, x, y, yaw):
    """A cast-aluminium patio dining chair: 0.58 x 0.6 m, seat 0.45 m, back 0.9 m, sling seat."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def P(dx, dy, z):
        return (x + c * dx - s * dy, y + s * dx + c * dy, z)
    for dx in (-0.25, 0.25):
        for dy in (-0.26, 0.26):
            top = 0.9 if dx < 0 else 0.45
            p.tube("Steel", P(dx, dy, 0.0), P(dx * 0.9, dy, top), 0.012, sides=8)
        p.tube("Steel", P(dx, -0.26, 0.45), P(dx, 0.26, 0.45), 0.01, sides=6)
    for dy in (-0.26, 0.26):
        p.tube("Steel", P(-0.25, dy, 0.45), P(0.25, dy, 0.45), 0.012, sides=8)
        p.tube("Steel", P(-0.18, dy, 0.65), P(0.25, dy, 0.65), 0.012, sides=8)            # arm
    p.box("Canvas", P(0.0, 0.0, 0.455), (0.24, 0.25, 0.008), yaw=yaw)
    p.box("Canvas", P(-0.235, 0.0, 0.69), (0.008, 0.25, 0.2), yaw=yaw, pitch=-8)


def patio_table_set():
    """A 1.2 m round patio dining table (0.74 m high) with four chairs and an umbrella hole."""
    p = Part("SM_Yard_PatioTableSet", seed=101)
    p.lathe("Steel", (0, 0, 0), [(0.3, 0.0), (0.3, 0.02), (0.05, 0.05), (0.03, 0.7), (0.0, 0.7)], sides=16)
    p.lathe("Glass", (0, 0, 0.7), [(0.0, 0.0), (0.6, 0.0), (0.6, 0.02), (0.0, 0.02)], sides=32)
    p.lathe("Steel", (0, 0, 0.7), [(0.6, -0.03), (0.62, -0.03), (0.62, 0.025), (0.6, 0.025)], sides=32)
    for k in range(4):
        a = k * 90.0 + 45.0
        chair_alu(p, 0.85 * math.cos(math.radians(a)), 0.85 * math.sin(math.radians(a)), a + 180)
    return p


def adirondack(p, x, y, yaw):
    """An Adirondack chair (poly lumber): 0.76 wide, 0.9 deep, seat 0.35 m sloping back, back 0.95 m."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def P(dx, dy, z):
        return (x + c * dx - s * dy, y + s * dx + c * dy, z)
    for dy in (-0.3, 0.3):
        p.box("Plastic", P(0.0, dy, 0.25), (0.42, 0.02, 0.06), yaw=yaw, pitch=8)          # side rails
        p.box("Plastic", P(0.33, dy, 0.28), (0.04, 0.02, 0.28), yaw=yaw)                 # front legs
        p.box("Plastic", P(0.05, dy * 1.2, 0.58), (0.38, 0.07, 0.014), yaw=yaw)          # wide arms
    for k in range(6):
        p.box("Plastic", P(0.3 - k * 0.11, 0.0, 0.33 - k * 0.012), (0.045, 0.3, 0.012), yaw=yaw, pitch=8)
    for k in range(7):
        dy = -0.27 + k * 0.09
        h = 0.36 + 0.06 * math.cos(dy * 4)
        p.box("Plastic", P(-0.42 - 0.12, dy, 0.33 + h), (0.012, 0.04, h), yaw=yaw, pitch=-25)


def adirondack_pair():
    """Two Adirondack chairs angled to a small side table: the dock and lawn favourite."""
    p = Part("SM_Yard_AdirondackPair", seed=102)
    adirondack(p, 0.0, -0.55, 15)
    adirondack(p, 0.0, 0.55, -15)
    p.box("Plastic", (0.25, 0.0, 0.4), (0.22, 0.22, 0.015))
    for dx in (-0.18, 0.18):
        for dy in (-0.18, 0.18):
            p.box("Plastic", (0.25 + dx, dy, 0.2), (0.02, 0.02, 0.2))
    return p


def chaise():
    """A chaise lounge (2.0 x 0.7 m), aluminium frame, back raised 45 deg, outdoor cushion."""
    p = Part("SM_Yard_Chaise", seed=103)
    for y in (-0.33, 0.33):
        p.sweep("Steel", [(1.0, y, 0.0), (0.95, y, 0.32), (-0.3, y, 0.32), (-0.95, y, 0.85)], [(0.014, 0.014)] * 4, sides=8)
        p.tube("Steel", (0.0, y, 0.0), (0.0, y, 0.32), 0.014, sides=8)
        p.tube("Steel", (-0.45, y, 0.0), (-0.45, y, 0.42), 0.014, sides=8)
        p.lathe("Dark", (-0.75, y, 0.06), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.035), (0.0, 0.035)], sides=12, axis="Y")
    p.box("Canvas", (0.35, 0, 0.37), (0.65, 0.31, 0.05), bevel=0.03)
    p.box("Canvas", (-0.63, 0, 0.6), (0.38, 0.31, 0.05), bevel=0.03, pitch=-40)
    return p


def kettle_grill():
    """A 22 in kettle grill: 0.57 m bowl on three legs, lid with handle and vent, ash catcher, two wheels."""
    p = Part("SM_Yard_KettleGrill", seed=104)
    z = 0.68
    prof_bowl = [(0.0, -0.27), (0.17, -0.25), (0.25, -0.17), (0.285, -0.06), (0.29, 0.0)]
    p.lathe("Dark", (0, 0, z), prof_bowl, sides=24)
    p.lathe("Dark", (0, 0, z), [(0.29, 0.0), (0.285, 0.08), (0.24, 0.18), (0.15, 0.25), (0.0, 0.27)], sides=24)
    p.lathe("Steel", (0, 0, z + 0.27), [(0.05, 0.0), (0.05, 0.015), (0.0, 0.02)], sides=12)
    p.sweep("Wood", [(0.0, -0.08, z + 0.29), (0.0, 0.08, z + 0.29)], [(0.015, 0.018)] * 2, sides=8)
    for k in range(3):
        a = math.radians(90 + k * 120)
        p.tube("Steel", (0.13 * math.cos(a), 0.13 * math.sin(a), z - 0.22), (0.3 * math.cos(a), 0.3 * math.sin(a), 0.0), 0.012, sides=8)
    p.lathe("Steel", (0, 0, 0.2), [(0.0, 0.0), (0.2, 0.0), (0.2, 0.03), (0.0, 0.03)], sides=16)
    for a in (210, 330):
        x, y = 0.3 * math.cos(math.radians(a)), 0.3 * math.sin(math.radians(a))
        p.lathe("Dark", (x, y, 0.08), [(0.0, -0.025), (0.08, -0.025), (0.08, 0.025), (0.0, 0.025)], sides=14, axis="Y")
    return p


def gas_grill():
    """A three-burner cart gas grill: 1.3 x 0.6 m, cook box 0.9 m up, lid 1.2 m, side shelves, cabinet, wheels, tank."""
    p = Part("SM_Yard_GasGrill", seed=105)
    p.box("Dark", (0, 0, 0.45), (0.3, 0.27, 0.4), bevel=0.01)                                 # cabinet
    p.box("Steel", (0.305, 0, 0.45), (0.005, 0.25, 0.36), bevel=0.003)                         # doors
    p.box("Dark", (0, 0, 0.92), (0.3, 0.33, 0.08), bevel=0.01)                                 # cook box
    for k in range(9):
        a = math.pi * k / 8
        p.box("Steel", (-0.28 * math.cos(a), 0, 1.0 + 0.2 * math.sin(a)), (0.04, 0.32, 0.006), pitch=math.degrees(a) - 90 + 90 * 0)
    p.tube("Steel", (0.32, -0.25, 1.15), (0.32, 0.25, 1.15), 0.012, sides=8)
    for s in (-1, 1):
        p.box("Dark", (0, s * 0.5, 0.92), (0.27, 0.17, 0.012), bevel=0.004)
    p.box("Dark", (0.25, 0, 0.88), (0.05, 0.3, 0.05))
    for y in (-0.15, 0.0, 0.15):
        p.lathe("Steel", (0.31, y, 0.88), [(0.025, 0.0), (0.025, 0.02), (0.0, 0.025)], sides=10, axis="X")
    for x in (-0.25, 0.25):
        p.lathe("Dark", (x, -0.24, 0.05), [(0.0, 0.0), (0.05, 0.0), (0.05, 0.03), (0.0, 0.03)], sides=12, axis="-Y")
    p.lathe("White", (-0.1, 0.0, 0.07), [(0.0, 0.0), (0.15, 0.02), (0.15, 0.36), (0.1, 0.44), (0.02, 0.46)], sides=16)
    return p


def umbrella(open_):
    """A 9 ft (2.7 m) market umbrella: aluminium pole 2.4 m, eight ribs, the canopy open or furled, a base."""
    p = Part("SM_Yard_UmbrellaOpen" if open_ else "SM_Yard_UmbrellaClosed", seed=106)
    p.lathe("Dark", (0, 0, 0), [(0.0, 0.0), (0.25, 0.0), (0.25, 0.04), (0.08, 0.12), (0.03, 0.14)], sides=16)
    p.tube("Steel", (0, 0, 0.1), (0, 0, 2.45), 0.019, sides=10)
    if open_:
        R, zt, ze = 1.37, 2.45, 2.05
        n = 8
        bm = p.bm
        apex = bm.verts.new((0, 0, zt + 0.05))
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            mid = bm.verts.new((0.55 * R * math.cos(a + math.pi / n), 0.55 * R * math.sin(a + math.pi / n), zt - 0.18))
            ring.append(bm.verts.new((R * math.cos(a), R * math.sin(a), ze)))
            ring.append(mid)
        faces = []
        for k in range(n):
            a0, m, a1 = ring[2 * k], ring[2 * k + 1], ring[(2 * k + 2) % (2 * n)]
            faces += [bm.faces.new((apex, a0, m)), bm.faces.new((apex, m, a1))]
            p.tube("Steel", (0, 0, zt - 0.02), tuple(a0.co), 0.006, sides=5)
            p.tube("Steel", (0, 0, 1.75), (0.5 * a0.co.x, 0.5 * a0.co.y, zt - 0.2), 0.005, sides=5)
            # the valance flap between ribs
            v0, v1 = a0.co, a1.co
            faces.append(bm.faces.new((a0, a1, bm.verts.new((v1.x, v1.y, ze - 0.14)), bm.verts.new((v0.x, v0.y, ze - 0.14)))))
        p._faces(faces, "Canvas")
        p.lathe("Canvas", (0, 0, zt + 0.05), [(0.18, 0.0), (0.18, 0.08), (0.0, 0.12)], sides=8)
    else:
        p.lathe("Canvas", (0, 0, 1.0), [(0.03, 0.0), (0.09, 0.3), (0.11, 0.9), (0.07, 1.3), (0.03, 1.45), (0.0, 1.5)], sides=8)
        p.lathe("Canvas", (0, 0, 1.85), [(0.08, 0.0), (0.08, 0.06), (0.0, 0.06)], sides=8)
    return p


def fire_pit():
    """A fire pit ring of stacked limestone blocks (1.1 m across, 0.4 m high) with a steel liner and two benches."""
    p = Part("SM_Yard_FirePit", seed=107)
    n = 14
    for row in range(3):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (row % 2)) / n
            r = 0.5
            p.box("Limestone", (r * math.cos(a), r * math.sin(a), 0.065 + row * 0.13), (0.1, 0.115, 0.062),
                  bevel=0.015, yaw=math.degrees(a) + p.rng.uniform(-4, 4))
    p.lathe("Dark", (0, 0, 0.0), [(0.0, 0.05), (0.38, 0.05), (0.39, 0.4), (0.4, 0.4), (0.4, 0.38)], sides=24)
    for a in (40, 220):
        x, y = 1.6 * math.cos(math.radians(a)), 1.6 * math.sin(math.radians(a))
        p.box("Wood", (x, y, 0.43), (0.22, 0.75, 0.025), yaw=a, bevel=0.005)
        for d in (-0.6, 0.6):
            p.box("Wood", (x - math.sin(math.radians(a)) * d * 1, y + math.cos(math.radians(a)) * d, 0.2), (0.2, 0.04, 0.2), yaw=a)
    return p


def kayak():
    """A 10 ft sit-on-top kayak (3.05 x 0.76 m), rotomoulded: hull, moulded seat well, hatch, carry handles."""
    p = Part("SM_Yard_Kayak", seed=108)
    L = 3.05
    st = []
    for i in range(11):
        f = i / 10
        x = L * f - L / 2
        hw = 0.38 * math.sin(math.pi * min(1.0, 0.04 + f * 0.96)) ** 0.6
        zb = 0.06 * (abs(f - 0.5) * 2) ** 3
        zt = 0.3 + 0.08 * (abs(f - 0.5) * 2) ** 2
        st.append((x, zb, zt, max(hw, 0.02)))
    p.loft("Plastic", st, n=2.4, sides=20)
    p.loft("Dark", [(-0.35, 0.26, 0.31, 0.24), (0.05, 0.24, 0.31, 0.26), (0.45, 0.27, 0.31, 0.2)], n=3.0, sides=14)
    p.lathe("Dark", (0.95, 0, 0.36), [(0.0, 0.0), (0.12, 0.0), (0.12, 0.025), (0.0, 0.03)], sides=16)
    for x in (-1.45, 1.45):
        p.sweep("Dark", [(x, -0.06, 0.32), (x + math.copysign(0.05, x), 0.0, 0.35), (x, 0.06, 0.32)], [(0.01, 0.01)] * 3, sides=6)
    return p


def paddleboard():
    """A 10 ft 6 in stand-up paddleboard (3.2 x 0.81 x 0.15 m) lying flat with its traction pad, and its paddle."""
    p = Part("SM_Yard_Paddleboard", seed=109)
    L = 3.2
    st = []
    for i in range(11):
        f = i / 10
        hw = 0.405 * (math.sin(math.pi * (0.05 + 0.9 * f)) ** 0.5) * (1.0 if f < 0.8 else 1.0 - (f - 0.8) * 2.2)
        st.append((L * f - L / 2, 0.0 + 0.04 * max(0.0, f - 0.8) * 4, 0.15, max(hw, 0.04)))
    p.loft("Plastic", st, n=4.0, sides=20)
    p.box("Dark", (-0.1, 0, 0.152), (0.55, 0.3, 0.004), bevel=0.02)
    p.box("Dark", (-1.3, 0, 0.03), (0.06, 0.006, 0.08))                                       # fin
    p.tube("Dark", (-0.9, 0.5, 0.02), (1.0, 0.5, 0.02), 0.014, sides=8)
    p.box("Dark", (1.12, 0.5, 0.02), (0.16, 0.1, 0.008), bevel=0.01)
    return p


def canoe():
    """A 16 ft canoe (4.9 x 0.9 m) turned over on two sawhorses, as one is stored on a lawn."""
    p = Part("SM_Yard_Canoe", seed=110)
    L = 4.9
    st = []
    for i in range(13):
        f = i / 12
        hw = 0.45 * math.sin(math.pi * (0.03 + 0.94 * f)) ** 0.7
        zg = 0.36 + 0.2 * (abs(f - 0.5) * 2) ** 3
        st.append((L * f - L / 2, 0.0, zg, max(hw, 0.02)))
    p.loft("Plastic", st, n=2.0, sides=16)
    p.bm.verts.ensure_lookup_table()
    for v in p.bm.verts:
        v.co.z = 1.25 - v.co.z                   # turned over: gunwales down at 0.89, keel up at 1.25
    for x in (-1.3, 1.3):
        p.box("Wood", (x, 0, 0.82), (0.045, 0.5, 0.04))
        for dy in (-0.42, 0.42):
            for dx in (-0.12, 0.12):
                p.box("Wood", (x + dx, dy, 0.39), (0.02, 0.04, 0.4), roll=0, pitch=math.degrees(dx * 1.2))
    return p


def boat_trailer():
    """A single-axle bunk trailer for a 19-21 ft boat (empty): galvanized frame 6.7 m with tongue, two carpeted
    bunks, winch stand, fenders, tyres, lights."""
    p = Part("SM_Yard_BoatTrailer", seed=111)
    for y in (-0.5, 0.5):
        p.box("Galv", (-0.4, y, 0.5), (2.6, 0.04, 0.07))
        p.box("Carpet", (-0.6, y * 0.9, 0.66), (2.0, 0.05, 0.05), bevel=0.01)
        p.box("Galv", (-0.6, y * 0.9, 0.58), (0.05, 0.05, 0.08))
    p.sweep("Galv", [(-3.0, -0.5, 0.5), (2.2, -0.05, 0.5), (3.3, 0.0, 0.48)], [(0.04, 0.06)] * 3, sides=4, up=(0, 0, 1))
    p.sweep("Galv", [(-3.0, 0.5, 0.5), (2.2, 0.05, 0.5), (3.3, 0.0, 0.48)], [(0.04, 0.06)] * 3, sides=4, up=(0, 0, 1))
    for x in (-2.5, -1.0, 0.6):
        p.box("Galv", (x, 0, 0.5), (0.04, 0.55, 0.05))
    p.lathe("Galv", (3.35, 0, 0.45), [(0.0, 0.0), (0.05, 0.0), (0.05, 0.06), (0.0, 0.08)], sides=12)
    p.tube("Galv", (2.1, 0, 0.5), (2.1, 0, 1.15), 0.035, sides=8)
    p.box("Steel", (2.15, 0, 1.0), (0.1, 0.08, 0.08))
    p.lathe("Dark", (2.15, 0.1, 1.0), [(0.0, 0.0), (0.06, 0.0), (0.06, 0.05), (0.0, 0.05)], sides=12, axis="Y")
    for y in (-1.0, 1.0):
        p.lathe("Tyre", (-0.9, y, 0.33), [(0.0, -0.09), (0.25, -0.1), (0.33, -0.08), (0.33, 0.08), (0.25, 0.1), (0.0, 0.09)], sides=20, axis="Y")
        p.lathe("Steel", (-0.9, y, 0.33), [(0.0, -0.1), (0.17, -0.1), (0.17, 0.1), (0.0, 0.1)], sides=16, axis="Y")
        p.sweep("Galv", [(-1.35, y * 0.95, 0.45), (-1.2, y * 0.95, 0.7), (-0.6, y * 0.95, 0.7), (-0.45, y * 0.95, 0.45)], [(0.12, 0.004)] * 4, sides=4, up=(0, 0, 1))
        p.box("TailLight", (-3.0, y * 0.7, 0.62), (0.03, 0.08, 0.05))
    return p


def pwc_trailer():
    """A double personal-watercraft trailer (3.9 x 2.3 m), galvanized, four carpeted bunks."""
    p = Part("SM_Yard_PWCTrailer", seed=112)
    for y in (-1.05, 1.05):
        p.box("Galv", (-0.3, y, 0.45), (1.6, 0.035, 0.05))
    for x in (-1.6, -0.4, 0.9):
        p.box("Galv", (x, 0, 0.45), (0.035, 1.1, 0.05))
    p.sweep("Galv", [(1.3, -1.05, 0.45), (2.7, 0.0, 0.45), (3.0, 0.0, 0.44)], [(0.035, 0.05)] * 3, sides=4, up=(0, 0, 1))
    p.sweep("Galv", [(1.3, 1.05, 0.45), (2.7, 0.0, 0.45)], [(0.035, 0.05)] * 2, sides=4, up=(0, 0, 1))
    for y in (-0.85, -0.3, 0.3, 0.85):
        p.box("Carpet", (-0.3, y, 0.55), (1.4, 0.04, 0.04), bevel=0.01)
    for y in (-0.55, 0.55):
        p.tube("Galv", (1.4, y, 0.45), (1.4, y, 0.95), 0.03, sides=8)
    for y in (-1.25, 1.25):
        p.lathe("Tyre", (-0.4, y, 0.28), [(0.0, -0.08), (0.28, -0.08), (0.28, 0.08), (0.0, 0.08)], sides=18, axis="Y")
        p.sweep("Galv", [(-0.75, y, 0.4), (-0.6, y, 0.6), (-0.2, y, 0.6), (-0.05, y, 0.4)], [(0.11, 0.004)] * 4, sides=4, up=(0, 0, 1))
    return p


def suv():
    """A generic mid-size SUV (4.85 x 1.95 x 1.75 m), no badges: body, glasshouse, wheels, lights, roof rails."""
    p = Part("SM_Yard_SUV", seed=113)
    body = [(-2.42, 0.35, 0.95, 0.9), (-2.3, 0.3, 1.0, 0.95), (-1.8, 0.28, 1.05, 0.97), (1.5, 0.28, 1.0, 0.97), (2.25, 0.33, 0.9, 0.93), (2.43, 0.4, 0.75, 0.85)]
    p.loft("Paint", body, n=5.0, sides=24)
    p.loft("Glass", [(-2.3, 0.98, 1.68, 0.8), (-1.6, 1.0, 1.73, 0.84), (0.9, 1.0, 1.72, 0.84), (1.45, 1.0, 1.05, 0.88)], n=6.0, sides=20)
    p.box("Paint", (-0.35, 0, 1.73), (1.6, 0.8, 0.025), bevel=0.02)
    for y in (-0.62, 0.62):
        p.box("Dark", (-0.4, y, 1.78), (1.3, 0.025, 0.02))
    for x in (-1.45, 1.45):
        for y in (-0.86, 0.86):
            p.lathe("Tyre", (x, y, 0.37), [(0.0, -0.12), (0.3, -0.13), (0.37, -0.1), (0.37, 0.1), (0.3, 0.13), (0.0, 0.12)], sides=22, axis="Y")
            p.lathe("Steel", (x, y + math.copysign(0.02, y), 0.37), [(0.0, -0.12), (0.22, -0.12), (0.22, 0.12), (0.0, 0.12)], sides=16, axis="Y")
    for y in (-0.7, 0.7):
        p.box("HeadLight", (2.42, y, 0.82), (0.03, 0.17, 0.05))
        p.box("TailLight", (-2.43, y, 0.95), (0.02, 0.12, 0.07))
    p.box("Dark", (2.44, 0, 0.6), (0.03, 0.55, 0.14))
    p.box("Dark", (-2.44, 0, 0.45), (0.03, 0.8, 0.08))
    return p


def golf_cart():
    """A two-seat golf cart (2.4 x 1.2 x 1.8 m), common on lake lots and at the club."""
    p = Part("SM_Yard_GolfCart", seed=114)
    p.loft("Plastic", [(-1.15, 0.25, 0.55, 0.55), (0.3, 0.2, 0.5, 0.58), (0.9, 0.2, 0.75, 0.56), (1.18, 0.3, 0.65, 0.45)], n=4.0, sides=18)
    p.box("Cushion", (-0.3, 0, 0.75), (0.25, 0.5, 0.06), bevel=0.03)
    p.box("Cushion", (-0.55, 0, 1.0), (0.05, 0.5, 0.2), bevel=0.03)
    for x, y in ((0.75, -0.55), (0.75, 0.55), (-0.62, -0.55), (-0.62, 0.55)):
        p.tube("Steel", (x, y, 0.55 if x > 0 else 0.6), (x * 0.95, y, 1.82), 0.017, sides=8)
    p.box("Plastic", (0.05, 0, 1.85), (0.9, 0.62, 0.035), bevel=0.03)
    p.box("Glass", (0.77, 0, 1.3), (0.006, 0.55, 0.45))
    p.lathe("Dark", (0.55, -0.15, 0.95), [(0.0, 0.0), (0.17, 0.0), (0.17, 0.02), (0.0, 0.02)], sides=16, axis="X")
    for x in (-0.8, 0.82):
        for y in (-0.52, 0.52):
            p.lathe("Tyre", (x, y, 0.23), [(0.0, -0.09), (0.23, -0.1), (0.23, 0.1), (0.0, 0.09)], sides=18, axis="Y")
    return p


def swing_set():
    """A wooden A-frame swing set with a fort, slide and two swings (5.5 x 2.4 x 3.0 m): cedar 4x4s, green roof."""
    p = Part("SM_Yard_SwingSet", seed=115)
    # an A-frame at the far end and a beam 2.4 m up back to the fort
    for s in (-1, 1):
        p.sweep("Wood", [(1.5, s * 1.2, 0.0), (1.5, 0.0, 2.35)], [(0.045, 0.045)] * 2, sides=4, up=(1, 0, 0))
    p.box("Wood", (0.25, 0, 2.38), (1.3, 0.045, 0.09))
    for y in (-0.55, 0.55):                                                                     # fort posts
        for x in (-1.6, -0.5):
            p.box("Wood", (x, y, 1.35), (0.045, 0.045, 1.35))
    p.decking(-1.65, -0.45, -0.6, 0.6, 1.5, across=False, board=0.14, t=0.025, slot="Wood")
    p.box("Plastic", (-1.05, -0.62, 2.85), (0.62, 0.02, 0.28), roll=55)
    p.box("Plastic", (-1.05, 0.62, 2.85), (0.62, 0.02, 0.28), roll=-55)
    p.rail([(-1.62, -0.58), (-0.48, -0.58)], 1.5, h=0.7, post_every=1.2)
    p.rail([(-1.62, 0.58), (-0.48, 0.58)], 1.5, h=0.7, post_every=1.2)
    # slide down toward -X
    p.loft("Plastic", [(-1.7, 1.42, 1.5, 0.25), (-3.6, 0.25, 0.32, 0.25), (-3.9, 0.22, 0.28, 0.25)], n=6.0, sides=12)
    # ladder up the +Y side? climbing rungs on the -X-side posts
    for k in range(5):
        p.tube("Wood", (-0.45, -0.55, 0.28 * (k + 1)), (-0.45, 0.55, 0.28 * (k + 1)), 0.02, sides=6)
    for y in (-0.4, 0.4):                                                                       # swings
        for dy in (-0.22, 0.22):
            p.tube("Steel", (0.6, y + dy, 2.32), (0.6, y + dy, 0.45), 0.004, sides=4, caps=False)
        p.box("Plastic", (0.6, y, 0.43), (0.08, 0.24, 0.015), bevel=0.01)
    return p


def trampoline():
    """A 14 ft (4.3 m) round trampoline with a safety net on eight curved poles."""
    p = Part("SM_Yard_Trampoline", seed=116)
    R = 2.13
    p.lathe("Dark", (0, 0, 0.9), [(0.0, 0.0), (R - 0.18, 0.0), (R - 0.18, 0.005), (0.0, 0.005)], sides=40)
    p.lathe("Plastic", (0, 0, 0.9), [(R - 0.2, 0.0), (R + 0.05, 0.0), (R + 0.05, 0.05), (R - 0.2, 0.05)], sides=40)
    n = 8
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        p.sweep("Galv", [(R * c * 0.9, R * s * 0.9, 0.0), (R * c, R * s, 0.15), (R * c, R * s, 0.88)], [(0.019, 0.019)] * 3, sides=8)
        p.sweep("Galv", [(R * c, R * s, 0.9), (R * 1.03 * c, R * 1.03 * s, 1.8), (R * c, R * s, 2.7)], [(0.016, 0.016)] * 3, sides=8)
    bm = p.bm
    rows = []
    for zf in (0.95, 2.6):
        rows.append([bm.verts.new((R * math.cos(2 * math.pi * k / 32), R * math.sin(2 * math.pi * k / 32), zf)) for k in range(32)])
    faces = [bm.faces.new((rows[0][k], rows[0][(k + 1) % 32], rows[1][(k + 1) % 32], rows[1][k])) for k in range(32)]
    p._faces(faces, "Net")
    p.sweep("Galv", [(R * math.cos(2 * math.pi * k / 32), R * math.sin(2 * math.pi * k / 32), 0.88) for k in range(33)], [(0.022, 0.022)] * 33, sides=8)
    return p


def flagpole():
    """A 20 ft (6.1 m) residential flagpole: tapered aluminium, gold ball, a flag hanging limp, halyard and cleat."""
    p = Part("SM_Yard_Flagpole", seed=117)
    p.tube("Steel", (0, 0, 0.0), (0, 0, 6.1), 0.044, 0.03, sides=14)
    p.lathe("Gold", (0, 0, 6.1), [(0.0, 0.0), (0.04, 0.02), (0.06, 0.06), (0.04, 0.1), (0.0, 0.12)], sides=12)
    p.lathe("Concrete", (0, 0, 0.0), [(0.0, 0.0), (0.25, 0.0), (0.25, 0.04), (0.0, 0.05)], sides=16)
    # a 3 x 5 ft flag hanging in light air: a folded strip down the pole
    bm = p.bm
    cols = []
    for i in range(7):
        f = i / 6
        x = 0.05 + 0.25 * f
        y = 0.05 * math.sin(f * 6.0)
        cols.append([bm.verts.new((x, y, 5.95 - f * 0.25)), bm.verts.new((x, y, 5.95 - 0.91 - f * 0.3))])
    faces = [bm.faces.new((a[0], b[0], b[1], a[1])) for a, b in zip(cols, cols[1:])]
    p._faces(faces, "Canvas")
    p.tube("White", (0.035, 0, 6.0), (0.035, 0, 1.2), 0.003, sides=4, caps=False)
    return p


def pool_fence():
    """A removable pool safety fence panel: 4 ft (1.22 m) high mesh, 15 ft (4.6 m) long, poles every 0.9 m."""
    p = Part("SM_Yard_PoolFence", seed=118)
    L = 4.6
    n = 5
    for k in range(n + 1):
        y = -L / 2 + L * k / n
        p.tube("Galv", (0, y, -0.1), (0, y, 1.22), 0.016, sides=8)
        p.lathe("Dark", (0, y, 1.22), [(0.017, 0.0), (0.017, 0.02), (0.0, 0.03)], sides=8)
    p.box("Net", (0, 0, 0.66), (0.003, L / 2, 0.52))
    p.box("Dark", (0, 0, 0.13), (0.006, L / 2, 0.03))
    p.box("Dark", (0, 0, 1.19), (0.006, L / 2, 0.03))
    return p


def planter():
    """A large glazed planter (0.6 m) with a boxwood ball, a porch or dock pair."""
    p = Part("SM_Yard_Planter", seed=119)
    p.lathe("Plastic", (0, 0, 0), [(0.0, 0.0), (0.2, 0.0), (0.27, 0.15), (0.3, 0.42), (0.29, 0.55), (0.25, 0.55), (0.0, 0.5)], sides=20)
    bm_r = 0.36
    p.lathe("Crown", (0, 0, 0.52), [(0.0, 0.0), (bm_r * 0.7, 0.04), (bm_r, 0.3), (bm_r * 0.75, 0.56), (0.0, 0.66)], sides=14)
    return p


def raised_bed():
    """A cedar raised vegetable bed, 2.4 x 1.2 x 0.4 m, soil and a few plants."""
    p = Part("SM_Yard_RaisedBed", seed=120)
    for k in range(3):
        z = 0.07 + k * 0.14
        for y in (-0.6, 0.6):
            p.box("Wood", (0, y, z), (1.2, 0.019, 0.07))
        for x in (-1.2, 1.2):
            p.box("Wood", (x, 0, z), (0.019, 0.6, 0.07))
    p.box("Dark", (0, 0, 0.34), (1.18, 0.58, 0.02))                                           # soil
    for k in range(6):
        x, y = -0.9 + k * 0.36, ((k % 2) - 0.5) * 0.5
        p.lathe("Crown", (x, y, 0.35), [(0.0, 0.0), (0.12, 0.08), (0.16, 0.22), (0.0, 0.36)], sides=8)
    return p


def trash_cart():
    """A 96 gallon wheeled refuse cart (0.74 x 0.86 x 1.1 m) with its lid."""
    p = Part("SM_Yard_TrashCart", seed=121)
    p.loft("Plastic", [(-0.36, 0.06, 1.02, 0.3), (0.36, 0.06, 1.02, 0.36)], n=5.0, sides=16)
    p.bm.verts.ensure_lookup_table()
    p.box("Plastic", (0.02, 0, 1.06), (0.42, 0.38, 0.03), bevel=0.015)
    p.tube("Dark", (-0.44, -0.3, 1.0), (-0.44, 0.3, 1.0), 0.016, sides=8)
    for y in (-0.33, 0.33):
        p.lathe("Tyre", (-0.36, y, 0.13), [(0.0, -0.03), (0.13, -0.04), (0.13, 0.04), (0.0, 0.03)], sides=16, axis="Y")
    return p


def mailbox():
    """A rural mailbox on a 4x4 post (box top 1.1 m: USPS height 41-45 in), with its flag."""
    p = Part("SM_Yard_Mailbox", seed=122)
    p.box("Wood", (0, 0, 0.5), (0.045, 0.045, 0.55))
    p.box("Wood", (0.1, 0, 0.98), (0.3, 0.06, 0.02))
    p.box("Paint", (0.1, 0, 1.06), (0.24, 0.085, 0.06))
    p.loft("Paint", [(-0.14, 1.04, 1.18, 0.085), (0.34, 1.04, 1.18, 0.085)], n=2.0, sides=14)
    p.box("SafetyRed", (0.0, -0.095, 1.17), (0.005, 0.005, 0.08))
    p.box("SafetyRed", (0.04, -0.095, 1.24), (0.04, 0.004, 0.025))
    return p


def wheelbarrow():
    """A 6 cu ft contractor wheelbarrow (1.5 x 0.66 m): steel tray, wooden handles, one pneumatic wheel."""
    p = Part("SM_Yard_Wheelbarrow", seed=123)
    p.loft("Paint", [(-0.3, 0.42, 0.62, 0.3), (0.25, 0.3, 0.65, 0.33), (0.4, 0.42, 0.67, 0.2)], n=3.0, sides=16)
    for y in (-0.25, 0.25):
        p.tube("Wood", (0.5, y * 0.25, 0.2), (-0.68, y, 0.5), 0.018, sides=8)
        p.tube("Steel", (-0.3, y, 0.0), (-0.3, y, 0.42), 0.014, sides=8)
        p.tube("Dark", (-0.68, y, 0.5), (-0.8, y, 0.53), 0.02, sides=8)
    p.lathe("Tyre", (0.5, 0, 0.2), [(0.0, -0.05), (0.2, -0.05), (0.2, 0.05), (0.0, 0.05)], sides=18, axis="Y")
    return p


def hose_reel():
    p = Part("SM_Yard_HoseReel", seed=124)
    for y in (-0.2, 0.2):
        p.lathe("Plastic", (0, y, 0.4), [(0.0, -0.01), (0.28, -0.01), (0.28, 0.01), (0.0, 0.01)], sides=18, axis="Y")
        p.box("Plastic", (0, y, 0.2), (0.25, 0.02, 0.2))
    p.lathe("TrimGreen", (0, 0, 0.4), [(0.0, -0.18), (0.2, -0.18), (0.2, 0.18), (0.0, 0.18)], sides=18, axis="Y")
    p.tube("Plastic", (0, -0.2, 0.85), (0, 0.2, 0.85), 0.015, sides=8)
    for y in (-0.2, 0.2):
        p.tube("Plastic", (0, y, 0.4), (0, y, 0.85), 0.012, sides=6)
    return p


def cooler():
    """A 70 qt marine cooler (0.86 x 0.44 x 0.46 m), white with rope handles."""
    p = Part("SM_Yard_Cooler", seed=125)
    p.box("White", (0, 0, 0.2), (0.43, 0.22, 0.2), bevel=0.03)
    p.box("White", (0, 0, 0.43), (0.44, 0.23, 0.035), bevel=0.02)
    for x in (-0.47, 0.47):
        p.sweep("Dark", [(x * 0.96, -0.08, 0.3), (x, 0.0, 0.25), (x * 0.96, 0.08, 0.3)], [(0.008, 0.008)] * 3, sides=6)
    return p


def bird_bath():
    p = Part("SM_Yard_BirdBath", seed=126)
    p.lathe("Concrete", (0, 0, 0), [(0.0, 0.0), (0.2, 0.0), (0.18, 0.06), (0.08, 0.12), (0.06, 0.6), (0.1, 0.66), (0.3, 0.7), (0.32, 0.74), (0.28, 0.74), (0.0, 0.7)], sides=20)
    return p


def garden_bench():
    """A teak garden bench (1.5 m, seat 0.45 m, back 0.9 m)."""
    p = Part("SM_Yard_Bench", seed=127)
    for k in range(4):
        p.box("Wood", (0.2 - k * 0.1, 0, 0.45), (0.04, 0.75, 0.015), bevel=0.004)
    for k in range(6):
        p.box("Wood", (-0.18 - 0.02 * k / 6, -0.6 + k * 0.24, 0.72), (0.015, 0.035, 0.24), pitch=-10)
    p.box("Wood", (-0.21, 0, 0.92), (0.025, 0.76, 0.04), bevel=0.005)
    for y in (-0.73, 0.73):
        p.box("Wood", (0.2, y, 0.32), (0.03, 0.03, 0.32))
        p.box("Wood", (-0.2, y, 0.47), (0.03, 0.03, 0.47))
        p.box("Wood", (0.0, y, 0.65), (0.25, 0.035, 0.02))
        p.box("Wood", (0.0, y, 0.1), (0.22, 0.02, 0.03))
    return p


def picnic_table():
    """A 6 ft wooden picnic table with attached benches (1.83 x 1.6 m, top 0.76 m)."""
    p = Part("SM_Yard_PicnicTable", seed=128)
    for k in range(5):
        p.box("Wood", (-0.36 + k * 0.18, 0, 0.75), (0.07, 0.915, 0.019), bevel=0.004)
    for s in (-1, 1):
        for k in range(2):
            p.box("Wood", (s * (0.62 + k * 0.15), 0, 0.45), (0.07, 0.915, 0.019), bevel=0.004)
        for y in (-0.7, 0.7):
            p.sweep("Wood", [(s * 0.78, y, 0.0), (0.0, y, 0.73)], [(0.019, 0.07)] * 2, sides=4, up=(0, 1, 0))
    for y in (-0.7, 0.7):
        p.box("Wood", (0, y, 0.42), (0.85, 0.019, 0.045))
        p.box("Wood", (0, y, 0.715), (0.4, 0.019, 0.045))
    return p


def basketball_hoop():
    """A portable basketball hoop (rim at 10 ft, 3.05 m): weighted base, pole, 44 in backboard, rim and net."""
    p = Part("SM_Yard_BasketballHoop", seed=129)
    p.box("Plastic", (-0.3, 0, 0.15), (0.6, 0.35, 0.15), bevel=0.05)
    p.sweep("Galv", [(0.0, 0, 0.25), (0.15, 0, 2.0), (0.2, 0, 3.3)], [(0.045, 0.045)] * 3, sides=10)
    p.box("Glass", (0.4, 0, 3.3), (0.01, 0.56, 0.36))
    for z in (2.94, 3.66):
        p.box("Dark", (0.4, 0, z), (0.02, 0.58, 0.02))
    for y in (-0.58, 0.58):
        p.box("Dark", (0.4, y, 3.3), (0.02, 0.02, 0.38))
    p.lathe("SafetyRed", (0.64, 0, 3.05), [(0.225, -0.008), (0.235, -0.008), (0.235, 0.008), (0.225, 0.008), (0.225, -0.008)], sides=20)
    p.lathe("Net", (0.64, 0, 3.05), [(0.225, 0.0), (0.17, -0.25), (0.15, -0.42)], sides=12)
    return p


def lawn_mower():
    p = Part("SM_Yard_LawnMower", seed=130)
    p.loft("Plastic", [(-0.3, 0.08, 0.3, 0.27), (0.3, 0.08, 0.3, 0.27)], n=4.0, sides=14)
    p.box("Dark", (0.0, 0, 0.36), (0.12, 0.12, 0.08), bevel=0.02)
    for y in (-0.22, 0.22):
        p.tube("Steel", (-0.25, y, 0.25), (-0.85, y, 0.95), 0.012, sides=8)
        for x in (-0.22, 0.22):
            p.lathe("Tyre", (x, y * 1.25, 0.1), [(0.0, -0.025), (0.1, -0.03), (0.1, 0.03), (0.0, 0.025)], sides=14, axis="Y")
    p.tube("Dark", (-0.85, -0.22, 0.95), (-0.85, 0.22, 0.95), 0.014, sides=8)
    p.box("Dark", (-0.5, 0, 0.35), (0.22, 0.2, 0.15), bevel=0.04)
    return p


def hammock():
    """A steel hammock stand (4.6 m) with a rope hammock."""
    p = Part("SM_Yard_Hammock", seed=131)
    p.sweep("Galv", [(-2.3, 0, 1.25), (-2.0, 0, 0.06), (2.0, 0, 0.06), (2.3, 0, 1.25)], [(0.03, 0.03)] * 4, sides=8)
    for x in (-2.0, 2.0):
        p.box("Galv", (x, 0, 0.03), (0.04, 0.4, 0.03))
    pts = []
    for i in range(13):
        f = i / 12
        x = -2.15 + 4.3 * f
        z = 1.2 - 0.75 * math.sin(math.pi * f) ** 0.8
        pts.append((x, 0, z))
    p.sweep("Canvas", pts, [(0.45 * math.sin(math.pi * (i / 12)) ** 0.5 + 0.02, 0.01) for i in range(13)], sides=4, up=(0, 0, 1))
    return p


PROPS = {"PatioTableSet": patio_table_set, "AdirondackPair": adirondack_pair, "Chaise": chaise, "KettleGrill": kettle_grill,
         "GasGrill": gas_grill, "UmbrellaOpen": lambda: umbrella(True), "UmbrellaClosed": lambda: umbrella(False),
         "FirePit": fire_pit, "Kayak": kayak, "Paddleboard": paddleboard, "Canoe": canoe, "BoatTrailer": boat_trailer,
         "PWCTrailer": pwc_trailer, "SUV": suv, "GolfCart": golf_cart, "SwingSet": swing_set, "Trampoline": trampoline,
         "Flagpole": flagpole, "PoolFence": pool_fence, "Planter": planter, "RaisedBed": raised_bed, "TrashCart": trash_cart,
         "Mailbox": mailbox, "Wheelbarrow": wheelbarrow, "HoseReel": hose_reel, "Cooler": cooler, "BirdBath": bird_bath,
         "Bench": garden_bench, "PicnicTable": picnic_table, "BasketballHoop": basketball_hoop, "LawnMower": lawn_mower,
         "Hammock": hammock}


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = os.path.abspath(a[0])
    only = a[a.index("--only") + 1].split(",") if "--only" in a else None
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(out, exist_ok=True)
    stats = {}
    for key, fn in PROPS.items():
        if only and key not in only:
            continue
        p = fn()
        stats[p.name] = p.export(out)
    shorekit.write_manifest(out, "yard", stats)


if __name__ == "__main__":
    main()
