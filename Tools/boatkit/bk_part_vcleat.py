"""VCleat: a small moulded V-cleat with a fairlead eye for 3-6 mm control lines (part detail loop, Nov 2026).

Kept in its own file so other parts' threads don't touch the same lines; bk_parts imports every bk_part_*.py at the end.
Card: partloop/parts/vcleat.json; method and results: docs/part-detail-loop/vcleat.md.

What it is (Bean's reference sheet, Nov 8 2026, "V Cleat"): one dark grey composite moulding, about 70 mm long, low at
the tail and rising toward a rounded nose. From the tail: a shallow pocket holding the aft screw, a bulkhead with an oval
fairlead eye the line leads out through, then the V jaw, open on top, whose walls carry raked ridges that grip the
line as it is pulled down into the V; the forward screw sits at the bottom of the V. Screws on 48 mm centres
(catalogue: 4 mm fasteners, 48 mm hole centres, 3-6 mm line, 11 g).

Frame (bk_parts convention): origin on the mounting surface at the middle of the base, +Z up, +X toward the nose (the
side the loaded line comes from), so the line runs nose -> V -> eye -> tail, where the sailor pulls it.
"""
import math

import bmesh
from mathutils import Matrix

import bk_geom as G
import bk_parts as P

MM = 0.001


def _profile_top(x, L):
    """Height of the top edge (mm) along the length (mm from the tail)."""
    pts = [(0.0, 6.0), (1.0, 7.6), (3.0, 8.4), (10.0, 9.6), (20.0, 11.8), (30.0, 14.6), (40.0, 17.2), (50.0, 19.5),
           (58.0, 21.0), (63.0, 21.6), (66.5, 20.0), (68.6, 16.5), (69.7, 12.0), (70.0, 6.0)]
    s = L / 70.0
    pts = [(a * s, b) for a, b in pts]
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def _xz_solid(name, outline_xz, w, mat=None):
    """A side outline [(x, z)] in mm, extruded across the full width w (mm) in Y; returned in metres."""
    o = G.prism(name, [(x * MM, z * MM) for x, z in outline_xz], -w / 2 * MM, w / 2 * MM, mat)
    o.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")      # prism's XY -> XZ, its Z -> -Y
    G.bake_xform(o)
    return o


def _yz_solid(name, outline_yz, x0, x1, mat=None):
    """A section [(y, z)] in mm extruded along X from x0 to x1 (mm)."""
    bm = bmesh.new()
    a = [bm.verts.new((x0 * MM, y * MM, z * MM)) for y, z in outline_yz]
    b = [bm.verts.new((x1 * MM, y * MM, z * MM)) for y, z in outline_yz]
    n = len(a)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _v_section(half_bot, z_bot, k, z_top, grow=0.0):
    """The V's cross-section: half-width half_bot at z_bot opening by k per mm of height, closed well above the top."""
    hb = half_bot + grow
    ht = half_bot + (z_top - z_bot) * k + grow
    return [(-hb, z_bot - grow), (hb, z_bot - grow), (ht, z_top), (-ht, z_top)]


def _vcleat_parts(L=71.6, W=18.0, holes=48.0, eye=(8.6, 7.2), v_bot=4.5, v_half=1.0, v_k=0.40, ridges=6,
                  groove=(1.3, 1.2), lean=(20.0, 55.0), round_mm=0.6, voxel=0.17, tris=17500,
                  floor_z=2.6, bulk_rake=34.0, eye_z=8.2, eye_tilt=6.0, draft=0.90):
    pl, ss = P.M("BlackPlastic"), P.M("Stainless")
    xa = 7.0                      # aft screw, mm from the tail
    xf = xa + holes               # forward screw
    xp1, xb1 = 21.0, 34.0         # the pocket's floor ends / the jaw starts (mm from the tail)
    # side outline: the base, then the top edge from the nose back to the tail
    xs = [i * L / 140 for i in range(141)]
    side = [(0.0, 0.0), (L, 0.0)] + [(x, _profile_top(x, L)) for x in reversed(xs)]
    body = _xz_solid("vbody", side, W + 2, pl)
    # plan: rounded at both ends, the sides drawn in toward the top (moulding draft) so the shoulders roll over
    plan = G.prism("plan", G.rrect(L * MM, W * MM, W / 2 * MM, 12), -0.01, 0.05, taper=draft)
    plan.location = (L / 2 * MM, 0, 0)
    G.bake_xform(plan)
    G.boolean(body, plan, "INTERSECT")
    # the moulding's outer edges: a coarse remesh and a strong smooth round every outside edge by about 1.5 mm
    m = body.modifiers.new("round", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", round_mm * MM, 0.0
    sm = body.modifiers.new("roundsmooth", "SMOOTH")
    sm.factor, sm.iterations = 0.6, 16
    G.apply(body)

    # the tail pocket: a rounded tray inside a 2 mm rim, its floor `floor_z` up, closed forward by a raked bulkhead
    pocket = G.prism("pocket", G.rrect((xp1 - 2.2) * MM, (W - 5.0) * MM, (W / 2 - 2.5) * MM, 10), floor_z * MM, 0.05)
    pocket.location = ((2.2 + (xp1 - 2.2) / 2) * MM, 0, 0)
    G.bake_xform(pocket)
    G.boolean(body, pocket)
    rake = G.box("rake", (-10 * MM, 0, 20 * MM), (20 * MM, (W - 5.0) * MM, 40 * MM))
    rake.matrix_world = Matrix.Translation((xp1 * MM, 0, floor_z * MM)) @ Matrix.Rotation(math.radians(bulk_rake), 4, "Y")
    G.bake_xform(rake)
    G.boolean(body, rake)

    # the V jaw: from the bulkhead right out through the nose end (Bean, Nov 8: the V runs open through the end of the
    # body), open on top
    zt = 40.0
    jaw = _yz_solid("jaw", _v_section(v_half, v_bot, v_k, zt), xb1 - 4.0, L + 6.0, pl)
    # the opening is an oval in plan (round ends), not a rectangle
    jplan = G.prism("jplan", G.rrect((L + 14.0 - xb1) * MM, 14.0 * MM, 6.9 * MM, 10), -0.01, 0.05, pl)
    jplan.location = ((xb1 + (L + 14.0 - xb1) / 2) * MM, 0, 0)
    G.bake_xform(jplan)
    G.boolean(jaw, jplan, "INTERSECT")
    G.boolean(body, jaw)
    # raked ridges: grooves 0.7 mm into each V wall, leaning back toward the tail at the top (the line pulled down and
    # aft wedges into them)
    slabs = []
    pitch = (L - 3.0 - xb1 - 2.0) / ridges
    for i in range(ridges + 1):
        x0 = xb1 + 2.0 + i * pitch
        # each groove sweeps back as it rises (steep at the bottom of the V, flatter near the top: the swirl)
        path, z, x = [], v_bot - 1.0, x0
        while z < 30.0:
            path.append((x, z))
            a = math.radians(lean[0] + (lean[1] - lean[0]) * min(1.0, max(0.0, (z - v_bot) / 12.0)))
            x -= math.sin(a) * 0.8
            z += math.cos(a) * 0.8
        hw = groove[0] / 2
        strip = [(px + hw, pz) for px, pz in path] + [(px - hw, pz) for px, pz in reversed(path)]
        slabs.append(_xz_solid(f"slab{i}", strip, 40.0, pl))
    grooves = G.join("grooves", slabs)
    shell = _yz_solid("shell", _v_section(v_half, v_bot, v_k, zt, grow=groove[1]), xb1 - 1.0, L + 6.0, pl)
    G.boolean(grooves, shell, "INTERSECT")
    G.boolean(body, grooves)
    # the fairlead eye: an oval through the raked bulkhead, its axis along the line's lead up into the V
    ez = eye_z
    ex = xp1 + (ez - floor_z) * math.tan(math.radians(bulk_rake))      # where the eye's axis meets the bulkhead face
    e = G.cyl("eye", (-0.3, 0, 0), (0.7, 0, 0), 1.0, None, 40)
    e.data.transform(Matrix.Diagonal((18 * MM, eye[0] / 2 * MM, eye[1] / 2 * MM, 1.0)))
    e.matrix_world = Matrix.Translation((ex * MM, 0, ez * MM)) @ Matrix.Rotation(-math.radians(eye_tilt), 4, "Y")
    G.bake_xform(e)
    G.boolean(body, e)

    # moulded softness: one voxel remesh fuses every cut edge into a small radius, as a moulding has
    m = body.modifiers.new("mould", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", voxel * MM, 0.0
    sm = body.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 4
    G.apply(body)
    floor = G.box("floor", (0, 0, -0.05), (1.0, 1.0, 0.1))
    G.boolean(body, floor)

    # screw holes: the aft one countersunk in the pocket floor, the forward one counterbored up through the V's bottom
    G.boolean(body, G.cyl("haft", (xa * MM, 0, -0.01), (xa * MM, 0, 0.02), 2.2 * MM, None, 32))
    G.boolean(body, G.cyl("csk", (xa * MM, 0, (floor_z - 1.4) * MM), (xa * MM, 0, (floor_z + 0.05) * MM), 2.2 * MM, None, 32, r1=4.0 * MM))
    G.boolean(body, G.cyl("hfwd", (xf * MM, 0, -0.01), (xf * MM, 0, 0.02), 2.2 * MM, None, 32))
    G.boolean(body, G.cyl("cbore", (xf * MM, 0, (v_bot - 1.5) * MM), (xf * MM, 0, 0.03), 3.9 * MM, None, 32))

    d = body.modifiers.new("budget", "DECIMATE")
    me = body.data
    me.calc_loop_triangles()
    d.ratio = min(1.0, tris / max(1, len(me.loop_triangles)))
    G.apply(body)
    G.finish(body, 0.0, sharp=70)
    body.name = "moulding"

    objs = [body]
    # stainless screws: a flat countersunk head in the pocket, a pan head down in the V
    fh = G.lathe("screw_aft", [(0, (floor_z - 1.35) * MM), (2.05 * MM, (floor_z - 1.35) * MM), (3.85 * MM, (floor_z - 0.05) * MM),
                               (0, (floor_z - 0.05) * MM)], ss, 24)
    fh.location = (xa * MM, 0, 0)
    G.bake_xform(fh)
    objs.append(G.finish(fh, 0, weighted=False))
    ph = G.lathe("screw_fwd", [(0, 0), (3.5 * MM, 0), (3.4 * MM, 1.2 * MM), (2.6 * MM, 2.0 * MM), (0, 2.2 * MM)], ss, 24)
    ph.location = (xf * MM, 0, (v_bot - 1.5) * MM)
    G.bake_xform(ph)
    objs.append(G.finish(ph, 0, weighted=False))
    for nm, x in (("slot_aft", xa), ("slot_fwd", xf)):
        z = floor_z - 0.04 if nm == "slot_aft" else v_bot - 1.5 + 2.2
        objs.append(G.finish(G.box(nm, (x * MM, 0, z * MM), (5.2 * MM, 0.7 * MM, 0.12 * MM), P.M("BlackPlastic")), 0, weighted=False))
    # the maker's plate on the outboard cheek (made-up TERNWAY mark: no real maker's logo)
    zc = 0.5 * _profile_top(44.0, L)
    yc = W / 2 * (1 - (1 - draft) * (zc + 10.0) / 60.0) - 0.15            # the drafted side at that height
    objs.append(P.badge("plate", "Plate", 12 * MM, 2.6 * MM,
                        Matrix.Translation((44.0 * MM, -yc * MM, zc * MM)) @ Matrix.Rotation(math.radians(90), 4, "X"), pl))

    # move the origin to the middle of the base
    off = Matrix.Translation((-L / 2 * MM, 0, 0))
    for o in objs:
        o.data.transform(off)
    h = lambda x: (x - L / 2) * MM                                       # noqa: E731
    # a 6 mm line touches both V walls where the V's half-width is 3 mm / cos(half-angle)
    zj = v_bot + (3.0 / math.cos(math.atan(v_k)) - v_half) / v_k
    socks = [("Jaw", (h(48.0), 0, zj * MM)), ("LineIn", (h(L), 0, (zj + 0.5) * MM)),
             ("Eye", (h(ex), 0, ez * MM)), ("LineOut", (h(0.0), 0, ez * MM)),
             ("FixAft", (h(xa), 0, 0)), ("FixFwd", (h(xf), 0, 0))]
    return objs, socks


def render_rope(socks):
    """A 6 mm line made fast in the jaw for the loop's in-use stills (render-only): from the load, in through the open nose
    into the V, along it and out through the eye to the tail, which hangs off toward the sailor (metres)."""
    j, li, ey, lo = (socks[k] for k in ("Jaw", "LineIn", "Eye", "LineOut"))
    s = 0.001
    return [(li[0] * s + 0.10, 0, li[2] * s + 0.012), (li[0] * s + 0.035, 0, li[2] * s + 0.003), (li[0] * s, 0, li[2] * s),
            (j[0] * s, 0, j[2] * s), (ey[0] * s, 0, ey[2] * s), (ey[0] * s - 0.008, 0, ey[2] * s + 0.0015),
            (lo[0] * s + 0.002, 0, 0.0135), (lo[0] * s - 0.02, -0.004, 0.022), (lo[0] * s - 0.07, -0.02, 0.036)], 0.003


@P.part("VCleat", "cleat", "Moulded V-cleat with fairlead eye for 3-6 mm control lines, 70 mm, screws on 48 mm centres")
def v_cleat():
    """Part detail loop round 1 (Nov 2026, docs/part-detail-loop/vcleat.md)."""
    objs, socks = _vcleat_parts()
    return P.done("VCleat", objs, socks)


# render-only hints for partloop/render_views.py, kept on the builder (PARTS info goes into kit.json, so no functions there)
v_cleat.render_rope = render_rope
v_cleat.photo_view = (-1.0, -1.0, 0.8)      # the reference photo's angle: from above the tail, pocket nearest
P.SIZES["VCleat"] = {"dim": "line mm (hole centres 48 / 64 mm)", "default": "3-6", "scale": {"3-6": 1.0, "6-10": 1.33}}
