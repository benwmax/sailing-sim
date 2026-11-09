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

import bmesh

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
    names = [o.name for o in objs if o is not None]
    ob = G.join(f"SM_Kit_{name}", objs)
    ob["bk_parts"] = names                      # what it was joined from: the part loop's feature check reads these
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


@part("HornCleat", "cleat", "Cast aluminium open-base horn cleat, 150 mm (6 in), line hole, two through-bolts")
def horn_cleat(length=0.150):
    """Part detail loop round 1 (Nov 2026, docs/part-detail-loop): a cast open-base cleat. The side outline follows the
    square-on reference photo's proportions (fractions of the length), the height the catalogue's 6 in open-base cleat
    (1.88 in). Built as overlapping pedestal and horn shapes, fused by a voxel remesh so the joins get the soft fillets of
    a casting, then cut flat underneath, drilled for the line hole and reduced to the budget."""
    return done("HornCleat", *_cast_cleat_parts("HornCleat", length))


# side profile of a cast open-base cleat as fractions of its length (measured on the square-on reference photo)
_CLEAT_PED = [(0.000, 0.228), (0.010, 0.228), (0.020, 0.222), (0.030, 0.212), (0.040, 0.202), (0.050, 0.193),
              (0.060, 0.187), (0.080, 0.178), (0.100, 0.171), (0.120, 0.169), (0.140, 0.176), (0.150, 0.185),
              (0.160, 0.202), (0.170, 0.230), (0.180, 0.262), (0.190, 0.300), (0.200, 0.345), (0.210, 0.395)]
#                (|x|, horn top, horn underside)
_CLEAT_HORN = [(0.00, 0.263, None), (0.10, 0.266, None), (0.20, 0.272, 0.188), (0.25, 0.280, 0.183),
               (0.30, 0.288, 0.193), (0.35, 0.294, 0.204), (0.40, 0.300, 0.214), (0.44, 0.305, 0.222),
               (0.47, 0.307, 0.228), (0.50, 0.290, 0.248)]


def _lerp_tab(tab, x, col=1):
    for a, b in zip(tab, tab[1:]):
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return a[col] + (b[col] - a[col]) * t
    return tab[-1][col] if x > tab[-1][0] else tab[0][col]


def _loft_z(name, rings, mat):
    """Close a stack of same-length horizontal outlines [(z, [(x, y), ...]), ...] into a solid."""
    bm = bmesh.new()
    vs = [[bm.verts.new((x, y, z)) for x, y in pts] for z, pts in rings]
    n = len(vs[0])
    for a, b in zip(vs, vs[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(list(reversed(vs[0])))
    bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _oval_sweep(name, path, half_w, half_h, mat, segs=24):
    """A tube along a path in the XZ plane whose oval section is half_w across (Y) and half_h in the path's plane."""
    bm = bmesh.new()
    P_ = [Vector(p) for p in path]
    rings = []
    for i, p in enumerate(P_):
        t = (P_[min(i + 1, len(P_) - 1)] - P_[max(i - 1, 0)]).normalized()
        u = Vector((0, 1, 0))
        v = t.cross(u).normalized()
        if v.z < 0:
            v = -v
        rings.append([bm.verts.new(p + u * (half_w[i] * math.cos(G.TAU * k / segs)) + v * (half_h[i] * math.sin(G.TAU * k / segs)))
                      for k in range(segs)])
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _cast_cleat_parts(name, L, foot_w=0.029, waist_w=0.017, top_w=0.0135, horn_w=0.016, tip_w=0.012, hole_d=0.087,
                      voxel=0.0004, tris=15000):
    al, ss = M("Aluminium"), M("Stainless")
    # pedestal: horizontal rounded-rectangle sections from just under the deck up into the horns
    rings = []
    zs = [-0.004] + [z for z, _ in _CLEAT_PED]
    for i, zf in enumerate(zs):
        z = zf * L
        a = _lerp_tab(_CLEAT_PED, max(zf, 0.0)) * L
        t = min(1.0, max(0.0, zf / 0.10))
        w = foot_w + (waist_w - foot_w) * (1 - (1 - t) ** 2)          # flares out to the foot like the length does
        w -= (waist_w - top_w) * min(1.0, max(0.0, (zf - 0.12) / 0.08))  # and narrows under the horn so it doesn't step
        rings.append((z, G.rrect(2 * a, w, min(w * 0.45, a), 6)))
    ped = _loft_z("pedestal", rings, al)
    # horns: one sweep tip to tip along the middle of the horn, an oval section scaled by the horn's thickness
    xs = [i / 40.0 * 0.47 for i in range(41)]
    xs = [-x for x in reversed(xs[1:])] + xs
    path, radii = [], []
    for xf in xs:
        ax = abs(xf)
        top = _lerp_tab(_CLEAT_HORN, ax)
        bot = _lerp_tab([r for r in _CLEAT_HORN if r[2] is not None], ax, 2) if ax >= 0.20 else 0.188 + (0.20 - ax) * 0.0
        th = (top - bot) * L
        path.append((xf * L, 0.0, (top + bot) / 2 * L))
        radii.append(th / 2)
    hw = [horn_w / 2 + (tip_w / 2 - horn_w / 2) * min(1.0, abs(p[0]) / (0.47 * L)) for p in path]
    horn = _oval_sweep("horn", path, hw, radii, al)
    # round knob ends: an ellipsoid on each tip, a little fatter than the horn
    knobs = []
    for sgn in (-1, 1):
        x = sgn * 0.47 * L
        zc = (_lerp_tab(_CLEAT_HORN, 0.47) + _lerp_tab(_CLEAT_HORN, 0.47, 2)) / 2 * L
        rz = (_lerp_tab(_CLEAT_HORN, 0.47) - _lerp_tab(_CLEAT_HORN, 0.47, 2)) / 2 * L * 1.05
        k = G.lathe(f"knob{sgn}", [(math.sin(math.pi * i / 16), -math.cos(math.pi * i / 16)) for i in range(17)], al, 32)
        k.data.transform(Matrix.Diagonal((0.03 * L, tip_w / 2 * 1.04, rz, 1.0)))
        k.location = (x, 0, zc)
        G.bake_xform(k)
        knobs.append(k)
    body = G.join("body", [ped, horn] + knobs)
    # fuse: voxel remesh (one closed casting with filleted joins), a light smooth, then cut flat and drill
    m = body.modifiers.new("fuse", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", voxel, 0.0
    sm = body.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 4
    G.apply(body)
    floor = G.box("floor", (0, 0, -0.05), (L * 2, L, 0.1))
    G.boolean(body, floor)
    zh = 0.126 * L
    hole = G.cyl("hole", (0, -0.05, zh), (0, 0.05, zh), hole_d / 2 * L, None, 40)
    G.boolean(body, hole)
    d = body.modifiers.new("budget", "DECIMATE")
    me = body.data
    me.calc_loop_triangles()
    d.ratio = min(1.0, tris / max(1, len(me.loop_triangles)))
    G.apply(body)
    G.finish(body, 0.0006, segs=2, angle=60, sharp=60)        # only the foot's edge and the hole's rim are sharp
    body.name = "casting"
    # two through-bolts on the top flat: hex heads in shallow spot faces
    bolts = []
    for sgn in (-1, 1):
        x = sgn * 0.125 * L
        zt = _lerp_tab(_CLEAT_HORN, 0.125) * L
        hexo = [(0.0042 * math.cos(G.TAU * i / 6 + math.pi / 6), 0.0042 * math.sin(G.TAU * i / 6 + math.pi / 6)) for i in range(6)]
        b = G.prism(f"bolt{sgn}", hexo, zt - 0.0012, zt + 0.0016, ss, taper=0.9)
        b.location = (x, 0, 0)
        G.bake_xform(b)
        bolts.append(G.finish(b, 0.0004, segs=1))
        face = G.cyl(f"spot{sgn}", (x, 0, zt - 0.0016), (x, 0, zt - 0.0011), 0.0062, al, 24)
        bolts.append(G.finish(face, 0.0003, segs=1))
    top = _lerp_tab(_CLEAT_HORN, 0.0) * L
    tipz = (_lerp_tab(_CLEAT_HORN, 0.47) + _lerp_tab(_CLEAT_HORN, 0.47, 2)) / 2 * L
    socks = [("Wrap", (0, 0, top)), ("HornFwd", (L / 2, 0, tipz)), ("HornAft", (-L / 2, 0, tipz)), ("Hole", (0, 0, zh))]
    return [body] + bolts, socks


@part("CamCleat", "cleat", "Composite cam cleat, 38 mm axle centres: two toothed teardrop cams on a moulded base")
def cam_cleat(spacing=0.038):
    """Part detail loop (Nov 2026, docs/part-detail-loop): a moulded composite cam cleat like Bean's reference photo.
    The top-view proportions are the photo's (as fractions of the width across the cams), the axle centres the
    catalogue's 38 mm class (M5 screws). The line runs along X between the cams; the cams' toothed tips point to -X,
    the side the load comes from (the Lead socket)."""
    S = spacing
    W = S / 0.618                            # width across the cams (photo: axle centres are 0.618 of it)
    al, bk, red, ss = M("Aluminium"), M("BlackPlastic"), M("Graphics"), M("Stainless")
    zb, zc, zr, zs = 0.0055, 0.0160, 0.0180, 0.0192          # base top, cam top, bushing top, screw top
    objs = []
    # moulded base: a rounded slab across the line, its ends under the cams' backs
    half = S / 2 + 0.205 * W
    x0, x1 = -0.188 * W, 0.222 * W
    base = G.prism("base", [(x + (x0 + x1) / 2, y) for x, y in G.rrect(x1 - x0, 2 * half, 0.2 * W, 8)], 0, zb, bk, taper=0.97)
    objs.append(G.finish(base, 0.0018, segs=3))
    for side in (-1, 1):
        ay = side * S / 2
        inward = -side                        # toward the line
        # teardrop: a round back about the axle and a toothed flank running out to the tip
        rc = 0.20 * W
        ring = [(rc * math.cos(G.TAU * i / 48), rc * math.sin(G.TAU * i / 48)) for i in range(48)]
        tip, bulge, outer = (-0.36 * W, 0.0), (-0.21 * W, inward * 0.153 * W), (-0.21 * W, -inward * 0.096 * W)
        hull = _hull2d(ring + [tip, bulge, outer])
        # teeth: a raked sawtooth along the inner flank, from the tip back to where the flank meets the round back
        out = []
        for i, p in enumerate(hull):
            q = hull[(i + 1) % len(hull)]
            out.append(p)
            mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            if mid[1] * inward > 0.02 * W and mid[0] < 0.06 * W:           # inner flank, wrapping onto the round back
                dx, dy = q[0] - p[0], q[1] - p[1]
                L = math.hypot(dx, dy)
                n = max(1, int(L / 0.0021))           # fine raked teeth (round 2's bolder 3 mm teeth lost the blind review)
                nx, ny = dy / L, -dx / L
                if nx * (mid[0]) + ny * (mid[1]) < 0:
                    nx, ny = -nx, -ny
                for k in range(n):
                    t0, t1 = k / n, (k + 0.7) / n
                    out.append((p[0] + dx * t0 + nx * 0.0, p[1] + dy * t0))
                    out.append((p[0] + dx * t1 + nx * 0.0015, p[1] + dy * t1 + ny * 0.0015))
        cam = G.prism(f"cam{side}", [(x, y + ay) for x, y in out], zb - 0.0004, zc, bk)
        objs.append(G.finish(cam, 0.0020, segs=4, angle=40, sharp=55))     # softly rounded top edge, like a moulding
        # chunky red bushing standing proud of the cam (a recessed one lost the blind review), domed at its rim
        bush = G.lathe(f"bushing{side}", [(0.0026, zc - 0.0004), (0.0070, zc - 0.0004), (0.0070, zr - 0.0010), (0.0066, zr - 0.0003),
                                           (0.0058, zr), (0.0036, zr), (0.0032, zr - 0.0004), (0.0026, zr - 0.0004)], red, 40)
        bush.location = (0, ay, 0)
        G.bake_xform(bush)
        objs.append(G.finish(bush, 0, weighted=False))
        scr = G.lathe(f"screw{side}", [(0, zr - 0.0005), (0.0030, zr - 0.0005), (0.0029, zr + 0.0005), (0.0024, zs - 0.0002), (0.0012, zs), (0, zs)], ss, 32)
        scr.location = (0, ay, 0)
        G.bake_xform(scr)
        for ang in (0, 90):
            cut = G.box("x", (0, 0, zs), (0.0034, 0.0007, 0.0016))
            cut.matrix_world = Matrix.Translation((0, ay, 0)) @ Matrix.Rotation(math.radians(ang + 45), 4, "Z")
            G.bake_xform(cut)
            G.boolean(scr, cut)
        objs.append(G.finish(scr, 0, weighted=False))
    socks = [("Line", (0.0, 0, (zb + zc) / 2)), ("Lead", (-0.36 * W, 0, (zb + zc) / 2)),
             ("AxleL", (0, -S / 2, zc)), ("AxleR", (0, S / 2, zc))]
    return done("CamCleat", objs, socks)


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


def _xz_prism(name, outline_xz, y0, y1, mat):
    """Extrude an outline drawn in the block's XZ plane (x forward, z up) across Y from y0 to y1."""
    o = G.prism(name, outline_xz, -y1, -y0, mat)
    o.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")       # prism (x, v, e) -> (x, -e, v)
    G.bake_xform(o)
    return o


def _hull2d(pts):
    """Convex hull (monotone chain), counter-clockwise."""
    pts = sorted(set((round(x, 7), round(y, 7)) for x, y in pts))
    def half(ps):
        out = []
        for p in ps:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    lower, upper = half(pts), half(list(reversed(pts)))
    return lower[:-1] + upper[:-1]


def _clip_above(poly, z0):
    """The part of a convex outline above the line z = z0 (2D points (x, z))."""
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        pin, qin = p[1] >= z0, q[1] >= z0
        if pin:
            out.append(p)
        if pin != qin:
            t = (z0 - p[1]) / (q[1] - p[1])
            out.append((p[0] + t * (q[0] - p[0]), z0))
    return out


def _capsule(a, b, r, segs=8):
    """Outline of a slot with round ends from a to b (2D)."""
    ax, ay = a
    bx, by = b
    ang = math.atan2(by - ay, bx - ax)
    pts = []
    for i in range(segs + 1):
        t = ang - math.pi / 2 - math.pi * i / segs
        pts.append((ax + r * math.cos(t), ay + r * math.sin(t)))
    for i in range(segs + 1):
        t = ang + math.pi / 2 - math.pi * i / segs
        pts.append((bx + r * math.cos(t), by + r * math.sin(t)))
    return pts


def _mb_rivet(name, x, z, side, yo, r, k, steel):
    """A flat-domed rivet head of radius r on a cheek's outer face (side -1: the -Y cheek)."""
    rv = G.lathe(name, [(0, -0.0002 * k), (r, -0.0002 * k), (r * 0.115 / 0.12, 0.0003 * k), (r * 0.08 / 0.12, 0.0006 * k), (0, 0.0007 * k)], steel, 20)
    rv.matrix_world = Matrix.Translation((x, side * yo, z)) @ Matrix.Rotation(math.radians(-90 * side), 4, "X")
    G.bake_xform(rv)
    return G.finish(rv, 0, weighted=False)


def _mb_cheek(side, outline, inner, yi, yo, pocket, bosses, cuts, k, plastic):
    """One moulded cheek: the outline extruded between yi and yo, a shallow pocket inside a rim on the outer face,
    raised bosses ((x, z, r0, r1): back up to rim level), rounded edges, then the openings `cuts(side)` cut through."""
    y0, y1 = (-yo, -yi) if side < 0 else (yi, yo)
    cheek = _xz_prism(f"cheek{side}", outline, y0, y1, plastic)
    well = _xz_prism(f"pocket{side}", inner, (yo - pocket) if side > 0 else -yo - 0.001, (yo + 0.001) if side > 0 else -(yo - pocket), plastic)
    G.boolean(cheek, well)
    for i, (bx, bz, r0, r1) in enumerate(bosses):
        boss = G.cyl(f"boss{side}{i}", (bx, side * (yo - pocket - 0.0002 * k), bz), (bx, side * yo, bz), r0, plastic, 48, r1=r1)
        G.boolean(cheek, boss, op="UNION")
    # round the moulded edges before the holes go in (two segments), then only a small chamfer on the hole edges:
    # rounding every hole with two segments cost 14k triangles for the pair of cheeks
    G.finish(cheek, 0.0011 * k, segs=2, weighted=False)
    G.boolean(cheek, G.join(f"cut{side}", cuts(side)))
    return G.finish(cheek, 0.0004 * k, segs=1, angle=50.0)


def _mb_sheave(name, R, ts, rsi, cz, k, plastic, segs=40, shape=None):
    """A sheave in the XZ plane at height cz with a round groove for the line, bored to rsi; `shape(mesh)` reshapes the
    turned sheave before the bore (the ratchet's flats)."""
    groove = [(R - 0.0029 * k * math.sin(math.pi * i / 10), -ts / 2 + 0.0011 * k + (ts - 0.0022 * k) * i / 10) for i in range(11)]
    prof = [(rsi, -ts / 2), (R - 0.0006 * k, -ts / 2), (R, -ts / 2 + 0.0006 * k)] + groove + [(R, ts / 2 - 0.0006 * k), (R - 0.0006 * k, ts / 2), (rsi, ts / 2)]
    sh = G.lathe(name, prof, plastic, segs)
    sh.matrix_world = Matrix.Translation((0, 0, cz)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    G.bake_xform(sh)
    if shape:
        shape(sh.data)
    G.boolean(sh, G.cyl(f"{name}_bore", (0, -0.05 * k, cz), (0, 0.05 * k, cz), rsi, plastic, segs))   # lathe caps its end rings
    return G.finish(sh, 0, sharp=50)


def _mb_hub(sfx, rb, yi, yo, rsi, cz, k, steel):
    """The see-through hub: a thin hollow stainless axle with a rolled lip on each face, round a stainless bearing race."""
    ra, ri = rb * 0.37, rb * 0.33
    lipr = rb * 0.415
    e = 0.0004 * k
    ax = G.lathe(f"axle{sfx}", [(0, -yo - 2 * e), (lipr - e, -yo - 2 * e), (lipr, -yo - e), (lipr, -yo + e), (ra, -yo + 2 * e),
                                (ra, yo - 2 * e), (lipr, yo - e), (lipr, yo + e), (lipr - e, yo + 2 * e), (0, yo + 2 * e)], steel, 36)
    race = G.lathe(f"race{sfx}", [(0, -yi + e), (rsi + 0.0002 * k, -yi + e), (rsi + 0.0002 * k, yi - e), (0, yi - e)], steel, 36)
    out = []
    for o in (ax, race):
        o.matrix_world = Matrix.Translation((0, 0, cz)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        G.bake_xform(o)
        G.boolean(o, G.cyl(f"bore_{o.name}", (0, -0.05 * k, cz), (0, 0.05 * k, cz), ri, steel, 24))
        out.append(G.finish(o, 0.0002 * k, segs=1, sharp=50))
    return out


def _mb_swivel_shackle(zh, rb, k, steel, neck=1.0):
    """Swivel collar on the head at zh, post, eye (hole along Y) and a D-shackle with its pin along X at the origin.
    `neck` thickens the post, the eye's wire and the collar (Ratchet57: Bean, Nov 9 2026, the neck read thin edge-on)."""
    objs = []
    cr = rb * 0.27 * (1 + (neck - 1) * 0.35)
    collar = G.lathe("collar", [(0, -0.0006 * k), (cr, -0.0006 * k), (cr, 0.0012 * k * neck), (cr * 0.22 / 0.27, 0.0024 * k * neck), (0, 0.0024 * k * neck)], steel, 28)
    collar.location = (0, 0, zh)
    G.bake_xform(collar)
    objs.append(G.finish(collar, 0, sharp=50))
    ez, er, emin = -0.013 * k, 0.0034 * k * (1 + (neck - 1) * 0.3), 0.0014 * k * neck
    post = G.cyl("post", (0, 0, zh), (0, 0, ez - er + 0.0006 * k), 0.0040 * k * neck, steel, 24, r1=0.0034 * k * neck)
    objs.append(G.finish(post, 0.0003 * k))
    eye = G.tube("eye", G.arc_pts((0, 0, ez), er, 0, G.TAU, 24, "xz")[:-1], emin, steel, 10, closed=True)
    objs.append(G.finish(eye))
    w, wr = 0.0046 * k * (1 + (neck - 1) * 0.3), 0.0018 * k * (1 + (neck - 1) * 0.8)
    bow = G.tube("bow", [(-w, 0, 0), (-w, 0, -0.0075 * k)] + G.arc_pts((0, 0, -0.0075 * k), w, math.pi, G.TAU, 14, "xz")[1:-1] + [(w, 0, -0.0075 * k), (w, 0, 0)], wr, steel, 10)
    objs.append(G.finish(bow))
    for sx in (-1, 1):
        ear = G.cyl(f"ear{sx}", (sx * (w - 0.0014 * k), 0, 0), (sx * (w + 0.0014 * k), 0, 0), 0.0030 * k, steel, 16)
        objs.append(G.finish(ear, 0.0003 * k))
    pin = G.cyl("pin", (-w - 0.0016 * k, 0, 0), (w + 0.0019 * k, 0, 0), 0.0020 * k, steel, 14)
    objs.append(G.finish(pin, 0.0002 * k))
    phead = G.cyl("pinhead", (-w - 0.0016 * k, 0, 0), (-w - 0.0030 * k, 0, 0), 0.0032 * k, steel, 18)
    objs.append(G.finish(phead, 0.0004 * k))
    return objs


def _mb_ratchet_sheave(name, R, ts, rsi, cz, k, mat, facets=12, segs=96):
    """A ratchet sheave: the round-grooved sheave with its groove floor pressed into flats (`facets` round), the faceted
    drum that grips the line one way, and the flanges left round (Sunfish deck gear, Nov 2026)."""
    band = ts / 2 - 0.0010 * k
    seg = G.TAU / facets

    def flats(me):
        for v in me.vertices:
            x, y, z = v.co.x, v.co.y, v.co.z - cz
            if math.hypot(x, z) < R - 0.0034 * k or abs(y) > band:
                continue
            a = math.atan2(z, x) % seg - seg / 2
            f = math.cos(seg / 2) / math.cos(a)        # the groove floor pulled in to the polygon's flats
            v.co.x, v.co.z = x * f, z * f + cz
    return _mb_sheave(name, R, ts, rsi, cz, k, mat, segs=segs, shape=flats)


def _modern_block_parts(name, sheave_d, becket=False, plate=None, overall=None, head=1.66, hk=None, ratchet=False,
                        holes=True, neck=1.0):
    """Part detail loop round 1 (docs/part-detail-loop): a modern moulded-cheek swivel block, measured against a 40 mm
    catalogue block (86 mm from the shackle pin to the foot, 4 mm pin, 10 mm line) and reference photos.

    Generic TERNWAY design, not a copy of any maker's: teardrop cheeks (a circle round the sheave narrowing to a flat
    head), a see-through hollow axle with its bearing balls showing, an open ring of lightening holes on the lower
    cheek, two angled slots beside the head, two head rivets, a grooved sheave for 10 mm line, a swivel post with a
    collar and eye, and a D-shackle with its pin along X at the origin. Hangs along -Z from the pin; axle along Y."""
    k = sheave_d / 0.040
    hk = hk or k                         # the swivel and shackle's scale (a 57 mm ratchet keeps 6 mm hardware)
    overall = overall or 0.086 * k
    objs = []
    R = sheave_d / 2
    rb = R * 1.18                        # cheek radius round the axle
    H = rb * head                        # head top above the axle
    hw, rc = rb * 0.44, rb * 0.17        # head half width, its corner radius
    tc = 0.0034 * k                      # cheek thickness (round 2: moulded, not sheet)
    ts = 0.0105 * k                      # sheave thickness (10 mm line at 40 mm)
    gap = 0.0006 * k
    yi = ts / 2 + gap                    # cheek inner face
    yo = yi + tc                         # cheek outer face
    cz = 0.002 * hk - overall + rb      # axle height: `overall` (86 mm at 40) from the top of the pin to the foot of the cheeks
    zh = cz + H                          # head top
    plastic, steel = M("BlackPlastic"), M("Stainless")

    # cheek outline: hull of the round body and the head's rounded corners
    pts = [(rb * math.cos(G.TAU * i / 56), cz + rb * math.sin(G.TAU * i / 56)) for i in range(56)]
    for sx in (-1, 1):
        cx_, cz_ = sx * (hw - rc), zh - rc
        pts += [(cx_ + rc * math.cos(G.TAU * i / 16), cz_ + rc * math.sin(G.TAU * i / 16)) for i in range(16)]
    outline = _hull2d(pts)
    # the same outline 1.5 mm in: the floor of the shallow pocket that leaves a moulded rim round each cheek's face
    lip = 0.0015 * k
    pts_in = [(rb - lip) * math.cos(G.TAU * i / 56) for i in range(56)]
    pts_in = [(x, cz + (rb - lip) * math.sin(G.TAU * i / 56)) for i, x in enumerate(pts_in)]
    for sx in (-1, 1):
        cx_, cz_ = sx * (hw - rc), zh - rc
        pts_in += [(cx_ + (rc - lip) * math.cos(G.TAU * i / 16), cz_ + (rc - lip) * math.sin(G.TAU * i / 16)) for i in range(16)]
    inner = _hull2d(pts_in)
    pocket = 0.0005 * k

    ro = rb * 0.44                       # central opening (see-through hub; round 2: bigger, shows sheave face and balls)
    # round 3: a near-closed ring of small holes hugging the boss, skipping the shoulder windows (reviewers: round 2's
    # lower crescent of big holes read as an industrial pulley)
    ring_r, hole_r = rb * 0.68, rb * 0.052
    win = [((sx * rb * 0.66, cz + rb * 0.36), (sx * rb * 0.42, cz + rb * 1.02)) for sx in (-1, 1)]

    def _clear(px, pz):
        for (ax_, az_), (bx_, bz_) in win:
            dx, dz = bx_ - ax_, bz_ - az_
            t = max(0.0, min(1.0, ((px - ax_) * dx + (pz - az_) * dz) / (dx * dx + dz * dz)))
            if math.hypot(px - ax_ - t * dx, pz - az_ - t * dz) < rb * 0.12 + hole_r + rb * 0.05:
                return False
        return True
    ring_angles = [a for a in (G.TAU * i / 24 for i in range(24)) if _clear(ring_r * math.cos(a), cz + ring_r * math.sin(a))]
    if not holes:
        ring_angles = []
    def cuts(side):
        cut = [G.cyl(f"open{side}", (0, -1, cz), (0, 1, cz), ro, plastic, 48)]
        cut += [G.cyl(f"h{side}{i}", (ring_r * math.cos(a), -1, cz + ring_r * math.sin(a)), (ring_r * math.cos(a), 1, cz + ring_r * math.sin(a)),
                      hole_r, plastic, 8) for i, a in enumerate(ring_angles)]
        for sx in (-1, 1):
            # shoulder windows: wide, angled with the cheek's side, low enough to show the sheave behind
            cut.append(_xz_prism(f"slot{side}{sx}", _capsule((sx * rb * 0.66, cz + rb * 0.36), (sx * rb * 0.42, cz + rb * 1.02), rb * 0.12),
                                 -1, 1, plastic))
        return cut
    for side in (-1, 1):
        # raised boss round the hub, level with the rim
        objs.append(_mb_cheek(side, outline, inner, yi, yo, pocket, [(0, cz, rb * 0.58, rb * 0.56)], cuts, k, plastic))
        # head rivets, domed, on each outer face
        for sx in (-1, 1):
            objs.append(_mb_rivet(f"rivet{side}{sx}", sx * (hw - rb * 0.17), zh - rb * 0.22, side, yo, rb * 0.12, k, steel))
    # spacer filling the head between the cheeks, above the sheave
    # moulded crown filling the head between the cheeks above the sheave: the cheek outline itself, so edge-on the head
    # reads as one rounded moulding (round 2; round 1 had a square spacer)
    # it starts 7.6 mm above the sheave: room for a 10 mm line over the top of the sheave
    crown = _xz_prism("headblock", _clip_above(outline, cz + R + 0.0076 * k), -yi - 0.0002 * k, yi + 0.0002 * k, plastic)
    objs.append(G.finish(crown, 0.0011 * k, segs=2))

    # sheave with a round groove for the line
    rsi = rb * 0.395
    if ratchet:
        objs.append(_mb_ratchet_sheave("sheave", R, ts, rsi, cz, k, M("Aluminium")))
        # the ratchet's on/off switch on each cheek below the hub: a moulded boss and its lever, ON pointing at the head
        for side in (-1, 1):
            sw = G.cyl(f"switch{side}", (0, side * (yo - 0.0002 * k), cz - rb * 0.6), (0, side * (yo + 0.0016 * k), cz - rb * 0.6),
                       rb * 0.2, plastic, 28, r1=rb * 0.18)
            objs.append(G.finish(sw, 0.0004 * k, segs=1))
            lv = G.box(f"lever{side}", (0, side * (yo + 0.0022 * k), cz - rb * 0.6), (rb * 0.09, 0.0016 * k, rb * 0.34), M("Aluminium"))
            objs.append(G.finish(lv, 0.0005 * k, segs=1))
    else:
        objs.append(_mb_sheave("sheave", R, ts, rsi, cz, k, plastic))
    # hollow stainless axle with a rolled lip on each face, round a stainless bearing race; the bore is cut through so
    # you can see through the middle (round 2: round 1's balls between the lip and the sheave read as a cog)
    # round 3: a large hollow axle (a thin stainless liner), so the centre reads as a big open hole (round 2's small
    # boss read as a hardware-store pulley)
    objs += _mb_hub("", rb, yi, yo, rsi, cz, k, steel)
    # swivel: collar on the head, post, eye (hole along Y); D-shackle: pin along X at the origin, bow through the eye
    objs += _mb_swivel_shackle(zh, rb, hk, steel, neck)
    if becket:
        bz = cz - rb - 0.0022 * k
        bk = G.tube("becket", [(-0.0050 * k, 0, cz - R * 0.6)] + G.arc_pts((0, 0, bz), 0.0050 * k, math.pi, G.TAU, 14, "xz")[1:-1] + [(0.0050 * k, 0, cz - R * 0.6)],
                    0.0021 * k, steel, 12)
        objs.append(G.finish(bk))
    if plate:
        objs.append(badge("plate", plate, rb * 0.52, rb * 0.17,
                          Matrix.Translation((0, -yo + pocket - 0.0002 * k, cz + rb * 0.98)) @ Matrix.Rotation(math.radians(90), 4, "X"), plastic))
    socks = [("Head", (0, 0, 0)), ("Axle", (0, 0, cz)), ("LineIn", (R, 0, cz)), ("LineOut", (-R, 0, cz))]
    if becket:
        socks.append(("Becket", (0, 0, cz - rb - 0.0072 * k)))
    return objs, socks


def _inside(poly, px, pz):
    """Distance from (px, pz) to the nearest edge of a convex counter-clockwise outline (negative outside)."""
    best = 1e9
    for i, (ax_, az_) in enumerate(poly):
        bx_, bz_ = poly[(i + 1) % len(poly)]
        ex, ez = bx_ - ax_, bz_ - az_
        best = min(best, (ex * (pz - az_) - ez * (px - ax_)) / math.hypot(ex, ez))
    return best


def _fiddle_parts(name, sheave_d=0.040, small_d=0.026, overall=0.115, cam=False, becket=False, plate=None):
    """Part detail loop, the vang (docs/part-detail-loop): a modern fiddle block, the big sheave under the head and a
    smaller one in line below it, so the big sheave's lines pass outside the narrow lower cheeks. Same TERNWAY family
    as Block40 (moulded cheeks with a rim, open lined hub with a ring of holes, shoulder windows, head rivets, swivel and
    D-shackle). Sized to a 40 mm catalogue fiddle: 115 mm from the top of the pin to the foot of the cheeks, 4 mm pin,
    10 mm line. `becket`: a pin through a tail of the cheeks below the small sheave (clear of its line) with a stainless
    loop, 131 mm overall. `cam`: an aluminium bracket on each cheek round the big hub, carrying a cam cleat beside the
    big sheave for the tail (red jaws over a moulded base, a fairlead hoop where the line is pulled). Hangs along -Z
    from the pin; axles along Y."""
    k = sheave_d / 0.040
    objs = []
    R, r = sheave_d / 2, small_d / 2
    rb = R * 1.18                        # cheek radius round the big axle (as Block40)
    rbs = r + 0.0035 * k                 # round the small one: the big sheave's lines pass just outside it
    H = rb * 1.66
    hw, rc = rb * 0.44, rb * 0.17
    tc, ts, gap = 0.0034 * k, 0.0105 * k, 0.0006 * k
    yi = ts / 2 + gap
    yo = yi + tc
    zh = (0.002 - 0.086) * k + rb + H    # head top: the same swivel and shackle stack as Block40
    cz = zh - H                          # big axle
    foot = (0.002 - overall) * k
    cz2 = foot + rbs                     # small axle
    zb = cz2 - r - 0.0105 * k            # becket pin, clear of a 10 mm line round the small sheave
    rbk = 0.0042 * k
    plastic, steel, alu = M("BlackPlastic"), M("Stainless"), M("Aluminium")

    def outline_pts(inset):
        pts = [((rb - inset) * math.cos(G.TAU * i / 56), cz + (rb - inset) * math.sin(G.TAU * i / 56)) for i in range(56)]
        pts += [((rbs - inset) * math.cos(G.TAU * i / 40), cz2 + (rbs - inset) * math.sin(G.TAU * i / 40)) for i in range(40)]
        # round 2: a fuller shoulder below the big sheave (reviewers: round 1's straight sides read as a diamond)
        pts += [((rmid - inset) * math.cos(G.TAU * i / 48), zmid + (rmid - inset) * math.sin(G.TAU * i / 48)) for i in range(48)]
        for sx in (-1, 1):
            cx_, cz_ = sx * (hw - rc), zh - rc
            pts += [(cx_ + (rc - inset) * math.cos(G.TAU * i / 16), cz_ + (rc - inset) * math.sin(G.TAU * i / 16)) for i in range(16)]
        if becket:
            pts += [((rbk - inset) * math.cos(G.TAU * i / 20), zb + (rbk - inset) * math.sin(G.TAU * i / 20)) for i in range(20)]
        return _hull2d(pts)
    zmid = cz - 0.40 * (cz - cz2)
    rmid = rb + 0.40 * (rbs - rb) + 0.0016 * k
    lip = 0.0015 * k
    outline, inner = outline_pts(0.0), outline_pts(lip)
    pocket = 0.0005 * k

    ro = rb * 0.44
    hole_r = rb * 0.052
    win = [((sx * rb * 0.66, cz + rb * 0.36), (sx * rb * 0.42, cz + rb * 1.02)) for sx in (-1, 1)]

    def clear_of_windows(px, pz, rr):
        for (ax_, az_), (bx_, bz_) in win:
            dx, dz = bx_ - ax_, bz_ - az_
            t = max(0.0, min(1.0, ((px - ax_) * dx + (pz - az_) * dz) / (dx * dx + dz * dz)))
            if math.hypot(px - ax_ - t * dx, pz - az_ - t * dz) < rb * 0.12 + rr + rb * 0.05:
                return False
        return True
    # lightening holes: the ring round the big hub (Block40's), then a ring round the small axle, each kept only where
    # it clears the windows, the other axle's boss, its neighbours and the cheek's rim
    holes = []
    # round 2: only the big hub keeps a ring of holes; the small sheave shows through four kidney slots (reviewers: the
    # second ring of dots read as a metal ring, the real cheeks have big slots round the small sheave)
    rings = [(0.0, cz, rb * 0.68, 24, rb * 0.58)]
    kr, kw = rbs * 0.69, 0.0019 * k

    def kidney(a0, a1, n=10):
        out = [(kr + kw) * math.cos(a0 + (a1 - a0) * i / n) for i in range(n + 1)]
        out = [(x, cz2 + (kr + kw) * math.sin(a0 + (a1 - a0) * i / n)) for i, x in enumerate(out)]
        for a_, t0 in ((a1, 0.0), (a0, math.pi)):
            ex, ez = kr * math.cos(a_), cz2 + kr * math.sin(a_)
            out += [(ex + kw * math.cos(a_ + t0 + math.pi * i / 6), ez + kw * math.sin(a_ + t0 + math.pi * i / 6)) for i in range(1, 6)]
            if t0 == 0.0:
                out += [((kr - kw) * math.cos(a1 - (a1 - a0) * i / n), cz2 + (kr - kw) * math.sin(a1 - (a1 - a0) * i / n)) for i in range(n + 1)]
        return out
    kidneys = [kidney(c - 0.55, c + 0.55) for c in (math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4)]
    for ci, (hx, hz, rr_, n, _) in enumerate(rings):
        for i in range(n):
            a = G.TAU * i / n + (math.pi / n if ci else 0.0)
            px, pz = hx + rr_ * math.cos(a), hz + rr_ * math.sin(a)
            if not clear_of_windows(px, pz, hole_r):
                continue
            if _inside(outline, px, pz) < hole_r + lip + 0.0008 * k:
                continue
            if any(math.hypot(px - bx, pz - bz) < br + hole_r + 0.0008 * k for j, (bx, bz, _, _, br) in enumerate(rings) if j != ci):
                continue
            if any(math.hypot(px - qx, pz - qz) < 2 * hole_r + 0.0012 * k for qx, qz in holes):
                continue
            holes.append((px, pz))

    def cuts(side):
        cut = [G.cyl(f"open{side}", (0, -1, cz), (0, 1, cz), ro, plastic, 48)]
        cut += [G.cyl(f"h{side}{i}", (px, -1, pz), (px, 1, pz), hole_r, plastic, 8) for i, (px, pz) in enumerate(holes)]
        for sx in (-1, 1):
            cut.append(_xz_prism(f"slot{side}{sx}", _capsule((sx * rb * 0.66, cz + rb * 0.36), (sx * rb * 0.42, cz + rb * 1.02), rb * 0.12),
                                 -1, 1, plastic))
        cut += [_xz_prism(f"kid{side}{i}", kd, -1, 1, plastic) for i, kd in enumerate(kidneys)]
        return cut
    bosses = [(0, cz, rb * 0.58, rb * 0.56), (0, cz2, rbs * 0.50, rbs * 0.48)]
    for side in (-1, 1):
        objs.append(_mb_cheek(side, outline, inner, yi, yo, pocket, bosses, cuts, k, plastic))
        for sx in (-1, 1):
            objs.append(_mb_rivet(f"rivet{side}{sx}", sx * (hw - rb * 0.17), zh - rb * 0.22, side, yo, rb * 0.12, k, steel))
        # the small sheave's axle is a riveted pin: a bigger domed head on each face
        objs.append(_mb_rivet(f"rivetaxle{side}", 0.0, cz2, side, yo, rbs * 0.30, k, steel))
        if becket:
            objs.append(_mb_rivet(f"rivetbecket{side}", 0.0, zb, side, yo, rbk * 0.62, k, steel))
    crown = _xz_prism("headblock", _clip_above(outline, cz + R + 0.0076 * k), -yi - 0.0002 * k, yi + 0.0002 * k, plastic)
    objs.append(G.finish(crown, 0.0011 * k, segs=2))

    rsi = rb * 0.395
    objs.append(_mb_sheave("sheave", R, ts, rsi, cz, k, plastic))
    objs += _mb_hub("", rb, yi, yo, rsi, cz, k, steel)
    # the small sheave on a solid pin with a stainless race each side
    rsi2 = rbs * 0.34
    objs.append(_mb_sheave("sheave2", r, ts, rsi2, cz2, k, plastic, segs=32))
    pin2 = G.cyl("axle2pin", (0, -yo, cz2), (0, yo, cz2), rsi2, steel, 20)
    objs.append(G.finish(pin2, 0.0002 * k, segs=1))
    for sgn in (-1, 1):
        rc2 = G.lathe(f"race2{sgn}", [(rsi2, 0), (rsi2 + 0.0022 * k, 0), (rsi2 + 0.0022 * k, 0.0005 * k), (rsi2, 0.0005 * k)], steel, 28)
        y_ = -ts / 2 - 0.0005 * k if sgn < 0 else ts / 2      # on each face of the sheave (the lathe runs along +Y)
        rc2.matrix_world = Matrix.Translation((0, y_, cz2)) @ Matrix.Rotation(math.radians(-90), 4, "X")
        G.bake_xform(rc2)
        objs.append(G.finish(rc2, 0, weighted=False))
    objs += _mb_swivel_shackle(zh, rb, k, steel)
    if becket:
        # becket: a stainless pin through the cheeks' tail and a loop round it, hanging below
        bp = G.cyl("becketpin", (0, -yi, zb), (0, yi, zb), 0.0019 * k, steel, 14)
        objs.append(G.finish(bp, 0.0002 * k, segs=1))
        lr = 0.0058 * k
        loop = G.tube("becket", G.arc_pts((0, 0, zb - lr + 0.0019 * k + 0.0026 * k), lr, 0, G.TAU, 24, "xz")[:-1], 0.0026 * k, steel, 10, closed=True)
        objs.append(G.finish(loop))
    socks = [("Head", (0, 0, 0)), ("Axle", (0, 0, cz)), ("LineIn", (R, 0, cz)), ("LineOut", (-R, 0, cz)),
             ("Axle2", (0, 0, cz2)), ("LineIn2", (r, 0, cz2)), ("LineOut2", (-r, 0, cz2))]
    if becket:
        socks.append(("Becket", (0, 0, zb - 2 * lr + 0.0019 * k + 0.0005 * k)))
    if cam:
        objs_cam, cam_socks = _fiddle_cam(cz, R, rb, ro, yo, holes, k, alu, steel, plastic)
        objs += objs_cam
        socks += cam_socks
    if plate:
        objs.append(badge("plate", plate, rb * 0.52, rb * 0.17,
                          Matrix.Translation((0, -yo + pocket - 0.0002 * k, cz + rb * 0.98)) @ Matrix.Rotation(math.radians(90), 4, "X"), plastic))
    return objs, socks


def _fiddle_cam(cz, R, rb, ro, yo, holes, k, alu, steel, plastic):
    """The fiddle's cam cleat (Bean's J/22 mainsheet photo): an aluminium bracket on each cheek, a ring round the big hub
    (the cheek's lightening holes go through it) with a short arm straight out at hub height to a bent-up mount plate,
    two open toothed cams with red jaws on the plate either side of the tail's path, and a fairlead hoop where the line
    is pulled. The tail leaves the top of the big sheave on +X and runs out and down through the jaws toward the foot
    (-Z: the block is mounted head down). Round 2 (blind review): no moulded housing round the cams (it read as one cam
    in a box), the cams level with the hub, the plate on the block's side of the cams so their teeth face out.
    Returns the objects and the Cam and CamLead sockets (the jaws' centre, and a point 10 mm on along the tail's lead)."""
    objs = []
    t = 0.0016 * k                                    # bracket plate thickness
    rcam, hcam = 0.0062 * k, 0.0096 * k               # cam radius, length along X (round 3: a little smaller)
    lx = R + 0.0165 * k                               # the line's path through the jaws (round 3: a longer arm)
    lz0, lz1 = cz + 0.0060 * k, cz - 0.0200 * k
    jz = cz - 0.0060 * k                              # the cams' centre
    px0, px1 = lx - hcam / 2 - t, lx - hcam / 2       # the mount plate, square to X, the cams standing out from it
    wy = 2 * (2 * rcam + 0.0016 * k + 0.0010 * k)
    ring_out = rb * 0.78
    # round 3: the whole cam unit is turned about the arm's root so the jaws line up with the tail's lead out and down off
    # the big sheave (reviewers: round 2's cams stuck straight out sideways)
    tilt = math.radians(-22)
    piv = Vector((ring_out, 0, cz))
    rot = Matrix.Translation(piv) @ Matrix.Rotation(tilt, 4, "Y") @ Matrix.Translation(-piv)

    def tp(x, z):
        v = rot @ Vector((x, 0, z))
        return (v.x, v.z)
    # each cheek's bracket: the ring round the hub and a longer arm out to the mount plate's edge
    pts = [(ring_out * math.cos(G.TAU * i / 40), cz + ring_out * math.sin(G.TAU * i / 40)) for i in range(40)]
    pts += [tp(px1, lz0 - 0.0010 * k), tp(px1, lz1 + 0.0010 * k)]
    plate_out = _hull2d(pts)
    # a large triangular window in the arm, corners rounded
    cr = 0.0010 * k
    a0 = ring_out + 0.0026 * k                      # clear of the ring's holes (overlapping cutters empty the boolean)
    tri = [(a0 * math.cos(0.40), cz + a0 * math.sin(0.40) - 0.001 * k), (a0 * math.cos(-0.50), cz + a0 * math.sin(-0.50) + 0.001 * k),
           tp(px1 - 0.0026 * k, jz)]
    win = _hull2d([(x + cr * math.cos(G.TAU * i / 8), z + cr * math.sin(G.TAU * i / 8)) for x, z in tri for i in range(8)])
    for side in (-1, 1):
        y0, y1 = (-(yo + t), -yo) if side < 0 else (yo, yo + t)
        br = _xz_prism(f"cambracket{side}", plate_out, y0, y1, alu)
        G.finish(br, 0.0005 * k, segs=1, weighted=False)
        cut = [G.cyl(f"bo{side}", (0, -1, cz), (0, 1, cz), ro + 0.0006 * k, alu, 40)]
        cut += [G.cyl(f"bh{side}{i}", (qx, -1, qz), (qx, 1, qz), rb * 0.052, alu, 8) for i, (qx, qz) in enumerate(holes)
                if math.hypot(qx, qz - cz) < ring_out - rb * 0.08]
        if px1 - a0 > 0.006 * k:
            cut.append(_xz_prism(f"bw{side}", win, -1, 1, alu))
        G.boolean(br, G.join(f"bcut{side}", cut))
        objs.append(G.finish(br, 0.0002 * k, segs=1, angle=50.0))
    unit = []
    # the mount plate joining both brackets, rounded corners
    mp = G.prism("cammount", G.rrect(lz0 - lz1 + 0.002 * k, wy, 0.0035 * k), 0.0, t, alu)
    mp.matrix_world = Matrix.Translation((px0, 0, (lz0 + lz1) / 2)) @ Matrix.Rotation(math.radians(90), 4, "Y")
    G.bake_xform(mp)
    unit.append(G.finish(mp, 0.0004 * k, segs=1, weighted=False))
    # cams: toothed lobes on axles along X standing out from the plate, either side of the line, the lobe toward it
    for sy in (-1, 1):
        prof = []
        teeth = 12
        for i in range(teeth * 3):
            a = G.TAU * i / (teeth * 3)
            rr_ = rcam + 0.0013 * k * max(0.0, math.cos(a - (math.pi if sy > 0 else 0.0))) + (0.0011, 0.0005, 0.0)[i % 3] * k
            prof.append((rr_ * math.cos(a), rr_ * math.sin(a)))
        cy = sy * (rcam + 0.0016 * k)
        cm = G.prism(f"cam{sy}", prof, 0, hcam, M("Graphics"))
        # prism axis Z -> +X (out from the plate), profile (u, v) -> (y, z)
        cm.matrix_world = Matrix.Translation((px1, cy, jz)) @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "Z")
        G.bake_xform(cm)
        unit.append(G.finish(cm, 0.0003 * k, sharp=50))
        # a stainless cap on each cam's free end (the axle's head) and a black spring housing at its foot
        cap = G.cyl(f"camcap{sy}", (px1 + hcam - 0.0002 * k, cy, jz), (px1 + hcam + 0.0006 * k, cy, jz), 0.0030 * k, steel, 16)
        unit.append(G.finish(cap, 0.0002 * k))
        foot = G.cyl(f"camfoot{sy}", (px1, cy, jz), (px1 + 0.0016 * k, cy, jz), rcam * 0.78, plastic, 20)
        unit.append(G.finish(foot, 0.0003 * k))
    # fairlead hoop at the pulling end (-Z), from the plate round the line
    hz = lz1 - 0.0005 * k
    hr = 0.0050 * k
    hoop = G.tube("camhoop", [(px1 - 0.0005 * k, -hr, hz)] + G.arc_pts((lx, 0, hz), hr, -0.5 * math.pi, 0.5 * math.pi, 12, "xy") + [(px1 - 0.0005 * k, hr, hz)],
                  0.0013 * k, steel, 10)
    unit.append(G.finish(hoop))
    for o in unit:
        o.matrix_world = rot @ o.matrix_world
        G.bake_xform(o)
    objs += unit
    cam_at = rot @ Vector((lx, 0, jz))
    lead = (rot @ Vector((lx, 0, jz - 0.010 * k))) - cam_at
    return objs, [("Cam", tuple(cam_at)), ("CamLead", tuple(cam_at + lead))]


@part("Block29", "block", "29 mm single block with swivel, sheets and control lines")
def block29(becket=False):
    objs, socks = _block_parts("Block29", 0.029, becket=becket, plate="Plate29")
    return done("Block29" + ("B" if becket else ""), objs, socks)


@part("Block40", "block", "40 mm single block with swivel and becket")
def block40():
    objs, socks = _modern_block_parts("Block40", 0.040, becket=True, plate="Plate40")
    return done("Block40", objs, socks)


@part("Ratchet57", "block", "57 mm swivel ratchet block, on/off switch, 10 mm line: the Sunfish's and ILCA's mainsheet block")
def ratchet57(standup=False):
    """Sunfish deck gear (Nov 2026, docs/part-detail-loop/sunfish.md): the moulded-cheek swivel block at the catalogue's
    57 mm ratchet size (103 mm overall, 10 mm line), a faceted ratchet sheave, an on/off switch on each cheek and a 6 mm
    swivel shackle. `standup`: a stand-up spring round the shackle and swivel, so the block stands on its deck eye."""
    objs, socks = _modern_block_parts("Ratchet57", 0.057, plate="Plate57", overall=0.103, head=1.32, hk=1.2, ratchet=True, holes=False, neck=1.6)
    if standup:
        zh = socks[1][1][2] + 0.0336 * 1.32          # the head's top (Axle + H)
        n, r, z0 = 9, 0.0095, -0.0015
        pts = [(r * math.cos(G.TAU * t / 16), r * math.sin(G.TAU * t / 16), z0 + (zh + 0.0012 - z0) * t / (16 * n)) for t in range(16 * n + 1)]
        objs.append(G.finish(G.tube("spring", pts, 0.0011, M("Stainless"), 6)))
    return done("Ratchet57" + ("S" if standup else ""), objs, socks)


@part("Fiddle40", "block", "40 mm fiddle block with swivel: a big and a small sheave in line (the vang's and mainsheet's upper block)")
def fiddle40():
    objs, socks = _fiddle_parts("Fiddle40", 0.040, plate="Plate40")
    return done("Fiddle40", objs, socks)


@part("FiddleCam", "block", "40 mm fiddle block with becket and cam cleat: the vang's and mainsheet's lower block")
def fiddle_cam():
    objs, socks = _fiddle_parts("FiddleCam", 0.040, cam=True, becket=True, plate="Plate40")
    return done("FiddleCam", objs, socks)


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
    "CamCleat":   {"dim": "length mm (size label; the default is the 38 mm axle-centre class, 61 mm across)", "default": "75", "scale": {"38": 0.51, "75": 1.0, "102": 1.36}},
    "Fairlead":   {"dim": "outside diameter mm", "default": "32", "scale": {"25": 0.78, "32": 1.0, "44": 1.375}},
    "Block29":    {"dim": "sheave mm", "default": "29", "scale": {"22": 0.76, "29": 1.0}},
    "Block40":    {"dim": "sheave mm", "default": "40", "scale": {"40": 1.0, "57": 1.425}},
    "Fiddle40":   {"dim": "sheave mm", "default": "40", "scale": {"40": 1.0, "57": 1.425}},
    "FiddleCam":  {"dim": "sheave mm", "default": "40", "scale": {"40": 1.0, "57": 1.425}},
    "Ratchet57":  {"dim": "sheave mm", "default": "57", "scale": {"57": 1.0, "75": 1.316}},
    "Winch16":    {"dim": "winch size (base diameter 102 / 120 / 130 / 152 / 175 mm)", "default": "16",
                   "scale": {"8": 0.85, "16": 1.0, "20": 1.083, "30": 1.267, "40": 1.458}},
    "Winch70":    {"dim": "winch size", "default": "70", "kw": {"50": {"scale": 0.85}, "70": {"scale": 1.0}}},
    "JibTrack":   {"dim": "track length mm", "default": "600", "kw": {"450": {"length": 0.45}, "600": {"length": 0.60}, "900": {"length": 0.90}}},
    "Traveler":   {"dim": "track length mm", "default": "900", "kw": {"600": {"length": 0.60}, "900": {"length": 0.90}, "1500": {"length": 1.50}}},
    "Chainplate": {"dim": "wire mm", "default": "5", "scale": {"4": 0.85, "5": 1.0, "6": 1.15}},
    "Stanchion":  {"dim": "height mm", "default": "610", "kw": {"457": {"height": 0.457}, "610": {"height": 0.610}, "760": {"height": 0.760}}},
    "BowPulpit":  {"dim": "width mm", "default": "600", "kw": {"450": {"width": 0.45, "length": 0.35}, "600": {"width": 0.60}, "800": {"width": 0.80, "length": 0.60}}},
    "Pushpit":    {"dim": "width mm", "default": "1500", "kw": {"1200": {"width": 1.20}, "1500": {"width": 1.50}, "2000": {"width": 2.00, "depth": 0.50}}},
    "Clutch":     {"dim": "line mm", "default": "10", "scale": {"8": 0.85, "10": 1.0, "14": 1.3}},
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


# Parts kept in their own files (bk_part_<name>.py) register themselves with @part when imported here.
import glob as _glob  # noqa: E402
import importlib as _importlib  # noqa: E402
import os as _os  # noqa: E402
for _f in sorted(_glob.glob(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "bk_part_*.py"))):
    _importlib.import_module(_os.path.basename(_f)[:-3])
