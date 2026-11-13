"""Bluebonnet's hull surface from lines_bluebonnet.json: pure geometry (numpy and scipy, no Blender) (docs/jclass-1).

Our own lines, drawn to the size card (specs_bluebonnet.json), not read from any real yacht. The design is a handful of
curves along the length: the canoe body's centreline (counter, run, bottom, forefoot, spoon bow), the keel's outline
(raked leading edge, bottom with drag, raked post), the sheer, the deck edge's half-breadth and the "knuckle" (each
section's shoulder: on the load waterline amidships, rising up the section in the overhangs), plus a few shape factors.
Each station's section is a control polygon built from those curves (keel bottom, keel side, keel root, floor, bilge,
knuckle, topside, sheer), and the hull is the bicubic B-spline surface on that control net. A B-spline surface is
smooth to the second derivative everywhere (C2), so a fair net gives a fair hull: the fairness check
(Tools/shapeloop/fairness.py) counts what is left. The keel is part of the same surface: where the keel's outline drops
below the canoe body, the section's first control points run down the keel's sides, and the surface turns them into
the wineglass section's hollow garboard on its own.

The aft rows lean to the transom's rake, so the surface's aft edge lies in the transom's plane; the forward row is the
stem head itself. Frame: metres, X forward, Y starboard, Z up, origin on the centreline at the middle of the load
waterline. The surface is the starboard half (y >= 0); the build mirrors it.

    python loft.py [out dir]      writes hydrostatics.json, sections.json and lines.png (lines.png needs matplotlib)
"""
import json
import math
import os
import sys

import numpy as np
from scipy.interpolate import BSpline

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = json.load(open(os.path.join(HERE, "lines_bluebonnet.json")))
SPECS = json.load(open(os.path.join(HERE, "specs_bluebonnet.json")))

N_ROWS = 72          # control rows along the length
N_TILT = 5           # aft rows leaning toward the transom's rake
DEG = 3              # bicubic
RHO_SEA = 1025.0     # kg/m^3
FT = 0.3048


def _fair(pts, tol):
    """A design curve faired through its key points the way a loftsman's batten is: a cubic spline that may miss each
    key point by up to tol (the ends are held), with the least change of curvature (the integral of the third
    derivative squared) that allows. A spline forced exactly through hand-placed points bends to meet each one, and on
    a hull that shows as a ripple in the reflections every few metres; the faired curve's curvature changes evenly."""
    p = np.asarray(pts, float)
    x, y = p[:, 0], p[:, 1]
    lo, hi = float(x[0]), float(x[-1])
    nseg = max(6, int(round((hi - lo) / FAIR_KNOT_M)))
    t = np.concatenate([[lo] * DEG, np.linspace(lo, hi, nseg + 1), [hi] * DEG])
    nc = nseg + DEG
    eye = np.eye(nc)
    A = np.stack([BSpline(t, eye[j], DEG)(x) for j in range(nc)], axis=1)
    mids = 0.5 * (t[DEG:DEG + nseg] + t[DEG + 1:DEG + 1 + nseg])
    D3 = np.stack([BSpline(t, eye[j], DEG).derivative(3)(mids) for j in range(nc)], axis=1)
    P = (hi - lo) / nseg * D3.T @ D3
    P *= np.trace(A.T @ A) / max(np.trace(P), 1e-30)          # the penalty on the data's scale
    w = np.ones(len(x))
    w[0] = w[-1] = 1e6                                        # the ends are held

    def solve(lam):
        return np.linalg.solve(A.T @ (w[:, None] * A) + lam * P + 1e-12 * np.eye(nc), A.T @ (w * y))
    a, b = -10.0, 6.0                                         # log10 of the penalty: the stiffest batten within tol
    for _ in range(48):
        m = 0.5 * (a + b)
        if np.max(np.abs(A @ solve(10 ** m) - y)) <= tol:
            a = m
        else:
            b = m
    f = BSpline(t, solve(10 ** a), DEG)

    def g(xq):
        return f(np.clip(np.asarray(xq, float), lo, hi))
    g.miss = float(np.max(np.abs(f(x) - y)))
    assert g.miss <= tol * 1.001, f"design curve misses its key points by {g.miss:.4f} (tolerance {tol})"
    return g


FAIR = LINES["fairing"]["tolerance"]
FAIR_KNOT_M = LINES["fairing"]["knot_spacing_m"]
SS = LINES["section_shape"]
CANOE = _fair(LINES["canoe_bottom"]["points"], FAIR["canoe_bottom"])
SHEER = _fair(LINES["sheer"]["points"], FAIR["sheer"])
DECK_HB = _fair(LINES["deck_half_breadth"]["points"], FAIR["deck_half_breadth"])
KNUCKLE = _fair(LINES["knuckle"]["half_breadth"], FAIR["knuckle_half_breadth"])
KNUCKLE_F = _fair(LINES["knuckle"]["height_fraction"], FAIR["knuckle_height_fraction"])
FLOOR = _fair(SS["floor"], FAIR["floor"])
DEADRISE = _fair(SS["deadrise_deg"], FAIR["deadrise_deg"])
BILGE_B = _fair(SS["bilge_breadth"], FAIR["bilge_breadth"])
BILGE_H = _fair(SS["bilge_height"], FAIR["bilge_height"])
FLARE = _fair(SS["flare"], FAIR["flare"])
KEEL = LINES["keel"]
END = LINES["ends"]


def smin(a, b, k):
    """Polynomial smooth minimum (C2): exactly min(a, b) where they differ by more than k (k may vary along x)."""
    k = np.maximum(k, 1e-9)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h ** 3 * k / 6.0


def smax(a, b, k):
    return -smin(-a, -b, k)


def _line(p, q):
    (x0, z0), (x1, z1) = p, q
    s = (z1 - z0) / (x1 - x0)
    return lambda x: z0 + s * (np.asarray(x, float) - x0), s


LE, LE_SLOPE = _line(*KEEL["leading_edge"])
BOT, _ = _line(*KEEL["bottom"])
POST, POST_SLOPE = _line(*KEEL["post"])


def keel_outline(x):
    """The keel's lower edge (leading edge, bottom, post), its corners rounded; above 4 m it no longer matters."""
    z = smax(LE(x), BOT(x), KEEL["round_bottom_fwd"])
    z = smax(z, POST(x), KEEL["round_heel"])
    (xt, zt), _ = KEEL["leading_edge"]               # past the leading edge's top it climbs away into the canoe body
    z = smax(z, zt + 3.0 * (np.asarray(x, float) - xt), 0.3)
    return np.minimum(z, 4.0)


def leading_edge_tangent(toe):
    """The leading edge's top: where the straight line up from the toe touches the forefoot from below, so the keel's
    leading edge and the stem are one convex line with no knee between (lines_bluebonnet.json holds the result)."""
    xs = np.linspace(toe[0] + 4.0, END["stem_head"][0] - 0.5, 2000)
    s = (CANOE(xs) - toe[1]) / (xs - toe[0])
    i = int(np.argmin(s))
    return [round(float(xs[i]), 3), round(float(CANOE(xs[i])), 3)]


def fillet(x):
    """The hollow where the keel meets the canoe body: full under the counter (the post's fillet), none at the forefoot,
    where the leading edge runs tangent into the stem. It changes along the keel's bottom, where the two are far apart."""
    xa, xf = KEEL["bottom"][1][0], KEEL["bottom"][0][0]
    t = np.clip((np.asarray(x, float) - xa) / (xf - xa), 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    return KEEL["fillet"] + (KEEL["fillet_fwd"] - KEEL["fillet"]) * t


def profile(x):
    """The centreline's lowest point at x: the canoe body, or the keel where it hangs below, with a hollow aft."""
    return smin(CANOE(x), keel_outline(x), fillet(x))


def _naca(xi):
    xi = np.clip(xi, 0.0, 1.0)
    return 5 * 0.2 * (0.2969 * np.sqrt(xi) - 0.1260 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3 - 0.1036 * xi ** 4) / 0.1


def keel_half_thickness(x, z, f):
    """Half-thickness of the keel at (x, z), f of the way up from its bottom to the canoe body there: a foil between
    the leading edge and the post at that height, thickest a third of the way back, tapering from the root's thickness
    down to the bottom's (the lead's), so the garboard's hollow runs on down the keel's sides."""
    xle = KEEL["leading_edge"][0][0] + (z - KEEL["leading_edge"][0][1]) / LE_SLOPE
    xte = KEEL["post"][0][0] + (z - KEEL["post"][0][1]) / POST_SLOPE
    c = max(xle - xte, 0.5)
    xi = (xle - x) / c
    f = min(max(f, 0.0), 1.0)
    T = KEEL["half_thickness_bottom"] + f * (KEEL["half_thickness_root"] - KEEL["half_thickness_bottom"])
    tp = KEEL["half_thickness_post"]
    s = _naca(xi) / _naca(0.3)
    # the lead's casting is blunt: along the keel's bottom (its lowest 0.6 m) it keeps most of its thickness out to
    # the toe and the heel, so the keel ends in a broad rounded bottom, not a knife edge; the foil's fine leading edge
    # and the post's thin trailing edge start above it
    b = KEEL["bottom_blunt"] * (1.0 - _smoothstep((z - float(BOT(x))) / 0.6))
    s = 1.0 - (1.0 - min(max(s, 0.0), 1.0)) * (1.0 - b)
    t = tp + (T - tp) * min(max(s, 0.0), 1.0)
    # forward of the keel and aft of the post the line runs on as the stem bar's width, toward the stem and transom
    xf, xa = KEEL["leading_edge"][0][0], KEEL["post"][1][0]
    f = max(_smoothstep((x - xf) / 3.0), _smoothstep((xa - x) / 3.0))
    return t + (KEEL["half_thickness_stem"] - t) * f


def _smoothstep(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (6 * t - 15) + 10)


def section_polygon(x, xs_sheer=None):
    """Control polygon of the half section at x (vertical plane): list of (y, z), keel bottom to sheer."""
    xs = x if xs_sheer is None else xs_sheer
    zb = float(profile(x))
    zc = float(CANOE(x))
    hf = max(0.0, zc - zb)
    zs = float(SHEER(xs))
    hd = float(DECK_HB(xs))
    H = max(zs - zc, 1e-6)
    zw = zc + float(KNUCKLE_F(x)) * H
    bw = min(float(KNUCKLE(x)), hd)
    fl = float(FLOOR(x))
    beta = math.radians(float(DEADRISE(x)))
    c2 = (float(BILGE_B(x)) * bw, zc + float(BILGE_H(x)) * (zw - zc))
    # the floor rises from the keel bar's face (the bar narrows into the stem head, where the whole section does);
    # never above the straight line to the bilge point
    y0 = min(KEEL["half_thickness_stem"], 0.4 * bw)
    run = max(c2[0] - y0, 1e-3)
    rise = min(math.tan(beta), max(c2[1] - zc, 0.0) / run)
    c1y = min(max(y0 + fl * (bw - y0), y0), c2[0])
    c1 = (c1y, zc + (c1y - y0) * rise)
    c3 = (bw, zw)
    c4 = (bw + (hd - bw) * float(FLARE(x)), zw + 0.55 * (zs - zw))
    c5 = (hd, zs)
    # The keel's run of points: its bottom, two points up each side and its root, where the garboard's hollow turns out
    # into the canoe's floor. Where there is no keel (forefoot, counter) the same points sit together at the canoe's
    # centreline, a keel bar's width out, so the section is the same family of curves everywhere along the hull.
    z2 = zb + 0.35 * hf
    z3 = zb + 0.62 * hf
    def kt(z):        # the keel's half-thickness, or the stem bar's (narrowing into the stem head) where there is none;
        if hf <= 0:   # where the keel is shallow (its leading edge's top, the post's) it eases to the bar's, so the
            return y0  # bar runs on into the keel with no swelling
        t = keel_half_thickness(x, z, (z - zb) / hf)
        return y0 + (t - y0) * _smoothstep(hf / KEEL["full_thickness_depth"])
    ys = np.maximum.accumulate([0.0, 0.85 * kt(zb), kt(z2), kt(z3)])     # never narrowing upward
    lead = [(float(ys[0]), zb), (float(ys[1]), zb), (float(ys[2]), z2), (float(ys[3]), z3)]
    return lead + [c1, c2, c3, c4, c5]


def row_positions():
    """The control rows' x along the hull, closer together toward the ends."""
    xa, xf = END["transom_bottom"][0], END["stem_head"][0]
    s = np.linspace(0, 1, N_ROWS)
    g = s - 0.45 * np.sin(2 * math.pi * s) / (2 * math.pi)
    return xa + (xf - xa) * g


def control_net():
    """(N_ROWS, cols, 3) control points. The aft rows lean so the first row lies in the transom's plane."""
    (xtb, ztb), (xtt, ztt) = END["transom_bottom"], END["transom_top"]
    tau0 = (xtt - xtb) / (ztt - ztb)
    rows = []
    xs = row_positions()
    for i, x in enumerate(xs):
        tau = tau0 * (1 - i / N_TILT) ** 2 if i < N_TILT else 0.0
        zb = float(profile(x))
        xsh = x + tau * (float(SHEER(x)) - zb)
        for _ in range(2):
            xsh = x + tau * (float(SHEER(xsh)) - zb)
        poly = section_polygon(x, xsh)
        if i == len(xs) - 1:                         # the stem head: one point
            poly = [(0.0, float(SHEER(x)))] * len(poly)
        else:                                        # a section runs out and up from the keel: no folds
            d = np.diff(np.array(poly), axis=0)
            assert (d >= -1e-9).all(), f"section polygon at x {x:.3f} folds back: {poly}"
        rows.append([(x + tau * (z - zb), y, z) for y, z in poly])
    return np.array(rows)


def _knots(n):
    inner = np.linspace(0, 1, n - DEG + 1)
    return np.concatenate([[0] * DEG, inner, [1] * DEG])


def surface(nu=480, nv=160, net=None):
    """The starboard half surface on an (nu, nv) grid: (nu, nv, 3). u runs transom to stem, v keel to sheer.
    The grid is finer near the ends and near the keel bottom, where the surface turns fastest."""
    P = control_net() if net is None else net
    nr, nc, _ = P.shape
    s = np.linspace(0, 1, nu)
    u = s - 0.35 * np.sin(2 * math.pi * s) / (2 * math.pi)
    t = np.linspace(0, 1, nv)
    v = 0.35 * 0.5 * (1 - np.cos(math.pi * t)) + 0.65 * t
    Nu = BSpline.design_matrix(np.clip(u, 0, 1 - 1e-12), _knots(nr), DEG).toarray()
    Nv = BSpline.design_matrix(np.clip(v, 0, 1 - 1e-12), _knots(nc), DEG).toarray()
    Nu[-1] = 0
    Nu[-1, -1] = 1
    Nv[-1] = 0
    Nv[-1, -1] = 1
    return np.einsum("ui,ijk,vj->uvk", Nu, P, Nv)


# ----------------------------------------------------------------------------------------------- measuring the hull

def _clip_area_below(sec, zcut=0.0):
    """Area and centroid (y, z) of the half section below zcut, between the curve and the centreline (shoelace)."""
    pts = []
    for (y0, z0), (y1, z1) in zip(sec[:-1], sec[1:]):
        if z0 <= zcut:
            pts.append((y0, z0))
        if (z0 - zcut) * (z1 - zcut) < 0:
            t = (zcut - z0) / (z1 - z0)
            pts.append((y0 + t * (y1 - y0), zcut))
    if sec[-1][1] <= zcut:
        pts.append(tuple(sec[-1]))
    if len(pts) < 2:
        return 0.0, 0.0, 0.0
    # close along the cut to the centreline and down the centreline to the start
    poly = [(0.0, pts[0][1])] + pts + [(0.0, pts[-1][1])]
    a = cy = cz = 0.0
    for (y0, z0), (y1, z1) in zip(poly, poly[1:] + poly[:1]):
        c = y0 * z1 - y1 * z0
        a += c
        cy += (y0 + y1) * c
        cz += (z0 + z1) * c
    a *= 0.5
    if abs(a) < 1e-12:
        return 0.0, 0.0, 0.0
    return abs(a), cy / (6 * a), cz / (6 * a)


def _half_breadth_at(sec, z):
    """The outermost half-breadth where the section crosses height z (0 if it doesn't)."""
    best = 0.0
    for (y0, z0), (y1, z1) in zip(sec[:-1], sec[1:]):
        if (z0 - z) * (z1 - z) <= 0 and z0 != z1:
            t = (z - z0) / (z1 - z0)
            best = max(best, y0 + t * (y1 - y0))
    return best


def station_cut(S, x):
    """The half section at exactly x, cut from the surface grid: list of (y, z) keel to sheer, or None."""
    out = []
    for j in range(S.shape[1]):
        col = S[:, j, :]
        xs = col[:, 0]
        k = np.where((xs[:-1] - x) * (xs[1:] - x) <= 0)[0]
        if len(k) == 0:
            continue
        k = k[-1]
        x0, x1 = xs[k], xs[k + 1]
        t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
        p = col[k] + t * (col[k + 1] - col[k])
        out.append((float(p[1]), float(p[2])))
    return out if len(out) >= 2 else None


def hydrostatics(S=None, n=400):
    S = surface() if S is None else S
    cl = S[:, 0, :]                        # the centreline (keel, stem, counter): v = 0
    sheer = S[:, -1, :]
    x_lo, x_hi = float(S[..., 0].min()), float(S[..., 0].max())
    # load waterline ends: where the centreline profile crosses z 0, fore and aft
    z = cl[:, 2]
    cross = np.where(z[:-1] * z[1:] < 0)[0]
    xs_cross = [cl[k, 0] + (0 - z[k]) / (z[k + 1] - z[k]) * (cl[k + 1, 0] - cl[k, 0]) for k in cross]
    wl_aft, wl_fwd = float(min(xs_cross)), float(max(xs_cross))
    xs = np.linspace(x_lo + 1e-3, x_hi - 1e-3, n)
    A, Y, Zc, B = [], [], [], []
    secs = {}
    for x in xs:
        sec = station_cut(S, x)
        if sec is None:
            A.append(0.0); Y.append(0.0); Zc.append(0.0); B.append(0.0)
            continue
        a, cy, cz = _clip_area_below(sec)
        A.append(2 * a); Zc.append(cz); B.append(_half_breadth_at(sec, 0.0) if a > 0 else 0.0)
        secs[float(x)] = sec
    A, Zc, B = np.array(A), np.array(Zc), np.array(B)
    V = float(np.trapezoid(A, xs))
    lcb = float(np.trapezoid(A * xs, xs) / V)
    vcb = float(np.trapezoid(A * Zc, xs) / V)
    Aw = float(np.trapezoid(2 * B, xs))
    lcf = float(np.trapezoid(2 * B * xs, xs) / Aw)
    i_t = float(np.trapezoid(2 * B ** 3 / 3, xs))              # transverse second moment of the waterplane
    Am = float(A.max())
    x_am = float(xs[int(A.argmax())])
    lwl = wl_fwd - wl_aft
    bwl = 2 * float(B.max())
    draft = -float(S[..., 2].min())
    beam = 2 * float(S[..., 1].max())
    # wetted area: the grid's quads below the waterline (both sides)
    q = S
    d1 = q[1:, 1:] - q[:-1, :-1]
    d2 = q[1:, :-1] - q[:-1, 1:]
    qa = 0.5 * np.linalg.norm(np.cross(d1, d2), axis=-1)
    qz = 0.25 * (q[1:, 1:, 2] + q[:-1, :-1, 2] + q[1:, :-1, 2] + q[:-1, 1:, 2])
    wetted = 2 * float(qa[qz < 0].sum())
    # canoe body (above the keel's root) for the keel's volume
    return {
        "loa_m": round(x_hi - x_lo, 3), "loa_ft": round((x_hi - x_lo) / FT, 2),
        "lwl_m": round(lwl, 3), "lwl_ft": round(lwl / FT, 2), "lwl_ends_m": [round(wl_aft, 3), round(wl_fwd, 3)],
        "beam_m": round(beam, 3), "beam_ft": round(beam / FT, 2),
        "beam_wl_m": round(bwl, 3), "beam_wl_ft": round(bwl / FT, 2),
        "draft_m": round(draft, 3), "draft_ft": round(draft / FT, 2),
        "freeboard_min_m": round(float(sheer[:, 2].min()), 3),
        "bow_overhang_ft": round((x_hi - wl_fwd) / FT, 2), "stern_overhang_ft": round((wl_aft - x_lo) / FT, 2),
        "volume_m3": round(V, 2), "volume_ft3": round(V / FT ** 3, 0),
        "displacement_t": round(V * RHO_SEA / 1000, 1), "displacement_long_tons": round(V / FT ** 3 / 35.0, 1),
        "lcb_m": round(lcb, 3), "lcb_pct_lwl_from_bow": round(100 * (wl_fwd - lcb) / lwl, 1),
        "vcb_m": round(vcb, 3),
        "waterplane_m2": round(Aw, 2), "lcf_m": round(lcf, 3),
        "bm_t_m": round(i_t / V, 3),
        "midship_area_m2": round(Am, 3), "midship_x_m": round(x_am, 2),
        "cp": round(V / (Am * lwl), 3), "cb": round(V / (lwl * bwl * draft), 3),
        "cwp": round(Aw / (lwl * bwl), 3),
        "wetted_m2": round(wetted, 1), "wetted_ft2": round(wetted / FT ** 2, 0),
        "disp_length_ratio": round((V / FT ** 3 / 35.0) / (0.01 * lwl / FT) ** 3, 1),
    }


def rudder_stock_z(x):
    """The rudder's stock line: parallel to the post, the rudder's chord forward of it. At station x the rudder is the
    part of the keel below this height (aft of the stock); slice 2 hangs it there."""
    (hx, hz), _ = KEEL["post"]
    return hz + POST_SLOPE * (np.asarray(x, float) - hx - KEEL["rudder_chord"])


def volume_below(S, zcut, n=400, zfloor=None):
    """Volume (m^3) of the hull below the plane z = zcut (and above zfloor(x), if given), and its centroid (x, z)."""
    x_lo, x_hi = float(S[..., 0].min()), float(S[..., 0].max())
    xs = np.linspace(x_lo + 1e-3, x_hi - 1e-3, n)
    A, Z = [], []
    for x in xs:
        sec = station_cut(S, x)
        a, _, cz = _clip_area_below(sec, zcut) if sec else (0.0, 0.0, 0.0)
        if sec and zfloor is not None:
            a2, _, cz2 = _clip_area_below(sec, min(float(zfloor(x)), zcut))
            if a - a2 > 1e-12:
                a, cz = a - a2, (a * cz - a2 * cz2) / (a - a2)
            else:
                a, cz = 0.0, 0.0
        A.append(2 * a)
        Z.append(cz)
    A, Z = np.array(A), np.array(Z)
    V = float(np.trapezoid(A, xs))
    if V <= 0:
        return 0.0, 0.0, 0.0
    return V, float(np.trapezoid(A * xs, xs) / V), float(np.trapezoid(A * Z, xs) / V)


def lead_keel(S, lead_t, rho_lead=11340.0):
    """Where the lead goes: the depth whose keel volume below it, forward of the rudder's stock, holds lead_t tonnes,
    and the lead's centroid. Slice 2 puts the casting's top line there."""
    need = lead_t * 1000.0 / rho_lead
    lo, hi = float(S[..., 2].min()), 0.0                # the keel's bottom and the waterline
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if volume_below(S, mid, 200, rudder_stock_z)[0] > need:
            hi = mid
        else:
            lo = mid
    top = 0.5 * (lo + hi)
    V, cx, cz = volume_below(S, top, zfloor=rudder_stock_z)
    assert abs(V - need) < 0.01 * need, "the lead does not fit in the hull"
    assert top < float(CANOE(np.linspace(-10, 10, 201)).min()), "the lead's top is above the canoe body: no keel to hold it"
    return {"lead_t": round(lead_t, 1), "lead_m3": round(need, 2), "lead_m3_placed": round(V, 3), "top_z_m": round(top, 3),
            "centroid_x_m": round(cx, 3), "centroid_z_m": round(cz, 3)}


def weight_check(S, h):
    """The size card's weight split against the hull: does the lead fit in the keel, and where are G and B?
    Heights of the parts other than the lead are our estimates for a 1930s steel J (see specs_bluebonnet.json)."""
    w = SPECS["weights"]
    lt = 1.016047
    lead = lead_keel(S, w["lead_keel"] * lt)
    # (long tons, x m, z m) of each part; the lead's from the hull, the rest estimated
    parts = {"lead_keel": (w["lead_keel"], lead["centroid_x_m"], lead["centroid_z_m"])}
    for k, xz in SPECS["weight_positions"].items():
        if k != "note":
            parts[k] = (w[k], xz[0], xz[1])
    W = sum(p[0] for p in parts.values())
    xg = sum(p[0] * p[1] for p in parts.values()) / W
    zg = sum(p[0] * p[2] for p in parts.values()) / W
    km = h["vcb_m"] + h["bm_t_m"]
    return {"lead": lead, "total_long_tons": round(W, 1), "lcg_m": round(xg, 3), "lcb_m": h["lcb_m"],
            "lcg_minus_lcb_m": round(xg - h["lcb_m"], 3), "vcg_m": round(zg, 3), "km_m": round(km, 3),
            "gm_m": round(km - zg, 3)}


def export_sections(path, S=None, n=31):
    """Half sections at n stations for the physics (slice 13), in the shape of Tools/boats/maxi/sections.json: each
    from the centreline (keel or counter) out to the sheer, 24 points. Unlike the maxi's, the sections include the keel:
    a J's keel is part of her hull surface, so there are no separate appendages to add (the rudder is slice 2)."""
    S = surface() if S is None else S
    h = hydrostatics(S)
    x_lo, x_hi = END["transom_bottom"][0], float(S[..., 0].max())     # aft of the transom's foot the cut misses the keel
    out = {"tag": "Bluebonnet", "frame": "metres, X forward, Y starboard, Z up, origin on the centreline at mid "
           "load waterline", "keel": "included in the sections", "stations": [],
           "volume_m3": h["volume_m3"], "centre_of_buoyancy": [h["lcb_m"], h["vcb_m"]]}
    for x in np.linspace(x_lo + 0.05, x_hi - 0.05, n):
        sec = station_cut(S, x)
        if not sec:
            continue
        p = np.array(sec)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
        t = np.linspace(0.0, s[-1], 24)                     # 24 points evenly along the girth
        pts = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
        out["stations"].append({"x": round(float(x), 4),
                                "half_section": [[round(float(y), 4), round(float(z), 4)] for y, z in pts],
                                "sheer": round(float(p[-1, 1]), 4), "half_wl": round(_half_breadth_at(sec, 0.0), 4)})
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    return out


def draw_lines(S, path):
    """A lines drawing (profile with buttocks, half-breadth plan with waterlines, body plan) for the docs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(18, 7), dpi=110)
    axp = fig.add_axes([0.03, 0.47, 0.62, 0.46])
    axh = fig.add_axes([0.03, 0.06, 0.62, 0.34])
    axb = fig.add_axes([0.68, 0.06, 0.31, 0.87])
    x_lo, x_hi = float(S[..., 0].min()), float(S[..., 0].max())
    # profile: centreline and sheer
    axp.plot(S[:, 0, 0], S[:, 0, 2], "k", lw=1.2)
    axp.plot(S[:, -1, 0], S[:, -1, 2], "k", lw=1.2)
    axp.plot(S[0, :, 0], S[0, :, 2], "k", lw=1.2)
    axp.axhline(0, color="tab:blue", lw=0.8)
    # buttocks: y = const cuts
    for yb in (0.5, 1.0, 1.5, 2.0, 2.5):
        pts = []
        for i in range(S.shape[0]):
            row = S[i]
            ys = row[:, 1]
            k = np.where((ys[:-1] - yb) * (ys[1:] - yb) <= 0)[0]
            for kk in k:
                t = (yb - ys[kk]) / (ys[kk + 1] - ys[kk]) if ys[kk + 1] != ys[kk] else 0
                p = row[kk] + t * (row[kk + 1] - row[kk])
                pts.append((p[0], p[2], kk))
        if pts:
            # the lowest crossing at each row is the buttock's underwater line
            by = {}
            for x, z, kk in pts:
                by.setdefault(round(x, 4), []).append(z)
            xs = sorted(by)
            axp.plot(xs, [min(by[x]) for x in xs], color="tab:red", lw=0.6)
    # waterlines in plan, and the deck edge
    axh.plot(S[:, -1, 0], S[:, -1, 1], "k", lw=1.2)
    for zl in (-1.2, -0.9, -0.6, -0.3, 0.0, 0.4, 0.8):
        xs, ys = [], []
        for i in range(S.shape[0]):
            sec = list(zip(S[i, :, 1], S[i, :, 2]))
            b = _half_breadth_at(sec, zl)
            if b > 0:
                xs.append(S[i, 0, 0]); ys.append(b)
        axh.plot(xs, ys, color="tab:blue" if zl == 0 else "tab:gray", lw=1.0 if zl == 0 else 0.6)
    # stations
    stations = np.linspace(-12.954, 12.954, 11)
    for x in stations:
        axp.axvline(x, color="0.85", lw=0.5, zorder=0)
        axh.axvline(x, color="0.85", lw=0.5, zorder=0)
        sec = station_cut(S, x)
        if sec:
            ys = [p[0] for p in sec]
            zs = [p[1] for p in sec]
            if x >= -0.01:
                axb.plot(ys, zs, "k", lw=0.8)
            else:
                axb.plot([-y for y in ys], zs, "k", lw=0.8)
    for ax in (axp, axh):
        ax.set_xlim(x_lo - 0.5, x_hi + 0.5)
        ax.set_aspect("equal")
        ax.grid(False)
    axb.axhline(0, color="tab:blue", lw=0.8)
    axb.axvline(0, color="0.6", lw=0.5)
    axb.set_aspect("equal")
    axp.set_title("Profile (red: buttocks 0.5-2.5 m)")
    axh.set_title("Half-breadth plan (blue: load waterline; grey: waterlines -1.2 to +0.8 m)")
    axb.set_title("Body plan (right: forward, left: aft; stations every LWL/10)")
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    S = surface()
    h = hydrostatics(S)
    h["weights"] = weight_check(S, h)
    with open(os.path.join(out, "hydrostatics.json"), "w") as f:
        json.dump(h, f, indent=1)
    export_sections(os.path.join(out, "sections.json"), S)
    try:
        draw_lines(S, os.path.join(out, "lines.png"))
    except ImportError:
        pass
    for k, v in h.items():
        print(f"{k:24s} {v}")
