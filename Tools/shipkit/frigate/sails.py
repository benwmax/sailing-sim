"""The frigate's sails (docs/shipkit-5): twenty sails of plain sail, each in three states.

    from sails import Sails;  sv = Sails(rig, st).build();  sv.objects()

Square sails (the courses on the fore and main, a topsail, topgallant and royal on every mast) hang from their yards:
the head bent along the yard's fore side by robands, the clews at the sheaves in the arms of the yard below (a course's
over the rail), the foot roached up in the middle, reef bands with their points across the fore side. The roach is
sails_1797.json's least share of the foot, cut deeper where the set sail would come within roach_clear_in of a stay or
of the top, crosstrees or cap of the mast below (the stays and those parts sampled into obstacle points at load). The
headsails and staysails are hanked to their stays (slice 4), the spanker laced to the mizzen mast and its gaff. Sizes
come from sails_1797.json (each with its source). Units as spars.py: metres in the ship frame (X forward, Y starboard,
Z up).

The states, one object each, built where they hang:

  Set      full of wind: the square sails with the yards square and the wind aft (the front face, forward, is to
           leeward); the fore-and-aft sails on the port tack (clew and belly to starboard: the starboard tack is the
           mirror about the centreline).
  Clewed   a square sail clewed up and its buntlines hauled (hanging in its gear: clews under the yard at the clew
           blocks, the foot up at the buntline blocks, the cloth in bags between); a headsail or staysail hauled down
           (in a loose heap along its boom or its stay's foot); the spanker brailed in to the gaff and mast.
  Furled   rolled up and lashed: on the yard, the bunt in the middle (square sails); along the boom (headsails) or the
           stay's foot (staysails); along the gaff and mast (the spanker). A topsail, topgallant or royal is furled
           with its yard lowered (rig.json's hoist_m[0], as a ship lies in harbour): hoisted, its stay runs through the
           bunt. The roll is packed tighter where a stay or the mast's head below comes near it at that height.

A square sail's objects (and the spanker's) are in their spar's frame (Sail_<Name>_<State>, origin and axes the yard's,
or the gaff's): parent them to it and they brace and hoist with it. Each square sail and the spanker also has a Head
object (head rope and robands, the spanker's lacing), the same in every state. A headsail's or staysail's objects
are in the ship's frame (stays don't move).

The cloth carries the sail cloth material's UVs (FSailCloth, Source/SailingSim/Public/SailCloth.h): UV0 metres
(x along the chord from the luff, y up from the foot), UV1 the normalized planform, UV2.x metres from the leech. A
square sail's luff is its port leech, and its x is square to its centre line (the cloths run up and down it, so a
seam is a line of constant UV0.x), counted from a whole number of cloths to port of the middle so the cloths lie
evenly about it (the port clew is a part cloth in from UV0.x = 0); a fore-and-aft sail's cloths run parallel to its
leech (constant UV2.x, measured square to the leech rather than along the row as FSailCloth's, so the cloths are their
true width apart; UV2.y is 0). The cloth faces forward on square sails, to starboard on the others.
"""
import json
import math
import os
import zlib

import numpy as np
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import ConvexHull

import loft
from rigging import rope_r, tube
from spars import Mesh, unit

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)
STATES = ("Set", "Clewed", "Furled")
CLOTH, CLOTH_FA = "Sailcloth", "SailclothFA"      # square sails' cloth, the fore-and-aft sails' (their seams differ)
ROPE, LINE = "Tarred", "Hemp"                      # bolt ropes; robands, reef points, gaskets, hanks' seizings
CORNERS = np.array([[i, j, k] for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)], float)     # a box's, in half sizes


def camel(key):
    return "".join(w.capitalize() for w in key.split("_"))


def seed_of(key):
    return zlib.crc32(key.encode()) & 0xFFFFFFFF


class SailMesh:
    """Vertices, triangles, a material per triangle and six UV numbers per vertex (UV0, UV1, UV2)."""

    def __init__(self):
        self.V, self.F, self.M, self.U = [], [], [], []
        self.n = 0

    def add(self, V, F, mat, uv=None):
        V = np.asarray(V, float).reshape(-1, 3)
        uv = np.zeros((len(V), 6)) if uv is None else np.asarray(uv, float).reshape(-1, 6)
        F = [tuple(int(i) for i in f) for f in F]
        tris = []
        for f in F:                                        # fans: everything goes in as triangles
            tris += [(f[0], f[k], f[k + 1]) for k in range(1, len(f) - 1)]
        self.V.append(V)
        self.U.append(uv)
        self.F += [tuple(self.n + i for i in t) for t in tris]
        self.M += [mat] * len(tris) if isinstance(mat, str) else [m for f, m in zip(F, mat) for _ in range(len(f) - 2)]
        self.n += len(V)

    def add_mesh(self, m):
        V, F, M = m.arrays()
        if len(V):
            self.add(V, F, M)

    def arrays(self):
        V = np.concatenate(self.V) if self.V else np.zeros((0, 3))
        U = np.concatenate(self.U) if self.U else np.zeros((0, 6))
        return V, list(self.F), list(self.M), U

    def tris(self):
        return len(self.F)


def grid_tris(nu, nv, flip=False):
    """Triangles of an (nu+1) x (nv+1) vertex grid, index i * (nv + 1) + j (i across, j down)."""
    F = []
    for i in range(nu):
        for j in range(nv):
            a, b, c, d = i * (nv + 1) + j, i * (nv + 1) + j + 1, (i + 1) * (nv + 1) + j + 1, (i + 1) * (nv + 1) + j
            F += [(a, c, b), (a, d, c)] if flip else [(a, b, c), (a, c, d)]
    return F


def catenary(A, B, length, n, side=EX):
    """n + 1 points by equal arc length along a chain of the given length hanging from A to B, in the vertical plane
    through them (side: that plane's direction when B is straight under or over A)."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    d = B - A
    h = np.array([d[0], d[1], 0.0])
    dx = float(np.linalg.norm(h))
    if dx < 1e-4:
        h, dx = np.asarray(side, float), 1e-4
    else:
        h = h / dx
    dz = float(d[2])
    chord = math.hypot(dx, dz)
    L = max(float(length), chord * 1.0001)
    lhs = math.sqrt(L * L - dz * dz)
    if lhs <= dx * 1.0005:                              # taut: a straight line
        t = np.linspace(0.0, 1.0, n + 1)
        return A[None, :] + t[:, None] * d[None, :]
    lo, hi = 1e-7, 1e7
    for _ in range(120):                                # 2a sinh(dx / 2a) = sqrt(L^2 - dz^2), a by bisection
        a = math.sqrt(lo * hi)
        if 2 * a * math.sinh(min(dx / (2 * a), 700.0)) > lhs:
            lo = a
        else:
            hi = a
    a = math.sqrt(lo * hi)
    x0 = dx / 2 - a * math.atanh(max(-0.999999, min(0.999999, dz / L)))
    s0 = a * math.sinh(-x0 / a)
    ss = np.linspace(0.0, L, n + 1)
    x = x0 + a * np.arcsinh((ss + s0) / a)
    z = a * (np.cosh((x - x0) / a) - math.cosh(-x0 / a))
    P = A[None, :] + x[:, None] * h[None, :] + z[:, None] * EZ[None, :]
    P[-1] = B
    return P


def chain_depth(length, span):
    """How far a chain of the given length hangs below two points level and span apart."""
    if length <= span * 1.0005:
        return 0.0
    lo, hi = 1e-7, 1e7
    for _ in range(120):
        a = math.sqrt(lo * hi)
        if 2 * a * math.sinh(min(span / (2 * a), 700.0)) > length:
            lo = a
        else:
            hi = a
    a = math.sqrt(lo * hi)
    return a * (math.cosh(min(span / (2 * a), 700.0)) - 1.0)


def torus(mesh, c, nrm, R, r, mat, n=10, m=4):
    """A ring of radius R (rope radius r) round c in the plane square to nrm."""
    a = unit(np.cross(nrm, EZ if abs(nrm @ EZ) < 0.9 else EX))
    b = np.cross(nrm, a)
    th = np.arange(n + 1) * 2 * math.pi / n
    P = c[None, :] + R * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b)
    tube(mesh, P[:-1], r, mat, n=m, closed=True)


def solids_sdf(P, solids):
    """each point's (P (n, 3)) distance (m) to the nearest of solids (spars.yard_mesh's boxes and cylinders), negative
    inside one; inf with none"""
    P = np.atleast_2d(np.asarray(P, float))
    d = np.full(len(P), np.inf)
    for so in solids:
        if so["kind"] == "box":
            q = np.abs((P - so["c"]) @ so["axes"].T) - so["half"]
            e = np.linalg.norm(np.maximum(q, 0.0), axis=1) + np.minimum(q.max(1), 0.0)
        else:
            a, b, r = so["a"], so["b"], so["r"]
            Lc = float(np.linalg.norm(b - a))
            u = (b - a) / Lc
            t = (P - a) @ u
            dx = np.linalg.norm(P - a - t[:, None] * u, axis=1) - r
            dy = np.abs(t - Lc / 2) - Lc / 2
            e = np.hypot(np.maximum(dx, 0.0), np.maximum(dy, 0.0)) + np.minimum(np.maximum(dx, dy), 0.0)
        d = np.minimum(d, e)
    return d


def solid_y_range(so):
    """a solid's extent along Y (its yard)"""
    if so["kind"] == "box":
        C = so["c"] + (CORNERS * so["half"]) @ so["axes"]
        return float(C[:, 1].min()), float(C[:, 1].max())
    a, b, r = so["a"], so["b"], so["r"]
    u = unit(b - a)
    sp = r * math.sqrt(max(0.0, 1.0 - u[1] ** 2))
    return float(min(a[1], b[1]) - sp), float(max(a[1], b[1]) + sp)


def solids_section(solids, y0, y1, n=16):
    """points whose convex hull holds every solid's part between y0 and y1 along Y (a box's corners, a cylinder's
    rings at the ends of that part)"""
    pts = []
    for so in solids:
        lo, hi = solid_y_range(so)
        if hi < y0 or lo > y1:
            continue
        if so["kind"] == "box":
            pts.append(so["c"] + (CORNERS * so["half"]) @ so["axes"])
            continue
        a, b, r = so["a"], so["b"], so["r"]
        Lc = float(np.linalg.norm(b - a))
        u = (b - a) / Lc
        if abs(u[1]) < 1e-6:
            ts = [0.0, Lc]
        else:
            ts = sorted([(y0 - a[1]) / u[1], (y1 - a[1]) / u[1]])
            ts = [max(0.0, ts[0]), min(Lc, ts[1])]
        e1 = unit(np.cross(u, EZ if abs(u[2]) < 0.9 else EX))
        e2 = np.cross(u, e1)
        th = np.linspace(0, 2 * math.pi, n, endpoint=False)
        for t in ts:
            pts.append(a + t * u + r / math.cos(math.pi / n) * (np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2))
    return pts


def inside_poly(Q, poly):
    """which of the 2-D points Q (k, 2) lie inside the closed polygon poly (m, 2)"""
    x, y = Q[:, :1], Q[:, 1:2]
    x0, y0 = poly[None, :, 0], poly[None, :, 1]
    x1, y1 = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    dy = np.where(y1 == y0, 1e-30, y1 - y0)
    cross = ((y0 > y) != (y1 > y)) & (x < x0 + (y - y0) * (x1 - x0) / dy)
    return cross.sum(1) % 2 == 1


def edge_points(V, F, step):
    """points along every edge of a mesh about step apart (its vertices too), and which connected part of the mesh
    each is on: a slab across a spar or rope holds a ring of them round its section, whatever its faces' shape"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    E = set()
    for f in F:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            E.add((a, b) if a < b else (b, a))
    E = np.array(sorted(E), dtype=np.int64).reshape(-1, 2)
    _, comp = connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(len(V), len(V))),
                                   directed=False)
    A, B = V[E[:, 0]], V[E[:, 1]]
    n = np.maximum(1, np.ceil(np.linalg.norm(B - A, axis=1) / step).astype(int))
    idx = np.repeat(np.arange(len(E)), n)
    t = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)) / np.repeat(n, n)
    return np.concatenate([V, A[idx] + t[:, None] * (B[idx] - A[idx])]), np.concatenate([comp, comp[E[idx, 0]]])


def surface_points(V, F, step):
    """points over a mesh's faces (each fanned into triangles) about step apart, and its vertices: along the edges of a
    thin triangle (narrower than step), over the whole of a broad one"""
    out = [V]
    for f in F:
        for k in range(1, len(f) - 1):
            a, b, c = V[f[0]], V[f[k]], V[f[k + 1]]
            ls = [np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)]
            L_ = max(ls)
            if L_ < step:
                continue
            if np.linalg.norm(np.cross(b - a, c - a)) / L_ < step:  # thin: its edges
                for p0, p1, ln in ((a, b, ls[0]), (b, c, ls[1]), (c, a, ls[2])):
                    t = np.linspace(0.0, 1.0, int(math.ceil(ln / step)) + 1)[1:-1]
                    out.append(p0[None] + t[:, None] * (p1 - p0)[None])
                continue
            n = int(min(80, math.ceil(L_ / step)))
            i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
            m = i + j <= n
            u, v = i[m] / n, j[m] / n
            out.append(a[None] + u[:, None] * (b - a)[None] + v[:, None] * (c - a)[None])
    return np.concatenate(out)


class Surface:
    """A sail's cloth as a map from (s, t) to a point: s across it (from lo to hi: -1 port leech .. 1 starboard
    leech on a square sail, 0 luff .. 1 leech on the others), t from the head (0) to the foot (1). f(s, t) takes two
    1-D arrays and returns the grid (len(s), len(t), 3)."""

    def __init__(self, f, lo=-1.0, hi=1.0):
        self.f, self.lo, self.hi = f, lo, hi

    def grid(self, s, t):
        return self.f(np.atleast_1d(np.asarray(s, float)), np.atleast_1d(np.asarray(t, float)))

    def at(self, s, t):
        """points at matched (s_k, t_k)"""
        return np.array([self.grid(sk, tk)[0, 0] for sk, tk in zip(np.atleast_1d(s), np.atleast_1d(t))])

    def normal(self, s, t, eps=2e-3):
        """unit normals at matched (s_k, t_k): (down t) x (along s), the cloth's front face (forward on a square
        sail, to starboard on a fore-and-aft one)"""
        out = []
        for sk, tk in zip(np.atleast_1d(s), np.atleast_1d(t)):
            s0, s1 = max(sk - eps, self.lo), min(sk + eps, self.hi)
            t0, t1 = max(tk - eps, 0.0), min(tk + eps, 1.0)
            G = self.grid([s0, s1], [t0, t1])
            ds = (G[1, 0] + G[1, 1] - G[0, 0] - G[0, 1]) / 2
            dt = (G[0, 1] + G[1, 1] - G[0, 0] - G[1, 0]) / 2
            out.append(unit(np.cross(dt, ds)))
        return np.array(out)


class Sails:
    def __init__(self, rig, st, path=os.path.join(HERE, "sails_1797.json")):
        self.rig, self.st = rig, st
        self.sp = json.load(open(path))
        self.objs = {}               # object name -> {"mesh", "frame", "parent", "sail", "state"}
        self.info = {}               # sail key -> its numbers for sails.json and the docs
        self.stays = {nm: (np.asarray(a, float), np.asarray(b, float), r) for nm, a, b, r in st.spans}
        cv = self.sp["canvas"]
        self.cloth_m = cv["cloth_in"] * IN
        self.pitch_m = (cv["cloth_in"] - cv["seam_in"]) * IN       # seam to seam, the cloths overlapping at the seams
        self.thick_m = cv["thick_in"] * IN
        # what a square sail's foot and a furled sail must clear: the stays' straight runs (points every 2 in, with
        # their radius) and the masts, tops, caps and crosstrees (their vertices and faces' centres)
        P, r, names = [], [], []
        for nm, a, b, rr in st.spans:
            if nm.endswith(" stay"):
                n = int(np.linalg.norm(b - a) / (2 * IN)) + 2
                P.append(a[None] + np.linspace(0.0, 1.0, n)[:, None] * (b - a)[None])
                r.append(np.full(n, rr))
                names += [nm] * n
        for nm, d in rig.parts_.items():
            if d["frame"] is None:
                V, F, _ = d["mesh"].arrays()
                C = surface_points(np.asarray(V, float), F, 4.0 * IN)
                P.append(C)
                r.append(np.zeros(len(C)))
                names += [nm] * len(C)
        self.obst_P, self.obst_r, self.obst_name = np.concatenate(P), np.concatenate(r), np.array(names)

    # ---- helpers ------------------------------------------------------------------------------------------------------
    def obj(self, name, frame, parent, key, state):
        m = SailMesh()
        self.objs[name] = {"mesh": m, "frame": frame, "parent": parent, "sail": key, "state": state}
        return m

    def cloth(self, out, surf, s, t, flat, mat):
        """The cloth: the grid of surf at s x t, with UVs from flat(s_grid, t_grid) -> (n, 6)."""
        G = surf.grid(s, t)
        S_, T_ = np.meshgrid(s, t, indexing="ij")
        out.add(G.reshape(-1, 3), grid_tris(len(s) - 1, len(t) - 1), mat, flat(S_.ravel(), T_.ravel()))
        return G

    def reef_gear(self, out, surf, bands, s_of_x, xs_of_band, pt_len, pt_r, band_w, flat):
        """Reef bands (a strip on the front face, with the cloth's UVs from flat(s, t)) and their points (each a
        short line on both faces, hanging down the cloth), and a cringle at each end of a band. bands: [(t_of_s,
        x_half)] where t_of_s(s) is the band's t at s and x_half its half width (m, flat)."""
        R = Mesh()
        for t_of_s, x_half in bands:
            ss = np.linspace(-1.0, 1.0, 41)
            tt = np.array([t_of_s(x) for x in ss])
            P = surf.at(ss, tt)
            N = surf.normal(ss, tt)
            Q = P + N * (0.5 * IN)
            dn = np.gradient(P, axis=0)
            dn = np.array([unit(np.cross(N[k], dn[k])) for k in range(len(P))])  # down the cloth (N x along)
            strip = np.concatenate([Q - dn * band_w / 2, Q + dn * band_w / 2])
            k = len(P)
            F = [(i, i + 1, k + i + 1, k + i) for i in range(k - 1)]
            uv = flat(ss, tt)
            lo, hi = uv.copy(), uv.copy()
            lo[:, 1] -= band_w / 2
            hi[:, 1] += band_w / 2
            out.add(strip, F, CLOTH, np.concatenate([lo, hi]))
            for x in xs_of_band(x_half):
                sk = s_of_x(x, t_of_s)
                tk = t_of_s(sk)
                for side in (1.0, -1.0):
                    off = side * (pt_r + 0.6 * IN + (0.5 * IN if side > 0 else 0.0))
                    ts_ = self.down_ts(surf, sk, tk, pt_len)
                    path = surf.at([sk] * 4, ts_) + surf.normal([sk] * 4, ts_) * off
                    tube(R, np.array(path), pt_r, LINE, n=3, caps=False)
            for sk in (-1.0, 1.0):
                tk = t_of_s(sk)
                p = surf.at([sk], [tk])[0]
                dir_out = unit(p - surf.at([sk * 0.98], [t_of_s(sk * 0.98)])[0])
                torus(R, p + dir_out * 1.5 * IN, surf.normal([sk], [tk])[0], 1.6 * IN, 0.45 * IN, ROPE, n=8, m=4)
        out.add_mesh(R)

    @staticmethod
    def down_ts(surf, s, t, length):
        """four t values from t along the cloth, the way that goes down, covering about length (m)"""
        G = surf.grid([s], np.clip([t - 0.02, t + 0.02], 0, 1))[0]
        dz = G[1, 2] - G[0, 2]
        step = np.linalg.norm(G[1] - G[0]) / 0.04
        dt = min(0.3, length / max(step, 1e-6))
        sgn = 1.0 if dz < 0 else -1.0
        return list(np.clip(t + sgn * dt * np.array([0.0, 0.33, 0.66, 1.0]), 0.0, 1.0))

    # ---- square sails --------------------------------------------------------------------------------------------------
    def square(self, key):
        S = self.sp["square"]
        spec = S["sails"][key]
        kind = spec["kind"]
        rig = self.rig
        yn = spec["yard"]
        g = rig.yard_geom[yn]
        o, R = rig.parts_[yn]["frame"]
        xc = g["x_off"]

        def Ry(y):
            return np.asarray(rig.yard_radius(yn, y), float)
        # the head earings just outside the stop cleats (the cleats stop them sliding in)
        hh = g["cleat_y"] + g["cleat_half"] + S["head_outside_cleat_in"] * IN
        ropes = S["bolt_rope_in"][kind]
        r_head, r_leech, r_foot = (rope_r(ropes[k]) for k in ("head", "leech", "foot"))
        a_h = math.radians(S["head_rope_deg"])                        # the head rope on the yard's fore side

        solids = g.get("solids", [])

        def sdf(P):
            """a point's clearance (m) from the yard and everything on it (cleats, irons, studding sail booms)"""
            P = np.atleast_2d(np.asarray(P, float))
            return np.minimum(np.hypot(P[:, 0] - xc, P[:, 2]) - Ry(P[:, 1]), solids_sdf(P, solids))

        def section(y0, y1):
            """points whose convex hull holds the yard and its fittings between y0 and y1 along it"""
            rmax = float(Ry(np.array([y0, (y0 + y1) / 2, y1])).max())
            return np.concatenate([self.ring(np.array([xc, (y0 + y1) / 2, 0.0]), EX, EZ, rmax)] +
                                  solids_section(solids, y0, y1))

        # the clews: a topsail's, topgallant's or royal's at the sheaves in the arms of the yard below; a course's
        # hauled in to the ship's side by its tack and sheet. A course is cut (and the draught draws it) with its foot
        # wider than its head and its clews over the rail; set, its clews come in to the side and up as far as the
        # leech lets them, and the foot's slack goes into its belly. kclew is the clew as cut, clew as set.
        if kind == "course":
            Cs = S["course"]
            yk = Cs["foot_of_head"] * hh
            below = None
        else:
            below = spec["sheets_to"]
            gb = rig.yard_geom[below]
            ob, Rb = rig.parts_[below]["frame"]
            ys = gb["half"] - gb["arm"] * (1.0 - S["sheave_in_yardarm"][kind])
            zc = float(rig.yard_radius(below, ys)) + S["clew_over_yard_in"] * IN
            bm = gb.get("boom")
            if bm is not None:                                        # a topsail's clew rides over the boom
                hb = bm["h0"] + (ys - bm["y0"]) / (bm["y1"] - bm["y0"]) * (bm["h1"] - bm["h0"])
                zc = max(zc, hb * math.sin(math.radians(bm["deg"])) + bm["r"] + rope_r(ropes["foot"]) + 0.5 * IN)
            pb = np.array([gb["x_off"], ys, zc])
            clew = (ob + Rb @ pb - o) @ R
            yc = float(clew[1])
            kclew, yk = clew, yc
        # the cloth's columns (s, -1 port leech .. 1 starboard), and the head along the yard's fore side: the head rope
        # runs straight from column to column, each column's point as far out as the cleats, irons and booms between
        # its neighbours need it (the rope clear by gap); the earings just outside the stop cleats
        nu = int(np.clip(round((hh + yk) / 0.55), 8, 32)) * 2
        ss = np.linspace(-1, 1, nu + 1)
        gap = 0.3 * IN
        yd = np.linspace(-hh, hh, int(2 * hh / (0.5 * IN)) + 1)
        rho = (Ry(yd) + r_head + gap)[:, None] + np.arange(240)[None] * 0.1 * IN
        Pd = np.stack([xc + rho * math.cos(a_h), np.broadcast_to(yd[:, None], rho.shape), rho * math.sin(a_h)], -1)
        ok = (sdf(Pd.reshape(-1, 3)) >= r_head + gap).reshape(rho.shape)
        if not ok.any(1).all():
            raise RuntimeError(f"{key}: the head rope can't clear its yard's fittings")
        need = rho[np.arange(len(yd)), np.argmax(ok, 1)]
        yq = ss * hh
        rad = np.array([need[(yd >= yq[max(i - 1, 0)] - 1e-9) & (yd <= yq[min(i + 1, nu)] + 1e-9)].max()
                        for i in range(nu + 1)])

        def head(s):
            s = np.asarray(s, float)
            r = np.interp(s, ss, rad)
            return np.stack([xc + r * math.cos(a_h), s * hh, r * math.sin(a_h)], -1)

        he = head(np.array([1.0]))[0]
        if kind == "course":
            x_ft = float(rig.masts[g["mast"]]["O"][0]) / FT
            z_c = (rig.rail_ft(x_ft) + rig.rail_cap_ft + Cs["clew_over_rail_ft"]) * FT
            kclew = np.array([xc, yk, (z_c - o[2] - R[2, 0] * xc - R[2, 1] * yk) / R[2, 2]])
            leech = float(np.linalg.norm(kclew - he))
            px = xc + Cs["clew_fwd_of_yard_ft"] * FT
            xw = float((o + R @ np.array([px, 0.0, 0.0]))[0]) / FT
            side = float(self.st.hull_at(xw, self.st.rail_top_ft(xw))[0][1])
            yc = side + Cs["clew_out_of_side_ft"] * FT
            clew = np.array([px, yc, he[2] - math.sqrt(leech ** 2 - (px - he[0]) ** 2 - (yc - he[1]) ** 2)])
        mir = np.array([1.0, -1.0, 1.0])
        hm = head(np.array([0.0]))[0]

        def plane(cS_):
            """the middle of the foot, and down, up and forward square to the sail (its plane through cS_, -cS_)"""
            fm_ = cS_ * np.array([1.0, 0.0, 1.0])
            dn_ = fm_ - hm
            dn_ = unit(dn_ - (dn_ @ EY) * EY)
            return fm_, -dn_, unit(np.cross(dn_, EY))
        cS = clew
        fm, up, nf = plane(cS)
        fk, upk, _ = plane(kclew)
        depth = float((hm - fm) @ up)                                 # as set
        depth_k = float((hm - fk) @ upk)                              # as cut
        roach = S["roach_of_foot"][kind] * 2 * yk

        def base_q(s, t, cS_, up_):
            """the unbellied sail at matched (s, t): the head on the yard, the foot from clew to clew with its roach"""
            H_ = head(s)
            F_ = (cS_ * mir)[None] + (cS_ - cS_ * mir)[None] * ((s + 1) / 2)[:, None] + \
                (roach * (1 - s ** 2))[:, None] * up_[None]
            return H_ * (1 - t)[:, None] + F_ * t[:, None]

        def base_m(s, t):
            return base_q(s, t, cS, up)

        # the cloths are laid out from the middle, as a sailmaker did, a seam on the centre line: UV0.x counts from
        # xo to port of it, the whole cloths' width that just takes in the foot, so the leeches' part cloths match
        xo = self.pitch_m * math.ceil(yk / self.pitch_m - 1e-9)

        def flat(s, t):
            """the sail as cut, flat (UV0 metres across from xo to port of the middle, so the port clew is at
            xo - yk, and up from the foot; UV1 the planform; UV2.x metres from the starboard leech along the row)"""
            P = base_q(s, t, kclew, upk)
            X, Yf = P[:, 1], (P - fk) @ upk
            return np.stack([X + xo, Yf, (s + 1) / 2, 1 - t, yk - X, 0 * Yf], 1)

        def Yhead(s):
            return (head(s) - fm) @ up

        def strip_len(s):
            """each cloth's length from head to foot, as cut"""
            s = np.asarray(s, float)
            return np.hypot(s * (hh - yk), (head(s) - fk) @ upk - roach * (1 - s ** 2))

        D = S["belly_of_width"] * (hh + yk)                           # a tenth of the mean width
        fb, lb = S["course"]["foot_belly"] if kind == "course" else S["foot_belly"], S["leech_bow"]

        def g_t(t):
            a = np.sin(np.pi / 2 * np.minimum(t / 0.45, 1.0))
            b = 1 - (1 - fb) * np.clip((t - 0.45) / 0.55, 0, 1) ** 2
            return np.where(t < 0.45, a, b)

        def set_f(s, t):
            S_, T_ = np.meshgrid(s, t, indexing="ij")
            P = base_m(S_.ravel(), T_.ravel()).reshape(len(s), len(t), 3)
            b = D * (g_t(T_) * (1 - S_ ** 2) + lb * np.sin(np.pi * T_) * S_ ** 2)
            return P + b[..., None] * nf

        # the foot's roach, cut deep enough that the set sail clears the stays and the head of the mast below (as
        # sailmakers cut it): every stay point or spar's corner that would lie at the cloth (within its radius and
        # S["roach_clear_in"] of the cloth, its middle 80%) goes under the foot by that much, at least the table's roach
        Pl = (self.obst_P - o) @ R
        cl = S["roach_clear_in"] * IN
        sel = (np.abs(Pl[:, 1]) < 0.8 * yc) & ((Pl - fm) @ up > -cl) & ((Pl - fm) @ up < depth * 0.6)
        Pl, rl, nl = Pl[sel], self.obst_r[sel], self.obst_name[sel]
        roach_table, roach_for = roach, set()
        for _ in range(9):
            Gs = set_f(np.linspace(-1, 1, 61), np.linspace(0, 1, 91)).reshape(-1, 3)
            ip = LinearNDInterpolator(np.stack([Gs[:, 1], (Gs - fm) @ up], 1), (Gs - fm) @ nf)
            Yp, Up, Fp = Pl[:, 1], (Pl - fm) @ up, (Pl - fm) @ nf
            above = Up > roach * (1 - (Yp / yc) ** 2) - r_foot
            f = ip(Yp, Up)
            at = above & ~np.isnan(f) & (np.abs(Fp - np.nan_to_num(f)) < rl + cl)
            if not at.any():
                break
            if _ == 8 or roach >= S["roach_max_of_foot"] * 2 * yk:
                raise RuntimeError(f"{key}: no roach up to roach_max_of_foot clears {sorted(set(nl[at]))}")
            needs = (Up[at] + rl[at] + cl + r_foot) / (1 - (Yp[at] / yc) ** 2)
            roach_for.add(str(nl[at][int(np.argmax(needs))]))
            roach = min(max(roach, float(needs.max())) + 0.5 * IN, S["roach_max_of_foot"] * 2 * yk)

        nv = int(np.clip(round(depth / 0.55), 10, 40))
        tt = np.linspace(0, 1, nv + 1)
        name = "Sail_" + camel(key)
        frame = (o, R)
        area = self.polygon_area(flat, -1.0, 1.0)

        # reef bands: a share of the depth under the head, level across the sail
        def band(rk):
            Yb = float(Yhead(np.array([0.0]))[0]) - rk * depth

            def t_of_s(sv):
                sv = np.asarray(sv, float)
                yh = Yhead(np.atleast_1d(sv))
                tv = (yh - Yb) / (yh - roach * (1 - np.atleast_1d(sv) ** 2))
                return float(tv[0]) if np.ndim(sv) == 0 else tv
            tl = t_of_s(1.0)
            return t_of_s, (1 - tl) * hh + tl * yk

        def s_of_x(x, t_of_s):
            """s where the flat sail's x (m from its middle, as cut) crosses a band"""
            sv = x / hh
            for _ in range(4):
                tv = t_of_s(sv)
                sv = x / ((1 - tv) * hh + tv * yk)
            return float(np.clip(sv, -1, 1))

        def xs_of_band(x_half):
            """a reef point in the middle of each cloth (between the seams: UV0.x at odd halves of the seam pitch)"""
            k = np.arange(-200, 200)
            x = (k + 0.5) * self.pitch_m - xo
            return [float(v) for v in x if abs(v) < x_half - 0.25 * self.cloth_m]
        bands = [band(rk) for rk in S["reefs"][kind]]
        pt_len, pt_r, band_w = S["reef_point_ft"] * FT, rope_r(S["reef_point_in"]), S["reef_band_in"] * IN

        # -- the head (the same in every state): head rope, robands, earings
        hd = self.obj(name + "_Head", frame, yn, key, "Head")
        Hm = Mesh()
        tube(Hm, head(ss), r_head, ROPE)
        r_rb = rope_r(S["roband_in"])
        busy = [solid_y_range(so) for so in solids if so["what"] != "boom"]
        for x in xs_of_band(hh + 0.25 * self.cloth_m):                # one in the middle of each cloth
            # round the yard, the head rope and the studding sail boom where it lies on the yard; none at a cleat or
            # an iron
            if abs(x) > g["cleat_y"] - g["cleat_half"] - 2 * IN or \
                    any(lo - 3 * IN < x < hi + 3 * IN for lo, hi in busy):
                continue
            w = r_rb + 0.25 * IN
            pts = np.concatenate([section(x - w, x + w), self.ring(head(np.array([x / hh]))[0], EX, EZ, r_head)])
            self.gasket(Hm, pts, EY, r_rb, gap=0.15 * IN)
        r_e = 0.5 * IN
        for sg in (1.0, -1.0):                                        # earings: two turns round the yardarm
            for j in range(2):
                yj = sg * (hh + r_e + 0.25 * IN + j * (2 * r_e + 0.2 * IN))
                self.gasket(Hm, section(yj - r_e - 0.2 * IN, yj + r_e + 0.2 * IN), EY, r_e, gap=0.15 * IN)
        hd.add_mesh(Hm)

        # -- set
        sm = self.obj(name + "_Set", frame, yn, key, "Set")
        surf = Surface(set_f)
        G = self.cloth(sm, surf, ss, tt, flat, CLOTH)
        self.edge_ropes(sm, surf, ss, tt, G, r_leech, r_foot, aft=-1.0, clear=sdf)
        self.reef_gear(sm, surf, bands, s_of_x, xs_of_band, pt_len, pt_r, band_w, flat)

        # -- clewed up: each cloth's strip hangs from the head to its foot, hauled up under the yard
        C = S["clewed"]
        q = C["clew_block_of_head"] * hh
        under, ahead, fold = C["under_yard_in"] * IN, C["foot_ahead_in"] * IN, C["fold_in"] * IN
        picks = sorted([-1.0, 1.0] + [b for b in C["buntlines"][kind]] + [-b for b in C["buntlines"][kind]])
        sag_of = []
        for sa, sb in zip(picks[:-1], picks[1:]):
            fs = np.linspace(sa, sb, 25)
            fx, fy = fs * yk, roach * (1 - fs ** 2)
            Lf = float(np.sum(np.hypot(np.diff(fx), np.diff(fy))))
            sag_of.append((sa, sb, chain_depth(Lf, q * (sb - sa))))

        def foot_target(s):
            y = q * s
            sag = np.zeros_like(s)
            for sa, sb, dep in sag_of:
                m = (s >= sa) & (s <= sb)
                u = (2 * s[m] - sa - sb) / (sb - sa)
                sag[m] = dep * (1 - u ** 2)
            return np.stack([xc + Ry(y) + ahead, y, -(Ry(y) + under) - sag], -1)
        rng = np.random.default_rng(seed_of(key))
        n_fold = max(3, int(round(2 * hh / (2.5 * self.cloth_m))))
        ph = rng.uniform(0, 2 * math.pi, 3)
        uu = np.linspace(0, 1, 97)

        def clew_f(s, t):
            H_, F_, Ls = head(s), foot_target(s), strip_len(s)
            out = np.empty((len(s), len(t), 3))
            for i in range(len(s)):
                P = catenary(H_[i], F_[i], Ls[i], 96, side=EX)
                out[i] = np.stack([np.interp(t, uu, P[:, k]) for k in range(3)], -1)
            S_, T_ = np.meshgrid(s, t, indexing="ij")
            w = (np.sin(2 * math.pi * n_fold * (S_ + 1) / 2 + ph[0]) + 0.35 * np.sin(2 * math.pi * 2.3 * n_fold *
                 (S_ + 1) / 2 + ph[1])) * np.sin(np.pi * T_) ** 0.7 * (1 - S_ ** 8)
            out[..., 0] += fold * w
            return out
        cm = self.obj(name + "_Clewed", frame, yn, key, "Clewed")
        surf_c = Surface(clew_f)
        tt_c = np.linspace(0, 1, 2 * nv + 1)                          # the bags need more rows than the set sail
        Gc = self.cloth(cm, surf_c, ss, tt_c, flat, CLOTH)
        self.edge_ropes(cm, surf_c, ss, tt_c, Gc, r_leech, r_foot, aft=-1.0, clear=sdf)
        self.reef_gear(cm, surf_c, bands, s_of_x, xs_of_band, pt_len, pt_r, band_w, flat)

        # -- furled: rolled on the yard's top and fore side, the bunt in the middle, gaskets
        Fu = S["furled"]
        ny = int(np.clip(round(2 * hh / 0.3), 24, 120))
        y = np.linspace(-hh, hh, ny + 1)
        w = 0.6 + 0.4 * (1 - (y / hh) ** 2) + (Fu["bunt_factor"] - 1) * np.exp(-(y / (Fu["bunt_of_half"] * hh)) ** 2)
        w = w / w.mean()
        r = np.sqrt(area / (2 * hh) * self.thick_m * Fu["packing"] * w / math.pi)
        r *= np.clip((hh - np.abs(y)) / (0.03 * hh), 0.45, 1.0)
        fm_ = self.obj(name + "_Furled", frame, yn, key, "Furled")
        bunt = np.exp(-(y / (Fu["bunt_of_half"] * hh)) ** 2)
        a_c = np.radians(Fu["roll_deg"] + (Fu["bunt_deg"] - Fu["roll_deg"]) * bunt)   # the bunt up on top, by the mast
        er = np.stack([np.cos(a_c), 0 * a_c, np.sin(a_c)], 1)
        et = np.stack([-np.sin(a_c), 0 * a_c, np.cos(a_c)], 1)
        # each station's roll rests on the yard: moved out along er from the yard's axis until it clears the yard, its
        # cleats, irons and studding sail booms by gap (tried at its neighbours' places too, so the cloth between
        # stations clears them), and none of them is inside it. It is packed tighter where a stay or the masthead would
        # be in it, to clear them by Fu["clear_in"], with the yard lowered (a topsail, topgallant or royal is furled
        # with its yard down on the cap: hoisted, the stay from just above it runs through the bunt)
        h0 = self.st.yard_rests().get(yn, rig.meta[yn]["hoist_m"][0])
        Pl = (self.obst_P - (o + R[:, 2] * h0)) @ R
        near = (Pl[:, 2] > -0.5) & (Pl[:, 2] < 3.0) & (Pl[:, 0] > xc - 2.0) & (Pl[:, 0] < xc + 3.0)
        Pl, rl = Pl[near], self.obst_r[near]
        n_y = len(y)
        nb = [(max(k - 1, 0), min(k + 1, n_y - 1)) for k in range(n_y)]
        sect = [section(y[a_], y[b_]) for a_, b_ in nb]
        hulls = []
        for k in range(n_y):
            P2 = sect[k][:, [0, 2]]
            H = ConvexHull(P2)
            hulls.append((H.equations, P2[H.vertices]))

        def rest(k, Dk):
            """how far out along er[k] the roll Dk (its ring about its centre) must lie to rest on the yard: clear of
            the convex hull of the yard and its fittings between its neighbours (so it can't tuck in under a boom) by
            twice gap (the cloth between two stations, turning toward the bunt, sags in a little)"""
            eqs, hv = hulls[k]
            Q = np.concatenate([Dk + (np.roll(Dk, -1, 0) - Dk) * w_ for w_ in (0.0, 1 / 3, 2 / 3)])[:, [0, 2]]
            lam = float(Ry(y[k])) + np.arange(0.0, 3.0 * np.abs(Dk).max() + 0.3, 0.25 * IN)
            C = np.array([xc, 0.0]) + lam[:, None] * er[k][[0, 2]]
            sd = ((C[:, None, :] + Q[None]) @ eqs[:, :2].T + eqs[:, 2]).max(-1)
            for i in np.flatnonzero((sd >= 2 * gap).all(1)):
                if not inside_poly(hv, C[i] + Dk[:, [0, 2]]).any():
                    return float(lam[i])
            raise RuntimeError(f"{key}: the furled roll finds no rest on its yard at y {y[k]:.2f}")

        def seg_dist(Pts, poly):
            """2-D distances from points to a closed polygon's edges (negative inside)"""
            A_, B_ = poly, np.roll(poly, -1, 0)
            AB = B_ - A_
            t_ = np.clip(((Pts[:, None] - A_[None]) * AB[None]).sum(-1) / (AB * AB).sum(-1)[None], 0, 1)
            d_ = np.linalg.norm(Pts[:, None] - A_[None] - t_[..., None] * AB[None], axis=-1).min(1)
            return np.where(inside_poly(Pts, poly), -d_, d_)

        def place(D):
            cut = np.ones(n_y)
            for k in range(n_y):
                m = np.abs(Pl[:, 1] - y[k]) < 0.15
                if not m.any():
                    continue
                for f in np.linspace(1.0, 0.3, 15):
                    c = np.array([xc, y[k], 0.0]) + rest(k, D[k] * f) * er[k]
                    d = seg_dist(Pl[m][:, [0, 2]], (c + D[k] * f)[:, [0, 2]]) - rl[m] - Fu["clear_in"] * IN
                    if d.min() >= 0.0:
                        break
                cut[k] = f
            cut = np.minimum.reduce([cut, np.roll(cut, 1), np.roll(cut, -1), np.roll(cut, 2), np.roll(cut, -2)])
            sc = np.convolve(np.pad(cut, 3, mode="edge"), np.ones(7) / 7, mode="valid")
            lam = np.array([rest(k, D[k] * sc[k]) for k in range(n_y)])
            lam = np.maximum(lam, np.convolve(np.pad(lam, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid"))
            return np.array([xc, 0.0, 0.0])[None] + y[:, None] * EY[None] + lam[:, None] * er, sc
        secs = self.bundle(fm_, np.stack([np.full(n_y, xc), y, 0 * y], 1), EY, er, et, r, (0.85, 1.15), rng, CLOTH,
                           place=place)
        n_g = max(2, int(round(2 * hh / (Fu["gasket_every_ft"] * FT))))
        r_g = rope_r(Fu["gasket_in"])
        for yg in list(np.linspace(-hh * 0.94, hh * 0.94, n_g)) + ([0.0] if n_g % 2 == 0 else []):
            k = int(np.argmin(np.abs(y - yg)))
            w = r_g + 0.3 * IN
            self.gasket(fm_, np.concatenate([secs[k], section(y[k] - w, y[k] + w)]), EY, r_g)

        self.info[key] = {"kind": kind, "yard": yn, "sheets_to": below, "area_ft2": round(area / FT ** 2, 0),
                          "head_ft": round(2 * hh / FT, 2), "foot_ft": round(2 * yk / FT, 2),
                          "depth_ft": round(depth_k / FT, 2), "belly_ft": round(D / FT, 2),
                          "clews_set_apart_ft": round(2 * yc / FT, 2),
                          "roach_ft": round(roach / FT, 2), "roach_table_ft": round(roach_table / FT, 2),
                          "roach_clears": sorted(roach_for), "reefs": S["reefs"][kind],
                          "clew_local_m": np.round(clew, 3).tolist(), "clew_cut_local_m": np.round(kclew, 3).tolist(),
                          "head_earing_local_m": np.round(head(np.array([1.0]))[0], 3).tolist(),
                          "clew_block_local_m": np.round(foot_target(np.array([1.0]))[0], 3).tolist(),
                          "grid": [nu, nv]}

    # ---- headsails and staysails --------------------------------------------------------------------------------------
    def boom_of(self, stay):
        """the spar a headsail is tacked to and stowed on: (heel, along, up, length, radius(s))"""
        bs = self.rig.bs
        if stay == "fore topmast stay":
            return bs["H"], bs["ub"], bs["up"], bs["Lb"], bs["R"]
        p0, u, upv, Lb, Rf = bs["jib"] if stay == "fore topgallant stay" else bs["fjb"]
        return p0, u, upv, Lb, Rf

    def fore_and_aft(self, key, group):
        FA = self.sp["fore_and_aft"]
        spec = FA[group][key]
        rig = self.rig
        a, b, r_st = self.stays[spec["stay"]]
        u_st = unit(a - b)
        Ls = float(np.linalg.norm(a - b))
        if group == "headsails":
            T0 = b + u_st * spec["tack_up_ft"] * FT
            H0 = T0 + u_st * spec["luff_of_stay"] * Ls
        else:
            mf, mt = rig.masts[spec["from"]], rig.masts[spec["to"]]

            def mast_x(m, z):
                return float(m["O"][0] + (z - m["O"][2]) / m["u"][2] * m["u"][0])

            def on_stay(x):
                return b + (x - b[0]) / (a[0] - b[0]) * (a - b)
            P = on_stay(float(mf["O"][0]) + spec["head_fwd_ft"] * FT)
            for _ in range(4):
                P = on_stay(mast_x(mf, P[2]) + spec["head_fwd_ft"] * FT)
            H0 = P
            P = on_stay(float(mt["O"][0]) - spec["tack_aft_ft"] * FT)
            for _ in range(4):
                P = on_stay(mast_x(mt, P[2]) - spec["tack_aft_ft"] * FT)
            T0 = P
        Lv = H0 - T0
        Ll = float(np.linalg.norm(Lv))
        p_ad = unit(np.array([-Lv[2], 0.0, Lv[0]]))                 # square to the luff, aft and down
        if group == "headsails":
            al, be = spec["clew"]
            C = T0 + al * Lv + be * Ll * p_ad
        else:
            C = np.array([H0[0], 0.0, spec["clew_z_ft"] * FT])
        foot = float(np.linalg.norm(C - T0))
        C = C + EY * spec.get("lee_of_foot", FA["clew_to_lee_of_foot"]) * foot
        ropes = FA["bolt_rope_in"]
        r_luff, r_leech, r_foot = (rope_r(ropes[k]) for k in ("luff", "leech", "foot"))
        off = r_st + r_luff + 0.6 * IN                              # the luff hangs under the stay
        T, Hl = T0 + p_ad * off, H0 + p_ad * off
        e_f = unit(C - T)
        e_u = unit((Hl - T) - ((Hl - T) @ e_f) * e_f)
        xh, yh, xcf = (Hl - T) @ e_f, (Hl - T) @ e_u, (C - T) @ e_f
        n_lee = unit(np.cross(T - Hl, C - Hl))
        if n_lee[1] < 0:
            n_lee = -n_lee

        def base_m(s, t):
            Lp = Hl[None] + t[:, None] * (T - Hl)[None]
            Ep = Hl[None] + t[:, None] * (C - Hl)[None]
            return Lp + s[:, None] * (Ep - Lp)

        sq_leech = yh / math.hypot(xh - xcf, yh)                     # across the row to square to the leech

        def flat(s, t):
            """UV0 metres along the row from the luff and up from the foot, UV1 the planform, UV2.x metres from the
            leech square to it (so the cloths, parallel to it, are their true width apart)"""
            P = base_m(s, t)
            xf, yf = (P - T) @ e_f, (P - T) @ e_u
            return np.stack([xf - yf * xh / yh, yf, s, 1 - t, (xcf + (xh - xcf) * yf / yh - xf) * sq_leech, 0 * yf], 1)
        cam = FA["belly_of_chord"]
        chord_foot = float(np.linalg.norm(C - T))

        def fs(s):
            return 0.5 * 4 * s * (1 - s) + 0.5 * 6.75 * s * (1 - s) ** 2

        def set_f(s, t):
            S_, T_ = np.meshgrid(s, t, indexing="ij")
            P = base_m(S_.ravel(), T_.ravel()).reshape(len(s), len(t), 3)
            return P + (cam * chord_foot * T_ * fs(S_))[..., None] * n_lee

        nu = int(np.clip(round(chord_foot / 0.6), 8, 40))
        nv = int(np.clip(round(Ll / 0.6), 12, 60))
        ss, tt = np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1)
        name = "Sail_" + camel(key)
        area = self.polygon_area(flat, 0.0, 1.0)
        rng = np.random.default_rng(seed_of(key))

        # -- set: the cloth, its bolt ropes, the hanks on the stay and the cringles
        sm = self.obj(name + "_Set", None, None, key, "Set")
        surf = Surface(set_f, 0.0, 1.0)
        G = self.cloth_tri(sm, surf, ss, tt, flat, CLOTH_FA)
        self.edge_ropes(sm, surf, ss, tt, G, r_leech, r_foot, aft=-1.0, luff=(r_luff, 0.0))
        Hm = Mesh()
        for d in np.arange(0.5 * FT, Ll, FA["hank_every_ft"] * FT):
            torus(Hm, T0 + unit(Lv) * d, u_st, r_st + 0.9 * IN, 0.45 * IN, "Deadeye", n=10, m=4)
        Gc = G.reshape(-1, 3).mean(0)

        def stay_clear(c):
            d = a - b
            tq = float(np.clip((c - b) @ d / (d @ d), 0.0, 1.0))
            return float(np.linalg.norm(c - (b + tq * d))) - r_st
        for P_ in (G[-1, -1], G[0, -1], G[0, 0]):                      # the corners' cringles, in the bolt rope
            self.cringle(Hm, P_, Gc, n_lee, stay_clear)
        sm.add_mesh(Hm)

        # -- hauled down and stowed
        Fu = FA["furled"]
        hd = FA["hauled_down"]
        if group == "headsails":
            p0, ub, upb, _, _ = self.boom_of(spec["stay"])
            s_t = float((T0 - p0) @ ub)
            side = math.radians(spec.get("side_deg", 0.0))
            e_side = unit(np.cross(ub, upb))
            if e_side[1] < 0:
                e_side = -e_side
            e_out = math.cos(side) * upb + math.sin(side) * e_side   # where on the spar the heap lies

            def axis(length, n):
                """stations along the spar from 1 1/2 ft in from the tack (where the guys and the stay leave its end)"""
                sv = np.linspace(s_t - 1.5 * FT - length, s_t - 1.5 * FT, n)
                return p0[None] + sv[:, None] * ub[None], sv
            e1, e2, along = e_out, np.cross(ub, e_out), ub
        else:
            hang = unit(-EZ - (-EZ @ u_st) * u_st)

            def axis(length, n):
                sv = np.linspace(0.3 * FT, length, n)
                return T0[None] + sv[:, None] * u_st[None], sv
            e1, e2, along = hang, np.cross(u_st, hang), u_st
        Lb_s = spec["stow_ft"] * FT if group == "headsails" else hd["share_of_luff"] * Ll
        n_st = int(np.clip(round(Lb_s / 0.3), 16, 80))
        prof = np.sin(np.pi * np.clip(np.linspace(0, 1, n_st) * 1.0, 0.04, 0.96)) ** 0.5
        HP, HC = self.heap_points()
        for state, length, factor, ax, lumpy in (("Clewed", Lb_s, hd["loose"], (1.25, 0.95), 2.0),
                                                 ("Furled", Lb_s * 0.85, 1.0, (1.0, 1.0), 0.7)):
            rr = math.sqrt(area * self.thick_m * Fu["packing"] * factor / length / math.pi) * prof / prof.mean()
            C0, sv = axis(length, n_st)
            # the heap rests on its spar or under its stay: each station's section clear of the spar's (or stay's)
            # and everything else's there (between its neighbours: the jibboom on the bowsprit, a guy, a stay)
            reach = 4.0 * float(rr.max()) + 0.5
            box_ = (np.abs(HP - C0.mean(0)) < np.abs(C0[-1] - C0[0]) / 2 + reach).all(1)
            HPn, HCn = HP[box_], HC[box_]
            ds = float(sv[1] - sv[0])
            pieces = [self.slab_pieces(HPn, HCn, C0[k], along, e1, e2, -ds - 2 * IN, ds + 2 * IN, reach)
                      for k in range(n_st)]

            def place(D, C0=C0, pieces=pieces):
                return C0 + self.rest_on(e1, e2, e1, D, lambda k: pieces[k])[:, None] * e1[None], np.ones(len(D))
            om = self.obj(name + "_" + state, None, None, key, state)
            secs = self.bundle(om, C0, along, e1, e2, rr, ax, rng, CLOTH_FA, lumpy=lumpy, place=place)
            if state == "Furled":
                r_g = rope_r(Fu["gasket_in"])
                for d in np.arange(1.0 * FT, length - 0.5 * FT, Fu["gasket_every_ft"] * FT):
                    k = int(np.argmin(np.abs(sv - sv[0] - d)))
                    pc = self.slab_pieces(HPn, HCn, C0[k], along, e1, e2, -r_g - 3 * IN, r_g + 3 * IN, reach)
                    self.lash(om, secs[k], C0[k], along, e1, e2, pc, r_g)
        self.info[key] = {"kind": group[:-1], "stay": spec["stay"], "area_ft2": round(area / FT ** 2, 0),
                          "luff_ft": round(Ll / FT, 2), "foot_ft": round(foot / FT, 2),
                          "leech_ft": round(float(np.linalg.norm(C - H0)) / FT, 2),
                          "tack_m": np.round(T0, 3).tolist(), "head_m": np.round(H0, 3).tolist(),
                          "clew_m": np.round(C, 3).tolist(), "grid": [nu, nv],
                          "starboard_tack_mirror": {"point_m": np.round(T0, 4).tolist(),
                                                    "normal": np.round(unit(np.cross(u_st, EZ)), 6).tolist()}}

    def cloth_tri(self, out, surf, ss, tt, flat, mat):
        """A triangular sail's cloth: the grid of surf at ss x tt whose first row (t = 0) is the head, one vertex."""
        G = surf.grid(ss, tt)
        nu, nv = len(ss) - 1, len(tt) - 1
        S_, T_ = np.meshgrid(ss, tt[1:], indexing="ij")
        V = np.concatenate([G[:, 1:].reshape(-1, 3), G[:1, 0]])
        U = np.concatenate([flat(S_.ravel(), T_.ravel()), flat(np.array([0.0]), np.array([0.0]))])
        h = (nu + 1) * nv

        def vi(i, j):
            return h if j == 0 else i * nv + (j - 1)
        F = []
        for i in range(nu):
            F.append((h, vi(i, 1), vi(i + 1, 1)))
            for j in range(1, nv):
                a, b, c, d = vi(i, j), vi(i, j + 1), vi(i + 1, j + 1), vi(i + 1, j)
                F += [(a, b, c), (a, c, d)]
        out.add(V, F, mat, U)
        return G

    # ---- the spanker ---------------------------------------------------------------------------------------------------
    def spanker(self):
        from spars import taper
        SP = self.sp["spanker"]
        rig = self.rig
        gg, bgm = rig.spanker_geom["SpankerGaff"], rig.spanker_geom["SpankerBoom"]
        og, Rg = rig.parts_["SpankerGaff"]["frame"]
        ob, Rb = rig.parts_["SpankerBoom"]["frame"]
        m = rig.masts["mizzen"]
        s_g = float((og - m["O"]) @ m["u"])
        bt = taper(rig.sp["taper"]["boom"])
        ropes = SP["bolt_rope_in"]
        r_luff, r_head, r_leech, r_foot = (rope_r(ropes[k]) for k in ("luff", "head", "leech", "foot"))

        hoop = rig.fit["hoops"]["thick_in"] * IN

        def Rm(z):
            return float(m["R_lower"](s_g + z))

        def mast_ring(z):
            """the mast's section at z (gaff frame) out over its iron hoops"""
            return self.ring(np.array([0.0, 0.0, z]), EX, EY, Rm(z) + hoop)
        ug, Lg = gg["axis"], gg["length"]
        dn_g = unit(np.cross(ug, EY))                                 # square to the gaff, downward

        def gaff_pt(sv, extra):
            r = gg["d"] / 2 * float(bt(sv / Lg))
            return gg["heel"] + sv * ug + (r + extra) * dn_g
        ub_b = (Rb @ bgm["axis"]) @ Rg                                # the boom in the gaff's frame
        up_b = unit(np.cross(EY, ub_b))
        if up_b[2] < 0:
            up_b = -up_b
        heel_b = (ob + Rb @ bgm["heel"] - og) @ Rg
        Lb = bgm["length"]

        def boom_pt(sv, extra):
            r = bgm["d"] / 2 * float(bt(sv / Lb))
            return heel_b + sv * ub_b + (r + extra) * up_b
        s_th, s_pk = 0.6 * FT, Lg - SP["head_short_of_peak_ft"] * FT
        Th, Pk = gaff_pt(s_th, r_head), gaff_pt(s_pk, r_head)
        z_tk = boom_pt(0.6 * FT, 0.0)[2] + SP["luff_over_boom_ft"] * FT
        Cl = boom_pt(Lb - SP["clew_short_of_end_ft"] * FT, 0.3 * FT)

        gap = SP["luff_off_mast_in"] * IN

        def luff_x(z):
            return -(Rm(z) + gap + r_luff)
        Th = np.array([luff_x(Th[2]), 0.0, Th[2]])
        Tk = np.array([luff_x(z_tk), 0.0, z_tk])

        def head(s):
            return np.array([gaff_pt(s_th + x * (s_pk - s_th), r_head) for x in s])

        def luff(t):
            z = Th[2] + t * (Tk[2] - Th[2])
            return np.stack([np.array([luff_x(zz) for zz in z]), 0 * z, z], 1)

        def foot(s):
            return Tk[None] + s[:, None] * (Cl - Tk)[None]

        def leech(t):
            return Pk[None] + t[:, None] * (Cl - Pk)[None]

        def base_m(s, t):
            H_, F_, L_, E_ = head(s), foot(s), luff(t), leech(t)
            st_, tt_ = s[:, None], t[:, None]
            return ((1 - tt_) * H_ + tt_ * F_ + (1 - st_) * L_ + st_ * E_ -
                    ((1 - st_) * (1 - tt_) * Th + st_ * (1 - tt_) * Pk + (1 - st_) * tt_ * Tk + st_ * tt_ * Cl))
        e_fu = unit(Cl - Tk)
        e_up = unit(np.cross(EY, e_fu))
        if e_up[2] < 0:
            e_up = -e_up

        sq_leech = abs(Pk[2] - Cl[2]) / math.hypot(Pk[0] - Cl[0], Pk[2] - Cl[2])

        def flat(s, t):
            """UV0 metres aft from the luff and up from the tack, UV1 the planform, UV2.x metres from the leech square
            to it (UV2.y 0, as FSailCloth's)"""
            P = base_m(s, t)
            z = P[:, 2]
            lx = np.array([luff_x(zz) for zz in z])
            fz = np.clip((z - Pk[2]) / (Cl[2] - Pk[2]), 0, 1)
            ex = Pk[0] + fz * (Cl[0] - Pk[0])
            return np.stack([lx - P[:, 0], (P - Tk) @ e_up, s, 1 - t, (P[:, 0] - ex) * sq_leech, 0 * z], 1)
        cam = SP["belly_of_chord"]

        def set_f(s, t):
            S_, T_ = np.meshgrid(s, t, indexing="ij")
            P = base_m(S_.ravel(), T_.ravel()).reshape(len(s), len(t), 3)
            chord = np.linalg.norm(leech(t) - luff(t), axis=1)[None, :]
            fs = 0.5 * 4 * S_ * (1 - S_) + 0.5 * 6.75 * S_ * (1 - S_) ** 2
            h = np.sin(np.pi / 2 * np.minimum(1.0, T_ / 0.35))
            return P + (cam * chord * fs * h)[..., None] * EY

        chord_mid = float(np.linalg.norm(leech(np.array([0.5]))[0] - luff(np.array([0.5]))[0]))
        nu = int(np.clip(round(chord_mid / 0.55), 12, 48))
        nv = int(np.clip(round(abs(Th[2] - Tk[2]) / 0.55), 12, 48))
        ss, tt = np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1)
        name = "Sail_Spanker"
        frame = (og, Rg)
        area = self.polygon_area(flat, 0.0, 1.0)
        rng = np.random.default_rng(seed_of("spanker"))

        # -- the head and luff (every state): head and luff ropes, the lacing round the gaff and the mast
        hd = self.obj(name + "_Head", frame, "SpankerGaff", "spanker", "Head")
        Hm = Mesh()
        hs = np.linspace(0, 1, 40)
        tube(Hm, head(hs), r_head, ROPE)
        tube(Hm, luff(np.linspace(0, 1, 30)), r_luff, ROPE)
        e2g = np.cross(ug, dn_g)
        r_lace = rope_r(SP["lacing_in"])
        for sv in np.arange(s_th + 1.0 * FT, s_pk, SP["head_lacing_every_ft"] * FT):   # round the gaff and head rope
            gaff = self.ring(gg["heel"] + sv * ug, dn_g, e2g, gg["d"] / 2 * float(bt(sv / Lg)))
            rope = self.ring(gaff_pt(sv, r_head), dn_g, e2g, r_head)
            self.gasket(Hm, np.concatenate([gaff, rope]), ug, r_lace, gap=0.15 * IN)
        for z in np.arange(Tk[2] + 0.5 * FT, Th[2] - 0.5 * FT, SP["luff_lacing_every_ft"] * FT):
            rope = self.ring(np.array([luff_x(z), 0.0, z]), EX, EY, r_luff)   # round the mast (its hoops) and luff
            self.gasket(Hm, np.concatenate([mast_ring(z), rope]), EZ, r_lace, gap=0.15 * IN)
        hd.add_mesh(Hm)

        # -- set
        sm = self.obj(name + "_Set", frame, "SpankerGaff", "spanker", "Set")
        surf = Surface(set_f, 0.0, 1.0)
        G = self.cloth(sm, surf, ss, tt, flat, CLOTH_FA)
        Rp = Mesh()
        Ns = surf.normal(np.ones(len(tt)), tt)
        tube(Rp, G[-1] - Ns * r_leech * 0.9, r_leech, ROPE)
        Nf = surf.normal(ss, np.ones(len(ss)))
        tube(Rp, G[:, -1] - Nf * r_foot * 0.9, r_foot, ROPE)
        Gc = G.reshape(-1, 3).mean(0)

        def spar_clear(c):
            """clearance from the gaff, the boom and the mast"""
            sg = float(np.clip((c - gg["heel"]) @ ug, 0.0, Lg))
            dg = float(np.linalg.norm(c - (gg["heel"] + sg * ug))) - gg["d"] / 2 * float(bt(sg / Lg))
            sb = float(np.clip((c - heel_b) @ ub_b, 0.0, Lb))
            db = float(np.linalg.norm(c - (heel_b + sb * ub_b))) - bgm["d"] / 2 * float(bt(sb / Lb))
            dm = float(np.hypot(c[0], c[1])) - Rm(c[2]) - hoop
            return min(dg, db, dm)
        for P_ in (G[-1, -1], G[0, -1], G[-1, 0]):                      # clew, tack and peak cringles
            self.cringle(Rp, P_, Gc, EY, spar_clear)
        sm.add_mesh(Rp)

        # -- brailed up (gathered in to the gaff and the mast) and furled: heaps along the gaff's underside and down
        # the mast's after side
        luff_len = float(Th[2] - Tk[2])
        Fu_in = self.sp["fore_and_aft"]["furled"]["gasket_in"]
        # what the heap under the gaff rests on and clears, in the gaff's frame: the gaff, its head rope and lacing's
        # bulk (rings round the head rope), the mast and the rigging near it
        Vg, Fg, _ = rig.parts_["SpankerGaff"]["mesh"].arrays()
        hr = head(np.linspace(0, 1, int((s_pk - s_th) / (2 * IN)) + 2))
        thr = np.linspace(0, 2 * math.pi, 8, endpoint=False)
        HP, HC = self.heap_points()
        HPg = (HP - og) @ Rg
        near_ = (HPg[:, 2] > Pk[2] - 2.0) & (HPg[:, 2] < Th[2] + 2.0) & (HPg[:, 0] > Pk[0] - 2.0) & \
            (HPg[:, 0] < 2.0) & (np.abs(HPg[:, 1]) < 2.0)
        Pg, Cg = edge_points(np.asarray(Vg, float), Fg, 2.0 * IN)
        Ph = (hr[:, None, :] + r_head * (np.cos(thr)[None, :, None] * dn_g + np.sin(thr)[None, :, None] * e2g))
        GHP = np.concatenate([Pg, HPg[near_], Ph.reshape(-1, 3)])
        GHC = np.concatenate([-2 - Cg, HC[near_], np.full(Ph.shape[0] * Ph.shape[1], -1)])   # gaff -2.., head rope -1
        for state, factor, ax, lumpy, share in (("Clewed", self.sp["fore_and_aft"]["hauled_down"]["loose"],
                                                 (1.25, 0.95), 2.0, 1.0), ("Furled", 1.0, (1.0, 1.0), 0.7, 0.8)):
            om = self.obj(name + "_" + state, frame, "SpankerGaff", "spanker", state)
            vol = area * self.thick_m * self.sp["fore_and_aft"]["furled"]["packing"] * factor
            Lg_b, Lm_b = 0.8 * (s_pk - s_th) * share, 0.45 * luff_len * share
            ng, nm_ = int(np.clip(round(Lg_b / 0.3), 16, 80)), int(np.clip(round(Lm_b / 0.3), 8, 60))
            ug_ = np.linspace(0, 1, ng)
            prof_g = (1.0 - 0.65 * ug_) * np.sin(np.pi * np.clip(ug_, 0.03, 0.97)) ** 0.15
            rg0 = math.sqrt(0.6 * vol / (Lg_b * math.pi * np.mean(prof_g ** 2)))
            rr = rg0 * prof_g
            sv = s_th + 0.3 * FT + ug_ * Lg_b
            # under the gaff, resting on it and its head rope (and clear of the mast at the jaws)
            C0 = gg["heel"][None] + sv[:, None] * ug[None]
            ds = float(sv[1] - sv[0])
            reach = 4.0 * float(rr.max()) + 0.5
            pieces = [self.slab_pieces(GHP, GHC, C0[k], ug, dn_g, e2g, -ds - 2 * IN, ds + 2 * IN, reach)
                      for k in range(ng)]

            def place(D, C0=C0, pieces=pieces):
                return C0 + self.rest_on(dn_g, e2g, dn_g, D, lambda k: pieces[k])[:, None] * dn_g[None], np.ones(len(D))
            secs = self.bundle(om, C0, ug, dn_g, e2g, rr, ax, rng, CLOTH_FA, lumpy=lumpy, place=place)
            um = np.linspace(0, 1, nm_)
            prof_m = (1.0 - 0.6 * um)
            rm0 = math.sqrt(0.4 * vol / (Lm_b * math.pi * np.mean(prof_m ** 2)))
            rm = rm0 * prof_m
            zm = Th[2] - 0.6 * FT - um * Lm_b
            off = ax[::-1][0] * (1 + 0.225 * lumpy) * rm + 1.0 * IN      # its folds clear of the mast
            cen_m = np.stack([np.array([luff_x(z) for z in zm]) - off, 0 * zm, zm], 1)
            secs_m = self.bundle(om, cen_m, -EZ, -EX, EY, rm, ax[::-1], rng, CLOTH_FA, lumpy=lumpy)
            if state == "Furled":
                r_g = rope_r(Fu_in)
                for k in range(3, ng - 1, max(1, int(round(4 * FT / (Lg_b / ng))))):
                    pc = self.slab_pieces(GHP, GHC, C0[k], ug, dn_g, e2g, -r_g - 3 * IN, r_g + 3 * IN, reach)
                    self.lash(om, secs[k], C0[k], ug, dn_g, e2g, pc, r_g)
                for k in range(2, nm_ - 1, max(1, int(round(4 * FT / (Lm_b / nm_))))):
                    self.gasket(om, np.concatenate([secs_m[k], mast_ring(zm[k])]), EZ, rope_r(Fu_in))
        self.info["spanker"] = {"kind": "spanker", "area_ft2": round(area / FT ** 2, 0),
                                "luff_ft": round(luff_len / FT, 2), "head_ft": round(float(np.linalg.norm(Pk - Th)) / FT, 2),
                                "foot_ft": round(float(np.linalg.norm(Cl - Tk)) / FT, 2),
                                "leech_ft": round(float(np.linalg.norm(Cl - Pk)) / FT, 2),
                                "corners_gaff_frame_m": {k: np.round(v, 3).tolist() for k, v in
                                                         (("throat", Th), ("peak", Pk), ("tack", Tk), ("clew", Cl))},
                                "grid": [nu, nv],
                                "starboard_tack_mirror": {"point_m": [0.0, 0.0, 0.0], "normal": [0.0, 1.0, 0.0],
                                                          "frame": "SpankerGaff"}}

    # ---- shared pieces -------------------------------------------------------------------------------------------------
    @staticmethod
    def polygon_area(flat, lo, hi, n=200):
        """the sail's flat area (m^2), round its outline in UV0"""
        a = np.linspace(lo, hi, n)
        z, o = np.zeros(n), np.ones(n)
        loop = np.concatenate([flat(a, z), flat(o * hi, a * 0 + np.linspace(0, 1, n)), flat(a[::-1], o),
                               flat(o * lo, np.linspace(1, 0, n))])[:, :2]
        x, y = loop[:, 0], loop[:, 1]
        return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2)

    def edge_ropes(self, out, surf, ss, tt, G, r_leech, r_foot, aft, luff=None, clear=None):
        """bolt ropes sewn along the leeches and foot on the cloth's after (square sails, aft=-1: behind the front
        face) or port side (the others), luff=(r, s0) for a fore-and-aft sail's luff rope along s = s0. clear(P), if
        given, is a point's clearance from the spar at the head: a leech rope starts where it clears it by 0.3 in"""
        M = Mesh()
        edges = []
        lo, hi = ss[0], ss[-1]
        if luff is None:
            edges += [(lo, None, r_leech), (hi, None, r_leech)]
        else:
            edges += [(luff[1], None, luff[0]), (hi, None, r_leech)]
        edges.append((None, tt[-1], r_foot))
        for s_fix, t_fix, r in edges:
            if s_fix is not None:
                sv, tv = np.full(len(tt), s_fix), tt
                P = G[0 if s_fix == lo else -1]
            else:
                sv, tv = ss, np.full(len(ss), t_fix)
                P = G[:, -1]
            N = surf.normal(sv, tv)
            Q = P + aft * N * r * 0.9
            if clear is not None and s_fix is not None:
                # from the head down to where it is well clear, every half inch: it starts after the last place it
                # would come within 0.3 in of the spar (its straight runs between the cloth's rows included)
                cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
                sd = np.arange(0.0, cum[-1], 0.5 * IN)
                Qd = np.stack([np.interp(sd, cum, Q[:, i]) for i in range(3)], 1)
                c = clear(Qd) - r - 0.3 * IN
                far = np.flatnonzero(c > 6 * IN)
                bad = np.flatnonzero(c[:far[0] if len(far) else len(c)] <= 0)
                if len(bad):
                    j = min(int(bad[-1]) + 1, len(sd) - 1)
                    Q = np.vstack([Qd[j], Q[np.searchsorted(cum, sd[j], side="right"):]])
            tube(M, Q, r, ROPE)
        out.add_mesh(M)

    def bundle(self, out, cen, T, e1, e2, r, axes, rng, mat, lumpy=1.0, place=None):
        """A roll or heap of cloth along the path cen (n, 3): at each station an oval of semi-axes axes[0] * r along
        e1 and axes[1] * r along e2 (both square to the path's tangent T; each a vector or an (n, 3) array), made lumpy
        by folds, closed at both ends. place(D), if given, takes the rings about their centres (n, m, 3) and returns
        the centres and a scale for each ring. Returns the stations' rings (n, m, 3)."""
        n, m = len(cen), 16
        E1 = np.broadcast_to(e1, (n, 3))
        E2 = np.broadcast_to(e2, (n, 3))
        th = np.linspace(0, 2 * math.pi, m, endpoint=False)
        u = np.linspace(0, 1, n)
        c = rng.uniform(0, 2 * math.pi, 6)
        f = rng.uniform(2.0, 6.0, 3)
        ph1 = 4.0 * np.sin(2 * math.pi * f[0] * u + c[0])
        ph2 = 4.0 * np.sin(2 * math.pi * f[1] * u + c[1])
        amp = 1.0 + 0.5 * np.sin(2 * math.pi * f[2] * u + c[2])
        lump = lumpy * amp[:, None] * (0.07 * np.sin(3 * th[None, :] + ph1[:, None]) +
                                       0.05 * np.sin(5 * th[None, :] + ph2[:, None]) +
                                       0.03 * np.sin(8 * th[None, :] + c[3] + 9 * u[:, None]))
        rr = np.asarray(r, float)[:, None] * (1 + lump)
        D = rr[..., None] * (axes[0] * np.cos(th)[None, :, None] * E1[:, None, :] +
                             axes[1] * np.sin(th)[None, :, None] * E2[:, None, :])
        if place is not None:
            cen, sc = place(D)
            D = D * np.asarray(sc, float)[:, None, None]
            r = np.asarray(r, float) * sc
        P = cen[:, None, :] + D
        along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(cen, axis=0), axis=1))])
        per = 2 * math.pi * float(np.mean(r))
        UV = np.zeros((n, m, 6))
        UV[..., 0] = along[:, None]
        UV[..., 1] = th[None, :] / (2 * math.pi) * per
        UV[..., 2] = (along / max(along[-1], 1e-6))[:, None]
        UV[..., 3] = th[None, :] / (2 * math.pi)
        UV[..., 4] = (along[-1] - along)[:, None]
        V = list(P.reshape(-1, 3)) + [cen[0], cen[-1]]
        U = list(UV.reshape(-1, 6)) + [UV[0, 0], UV[-1, 0]]
        F = []
        for i in range(n - 1):
            for j in range(m):
                a, b = i * m + j, i * m + (j + 1) % m
                F += [(a, b, b + m), (a, b + m, a + m)]
        c0, c1 = n * m, n * m + 1
        for j in range(m):
            F += [(c0, (j + 1) % m, j), (c1, (n - 1) * m + j, (n - 1) * m + (j + 1) % m)]
        # outward: flip if the first face points in
        a, b, cc = V[F[0][0]], V[F[0][1]], V[F[0][2]]
        if np.cross(b - a, cc - a) @ (a - cen[0]) < 0:
            F = [(x, z, y) for x, y, z in F]
        out.add(np.array(V), F, mat, np.array(U))
        return P

    def heap_points(self):
        """everything a heap of cloth on a spar or stay rests on or must clear, as points in the ship's frame: the
        masts', tops' and spars' (built in place) and the standing rigging's edges, every 2 in, with an id for each
        connected part (a spar, a rope, a deadeye)"""
        if not hasattr(self, "_heap_P"):
            P, C, n0 = [], [], 0
            for mesh in [d["mesh"] for d in self.rig.parts_.values() if d["frame"] is None] + \
                    list(self.st.meshes.values()):
                V, F, _ = mesh.arrays()
                if len(V):
                    p, c = edge_points(np.asarray(V, float), F, 2.0 * IN)
                    P.append(p)
                    C.append(c + n0)
                    n0 += int(c.max()) + 1
            self._heap_P, self._heap_C = np.concatenate(P), np.concatenate(C)
        return self._heap_P, self._heap_C

    @staticmethod
    def slab_pieces(P, part, c, along, e1, e2, lo, hi, reach):
        """the points P between lo and hi along `along` from c and within reach of it, on (e1, e2) about c, one set
        for each part they are on, each padded by a quarter inch (a convex hull of a few is never flat)"""
        sv = (P - c) @ along
        m = (sv >= lo) & (sv <= hi)
        Q, pt = P[m] - c, part[m]
        Q = np.stack([Q @ e1, Q @ e2], 1)
        m = np.linalg.norm(Q, axis=1) < reach
        Q, pt = Q[m], pt[m]
        th = np.linspace(0, 2 * math.pi, 6, endpoint=False)
        pad = 0.25 * IN * np.stack([np.cos(th), np.sin(th)], 1)
        return [(Q[pt == i][:, None, :] + pad[None]).reshape(-1, 2) for i in np.unique(pt)]

    @staticmethod
    def rest_on(e1, e2, e_out, D, pieces, gap=0.3 * IN):
        """for each station k of a heap (its rings D (n, m, 3) about their centres), how far from the axis along e_out
        its centre must lie to clear every piece (pieces(k): 2-D points on (e1, e2) about the axis) by twice gap,
        holding none of them; each of e1, e2, e_out a vector or an (n, 3) array"""
        n = len(D)
        E1, E2, Eo = (np.broadcast_to(np.asarray(v, float), (n, 3)) for v in (e1, e2, e_out))
        lam = np.zeros(n)
        for k in range(n):
            D2 = np.stack([D[k] @ E1[k], D[k] @ E2[k]], 1)
            o2 = np.array([Eo[k] @ E1[k], Eo[k] @ E2[k]])
            Q = np.concatenate([D2 + (np.roll(D2, -1, 0) - D2) * w_ for w_ in (0.0, 1 / 3, 2 / 3)])
            cand = np.arange(0.0, 3.0 * np.abs(D2).max() + 1.0, 0.25 * IN)
            okc = np.ones(len(cand), bool)
            hv = []
            for pc in pieces(k):
                H = ConvexHull(pc)
                eq = H.equations
                okc &= (((cand[:, None, None] * o2 + Q[None]) @ eq[:, :2].T + eq[:, 2]).max(-1) >= 2 * gap).all(1)
                hv.append(pc[H.vertices])
            for i in np.flatnonzero(okc):
                ring = cand[i] * o2 + D2
                if not any(inside_poly(h, ring).any() for h in hv):
                    lam[k] = cand[i]
                    break
            else:
                raise RuntimeError(f"a heap finds no rest at station {k}")
        return lam

    def lash(self, out, ring, c, along, e1, e2, pieces, r, gap=0.3 * IN):
        """a gasket round a heap's section ring (m, 3) and what it rests on (c, the spar's or stay's axis there, in
        pieces: 2-D points on (e1, e2) about c), and any other piece it would otherwise pass through"""
        R2 = np.stack([(ring - c) @ e1, (ring - c) @ e2], 1)
        own = [pc for pc in pieces if inside_poly(np.zeros((1, 2)), pc[ConvexHull(pc).vertices])[0] or
               np.linalg.norm(pc, axis=1).min() < 0.5 * IN]
        held = [R2] + own
        rest = [pc for pc in pieces if not any(pc is h for h in own)]
        reach = r + gap + 0.5 * IN
        while True:
            H = ConvexHull(np.concatenate(held))
            eq = H.equations
            add = [pc for pc in rest if ((pc @ eq[:, :2].T + eq[:, 2]).max(-1) < reach).any()]
            if not add:
                break
            held += add
            rest = [pc for pc in rest if not any(pc is a_ for a_ in add)]
        P2 = np.concatenate(held)
        self.gasket(out, c[None] + P2[:, :1] * e1[None] + P2[:, 1:] * e2[None], along, r, gap=gap)

    @staticmethod
    def cringle(out, P_, Gc, nrm, clear, R_c=2.0 * IN, r_c=0.6 * IN, gap=0.3 * IN):
        """a cringle (a rope ring worked into the bolt rope) at a sail's corner P_, in the cloth (axis nrm), moved
        in toward Gc until clear(centre) (its clearance from the stay or spar there) leaves it gap to spare"""
        e = unit(Gc - P_)
        k = R_c
        while k < 14 * IN and clear(P_ + e * k) < R_c + r_c + gap:
            k += 0.25 * IN
        torus(out, P_ + e * k, nrm, R_c, r_c, ROPE, n=8, m=4)

    @staticmethod
    def gasket(out, P3, axis, r, gap=0.3 * IN, tol=0.1 * IN):
        """a rope of radius r round the convex hull of the points P3 (a roll's section and its spar's: see ring()),
        square to axis, gap clear of it all round (the hull pushed out along its normals, rounded at the corners,
        then cut to as few points as keep it within tol of that)"""
        axis = unit(axis)
        a = unit(np.cross(axis, EZ if abs(axis @ EZ) < 0.9 else EX))
        b = np.cross(axis, a)
        c0 = P3.mean(0)
        Q = np.stack([(P3 - c0) @ a, (P3 - c0) @ b], 1)
        H = Q[ConvexHull(Q).vertices]                                 # counter-clockwise
        d = r + gap + tol
        path = []
        for i in range(len(H)):
            e0, e1 = H[i] - H[i - 1], H[(i + 1) % len(H)] - H[i]
            a0, a1 = math.atan2(-e0[0], e0[1]), math.atan2(-e1[0], e1[1])      # the edges' outward normals
            if a1 < a0:
                a1 += 2 * math.pi
            for ang in np.linspace(a0, a1, max(2, int((a1 - a0) / 0.1) + 2)):
                path.append(H[i] + d * np.array([math.cos(ang), math.sin(ang)]))
        path = np.array(path)
        keep, i, n = [0], 0, len(path)
        while True:                                                   # greedy: the longest chords within tol
            j = i + 2
            while j <= n:
                A, B = path[i], path[j % n]
                e = B - A
                m = path[i + 1:j]
                dist = np.abs((m - A) @ np.array([-e[1], e[0]])) / max(np.linalg.norm(e), 1e-12)
                if dist.max() > tol:
                    break
                j += 1
            i = j - 1
            if i >= n:
                break
            keep.append(i)
        if len(keep) < 6:
            keep = list(np.linspace(0, n, 7, endpoint=False).astype(int))
        pts = path[keep]
        P = c0[None] + pts[:, :1] * a[None] + pts[:, 1:] * b[None] + ((P3 - c0) @ axis).mean() * axis
        tube(out, P, r, LINE, n=4, closed=True)                       # out: a Mesh or a SailMesh

    @staticmethod
    def ring(c, e1, e2, r, n=32):
        """points round a circle (centre c, in the plane of e1, e2) whose chords stay outside radius r"""
        th = np.linspace(0, 2 * math.pi, n, endpoint=False)
        rr = r / math.cos(math.pi / n)
        return c[None] + rr * (np.cos(th)[:, None] * e1[None] + np.sin(th)[:, None] * e2[None])

    # ---- all of them ---------------------------------------------------------------------------------------------------
    def build(self, only=None):
        L = self.sp["sail_list"]
        for key in L["square"]:
            if only is None or key in only:
                self.square(key)
        for key in L["headsails"]:
            if only is None or key in only:
                self.fore_and_aft(key, "headsails")
        for key in L["staysails"]:
            if only is None or key in only:
                self.fore_and_aft(key, "staysails")
        if only is None or "spanker" in only:
            self.spanker()
        return self

    def objects(self):
        """name -> (V, F, M, UV (n, 6), frame, parent, sail, state); frame None (in the ship's frame) or (origin, R)"""
        out = {}
        for name, d in self.objs.items():
            V, F, M, U = d["mesh"].arrays()
            out[name] = (V, F, M, U, d["frame"], d["parent"], d["sail"], d["state"])
        return out
