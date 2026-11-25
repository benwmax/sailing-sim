"""The Lagoon 42's keels, rudders and saildrives from appendages_lagoon42.json: pure geometry, no Blender
(docs/lagoon42-6).

Each solid is rings of game-frame points (every ring the same length, closed), stacked from the top down or from the
front aft, plus a cap at each end; build_lagoon42.py meshes them. Everything is drawn for the starboard hull (centred at
hull_lagoon42.HULL_Y) and mirrored to port by mirror().

    python3 -I appendages_lagoon42.py      prints the main numbers and writes nothing

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the game's waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_lagoon42 as H  # noqa: E402

AP = json.load(open(os.path.join(HERE, "appendages_lagoon42.json")))
KEEL, RUD, SD = AP["keel"], AP["rudder"], AP["saildrive"]
TIP_Z = AP["light_waterline_z"] - KEEL["draft"]


# ---- shared ----

def naca(u, t):
    """A NACA 4-digit section's half-thickness at chord fraction u (0 at the leading edge), thickness ratio t, its
    trailing edge closed."""
    u = min(max(u, 0.0), 1.0)
    return 5 * t * (0.2969 * math.sqrt(u) - 0.1260 * u - 0.3516 * u ** 2 + 0.2843 * u ** 3 - 0.1036 * u ** 4)


def chord_us(m):
    """m + 1 chord fractions, close together at both edges."""
    return [(1 - math.cos(math.pi * k / m)) / 2 for k in range(m + 1)]


def ring(le, te, half, y0, z, m):
    """A horizontal section: from the leading edge along the starboard face to the trailing edge and back along the
    port face, 2m points. le, te: the edges' x; half(u, x) the half-thickness."""
    us = chord_us(m)
    xs = [le + (te - le) * u for u in us]
    stbd = [(x, y0 + half(u, x), z) for u, x in zip(us, xs)]
    port = [(x, y0 - half(u, x), z) for u, x in zip(us[1:-1], xs[1:-1])][::-1]
    return stbd + port


def fillet(poly, radii, n=8):
    """A closed polygon [(a, b)] with each corner i rounded through radii[i] (0 keeps it sharp)."""
    out = []
    N = len(poly)
    for i in range(N):
        p0, p, p1 = poly[i - 1], poly[i], poly[(i + 1) % N]
        r = radii[i]
        if r <= 0:
            out.append(p)
            continue
        d0 = (p0[0] - p[0], p0[1] - p[1])
        d1 = (p1[0] - p[0], p1[1] - p[1])
        l0, l1 = math.hypot(*d0), math.hypot(*d1)
        d0, d1 = (d0[0] / l0, d0[1] / l0), (d1[0] / l1, d1[1] / l1)
        ang = math.acos(max(-1.0, min(1.0, d0[0] * d1[0] + d0[1] * d1[1])))
        t = r / math.tan(ang / 2)                     # the arc's tangent points are t along each edge
        a = (p[0] + d0[0] * t, p[1] + d0[1] * t)
        b = (p[0] + d1[0] * t, p[1] + d1[1] * t)
        bis = (d0[0] + d1[0], d0[1] + d1[1])
        lb = math.hypot(*bis)
        c = (p[0] + bis[0] / lb * r / math.sin(ang / 2), p[1] + bis[1] / lb * r / math.sin(ang / 2))
        a0 = math.atan2(a[1] - c[1], a[0] - c[0])
        a1 = math.atan2(b[1] - c[1], b[0] - c[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        out += [(c[0] + r * math.cos(a0 + da * k / n), c[1] + r * math.sin(a0 + da * k / n)) for k in range(n + 1)]
    return out


def x_range(poly, z):
    """Where a closed (x, z) outline crosses the height z: (aftmost x, foremost x)."""
    xs = []
    N = len(poly)
    for i in range(N):
        (xa, za), (xb, zb) = poly[i], poly[(i + 1) % N]
        if (za - z) * (zb - z) <= 0 and za != zb:
            xs.append(xa + (xb - xa) * (z - za) / (zb - za))
    return min(xs), max(xs)


def _smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def root_flare(x, z, r):
    """How much a foil thickens (each side) where it meets the hull's bottom at station x: a concave fillet of radius
    r, all of it above the keel line (inside the hull)."""
    d = H.keel_z(x) - z                     # how far under the hull's bottom
    if d <= 0:
        return r
    if d >= r:
        return 0.0
    return r - math.sqrt(max(0.0, r * r - (r - d) ** 2))


def mirror(rings):
    """A solid's rings mirrored onto the port hull."""
    return [[(x, -y, z) for x, y, z in rg] for rg in rings]


# ---- the keel ----

def keel_outline():
    """The keel's profile (x, z), its corners rounded: the top inside the hull, the raked leading edge, the bottom,
    the trailing edge."""
    (ra, rf), (ta, tf) = KEEL["root_x"], KEEL["tip_x"]
    zt = KEEL["top_z"]
    za, zf = H.keel_z(ra), H.keel_z(rf)
    le_top = tf + (rf - tf) * (zt - TIP_Z) / (zf - TIP_Z)
    te_top = ta + (ra - ta) * (zt - TIP_Z) / (za - TIP_Z)
    poly = [(te_top, zt), (le_top, zt), (tf, TIP_Z), (ta, TIP_Z)]
    return fillet(poly, [0.0, 0.0, KEEL["toe_radius"], KEEL["heel_radius"]], 12)


def keel_levels():
    """The keel's section heights from the top down: close together through the root's fillet and round the bottom."""
    zt, rb = KEEL["top_z"], KEEL["bottom_radius"]
    zr0, zr1 = -0.74, -0.95                            # the hull's keel line lies between these under the keel
    zs = [zt + (zr0 - zt) * k / 3 for k in range(3)]
    zs += [zr0 + (zr1 - zr0) * k / 16 for k in range(16)]
    zb = TIP_Z + rb
    n = max(3, round((zr1 - zb) / 0.05))
    zs += [zr1 + (zb - zr1) * k / n for k in range(n)]
    zs += [TIP_Z + rb * math.cos(0.5 * math.pi * k / 8) for k in range(8)] + [TIP_Z + 0.002]
    return zs


def keel_half(z, le, te):
    """The keel's half-thickness function at height z (chord le..te)."""
    c = le - te
    zr = H.keel_z(H.BOT["lowest_x"])
    s = _smooth((zr - z) / (zr - TIP_Z))
    t = (KEEL["thickness"][0] + (KEEL["thickness"][1] - KEEL["thickness"][0]) * s) / c
    h = z - TIP_Z
    rb = KEEL["bottom_radius"]
    f = math.sqrt(max(0.0, 1 - (1 - h / rb) ** 2)) if h < rb else 1.0
    rf = KEEL["root_fillet"]
    return lambda u, x: naca(u, t) * c * f + root_flare(x, z, rf) * math.sqrt(max(0.0, math.sin(math.pi * u)))


def keel_rings(m=40):
    """The starboard keel as rings from the top down, and the index of the first ring in the sacrificial shoe."""
    poly = keel_outline()
    out, shoe = [], None
    for z in keel_levels():
        te, le = x_range(poly, z)
        out.append(ring(le, te, keel_half(z, le, te), H.HULL_Y, z, m))
        if shoe is None and z < TIP_Z + KEEL["shoe_height"]:
            shoe = len(out) - 1
    return out, shoe


# ---- the rudder ----

def rudder_pivot(cy=None):
    """The top of the rudder's stock where it leaves the blade: the game's RudderPivot."""
    x = RUD["stock_x"]
    return (x, H.HULL_Y if cy is None else cy, H.keel_z(x) - RUD["gap"])


def rudder_outline():
    xs, zt = RUD["stock_x"], H.keel_z(RUD["stock_x"]) + 0.3
    (lt, lb), (ct, cb), (rl, rt) = RUD["le_offset"], RUD["chord"], RUD["corner_radius"]
    poly = [(xs + lt - ct, zt), (xs + lt, zt), (xs + lb, RUD["tip_z"]), (xs + lb - cb, RUD["tip_z"])]
    return fillet(poly, [0.0, 0.0, rl, rt], 10)


def rudder_rings(m=24):
    """The starboard rudder's blade as rings from the top (following the hull's bottom, gap under it) down to the tip."""
    poly = rudder_outline()
    t = RUD["thickness_ratio"]
    z1 = max(H.keel_z(x) for x in (RUD["stock_x"] + 0.2, RUD["stock_x"] - 0.6)) - RUD["gap"] - 0.01
    lo = min(z for _, z in poly)
    out = []
    te, le = x_range(poly, z1)
    top = ring(le, te, lambda u, x: naca(u, t) * (le - te), H.HULL_Y, 0.0, m)
    out.append([(x, y, H.keel_z(x) - RUD["gap"]) for x, y, _ in top])
    n = 22
    for k in range(n + 1):
        v = k / n
        z = z1 + (lo + 0.002 - z1) * (1 - math.cos(0.5 * math.pi * v)) ** 0.7 if k else z1
        te, le = x_range(poly, z)
        c = le - te
        out.append(ring(le, te, lambda u, x, c=c: naca(u, t) * c, H.HULL_Y, z, m))
    return out


def rudder_stock():
    """(bottom, top, radius) of the stock, game frame, starboard: from just inside the blade's top (where the blade is
    thick enough to hide it) up into the hull, so only the gap shows it."""
    x, y, z = rudder_pivot()
    return (x, y, z - 0.05), (x, y, z + 0.3), RUD["stock_diameter"] / 2


# ---- the saildrive ----

def sd_axis_z():
    return H.keel_z(SD["le_x"] - SD["chord"] / 2) - SD["depth"]


def leg_rings(m=24):
    """The leg from inside the hull to the pod's axis, rings from the top down."""
    za = sd_axis_z()
    zt = max(H.keel_z(SD["le_x"]), H.keel_z(SD["le_x"] - SD["chord"])) + 0.06
    c, t = SD["chord"], SD["thickness"] / SD["chord"]
    zs = [zt, zt - 0.04] + [zt - 0.04 + (za - zt + 0.04) * k / 14 for k in range(1, 15)]
    out = []
    for z in zs:
        le = SD["le_x"] - SD["rake"] * (zt - z) / (zt - za)
        out.append(ring(le, le - c, lambda u, x, z=z: naca(u, t) * c + root_flare(x, z, SD["root_fillet"])
                        * math.sqrt(max(0.0, math.sin(math.pi * u))), H.HULL_Y, z, m))
    return out


def revolve(profile, axis_y, axis_z, n=24):
    """A body of revolution about an axis along x: profile [(x, r)] from front to back, rings of n points."""
    return [[(x, axis_y + r * math.cos(2 * math.pi * j / n), axis_z + r * math.sin(2 * math.pi * j / n))
             for j in range(n)] for x, r in profile]


def pod_profile():
    p = SD["pod"]
    x0, r0 = p["nose_x"], p["radius"]
    (t0, t1), rt = p["taper_x"], p["tail_radius"]
    nose = [(x0 - 0.12 * (1 - math.cos(0.5 * math.pi * k / 8)), r0 * math.sin(0.5 * math.pi * k / 8) + 0.002)
            for k in range(9)]
    body = [(x0 - 0.12 + (t0 - x0 + 0.12) * k / 4, r0) for k in range(1, 5)]
    taper = [(t0 + (t1 - t0) * k / 6, rt + (r0 - rt) * (1 - _smooth(k / 6))) for k in range(1, 7)]
    return nose + body + taper


def pod_rings():
    return revolve(pod_profile(), H.HULL_Y, sd_axis_z())


def anode_rings():
    a = SD["anode"]
    (x0, x1), r = a["x"], a["radius"]
    e = 0.008
    prof = [(x0, r - e - 0.02), (x0, r - e), (x0 - e, r), (x1 + e, r), (x1, r - e), (x1, r - e - 0.02)]
    return revolve(prof, H.HULL_Y, sd_axis_z())


def intake_slots():
    """The cooling water intake: slots on each side of the leg (closed quads 1.5 mm proud of its faces)."""
    it = SD["intake"]
    za = sd_axis_z()
    zt = max(H.keel_z(SD["le_x"]), H.keel_z(SD["le_x"] - SD["chord"])) + 0.06
    c, t = SD["chord"], SD["thickness"] / SD["chord"]
    (z0, z1), (a, b), n = it["z_over_axis"], it["x_from_le"], it["slots"]
    out = []
    for k in range(n):
        zc = za + z0 + (z1 - z0) * k / (n - 1)
        le = SD["le_x"] - SD["rake"] * (zt - zc) / (zt - za)
        quad = []
        for dx, dz in ((a, -0.006), (b, -0.006), (b, 0.006), (a, 0.006)):
            x = le - dx
            quad.append((x, naca(dx / c, t) * c + 0.0015, zc + dz))
        for side in (1, -1):
            pts = [(x, H.HULL_Y + side * y, z) for x, y, z in quad]
            out.append(pts if side == 1 else pts[::-1])
    return out


def prop_axis():
    return (SD["prop"]["x"], H.HULL_Y, sd_axis_z())


def hub_rings():
    p = SD["prop"]
    x0, (a, b), rc, r = p["x"], p["hub_x"], p["cone_x"], p["hub_radius"]
    prof = [(x0 + a, r - 0.006), (x0 + a - 0.006, r)] + [(x0 + a + (b - a) * k / 4, r - 0.004 * k / 4)
                                                          for k in range(1, 5)]
    prof += [(x0 + b + (rc - b) * k / 6, (r - 0.004) * math.cos(0.5 * math.pi * k / 6) + 0.003) for k in range(1, 7)]
    _, y, z = prop_axis()
    return revolve(prof, y, z)


def blade_rings(k, n_r=14, m=12):
    """Blade k of the starboard propeller: rings from inside the hub to the tip (ogival sections: a flat face, a
    curved back), pitched to the propeller's pitch at each radius and skewed toward its trailing edge."""
    p = SD["prop"]
    x0, y0, z0 = prop_axis()
    R, rh = p["diameter"] / 2, p["hub_radius"] - 0.01
    th = math.pi / 2 + 2 * math.pi * k / p["blades"]
    er = (0.0, math.cos(th), math.sin(th))
    et = (0.0, -math.sin(th), math.cos(th))
    ea = (1.0, 0.0, 0.0)
    out = []
    for i in range(n_r + 1):
        rho = i / n_r
        r = rh + (R - rh) * (1 - (1 - rho) ** 1.3)
        q = (r - rh) / (R - rh)
        c = p["max_chord"] * math.sqrt(max(0.0, 1 - ((q - 0.45) / 0.62) ** 2) * (1 - q ** 6)) + 0.004   # widest at 0.6 R
        t = p["thickness"] * (1 - 0.8 * q) + 0.002
        phi = math.atan2(p["pitch"], 2 * math.pi * r)
        dc = [math.cos(phi) * et[j] + math.sin(phi) * ea[j] for j in range(3)]
        dn = [-math.sin(phi) * et[j] + math.cos(phi) * ea[j] for j in range(3)]
        sk = -p["skew"] * q ** 2
        pts = []
        us = chord_us(m)
        for u in us:                                    # the back, leading edge to trailing edge
            s = c * (0.5 - u)
            pts.append((s, t * 4 * u * (1 - u)))
        for u in us[1:-1][::-1]:                        # the face, back to the leading edge
            pts.append((c * (0.5 - u), 0.0))
        out.append([tuple((x0, y0, z0)[j] + r * er[j] + (s + sk) * dc[j] + y * dn[j] for j in range(3)) for s, y in pts])
    return out


# ---- volumes and areas ----

def _below(x, z):
    return z < H.keel_z(x)


def volume_outside(rings_fn_half, outline, zs, n_u=120, nz=None):
    """Numerically: the volume of a foil under the hull's bottom from its half-thickness and outline."""
    vol = 0.0
    for z0, z1 in zip(zs[:-1], zs[1:]):
        z = (z0 + z1) / 2
        te, le = x_range(outline, z)
        half = rings_fn_half(z, le, te)
        area = 0.0
        for i in range(n_u):
            u = (i + 0.5) / n_u
            x = le + (te - le) * u
            if _below(x, z):
                area += 2 * half(u, x) * (le - te) / n_u
        vol += area * abs(z0 - z1)
    return vol


def lateral(outline, zs, n_u=200):
    """The foil's profile area under the hull's bottom, and its centroid's x."""
    a = ax = 0.0
    for z0, z1 in zip(zs[:-1], zs[1:]):
        z = (z0 + z1) / 2
        te, le = x_range(outline, z)
        for i in range(n_u):
            x = te + (le - te) * (i + 0.5) / n_u
            if _below(x, z):
                d = (le - te) / n_u * abs(z0 - z1)
                a += d
                ax += d * x
    return a, ax / a


def _fine(z0, z1, n=200):
    return [z0 + (z1 - z0) * k / n for k in range(n + 1)]


def keel_numbers():
    poly = keel_outline()
    zs = _fine(KEEL["top_z"], TIP_Z)
    area, cx = lateral(poly, zs)
    return {"volume": volume_outside(keel_half, poly, zs), "area": area, "centroid_x": cx}


def rudder_numbers():
    poly = rudder_outline()
    lo = min(z for _, z in poly)
    zs = _fine(H.keel_z(RUD["stock_x"]) + 0.05, lo)
    t = RUD["thickness_ratio"]
    gap_half = lambda z, le, te: (lambda u, x: naca(u, t) * (le - te) if z < H.keel_z(x) - RUD["gap"] else 0.0)
    area, cx = lateral(poly, zs)
    return {"volume": volume_outside(gap_half, poly, zs), "area": area, "centroid_x": cx}


def saildrive_volume():
    """The leg under the hull to the pod's axis, the pod, the anode and the hub (the blades are a few hundred cm^3)."""
    za = sd_axis_z()
    c, t = SD["chord"], SD["thickness"] / SD["chord"]
    leg = 0.0
    n = 60
    for i in range(n):
        x = SD["le_x"] - c * (i + 0.5) / n
        depth = H.keel_z(x) - (za + SD["pod"]["radius"] * 0.7)
        leg += 2 * naca((i + 0.5) / n, t) * c * (c / n) * max(depth, 0.0)

    def solid(profile):
        return sum(math.pi * ((r0 + r1) / 2) ** 2 * abs(x0 - x1) for (x0, r0), (x1, r1) in zip(profile[:-1], profile[1:]))

    p = SD["prop"]
    hub = math.pi * p["hub_radius"] ** 2 * (p["hub_x"][0] - p["cone_x"]) * 0.8
    a = SD["anode"]
    anode = math.pi * (a["radius"] ** 2 - (SD["pod"]["radius"] * 0.85) ** 2) * (a["x"][0] - a["x"][1])
    return leg + solid(pod_profile()) + hub + anode


def numbers():
    k, r = keel_numbers(), rudder_numbers()
    s = saildrive_volume()
    return {"keel": k, "rudder": r, "saildrive_volume": s, "total_volume": 2 * (k["volume"] + r["volume"] + s)}


if __name__ == "__main__":
    H.solve_depth()
    nb = numbers()
    k, r = nb["keel"], nb["rudder"]
    print(f"keel: bottom {TIP_Z:.3f} m ({KEEL['draft']:.2f} under the light waterline {AP['light_waterline_z']:.3f}), "
          f"{-TIP_Z + H.keel_z(H.BOT['lowest_x']):.3f} m under the canoe; profile area {k['area']:.2f} m^2 about x "
          f"{k['centroid_x']:+.2f} (physics 2.2 m^2 at x +0.3), volume {k['volume']:.3f} m^3")
    print(f"rudder: stock x {RUD['stock_x']:.2f}, pivot z {rudder_pivot()[2]:.3f}, tip {RUD['tip_z']:.2f}; area "
          f"{r['area']:.2f} m^2 about x {r['centroid_x']:+.2f} (physics 0.5 at x -5.4), volume {r['volume']:.4f} m^3")
    print(f"saildrive: axis z {sd_axis_z():.3f}, propeller {SD['prop']['diameter']:.2f} m at x {SD['prop']['x']:.2f}, "
          f"volume {nb['saildrive_volume']:.4f} m^3")
    print(f"appendages, both hulls: {nb['total_volume']:.3f} m^3 (lines_lagoon42.json allows "
          f"{H.BOT['appendage_volume_m3']:.3f})")
