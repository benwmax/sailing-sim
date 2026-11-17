"""The Catalina 22's swing keel, keel stub and trunk, kick-up rudder and tiller (docs/c22-4): pure geometry, no Blender.

keel_c22.json holds the sizes; build_keel_c22.py meshes what these functions give. Frame: the game's body frame
(X forward, Y starboard, Z up), metres, origin amidships on the design waterline.

  keel_outline()        the keel plate's outline, down, as (x, z) round the plate
  keel_rows(), half_t() the plate as rows of z with their forward and aft edges, and its half-thickness across a row
  raise_angle()         how far the keel turns aft about its pin to its raised draft
  thickness()           the plate's thickness that makes its volume the card's 249 kg of cast iron
  stub_bottom(x), stub_section(x)   the stub moulded under the hull: its bottom and its cross-section
  trunk_top(x)          the slot's top: the trunk inside the hull where the keel's top swings, the hull's bottom aft of it
  stub_volume()         what the stub adds under the water and what the flooded trunk takes away (hull_c22 floats on it)
  blade_outline(), blade_rows()      the rudder blade
  tiller_path()         the tiller's centreline from the rudder head to today's TillerEnd socket

    python3 -I keel_c22.py      prints the sizes and checks; exits non-zero if a check fails
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
K = json.load(open(os.path.join(HERE, "keel_c22.json")))
KL, ST, SL, RD = K["keel"], K["stub"], K["slot"], K["rudder"]
CARD = json.load(open(os.path.join(HERE, "specs_c22.json")))
SINK = CARD["game"]["crew_sink_m"]
DRAFT_DOWN = CARD["targets"]["draft_keel_down_m"] + SINK      # the keel's lowest point under the game's waterline
DRAFT_UP = KL["draft_up"] + SINK
CLEAR = 0.03          # the keel's least clearance inside the slot, at every angle of its swing


def _hull():
    import hull_c22 as H        # (imported late: hull_c22.solve_depth asks this module for the stub's volume; the
    return H                    # caller solves the depth first)


def hull_z(x, y):
    """The hull's bottom at (x, |y|): the section's height where its half-breadth is y (bisection on girth)."""
    H = _hull()
    lo, hi = 0.0, 0.5
    for _ in range(50):
        f = (lo + hi) / 2
        if H.section(x, f)[0] < abs(y):
            lo = f
        else:
            hi = f
    return H.section(x, (lo + hi) / 2)[1]


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (6 * t - 15) + 10)


# ------------------------------------------------------------------ the keel

def fillet(prev, corner, nxt, r, n=8):
    """Points of an arc of radius r rounding the corner prev-corner-nxt (2D), tangent to both legs."""
    ux, uy = prev[0] - corner[0], prev[1] - corner[1]
    vx, vy = nxt[0] - corner[0], nxt[1] - corner[1]
    lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
    ux, uy, vx, vy = ux / lu, uy / lu, vx / lv, vy / lv
    half = math.acos(max(-1.0, min(1.0, ux * vx + uy * vy))) / 2
    d = min(r / math.tan(half), 0.49 * lu, 0.49 * lv)
    r = d * math.tan(half)
    p0 = (corner[0] + ux * d, corner[1] + uy * d)
    p1 = (corner[0] + vx * d, corner[1] + vy * d)
    bx, by = ux + vx, uy + vy
    bl = math.hypot(bx, by)
    c = (corner[0] + bx / bl * r / math.sin(half), corner[1] + by / bl * r / math.sin(half))
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    return [(c[0] + r * math.cos(a0 + da * k / n), c[1] + r * math.sin(a0 + da * k / n)) for k in range(n + 1)]


def _keel_poly(span, n):
    """The plate's outline for a leading edge `span` long (see keel_outline)."""
    px, pz = KL["pivot"]
    rb = KL["boss_radius"]
    a = math.radians(KL["rake_deg"])
    es = (-math.sin(a), -math.cos(a))                 # down the leading edge
    ec = (-math.cos(a), math.sin(a))                  # aft across the plate, square to it
    nf = (-ec[0], -ec[1])                             # the leading edge's forward normal
    o = (px + rb * nf[0], pz + rb * nf[1])            # the leading edge's top, on the boss
    c0, c1 = KL["chord_root"], KL["chord_tip"]
    le = (o[0] + span * es[0], o[1] + span * es[1])
    te = (le[0] + c1 * ec[0], le[1] + c1 * ec[1])
    root = (o[0] + c0 * ec[0], o[1] + c0 * ec[1])     # the trailing edge's line meets the pin's level here
    r_fwd, r_aft = KL["corner_radius"]
    pts = []
    a_nf = math.atan2(nf[1], nf[0])
    a0 = math.radians(100)
    for k in range(n + 1):                            # the boss, from its top round to the leading edge
        t = a0 + (a_nf - a0) * k / n
        pts.append((px + rb * math.cos(t), pz + rb * math.sin(t)))
    pts += fillet(o, le, te, r_fwd, n)                # the lower forward corner
    pts += fillet(le, te, root, r_aft, 2 * n)         # the lower aft corner, on a big radius
    R = math.hypot(root[0] - px, root[1] - pz)        # the top's arc about the pin, from the trailing edge forward
    g0 = math.atan2(root[1] - pz, root[0] - px) % (2 * math.pi)
    g1 = math.radians(KL["top_arc_end_deg"])
    for k in range(n + 1):
        t = g0 + (g1 - g0) * k / n
        pts.append((px + R * math.cos(t), pz + R * math.sin(t)))
    return pts


def keel_outline(n=24):
    """The plate's outline, down, as (x, z): round the pin's boss, down the leading edge raked aft rake_deg, round a
    small lower forward corner and a big lower aft corner, up the trailing edge (square to the leading edge across
    the chord, so the whole plate is raked, not just its front), forward round the top's arc about the pin, and back
    along its top to the boss. Its leading edge's length is solved so its lowest point is the draft."""
    lo, hi = 0.5, 2.0
    for _ in range(50):
        m = (lo + hi) / 2
        if min(z for _, z in _keel_poly(m, 8)) > -DRAFT_DOWN:
            lo = m
        else:
            hi = m
    return _keel_poly((lo + hi) / 2, n)


def _cuts(poly, z):
    """The x's where the closed polygon crosses height z, sorted."""
    xs = []
    for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]):
        if (z0 - z) * (z1 - z) < 0 or (z0 == z and z1 != z):
            xs.append(x0 + (x1 - x0) * (z - z0) / (z1 - z0))
    return sorted(xs)


def rows_of(poly, nz, cluster=True):
    """The region inside `poly` (one span per height) as rows (z, x_aft, x_fwd) from its lowest to its highest
    point, closer together at both ends where the edges turn."""
    zs = [p[1] for p in poly]
    z0, z1 = min(zs), max(zs)
    out = []
    for i in range(nz + 1):
        u = i / nz
        if cluster:
            u = 0.5 - 0.5 * math.cos(math.pi * u) if True else u
            u = 0.6 * u + 0.4 * (i / nz)
        z = z0 + (z1 - z0) * u
        if i == 0 or i == nz:
            x = [p[0] for p in poly if abs(p[1] - z) < 1e-9]
            xm = sum(x) / len(x)
            out.append((z, xm, xm))
            continue
        c = _cuts(poly, z)
        out.append((z, c[0], c[-1]))
    return out


def keel_rows(nz=60):
    return rows_of(keel_outline(), nz)


def half_t(t, xa, xf, x):
    """The plate's half-thickness at x across a row from xa to xf: flat sides, edges rounded on half the thickness."""
    r = t / 2
    d = min(x - xa, xf - x)
    if d >= r:
        return r
    d = max(d, 0.0)
    return r * math.sqrt(max(1 - (1 - d / r) ** 2, 0.0))


def plate_volume(t, rows, nu=16):
    """The plate's volume as build_keel_c22 meshes it: on each row, its two faces through nu + 1 points bunched toward
    both edges (half_t at each, 0 on the outline), straight between them; the rows straight between each other."""
    def row_area(xa, xf):
        c = xf - xa
        if c <= 0:
            return 0.0
        xs = [xa + c * (0.5 - 0.5 * math.cos(math.pi * j / nu)) for j in range(nu + 1)]
        hs = [half_t(t, xa, xf, x) if 0 < j < nu else 0.0 for j, x in enumerate(xs)]
        return sum((xs[j + 1] - xs[j]) * (hs[j] + hs[j + 1]) for j in range(nu))     # both faces: 2 x trapezoids / 2
    v = 0.0
    for (za, xa0, xf0), (zb, xa1, xf1) in zip(rows, rows[1:]):
        v += 0.5 * (row_area(xa0, xf0) + row_area(xa1, xf1)) * (zb - za)
    return v


def thickness():
    """The plate's thickness that makes its volume, as meshed (keel_rows(60), plate_volume), the card's keel weight
    of cast iron."""
    want = KL["mass_kg"] / KL["iron_kg_m3"]
    rows = keel_rows(60)
    lo, hi = 0.01, 0.12
    for _ in range(40):
        t = (lo + hi) / 2
        if plate_volume(t, rows) < want:
            lo = t
        else:
            hi = t
    return (lo + hi) / 2


def turn(pts, phi, about=None):
    """Points (x, z) turned by phi about the pin; positive phi swings the keel's foot aft and up."""
    px, pz = about or KL["pivot"]
    c, s = math.cos(phi), math.sin(phi)
    return [(px + (x - px) * c + (z - pz) * s, pz - (x - px) * s + (z - pz) * c) for x, z in pts]


def raise_angle():
    """The keel's turn about its pin that brings its lowest point to the raised draft."""
    o = keel_outline(48)
    lo, hi = 0.0, math.pi
    for _ in range(60):
        m = (lo + hi) / 2
        if min(z for _, z in turn(o, m)) < -DRAFT_UP:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


# ------------------------------------------------------------------ the stub and the trunk

def stub_shape(x):
    """0 at the stub's ends (inside the hull), 1 along its full depth: a long smooth taper aft, a shorter one forward
    (its front raked about 40 degrees)."""
    (x0, x1), (f0, f1) = ST["x"], ST["full_x"]
    if x <= x0 or x >= x1:
        return 0.0
    if x < f0:
        return smooth((x - x0) / (f0 - x0))
    if x > f1:
        return smooth((x1 - x) / (x1 - f1))
    return 1.0


def stub_bottom(x):
    """The stub's bottom: ST bottom_z along its full depth, rising into the hull (1 cm inside it) at its ends."""
    top = _hull().keel_z(x) + 0.01
    return top + (ST["bottom_z"] - top) * stub_shape(x)


def stub_section(x, n=4):
    """The stub's port half at x, from its top (1.5 cm inside the hull) down its side, round its bottom corner, to
    the slot's edge: [(y, z)] with y negative (port). The starboard half mirrors it."""
    zb = stub_bottom(x)
    wt, wb = ST["half_width_top"], ST["half_width_bottom"]
    s = SL["half_width"]
    zt = hull_z(x, wt) + 0.015
    d = max(zt - zb, 1e-4)
    rc = min(ST["corner_radius"], 0.45 * d, wb - s - 0.002)
    pts = [(-wt, zt)]
    side = lambda z: -(wb + (wt - wb) * (z - zb) / d)
    for k in range(1, 4):
        z = zt - (d - rc) * k / 4
        pts.append((side(z), z))
    for k in range(n + 1):                                       # the corner
        a = math.pi * (1.0 + 0.5 * k / n)
        pts.append((-wb + rc + rc * math.cos(a), zb + rc + rc * math.sin(a)))
    pts.append((-s, zb))
    return pts


def _dense(poly, step=0.01):
    """The closed polygon with points at most `step` apart along each edge."""
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    return out


_TOP = []


def trunk_knots():
    """The trunk's top as knots (x, z) every 10 cm along the slot: the highest the keel's outline reaches within 10 cm
    either side at any angle of its swing, plus CLEAR (so the straight line between two knots clears it too), and
    never under 1.5 cm over the hull's bottom."""
    if not _TOP:
        o = _dense(keel_outline(24))
        phi = raise_angle()
        pts = [p for k in range(61) for p in turn(o, phi * k / 60)]
        s0, s1 = SL["x"]
        n = int(round((s1 - s0) / 0.1))
        for i in range(n + 1):
            x = s0 + (s1 - s0) * i / n
            near = [z for px, z in pts if abs(px - x) <= (s1 - s0) / n + 1e-9]
            need = (max(near) + CLEAR + 0.005) if near else -9.0
            _TOP.append((x, max(need, hull_z(x, SL["half_width"]) + 0.015)))
    return _TOP


def trunk_top(x):
    """The slot's top at x: the trunk inside the hull, as high as the keel's top swings there (trunk_knots)."""
    k = trunk_knots()
    if x <= k[0][0]:
        return k[0][1]
    for (xa, za), (xb, zb) in zip(k, k[1:]):
        if x <= xb:
            return za + (zb - za) * (x - xa) / (xb - xa)
    return k[-1][1]


def _area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def stub_volume(n=200):
    """(solid, flooded): what the stub adds under the hull (its section below the hull's bottom, less the slot), and
    the slot's water inside the hull's skin below the waterline (the hull's mesh counts it as hull)."""
    x0, x1 = ST["x"]
    s = SL["half_width"]
    s0, s1 = SL["x"]
    solid = flooded = 0.0
    H = _hull()
    for i in range(n):
        x = x0 + (x1 - x0) * (i + 0.5) / n
        dx = (x1 - x0) / n
        zb = stub_bottom(x)
        sec = stub_section(x)
        hz = H.keel_z(x)
        # the half section below the hull's bottom (approximated by the centreline's height), both sides
        poly = [(y, min(z, hz)) for y, z in sec] + [(0.0, zb), (0.0, hz)]
        a = 2 * _area(poly)
        if s0 <= x <= s1:
            a -= 2 * s * max(hz - zb, 0.0)
            flooded += 2 * s * max(min(trunk_top(x), 0.0) - hz, 0.0) * dx
        solid += max(a, 0.0) * dx
    return solid, flooded


def swing_check(t):
    """The keel inside its slot at every angle from down to up: [(what, worst margin, where)] (negative fails)."""
    s = SL["half_width"]
    (s0, s1) = SL["x"]
    out = []
    side = s - t / 2
    out.append(("the plate's side to the slot's wall", side, None))
    o = keel_outline(48)
    phi = raise_angle()
    worst_top, worst_end, where = 9.0, 9.0, None
    for k in range(41):
        for x, z in turn(o, phi * k / 40):
            if z > stub_bottom(x) - 0.002 or z > ST["bottom_z"]:
                m = trunk_top(x) - z
                if m < worst_top:
                    worst_top, where = m, (round(x, 3), round(z, 3), k)
                worst_end = min(worst_end, x - s0, s1 - x)
    out.append(("the keel's top under the trunk's top", worst_top, where))
    out.append(("the keel's ends inside the slot's ends", worst_end, None))
    return out


# ------------------------------------------------------------------ the rudder

def blade_outline(n=16):
    """The blade, down, as (x, z): its top round the kick-up bolt (inside the head's cheeks), the shoulder down and
    aft out of the head's foot, the trailing edge down to a rounded lower aft corner, a flat foot, a small lower
    forward corner, and the leading edge, nearly upright, back up to the top's round."""
    px = RD["pivot_x"]
    B, HD = RD["blade"], RD["head"]
    bx, bz = px + HD["bolt"][0], HD["bolt"][1]
    rt = B["top_radius"]
    a_f = math.radians(-30)
    top_f = (bx + rt * math.cos(a_f), bz + rt * math.sin(a_f))         # where the leading edge leaves the top's round
    rake = math.radians(B["rake_deg"])
    zf = B["tip_z"]
    le = (top_f[0] - (top_f[1] - zf) * math.tan(rake), zf)              # the lower forward corner (sharp)
    te = (le[0] - B["chord_tip"], zf)                                   # the lower aft corner (sharp)
    sh = (top_f[0] - (top_f[1] - B["shoulder_z"]) * math.tan(rake) - B["chord_top"], B["shoulder_z"])   # TE's top
    r_fwd, r_aft = B["corner_radius"]
    pts = []
    a_back = math.radians(215)
    for k in range(n + 1):                                    # the top, from forward over to aft, about the bolt
        a = a_f + (a_back - a_f) * k / n
        pts.append((bx + rt * math.cos(a), bz + rt * math.sin(a)))
    pts.append(sh)                                            # the shoulder, down and aft
    pts += fillet(sh, te, le, r_aft, 2 * n)                   # the lower aft corner
    pts += fillet(te, le, top_f, r_fwd, n)                    # the lower forward corner
    return pts


def blade_rows(nz=50):
    return rows_of(blade_outline(), nz)


def naca_half(x, xa, xf, ratio):
    """Half thickness of a NACA 00xx section (thickness/chord `ratio`) at x on a row from its trailing edge xa to its
    leading edge xf."""
    c = xf - xa
    if c <= 0:
        return 0.0
    u = min(max((xf - x) / c, 0.0), 1.0)
    return 5 * ratio * c * (0.2969 * math.sqrt(u) - 0.1260 * u - 0.3516 * u * u + 0.2843 * u ** 3 - 0.1015 * u ** 4)


def blade_area_below(z=0.0, nz=400):
    rows = rows_of(blade_outline(48), nz, cluster=False)
    a = 0.0
    for (za, xa0, xf0), (zb, xa1, xf1) in zip(rows, rows[1:]):
        if zb > z:
            continue
        a += 0.5 * ((xf0 - xa0) + (xf1 - xa1)) * (zb - za)
    return a


def tiller_path(n=24):
    """The tiller's centreline: from inside the head's top, forward over the deck at the transom, to TillerEnd."""
    px = RD["pivot_x"]
    T = RD["tiller"]
    x0, z0 = px + T["root_dx"], T["root_z"]
    x1, z1 = T["end"]
    out = []
    for k in range(n + 1):
        u = k / n
        x = x0 + (x1 - x0) * u
        z = z0 + (z1 - z0) * u + 0.025 * math.sin(math.pi * u)          # a slight arch
        out.append((x, z))
    return out


# ------------------------------------------------------------------ report

def main():
    fails = []
    H = _hull()
    H.solve_depth()
    t = thickness()
    rows = keel_rows(60)
    vol = plate_volume(t, rows)
    o = keel_outline(48)
    low = min(z for _, z in o)
    phi = raise_angle()
    up = turn(o, phi)
    exposed = sum(0.5 * ((r0[2] - r0[1]) + (r1[2] - r1[1])) * (r1[0] - r0[0])
                  for r0, r1 in zip(rows, rows[1:]) if r1[0] <= ST["bottom_z"])
    solid, flooded = stub_volume()
    print(f"keel: plate {t * 1000:.1f} mm thick, {vol:.4f} m^3 = {vol * KL['iron_kg_m3']:.0f} kg of cast iron; "
          f"lowest point z {low:.3f} (draft {-low - SINK:.3f} m empty); {exposed:.3f} m^2 under the stub "
          f"(the physics' keel: 0.60)")
    print(f"raised: turned {math.degrees(phi):.1f} deg aft about the pin, lowest point z {min(z for _, z in up):.3f} "
          f"(draft {-min(z for _, z in up) - SINK:.3f} m empty), from x {min(x for x, _ in up):.3f} to "
          f"{max(x for x, _ in up):.3f}, up to z {max(z for _, z in up):.3f}")
    for what, m, where in swing_check(t):
        ok = m >= (0.008 if "wall" in what else CLEAR - 1e-6) if "top" in what else m >= 0.008
        print(f"  {what}: {m * 1000:.0f} mm{'' if where is None else f' (worst at x, z, step {where})'}"
              f"{'' if ok else '  FAIL'}")
        if not ok:
            fails.append(what)
    print(f"stub: {solid:.4f} m^3 under the hull's bottom, the trunk's water inside the hull {flooded:.4f} m^3 "
          f"(the hull floats on {CARD['game']['design_volume_m3']:.3f} less the keel, the stub's and plus the "
          f"trunk's: canoe depth {H.CANOE_D[0]:.4f})")
    a = blade_area_below()
    br = blade_outline(48)
    print(f"rudder: blade {a:.3f} m^2 under the waterline (the physics' 0.25), lowest point z "
          f"{min(z for _, z in br):.3f} (draft {-min(z for _, z in br) - SINK:.3f} m empty)")
    HD = RD["head"]
    bolt = (RD["pivot_x"] + HD["bolt"][0], HD["bolt"][1])
    kicked = turn(br, math.radians(RD["blade"]["kick_up_deg"]), about=bolt)
    lo_k = min(z for _, z in kicked)
    print(f"  kicked up {RD['blade']['kick_up_deg']} deg: its lowest point z {lo_k:.3f}, aft to x "
          f"{min(x for x, _ in kicked):.3f}{'' if lo_k > 0 else '  FAIL (still in the water)'}")
    if lo_k <= 0:
        fails.append("kicked-up blade out of the water")
    tp = tiller_path()
    xt = -3.25
    zt = min(tp, key=lambda p: abs(p[0] - xt))[1] - RD["tiller"]["depth"][0] / 2
    import deck_c22 as DK
    gap = zt - DK.deck_z(xt, 0.0)
    print(f"tiller: its underside {gap * 1000:.0f} mm over the deck at the transom")
    if gap < 0.01:
        fails.append("tiller over the transom")
    if abs(vol * KL["iron_kg_m3"] - KL["mass_kg"]) > 0.01 * KL["mass_kg"]:
        fails.append("keel weight")
    if fails:
        sys.exit("keel_c22: FAIL: " + ", ".join(fails))


if __name__ == "__main__":
    main()
