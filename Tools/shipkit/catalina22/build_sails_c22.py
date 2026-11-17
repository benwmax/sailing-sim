"""The Catalina 22's sails as meshes (docs/c22-6), from sails_c22. Imported by build_c22.py (needs Blender's Python).
Built in the game's frame (X forward, Y starboard, Z up) and written with Y mirrored to Blender's port-positive Y, as the
rest of her is (build_deck_c22.Mesh).

One object per sail and state, all hidden but the mainsail under its cover (the boat at her mooring):

  C22_Sail_Main_Set       close-hauled on starboard tack (the boom 4 deg to port): the cloth, its bolt ropes, headboard,
                          batten pockets, the reef's points and cringles, the clew's ring
  C22_Sail_Main_Run       squared off to 70 deg under the spinnaker, lying on the lee shrouds
  C22_Sail_Main_Reefed    one reef tied in: the sail hoisted 20% lower, the bunt rolled on the boom and tied
  C22_Sail_Main_Flaked    lowered and flaked on the boom, four sail ties round it (in the boom's frame, on the centreline)
  C22_Sail_Main_Covered   flaked under its cover, which wraps the boom and the mast's foot
  C22_Sail_Jib_Set, _Lowered, _Bagged, C22_Sail_Genoa_Set, _Lowered, _Bagged
                          a headsail set on starboard tack, its hanks on the forestay; lowered in a heap on the foredeck,
                          still hanked on; or in its bag on the foredeck
  C22_Sail_Spinnaker_Set  on a run, its pole squared to starboard; C22_Sail_Spinnaker_Bagged in its bag

The set states record the boom's angle they were built for (each object's 'boom_deg' property): render_sails_c22.py
swings C22_Boom to it. The cloth is one sheet carrying UV0, UV1 and UV2 (sails_c22's convention, the game's sail cloth);
its slots are Cloth<Sail>; ropes and tapes SailLine and SailHeap, pockets SailPatch, bags SailBag, the cover SailCover.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import build_deck_c22 as BD
import build_keel_c22 as BK
import build_rig_c22 as BR
import rig_c22 as RC
import sails_c22 as SC

CLOTH_SLOT = {"Main": "ClothMain", "Jib": "ClothJib", "Genoa": "ClothGenoa", "Spinnaker": "ClothSpinnaker"}


# ------------------------------------------------------------------ helpers

def cloth_object(name, sheet, slot, mats):
    """The sheet's grid as a mesh with its three UV maps, wound so its normals face the sheet's face side."""
    G, UV = sheet.G, sheet.UV
    nu, nv = sheet.nu, sheet.nv
    bm = bmesh.new()
    idx = {}
    for i in range(nu + 1):
        for j in range(nv + 1):
            if sheet.collapse and j == nv and i > 0:
                idx[i, j] = idx[0, j]
                continue
            p = G[i, j]
            idx[i, j] = bm.verts.new((float(p[0]), float(-p[1]), float(p[2])))
    lay = [bm.loops.layers.uv.new(n) for n in ("UV0", "UV1", "UV2")]
    face = Vector((float(sheet.face[0]), float(-sheet.face[1]), float(sheet.face[2])))
    vmap = {}
    for (i, j), v in idx.items():
        vmap.setdefault(v, (i, j))
    for i in range(nu):
        for j in range(nv):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            vs, keys = [], []
            for k in q:
                if idx[k] not in vs:
                    vs.append(idx[k])
                    keys.append(k)
            if len(vs) < 3:
                continue
            f = bm.faces.new(vs)
            for lp in f.loops:
                k = keys[vs.index(lp.vert)]
                for li, ly in enumerate(lay):
                    lp[ly].uv = (float(UV[k][2 * li]), float(UV[k][2 * li + 1]))
            f.smooth = True
    # one winding for the whole sheet, from its area-weighted mean normal (never face by face: on a deep spinnaker or a
    # twisted head single faces would turn and break the shading)
    bm.normal_update()
    mean = Vector((0.0, 0.0, 0.0))
    for f in bm.faces:
        mean += f.normal * f.calc_area()
    if mean.dot(face) < 0:
        for f in bm.faces:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mats[slot])
    return ob


def join(obs, name):
    """Join objects into the first, named name. The trim's box-projected "UVMap" becomes UV0 and gets empty UV1 and UV2
    first, so the joined mesh keeps exactly the cloth's three maps (the trim reads only UV0)."""
    obs = [o for o in obs if o is not None]
    names = [u.name for u in obs[0].data.uv_layers]
    for o in obs[1:]:
        uvs = o.data.uv_layers
        if len(uvs) and uvs[0].name not in names:
            uvs[0].name = names[0] if names else uvs[0].name
        for n in names:
            if n not in uvs:
                lay = uvs.new(name=n)
                for d in lay.data:
                    d.uv = (0.0, 0.0)
    with bpy.context.temp_override(active_object=obs[0], selected_editable_objects=obs, object=obs[0]):
        bpy.ops.object.join()
    obs[0].name = obs[0].data.name = name
    return obs[0]


def transport(pts):
    """Unit tangents and two normals along a polyline (parallel transport, no twist)."""
    P = [Vector(p) for p in pts]
    T = []
    for k in range(len(P)):
        a, b = P[max(k - 1, 0)], P[min(k + 1, len(P) - 1)]
        T.append((b - a).normalized())
    u, w = BR.frame(T[0])
    U, W = [u], [w]
    for k in range(1, len(P)):
        u = U[-1] - T[k] * U[-1].dot(T[k])
        u = u.normalized() if u.length > 1e-9 else BR.frame(T[k])[0]
        U.append(u)
        W.append(T[k].cross(u).normalized())
    return P, T, U, W


def tube(m, pts, r, slot, n=8, closed=False, caps=True):
    """A rope or tape along a polyline: rings of n round each point, capped (or joined end to end if closed)."""
    P, T, U, W = transport(pts)
    rings = [[tuple(p + u * (r * math.cos(2 * math.pi * k / n)) + w * (r * math.sin(2 * math.pi * k / n)))
              for k in range(n)] for p, u, w in zip(P, U, W)]
    rings_solid(m, rings, slot, closed=closed, caps=caps)


def rings_solid(m, rings, slot, closed=False, caps=True):
    """A solid through closed rings of points (each ring the same count, in order round the axis), faces turned out
    from each ring's middle."""
    vs = [[m.v(p) for p in r] for r in rings]
    mids = [Vector([sum(c) / len(r) for c in zip(*r)]) for r in rings]
    n = len(rings[0])
    span = range(len(rings)) if closed else range(len(rings) - 1)
    for i in span:
        i1 = (i + 1) % len(rings)
        for k in range(n):
            k1 = (k + 1) % n
            q = [vs[i][k], vs[i][k1], vs[i1][k1], vs[i1][k]]
            c = (Vector(rings[i][k]) + Vector(rings[i][k1]) + Vector(rings[i1][k1]) + Vector(rings[i1][k])) / 4
            m.face(q, slot, tuple(c - (mids[i] + mids[i1]) / 2))
    if caps and not closed:
        ax = mids[-1] - mids[0]
        m.polygon(rings[0], slot, tuple(-ax))
        m.polygon(rings[-1], slot, tuple(ax))


def torus(m, c, axis, R, r, slot, n=14, k=6):
    c, ax = Vector(c), Vector(axis).normalized()
    u, w = BR.frame(ax)
    pts = [tuple(c + u * (R * math.cos(2 * math.pi * i / n)) + w * (R * math.sin(2 * math.pi * i / n))) for i in range(n)]
    tube(m, pts, r, slot, k, closed=True)


def bundle(m, path, half_w, half_h, slot, seed, n=18, lump=0.12, fold=0.0, fold_len=0.3, base=None, layers=0,
           layer_amp=0.0, drape=0.0, rest_w=0.0):
    """A soft heap of cloth along a path (game frame points): at each point an oval half_w across and half_h tall
    (lists, one per point), its bottom flat at the path's z (or base(x, y)). `lump` bends its outline in slow, smooth
    waves (two harmonics whose sizes and phases wander along the path, so it reads as cloth, not noise); `fold` bulges
    its sides every `fold_len` along it (a heap's gathers); `layers` stacks that many flakes up each side (each a
    band `layer_amp` of the width proud of the next); `drape` lets its sides hang that far below its bottom outside
    `rest_w` (a flaked sail over the boom's sides)."""
    rng = random.Random(seed)
    P = [Vector(p) for p in path]
    knots = max(2, len(P) // 4 + 2)
    keys = [[rng.uniform(-1, 1) for _ in range(4)] + [rng.uniform(0, 2 * math.pi) for _ in range(2)] for _ in range(knots)]

    def wander(k):
        u = k / max(len(P) - 1, 1) * (knots - 1)
        i = min(int(u), knots - 2)
        f = u - i
        f = f * f * (3 - 2 * f)
        return [a + (b - a) * f for a, b in zip(keys[i], keys[i + 1])]
    rings = []
    for k, p in enumerate(P):
        a, b = P[max(k - 1, 0)], P[min(k + 1, len(P) - 1)]
        t = (b - a)
        t.z = 0
        t = t.normalized()
        side = Vector((-t.y, t.x, 0))
        s = sum((P[i + 1] - P[i]).length for i in range(k))
        fl = 1 + fold * math.sin(2 * math.pi * s / fold_len)
        a1, a2, h1, h2, p1, p2 = wander(k)
        ring = []
        z0 = base(p.x, p.y) if base else p.z
        for i in range(n):
            th = 2 * math.pi * i / n
            cth, sth = math.cos(th), math.sin(th)
            wob = 1 + lump * (a1 * math.sin(2 * th + p1) + 0.6 * a2 * math.sin(3 * th + p2))
            wid = half_w[k] * fl * wob * (1 + 0.15 * max(0.0, -sth))         # the heap sags wider at its foot
            if layers and sth > -0.3:
                band = (sth + 0.3) / 1.3 * layers                           # flakes stacked up the side
                wid *= 1 + layer_amp * (abs(math.sin(math.pi * band)) - 0.5)
            y = cth * wid
            z = (sth + 1) * half_h[k] * (1 + lump * 0.5 * (h1 * math.cos(th + p1) + 0.5 * h2))
            if sth < -0.6:
                z = min(z, 0.15 * half_h[k])                                  # sitting flat on what is under it
            if drape and sth < 0.2 and abs(y) > rest_w:
                z -= drape * min(1.0, (abs(y) - rest_w) / max(wid - rest_w, 1e-6)) * min(1.0, (0.2 - sth) / 0.6)
            ring.append(tuple(Vector((p.x, p.y, z0)) + side * y + Vector((0, 0, z))))
        rings.append(ring)
    rings_solid(m, rings, slot)


def boom_frame(beta):
    """Rotate game-frame points about the gooseneck's pin by beta (the boom's angle to port)."""
    g = Vector(RC.gooseneck())
    cb, sb = math.cos(beta), math.sin(beta)
    return lambda p: tuple(g + Vector(((p[0] - g.x) * cb - (p[1] - g.y) * sb, (p[0] - g.x) * sb + (p[1] - g.y) * cb,
                                       p[2] - g.z)))


def round_box(th, half_w, half_h, n=6.0):
    """A superellipse round a box half_w by half_h (the boom's section): (y, z) at angle th, clear of its corners."""
    c, s = math.cos(th), math.sin(th)
    return (math.copysign(abs(c) ** (2 / n), c) * half_w, math.copysign(abs(s) ** (2 / n), s) * half_h)


def tie(m, x, beta, top, half, slot="SailLine", r=0.005, gap=0.006):
    """A sail tie (or a reef point's knot) round the boom and what lies on it at x: under the boom it hugs the boom's
    boxy section (a superellipse `gap` clear of its corners), over the top an arch `half` wide up to `top`."""
    rot = boom_frame(beta)
    zb = RC.boom_top()
    bh, bw = RC.BM["section"][0] / 2 + gap, RC.BM["section"][1] / 2 + gap
    zc = zb - RC.BM["section"][0] / 2
    pts = []
    for k in range(9):                                       # under: from the starboard side round to port
        y, z = round_box(-math.pi * k / 8, bw, bh)
        pts.append((x, y, zc + z))
    for k in range(9):                                       # over: from port, out over the sail and back
        th = math.pi + math.pi * k / 8
        pts.append((x, half * math.cos(th) if k else -bw, zb + (top - zb) * abs(math.sin(th))))
    pts[-1] = (x, bw, zb)
    tube(m, [rot(p) for p in pts], r, slot, 6, closed=True)


# ------------------------------------------------------------------ the mainsail

def main_trim(m, sh, state):
    """Bolt ropes, headboard, battens' pockets, the reef's points and cringles and the clew's ring on a set main."""
    G = sh.G
    tube(m, [tuple(p) for p in G[0, :]], 0.004, "SailHeap", 8)                    # the luff's bolt rope, in the groove
    tube(m, [tuple(p) for p in G[:, 0]], 0.004, "SailHeap", 8)                    # the foot's, in the boom's
    vs = sh.UV[0, :, 1]
    # the headboard: a plate each side of the head, the cloth between
    top = G[:, -1]
    d = Vector(tuple(top[-1] - top[0])).normalized()
    nrm = Vector(tuple(sh.normals(np.array([0.0, 1.0, 0.0]))[0, -1]))
    c = Vector(tuple(top[0])) + d * (SC.MS["head_board"] / 2 + 0.005) - Vector((0, 0, 0.07))
    BR.plank(m, tuple(c), tuple(d), tuple(nrm), (0, 0, 1), SC.MS["head_board"] / 2 + 0.008, 0.004, 0.075, "Aluminium")
    # battens' pockets: a strip of cloth each side along the row from the leech in
    for h, L in SC.MS["battens"]:
        v = h * SC.P_M
        if v < vs[0] + 0.05:
            continue
        chord = float(sh.extras["chord"](v))
        f0 = max(0.0, 1.0 - L / chord)
        hw = SC.MS["batten_pocket_w"] / 2
        rings = []
        for f in np.linspace(f0, 0.995, 10):
            p = Vector(tuple(SC.main_point(sh, f, v)))
            pu = Vector(tuple(SC.main_point(sh, f, v + 0.05)))
            up = (pu - p).normalized()
            n_ = Vector(tuple(SC.main_point(sh, min(f + 0.01, 1.0), v))) - p
            n = n_.cross(up).normalized()
            rings.append([tuple(p + up * (hw * a) + n * (0.003 * b)) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        rings_solid(m, rings, "SailPatch")
    # the reef: its points across the sail (a short tail each side) and a cringle at each end
    vr = SC.MS["reef"] * SC.P_M
    if state != "Reefed":
        k = SC.MS["reef_points"]
        for i in range(1, k + 1):
            f = i / (k + 1)
            p = Vector(tuple(SC.main_point(sh, f, vr)))
            pa = Vector(tuple(SC.main_point(sh, f + 0.01, vr)))
            pu = Vector(tuple(SC.main_point(sh, f, vr + 0.05)))
            n = (pa - p).cross(pu - p).normalized()
            for sgn in (-1, 1):
                a = p + n * (sgn * 0.004)
                tube(m, [tuple(a), tuple(a + n * (sgn * 0.02) - Vector((0, 0, 0.05))),
                         tuple(a + n * (sgn * 0.03) - Vector((0, 0, 0.17)))], 0.003, "SailLine", 6)
        for f, back in ((0.0, 1), (1.0, -1)):
            p = Vector(tuple(SC.main_point(sh, f, vr)))
            pa = Vector(tuple(SC.main_point(sh, min(max(f + 0.02 * back, 0), 1), vr)))
            pu = Vector(tuple(SC.main_point(sh, f, vr + 0.05)))
            dd = (pa - p).normalized()
            torus(m, tuple(p + dd * 0.025), tuple((pa - p).cross(pu - p)), 0.011, 0.003, "Stainless")
    # the clew's ring
    p, pa = Vector(tuple(G[-1, 0])), Vector(tuple(G[-2, 0]))
    torus(m, tuple(p + (pa - p).normalized() * 0.03 + Vector((0, 0, 0.03))), tuple((pa - p).cross(Vector((0, 0, 1)))),
          0.012, 0.0035, "Stainless")


def build_main_set(mats, state, sheets):
    sh = sheets["Main" + state]
    cl = cloth_object("C22_Sail_Main_%s_cloth" % state, sh, CLOTH_SLOT["Main"], mats)
    m = BD.Mesh("C22_Sail_Main_%s_trim" % state)
    main_trim(m, sh, state)
    beta = sh.extras["beta"]
    if state == "Reefed":
        # the bunt: the reef's panel rolled along the boom, tied at each reef point round the boom
        rot = boom_frame(beta)
        xl = sh.extras["xl"]
        chord = sh.extras["chord"](sh.extras["reef"])
        zb = RC.boom_top()
        xs = np.linspace(xl - 0.05, xl - chord + 0.1, 24)
        path = [rot((x, 0.0, zb)) for x in xs]
        hw = [0.045 + 0.02 * math.sin(math.pi * k / 23) for k in range(24)]
        hh = [0.04 + 0.015 * math.sin(math.pi * k / 23) for k in range(24)]
        bundle(m, path, hw, hh, "SailHeap", seed=11, lump=0.15)
        k = SC.MS["reef_points"]
        for i in range(1, k + 1):
            x = xl - chord * i / (k + 1)
            q = int(round(np.interp(x, xs[::-1], np.arange(24)[::-1])))     # the bunt's ring there: tie round it
            tie(m, x, beta, zb + 2 * hh[q] * 1.12 + 0.004, hw[q] * 1.08 + 0.004)
    tr = m.finish(mats)
    ob = join([cl, tr], "C22_Sail_Main_" + state)
    ob["boom_deg"] = math.degrees(beta)
    return ob


def build_main_flaked(mats, covered):
    """The mainsail lowered and flaked on the boom (on the centreline), its ties round it; or under its cover."""
    m = BD.Mesh("C22_Sail_Main_" + ("Covered" if covered else "Flaked"))
    xl = RC.MAST_X - RC.A / 2
    x_end = RC.boom_band()[1] + 0.05
    zb = RC.boom_top()
    n = 40
    xs = np.linspace(xl - 0.04, x_end, n)
    vol = SC.MS["area"] * 1.08 * SC.CL["dacron_mm"] / 1000 * SC.CL["bulk"]
    # an oval that tapers aft, sized to the sail's folded volume
    shape = [1.0 - 0.45 * k / (n - 1) for k in range(n)]
    L = xl - x_end
    area = vol / L
    h0 = math.sqrt(area / (math.pi * 0.5 * 0.75)) * 1.1
    hw = [0.75 * h0 * s for s in shape]
    hh = [0.5 * h0 * s * 1.1 for s in shape]
    if covered:
        cw = [w + 0.02 for w in hw]
        rings = []
        bw, bh = RC.BM["section"][1] / 2, RC.BM["section"][0]
        for k, x in enumerate(xs):
            ring = []
            for i in range(20):
                th = 2 * math.pi * i / 20
                c, s = math.cos(th), math.sin(th)
                if s >= 0:                                  # over the sail
                    y, z = c * cw[k], zb + 0.004 + s * (2 * hh[k] + 0.02)
                else:                                       # down the boom's sides, closed under it, clear of
                    y, z = round_box(th, bw + 0.008, bh / 2 + 0.008)   # its corners
                    z += zb - bh / 2
                ring.append((x, y, z))
            rings.append(ring)
        rings_solid(m, rings, "SailCover")
        # the cover's collar round the mast above the gooseneck, and its zip's line along the top
        BR.loft(m, BR.oval(0.012), [(zb - 0.01, 1), (zb + 0.28, 1)], lambda u, v, z: (RC.MAST_X + u, v, z), "SailCover")
        tube(m, [(x, 0.0, zb + 0.004 + 2 * hh[k] + 0.021) for k, x in enumerate(xs)], 0.004, "BlackPlastic", 6)
    else:
        path = [(x, 0.0, zb) for x in xs]
        bundle(m, path, hw, hh, "SailHeap", seed=5, lump=0.08, fold=0.06, fold_len=0.45, layers=5, layer_amp=0.12,
               drape=0.035, rest_w=RC.BM["section"][1] / 2 + 0.004)
        for f in (0.12, 0.38, 0.62, 0.86):
            k = int(f * (n - 1))
            tie(m, xs[k], 0.0, zb + 2 * hh[k] + 0.006, hw[k] + 0.01)
        # the headboard and its halyard shackle at the forward end, on top
        BR.plank(m, (xl - 0.12, 0.0, zb + 2 * hh[0] + 0.01), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.06, 0.05, 0.004, "Aluminium")
    return m.finish(mats)


# ------------------------------------------------------------------ the headsails

def hank_stations(sh, spacing=None):
    """Where the hanks sit up the luff (metres along it from the tack)."""
    G = sh.G
    lu = np.cumsum(np.r_[0.0, np.linalg.norm(np.diff(G[0], axis=0), axis=1)])
    return np.arange(0.12, lu[-1] - 0.05, spacing or SC.HS["hank_spacing"]), lu


def hank_count(sh):
    return len(hank_stations(sh)[0])


def hanks(m, sh, spacing):
    """Piston hanks up the luff: a ring round the forestay and over the luff tape every `spacing`."""
    foot, u, Ls = SC.stay()
    G = sh.G
    ss, lu = hank_stations(sh, spacing)
    for s in ss:
        p = Vector(tuple(np.array([np.interp(s, lu, G[0, :, a]) for a in range(3)])))
        q = Vector(tuple(foot)) + Vector(tuple(u)) * (Vector(tuple(foot - p)).dot(-Vector(tuple(u))))
        mid = (p + q) / 2
        torus(m, tuple(mid), tuple(u), (p - q).length / 2 + 0.006, 0.0022, "Stainless", 12, 5)


def headsail_trim(m, sh, name):
    G = sh.G
    tube(m, [tuple(p) for p in G[0, :]], 0.0045, "SailHeap", 8)                      # the luff tape
    hanks(m, sh, SC.HS["hank_spacing"])
    T, C = Vector(tuple(G[0, 0])), Vector(tuple(G[-1, 0]))
    for p, q in ((T, Vector(tuple(G[1, 0]))), (C, Vector(tuple(G[-2, 0])))):     # the tack's and clew's rings
        up = Vector(tuple(G[0 if p is T else -1, 2])) - p
        torus(m, tuple(p + (q - p).normalized() * 0.025 + up.normalized() * 0.02), tuple((q - p).cross(up)), 0.011,
              0.0035, "Stainless")
    tack_pennant(m, Vector(tuple(sh.extras["T"])))


def tack_pennant(m, T):
    """A sail cut with its tack above the stemhead fitting (the genoa, so its foot clears the pulpit) reaches it on a
    3/16 in wire pennant: an eye spliced round a thimble at each end, the lower shackled to the fitting."""
    F = Vector(tuple(SC.tack_fitting()))
    if (T - F).length < 0.05:
        return
    d = (T - F).normalized()
    side = d.cross(Vector((0.0, 1.0, 0.0))).normalized()
    a, b = F + d * 0.035, T - d * 0.03
    tube(m, [tuple(a), tuple(b)], 0.0024, "Stainless", 8)
    for p, s in ((a, 1), (b, -1)):
        torus(m, tuple(p - d * (s * 0.012)), tuple(side), 0.010, 0.0025, "Stainless", 12, 5)     # the thimbled eyes
    BR.rod(m, tuple(F - d * 0.01), tuple(F + d * 0.012), 0.004, "Stainless", 10)                # its shackle's pin


def build_headsail_set(mats, name, sheets):
    sh = sheets[name + "Set"]
    cl = cloth_object("C22_Sail_%s_Set_cloth" % name, sh, CLOTH_SLOT[name], mats)
    m = BD.Mesh("C22_Sail_%s_Set_trim" % name)
    headsail_trim(m, sh, name)
    return join([cl, m.finish(mats)], "C22_Sail_%s_Set" % name)


def deck_base(lift=0.0):
    return lambda x, y: SC.floor_z(x, y) + lift


def build_headsail_lowered(mats, name, sheets):
    """Down in a heap along the foredeck from the tack aft, its hanks still on the forestay's foot."""
    m = BD.Mesh("C22_Sail_%s_Lowered" % name)
    area = sheets[name + "Set"].area()
    vol = area * SC.CL["dacron_mm"] / 1000 * SC.CL["bulk"] * 1.4            # a loose heap, not flaked
    T = SC.tack_fitting()                                                  # the heap starts at the stemhead
    Ts = SC.headsail_corners(name)[0]                                       # the tack itself, on its pennant if cut high
    FH = BD.DK.D["fore_hatch"]
    L = T[0] - 0.06 - (FH["x"] + FH["size"][0] / 2 + 0.05)                # ends 5 cm forward of the fore hatch
    n = 30
    xs = np.linspace(T[0] - 0.06, T[0] - L, n)
    rng = random.Random(name)
    ys = [0.05 * math.sin(2.4 * k / n * math.pi) * (k / n) + 0.02 * (rng.random() - 0.5) for k in range(n)]
    shape = [math.sin(math.pi * (0.15 + 0.85 * k / (n - 1))) ** 0.6 for k in range(n)]
    s_mean = sum(shape) / n
    h0 = math.sqrt(vol / (L * math.pi * 0.5 * 1.6 * s_mean ** 2))
    hw = [0.8 * h0 * s + 0.02 for s in shape]
    hh = [0.5 * h0 * s + 0.01 for s in shape]
    path = [(x, y, 0.0) for x, y in zip(xs, ys)]
    bundle(m, path, hw, hh, "SailHeap", seed=sum(map(ord, name)), lump=0.25, fold=0.14, fold_len=0.22,
           base=deck_base(-0.004))
    # the hanks bunched at the stay's foot, the luff tape running up into them
    foot, u, Ls = SC.stay()
    k_n = hank_count(sheets[name + "Set"])                                  # as many as the set luff carries
    s0 = max(0.06, float(np.dot(Ts - foot, u)) + 0.03)                      # stacked, touching, above the tack
    for k in range(k_n):
        s = s0 + 0.009 * k
        c = Vector(tuple(foot)) + Vector(tuple(u)) * s
        torus(m, tuple(c + Vector((-0.006, 0, 0))), tuple(u), 0.015, 0.0022, "Stainless", 12, 5)   # clear of the stay
    tube(m, [tuple(Vector(tuple(foot)) + Vector(tuple(u)) * (s0 + 0.03 + 0.009 * k_n) + Vector((-0.02, 0, 0))),
          tuple(Vector(tuple(T)) + Vector((-0.06, 0, 0.03)))], 0.0045, "SailHeap", 8)
    tack_pennant(m, Vector(tuple(Ts)))
    return m.finish(mats)


def build_bag(mats, name, area, nylon, at):
    """A sail in its bag lying on the foredeck: a soft drum with a drawstring's gather at one end."""
    m = BD.Mesh("C22_Sail_%s_Bagged" % name)
    L, r = SC.bag_size(area, nylon)
    n = 12
    xs = np.linspace(at[0] + L / 2, at[0] - L / 2, n)
    end = [math.sin(math.pi * (0.06 + 0.88 * k / (n - 1))) ** 0.35 for k in range(n)]
    hw = [r * 1.12 * e for e in end]
    hh = [r * 0.82 * e for e in end]
    bundle(m, [(x, at[1], 0.0) for x in xs], hw, hh, "SailBag", seed=len(name) * 7, lump=0.08, base=deck_base(-0.003))
    z = SC.floor_z(xs[0], at[1]) + hh[0]
    torus(m, (xs[0] + 0.005, at[1], z), (1, 0, 0), hw[0] * 0.55, 0.004, "SailLine", 12, 5)
    return m.finish(mats)


# ------------------------------------------------------------------ the spinnaker

def build_spinnaker_set(mats, sheets):
    sh = sheets["SpinnakerSet"]
    cl = cloth_object("C22_Sail_Spinnaker_Set_cloth", sh, CLOTH_SLOT["Spinnaker"], mats)
    m = BD.Mesh("C22_Sail_Spinnaker_Set_trim")
    G = sh.G
    tube(m, [tuple(p) for p in G[0, :]], 0.003, "SailLine", 6)                    # the luff's and leech's tapes
    tube(m, [tuple(p) for p in G[-1, :]], 0.003, "SailLine", 6)
    tube(m, [tuple(p) for p in G[:, 0]], 0.003, "SailLine", 6)                    # the foot's
    ring, tip = SC.pole()
    d = Vector(tuple(tip - ring)).normalized()
    BR.rod(m, tuple(Vector(tuple(ring)) + d * 0.02), tuple(Vector(tuple(tip)) - d * 0.03), SC.SP["pole_d"] / 2, "Aluminium", 16)
    for a, b in ((Vector(tuple(ring)) + d * 0.0, Vector(tuple(ring)) + d * 0.06),
                 (Vector(tuple(tip)) - d * 0.07, Vector(tuple(tip)) - d * 0.01)):
        BR.rod(m, tuple(a), tuple(b), SC.SP["pole_d"] / 2 + 0.003, "BlackPlastic", 16)
    # the pole's ring on the mast's front: a strap and an eye
    BR.plank(m, (RC.MAST_X + RC.A / 2 + 0.004, 0.0, ring[2]), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.004, 0.014, 0.05, "Stainless")
    torus(m, tuple(Vector(tuple(ring)) + Vector((0.004, 0, 0))), (0, 0, 1), 0.012, 0.0035, "Stainless")
    for p in (sh.extras["T"], sh.extras["C"]):                                       # the tack's and clew's rings
        torus(m, tuple(p), (0, 0, 1), 0.012, 0.0035, "Stainless")
    top = Vector(tuple(sh.extras["H"])) + Vector((0, 0, 0.05))
    BR.rod(m, tuple(sh.extras["H"]), tuple(top), 0.006, "Stainless", 10)                # the head's swivel
    tube(m, [tuple(top), tuple(SC.halyard_block())], 0.004, "SailLine", 6)          # up to the halyard's block
    return join([cl, m.finish(mats)], "C22_Sail_Spinnaker_Set")


# ------------------------------------------------------------------ all of it

SHOWN = ("C22_Sail_Main_Covered",)


def build_all(mats):
    sheets = SC.set_sheets()
    obs = [build_main_set(mats, st, sheets) for st in ("Set", "Run", "Reefed")]
    obs += [build_main_flaked(mats, False), build_main_flaked(mats, True)]
    for name, at in (("Jib", (2.62, 0.0)), ("Genoa", (2.62, 0.0))):
        obs += [build_headsail_set(mats, name, sheets), build_headsail_lowered(mats, name, sheets),
                build_bag(mats, name, sheets[name + "Set"].area(), False, at)]
    obs += [build_spinnaker_set(mats, sheets), build_bag(mats, "Spinnaker", SC.SP["area"], True, (2.62, 0.0))]
    for ob in obs:
        if ob.name not in SHOWN:
            ob.hide_render = ob.hide_viewport = True
    return obs
