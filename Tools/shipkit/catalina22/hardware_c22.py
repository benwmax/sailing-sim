"""The Catalina 22's deck hardware and running rigging (docs/c22-7): where every fitting stands and where every line
runs, from hardware_c22.json, on the deck, cabin, rig and sails of slices 2 to 5; and the checks that hold them.

    python3 -I hardware_c22.py            (needs numpy and mathutils: Blender's Python, or pip install mathutils)

Frame: the game's body frame (X forward, Y starboard, Z up), metres. Nothing here needs Blender: the kit parts' sockets
are copied from the kit (KIT below, at the sizes used), and build_hardware_c22.py checks the copies against the parts it
builds. build_hardware_c22.py meshes what fittings() and lines() return.

A fitting is the kit part's name, its size or options, its origin and its axes (the kit's X along the part, Z out of
the surface it stands on), and whether its light copy is used. A line is a polyline, a diameter and a slot; each belongs
to a state of the boat:

  rest    at her mooring: the main flaked under its cover on a centred boom, the headsails bagged, the halyards made
          fast and coiled, the jib halyard clipped to the pulpit and the main's to the headboard at the gooseneck
  up      close-hauled on starboard tack under main and the high-cut 140% genoa (slice 5's MainSet and GenoaSet)
  jib     the same under main and the 90% working jib (MainSet and JibSet)
  reef    reefed main and the working jib (MainReefed and JibSet)
  run     on a run under main and spinnaker (MainRun and SpinnakerSet), the pole squared to starboard

The halyards' falls, cleats and coils are in every state ("all"); the sheets, the mainsheet, the vang and the topping
lift follow their state's sails and boom.
"""
import json
import math
import os
import random
import re
import sys

import numpy as np
try:
    from mathutils import Vector
except ImportError:     # the bpy module carries mathutils but only hands it out once bpy is loaded
    import bpy  # noqa: F401
    from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
KIT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "boatkit"))
if KIT_DIR not in sys.path:
    sys.path.insert(0, KIT_DIR)
import bk_ropework as RW  # noqa: E402  (plain maths: mathutils only)
import deck_c22 as D  # noqa: E402
import hull_c22 as H  # noqa: E402
import rig_c22 as RC  # noqa: E402
import sails_c22 as SC  # noqa: E402

HW = json.load(open(os.path.join(HERE, "hardware_c22.json")))
RP = HW["rope"]
STATES = ("rest", "up", "jib", "reef", "run")
BOOM_DEG = {"rest": 0.0, "up": SC.MS["states"]["Set"]["boom_deg"], "jib": SC.MS["states"]["Set"]["boom_deg"],
            "reef": SC.MS["states"]["Reefed"]["boom_deg"], "run": SC.MS["states"]["Run"]["boom_deg"]}
TINY = 0.1              # the share of their triangles the padeyes and blocks keep: their full copies are 6,700 to
                        # 29,000 triangles each (a padeye more than a winch), and each state carries its own blocks
CLEAR = 0.01            # the least gap a line keeps to anything it isn't meant to touch (the sails' check's floor)
END = 0.10              # the length at each end of a line that is its fitting's, where it may meet the wires that
                        # share that fitting (the halyards and the forestay at the masthead, the lift and the backstay)

# The kit's sockets at the sizes used here (kit frame: X along the part, Y across, Z up, origin on its base), as
# bk_parts builds them: build_hardware_c22.py compares each with the part it builds and fails if one moved.
KIT = {
    "WinchPlain": {"Drum": (0.0, 0.028, 0.06), "Tail": (0.0, -0.028, 0.06), "Handle": (0.0, 0.0, 0.095)},
    "HornCleat150": {"Hole": (0.0, 0.0, 0.019), "HornAft": (-0.075, 0.0, 0.04), "HornFwd": (0.075, 0.0, 0.04),
                     "Wrap": (0.0, 0.0, 0.039)},
    "HornCleat200": {"Hole": (0.0, 0.0, 0.025), "HornAft": (-0.1, 0.0, 0.054), "HornFwd": (0.1, 0.0, 0.054),
                     "Wrap": (0.0, 0.0, 0.053)},
    "JibTrack": {"Sheave": (0.01, 0.0, 0.045), "CarFwd": (0.045, 0.0, 0.026)},
    "Traveler": {"Car": (0.0, 0.0, 0.04)},
    "Fiddle40": {"Head": (0.0, 0.0, 0.0), "LineIn": (0.02, 0.0, -0.06), "LineOut": (-0.02, 0.0, -0.06),
                 "LineIn2": (0.013, 0.0, -0.097), "LineOut2": (-0.013, 0.0, -0.097)},
    "FiddleCam": {"Head": (0.0, 0.0, 0.0), "LineIn": (0.02, 0.0, -0.06), "LineOut": (-0.02, 0.0, -0.06),
                  "LineIn2": (0.013, 0.0, -0.097), "LineOut2": (-0.013, 0.0, -0.097), "Becket": (0.0, 0.0, -0.129),
                  "CamLead": (0.041, 0.0, -0.068)},
    "Block29": {"Head": (0.0, 0.0, 0.0), "LineIn": (0.014, 0.0, -0.031), "LineOut": (-0.014, 0.0, -0.031)},
    "Block40": {"Head": (0.0, 0.0, 0.0), "LineIn": (0.02, 0.0, -0.06), "LineOut": (-0.02, 0.0, -0.06)},
    "Padeye": {"Eye": (0.0, 0.0, 0.021)},
    "Stanchion": {"LifelineTop": (0.0, 0.0, 0.602)},
    "Fairlead": {"Line": (0.0, 0.0, 0.008)},
    "CamCleat": {"Line": (0.0, 0.0, 0.0108), "Lead": (-0.0221, 0.0, 0.0108)},
}
CLEAT_FIT = lambda L: dict(L=L, h_under=0.19 * L, h_top=0.30 * L, half_w=0.093 * L, foot_x=0.185 * L)


def V(p):
    return Vector((float(p[0]), float(p[1]), float(p[2])))


# ------------------------------------------------------------------ surfaces

def cockpit(x, y):
    """The cockpit's floor under (x, y): a seat or the footwell's sole, or None outside the opening."""
    x0, x1 = D.CK["x"]
    if x0 < x < x1 and abs(y) < D.CK["half_width"]:
        return D.seat_z(x) if abs(y) > D.CK["footwell_half_width"] else D.CK["sole_z"]
    return None


def on_lid(x, y):
    x0, x1 = D.PT["x"]
    return x0 <= x <= x1 and abs(y) <= D.trunk_edge(x) - D.PT["inset"]


def surface(x, y):
    """What a fitting or a lying line rests on at (x, y): the cockpit's seats and sole, the deck, the trunk's top and
    the pop-top's lid (lid_rise proud of the top)."""
    c = cockpit(x, y)
    if c is not None:
        return c
    z = SC.floor_z(x, y)
    if on_lid(x, y):
        z += D.PT["lid_rise"]
    return z


def normal(x, y, h=0.01):
    zx = (surface(x + h, y) - surface(x - h, y)) / (2 * h)
    zy = (surface(x, y + h) - surface(x, y - h)) / (2 * h)
    return Vector((-zx, -zy, 1.0)).normalized()


def edge_y(x, inset):
    """y of a point `inset` in from the deck's edge (the rubrail's outer face) at x."""
    return H.half_beam(x) - inset


# ------------------------------------------------------------------ fittings

class Fit:
    """A kit part placed: origin o and unit axes X, Y, Z (right-handed) in the game frame."""

    def __init__(self, name, kit, o, X, Z, size=None, light=False, kw=None, socks=None, group="fittings"):
        Z = V(Z).normalized()
        X = (V(X) - Z * V(X).dot(Z)).normalized()
        self.name, self.kit, self.size, self.light, self.kw = name, kit, size, light, kw or {}
        self.o, self.X, self.Z = V(o), X, Z
        self.Y = Z.cross(X)
        self.local = socks if socks is not None else KIT.get(kit + (size or "") if kit == "HornCleat" else kit, {})
        self.group = group

    def p(self, loc):
        # the kit's local y lands on -Y here: build_rig_c22.kit_frame keeps each part unmirrored in Blender's frame,
        # whose Y is this frame's mirrored
        return self.o + self.X * loc[0] - self.Y * loc[1] + self.Z * loc[2]

    def s(self, name):
        return self.p(self.local[name])


def on(name, kit, x, y, along=(1, 0, 0), dz=0.0, **kw):
    """A fitting standing on the surface at (x, y), its X along `along` (projected onto the surface)."""
    n = normal(x, y)
    return Fit(name, kit, (x, y, surface(x, y) + dz), along, n, **kw)


def hanging(name, kit, head, toward, xdir=(1, 0, 0), **kw):
    """A block hung from `head` (its kit Z pointing back up from the body to the head), its body toward `toward`."""
    Z = (V(head) - V(toward)).normalized()
    return Fit(name, kit, head, V(xdir), Z, **kw)


def sides():
    return ((1, "S"), (-1, "P"))


SPIN_QUARTER = 45.0     # degrees round the mast's oval from its front to starboard: the spinnaker halyard's fall and cleat


def mast_quarter(deg, out):
    """A point `out` off the mast's oval section at `deg` round from its front (positive to starboard), and the
    section's outward normal there (z = 0)."""
    a = math.radians(deg)
    nrm = Vector((math.cos(a) / (RC.A / 2), math.sin(a) / (RC.B / 2), 0)).normalized()
    return Vector((RC.MAST_X + (RC.A / 2) * math.cos(a), (RC.B / 2) * math.sin(a), 0.0)) + nrm * out, nrm


def winch_place(sd):
    W = HW["winch"]
    return W["x"], sd * (D.CK["half_width"] + W["out"])


def pulpit_plan():
    """The bow pulpit drawn to her bow: the hoop's plan from its aft end on one side round the nose to the other
    ((x, y) in the game frame), its legs' feet, and its aft end's x. The hoop keeps 'rail_in' inside the deck's edge,
    no wider than its aft legs, and rounds to a nose of radius nose_r at nose_x."""
    P, LL = HW["lifelines"]["pulpit"], HW["lifelines"]
    xa, xn, rn = P["aft_x"], P["nose_x"], P["nose_r"]
    w2 = edge_y(xa + 0.02, LL["in"])

    def hw(x):
        h = min(w2, edge_y(x, P["rail_in"]))
        if x > xn - rn:
            h = min(h, math.sqrt(max(0.0, rn * rn - (x - (xn - rn)) ** 2)))
        return h
    xs = [xa + (xn - xa) * i / 30 for i in range(31)]
    side = [(x, hw(x)) for x in xs]
    for _ in range(4):                                     # round the corner where the nose meets the deck's line
        side = [side[0]] + [(side[i][0], (side[i - 1][1] + 2 * side[i][1] + side[i + 1][1]) / 4)
                            for i in range(1, len(side) - 1)] + [side[-1]]
    hoop = [(x, y) for x, y in side[:-1]] + [(xn, 0.0)] + [(x, -y) for x, y in reversed(side[:-1])]
    xl = xa + P["legs"][1] * (xn - xa)
    legs = [(xa + P["legs"][0], s * w2) for s in (1, -1)] + [(xl, s * edge_y(xl, LL["in"])) for s in (1, -1)]
    return xa, hoop, legs


def rail_paths():
    """The pulpit's and the stern rail's tubes (rails and legs) in the game frame, as polylines: what the lines keep
    clear of."""
    F = by_name(fittings())
    out = {}
    bp = F["BowPulpit"]
    hoop = [bp.p((x, y, 0.61)) for x, y in bp.kw["hoop"]]
    out["PulpitRail"] = [tuple(p) for p in hoop]
    for k, (x, y, z) in enumerate(bp.kw["legs"]):
        foot = bp.p((x, y, z + 0.01))
        top = min(hoop, key=lambda q: (q - bp.p((x, y, 0.61))).length)
        out[f"PulpitLeg{k}"] = [tuple(foot), tuple(top)]
    sr = F["SternRail"]
    w, dp = sr.kw["width"] / 2, sr.kw["depth"]
    half = [(0.0, -w), (-0.7 * dp, -w)] + [(-0.7 * dp + 0.3 * dp * math.cos(a), -w + 0.3 * dp + 0.3 * dp * math.sin(a))
                                           for a in np.linspace(-math.pi / 2, -math.pi, 8)[1:]] + [(-dp, -0.3 * w)]
    path = half + [(x, -y) for x, y in reversed(half)]
    rail = [sr.p((x, y, 0.61)) for x, y in path]
    out["SternRailTube"] = [tuple(p) for p in rail]
    for k, (x, y, z) in enumerate(sr.kw["legs"]):
        top = min(rail, key=lambda q: (q - sr.p((x, y, 0.61))).length)
        out[f"SternRailLeg{k}"] = [tuple(sr.p((x, y, z + 0.01))), tuple(top)]
    return out


def pushpit_dims():
    LL = HW["lifelines"]
    depth = LL["pushpit"][1]
    xf = H.TRANSOM_X + depth
    w = 2 * edge_y(xf - 0.02, LL["in"])
    return xf, w, depth


def fittings():
    """Every kit fitting of slice 6, as Fit objects."""
    F = []
    W, WC = HW["winch"], HW["winch_cleat"]
    for sd, t in sides():
        x, y = winch_place(sd)
        F.append(on("Winch_" + t, "WinchPlain", x, y, size=W["size"]))
        # both winches turn clockwise, so a line from forward comes onto the drum's starboard side and one from aft
        # (the spinnaker's sheet and guy) onto its port side: each cleat stands on its winch's forward lines' side,
        # clear of the line from aft (outboard to starboard, a little inboard to port)
        F.append(on("WinchCleat_" + t, "HornCleat", x + WC["dx"], y + sd * WC["out"][t], size=WC["size"], light=True))
        # the genoa's track along the deck's edge, its car in its middle at car_x
        G = HW["genoa_track"]
        cx = 0.5 * (G["x"][0] + G["x"][1])               # the car is in the track's middle
        y0, y1 = edge_y(cx - 0.05, G["in"]), edge_y(cx + 0.05, G["in"])
        F.append(on("GenoaTrack_" + t, "JibTrack", cx, sd * edge_y(cx, G["in"]), along=(0.1, sd * (y1 - y0), 0), light=True,
                    kw={"length": G["x"][1] - G["x"][0]}))
        J = HW["jib_track"]
        F.append(on("JibTrack_" + t, "JibTrack", 0.5 * (J["x"][0] + J["x"][1]), sd * J["y"], light=True,
                    kw={"length": J["x"][1] - J["x"][0]}))
        F.append(on("JibFairlead_" + t, "Fairlead", J["corner"][0], sd * J["corner"][1], light=False))
        F.append(on("JibTurnPadeye_" + t, "Padeye", J["turn"][0], sd * J["turn"][1], light=TINY))
        # the quarter blocks for the spinnaker's sheet and guy: a padeye on the aft deck's corner, a block on it
        q = HW["spinnaker"]["quarter_block"]
        F.append(on("QuarterPadeye_" + t, "Padeye", q[0], sd * edge_y(q[0], q[1]), light=TINY))
    T = HW["traveller"]
    tz = D.seat_z(T["x"]) + 0.002
    F.append(Fit("Traveller", "Traveler", (T["x"], 0.0, tz), (0, 1, 0), (0, 0, 1), kw={"length": T["length"]}))
    # the cleats
    C = HW["cleats"]
    F.append(on("BowCleat", "HornCleat", C["bow"][0], 0.0, size=C["bow"][1], light=True))
    for sd, t in sides():
        sx, syy, ss = C["stern"]
        F.append(on("SternCleat_" + t, "HornCleat", sx, sd * syy, size=ss, light=True))
    # the mast's halyard cleats: on its sides (main to port, jib to starboard) and the spinnaker's forward of the jib's
    hz = HW["halyards"]["cleat_z"]
    zs = RC.step_z()
    F.append(Fit("MainHalyardCleat", "HornCleat", (RC.MAST_X, -(RC.B / 2 + 0.004), zs + hz[0]), (0, 0, 1), (0, -1, 0),
                 size=HW["halyards"]["size"], light=True, group="mast"))
    F.append(Fit("JibHalyardCleat", "HornCleat", (RC.MAST_X, RC.B / 2 + 0.004, zs + hz[1]), (0, 0, 1), (0, 1, 0),
                 size=HW["halyards"]["size"], light=True, group="mast"))
    o, nrm = mast_quarter(SPIN_QUARTER, 0.004)             # on the front's starboard quarter, where its fall runs
    F.append(Fit("SpinHalyardCleat", "HornCleat", (o.x, o.y, zs + hz[2]), (0, 0, 1), nrm,
                 size=HW["halyards"]["size"], light=True, group="mast"))
    # the pole's lift: a block under a padeye on the mast's front; its fall to a cam cleat on the front's port quarter
    sp = HW["spinnaker"]
    front = RC.MAST_X + RC.A / 2
    F.append(Fit("PoleLiftPadeye", "Padeye", (front, 0.0, sp["lift_z"]), (0, 0, 1), (1, 0, 0), light=TINY, group="mast"))
    o, nrm = mast_quarter(-SPIN_QUARTER, 0.0)
    F.append(Fit("PoleLiftCam", "CamCleat", (o.x, o.y, zs + 0.75), (0, 0, -1), nrm, light=True, group="mast"))
    fx, fy = sp["foreguy"]
    F.append(on("ForeguyPadeye", "Padeye", fx, fy, light=TINY))
    F.append(on("ForeguyCam", "CamCleat", RC.MAST_X - 0.20, 0.14, along=(-1, 0, 0), light=True))
    # lifelines: pulpit, stern rail, stanchions
    # (the kit's local y lands on the game's -Y, so a starboard socket's local y is negative: see Fit.p)
    xa, hoop, legs = pulpit_plan()
    z0 = max(surface(x, y) for x, y in legs)
    loc = lambda x, y: (x - xa, -y)
    F.append(Fit("BowPulpit", "BowPulpit", (xa, 0.0, z0), (1, 0, 0), (0, 0, 1),
                 kw={"hoop": [loc(x, y) for x, y in hoop],
                     "legs": [loc(x, y) + (surface(x, y) - z0,) for x, y in legs]},
                 socks={"LifelineS": (0.0, -hoop[0][1], 0.61), "LifelineP": (0.0, -hoop[-1][1], 0.61),
                        "Bow": (max(x for x, _ in hoop) - xa, 0, 0.61)}))
    xf, wp, dp = pushpit_dims()
    feet = [(-0.02, -wp / 2), (-0.02, wp / 2), (-dp + 0.02, -0.6 * wp / 2), (-dp + 0.02, 0.6 * wp / 2)]   # kit frame
    zr = max(surface(xf + x, y) for x, y in feet)
    F.append(Fit("SternRail", "Pushpit", (xf, 0.0, zr), (1, 0, 0), (0, 0, 1),
                 kw={"width": wp, "depth": dp, "legs": [(x, y, surface(xf + x, y) - zr) for x, y in feet]},
                 socks={"LifelineS": (0.0, -wp / 2, 0.61), "LifelineP": (0.0, wp / 2, 0.61)}))
    LL = HW["lifelines"]
    for sd, t in sides():
        for k, sx in enumerate(LL["stanchions_x"]):
            F.append(Fit(f"Stanchion{k}_{t}", "Stanchion", (sx, sd * edge_y(sx, LL["in"]), surface(sx, sd * edge_y(sx, LL["in"]))),
                         (1, 0, 0), (0, 0, 1), size="610", light=True))
    # cabin top: handrails on the lid, vents, the fore hatch on its curb
    HR = HW["handrails"]
    for sd, t in sides():
        xm = 0.5 * (HR["x"][0] + HR["x"][1])
        y = sd * (D.trunk_edge(xm) - D.PT["inset"] - HR["in"])
        F.append(on("Handrail_" + t, "HandrailTeak", xm, y, kw={"length": HR["x"][1] - HR["x"][0], "loops": 4}))
    DF = HW["deck_fittings"]
    for sd, t in sides():
        F.append(on("Vent_" + t, "VentMushroom", DF["vents"][0], sd * DF["vents"][1]))
    FH = D.D["fore_hatch"]
    F.append(Fit("ForeHatch", "HatchFwd", (FH["x"], 0.0, D.deck_z(FH["x"], 0.0) + 0.06), (1, 0, 0), (0, 0, 1),
                 kw={"w": FH["size"][0], "d": FH["size"][1]}, light=True))
    # the bow eye on the stem's face for the trailer's winch, 0.30 m under the sheer
    zb = H.sheer_z(H.STEM_X) - 0.30
    xb = H.stem_x_at(zb)
    F.append(Fit("BowEye", "BowEye", (xb, 0.0, zb), (0, 0, 1), (1, 0, 0), light=True))
    for y in DF["scuppers"]:
        for sd, t in sides():
            F.append(Fit("Scupper_" + t, "Scupper", (H.TRANSOM_X - 0.005, sd * y, D.CK["sole_z"] + 0.04), (0, 0, 1), (-1, 0, 0),
                         light=True))
    # a winch handle in its pocket in the starboard cockpit side, 0.35 m aft of the winch
    F.append(Fit("HandlePocket", "HandlePocket", (W["x"] - 0.35, D.CK["half_width"] - 0.002, D.seat_z(W["x"]) + 0.17),
                 (1, 0, 0), (0, -1, 0)))
    return F


def ladder():
    """The folding stern ladder on the transom's port side, folded up: its two rails hook over the aft deck and run down
    the transom's face to above the water; three rungs. Returns the rails (polylines) and the rungs (pairs)."""
    yc, w = HW["deck_fittings"]["ladder"]
    xt = H.TRANSOM_X
    zt = H.sheer_z(xt)
    rails = []
    for y in (yc - w / 2, yc + w / 2):
        rails.append([Vector((xt + 0.07, y, surface(xt + 0.07, y) + 0.012)), Vector((xt - 0.015, y, zt + 0.03)),
                      Vector((xt - 0.035, y, zt - 0.03)), Vector((xt - 0.035, y, 0.10))])
    rungs = [(Vector((xt - 0.035, yc - w / 2, z)), Vector((xt - 0.035, yc + w / 2, z))) for z in (0.62, 0.42, 0.22)]
    return rails, rungs


def bridge():
    """The traveller's moulded bridge across the footwell, flush with the seats: (centre, half sizes)."""
    x = HW["traveller"]["x"]
    top, sole = D.seat_z(x), D.CK["sole_z"]
    return Vector((x, 0.0, 0.5 * (top + sole))), Vector((0.06, D.CK["footwell_half_width"] + 0.004, 0.5 * (top - sole)))


def by_name(F):
    return {f.name: f for f in F}


# ------------------------------------------------------------------ the boom and its blocks for a state

def boom_rot(beta_deg):
    """A function turning a centred boom's point to the boom swung beta_deg to port about the gooseneck's pin."""
    g = V(RC.gooseneck())
    b = math.radians(beta_deg)
    cb, sb = math.cos(b), math.sin(b)
    return lambda p: g + Vector(((p[0] - g.x) * cb - (p[1] - g.y) * sb, (p[0] - g.x) * sb + (p[1] - g.y) * cb,
                                 p[2] - g.z))


def boom_points(state):
    rot = boom_rot(BOOM_DEG[state])                     # (to port: negative y, as sails_c22 swings it)
    zc = RC.BM["gooseneck_z"]
    under = zc - RC.BM["section"][0] / 2 - 0.004
    xa, xf = RC.boom_x()
    return {"mainsheet": rot((RC.BM["mainsheet_x"], 0, under)), "vang": rot((RC.BM["vang_x"], 0, under)),
            "end": rot((xa + 0.02, 0, zc + 0.01)), "rot": rot}


def tackle(state, which):
    """The mainsheet's or the vang's two blocks and its four parts and tail for a state."""
    B = boom_points(state)
    if which == "mainsheet":
        top = B["mainsheet"]
        F = fittings()
        car = by_name(F)["Traveller"]
        T = HW["traveller"]
        # the car rides down the track toward the boom's side, half the bail's offset (10 cm close-hauled, to the
        # stop on the run)
        cy = max(-T["length"] / 2 + 0.06, min(T["length"] / 2 - 0.06, top.y * 0.5))
        bot = Vector((car.o.x, cy, car.o.z + 0.04))
    else:
        top = B["vang"]
        bot = V(RC.vang_foot())
    up = hanging(f"{which}_upper", "Fiddle40", top, bot, xdir=(1, 0, 0), light=TINY, group=which)
    # the lower block's cam faces the crew: forward for the mainsheet (they sit forward of the traveller), aft for the
    # vang (its tail is led aft from the mast's foot); turned about its axis, its sheaves' sides swap
    aft = which == "vang"
    dn = hanging(f"{which}_lower", "FiddleCam", bot, top, xdir=(-1 if aft else 1, 0, 0), light=TINY, group=which)
    i1, o1, i2, o2 = ("LineOut", "LineIn", "LineOut2", "LineIn2") if aft else ("LineIn", "LineOut", "LineIn2", "LineOut2")
    parts = [[up.s("LineIn"), dn.s(i1)], [dn.s(o1), up.s("LineOut")], [up.s("LineIn2"), dn.s(i2)],
             [dn.s(o2), up.s("LineOut2")]]
    return up, dn, parts


# ------------------------------------------------------------------ line helpers

def surface_near(x, y, pad):
    """The highest surface within `pad` of (x, y): a line lying over an edge (the cockpit's coaming) rests on its lip."""
    if pad <= 0:
        return surface(x, y)
    return max(surface(x + pad * math.cos(a), y + pad * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 9)[:-1])


def drape(pts, r, step=0.01, lift=0.002, pad=0.012):
    """A polyline resampled every `step` and lifted wherever it would pass under the surface: a line lying on the deck,
    the cabin top or the lid where it touches them (and, with `pad`, over any edge within pad of it)."""
    out = []
    P = [V(p) for p in pts]
    for a, b in zip(P, P[1:]):
        n = max(1, int(math.ceil((b - a).length / step)))
        for i in range(n):
            out.append(a.lerp(b, i / n))
    out.append(P[-1])
    for i, p in enumerate(out):
        s = max(surface(p.x, p.y), surface_near(p.x, p.y, pad))
        if s > -0.5 and p.z < s + r + lift:
            out[i] = Vector((p.x, p.y, s + r + lift))
    return out


def sag(a, b, drop, n=16):
    return [V(p) for p in RW.sag(V(a), V(b), drop, n)]


def wraps(c, axis, R, z0, turns, start_ang, pitch, n=14):
    """Turns of line round a drum: centre c, axis (unit), radius R, from height z0 along the axis, starting at
    start_ang (radians, measured from the drum's X toward its Y), rising `pitch` a turn. Seen from above, X forward
    and Y to starboard, a rising angle runs clockwise, the way a winch turns."""
    axis = V(axis).normalized()
    u = Vector((1, 0, 0)) - axis * axis.x
    u = u.normalized() if u.length > 1e-6 else Vector((0, 1, 0))
    w = axis.cross(u)
    out = []
    m = int(turns * n)
    for i in range(m + 1):
        a = start_ang + 2 * math.pi * i / n
        out.append(V(c) + axis * (z0 + pitch * i / n) + u * (R * math.cos(a)) + w * (R * math.sin(a)))
    return out


def flat_coil(c, nrm, L, d, R=0.09, seed=1):
    """A coil lying on a surface: rings of radius about R stacked on the surface's normal, totalling length L."""
    rng = random.Random(seed)
    nrm = V(nrm).normalized()
    u = Vector((1, 0, 0)) - nrm * nrm.x
    u = u.normalized() if u.length > 1e-6 else Vector((0, 1, 0))
    w = nrm.cross(u)
    turns = max(1.0, L / (2 * math.pi * R))
    n = 18
    out = []
    ph = [rng.uniform(0, 6.28) for _ in range(3)]
    for i in range(int(turns * n) + 1):
        a = 2 * math.pi * i / n
        k = i / n
        r = R * (1 + 0.06 * math.sin(a * 2 + ph[0]) + 0.04 * math.sin(k * 1.7 + ph[1]))
        h = d / 2 + 0.001 + d * 0.55 * min(k, 3.0) / 3.0 * (0.5 + 0.5 * math.sin(a + ph[2]))
        out.append(V(c) + u * (r * math.cos(a)) + w * (r * math.sin(a)) + nrm * h)
    return out


def hung_coil(top, plane_x, down, L, d, R=0.11, seed=1):
    """A coil hung from a cleat's horn: loops hanging under `top` in the plane of `plane_x` and `down` (unit vectors),
    each a teardrop pinched at the horn, about 1.4 R wide and 2.6 R deep (a coil hangs long), totalling length L."""
    rng = random.Random(seed)
    px, dn = V(plane_x).normalized(), V(down).normalized()
    out_n = px.cross(dn)
    rx, ry = 0.7 * R, 1.3 * R
    per = 2 * math.pi * math.sqrt(0.5 * (rx * rx + ry * ry)) * 0.92        # a teardrop's length, about
    turns = max(1.0, L / per)
    n = 20
    out = []
    loop = [(rng.uniform(0.93, 1.07), rng.uniform(-0.15, 0.15)) for _ in range(int(turns) + 2)]
    for i in range(int(turns * n) + 1):
        a = 2 * math.pi * i / n
        k, sk = loop[i // n]
        w = rx * math.sin(a) * (0.25 + 0.75 * abs(math.sin(a / 2))) * (1 + sk)
        h = ry * k * (1 - math.cos(a))
        off = out_n * (d * 0.9 * (i / n) - d * 0.9 * turns / 2)
        out.append(V(top) + dn * h + px * w + off)
    return out


def cleat_hitch(cleat, lead_world, d, tail=0.25):
    """A line made fast on a horn cleat (the kit's): the ASA cleat hitch in the cleat's frame, with the line arriving
    from lead_world (a point)."""
    L = {"150": 0.150, "200": 0.200}[cleat.size]
    c = CLEAT_FIT(L)
    lw = V(lead_world) - cleat.o
    lead = (lw.dot(cleat.X), -lw.dot(cleat.Y))                 # (the kit frame's y: see Fit.p)
    path = RW.cleat_hitch(c["L"], d, lead, c["h_under"], c["h_top"], c["half_w"], c["foot_x"], tail=tail)
    # the hitch's path starts 0.5 m out along the lead (resampled every few mm): it is taken from its second waypoint,
    # 6 cm out, where the caller's line arrives (as bk_ropework.cleat_hitch places it)
    u = Vector((lead[0], lead[1], 0.0)).normalized()
    Fh, Ls = (-1.0 if u.x >= 0 else 1.0), (-1.0 if u.y <= 0 else 1.0)
    cx = c["foot_x"] * 0.62
    w2 = Vector((Fh * cx, Ls * (c["foot_x"] + d / 2 + 0.003 - cx), d / 2 + 0.0085)) + u * 0.06
    k = min(range(len(path) // 2), key=lambda i: (Vector(path[i]) - w2).length)
    return [cleat.p(p) for p in path[k:]]


def line(pts, d, slot="Rope", kind="line", via=()):
    """A line's polyline, diameter, slot and kind (line, coil, wire), and the fittings it is led through or made
    fast on (`via`, their names): the checks let it touch those."""
    return {"pts": [V(p) for p in pts], "d": d, "slot": slot, "kind": kind, "via": tuple(via)}


# ------------------------------------------------------------------ the halyards (every state)

def halyards():
    F = by_name(fittings())
    out = {}
    d = RP["halyard_d"]
    zs = RC.step_z()
    for name, cleat, side in (("MainHalyard", "MainHalyardCleat", -1), ("JibHalyard", "JibHalyardCleat", 1)):
        c = F[cleat]
        # internal: out of an exit slot 0.15 m over its cleat, down the mast's side to the cleat's upper horn
        ex = Vector((RC.MAST_X, side * (RC.B / 2 + d / 2 + 0.002), c.o.z + 0.15))
        approach = c.o + c.X * 0.12 + c.Z * (c.local["HornFwd"][2] + d / 2)
        hitch = cleat_hitch(c, approach + c.X * 0.4, d, tail=0.0)
        out[name] = line([ex, approach] + hitch, d, "RopeHalyard", via=(cleat,))
        # the coil hung over the upper horn, against the mast's side
        out[name + "Coil"] = line(hung_coil(c.s("HornFwd") + c.Z * 0.01, Vector((1, 0, 0)), -c.X, 6.0, d,
                                            R=0.08, seed=3 if side < 0 else 4), d, "RopeHalyard", "coil", via=(cleat,))
        out[name + "Exit"] = {"box": (ex, Vector((0.012, 0.004 * side, 0.045))), "slot": "Aluminium"}
    # the spinnaker's: external, from the block on the masthead's forward face down the front's starboard quarter
    # (clear of the pole lift's padeye on the front) to its cleat there
    c = F["SpinHalyardCleat"]
    blk = V(SC.halyard_block())
    approach = c.o + c.X * 0.12 + c.Z * (c.local["HornFwd"][2] + d / 2)
    q, _ = mast_quarter(SPIN_QUARTER, d / 2 + 0.004)
    fall = [blk + Vector((0.0, 0.012, -0.03)), Vector((q.x, q.y, zs + 6.2)), Vector((q.x, q.y, approach.z + 0.3)), approach]
    out["SpinHalyard"] = line(fall + cleat_hitch(c, approach + c.X * 0.4, d, tail=0.0), d, "RopeSpin",
                              via=("SpinHalyardCleat",))
    out["SpinHalyardCoil"] = line(hung_coil(c.s("HornFwd") + c.Z * 0.01, c.Y, -c.X, 5.0, d, R=0.08, seed=5), d,
                                  "RopeSpin", "coil", via=("SpinHalyardCleat",))
    return out


# ------------------------------------------------------------------ the sheets

def winch_wraps(w, arrive, d, turns=3.0):
    """Turns on a winch's drum (clockwise from above), the line arriving from `arrive`; returns the turns and where
    the tail leaves the top turn (aft side)."""
    R = 0.028 + d / 2
    drum_c = w.o
    a0 = math.atan2((arrive - w.o).dot(w.Y), (arrive - w.o).dot(w.X))
    start = a0 + math.pi / 2                              # tangent: the line meets the drum square to its radius,
                                                          # on the side from which it turns clockwise
    return wraps(drum_c, w.Z, R, 0.035, turns, start, d * 1.05)


def sheet_run(clew, lead_pts, winch, cleat, d, coil_at, seed, slot="RopeSheet", via=()):
    """A working sheet: from the clew through its leads (the fittings `via`) to the winch, three turns, the tail to
    the cleat's hitch and the rest in a flat coil on the seat beside it."""
    pts = [V(clew)] + [V(p) for p in lead_pts]
    turns = winch_wraps(winch, pts[-1], d)
    tail_from = turns[-1]
    cl = cleat_hitch(cleat, tail_from, d, tail=0.0)
    body = drape(pts + [turns[0]], d / 2)
    tail = [tail_from] + cl
    coil = flat_coil(coil_at, normal(coil_at[0], coil_at[1]), 3.0, d, R=0.10, seed=seed)
    return [line(body + turns[1:], d, slot, via=tuple(via) + (winch.name,)),
            line(tail, d, slot, via=(winch.name, cleat.name)), line(coil, d, slot, "coil")]


def lazy_run(clew, winch, cleat, via, d, coil_at, seed, slot="RopeSheet", leads=()):
    """The slack sheet on the other side: from the clew round the front of the mast and back over the cabin top to
    the windward lead (the fittings `leads`), its winch (one turn) and cleat."""
    v0 = V(via[0])
    v0 = Vector((v0.x, v0.y, max(v0.z, surface(v0.x, v0.y) + d / 2)))
    hang = sag(V(clew), v0, 0.18, 16)                 # slack from the clew: it hangs in a curve to the deck
    pts = drape(hang + [V(p) for p in via[1:]], d / 2)
    turns = winch_wraps(winch, pts[-1], d, turns=1.0)
    cl = cleat_hitch(cleat, turns[-1], d, tail=0.0)
    coil = flat_coil(coil_at, normal(coil_at[0], coil_at[1]), 2.5, d, R=0.10, seed=seed)
    return [line(pts + turns, d, slot, via=tuple(leads) + (winch.name,)),
            line([turns[-1]] + cl, d, slot, via=(winch.name, cleat.name)), line(coil, d, slot, "coil")]


def seat_spot(x, sd):
    y = sd * 0.47
    return Vector((x, y, surface(x, y)))


def turning_block(name, pe, frm, to, kit="Block29", group="fittings"):
    """A block on a padeye's eye turning a line from `frm` toward `to`: its body pulled along the sum of the two
    directions, its sheave in their plane. Returns the block and the line's points round its sheave."""
    eye = pe.s("Eye") + pe.Z * 0.004
    a, b = (V(frm) - eye).normalized(), (V(to) - eye).normalized()
    blk = hanging(name, kit, eye, eye + (a + b).normalized(), xdir=a - b, light=TINY, group=group)
    cz, r = blk.local["LineIn"][2], blk.local["LineIn"][0]
    return blk, [blk.s("LineIn"), blk.p((0.0, 0.0, cz + 0.7 * r)), blk.s("LineOut")]


def headsail_lines(name):
    """The genoa's or the jib's sheets on starboard tack: the working sheet to port (the sail's side), the lazy one to
    starboard."""
    F = by_name(fittings())
    T, Hd, C, _ = SC.headsail_corners(name)
    clew = V(C) + Vector((-0.02, 0, -0.01))
    d = RP["sheet_d"]
    out = {}
    if name == "Genoa":
        car = F["GenoaTrack_P"]
        via_w = [car.s("Sheave") + car.Z * (d / 2)]
        lazy_car = F["GenoaTrack_S"]
        # round the mast's front and forward of the vents, then aft along the starboard side deck to its car
        lazy_via = [Vector((0.4, -0.55, 0)), Vector((1.45, -0.27, 0)), Vector((1.60, 0.0, 0)), Vector((1.45, 0.30, 0)),
                    Vector((0.5, 0.75, 0)), lazy_car.s("Sheave") + lazy_car.Z * (d / 2)]
        leads_w, leads_l = ("GenoaTrack_P",), ("GenoaTrack_S",)
    else:
        car = F["JibTrack_P"]
        fl = F["JibFairlead_P"]
        flp = fl.s("Line") + fl.Z * (d / 2)
        tb, tbp = turning_block("JibTurnBlock_P", F["JibTurnPadeye_P"], flp, F["Winch_P"].s("Drum"), group=name)
        out["_blk_turn_P"] = tb
        via_w = [car.s("Sheave") + car.Z * (d / 2), flp] + tbp
        lazy_car = F["JibTrack_S"]
        lfl = F["JibFairlead_S"]
        lflp = lfl.s("Line") + lfl.Z * (d / 2)
        ltb, ltbp = turning_block("JibTurnBlock_S", F["JibTurnPadeye_S"], lflp, F["Winch_S"].s("Drum"), group=name)
        out["_blk_turn_S"] = ltb
        lazy_via = [Vector((1.15, -0.2, 0)), Vector((1.3, 0.0, 0)), Vector((1.15, 0.25, 0)),
                    lazy_car.s("Sheave") + lazy_car.Z * (d / 2), lflp] + ltbp
        leads_w = ("JibTrack_P", "JibFairlead_P", "JibTurnPadeye_P")
        leads_l = ("JibTrack_S", "JibFairlead_S", "JibTurnPadeye_S")
    a, b, c = sheet_run(clew, via_w, F["Winch_P"], F["WinchCleat_P"], d, seat_spot(-1.55, -1), 11, via=leads_w)
    out[name + "Sheet_P"], out[name + "SheetTail_P"], out[name + "SheetCoil_P"] = a, b, c
    a, b, c = lazy_run(clew, F["Winch_S"], F["WinchCleat_S"], lazy_via, d, seat_spot(-1.55, 1), 12, leads=leads_l)
    out[name + "Sheet_S"], out[name + "SheetTail_S"], out[name + "SheetCoil_S"] = a, b, c
    return out


def spinnaker_lines():
    """On a run, the pole squared to starboard: the guy from the pole's end to the starboard quarter block and winch,
    the sheet from the clew to the port quarter block and winch; the pole's lift and foreguy."""
    F = by_name(fittings())
    d = RP["spin_sheet_d"]
    ring, tip = SC.pole()
    clew = V(SC.SP["clew"])
    out = {}
    # the sheet passes outside the boom's end (the main is out to port, across its way aft) and under it, aft
    B = boom_points("run")
    g = V(RC.gooseneck())
    outward = Vector((B["end"].x - g.x, B["end"].y - g.y, 0.0)).normalized()
    round_end = B["end"] + outward * 0.15 + Vector((0.0, 0.0, -0.15))
    for name, frm, sd, t, pre in (("SpinGuy", V(tip), 1, "S", []), ("SpinSheet", clew, -1, "P", [round_end])):
        blk, via = turning_block(f"QuarterBlock_{t}", F["QuarterPadeye_" + t], pre[-1] if pre else frm,
                                 F["Winch_" + t].s("Drum"), kit="Block40", group="run")
        out["_blk_" + t] = blk
        a, b, c = sheet_run(frm, pre + via, F["Winch_" + t], F["WinchCleat_" + t], d, seat_spot(-2.05, sd), 21 + sd,
                            via=("QuarterPadeye_" + t,))
        out[name], out[name + "Tail"], out[name + "Coil"] = a, b, c
    mid = (V(ring) + V(tip)) * 0.5
    lp = F["PoleLiftPadeye"]
    lblk = hanging("PoleLiftBlock", "Block29", lp.s("Eye") + lp.Z * 0.003, mid, xdir=(0, 1, 0), light=TINY, group="run")
    out["_blk_lift"] = lblk
    dl = RP["control_d"]
    cam = F["PoleLiftCam"]
    q, _ = mast_quarter(-SPIN_QUARTER, dl / 2 + 0.003)       # down the front's port quarter to its cam
    jaws = cam.s("Line") + cam.Z * (dl / 2)
    out["PoleLift"] = line([mid + Vector((0, 0, 0.03)), lblk.p((0, 0, -0.031)), Vector((q.x, q.y, lblk.o.z - 0.15)),
                            Vector((q.x, q.y, jaws.z + 0.1)), jaws, jaws + Vector((0, 0, -0.3))], dl, "RopeControl",
                           via=("PoleLiftPadeye", "PoleLiftCam"))
    fp = F["ForeguyPadeye"]
    fblk = Fit("ForeguyBlock", "Block29", fp.s("Eye") + fp.Z * 0.003, (0, 1, 0), (V(fp.s("Eye")) - mid).normalized(),
               light=TINY, group="run")
    out["_blk_foreguy"] = fblk
    fc = F["ForeguyCam"]
    out["Foreguy"] = line([mid - Vector((0, 0, 0.03)), fblk.p((0, 0, -0.031)), fc.s("Line") + fc.Z * (dl / 2)] +
                          drape([fc.s("Line") + fc.Z * (dl / 2), fc.s("Line") + Vector((-0.4, 0.05, 0))], dl / 2),
                          dl, "RopeControl", via=("ForeguyPadeye", "ForeguyCam"))
    return out


MAIN_STATE = {"up": "Set", "jib": "Set", "reef": "Reefed", "run": "Run"}


def boom_lines(state, B):
    """The outhaul (and, reefed, the reef's clew pennant instead) along the boom, to a cam cleat on the boom's side near
    the gooseneck: worked in the centred boom's frame and swung with it."""
    out = {}
    rot = B["rot"]
    zc = RC.BM["gooseneck_z"]
    hd, hw = RC.BM["section"][0] / 2, RC.BM["section"][1] / 2
    xa, xf = RC.boom_x()
    d = RP["control_d"]
    fwd = (rot((1, 0, 0)) - rot((0, 0, 0))).normalized()

    def cam_on(name, x):
        """A cam cleat on the boom's starboard side, its jaws taking a line from aft."""
        o, Z = rot((x, hw + 0.001, zc)), rot((0, 1, 0)) - rot((0, 0, 0))
        return Fit(name, "CamCleat", o, fwd, Z, light=True, group=state)

    sh = SC.main_sheet(MAIN_STATE[state])
    clew = V(sh.G[-1, 0]) + Vector((0, 0, 0.012))
    if state != "reef":
        # the outhaul: from the clew's ring aft over the end's sheave, out of the end and forward along the boom's
        # starboard side (clear of the bails under it) to a cam on that side near the gooseneck
        cam = cam_on("OuthaulCam", xf - 0.30)
        out["_outhaul_cam"] = cam
        ring = [clew, rot((xa + 0.045, 0, zc + hd - 0.004)), rot((xa + 0.025, 0, zc + 0.02)), rot((xa + 0.022, 0, zc)),
                rot((xa + 0.03, 0.015, zc - 0.03)), rot((xa + 0.09, hw + d / 2 + 0.002, zc - 0.012))]
        jaws = cam.s("Line") + cam.Z * (d / 2)
        tail = [jaws, jaws + fwd * 0.05, jaws + fwd * 0.10 + Vector((0, 0, -0.10)), jaws + fwd * 0.12 + Vector((0, 0.01, -0.22))]
        out["Outhaul"] = line(ring + [jaws] + tail[1:], d, "RopeControl")
    else:
        # the reef's clew pennant: from an eye on the boom's port side up through the cringle, down to a cheek on the
        # starboard side and forward along it to a cam on that side
        xc = sh.extras["xl"] - float(sh.extras["chord"](sh.extras["reef"]))
        cam = cam_on("ReefCam", xf - 0.42)
        out["_reef_cam"] = cam
        jaws = cam.s("Line") + cam.Z * (d / 2)
        pts = [rot((xc - 0.05, -(hw + d / 2 + 0.002), zc + 0.01)), rot((xc - 0.01, -0.012, zc + hd + 0.03)), clew,
               rot((xc - 0.01, 0.012, zc + hd + 0.03)), rot((xc - 0.07, hw + d / 2 + 0.003, zc + 0.01)),
               rot((xc - 0.03, hw + d / 2 + 0.003, zc)), jaws]
        tail = [jaws + fwd * 0.05, jaws + fwd * 0.09 + Vector((0, 0, -0.12)), jaws + fwd * 0.08 + Vector((0, 0.01, -0.25))]
        out["ReefPennant"] = line(pts + tail, d, "RopeControl")
    return out


def main_lines(state):
    """The mainsheet and vang tackles at the state's boom angle, their tails, and the topping lift."""
    out = {}
    B = boom_points(state)
    for which, d in (("mainsheet", RP["mainsheet_d"]), ("vang", RP["control_d"])):
        up, dn, parts = tackle(state, which)
        out["_" + which] = (up, dn)
        for k, p in enumerate(parts):
            if which == "mainsheet":                         # eased right out (the run), its parts lie over the coaming
                out[f"Mainsheet{k}"] = line(drape(p, d / 2), d, "RopeSheet", via=("Traveller",))
            else:
                out[f"Vang{k}"] = line(p, d, "RopeControl")
        cam = dn.s("CamLead")
        if which == "mainsheet":
            R = 0.12                                         # the tail and its coil on the footwell's sole, inside it
            lim = D.CK["footwell_half_width"] - 1.12 * R - d
            cy = max(-lim, min(lim, dn.o.y * 0.5))
            down = Vector((dn.o.x + 0.25, cy, D.CK["sole_z"]))
            tail = drape([cam, cam + (down - cam) * 0.5 + Vector((0, 0, 0.05)), down], d / 2)
            out["MainsheetTail"] = line(tail, d, "RopeSheet", via=("Traveller",))
            out["MainsheetCoil"] = line(flat_coil(Vector((down.x + 0.2, cy, D.CK["sole_z"])), (0, 0, 1), 3.5, d,
                                                  R=R, seed=7), d, "RopeSheet", "coil")
        else:
            # aft out of the cam, down onto the cabin top and lying aft along it beside the mast's foot
            x1, y1 = cam.x - 0.20, 0.07
            tail = [cam, cam + Vector((-0.06, 0.01, -0.05)), Vector((x1, y1, surface(x1, y1) + d / 2 + 0.002)),
                    Vector((x1 - 0.35, y1 + 0.05, 0))]
            out["VangTail"] = line(drape(tail, d / 2), d, "RopeControl")
    if state != "rest":
        out.update(boom_lines(state, B))
    # the topping lift: masthead crane to the boom's end; slack under sail, bowed to leeward of the leech (the boom's
    # port side as it swings: forward of the leech on the run), where the wind blows it
    top = V(RC.crane_pin()) + Vector((0.03, 0.02, -0.012))   # an eye on the crane's side, forward of the backstay's pin
    end = B["end"]
    pts = sag(top, end, 0.0, 30)
    if state != "rest":
        lee = B["rot"]((0, -1, 0)) - B["rot"]((0, 0, 0))
        pts = [p + lee * (0.25 * math.sin(math.pi * i / 30)) for i, p in enumerate(pts)]
    out["ToppingLift"] = line(pts, RP["control_d"], "RopeControl")
    return out


def rest_lines():
    """At the mooring: the jib halyard's end clipped to the pulpit, the main's down the mast's after face to the
    headboard at the gooseneck, the spinnaker's down the mast's front to its cleat."""
    F = by_name(fittings())
    d = RP["halyard_d"]
    top = RC.top_z()
    pul = F["BowPulpit"]
    out = {}
    jb = V((RC.MAST_X + RC.A / 2 + 0.01, -0.012, top - 0.04))
    # its shackle snapped round the hoop's starboard side, a third of the way from its legs to the nose, on the
    # tube's inboard top
    xa, hoop, _ = pulpit_plan()
    xc = xa + 0.33 * (max(x for x, _ in hoop) - xa)
    hy = min((p for p in hoop if p[1] > 0), key=lambda p: abs(p[0] - xc))[1]
    pj = Vector((xc, hy - 0.012, pul.o.z + 0.61 + 0.0127 + d / 2))
    out["JibHalyardEnd"] = line(sag(jb, pj, 0.12, 30), d, "RopeHalyard", via=("BowPulpit",))
    # the spinnaker's end is brought down the mast alongside its fall and clipped round its cleat's lower horn, where
    # it can't wrap the forestay
    sc = F["SpinHalyardCleat"]
    sb = V(SC.halyard_block()) + Vector((0, 0.025, -0.04))
    clip = sc.s("HornAft") + sc.Z * 0.012
    q, _ = mast_quarter(SPIN_QUARTER - 5.0, 1.5 * d + 0.006)       # alongside its fall, outside it
    out["SpinHalyardEnd"] = line([sb, Vector((q.x, q.y, RC.step_z() + 6.0)), Vector((q.x, q.y, clip.z + 0.25)),
                                  clip], d, "RopeSpin", via=("SpinHalyardCleat",))
    mb = V((RC.MAST_X - RC.A / 2 - 0.01, 0.0, top - 0.04))
    head = V((RC.MAST_X - RC.A / 2 - 0.12, 0.0, RC.boom_top() + 0.10))
    out["MainHalyardEnd"] = line([mb, mb + (head - mb) * 0.5 + Vector((-0.02, 0, 0)), head], d, "RopeHalyard")
    return out


def lifeline_wires():
    F = by_name(fittings())
    out = {}
    for sd, t in sides():
        pts = [F["BowPulpit"].s("Lifeline" + t)]
        for k in range(len(HW["lifelines"]["stanchions_x"])):
            pts.append(F[f"Stanchion{k}_{t}"].s("LifelineTop"))
        pts.append(F["SternRail"].s("Lifeline" + t))
        out["Lifeline_" + t] = line(pts, HW["lifelines"]["wire_d"], "Lifeline", "wire")
    return out


def lines():
    """{state: {name: line}} for every state, plus 'all' (in every state)."""
    out = {"all": {}}
    out["all"].update(halyards())
    out["all"].update(lifeline_wires())
    out["rest"] = main_lines("rest")
    out["rest"].update(rest_lines())
    out["up"] = main_lines("up")
    out["up"].update(headsail_lines("Genoa"))
    out["jib"] = main_lines("jib")
    out["jib"].update(headsail_lines("Jib"))
    out["reef"] = main_lines("reef")
    out["reef"].update(headsail_lines("Jib"))
    out["run"] = main_lines("run")
    out["run"].update(spinnaker_lines())
    return out


# ------------------------------------------------------------------ checks

def seg_dist(P, a, b):
    """Distances from points P (n, 3) to the segment a-b."""
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def poly_dist(P, Q, skip=0.0):
    """Least distance from the polyline P's points (sampled every cm, leaving out `skip` metres at each end) to the
    polyline Q."""
    P = np.asarray(P, float)
    dense, arc = [P[0]], [0.0]
    for a, b in zip(P[:-1], P[1:]):
        ln = float(np.linalg.norm(b - a))
        n = max(1, int(ln / 0.01))
        dense += [a + (b - a) * (i / n) for i in range(1, n + 1)]
        arc += [arc[-1] + ln * i / n for i in range(1, n + 1)]
    dense, arc = np.array(dense), np.array(arc)
    keep = (arc >= skip) & (arc <= arc[-1] - skip)
    if keep.any():
        dense = dense[keep]
    Q = np.asarray(Q, float)
    return min(seg_dist(dense, a, b).min() for a, b in zip(Q[:-1], Q[1:]))


# A kit fitting's box in its own frame, for the checks: half length along X, half width along Y, height along Z (None:
# half its length; "w"/"d": half its kw)
SHAPE = {"WinchPlain": (0.051, 0.051, 0.10), "HornCleat150": (0.075, 0.015, 0.04), "HornCleat200": (0.10, 0.02, 0.054),
         "JibTrack": (None, 0.016, 0.03), "Padeye": (0.02, 0.02, 0.03), "Fairlead": (0.016, 0.016, 0.016),
         "CamCleat": (0.03, 0.02, 0.02), "HandrailTeak": (None, 0.015, 0.06), "VentMushroom": (0.055, 0.055, 0.037),
         "HatchFwd": ("w", "d", 0.05), "Traveler": (None, 0.02, 0.04)}
BOOM_LINES = ("Mainsheet", "Vang", "Outhaul", "ReefPennant", "ToppingLift", "MainHalyardEnd")
THROUGH_SAIL = ("Outhaul", "ReefPennant")        # led through the main's clew or its reef cringle


def box_of(f):
    k = f.kit + (f.size or "") if f.kit == "HornCleat" else f.kit
    if k not in SHAPE:
        return None
    hx, hy, hz = SHAPE[k]
    hx = f.kw["length"] / 2 if hx is None else (f.kw[hx] / 2 if isinstance(hx, str) else hx)
    hy = f.kw[hy] / 2 if isinstance(hy, str) else hy
    return hx, hy, hz


def box_gap(f, P):
    """The signed distance from points P (n, 3) to the fitting's box (negative inside)."""
    hx, hy, hz = box_of(f)
    v = P - np.array(tuple(f.o))
    x, y, z = v @ np.array(tuple(f.X)), v @ np.array(tuple(f.Y)), v @ np.array(tuple(f.Z))
    q = np.stack([np.abs(x) - hx, np.abs(y) - hy, np.maximum(-z, z - hz)], axis=1)
    return np.linalg.norm(np.maximum(q, 0.0), axis=1) + np.minimum(q.max(axis=1), 0.0)


def dense(pts, step=0.005, skip=0.0):
    """A polyline's points every `step`, leaving out `skip` metres at each end."""
    P = np.array([tuple(p) for p in pts], float)
    out, arc = [P[0]], [0.0]
    for a, b in zip(P[:-1], P[1:]):
        ln = float(np.linalg.norm(b - a))
        n = max(1, int(ln / step))
        out += [a + (b - a) * (i / n) for i in range(1, n + 1)]
        arc += [arc[-1] + ln * i / n for i in range(1, n + 1)]
    out, arc = np.array(out), np.array(arc)
    keep = (arc >= skip) & (arc <= arc[-1] - skip)
    return out[keep] if keep.any() else out


def obstacles(state):
    """What the lines keep clear of, as {name: (polyline, radius, owner)}: the rig's wires and the mast, the
    lifelines, stanchions, the pulpit's and stern rail's tubes and legs, and the boom at the state's angle. A line
    led through the owner (its `via`) may touch it."""
    out = {n: (p, r, n) for n, (p, r) in SC.wire_lines().items()}
    for n, ln in lifeline_wires().items():
        out[n] = (np.array([tuple(p) for p in ln["pts"]]), ln["d"] / 2, "Lifeline")
    for f in fittings():
        if f.kit == "Stanchion":
            out[f.name] = (np.array([tuple(f.o), tuple(f.p((0, 0, 0.61)))]), 0.0125, f.name)
    for n, path in rail_paths().items():
        out[n] = (np.array(path), 0.0127, "BowPulpit" if n.startswith("Pulpit") else "SternRail")
    rot = boom_points(state)["rot"]
    xa, xf = RC.boom_x()
    zc = RC.BM["gooseneck_z"]
    out["Boom"] = (np.array([tuple(rot((xf, 0, zc))), tuple(rot((xa, 0, zc)))]), max(RC.BM["section"]) / 2, "Boom")
    return out


def owned(name, ln, owner):
    if owner == "Mast":
        return "Halyard" in name or name == "PoleLift"
    if owner == "Boom":
        return name.startswith(BOOM_LINES)
    if owner == "Lifeline":
        return False
    return owner in ln.get("via", ())


def check_lines(L, state, fails, report):
    """Every line and coil clear of the wires, mast, lifelines, stanchions, rails and boom by CLEAR, except what it
    is led through or along (the halyards on the mast, the mainsheet and vang on the boom)."""
    obs = obstacles(state)
    worst = {}
    for name, ln in L.items():
        if name.startswith("_") or "pts" not in ln or ln["kind"] == "wire":
            continue
        P = np.array([tuple(p) for p in ln["pts"]])
        for on_, (Q, r, owner) in obs.items():
            if owned(name, ln, owner):
                continue
            g = poly_dist(P, Q, 0.0 if ln["kind"] == "coil" else END) - r - ln["d"] / 2
            if g < worst.get(name, (9.0,))[0]:
                worst[name] = (g, on_)
    for name, (g, on_) in sorted(worst.items()):
        ok = g >= CLEAR
        report.append(f"  {state:5s} {name:18s} least gap {g * 100:6.1f} cm  ({on_})  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{state} {name} touches {on_}")


def check_surfaces(L, state, F, fails, report):
    """No line or coil under the deck, the cockpit's seats and sole, the cabin top or the lid (by more than 3 mm),
    and none into a deck or mast fitting it isn't led through or made fast on."""
    boxes = [f for f in F if box_of(f) is not None]
    for name, ln in sorted(L.items()):
        if name.startswith("_") or "pts" not in ln or ln["kind"] == "wire":
            continue
        r = ln["d"] / 2
        P = dense(ln["pts"], 0.005)
        under = 0.0
        for p in P:
            s = surface(p[0], p[1])
            if s > -0.5:
                under = max(under, s - (p[2] - r))
        Pf = dense(ln["pts"], 0.005, 0.0 if ln["kind"] == "coil" else END)
        into, what = 0.0, ""
        for f in boxes:
            if f.name in ln.get("via", ()):
                continue
            g = -(box_gap(f, Pf) - r).min()
            if g > into:
                into, what = g, f.name
        ok = under <= 0.003 and into <= 0.0
        if not ok or under > 0.0 or into > -0.005:
            report.append(f"  {state:5s} {name:18s} under the surface by {under * 1000:4.1f} mm, into {what or '-'} by "
                          f"{max(into, 0) * 1000:4.1f} mm  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{state} {name} " + (f"under the deck {under * 1000:.0f} mm" if under > 0.003 else
                                               f"into {what} {into * 1000:.0f} mm"))


STATE_SAILS = {"up": ("MainSet", "GenoaSet"), "jib": ("MainSet", "JibSet"), "reef": ("MainReefed", "JibSet"),
               "run": ("MainRun", "SpinnakerSet")}
# Sail-on-rail contacts reported but not failed: none since the genoa was cut high (Bean, Nov 17: its tack on a pennant
# over the pulpit, its clew above the lifeline; docs/c22-7).
KNOWN_SAIL_CONTACTS = {}
_SETS = {}


def check_sails(L, state, fails, report):
    """No line through a sail of its state (past END at its ends), but the outhaul and the reef's pennant, which are
    led through the main's clew and cringle; and no rail, stanchion or lifeline through a sail (but KNOWN_SAIL_CONTACTS).
    The sails are slice 5's as built (sails_c22.set_sheets)."""
    if not _SETS:
        _SETS.update(SC.set_sheets())
    obs = obstacles(state)
    for sn in STATE_SAILS.get(state, ()):
        sh = _SETS[sn]
        bad, known = [], []
        for name, ln in sorted(L.items()):
            if name.startswith("_") or "pts" not in ln or ln["kind"] == "wire" or name.startswith(THROUGH_SAIL):
                continue
            P = dense(ln["pts"], 0.02, 0.0 if ln["kind"] == "coil" else END)
            if len(P) > 1 and SC.crossings(sh, P):
                bad.append(name)
        for on_, (Q, r, owner) in obs.items():
            if owner in ("Lifeline", "BowPulpit", "SternRail") or on_.startswith("Stanchion"):
                if SC.crossings(sh, np.asarray(Q, float)):
                    (known if on_ in KNOWN_SAIL_CONTACTS.get(sn, ()) else bad).append(on_)
        ok = not bad
        report.append(f"  {state:5s} {sn:12s} crossed by {', '.join(bad) or 'no line or rail'}"
                      f"{'; lies on ' + ', '.join(known) + ' (known)' if known else ''}  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{state} {sn} crossed by {', '.join(bad)}")


def group_of(name):
    """A line's family: a sheet with its tail and coil, a tackle's parts with its tail, a halyard with its end."""
    base = re.sub(r"(Tail|Coil|End)(_[SP])?$", r"\2", name)
    return re.sub(r"\d+$", "", base)


def check_crossings(L, state, fails, report):
    """No two lines (of different families) through each other: their centrelines at least the sum of their radii
    apart (to a millimetre), past END at each end of a working line (lines meeting at a clew or a pole)."""
    items = []
    for name, ln in L.items():
        if name.startswith("_") or "pts" not in ln or ln["kind"] == "wire":
            continue
        P = dense(ln["pts"], 0.005, 0.0 if ln["kind"] == "coil" else END)
        items.append((name, P, ln["d"] / 2, P.min(axis=0), P.max(axis=0)))
    bad = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            na, A, ra, lo_a, hi_a = items[i]
            nb, B, rb, lo_b, hi_b = items[j]
            if group_of(na) == group_of(nb):
                continue
            m = ra + rb
            if np.any(lo_a - m > hi_b) or np.any(lo_b - m > hi_a):
                continue
            best = 9.0
            for k in range(0, len(A), 1500):
                D2 = ((A[k:k + 1500, None, :] - B[None, :, :]) ** 2).sum(axis=2)
                best = min(best, float(np.sqrt(D2.min())))
            g = best - m
            if g < -0.001:
                bad.append(f"{na}/{nb} {g * 1000:.0f} mm")
    ok = not bad
    report.append(f"  {state:5s} lines through each other: {', '.join(bad) or 'none'}  {'ok' if ok else 'FAIL'}")
    if not ok:
        fails.append(f"{state} lines through each other ({len(bad)})")


def sheet_angle(name):
    """The angle between the headsail's sheet (clew to its lead) and the bisector of its clew's angle, seen square to
    the sail, and where the sheet's line meets the luff (as a share of the luff from the tack). A fair lead pulls
    along the bisector (foot and leech loaded alike); carried on, the bisector meets the luff where the foot and the
    leech divide it (the angle bisector theorem): about a third of the way up on these long-footed sails, so the share
    is reported, not held to the "halfway" rule of thumb for jibs with short feet."""
    F = by_name(fittings())
    T, Hd, C, _ = SC.headsail_corners(name)
    T, Hd, C = V(T), V(Hd), V(C)
    lead = (F["GenoaTrack_P"] if name == "Genoa" else F["JibTrack_P"]).s("Sheave")
    n = (Hd - T).cross(C - T).normalized()               # the sail's plane (tack, head, clew)
    flat = lambda v: (v - n * v.dot(n)).normalized()
    bis = flat((T - C).normalized() + (Hd - C).normalized())
    s3 = (lead - C).normalized()
    s = flat(s3)
    ang = math.degrees(math.acos(max(-1.0, min(1.0, (-s).dot(bis)))))
    out_of_plane = math.degrees(math.asin(min(1.0, abs(s3.dot(n)))))
    # where the sheet's line, carried up from the clew past it, meets the luff (closest approach)
    dd, u = -s, (Hd - T)
    w0 = C - T
    a, b, c, d_, e = dd.dot(dd), dd.dot(u), u.dot(u), dd.dot(w0), u.dot(w0)
    den = a * c - b * b
    tl = (a * e - b * d_) / den if abs(den) > 1e-9 else 0.0
    return ang, tl, out_of_plane


def check_winches(L, state, fails, report):
    """Each sheet meets its winch's drum nearly square to its axis (between 80 and 95 degrees: a line climbing onto
    the drum from below rides up off the turns, one coming down from above overrides them)."""
    F = by_name(fittings())
    for name, ln in L.items():
        if name.startswith("_") or "pts" not in ln or ln["kind"] != "line":
            continue
        if not ("Sheet_" in name or name in ("SpinGuy", "SpinSheet")):
            continue
        side = name[-1] if name[-2] == "_" else ("S" if name == "SpinGuy" else "P")
        w = F["Winch_" + side]
        P = ln["pts"]
        # the last point before the turns start (the turns lie within the drum's radius + 2 cm of its axis)
        k = next(i for i, p in enumerate(P) if ((p - w.o) - w.Z * (p - w.o).dot(w.Z)).length < 0.03 + ln["d"] and
                 abs((p - w.o).dot(w.Z)) < 0.12)
        a, b = P[max(0, k - 3)], P[k]
        dirn = (b - a).normalized()
        ang = math.degrees(math.acos(max(-1.0, min(1.0, dirn.dot(w.Z)))))
        ok = 80.0 <= ang <= 95.0
        report.append(f"  {state:5s} {name:18s} meets its winch at {ang:5.1f} deg to the axis  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{state} {name} winch angle {ang:.1f}")


def check_fittings(F, fails, report):
    """Each deck fitting's base on its surface (the surface under its footprint within 6 mm of its base plane: the
    deck's camber and the cabin's crown under a long track), no two deck fittings' footprints overlapping, and the
    pulpit's and stern rail's feet on the deck at least 3 cm inside its edge."""
    foot = {"WinchPlain": 0.05, "HornCleat": 0.07, "JibTrack": 0.0, "Padeye": 0.02, "Fairlead": 0.016,
            "HandrailTeak": 0.0, "VentMushroom": 0.055, "CamCleat": 0.015}
    for f in F:
        if f.kit not in foot or f.group != "fittings":
            continue
        if f.kit in ("JibTrack", "HandrailTeak"):
            half = f.kw["length"] / 2
            pts = [f.p((s * half, 0, 0)) for s in np.linspace(-1, 1, 9)]
        else:
            r = foot[f.kit]
            pts = [f.p((r * math.cos(a), r * math.sin(a), 0)) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
        dev = max(abs(surface(p.x, p.y) - p.z) for p in pts)
        ok = dev <= 0.006
        report.append(f"  {f.name:18s} base off its surface by at most {dev * 1000:4.1f} mm  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{f.name} base {dev * 1000:.1f} mm")
    # footprints: each deck fitting's box in plan, sampled, against every other's (2 mm of play)
    deck = [f for f in F if f.group == "fittings" and box_of(f) is not None]
    for i, a in enumerate(deck):
        hx, hy, _ = box_of(a)
        S = np.array([tuple(a.p((x, y, 0.005))) for x in np.linspace(-hx, hx, 7) for y in np.linspace(-hy, hy, 5)])
        for b in deck[i + 1:]:
            if (a.o - b.o).length > 1.5:
                continue
            g = box_gap(b, S)
            if g.min() < -0.002:
                report.append(f"  {a.name} and {b.name} overlap  FAIL")
                fails.append(f"{a.name}/{b.name} overlap")
    Fn = by_name(F)
    for rail in ("BowPulpit", "SternRail"):
        f = Fn[rail]
        for k, p in enumerate(f.p(leg) for leg in f.kw["legs"]):
            inside = H.half_beam(p.x) - abs(p.y)
            off = abs(surface(p.x, p.y) - p.z)
            ok = inside >= 0.03 and off <= 0.02
            report.append(f"  {rail} foot {k}: {inside * 100:4.1f} cm inside the deck's edge, {off * 1000:4.1f} mm off "
                          f"it  {'ok' if ok else 'FAIL'}")
            if not ok:
                fails.append(f"{rail} foot {k}")


def main():
    fails, report = [], []
    F = fittings()
    print(f"slice 6: {len(F)} kit fittings")
    check_fittings(F, fails, report)
    for name in ("Genoa", "Jib"):
        ang, tl, oop = sheet_angle(name)
        ok = ang <= 12.0
        report.append(f"  {name} sheet {ang:4.1f} deg off the clew's bisector seen square to the sail ({oop:.0f} deg "
                      f"out of its plane), its line meets the luff {tl:.0%} up  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(name + " lead")
    # the boom the lines are hung from is the boom the sails were cut on: the end within 20 cm of the main's clew
    for st in ("up", "jib", "run"):
        gap = (boom_points(st)["end"] - V(SC.main_sheet(MAIN_STATE[st]).G[-1, 0])).length
        ok = gap < 0.20
        report.append(f"  {st:5s} boom's end {gap * 100:5.1f} cm from the main's clew  {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{st} boom off the sail")
    L = lines()
    for st in STATES:
        LL = dict(L["all"])
        LL.update(L[st])
        check_lines(LL, st, fails, report)
        check_surfaces(LL, st, F, fails, report)
        check_winches(LL, st, fails, report)
        check_sails(LL, st, fails, report)
        check_crossings(LL, st, fails, report)
    for r in report:
        print(r)
    n = sum(1 for st in L.values() for k, v in st.items() if not k.startswith("_") and "pts" in v)
    length = sum(sum((b - a).length for a, b in zip(v["pts"], v["pts"][1:])) for st in L.values()
                 for k, v in st.items() if not k.startswith("_") and "pts" in v)
    print(f"{n} lines, {length:.1f} m of rope and wire in all states")
    if fails:
        print("FAIL: " + ", ".join(fails))
        sys.exit(1)
    print("pass")


if __name__ == "__main__":
    main()
