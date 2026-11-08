"""Part detail loop (Nov 2026, docs/part-detail-loop/snaphook.md): the forged stainless snap hook.

The kind of hook spliced onto a halyard, a spinnaker sheet or a dock line: one forged teardrop body, a wire spring gate
that tucks under a turned-down nose, a flat palm with an oval eye for the line, and a round riveted boss where the gate's
spring sits. Sized from the 75 mm catalogue size (75 mm long, 67 g); the outline follows Bean's reference sheet (Nov 8)
traced square-on, as fractions of the length.

How it is built: the body is one signed distance field (the traced outline with the eye cut out, made into a slab whose
edges are rounded almost to an oval, thicker along the spine than at the nose, with the boss on its face and a square
recess in the boss), turned into a mesh with surface nets on a 0.25 mm grid, smoothed lightly and reduced to the budget.
So the casting has no seams and its sections are the soft flattened ovals of a forging. The gate is a separate stainless
wire loop. Numpy only (it ships with Blender), so the PC's kit build needs nothing new.

Frame: the hook lies in the XZ plane, the eye's centre at the origin (where the line is made fast), the hook up +Z, the
spine on +X and the gate on -X; the riveted face looks to -Y, so the side render sees it as the photo does.
"""
import math

import bmesh
import numpy as np

import bk_geom as G
import bk_parts as P

# Traced on the square-on reference (Bean's sheet, turned so the long axis is vertical: docs/part-detail-loop/snaphook.md),
# in that image's pixels: x right, y down. The hook runs from y = 11 (crown) to y = 357 (bottom of the eye), 75 mm.
_PX_TOP, _PX_BOT, _PX_X0, _PX_Y0 = 11.0, 357.0, 100.0, 297.0      # the eye's centre is the origin
_OUTER = [(18, 138), (11, 126), (8, 110), (10, 94), (15, 82), (20, 76), (30, 60), (44, 44), (62, 30), (82, 19), (102, 13), (122, 11),
          (140, 15), (154, 25), (164, 41), (170, 62), (173, 92), (174, 130), (173, 175), (170, 220), (165, 258),
          (158, 290), (147, 318), (132, 338), (113, 352), (92, 357), (72, 354), (57, 344), (47, 330), (43, 312),
          (45, 294), (50, 280)]
_INNER = [(54, 258), (59, 240), (66, 223), (76, 205), (88, 187), (99, 169), (109, 150), (116, 134), (120, 118),
          (121, 98), (116, 74), (104, 56), (88, 46), (70, 46), (55, 54), (44, 68), (37, 86), (34, 104), (33, 118),
          (32, 134), (25, 140)]
_EYE = (101, 296, 44, 26, -32)          # centre x, y, semi-axis along the hook, across, tilt (deg, top leaning to +x)
_BOSS = (131, 200, 21)                   # centre x, y, radius
_GATE = [((29, 109), (44, 304)), ((45, 110), (59, 299))]   # the wire's two legs, nose end to the palm


def _px(x, y, s):
    return ((x - _PX_X0) * s, (_PX_Y0 - y) * s)


def _chaikin(pts, n=3):
    for _ in range(n):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            out += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        pts = out
    return pts


def _poly_sdf(poly, X, Z):
    """Signed distance (negative inside) from the points (X, Z) to a closed polygon."""
    p = np.asarray(poly)
    a, b = p, np.roll(p, -1, axis=0)
    px, pz = X.reshape(-1, 1), Z.reshape(-1, 1)
    ex, ez = (b[:, 0] - a[:, 0])[None], (b[:, 1] - a[:, 1])[None]
    wx, wz = px - a[None, :, 0], pz - a[None, :, 1]
    t = np.clip((wx * ex + wz * ez) / (ex * ex + ez * ez + 1e-18), 0.0, 1.0)
    d = np.sqrt(((wx - ex * t) ** 2 + (wz - ez * t) ** 2).min(1))
    # crossing number for inside
    az, bz = a[None, :, 1], b[None, :, 1]
    cond = (az > pz) != (bz > pz)
    xint = a[None, :, 0] + (pz - az) * (b[None, :, 0] - a[None, :, 0]) / (bz - az + 1e-18)
    inside = (cond & (px < xint)).sum(1) % 2 == 1
    return np.where(inside, -d, d).reshape(X.shape)


def _smooth(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _surface_nets(F, origin, vs):
    """Quads (outward) round the zero level of a sampled field F (negative inside): one vertex per cell the surface
    crosses, at the mean of its edge crossings."""
    nx, ny, nz = F.shape
    cx, cy, cz = nx - 1, ny - 1, nz - 1
    acc = np.zeros((cx * cy * cz, 3))
    cnt = np.zeros(cx * cy * cz)
    grid = np.indices(F.shape).astype(float)
    quads = []
    for ax in range(3):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[ax], sl1[ax] = slice(0, -1), slice(1, None)
        f0, f1 = F[tuple(sl0)], F[tuple(sl1)]
        ch = (f0 < 0) != (f1 < 0)
        e = np.nonzero(ch)
        t = f0[e] / (f0[e] - f1[e])
        pos = np.stack([grid[i][tuple(sl0)][e] for i in range(3)], 1)
        pos[:, ax] += t
        # the four cells sharing this edge
        o1, o2 = [a_ for a_ in range(3) if a_ != ax]
        for d1 in (-1, 0):
            for d2 in (-1, 0):
                c = [e[0].copy(), e[1].copy(), e[2].copy()]
                c[o1] = c[o1] + d1
                c[o2] = c[o2] + d2
                ok = (c[0] >= 0) & (c[0] < cx) & (c[1] >= 0) & (c[1] < cy) & (c[2] >= 0) & (c[2] < cz)
                ci = (c[0][ok] * cy + c[1][ok]) * cz + c[2][ok]
                np.add.at(acc, ci, pos[ok])
                np.add.at(cnt, ci, 1)
        # faces: edges away from the border; corner order counter-clockwise about +ax
        inner = np.ones(len(t), bool)
        for o in (o1, o2):
            inner &= (e[o] >= 1) & (e[o] < F.shape[o] - 1)
        ee = [x[inner] for x in e]
        neg = (f0[e] < 0)[inner]                 # inside at the low end: outward is +ax
        # (o1, o2) is a right-handed pair about ax for ax = 0 (y, z) and 2 (x, y); for ax = 1 it is (x, z): flip
        flip = neg if ax != 1 else ~neg
        cells = []
        for d1, d2 in ((-1, -1), (0, -1), (0, 0), (-1, 0)):
            c = [ee[0].copy(), ee[1].copy(), ee[2].copy()]
            c[o1] = c[o1] + d1
            c[o2] = c[o2] + d2
            cells.append((c[0] * cy + c[1]) * cz + c[2])
        q = np.stack(cells, 1)
        q[~flip] = q[~flip][:, ::-1]
        quads.append(q)
    used = np.nonzero(cnt)[0]
    remap = -np.ones(len(cnt), int)
    remap[used] = np.arange(len(used))
    verts = origin + acc[used] / cnt[used, None] * vs
    faces = remap[np.concatenate(quads)]
    return verts, faces


def _body_field(s, vs, pad, h_base, h_spine, h_nose, round_k, boss_h, eye_rim=0.0):
    outer = [_px(x, y, s) for x, y in _chaikin(_OUTER + _INNER, 3)]
    ex, ey, ea, eb, tilt = _EYE
    ec = _px(ex, ey, s)
    th = math.radians(tilt)
    eye = []
    for i in range(72):
        u = G.TAU * i / 72
        lx, lz = eb * s * math.cos(u), ea * s * math.sin(u)            # across, along (along is +Z before the tilt)
        eye.append((ec[0] + lx * math.cos(th) + lz * math.sin(th), ec[1] - lx * math.sin(th) + lz * math.cos(th)))
    xs = [p[0] for p in outer]
    zs = [p[1] for p in outer]
    hmax = max(h_base, h_spine) + eye_rim + boss_h + pad
    gx = np.arange(min(xs) - pad, max(xs) + pad + vs, vs)
    gy = np.arange(-hmax, hmax + vs, vs)
    gz = np.arange(min(zs) - pad, max(zs) + pad + vs, vs)
    X2, Z2 = np.meshgrid(gx, gz, indexing="ij")
    de = _poly_sdf(eye, X2, Z2)                  # outside the eye is positive
    d2 = np.maximum(_poly_sdf(outer, X2, Z2), -de)
    # half-thickness: the spine is the beefy side, the nose arm the thinnest
    L = (_PX_BOT - _PX_TOP) * s
    zn = Z2 / L
    spine = _smooth(0.02 * L, 0.12 * L, X2) * _smooth(0.0, 0.14, zn) * (1 - _smooth(0.66, 0.84, zn))
    nose = _smooth(0.0, -0.12 * L, X2) * _smooth(0.55, 0.70, zn)
    h = h_base + (h_spine - h_base) * spine + (h_nose - h_base) * nose
    h = h + eye_rim * np.exp(-((np.maximum(de, 0) - 0.0012) / 0.0011) ** 2)   # the eye's raised rounded rim
    r = round_k * h
    X3 = X2[:, None, :]
    Y3 = gy[None, :, None]
    Z3 = Z2[:, None, :]
    w1 = d2[:, None, :] + r[:, None, :]
    w2 = np.abs(Y3) - (h - r)[:, None, :]
    F = np.minimum(np.maximum(w1, w2), 0) + np.sqrt(np.maximum(w1, 0) ** 2 + np.maximum(w2, 0) ** 2) - r[:, None, :]
    # the riveted boss on the -Y face: a low rounded disc, and a square recess in it (the spring's rivet)
    bx, by, br = _BOSS
    bc = _px(bx, by, s)
    i_b = (np.abs(gx - bc[0]).argmin(), np.abs(gz - bc[1]).argmin())
    hb = float(h[i_b])
    rad = np.sqrt((X3 - bc[0]) ** 2 + (Z3 - bc[1]) ** 2) - br * s
    yb = -(hb + boss_h * 0.5)
    rr = 0.35 * boss_h
    q1, q2 = rad + rr, np.abs(Y3 - yb) - (boss_h + hb * 0.4) * 0.5 + rr   # sinks into the body a little
    boss = np.minimum(np.maximum(q1, q2), 0) + np.sqrt(np.maximum(q1, 0) ** 2 + np.maximum(q2, 0) ** 2) - rr
    F = np.minimum(F, boss)
    a = math.radians(18)
    ux = (X3 - bc[0]) * math.cos(a) + (Z3 - bc[1]) * math.sin(a)
    uz = -(X3 - bc[0]) * math.sin(a) + (Z3 - bc[1]) * math.cos(a)
    sq = 0.42 * br * s
    rec = np.maximum(np.maximum(np.abs(ux) - sq, np.abs(uz) - sq), Y3 - (-(hb + boss_h) + 0.0005))   # 0.5 mm deep
    F = np.maximum(F, -rec)
    return F, np.array([gx[0], gy[0], gz[0]]), h, (gx, gz)


def _mesh(name, verts, faces, mat):
    bm = bmesh.new()
    vv = [bm.verts.new(tuple(v)) for v in verts]
    for f in faces:
        if len(set(f)) == 4:
            try:
                bm.faces.new([vv[i] for i in f])
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _hook_parts(L=0.075, vs=0.00025, tris=16000):
    s = L / (_PX_BOT - _PX_TOP)                 # metres per traced pixel
    ss = P.M("Stainless")
    F, origin, h, _ = _body_field(s, vs, pad=4 * vs, h_base=0.0031, h_spine=0.0041, h_nose=0.0025,
                                  round_k=0.8, boss_h=0.0009, eye_rim=0.0005)
    verts, faces = _surface_nets(F, origin, vs)
    body = _mesh("forging", verts, faces, ss)
    sm = body.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 3
    G.apply(body)
    d = body.modifiers.new("budget", "DECIMATE")
    me = body.data
    me.calc_loop_triangles()
    d.ratio = min(1.0, tris / max(1, len(me.loop_triangles)))
    G.apply(body)
    G.finish(body, 0.0, sharp=75)
    objs = [body]
    # the gate: one stainless spring wire, a long narrow loop whose two legs run from the palm up under the nose
    rw = 0.00115
    (a0, a1), (b0, b1) = _GATE
    A0, A1, B0, B1 = (_px(*p, s) for p in (a0, a1, b0, b1))
    top = ((A0[0] + B0[0]) / 2, max(A0[1], B0[1]) + 0.3 * abs(B0[0] - A0[0]))
    rad = abs(B0[0] - A0[0]) / 2
    arc = G.arc_pts((top[0], 0, max(A0[1], B0[1])), rad, math.pi, 0, 10, "xz")
    path = [(A1[0], 0, A1[1])] + [(A0[0], 0, A0[1])] + arc[1:-1] + [(B0[0], 0, B0[1]), (B1[0], 0, B1[1])]
    gate = G.tube("gate", path, rw, ss, 12)
    objs.append(G.finish(gate, 0.0, sharp=80))
    nose = _px(20, 122, s)
    socks = [("Eye", (0, 0, 0)), ("Bite", (_px(95, 50, s)[0], 0, _px(95, 50, s)[1])), ("Nose", (nose[0], 0, nose[1])),
             ("Gate", ((A0[0] + A1[0]) / 2, 0, (A0[1] + A1[1]) / 2))]
    return objs, socks


@P.part("SnapHook", "fastener", "Forged stainless snap hook, 75 mm, wire spring gate under a turned-down nose, oval eye")
def snap_hook(length=0.075):
    objs, socks = _hook_parts(length)
    return P.done("SnapHook", objs, socks)


P.SIZES["SnapHook"] = {"dim": "length mm", "default": "75", "scale": {"50": 0.667, "75": 1.0, "100": 1.333}}
