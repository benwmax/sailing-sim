"""Bluebonnet below decks, forward (docs/jclass-9), from interior_bluebonnet.json: the crew's end of the yacht from the
forepeak to the bulkhead forward of the saloon.

  structure   the plating's inside face, the angle-bar frames and the deck beams with their bracket knees, the
              carlins round the deck's openings and the mast's partners, and the deckhead (the planking's underside):
              the steel counted in the hull's weight, the planking in the deck's, so none of it is weighed here
  ceiling     horizontal pine battens on the frames' inner edges (tongue-and-groove lining in the galley)
  joinery     the bulkheads with their doors, the soles and their steps, the mess table and benches, the galley's
              counter, lockers and dresser, the sail bins, the ladders, the washroom's lockers, the forepeak's platform,
              shelves and chain locker
  fittings    the pipe cots and their chains and hooks, the range, sink and pump, the ice chest's lining, the WC and
              basin, the windlass, spurling pipes, chain and the bower anchor
  canvas      the cots' canvas and the sail bags in the bins

    parts, rep = interior.build(S, holes)

S is slice 1's surface grid (loft.surface: the plating's outside); holes the deck's openings ({name: plan outline},
deck.build's rep['_holes']). Objects "Below.<kind>", each a set of closed solids labelled "<group> | <kind>", weighed
from their geometry and the json's densities (deck.Part.masses), the steel and the planking excepted. Units are metres
in the hull's frame (X forward, Y starboard, Z up). Needs Blender's mathutils for the deckhead's triangulation.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck  # noqa: E402
import loft  # noqa: E402
import shell  # noqa: E402
import spars  # noqa: E402
from deck import box, ear_clip, loft_rings, loft_section, region_slab  # noqa: E402,F401

IN = json.load(open(os.path.join(HERE, "interior_bluebonnet.json")))
ST, CE, RM, BH = IN["structure"], IN["ceiling"], IN["rooms"], IN["bulkheads"]
WT = IN["weights"]
PLANK = deck.PL["thickness"]                     # the deck's planking: the deckhead is its underside
ROOMS = sorted(((k, v) for k, v in RM.items() if isinstance(v, dict)), key=lambda kv: kv[1]["x"][0])
FRAMES = ST["frames_from"] + ST["frame_spacing"] * np.arange(
    int(round((ST["frames_to"] - ST["frames_from"]) / ST["frame_spacing"])) + 1)
OBJECTS = ("Below.Structure", "Below.Ceiling", "Below.Joinery", "Below.Fittings", "Below.Canvas")
X0, X1 = float(FRAMES[0]), float(FRAMES[-1])      # the after and forward bulkheads
SIDES = ((1, "starboard"), (-1, "port"))


def lab(group, kind):
    return f"{group} | {kind}"


def openings():
    """The deck's openings over these cabins, for deck.build (hatches and skylights by name) and hardware.build and
    hardware.deck_holes (the prisms by index, the cowls by place, the chain pipe)."""
    o = IN["openings"]
    return {"hatches": list(o["hatches"]), "skylights": list(o["skylights"]), "prisms": list(o["prisms"]),
            "cowls": list(o["cowls"]), "chain_pipe": bool(o["chain_pipe"])}


def deckhead_z(x, y):
    """The deckhead: the planking's underside."""
    return shell.deck_z(np.asarray(x, float), np.asarray(y, float)) - PLANK


def room_at(x):
    for name, r in ROOMS:
        if r["x"][0] <= x <= r["x"][1]:
            return name, r
    return ROOMS[-1] if x > ROOMS[-1][1]["x"][1] else ROOMS[0]


def sole_at(name, x):
    """A room's sole's top at x (its raised forward part forward of 'sole_forward')."""
    r = RM[name]
    if "sole_forward" in r and x >= r["sole_forward"][0]:
        return r["sole_forward"][1]
    return r["sole"]


# ------------------------------------------------------------------------------------------------ the hull's inside
class Hull:
    """The plating's outside (slice 1's surface) cut at any x, and offsets inboard of it in the section's plane."""

    def __init__(self, S):
        S = np.asarray(S, float)
        Su, Sv = np.gradient(S, axis=0), np.gradient(S, axis=1)
        N = np.cross(Su, Sv)
        N /= np.maximum(np.linalg.norm(N, axis=2), 1e-12)[..., None]
        i, j = S.shape[0] // 2, int(S.shape[1] * 0.8)
        if N[i, j, 1] > 0:                          # inboard: toward the centreline on the topsides
            N = -N
        self.S, self.N = S, N
        self._cache = {}

    def cut(self, x):
        """The section at x: points (m, 3) keel to sheer and the inboard normals there (m, 3)."""
        key = round(float(x), 6)
        if key in self._cache:
            return self._cache[key]
        P, Nn = [], []
        for j in range(self.S.shape[1]):
            xs = self.S[:, j, 0]
            k = np.where((xs[:-1] - x) * (xs[1:] - x) <= 0)[0]
            if len(k) == 0:
                continue
            k = k[-1]
            t = 0.0 if xs[k + 1] == xs[k] else (x - xs[k]) / (xs[k + 1] - xs[k])
            P.append(self.S[k, j] + t * (self.S[k + 1, j] - self.S[k, j]))
            n = self.N[k, j] + t * (self.N[k + 1, j] - self.N[k, j])
            Nn.append(n / np.linalg.norm(n))
        out = (np.array(P), np.array(Nn))
        self._cache[key] = out
        return out

    def inner(self, x, d, z_lo=-9.0, z_hi=9.0, step=0.08, y_min=0.02, n=None):
        """The surface d inboard of the plating's outside (along its normal), cut at x and clipped to z_lo..z_hi (and
        to y > y_min, off the stem bar), resampled every `step` along its girth (or to n points): (y, z) points (m, 2),
        the inboard normals in the section's plane (m, 2), and each point's bevel: how far inboard the surface moves
        (in the plane) per metre forward."""
        P, N = self.cut(x)
        nyz = np.linalg.norm(N[:, 1:], axis=1)
        n2 = N[:, 1:] / nyz[:, None]
        Q = P[:, 1:] + (d / nyz)[:, None] * n2
        bev = -N[:, 0] / nyz
        # clip: from where it first rises past z_lo with y past y_min to where it reaches z_hi
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
        ok = (Q[:, 1] >= z_lo) & (Q[:, 0] >= y_min)
        if not ok.any():
            return None
        i0 = int(np.argmax(ok))
        s0 = s[i0]
        if i0 > 0:                                  # back to the crossing
            a, b = Q[i0 - 1], Q[i0]
            ta = (z_lo - a[1]) / (b[1] - a[1]) if (a[1] < z_lo <= b[1]) else 0.0
            tb = (y_min - a[0]) / (b[0] - a[0]) if (a[0] < y_min <= b[0]) else 0.0
            t = max(ta, tb)
            s0 = s[i0 - 1] + t * (s[i0] - s[i0 - 1])
        above = np.where(Q[:, 1] >= z_hi)[0]
        above = above[above > i0]
        if len(above):
            i1 = int(above[0])
            a, b = Q[i1 - 1], Q[i1]
            t = (z_hi - a[1]) / (b[1] - a[1])
            s1 = s[i1 - 1] + t * (s[i1] - s[i1 - 1])
        else:
            s1 = s[-1]
        n = n or max(int(math.ceil((s1 - s0) / step)), 2) + 1
        ss = np.linspace(s0, s1, n)
        pts = np.column_stack([np.interp(ss, s, Q[:, 0]), np.interp(ss, s, Q[:, 1])])
        nn = np.column_stack([np.interp(ss, s, n2[:, 0]), np.interp(ss, s, n2[:, 1])])
        nn /= np.linalg.norm(nn, axis=1)[:, None]
        return pts, nn, np.interp(ss, s, bev)

    def y_at(self, x, d, z):
        """The half-breadth d inboard of the plating's outside at height z (0 where the section does not reach z)."""
        P, N = self.cut(x)
        nyz = np.linalg.norm(N[:, 1:], axis=1)
        Q = P[:, 1:] + (d / nyz)[:, None] * (N[:, 1:] / nyz[:, None])
        return loft._half_breadth_at([tuple(q) for q in Q], z)

    def side_top(self, x, d, below=0.0):
        """The height where the surface d inboard meets the deckhead (less `below`), and its half-breadth there."""
        y = float(loft.DECK_HB(np.clip(x, *shell.DECK_X)))
        for _ in range(4):
            z = float(deckhead_z(x, y)) - below
            y = self.y_at(x, d, z) or y
        return z, y


# ------------------------------------------------------------------------------------------------ shapes
def ring_tube(path, radius, n=8):
    """A round rod round a closed loop of points (a cot's pipe frame, a chain's link): each section square to the loop,
    its frame the loop's plane's normal (Newell's) and the way in, so the sections never turn about the loop."""
    P = np.asarray(path, float)
    m = len(P)
    a = 2 * math.pi * np.arange(n) / n
    N = np.sum(np.cross(P, np.roll(P, -1, axis=0)), axis=0)
    N = N / max(np.linalg.norm(N), 1e-15)
    rings = []
    for i in range(m):
        t = P[(i + 1) % m] - P[i - 1]
        t /= np.linalg.norm(t)
        u = N - (N @ t) * t
        u /= np.linalg.norm(u)
        v = np.cross(t, u)
        rings.append(P[i] + radius * (np.cos(a)[:, None] * u + np.sin(a)[:, None] * v))
    return loft_rings(rings, closed=True)


def sweep(rings_2d, place):
    """A closed solid through cross-sections: rings_2d a list of (n, 2) local sections, place(i, sec) -> (n, 3)."""
    return loft_rings([place(i, np.asarray(r, float)) for i, r in enumerate(rings_2d)])


def strip_solid(top, bot):
    """A closed solid between two (m, k, 3) grids of the same shape (a slab: its top and bottom sheets), walled round
    its edge."""
    top, bot = np.asarray(top, float), np.asarray(bot, float)
    m, k, _ = top.shape
    V = np.concatenate([top.reshape(-1, 3), bot.reshape(-1, 3)])
    o = m * k
    idx = lambda i, j: i * k + j  # noqa: E731
    F = []
    for i in range(m - 1):
        for j in range(k - 1):
            F.append((idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)))
            F.append((o + idx(i, j + 1), o + idx(i + 1, j + 1), o + idx(i + 1, j), o + idx(i, j)))
    rim = [idx(0, j) for j in range(k)] + [idx(i, k - 1) for i in range(1, m)] + \
          [idx(m - 1, j) for j in range(k - 2, -1, -1)] + [idx(i, 0) for i in range(m - 2, 0, -1)]
    for a, b in zip(rim, rim[1:] + rim[:1]):
        F.append((a, b, o + b, o + a))
    return V, F


def plane_poly(P2, origin, U, Vd):
    return np.asarray(origin, float) + np.asarray(P2)[:, :1] * np.asarray(U) + np.asarray(P2)[:, 1:2] * np.asarray(Vd)


def fan_slab(P2, origin, U, Vd, N, t0, t1):
    """A plate over a convex polygon (deck.slab)."""
    return deck.slab(np.asarray(P2, float), origin, U, Vd, N, t0, t1)


def clip_halfplane(P, a, b, c):
    """The convex polygon P (n, 2) clipped to a*x + b*y <= c (Sutherland-Hodgman)."""
    out = []
    n = len(P)
    for i in range(n):
        p, q = P[i], P[(i + 1) % n]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 0:
            out.append(p)
        if fp * fq < 0:
            t = fp / (fp - fq)
            out.append(p + t * (q - p))
    return np.array(out)


def clean_poly(P, tol=1e-6):
    P = np.asarray(P, float)
    keep = [0]
    for i in range(1, len(P)):
        if np.linalg.norm(P[i] - P[keep[-1]]) > tol:
            keep.append(i)
    P = P[keep]
    if len(P) > 1 and np.linalg.norm(P[0] - P[-1]) <= tol:
        P = P[:-1]
    return P


# ------------------------------------------------------------------------------------------------ the structure
FR_D, FR_F, FR_T = ST["frame"]
BM_D, BM_F, BM_T = ST["beam"]
WEB = 0.5 * BM_T
DH_TOP = 0.012                                   # the deckhead slab's top under the deck's top


def angle_section(depth, flange, t, toward=-1.0):
    """An angle bar's section (a along the flange, b along the web from its heel): the web at a = 0 (t thick), the
    flange from it toward `toward`."""
    h = 0.5 * t
    s = toward
    return np.array([[-s * h, 0.0], [-s * h, depth], [s * h, depth], [s * h, t], [s * (flange - h), t],
                     [s * (flange - h), 0.0]])


FRAME_L = angle_section(FR_D, FR_F, FR_T)        # flange aft, toward amidships (an open bevel)
BEAM_L = angle_section(BM_D, BM_F, BM_T)
WEB_L = np.array([[-WEB, BM_T], [-WEB, BM_D], [WEB, BM_D], [WEB, BM_T]])  # a beam's web under its flange's level


FLANGE_L = np.array([[WEB, 0.0], [WEB, BM_T], [WEB - BM_F, BM_T], [WEB - BM_F, 0.0]])  # its flange alone


def beam_run(xk, y0, y1, prof=None, end0=None, end1=None):
    """A deck beam (or `prof`, a part of its section) on frame xk from y0 to y1 under the deckhead; end0(x, z) and
    end1(x, z) the half-breadths its ends at y0 and y1 are cut to, vertex by vertex (each end should reach no further
    out than the least of them)."""
    prof = BEAM_L if prof is None else prof
    a, b = prof[:, 0], prof[:, 1]
    ys = np.linspace(y0, y1, max(int(math.ceil((y1 - y0) / 0.12)), 2) + 1)
    rings = [np.column_stack([xk + a, np.full(len(a), y), deckhead_z(xk + a, np.full(len(a), y)) - b]) for y in ys]
    for i, end in ((0, end0), (-1, end1)):
        if end is None:
            continue
        r, sg = rings[i], np.sign(ys[i])
        for _ in range(3):
            r[:, 1] = sg * np.array([end(px, pz) for px, pz in r[:, [0, 2]]])
            r[:, 2] = deckhead_z(r[:, 0], r[:, 1]) - b
    return loft_section(rings, prof)


def lowest(x):
    """How far down the plating and frames are drawn at x: 'below_sole' under the room's lowest sole, or (in the
    forepeak, whose platform is slatted) down to the stem bar."""
    name, r = room_at(x)
    if name == "Forepeak":
        return -9.0
    return r["sole"] - ST["below_sole"]


def mast_box():
    """The mast's partners under the deckhead: its outline there (the mast's section at the beams' underside and at
    the deckhead), and the box the beams are cut back to (the wedges' thickness and the partners' web outside it)."""
    yp, depth, wedge = ST["partners"]
    zt = float(deckhead_z(spars.X_P, 0.0))
    s_t, s_b = (zt - spars.Z_P) / math.cos(spars.RAKE), (zt - BM_D - spars.Z_P) / math.cos(spars.RAKE)
    rings = [spars.ring_at(s, 48) for s in (s_t, s_b)]
    xs = np.concatenate([r[:, 0] for r in rings])
    return {"half_y": yp, "x": (float(xs.min()) - wedge - BM_T, float(xs.max()) + wedge + BM_T), "s": (s_t, s_b),
            "wedge": wedge}


def beam_cuts(xk, holes, cut_names):
    """Where the beam on frame xk is cut: [(y half-width, what)] for each opening its footprint crosses (back to the
    carlins just outside the coaming) and for the mast's partners."""
    a0, a1 = xk + BEAM_L[:, 0].min(), xk + BEAM_L[:, 0].max()
    out = []
    for name in cut_names:
        spec = deck.DK["hatches"].get(name) or deck.DK["skylights"][name]
        x0, x1 = spec["x"] - spec["length"] / 2, spec["x"] + spec["length"] / 2
        if a1 > x0 and a0 < x1:
            out.append((spec["width"] / 2 + 2 * WEB, name))
    mb = mast_box()
    if a1 > mb["x"][0] and a0 < mb["x"][1]:
        out.append((mb["half_y"] + WEB, "mast"))
    for name, H in holes.items():                  # the fittings' holes (and their backing rings) clear of every beam
        if name in cut_names:
            continue
        H = np.asarray(H)
        m = 0.004 if name.startswith("Deck prism") else 0.035
        if H[:, 0].max() + m > a0 and H[:, 0].min() - m < a1:
            raise ValueError(f"the beam on frame {xk:.3f} passes under {name}'s hole: re-space the frames")
    return out


def structure(part, hull, holes, cut_names):
    """The plating's inside, the frames, beams, knees, carlins and partners, and the deckhead. Returns its report."""
    pl = ST["plating"]
    rep = {"frames": [round(float(x), 3) for x in FRAMES]}
    # the plating's inside face: a 6 mm skin from 2 mm inside the moulded surface to its inside face, from the
    # after bulkhead to the forward one and from under the soles up into the planking (where the deckhead meets it),
    # drawn room by room (each piece down to under its own sole, ending inside the bulkhead between two rooms), so
    # the skin between two stations never twists from one room's depth to the next's; where it is drawn down to the
    # stem bar (the forepeak, the washroom's forward end) each side's skin runs on 4 mm past the centreline along the
    # other side's section, so no seam opens there and the two never share an edge (the two sides overlap there by
    # design: build_jclass's IN_ALLOWED)
    # (every 45 mm round the girth, 30 mm in the two rooms right forward whose narrow bottoms turn tightest, so the
    # skin's chords stay within a few tenths of a millimetre of the true section the frames and bulkheads are fitted to)
    mid = 0.5 * FR_T + 0.5 * BH["thickness"]          # a joiner's bulkhead's middle, forward of its frame
    ends = [X0 + mid] + [r["x"][1] + mid for _, r in ROOMS]
    feet = (0.5 * FR_T, -0.5 * FR_T, -(FR_F - 0.5 * FR_T))   # a frame's faces fore and aft: its web's two, its flange's
    on_plating = {}                                          # after edge; the plating has a section at each of them
    for (name, _), xa, xb in zip(ROOMS, ends[:-1], ends[1:]):
        if xa > ends[0]:
            xa -= 0.0005                          # half a millimetre into the room aft's piece: no shared end section
        xs = np.linspace(xa, xb, max(int(math.ceil((xb - xa) / 0.1)), 2) + 1)
        fx = [xk + f for xk in FRAMES if xa <= xk + feet[2] and xk + feet[0] < xb for f in feet]
        xs = np.array(sorted([x for x in xs if not fx or min(abs(x - f) for f in fx) > 0.003] + fx))
        z_lo = lowest(0.5 * (RM[name]["x"][0] + RM[name]["x"][1]))
        step = 0.03 if name in ("Forepeak", "Washroom") else 0.045
        ng = max(len(hull.inner(x, pl, z_lo, hull.side_top(x, pl, below=-(PLANK - 0.006))[0], y_min=-0.001,
                                step=step)[0]) for x in xs)
        sheets = []
        for d in (0.002, pl):
            rows = []
            for x in xs:
                zt, _ = hull.side_top(x, d, below=-(PLANK - 0.006))
                pts, nn, _ = hull.inner(x, d, z_lo, zt, y_min=-0.001, n=ng)
                if d == pl:
                    on_plating[round(float(x), 6)] = (pts.copy(), nn)
                if pts[0, 0] < 0.001:
                    a_, b_ = pts[0], pts[1]
                    t = (a_[0] + 0.004) / (a_[0] + b_[0])
                    pts[0] = [-0.004, a_[1] + t * (b_[1] - a_[1])]
                rows.append(np.column_stack([np.full(ng, x), pts[:, 0], pts[:, 1]]))
            sheets.append(np.array(rows))
        for sd, side in SIDES:
            top, bot = (sh * np.array([1.0, sd, 1.0]) for sh in (sheets[1], sheets[0]))
            V, F = strip_solid(top, bot)
            part.add(V, F, "WhitePaint", None, lab(f"Plating, {side}", "plating"))
    # the frames: angle bars from under the soles up under the beam's flange, which runs out over the frame's head
    # to the plating; the flange aft on the plating (open bevel), each face on the plating's own section there, so
    # the heel follows the skin exactly. The head is cut along the flange's underside: the flange's aft end is lower
    # where the sheer rises forward, and the web's inner end, square to a flared side, stands higher than its heel
    row_of = {0.5 * FR_T: 0, -0.5 * FR_T: 1, -(FR_F - 0.5 * FR_T): 2}
    which = [row_of[min(row_of, key=lambda f: abs(f - a))] for a in FRAME_L[:, 0]]
    for xk in FRAMES:
        zt = min(hull.side_top(xk + f, pl, below=BM_T + 0.0005)[0] for f in feet)
        secs = []
        for f in feet:
            got = on_plating.get(round(float(xk + f), 6))
            if got is None:                               # no plating drawn there (the after bulkhead's frame)
                x = xk + f
                got = hull.inner(x, pl, lowest(xk), hull.side_top(x, pl, below=-(PLANK - 0.006))[0], y_min=-0.001,
                                 n=64)[:2]
            secs.append(got)
        # its rings: the sections' points up to the head, from where the web's inner edge stays 3 mm off the
        # centreline (where the bottom narrows to the stem bar), and a last ring at the head
        top_k = min(int(np.sum(P[:, 1] < zt - 1e-6)) for P, _ in secs) - 1
        ok = np.all([P[:top_k + 1, 0] + FR_D * N[:top_k + 1, 0] >= 0.003 for P, N in secs], axis=0)
        k0 = int(np.nonzero(~ok)[0].max()) + 1 if not ok.all() else 0
        heads = []
        for P, N in secs:
            k = int(np.sum(P[:, 1] < zt - 1e-6)) - 1
            t = (zt - P[k, 1]) / (P[k + 1, 1] - P[k, 1])
            n2 = N[k] + t * (N[k + 1] - N[k])
            heads.append((P[k] + t * (P[k + 1] - P[k]), n2 / np.linalg.norm(n2)))
        pts_n = [[(P[k], N[k]) for P, N in secs] for k in range(k0, top_k + 1)] + [heads]
        for sd, side in SIDES:
            rings = []
            for ring in pts_n:
                R = []
                for (a, b), w in zip(FRAME_L, which):
                    p, n2 = ring[w]
                    q = p + (b if b > 0.0 else 0.0002) * n2       # the flange's face 0.2 mm off the skin (on it
                    # exactly it would share the skin's vertices and edges, and the object would not close)
                    R.append((xk + a, sd * q[0], q[1]))
                rings.append(np.array(R))
            V, F = loft_section(rings, FRAME_L)
            V[:, 2] = np.minimum(V[:, 2], deckhead_z(V[:, 0], V[:, 1]) - BM_T - 0.0005)
            part.add(V, F, "WhitePaint", None, lab(f"Frame {xk:.2f}, {side}", "frame"))
    # the beams across under the deckhead, each cut where it would cross an opening or the mast, and their knees
    rep["beams_cut"] = {}
    for xk in FRAMES:
        _, ye = hull.side_top(xk, pl)
        zt, _ = hull.side_top(xk, pl, below=BM_T)
        cuts = beam_cuts(xk, holes, cut_names)
        if cuts:
            rep["beams_cut"][f"{xk:.3f}"] = [w for _, w in cuts]
        yc = max([c for c, _ in cuts], default=0.0)
        # the beam's web runs out to 4 mm short of the frame's inner edge (the two webs stand in one plane, joined by
        # the knee on their after faces), and its flange on over the frame's head to the plating, each end cut to the
        # side's flare; a cut beam butts its web against the carlin's web (yc) under the carlin's flange, its own
        # flange stopping at the carlin's flange's edge (BM_F further out), so the two flanges never lap
        web_end = lambda x, z: hull.y_at(x, pl + FR_D + 0.004, z)                 # noqa: E731
        fl_end = lambda x, z: hull.y_at(x, pl, z) - 0.0015                       # noqa: E731
        z_web, z_fl = float(deckhead_z(xk, ye)) - BM_D, float(deckhead_z(xk, ye)) - BM_T
        yw = min(web_end(xk + a, z) for a in (BEAM_L[:, 0].min(), BEAM_L[:, 0].max())
                 for z in (z_web, z_fl + BM_T))
        yl = min(fl_end(xk + a, z) for a in (FLANGE_L[:, 0].min(), FLANGE_L[:, 0].max()) for z in (z_fl, z_fl + BM_T))
        yf = yc + BM_F - 2 * WEB
        spans = [(-yw, -yf, web_end, None), (yf, yw, None, web_end)] if cuts else [(-yw, yw, web_end, web_end)]
        for y0, y1, e0, e1 in spans:
            V, F = beam_run(xk, y0, y1, end0=e0, end1=e1)
            part.add(V, F, "WhitePaint", None, lab(f"Beam {xk:.2f}", "beam"))
        for y0, y1, e0, e1 in ((-yl, -(yw - 0.01), fl_end, None), (yw - 0.01, yl, None, fl_end)):
            V, F = beam_run(xk, y0, y1, FLANGE_L, end0=e0, end1=e1)
            part.add(V, F, "WhitePaint", None, lab(f"Beam {xk:.2f}", "beam"))
        if cuts:
            for y0, y1 in ((yc, yf + 0.0005), (-yf - 0.0005, -yc)):     # into the web beside it: no shared end
                V, F = beam_run(xk, y0, y1, WEB_L)
                part.add(V, F, "WhitePaint", None, lab(f"Beam {xk:.2f}", "beam"))
        # the knees: plates on the webs' after faces, from the beam's underside down the frame 'knee', the top edge
        # under the beam's flange out to the frame's flange
        kn = ST["knee"]
        xa_k = xk - WEB - 0.008                       # the knee's after face (its forward face on the beam's web)
        top = hull.inner(xk, pl, zt - kn - 0.2, zt, step=0.01)
        dh = lambda y: float(deckhead_z(xa_k, y))  # noqa: E731
        yo, zo = ye, dh(ye) - BM_T
        for _ in range(4):                            # its outboard top corner on the frame's flange, under the beam's
            yo = hull.y_at(xk, pl + FR_T + 0.0005, zo)
            zo = dh(yo) - BM_T
        for sd, side in SIDES:
            pts, nn, _ = top
            s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
            sa = s[-1] - kn
            pa = np.array([np.interp(sa, s, pts[:, 0]), np.interp(sa, s, pts[:, 1])])
            na = np.array([np.interp(sa, s, nn[:, 0]), np.interp(sa, s, nn[:, 1])])
            na /= np.linalg.norm(na)
            yb = ye - FR_D - kn
            poly = np.array([[yo, zo], pa + (FR_T + 0.0005) * na, pa + FR_D * na,
                             [yb, dh(yb) - BM_D], [yb, dh(yb) - BM_T]])
            poly[:, 0] *= sd
            V, F = deck.slab(poly, (xa_k, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 0.0, 0.008)
            part.add(V, F, "WhitePaint", None, lab(f"Frame {xk:.2f}, {side}", "knee"))
    # carlins: under each cut opening's sides (just outside its coaming) and either side of the mast, from the
    # uncut beam aft of it to the uncut beam forward of it, the flange outboard
    rep["carlins"] = {}
    cut_at = {}
    for xs_, ws in rep["beams_cut"].items():
        for w in ws:
            cut_at.setdefault(w, []).append(float(xs_))
    for what, xc in cut_at.items():
        aft = max(x for x in FRAMES if x < min(xc) - 1e-6)
        fwd = min(x for x in FRAMES if x > max(xc) + 1e-6)
        if what == "mast":
            yw = ST["partners"][0]
        else:
            spec = deck.DK["hatches"].get(what) or deck.DK["skylights"][what]
            yw = spec["width"] / 2 + WEB
        # from the web of the beam aft of it to the web of the beam forward of it; that beam's flange reaches aft over
        # the carlin's end, so the carlin's flange stops at its edge and only its web runs on under it
        x0, x1 = aft + WEB, fwd - WEB
        xf = fwd - BM_F + WEB
        for sd, side in SIDES:
            for xa, xb, prof in ((x0, xf, BEAM_L), (xf - 0.0005, x1, WEB_L)):  # the web lapping its own, no shared end
                c, b = -prof[:, 0] * sd, prof[:, 1]       # the flange outboard
                xx = np.linspace(xa, xb, max(int(math.ceil((xb - xa) / 0.1)), 2) + 1)
                rings = [np.column_stack([np.full(len(c), x), sd * yw + c,
                                          deckhead_z(np.full(len(c), x), sd * yw + c) - b]) for x in xx]
                V, F = loft_section(rings, prof)
                part.add(V, F, "WhitePaint", None, lab(f"Carlin, {what}, {side}", "carlin"))
        rep["carlins"][what] = {"x": [round(x0, 3), round(x1, 3)], "half_y": round(yw, 3)}
        if what == "mast":
            continue
        # the headers: an angle across each end of the opening, between the carlins' webs, its web against the
        # coaming's lining and its flange away from the opening, so the planking's ends there are carried
        xe0, xe1 = spec["x"] - spec["length"] / 2, spec["x"] + spec["length"] / 2
        hx = []
        for xe, toward in ((xe0 - WEB, -1.0), (xe1 + WEB, 1.0)):
            a, b = -BEAM_L[:, 0] * toward, BEAM_L[:, 1]
            near = [xk for xk in FRAMES if f"{xk:.3f}" not in rep["beams_cut"] and abs(xk - xe) < BM_F + 0.02]
            if near:
                raise ValueError(f"the header at x {xe:.3f} ({what}) comes on the beam at {near[0]:.3f}: move the "
                                 "opening or re-space the frames")
            for name, H in holes.items():
                H = np.asarray(H)
                if name in cut_names or H[:, 1].max() < -yw or H[:, 1].min() > yw:
                    continue
                if H[:, 0].max() + 0.035 > xe + a.min() and H[:, 0].min() - 0.035 < xe + a.max():
                    raise ValueError(f"the header at x {xe:.3f} ({what}) passes under {name}'s hole")
            ys = np.linspace(-yw + WEB, yw - WEB, 7)
            rings = [np.column_stack([xe + a, np.full(len(a), y), deckhead_z(xe + a, np.full(len(a), y)) - b])
                     for y in ys]
            V, F = loft_section(rings, BEAM_L)
            part.add(V, F, "WhitePaint", None, lab(f"Header, {what}", "header"))
            hx.append(round(xe, 3))
        rep["carlins"][what]["headers_x"] = hx
    # the mast's partners: short beams across between its carlins fore and aft of it, and the wedges round the mast
    mb = mast_box()
    yw = ST["partners"][0]
    for xp, toward in ((mb["x"][0], -1.0), (mb["x"][1], 1.0)):
        a, b = -BEAM_L[:, 0] * toward, BEAM_L[:, 1]
        ys = np.linspace(-yw + WEB, yw - WEB, 7)                 # between the carlins' webs
        rings = [np.column_stack([xp + a, np.full(len(a), y), deckhead_z(xp + a, np.full(len(a), y)) - b]) for y in ys]
        V, F = loft_section(rings, BEAM_L)
        part.add(V, F, "WhitePaint", None, lab("Mast partners", "partner"))
    s_t, s_b = mb["s"]
    s_t += 0.006
    rings = [spars.ring_at(s_t, 48, 0.0), spars.ring_at(s_t, 48, mb["wedge"]), spars.ring_at(s_b, 48, mb["wedge"]),
             spars.ring_at(s_b, 48, 0.0)]
    V, F = loft_rings(rings, closed=True)
    part.add(V, F, "Varnish", ("solid", WT["teak"]), lab("Mast partners", "wedges"))
    rep["mast_partners"] = {"x": [round(v, 3) for v in mb["x"]], "half_y": yw}
    # the deckhead: the planking's underside, from the after bulkhead to the forward one and out into the plating,
    # with the deck's holes through it
    # (out to 0.5 mm inside the plating at its underside and at its top, whichever is less), its top 'DH_TOP' under
    # the deck's, clear of the fittings let 10 mm into the planking (the mast coat's flange)
    xs = np.linspace(X0 + 0.015, X1 + 0.015, int(round((X1 - X0) / 0.1)) + 1)
    ys = []
    for x in xs:
        z, y = hull.side_top(x, pl + 0.0005)
        ys.append(min(y, hull.y_at(x, pl + 0.0005, z + PLANK - DH_TOP) or y))
    ys = np.array(ys)
    # its ends straight across, with points every 0.1 m so the slab follows the camber there too
    fwd = [(xs[-1], y) for y in np.linspace(ys[-1], -ys[-1], int(math.ceil(2 * ys[-1] / 0.1)) + 1)[1:-1]]
    aft = [(xs[0], y) for y in np.linspace(-ys[0], ys[0], int(math.ceil(2 * ys[0] / 0.1)) + 1)[1:-1]]
    outline = np.concatenate([np.column_stack([xs, ys]), np.array(fwd).reshape(-1, 2),
                              np.column_stack([xs[::-1], -ys[::-1]]), np.array(aft).reshape(-1, 2)])
    inside = {k: np.asarray(v, float) for k, v in holes.items() if X0 < np.asarray(v)[:, 0].mean() < X1}
    # and the mast's: round its wedges at the slab's mid-depth, 1 mm clear (the mast's rake moves them under 1 mm)
    z_mid = float(shell.deck_z(spars.X_P, 0.0)) - 0.5 * (PLANK + DH_TOP)
    inside["mast"] = spars.ring_at((z_mid - spars.Z_P) / math.cos(spars.RAKE), 48, ST["partners"][2] + 0.001)[:, :2]
    to3 = lambda A, t: np.column_stack([A, shell.deck_z(A[:, 0], A[:, 1]) - t])  # noqa: E731
    # the holes' straight sides cut every 5 cm, so the slab follows the camber along them too (a 1 m side drawn as
    # one chord sagged a millimetre under the headers there)
    V, F = region_slab(outline, [densify(h, 0.05) for h in inside.values()], to3, PLANK, DH_TOP, grid=0.12)
    part.add(V, F, "WhitePaint", None, lab("Deckhead", "deckhead"))
    rep["deckhead_holes"] = sorted(inside)
    return rep


def densify(P, step):
    """A closed polygon with points put along each side so none is longer than `step` (its shape unchanged)."""
    P = np.asarray(P, float)
    out = []
    for a, b in zip(P, np.roll(P, -1, axis=0)):
        n = max(int(math.ceil(float(np.linalg.norm(b - a)) / step)), 1)
        out += [a + (b - a) * k / n for k in range(n)]
    return np.array(out)


# ------------------------------------------------------------------------------------------------ the ceiling
def frame_edge(hull, x, z_lo=-9.0, z_hi=9.0, step=0.04):
    """The frames' inner edges as if a frame stood at x: the plating's inside face carried FR_D inboard in the
    section's plane, as the frames' webs are, and on by half the web's thickness times the side's bevel (the edge of
    whichever of the web's faces stands further in) and 0.3 mm. (y, z) points and the in-plane inboard normals."""
    got = hull.inner(x, ST["plating"], z_lo - 0.3, z_hi + 0.3, step=step)
    pts, nn, bev = got
    return pts + (FR_D + 0.5 * FR_T * np.abs(bev) + 0.0003)[:, None] * nn, nn


def web_edge(hull, x, z_lo=-9.0, z_hi=9.0, step=0.04):
    """A frame's web's inner edge in its middle plane as if a frame stood at x (the plating's inside face carried FR_D
    inboard): what a shelf or a cleat fastened to the frames lies against. (y, z) points and the inboard normals."""
    pts, nn, _ = hull.inner(x, ST["plating"], z_lo - 0.3, z_hi + 0.3, step=step)
    return pts + FR_D * nn, nn


def level_point(pts, nn, z):
    """The point of a section's polyline at height z (the first crossing), its tangent (upward) and normal."""
    k = np.where((pts[:-1, 1] - z) * (pts[1:, 1] - z) <= 0)[0]
    if len(k) == 0:
        return None
    k = int(k[0])
    a, b = pts[k], pts[k + 1]
    t = 0.0 if b[1] == a[1] else (z - a[1]) / (b[1] - a[1])
    p = a + t * (b - a)
    tg = (b - a) / np.linalg.norm(b - a)
    n = nn[k] + t * (nn[k + 1] - nn[k])
    return p, tg, n / np.linalg.norm(n)


def room_span(name):
    """A room's clear length: from its after bulkhead's forward face to its forward bulkhead's after face."""
    x0, x1 = RM[name]["x"]
    t = BH["thickness"]
    return x0 + 0.5 * FR_T + t, x1 + 0.5 * FR_T


def board_on(pts, nn, z, w):
    """A flat board w wide, centred (along the line) at height z on a section's polyline, lying on it as a board lies
    on a curved frame: across it, touching where the line stands furthest in and nowhere digging into it. Its outer
    face's two edges and its inboard normal, or None where the line does not reach z or the board would run off it."""
    k = np.where((pts[:-1, 1] - z) * (pts[1:, 1] - z) <= 0)[0]
    if len(k) == 0:
        return None
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    k = int(k[0])
    a, b = pts[k], pts[k + 1]
    t = 0.0 if b[1] == a[1] else (z - a[1]) / (b[1] - a[1])
    sc = s[k] + t * (s[k + 1] - s[k])
    if sc - w / 2 < 0.0 or sc + w / 2 > s[-1]:
        return None
    at = lambda q: np.array([np.interp(q, s, pts[:, 0]), np.interp(q, s, pts[:, 1])])  # noqa: E731
    lo, hi = at(sc - w / 2), at(sc + w / 2)
    c = (hi - lo) / np.linalg.norm(hi - lo)
    n = np.array([-c[1], c[0]])
    if n @ nn[k] < 0:
        n = -n
    inner = np.array([at(q) for q in np.linspace(sc - w / 2, sc + w / 2, 9)])
    lift = max(0.0, float(np.max((inner - lo) @ n)))     # where the line bulges in (a hollow), stand off it
    return lo + lift * n, hi + lift * n, n


_ROWS = {}


def ceiling_rows(hull, name):
    """A room's ceiling as ceiling() draws it: its stations (the room's ends and the frames in it) and its rows, each
    (z, [(lo, hi, nn) at each station]: board_on's outer face and inboard normal); cached by hull and room."""
    key = (id(hull), name)
    if key not in _ROWS:
        r = RM[name]
        bw, bt = CE["batten"]
        x0, x1 = room_span(name)
        st = [x0] + [x for x in FRAMES if x0 < x < x1 - 1e-6] + [x1]
        edges = {x: frame_edge(hull, x, r["sole"], 3.0, step=0.02) for x in st}
        lined = name in CE["lined"]
        w, pitch = (CE["board"] - 0.002, CE["board"]) if lined else (bw, CE["pitch"])
        z0 = r["sole"] + CE["from_sole"]
        z1 = min(hull.side_top(x, ST["plating"] + FR_D)[0] for x in st) - CE["to_deckhead"]
        rows = []
        for k in range(int((z1 - z0 - w) / pitch) + 1):
            z = z0 + 0.5 * w + k * pitch
            got = [board_on(*edges[x], z, w) for x in st]
            if any(g is None for g in got) or min(min(g[0][0], g[1][0]) for g in got) < 0.02:
                continue
            rows.append((z, got))
        _ROWS[key] = {"st": st, "rows": rows, "thickness": bt, "lined": lined, "z": (z0, z1)}
    return _ROWS[key]


def ceiling_face(hull, x, z, row=None):
    """The ceiling's inner face (the battens' or the lining's) at (x, z): its half-breadth there on the row covering z
    (or on `row`, an index into ceiling_rows' rows; or, between rows, the nearest), carried past the row's edges, with
    the row's index and its band (z from, to) at x."""
    name, _ = room_at(x)
    c = ceiling_rows(hull, name)
    st, bt = c["st"], c["thickness"]
    k = min(max(int(np.searchsorted(st, x)) - 1, 0), len(st) - 2)
    u = (x - st[k]) / (st[k + 1] - st[k])
    best = None
    for i, (_, got) in enumerate(c["rows"]):
        if row is not None and i != row:
            continue
        (la, ha, na), (lb, hb, nb) = got[k], got[k + 1]
        lo = (1 - u) * (la + bt * na) + u * (lb + bt * nb)
        hi = (1 - u) * (ha + bt * na) + u * (hb + bt * nb)
        band = (min(lo[1], hi[1]), max(lo[1], hi[1]))
        off = max(band[0] - z, z - band[1], 0.0)
        if best is None or off < best[0]:
            t = (z - lo[1]) / (hi[1] - lo[1])
            best = (off, (float(lo[0] + t * (hi[0] - lo[0])), i, band))
    if best is None:
        raise ValueError(f"no ceiling row in the {name} at x {x:.2f}")
    return best[1]


def ceiling(part, hull):
    """Battens on the frames' inner edges in every room but the bare ones (the forepeak), or the galley's
    tongue-and-groove lining: horizontal, from 'from_sole' over the room's (lower) sole to 'to_deckhead' under the
    deckhead at the side, each flat across the frames' curve (board_on), a row left out where it would come within
    2 cm of the centreline (the bow's narrow bottom). A ceiled room with no row is an error."""
    rep = {}
    for name, r in ROOMS:
        if name in CE["bare"]:
            rep[name] = {"rows_each_side": 0, "kind": "bare (the frames show)"}
            continue
        c = ceiling_rows(hull, name)
        if not c["rows"]:
            raise ValueError(f"the {name}'s ceiling has no row between {c['z'][0]:.3f} and {c['z'][1]:.3f}")
        bt, lined = c["thickness"], c["lined"]
        for z, got in c["rows"]:
            for sd, side in SIDES:
                rings = []
                for x, (lo, hi, nn) in zip(c["st"], got):
                    q = np.array([lo, hi, hi + bt * nn, lo + bt * nn])
                    rings.append(np.column_stack([np.full(4, x), sd * q[:, 0], q[:, 1]]))
                V, F = loft_rings(rings)
                if lined:
                    part.add(V, F, "WhitePaint", ("solid", WT["pine"]), lab(f"{name} lining, {side}", "lining"))
                else:
                    part.add(V, F, "Varnish", ("solid", WT["pine"]), lab(f"{name} ceiling, {side}", "batten"))
        rep[name] = {"rows_each_side": len(c["rows"]), "from_z": round(c["z"][0], 3), "to_z": round(c["z"][1], 3),
                     "kind": "lining" if lined else "battens"}
    return rep


# ------------------------------------------------------------------------------------------------ bulkheads
def section_outline(hull, x, z_bot, d=None, x2=None, clear=0.0):
    """A bulkhead's outline at x in (y, z): the surface d inboard of the plating's outside (its inside face unless
    given) from z_bot up to the deckhead on each side and the deckhead across, closed along z_bot (or, where the
    section's bottom is above z_bot, across its bottom at the centreline). With x2 (a plate from x to x2), inside that
    section too and `clear` under the deckhead at both."""
    d = ST["plating"] if d is None else d
    at = (x,) if x2 is None else (x, x2)
    zt = min(hull.side_top(xx, d, below=clear)[0] for xx in at)
    pts, _, _ = hull.inner(x, d, z_bot, zt, step=0.05, y_min=0.0005)
    if x2 is not None:
        for p in pts:
            p[0] = min(p[0], hull.y_at(x2, d, p[1]) or p[0])
    ys = np.linspace(pts[-1, 0], -pts[-1, 0], 25)[1:-1]
    top = np.column_stack([ys, np.min([deckhead_z(np.full(len(ys), xx), ys) for xx in at], axis=0) - clear])
    port = pts[::-1] * np.array([-1.0, 1.0])
    P = np.concatenate([pts, top, port])
    if pts[0, 1] <= z_bot + 1e-6:
        P[0, 1] = P[-1, 1] = z_bot
    return clean_poly(P)


def board_polys(outline, y0, y1, cuts=()):
    """The outline clipped to the strip y0..y1, less each cut (z0, z1) across it: convex pieces."""
    P = clip_halfplane(clip_halfplane(outline, -1.0, 0.0, -y0), 1.0, 0.0, y1)
    if len(P) < 3:
        return []
    out = [P]
    for z0, z1 in cuts:
        nxt = []
        for Q in out:
            lo = clip_halfplane(Q, 0.0, 1.0, z0)
            hi = clip_halfplane(Q, 0.0, -1.0, -z1)
            nxt += [R for R in (lo, hi) if len(R) >= 3 and abs(deck.poly_area(R)) > 1e-6]
        out = nxt
    return [clean_poly(Q) for Q in out]


DOOR_FW, DOOR_PR, SILL_OVER = 0.05, 0.006, 0.01  # a door's frame: its width, proud of the boards; the sill prouder


def sill_face(xb):
    """The forward face of the sill of the door (or scuttle) in the bulkhead on frame xb."""
    return xb + 0.5 * FR_T + BH["thickness"] + DOOR_PR + SILL_OVER


def bulkhead_list():
    """Each bulkhead: (x of its frame, the room aft, the room forward, kind)."""
    out = [(ROOMS[0][1]["x"][0], None, ROOMS[0][0], "door_closed")]
    for (na, ra), (nb, rb) in zip(ROOMS[:-1], ROOMS[1:]):
        out.append((ra["x"][1], na, nb, "scuttle" if nb == "Forepeak" else "door"))
    out.append((ROOMS[-1][1]["x"][1], ROOMS[-1][0], None, "plate"))
    return out


def bulkheads(part, hull, steel):
    """The joiner's bulkheads (in `part`), each on the forward face of its frame: tongue-and-groove pine boards up to
    the deckhead beside the beam, round a door on the centreline (or the forepeak's scuttle) with its frame and sill
    and its leaf hooked back to port on the forward face (the after bulkhead's door shut); the forward bulkhead at the
    forward end a plain steel plate, with the structure (in `steel`)."""
    t, bwid = BH["thickness"], CE["board"]
    rep = {}
    for xb, aft, fwd, kind in bulkhead_list():
        xa_ = xb + 0.5 * FR_T                         # its after face
        soles = [sole_at(n, xb + (0.1 if n == fwd else -0.1)) for n in (aft, fwd) if n]
        z_bot = min(soles) - 0.12
        if kind == "plate":
            # the forward bulkhead: a steel plate on the last frame's forward face, the stem bar closing its foot
            tp = 0.010
            outline = section_outline(hull, xa_ + tp, z_bot, ST["plating"] + 0.0015, x2=xa_, clear=0.0005)
            V, F = deck.slab(outline, (xa_, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 0.0, tp)
            steel.add(V, F, "WhitePaint", None, lab("Forward bulkhead", "bulkhead"))
            rep[f"{xb:.3f}"] = {"kind": "forward bulkhead (steel plate, in the hull's weight)", "thickness_m": tp}
            continue
        # each face of the boards 1.5 mm inside the plating and 0.5 mm under the deckhead (its sheer and camber)
        outline = section_outline(hull, xa_ + t, z_bot, ST["plating"] + 0.0015, x2=xa_, clear=0.0005)
        hi = max(soles)
        fw, pr = DOOR_FW, DOOR_PR
        w = (BH["scuttle"] if kind == "scuttle" else BH["door"])[0]
        # the beam over it, lowest across the frame's head (the deck's camber drops it toward the sides)
        beam_under = min(float(deckhead_z(xb, y)) for y in np.linspace(0.0, w / 2 + fw, 5)) - BM_D
        if kind == "scuttle":
            _, h, sill = BH["scuttle"]
            z0 = sole_at(aft, xb - 0.1) + sill
            z1 = min(z0 + h, beam_under - fw - 0.002)  # the frame's head under the beam
        else:
            h = BH["door"][1]
            z0 = hi + 0.04                             # over its sill
            z1 = min(hi + h, beam_under - BH["head_clear"])
        # boards outward from the jambs, and over and under the opening
        ymax = float(np.abs(outline[:, 0]).max())
        strips = []
        nd = max(int(round(w / bwid)), 1)
        for k in range(nd):
            strips.append((-w / 2 + k * w / nd, -w / 2 + (k + 1) * w / nd, True))
        y = w / 2
        while y < ymax:
            strips.append((y, min(y + bwid, ymax + 0.01), False))
            strips.append((-min(y + bwid, ymax + 0.01), -y, False))
            y += bwid
        nb = 0
        for y0, y1, door in strips:
            for Q in board_polys(outline, y0 + 0.001, y1 - 0.001, [(z0, z1)] if door else []):
                V, F = deck.slab(Q, (xa_, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 0.0, t)
                part.add(V, F, "WhitePaint", ("solid", WT["pine"]), lab(f"Bulkhead {xb:.2f}", "bulkhead"))
                nb += 1
        # the frame round the opening: jambs, head and sill, 6 mm proud of each face
        xc = xa_ + 0.5 * t
        for sd in (1.0, -1.0):
            V, F = box((xc, sd * (w / 2 + fw / 2), 0.5 * (z0 + z1 + fw)), (0.5 * t + pr, fw / 2, 0.5 * (z1 + fw - z0)))
            part.add(V, F, "Varnish", ("solid", WT["teak"]), lab(f"Bulkhead {xb:.2f}", "door frame"))
        V, F = box((xc, 0.0, z1 + fw / 2), (0.5 * t + pr, w / 2 + 0.0005, fw / 2))
        part.add(V, F, "Varnish", ("solid", WT["teak"]), lab(f"Bulkhead {xb:.2f}", "door frame"))
        zs = z0 - 0.04 if kind == "door" else z0 - 0.03
        V, F = box((xc, 0.0, 0.5 * (zs + z0)), (0.5 * t + pr + SILL_OVER, w / 2 + 0.0005, 0.5 * (z0 - zs)))
        part.add(V, F, "Varnish", ("solid", WT["teak"]), lab(f"Bulkhead {xb:.2f}", "sill"))
        # the leaf, 2 mm clear of its frame all round when shut, on two bronze hinges at the port jamb: shut in its
        # frame (the after bulkhead), or swung forward and round flat against the port jamb's forward face, held
        # off the boards there by a block under its outer edge (where its hook would be)
        lt, half = BH["leaf"], 0.5 * (z1 - z0) - 0.002
        gb = f"Bulkhead {xb:.2f}"
        if kind == "door_closed":
            V, F = box((xc, 0.0, 0.5 * (z0 + z1)), (0.5 * lt, w / 2 - 0.002, half))
            hinge_at = (xc + 0.5 * lt, -w / 2 + 0.001)          # its pin at the leaf's forward edge
        else:
            xh = xa_ + t + pr                                  # the jamb's forward face
            yo = w / 2 + fw + 0.002                            # the leaf's hinge edge, past the jamb
            V, F = box((xh + 0.5 * lt, -(yo + w / 2 - 0.002), 0.5 * (z0 + z1)), (0.5 * lt, w / 2 - 0.002, half))
            hinge_at = (xh + 0.002, -(w / 2 + fw + 0.001))     # its pin at the jamb's outer corner
            V2, F2 = box((xa_ + t + 0.5 * pr, -(yo + w - 0.004 - 0.03), 0.5 * (z0 + z1)), (0.5 * pr, 0.02, 0.03))
            part.add(V2, F2, "Varnish", ("solid", WT["teak"]), lab(gb, "door stop"))
        part.add(V, F, "Varnish", ("solid", WT["teak"]), lab(gb, "door"))
        for zh in (z0 + 0.2, z1 - 0.2):
            V, F = deck.revolve([(0.0, -0.05), (0.006, -0.05), (0.006, 0.05), (0.0, 0.05)],
                                (hinge_at[0], hinge_at[1], zh), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 12)
            part.add(V, F, "Bronze", ("solid", spars.BRZ), lab(gb, "hinge"))
        rep[f"{xb:.3f}"] = {"kind": kind, "between": [aft, fwd], "opening_m": [round(w, 3), round(z1 - z0, 3)],
                            "sill_z": round(z0, 3), "head_z": round(z1, 3), "boards": nb,
                            "beam_underside_z": round(beam_under, 3)}
    return rep


# ------------------------------------------------------------------------------------------------ soles
def mast_outline_at(z):
    """The mast's section (plan points) at height z."""
    s = (z - spars.Z_P) / math.cos(spars.RAKE)
    return spars.ring_at(s, 48)[:, :2]


def sole_planks(part, hull, name, x0, x1, z, group, slat=None, holes=()):
    """Planks fore and aft over x0..x1 at height z (their tops), each 'sole_plank' wide (or `slat`: (width, gap) for a
    slatted platform) out to 'sole_clear' from the frames' inner edges, the outer planks scribed to that edge and
    tapering out where the hull closes in, cut round the mast where it passes and round each of `holes` ((x, y,
    radius): a pipe through them)."""
    pw = RM["sole_plank"]
    gap = 0.003
    if slat:
        pw, gap = slat[0] + slat[1], slat[1]
    th = RM["sole_thickness"]
    xs = np.linspace(x0, x1, max(int(math.ceil((x1 - x0) / 0.08)), 2) + 1)
    half = []
    for x in xs:
        pts, nn = frame_edge(hull, x, z - 0.2, z + 0.2)
        g = level_point(pts, nn, z - th)
        g2 = level_point(pts, nn, z)
        half.append(min(g[0][0] if g else 0.0, g2[0][0] if g2 else 0.0) - RM["sole_clear"])
    half = np.array(half)
    mast = mast_outline_at(z)
    in_mast = x0 < mast[:, 0].mean() < x1
    n = int(math.ceil(half.max() / pw)) + 1
    count, tip = 0, 0.006
    for k in range(-n, n):
        y0, y1 = k * pw + 0.5 * gap, (k + 1) * pw - 0.5 * gap
        near = min(abs(y0), abs(y1)) if y0 * y1 > 0 else 0.0
        room = half - near                           # how much of the plank's width the sole has here
        ok = room >= tip
        if ok.sum() < 1:
            continue
        # the plank's run (the longest stretch where it fits), its ends carried out to where it tapers to `tip`
        idx = np.nonzero(ok)[0]
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        run = max(runs, key=len)
        i0, i1 = int(run[0]), int(run[-1])
        cross = lambda i, j: xs[i] + (tip - room[i]) / (room[j] - room[i]) * (xs[j] - xs[i])  # noqa: E731
        xa = xs[i0] if i0 == 0 else cross(i0 - 1, i0)
        xb = xs[i1] if i1 == len(xs) - 1 else cross(i1, i1 + 1)
        if xb - xa < 0.05:
            continue
        out = []
        if in_mast:
            m = mast[(mast[:, 1] > y0 - 0.02) & (mast[:, 1] < y1 + 0.02)]
            if len(m):
                out.append((m[:, 0].min() - 0.012, m[:, 0].max() + 0.012))
        for hx, hy, hr in holes:
            if y0 - hr < hy < y1 + hr:
                out.append((hx - hr, hx + hr))
        cuts = [(xa, xb)]
        for oa, ob in sorted(out):
            cuts = [piece for ca, cb in cuts for piece in ((ca, min(cb, oa)), (max(ca, ob), cb)) if piece[1] > piece[0]]
        for ca, cb in cuts:
            if cb - ca < 0.05:
                continue
            inner = xs[(xs > ca + 1e-6) & (xs < cb - 1e-6)]
            xq = np.concatenate([[ca], inner, [cb]])
            hq = np.interp(xq, xs, half)
            lq = np.maximum(y0, -hq)
            uq = np.minimum(y1, hq)
            if y0 * y1 > 0:                          # the tip keeps `tip` of width where the edge closes on it
                if y0 > 0:
                    uq = np.maximum(uq, y0 + tip)
                else:
                    lq = np.minimum(lq, y1 - tip)
            top = np.stack([np.column_stack([xq, lq, np.full(len(xq), z)]),
                            np.column_stack([xq, uq, np.full(len(xq), z)])], axis=1)
            bot = top - np.array([0.0, 0.0, th])
            V, F = strip_solid(top, bot)
            part.add(V, F, "Pine", ("solid", WT["pine"]), lab(group, "slat" if slat else "sole"))
            count += 1
    return count


def bearers(part, hull, x0, x1, z_top, group, depth=0.07):
    """The bearers a sole's planks (their undersides at z_top) lie on: a pine bearer 50 mm fore and aft on the forward
    face of each frame between x0 and x1, and a cleat on each end's bulkhead, each scribed to 2 mm inside the frames'
    edges (wider at its top than its foot, where the bottom is narrower), cut round the mast where it passes."""
    n = 0
    xs = [(x + 0.5 * FR_T, x + 0.5 * FR_T + 0.05) for x in FRAMES if x0 + 0.06 < x < x1 - 0.06]
    for xa, xb in xs + [(x0, x0 + 0.03), (x1 - 0.03, x1)]:
        z0 = z_top - (depth if xb - xa > 0.04 else 0.05)
        hw = {z0: 9.0, z_top: 9.0}
        for x in (xa, xb):
            pts, nn = frame_edge(hull, x, z0 - 0.1, z_top + 0.1)
            for z in (z0, z_top):
                g = level_point(pts, nn, z)
                hw[z] = min(hw[z], float(g[0][0]) - 0.002 if g else 0.0)
        if hw[z0] < 0.05:
            continue
        m = np.concatenate([mast_outline_at(z) for z in (z0, z_top)])
        m = m[(m[:, 0] > xa - 0.012) & (m[:, 0] < xb + 0.012)]
        ym = float(np.abs(m[:, 1]).max()) + 0.012 if len(m) else 0.0
        for sg in ((-1.0, 1.0) if ym else (0.0,)):
            if ym:
                if hw[z0] - ym < 0.04:
                    continue
                P = np.array([(sg * ym, z0), (sg * hw[z0], z0), (sg * hw[z_top], z_top), (sg * ym, z_top)])
            else:
                P = np.array([(-hw[z0], z0), (hw[z0], z0), (hw[z_top], z_top), (-hw[z_top], z_top)])
            V, F = deck.slab(P, (xa, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 0.0, xb - xa)
            part.add(V, F, "Pine", ("solid", WT["pine"]), lab(group, "bearer"))
            n += 1
    return n


def soles(part, hull):
    """Each room's sole (the forepeak's slatted platform), the washroom's riser and the steps where soles differ by
    more than 'step_max', and a collar round the mast at the galley's sole."""
    rep = {}
    for name, r in ROOMS:
        x0, x1 = room_span(name)
        if name == "Forepeak":
            fp = IN["forepeak"]
            import furniture
            nx, ny = furniture.navel_at()
            xp0 = max(fp["platform"][0], sill_face(r["x"][0]) + 0.0005)   # clear of the scuttle's sill
            n = sole_planks(part, hull, name, xp0, fp["platform"][1], r["sole"], "Forepeak platform",
                            slat=(0.07, 0.03), holes=[(nx, ny, fp["navel"]["r"] + 0.004)])
            nb = bearers(part, hull, x0, fp["platform"][1], r["sole"] - RM["sole_thickness"], "Forepeak platform")
            rep[name] = {"platform_z": r["sole"], "x": [round(xp0, 4), fp["platform"][1]], "slats": n, "bearers": nb}
            continue
        if "sole_forward" in r:
            xf, zf = r["sole_forward"]
            import furniture
            through = furniture.wc_pipes() if name == "Washroom" else []
            n = sole_planks(part, hull, name, x0, xf, r["sole"], f"{name} sole",
                            holes=[(x, y, rp + 0.004) for x, y, rp in through])
            n += sole_planks(part, hull, name, xf, x1, zf, f"{name} sole")
            th = RM["sole_thickness"]
            nb = bearers(part, hull, x0, xf - 0.022, r["sole"] - th, f"{name} sole")
            nb += bearers(part, hull, xf, x1, zf - th, f"{name} sole")
            pts, nn = frame_edge(hull, xf, zf - 0.4, zf + 0.1)
            g = level_point(pts, nn, r["sole"])
            yr = (g[0][0] if g else 0.3) - RM["sole_clear"]
            V, F = box((xf - 0.011, 0.0, 0.5 * (r["sole"] + zf - th)), (0.011, yr, 0.5 * (zf - th - r["sole"])))
            part.add(V, F, "Pine", ("solid", WT["pine"]), lab(f"{name} sole", "riser"))
        else:
            n = sole_planks(part, hull, name, x0, x1, r["sole"], f"{name} sole")
            nb = bearers(part, hull, x0, x1, r["sole"] - RM["sole_thickness"], f"{name} sole")
        rep[name] = {"sole_z": r["sole"], "x": [round(x0, 3), round(x1, 3)], "planks": n, "bearers": nb}
    # steps up to a door where the sole beyond it is more than step_max higher, and up to the forepeak's scuttle
    rep["steps"] = []
    for xb, aft, fwd, kind in bulkhead_list():
        if kind not in ("door", "scuttle"):
            continue
        za, zf = sole_at(aft, xb - 0.1), sole_at(fwd, xb + 0.1)
        top = RM["step_max"]
        if kind == "scuttle":
            zf, top = za + BH["scuttle"][2], BH["scuttle_step"]
        dz = zf - za
        if abs(dz) <= top + 1e-9:
            continue
        nst = int(math.ceil(abs(dz) / top)) - 1
        # each step 0.25 m deep, the first against the bulkhead (0.5 mm off it), as wide as the opening but kept
        # 'sole_clear' inside the frames' edges where the bow's bottom narrows, so clear of the frame's web
        near = xb + 0.5 * FR_T - 0.0005 if dz > 0 else xb + 0.5 * FR_T + BH["thickness"] + 0.0005
        z_lo = min(za, zf)
        for k in range(1, nst + 1):
            zt = z_lo + abs(dz) * k / (nst + 1)
            xa = near - k * 0.25 * np.sign(dz)
            xb_ = near - (k - 1) * 0.25 * np.sign(dz)
            sw = BH["scuttle"][0] if kind == "scuttle" else BH["door"][0]
            hw = sw / 2
            for x in (xa, xb_):
                pts, nn = frame_edge(hull, x, z_lo - 0.1, zt + 0.1)
                for z in (z_lo, zt):
                    g = level_point(pts, nn, z)
                    if g:
                        hw = min(hw, float(g[0][0]) - RM["sole_clear"])
            V, F = box((0.5 * (xa + xb_), 0.0, 0.5 * (zt + z_lo)), (0.5 * abs(xb_ - xa), hw, 0.5 * (zt - z_lo)))
            part.add(V, F, "Pine", ("solid", WT["pine"]), lab(f"Step at {xb:.2f}", "step"))
            rep["steps"].append({"at": round(xb, 3), "top_z": round(zt, 3), "rise_m": round(abs(dz) / (nst + 1), 3),
                                 "width_m": round(2 * hw, 3)})
    # the collar round the mast where it passes the galley's sole: its foot flat on the planks round their cut (the
    # mast's section square to its raked axis is levelled onto the sole), its top 22 mm up
    zs = RM["Galley"]["sole"]
    s0 = (zs - spars.Z_P) / math.cos(spars.RAKE)

    def level(r, z):
        r = np.array(r, float)
        r[:, 2] = z
        return r
    rings = [level(spars.ring_at(s0, 48, 0.0125), zs), level(spars.ring_at(s0, 48, 0.06), zs),
             level(spars.ring_at(s0 + 0.018, 48, 0.05), zs + 0.018),
             level(spars.ring_at(s0 + 0.022, 48, 0.0125), zs + 0.022)]
    V, F = loft_rings(rings, closed=True)
    part.add(V, F, "Varnish", ("solid", WT["teak"]), lab("Mast collar", "collar"))
    return rep


# ------------------------------------------------------------------------------------------------ the whole
LINING = PLANK + BM_D + 0.002                    # the coamings' linings reach the beams' underside (deck.build)
MATERIALS = {"WhitePaint": (0.42, 0.0, 0.0), "Pine": (0.82, 0.0, 0.0), "Varnish": (0.3, 0.0, 1.0),
             "Canvas": (0.9, 0.0, 0.0), "Zinc": (0.45, 0.8, 0.0), "Porcelain": (0.12, 0.0, 0.6)}  # rough, metal, coat


def build(S, holes):
    """{object name: SparPart} and the report."""
    hull = Hull(S)
    parts = {k: spars.SparPart(k) for k in OBJECTS}
    cut = list(IN["openings"]["hatches"]) + list(IN["openings"]["skylights"])
    rep = {"structure": structure(parts["Below.Structure"], hull, holes, cut)}
    rep["ceiling"] = ceiling(parts["Below.Ceiling"], hull)
    rep["bulkheads"] = bulkheads(parts["Below.Joinery"], hull, parts["Below.Structure"])
    rep["soles"] = soles(parts["Below.Joinery"], hull)
    import furniture
    side = furniture.Side(hull)
    rep["mess"] = furniture.mess(parts, side)
    rep["galley"] = furniture.galley(parts, side)
    rep["bins"] = furniture.bins(parts, side)
    rep["ladders"] = furniture.ladders(parts, holes)
    rep["cots"] = furniture.cots(parts, side, list(FRAMES))
    rep["washroom"] = furniture.washroom(parts, side)
    rep["forepeak"] = furniture.forepeak(parts, side, hull, list(FRAMES))
    rep["coaming_linings"] = coaming_linings(parts["Below.Joinery"], cut)
    cr = rep["forepeak"]["windlass"]["crank"]
    cr["clearance"] = furniture.crank_clearance(parts, cr.pop("sweep"), RM["Forepeak"]["sole"])
    if min(cr["clearance"]["fist_m"], cr["clearance"]["arm_m"], cr["clearance"]["platform_under_fist_m"]) < 0.02:
        raise ValueError(f"the windlass's crank does not turn clear: {cr['clearance']}")
    rep["headroom"] = headroom()
    rep["weights"] = weights(parts)
    return parts, rep


def coaming_linings(part, names):
    """The coamings' linings below the deck: deck.coaming_ring draws each opened hatch's and skylight's coaming on down
    through the planking to LINING under the deck's top, and weighs only what stands above it; the rest, its walls
    round the opening (teak, the coaming's thickness), is weighed here with the accommodation."""
    tb = deck.TB
    out = {}
    for name in names:
        spec = deck.DK["hatches"].get(name) or deck.DK["skylights"][name]
        t = tb["coaming"]
        area = 2 * (spec["length"] + spec["width"] - 2 * t) * LINING
        kg = tb["teak"] * t * area
        c = [spec["x"], spec.get("y", 0.0), float(shell.deck_z(spec["x"], 0.0)) - 0.5 * LINING]
        part.weight(f"Coaming lining: {name}", kg, c)
        out[name] = round(kg, 1)
    return out


def headroom(walkway=0.3):
    """Each room's headroom from its sole (the higher, where it has two), on the centreline and over the walkway (out
    to `walkway` each side, where the deck's camber brings the deckhead down): under the deck beams over it (the
    lowest beam's underside: the carlins and the openings' headers are as deep) and between the beams, to the
    deckhead at its lowest."""
    out = {}
    for name, r in ROOMS:
        x0, x1 = r["x"]
        zs = max(r["sole"], r["sole_forward"][1] if "sole_forward" in r else r["sole"])
        xs = [f for f in FRAMES if x0 <= f <= x1]
        row = {"sole_z": zs}
        for key, ys in (("centreline", [0.0]), (f"walkway_{2 * walkway:.1f}_m", [-walkway, 0.0, walkway])):
            beams = min(float(deckhead_z(f, y)) for f in xs for y in ys) - BM_D
            head = min(float(deckhead_z(x, y)) for x in np.linspace(x0, x1, 41) for y in ys)
            row[key] = {"under_beams_m": round(beams - zs, 3), "between_beams_m": round(head - zs, 3)}
        row["lowest_beam_underside_z"] = round(min(float(deckhead_z(f, 0.0)) for f in xs) - BM_D, 3)
        row["headroom_m"] = row["centreline"]["under_beams_m"]
        row["between_beams_m"] = row["centreline"]["between_beams_m"]
        out[name] = row
    return out


GROUND_TACKLE = ("Windlass", "Cable", "Bower anchor", "Bower chocks", "Spurling pipe", "Navel pipe")


def weights(parts):
    """What the interior weighs, in two rows: the ground tackle (the windlass, the cable, the bower on its chocks and
    the spurling and navel pipes: weighed with the deck hardware against the size card's winches and hardware, in place
    of slice 8's estimate) and the rest, the accommodation forward (part of the card's accommodation, which slice 10's
    aft cabins share). Each row by kind of piece, with its total and centre."""
    rows = {"ground_tackle": {}, "accommodation_forward": {}}
    for p in parts.values():
        for m in p.masses:
            g = m["part"].split(" | ")[0].split(",")[0].split(":")[0].split(" (")[0].strip()
            key = "ground_tackle" if g in GROUND_TACKLE else "accommodation_forward"
            t = rows[key].setdefault(g, {"kg": 0.0, "mom": np.zeros(3)})
            t["kg"] += m["kg"]
            t["mom"] += m["kg"] * np.asarray(m["centre"], float)
    missing = [g for g in GROUND_TACKLE if g not in rows["ground_tackle"]]
    if missing:                                     # a group renamed would move its weight to the other row unseen
        raise ValueError(f"the ground tackle's {missing} weigh nothing: renamed? (interior.GROUND_TACKLE)")
    out = {}
    for key, groups in rows.items():
        kg = sum(v["kg"] for v in groups.values())
        mom = sum((v["mom"] for v in groups.values()), np.zeros(3))
        out[key] = {"rows": {g: {"kg": round(v["kg"], 1), "centre": [round(float(a), 3) for a in v["mom"] / v["kg"]]}
                             for g, v in sorted(groups.items()) if v["kg"] > 0},
                    "total_kg": round(kg, 1), "total_long_tons": round(kg / deck.LT_KG, 3),
                    "centre": [round(float(a), 3) for a in mom / max(kg, 1e-9)]}
    return out
