"""The frigate's head (docs/shipkit-9): the knee of the head with its gammoning slot and bobstay holes, the cheeks and
trailboards on it (the trailboards carved), the head rails and timbers, the head gratings, the knightheads either side
of the bowsprit, the bow's opening between them and the bowsprit's bed under it, and our figure on her console at the
knee's head.
    from head import Head;  hd = Head(L, rig, sk).build();  hd.parts();  hd.open_bow(skin_parts)
Sizes and places are decor_1797.json's "head" and "figure", each with its source: the 1927 lines plan's head (traced
and taken to the ship's frame through scanreg), the 1817 draught, or the period's practice. Units: metres in the ship
frame (X forward, Y starboard, Z up, origin on the centreline at midships on waterline A). The knee, the figure and her
console and the bowsprit's bed are built whole (both sides); the cheeks, trailboards, rails, timbers, gratings and
knightheads are starboard parts, mirrored for port by the caller. Our bowsprit steeves from the forecastle (slice 3)
and passes over the stem head about 1.3 m higher than the 1927 plan's: the knee, cheeks and rails keep the plan's
elevation and the figure (Head.figure, from make_figure.py's figure_hope.npz) stands up under the bowsprit. The
gammoning and bobstays through the knee are rigging.py's (Standing.head_rigging).
"""
import json
import math
import os

import numpy as np
from scipy.interpolate import CubicSpline

import carve
import deck
import loft
from skin import Part, compact, sweep

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def spline_pts(P, step):
    """Points along a smooth curve through P (n, d) (a cubic spline in chord length), about step apart, ends kept."""
    P = np.asarray(P, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    cs = CubicSpline(s, P, bc_type="natural")
    n = max(2, int(math.ceil(s[-1] / step)) + 1)
    return cs(np.linspace(0.0, s[-1], n))


def resample(P, step):
    """A polyline P (n, d) resampled about step apart (straight between its points), ends kept."""
    P = np.asarray(P, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    n = max(2, int(math.ceil(s[-1] / step)) + 1)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])], -1)


def signed_area(P):
    P = np.asarray(P, float)
    return 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))


def ccw(P):
    P = np.asarray(P, float)
    return P if signed_area(P) > 0 else P[::-1]


def stadium(x0, x1, z0, z1, n=8):
    """A rounded slot (n points on each round end), counter-clockwise."""
    r = 0.5 * (z1 - z0)
    zc = 0.5 * (z0 + z1)
    a = np.linspace(-math.pi / 2, math.pi / 2, n)
    right = np.stack([x1 - r + r * np.cos(a), zc + r * np.sin(a)], -1)
    left = np.stack([x0 + r - r * np.cos(a), zc - r * np.sin(a)], -1)
    return np.concatenate([right, left])


def disc(c, r, n=14):
    a = np.arange(n) * 2 * math.pi / n
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], -1)


def slab(mesh, outline, holes, step, to3d, half, mat, edge_mat=None):
    """A plate over the 2D outline less its holes, its two faces half(P2) either side of its plane (to3d(P2, d): points
    of the plane's coordinates P2 moved d along its normal), walls round the outline and every hole; every face turned
    out. half may vary over the plate (a bevel)."""
    outline = ccw(outline)
    holes = [ccw(h)[::-1] for h in holes]              # clockwise: the solid lies to the left of every boundary edge
    P2, T = deck.cdt(outline, holes, step)             # (P2 starts with the outline's and the holes' points, in order)
    n = len(P2)
    h = np.asarray(half(P2), float)
    V = np.concatenate([to3d(P2, h), to3d(P2, -h)])
    # the + face: its triangles counter-clockwise in the plane's coordinates face along +normal if to3d is right-handed
    t0 = T[0]
    a, b, c = V[t0[0]], V[t0[1]], V[t0[2]]
    nrm = np.cross(b - a, c - a)
    plus = to3d(P2[t0[:1]], np.ones(1))[0] - to3d(P2[t0[:1]], np.zeros(1))[0]
    flip = nrm @ plus < 0
    F = [tuple(t[::-1]) if flip else tuple(t) for t in T]
    F += [tuple(n + i for i in (t if flip else t[::-1])) for t in T]
    M = [mat] * len(F)
    k0 = 0
    for loop in [outline] + holes:
        m = len(loop)
        for i in range(m):
            p, q = k0 + i, k0 + (i + 1) % m
            # the solid is to the left of p -> q: the wall faces right; build it so and check against that
            quad = (p, n + p, n + q, q)
            Q = V[list(quad)]
            wn = np.cross(Q[1] - Q[0], Q[3] - Q[0])
            d2 = P2[q] - P2[p]
            right = to3d(np.array([P2[p] + np.array([d2[1], -d2[0]]) * 1e-3]), np.zeros(1))[0] - \
                to3d(P2[p:p + 1], np.zeros(1))[0]
            F.append(quad if wn @ right > 0 else quad[::-1])
            M.append(edge_mat or mat)
        k0 += m
    mesh.add(V, F, M)
    return P2, T


def cut_away(V, F, M, cuts, near):
    """The faces (V, F, M) less what lies inside the convex region where (p - c).n < 0 for every cut (c, n): the
    faces with a corner near it (near(p)) are split on each cut's plane (bmesh: an edge is split once for both its
    faces, so no crack opens), then every face whose middle lies inside goes. Returns V, F, M, the count of faces gone
    and the cut's edges, each (p, q, j): an open edge left lying on cut j's plane."""
    import bmesh
    V = np.asarray(V, float)
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(p)) for p in V]
    mats = sorted(set(M))
    for f, mt in zip(F, M):
        bm.faces.new([vs[i] for i in f]).material_index = mats.index(mt)
    close = [near(p) for p in V]
    faces = [f for f, g in zip(bm.faces, F) if any(close[i] for i in g)]
    for c, n in cuts:
        geom = faces + list({e for f in faces for e in f.edges}) + list({v for f in faces for v in f.verts})
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=tuple(c), plane_no=tuple(n))
        faces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
    inside = lambda p: all(float((p - c) @ n) < 0.0 for c, n in cuts)          # noqa: E731
    gone = [f for f in faces if inside(np.array(f.calc_center_median()))]
    bmesh.ops.delete(bm, geom=gone, context="FACES_ONLY")
    E = []
    for e in bm.edges:
        if len(e.link_faces) != 1:
            continue
        p, q = np.array(e.verts[0].co), np.array(e.verts[1].co)
        for j, (c, n) in enumerate(cuts):
            if abs(float((p - c) @ n)) < 1e-5 and abs(float((q - c) @ n)) < 1e-5:
                E.append((p, q, j))
                break
    bm.verts.index_update()
    V2 = np.array([v.co[:] for v in bm.verts], float)
    F2 = [tuple(v.index for v in f.verts) for f in bm.faces]
    M2 = [mats[f.material_index] for f in bm.faces]
    bm.free()
    return V2, F2, M2, len(gone), E


def section_frame(path, normal):
    """At each point of a path (n, 3): the tangent, the outward direction (normal less its part along the tangent) and
    the up direction (their cross, pointing up)."""
    P = np.asarray(path, float)
    T = np.gradient(P, axis=0)
    T = unit(T)
    N = np.asarray(normal, float)
    N = unit(N - (N * T).sum(1)[:, None] * T)
    U = np.cross(T, N)
    U = np.where((U[:, 2] < 0)[:, None], -U, U)
    return T, N, U


def rounded_rect(w, h, r, n=4):
    """A rectangle w x h about its centre, its corners rounded r (n points each), counter-clockwise."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 90.0), (-w / 2 + r, -h / 2 + r, 180.0),
                       (w / 2 - r, -h / 2 + r, 270.0)):
        for k in range(n):
            a = math.radians(a0 + 90.0 * k / (n - 1))
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts)


class Head:
    def __init__(self, L, rig, sk, cfg=None):
        self.L, self.rig, self.sk = L, rig, sk
        self.cfg = cfg or json.load(open(os.path.join(HERE, "decor_1797.json")))
        self.c = self.cfg["head"]
        self.meshes = {}                # name -> (Part, side)
        self.info = {}
        self.bs = rig.bs
        ol = np.array(loft.backbone_outline(L))
        P = np.stack(L.to_m(ol[:, 0], np.zeros(len(ol)), ol[:, 1]), -1)
        self.stem_ol = P[:, [0, 2]]
        self.hw_backbone = (L.k + sk.pl.t0 * sk.pr.pxin) * FT / L.ppf_y
        self.x_rabbet = lambda z: float((np.asarray(L._x_fwd(np.asarray(z, float) / FT * L.ppf_y)) - L.mid_px) /
                                        L.ppf * FT)

    def mesh(self, name, side):
        if name not in self.meshes:
            self.meshes[name] = (Part(), side)
        return self.meshes[name][0]

    # ---- the ship's lines here ---------------------------------------------------------------------------------------
    def stem_x(self, z):
        """The stem's fore face at height z (the backbone outline's foremost crossing)."""
        P = self.stem_ol
        best = -1e9
        for a, b in zip(P, np.roll(P, -1, axis=0)):
            if (a[1] - z) * (b[1] - z) <= 0 and a[1] != b[1]:
                t = (z - a[1]) / (b[1] - a[1])
                best = max(best, a[0] + t * (b[0] - a[0]))
        return best

    def bowsprit_under(self, x):
        """The bowsprit's underside (z) over x on the centreline."""
        b = self.bs
        s = (np.asarray(x, float) - b["H"][0]) / b["ub"][0]
        return b["H"][2] + s * b["ub"][2] - np.vectorize(lambda q: float(b["R"](q)))(s) / b["ub"][0]

    def hull_out(self, x, z):
        """The planked side's outside at (x, z) (starboard) and its outward normal; where x is forward of the rabbet at
        that height, the stem's side (the backbone's half-width) facing +y."""
        L = self.L
        x, z = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))
        X = L.mid_px + x / FT * L.ppf
        Z = z / FT * L.ppf_y
        xr = np.array([self.x_rabbet(q) for q in z])
        P = np.stack([x, np.full(len(x), self.hw_backbone), z], -1)
        N = np.tile(EY, (len(x), 1))
        on = x < xr - 1e-4
        if on.any():
            Ps, Ns = self.sk.surf(X[on], Z[on])
            P[on], N[on] = Ps, Ns
        return P, N

    def knee_half(self, P2):
        """The knee's half-siding at points (x, z): the table's taper, taken down toward the cutwater's fore edge."""
        c = self.c["knee"]
        sd = np.array(c["siding_m"], float)
        P2 = np.asarray(P2, float).reshape(-1, 2)
        h = 0.5 * np.interp(P2[:, 0], sd[:, 0], sd[:, 1])
        d = deck.seg_dist(P2, self.fore_edge, closed=False)
        return h * (c["bevel_keep"] + (1 - c["bevel_keep"]) * smoothstep(d / c["bevel_m"]))

    # ---- the knee of the head ----------------------------------------------------------------------------------------
    def knee(self):
        c = self.c["knee"]
        cw = spline_pts(np.array(c["cutwater_m"], float), 0.05)
        top = spline_pts(np.array(c["top_m"], float), 0.05)
        self.knee_top = top[np.argsort(top[:, 0])]
        self.fore_edge = np.concatenate([cw, top[:3]])
        z_top_aft, z_bot = float(top[-1, 1]), float(cw[0, 1])
        zs = np.linspace(z_top_aft, z_bot, 60)
        aft = np.array([(self.stem_x(z) - c["into_stem_m"], z) for z in zs])
        outline = np.concatenate([aft, cw, top])
        keep = np.concatenate([[True], np.linalg.norm(np.diff(outline, axis=0), axis=1) > 0.01])
        outline = outline[keep]
        g = self.c["gammoning"]["slot_m"]
        holes = [stadium(g["x"][0], g["x"][1], g["z"][0], g["z"][1])]
        bo = self.c["bobstays"]
        r_hole = 0.5 * bo["hole_d_in"] * IN
        self.bobstay_holes = [self.edge_inset(z, bo["hole_inset_m"]) for z in bo["holes_z_m"]]
        holes += [disc(p, r_hole) for p in self.bobstay_holes]
        self.knee_outline, self.knee_holes = outline, holes
        m = self.mesh("HeadKnee", "centre")
        to3d = lambda P2, d: np.stack([P2[:, 0], np.asarray(d, float) * np.ones(len(P2)), P2[:, 1]], -1)
        slab(m, outline, holes, 0.08, to3d, self.knee_half, "HullBlack")
        self.info["knee"] = {"top_aft_z_m": round(z_top_aft, 3), "fore_top_m": np.round(cw[-1], 3).tolist(),
                             "outline_points": len(outline),
                             "bobstay_holes_m": [np.round(h, 3).tolist() for h in self.bobstay_holes]}

    def edge_inset(self, z, d):
        """The point d in from the cutwater's fore edge at height z, square to the edge (x, z)."""
        E = self.fore_edge
        i = int(np.clip(np.searchsorted(E[:, 1], z), 1, len(E) - 1))
        t = unit(E[i] - E[i - 1])
        n = np.array([t[1], -t[0]])                     # square to the edge, forward (the edge runs up the knee)
        if n[0] < 0:
            n = -n
        return np.array([self.cutwater_x(z), z]) - d * n

    # ---- the knightheads and the bow's opening -------------------------------------------------------------------------
    def knightheads(self):
        """Two timbers either side of the bowsprit where it passes over the stem head, from the forecastle deck up past
        the rail; the bow's bulwark between them is opened for the bowsprit (open_bow)."""
        k = self.c["knightheads"]
        m = self.mesh("Knightheads", "stbd")
        x0, x1 = k["x_m"]
        y0 = k["inner_y_m"]
        w = k["sided_m"]
        zb, zt = k["z_m"]
        r = k["round_m"]
        # the top rounded over (a half-round head), the body square
        sec = rounded_rect(x1 - x0, w, 0.03, 3) + np.array([0.5 * (x0 + x1), y0 + 0.5 * w])
        rings = []
        for z in np.concatenate([[zb], np.linspace(zt - r, zt, 6)]):
            f = 1.0 if z <= zt - r else math.sqrt(max(1e-6, 1.0 - ((z - (zt - r)) / r) ** 2))
            cx, cy = 0.5 * (x0 + x1), y0 + 0.5 * w
            ring = np.column_stack([cx + (sec[:, 0] - cx) * max(f, 0.25), cy + (sec[:, 1] - cy) * max(f, 0.25),
                                    np.full(len(sec), z)])
            rings.append(ring)
        deck.solid(m, rings, "HullBlack")
        self.info["knightheads"] = {"x_m": [x0, x1], "inner_y_m": y0, "top_z_m": zt}

    # ---- the bowsprit's passage through the bow ----------------------------------------------------------------------
    def saddle(self):
        """The bowsprit's bed as planes: the lower half of a polygon of `facets` sides about the spar's axis, each facet
        clear_m off the spar at its middle, the spar's taper followed (its radius taken as a straight line along it
        over the bed, raised by the most the line falls short). Returns H (the spar's heel), W (up, square to the spar)
        and the planes [(n, A)]: n.(p - H) = A on a facet, n.(p - H) < A on the spar's side of it."""
        b, c, k = self.bs, self.c["bed"], self.c["knightheads"]
        H, ub = np.asarray(b["H"], float), np.asarray(b["ub"], float)
        W = np.cross(ub, EY)                                    # up, square to the spar, in its plane of symmetry
        x1 = self.stem_x(float(self.bowsprit_under(k["x_m"][1])))
        s = np.linspace((k["x_m"][0] - 0.3 - H[0]) / ub[0], (x1 + 0.3 - H[0]) / ub[0], 41)
        R = np.array([float(b["R"](q)) for q in s])
        slope, r0 = np.polyfit(s, R, 1)
        r0 += float(np.max(R - (r0 + slope * s))) + c["clear_m"]
        n = c["facets"]
        step = 2.0 * math.pi / n
        K = int(math.ceil(n / 4.0)) - 1                        # the facets wholly under the spar's middle
        planes = []
        for j in range(-K, K + 1):
            phi = -0.5 * math.pi + j * step
            d = math.cos(phi) * EY + math.sin(phi) * W
            planes.append((d - slope * ub, r0))                # d.(p - H) = r0 + slope * s, s = ub.(p - H)
        return H, W, planes

    @staticmethod
    def plane_z(plane, H, x, y):
        """z on a plane (n, A) (n.(p - H) = A) over (x, y)."""
        n, A = plane
        return H[2] + (A - n[0] * (x - H[0]) - n[1] * (y - H[1])) / n[2]

    def open_bow(self, parts):
        """Open the bow between the knightheads for the bowsprit and bed it: the parts named in opening_parts (the
        bow's planking, bulwark faces, rail cap and the bow's inside) lose what lies in the passage, cut exactly on its
        planes (cut_away): between the knightheads' inner faces, forward of their after faces, over the bed's top (the
        saddle's facets). Their cut edges so lie on the knightheads' inner faces and the bed's top, and the bed
        (BowspritBed, bed()) is built to take them: a check fails the build if any cut edge is left open.
        parts: skin.Skin.parts()'s dict, changed in place."""
        k = self.c["knightheads"]
        y0, (kx0, kx1), (kz0, kz1) = k["inner_y_m"], k["x_m"], k["z_m"]
        H, W, facets = self.saddle()
        # the passage: (p - c).n < 0 for every cut (c, n): the knightheads' after faces, their inner faces, the facets
        cuts = [(np.array([kx0, 0.0, 0.0]), -EX), (np.array([0.0, y0, 0.0]), EY), (np.array([0.0, -y0, 0.0]), -EY)]
        cuts += [(H + n * A / (n @ n), n / np.linalg.norm(n)) for n, A in facets]
        zlow = min(float(self.bowsprit_under(kx0)), float(self.bowsprit_under(kx1))) - 0.3
        near = lambda p: p[0] > kx0 - 0.3 and abs(p[1]) < y0 + 0.3 and p[2] > zlow      # noqa: E731
        gone, edges = {}, {}
        for name in k["opening_parts"]:
            V, F, M, side = parts[name]
            V, F, M, n0, E = cut_away(V, F, M, cuts, near)
            parts[name] = compact(V, F, M) + (side,)
            gone[name], edges[name] = n0, E
        bed = self.bed(H, W, facets, edges)
        # every cut edge lies on a knighthead's inner face or on the bed's top
        open_ = []
        for name, E in edges.items():
            for p, q, j in E:
                m = 0.5 * (p + q)
                if j == 0:
                    ok = False                                              # the passage's after face: nothing there
                elif j in (1, 2):
                    ok = kx0 - 1e-4 <= m[0] <= kx1 + 1e-4 and kz0 <= m[2] <= kz1
                else:
                    ok = bed["covers"](m) or (abs(m[1]) > bed["half_m"][0] and kx0 <= m[0] <= kx1 + 1e-4)
                if not ok:
                    open_.append((name, np.round(m, 3).tolist()))
        if open_:
            raise ValueError(f"the bow's opening leaves {len(open_)} cut edges open, e.g. {open_[:4]}")
        self.info["opening"] = {"faces_gone": gone, "cut_edges": {n: len(E) for n, E in edges.items()},
                                "inner_y_m": y0}

    def bed(self, H, W, facets, edges):
        """The bowsprit's bed (BowspritBed, built whole): a timber under the spar between the knightheads and along
        the stem head, its top the saddle's facets (the spar lies clear_m over it), its bottom depth_m under their
        lowest line (square to the spar). Between the knightheads it is as wide as their inner faces less side_m, from
        lap_m inside the bow's inside (measured on the cut edges of the parts other than the planking) to lap_m outside
        the planking (on the planking's cut edges: a fore face slanting in to the stem's side); along the stem head it
        is the stem's siding less side_m, to fore_m short of the stem's fore face. Returns its plan for the check."""
        c, k = self.c["bed"], self.c["knightheads"]
        lap, side = c["lap_m"], c["side_m"]
        w_max, w_stem = k["inner_y_m"] - side, self.hw_backbone - side
        on_bed = lambda name: [(0.5 * (p + q)) for p, q, j in edges[name] if j >= 3]     # noqa: E731
        inner = [m for name in edges if name != "Skin" for m in on_bed(name)]
        outer = [m for m in on_bed("Skin") if w_stem < abs(m[1]) <= w_max + 1e-4]
        if not inner or not outer:
            raise ValueError("the bow's opening: no cut edges on the bed's top to fit it to")
        xa = min(float(m[0]) for m in inner) - lap
        # the fore face: from (xs0, w_max) slanting forward to (xs1, w_stem), lap_m outside every planking cut edge
        Q = np.array([(abs(m[1]), m[0] + lap) for m in outer])
        lo, hi = Q[:, 0] <= w_stem + 0.03, Q[:, 0] >= w_max - 0.03
        xs1 = float(Q[lo, 1].max()) if lo.any() else float(Q[:, 1].max())
        xs0 = float(Q[hi, 1].max()) if hi.any() else xs1
        line = lambda y: xs0 + (xs1 - xs0) * (w_max - y) / (w_max - w_stem)          # noqa: E731
        shift = max(0.0, float(np.max(Q[:, 1] - line(Q[:, 0]))))
        xs0, xs1 = xs0 + shift, xs1 + shift
        x_e = self.stem_x(float(self.bowsprit_under(xs1))) - c["fore_m"]
        # the bottom: W.(p - H) = -B, depth_m under the facets' lowest line at the fore end (their inradius is r0 +
        # slope * s, and slope = -n.ub)
        n_mid, r0 = facets[len(facets) // 2]
        ub = np.asarray(self.bs["ub"], float)
        B = r0 - float(n_mid @ ub) * (x_e - H[0]) / ub[0] + c["depth_m"]
        zb = lambda x: H[2] + (-B - W[0] * (x - H[0])) / W[2]                       # noqa: E731
        ztop = lambda x, y: max(self.plane_z(f, H, x, y) for f in facets)          # noqa: E731

        def crease(x, i):
            (n1, A1), (n2, A2) = facets[i], facets[i + 1]
            Mx = np.array([[n1[1], n1[2]], [n2[1], n2[2]]])
            r = np.array([A1 - n1[0] * (x - H[0]), A2 - n2[0] * (x - H[0])])
            yz = np.linalg.solve(Mx, r)
            return yz[0] + H[1], yz[1] + H[2]

        def half(x):
            if x <= xs0:
                return w_max
            if x >= xs1:
                return w_stem
            return w_max + (w_stem - w_max) * (x - xs0) / (xs1 - xs0)

        # stations: the ends, the fore face's corners and where it passes each crease (so every face stays flat)
        st = [xa, xs0]
        for i in range(len(facets) - 1):
            yc = lambda x: abs(crease(x, i)[0])                                    # noqa: E731
            if (yc(xs0) - half(xs0)) * (yc(xs1) - half(xs1)) < 0:
                a, b2 = xs0, xs1
                for _ in range(60):
                    mid = 0.5 * (a + b2)
                    if (yc(a) - half(a)) * (yc(mid) - half(mid)) <= 0:
                        b2 = mid
                    else:
                        a = mid
                st.append(0.5 * (a + b2))
        st = sorted(set(np.round(st + [xs1, x_e], 6).tolist()))
        secs = []
        for x in st:
            w = half(x)
            tr, tl = (x, w, ztop(x, w)), (x, -w, ztop(x, -w))
            pts = [(x, -w, zb(x)), (x, w, zb(x)), tr]
            for i in range(len(facets) - 2, -1, -1):
                y, z = crease(x, i)
                pts.append(tr if y >= w else tl if y <= -w else (x, y, z))
            pts.append(tl)
            secs.append(np.array(pts, float))
        m = len(secs[0])
        V = np.concatenate(secs)
        F = [(i * m + j, i * m + (j + 1) % m, (i + 1) * m + (j + 1) % m, (i + 1) * m + j)
             for i in range(len(secs) - 1) for j in range(m)]
        for end, face_dir in ((0, -1.0), (len(secs) - 1, 1.0)):
            S = secs[end]
            keep = [j for j in range(m) if j == 0 or np.linalg.norm(S[j] - S[j - 1]) > 1e-9]
            keep = [j for j in keep if not (j == keep[-1] and np.linalg.norm(S[j] - S[keep[0]]) < 1e-9)]
            tri = loft.ear_clip(S[keep][:, 1:])
            for t in tri:
                f = tuple(end * m + keep[q] for q in t)
                F.append(f if face_dir > 0 else f[::-1])
        V, F, M = compact(V, F, ["HullBlack"] * len(F))
        Va = np.asarray(V, float)
        vol = sum(float(Va[f[0]] @ np.cross(Va[f[q]], Va[f[q + 1]])) for f in F for q in range(1, len(f) - 1)) / 6.0
        if vol <= 0.0:
            raise ValueError(f"the bowsprit's bed turned inside out (volume {vol:.4f})")
        self.mesh("BowspritBed", "centre").add(V, F, M)

        def covers(p):
            y = abs(p[1])
            if y <= w_stem + 1e-4:
                return xa - 1e-4 <= p[0] <= x_e + 1e-4
            fore = xs0 + (xs1 - xs0) * (w_max - y) / (w_max - w_stem)
            return y <= w_max + 1e-4 and xa - 1e-4 <= p[0] <= fore + 1e-4

        self.info["bed"] = {"x_m": [round(xa, 3), round(xs0, 3), round(xs1, 3), round(x_e, 3)],
                            "half_width_m": [round(w_max, 3), round(w_stem, 3)], "volume_m3": round(vol, 4),
                            "spar_clear_m": c["clear_m"], "facets": c["facets"]}
        return {"covers": covers, "half_m": (w_max, w_stem)}

    # ---- what lies on the knee and the bow -----------------------------------------------------------------------
    def side_at(self, x, z):
        """The outside of what a cheek or board lies on at (x, z) (starboard): the planked bow, the stem's side, or the
        knee's side forward of the stem; and its outward normal."""
        x, z = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))
        P, N = self.hull_out(x, z)
        sx = np.array([self.stem_x(q) for q in z])
        fwd = x > sx
        if fwd.any():
            P[fwd, 1] = self.knee_half(np.stack([x[fwd], z[fwd]], -1))
            N[fwd] = EY
        return P, N

    def solid_side(self, x, z):
        """How far out (y, starboard) the solid reaches at (x, z): the planking, the stem's side, or the knee's side up
        to the knee's top; nothing over the knee forward of the stem."""
        x, z = np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(z, float))
        y = self.side_at(x, z)[0][:, 1]
        sx = np.array([self.stem_x(q) for q in z])
        over = (x > sx) & (z > np.interp(x, self.knee_top[:, 0], self.knee_top[:, 1]))
        return np.where(over, 0.0, y)

    def cutwater_x(self, z):
        """The cutwater's fore edge (x) at height z."""
        E = self.fore_edge
        return float(np.interp(z, E[:, 1], E[:, 0]))

    @staticmethod
    def smooth(a, k, ends="hold"):
        """a moving average over 2k+1 samples along the first axis; at the ends the samples are held (repeated), or
        (ends 'line') carried on the way the last few run (an odd reflection), which keeps a straight run straight to
        its end"""
        a = np.asarray(a, float)
        if k < 1:
            return a
        if ends == "line":
            pad = np.concatenate([2 * a[:1] - a[k:0:-1], a, 2 * a[-1:] - a[-2:-k - 2:-1]])
        else:
            pad = np.concatenate([np.repeat(a[:1], k, 0), a, np.repeat(a[-1:], k, 0)])
        ker = np.ones(2 * k + 1) / (2 * k + 1)
        if a.ndim == 1:
            return np.convolve(pad, ker, mode="valid")
        return np.stack([np.convolve(pad[:, j], ker, mode="valid") for j in range(a.shape[1])], -1)

    def cheeks(self):
        """The upper and lower cheeks: moulded knees along the traced bands, lying on the bow, the stem and the knee,
        their ends tapering into the side, the fore end short of the cutwater's edge (every point of it fore_clear_m
        aft of the edge at its own height). The outer face follows what the cheek lies on, smoothed over the rabbet's
        turn and over the step where the knee (sided less than the stem) comes out of the stem; the back is fayed to
        it: its top, middle and bottom let in embed_m wherever the smoothed line would leave them standing off."""
        c = self.c["cheeks"]
        m = self.mesh("HeadCheeks", "stbd")
        d, p, e = c["deep_m"], c["proud_m"], c["embed_m"]
        fe = self.fore_edge
        self.cheek_paths = {}
        for key in ("lower_m", "upper_m"):
            E = spline_pts(np.array(c[key], float), 0.03)
            E = E[np.array([q[0] <= self.cutwater_x(q[1]) - 0.08 for q in E])]
            for _ in range(60):
                secs, path, Nn, U, f = self.cheek_sections(E, d, p, e)
                S = np.array(secs)
                over = np.nonzero((S[:, :, 0] > np.interp(S[:, :, 2], fe[:, 1], fe[:, 0]) - c["fore_clear_m"]).any(1))[0]
                if not len(over):
                    break
                E = E[:int(over.min())]
            else:
                raise ValueError(f"the {key} cheek can't be kept {c['fore_clear_m']} m short of the cutwater")
            V, F, M = carve.tube(secs, "HullBlack")
            m.add(V, F, M)
            self.cheek_paths[key] = (path, Nn, U, f)

    def cheek_sections(self, E, d, p, e):
        """a cheek's sections along its middle line E (x, z): (sections, path, out, up, taper)"""
        P, N = self.side_at(E[:, 0], E[:, 1])
        y = self.smooth(P[:, 1], 5, ends="line") - e
        N = unit(self.smooth(N, 5))
        path = np.stack([E[:, 0], y, E[:, 1]], -1)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        # each end tapers: the aft end into the bow over 0.35 m, the fore end over 0.5 m
        f = np.minimum(0.35 + 0.65 * smoothstep(s / 0.35), 0.45 + 0.55 * smoothstep((s[-1] - s) / 0.5))
        T, Nn, U = section_frame(path, N)
        secs = []
        for k in range(len(path)):
            pw = e + (p - e) * f[k]
            hd = 0.5 * d * (0.7 + 0.3 * f[k])
            prof = np.array([(0.0, -hd), (0.55 * pw, -hd), (0.85 * pw, -0.8 * hd), (pw, -0.35 * hd), (pw, 0.35 * hd),
                             (0.85 * pw, 0.8 * hd), (0.55 * pw, hd), (0.0, hd), (0.0, 0.0)])
            secs.append(path[k] + prof[:, :1] * Nn[k] + prof[:, 1:2] * U[k])
        S = np.array(secs)
        back = [0, 7, 8]
        Q = S[:, back].reshape(-1, 3)
        ys = self.side_at(Q[:, 0], Q[:, 2])[0][:, 1].reshape(len(S), len(back))
        S[:, back, 1] = np.minimum(S[:, back, 1], ys - e)
        return list(S), path, Nn, U, f

    def cheek_edge(self, key, top):
        """A cheek's top (or bottom) edge in elevation: (x, z) along it."""
        path, N, U, f = self.cheek_paths[key]
        hd = 0.5 * self.c["cheeks"]["deep_m"] * (0.7 + 0.3 * f)
        Q = path + (hd if top else -hd)[:, None] * U
        return Q[:, [0, 2]]

    def trailboards(self):
        """The board between the cheeks on the knee's side, from just before the stem forward to short of the
        cutwater's edge (the bobstay holes are forward of it), its edges tucked under the cheeks; carved (carving())."""
        c = self.c["trailboard"]
        m = self.mesh("Trailboards", "stbd")
        lo = self.cheek_edge("lower_m", True)
        up = self.cheek_edge("upper_m", False)
        xa = self.stem_x(3.0) + c["x_aft_of_stem_m"]
        fm = np.array(c["front_margin_m"], float)
        margin = lambda z: float(np.interp(z, fm[:, 0], fm[:, 1]))                    # noqa: E731
        front = lambda q: q[:, 0] <= np.array([self.cutwater_x(z) - margin(z) for z in q[:, 1]])  # noqa: E731
        lo = lo[(lo[:, 0] >= xa) & front(lo)] + np.array([0.0, -c["tuck_m"]])
        up = up[(up[:, 0] >= xa) & front(up)] + np.array([0.0, c["tuck_m"]])
        # forward: square across from the lower edge's end to the upper's, along the margin off the cutwater's edge
        za, zb = float(lo[-1, 1]), float(up[-1, 1])
        zs = np.linspace(za, zb, 12)[1:-1]
        fr = np.array([(self.cutwater_x(z) - margin(z), z) for z in zs])
        outline = np.concatenate([lo, fr, up[::-1]])
        outline = outline[np.concatenate([[True], np.linalg.norm(np.diff(outline, axis=0), axis=1) > 0.01])]
        g, pr = c["gap_m"], c["proud_m"]
        self.trail_face = lambda P2: self.side_at(P2[:, 0], P2[:, 1])[0][:, 1] + g + pr      # noqa: E731

        def to3d(P2, dd):
            y0 = self.side_at(P2[:, 0], P2[:, 1])[0][:, 1]
            return np.stack([P2[:, 0], y0 + g + 0.5 * pr + np.asarray(dd, float) * np.ones(len(P2)), P2[:, 1]], -1)
        slab(m, outline, [], 0.06, to3d, lambda P2: np.full(len(P2), 0.5 * pr), "HullBlack")
        self.trail_outline = outline
        # the carving's band: the board's face between the cheeks' edges (less a margin), forward of its after end
        k = c["carving"]["inset_m"]
        self.trail_band = (lo[lo[:, 0] >= xa + k] + np.array([0.0, c["tuck_m"] + k]),
                           up[up[:, 0] >= xa + k] - np.array([0.0, c["tuck_m"] + k]))
        self.info["trailboard"] = {"x_m": [round(float(outline[:, 0].min()), 3), round(float(outline[:, 0].max()), 3)]}

    def carving(self):
        """The trailboards' carving: a running scroll in gilt relief on each board's face (carve.py)."""
        c = self.c["trailboard"]["carving"]
        band = carve.Band(*self.trail_band)
        design = carve.running_scroll(band.length, band.half_min, c)
        m = self.mesh("TrailCarving", "stbd")

        def place(XZ):
            XZ = np.asarray(XZ, float)
            e = 0.01
            y = self.trail_face(XZ)
            dx = (self.trail_face(XZ + [e, 0.0]) - self.trail_face(XZ - [e, 0.0])) / (2 * e)
            dz = (self.trail_face(XZ + [0.0, e]) - self.trail_face(XZ - [0.0, e])) / (2 * e)
            P = np.stack([XZ[:, 0], y, XZ[:, 1]], -1)
            return P, unit(np.stack([-dx, np.ones(len(XZ)), -dz], -1))
        tris = carve.relief(m, design, band.to_xz, place, c["mat"])
        self.info["carving"] = {"band_m": [round(band.length, 3), round(2 * band.half_min, 3)],
                                "strokes": len(design["strokes"]), "leaves": len(design["leaves"]),
                                "triangles_a_side": tris}

    def rail_path(self, elev, plan, half_t, fay, land, step=0.04):
        """A head rail's centre line: its elevation (x, z) and plan (x, y) curves, the plan held outside what it passes
        (half its thickness off the planking, the stem or the knee); its last fay metres (along it) lie on the bow, fayed to
        the planking (land_embed_m into it), and it comes in to the bow over the land metres before that; and its outward
        (plan) normals."""
        c = self.c["rails"]
        E = spline_pts(np.array(elev, float), step)
        Pl = np.array(plan, float)
        Pl = Pl[np.argsort(Pl[:, 0])]
        y = CubicSpline(Pl[:, 0], Pl[:, 1])(E[:, 0])
        hold = self.solid_side(E[:, 0], E[:, 1]) + half_t
        aft = int(np.argmin(E[:, 0]))
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(E, axis=0), axis=1))])
        w = smoothstep((np.abs(s - s[aft]) - fay) / land)
        floor = hold - c["land_embed_m"] * (1.0 - w)
        y = floor + np.maximum(y - floor, 0.0) * w
        y = np.maximum(self.smooth(y, 3), floor)
        path = np.stack([E[:, 0], y, E[:, 1]], -1)
        T = unit(np.gradient(path, axis=0))
        out = unit(np.stack([-T[:, 1], T[:, 0], np.zeros(len(T))], -1) * np.sign(-T[:, 0])[:, None])
        out = np.where((out[:, 1] < 0)[:, None], -out, out)
        return path, out

    def rails(self):
        """The main rail (from the figure's back down and aft, then up to the bow under the cathead) and the lower rail
        (the gratings' edge), moulded, each landing on the bow at its after end."""
        c = self.c["rails"]
        m = self.mesh("HeadRails", "stbd")
        self.rail = {}
        for i, (key, sec, plan) in enumerate((("main", c["main_section_m"], c["main_plan_m"]),
                                              ("lower", c["lower_section_m"], None))):
            t, dpt = sec
            if plan is None:
                pm = np.array(c["main_plan_m"], float)
                plan = np.column_stack([pm[:, 0], pm[:, 1] * c["lower_plan_scale"]])
            path, out = self.rail_path(c[key + "_m"], plan, 0.5 * t, c["fay_m"][i], c["land_m"][i])
            prof = np.array([(-0.5 * t, -0.5 * dpt), (0.5 * t, -0.5 * dpt), (0.5 * t, 0.25 * dpt), (0.42 * t, 0.42 * dpt),
                             (0.2 * t, 0.5 * dpt), (-0.2 * t, 0.5 * dpt), (-0.42 * t, 0.42 * dpt),
                             (-0.5 * t, 0.25 * dpt)])
            T, N, U = section_frame(path, out)
            secs = [p + prof[:, :1] * n + prof[:, 1:2] * u for p, n, u in zip(path, N, U)]
            V, F, M = carve.tube(secs, "HullBlack")
            m.add(V, F, M)
            self.rail[key] = (path, N, U, t, dpt)
            aft = path[:, 0] < self.stem_x(float(path[:, 2].min())) - 0.2
            if aft.any():
                gap = path[aft, 1] - 0.5 * t - self.hull_out(path[aft, 0], path[aft, 2])[0][:, 1]
                self.info.setdefault("rails", {})[key] = {
                    "aft_end_m": np.round(path[np.argmin(path[:, 0])], 3).tolist(),
                    "off_bow_m": [round(float(gap.min()), 3), round(float(gap.max()), 3)],
                    "off_bow_at_x": np.round(np.stack([path[aft, 0], gap], -1)[::6], 2).tolist()}

    def rail_at(self, key, x):
        path = self.rail[key][0]
        o = np.argsort(path[:, 0])
        return np.array([np.interp(x, path[o, 0], path[o, k]) for k in range(3)])

    def timbers(self):
        """The head timbers: from the upper cheek's top up through the lower rail to the main rail, leaning out with
        the rails."""
        c = self.c["timbers"]
        m = self.mesh("HeadTimbers", "stbd")
        w, t = c["section_m"]
        top_edge = self.cheek_edge("upper_m", True)
        path_u = self.cheek_paths["upper_m"][0]
        for xt in c["x_m"]:
            zb = float(np.interp(xt, top_edge[:, 0], top_edge[:, 1])) - 0.03
            yb = float(np.interp(xt, path_u[:, 0], path_u[:, 1])) + 0.5 * self.c["cheeks"]["proud_m"]
            top = self.rail_at("main", xt)
            top[2] -= 0.02
            lr = self.rail_at("lower", xt)
            # up from the cheek, out through the lower rail (which is fastened to it) to the main rail's underside
            cs = CubicSpline([zb, lr[2], top[2]], [yb, lr[1], top[1]], bc_type="natural")
            zz = np.linspace(zb, top[2], 16)
            path = np.stack([np.full(len(zz), xt), cs(zz), zz], -1)
            T = unit(np.gradient(path, axis=0))
            side = unit(np.cross(T, np.tile(EX, (len(T), 1))))
            side = np.where((side[:, 1] < 0)[:, None], -side, side)
            secs = []
            for p_, s_ in zip(path, side):
                fw = EX - (EX @ s_) * s_
                fw = fw / np.linalg.norm(fw)
                secs.append([p_ - 0.5 * w * s_ - 0.5 * t * fw, p_ + 0.5 * w * s_ - 0.5 * t * fw,
                             p_ + 0.5 * w * s_ + 0.5 * t * fw, p_ - 0.5 * w * s_ + 0.5 * t * fw])
            V, F, M = carve.tube(secs, "HullBlack")
            m.add(V, F, M)

    def gratings(self):
        """A grating each side of the knee: battens and ledges halved together (a flush top with square openings), from
        the knee's side (aft of the stem's fore face, the stem's) out to the lower rail, let into both (let_in_m), its
        top top_under_rail_m under the rail's top. The openings are laid out at their true size (hole_in between bar_in
        battens) and kept where a whole one fits a batten's width inside the edges, so the grating is solid along the
        rail where the rail's line cuts across the battens."""
        c = self.c["gratings"]
        m = self.mesh("HeadGratings", "stbd")
        x0, x1 = c["x_m"]
        bar, hole, dp = c["bar_in"] * IN, c["hole_in"] * IN, c["deep_in"] * IN
        lk, lr = c["let_in_m"]
        path, N, U, t, dpt = self.rail["lower"]
        o = np.argsort(path[:, 0])
        zm = lambda x: np.interp(x, path[o, 0], path[o, 2]) + 0.5 * dpt - c["top_under_rail_m"] - 0.5 * dp  # noqa: E731
        yo = lambda x: np.interp(x, path[o, 0], path[o, 1]) - 0.5 * t + lr                                 # noqa: E731
        y0 = lambda x: self.knee_half(np.stack([x, zm(x)], -1)) - lk          # noqa: E731  (v = 0: in the knee's side)
        # across (v) from the knee's side: aft of the stem's fore face its inner edge steps out onto the stem's side
        sx = self.stem_x(float(zm(np.array([28.0]))[0]))
        xs = np.unique(np.concatenate([np.linspace(x0, x1, 61), [sx - 0.002, sx + 0.002]]))
        xs = xs[(xs >= x0) & (xs <= x1)]
        v_in = np.maximum(self.side_at(xs, zm(xs))[0][:, 1] - lk - y0(xs), 0.0)
        v_in[xs > sx] = 0.0
        v_out = yo(xs) - y0(xs)
        outline = np.concatenate([np.stack([xs, v_in], -1), np.stack([xs[::-1], v_out[::-1]], -1)])
        us, ubar = deck.bars_and_gaps(x0, x1, bar, hole)
        vs, vbar = deck.bars_and_gaps(0.0, float(v_out.max()), bar, hole)
        holes = []
        for i in range(len(us) - 1):
            if ubar[i]:
                continue
            a, b = us[i], us[i + 1]
            sel = (xs >= a - 0.002) & (xs <= b + 0.002)
            lo = float(v_in[sel].max()) + bar
            hi = float(v_out[sel].min()) - bar
            for j in range(len(vs) - 1):
                if not vbar[j] and vs[j] >= lo and vs[j + 1] <= hi:
                    holes.append(np.array([(a, vs[j]), (b, vs[j]), (b, vs[j + 1]), (a, vs[j + 1])]))

        def to3d(P2, d):
            x = P2[:, 0]
            return np.stack([x, y0(x) + P2[:, 1], zm(x) + np.asarray(d, float) * np.ones(len(P2))], -1)
        slab(m, outline, holes, 1.0, to3d, lambda P2: np.full(len(P2), 0.5 * dp), "Oak")
        self.info["gratings"] = {"openings_a_side": len(holes), "x_m": [x0, x1],
                                 "top_z_m": [round(float(zm(np.array([x0]))[0] + 0.5 * dp), 3),
                                             round(float(zm(np.array([x1]))[0] + 0.5 * dp), 3)]}

    # ---- the figure ----------------------------------------------------------------------------------------------
    def figure_frame(self):
        """The figure's frame: origin the middle of her footprint, her up leaning forward (lean_deg) about the ship's Y."""
        f = self.cfg["figure"]
        th = math.radians(f["lean_deg"])
        up = np.array([math.sin(th), 0.0, math.cos(th)])
        fwd = np.array([math.cos(th), 0.0, -math.sin(th)])
        return np.array(f["feet_m"], float), fwd, EY.copy(), up

    def figure(self):
        """Our figure (make_figure.py's mesh: 1 m tall, facing +X, her cut footprint at z 0), scaled, the middle of her
        footprint on feet_m, leaned forward and stood on her console."""
        f = self.cfg["figure"]
        d = np.load(os.path.join(HERE, f["mesh"]))
        box = d["box"]
        V = box[0] + d["V"].astype(np.float64) / 65535.0 * (box[1] - box[0])
        T = d["T"].astype(np.int64)
        feet = V[V[:, 2] < 0.02]
        lo, hi = feet[:, :2].min(0), feet[:, :2].max(0)
        V = (V - np.array([0.5 * (lo[0] + hi[0]), 0.5 * (lo[1] + hi[1]), 0.0])) * f["height_m"]
        self.footprint = 0.5 * (hi - lo) * f["height_m"]               # half her footprint along fwd and across
        o, fwd, side, up = self.figure_frame()
        W = o + V[:, :1] * fwd + V[:, 1:2] * side + V[:, 2:3] * up
        m = self.mesh("Figurehead", "centre")
        m.add(W, [tuple(t) for t in T], "FigurePaint")
        self.figure_V = W
        self.info["figure"] = {"triangles": int(len(T)), "top_m": np.round(W[np.argmax(W[:, 2])], 3).tolist(),
                               "foremost_m": np.round(W[np.argmax(W[:, 0])], 3).tolist(),
                               "footprint_half_m": np.round(self.footprint, 3).tolist(),
                               "bowsprit_clear_m": round(float(np.min(self.bowsprit_under(W[:, 0]) - W[:, 2])), 3)}

    def figure_base(self):
        """The console she stands on: in profile a block on the knee's top, curled aft under her heels and a little
        forward at its foot, its top square to her and over her footprint; it flares from a lip over the knee's siding
        at its foot to its top's breadth. Painted with her; on each side a gilt volute forward of where the main rail
        lands on the after curl and a small one low forward, and a gilt bead round the top."""
        b = self.cfg["figure"]["base"]
        o, fwd, side, up = self.figure_frame()
        th = math.radians(self.cfg["figure"]["lean_deg"])
        A, B = 0.5 * b["top_m"][0], 0.5 * b["top_m"][1]
        if A < self.footprint[0] or B < self.footprint[1]:
            raise ValueError(f"the console's top {b['top_m']} does not cover her footprint {2 * self.footprint}")
        o2 = o + b["lift_m"] * up                                      # her cut rim a little into the console's top
        tf = np.array([o2[0] + A * math.cos(th), o2[2] - A * math.sin(th)])
        tb = np.array([o2[0] - A * math.cos(th), o2[2] + A * math.sin(th)])
        e = b["embed_m"]
        zk = lambda x: np.interp(x, self.knee_top[:, 0], self.knee_top[:, 1])        # noqa: E731
        x_fb, x_ft = b["foot_x_m"]
        bot = np.array([(x, float(zk(x)) - e) for x in np.linspace(x_fb, x_ft, 16)])
        # forward: from the foot's fore end up to the top's, bulging a little forward
        front = carve.bezier(bot[-1], [0.4, 1.0], tf, [-0.2, 1.0], 10)
        # aft: the curl, from the top's after edge round aft and down to the foot
        k = b["curl_aft_m"] * 1.33
        P0, P1 = tb, bot[0]
        t = np.linspace(0.0, 1.0, 22)[:, None]
        C0, C1 = P0 + np.array([-k, 0.02]), P1 + np.array([-k, 0.06])
        back = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * C0 + 3 * (1 - t) * t ** 2 * C1 + t ** 3 * P1
        top = np.linspace(tf, tb, 12)
        outline = np.concatenate([bot, front[1:], top[1:], back[1:-1]])
        outline = outline[np.concatenate([[True], np.linalg.norm(np.diff(outline, axis=0), axis=1) > 0.008])]
        w0, p = b["foot_half_m"], b["flare_power"]
        z_top = lambda x: o2[2] - (x - o2[0]) * math.tan(th)                       # noqa: E731

        def half(P2):
            P2 = np.asarray(P2, float).reshape(-1, 2)
            zb = zk(P2[:, 0]) - e
            v = np.clip((P2[:, 1] - zb) / np.maximum(z_top(P2[:, 0]) - zb, 0.05), 0.0, 1.0)
            return w0 + (B - w0) * v ** p
        m = self.mesh("FigureBase", "centre")
        to3d = lambda P2, d: np.stack([P2[:, 0], np.asarray(d, float) * np.ones(len(P2)), P2[:, 1]], -1)  # noqa
        slab(m, outline, [], 0.035, to3d, half, "FigurePaint")
        self.base_outline, self.base_half = outline, half
        g = self.mesh("FigureBaseGilt", "centre")
        # the bead round the top: a half-round on the top's edge
        rb = b["bead_r_m"]
        ring = rounded_rect(2 * A, 2 * B, 0.05, 5)
        loop = np.array([o2 + a_ * fwd + c_ * side for a_, c_ in ring])
        kk = np.arange(8) * 2 * math.pi / 8
        secs = []
        for i in range(len(loop)):
            t_ = unit(loop[(i + 1) % len(loop)] - loop[i - 1])
            u1 = unit(np.cross(t_, up))
            u2 = np.cross(u1, t_)
            secs.append(loop[i] + rb * (np.cos(kk)[:, None] * u1 + np.sin(kk)[:, None] * u2))
        V, F, M = sweep(secs + secs[:1], "Gilt", closed=True, caps=False)
        g.add(V, F, M)

        # the volutes: spirals laid on each flared side
        def place(XZ, sgn):
            XZ = np.asarray(XZ, float)
            h = 0.004
            y = half(XZ)
            dx = (half(XZ + [h, 0.0]) - half(XZ - [h, 0.0])) / (2 * h)
            dz = (half(XZ + [0.0, h]) - half(XZ - [0.0, h])) / (2 * h)
            P = np.stack([XZ[:, 0], sgn * y, XZ[:, 1]], -1)
            return P, unit(np.stack([-dx, np.full(len(XZ), sgn), -dz], -1))
        vo, fv = b["volute"], b["front_volute"]
        mid = 0.5 * (tb + bot[0]) + np.array([vo["fwd_m"], vo["up_m"]])
        R = vo["r_m"]
        spir = carve.spiral(mid, R, vo["end"] * R, vo["turns"], math.pi / 2, 1.0)
        cf = np.array([x_ft - fv["aft_m"], float(zk(x_ft - fv["aft_m"])) - e + fv["up_m"]])
        spf = carve.spiral(cf, fv["r_m"], fv["end"] * fv["r_m"], fv["turns"], math.pi / 2, -1.0)
        r0, r1 = vo["rope_m"]
        design = {"strokes": [(spir, np.linspace(r0, r1, len(spir))), (spf, np.linspace(0.8 * r0, r1, len(spf)))],
                  "leaves": [], "berries": [(spir[-1], 1.5 * r1), (spf[-1], 1.3 * r1)]}
        ident = lambda P: np.asarray(P, float)                                    # noqa: E731
        for sgn in (1.0, -1.0):
            carve.relief(g, design, ident, lambda XZ, s_=sgn: place(XZ, s_), "Gilt")
        self.info["figure_base"] = {"top_front_m": np.round(tf, 3).tolist(), "top_back_m": np.round(tb, 3).tolist(),
                                    "foot_x_m": [x_fb, x_ft]}

    # ---- all of it ---------------------------------------------------------------------------------------------------
    def build(self):
        self.knee()
        self.knightheads()
        self.cheeks()
        self.trailboards()
        self.carving()
        self.rails()
        self.timbers()
        self.gratings()
        self.figure()
        self.figure_base()
        return self

    def parts(self):
        """name -> (V, F, M, side): 'stbd' parts are the starboard half (mirror them for port), 'centre' parts whole."""
        out = {}
        for name, (mesh, side) in self.meshes.items():
            V, F, M = mesh.arrays()
            out[name] = compact(V, F, M) + (side,)
        return out
