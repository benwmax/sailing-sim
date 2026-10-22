"""The shared hardware kit: deck fittings modelled once at hero quality and placed on every boat from a layout file.

Each part is generic and brand-free (no maker's shapes copied, no logos), sized from small-keelboat hardware catalogues'
published dimensions. Every part:
- is built at its mount point (origin on the mounting surface, +Z out of it, +X forward along the part);
- has real chamfers and weighted normals on its hard edges (bk_geom.finish);
- carries its material slots by MI_Boat_* name (bk_materials), so it imports onto the game's library;
- names its attach points as SOCKET_* empties (where a rope leads, where a pin sits, where a hand grips).

`PARTS` maps a kit name to (builder, info). Builders take keyword options (length, size) and return one object.
"""
import math

from mathutils import Matrix, Vector

import bk_geom as G
import bk_materials as BM
import bk_trim as BT

PARTS = {}


def part(name, category, note):
    def deco(fn):
        PARTS[name] = (fn, {"category": category, "note": note})
        return fn
    return deco


def M(slot):
    return BM.get(slot)


def done(name, objs, sockets=()):
    ob = G.join(f"SM_Kit_{name}", objs)
    for s in sockets:
        G.socket(ob, *s)
    return ob


def badge(name, cell, w, h, xform, mat, inst=0, disc=False):
    """A maker's plate (boat fidelity 2): a thin plate or disc whose top lands whole on a trim-sheet brand cell (TERNWAY:
    a made-up maker). Built in XY on z = 0 (+X along the text), then placed by `xform` 0.2 mm proud of its face."""
    if disc:
        o = G.lathe(name, [(0, 0), (w / 2, 0), (w / 2, 0.0004), (0, 0.0004)], mat, 32)
    else:
        o = G.prism(name, G.rrect(w, h, min(w, h) * 0.2), 0.0, 0.0004, mat)
    o.matrix_world = xform @ Matrix.Translation((0, 0, 0.0002))
    G.bake_xform(o)
    G.finish(o, 0, weighted=False)
    return BT.mark(o, cell=cell, inst=inst)


# ------------------------------------------------------------------ small hardware

def _fastener_ring(n, rx, ry, z, mat, r=0.0028):
    pts = [(rx * math.cos(G.TAU * i / n), ry * math.sin(G.TAU * i / n), z) for i in range(n)]
    return G.screw_heads("fast", pts, mat, r)


@part("ShackleD", "fastener", "5 mm stainless D-shackle, pin along Y, bow up")
def shackle_d(size=1.0):
    s = size
    w, L, d = 0.008 * s, 0.022 * s, 0.0025 * s
    bow = G.tube("bow", [(0, -w, 0)] + G.arc_pts((0, 0, L - w), w, math.pi, 0, 12, "yz") + [(0, w, 0)], d, M("Stainless"), 10)
    # straight legs down to the pin eyes
    bow = G.finish(bow)
    pin = G.finish(G.cyl("pin", (0, -w - 0.004 * s, 0), (0, w + 0.003 * s, 0), d * 1.05, M("Stainless"), 14), 0.0004)
    head = G.finish(G.cyl("head", (0, -w - 0.004 * s, 0), (0, -w - 0.0065 * s, 0), d * 1.9, M("Stainless"), 16), 0.0006)
    return done("ShackleD", [bow, pin, head], [("Pin", (0, 0, 0)), ("Bow", (0, 0, L))])


@part("Padeye", "fastener", "Stainless U-bolt padeye on a 50 x 30 mm backing plate")
def padeye():
    plate = G.prism("plate", G.rrect(0.050, 0.030, 0.008), 0, 0.003, M("Stainless"), taper=0.94)
    G.finish(plate, 0.0008)
    loop = G.tube("loop", [(-0.012, 0, 0.002)] + G.arc_pts((0, 0, 0.018), 0.012, math.pi, 0, 14, "xz") + [(0.012, 0, 0.002)], 0.0035, M("Stainless"), 14)
    G.finish(loop)
    nuts = G.screw_heads("n", [(-0.012, 0, 0.003), (0.012, 0, 0.003)], M("Stainless"), 0.006, 0.002)
    return done("Padeye", [plate, loop] + nuts, [("Eye", (0, 0, 0.030))])


@part("HornCleat", "cleat", "Cast aluminium horn cleat, 150 mm, two bolts")
def horn_cleat(length=0.150):
    L = length
    h = L * 0.22
    base = G.prism("base", G.rrect(L * 0.42, L * 0.20, L * 0.08), 0, h * 0.55, M("Aluminium"), taper=0.82)
    G.finish(base, 0.003)
    # one tapering horn from end to end, an ellipse section swept over an arch
    path = G.bezier((-L / 2, 0, h * 0.62), (-L * 0.25, 0, h * 1.02), (L * 0.25, 0, h * 1.02), (L / 2, 0, h * 0.62), 24)
    radii = [0.55 + 0.45 * math.sin(math.pi * i / (len(path) - 1)) ** 0.6 for i in range(len(path))]
    horn = G.sweep("horn", path, G.ellipse(L * 0.055, L * 0.075, 20), M("Aluminium"), radii=radii, twist_up=(0, 0, 1))
    G.finish(horn, 0.0, sharp=80)
    bolts = G.screw_heads("b", [(-L * 0.12, 0, h * 0.55), (L * 0.12, 0, h * 0.55)], M("Stainless"), 0.0045, 0.002)
    return done("HornCleat", [base, horn] + bolts, [("Wrap", (0, 0, h * 0.9)), ("HornFwd", (L / 2, 0, h * 0.62)), ("HornAft", (-L / 2, 0, h * 0.62))])


@part("CamCleat", "cleat", "Aluminium cam cleat, 75 mm, two toothed cams on a base with a fairlead")
def cam_cleat():
    L, W = 0.075, 0.045
    base = G.prism("base", G.rrect(L, W, 0.006), 0, 0.006, M("Aluminium"), taper=0.96)
    G.finish(base, 0.0012)
    objs = [base]
    for side in (-1, 1):
        # cam: a toothed disc on a vertical axle, eccentric toward the line
        cy = side * 0.014
        prof = []
        teeth = 18
        # pc/j22-detail assembly 5: raked teeth (a sawtooth: the line slides in, not out) on an eccentric lobe toward the line
        for i in range(teeth * 3):
            a = G.TAU * i / (teeth * 3)
            r = 0.0108 + 0.0018 * max(0.0, math.cos(a + side * math.pi / 2)) + (0.0013, 0.0006, 0.0)[i % 3]
            prof.append((r * math.cos(a), r * math.sin(a)))
        cam = G.prism(f"cam{side}", prof, 0.006, 0.020, M("Aluminium"))
        cam.location = (0.004, cy, 0)
        G.bake_xform(cam)
        objs.append(G.finish(cam, 0.0004, sharp=50))
        axle = G.cyl(f"axle{side}", (0.004, cy, 0.020), (0.004, cy, 0.0225), 0.004, M("Stainless"), 16)
        objs.append(G.finish(axle, 0.0006))
    # the fairlead hoop at the aft end
    hoop = G.tube("hoop", G.arc_pts((-L / 2 + 0.004, 0, 0.006), 0.012, 0, math.pi, 14, "yz"), 0.0026, M("Aluminium"), 12)
    objs.append(G.finish(hoop))
    objs += G.screw_heads("s", [(L / 2 - 0.007, 0, 0.006), (-L / 2 + 0.012, 0.016, 0.006), (-L / 2 + 0.012, -0.016, 0.006)], M("Stainless"))
    return done("CamCleat", objs, [("Line", (0.004, 0, 0.014)), ("Lead", (-L / 2, 0, 0.012))])


@part("CamRiser", "cleat", "Angled riser wedge under a cam cleat, 20 degrees")
def cam_riser():
    L, W = 0.080, 0.050
    o = G.prism("riser", G.rrect(L, W, 0.006), 0, 0.006, M("BlackPlastic"))
    for v in o.data.vertices:
        if v.co.z > 0.001:
            v.co.z += math.tan(math.radians(20)) * (L / 2 - v.co.x)
    G.finish(o, 0.0015)
    h = math.tan(math.radians(20)) * L / 2 + 0.006
    return done("CamRiser", [o], [("Top", (0, 0, h), (0, math.radians(20), 0))])


@part("Fairlead", "lead", "Moulded bullseye fairlead, 32 mm, for sheets and control lines")
def fairlead():
    body = G.lathe("body", [(0.008, 0), (0.016, 0), (0.016, 0.004), (0.013, 0.012), (0.0085, 0.013), (0.0065, 0.010), (0.0065, 0.0), ], M("BlackPlastic"), 32)
    G.finish(body, 0.0008)
    return done("Fairlead", [body] + G.screw_heads("s", [(0.012, 0, 0.004), (-0.012, 0, 0.004)], M("Stainless"), 0.0022), [("Line", (0, 0, 0.008))])


def _block_parts(name, sheave_d, sheaves=1, cam=False, becket=False, ratchet=False, plate=None):
    """Plastic-cheek block hanging along -Z from a swivel at the origin; axle along Y; `plate` badges the -Y cheek."""
    objs = []
    R = sheave_d / 2
    t = 0.007                                              # sheave thickness
    width = sheaves * t + (sheaves + 1) * 0.004
    cz = -R - 0.016                                        # axle height below the head
    for i in range(sheaves + 1):
        y = -width / 2 + 0.002 + i * (t + 0.004)
        cheek = G.prism(f"cheek{i}", G.ellipse(R + 0.006, R + 0.010, 40), y, y + 0.003, M("BlackPlastic"))
        cheek.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(cheek)
        cheek.location = (0, 0, cz)
        G.bake_xform(cheek)
        # pc/j22-detail assembly 5: a ring of lightening holes through the outer cheeks (the sheave shows through), clear
        # of the head and the badge
        if i in (0, sheaves):
            holes = [G.cyl(f"hole{i}{k}", (R * 0.62 * math.cos(a), -1.0, cz + R * 0.62 * math.sin(a)), (R * 0.62 * math.cos(a), 1.0, cz + R * 0.62 * math.sin(a)),
                           R * 0.16, None, 16) for k, a in enumerate(G.TAU * (j + 0.5) / 6 for j in range(6)) if not (plate and i == 0 and math.sin(a) < -0.4)]
            G.boolean(cheek, G.join(f"holes{i}", holes))
            hub = G.lathe(f"hub{i}", [(0, 0), (R * 0.34, 0), (R * 0.32, 0.0012), (0, 0.0012)], M("BlackPlastic"), 24)
            side = -1 if i == 0 else 1
            hub.matrix_world = Matrix.Translation((0, y + (0 if i == 0 else 0.003), cz)) @ Matrix.Rotation(math.radians(-90 * side), 4, "X")
            G.bake_xform(hub)
            objs.append(G.finish(hub, 0.0004))
        objs.append(G.finish(cheek, 0.0008))
    for i in range(sheaves):
        y0 = -width / 2 + 0.005 + i * (t + 0.004) + 0.0005
        prof = [(0.003, 0), (R, 0), (R, 0.0015), (R - 0.002, t / 2), (R, t - 0.0015), (R, t), (0.003, t)]
        sh = G.lathe(f"sheave{i}", prof, M("Rubrail" if ratchet else "BlackPlastic"), 36)
        sh.matrix_world = Matrix.Translation((0, y0, cz)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        G.bake_xform(sh)
        objs.append(G.finish(sh, 0, sharp=60))
        # the ball bearings' race on each face of the sheave
        for face in (0.0, t):
            race = G.lathe(f"race{i}{face}", [(R * 0.40, 0), (R * 0.50, 0), (R * 0.50, 0.0005), (R * 0.40, 0.0005)], M("Stainless"), 28)
            race.matrix_world = Matrix.Translation((0, y0 + face - (0.0005 if face == 0.0 else 0.0), cz)) @ Matrix.Rotation(math.radians(-90), 4, "X")
            G.bake_xform(race)
            objs.append(G.finish(race, 0, weighted=False))
    ax = G.cyl("axle", (0, -width / 2 - 0.001, cz), (0, width / 2 + 0.001, cz), 0.0045, M("Stainless"), 16)
    objs.append(G.finish(ax, 0.0006))
    # swivel head: a stainless strap over the top and a swivel shackle
    strap = G.tube("strap", [(0, -width / 2 + 0.001, cz)] + G.arc_pts((0, 0, cz), R + 0.012, math.pi, 0, 18, "yz")[1:-1] + [(0, width / 2 - 0.001, cz)], 0.002, M("Stainless"), 10)
    objs.append(G.finish(strap))
    swivel = G.lathe("swivel", [(0, -0.012), (0.004, -0.012), (0.004, -0.004), (0.0025, -0.003), (0.0025, 0), (0, 0)], M("Stainless"), 16)
    objs.append(G.finish(swivel, 0.0004))
    if becket:
        bk = G.tube("becket", G.arc_pts((0, 0, cz - R - 0.012), 0.007, math.pi, G.TAU, 12, "yz"), 0.0018, M("Stainless"), 10)
        objs.append(G.finish(bk))
    if cam:
        arm = G.box("camarm", (0.020, 0, cz - R * 0.2), (0.020, 0.030, 0.006), M("Aluminium"))
        objs.append(G.finish(arm, 0.0015))
    if plate:
        objs.append(badge("plate", plate, R * 1.1, R * 0.45,
                          Matrix.Translation((0, -width / 2 + 0.002, cz - R * 0.45)) @ Matrix.Rotation(math.radians(90), 4, "X"), M("BlackPlastic")))
    socks = [("Head", (0, 0, 0)), ("Axle", (0, 0, cz)), ("LineIn", (R, 0, cz)), ("LineOut", (-R, 0, cz))]
    if becket:
        socks.append(("Becket", (0, 0, cz - R - 0.019)))
    return objs, socks


@part("Block29", "block", "29 mm single block with swivel, sheets and control lines")
def block29(becket=False):
    objs, socks = _block_parts("Block29", 0.029, becket=becket, plate="Plate29")
    return done("Block29" + ("B" if becket else ""), objs, socks)


@part("Block40", "block", "40 mm single block with swivel and becket")
def block40():
    objs, socks = _block_parts("Block40", 0.040, becket=True, plate="Plate40")
    return done("Block40", objs, socks)


@part("Ratchet57", "block", "57 mm ratchet block for the jib sheet or mainsheet")
def ratchet57():
    objs, socks = _block_parts("Ratchet57", 0.057, ratchet=True, plate="Plate57")
    return done("Ratchet57", objs, socks)


@part("FiddleCam", "block", "40 mm fiddle block with a cam cleat arm: the mainsheet's bottom block")
def fiddle_cam():
    objs, socks = _block_parts("FiddleCam", 0.040, sheaves=2, cam=True, becket=True, plate="Plate40")
    return done("FiddleCam", objs, socks)


# ------------------------------------------------------------------ winches

@part("Winch16", "winch", "Two-speed self-tailing-free winch, size 16: base flange, drum with grip band, top cap")
def winch16():
    prof = [(0, 0), (0.060, 0), (0.060, 0.006), (0.055, 0.010), (0.044, 0.014),       # base flange
            (0.040, 0.016), (0.040, 0.022), (0.036, 0.024),                            # drum foot
            (0.033, 0.030), (0.031, 0.070), (0.033, 0.080),                            # drum (slight waist)
            (0.036, 0.082), (0.036, 0.090), (0.030, 0.094), (0.016, 0.096), (0, 0.096)]
    base = G.lathe("base", prof[:5] + [(0, 0.014)], M("BlackPlastic"), 48)
    G.finish(base, 0.0012)
    drum = G.lathe("drum", [(0, 0.014)] + prof[5:], M("Aluminium"), 64)
    # vertical grip ribs on the drum band
    for v in drum.data.vertices:
        if 0.034 < v.co.z < 0.068:
            a = math.atan2(v.co.y, v.co.x)
            k = 1 + 0.025 * max(0.0, math.cos(a * 32)) ** 6
            v.co.x *= k
            v.co.y *= k
    G.finish(drum, 0.001, sharp=50)
    sock = G.lathe("socket", [(0, 0.096), (0.012, 0.096), (0.012, 0.097), (0.0, 0.097)], M("BlackPlastic"), 8)   # octagonal socket
    G.finish(sock, 0)
    objs = [base, drum, sock] + _fastener_ring(5, 0.050, 0.050, 0.006, M("Stainless"), 0.0035)
    # pc/j22-detail assembly 5: the top cap's screws and the cap's chrome edge ring
    objs += _fastener_ring(5, 0.022, 0.022, 0.0952, M("Stainless"), 0.0022)
    ring = G.lathe("capring", [(0.0335, 0.0895), (0.0362, 0.0895), (0.0362, 0.0912), (0.0335, 0.0912)], M("Stainless"), 64)
    objs.append(G.finish(ring, 0, weighted=False))
    # The maker's plate on the base flange's slope, facing forward, reading along the flange.
    tilt = math.atan2(0.008, 0.016)
    objs.append(badge("plate", "Plate16", 0.024, 0.006, Matrix.Translation((0.052, 0, 0.010)) @ Matrix.Rotation(tilt, 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "Z"),
                      M("BlackPlastic")))
    return done("Winch16", objs, [("Drum", (0, 0.032, 0.050)), ("Handle", (0, 0, 0.097)), ("Tail", (0, -0.034, 0.075))])


@part("WinchHandle", "winch", "8 in lock-in winch handle with a single grip")
def winch_handle():
    arm = G.prism("arm", G.rrect(0.205, 0.024, 0.011), 0, 0.012, M("Aluminium"))
    arm.location = (0.0925, 0, 0)
    G.bake_xform(arm)
    G.finish(arm, 0.002)
    stub = G.lathe("stub", [(0, -0.030), (0.011, -0.030), (0.011, -0.002), (0.014, 0), (0.014, 0.012), (0.010, 0.016), (0, 0.016)], M("Aluminium"), 8)
    G.finish(stub, 0.001)
    grip = G.lathe("grip", [(0, 0.012), (0.014, 0.012), (0.016, 0.040), (0.016, 0.085), (0.013, 0.105), (0, 0.108)], M("BlackPlastic"), 32)
    grip.location = (0.185, 0, 0)
    G.bake_xform(grip)
    BT.mark(G.finish(grip, 0), band="grip")
    return done("WinchHandle", [arm, stub, grip], [("Drive", (0, 0, -0.030)), ("Grip", (0.185, 0, 0.06))])


@part("HandlePocket", "winch", "Moulded winch-handle pocket for a cockpit side")
def handle_pocket():
    rim = G.prism("rim", G.rrect(0.075, 0.300, 0.020), 0, 0.006, M("BlackPlastic"), taper=0.96)
    G.finish(rim, 0.002)
    inner = G.prism("inner", G.rrect(0.060, 0.285, 0.016), -0.040, 0.0061, M("BlackPlastic"))
    G.finish(inner, 0.0)
    for f in inner.data.polygons:
        f.flip()
    return done("HandlePocket", [rim, inner] + _fastener_ring(4, 0.030, 0.140, 0.006, M("Stainless"), 0.0025), [("Mouth", (0, 0, 0.006))])


# ------------------------------------------------------------------ tracks and cars

def _track(length, w=0.025, h=0.010, mat="Aluminium"):
    prof = [(-w / 2, 0), (w / 2, 0), (w / 2, h * 0.55), (w * 0.32, h * 0.6), (w * 0.32, h), (-w * 0.32, h), (-w * 0.32, h * 0.6), (-w / 2, h * 0.55)]
    o = G.sweep("track", [(-length / 2, 0, 0), (length / 2, 0, 0)], [(p[0], p[1]) for p in prof], M(mat), twist_up=(0, 0, 1))
    G.finish(o, 0.0008, sharp=40)
    n = max(2, int(length / 0.10) + 1)
    bolts = G.screw_heads("b", [(-length / 2 + 0.02 + i * (length - 0.04) / (n - 1), 0, h) for i in range(n)], M("Stainless"), 0.004, 0.0015)
    return [o] + bolts


@part("JibTrack", "track", "T-track 25 mm with a jib lead car (sheave, plunger stop); length option")
def jib_track(length=0.60):
    objs = _track(length)
    car = G.prism("car", G.rrect(0.090, 0.040, 0.010), 0.008, 0.026, M("Aluminium"), taper=0.85)
    G.finish(car, 0.002)
    objs.append(car)
    ch = 0.026
    sh = G.lathe("sheave", [(0.004, 0), (0.019, 0), (0.019, 0.002), (0.016, 0.005), (0.019, 0.008), (0.019, 0.010), (0.004, 0.010)], M("BlackPlastic"), 32)
    sh.matrix_world = Matrix.Translation((0.010, -0.005, ch + 0.019)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    G.bake_xform(sh)
    objs.append(G.finish(sh, 0, sharp=60))
    for s in (-1, 1):
        cheek = G.prism(f"cheek{s}", [(-0.012, 0), (0.035, 0), (0.030, 0.035), (-0.004, 0.035)], 0, 0.003, M("Stainless"))
        cheek.matrix_world = Matrix.Translation((-0.0, s * 0.0085 - 0.0015, ch)) @ Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(cheek)
        objs.append(G.finish(cheek, 0.0006))
    plunger = G.cyl("plunger", (-0.034, 0, ch), (-0.034, 0, ch + 0.016), 0.006, M("BlackPlastic"), 20)
    objs.append(G.finish(plunger, 0.0015))
    return done("JibTrack", objs, [("Sheave", (0.010, 0, ch + 0.019)), ("CarFwd", (0.045, 0, ch)), ("TrackEnd", (length / 2, 0, 0))])


@part("Traveler", "track", "Mainsheet traveler: track, car with two control sheaves, end stops; length option")
def traveler(length=0.90):
    objs = _track(length, 0.032, 0.014)
    car = G.prism("car", G.rrect(0.070, 0.050, 0.010), 0.010, 0.030, M("Aluminium"), taper=0.9)
    objs.append(G.finish(car, 0.002))
    for s in (-1, 1):
        stop = G.prism(f"stop{s}", G.rrect(0.030, 0.045, 0.008), 0.0, 0.032, M("BlackPlastic"), taper=0.9)
        stop.location = (s * (length / 2 - 0.015), 0, 0)
        G.bake_xform(stop)
        objs.append(G.finish(stop, 0.002))
        sh = G.lathe(f"cs{s}", [(0.003, 0), (0.010, 0), (0.010, 0.006), (0.003, 0.006)], M("BlackPlastic"), 20)
        sh.matrix_world = Matrix.Translation((s * 0.037, -0.003, 0.022)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        G.bake_xform(sh)
        objs.append(G.finish(sh, 0.0005))
    eye = G.tube("eye", G.arc_pts((0, 0, 0.030), 0.010, 0, math.pi, 12, "yz"), 0.003, M("Stainless"), 10)
    objs.append(G.finish(eye))
    return done("Traveler", objs, [("Car", (0, 0, 0.040)), ("EndP", (-length / 2, 0, 0.02)), ("EndS", (length / 2, 0, 0.02))])


# ------------------------------------------------------------------ big-boat deck gear (the maxi, Tools/boats/maxi)

@part("Winch70", "winch", "Large two-speed self-tailing winch (about 70 size): flanged base, ribbed drum, self-tailer jaws and stripper arm, top cap; scale option")
def winch70(scale=1.0):
    s = scale
    base = G.lathe("base", [(0, 0), (0.165 * s, 0), (0.165 * s, 0.012 * s), (0.150 * s, 0.022 * s), (0.120 * s, 0.032 * s), (0, 0.032 * s)], M("CarbonMatte"), 64)
    G.finish(base, 0.003 * s)
    prof = [(0, 0.032 * s), (0.112 * s, 0.032 * s), (0.112 * s, 0.050 * s), (0.104 * s, 0.056 * s), (0.098 * s, 0.070 * s),
            (0.094 * s, 0.200 * s), (0.100 * s, 0.215 * s), (0.110 * s, 0.222 * s), (0, 0.222 * s)]
    drum = G.lathe("drum", prof, M("Aluminium"), 96)
    for v in drum.data.vertices:
        if 0.075 * s < v.co.z < 0.195 * s:
            a = math.atan2(v.co.y, v.co.x)
            k = 1 + 0.02 * max(0.0, math.cos(a * 48)) ** 6
            v.co.x *= k
            v.co.y *= k
    G.finish(drum, 0.002 * s, sharp=50)
    # The self-tailer: two jaw rings with a groove between, a stripper arm reaching out over the drum.
    jaws = G.lathe("jaws", [(0, 0.222 * s), (0.118 * s, 0.222 * s), (0.124 * s, 0.232 * s), (0.104 * s, 0.240 * s), (0.124 * s, 0.248 * s),
                            (0.118 * s, 0.262 * s), (0.060 * s, 0.272 * s), (0, 0.274 * s)], M("BlackPlastic"), 72)
    G.finish(jaws, 0.0015 * s)
    arm = G.prism("stripper", [(0.0, -0.018 * s), (0.150 * s, -0.012 * s), (0.150 * s, 0.012 * s), (0.0, 0.018 * s)], 0.236 * s, 0.252 * s, M("CarbonMatte"))
    G.finish(arm, 0.003 * s)
    cap = G.lathe("cap", [(0, 0.274 * s), (0.030 * s, 0.274 * s), (0.030 * s, 0.284 * s), (0, 0.284 * s)], M("Aluminium"), 8)   # octagonal handle socket
    G.finish(cap, 0.001)
    objs = [base, drum, jaws, arm, cap] + _fastener_ring(8, 0.150 * s, 0.150 * s, 0.012 * s, M("Stainless"), 0.006 * s)
    # The maker's disc on the top of the self-tailer, round the handle socket.
    objs.append(badge("disc", "DiscLarge", 0.110 * s, 0, Matrix.Translation((0, 0, 0.272 * s)), M("Aluminium"), disc=True))
    return done("Winch70", objs, [("Drum", (0, 0.098 * s, 0.13 * s)), ("Handle", (0, 0, 0.284 * s)), ("Tail", (0.150 * s, 0, 0.244 * s)),
                                  ("Grinder", (0, 0, 0.0))])


@part("GrinderPedestal", "winch", "Coffee-grinder pedestal: tapered carbon column on a foot plate, a gearbox head and two crank arms with folding grips")
def grinder_pedestal(height=0.92):
    foot = G.prism("foot", G.rrect(0.42, 0.34, 0.06), 0, 0.02, M("CarbonMatte"), taper=0.96)
    G.finish(foot, 0.004)
    col = G.prism("column", G.rrect(0.20, 0.16, 0.05), 0.02, height - 0.12, M("Carbon"), taper=0.72)
    G.finish(col, 0.008)
    head = G.prism("head", G.rrect(0.20, 0.26, 0.06), height - 0.14, height, M("Carbon"), taper=0.94)
    G.finish(head, 0.012)
    objs = [foot, col, head]
    hz = height - 0.07
    for s in (1, -1):
        hub = G.cyl(f"hub{s}", (0, s * 0.13, hz), (0, s * 0.17, hz), 0.045, M("Aluminium"), 32)
        objs.append(G.finish(hub, 0.003))
        # The crank, opposite phase each side (the arms at 180 degrees, as they are in use).
        a = 0.6 if s > 0 else 0.6 + math.pi
        tip = (0.30 * math.cos(a), s * 0.19, hz + 0.30 * math.sin(a))
        crank = G.prism(f"crank{s}", G.rrect(0.32, 0.045, 0.02), 0, 0.022, M("Aluminium"))
        crank.matrix_world = Matrix.Translation((0.15 * math.cos(a), s * 0.185, hz + 0.15 * math.sin(a))) @ Matrix.Rotation(-a, 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(crank)
        objs.append(G.finish(crank, 0.004))
        grip = G.lathe(f"grip{s}", [(0, 0), (0.019, 0), (0.021, 0.03), (0.021, 0.11), (0.017, 0.13), (0, 0.13)], M("BlackPlastic"), 32)
        grip.matrix_world = Matrix.Translation((tip[0], s * 0.20, tip[2])) @ Matrix.Rotation(math.radians(-90 * s), 4, "X")
        G.bake_xform(grip)
        objs.append(G.finish(grip, 0))
    return done("GrinderPedestal", objs, [("CrankS", (0, 0.19, hz)), ("CrankP", (0, -0.19, hz)), ("Stance", (-0.45, 0, 0)), ("Drive", (0, 0, 0))])


@part("SteeringWheel", "steering", "Carbon wheel on a binnacle pedestal: thin rim with a grip wrap, five spokes, hub, binnacle with an instrument pod; diameter option")
def steering_wheel(diameter=1.95, binnacle=0.78):
    r = diameter / 2
    objs = []
    ped = G.prism("binnacle", G.rrect(0.26, 0.22, 0.06), 0, binnacle, M("Carbon"), taper=0.7)
    objs.append(G.finish(ped, 0.01))
    pod = G.prism("pod", G.rrect(0.30, 0.10, 0.03), binnacle - 0.02, binnacle + 0.20, M("CarbonMatte"), taper=0.9)
    objs.append(G.finish(pod, 0.008))
    hz = binnacle + 0.06
    # The wheel stands in the YZ plane, its axle along X (aft of the binnacle).
    hub = G.cyl("hub", (-0.06, 0, hz), (-0.18, 0, hz), 0.07, M("Aluminium"), 32)
    objs.append(G.finish(hub, 0.004))
    rim = G.tube("rim", [(-0.18, r * math.cos(2 * math.pi * k / 96), hz + r * math.sin(2 * math.pi * k / 96)) for k in range(96)], 0.022, M("Carbon"), 16, closed=True)
    objs.append(G.finish(rim))
    wrap = G.tube("wrap", [(-0.18, (r + 0.001) * math.cos(2 * math.pi * k / 96), hz + (r + 0.001) * math.sin(2 * math.pi * k / 96)) for k in range(40, 57)], 0.0245, M("BlackPlastic"), 16)
    objs.append(G.finish(wrap))
    for k in range(5):
        a = 2 * math.pi * k / 5 + math.pi / 2
        spoke = G.tube(f"spoke{k}", [(-0.18, 0.07 * math.cos(a), hz + 0.07 * math.sin(a)), (-0.18, (r - 0.02) * math.cos(a), hz + (r - 0.02) * math.sin(a))], 0.016, M("Carbon"), 12,
                       radii=[0.022, 0.012])
        objs.append(G.finish(spoke))
    return done("SteeringWheel", objs, [("Axle", (-0.18, 0, hz)), ("GripTop", (-0.18, 0, hz + r)), ("GripS", (-0.18, r, hz)), ("GripP", (-0.18, -r, hz)),
                                        ("Stance", (-0.75, 0, 0))])


@part("ClutchBank", "rope", "A bank of rope clutches on a moulded base, handles closed; count option")
def clutch_bank(count=4, pitch=0.072):
    w = count * pitch + 0.03
    base = G.prism("base", G.rrect(0.20, w, 0.012), 0, 0.012, M("CarbonMatte"), taper=0.97)
    objs = [G.finish(base, 0.003)]
    for i in range(count):
        y = -w / 2 + 0.015 + pitch * (i + 0.5)
        body = G.prism(f"body{i}", G.rrect(0.17, pitch - 0.012, 0.012), 0.012, 0.062, M("BlackPlastic"), taper=0.88)
        body.location = (0, y, 0)
        G.bake_xform(body)
        objs.append(G.finish(body, 0.004))
        handle = G.prism(f"handle{i}", G.rrect(0.15, pitch - 0.022, 0.010), 0.062, 0.078, M("Aluminium"), taper=0.9)
        handle.location = (-0.01, y, 0)
        G.bake_xform(handle)
        objs.append(G.finish(handle, 0.003))
        objs.append(badge(f"plate{i}", "Plate", 0.060, 0.016, Matrix.Translation((-0.01, y, 0.078)), M("BlackPlastic"), inst=i))
        objs += G.screw_heads(f"s{i}", [(0.075, y, 0.012), (-0.075, y, 0.012)], M("Stainless"), 0.004, 0.0015)
    socks = [(f"Line{i}", (0.09, -w / 2 + 0.015 + pitch * (i + 0.5), 0.04)) for i in range(count)]
    return done("ClutchBank", objs, socks)


@part("TravellerHeavy", "track", "Big-boat mainsheet traveller: wide low track, ball-bearing car with a sheave pair, end controls; length option")
def traveller_heavy(length=4.4):
    objs = _track(length, 0.070, 0.024, "CarbonMatte")
    car = G.prism("car", G.rrect(0.26, 0.11, 0.02), 0.020, 0.075, M("Aluminium"), taper=0.9)
    objs.append(G.finish(car, 0.004))
    for s in (-1, 1):
        sh = G.lathe(f"sh{s}", [(0.008, 0), (0.045, 0), (0.045, 0.014), (0.008, 0.014)], M("BlackPlastic"), 40)
        sh.matrix_world = Matrix.Translation((s * 0.06, -0.007, 0.11)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        G.bake_xform(sh)
        objs.append(G.finish(sh, 0.001))
        end = G.prism(f"end{s}", G.rrect(0.09, 0.12, 0.02), 0.0, 0.07, M("BlackPlastic"), taper=0.9)
        end.location = (s * (length / 2 - 0.045), 0, 0)
        G.bake_xform(end)
        objs.append(G.finish(end, 0.004))
    return done("TravellerHeavy", objs, [("Car", (0, 0, 0.12)), ("EndP", (-length / 2, 0, 0.04)), ("EndS", (length / 2, 0, 0.04))])


@part("GenoaTrackHeavy", "track", "Big-boat genoa track with an adjustable lead car (large sheave); length option")
def genoa_track_heavy(length=4.8):
    objs = _track(length, 0.045, 0.016, "CarbonMatte")
    car = G.prism("car", G.rrect(0.22, 0.07, 0.015), 0.014, 0.05, M("Aluminium"), taper=0.85)
    objs.append(G.finish(car, 0.004))
    sh = G.lathe("sheave", [(0.010, 0), (0.060, 0), (0.060, 0.006), (0.052, 0.012), (0.060, 0.018), (0.060, 0.024), (0.010, 0.024)], M("BlackPlastic"), 48)
    sh.matrix_world = Matrix.Translation((0.03, -0.012, 0.11)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    G.bake_xform(sh)
    objs.append(G.finish(sh, 0, sharp=60))
    return done("GenoaTrackHeavy", objs, [("Sheave", (0.03, 0, 0.11)), ("TrackEnd", (length / 2, 0, 0))])


# ------------------------------------------------------------------ rig attachments

@part("Chainplate", "rig", "Stainless chainplate strap through a deck cover plate, with clevis and split ring")
def chainplate():
    cover = G.prism("cover", G.rrect(0.070, 0.026, 0.008), 0, 0.003, M("Stainless"), taper=0.92)
    G.finish(cover, 0.0008)
    strap = G.prism("strap", [(-0.012, -0.003), (0.012, -0.003), (0.012, 0.003), (-0.012, 0.003)], 0.002, 0.045, M("Stainless"))
    for v in strap.data.vertices:
        if v.co.z > 0.03:
            v.co.x *= 0.75
    G.finish(strap, 0.0012)
    pin = G.cyl("pin", (0, -0.008, 0.035), (0, 0.008, 0.035), 0.003, M("Stainless"), 14)
    G.finish(pin, 0.0004)
    objs = [cover, strap, pin] + G.screw_heads("s", [(-0.028, 0, 0.003), (0.028, 0, 0.003)], M("Stainless"), 0.0025)
    return done("Chainplate", objs, [("Pin", (0, 0, 0.035))])


@part("Stemhead", "rig", "Bow stem fitting with forestay tang, tack shackle hole and bow roller cheeks")
def stemhead():
    plate = G.prism("plate", [(-0.10, -0.022), (0.04, -0.016), (0.07, 0), (0.04, 0.016), (-0.10, 0.022)], 0, 0.004, M("Stainless"))
    G.finish(plate, 0.0012)
    tang = G.prism("tang", [(-0.01, 0), (0.05, 0), (0.06, 0.035), (0.03, 0.075), (0.0, 0.06)], -0.004, 0.004, M("Stainless"))
    tang.matrix_world = Matrix.Translation((0, 0, 0.004)) @ Matrix.Rotation(math.radians(90), 4, "X")
    G.bake_xform(tang)
    G.finish(tang, 0.0012)
    objs = [plate, tang]
    for i, (x, z) in enumerate(((0.03, 0.06), (0.012, 0.035))):
        objs.append(G.finish(G.cyl(f"pin{i}", (x, -0.009, z), (x, 0.009, z), 0.003, M("Stainless"), 14), 0.0004))
    objs += G.screw_heads("s", [(-0.08, 0, 0.004), (-0.04, 0, 0.004), (0.02, 0, 0.004)], M("Stainless"), 0.0028)
    return done("Stemhead", objs, [("Forestay", (0.03, 0, 0.06)), ("Tack", (0.012, 0, 0.035))])


@part("MastStep", "rig", "Deck-stepped mast base: cast plate with a hinge pin and halyard turning blocks")
def mast_step():
    plate = G.prism("plate", G.rrect(0.22, 0.13, 0.03), 0, 0.012, M("Aluminium"), taper=0.92)
    G.finish(plate, 0.002)
    shoe = G.prism("shoe", G.rrect(0.14, 0.08, 0.025), 0.012, 0.060, M("Aluminium"), taper=0.96)
    G.finish(shoe, 0.002)
    pin = G.cyl("pin", (0.03, -0.05, 0.030), (0.03, 0.05, 0.030), 0.006, M("Stainless"), 16)
    G.finish(pin, 0.0008)
    objs = [plate, shoe, pin] + _fastener_ring(6, 0.095, 0.052, 0.012, M("Stainless"), 0.0035)
    for i, (x, y) in enumerate(((-0.09, -0.045), (-0.09, 0.045))):
        objs.append(G.finish(G.tube(f"eye{i}", G.arc_pts((x, y, 0.012), 0.009, 0, math.pi, 10, "xz"), 0.0028, M("Stainless"), 10)))
    return done("MastStep", objs, [("Mast", (0, 0, 0.060)), ("TurnP", (-0.09, -0.045, 0.02)), ("TurnS", (-0.09, 0.045, 0.02))])


# ------------------------------------------------------------------ hatches, ports, vents

@part("HatchFwd", "hatch", "Low-profile acrylic deck hatch, 500 x 500 mm: frame, smoked lid, hinges, two handles")
def hatch_fwd(w=0.50, d=0.50):
    frame = G.prism("frame", G.rrect(w, d, 0.05), 0, 0.018, M("Aluminium"), taper=0.985)
    G.finish(frame, 0.003)
    lid = G.prism("lid", G.rrect(w - 0.03, d - 0.03, 0.04), 0.018, 0.026, M("CabinWindow"), taper=0.995)
    G.finish(lid, 0.002)
    objs = [frame, lid]
    for s in (-1, 1):
        objs.append(G.finish(G.box(f"hinge{s}", (-w / 2 + 0.01, s * d * 0.3, 0.022), (0.03, 0.06, 0.012), M("Aluminium")), 0.002))
        objs.append(G.finish(G.tube(f"handle{s}", G.bezier((w / 2 - 0.05, s * d * 0.25 - 0.03, 0.026), (w / 2 - 0.05, s * d * 0.25 - 0.03, 0.045),
                                                            (w / 2 - 0.05, s * d * 0.25 + 0.03, 0.045), (w / 2 - 0.05, s * d * 0.25 + 0.03, 0.026), 10), 0.006, M("BlackPlastic"), 14)))
    objs += _fastener_ring(16, w / 2 - 0.012, d / 2 - 0.012, 0.018, M("Stainless"), 0.0025)
    return done("HatchFwd", objs, [("HandleS", (w / 2 - 0.05, d * 0.25, 0.04)), ("HandleP", (w / 2 - 0.05, -d * 0.25, 0.04)), ("Hinge", (-w / 2, 0, 0.02))])


@part("Portlight", "hatch", "Fixed portlight: smoked acrylic in a moulded rim with screws; length option")
def portlight(length=0.45, height=0.11):
    rim = G.prism("rim", G.rrect(length, height, height * 0.45), 0, 0.006, M("BlackPlastic"), taper=0.98)
    G.finish(rim, 0.002)
    pane = G.prism("pane", G.rrect(length - 0.02, height - 0.02, height * 0.4), 0.003, 0.007, M("CabinWindow"))
    G.finish(pane, 0.001)
    n = max(6, int(length / 0.07))
    pts = []
    for i in range(n):
        x = -length / 2 + 0.03 + i * (length - 0.06) / (n - 1)
        pts += [(x, height / 2 - 0.006, 0.006), (x, -height / 2 + 0.006, 0.006)]
    return done("Portlight", [rim, pane] + G.screw_heads("s", pts, M("Stainless"), 0.002, 0.001), [])


@part("VentMushroom", "hatch", "Low mushroom vent, 110 mm, stainless cap on a moulded base")
def vent_mushroom():
    base = G.lathe("base", [(0, 0), (0.055, 0), (0.055, 0.003), (0.040, 0.010), (0.025, 0.012), (0, 0.012)], M("BlackPlastic"), 40)
    G.finish(base, 0.0008)
    cap = G.lathe("cap", [(0, 0.016), (0.048, 0.016), (0.050, 0.020), (0.044, 0.030), (0.020, 0.036), (0, 0.037)], M("Stainless"), 48)
    G.finish(cap, 0)
    return done("VentMushroom", [base, cap] + _fastener_ring(4, 0.047, 0.047, 0.003, M("Stainless"), 0.0022), [])


@part("DeckPlate", "hatch", "Screw-out inspection deck plate, 100 mm")
def deck_plate():
    o = G.lathe("plate", [(0, 0.004), (0.050, 0.004), (0.052, 0.002), (0.052, 0), (0.0, 0)], M("BlackPlastic"), 48)
    G.finish(o, 0.0008)
    cap = G.lathe("cap", [(0, 0.004), (0.040, 0.004), (0.040, 0.008), (0.036, 0.009), (0, 0.009)], M("BlackPlastic"), 48)
    G.finish(cap, 0.0006)
    lug = G.box("lug", (0, 0, 0.011), (0.050, 0.008, 0.005), M("BlackPlastic"))
    G.finish(lug, 0.0015)
    return done("DeckPlate", [o, cap, lug], [])


@part("HandrailTeak", "trim", "Teak cabin-top handrail with N loops; length option")
def handrail(length=0.90, loops=4):
    h, t = 0.060, 0.030
    # the rail as one sweep over feet and arches, then the hand holes as the gaps between feet
    feet = loops + 1
    pitch = length / loops
    objs = []
    top = G.sweep("rail", [(-length / 2, 0, h - 0.012), (length / 2, 0, h - 0.012)], [(-t / 2, -0.012), (t / 2, -0.012), (t / 2, 0.006), (t * 0.3, 0.012), (-t * 0.3, 0.012), (-t / 2, 0.006)], M("Teak"))
    objs.append(G.finish(top, 0.003))
    for i in range(feet):
        x = -length / 2 + i * pitch
        x = min(max(x, -length / 2 + 0.03), length / 2 - 0.03)
        foot = G.prism(f"foot{i}", G.rrect(0.060, t, 0.008), 0, h - 0.024, M("Teak"), taper=0.94)
        foot.location = (x, 0, 0)
        G.bake_xform(foot)
        objs.append(G.finish(foot, 0.003))
        objs.append(G.finish(G.cyl(f"plug{i}", (x, 0, h - 0.001), (x, 0, h + 0.0005), 0.005, M("Teak"), 12), 0))
    return done("HandrailTeak", objs, [(f"Grip{i}", (-length / 2 + (i + 0.5) * pitch, 0, h - 0.012)) for i in range(loops)])


# ------------------------------------------------------------------ steering and outboard

@part("Tiller", "steering", "Laminated ash tiller, 1.05 m, tapered, with a rudder-head socket and an extension pivot")
def tiller(length=1.05):
    path = [(0, 0, 0), (-0.25, 0, 0.03), (-0.6, 0, 0.07), (-length, 0, 0.10)]
    path = G.bezier(path[0], path[1], path[2], path[3], 30)
    radii = [1.0 - 0.35 * (i / 30) for i in range(31)]
    body = G.sweep("tiller", path, [(p[0] * 0.018, p[1] * 0.024) for p in G.rrect(2, 2, 0.6, 4)], M("Wood"), radii=radii)
    G.finish(body, 0)
    head = G.prism("head", G.rrect(0.10, 0.048, 0.008), -0.032, 0.032, M("Aluminium"))
    head.matrix_world = Matrix.Translation((0.03, 0, 0))
    G.bake_xform(head)
    G.finish(head, 0.002)
    knob = G.lathe("knob", [(0, 0), (0.012, 0), (0.014, 0.008), (0.010, 0.016), (0, 0.017)], M("BlackPlastic"), 24)
    knob.matrix_world = Matrix.Translation((-length + 0.02, 0, 0.115))
    G.bake_xform(knob)
    G.finish(knob, 0)
    return done("Tiller", [body, head, knob], [("Stock", (0.03, 0, 0)), ("ExtPivot", (-length + 0.02, 0, 0.13)), ("Hand", (-length * 0.8, 0, 0.09))])


@part("TillerExtension", "steering", "1.0 m tiller extension: aluminium tube, rubber universal joint, foam grip, end knob")
def tiller_extension(length=1.0):
    tube = G.cyl("tube", (0, 0, 0.03), (length, 0, 0.03), 0.0095, M("Aluminium"), 24)
    tube.matrix_world = Matrix.Identity(4)
    G.finish(tube, 0.0006)
    uj = G.lathe("uj", [(0, 0), (0.012, 0), (0.016, 0.010), (0.012, 0.022), (0.012, 0.03), (0, 0.03)], M("BlackPlastic"), 24)
    for v in uj.data.vertices:          # moulded rubber ribs
        if 0.004 < v.co.z < 0.02:
            k = 1 + 0.06 * math.cos(v.co.z * 900)
            v.co.x *= k
            v.co.y *= k
    G.finish(uj, 0)
    grip = G.cyl("grip", (length * 0.55, 0, 0.03), (length - 0.03, 0, 0.03), 0.0135, M("BlackPlastic"), 24)
    BT.mark(G.finish(grip, 0.003), band="grip")
    knob = G.lathe("knob", [(0, 0), (0.016, 0), (0.019, 0.012), (0.012, 0.028), (0, 0.030)], M("BlackPlastic"), 24)
    knob.matrix_world = G.along((length - 0.03, 0, 0.03), (1, 0, 0))
    G.bake_xform(knob)
    G.finish(knob, 0)
    return done("TillerExtension", [tube, uj, grip, knob], [("UJ", (0, 0, 0)), ("Grip", (length * 0.8, 0, 0.03)), ("Tip", (length, 0, 0.03))])


@part("OutboardBracket", "outboard", "Two-position transom outboard bracket with a spring lift and lock pin")
def outboard_bracket():
    objs = []
    for s in (-1, 1):
        plate = G.prism(f"plate{s}", [(-0.02, 0), (0.0, 0), (0.0, 0.22), (-0.02, 0.22)], s * 0.10 - 0.003, s * 0.10 + 0.003, M("Stainless"))
        plate.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(plate)
        objs.append(G.finish(plate, 0.0015))
        for z in (0.06, 0.16):
            objs.append(G.finish(G.box(f"arm{s}{z}", (-0.09, s * 0.10, z), (0.15, 0.012, 0.025), M("Stainless")), 0.002))
    board = G.box("board", (-0.17, 0, 0.11), (0.03, 0.26, 0.20), M("Teak"))
    objs.append(G.finish(board, 0.004))
    spring = G.tube("spring", [(-0.08 + 0.008 * math.cos(i * 0.6), 0.008 * math.sin(i * 0.6), 0.05 + i * 0.002) for i in range(60)], 0.002, M("Stainless"), 8)
    objs.append(G.finish(spring))
    objs += G.screw_heads("s", [(0.0, s * 0.10, z) for s in (-1, 1) for z in (0.03, 0.19)], M("Stainless"), 0.004)
    return done("OutboardBracket", objs, [("Clamp", (-0.17, 0, 0.21)), ("Pin", (-0.09, 0.11, 0.11))])


@part("Outboard35", "outboard", "Generic 3.5 hp four-stroke outboard (brand-free): cowl, midsection, leg, skeg, 3-blade prop, tiller arm")
def outboard35():
    objs = []
    cowl = G.lathe("cowl", [(0, 0), (0.15, 0), (0.17, 0.05), (0.17, 0.20), (0.14, 0.27), (0.07, 0.30), (0, 0.305)], M("Deck"), 40)
    cowl.matrix_world = Matrix.Translation((0, 0, 0.60)) @ Matrix.Diagonal((1.25, 0.85, 1.0, 1))
    G.bake_xform(cowl)
    objs.append(G.finish(cowl, 0))
    band = G.lathe("band", [(0, 0), (0.175, 0), (0.175, 0.03), (0, 0.03)], M("BlackPlastic"), 40)
    band.matrix_world = Matrix.Translation((0, 0, 0.59)) @ Matrix.Diagonal((1.25, 0.85, 1.0, 1))
    G.bake_xform(band)
    objs.append(G.finish(band, 0.002))
    mid = G.prism("mid", G.rrect(0.20, 0.13, 0.05), 0.42, 0.59, M("Deck"), taper=1.05)
    objs.append(G.finish(mid, 0.004))
    leg = G.sweep("leg", [(0, 0, 0.10), (0, 0, 0.42)], [(x * 0.05, y * 0.025) for x, y in G.ellipse(1, 1, 20)], M("Aluminium"), radii=[0.9, 1.0])
    for v in leg.data.vertices:
        if v.co.x < 0:
            v.co.x *= 1.6                                   # foil-shaped leg, blunt nose forward
    objs.append(G.finish(leg, 0))
    torp = G.lathe("torpedo", [(0, -0.09), (0.035, -0.06), (0.042, 0.0), (0.04, 0.12), (0.03, 0.17), (0, 0.18)], M("Aluminium"), 32)
    torp.matrix_world = Matrix.Translation((0.05, 0, 0.11)) @ Matrix.Rotation(math.radians(-90), 4, "Y")
    G.bake_xform(torp)
    objs.append(G.finish(torp, 0))
    skeg = G.prism("skeg", [(-0.06, 0), (0.04, 0), (0.0, -0.11), (-0.04, -0.10)], -0.005, 0.005, M("Aluminium"))
    skeg.matrix_world = Matrix.Translation((0, 0, 0.08)) @ Matrix.Rotation(math.radians(90), 4, "X")
    G.bake_xform(skeg)
    objs.append(G.finish(skeg, 0.002))
    hub = G.lathe("hub", [(0, 0), (0.022, 0), (0.024, 0.04), (0.012, 0.07), (0, 0.075)], M("BlackPlastic"), 24)
    hub.matrix_world = Matrix.Translation((-0.13, 0, 0.11)) @ Matrix.Rotation(math.radians(-90), 4, "Y")
    G.bake_xform(hub)
    objs.append(G.finish(hub, 0))
    for k in range(3):
        a = G.TAU * k / 3
        blade = G.prism(f"blade{k}", [(0.0, -0.025), (0.09, -0.035), (0.11, 0.0), (0.085, 0.03), (0.0, 0.02)], -0.003, 0.003, M("BlackPlastic"))
        blade.matrix_world = Matrix.Translation((-0.15, 0, 0.11)) @ Matrix.Rotation(a, 4, "X") @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(math.radians(25), 4, "X") @ Matrix.Rotation(math.radians(-90), 4, "Z")
        G.bake_xform(blade)
        objs.append(G.finish(blade, 0.001))
    clamp = G.box("clamp", (0.12, 0, 0.62), (0.07, 0.14, 0.14), M("BlackPlastic"))
    objs.append(G.finish(clamp, 0.006))
    arm = G.sweep("arm", G.bezier((-0.15, 0, 0.66), (-0.30, 0, 0.67), (-0.42, 0, 0.70), (-0.55, 0, 0.72), 12), G.ellipse(0.016, 0.016, 16), M("BlackPlastic"), radii=[1 - 0.2 * i / 12 for i in range(13)])
    objs.append(G.finish(arm, 0))
    return done("Outboard35", objs, [("Clamp", (0.12, 0, 0.69)), ("TillerArm", (-0.55, 0, 0.72)), ("Prop", (-0.15, 0, 0.11)), ("Pivot", (0.12, 0, 0.62))])


# ------------------------------------------------------------------ hull fittings

@part("Gudgeon", "steering", "Transom-hung rudder gudgeon (cast strap with a bushed eye)")
def gudgeon():
    eye = G.lathe("eye", [(0.006, 0), (0.014, 0), (0.014, 0.030), (0.006, 0.030)], M("Stainless"), 24)
    eye.location = (0.026, 0, -0.015)
    G.bake_xform(eye)
    G.finish(eye, 0.001)
    straps = []
    for s in (-1, 1):
        st = G.prism(f"strap{s}", [(0.0, -0.014), (0.026, -0.010), (0.026, 0.010), (0.0, 0.014), (-0.10, 0.016), (-0.10, -0.016)], -0.0025, 0.0025, M("Stainless"))
        st.matrix_world = Matrix.Translation((0, s * 0.020, 0)) @ Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(st)
        straps.append(G.finish(st, 0.0008))
    return done("Gudgeon", [eye] + straps, [("Pin", (0.026, 0, 0))])


@part("BowEye", "hull", "Stainless U-bolt bow eye on the stem below the sheer, for the trailer winch")
def bow_eye():
    plate = G.prism("plate", G.rrect(0.040, 0.060, 0.012), 0, 0.003, M("Stainless"))
    G.finish(plate, 0.0008)
    loop = G.tube("loop", [(0, 0.012, 0.002)] + G.arc_pts((0, 0, 0.020), 0.012, 0, math.pi, 14, "yz") + [(0, -0.012, 0.002)], 0.0045, M("Stainless"), 14)
    G.finish(loop)
    return done("BowEye", [plate, loop], [("Eye", (0, 0, 0.032))])


@part("Scupper", "hull", "Cockpit drain thru-hull: flanged mushroom with a cross grille")
def scupper():
    fl = G.lathe("flange", [(0, 0), (0.028, 0), (0.028, 0.002), (0.020, 0.005), (0.013, 0.005), (0.013, -0.01), (0.0, -0.01)], M("Stainless"), 40)
    G.finish(fl, 0.0005)
    bars = [G.finish(G.box("bar0", (0, 0, 0.0015), (0.026, 0.003, 0.003), M("Stainless")), 0.0005),
            G.finish(G.box("bar1", (0, 0, 0.0015), (0.003, 0.026, 0.003), M("Stainless")), 0.0005)]
    return done("Scupper", [fl] + bars, [])


@part("Fender", "loose", "Ribbed vinyl fender, 150 x 500 mm, eyes at both ends")
def fender(colour="BlackPlastic"):
    prof = [(0, 0)]
    for i in range(41):
        z = 0.5 * i / 40
        r = 0.075 * math.sin(math.pi * min(1.0, 0.18 + 0.64 * i / 40)) ** 0.25
        r *= 1 + 0.015 * math.cos(G.TAU * i / 5)
        prof.append((r, z))
    prof.append((0, 0.5))
    body = G.lathe("body", prof, M(colour), 40)
    G.finish(body, 0)
    eyes = []
    for z, s in ((0.5, 1), (0, -1)):
        e = G.tube(f"eye{s}", G.arc_pts((0, 0, z + s * 0.012), 0.012, 0, G.TAU, 14, "xz"), 0.004, M(colour), 10, closed=True)
        eyes.append(G.finish(e))
    return done("Fender", [body] + eyes, [("Top", (0, 0, 0.524)), ("Bottom", (0, 0, -0.024))])


# ------------------------------------------------------------------ boat fidelity 2: lifelines, rigging screws, clutches, cars

@part("Stanchion", "lifeline", "25 mm stainless stanchion in a cast base, 610 mm (24 in), with a mid and a top lifeline eye; height option")
def stanchion(height=0.610):
    base = G.prism("base", G.rrect(0.090, 0.060, 0.010), 0, 0.006, M("Stainless"), taper=0.94)
    objs = [G.finish(base, 0.0012)]
    sock = G.lathe("socket", [(0, 0), (0.0175, 0), (0.0175, 0.012), (0.0150, 0.070), (0.0145, 0.085), (0, 0.085)], M("Stainless"), 32)
    objs.append(G.finish(sock, 0.0008))
    objs.append(G.finish(G.cyl("tube", (0, 0, 0.080), (0, 0, height - 0.012), 0.0127, M("Stainless"), 32), 0.0006))
    cap = G.lathe("cap", [(0, height - 0.014), (0.0135, height - 0.014), (0.0140, height - 0.004), (0.010, height), (0, height)], M("Stainless"), 32)
    objs.append(G.finish(cap, 0.0006))
    mid = height * 0.52
    ring = G.lathe("midring", [(0.0125, mid - 0.008), (0.0150, mid - 0.006), (0.0150, mid + 0.006), (0.0125, mid + 0.008)], M("Stainless"), 32)
    objs.append(G.finish(ring, 0.0004))
    objs += G.screw_heads("s", [(0.033, 0.019, 0.006), (0.033, -0.019, 0.006), (-0.033, 0.019, 0.006), (-0.033, -0.019, 0.006)], M("Stainless"), 0.0035)
    return done("Stanchion", objs, [("Base", (0, 0, 0)), ("LifelineTop", (0, 0, height - 0.008)), ("LifelineMid", (0, 0, mid))])


def _rail(name, path, feet, height, sockets):
    """A welded 25 mm stainless rail: the tube along `path`, legs from `feet` (x, y) up to the rail's height, cast bases."""
    objs = [G.finish(G.tube("rail", path, 0.0127, M("Stainless"), 20))]
    for i, (x, y) in enumerate(feet):
        top = min(path, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
        objs.append(G.finish(G.tube(f"leg{i}", [(x, y, 0.010), (top[0], top[1], top[2])], 0.0127, M("Stainless"), 20)))
        base = G.prism(f"base{i}", G.rrect(0.060, 0.050, 0.010), 0, 0.006, M("Stainless"), taper=0.92)
        base.location = (x, y, 0)
        G.bake_xform(base)
        objs.append(G.finish(base, 0.001))
        objs.append(G.finish(G.lathe(f"boss{i}", [(0, 0), (0.0175, 0), (0.0165, 0.030), (0, 0.030)], M("Stainless"), 24), 0.0006))
        objs[-1].location = (x, y, 0)
        G.bake_xform(objs[-1])
    return done(name, objs, sockets)


@part("BowPulpit", "lifeline", "Bow pulpit: a 25 mm stainless hoop over the stemhead, four legs, 610 mm high; width and length options")
def bow_pulpit(width=0.60, length=0.45, height=0.610):
    w = width / 2
    path = [(-0.0, -w, height)] + [(length * 0.55 + (length * 0.45) * math.sin(a), -w * math.cos(a), height) for a in [i * math.pi / 16 for i in range(17)]] + [(0.0, w, height)]
    feet = [(0.02, -w), (0.02, w), (length * 0.75, -w * 0.55), (length * 0.75, w * 0.55)]
    return _rail("BowPulpit", path, feet, height, [("LifelineP", (0.0, -w, height)), ("LifelineS", (0.0, w, height)), ("Bow", (length, 0, height))])


@part("Pushpit", "lifeline", "Stern pushpit: a 25 mm stainless rail round the transom corners, four legs, 610 mm; width and depth options")
def pushpit(width=1.50, depth=0.40, height=0.610):
    w = width / 2
    path = [(0.0, -w, height), (-depth * 0.7, -w, height)] + G.arc_pts((-depth * 0.7, -w + depth * 0.3, height), depth * 0.3, -math.pi / 2, -math.pi, 8, "xy")[1:] \
        + [(-depth, -w * 0.3, height)]
    path = [(p[0], p[1], height) for p in path]
    mirrored = [(p[0], -p[1], p[2]) for p in reversed(path)]
    path = path + mirrored
    feet = [(-0.02, -w), (-0.02, w), (-depth + 0.02, -w * 0.6), (-depth + 0.02, w * 0.6)]
    return _rail("Pushpit", path, feet, height, [("LifelineP", (0.0, -w, height)), ("LifelineS", (0.0, w, height)), ("Centre", (-depth, 0, height))])


@part("Turnbuckle", "rig", "Open-body rigging screw with toggle, for 5 mm wire: forged body, two threaded studs, swage eye up, toggle fork down")
def turnbuckle():
    L = 0.110                                  # body length
    objs = []
    for s in (-1, 1):
        bar = G.prism(f"bar{s}", G.rrect(0.006, 0.004, 0.0015), -L / 2, L / 2, M("Stainless"))
        bar.matrix_world = Matrix.Translation((0, s * 0.008, 0.080))
        G.bake_xform(bar)
        objs.append(G.finish(bar, 0.0006))
    for z in (0.080 - L / 2, 0.080 + L / 2):
        objs.append(G.finish(G.lathe(f"boss{z:.3f}", [(0, -0.006), (0.010, -0.006), (0.010, 0.006), (0, 0.006)], M("Stainless"), 24), 0.0008))
        objs[-1].location = (0, 0, z)
        G.bake_xform(objs[-1])
    lower = G.cyl("studL", (0, 0, 0.012), (0, 0, 0.080 - 0.010), 0.0035, M("Stainless"), 16)
    upper = G.cyl("studU", (0, 0, 0.080 + 0.010), (0, 0, 0.165), 0.0035, M("Stainless"), 16)
    objs += [G.finish(lower, 0.0003), G.finish(upper, 0.0003)]
    # Thread: fine rings on the studs (the hero's close-up), and lock nuts at the body.
    for z0, z1 in ((0.014, 0.060), (0.100, 0.150)):
        n = int((z1 - z0) / 0.0018)
        for k in range(n):
            z = z0 + k * (z1 - z0) / n
            objs.append(G.lathe(f"thr{z0}{k}", [(0.0034, z), (0.0040, z + 0.0005), (0.0034, z + 0.0010)], M("Stainless"), 12))
    swage = G.lathe("swage", [(0, 0.165), (0.0045, 0.165), (0.0045, 0.205), (0.0030, 0.215), (0, 0.216)], M("Stainless"), 20)
    objs.append(G.finish(swage, 0.0004))
    fork = G.prism("fork", G.rrect(0.014, 0.020, 0.004), 0.0, 0.016, M("Stainless"))
    objs.append(G.finish(fork, 0.0008))
    objs.append(G.finish(G.cyl("pin", (0, -0.012, 0.004), (0, 0.012, 0.004), 0.0025, M("Stainless"), 14), 0.0003))
    return done("Turnbuckle", objs, [("Toggle", (0, 0, 0.004)), ("Wire", (0, 0, 0.216))])


@part("Clutch", "rope", "Single rope clutch for 6 to 10 mm line on a moulded base, handle closed, maker's plate")
def clutch():
    base = G.prism("base", G.rrect(0.140, 0.050, 0.010), 0, 0.008, M("BlackPlastic"), taper=0.97)
    objs = [G.finish(base, 0.002)]
    body = G.prism("body", G.rrect(0.125, 0.040, 0.010), 0.008, 0.052, M("BlackPlastic"), taper=0.86)
    objs.append(G.finish(body, 0.004))
    handle = G.prism("handle", G.rrect(0.110, 0.030, 0.008), 0.052, 0.066, M("Aluminium"), taper=0.9)
    handle.location = (-0.008, 0, 0)
    G.bake_xform(handle)
    objs.append(G.finish(handle, 0.003))
    objs.append(badge("plate", "Plate", 0.050, 0.014, Matrix.Translation((-0.008, 0, 0.066)), M("BlackPlastic")))
    objs += G.screw_heads("s", [(0.058, 0, 0.008), (-0.058, 0, 0.008)], M("Stainless"), 0.004, 0.0015)
    return done("Clutch", objs, [("LineIn", (-0.07, 0, 0.032)), ("LineOut", (0.07, 0, 0.032))])


@part("TrackCar", "track", "T-track car for 25 mm track: a sheave between stainless cheeks and a plunger stop (the jib lead car alone)")
def track_car():
    objs = []
    car = G.prism("car", G.rrect(0.090, 0.040, 0.010), 0.0, 0.018, M("Aluminium"), taper=0.85)
    objs.append(G.finish(car, 0.002))
    ch = 0.018
    sh = G.lathe("sheave", [(0.004, 0), (0.019, 0), (0.019, 0.002), (0.016, 0.005), (0.019, 0.008), (0.019, 0.010), (0.004, 0.010)], M("BlackPlastic"), 32)
    sh.matrix_world = Matrix.Translation((0.010, -0.005, ch + 0.019)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    G.bake_xform(sh)
    objs.append(G.finish(sh, 0, sharp=60))
    for s in (-1, 1):
        cheek = G.prism(f"cheek{s}", [(-0.012, 0), (0.035, 0), (0.030, 0.035), (-0.004, 0.035)], 0, 0.003, M("Stainless"))
        cheek.matrix_world = Matrix.Translation((0.0, s * 0.0085 - 0.0015, ch)) @ Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(cheek)
        objs.append(G.finish(cheek, 0.0006))
    plunger = G.cyl("plunger", (-0.034, 0, ch), (-0.034, 0, ch + 0.016), 0.006, M("BlackPlastic"), 20)
    objs.append(G.finish(plunger, 0.0015))
    return done("TrackCar", objs, [("Sheave", (0.010, 0, ch + 0.019)), ("Track", (0, 0, 0)), ("Plunger", (-0.034, 0, ch + 0.016))])


# Sizes from small-boat hardware catalogues' published dimensions (boat fidelity 2). "scale" sizes are the default
# build scaled about its mount point (a component scale in the game); "kw" sizes rebuild with the builder's own options
# (tube parts whose wall and diameter don't scale with length). The value is what the catalogue lists.
SIZES = {
    "ShackleD":   {"dim": "pin diameter mm", "default": "5", "scale": {"4": 0.8, "5": 1.0, "6": 1.2, "8": 1.6, "10": 2.0}},
    "Padeye":     {"dim": "plate length mm", "default": "50", "scale": {"40": 0.8, "50": 1.0, "65": 1.3}},
    "HornCleat":  {"dim": "length mm", "default": "150", "kw": {"100": {"length": 0.100}, "150": {"length": 0.150}, "200": {"length": 0.200}, "250": {"length": 0.250}}},
    "CamCleat":   {"dim": "length mm", "default": "75", "scale": {"38": 0.51, "75": 1.0, "102": 1.36}},
    "Fairlead":   {"dim": "outside diameter mm", "default": "32", "scale": {"25": 0.78, "32": 1.0, "44": 1.375}},
    "Block29":    {"dim": "sheave mm", "default": "29", "scale": {"22": 0.76, "29": 1.0}},
    "Block40":    {"dim": "sheave mm", "default": "40", "scale": {"40": 1.0, "57": 1.425}},
    "Ratchet57":  {"dim": "sheave mm", "default": "57", "scale": {"57": 1.0, "75": 1.316}},
    "Winch16":    {"dim": "winch size (base diameter 102 / 120 / 130 / 152 / 175 mm)", "default": "16",
                   "scale": {"8": 0.85, "16": 1.0, "20": 1.083, "30": 1.267, "40": 1.458}},
    "Winch70":    {"dim": "winch size", "default": "70", "kw": {"50": {"scale": 0.85}, "70": {"scale": 1.0}}},
    "JibTrack":   {"dim": "track length mm", "default": "600", "kw": {"450": {"length": 0.45}, "600": {"length": 0.60}, "900": {"length": 0.90}}},
    "Traveler":   {"dim": "track length mm", "default": "900", "kw": {"600": {"length": 0.60}, "900": {"length": 0.90}, "1500": {"length": 1.50}}},
    "Chainplate": {"dim": "wire mm", "default": "5", "scale": {"4": 0.85, "5": 1.0, "6": 1.15}},
    "Turnbuckle": {"dim": "wire mm", "default": "5", "scale": {"4": 0.85, "5": 1.0, "6": 1.18, "8": 1.5}},
    "Stanchion":  {"dim": "height mm", "default": "610", "kw": {"457": {"height": 0.457}, "610": {"height": 0.610}, "760": {"height": 0.760}}},
    "BowPulpit":  {"dim": "width mm", "default": "600", "kw": {"450": {"width": 0.45, "length": 0.35}, "600": {"width": 0.60}, "800": {"width": 0.80, "length": 0.60}}},
    "Pushpit":    {"dim": "width mm", "default": "1500", "kw": {"1200": {"width": 1.20}, "1500": {"width": 1.50}, "2000": {"width": 2.00, "depth": 0.50}}},
    "Clutch":     {"dim": "line mm", "default": "10", "scale": {"8": 0.85, "10": 1.0, "14": 1.3}},
    "TillerExtension": {"dim": "length mm", "default": "1000", "kw": {"610": {"length": 0.61}, "1000": {"length": 1.0}, "1220": {"length": 1.22}}},
}


def build(name, size=None, **kw):
    """Build a part; `size` (a SIZES key) scales the default build or rebuilds it with that size's options."""
    fn, _ = PARTS[name]
    spec = SIZES.get(name)
    if size is None or spec is None or size == spec["default"]:
        return fn(**kw)
    if "kw" in spec:
        ob = fn(**{**spec["kw"][size], **kw})
    else:
        ob = fn(**kw)
        f = spec["scale"][size]
        ob.data.transform(Matrix.Scale(f, 4))
        for c in ob.children:
            c.location = c.location * f
    ob.name = f"{ob.name}_{size}"
    return ob
