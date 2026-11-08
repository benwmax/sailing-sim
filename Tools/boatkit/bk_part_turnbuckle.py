"""The kit's Turnbuckle (part detail loop, Nov 2026: docs/part-detail-loop/turnbuckle.md).

An open-body rigging screw for 3/16 in (5 mm) wire as small keelboats use on their shrouds: a forged jaw that straddles
the chainplate with a 1/4 in clevis pin and split ring, a threaded stud up into a forged open body with two long windows
and a centre bridge, cotter pins through the studs' ends inside the windows, and a threaded swage stud whose sleeve is
crimped onto the wire. Sizes from the catalogue (Hayn 3/16 in jaw-to-swage: 1/4-28 thread, 1/4 in pin, 6-5/8 in closed to
9-3/8 in open, pin to swage end); proportions of the jaw, body and sleeve from Bean's reference photo.

Frame (as bk_parts): the jaw's pin is the origin, on the chainplate's Pin socket, the pin along Y (the strap is thin in
Y), the wire up +Z. The body's windows look along Y, so the side view (along Y) shows them and the jaw's prong face.
`exposed` is the thread showing between the body and each end (how far the turnbuckle is opened); the default sets the
wire's end 216 mm above the pin, where the old part had it (Tools/blender/build_fleet.py's C22_TURNBUCKLE_TOP).

Kept in its own file so the loop's other parts can be worked at the same time (bk_parts imports every bk_part_*.py).
"""
import math

import bmesh

from mathutils import Matrix

import bk_geom as G
import bk_parts as P

IN = 0.0254
PIN_R = 0.25 * IN / 2          # 1/4 in clevis pin
THREAD_R = 0.25 * IN / 2       # 1/4-28 studs
PITCH = IN / 28
WIRE_R = 3 / 16 * IN / 2
JAW_W = 0.0195                 # jaw width across X (side view), photo: 1.14 x the body
HEAD_W = 0.0205                # the forged head above the prongs, the jaw's widest (photo)
JAW_GAP = 0.007                # between the prongs: a 6 mm chainplate strap
PRONG_T = 0.0042
JAW_R = 0.0095                 # the prongs' round ends about the pin
NECK_Z = 0.028                 # top of the jaw's forged neck: the thread starts here
BODY_L = 0.076                 # forged open body for 1/4-28 (closed length 6-5/8 in less the ends)
BODY_W = 0.0178                # across the windows' face (X); photo: 0.88 x the jaw's head
BODY_D = 0.0115                # edge-on (Y)
BOSS_R = 0.0056
WIN_W = 0.0066                 # each window's width (X); rails 5.2 mm
BRIDGE = 0.006                 # the centre bridge between the windows
SLEEVE_R = 0.0040              # swage sleeve (5/16 in) for 3/16 in wire
SLEEVE_L = 0.046
TOP = 0.216                    # pin to the sleeve's end, the old part's wire end (build_fleet C22_TURNBUCKLE_TOP)


def _loft(name, sections, mat, segs=6):
    """Loft rounded-rectangle sections [(z, half_x, half_y, corner r)] along Z into one closed mesh."""
    bm = bmesh.new()
    rings = []
    for z, hx, hy, r in sections:
        rings.append([bm.verts.new((x, y, z)) for x, y in G.rrect(2 * hx, 2 * hy, r, segs)])
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _thread(name, z0, z1, mat, segs=16):
    """A 1/4-28 thread from z0 to z1: a V profile turned round the stud (rings read as thread at arm's reach)."""
    prof = [(0, z0), (THREAD_R * 0.80, z0)]
    n = max(1, int((z1 - z0) / PITCH))
    p = (z1 - z0) / n
    for k in range(n):
        z = z0 + k * p
        prof += [(THREAD_R * 0.74, z + p * 0.05), (THREAD_R * 1.04, z + p * 0.5)]   # r5: deeper V
    prof += [(THREAD_R * 0.80, z1), (0, z1)]
    return G.finish(G.lathe(name, prof, mat, segs), 0, weighted=False, sharp=25)   # hard crests catch the light


def _stadium(w, h, segs=10):
    """A slot outline w wide (X) and h long (Y), round ends."""
    r = w / 2
    pts = [(r * math.cos(a), h / 2 - r + r * math.sin(a)) for a in [i * math.pi / segs for i in range(segs + 1)]]
    pts += [(r * math.cos(a), -h / 2 + r + r * math.sin(a)) for a in [math.pi + i * math.pi / segs for i in range(segs + 1)]]
    return pts


def _cut_y(ob, outline_xz, z_mid, depth=0.03, flare=1.0, face=None):
    """Cut a through-hole along Y whose outline is given in (x, z - z_mid). With `flare` > 1 and `face` (the half
    depth of the body), each side's cut opens out to the face, so the window's edge reads as a forged chamfer."""
    if flare == 1.0 or face is None:
        cuts = [(-depth / 2, depth / 2, 1.0)]
    else:
        cuts = [(0.0, face + 0.0004, flare), (0.0, -(face + 0.0004), flare)]
    for z0, z1, tp in cuts:
        c = G.prism("cut", outline_xz, min(z0, z1), max(z0, z1), taper=1.0)
        if tp != 1.0:
            # scale the outer end of the cutter out by `tp` (about its centre) so the hole flares toward the face
            for v in c.data.vertices:
                if abs(v.co.z) > 1e-6:
                    v.co.x *= tp
                    v.co.y = v.co.y * (1 + (tp - 1) * 0.5)
            c.data.update()
        c.matrix_world = Matrix.Translation((0, 0, z_mid)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        G.bake_xform(c)
        G.boolean(ob, c)
    return ob


def _jaw(objs, M):
    # two prongs straddling the strap: a round end about the pin, straight up into the head
    for s in (-1, 1):
        y0 = s * JAW_GAP / 2
        y1 = s * (JAW_GAP / 2 + PRONG_T)
        prof = [(JAW_R * math.cos(a), JAW_R * math.sin(a)) for a in [math.pi + i * math.pi / 16 for i in range(17)]]
        prof = prof + [(JAW_W / 2, 0.013), (-JAW_W / 2, 0.013)]
        # built in XY and turned +90 degrees about X, which takes (x, y, z) to (x, -z, y): the extrusion runs along -Y
        pr = G.prism(f"jaw_prong{s}", prof, -max(y0, y1), -min(y0, y1), M)
        pr.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(pr)
        objs.append(G.finish(pr, 0.0009))
    # the solid head where the prongs join, necking down round to the thread
    hy = JAW_GAP / 2 + PRONG_T
    # (r2: square shoulders kept full width up to 23 mm, as the photo's jaw, then a short round neck)
    head = _loft("jaw_head", [(0.0115, JAW_W / 2, hy, 0.003), (0.0145, HEAD_W / 2, hy, 0.003), (0.0215, HEAD_W / 2, hy, 0.003),
                              (0.0235, HEAD_W / 2 - 0.0014, hy - 0.0010, 0.0035), (0.0252, 0.0052, 0.0050, 0.0049),
                              (NECK_Z, 0.0042, 0.0042, 0.0041)], M)
    objs.append(G.finish(head, 0.0006))
    # the clevis pin: domed head on -Y, split ring through its end on +Y
    yl, yr = -(hy + 0.0016), hy + 0.0035
    objs.append(G.finish(G.cyl("pin", (0, yl, 0), (0, yr, 0), PIN_R, M, 20), 0.0004))
    ph = G.lathe("pin_head", [(0, 0), (0.0052, 0), (0.0052, 0.0007), (0.0040, 0.0016), (0, 0.0019)], M, 24)
    ph.matrix_world = Matrix.Translation((0, yl, 0)) @ Matrix.Rotation(math.radians(90), 4, "X")
    G.bake_xform(ph)
    objs.append(G.finish(ph, 0, weighted=False))
    # split ring: two turns of flat wire, through a hole across the pin's end, hanging below it
    R, yh = 0.0052, hy + 0.0022
    pts = []
    for i in range(65):
        a = math.pi / 2 + 2 * math.pi * 1.85 * i / 64
        pts.append((R * math.cos(a), yh + 0.0009 * i / 64, -R + R * math.sin(a)))
    objs.append(G.finish(G.sweep("pin_ring", pts, G.ellipse(0.00045, 0.00045, 8), M), 0, weighted=False))


def _body(objs, z0, M):
    """The forged open body: a lens-shaped loft between round end bosses, two windows cut through it, the bore along Z."""
    L = BODY_L
    hx, hy = BODY_W / 2, BODY_D / 2
    secs = []
    for t, sx, sy in ((0.0, BOSS_R * 0.92, BOSS_R * 0.92), (0.012, BOSS_R, BOSS_R), (0.05, BOSS_R, BOSS_R),
                      (0.12, hx * 0.86, hy), (0.20, hx * 0.98, hy), (0.30, hx, hy), (0.70, hx, hy), (0.80, hx * 0.98, hy),
                      (0.88, hx * 0.86, hy), (0.95, BOSS_R, BOSS_R), (0.988, BOSS_R, BOSS_R), (1.0, BOSS_R * 0.92, BOSS_R * 0.92)):
        r = min(sx, sy) * (0.98 if sx <= BOSS_R + 1e-6 else 0.62)
        secs.append((z0 + t * L, sx, sy, r))
    body = _loft("body", secs, M, segs=8)
    win = (L - 2 * 0.009 - BRIDGE) / 2            # each window's length
    for k in (0, 1):
        zc = z0 + 0.009 + win / 2 + k * (win + BRIDGE)
        _cut_y(body, _stadium(WIN_W * 0.86, win, 10), zc, flare=1.45, face=hy)
    bore = G.cyl("bore", (0, 0, z0 - 0.01), (0, 0, z0 + L + 0.01), THREAD_R * 0.98, None, 16)
    G.boolean(body, bore)
    objs.append(G.finish(body, 0.0007))
    return z0 + 0.009, z0 + 0.009 + win, z0 + L - 0.009 - win, z0 + L - 0.009


def _cotter(objs, z, M):
    """A small cotter pin across the stud's end (along X), its eye on one side and its legs bent back on the other."""
    r = 0.0008                                    # r5: thicker, so it reads in the window
    objs.append(G.finish(G.cyl("cotter", (-THREAD_R - 0.0012, 0, z), (THREAD_R + 0.0015, 0, z), r, M, 8), 0, weighted=False))
    eye = G.tube("cotter_eye", [(-THREAD_R - 0.0012 + 0.0011 * math.cos(a), 0, z + 0.0011 * math.sin(a))
                                for a in [math.pi / 2 + i * math.pi / 8 for i in range(17)]], r, M, 8, closed=False)
    objs.append(G.finish(eye, 0, weighted=False))
    for s in (-1, 1):
        objs.append(G.finish(G.tube(f"cotter_leg{s}", [(THREAD_R + 0.0012, 0, z), (THREAD_R + 0.0022, 0, z + s * 0.0022)], r, M, 8),
                             0, weighted=False))


@P.part("Turnbuckle", "rig", "Open-body rigging screw for 3/16 in (5 mm) wire: jaw with clevis pin and split ring on the "
                             "chainplate, forged open body with two windows, threaded studs with cotter pins, swage stud up")
def turnbuckle(exposed=None):
    M = P.M("Stainless")
    objs = []
    _jaw(objs, M)
    if exposed is None:                           # the kit's setting: the sleeve's end at TOP above the pin
        exposed = (TOP - NECK_Z - BODY_L - SLEEVE_L) / 2
    zb = NECK_Z + exposed                         # bottom of the body
    w1a, w1b, w2a, w2b = _body(objs, zb, M)
    zt = zb + BODY_L                              # top of the body
    zs = zt + exposed                             # bottom of the swage sleeve
    top = zs + SLEEVE_L
    # lower stud: from the jaw's neck up into the first window, its end pinned
    lo_end = w1a + (w1b - w1a) * 0.62
    objs.append(_thread("stud_lower", NECK_Z - 0.001, lo_end, M))
    _cotter(objs, lo_end - 0.0022, M)
    # upper stud: from the second window up out of the body to the swage sleeve
    up_end = w2b - (w2b - w2a) * 0.62
    objs.append(_thread("stud_upper", up_end, zs + 0.001, M))
    _cotter(objs, up_end + 0.0022, M)
    # the swage sleeve crimped onto the wire: a shoulder off the thread, the rolled sleeve, its taper and the wire's hole
    sl = G.lathe("swage", [(0, zs), (THREAD_R * 1.02, zs), (SLEEVE_R * 0.96, zs + 0.0025), (SLEEVE_R, zs + 0.0035),
                           (SLEEVE_R, top - 0.012), (SLEEVE_R * 0.97, top - 0.010), (SLEEVE_R * 0.97, top - 0.008),
                           (SLEEVE_R, top - 0.0075), (SLEEVE_R * 0.92, top - 0.0035), (SLEEVE_R * 0.80, top - 0.0004),
                           (WIRE_R * 1.08, top), (WIRE_R * 0.98, top - 0.0010), (0, top - 0.0010)], M, 24)
    objs.append(G.finish(sl, 0, weighted=False, sharp=40))
    return P.done("Turnbuckle", objs, [("Toggle", (0, 0, 0)), ("Wire", (0, 0, top))])


P.SIZES["Turnbuckle"] = {"dim": "wire mm", "default": "5", "scale": {"4": 0.85, "5": 1.0, "6": 1.18, "8": 1.5}}
