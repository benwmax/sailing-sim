"""The frigate's standing rigging (docs/shipkit-4): the ropes that hold the masts up and never move. The lower shrouds
with their deadeyes, lanyards and chains to the channels; the topmast shrouds set up in the tops with futtock plates
and futtock shrouds; the topgallant shrouds over the topmast crosstrees; the ratlines on all of them, the futtock staves
and catharpins; the topmast, topgallant and royal backstays to the channels; every stay with its hearts and collar; and
the bowsprit's shrouds, martingale stays and back ropes and the jibboom guys.

    from rigging import Standing;  st = Standing(rig, SK).build();  st.parts()

Sizes come from standing_1797.json (each with its source). Units as spars.py: metres in the ship frame (X forward, Y to
starboard, Z up). Nothing here moves, so every piece is built where it stands, as a handful of objects: Rigging_<Mast>
(its shrouds, backstays, futtock shrouds and staves), Ratlines_<Mast>, Deadeyes_<Mast> (deadeyes, lanyards, seizings,
chains and plates), Stays (every stay with its hearts and collars) and Rigging_Bowsprit. Build the rig (spars.Rig) and
the skin (skin.Skin) first: the shrouds land on the skin's channels, the stays on the spars.

How a shroud is laid: its eye goes over the masthead on the bolsters (pairs of shrouds share an eye; the eyes are laid
foremost pair first, starboard then port, so each side's eyes stack alternately), its leg comes down over the bolster and
the trestletree's edge as a taut line would, and at its foot it is turned in round the upper deadeye, which is set up to
the lower deadeye on the channel with a lanyard rove through their three holes. The lower deadeye's iron strop runs down
as the chain, two long links and a preventer plate bolted to the side. Each mast's deadeyes keep the 1817 draught's count
and order along the channel, moved the least it takes to stand clear of the spar deck ports (Standing.report lists the
moves). Stays come down the masthead's fore face in front of the shrouds' eyes and turn forward under the next mast's
heel.
"""
import contextlib
import json
import math
import os

import numpy as np
from scipy.spatial import ConvexHull, cKDTree

import loft
from spars import Mesh, box, frame_ring, loft_solid, ring_band, unit

HERE = os.path.dirname(os.path.abspath(__file__))
FT = loft.FT
IN = FT / 12.0
EX, EY, EZ = np.eye(3)
MI = {"fore": 0, "main": 1, "mizzen": 2}
EYE_GAP = 0.1 * IN                     # between eyes stacked over a masthead
SHADOW = "Shadow"                      # the deadeyes' and hearts' holes (a near-black material)
CLEAR = 1.5 * IN                       # the least room between a squared yard and the rigging it hangs among
PORT_COST = 30.0                       # channel_places: a lanyard's foot across a port costs as much as moving 5.5 ft


# ---- rope pieces ---------------------------------------------------------------------------------------------------
def rope_r(circ_in):
    """A rope's radius (m) from its circumference in inches, as rope was sized then."""
    return circ_in / math.pi / 2.0 * IN


def nsides(r):
    d = 2 * r / IN
    return 12 if d > 4.0 else 10 if d > 2.2 else 8 if d > 1.2 else 6


class Side:
    """A mesh seen from one side: pieces built on the starboard side go in as they are (sgn 1) or mirrored to port."""

    def __init__(self, mesh, sgn):
        self.mesh, self.sgn = mesh, sgn

    def add(self, V, F, mat):
        if self.sgn > 0:
            self.mesh.add(V, F, mat)
        else:
            self.mesh.add(np.asarray(V, float) * np.array([1.0, -1.0, 1.0]), [tuple(f[::-1]) for f in F], mat)


def dedupe(P, eps=2e-4):
    out = [P[0]]
    for p in P[1:]:
        if np.linalg.norm(p - out[-1]) > eps:
            out.append(p)
    return np.array(out)


def fillet(P, rad, step_deg=40.0):
    """Round each inner corner of a polyline with a curve of about radius rad (each corner takes at most 0.45 of the
    segments on either side, so neighbouring corners never overlap)."""
    P = dedupe(np.asarray(P, float))
    if len(P) < 3:
        return P
    out = [P[0]]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        t0, t1 = unit(b - a), unit(c - b)
        ang = math.acos(float(np.clip(t0 @ t1, -1.0, 1.0)))
        if ang < math.radians(2.0):
            out.append(b)
            continue
        tl = min(rad * math.tan(min(ang, math.radians(170)) / 2), 0.45 * np.linalg.norm(b - a), 0.45 * np.linalg.norm(c - b))
        p0, p2 = b - t0 * tl, b + t1 * tl
        k = max(2, int(math.ceil(math.degrees(ang) / step_deg)))
        for j in range(k + 1):
            t = j / k
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p2)
    out.append(P[-1])
    return dedupe(np.array(out))


def tube(mesh, P, r, mat, n=None, closed=False, caps=True, A0=None):
    """A rope of radius r along the polyline P (rotation-minimising frames); closed makes a loop."""
    P = dedupe(np.asarray(P, float))
    if closed and np.linalg.norm(P[0] - P[-1]) < 2e-4:
        P = P[:-1]
    n = n or nsides(r)
    m = len(P)
    if closed:
        T = np.array([unit(P[(i + 1) % m] - P[i - 1]) for i in range(m)])
    else:
        T = np.empty_like(P)
        T[0], T[-1] = unit(P[1] - P[0]), unit(P[-1] - P[-2])
        for i in range(1, m - 1):
            T[i] = unit(unit(P[i] - P[i - 1]) + unit(P[i + 1] - P[i]))
    if A0 is None:
        A0 = EZ if abs(T[0] @ EZ) < 0.9 else EX
    A = np.empty_like(P)
    A[0] = unit(A0 - (A0 @ T[0]) * T[0])
    for i in range(1, m):
        a = A[i - 1] - (A[i - 1] @ T[i]) * T[i]
        nn = np.linalg.norm(a)
        A[i] = a / nn if nn > 1e-6 else unit(np.cross(T[i], np.cross(A[i - 1], T[i])) + 1e-9)
    if closed:                                     # spread the frame's twist round the loop so it closes
        a = unit(A[-1] - (A[-1] @ T[0]) * T[0])
        ang = math.atan2(float(np.cross(A[0], a) @ T[0]), float(A[0] @ a))
        for i in range(m):
            th = -ang * i / m
            A[i] = math.cos(th) * A[i] + math.sin(th) * np.cross(T[i], A[i])
    B = np.cross(T, A)
    t = np.arange(n) * 2 * math.pi / n
    dirs = np.cos(t)[None, :, None] * A[:, None, :] + np.sin(t)[None, :, None] * B[:, None, :]
    for i in (range(m) if closed else range(1, m - 1)):    # mitre the corners: the ring keeps the rope's girth
        t0, t1 = unit(P[i] - P[i - 1]), unit(P[(i + 1) % m] - P[i])
        c = float(t0 @ t1)
        if c < 0.9995:
            k = unit(t1 - t0)
            sc = min(1.0 / math.sqrt((1.0 + c) / 2.0), 2.0) - 1.0
            dirs[i] += sc * (dirs[i] @ k)[:, None] * k[None, :]
    R = P[:, None, :] + r * dirs
    if closed:
        F = []
        for j in range(m):
            a_, b_ = j * n, ((j + 1) % m) * n
            for i in range(n):
                i1 = (i + 1) % n
                F.append((a_ + i, a_ + i1, b_ + i1, b_ + i))
        mesh.add(R.reshape(-1, 3), F, mat)
    else:
        loft_solid(mesh, list(R), mat, caps, caps)


def hoop(mesh, c, u, a, P2, broad, thick, mat):
    """A band of rectangular section round the outline P2 (counter-clockwise in a, u x a), centred at c, broad along
    u: a seizing round two ropes, a strap round a spar."""
    from spars import Rig
    b = np.cross(u, a)
    Pi = np.asarray(P2, float)
    Po = Rig.offset_outline(Pi, -thick)
    loops = [(Pi, -broad / 2), (Po, -broad / 2), (Po, broad / 2), (Pi, broad / 2)]
    rings = [frame_ring(c + z * u, a, b, PP) for PP, z in loops]
    n, m = len(Pi), len(rings)
    V = np.concatenate(rings)
    F = []
    for j in range(m):
        p, q = j * n, ((j + 1) % m) * n
        for i in range(n):
            i1 = (i + 1) % n
            F.append((p + i, p + i1, q + i1, q + i))
    mesh.add(V, F, mat)


def stadium(h, rad, k=5):
    """The outline round two ropes side by side (centres at +-h on the first axis), counter-clockwise."""
    pts = []
    for th in np.linspace(-math.pi / 2, math.pi / 2, k):
        pts.append((h + rad * math.cos(th), rad * math.sin(th)))
    for th in np.linspace(math.pi / 2, 3 * math.pi / 2, k):
        pts.append((-h + rad * math.cos(th), rad * math.sin(th)))
    return np.array(pts)


def deadeye(mesh, C, Xl, Yl, Zl, D, holes, wood, n=16, sy=1.0, h=0.275, hole_r=0.072, hole_at=0.24):
    """A deadeye (or, with sy < 1 and one big hole, a heart): turned round its face normal Zl, diameter D along Xl
    (sy of it along Yl), thickness 2h D, a groove round its edge for the strop, dark discs for its holes at the angles
    in holes (from Xl toward Yl). (Xl, Yl, Zl) must be right-handed."""
    prof = [(0.40, h), (0.5, h - 0.07), (0.5, 0.09), (0.45, 0.06), (0.45, -0.06), (0.5, -0.09), (0.5, -h + 0.07),
            (0.40, -h)]
    a = np.arange(n) * 2 * math.pi / n
    rad = np.cos(a)[:, None] * Xl[None, :] + sy * np.sin(a)[:, None] * Yl[None, :]
    V = [C + D * rho * rad + D * z * Zl for rho, z in prof]
    m = len(prof)
    V = np.concatenate(V)
    F = []
    for j in range(m - 1):
        for i in range(n):
            i1 = (i + 1) % n
            F.append((j * n + i, (j + 1) * n + i, (j + 1) * n + i1, j * n + i1))
    ct, cb = len(V), len(V) + 1
    V = np.vstack([V, C + D * h * Zl, C - D * h * Zl])
    F += [(ct, i, (i + 1) % n) for i in range(n)]
    F += [(cb, (m - 1) * n + (i + 1) % n, (m - 1) * n + i) for i in range(n)]
    mesh.add(V, F, wood)
    k = 8
    t = np.arange(k) * 2 * math.pi / k
    for ang in holes:
        hc = C + D * hole_at * (math.cos(ang) * Xl + sy * math.sin(ang) * Yl)
        for sgn in (1, -1):
            c0 = hc + sgn * (D * h + 0.002) * Zl
            ring = c0 + D * hole_r * (np.cos(t)[:, None] * Xl + sy * np.sin(t)[:, None] * Yl)
            Vh = np.vstack([ring, c0])
            Fh = [(k, i, (i + 1) % k) if sgn > 0 else (k, (i + 1) % k, i) for i in range(k)]
            mesh.add(Vh, Fh, SHADOW)


def hex_bolt(mesh, c, nrm, rad, height, mat):
    """A bolt head standing on a surface (its axis the surface's normal)."""
    a = unit(np.cross(nrm, EZ if abs(nrm @ EZ) < 0.9 else EX))
    b = np.cross(nrm, a)
    from spars import circle
    P2 = circle(rad, 6)
    loft_solid(mesh, [frame_ring(c, a, b, P2), frame_ring(c + height * nrm, a, b, P2 * 0.8)], mat)


def wrap2d(E, T, circles, n=24):
    """The taut line from E to T laid over circles (centre, radius) that stand on its left side: the hull's chain from E
    clockwise to T, with the circles' arcs as sampled points."""
    if not circles:
        return np.array([E, T], float)
    pts = [np.asarray(E, float), np.asarray(T, float)]
    for c, rad in circles:
        a = np.arange(n) * 2 * math.pi / n
        pts += list(np.asarray(c, float)[None, :] + rad * np.stack([np.cos(a), np.sin(a)], 1))
    P = np.array(pts)
    hv = list(ConvexHull(P).vertices)                      # counter-clockwise
    if 0 not in hv or 1 not in hv:
        return P[[0, 1]]
    i = hv.index(0)
    chain = []
    while True:
        chain.append(hv[i])
        if hv[i] == 1:
            break
        i = (i - 1) % len(hv)
    return P[chain]


def outside_path(cs, Ts, rs, r_x):
    """A rope of radius r_x laid level across lines (points cs on them at one height, fore to aft; their directions Ts,
    radii rs) on their outside (+y), straight between them, touching those that stand out and bridging those set in:
    its points, and on each line the point where it is seized (where it bears, or the corner over a line set in). Worked
    in plan at that height, with each line's section there (an ellipse, as the lines lean) taken as its long radius."""
    z = float(np.mean([c[2] for c in cs]))
    C = np.array([[c[0], c[1]] for c in cs], float)
    R = max((r + r_x) / max(abs(T[2]), 0.3) for r, T in zip(rs, Ts)) + 0.02 * IN
    ns, ds = [], []
    for k in range(len(C) - 1):
        d = unit(np.append(C[k + 1] - C[k], 0.0))[:2]
        nk = np.array([-d[1], d[0]])
        ns.append(nk if nk[1] >= 0 else -nk)
        ds.append(d)
    path = [C[0] + R * ns[0]]
    touch = [path[0]]
    for k in range(1, len(C) - 1):
        a, b = ns[k - 1], ns[k]
        if a @ ds[k] < 0:                                   # bends away from the outside: round the line
            t0, t1 = math.atan2(a[1], a[0]), math.atan2(b[1], b[0])
            dt = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi
            m = max(2, int(abs(dt) / 0.2) + 1)
            path += [C[k] + R * np.array([math.cos(t0 + dt * q / m), math.sin(t0 + dt * q / m)]) for q in range(m + 1)]
            touch.append(C[k] + R * unit(np.append(a + b, 0.0))[:2])
        else:                                               # bends toward it: the corner, clear of the line
            pm = C[k] + R * (a + b) / (1.0 + a @ b)
            path.append(pm)
            touch.append(pm)
    path.append(C[-1] + R * ns[-1])
    touch.append(path[-1])
    to3 = lambda q: np.array([q[0], q[1], z])
    return [to3(q) for q in path], [to3(q) for q in touch]


def point_at_z(Pa, Pb, z):
    """The point on the line through Pa and Pb at height z."""
    t = (z - Pa[2]) / (Pb[2] - Pa[2])
    return Pa + t * (Pb - Pa)


def pt_seg(p, a, b):
    """Distance from a point to a segment."""
    ab = b - a
    t = float(np.clip((p - a) @ ab / max(ab @ ab, 1e-12), 0.0, 1.0))
    return float(np.linalg.norm(a + t * ab - p))


def seg_dist(p0, p1, q0, q1):
    """Least distance between two segments (the closest points, clamped in turn)."""
    u, v, w = p1 - p0, q1 - q0, p0 - q0
    a, b, c, d, e = u @ u, u @ v, v @ v, u @ w, v @ w
    den = a * c - b * b
    s = float(np.clip((b * e - c * d) / den, 0.0, 1.0)) if den > 1e-12 else 0.0
    t = (b * s + e) / c if c > 1e-12 else 0.0
    if t < 0.0 or t > 1.0:
        t = float(np.clip(t, 0.0, 1.0))
        s = float(np.clip((t * b - d) / a, 0.0, 1.0)) if a > 1e-12 else 0.0
    return float(np.linalg.norm(p0 + s * u - q0 - t * v))


# ---- the yards the rigging must clear --------------------------------------------------------------------------------
class YardShape:
    """A moving spar (spars.Rig.parts_ and .meta) as points spread over its surface (about every 15 mm), so a rope's
    room from it can be measured at any hoist (0 lowered, 1 hoisted), squared."""

    def __init__(self, rig, pname, h=0.015):
        V, F, _ = rig.parts_[pname]["mesh"].arrays()
        V = np.asarray(V, float)
        self.o, self.Rm = rig.parts_[pname]["frame"]
        m = rig.meta[pname]
        self.ax, self.low = np.asarray(m["axis"], float), float(m["hoist_m"][0])
        T = np.array([(f[0], f[k], f[k + 1]) for f in F for k in range(1, len(f) - 1)], int)
        A, E1, E2 = V[T[:, 0]], V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]
        n1 = np.ceil(np.linalg.norm(E1, axis=1) / h).astype(int) + 1
        n2 = np.ceil(np.linalg.norm(E2, axis=1) / h).astype(int) + 1
        pts = [V]
        for a, b in set(zip(n1.tolist(), n2.tolist())):
            sel = (n1 == a) & (n2 == b)
            i, j = np.meshgrid(np.arange(a + 1) / a, np.arange(b + 1) / b)
            keep = i + j <= 1.0 + 1e-9
            u_, v_ = i[keep], j[keep]
            pts.append((A[sel, None, :] + u_[None, :, None] * E1[sel, None, :] + v_[None, :, None] * E2[sel, None, :])
                       .reshape(-1, 3))
        self.tree = cKDTree(np.concatenate(pts))

    def clearance(self, P, r, h=1.0):
        """The least room (m) between a rope of radius r along the polyline P and the yard at hoist h."""
        oh = self.o + self.ax * (1.0 - h) * self.low
        Q = (np.asarray(P, float) - oh) @ self.Rm
        Q = np.concatenate([a + np.linspace(0, 1, max(2, int(np.linalg.norm(b - a) / 0.004) + 1))[:, None] * (b - a)
                            for a, b in zip(Q[:-1], Q[1:])])
        return float(self.tree.query(Q)[0].min()) - r


def solve_back(clear, x0, step=1.0 * IN, tries=6):
    """The largest x <= x0 at which clear(x) >= CLEAR (the room grows as x moves aft): secant steps from x0."""
    x, c = x0, clear(x0)
    for _ in range(tries):
        if c >= CLEAR:
            return x
        c1 = clear(x - step)
        dc = (c1 - c) / step
        x = x - (CLEAR - c) / dc - 0.05 * IN if dc > 1e-6 else x - 2 * step
        c = clear(x)
    return x


# ---- the standing rigging ------------------------------------------------------------------------------------------
class Standing:
    def __init__(self, rig, SK, path=os.path.join(HERE, "standing_1797.json")):
        self.rig, self.SK, self.L, self.pr = rig, SK, rig.L, SK.pr
        self.sp = json.load(open(path))
        p = self.sp["paint"]
        self.ROPE, self.LAN, self.WOOD, self.IRON = p["rope"], p["lanyard"], p["wood"], p["iron"]
        self.meshes = {}
        self.top = {}                    # head -> next free height (along its mast) for an eye
        self.stack = {}                  # head -> [(height, radius)] of the eyes laid over it
        self.spans = []                  # the free straight runs: (name, a, b, radius), for the checks
        self.paths = []                  # a leg's points from its eye to its upper deadeye: (set, mast, points, r)
        self.report = {"channels": {}, "skipped": [], "deadeyes": 0, "hearts": 0}
        self.shroud_lines = {}           # (mast, set, side) -> [(top, bottom, r)] fore to aft
        self.stave = {}                  # (mast, side) -> [point on each lower shroud's outside at the stave]
        self.tm_lines = {}
        self.chan_x = {}
        self.yards = {}
        self.fan = {}                    # leg (mast, head, x_slot, s_e, r) -> (x, y, s) where it leaves the bundle
        self.laid = {}                   # leg (mast, head, side, s_e, ("x", slot) or ("az", azimuth)) -> (r, its points)

    def yard(self, pname):
        if pname not in self.yards:
            self.yards[pname] = YardShape(self.rig, pname)
        return self.yards[pname]

    def mesh(self, name):
        return self.meshes.setdefault(name, Mesh())

    def r_of(self, key, mast):
        return rope_r(self.sp["rope_in"][key][MI[mast]])

    def span(self, name, a, b, r):
        self.spans.append((name, np.asarray(a, float).copy(), np.asarray(b, float).copy(), r))

    # ---- the hull: channels, rail, side --------------------------------------------------------------------------
    def x_px(self, x_ft):
        return self.L.mid_px + x_ft * self.L.ppf

    def channel_edge(self, name, x_ft):
        """The channel's outer top edge at x (ft) and the side's outward horizontal normal there."""
        pr, SK = self.pr, self.SK
        ch = self.SK.sp["channels"]
        X = np.array([self.x_px(x_ft)])
        zt = pr.channel_top(name, X)
        zb = zt - ch["thick_in"] * pr.pxin
        Ot, Nt = SK.surf(X, zt)
        _, Nb = SK.surf(X, zb)
        h = 0.5 * (Nt[0] + Nb[0])
        h[2] = 0.0
        h = unit(h)
        return Ot[0] + h * ch[f"{name}_out_ft"] * FT, h

    def hull_at(self, x_ft, z_ft):
        """A point on the planking's outside (starboard) and its normal."""
        P, N = self.SK.surf(np.array([self.x_px(x_ft)]), np.array([z_ft * self.L.ppf_y]))
        return P[0], N[0]

    def rail_top_ft(self, x_ft):
        return self.rig.rail_ft(x_ft) + self.rig.rail_cap_ft

    def stem_head_x(self):
        """The stem head's after and fore faces at its top (m forward of midships)."""
        P = np.array(loft.backbone_outline(self.L))
        xs = P[np.abs(P[:, 1] - self.L.fwd_branch[-1][1]) < 1e-6][:, 0]
        return tuple(float((x - self.L.mid_px) / self.L.ppf * FT) for x in (xs.min(), xs.max()))

    def port_head_ft(self, x_ft, margin_ft):
        """The head (ft) of a gun deck port under x, or None."""
        pr = self.pr
        for a, f, _, _ in pr.gun:
            xa, xf = (a - self.L.mid_px) / self.L.ppf, (f - self.L.mid_px) / self.L.ppf
            if xa - margin_ft <= x_ft <= xf + margin_ft:
                return float(pr.Shd(np.array([self.x_px(x_ft)]))[0]) / self.L.ppf_y
        return None

    # ---- where each deadeye stands on its channel -----------------------------------------------------------------
    @staticmethod
    def draught_ft(xd, reg):
        return ((xd - reg["x_offset"]) / reg["x_scale"] - reg["mid_px"]) / reg["ppf"]

    def channel_places(self, mast):
        """x (ft) of each deadeye on the mast's channel: the draught's, in its order (aft to fore: royal backstay,
        topgallant backstay, topmast backstays, shrouds), each moved the least (a dynamic programme on a 0.02 ft grid)
        so that neighbours stand clear of each other both on the channel (their lower deadeyes) and at the rail (their
        upper deadeyes with the rope turned in round them), no lower deadeye stands in front of a spar deck port, and as
        little as may be of a lanyard leaning toward its masthead across a port's height (each foot of that costs as
        much as moving the deadeye PORT_COST ** 0.5 ft: the channels are too short to keep every lanyard clear of the
        1927 plan's ports). Standing.report lists the moves and what still crosses a port."""
        if mast in self.chan_x:
            return self.chan_x[mast]
        S = self.sp["masts"][mast]
        reg = dict(self.rig.sp["registration"], mid_px=self.L.mid_px, ppf=self.L.ppf)
        de, rp = self.sp["deadeyes"], self.sp["rope_in"]
        i = MI[mast]
        m = self.rig.masts[mast]
        bx = [self.draught_ft(x, reg) for x in S["backstay_x_draught"]]
        sx = [self.draught_ft(x, reg) for x in S["shroud_x_draught"]]
        th = self.sp["thimbles"]
        royal = m["Otg"] + (m["s_pole"] - self.sp["topgallant"]["royal_eyes_below_truck_in"] * IN) * m["u"]
        heads = {"shroud": m["O"] + m["s_tt1"] * m["u"], "topmast_backstay": m["Otm"] + m["s_tt2b"] * m["u"],
                 "topgallant_backstay": m["Otg"] + m["s_stop"] * m["u"], "royal_backstay": royal}
        # each item: name, draught x (ft), lower fitting's diameter, upper fitting's diameter, rope radius (in), head
        items = [("royal_backstay", bx[0] - 1.6, 0.0, th["diam_in"], rp["royal_backstays"][i], "royal_backstay"),
                 ("topgallant_backstay", bx[0] - 0.95, 0.0, th["diam_in"], rp["topgallant_backstays"][i],
                  "topgallant_backstay")]
        items += [(f"topmast_backstay_{k}", x, de["backstay"][i], de["backstay"][i], rp["topmast_backstays"][i],
                   "topmast_backstay") for k, x in enumerate(bx)]
        items += [(f"shroud_{k}", x, de["lower"][i], de["lower"][i], rp["shrouds"][i], "shroud") for k, x in enumerate(sx)]
        xa_px, xf_px, _, _ = self.pr.channels[mast]
        lo, hi = (xa_px - self.L.mid_px) / self.L.ppf + 1 / 12, (xf_px - self.L.mid_px) / self.L.ppf - 1 / 12
        mid = 0.5 * (lo + hi)
        z_ch = float(self.channel_edge(mast, mid)[0][2]) / FT
        z_rail = self.rail_top_ft(mid)
        ports = []
        for a, f in self.pr.spar:
            X = np.array([0.5 * (a + f)])
            ports.append(((a - self.L.mid_px) / self.L.ppf, (f - self.L.mid_px) / self.L.ppf,
                          float(self.pr.Ssp(X)[0]) / self.L.ppf_y, float(self.pr.H(X)[0]) / self.L.ppf_y))
        margin, gap, step = 0.15, 2.5 / 12, 0.02
        grid = np.arange(lo, hi + 1e-9, step)
        INF = 1e18
        geo = []
        for name, t, Dl_in, Du_in, circ, hk in items:
            xh, zh = heads[hk][0] / FT, heads[hk][2] / FT
            slope = (xh - grid) / (zh - z_ch)                       # dx/dz of the rope rising from the channel
            r_in = circ / math.pi / 2
            if Dl_in > 0:                                            # deadeyes: the lower on the channel, the upper at the rail
                zL, zU = z_ch + Dl_in / 24 + 1 / 24, z_rail
                wL, wU, wlan = Dl_in / 24 + 0.2 / 12, (0.45 * Du_in + 2 * r_in + 0.1) / 12, 0.3 * Du_in / 12
            else:                                                    # a thimble on a short lanyard to an eyebolt
                zL = zU = z_ch + (2.8 + th["lanyard_ft"] * 12 + Du_in / 2) / 12
                wL, wU, wlan = 1.5 / 12, (0.45 * Du_in + 2 * r_in + 0.1) / 12, r_in / 12
            ok = (grid >= lo + wL) & (grid <= hi - wL)
            pen = np.zeros_like(grid)
            for a, b, z0, z1 in ports:
                zs = np.linspace(max(z0, z_ch), z1, 9)
                over = np.zeros_like(grid)
                for z in zs:
                    w = wL if z <= zL + wL else wU if abs(z - zU) <= wU else wlan
                    xc = grid + slope * (z - z_ch)
                    o = np.clip(np.minimum(xc + w, b + margin) - np.maximum(xc - w, a - margin), 0.0, None)
                    q = 0.25 * (b - a)                                    # a port's middle half is the gun's: never
                    ok &= ~((xc + w > a + q) & (xc - w < b - q))
                    over = np.maximum(over, o)
                pen += over
            xu = grid + slope * (zU - z_ch)
            geo.append((ok, xu, wL, wU, np.sqrt(1 + slope ** 2), pen))
        prev, backs = None, []
        for k, (name, t, _, _, _, _) in enumerate(items):
            ok, xu, wL, wU, sec, pen = geo[k]
            cost = np.where(ok, (grid - t) ** 2 + PORT_COST * pen, INF)
            if prev is None:
                tot, back = cost, None
            else:
                _, xu0, wL0, wU0, _, _ = geo[k - 1]
                # the previous one's index may be at most: its lower deadeye clear of this one's, and its upper fitting
                # clear of this one's (measured square to the ropes)
                i_low = np.arange(len(grid)) - int(math.ceil((wL0 + wL + gap) / step - 1e-9))
                i_up = np.searchsorted(xu0, xu - (wU0 + wU + gap) * sec, side="right") - 1
                imax = np.minimum(i_low, i_up)
                pm = np.minimum.accumulate(prev)
                pa = np.zeros(len(prev), int)
                for j in range(1, len(prev)):
                    pa[j] = j if prev[j] < pm[j - 1] else pa[j - 1]
                tot = np.full_like(cost, INF)
                back = np.zeros(len(cost), int)
                v = imax >= 0
                tot[v] = cost[v] + pm[imax[v]]
                back[v] = pa[imax[v]]
            backs.append(back)
            prev = tot
        j = int(np.argmin(prev))
        if prev[j] >= INF:
            raise ValueError(f"the {mast} channel has no room for its deadeyes")
        idx = [j]
        for back in backs[:0:-1]:
            j = int(back[j])
            idx.append(j)
        xs = grid[idx[::-1]]
        out = {it[0]: float(x) for it, x in zip(items, xs)}
        for it, j, g in zip(items, idx[::-1], geo):
            if g[5][j] > 0.05 / 12:
                self.report["skipped"].append(f"{mast} channel: the {it[0].replace('_', ' ')}'s lanyard crosses a spar "
                                              f"deck port's edge by {g[5][j] * 12:.1f} in")
        # (the thimbles' backstays have no deadeyes on the draught: their x is only where they were sought, abaft the
        # topmast backstays)
        self.report["channels"][mast] = {
            it[0]: ({"draught_ft": round(it[1], 2), "model_ft": round(float(x), 2), "moved_ft": round(float(x) - it[1], 2)}
                    if it[2] > 0 else {"draught_ft": None, "sought_ft": round(it[1], 2), "model_ft": round(float(x), 2)})
            for it, x in zip(items, xs)}
        self.chan_x[mast] = out
        return out

    # ---- eyes over a masthead ---------------------------------------------------------------------------------------
    def head(self, mast, level):
        """A masthead's frame and fittings: level lower, topmast, stop (the topgallant mast's) or royal (the pole's)."""
        m = self.rig.masts[mast]
        u, f = m["u"], m["f"]
        if level == "lower":
            s0, s1 = m["s_h"], m["s_top"]
            return dict(O=m["O"], u=u, f=f, kind="square", hs=lambda s: m["hs"] * (1 - 0.04 * (s - s0) / (s1 - s0)),
                        base=max(m["s_tt1"] + 2 * m["bolster_r"], m["s_ct1"] + 0.1 * IN),
                        bolster=((m["hs"] + m["tt_b"] / 2, m["s_tt1"] + m["bolster_r"]), m["bolster_r"], m["bolster_x"]),
                        corner=(m["hs"] + m["tt_b"], m["s_tt1"]),
                        slots=(-1.1 * m["hs"], m["bolster_x"][1]),
                        crosstrees=(list(m["ct_xs"]), m["ct_b"] / 2, m["s_tt1"], m["s_ct1"]))
        if level == "topmast":
            s0, s1 = m["s_tmh"], m["s_tm_top"]
            return dict(O=m["Otm"], u=u, f=f, kind="square",
                        hs=lambda s: m["hs_tm"] * (1 - 0.04 * (s - s0) / (s1 - s0)),
                        base=m["s_tt2b"] + m["ct2_d"] + 0.1 * IN, bolster=None,
                        corner=(m["hs_tm"] + m["tt2_b"], m["s_tt2b"]),
                        slots=(-m["hs_tm"] - 0.02, m["off_tg"] - m["fid_tg"] / 2 - 0.25 * IN),
                        crosstrees=(list(m["ct2_xs"]), m["ct2_b"] / 2, m["s_tt2b"], m["s_tt2b"] + m["ct2_d"]))
        if level == "stop":
            return dict(O=m["Otg"], u=u, f=f, kind="round", R=lambda s: m["R_tg"](s), base=m["s_stop"])
        return dict(O=m["Otg"], u=u, f=f, kind="round", R=lambda s: m["R_tg"](s),
                    base=m["s_pole"] - self.sp["topgallant"]["royal_eyes_below_truck_in"] * IN)

    def eye(self, mast, level, r):
        """Lay an eye of a rope of radius r over the head (on top of those already there): its height."""
        key = (mast, level)
        if key not in self.top:
            self.top[key] = self.head(mast, level)["base"]
            self.stack[key] = []
        s = self.top[key] + r
        self.top[key] = s + r + EYE_GAP
        self.stack[key].append((s, r))
        return s

    def eye_loop(self, mesh, mast, level, s, r, mat=None):
        """The eye's loop round the head at height s, as points."""
        H = self.head(mast, level)
        O, u, f = H["O"], H["u"], H["f"]
        c = O + s * u
        if H["kind"] == "square":
            hs = H["hs"](s)
            pts = []
            for q, (cx, cy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
                for th in np.linspace(q * math.pi / 2, (q + 1) * math.pi / 2, 3):
                    pts.append(c + (cx * hs + r * math.cos(th)) * f + (cy * hs + r * math.sin(th)) * EY)
        else:
            R = H["R"](s)
            pts = [c + (R + r) * (math.cos(th) * f + math.sin(th) * EY) for th in np.arange(16) * 2 * math.pi / 16]
        if mesh is not None:
            tube(mesh, pts, r, mat or self.ROPE, n=max(6, nsides(r) - 2 if nsides(r) > 8 else nsides(r)), closed=True)
        return pts

    def slots(self, mast, level, ws, x_max=None):
        """x (along the mast's fore-and-aft axis f) of each leg leaving a square head, fore to aft, each leg's width
        ws[k] apart, centred on the head as near as its fittings allow (the after crosstree aft, the bolster's or the
        trestletree's end and the fid forward) and the foremost no further forward than x_max (to clear a yard)."""
        H = self.head(mast, level)
        lo, hi = H["slots"]
        lo, hi = lo + ws[-1] / 2 + 0.1 * IN, hi - ws[0] / 2 - 0.1 * IN
        if x_max is not None:
            hi = min(hi, x_max)
        gaps = [(ws[k] + ws[k + 1]) / 2 for k in range(len(ws) - 1)]
        span = sum(gaps)
        if span > hi - lo:
            sc = (hi - lo) / span
            gaps = [g * sc for g in gaps]
            span = hi - lo
            self.report["skipped"].append(f"{mast} {level} head: legs packed {sc:.2f} of their width")
        x_hi = min(hi, max(lo + span, span / 2))
        out = [x_hi]
        for g in gaps:
            out.append(out[-1] - g)
        return out

    def head_leg(self, mast, level, x_slot, s_e, r, target, plan=False):
        """A leg from its eye at height s_e on a square head down over the bolster (lower masts) and the trestletree's
        outer edge, as a taut rope lies, toward target: 3D points from the eye to where it leaves the last edge, or
        (plan) to where it leaves the head, before it meets the crosstrees or the legs beside it."""
        H = self.head(mast, level)
        O, u, f = H["O"], H["u"], H["f"]
        hs = H["hs"](s_e)
        rel = target - O
        T2 = np.array([rel @ EY, rel @ u])
        E2 = np.array([hs + r, s_e])
        x_E = float(np.clip(x_slot, -hs, hs))
        circles = []
        if H["bolster"] is not None:
            c, rb, (bx0, bx1) = H["bolster"]
            if bx0 - 1e-6 <= x_slot <= bx1 + 1e-6:
                circles.append((c, rb + r + 0.05 * IN))
        circles.append((H["corner"], r + 0.1 * IN))
        for sc, re in self.stack.get((mast, level), []):
            if sc < s_e - 1e-6:
                circles.append(((H["hs"](sc) + re, sc), re + r + 0.05 * IN))
        chain = wrap2d(E2, T2, circles)[:-1]
        if len(chain) < 2:
            chain = np.array([E2, E2 + 0.01 * unit(T2 - E2)])
        d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(chain, axis=0), axis=1))])
        fr = d / d[-1] if d[-1] > 0 else np.ones_like(d)
        xs = x_E + (x_slot - x_E) * fr
        pts = [O + s * u + x * f + y * EY for (y, s), x in zip(chain, xs)]
        if plan:
            return pts
        # a leg the bundle holds (plan_fan) leaves it under the crosstrees
        F = self.fan.get((mast, level, round(float(x_slot), 5), round(float(s_e), 5), round(float(r), 6)))
        if F is not None:
            pts.append(O + F[2] * u + F[0] * f + F[1] * EY)
            return pts
        # any other leg leaving above the crosstrees' underside that would run on into a crosstree as it leads fore or
        # aft bears on that crosstree's lower edge instead (it passes under it)
        xcs, hb, s_bot, s_top = H["crosstrees"]
        P = pts[-1]
        d = np.asarray(target, float) - P
        sP, ds = float((P - O) @ u), float(d @ u)
        if sP > s_bot - r and ds < 0:
            W = P + d * (s_bot - r - 0.25 * IN - sP) / ds
            xW = float((W - O) @ f)
            for xc in xcs:
                if min(x_slot, xW) - r < xc + hb and max(x_slot, xW) + r > xc - hb:
                    face = xc + hb if xc < x_slot else xc - hb
                    x_b = face + (r + 0.1 * IN) * (1 if xc < x_slot else -1)
                    pts.append(O + (s_bot - r - 0.1 * IN) * u + x_b * f + float(W[1]) * EY)
                    break
        return pts

    def lay(self, mast, level, side, s_e, key, r, pts, target):
        """Register a leg's first points (its chain and its first 2 ft on toward target), for the legs of the eyes laid
        over it to lie over it."""
        a = pts[-1]
        run = unit(np.asarray(target, float) - a)
        self.laid[(mast, level, side, round(float(s_e), 5), key)] = (r, list(pts) + [a + run * k * 0.5 * IN
                                                                                    for k in range(1, 49)])

    def laid_circles(self, mast, level, side, s_e, r, E2, radial, lateral, O, u):
        """The legs of the eyes under s_e on this head and side, as circles in a leg's plane (radial(q), q @ u for q from
        O): where a leg passes within its and their radii (lateral(q) across the plane) of one, it lies over it."""
        out = []
        for (m_, lv_, sd_, s_l, _), (r_l, P) in self.laid.items():
            if (m_, lv_, sd_) != (mast, level, side) or s_l >= s_e - 1e-4:
                continue
            need = r_l + r + 0.05 * IN
            for p in P:
                q = p - O
                off = lateral(q)
                if off < need:
                    cq = np.array([radial(q), q @ u])
                    rad = math.sqrt(need ** 2 - off ** 2)
                    if np.linalg.norm(cq - E2) > rad:
                        out.append((cq, rad))
        return out

    def eyes_ahead(self, mast, level, rs):
        """The heights the next eyes of ropes of radii rs (in the order they will be laid) will take on a head."""
        top = self.top.get((mast, level), self.head(mast, level)["base"])
        out = []
        for r in rs:
            out.append(top + r)
            top += 2 * r + EYE_GAP
        return out

    @contextlib.contextmanager
    def eyes_laid(self, mast, level, eyes):
        """For a plan: the head as it will be once eyes [(height, radius)] are laid on it (as they are, after)."""
        key = (mast, level)
        saved = self.stack.get(key)
        self.stack[key] = list(saved or []) + list(eyes)
        try:
            yield
        finally:
            if saved is None:
                del self.stack[key]
            else:
                self.stack[key] = saved

    def plan_fan(self, mast, level, legs):
        """The legs of one side of a square head (x_slot, s_e, r, target), as they come down it side by side: below the
        trestletrees each leads off toward its own target, but one that would run into the after crosstree is held in
        front of it, and one that would come against or cross the leg abaft it (in their order on the head) is held in
        front of that leg, as the bundle lies; and a leg from a higher eye that would come against one from a lower
        (on a crowded head) lies outside it. Where such a leg leaves the bundle, under the crosstrees, goes into
        self.fan; the rest lead straight off the head."""
        H = self.head(mast, level)
        O, u, f = H["O"], H["u"], H["f"]
        xcs, hb, s_bot, s_top = H["crosstrees"]
        nat, Ps = [], []
        for x_slot, s_e, r, T in legs:
            P = self.head_leg(mast, level, x_slot, s_e, r, T, plan=True)[-1]
            Ps.append(P)
            d = np.asarray(T, float) - P
            sP, ds = float((P - O) @ u), float(d @ u)
            s_b = s_bot - r - 0.1 * IN
            if ds >= 0 or sP <= s_b:
                nat.append(None)
                continue
            W = P + d * (s_b - sP) / ds
            xW = float((W - O) @ f)
            lb = -np.inf
            for xc in xcs:
                if xc < x_slot and min(x_slot, xW) - r < xc + hb and max(x_slot, xW) + r > xc - hb:
                    lb = max(lb, xc + hb + r + 0.1 * IN)
            nat.append((xW, float(W[1]), s_b, lb))
        F = {}
        for i in sorted(range(len(legs)), key=lambda k: legs[k][0]):          # aft first
            if nat[i] is None:
                continue
            x = max(nat[i][0], nat[i][3])
            for j, Fj in F.items():
                need = 1.1 * (legs[i][2] + legs[j][2]) + 0.15 * IN       # (worked level: the legs lean)
                dy = nat[i][1] - nat[j][1]
                if abs(dy) < need:                                         # (no wider than on the head)
                    x = max(x, Fj[0] + min(math.sqrt(need ** 2 - dy ** 2), legs[i][0] - legs[j][0]))
            F[i] = [x, nat[i][1], nat[i][2]]
        # then each pair, from the head (for one eye's two legs, from 6 in under it, where they part) to 3 ft past the
        # bundle: the leg from the higher eye (of one eye's two, the after) moves out until clear, by 14 in at most
        at = lambda i: O + F[i][2] * u + F[i][0] * f + F[i][1] * EY
        y0 = {i: F[i][1] for i in F}
        for _ in range(400):
            worst, wi = 0.0, None
            ids = sorted(F)
            for a_ in range(len(ids)):
                for b_ in range(a_ + 1, len(ids)):
                    i, j = ids[a_], ids[b_]
                    one = abs(legs[i][1] - legs[j][1]) < 1e-4
                    need = legs[i][2] + legs[j][2] + 0.15 * IN
                    segs = []
                    for k in (i, j):
                        Fk = at(k)
                        P0 = Ps[k] + unit(Fk - Ps[k]) * min(6 * IN, 0.5 * np.linalg.norm(Fk - Ps[k])) if one else Ps[k]
                        segs.append(((P0, Fk), (Fk, Fk + unit(np.asarray(legs[k][3], float) - Fk) * 3 * FT)))
                    dmin = min(seg_dist(p0, p1, q0, q1) for p0, p1 in segs[0] for q0, q1 in segs[1])
                    k = (i if legs[i][0] > legs[j][0] else j) if one else (i if legs[i][1] > legs[j][1] else j)
                    if need - dmin > worst + 1e-9 and F[k][1] - y0[k] < 14 * IN:
                        worst, wi = need - dmin, k
            if wi is None or worst < 0.02 * IN:
                break
            F[wi][1] += min(worst + 0.05 * IN, 1.0 * IN)
        held = 0
        for i, Fi in F.items():
            if Fi[0] > nat[i][0] + 0.05 * IN or Fi[1] > nat[i][1] + 0.05 * IN:
                x_slot, s_e, r, T = legs[i]
                self.fan[(mast, level, round(float(x_slot), 5), round(float(s_e), 5), round(float(r), 6))] = tuple(Fi)
                held += 1
        return held

    def round_leg(self, mast, level, s_e, r, target, side=0):
        """A leg leaving its eye round a pole toward target, from the eye's point facing it, down over the eyes laid
        under it, and the legs of those eyes on its side (side, 1 or -1, worked to starboard; 0 for a stay), as a taut
        rope lies: points from the eye to where it leaves the last."""
        H = self.head(mast, level)
        O, u = H["O"], H["u"]
        c = O + s_e * u
        d = target - c
        d = unit(d - (d @ u) * u)
        rel = np.asarray(target, float) - O
        E2 = np.array([H["R"](s_e) + r, s_e])
        circles = [((H["R"](sc) + re, sc), re + r + 0.05 * IN) for sc, re in self.stack.get((mast, level), [])
                   if sc < s_e - 1e-6]
        if side:
            lat = np.cross(u, d)
            circles += self.laid_circles(mast, level, side, s_e, r, E2, lambda q: q @ d, lambda q: abs(q @ lat), O, u)
        chain = wrap2d(E2, np.array([rel @ d, rel @ u]), circles)[:-1]
        pts = [O + s * u + y * d for y, s in chain]
        if side:
            self.lay(mast, level, side, s_e, ("az", round(math.atan2(d[1], d[0]), 1)), r, pts, target)
        return pts

    # ---- deadeyes, hearts, lanyards ---------------------------------------------------------------------------------
    def turnin(self, fit, C, Xl, Yl, Zl, D, r, sy=1.0, throat=1.15, end=1.6, seize=True):
        """A rope turned in round a deadeye's (or heart's) groove: points from the standing part's end at the throat
        (Xl points from the deadeye toward it), round the groove and back up alongside to the end; seizings on fit."""
        rx, ry = 0.45 * D + r, 0.45 * sy * D + r
        d = throat * D
        Q = C + Xl * d
        ph = np.linspace(0.02, math.pi / 2, 400)
        G = np.stack([rx * np.cos(ph), ry * np.sin(ph)], 1)
        dG = np.stack([-rx * np.sin(ph), ry * np.cos(ph)], 1)
        cr = (G[:, 0] - d) * dG[:, 1] - (G[:, 1] - r) * dG[:, 0]
        k = int(np.argmin(np.abs(cr)))
        p0 = ph[k]
        arc = [C + rx * math.cos(a) * Xl + ry * math.sin(a) * Yl for a in np.linspace(p0, 2 * math.pi - p0, 11)]
        pts = [Q + r * Yl] + arc + [Q - r * Yl, Q - r * Yl + Xl * end * D]
        if seize:
            for kk in (0.2, min(1.1, end - 0.15)):
                hoop(fit, Q + Xl * kk * D, Xl, Yl, stadium(r, r + 0.05 * IN, 4), 1.4 * r, 0.25 * r + 0.1 * IN, self.ROPE)
        return Q + r * Yl, pts

    def lanyard(self, fit, CU, CL, Xl, Yl, Zl, Du, Dl, r):
        """The lanyard rove through a pair of deadeyes' three holes (alternately out and in, knotted behind the upper
        deadeye's first hole), its end taken up behind the upper deadeye."""
        hu, hl = 0.275 * Du + r, 0.275 * Dl + r
        U = lambda a: CU + 0.24 * Du * (math.cos(a) * Xl + math.sin(a) * Yl)
        Lw = lambda a: CL + 0.24 * Dl * (math.cos(a) * Xl + math.sin(a) * Yl)
        pts = []
        for k, (fn, a, hh) in enumerate(((U, 120, hu), (Lw, 60, hl), (U, 0, hu), (Lw, 180, hl), (U, 240, hu), (Lw, 300, hl))):
            c = fn(math.radians(a))
            s0 = -1 if k % 2 == 0 else 1
            pts += [c + s0 * hh * Zl, c - s0 * hh * Zl]
        pts += [CU - (0.5 * Du + r) * Yl - hu * Zl - 0.15 * Du * Xl, CU - (0.5 * Du + r) * Yl - hu * Zl + 0.35 * Du * Xl,
                CU + 0.75 * Du * Xl - 2 * r * Yl - hu * Zl]
        tube(fit, pts, r, self.LAN, n=6)
        c = U(math.radians(120))
        tube(fit, [c - (hu + 0.4 * r) * Zl, c - (hu + 2.0 * r) * Zl], 1.7 * r, self.LAN, n=6)

    def deadeye_pair(self, fit, CL, CU, Zout, Du, Dl, r_lan):
        """Two deadeyes on one line (the upper at CU) and their lanyard; the frame (Xl up the line, Yl, Zl out)."""
        Xl = unit(CU - CL)
        Zl = unit(Zout - (Zout @ Xl) * Xl)
        Yl = np.cross(Zl, Xl)
        nU = 14 if Du > 15 * IN else 12
        nL = 14 if Dl > 15 * IN else 12
        deadeye(fit, CU, Xl, Yl, Zl, Du, [math.radians(a) for a in (0, 120, 240)], self.WOOD, nU)
        deadeye(fit, CL, Xl, Yl, Zl, Dl, [math.radians(a) for a in (180, 60, 300)], self.WOOD, nL)
        self.report["deadeyes"] += 2
        self.lanyard(fit, CU, CL, Xl, Yl, Zl, Du, Dl, r_lan)
        return Xl, Yl, Zl

    def heart_pair(self, fit, rope, A, t, a, b, Lh, r_stay, r_col, Zout, name="", collar=None):
        """Two hearts on a stay's line from its anchor A (t up the stay): the lower at a, the upper at b along it (or
        further, so the turn-ins' crowns stand a third of a heart apart for the lanyard); the collar's leg turned in
        round the lower from below (its end seized back on it short of the collar, at collar if not at A), the
        lanyard's turns between them, the stay turned in round the upper. Returns the stay's end (at the upper heart's
        throat) and the collar leg's points from A."""
        b = max(b, a + 0.9 * Lh + 2 * (r_stay + r_col) + 0.3 * Lh)
        Zl = unit(Zout - (Zout @ t) * t)
        Yl = np.cross(Zl, t)
        CL, CU = A + a * t, A + b * t
        r_lan = rope_r(self.sp["rope_in"]["lanyard_of_rope"] * r_stay / IN * 2 * math.pi)
        hole = max(0.2, (6 * r_lan + 0.4 * IN) / (2 * Lh))         # the heart's hole takes the lanyard's three turns
        for C in (CL, CU):
            deadeye(fit, C, t, Yl, Zl, Lh, [0.0], self.WOOD, 16, sy=0.85, h=0.25, hole_r=hole, hole_at=0.0)
        self.report["hearts"] += 2
        self.report.setdefault("heart_at", {})[name] = (CU.copy(), CL.copy())
        # the lanyard: turns round the upper heart's lower crown and the lower heart's upper crown, side by side
        rho = 0.25 * Lh + r_lan
        cu, cl = CU - t * 0.3 * Lh, CL + t * 0.3 * Lh
        for k in range(3):
            yk = (k - 1) * (2 * r_lan + 0.05 * IN)
            loop = [cu + yk * Yl + rho * (math.cos(th) * Zl + math.sin(th) * t) for th in np.linspace(0, math.pi, 7)]
            loop += [cl + yk * Yl + rho * (math.cos(th) * Zl + math.sin(th) * t) for th in np.linspace(math.pi, 2 * math.pi, 7)]
            tube(fit, loop, r_lan, self.LAN, n=6, closed=True)
        end, pts_u = self.turnin(fit, CU, t, Yl, Zl, Lh, r_stay, sy=0.85, throat=1.0, end=1.4)
        reach = float(np.linalg.norm(np.asarray(A if collar is None else collar, float) - (CL - t * Lh)))
        tail = min(1.4, max(0.35, (reach - 3 * r_col) / Lh))
        _, pts_l = self.turnin(fit, CL, -t, -Yl, Zl, Lh, r_col, sy=0.85, throat=1.0, end=tail)
        return end, pts_u, pts_l

    # ---- chains ---------------------------------------------------------------------------------------------------
    def chain(self, fit, mast, C_L, Xl, Zl, D, x_ft, slope, bar_in):
        """The lower deadeye's strop and chain: an iron strop in its groove, two long links down toward the side and a
        preventer plate bolted to the planking 5 ft under the channel (or over a gun deck port's head), in line with
        the shroud seen from the side."""
        I = self.IRON
        lw = self.sp["lower"]
        rb = bar_in * IN / 2
        ring_band(fit, C_L, Zl, Xl, 0.0, 0.45 * D, 0.1 * D, 1.2 * rb, I, 16)
        S_b = C_L - Xl * (0.45 * D + 1.2 * rb + rb)
        z_ch = C_L[2] / FT - 0.5 * D / FT
        z_B = z_ch - lw["chain_below_channel_ft"]
        x_B = x_ft - slope * (C_L[2] / FT - z_B)
        head = self.port_head_ft(x_B, 0.3)
        if head is not None and z_B < head + 0.3:
            z_B = head + 0.3
            x_B = x_ft - slope * (C_L[2] / FT - z_B)
        lp = min(1.3, 0.35 * (z_ch - z_B))
        B, nB = self.hull_at(x_B, z_B)
        P2, n2 = self.hull_at(x_B + slope * lp, z_B + lp)
        pt = 0.6 * IN
        # the plate lies flat over the planking's thickest strake under it (a wale stands proud of the strakes by it)
        sh = 0.0
        for fr in np.linspace(0.0, 1.0 + 2.2 * IN / (lp * FT), 9):
            for dx in (-1.6 * IN, 0.0, 1.6 * IN):
                Q = self.hull_at(x_B + slope * lp * fr + dx / FT, z_B + lp * fr)[0]
                sh = max(sh, float((Q - (B + (P2 - B) * fr)) @ nB))
        Bo, P2o = B + nB * (pt / 2 + sh), P2 + n2 * (pt / 2 + sh)
        a = 1.1 * 2 * rb
        # the links hang clear of the planking up to the channel, where the side swells over the wales: the plate's top
        # stands off as far as that takes (the upper link lies square to the side, the lower along it)
        off = n2 * max(0.0, rb + 0.05 * IN - pt / 2)          # the lower link's end through the plate's eye, clear behind
        top = P2o + unit(P2o - Bo) * 1.2 * IN + off
        nl = 2 if float(np.linalg.norm(S_b - top)) > 1.2 * FT else 1
        lift = 0.0
        for fr in np.linspace(0.0, 0.9, 13):
            p = top + (S_b - top) * fr
            Q, nQ = self.hull_at(p[0] / FT, p[2] / FT)
            need = (a if (nl == 1 or fr > 0.5) else 0.0) + rb + 0.1 * IN
            lift = max(lift, (need - float((p - Q) @ nQ)) / (1.0 - fr))
        P2o = P2o + n2 * min(lift, 2.0 * IN)
        up = unit(P2o - Bo)
        wd = unit(np.cross(nB, up))
        box(fit, 0.5 * (Bo + P2o) + up * 1.0 * IN, up, wd, np.cross(up, wd), np.linalg.norm(P2o - Bo) / 2 + 1.0 * IN,
            1.5 * IN, pt / 2, I)
        for fr in (0.15, 0.55):
            hex_bolt(fit, Bo + (P2o - Bo) * fr + nB * pt / 2, nB, 0.9 * IN, 0.5 * IN, I)
        top = P2o + up * 1.2 * IN + off
        dist = float(np.linalg.norm(S_b - top))
        uc = unit(top - S_b)
        side1 = unit(Zl - (Zl @ uc) * uc)
        nl = 2 if dist > 1.2 * FT else 1
        Hh =(dist + 2 * rb * (nl - 1)) / (2 * nl)
        for k in range(nl):
            c = S_b + uc * (Hh + k * (2 * Hh - 2 * rb))
            v = side1 if k % 2 == 0 else unit(np.cross(uc, side1))
            hl = Hh - a
            loop = [c - uc * hl + a * (math.cos(th) * v - math.sin(th) * uc) for th in np.linspace(0, math.pi, 6)]
            loop += [c + uc * hl + a * (math.cos(th) * v - math.sin(th) * uc) for th in np.linspace(math.pi, 2 * math.pi, 6)]
            tube(fit, loop, rb, I, n=6, closed=True)
        return S_b, top

    # ---- one leg to a channel: shroud or backstay ------------------------------------------------------------------
    def channel_leg(self, mast, sgn, x_ft, D_u, D_l, r, head_fn, set_name, chain_in):
        """A rope from a masthead (head_fn(target) gives its points from the eye) set up to the channel at x (ft):
        both deadeyes, the lanyard, the turn-in, the strop and chain (or, with D_u None, a thimble and a lanyard to an
        eyebolt in the channel). Returns the top and bottom of its straight part and the upper deadeye's centre."""
        Mn = mast.capitalize()
        rope, fit = Side(self.mesh(f"Rigging_{Mn}"), sgn), Side(self.mesh(f"Deadeyes_{Mn}"), sgn)
        edge, hside = self.channel_edge(mast, x_ft)
        if D_u is None:
            return self.thimble_leg(rope, fit, mast, sgn, edge, hside, r, head_fn, set_name, x_ft)
        hp, Mt, t, C_L, C_U = self.channel_geom(mast, x_ft, D_u, D_l, r, head_fn)
        self.paths.append((set_name, mast, [np.asarray(p) * [1, sgn, 1] for p in hp + [C_U]], r))
        Xl, Yl, Zl = self.deadeye_pair(fit, C_L, C_U, hside, D_u, D_l, rope_r(self.sp["rope_in"]["lanyard_of_rope"] * r / IN * 2 * math.pi))
        end, tp = self.turnin(fit, C_U, Xl, Yl, Zl, D_u, r)
        tube(rope, fillet(hp + tp, 2.0 * r), r, self.ROPE)
        slope = (Mt[0] - C_L[0]) / (Mt[2] - C_L[2])
        self.chain(fit, mast, C_L, Xl, Zl, D_l, C_L[0] / FT, slope, chain_in)
        nm = f"{set_name} {mast} {'stbd' if sgn > 0 else 'port'} at {x_ft:.1f} ft"
        self.span(nm, *(np.array([Mt, end]) * [1, sgn, 1]), r)
        return Mt, end, C_U

    def channel_geom(self, mast, x_ft, D_u, D_l, r, head_fn):
        """Where a rope set up to the channel at x (ft) with deadeyes lies (the upper deadeye at the rail's top, the
        lower on the channel): its head part, the top of its straight part, its direction and the deadeyes' centres."""
        edge, hside = self.channel_edge(mast, x_ft)
        target = edge + EZ * 20 * FT
        for _ in range(3):
            hp = head_fn(target)
            Mt = hp[-1]
            t = unit(Mt - edge)
            Zl = unit(hside - (hside @ t) * t)
            Yl = np.cross(Zl, t)
            # the lower deadeye's lowest point (its rim's, on its inner face) half an inch over the channel's top
            drop = D_l / 2 * math.sqrt(max(0.0, 1.0 - Zl[2] ** 2)) + 0.275 * D_l * abs(Zl[2])
            C_L = edge + t * ((drop + 0.5 * IN) / t[2])
            z_u = self.rail_top_ft(C_L[0] / FT) * FT
            C_U = C_L + t * max((z_u - C_L[2]) / t[2], 1.5 * (D_l + D_u) / 2 + 0.6 * D_u)
            target = C_U + t * 1.15 * D_u + r * Yl
        return hp, Mt, t, C_L, C_U

    def thimble_leg(self, rope, fit, mast, sgn, edge, hside, r, head_fn, set_name, x_ft):
        """A small backstay's foot: turned in round an iron thimble, set up with a lanyard of three turns to an eyebolt
        in the channel's top by its outer edge."""
        th = self.sp["thimbles"]
        Dt = th["diam_in"] * IN
        P = edge - hside * 2.0 * IN
        target = P + EZ * 20 * FT
        for _ in range(2):
            hp = head_fn(target)
            Mt = hp[-1]
            t = unit(Mt - P)
            eye = P + EZ * 2.8 * IN                               # the eyebolt's eye's top (eyebolt below)
            C = eye + t * (th["lanyard_ft"] * FT + Dt / 2)
            Zl = unit(hside - (hside @ t) * t)
            Yl = np.cross(Zl, t)
            target = C + t * 1.15 * Dt + r * Yl
        self.eyebolt(fit, P, EZ, t, self.IRON)
        ring_band(fit, C, Zl, t, 0.0, 0.42 * Dt, 0.22 * Dt, 0.12 * Dt, self.IRON, 10)
        end, tp = self.turnin(fit, C, t, Yl, Zl, Dt, r)
        tube(rope, fillet(hp + tp, 2.0 * r), r, self.ROPE)
        r_lan = rope_r(self.sp["rope_in"]["lanyard_of_rope"] * r / IN * 2 * math.pi)
        cu, cl = C - t * 0.42 * Dt, eye - t * 0.6 * IN
        rho = 0.12 * Dt + r_lan
        for k in range(3):
            yk = (k - 1) * (2 * r_lan + 0.05 * IN)
            loop = [cu + yk * Yl + rho * (math.cos(a) * Zl + math.sin(a) * t) for a in np.linspace(0, math.pi, 6)]
            loop += [cl + yk * Yl + rho * (math.cos(a) * Zl + math.sin(a) * t) for a in np.linspace(math.pi, 2 * math.pi, 6)]
            tube(fit, loop, r_lan, self.LAN, n=6, closed=True)
        self.span(f"{set_name} {mast} {'stbd' if sgn > 0 else 'port'} at {x_ft:.1f} ft", *(np.array([Mt, end]) * [1, sgn, 1]), r)
        return Mt, end, C

    # ---- lower shrouds -----------------------------------------------------------------------------------------------
    def lower_shrouds(self, mast):
        S, i = self.sp, MI[mast]
        n = S["masts"][mast]["shrouds"]
        r = self.r_of("shrouds", mast)
        D = S["deadeyes"]["lower"][i] * IN
        places = self.channel_places(mast)
        xs = [places[f"shroud_{k}"] for k in range(n)][::-1]          # fore to aft
        w = 2 * r + 0.15 * IN
        slots = self.slots(mast, "lower", [w] * n)
        # the foremost leg clears the lower yard, squared, by CLEAR: the legs move aft on the bolster (packed closer if
        # they must). Its eye is the first or second laid (starboard, then port)
        yd = self.yard({"fore": "Yard_Fore", "main": "Yard_Main", "mizzen": "Yard_Crossjack"}[mast])
        base = self.head(mast, "lower")["base"]

        def clear(x0):
            c = np.inf
            for s_e in (base + r, base + 3 * r + EYE_GAP):
                fn = lambda tg, s_e=s_e: self.head_leg(mast, "lower", x0, s_e, r, tg)
                hp, Mt, t, C_L, C_U = self.channel_geom(mast, xs[0], D, D, r, fn)
                c = min(c, yd.clearance(hp + [C_U + t * 1.15 * D], r, 1.0))
            return c
        x0 = solve_back(clear, slots[0])
        if x0 < slots[0] - 1e-6:
            slots = self.slots(mast, "lower", [w] * n, x_max=x0)
            self.report["skipped"].append(f"{mast} lower head: the foremost leg leaves {x0 / IN:.1f} in before the "
                                          f"mast's axis, clearing the lower yard by {clear(slots[0]) / IN:.1f} in")
        # how the legs lie down the head, side by side (each side's eyes alternate: starboard, then port)
        np_ = (n + 1) // 2
        s_all = self.eyes_ahead(mast, "lower", [r] * (2 * np_))
        with self.eyes_laid(mast, "lower", [(s, r) for s in s_all]):
            for q, sgn in enumerate((1, -1)):
                legs = []
                for j in range(n):
                    s_e = s_all[2 * (j // 2) + q]
                    fn = lambda tg, j=j, s_e=s_e: self.head_leg(mast, "lower", slots[j], s_e, r, tg, plan=True)
                    hp, Mt, t, C_L, C_U = self.channel_geom(mast, xs[j], D, D, r, fn)
                    legs.append((slots[j], s_e, r, C_U + t * 1.15 * D))
                held = self.plan_fan(mast, "lower", legs)
                if held and sgn > 0:
                    self.report["skipped"].append(f"{mast} lower head: {held} leg{'s' if held > 1 else ''} held in the bundle down the head "
                                                  f"to under the crosstrees (the after crosstree or the leg abaft)")
        lines = {1: [None] * n, -1: [None] * n}
        bar = max(0.6, 0.3 * 2 * r / IN)
        for p in range((n + 1) // 2):
            legs = [j for j in (2 * p, 2 * p + 1) if j < n]
            for sgn in (1, -1):
                s_e = self.eye(mast, "lower", r)
                self.eye_loop(Side(self.mesh(f"Rigging_{mast.capitalize()}"), sgn), mast, "lower", s_e, r)
                for j in legs:
                    fn = lambda tg, j=j, s_e=s_e: self.head_leg(mast, "lower", slots[j], s_e, r, tg)
                    Mt, end, C_U = self.channel_leg(mast, sgn, xs[j], D, D, r, fn, "lower shroud", bar)
                    lines[sgn][j] = (Mt, end, r, C_U)
        for sgn in (1, -1):
            self.shroud_lines[(mast, "lower", sgn)] = lines[sgn]

    # ---- ratlines ----------------------------------------------------------------------------------------------------
    def ratlines(self, mesh, lines, z0, z1, pitch, r_rat, every=5, skip_last=True):
        """Ratlines across lines [(top, bottom, r, ...)] (fore to aft, starboard side) from z0 up to z1 at pitch: on the
        lines' outside, straight between them (seized to each); every fifth to the aftmost line."""
        rows = 0
        z = z0
        k = 0
        while z <= z1 + 1e-9:
            nu = len(lines) if (not skip_last or k % every == 0) else len(lines) - 1
            if nu >= 2:
                cs = [point_at_z(ln[1], ln[0], z) for ln in lines[:nu]]
                pts, _ = outside_path(cs, [unit(ln[0] - ln[1]) for ln in lines[:nu]], [ln[2] for ln in lines[:nu]], r_rat)
                tube(mesh, pts, r_rat, self.ROPE, n=5)
                rows += 1
            k += 1
            z += pitch
        return rows

    def lower_ratlines_and_stave(self, mast):
        """The lower shrouds' ratlines, the futtock stave across them and the catharpins under it."""
        S, i, m = self.sp, MI[mast], self.rig.masts[mast]
        lw = S["lower"]
        z_top = (m["O"] + m["s_plat"] * m["u"])[2]
        z_st = z_top - lw["futtock_stave_below_top_ft"][i] * FT
        r_rat = rope_r(S["rope_in"]["ratlines"]["lower"])
        r_st = lw["futtock_stave_diam_in"][i] / 2 * IN
        Mn = mast.capitalize()
        for sgn in (1, -1):
            lines = self.shroud_lines[(mast, "lower", sgn)]
            z0 = max(ln[3][2] for ln in lines) + 2.9 * S["deadeyes"]["lower"][i] * IN + 0.3 * FT
            self.ratlines(Side(self.mesh(f"Ratlines_{Mn}"), sgn), lines, z0, z_st - 0.7 * FT,
                          lw["ratline_pitch_in"] * IN, r_rat)
            cs = [point_at_z(ln[1], ln[0], z_st) for ln in lines]
            stave, touch = outside_path(cs, [unit(ln[0] - ln[1]) for ln in lines], [ln[2] for ln in lines], r_st)
            ext = [stave[0] + unit(stave[0] - stave[1]) * 3 * IN] + stave + [stave[-1] + unit(stave[-1] - stave[-2]) * 3 * IN]
            tube(Side(self.mesh(f"Rigging_{Mn}"), sgn), ext, r_st, self.ROPE, n=8)
            self.stave[(mast, sgn)] = (touch, r_st)
        # catharpins: across under the stave, aft of the mast, from each of the aftmost shrouds to its fellow
        r_c = self.r_of("catharpins", mast)
        lines = self.shroud_lines[(mast, "lower", 1)]
        O, u = m["O"], m["u"]
        z_c = z_st - 0.5 * FT
        for k in range(lw["catharpins"][i]):
            ln = lines[-1 - k]
            Pt, Pb, rs = ln[0], ln[1], ln[2]
            p = point_at_z(Pb, Pt, z_c)
            T = unit(Pt - Pb)
            nrm = unit(EY - (EY @ T) * T)
            a = p - nrm * (rs + r_c)
            b = a * np.array([1, -1, 1])
            # clear of the mast?
            c = 0.5 * (a + b)
            s = (c - O) @ u
            d = np.linalg.norm((c - O) - s * u)
            if d < m["R_lower"](s) + r_c + 1.0 * IN or (c - O) @ m["f"] > 0:
                self.report["skipped"].append(f"{mast} catharpin {k}: would not clear the mast")
                continue
            tube(Side(self.mesh(f"Rigging_{Mn}"), 1), [a, b], r_c, self.ROPE)
            self.span(f"catharpin {mast} {k}", a, b, r_c)

    # ---- topmast shrouds, futtock shrouds ---------------------------------------------------------------------------
    def rim_geom(self, mast, x, x_slot, s_e, r, D, plan=False):
        """Where a topmast shroud from its eye at s_e (its leg leaving the head at x_slot) to a deadeye on the top's
        rim at x (along the mast, from its axis) lies: its head part, the top of its straight part, its direction, the
        deadeyes' centres, the rim point and the rim's outward normal."""
        from spars import Rig
        m, tmc = self.rig.masts[mast], self.sp["topmast"]
        O, u, f = m["O"], m["u"], m["f"]
        hw = Rig.top_half_width(m["outline"], x)
        dh = (Rig.top_half_width(m["outline"], x + 0.05) - Rig.top_half_width(m["outline"], x - 0.05)) / 0.1
        nout = unit(-dh * f + EY)
        R3 = O + (m["s_plat"] + 1.0 * IN) * u + x * f + (hw + 0.6 * IN) * EY
        target = R3 + u * 30 * FT
        for _ in range(3):
            hp = self.head_leg(mast, "topmast", x_slot, s_e, r, target, plan)
            Mt = hp[-1]
            t = unit(Mt - R3)
            C_L = R3 + t * (D / 2 + 1.2 * IN)
            C_U = C_L + t * tmc["lanyard_ft"] * FT
            Zl = unit(nout - (nout @ t) * t)
            Yl = np.cross(Zl, t)
            target = C_U + t * 1.15 * D + r * Yl
        return hp, Mt, t, C_L, C_U, R3, nout

    def topmast_rigging(self, mast):
        """Topmast shrouds from their eyes on the topmast head to deadeyes on the top's rim, the futtock plates under
        the rim and the futtock shrouds down to the stave; then the topmast backstays' eyes and legs to the channel."""
        S, i, m = self.sp, MI[mast], self.rig.masts[mast]
        n = S["masts"][mast]["topmast_shrouds"]
        nb = S["masts"][mast]["topmast_backstays"]
        r = self.r_of("topmast_shrouds", mast)
        rb = self.r_of("topmast_backstays", mast)
        D = S["deadeyes"]["topmast"][i] * IN
        Db = S["deadeyes"]["backstay"][i] * IN
        tmc = S["topmast"]
        O, u = m["O"], m["u"]
        fa, Lt = m["fa"], m["Lt"]
        rim = lambda a, b: [fa + (a + (b - a) * k / max(n - 1, 1)) * Lt for k in range(n)][::-1]  # fore to aft
        xr = rim(tmc["rim_from"], tmc["rim_to"])
        ws = [2 * r + 0.15 * IN] * n + [2 * rb + 0.15 * IN] * nb
        slots = self.slots(mast, "topmast", ws)
        Mn = mast.capitalize()
        # the foremost shroud clears the topsail yard, squared, from lowered to hoisted by CLEAR: its deadeye moves aft
        # on the rim for the lowered yard (the rest keep their spacing), its leg aft on the head for the hoisted
        yd = self.yard(f"Yard_{Mn}Topsail")
        base = self.head(mast, "topmast")["base"]

        def room(x_rim, x_slot, hoists):
            c = np.inf
            for s_e in (base + r, base + 3 * r + EYE_GAP):
                hp, Mt, t, C_L, C_U, R3, nout = self.rim_geom(mast, x_rim, x_slot, s_e, r, D)
                c = min(c, min(yd.clearance(hp + [C_U + t * 1.15 * D], r, h) for h in hoists))
            return c
        x_slot = solve_back(lambda x: room(xr[0], x, (0.75, 1.0)), slots[0])
        x_rim = solve_back(lambda x: room(x, x_slot, (0.0, 0.25, 0.5)), xr[0])
        x_slot = solve_back(lambda x: room(x_rim, x, (0.75, 1.0)), x_slot)
        if x_rim < xr[0] - 1e-6:
            to = (x_rim - fa) / Lt
            xr = rim(tmc["rim_from"], to)
            self.report["skipped"].append(f"{mast} top: the topmast shrouds' deadeyes end {to:.3f} of the top's "
                                          f"length from its after edge (the draught's {tmc['rim_to']}) to clear the "
                                          f"topsail yard lowered")
        if x_slot < slots[0] - 1e-6:
            slots = self.slots(mast, "topmast", ws, x_max=x_slot)
            self.report["skipped"].append(f"{mast} topmast head: the foremost leg leaves {x_slot / IN:.1f} in before "
                                          f"the topmast's axis to clear the topsail yard hoisted")
        # how the shrouds' and backstays' legs lie down the head, side by side
        places = self.channel_places(mast)
        bxs = [places[f"topmast_backstay_{k}"] for k in range(nb)][::-1]       # fore to aft
        ns_, nb_ = (n + 1) // 2, (nb + 1) // 2
        rs_all = [r] * (2 * ns_) + [rb] * (2 * nb_)
        s_all = self.eyes_ahead(mast, "topmast", rs_all)
        with self.eyes_laid(mast, "topmast", list(zip(s_all, rs_all))):
            for q, sgn in enumerate((1, -1)):
                legs = []
                for j in range(n):
                    s_e = s_all[2 * (j // 2) + q]
                    hp, Mt, t, C_L, C_U, R3, nout = self.rim_geom(mast, xr[j], slots[j], s_e, r, D, plan=True)
                    legs.append((slots[j], s_e, r, C_U + t * 1.15 * D))
                for k in range(nb):
                    s_e = s_all[2 * ns_ + 2 * (k // 2) + q]
                    fn = lambda tg, k=k, s_e=s_e: self.head_leg(mast, "topmast", slots[n + k], s_e, rb, tg, plan=True)
                    hp, Mt, t, C_L, C_U = self.channel_geom(mast, bxs[k], Db, Db, rb, fn)
                    legs.append((slots[n + k], s_e, rb, C_U + t * 1.15 * Db))
                held = self.plan_fan(mast, "topmast", legs)
                if held and sgn > 0:
                    self.report["skipped"].append(f"{mast} topmast head: {held} leg{'s' if held > 1 else ''} held in the bundle down the "
                                                  f"head to under the crosstrees (the after crosstree or the leg abaft)")
        lines = {1: [None] * n, -1: [None] * n}
        r_lan = rope_r(S["rope_in"]["lanyard_of_rope"] * r / IN * 2 * math.pi)
        r_fut = self.r_of("futtock_shrouds", mast)
        for p in range((n + 1) // 2):
            legs = [j for j in (2 * p, 2 * p + 1) if j < n]
            for sgn in (1, -1):
                rope, fit = Side(self.mesh(f"Rigging_{Mn}"), sgn), Side(self.mesh(f"Deadeyes_{Mn}"), sgn)
                s_e = self.eye(mast, "topmast", r)
                self.eye_loop(rope, mast, "topmast", s_e, r)
                for j in legs:
                    hp, Mt, t, C_L, C_U, R3, nout = self.rim_geom(mast, xr[j], slots[j], s_e, r, D)
                    Xl, Yl, Zl = self.deadeye_pair(fit, C_L, C_U, nout, D, D, r_lan)
                    end, tp = self.turnin(fit, C_U, Xl, Yl, Zl, D, r)
                    tube(rope, fillet(hp + tp, 2.0 * r), r, self.ROPE)
                    self.span(f"topmast shroud {mast} {'stbd' if sgn > 0 else 'port'} {j}", *(np.array([Mt, end]) * [1, sgn, 1]), r)
                    lines[sgn][j] = (Mt, end, r, C_U)
                    # the strop and futtock plate down through the rim to under the top, with an eye at its foot
                    bar = 0.6 * IN
                    ring_band(fit, C_L, Zl, Xl, 0.0, 0.45 * D, 0.1 * D, bar, self.IRON, 12)
                    S_b = C_L - Xl * (0.45 * D + bar)
                    s_low = m["s_plat"] - tmc["plate_below_top_ft"] * FT
                    ell = ((S_b - O) @ u - s_low) / (Xl @ u)
                    wd = unit(np.cross(Zl, Xl))
                    box(fit, S_b - Xl * ell / 2, Xl, wd, Zl, ell / 2 + 0.5 * IN, 1.25 * IN, 0.3 * IN, self.IRON)
                    P_e = S_b - Xl * (ell + 0.9 * IN)
                    ring_band(fit, P_e, Zl, Xl, 0.0, 0.7 * IN, 0.6 * IN, 0.5 * IN, self.IRON, 8)
                    lines[sgn][j] = lines[sgn][j] + (P_e,)
        # the futtock shrouds: each plate's eye to the stave on the nearest lower shroud (each to its own, in order)
        for sgn in (1, -1):
            touch, r_st = self.stave[(mast, sgn)]
            Pe = [ln[4] for ln in lines[sgn]]
            idx = self.assign([p[0] for p in Pe], [tp[0] for tp in touch])
            fl = []
            rope = Side(self.mesh(f"Rigging_{Mn}"), sgn)
            for j, k in enumerate(idx):
                sc = touch[k]
                a = Pe[j]
                b = sc + unit(a - sc) * (r_st + r_fut)
                tube(rope, [a + unit(b - a) * 0.6 * IN, b], r_fut, self.ROPE)
                self.span(f"futtock shroud {mast} {'stbd' if sgn > 0 else 'port'} {j}", *(np.array([a, b]) * [1, sgn, 1]), r_fut)
                fl.append((a, b, r_fut))
            self.shroud_lines[(mast, "futtock", sgn)] = fl
            self.shroud_lines[(mast, "topmast", sgn)] = lines[sgn]
        # ratlines on the topmast shrouds (from over the turn-ins to under the crosstrees) and on the futtock shrouds
        r_rt = rope_r(S["rope_in"]["ratlines"]["topmast"])
        r_rf = rope_r(S["rope_in"]["ratlines"]["futtock"])
        z_tt = (m["Otm"] + m["s_tt2a"] * u)[2]
        for sgn in (1, -1):
            ln = self.shroud_lines[(mast, "topmast", sgn)]
            z0 = max(x[3][2] for x in ln) + 2.9 * D + 0.3 * FT
            self.ratlines(Side(self.mesh(f"Ratlines_{Mn}"), sgn), ln, z0, z_tt - 1.5 * FT, tmc["ratline_pitch_in"] * IN, r_rt)
            fl = self.shroud_lines[(mast, "futtock", sgn)]
            fl_sorted = sorted(fl, key=lambda q: -q[0][0])
            z0 = max(q[1][2] for q in fl) + 1.0 * FT
            z1 = min(q[0][2] for q in fl) - 0.6 * FT
            self.ratlines(Side(self.mesh(f"Ratlines_{Mn}"), sgn), fl_sorted, z0, z1, S["lower"]["ratline_pitch_in"] * IN,
                          r_rf, skip_last=False)
        # the topmast backstays: their eye over the shrouds' on the topmast head, legs aftmost, to the channel
        for p in range((nb + 1) // 2):
            legs = [k for k in (2 * p, 2 * p + 1) if k < nb]
            for sgn in (1, -1):
                s_e = self.eye(mast, "topmast", rb)
                self.eye_loop(Side(self.mesh(f"Rigging_{Mn}"), sgn), mast, "topmast", s_e, rb)
                for k in legs:
                    fn = lambda tg, k=k, s_e=s_e: self.head_leg(mast, "topmast", slots[n + k], s_e, rb, tg)
                    self.channel_leg(mast, sgn, bxs[k], Db, Db, rb, fn, "topmast backstay", max(0.6, 0.3 * 2 * rb / IN))

    @staticmethod
    def assign(a, b):
        """Each of a's (sorted any way) to its own one of b's, keeping their order, least total distance: indices."""
        oa, ob = np.argsort(a), np.argsort(b)
        A, B = np.asarray(a)[oa], np.asarray(b)[ob]
        n, m = len(A), len(B)
        INF = 1e18
        cost = np.full((n + 1, m + 1), INF)
        cost[0, :] = 0.0
        for i in range(1, n + 1):
            for j in range(i, m + 1):
                cost[i, j] = min(cost[i, j - 1], cost[i - 1, j - 1] + abs(A[i - 1] - B[j - 1]))
        res, j = [0] * n, m
        for i in range(n, 0, -1):
            while j > i and cost[i, j] == cost[i, j - 1]:
                j -= 1
            res[i - 1] = j - 1
            j -= 1
        out = [0] * n
        for k in range(n):
            out[oa[k]] = int(ob[res[k]])
        return out

    # ---- topgallant shrouds, topgallant and royal backstays ----------------------------------------------------------
    def topgallant_rigging(self, mast):
        S, m = self.sp, self.rig.masts[mast]
        n = S["masts"][mast]["topgallant_shrouds"]
        r = self.r_of("topgallant_shrouds", mast)
        u, f = m["u"], m["f"]
        Otm = m["Otm"]
        Mn = mast.capitalize()
        # side by side through the after crosstree's ends: the crosstrees before it stand before the topgallant mast,
        # where the yard hangs, and a shroud led from there down to the topmast shrouds would cross the topsail yard
        # hoisted. Fore to aft
        xc = [m["ct2_xs"][0] - (k - (n - 1) / 2) * (2 * r + 0.15 * IN) for k in range(n)]
        s_ct0, s_ct1 = m["s_tt2b"], m["s_tt2b"] + m["ct2_d"]
        tgc = S["topgallant"]
        lines = {1: [None] * n, -1: [None] * n}
        # each goes down to its own topmast shroud (the nearest, in order), futtock_ft under the crosstrees
        z_f = (Otm + s_ct0 * u + xc[0] * f)[2] - tgc["futtock_ft"] * FT
        to = {sgn: self.assign(xc, [point_at_z(q[1], q[0], z_f)[0] for q in self.shroud_lines[(mast, "topmast", sgn)]])
              for sgn in (1, -1)}
        for p in range((n + 1) // 2):
            legs = [j for j in (2 * p, 2 * p + 1) if j < n]
            for sgn in (1, -1):
                rope, fit = Side(self.mesh(f"Rigging_{Mn}"), sgn), Side(self.mesh(f"Deadeyes_{Mn}"), sgn)
                s_e = self.eye(mast, "stop", r)
                self.eye_loop(rope, mast, "stop", s_e, r)
                tml = self.shroud_lines[(mast, "topmast", sgn)]
                for j in legs:
                    yt = m["B2"] / 2
                    top = Otm + s_ct1 * u + xc[j] * f + yt * EY
                    bot = Otm + s_ct0 * u + xc[j] * f + yt * EY
                    w1 = top + 0.75 * r * (EY + u)
                    w2 = bot + 0.75 * r * (EY - u)
                    # seized alongside its topmast shroud
                    k = to[sgn][j]
                    Pt, Pb, rs = tml[k][0], tml[k][1], tml[k][2]
                    T = unit(Pt - Pb)
                    nrm = unit(EY - (EY @ T) * T)
                    # alongside it in the shrouds' plane (on the side it comes from), clear of the ratlines outside
                    P_f = point_at_z(Pb, Pt, z_f)
                    sd = unit(np.cross(nrm, T))
                    sd = sd if sd @ (w2 - P_f) > 0 else -sd
                    F0 = P_f + sd * (rs + r + 0.05 * IN)
                    E = self.round_leg(mast, "stop", s_e, r, top, sgn)
                    pts = E + [w1, w2, F0, F0 - T * 1.2 * FT]
                    tube(rope, fillet(pts, 2.0 * r), r, self.ROPE)
                    hoop(fit, F0 - T * 0.8 * FT - sd * (rs + r) / 2, T, sd, stadium((rs + r) / 2, max(rs, r) + 0.05 * IN),
                         1.4 * r, 0.25 * r + 0.1 * IN, self.ROPE)
                    self.span(f"topgallant shroud {mast} {'stbd' if sgn > 0 else 'port'} {j}", *(np.array([E[-1], w1]) * [1, sgn, 1]), r)
                    lines[sgn][j] = (E[-1], w1, r)
        r_rg = rope_r(S["rope_in"]["ratlines"]["topgallant"])
        for sgn in (1, -1):
            ln = lines[sgn]
            z0 = ln[0][1][2] + 1.2 * FT
            z1 = (m["Otg"] + (m["s_stop"] - 3.5 * FT) * u)[2]
            self.ratlines(Side(self.mesh(f"Ratlines_{Mn}"), sgn), ln, z0, z1, tgc["ratline_pitch_in"] * IN, r_rg,
                          skip_last=False)
        # topgallant and royal backstays: an eye over the stop (and round the pole under the truck), straight to the
        # channel abaft the topmast backstays, set up with small deadeyes
        places = self.channel_places(mast)
        for key, level, place in (("topgallant_backstays", "stop", "topgallant_backstay"),
                                  ("royal_backstays", "royal", "royal_backstay")):
            rr = self.r_of(key, mast)
            for sgn in (1, -1):
                s_e = self.eye(mast, level, rr)
                self.eye_loop(Side(self.mesh(f"Rigging_{Mn}"), sgn), mast, level, s_e, rr)
                fn = lambda tg, s_e=s_e, level=level, rr=rr, sgn=sgn: self.round_leg(mast, level, s_e, rr, tg, sgn)
                self.channel_leg(mast, sgn, places[place], None, None, rr, fn, key.replace("_", " ")[:-1], 0.6)

    # ---- stays -------------------------------------------------------------------------------------------------------
    def stay_top(self, mast, level, r, y_off, s_e, nxt_heel):
        """A stay's points from its eye's fore side down the head's fore face, in front of the eyes below it, to under
        the next mast's heel (for lower and topmast stays)."""
        H = self.head(mast, level)
        m = self.rig.masts[mast]
        O, u, f = H["O"], H["u"], H["f"]
        below = [re for sc, re in self.stack[(mast, level)] if sc < s_e - 1e-6]
        hs = H["hs"](s_e)
        s_turn = nxt_heel - r - 1.0 * IN
        R = m["R_lower"] if level == "lower" else m["R_tm"]
        x_dn = max(hs + 2 * max(below + [0.0]), R(s_turn) + 0.1 * IN) + r + 0.25 * IN
        E = O + s_e * u + (hs + r) * f + y_off * EY
        P1 = O + (s_e - 0.5 * r) * u + x_dn * f + y_off * EY
        P2 = O + s_turn * u + x_dn * f + y_off * EY
        return [E, P1, P2]

    def beside(self, o, R, others):
        """The spars of others ([(p0, axis, up, length, R(s))]) lying alongside a collar's spar at o (radius R), as
        collar_spar's extra: a collar there goes round both."""
        out = []
        for p0, uq, _, Lq, Rq in others:
            s = float((o - p0) @ uq)
            if 0.0 <= s <= Lq and np.linalg.norm(p0 + s * uq - o) < R + Rq(s) + 2.0 * IN:
                out.append((p0 + s * uq, Rq(s)))
        return out

    def collar_spar(self, mesh, o, ax, R, r, extra=()):
        """A collar (a loop of rope) round a spar (axis point o, direction ax, radius R) and anything lying on it
        (extra: [(centre, radius)]): its points (drawn on mesh unless mesh is None)."""
        a = unit(np.cross(ax, EY)) if abs(ax @ EY) < 0.9 else EX
        b = np.cross(ax, a)
        P2 = [(0.0, 0.0, R)] + [((c - o) @ a, (c - o) @ b, rr) for c, rr in extra]
        pts = []
        for x, y, rr in P2:
            for th in np.arange(24) * 2 * math.pi / 24:
                pts.append((x + (rr + r) * math.cos(th), y + (rr + r) * math.sin(th)))
        pts = np.array(pts)
        hv = ConvexHull(pts).vertices
        loop = [o + p[0] * a + p[1] * b for p in pts[hv]]
        if mesh is not None:
            tube(mesh, loop, r, self.ROPE, n=max(6, nsides(r) - 4), closed=True)
        return loop, a, b

    def masthead_collar(self, mesh, mast, level, r):
        """A collar round another mast's head, over its eyes, for a stay that ends there: the collar's after point."""
        s = self.eye(mast, level, r)
        pts = self.eye_loop(mesh, mast, level, s, r)
        H = self.head(mast, level)
        if H["kind"] == "square":                        # the middle of the collar's after side
            return H["O"] + s * H["u"] - (H["hs"](s) + r) * H["f"]
        return min(pts, key=lambda p: (p - H["O"]) @ H["f"])

    def stays(self, mast):
        S, i, m = self.sp, MI[mast], self.rig.masts[mast]
        st = S["stays"]
        Ms = self.mesh("Stays")
        rope, fit = Side(Ms, 1), Side(Ms, 1)
        b = self.rig.bs
        reg = dict(self.rig.sp["registration"], mid_px=self.L.mid_px, ppf=self.L.ppf)
        # the lower stay (and preventer)
        names = [mast] + ([f"{mast}_preventer"] if S["rope_in"]["preventer_stay"][i] > 0 else [])
        for nm in names:
            spec = st[nm]
            prev = nm.endswith("preventer")
            r = rope_r(S["rope_in"]["preventer_stay" if prev else "stay"][i])
            r_col = rope_r(S["rope_in"]["collar_of_stay"] * S["rope_in"]["preventer_stay" if prev else "stay"][i])
            Lh = S["hearts_in"]["preventer_stay" if prev else "stay"][i] * IN
            y_off = (r + 0.25 * IN) * (-1 if prev else 1)
            s_e = self.eye(mast, "lower", r)
            self.eye_loop(rope, mast, "lower", s_e, r)
            top = self.stay_top(mast, "lower", r, y_off, s_e, m["s_tm_heel"])
            P2 = top[-1]
            if spec["to"] == "bowsprit":
                xd = [self.draught_ft(spec[k][0], reg) for k in ("collar_draught", "heart_low_draught", "heart_up_draught")]
                dpx = lambda p, q: math.hypot(spec[p][0] - spec[q][0], spec[p][1] - spec[q][1]) / reg["px_per_ft"]
                a = dpx("collar_draught", "heart_low_draught") * FT
                bb = dpx("collar_draught", "heart_up_draught") * FT
                s = (xd[0] * FT - b["H"][0]) / b["ub"][0]
                o = b["H"] + s * b["ub"]
                p0, uj, upj, Lj, Rj = b["jib"]
                sj = float((o - p0) @ uj)
                extra = [(p0 + sj * uj, Rj(sj))] if 0 <= sj <= Lj else []
                loop, _, _ = self.collar_spar(fit, o, b["ub"], b["R"](s), r_col, extra)
                A = max(loop, key=lambda p: p[2] + 0.2 * p[1] * np.sign(y_off))
                t = unit(P2 - A)
                end, pu, pl = self.heart_pair(fit, rope, A, t, a, bb, Lh, r, r_col, EY, nm)
                tube(rope, fillet(top + [end] + pu[1:], 3 * r), r, self.ROPE)
                tube(fit, fillet([A] + pl, 2 * r_col), r_col, self.ROPE)
            elif spec["to"] == "bowsprit_inboard":
                # set up on the forecastle: the heart over the bowsprit, the stay passing the foremast on its side
                xh = self.draught_ft(spec["heart_draught"][0], reg)
                s = (xh * FT - b["H"][0]) / b["ub"][0]
                o = b["H"] + s * b["ub"]
                ztop = o[2] + b["R"](s) / b["ub"][0]
                fm = self.rig.masts["fore"]
                side = spec["side"]

                def clearance(ye):
                    Hu = np.array([o[0], ye, ztop + spec["heart_over_bowsprit_ft"] * FT]) + 1.3 * Lh * unit(P2 - o)
                    best = 1e9
                    for ss in np.linspace(fm["s_h"] * 0.2, fm["s_h"], 60):
                        q = fm["O"] + ss * fm["u"]
                        # nearest point of the stay's line to the foremast's axis at this height
                        d = pt_seg(q, P2, Hu)
                        best = min(best, d - fm["R_lower"](ss))
                    return best
                need = r + 1.0 * IN
                lo_, hi_ = 0.0, 4.0
                for _ in range(40):
                    mid = 0.5 * (lo_ + hi_)
                    if clearance(side * mid) >= need:
                        hi_ = mid
                    else:
                        lo_ = mid
                ye = side * hi_
                # the draught's heart is the lower, the upper heart above it toward the masthead; the collar goes round
                # the bowsprit under the lower heart's throat, inboard of the stem head
                Lo = np.array([o[0], ye, ztop + spec["heart_over_bowsprit_ft"] * FT])
                t = unit(P2 - Lo)
                thr = Lo - t * 1.0 * Lh
                sc = float((thr - b["H"]) @ b["ub"])
                oc = b["H"] + sc * b["ub"]
                # the stem head stands under the bowsprit from its after face to its fore face: a collar there would
                # pass through it, so it goes round close before the stem (and the knightheads), and the hearts move
                # square to the stay onto the line from the masthead to it
                xa, xf = self.stem_head_x()
                lean = abs(b["ub"][2]) * (b["R"](sc) + r_col)        # the collar's underside lies forward of oc
                if oc[0] - r_col < xf and oc[0] + lean + r_col > xa:
                    sc = float((xf + r_col + 1.5 * IN - b["H"][0]) / b["ub"][0])
                    oc = b["H"] + sc * b["ub"]
                    loop, _, _ = self.collar_spar(None, oc, b["ub"], b["R"](sc), r_col)
                    Lo0 = Lo.copy()
                    for _ in range(4):
                        t = unit(P2 - Lo)
                        q = Lo + t * float((oc - Lo) @ t)
                        A = min(loop, key=lambda p: np.linalg.norm(p - q))
                        n = unit(np.cross(t, EY))
                        Lo = Lo + n * float((A - Lo) @ n)
                    t = unit(P2 - Lo)
                    thr = Lo - t * float((Lo - A) @ t)
                    mv = Lo - Lo0
                    self.report["skipped"].append(
                        f"{nm.replace('_', ' ')} stay: its collar goes round the bowsprit before the stem head (where "
                        f"the draught's heart puts it, it would pass through the stem), so its hearts move "
                        f"{np.linalg.norm(mv) / FT:.1f} ft {'forward' if mv[0] > 0 else 'aft'} and "
                        f"{'up' if mv[2] > 0 else 'down'} onto the line to it")
                loop, _, _ = self.collar_spar(fit, oc, b["ub"], b["R"](sc), r_col)
                A = min(loop, key=lambda p: np.linalg.norm(p - thr))
                end, pu, pl = self.heart_pair(fit, rope, Lo, t, 0.0, 1.3 * Lh, Lh, r, r_col, EY, nm, collar=A)
                tube(rope, fillet(top + [end] + pu[1:], 3 * r), r, self.ROPE)
                tube(fit, fillet([A] + pl, 2 * r_col), r_col, self.ROPE)
                self.report.setdefault("main_stays_y_ft", {})[nm] = round(ye / FT, 2)
            else:
                # the mizzen stay: to a collar round the main mast at the rail's height, the hearts abaft it
                mm = self.rig.masts["main"]
                z_r = self.rail_top_ft(mm["O"][0] / FT) * FT
                sc = (z_r - mm["O"][2]) / mm["u"][2]
                oc = mm["O"] + sc * mm["u"]
                loop, _, _ = self.collar_spar(fit, oc, mm["u"], mm["R_lower"](sc), r_col)
                A = min(loop, key=lambda p: (p - oc) @ mm["f"])
                t = unit(P2 - A)
                a = 2.4 * Lh + 0.5 * FT                 # the collar leg's turned-in end stops short of the mast
                end, pu, pl = self.heart_pair(fit, rope, A, t, a, a + 1.3 * Lh, Lh, r, r_col, EY, nm)
                tube(rope, fillet(top + [end] + pu[1:], 3 * r), r, self.ROPE)
                tube(fit, fillet([A] + pl, 2 * r_col), r_col, self.ROPE)
            self.span(f"{nm.replace('_', ' ')} stay", P2, end, r)
        # the topmast stay
        r = self.r_of("topmast_stay", mast)
        s_e = self.eye(mast, "topmast", r)
        self.eye_loop(rope, mast, "topmast", s_e, r)
        top = self.stay_top(mast, "topmast", r, 0.0, s_e, m["s_tg_heel"])
        to = st[f"{mast}_topmast"]["to"]
        if to == "bees":
            end = b["H"] + (b["bee_s"] + 1.0 * FT) * b["ub"] + b["bee_y"] * EY + b["up"] * (0.06 + r)
        else:
            tgt = "fore" if to == "fore_masthead" else "main"
            end = self.masthead_collar(rope, tgt, "lower", r)
        tube(rope, fillet(top + [end], 3 * r), r, self.ROPE)
        self.span(f"{mast} topmast stay", top[-1], end, r)
        # topgallant and royal stays: straight forward from their eyes
        for key, level, lvl_to in (("topgallant_stay", "stop", "topmast"), ("royal_stay", "royal", "royal")):
            r = self.r_of(key, mast)
            s_e = self.eye(mast, level, r)
            self.eye_loop(rope, mast, level, s_e, r)
            to = st[f"{mast}_{key.split('_')[0]}"]["to"]
            if to in ("jibboom_end", "flying_jibboom_end"):
                p0, uj, upj, Lj, Rj = b["jib"] if to == "jibboom_end" else b["fjb"]
                sj = Lj - (0.95 if to == "jibboom_end" else 0.8) * FT      # outermost: the stay leads up from it
                ex = self.beside(p0 + sj * uj, Rj(sj), [b["fjb"] if to == "jibboom_end" else b["jib"]])
                loop, _, _ = self.collar_spar(rope, p0 + sj * uj, uj, Rj(sj), r, ex)
                end = max(loop, key=lambda p: p[2])
            else:
                tgt = to.split("_")[0]
                lv = "topmast" if lvl_to == "topmast" else "royal"
                end = self.masthead_collar(rope, tgt, lv, r)
            E = self.round_leg(mast, level, s_e, r, end)
            tube(rope, fillet(E + [end], 2 * r) if len(E) > 1 else E + [end], r, self.ROPE)
            self.span(f"{mast} {key.replace('_', ' ')}", E[-1], end, r)

    # ---- the bowsprit's rigging ----------------------------------------------------------------------------------
    def eyebolt(self, fit, P, nrm, d, mat):
        """An eyebolt in the side at P (its normal nrm), its eye's plane holding direction d."""
        rr = 1.0 * IN
        c = P + nrm * (rr + 0.8 * IN)
        a = unit(d - (d @ nrm) * nrm) if np.linalg.norm(d - (d @ nrm) * nrm) > 1e-6 else unit(np.cross(nrm, EZ))
        ax = unit(np.cross(nrm, a))
        ring_band(fit, c, ax, nrm, 0.0, rr, 0.6 * IN, 0.5 * IN, mat, 10)
        hex_bolt(fit, P, nrm, 1.0 * IN, 0.6 * IN, mat)
        return c + nrm * rr

    def bowsprit_rigging(self):
        S = self.sp
        b = self.rig.bs
        bw = S["bowsprit"]
        ri = S["rope_in"]
        M = self.mesh("Rigging_Bowsprit")
        H, ub = b["H"], b["ub"]
        Db = S["deadeyes"]["bowsprit"] * IN
        rs = rope_r(ri["bowsprit_shrouds"])
        r_lan = rope_r(ri["lanyard_of_rope"] * ri["bowsprit_shrouds"])
        # the collars on the bowsprit and the jibbooms: one each, round the spar where it lies (the flying jibboom is
        # to starboard of the centreline), each with a leg to either side
        centre = Side(M, 1)
        sh_loops = []
        for xc in bw["shrouds"]["collars_x_ft"]:
            s = (xc * FT - H[0]) / ub[0]
            o = H + s * ub
            sh_loops.append((o, self.collar_spar(centre, o, ub, b["R"](s), rs, self.beside(o, b["R"](s), [b["jib"]]))[0]))
        # the martingale stays: from collars round the jibbooms' ends down to the dolphin striker's foot (the flying
        # martingale, coming in flatter from further out, the lower on the striker, so they do not cross)
        foot = b["ds_top"] + b["ds_dir"] * b["ds_len"]
        fwd = unit(ub - (ub @ b["ds_dir"]) * b["ds_dir"])
        mart = []
        for key, spr, back, k in (("martingale_stay", b["jib"], 1.25, 0.65), ("flying_martingale_stay", b["fjb"], 1.1, 0.3)):
            rm = rope_r(ri[key])
            p0, uj, upj, Lj, Rj = spr
            sj = Lj - back * FT
            ex = self.beside(p0 + sj * uj, Rj(sj), [q for q in (b["jib"], b["fjb"]) if q is not spr])
            loop, _, _ = self.collar_spar(None, p0 + sj * uj, uj, Rj(sj), rm, ex)
            col = min(loop, key=lambda p: p[2])
            a = foot - b["ds_dir"] * k * FT + fwd * (b["ds_d"] / 2 * 0.8 + rm)
            mart.append((key, spr, sj, rm, col, a, ex))
        guys = []
        for key, spr, back, dx in (("jibboom_guys", b["jib"], 1.6, 0.0), ("flying_jibboom_guys", b["fjb"], 1.4, -1.5)):
            rg = rope_r(ri[key])
            p0, uj, upj, Lj, Rj = spr
            sj = Lj - back * FT                                    # innermost: the guys lead aft and out from it
            og = p0 + sj * uj
            extra = self.beside(og, Rj(sj), [q for q in (b["jib"], b["fjb"]) if q is not spr])
            for _, spr_m, _, rm, col, a, _ in mart:              # over the martingale stay leading aft under it
                if spr_m is spr:
                    tt = float((og - col) @ uj) / float((a - col) @ uj)
                    if 0.0 <= tt <= 1.0:
                        extra.append((col + tt * (a - col), rm))
            guys.append((key, rg, p0, self.collar_spar(centre, og, uj, Rj(sj), rg, extra)[0], dx))
        mirror = lambda p, sgn: np.asarray(p, float) * [1, sgn, 1]
        for sgn in (1, -1):
            rope = Side(M, sgn)
            # shrouds: two a side, from collars round the bowsprit to deadeyes on eyebolts in the bow
            for xc, xb, (o, loop) in zip(bw["shrouds"]["collars_x_ft"], bw["shrouds"]["bow_x_ft"], sh_loops):
                B, nB = self.hull_at(xb, bw["shrouds"]["bow_z_ft"])
                col = max(loop, key=lambda p: p @ unit(B - o))
                eb = self.eyebolt(rope, B, nB, col - B, self.IRON)
                t = unit(col - eb)
                C_L = eb + t * (Db / 2 + 0.8 * IN)
                C_U = C_L + t * 1.9 * Db
                Xl, Yl, Zl = self.deadeye_pair(rope, C_L, C_U, nB, Db, Db, r_lan)
                ring_band(rope, C_L, Zl, Xl, 0.0, 0.45 * Db, 0.1 * Db, 0.6 * IN, self.IRON, 12)
                end, tp = self.turnin(rope, C_U, Xl, Yl, Zl, Db, rs)
                tube(rope, fillet([col] + tp, 2 * rs), rs, self.ROPE)
                self.span(f"bowsprit shroud {'stbd' if sgn > 0 else 'port'} {xc}", *(np.array([col, end]) * [1, sgn, 1]), rs)
            # martingale back ropes: from the dolphin striker's foot to the bow
            foot = b["ds_top"] + b["ds_dir"] * (b["ds_len"] - 0.25 * FT)
            rb = rope_r(ri["martingale_back_rope"])
            B, nB = self.hull_at(bw["martingale_back_rope"]["bow_x_ft"], bw["martingale_back_rope"]["bow_z_ft"])
            eb = self.eyebolt(rope, B, nB, foot - B, self.IRON)
            a = foot + unit((B - foot) - ((B - foot) @ b["ds_dir"]) * b["ds_dir"]) * (b["ds_d"] / 2 + rb)
            tube(rope, [a, eb], rb, self.ROPE)
            self.span(f"martingale back rope {'stbd' if sgn > 0 else 'port'}", *(np.array([a, eb]) * [1, sgn, 1]), rb)
            # jibboom and flying jibboom guys: from their collar (where the spar is) to an eyebolt on this side's bow
            for key, rg, p0, loop, dx in guys:
                B, nB = self.hull_at(bw["jibboom_guys"]["bow_x_ft"] + dx, bw["jibboom_guys"]["bow_z_ft"])
                col = max(loop, key=lambda p: p @ unit(mirror(B, sgn) - p0))           # on the spar, this side
                eb = mirror(self.eyebolt(rope, B, nB, mirror(col, sgn) - B, self.IRON), sgn)
                tube(centre, [col, eb], rg, self.ROPE)
                self.span(f"{key[:-1].replace('_', ' ')} {'stbd' if sgn > 0 else 'port'}", col, eb, rg)
        # the martingale stays' collars and legs
        for key, spr, sj, rm, col, a, ex in mart:
            p0, uj, upj, Lj, Rj = spr
            self.collar_spar(centre, p0 + sj * uj, uj, Rj(sj), rm, ex)
            tube(centre, [col, a], rm, self.ROPE)
            self.span(key.replace("_", " "), col, a, rm)

    # ---- all of it ---------------------------------------------------------------------------------------------------
    def build(self):
        for mast in ("fore", "main", "mizzen"):
            self.lower_shrouds(mast)
            self.lower_ratlines_and_stave(mast)
            self.topmast_rigging(mast)
            self.topgallant_rigging(mast)
        for mast in ("fore", "main", "mizzen"):
            self.stays(mast)
        self.bowsprit_rigging()
        return self

    def yard_rests(self):
        """Where each royal yard comes to rest lowered, now that the topgallant rigging's eyes are on the stop: just
        above them (spars.py rested it on the bare stop). {part: lowered hoist_m}, for rig.json."""
        out = {}
        for mast in ("fore", "main", "mizzen"):
            pname = f"Yard_{mast.capitalize()}Royal"
            mt, m = self.rig.meta[pname], self.rig.masts[mast]
            s_h = float((np.asarray(mt["origin_m"]) - m["Otg"]) @ m["u"])
            d = mt["diam_in"] * IN
            out[pname] = round(float(self.top[(mast, "stop")] + d / 2 + 0.25 * FT - s_h), 3)
        return out

    def parts(self):
        """name -> (V, F, M, None): built in place."""
        out = {}
        for name, mesh in self.meshes.items():
            V, F, M = mesh.arrays()
            out[name] = (V, F, M, None)
        return out

    def summary(self):
        res = {"objects": {n: m.tris() for n, m in self.meshes.items()}, "deadeyes": self.report["deadeyes"],
               "hearts": self.report["hearts"], "channels": self.report["channels"], "notes": self.report["skipped"]}
        if "main_stays_y_ft" in self.report:
            res["main_stays_heart_y_ft"] = self.report["main_stays_y_ft"]
        return res
