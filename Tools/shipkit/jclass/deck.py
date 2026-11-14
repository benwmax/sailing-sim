"""Bluebonnet's deck and what stands on it (docs/jclass-3): the laid teak deck with the cockpit let into it, the toe
rail, the hatches, skylights, companionway and doghouse, the steering gear's box, the wheel and the binnacle.

The deck is a surface over the hull's sheer with the period's beam camber (shell.deck_z: every beam cut from one
mould, so the deck rises less where it is narrower). It is one mesh that closes with the shell and transom into one
watertight solid: its edge is the shell's own sheer and the transom's top row, and the cockpit is a hole in it whose
walls and sole close it again. The planking is not modelled. Each vertex carries three UV maps from which the deck's
material draws the planks, seams, butts, king plank and covering boards, with the planks nibbed into the covering
boards (planking_terms, which build_jclass.py's 'Planking' shader and the deck drawing both run; the game's material
can do the same from the same maps):
  Planking  (x, y)          metres in the hull's frame
  Margin    (d, y_m)        d: distance square to the sheer in plan; y_m: |y| of the covering board's inner edge at
                            this x before nibbing (FAR where there is no covering board)
  Aft       (d_aft, s)      d_aft: distance forward of the deck's after edge; s: |dy_m/dx|, how fast the covering
                            board's edge crosses the planks (for the nibs' square ends)
Everything that stands on the deck is a set of closed solids, each let a few millimetres into the deck so it sits on
it with no gap, gathered into one object per kind. Weights come from the same geometry and the timber sizes in
deck_bluebonnet.json (`Part.masses`).

Geometry is in the hull's frame (X forward, Y starboard, Z up), and a face is wound so that numpy's cross product of
its edges points out of its solid: build_jclass.py turns y over and the faces round for Blender.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import shell  # noqa: E402

DK = json.load(open(os.path.join(HERE, "deck_bluebonnet.json")))
PL, TB = DK["deck"]["planking"], DK["timber"]
LET = DK["deck"]["let_in"]
FAR = 99.0                    # a UV value meaning 'no covering board / after margin here'
LT_KG = 1016.047              # kg per long ton
K_CAMBER = shell.DECK_CAMBER / shell.HDM ** 2
NY_AFT = 12                   # points across each half of the transom's top row


def _plain_u():
    """A place along the planks (U) as far as can be from every butt, port's and starboard's: a lid or the cockpit's
    sole sits there in the deck's pattern, so its planks run whole."""
    offs = sorted({(s + d) % 1.0 for s in PL["butt_stagger"] for d in (0.0, PL["starboard_shift"])})
    gaps = [((offs[(i + 1) % len(offs)] - offs[i]) % 1.0 or 1.0, offs[i]) for i in range(len(offs))]
    g, o = max(gaps)
    return PL["plank_length"] * (o + g / 2)


PLAIN_U = _plain_u()
PLAIN_Y = PL["king_plank"] / 2 + 40.5 * PL["pitch"]     # the middle of a plank well out from the king plank


def transom_tilt():
    """dx/dz of the transom's plane (its top leans aft)."""
    (xtb, ztb), (xtt, ztt) = loft.END["transom_bottom"], loft.END["transom_top"]
    return (xtt - xtb) / (ztt - ztb)


def aft_row(corner):
    """The deck's after edge, port to starboard, across the transom's top from the sheer's corner point (x, hd, z)
    (starboard): the beam camber's curve, leaning with the transom so it stays in the transom's plane. The transom's
    own top edge is the same row (build_jclass.transom_mesh)."""
    x0, hd, zs = (float(c) for c in corner)
    tilt = transom_tilt()
    row = []
    for k in range(2 * NY_AFT + 1):
        y = hd * (-1.0 + k / NY_AFT)
        z = zs + K_CAMBER * (hd * hd - y * y) if 0 < k < 2 * NY_AFT else zs
        row.append((x0 + tilt * (z - zs), y, z))
    return np.array(row)


def loft_sheer(n=460):
    """The sheer from the loft's own curves (starboard, the transom's corner to the stem head), for the first pass of
    the build before the shell exists (build_jclass.py measures the deck's weight on it, then rebuilds on the shell's
    sheer and checks the two agree)."""
    xs = np.linspace(*shell.DECK_X, n)
    hd = np.maximum(loft.DECK_HB(xs), 0.0)
    hd[-1] = 0.0
    return np.stack([xs, hd, loft.SHEER(xs)], 1)


# ------------------------------------------------------------------------------------------------ geometry helpers
def rrect(cx, cy, L, W, r, n=6):
    """A rounded rectangle in plan, counter-clockwise in (x, y): L fore and aft, W athwartships, corner radius r."""
    r = max(min(r, L / 2 - 1e-4, W / 2 - 1e-4), 0.004)
    pts = []
    for sx, sy, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((cx + sx * (L / 2 - r) + r * math.cos(a), cy + sy * (W / 2 - r) + r * math.sin(a)))
    return np.array(pts)


def rshape(cx, cy, L, W, r, n=6):
    """rrect as a function of an outward offset o: the same number of points at any offset."""
    return lambda o=0.0: rrect(cx, cy, L + 2 * o, W + 2 * o, r + o, n)


def poly_area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def in_poly(pts, P):
    """Even-odd test of points (m, 2) against polygon P (n, 2)."""
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    x0, y0 = P[:, 0][None, :], P[:, 1][None, :]
    x1, y1 = np.roll(P[:, 0], -1)[None, :], np.roll(P[:, 1], -1)[None, :]
    cross = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / np.where(y1 != y0, y1 - y0, 1e-30) + x0)
    return np.count_nonzero(cross, axis=1) % 2 == 1


def seg_dist(pts, P, closed=True, chunk=800):
    """Least distance from points (m, 2) to the polyline P (n, 2)."""
    A = P if closed else P[:-1]
    B = np.roll(P, -1, axis=0) if closed else P[1:]
    d = B - A
    L2 = np.maximum(np.sum(d * d, 1), 1e-30)
    out = np.empty(len(pts))
    for s in range(0, len(pts), chunk):
        q = pts[s:s + chunk][:, None, :]
        t = np.clip(np.sum((q - A[None]) * d[None], 2) / L2[None], 0, 1)
        c = A[None] + t[..., None] * d[None]
        out[s:s + chunk] = np.sqrt(np.min(np.sum((q - c) ** 2, 2), 1))
    return out


def densify(P, step):
    """A closed polygon with points added along any edge longer than step, so it follows a curved surface."""
    out = []
    for a, b in zip(P, np.roll(P, -1, axis=0)):
        n = max(int(math.ceil(np.linalg.norm(b - a) / step)), 1)
        out.extend(a + (b - a) * (k / n) for k in range(n))
    return np.array(out)


def edges_cross(A, B):
    """Does any edge of the closed polygon A properly cross an edge of the closed polygon B?"""
    def orient(p, q, r):
        return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
    P0, P1 = A[:, None], np.roll(A, -1, axis=0)[:, None]
    Q0, Q1 = B[None], np.roll(B, -1, axis=0)[None]
    return bool(np.any((orient(P0, P1, Q0) * orient(P0, P1, Q1) < 0) & (orient(Q0, Q1, P0) * orient(Q0, Q1, P1) < 0)))


def poly_gap(A, B):
    """The least distance between two closed polygons in plan; 0 if they overlap or touch. With no crossing and
    neither inside the other, it is attained at a corner of one of them, so corner-to-edge distances find it."""
    if in_poly(A, B).any() or in_poly(B, A).any() or edges_cross(A, B):
        return 0.0
    return float(min(seg_dist(A, B).min(), seg_dist(B, A).min()))


def miter(P, closed):
    """Each point's left-hand normal in plan (for a counter-clockwise loop: inward), mitred at corners."""
    n = len(P)
    if closed:
        d = np.roll(P, -1, axis=0) - P
    else:
        d = np.diff(P, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1)[:, None], 1e-30)
    nl = np.stack([-d[:, 1], d[:, 0]], 1)
    out = np.empty((n, 2))
    for i in range(n):
        if closed:
            a, b = nl[i - 1], nl[i]
        else:
            a, b = nl[max(i - 1, 0)], nl[min(i, n - 2)]
        m = a + b
        m /= max(np.linalg.norm(m), 1e-30)
        out[i] = m / max(float(m @ b), 0.35)
    return out


def tris_of(F):
    T = []
    for f in F:
        for k in range(1, len(f) - 1):
            T.append((f[0], f[k], f[k + 1]))
    return np.array(T, int)


def signed_volume(V, F):
    T = tris_of(F)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    return float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c)))) / 6.0


def mass_of(V, F, mode, rho, t=None):
    """A closed solid's mass (kg) and centre: 'solid' rho x volume; 'skin' rho x t x the area of its faces that do not
    face down (a hollow box built of t-thick boards); 'sides' the same over its near-vertical faces only; 'top' over
    its up-facing faces only."""
    T = tris_of(F)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    cr = np.cross(b - a, c - a)
    if mode == "solid":
        v6 = np.einsum("ij,ij->i", a, np.cross(b, c))
        vol = float(v6.sum()) / 6.0
        cen = ((a + b + c) / 4.0 * v6[:, None]).sum(0) / max(float(v6.sum()), 1e-30)
        return rho * vol, cen, vol
    area = 0.5 * np.linalg.norm(cr, axis=1)
    nz = cr[:, 2] / np.maximum(2 * area, 1e-30)
    keep = {"skin": nz > -0.9, "sides": np.abs(nz) < 0.5, "top": nz > 0.5}[mode]
    A = float(area[keep].sum())
    cen = (((a + b + c) / 3.0)[keep] * area[keep][:, None]).sum(0) / max(A, 1e-30)
    return rho * t * A, cen, A


def loft_rings(rings, closed=False, cap0=None, cap1=None):
    """A closed solid through rings (each (n, 3), the same n): quads between consecutive rings, and each end capped by
    a fan to its centre, or with concentric rings when cap0 / cap1 = (m, lift(x, y) -> z) for a curved cap. A closed
    loop of rings (a torus) needs no caps."""
    rings = [np.asarray(r, float) for r in rings]
    n = len(rings[0])
    V = np.concatenate(rings)
    F = []
    nr = len(rings)
    for i in range(nr if closed else nr - 1):
        j = (i + 1) % nr
        for k in range(n):
            k1 = (k + 1) % n
            F.append((i * n + k, i * n + k1, j * n + k1, j * n + k))
    if not closed:
        extra = []
        for which, spec in ((0, cap0), (nr - 1, cap1)):
            ring = rings[which]
            base = which * n
            m, lift = spec if spec else (1, None)
            c2 = ring[:, :2].mean(0)
            prev = list(range(base, base + n))
            off = len(V) + sum(len(e) for e in extra)
            for j in range(1, m):
                s = 1.0 - j / m
                xy = c2 + s * (ring[:, :2] - c2)
                z = lift(xy[:, 0], xy[:, 1]) if lift else ring[:, 2].mean() + s * (ring[:, 2] - ring[:, 2].mean())
                pts = np.column_stack([xy, np.broadcast_to(z, (n,))])
                extra.append(pts)
                cur = list(range(off, off + n))
                off += n
                for k in range(n):
                    k1 = (k + 1) % n
                    F.append((prev[k], prev[k1], cur[k1], cur[k]) if which else (prev[k1], prev[k], cur[k], cur[k1]))
                prev = cur
            zc = float(lift(np.array([c2[0]]), np.array([c2[1]]))[0]) if lift else float(ring[:, 2].mean())
            extra.append(np.array([[c2[0], c2[1], zc]]))
            ci = off
            for k in range(n):
                k1 = (k + 1) % n
                F.append((prev[k], prev[k1], ci) if which else (prev[k1], prev[k], ci))
        V = np.concatenate([V] + extra)
    return V, F


def revolve(profile, origin, axis, ref, n=24, ring=False):
    """A closed solid of revolution: profile [(r, h)] from one end to the other (an end at r = 0 becomes a pole; an end
    off the axis is capped flat), turned about `axis` through `origin`, `ref` a direction square to the axis. With
    ring=True the profile is a closed loop off the axis and the solid a ring (a bezel)."""
    W = np.asarray(axis, float)
    W /= np.linalg.norm(W)
    U = np.asarray(ref, float) - (np.asarray(ref, float) @ W) * W
    U /= np.linalg.norm(U)
    Vv = np.cross(W, U)
    o = np.asarray(origin, float)
    if ring:
        ang = 2 * math.pi * np.arange(n) / n
        dirs = np.cos(ang)[:, None] * U + np.sin(ang)[:, None] * Vv
        rings = [np.array([o + h * W + r * dv for r, h in profile]) for dv in dirs]
        return loft_rings(rings, closed=True)
    prof = [(float(r), float(h)) for r, h in profile]
    if prof[0][0] > 1e-9:
        prof.insert(0, (0.0, prof[0][1]))
    if prof[-1][0] > 1e-9:
        prof.append((0.0, prof[-1][1]))
    ang = 2 * math.pi * np.arange(n) / n
    ring_dirs = np.cos(ang)[:, None] * U + np.sin(ang)[:, None] * Vv
    V, F, idx = [], [], []
    for r, h in prof:
        if r <= 1e-9:
            idx.append([len(V)])
            V.append(o + h * W)
        else:
            idx.append(list(range(len(V), len(V) + n)))
            V.extend(o + h * W + r * ring_dirs)
    for a, b in zip(idx[:-1], idx[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for k in range(n):
            k1 = (k + 1) % n
            if len(a) == 1:
                F.append((a[0], b[k1], b[k]))
            elif len(b) == 1:
                F.append((a[k], a[k1], b[0]))
            else:
                F.append((a[k], a[k1], b[k1], b[k]))
    return np.array(V), F


def slab(poly_uv, origin, U, Vd, N, t0, t1):
    """A plate: the polygon poly_uv (in the plane through origin spanned by U and Vd) from t0 to t1 along N."""
    o = np.asarray(origin, float)
    P = o + poly_uv[:, :1] * np.asarray(U) + poly_uv[:, 1:2] * np.asarray(Vd)
    return loft_rings([P + t0 * np.asarray(N), P + t1 * np.asarray(N)])


def ring_slab(outer_uv, inner_uv, origin, U, Vd, N, t0, t1):
    """A flat ring (a window's rim): between two polygons with the same number of points, from t0 to t1 along N."""
    o = np.asarray(origin, float)
    lift = lambda P2, t: o + P2[:, :1] * np.asarray(U) + P2[:, 1:2] * np.asarray(Vd) + t * np.asarray(N)  # noqa
    rings = [lift(outer_uv, t0), lift(outer_uv, t1), lift(inner_uv, t1), lift(inner_uv, t0)]
    return loft_rings(rings, closed=True)


def box(c, half):
    """An axis-aligned box: centre c, half sizes."""
    c, h = np.asarray(c, float), np.asarray(half, float)
    P = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], float) * h[:2]
    return loft_rings([np.column_stack([P + c[:2], np.full(4, c[2] - h[2])]),
                       np.column_stack([P + c[:2], np.full(4, c[2] + h[2])])])


def tube(path, radius, n=10):
    """A round rod along a polyline, capped at both ends. Its section is carried along the path without twisting and
    stretched across each bend (a mitre), so the rod keeps its radius through the bend."""
    P = np.asarray(path, float)
    d = np.diff(P, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    a = 2 * math.pi * np.arange(n) / n
    ref = np.array([0.0, 0.0, 1.0]) if abs(d[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d[0], ref)
    u /= np.linalg.norm(u)
    rings = []
    for i in range(len(P)):
        if 0 < i < len(P) - 1:
            t = d[i - 1] + d[i]
            t /= np.linalg.norm(t)
        else:
            t = d[min(i, len(d) - 1)]
        u = u - (u @ t) * t
        u /= np.linalg.norm(u)
        v = np.cross(t, u)
        q = radius * (np.cos(a)[:, None] * u + np.sin(a)[:, None] * v)
        if 0 < i < len(P) - 1:
            bn = d[i] - d[i - 1]
            bn -= (bn @ t) * t
            if np.linalg.norm(bn) > 1e-9:
                bn /= np.linalg.norm(bn)
                stretch = 1.0 / max(float(t @ d[i]), 0.4) - 1.0
                q = q + stretch * (q @ bn)[:, None] * bn
        rings.append(P[i] + q)
    return loft_rings(rings)


# ------------------------------------------------------------------------------------------------ the parts
class Part:
    """One object's closed components: vertices, faces, each face's material slot, each vertex's UVs (the three maps),
    each component's weight, and the object's frame (origin, X, Z) when it moves (the wheel)."""

    def __init__(self, name, frame=None):
        self.name, self.frame = name, frame
        self.V, self.F, self.slot = [], [], []
        self.uv = {"Planking": [], "Margin": [], "Aft": []}
        self.masses = []

    def weight(self, label, kg, centre):
        """A weight with no geometry of its own (a fitting inside a solid, such as the steering gear in its box)."""
        self.masses.append({"part": label, "kg": round(float(kg), 1), "centre": [round(float(c), 3) for c in centre],
                            "how": "fixed"})

    def add(self, V, F, slot, mass=None, label=None, orient=True, uv=None):
        V = np.asarray(V, float)
        F = [tuple(int(i) for i in f) for f in F]
        if orient and signed_volume(V, F) < 0:
            F = [f[::-1] for f in F]
        off = len(self.V)
        self.V.extend(V.tolist())
        self.F.extend([tuple(i + off for i in f) for f in F])
        self.slot.extend(slot if isinstance(slot, list) else [slot] * len(F))
        uv = uv or {}
        self.uv["Planking"].extend(np.asarray(uv.get("Planking", V[:, :2])).tolist())
        self.uv["Margin"].extend(np.asarray(uv.get("Margin", np.full((len(V), 2), FAR))).tolist())
        self.uv["Aft"].extend(np.asarray(uv.get("Aft", np.column_stack([np.full(len(V), FAR), np.zeros(len(V))])))
                              .tolist())
        if mass:
            mode, rho = mass[0], mass[1]
            t = mass[2] if len(mass) > 2 else None
            kg, cen, _ = mass_of(V, F, mode, rho, t)
            self.masses.append({"part": label or self.name, "kg": round(float(kg), 1),
                                "centre": [round(float(c), 3) for c in cen], "how": mode})


def deck_height_ring(P2, dz=0.0):
    return np.column_stack([P2, shell.deck_z(P2[:, 0], P2[:, 1]) + dz])


def on_deck_prism(shape, z_top, slot, mass, label, part, bevel=0.0, cap=None, inset_top=0.0):
    """A solid standing on the deck: shape(o) its plan at an outward offset o, its foot let into the deck, its top at
    z_top (a number, or a function of x for a top that follows the deck's sheer) with the top edge rounded off by
    `bevel`, and its top capped flat or by cap = (m, lift)."""
    zt = z_top if callable(z_top) else (lambda xx: np.full(len(xx), float(z_top)))
    ring = lambda o, dz: (lambda P: np.column_stack([P, zt(P[:, 0]) + dz]))(shape(o))  # noqa: E731
    rings = [deck_height_ring(shape(0.0), -LET)]
    if bevel > 0:
        rings.append(ring(-inset_top, -bevel))
        rings.append(ring(-inset_top - bevel * (1 - math.sqrt(0.5)), -bevel * (1 - math.sqrt(0.5))))
        rings.append(ring(-inset_top - bevel, 0.0))
    else:
        rings.append(ring(-inset_top, 0.0))
    if cap is None and callable(z_top):
        cap = (2, lambda xx, yy: zt(xx))
    V, F = loft_rings(rings, cap1=cap)
    part.add(V, F, slot, mass, label)
    return V


def lid(shape, z_bot, thick, crown, slot, mass, label, part, bevel=0.01):
    """A lid or roof slab: underneath at z_bot (a number, or a function of x for a lid that follows the deck's sheer),
    its top `thick` above with a rounded edge, crowned `crown` at its middle (athwartships). A teak lid is planked on
    its own, fore and aft: its UVs put it on one plank's middle in the deck's pattern (plain edges, no butts) and its
    top across the planks, so the deck's material draws its seams."""
    zb = z_bot if callable(z_bot) else (lambda xx: np.full(np.shape(xx), float(z_bot)))
    P0 = shape(0.0)
    half_w = 0.5 * (P0[:, 1].max() - P0[:, 1].min())
    yc = 0.5 * (P0[:, 1].max() + P0[:, 1].min())
    top = lambda x, y: zb(x) + thick + crown * (1 - ((y - yc) / half_w) ** 2)  # noqa: E731
    Pb = shape(-bevel)
    r_mid = shape(-bevel * (1 - math.sqrt(0.5)))
    rings = [np.column_stack([P0, zb(P0[:, 0])]),
             np.column_stack([P0, top(P0[:, 0], P0[:, 1]) - bevel]),
             np.column_stack([r_mid, top(r_mid[:, 0], r_mid[:, 1]) - bevel * (1 - math.sqrt(0.5))]),
             np.column_stack([Pb, top(Pb[:, 0], Pb[:, 1])])]
    V, F = loft_rings(rings, cap1=(4, top))
    uv = None
    if slot == "Teak":
        n = len(P0)
        Yp = np.full(len(V), PLAIN_Y)
        Yp[2 * n:] += V[2 * n:, 1] - yc                     # the bevel's middle, the top and its cap: across the planks
        uv = {"Planking": np.column_stack([np.full(len(V), PLAIN_U), Yp])}
    part.add(V, F, slot, mass, label, uv=uv)
    return top


def centre_z(x):
    return float(shell.deck_z(x, 0.0))


def hatch(name, h, part, footprints):
    x, L, W = h["x"], h["length"], h["width"]
    zc = lambda xx: shell.deck_z(np.asarray(xx, float), 0.0) + h["coaming"]  # noqa: E731  (follows the sheer)
    shape = rshape(x, 0.0, L, W, h["corner"])
    on_deck_prism(shape, zc, "Wood", ("sides", TB["teak"], TB["coaming"]), f"{name} coaming", part, bevel=0.008)
    ov = h["overhang"]
    if h.get("split"):
        gap = 0.003
        for x0, x1 in ((x - L / 2 - ov, x - gap), (x + gap, x + L / 2 + ov)):
            sh = rshape(0.5 * (x0 + x1), 0.0, x1 - x0, W + 2 * ov, 0.012)
            lid(sh, lambda xx: zc(xx) - 0.002, h["lid"], h["crown"], "Teak", ("solid", TB["teak"]), f"{name} lid", part)
    else:
        sh = rshape(x, 0.0, L + 2 * ov, W + 2 * ov, h["corner"] + ov)
        lid(sh, lambda xx: zc(xx) - 0.002, h["lid"], h["crown"], "Teak", ("solid", TB["teak"]), f"{name} lid", part)
    footprints[name] = shape(0.0)


def skylight(name, s, part, footprints):
    """Coaming box, ridge bar, two glazed lids sloping off the ridge, panes and guard bars."""
    x, L, W = s["x"], s["length"], s["width"]
    zc = centre_z(x) + s["coaming"]
    shape = rshape(x, 0.0, L, W, s["corner"])
    on_deck_prism(shape, zc, "Wood", ("sides", TB["teak"], TB["coaming"]), f"{name} coaming", part, bevel=0.006)
    footprints[name] = shape(0.0)
    ov, t, rise = 0.02, s["lid"], s["rise"]
    ridge_hw = 0.03
    x0, x1 = x - L / 2 - ov, x + L / 2 + ov
    # each lid's top plane falls from the ridge (rise over the box's top, plus the lid) to the box's side, where its
    # underside rests on the box's top; it stands 'ov' out past the box all round
    slope = rise / (W / 2 - ridge_hw)
    ztop = lambda yy: zc + t + slope * (W / 2 - np.abs(yy))  # noqa: E731
    y_out = W / 2 + ov
    # the ridge bar along the centreline, from the box's top to 15 mm over the lids
    z0, z1 = zc - 0.003, zc + t + rise + 0.015
    V, F = box((x, 0.0, 0.5 * (z0 + z1)), (L / 2 + ov + 0.01, ridge_hw, 0.5 * (z1 - z0)))
    part.add(V, F, "Wood", ("solid", TB["teak"]), f"{name} ridge")
    # the box's end boards carried up as gables under the lids, closing the ends between the box's top and the lids'
    # undersides (2 mm into the lids, 3 mm into the box), out to where the box's corners start to round
    zg = lambda yy: ztop(yy) - t + 0.002  # noqa: E731
    yg = W / 2 - s["corner"] - 0.005
    gable = np.array([[-yg, zc - 0.003], [yg, zc - 0.003], [yg, zg(yg)], [ridge_hw, zg(ridge_hw)],
                      [-ridge_hw, zg(ridge_hw)], [-yg, zg(yg)]])
    for e in (1.0, -1.0):
        V, F = slab(gable, (x + e * L / 2, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (e, 0.0, 0.0),
                    -TB["coaming"], 0.0)
        part.add(V, F, "Wood", ("solid", TB["teak"]), f"{name} gable ends")
    for side in (1.0, -1.0):
        ys = np.array([ridge_hw, y_out]) * side
        quad = np.array([[x0, ys[0]], [x1, ys[0]], [x1, ys[1]], [x0, ys[1]]])
        top = np.column_stack([quad, ztop(quad[:, 1])])
        bot = top - np.array([0.0, 0.0, t])
        V, F = loft_rings([bot, top])
        part.add(V, F, "Wood", ("solid", 0.5 * TB["teak"]), f"{name} lid")
        # the lid's own frame on its top: U fore and aft, Vd down the slope, N out of the lid
        o = np.array([x0, ys[0], ztop(ys[0])])
        U = np.array([1.0, 0.0, 0.0])
        Vd = np.array([0.0, side * (y_out - ridge_hw), -slope * (y_out - ridge_hw)])
        lv = np.linalg.norm(Vd)
        Vd /= lv
        N = np.cross(U, Vd) * -side
        if N[2] < 0:
            N = -N
        npn = s["panes"]
        m, mul = 0.05, 0.035
        pw = (x1 - x0 - 2 * m - (npn - 1) * mul) / npn
        for k in range(npn):
            u0 = m + k * (pw + mul)
            pane = rrect(u0 + pw / 2, lv / 2, pw, lv - 2 * m, 0.008, 2)
            V, F = slab(pane, o, U, Vd, N, -0.002, 0.002)
            part.add(V, F, "CabinWindow", ("solid", TB["glass"] * 0.006 / 0.004), f"{name} glass")
        nb, r = s["bars"], s["bar_radius"]
        for k in range(nb):
            u = m + (x1 - x0 - 2 * m) * (k + 0.5) / nb
            p0, p1 = o + u * U + 0.03 * Vd, o + u * U + (lv - 0.03) * Vd
            path = [p0 - 0.01 * N, p0 + 0.016 * N, p1 + 0.016 * N, p1 - 0.01 * N]
            V, F = tube(path, r, 8)
            part.add(V, F, "Bronze", ("solid", TB["bronze"]), f"{name} bars")


def companionway(c, part, footprints):
    x, L, W, H = c["x"], c["length"], c["width"], c["height"]
    zc = centre_z(x) + H
    shape = rshape(x, 0.0, L, W, c["corner"])
    on_deck_prism(shape, zc, "Wood", ("sides", TB["teak"], TB["coaming"]), "Companionway", part, bevel=0.008)
    footprints["Companionway"] = shape(0.0)
    # the slide over the after part of the top, on two runners; the top forward of it is boarded, the rest open
    ls, hs = c["slide_length"], c["slide_height"]
    xa = x - L / 2
    part.weight("Companionway top (forward of the slide)", TB["teak"] * TB["coaming"] * (L - ls) * W,
                (x + ls / 2, 0.0, zc - TB["coaming"] / 2))
    for y in (-W / 2 + 0.05, W / 2 - 0.05):
        V, F = box((xa + ls / 2 + 0.02, y, zc + 0.008), (ls / 2 + 0.02, 0.012, 0.012))
        part.add(V, F, "Bronze", ("solid", TB["bronze"]), "Companionway runners")
    sh = rshape(xa + ls / 2 - 0.01, 0.0, ls + 0.02, W + 0.03, 0.02)
    lid(sh, zc + 0.014, hs, 0.015, "Teak", ("skin", TB["teak"], 0.025), "Companionway slide", part)
    # the doors in the after face, a pair meeting with 4 mm between them, inside the face's flat
    dw = (W - 2 * c["corner"] - 0.01) / 2
    for side in (-1, 1):
        panel = rrect(side * (dw / 2 + 0.002), H * 0.45, dw, H * 0.62, 0.01, 2)
        V, F = slab(panel, (xa, 0.0, centre_z(xa)), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]),
                    np.array([-1.0, 0.0, 0.0]), -0.004, 0.012)
        part.add(V, F, "Wood", ("solid", TB["teak"]), "Companionway doors")


def doghouse(d, part, footprints):
    x, L, W, H = d["x"], d["length"], d["width"], d["side_height"]
    tan_t = math.tan(math.radians(d["tumblehome_deg"]))
    lean = H * tan_t
    zb = centre_z(x)
    zt = zb + H
    shape = rshape(x, 0.0, L, W, d["corner"], 8)
    footprints["Doghouse"] = shape(0.0)
    rings = [deck_height_ring(shape(0.0), -LET), np.column_stack([shape(-lean), np.full(len(shape(0.0)), zt)])]
    V, F = loft_rings(rings)
    part.add(V, F, "Wood", ("sides", TB["teak"], TB["house_side"]), "Doghouse sides")
    # the roof: flat underneath, cambered athwartships, its eaves standing out past the sides' top
    roof_shape = rshape(x, 0.0, L - 2 * lean, W - 2 * lean, d["corner"] - lean, 8)
    eave = d["eave"]
    top = lid(lambda o: roof_shape(o + eave), zt - 0.004, d["roof_thickness"], d["roof_crown"], "Wood",
              ("top", TB["teak"], TB["house_roof"]), "Doghouse roof", part, bevel=0.015)

    def side_frame(face, at):
        """A point on the face (its base at `at` along it) and the face's axes: U along, Vd up it, N out."""
        if face in ("port", "starboard"):
            s = 1.0 if face == "starboard" else -1.0
            xb = at
            base = np.array([xb, s * W / 2, float(shell.deck_z(xb, s * W / 2))])
            Vd = np.array([0.0, -s * lean, zt - base[2]])
            U = np.array([1.0, 0.0, 0.0])
        else:
            s = 1.0 if face == "forward" else -1.0
            xf = x + s * L / 2
            base = np.array([xf, at, float(shell.deck_z(xf, at))])
            Vd = np.array([-s * lean, 0.0, zt - base[2]])
            U = np.array([0.0, 1.0, 0.0])
        Vd /= np.linalg.norm(Vd)
        N = np.cross(U, Vd)
        if face == "forward" and N[0] < 0 or face == "aft" and N[0] > 0 or \
                face == "starboard" and N[1] < 0 or face == "port" and N[1] > 0:
            N = -N
        return base, U, Vd, N

    def window(face, at, height, size, label):
        w, h, r = size
        base, U, Vd, N = side_frame(face, at)
        cos_l = float(Vd[2])
        o = base + (height / cos_l) * Vd
        # the glass runs 4 mm into the rim all round, so no edge of the two solids meets (they would not close)
        V, F = slab(rrect(0.0, 0.0, w + 0.008, h + 0.008, r + 0.004, 4), o, U, Vd, N, -0.004, 0.002)
        part.add(V, F, "CabinWindow", ("solid", TB["glass"]), f"Doghouse {label} glass")
        V, F = ring_slab(rrect(0.0, 0.0, w + 0.036, h + 0.036, r + 0.018, 4), rrect(0.0, 0.0, w, h, r, 4), o, U, Vd,
                         N, -0.004, 0.007)
        part.add(V, F, "Bronze", ("solid", TB["bronze"]), f"Doghouse {label} rims")

    straight = L - 2 * d["corner"]
    npt = d["ports_a_side"]
    for face in ("starboard", "port"):
        for k in range(npt):
            xp = x - straight / 2 + straight * (k + 0.5) / npt
            window(face, xp, 0.36, d["port"], "portlight")
    sw = W - 2 * d["corner"]
    for k in range(d["windows_forward"]):
        yp = -sw / 2 + sw * (k + 0.5) / d["windows_forward"]
        window("forward", yp, 0.38, d["window"], "window")
    # the doors in the after face
    dw, dh = d["doors"]
    for s in (-1, 1):
        base, U, Vd, N = side_frame("aft", s * (dw / 2 + 0.006))
        o = base + (0.06 + dh / 2) / float(Vd[2]) * Vd
        V, F = slab(rrect(0.0, 0.0, dw, dh, 0.012, 2), o, U, Vd, N, -0.004, 0.012)
        part.add(V, F, "Wood", ("solid", TB["teak"]), "Doghouse doors")
    # the sliding hatch on the roof's after end
    sl, sw_, sh = d["slide"]
    xa = x - L / 2 + lean + 0.02
    z_edge = float(top(np.array([xa]), np.array([sw_ / 2]))[0])
    lid(rshape(xa + sl / 2, 0.0, sl, sw_, 0.02), z_edge - 0.004, sh, 0.012, "Wood",
        ("skin", TB["teak"], 0.025), "Doghouse slide", part, bevel=0.008)
    # the handrails along the roof
    hr = d["handrail"]
    bw, bh = hr["section"]
    xr0, xr1 = x - L / 2 + lean + sl + 0.15, x + L / 2 - lean - 0.3
    for s in (-1, 1):
        y = s * (W / 2 - lean - hr["inboard_of_edge"])
        zr = float(top(np.array([x]), np.array([y]))[0])
        V, F = box(((xr0 + xr1) / 2, y, zr + hr["height"] + bh / 2), ((xr1 - xr0) / 2, bw / 2, bh / 2))
        part.add(V, F, "Wood", ("solid", TB["teak"]), "Doghouse handrails")
        for k in range(hr["feet"]):
            xf = xr0 + 0.05 + (xr1 - xr0 - 0.1) * k / (hr["feet"] - 1)
            zf = float(top(np.array([xf]), np.array([y]))[0])
            V, F = box((xf, y, (zf - 0.004 + zr + hr["height"] + 0.004) / 2),
                       (0.03, bw / 2 - 0.002, (zr + hr["height"] + 0.008 - zf) / 2))
            part.add(V, F, "Wood", ("solid", TB["teak"]), "Doghouse handrails")


def cockpit_outline(c):
    L = c["x_forward"] - c["x_aft"]
    return densify(rrect(0.5 * (c["x_forward"] + c["x_aft"]), 0.0, L, c["width"], c["corner"], 6), 0.15)


def cockpit_coaming(c, part, footprints):
    H = cockpit_outline(c)
    out = -miter(H, True)                      # the outline is counter-clockwise: its left normal points in
    hc, wc = c["coaming"], c["coaming_width"]
    prof = [(-0.002, 0.0), (-0.002, hc - 0.01), (0.006, hc), (wc - 0.01, hc), (wc - 0.002, hc - 0.01), (wc - 0.002, 0.0)]
    zref = shell.deck_z(H[:, 0], H[:, 1])
    rings = []
    for s, h in prof:
        P = H + s * out
        z = shell.deck_z(P[:, 0], P[:, 1]) - LET if h == 0.0 else zref + h
        rings.append(np.column_stack([P, z]))
    V, F = loft_rings(rings[::-1], closed=True)
    part.add(V, F, "Wood", ("solid", TB["teak"]), "Cockpit coaming")
    footprints["Cockpit"] = H + (wc - 0.002) * out


def toe_rail(loop, ns, i_corner_p, part):
    """The rail along the deck's edge: from just short of the stem down the starboard side, round the transom's top
    and up the port side. `loop` is the deck's edge: the starboard sheer from the transom's corner to the stem
    (indices 0 to ns - 1), the port sheer back to the port corner (to i_corner_p), then the transom's top row from
    port to starboard."""
    tr = DK["toe_rail"]
    hd_end = tr["ends_at_half_breadth"]
    stb = [i for i in range(ns - 1, -1, -1) if abs(loop[i, 1]) >= hd_end]          # stem end aft to the corner
    row = list(range(len(loop) - 1, i_corner_p, -1))                               # across the transom, to port
    port = [i for i in range(i_corner_p, ns - 1, -1) if abs(loop[i, 1]) >= hd_end]  # the port corner forward
    P = loop[stb + row + port]
    # the path runs counter-clockwise seen from above (aft down the starboard side, across, forward up the port
    # side), so its left-hand normal points inboard
    m = miter(P[:, :2], False)
    wb, wt, ht, ins = tr["base_width"], tr["top_width"], tr["height"], tr["inset"]
    prof = [(0.0, 0.0), (0.0, ht - 0.010), (0.003, ht - 0.003), (0.010, ht), (wt - 0.010, ht),
            (wt - 0.003, ht - 0.003), (wt, ht - 0.010), (wb, 0.0)]
    s_along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    rings = []
    for w, h in prof:
        Q = P[:, :2] + (ins + w) * m
        z = shell.deck_z(Q[:, 0], Q[:, 1]) - LET if h == 0.0 else P[:, 2] + h
        rings.append(np.column_stack([Q, z]))
    R = np.stack(rings, 1)                                # (path, profile, 3): one ring per point along the path
    V, F = loft_rings([R[i] for i in range(len(P))])
    part.add(V, F, "Wood", ("solid", TB["teak"]), "Toe rail")
    return float(s_along[-1])


def steering(st, part, wheel_part, footprints):
    """The wheel box over the rudder's head (the steering gear inside it as a weight), the binnacle on its lid, and the
    wheel on its shaft (its own part, in its own frame)."""
    b = st["box"]
    xb = 0.5 * (b["x_forward"] + b["x_aft"])
    Lb = b["x_forward"] - b["x_aft"]
    zt = centre_z(xb) + b["height"]
    shape = rshape(xb, 0.0, Lb, b["width"], b["corner"])
    on_deck_prism(shape, zt - b["lid"], "Wood", ("sides", TB["teak"], TB["cockpit"]), "Wheel box", part)
    lid_top = lid(rshape(xb, 0.0, Lb + 2 * b["lid_overhang"], b["width"] + 2 * b["lid_overhang"],
                         b["corner"] + b["lid_overhang"]),
                  zt - b["lid"] - 0.002, b["lid"], 0.004, "Wood", ("solid", TB["teak"]), "Wheel box lid", part)
    part.weight("Steering gear (inside the box)", TB["steering_gear_kg"], (xb, 0.0, centre_z(xb) + 0.15))
    footprints["WheelBox"] = shape(0.0)
    # the wheel: hub on the shaft, spokes, rim; its own frame, X forward along the shaft (from the helmsman toward the
    # box), Z up, so a positive turn about X is clockwise as the helmsman sees it: the top goes to starboard and, as on
    # any wheel, the bow follows, the game's positive helm. Spoke 0, the king spoke, stands upright amidships.
    w = st["wheel"]
    xw = w["x"]
    zh = centre_z(xw) + w["hub_height"]
    o = np.array([xw, 0.0, zh])
    ax = np.array([-1.0, 0.0, 0.0])
    up = np.array([0.0, 0.0, 1.0])
    wheel_part.frame = (o, -ax, up)
    hr, hl = w["hub"]
    V, F = revolve([(0.0, -hl / 2), (hr * 0.7, -hl / 2), (hr, -hl / 2 + 0.02), (hr, hl / 2 - 0.02), (hr * 0.75, hl / 2),
                    (0.0, hl / 2 + 0.01)], o, ax, up, 24)
    wheel_part.add(V, F, "Bronze", ("solid", TB["bronze"]), "Wheel hub")
    R = w["radius"]
    rr, ra = w["rim"]
    th = 2 * math.pi * np.arange(72) / 72
    e1, e2 = up, np.cross(ax, up)
    rings = []
    for t in th:
        radial = math.cos(t) * e1 + math.sin(t) * e2
        a = 2 * math.pi * np.arange(12) / 12
        rings.append(o + (R + 0.5 * rr * np.cos(a))[:, None] * radial + (0.5 * ra * np.sin(a))[:, None] * ax)
    V, F = loft_rings(rings, closed=True)
    wheel_part.add(V, F, "Wood", ("solid", TB["teak"]), "Wheel rim")
    r0, r1 = w["spoke_radius"]
    for k in range(w["spokes"]):
        t = 2 * math.pi * k / w["spokes"]
        radial = math.cos(t) * e1 + math.sin(t) * e2
        prof = [(0.0, hr * 0.8), (r0, hr * 0.8), (r0 * 1.25, hr + 0.03), (r0, hr + 0.06), (r0 * 0.95, 0.3 * R),
                (r0 * 1.15, 0.36 * R), (r0 * 0.95, 0.42 * R), (r1, R - 0.6 * rr), (r1 * 0.9, R - 0.05 * rr),
                (0.0, R - 0.05 * rr)]
        V, F = revolve(prof, o, radial, ax, 12)
        wheel_part.add(V, F, "Wood", ("solid", TB["teak"]), "Wheel spokes")
    # the shaft from the box to the hub
    V, F = revolve([(w["shaft_radius"], 0.0), (w["shaft_radius"], b["x_aft"] - xw + 0.03)],
                   np.array([b["x_aft"] + 0.03, 0.0, zh]), ax, up, 16)
    wheel_part.add(V, F, "Bronze", ("solid", TB["bronze"]), "Wheel shaft")
    # the binnacle, standing on the box's lid at its after end: a cast bronze pedestal and bowl (weighed as its walls,
    # the bowl's glass on its own), the bezel, the compass inside, and the soft iron corrector spheres on brackets
    bn = st["binnacle"]
    xn = bn["x"]
    zl = float(lid_top(np.array([xn]), np.array([0.0]))[0])
    h, rb, r_base = bn["height"], bn["bowl_radius"], bn["base_radius"]
    prof = [(0.0, -0.006), (r_base, -0.006), (r_base, 0.012), (0.72 * r_base, 0.03), (0.09, 0.07), (0.085, h - 0.17),
            (0.105, h - 0.12), (0.15, h - 0.08), (rb, h - 0.04), (rb, h + 0.01), (rb - 0.025, h + 0.02), (0.0, h + 0.02)]
    base = np.array([xn, 0.0, zl])
    xax = np.array([1.0, 0.0, 0.0])
    V, F = revolve(prof, base, up, xax, 32)
    if signed_volume(V, F) < 0:
        F = [f[::-1] for f in F]
    part.add(V, F, "Bronze", None, "Binnacle")
    Vb = np.asarray(V)
    walls = [f for f in F if Vb[list(f), 2].min() < zl + h + 0.02 - 1e-6]          # the bowl's top is its glass
    kg, cen, _ = mass_of(Vb, walls, "skin", TB["bronze"], TB["binnacle_wall"])
    part.masses.append({"part": "Binnacle", "kg": round(float(kg), 1), "centre": [round(float(a), 3) for a in cen],
                        "how": "skin"})
    V, F = revolve([(0.0, h + 0.016), (rb - 0.02, h + 0.016), (rb - 0.02, h + 0.027), (0.0, h + 0.03)], base, up, xax, 32)
    part.add(V, F, "CabinWindow", ("solid", TB["glass"]), "Binnacle glass")
    V, F = revolve([(rb - 0.03, h + 0.012), (rb + 0.008, h + 0.012), (rb + 0.008, h + 0.03), (rb - 0.012, h + 0.04),
                    (rb - 0.03, h + 0.034)], base, up, xax, 32, ring=True)
    part.add(V, F, "Bronze", ("solid", TB["bronze"]), "Binnacle bezel")
    part.weight("Compass (inside the bowl)", TB["compass_kg"], (xn, 0.0, zl + h - 0.05))
    rs, ys = bn["corrector_spheres"]
    for sd in (-1, 1):
        c = np.array([xn, sd * ys, zl + h - 0.04])
        V, F = revolve([(0.0, -rs)] + [(rs * math.sin(a), -rs * math.cos(a)) for a in np.linspace(0.2, math.pi - 0.2, 9)]
                       + [(0.0, rs)], c, up, xax, 20)
        part.add(V, F, "Iron", ("solid", 7200.0), "Binnacle corrector spheres (soft iron)")
        V, F = revolve([(0.012, 0.0), (0.012, ys - rs * 0.6 - rb + 0.01)], np.array([xn, sd * (rb - 0.01), zl + h - 0.06]),
                       np.array([0.0, sd, 0.0]), up, 10)
        part.add(V, F, "Bronze", ("solid", TB["bronze"]), "Binnacle brackets")


# ------------------------------------------------------------------------------------------------ the planking
def planking_terms(m, U, Ys, D, YM, DA, SL, mitre, aa=0.0012):
    """The laid deck's pattern from its three UV maps, written once for both its users: `m(op, a, b, c, clamp)` is
    either build_jclass's maker of Blender Math nodes (the material) or np_math (the drawing), with Blender's
    operation names. 'mitre' is (a, b) from deck_surface: a D - b DA is the distance (m) from the after margin's mitre
    with the covering board. Returns which piece a point is on (covering board, after margin, king plank, plank: 1 or
    0), the piece's id for its tint (idx, idy), and 'seam': 1 on a seam's centre line, 0 more than half a seam's width
    off it, with a soft edge 'aa' wide.

    The covering board's nibbed inner edge E: its edge y_m cuts the planks at a shallow angle, so each plank runs out
    along it until it is 'nib' of its width wide (f, the fraction of plank j left past the edge, at least nib), then is
    cut square across (the board notched to take it); in |y|, the board starts at E = k + w (j + f [f >= nib]). The
    nib's square end lies |f - nib| w / s along the plank from this point (s = |dy_m/dx|). The butts repeat over
    len(butt_stagger) planks, starboard's 'starboard_shift' of a length along from port's; the scarfs run 'scarf_run'
    along the piece across its width (their seams' widths measured square to them)."""
    sw = PL["seam"]

    def near(v, step):
        return m("ABSOLUTE", m("SUBTRACT", v, m("MULTIPLY", m("ROUND", m("DIVIDE", v, step)), step)))

    def line(d):
        return m("ADD", m("DIVIDE", m("SUBTRACT", sw / 2, d), aa), 0.5, clamp=True)

    Y = m("ABSOLUTE", Ys)
    stb = m("GREATER_THAN", Ys, 0.0)
    k, w, nib = PL["king_plank"] / 2, PL["pitch"], PL["nib"]
    cb, cba, L = PL["covering_board"], PL["after_margin"], PL["plank_length"]
    ks, cs, run, shift = PL["king_scarf"], PL["covering_scarf"], PL["scarf_run"], PL["starboard_shift"]
    t = m("DIVIDE", m("SUBTRACT", YM, k), w)
    j = m("FLOOR", t)
    f = m("SUBTRACT", t, j)
    E = m("MAXIMUM", m("ADD", k, m("MULTIPLY", w, m("ADD", j, m("MULTIPLY", f, m("GREATER_THAN", f, nib - 1e-6))))), k)
    side = m("GREATER_THAN", Y, E)
    aft = m("LESS_THAN", DA, cba)
    margin = m("MAXIMUM", side, aft)
    not_m = m("SUBTRACT", 1.0, margin)
    king = m("MULTIPLY", m("LESS_THAN", Y, k), not_m)
    plank = m("MULTIPLY", not_m, m("SUBTRACT", 1.0, king))
    not_aft = m("SUBTRACT", 1.0, aft)
    # in the quarters' corners, which side of the mitre: the covering board's (nearer the sheer) or the after margin's
    a_m, b_m = mitre
    mit = m("SUBTRACT", m("MULTIPLY", D, a_m), m("MULTIPLY", DA, b_m))
    board = m("MULTIPLY", side, m("SUBTRACT", 1.0, m("MULTIPLY", aft, m("GREATER_THAN", mit, 0.0))))
    after = m("SUBTRACT", margin, board)
    # the plank's index and its butts' offset along it
    jp = m("FLOOR", m("DIVIDE", m("SUBTRACT", Y, k), w))
    st = PL["butt_stagger"]
    mk = m("FLOORED_MODULO", jp, float(len(st)))
    frac = m("MULTIPLY", stb, shift)
    for i, s in enumerate(st):
        if s:
            frac = m("ADD", frac, m("MULTIPLY", m("COMPARE", mk, float(i), 0.5), s))
    off = m("MULTIPLY", frac, L)
    s_long = m("MULTIPLY", line(near(m("SUBTRACT", Y, k), w)),
               m("MAXIMUM", plank, m("MULTIPLY", king, m("GREATER_THAN", Y, k - sw / 2))))
    s_butt = m("MULTIPLY", line(near(m("SUBTRACT", U, off), L)), plank)
    # the king plank's scarfs run 'scarf_run' along it across its whole width
    rk = run / (2 * k)
    q_k = m("SUBTRACT", U, m("MULTIPLY", Ys, rk))
    s_king = m("MULTIPLY", line(m("DIVIDE", near(q_k, ks), math.sqrt(1 + rk * rk))), king)
    s_edge = m("MULTIPLY", line(m("ABSOLUTE", m("SUBTRACT", Y, E))), not_aft)
    dx_nib = m("DIVIDE", m("MULTIPLY", m("ABSOLUTE", m("SUBTRACT", f, nib)), w), m("ADD", SL, 1e-4))
    in_nib = m("MULTIPLY", m("GREATER_THAN", Y, m("ADD", k, m("MULTIPLY", j, w))),
               m("LESS_THAN", Y, m("ADD", k, m("MULTIPLY", m("ADD", j, nib), w))))
    s_nib = m("MULTIPLY", m("MULTIPLY", line(dx_nib), in_nib), m("MULTIPLY", not_aft, m("GREATER_THAN", t, 0.0)))
    s_aft = m("MULTIPLY", line(m("ABSOLUTE", m("SUBTRACT", DA, cba))), m("SUBTRACT", 1.0, side))
    s_mitre = m("MULTIPLY", line(m("ABSOLUTE", mit)), m("MULTIPLY", side, aft))
    # the covering boards' scarfs: across the board's width (to its widest, where a nib's notch is cut), 'scarf_run'
    # along it; starboard's board is scarfed 'starboard_shift' of a length along from port's
    rc = run / cb
    q = m("ADD", m("SUBTRACT", U, m("MULTIPLY", D, rc)), m("MULTIPLY", stb, shift * cs))
    s_scarf = m("MULTIPLY", line(m("DIVIDE", near(q, cs), math.sqrt(1 + rc * rc))),
                m("MULTIPLY", m("MULTIPLY", side, not_aft), m("LESS_THAN", D, cb + nib * w + 0.005)))
    seam = s_long
    for v in (s_butt, s_king, s_edge, s_nib, s_aft, s_mitre, s_scarf):
        seam = m("MAXIMUM", seam, v)
    # each piece's id, for its tint: the planks by index and length, the boards by length, port and starboard apart
    seg = m("FLOOR", m("DIVIDE", m("SUBTRACT", U, off), L))
    idx = m("ADD", m("MULTIPLY", plank, jp),
            m("ADD", m("ADD", m("MULTIPLY", board, -100.0), m("MULTIPLY", after, -300.0)),
              m("ADD", m("MULTIPLY", king, -200.0), m("MULTIPLY", m("MULTIPLY", stb, m("SUBTRACT", 1.0, king)), 500.0))))
    idy = m("ADD", m("MULTIPLY", plank, seg), m("ADD", m("MULTIPLY", board, m("FLOOR", m("DIVIDE", q, cs))),
                                                 m("MULTIPLY", king, m("FLOOR", m("DIVIDE", q_k, ks)))))
    return {"seam": seam, "side": side, "aft": aft, "board": board, "after": after, "king": king, "plank": plank,
            "Y": Y, "idx": idx, "idy": idy}


def np_math(op, a, b=None, c=None, clamp=False):
    """Blender's Math node operations on numpy arrays, for planking_terms outside Blender."""
    a = np.asarray(a, float)
    b = None if b is None else np.asarray(b, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = {"ADD": lambda: a + b, "SUBTRACT": lambda: a - b, "MULTIPLY": lambda: a * b,
             "DIVIDE": lambda: np.where(b != 0, a / np.where(b != 0, b, 1.0), 0.0),
             "ABSOLUTE": lambda: np.abs(a), "ROUND": lambda: np.floor(a + 0.5), "FLOOR": lambda: np.floor(a),
             "FRACT": lambda: a - np.floor(a),
             "FLOORED_MODULO": lambda: np.where(b != 0, a - np.floor(a / np.where(b != 0, b, 1.0)) * b, 0.0),
             "MAXIMUM": lambda: np.maximum(a, b), "GREATER_THAN": lambda: (a > b).astype(float),
             "LESS_THAN": lambda: (a < b).astype(float),
             "COMPARE": lambda: (np.abs(a - b) <= max(float(c), 1e-5)).astype(float)}[op]()
    return np.clip(r, 0.0, 1.0) if clamp else r


def after_mitre(sheer, ra, xf, ym):
    """The after margin's mitre with the covering board, as planking_terms takes it: (a, b) with a D - b DA the
    distance (m) from the mitre, the line from the transom's outer corner (D = DA = 0) to the inner corner, where the
    board's nibbed inner edge meets the margin's (DA = after_margin). The distance is a D - b DA divided by its
    gradient's length at the mitre's middle (near enough constant over a mitre 0.4 m long)."""
    cba = PL["after_margin"]
    x_aft = lambda yy: np.interp(np.abs(yy), np.abs(ra[:, 1]), ra[:, 0])  # noqa: E731
    dd = lambda xx, yy: seg_dist(np.column_stack([xx, np.abs(yy)]), sheer[:, :2], closed=False)  # noqa: E731
    ys = np.linspace(0.0, abs(sheer[0, 1]), 4000)
    xs = x_aft(ys) + cba
    T = planking_terms(np_math, xs, ys, dd(xs, ys), np.interp(xs, xf, ym), np.full(len(ys), cba), np.zeros(len(ys)),
                       (0.0, 0.0))
    on = np.nonzero(T["side"] > 0.5)[0]
    if not len(on):
        raise ValueError("the after margin's inner edge never meets the covering board")
    xi, yi = xs[on[0]], ys[on[0]]
    d_c = float(dd(np.array([xi]), np.array([yi]))[0])
    xm, ym_ = (sheer[0, 0] + xi) / 2, (abs(sheer[0, 1]) + yi) / 2
    fn = lambda xx, yy: cba * dd(np.array([xx]), np.array([yy]))[0] - d_c * (xx - x_aft(yy))  # noqa: E731
    h = 1e-3
    g = math.hypot((fn(xm + h, ym_) - fn(xm - h, ym_)) / (2 * h), (fn(xm, ym_ + h) - fn(xm, ym_ - h)) / (2 * h))
    return [round(cba / g, 6), round(d_c / g, 6)]


# ------------------------------------------------------------------------------------------------ the deck surface
def deck_surface(sheer, part):
    """The deck from the shell's sheer (starboard, from the transom's corner to the stem head), with the cockpit let
    in. Returns the deck's edge loop, the corner indices and a report."""
    from mathutils import Vector, geometry          # Blender's constrained Delaunay triangulation
    sheer = np.asarray(sheer, float)
    if abs(sheer[-1, 1]) > 1e-9:
        raise ValueError("the sheer must end on the centreline at the stem head")
    row = aft_row(sheer[0])                                # port to starboard
    port = sheer[-2::-1].copy()
    port[:, 1] *= -1
    loop = np.concatenate([sheer, port, row[1:-1]])        # stb corner -> stem -> port corner -> row -> back
    i_corner_p = len(sheer) + len(port) - 1
    c = DK["cockpit"]
    hole = cockpit_outline(c)
    g = DK["deck"]["grid"]
    # points inside: a triangular lattice, clear of the edges
    xs = np.arange(loop[:, 0].min() + g / 2, loop[:, 0].max(), g)
    yw = float(np.abs(loop[:, 1]).max()) + g
    pts = []
    for j, xx in enumerate(xs):
        ys = np.arange(-yw + (g / 2 if j % 2 else 0.0), yw, g)
        pts.append(np.column_stack([np.full(len(ys), xx), ys]))
    pts = np.concatenate(pts)
    keep = in_poly(pts, loop[:, :2]) & ~in_poly(pts, hole)
    pts = pts[keep]
    clear = np.minimum(seg_dist(pts, loop[:, :2]), seg_dist(pts, hole))
    pts = pts[clear > 0.55 * g]
    P2 = np.concatenate([loop[:, :2], hole, pts])
    nl, nh = len(loop), len(hole)
    E = [(k, (k + 1) % nl) for k in range(nl)] + [(nl + k, nl + (k + 1) % nh) for k in range(nh)]
    out = geometry.delaunay_2d_cdt([Vector((float(a), float(b))) for a, b in P2], E, [], 0, 1e-9, True)
    ov, oe, of, orig_v = out[0], out[1], out[2], out[3]
    if len(ov) != len(P2):
        raise ValueError(f"the deck's triangulation added or merged points ({len(ov)} for {len(P2)})")
    to_in = [ids[0] for ids in orig_v]
    T = np.array([[to_in[i] for i in f] for f in of])
    cen = P2[T].mean(1)
    T = T[in_poly(cen, loop[:, :2]) & ~in_poly(cen, hole)]
    # every edge of the deck's outline and of the cockpit must be in the triangulation, or the shell will not close
    have = set()
    for t in T:
        for k in range(3):
            have.add(frozenset((t[k], t[(k + 1) % 3])))
    missing = [e for e in E if frozenset(e) not in have]
    if missing:
        raise ValueError(f"the deck's triangulation lost {len(missing)} edges of its outline")
    # heights: the outline keeps the shell's own points; inside, the deck's camber
    Z = np.empty(len(P2))
    Z[:nl] = loop[:, 2]
    Z[nl:] = shell.deck_z(P2[nl:, 0], P2[nl:, 1])
    V = np.column_stack([P2, Z])
    a2 = (P2[T[:, 1], 0] - P2[T[:, 0], 0]) * (P2[T[:, 2], 1] - P2[T[:, 0], 1]) - \
         (P2[T[:, 1], 1] - P2[T[:, 0], 1]) * (P2[T[:, 2], 0] - P2[T[:, 0], 0])
    T[a2 < 0] = T[a2 < 0][:, ::-1]                       # face up
    deck_F = [tuple(t) for t in T]
    # the well: walls from the hole down to a flat sole
    rim = list(range(nl, nl + nh))
    z_sole = float(V[rim, 2].min()) - c["depth"]
    sole0 = len(V)
    V = np.concatenate([V, np.column_stack([hole, np.full(nh, z_sole)]), [[*hole.mean(0), z_sole]]])
    wall_F = [(rim[k], rim[(k + 1) % nh], sole0 + (k + 1) % nh, sole0 + k) for k in range(nh)]
    sole_F = [(sole0 + nh, sole0 + k, sole0 + (k + 1) % nh) for k in range(nh)]
    # UVs
    hd_x, hd_y = sheer[:, 0], np.abs(sheer[:, 1])
    xf = np.linspace(hd_x[0], hd_x[-1], 4000)
    hdf = np.interp(xf, hd_x, hd_y)
    dh = np.gradient(hdf, xf)
    ym = hdf - PL["covering_board"] * np.sqrt(1 + dh * dh)
    slope = np.abs(np.gradient(ym, xf))
    d_side = seg_dist(np.column_stack([V[:, 0], np.abs(V[:, 1])]), sheer[:, :2], closed=False)
    ra = row[NY_AFT:]                                     # the after row from the centreline out to starboard
    x_aft = np.interp(np.abs(V[:, 1]), np.abs(ra[:, 1]), ra[:, 0])
    on_deck = np.zeros(len(V), bool)
    on_deck[:nl + nh + len(pts)] = True
    plk = np.array(V[:, :2])
    plk[sole0:] = np.column_stack([np.full(len(V) - sole0, PLAIN_U), PLAIN_Y + V[sole0:, 1]])  # the sole: its own planks
    uv = {"Planking": plk,
          "Margin": np.where(on_deck[:, None], np.column_stack([d_side, np.interp(V[:, 0], xf, ym)]), FAR),
          "Aft": np.where(on_deck[:, None], np.column_stack([V[:, 0] - x_aft, np.interp(V[:, 0], xf, slope)]),
                          np.column_stack([np.full(len(V), FAR), np.zeros(len(V))]))}
    mitre = after_mitre(sheer, ra, xf, ym)
    faces = deck_F + wall_F + sole_F
    slots = ["Teak"] * len(deck_F) + ["Wood"] * len(wall_F) + ["Teak"] * len(sole_F)
    part.add(V, faces, slots, orient=False, uv=uv)
    # the deck's own weights: the planking over its top (less what stands on it, added in deck_weights), the well
    Tt = np.array(deck_F)
    cr = np.cross(V[Tt[:, 1]] - V[Tt[:, 0]], V[Tt[:, 2]] - V[Tt[:, 0]])
    ar = 0.5 * np.linalg.norm(cr, axis=1)
    cen = V[Tt].mean(1)
    area = float(ar.sum())
    c_deck = (cen * ar[:, None]).sum(0) / area - np.array([0.0, 0.0, PL["thickness"] / 2])
    part.masses.append({"part": "Deck planking (before what stands on it)", "kg": round(TB["teak"] * PL["thickness"] *
                        area, 1), "centre": [round(float(a), 3) for a in c_deck], "how": "top", "area_m2": round(area, 2)})
    Vw = np.array(V)
    ws = [mass_of(Vw, wall_F, "skin", TB["teak"], TB["cockpit"]), mass_of(Vw, sole_F, "skin", TB["teak"], TB["cockpit"])]
    kg = sum(m[0] for m in ws)
    cw = sum(m[0] * m[1] for m in ws) / kg
    part.masses.append({"part": "Cockpit sides and sole", "kg": round(float(kg), 1),
                        "centre": [round(float(a), 3) for a in cw], "how": "skin"})
    return loop, len(sheer), i_corner_p, {"deck_area_m2": round(area, 2), "deck_triangles": len(deck_F),
                                 "cockpit_sole_z_m": round(z_sole, 3), "edge_points": nl, "inside_points": len(pts),
                                 "planking_mitre": mitre}


# ------------------------------------------------------------------------------------------------ the whole deck
def build(sheer=None):
    """Every part of the deck: {name: Part}, the footprints (plan outlines of what stands on the deck), and a report
    (the deck's weights and the layout's checks)."""
    sheer = loft_sheer() if sheer is None else np.asarray(sheer, float)
    parts = {k: Part(k) for k in ("Deck", "ToeRail", "Hatches", "Skylights", "Companionway", "Doghouse", "Cockpit",
                                  "Steering", "Wheel")}
    fp = {}
    loop, ns, ic_p, rep = deck_surface(sheer, parts["Deck"])
    rep["toe_rail_length_m"] = round(toe_rail(loop, ns, ic_p, parts["ToeRail"]), 2)
    for name, h in DK["hatches"].items():
        if name != "note":
            hatch(name, h, parts["Hatches"], fp)
    for name, s in DK["skylights"].items():
        if name != "note":
            skylight(name, s, parts["Skylights"], fp)
    companionway(DK["companionway"], parts["Companionway"], fp)
    doghouse(DK["doghouse"], parts["Doghouse"], fp)
    cockpit_coaming(DK["cockpit"], parts["Cockpit"], fp)
    steering(DK["steering"], parts["Steering"], parts["Wheel"], fp)
    rep["weights"] = deck_weights(parts, fp)
    rep["layout"] = layout_checks(fp, sheer)
    rep["footprints"] = {k: [[round(float(a), 3) for a in p] for p in v] for k, v in fp.items()}
    return parts, rep


def deck_weights(parts, fp):
    """Every part's weight and the deck's together, less the planking under what stands on it (a coaming stands on the
    beams, not on planking)."""
    rows = [m for p in parts.values() for m in p.masses]
    under = 0.0
    cu = np.zeros(3)
    for k, P in fp.items():
        a = abs(poly_area(P))
        if k == "Cockpit":                                 # the well is a hole: only the coaming's ring has planking
            a -= abs(poly_area(cockpit_outline(DK["cockpit"])))
        under += a
        cu += a * np.array([*P.mean(0), float(shell.deck_z(*P.mean(0)))])
    kg_under = TB["teak"] * PL["thickness"] * under
    rows.append({"part": "Less the planking under coamings and houses", "kg": round(-kg_under, 1),
                 "centre": [round(float(a), 3) for a in cu / max(under, 1e-9)], "how": "top", "area_m2": round(under, 2)})
    kg = sum(r["kg"] for r in rows)
    c = sum(r["kg"] * np.array(r["centre"]) for r in rows) / kg
    agg = {}
    for r in rows:
        a = agg.setdefault(r["part"], {"part": r["part"], "kg": 0.0, "m": np.zeros(3), "how": r["how"], "pieces": 0})
        a["kg"] += r["kg"]
        a["m"] += r["kg"] * np.array(r["centre"])
        a["pieces"] += 1
    rows = [{"part": a["part"], "kg": round(a["kg"], 1), "centre": [round(float(v), 3) for v in a["m"] / a["kg"]],
             "how": a["how"], "pieces": a["pieces"]} for a in agg.values()]
    return {"rows": rows, "total_kg": round(kg, 1), "total_long_tons": round(kg / LT_KG, 3),
            "centre": [round(float(a), 3) for a in c], "card_long_tons": loft.SPECS["weights"]["deck_and_deckhouses"],
            "card_centre_xz": loft.SPECS["weight_positions"]["deck_and_deckhouses"]}


def layout_checks(fp, sheer):
    """What stands on the deck must stand inside the covering boards with room to walk past (0.15 m), clear of the
    mast's partners, and clear of each other (5 cm); the rudder's stock must come up under the wheel box."""
    sheer = np.asarray(sheer, float)
    cb = PL["covering_board"]
    out = {"inboard_m": {}, "mast_clear_m": {}, "pairs_closer_than_0_05_m": [], "ok": True}
    for k, P in fp.items():
        hd = np.interp(P[:, 0], sheer[:, 0], np.abs(sheer[:, 1]))
        room = float(np.min(hd - np.abs(P[:, 1]) - cb))
        out["inboard_m"][k] = round(room, 3)
        if room < 0.15:
            out["ok"] = False
        mp = np.array([[DK["mast"]["x"], 0.0]])
        mc = 0.0 if in_poly(mp, P)[0] else float(seg_dist(mp, P)[0])          # from the mast to the outline's edges
        out["mast_clear_m"][k] = round(mc, 3)
        if mc < DK["mast"]["clear_radius"]:
            out["ok"] = False
    names = list(fp)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = poly_gap(fp[names[i]], fp[names[j]])
            if d < 0.05:
                out["pairs_closer_than_0_05_m"].append([names[i], names[j], round(d, 3)])
                out["ok"] = False
    p0, up, top = shell.stock_axis()
    out["stock_meets_deck"] = [round(float(a), 3) for a in top]
    out["stock_under_wheel_box"] = bool(in_poly(np.array([top[:2]]), fp["WheelBox"])[0])
    out["ok"] = out["ok"] and out["stock_under_wheel_box"]
    return out
