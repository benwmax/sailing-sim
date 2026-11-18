"""The frigate Commonwealth as a ship for the game's physics (docs/frigate-physics).

    python physics.py <build dir> [out dir]

Reads a build's rig.json and sails.json (the yards' pivots and brace limits, each sail's size and corners) and the lines
(loft.py: no Blender), and the estimates in physics_frigate.json (her weights, the knobs only sailing her can settle),
and writes into the out dir (the build dir by default):

  physics.json                 the sheet: everything FBoatConfig needs for her, each number with where it comes from
  CommonwealthHullData.inl     her hull's half sections as the physics reads them (the maxi's MaxiHullData.inl's form)
  commonwealth_trial.inl       ApplyCommonwealth(FBoatConfig&): her whole config from the sheet, for trial/trial_sail.cpp
                               (the standalone physics) and later Fleet.cpp

How she becomes a physics ship
------------------------------
Hull. The physics floats a hull drawn by half sections from the centreline out (FHullShape::Stations: half breadths
never decreasing, the same number of points at each). Her sections are the loft's moulded sections (loft.Lines) with
the outside planking's 4 in added to every half breadth, from the keel's rabbet to the sheer. Her tumblehome (the side
falling in above the wales, up to 3 ft) is carried up vertical from her widest point, which the physics needs; the
sheet records how much breadth that adds high on the side, where only a heel past 15 deg would reach it. Below the
rabbet the keel, deadwood, stem and sternpost (the backbone, the keel's siding wide) are fixed buoyancy
(AppendageVolume), as the maxi's fin is.

Weight. The physics' water is fresh (1,000 kg/m^3), so she weighs 1,000 times her volume to float on her load line. Her
weight is not measured on the model: physics_frigate.json estimates it part by part from period figures (each row with
its source and how far to trust it), the ballast made up to her displacement, and each part spread where it lies (the
hull over its surface and decks, the guns at their ports, the masts up their lengths) for her centre of gravity and
radii of gyration. The sheet checks the result against what the period and her lines say: her metacentric height and
her roll period.

Keel and rudder. A frigate's keel is her whole lateral plane: the canoe body's centreline profile under the water and
the backbone below it. The rudder hangs on the sternpost as the plane's trailing-edge flap, as the J-Class's does
(Tools/shipkit/jclass/physics.py rudder_as_flap: thin-aerofoil flap theory, the lift put at the blade).

Sails. Her eleven square sails come from sails.json one by one (SquareRig.h: FSquareSailDef), their yards' pivots and
brace limits from rig.json, or from the model thread's measured limits.json (--limits); the three headsails are the physics' jib, the five staysails its staysail, the spanker its
main. Sizes as cut; centres and limits as the model has them.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402

FT = 0.3048
IN = 0.0254
FT2 = FT * FT
RHO_FRESH = 1000.0
LT_KG = 1016.047
N_STATIONS = 41
N_POINTS = 25
PLANK = 4 * IN                    # the bottom planking outside the moulded surface (specs_1795.json strakes)


# ----------------------------------------------------------------------------------------------------- the hull

class Lines:
    """loft.Lines in metres in the ship's frame (X forward from station 5, Z up from the load waterline A)."""

    def __init__(self):
        self.L = loft.Lines()
        L = self.L
        self.kx = FT / L.ppf
        self.ky = FT / L.ppf_y
        self.k = L.k * self.ky                                 # the keel's half siding

    def x_px(self, x):
        return x / self.kx + self.L.mid_px

    def x_m(self, xp):
        return (xp - self.L.mid_px) * self.kx

    def hb(self, xp, zp):
        """Moulded half breadth (px) at drawing x, z (px), or 0 outside the side."""
        L = self.L
        upper = zp > loft.KNUCKLE and xp < loft.JOINED
        try:
            return max(float(L.section(xp, "upper" if upper else "lower")(zp)), 0.0)
        except Exception:
            return 0.0

    def bottom_z(self, xp):
        """The side's lowest point at x (px): the rabbet, or where the stern face passes x on the counter."""
        L = self.L
        zb = L.rabbet_z(xp)
        if xp < L.x_aft(loft.KNUCKLE) - 1e-6:
            # aft of the post above the wing transom: the counter starts where the stern face passes x
            zb = L._root(lambda z: float(L._x_sf(z)) - xp, loft.KNUCKLE, L.hi_z[-1])
        return zb


def station(Lm, xp, n=N_POINTS):
    """One half section at drawing x (px): metres, from the centreline at the bottom out and up to the sheer, the
    planking added, half breadths made never decreasing (the tumblehome carried up vertical); and how much that added."""
    L = Lm.L
    zb, zt = Lm.bottom_z(xp), L.sheer_z(xp)
    # heights denser through the waterline (where the physics' columns are cut)
    t = np.linspace(0.0, 1.0, n - 1)
    zs = zb + (zt - zb) * (t - 0.12 * np.sin(2 * np.pi * t))
    hb = np.array([Lm.hb(xp, z) for z in zs])
    hb[0] = L.k
    y = hb * Lm.ky + PLANK
    raw = y.copy()
    y = np.maximum.accumulate(y)
    z = zs * Lm.ky
    pts = np.vstack([[0.0, z[0]], np.stack([y, z], 1)])
    return pts, float(np.max(y - raw))


def hull_stations(Lm):
    L = Lm.L
    x0 = L.x_aft(loft.KNUCKLE) - 25.0             # a little of the counter, over the water
    x1 = L.x_fwd(L.sheer_z(L.x_fwd(0.0))) - 2.0
    out, clamp = [], 0.0
    for xp in np.linspace(x0, x1, N_STATIONS):
        pts, c = station(Lm, xp)
        clamp = max(clamp, c)
        out.append({"x": round(float(Lm.x_m(xp)), 4), "sheer": round(float(pts[-1, 1]), 4),
                    "half_section": [[round(float(a), 4), round(float(b), 4)] for a, b in pts]})
    return out, clamp


def _area_below(pts, z=0.0):
    """Area and centroid z of a half section below z by the physics' own sums (trapezoids under each segment)."""
    a = m = 0.0
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        z0c, z1c = min(z0 - z, 0.0), min(z1 - z, 0.0)
        seg = 0.5 * (-z0c - z1c) * (y1 - y0)
        a += seg
        m += seg * (z + 0.25 * (z0c + z1c))
    return a, (m / a if a > 0 else 0.0)


def _girth_below(pts, z=0.0):
    g = 0.0
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        if abs(z1 - z0) < 1e-9 and min(y0, y1) < 1e-9:
            continue
        if z0 >= z and z1 >= z:
            continue
        if z0 < z <= z1:
            t = (z - z0) / (z1 - z0)
            y1, z1 = y0 + t * (y1 - y0), z
        g += math.hypot(y1 - y0, z1 - z0)
    return g


def _hb_at(pts, z):
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        if z0 <= z <= z1 and z1 > z0:
            return y0 + (z - z0) / (z1 - z0) * (y1 - y0)
    return 0.0


def hydrostatics(stations):
    """Volume, centre of buoyancy, waterplane and wetted girth of the sections at the load line, as the physics sums."""
    xs = np.array([s["x"] for s in stations])
    A, Z, G, B = [], [], [], []
    for s in stations:
        p = np.array(s["half_section"])
        a, zc = _area_below(p)
        A.append(2 * a)
        Z.append(zc)
        G.append(2 * _girth_below(p))
        B.append(_hb_at(p, 0.0) if p[0, 1] < 0 else 0.0)
    A, Z, G, B = (np.array(v) for v in (A, Z, G, B))
    V = float(np.trapezoid(A, xs))
    lcb = float(np.trapezoid(A * xs, xs) / V)
    vcb = float(np.trapezoid(A * Z, xs) / V)
    awp = float(np.trapezoid(2 * B, xs))
    it = float(np.trapezoid(2.0 / 3.0 * B ** 3, xs))             # transverse second moment of the waterplane
    wl = xs[B > 0]
    return {"volume_m3": V, "lcb_m": lcb, "vcb_m": vcb, "waterplane_m2": awp, "bm_m": it / V, "km_m": vcb + it / V,
            "wetted_m2": float(np.trapezoid(G, xs)), "lwl_m": float(wl.max() - wl.min()), "wl_aft_m": float(wl.min()),
            "wl_fwd_m": float(wl.max()), "beam_wl_m": float(2 * B.max()), "max_beam_m": 2 * max(
                max(q[0] for q in s["half_section"]) for s in stations)}


def profile(Lm):
    """Her centreline profile under the water: the canoe body (rabbet up to the load line), the backbone below the
    rabbet (keel, deadwood, stem, post: the keel's siding wide) and the rudder; areas (m^2) and centres (x, z)."""
    L = Lm.L
    kb = np.array(L.P["keel_bottom_z_px"])
    post = np.array(L.P["sternpost_aft_face_px"])
    stem = np.array(L.P["stem_outer_px"])
    xa_post = float(post[:, 0][np.argmin(post[:, 1])])         # the post's foot (aft face)
    xs = np.linspace(xa_post, L.x_fwd(0.0), 4000)

    def keel_bottom(xp):
        if xp <= kb[0, 0]:
            return float(kb[0, 1])
        if xp >= kb[-1, 0]:
            # the stem's forefoot: its outer face's height at x
            o = stem[np.argsort(stem[:, 0])]
            return float(np.interp(xp, o[:, 0], o[:, 1]))
        return float(np.interp(xp, kb[:, 0], kb[:, 1]))

    canoe, back = [], []
    for xp in xs:
        zr = min(L.rabbet_z(xp), 0.0) if xp >= L.x_aft(0.0) else 0.0
        zk = min(keel_bottom(xp), zr)
        canoe.append((xp, zr))
        back.append((xp, zk, zr))
    # the post and stem beyond the rabbet's ends: from the rabbet's end out to the outer face (the backbone too)

    def strip(rows):
        a = cx = cz = 0.0
        for (x0, lo0, hi0), (x1, lo1, hi1) in zip(rows[:-1], rows[1:]):
            d = 0.5 * ((hi0 - lo0) + (hi1 - lo1)) * (x1 - x0)
            a += d
            cx += d * 0.5 * (x0 + x1)
            cz += d * 0.25 * (lo0 + hi0 + lo1 + hi1)
        return a, cx / a, cz / a

    a_c, cx_c, cz_c = strip([(x, z, 0.0) for x, z in canoe])
    a_b, cx_b, cz_b = strip(back)
    # the rudder: between the post's aft face and its own aft edge, from its foot to the load line
    ra = L.rudder_aft_edge                                       # [[x top, z top], [x bottom, z bottom]]
    zs = np.linspace(min(ra[1][1], post[:, 1].min()), 0.0, 400)
    pz = post[np.argsort(post[:, 1])]
    post_x = np.interp(zs, pz[:, 1], pz[:, 0])
    edge_x = np.interp(zs, [ra[1][1], ra[0][1]], [ra[1][0], ra[0][0]])
    chord = np.maximum(post_x - edge_x, 0.0)
    a_r = float(np.trapezoid(chord, zs))
    cx_r = float(np.trapezoid(chord * 0.5 * (post_x + edge_x), zs) / a_r)
    cz_r = float(np.trapezoid(chord * zs, zs) / a_r)
    kx2, ky = Lm.kx * Lm.ky, Lm.ky
    siding = 2 * L.k * ky
    draft = -min(kb[:, 1].min(), post[:, 1].min()) * ky
    return {"canoe": {"area_m2": a_c * kx2, "centre": [Lm.x_m(cx_c), cz_c * ky]},
            "backbone": {"area_m2": a_b * kx2, "centre": [Lm.x_m(cx_b), cz_b * ky], "siding_m": siding,
                         "volume_m3": a_b * kx2 * siding},
            "rudder": {"area_m2": a_r * kx2, "centre": [Lm.x_m(cx_r), cz_r * ky],
                       "chord_m": float(chord[zs < -1.0].mean() * Lm.kx), "span_m": float(-zs[0] * ky),
                       "stock_x_m": float(Lm.x_m(post_x.mean()))},
            "draft_m": draft}


def helmbold(ar):
    return 2.0 * math.pi * ar / (2.0 + math.sqrt(ar * ar + 4.0))


def rudder_as_flap(plane_area, plane_chord, keel_ar, blade_area, blade_chord, blade_ar, ar):
    """The rudder as the lateral plane's trailing-edge flap (Tools/shipkit/jclass/physics.py: thin-aerofoil theory,
    tau = 1 - (theta - sin theta) / pi with theta = acos(2E - 1), E the blade's share of the chord), as one foil at the
    blade of aspect ar giving the same lift per radian."""
    E = blade_chord / plane_chord
    theta = math.acos(2.0 * E - 1.0)
    tau = 1.0 - (theta - math.sin(theta)) / math.pi
    lift = plane_area * helmbold(keel_ar) * tau
    blade = blade_area * helmbold(blade_ar)
    return {"chord_share": E, "tau": tau, "lift_m2_per_rad": lift, "blade_m2_per_rad": blade,
            "blade_lift_share": min(1.0, blade / lift), "aspect_ratio": ar, "area_m2": lift / helmbold(ar)}


# ----------------------------------------------------------------------------------------------- weights and inertia

class Masses:
    """Point masses (kg, x, y, z) by part."""

    def __init__(self):
        self.parts = {}

    def add(self, part, kg, x, y, z):
        self.parts.setdefault(part, []).append((float(kg), float(x), float(y), float(z)))

    def line(self, part, kg, a, b, n=30, taper=1.0):
        a, b = np.asarray(a, float), np.asarray(b, float)
        t = (np.arange(n) + 0.5) / n
        w = 1.0 + (taper - 1.0) * t
        w = w / w.sum() * kg
        for ti, wi in zip(t, w):
            self.add(part, wi, *(a + ti * (b - a)))

    def total(self, part=None):
        rows = self.parts[part] if part else [r for v in self.parts.values() for r in v]
        m = np.array(rows)
        kg = m[:, 0].sum()
        return float(kg), (m[:, 0:1] * m[:, 1:]).sum(axis=0) / kg

    def scale(self, part, f):
        self.parts[part] = [(k * f, a, b, c) for k, a, b, c in self.parts[part]]

    def radii(self, cg):
        m = np.array([r for v in self.parts.values() for r in v])
        kg = m[:, 0].sum()
        d = m[:, 1:] - np.asarray(cg, float)
        ixx = float((m[:, 0] * (d[:, 1] ** 2 + d[:, 2] ** 2)).sum())
        iyy = float((m[:, 0] * (d[:, 0] ** 2 + d[:, 2] ** 2)).sum())
        izz = float((m[:, 0] * (d[:, 0] ** 2 + d[:, 1] ** 2)).sum())
        return [math.sqrt(i / kg) for i in (ixx, iyy, izz)]


def deck_band(M, part, kg, stations, z, inset=0.15, n_x=40):
    """kg spread over a deck at height z (m): across the hull's breadth there, along her length."""
    xs, hbs = [], []
    for s in stations:
        p = np.array(s["half_section"])
        if p[0, 1] < z < p[-1, 1]:
            xs.append(s["x"])
            hbs.append(max(_hb_at(p, z) - inset, 0.05))
    xs, hbs = np.array(xs), np.array(hbs)
    w = hbs / hbs.sum() * kg
    for x, h, wi in zip(xs, hbs, w):
        for f in (-0.75, -0.25, 0.25, 0.75):
            M.add(part, wi / 4, x, f * h, z)


def shell(M, part, kg, stations, z_top=None):
    """kg spread over the hull's sides and bottom (its girth), up to z_top (the sheer by default)."""
    pts = []
    for s in stations:
        p = np.array(s["half_section"])
        for (y0, z0), (y1, z1) in zip(p[:-1], p[1:]):
            if z_top is not None and z0 > z_top:
                continue
            ln = math.hypot(y1 - y0, z1 - z0)
            pts.append((ln, s["x"], 0.5 * (y0 + y1), 0.5 * (z0 + z1)))
    tot = sum(q[0] for q in pts)
    for ln, x, y, z in pts:
        for sgn in (-1, 1):
            M.add(part, kg * ln / tot / 2, x, sgn * y, z)


def weights(est, stations, hydro, rig, prof):
    """Her weight estimate part by part (physics_frigate.json 'weights'), each spread where it lies, the ballast made up
    so she weighs what her hull displaces in fresh water."""
    M = Masses()
    W = est["weights"]
    decks = W["deck_heights_m"]
    hull = W["hull_structure"]
    shell(M, "hull", hull["kg"] * hull["shell_share"], stations)
    for name, share in hull["deck_shares"].items():
        deck_band(M, "hull", hull["kg"] * share, stations, decks[name])
    # the guns at their ports: long guns on the gun deck, carronades and chase guns on the spar deck, along the side
    for g in W["guns"]["rows"]:
        xs = np.linspace(g["x_m"][0], g["x_m"][1], g["per_side"])
        z = decks[g["deck"]] + g["above_deck_m"]
        for x in xs:
            hb = max(_hb_at(np.array(min(stations, key=lambda s: abs(s["x"] - x))["half_section"]), z) - g["in_m"], 0.5)
            for sgn in (-1, 1):
                M.add("guns", g["kg_each"], x, sgn * hb, z)
    # stores, shot, powder, water, provisions: each in its hold or room
    for r in W["stores"]["rows"]:
        x0, x1 = r["x_m"]
        M.line("stores", r["kg"], (x0, 0.0, r["z_m"]), (x1, 0.0, r["z_m"]), n=20)
    # the masts, yards, rigging and sails: each mast up its length, the yards at their heights
    for name, r in W["rig"]["masts"].items():
        if not isinstance(r, dict): continue
        M.line("rig", r["kg"], (r["x_m"], 0, r["z_m"][0]), (r["x_m"], 0, r["z_m"][1]), n=40, taper=0.35)
    yards = [p for k, p in rig.items() if k.startswith("Yard_") and k != "Yard_Spritsail"]
    yl = sum(p["length_ft"] for p in yards)
    for p in yards:
        o = p["origin_m"]
        M.add("rig", W["rig"]["yards_kg"] * p["length_ft"] / yl, o[0], 0.0, o[2])
    sr = W["rig"]["standing_running_sails"]
    for x, z0, z1, share in sr["spread"]:
        M.line("rig", sr["kg"] * share, (x, 0, z0), (x, 0, z1), n=20)
    bs = W["rig"]["bowsprit"]
    M.line("rig", bs["kg"], bs["heel_m"], bs["end_m"], n=20, taper=0.4)
    for r in W["fittings"]["rows"]:
        M.add("fittings", r["kg"], *r["at_m"])
    # the crew (the physics takes them apart: CrewMass)
    crew = W["crew"]
    # the ballast: iron pigs and shingle along the hold's floor, made up to her displacement
    target = hydro["volume_m3"] * RHO_FRESH + prof["backbone"]["volume_m3"] * RHO_FRESH
    so_far = M.total()[0] + crew["count"] * crew["kg_each"]
    ballast = target - so_far
    b = W["ballast"]
    M.line("ballast", ballast, (b["x_m"][0], 0.0, b["z_m"]), (b["x_m"][1], 0.0, b["z_m"]), n=30)
    return M, ballast, target


# ----------------------------------------------------------------------------------------------------- the sails

def square_sails(rig, sails, est, limits=None):
    """Each square sail as the physics' FSquareSailDef (SquareRig.h), from the model's yards and cut. The brace limit is
    the yard's stop: limits.json's hard limit (the model thread's measure) when given, else rig.json's."""
    masts = {"fore": 0, "main": 1, "mizzen": 2}
    order = ["fore_course", "fore_topsail", "fore_topgallant", "fore_royal", "main_course", "main_topsail",
             "main_topgallant", "main_royal", "mizzen_topsail", "mizzen_topgallant", "mizzen_royal"]
    kinds = {"course": "Course", "topsail": "Topsail", "topgallant": "Topgallant", "royal": "Royal"}
    out = []
    offsets = est["sails"]["brace_offset_deg"]
    for key in order:
        s = sails[key]
        i = s["info"]
        y = rig[s["parent"]]
        head_z = y["origin_m"][2] + i["head_earing_local_m"][2]
        depth = i["depth_ft"] * FT
        lim = min(abs(s["brace_deg"][0]), abs(s["brace_deg"][1]))
        if limits and s["parent"] in limits["yards"]:
            lim = min(abs(v) for v in limits["yards"][s["parent"]]["hard_deg"])
        reefs = i.get("reefs") or []
        area = i["area_ft2"] * FT2
        # a reef takes in the share of the depth its band sits below the head: the sail left is the part under it,
        # narrower at the head than the foot (a topsail's head is about 0.55 of its foot), so a little more than that share
        hw, fw = i["head_ft"] * FT, i["foot_ft"] * FT

        def left(share):
            w = hw + share * (fw - hw)
            return (1.0 - share) * 0.5 * (w + fw) / (0.5 * (hw + fw))
        out.append({"name": key, "kind": kinds[i["kind"]], "mast": masts[key.split("_")[0]],
                    "pivot_x": round(y["origin_m"][0], 3),
                    "fore_offset": round(i["head_earing_local_m"][0] + 0.5 * i["belly_ft"] * FT, 3),
                    "foot_z": round(head_z - depth, 3), "head_z": round(head_z, 3),
                    "head_width": round(hw, 3), "foot_width": round(fw, 3), "area": round(area, 2),
                    "brace_limit_deg": lim, "brace_offset_deg": offsets.get(i["kind"], 0.0),
                    "sets_past_yard_deg": est["sails"]["sets_past_yard_deg"].get(i["kind"], 0.0),
                    "reef_area_fraction": [round(left(r), 4) for r in reefs]})
    return out


def fore_and_aft(sails, names):
    """Several fore-and-aft sails as one (the physics' jib or staysail): their area, the area-weighted heights of their
    feet and heads, and the luff's X at foot and head, foot chord from the area."""
    A = sum(sails[n]["info"]["area_ft2"] * FT2 for n in names)
    foot_z = sum(min(sails[n]["info"]["tack_m"][2], sails[n]["info"]["clew_m"][2]) * sails[n]["info"]["area_ft2"]
                 for n in names) * FT2 / A
    head_z = sum(sails[n]["info"]["head_m"][2] * sails[n]["info"]["area_ft2"] for n in names) * FT2 / A
    luff_x_foot = sum(sails[n]["info"]["tack_m"][0] * sails[n]["info"]["area_ft2"] for n in names) * FT2 / A
    luff_x_head = sum(sails[n]["info"]["head_m"][0] * sails[n]["info"]["area_ft2"] for n in names) * FT2 / A
    foot = 2.0 * A / (head_z - foot_z)                        # a triangle of that height and area
    return {"area": A, "foot_z": foot_z, "head_z": head_z, "luff_x_foot": luff_x_foot, "luff_x_head": luff_x_head,
            "foot_chord": foot, "sails": names}


# ----------------------------------------------------------------------------------------------------- output

def write_hull_inl(path, stations, hydro, prof):
    n = len(stations[0]["half_section"])
    with open(path, "w") as f:
        f.write("// Generated by Tools/shipkit/frigate/physics.py from the loft (loft.py, offsets.json): do not edit.\n")
        f.write("// The frigate Commonwealth's half sections, stern to stem: body frame metres (X forward from station 5,\n")
        f.write("// Y starboard, Z up from the load waterline), each from the keel's rabbet (Y 0) to the sheer, planking\n")
        f.write("// included, half breadths never decreasing (her tumblehome carried up vertical).\n")
        f.write(f"// Sections: volume {hydro['volume_m3']:.1f} m^3, centre of buoyancy x {hydro['lcb_m']:.3f} z {hydro['vcb_m']:.3f}.\n\n")
        f.write(f"constexpr int kCommonwealthStations = {len(stations)};\n")
        f.write(f"constexpr int kCommonwealthSectionPoints = {n};\n")
        bb = prof["backbone"]
        f.write("// The backbone below the rabbet (keel, deadwood, stem and post): fixed buoyancy (m^3; x, z).\n")
        f.write(f"constexpr double kCommonwealthKeelVolume = {bb['volume_m3']:.4f}; constexpr double kCommonwealthKeelX = "
                f"{bb['centre'][0]:.4f}; constexpr double kCommonwealthKeelZ = {bb['centre'][1]:.4f};\n\n")
        f.write("struct FCommonwealthSection { double X, Sheer; double Y[kCommonwealthSectionPoints], Z[kCommonwealthSectionPoints]; };\n")
        f.write("const FCommonwealthSection kCommonwealthSections[kCommonwealthStations] = {\n")
        for s in stations:
            ys = ", ".join(f"{p[0]:.4g}" for p in s["half_section"])
            zs = ", ".join(f"{p[1]:.4g}" for p in s["half_section"])
            f.write(f"\t{{ {s['x']:.4f}, {s['sheer']:.4f}, {{ {ys} }}, {{ {zs} }} }},\n")
        f.write("};\n")


def _num(v):
    return f"{v:.6g}"


def write_config_inl(path, sheet):
    h, c = sheet["hull"], sheet["config"]
    L = []
    w = L.append
    w("// Generated by Tools/shipkit/frigate/physics.py: the frigate Commonwealth's config from the sheet (physics.json).")
    w("static void ApplyCommonwealth(Sailing::FBoatConfig& C)")
    w("{")
    w("\tusing namespace Sailing;")
    w('\tC.Name = "Commonwealth";')
    w("\tFHullShape H;")
    w("\tfor (const FCommonwealthSection& M : kCommonwealthSections)")
    w("\t{")
    w("\t\tFHullShape::FStation St; St.X = M.X; St.Sheer = M.Sheer;")
    w("\t\tSt.Y.assign(M.Y, M.Y + kCommonwealthSectionPoints); St.Z.assign(M.Z, M.Z + kCommonwealthSectionPoints);")
    w("\t\tH.StationDepth = std::max(H.StationDepth, -M.Z[0]); H.Stations.push_back(St);")
    w("\t}")
    w("\tH.BowX = kCommonwealthSections[kCommonwealthStations - 1].X; H.SternX = kCommonwealthSections[0].X;")
    w(f"\tH.WaterlineMidX = {_num(h['wl_mid_x'])}; H.WaterlineHalfLength = {_num(h['wl_half'])};")
    w(f"\tH.MaxHalfBeam = {_num(h['max_half_beam'])}; H.MaxBeamX = {_num(h['max_beam_x'])}; H.AftLength = {_num(h['aft_length'])}; "
      f"H.TransomBeamLoss = {_num(h['transom_loss'])};")
    w(f"\tH.SheerZ = {_num(h['sheer_z'])}; H.SheerRise = {_num(h['sheer_rise'])}; H.SheerRiseFromX = 0.0;")
    w("\tC.Hulls = { H };")
    w(f"\tC.LengthOverall = {_num(c['loa'])}; C.WaterlineLength = {_num(c['lwl'])}; C.Beam = {_num(c['beam'])}; "
      f"C.WaterlineBeam = {_num(c['beam_wl'])}; C.Draft = {_num(c['draft'])};")
    w(f"\tC.Bowsprit = {_num(c['bowsprit'])};")
    w(f"\tC.TrimHeelLimitDeg = {_num(c['trim_heel_limit_deg'])}; C.TrimMaxEaseDeg = 25;")
    w(f"\tC.CrewMass = {_num(c['crew_kg'])}; C.CrewCount = {c['crew_count']}; C.CrewCG = Vec3({_num(c['crew_cg'][0])}, 0, {_num(c['crew_cg'][2])});")
    w("\tC.CrewSitOut = 0; C.CrewHikeOut = 0; C.CrewMoveSpeed = 0.5;")
    w(f"\tC.BallastMass = {_num(c['ballast_kg'])}; C.BallastCG = Vec3({_num(c['ballast_cg'][0])}, 0, {_num(c['ballast_cg'][2])});")
    w("\tC.AppendageVolume = kCommonwealthKeelVolume;")
    w("\tC.AppendageCentre = Vec3(kCommonwealthKeelX, 0.0, kCommonwealthKeelZ);")
    w(f"\tC.HullRigMass = {_num(c['hull_rig_kg'])}; C.HullRigCG = Vec3({_num(c['hull_rig_cg'][0])}, {_num(c['hull_rig_cg'][1])}, {_num(c['hull_rig_cg'][2])});")
    w(f"\tC.RadiiOfGyration = Vec3({_num(c['radii'][0])}, {_num(c['radii'][1])}, {_num(c['radii'][2])});")
    res = ", ".join(f"{{ {a:g}, {b:.6g} }}" for a, b in c["residuary"])
    w(f"\tC.Residuary = {{ {res} }};")
    w(f"\tC.WettedAreaCoef = {_num(c['wetted_coef'])}; C.FormFactor = {_num(c['form_factor'])};")
    w(f"\tC.AddedResistanceCoef = {_num(c['added_resistance'])};")
    w(f"\tC.HullLateralArea = {_num(c['hull_lateral'])}; C.MunkAddedMass = {_num(c['munk'])}; C.YawDampingLinear = {_num(c['yaw_damping'])}; "
      f"C.HeaveDamping = {_num(c['heave_damping'])}; C.WaveSlopeForceScale = {_num(c['wave_slope'])};")
    k, r = c["keel"], c["rudder"]
    w(f"\tFFoilDef Keel = Foil(EFoilRole::Keel, Vec3({_num(k['x'])}, 0.0, {_num(k['z'])}), {_num(k['area'])}, {_num(k['chord'])}, "
      f"{_num(k['ar'])}, {_num(k['stall'])});   // her whole lateral plane less the rudder")
    w(f"\tKeel.Params.ProfileDrag = {_num(k['profile_drag'])};")
    w(f"\tKeel.ContactLeadingX = {_num(k['contact'][1])}; Keel.ContactTrailingX = {_num(k['contact'][0])};")
    w(f"\tFFoilDef Rudder = Foil(EFoilRole::Rudder, Vec3({_num(r['x'])}, 0, {_num(r['z'])}), {_num(r['area'])}, {_num(r['chord'])}, "
      f"{_num(r['ar'])}, {_num(r['stall'])});   // the plane's flap (physics.json)")
    w(f"\tRudder.Params.ProfileDrag = {_num(r['profile_drag'])}; Rudder.VentStartDeg = 60; Rudder.VentEndDeg = 85; Rudder.VentDepth = 0.9;")
    w("\tKeel.VentStartDeg = 60; Keel.VentEndDeg = 85;")
    w("\tC.Foils = { Keel, Rudder };")
    w(f"\tC.KeelDownwashFactor = {_num(c['downwash'])}; C.HeelYawCoef = {_num(c['heel_yaw'])};")
    w(f"\tC.MaxRudderAngleDeg = {_num(c['max_rudder_deg'])}; C.RudderStockToCP = {_num(c['stock_to_cp'])}; C.TillerLength = 0.5; "
      f"C.HelmStiffness = 1e7; C.RudderResponseTime = 1.0;")
    w(f"\tC.WheelHardOverSeconds = {_num(c['wheel_hard_over_s'])};")
    w(f"\tC.MastX = {_num(c['mast_x'])}; C.MastheadZ = {_num(c['masthead_z'])}; C.MastDiameter = {_num(c['mast_diameter'])};")
    sp = c["spanker"]
    w(f"\tSetMain(C, {_num(sp['foot_z'])}, {_num(sp['head_z'])}, {_num(sp['foot_chord'])}, {_num(sp['head_chord'])}, 0.0, "
      f"{_num(sp['luff_x'])}, {_num(sp['luff_x'])}, {_num(sp['area'])}, {_num(sp['lift_slope'])}, {_num(sp['ar'])}, {_num(sp['camber'])});")
    w(f"\tC.BoomZ = {_num(sp['boom_z'])};")
    j = c["jib"]
    w(f"\tC.JibFootZ = {_num(j['foot_z'])}; C.JibHeadZ = {_num(j['head_z'])}; C.JibFootChord = {_num(j['foot_chord'])}; C.JibHeadChord = 0.3; "
      f"C.JibLuffX = {_num(j['luff_x_foot'])}; C.JibLuffXHead = {_num(j['luff_x_head'])}; C.JibArea = {_num(j['area'])};")
    w(f"\tSetSail(C.Jib, C.JibFootZ, C.JibHeadZ, C.JibFootChord, C.JibHeadChord, C.JibLuffX, C.JibLuffXHead, C.JibArea, "
      f"{_num(j['lift_slope'])}, {_num(j['ar'])}, {_num(j['camber'])});")
    s = c["staysail"]
    w(f"\tSetSail(C.Staysail, {_num(s['foot_z'])}, {_num(s['head_z'])}, {_num(s['foot_chord'])}, 0.3, {_num(s['luff_x_foot'])}, "
      f"{_num(s['luff_x_head'])}, {_num(s['area'])}, {_num(s['lift_slope'])}, {_num(s['ar'])}, {_num(s['camber'])});")
    w(f"\tC.StaysailMinAngleDeg = {_num(s['min_deg'])}; C.StaysailMaxAngleDeg = {_num(s['max_deg'])};")
    w("\tC.Spinnaker = FSailGeometry(); C.Spinnaker.NumStrips = 0;")
    w(f"\tC.MainMaxEaseDeg = {_num(sp['max_ease_deg'])}; C.TravelerRangeDeg = 0; C.JibMinAngleDeg = {_num(j['min_deg'])}; C.JibMaxAngleDeg = {_num(j['max_deg'])};")
    w(f"\tC.RigWindageCdA = {_num(c['rig_windage'])}; C.HullWindageCdA = {_num(c['hull_windage'])};")
    w("\tC.ReefLuffFraction.clear(); C.ReefJibFraction.clear();")
    w("\tC.Engines.clear();")
    q = c["square"]
    w("\tFSquareRig& R = C.Square;")
    w(f"\tR.NumMasts = 3; R.MastX[0] = {_num(q['mast_x'][0])}; R.MastX[1] = {_num(q['mast_x'][1])}; R.MastX[2] = {_num(q['mast_x'][2])};")
    for key, attr in (("camber", "Camber"), ("aspect_ratio", "AspectRatio"), ("induced_ar", "InducedAspectRatio"),
                      ("luff_deg", "LuffDeg"), ("running_cd", "RunningCD"), ("backed_lift", "BackedLiftShare"),
                      ("backed_drag", "BackedDragShare"), ("clewed_cda", "ClewedCdAShare"), ("blanket", "BlanketShare"),
                      ("downwash_deg", "DownwashDegPerMast"), ("brace_rate", "BraceDegPerSecond"),
                      ("set_s", "SetSeconds"), ("clew_s", "ClewSeconds"), ("furl_s", "FurlSeconds")):
        w(f"\tR.{attr} = {_num(q[key])};")
    w("\tR.Sails.clear();")
    for s in q["sails"]:
        reefs = ", ".join(_num(v) for v in s["reef_area_fraction"])
        w(f"\t{{ FSquareSailDef S; S.Kind = ESquareSailKind::{s['kind']}; S.Mast = {s['mast']}; S.PivotX = {_num(s['pivot_x'])}; "
          f"S.ForeOffset = {_num(s['fore_offset'])}; S.FootZ = {_num(s['foot_z'])}; S.HeadZ = {_num(s['head_z'])}; "
          f"S.HeadWidth = {_num(s['head_width'])}; S.FootWidth = {_num(s['foot_width'])}; S.Area = {_num(s['area'])}; "
          f"S.BraceLimitDeg = {_num(s['brace_limit_deg'])}; S.BraceOffsetDeg = {_num(s['brace_offset_deg'])}; "
          f"S.SetsPastYardDeg = {_num(s['sets_past_yard_deg'])}; "
          f"S.ReefAreaFraction = {{ {reefs} }}; R.Sails.push_back(S); }}   // {s['name']}")
    w("}")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def main(build, out, limits_path=None, source=False):
    est = json.load(open(os.path.join(HERE, "physics_frigate.json")))
    limits = json.load(open(limits_path)) if limits_path else None
    rig = json.load(open(os.path.join(build, "rig.json")))["parts"]
    sails = json.load(open(os.path.join(build, "sails.json")))["sails"]
    Lm = Lines()
    stations, clamp = hull_stations(Lm)
    hydro = hydrostatics(stations)
    prof = profile(Lm)
    M, ballast, target = weights(est, stations, hydro, rig, prof)
    crew = est["weights"]["crew"]
    crew_kg = crew["count"] * crew["kg_each"]
    crew_cg = crew["cg_m"]
    kg_all, cg_all = M.total()
    # the whole ship's centre with the crew in it
    tot = kg_all + crew_kg
    cg = (cg_all * kg_all + np.array(crew_cg) * crew_kg) / tot
    M.add("crew", crew_kg, *crew_cg)
    radii = M.radii(cg)
    M.parts.pop("crew")
    gm = hydro["km_m"] - cg[2]
    # the physics' three masses: ballast, crew, the rest
    kb, cb = M.total("ballast")
    rest = {k: v for k, v in M.parts.items() if k != "ballast"}
    R = Masses()
    R.parts = rest
    kr, cr = R.total()

    # foils
    K = est["foils"]
    plane_area = prof["canoe"]["area_m2"] + prof["backbone"]["area_m2"]
    keel_area = plane_area
    kx = (prof["canoe"]["area_m2"] * prof["canoe"]["centre"][0] + prof["backbone"]["area_m2"] * prof["backbone"]["centre"][0]) / plane_area
    kz = (prof["canoe"]["area_m2"] * prof["canoe"]["centre"][1] + prof["backbone"]["area_m2"] * prof["backbone"]["centre"][1]) / plane_area
    draft = prof["draft_m"]
    plane_chord = keel_area / draft
    rud = prof["rudder"]
    flap = rudder_as_flap(keel_area + rud["area_m2"], plane_chord, K["keel_ar"], rud["area_m2"], rud["chord_m"],
                          K["blade_ar"], K["rudder_ar"])
    stock_to_cp = 0.33 * rud["chord_m"] * flap["blade_lift_share"]

    # hull summary for FHullShape's stand-in fit
    xs = np.array([s["x"] for s in stations])
    hbmax = np.array([max(p[0] for p in s["half_section"]) for s in stations])
    i_max = int(np.argmax(hbmax))
    sheer = np.array([s["sheer"] for s in stations])
    lwl = hydro["lwl_m"]
    vol = hydro["volume_m3"]
    wet = hydro["wetted_m2"]

    q = est["sails"]
    sq = square_sails(rig, sails, est, limits)
    jib = fore_and_aft(sails, ["fore_topmast_staysail", "jib", "flying_jib"])
    stay = fore_and_aft(sails, ["main_staysail", "main_topmast_staysail", "main_topgallant_staysail", "mizzen_staysail",
                                "mizzen_topmast_staysail"])
    sp_i = sails["spanker"]["info"]
    boom, gaff = rig["SpankerBoom"], rig["SpankerGaff"]
    spanker = {"area": sp_i["area_ft2"] * FT2, "foot_z": boom["origin_m"][2] + 0.3, "head_z": gaff["origin_m"][2] + 3.0,
               "foot_chord": sp_i["foot_ft"] * FT, "head_chord": sp_i["head_ft"] * FT, "luff_x": boom["origin_m"][0],
               "boom_z": boom["origin_m"][2], "max_ease_deg": abs(boom["brace_deg"][0]), **q["spanker"]}
    if limits and "SpankerBoom" in limits["yards"]:
        spanker["max_ease_deg"] = min(abs(v) for v in limits["yards"]["SpankerBoom"]["hard_deg"])
    masts = est["weights"]["rig"]["masts"]
    mast_x = [masts["fore"]["x_m"], masts["main"]["x_m"], masts["mizzen"]["x_m"]]

    config = {
        "loa": round(float(rig["Yard_Spritsail"]["origin_m"][0] - stations[0]["x"]), 3),
        "lwl": round(lwl, 3), "beam": round(hydro["max_beam_m"], 3), "beam_wl": round(hydro["beam_wl_m"], 3),
        "draft": round(draft, 3), "bowsprit": 0.0,
        "trim_heel_limit_deg": K["trim_heel_limit_deg"],
        "crew_kg": crew_kg, "crew_count": crew["count"], "crew_cg": crew_cg,
        "ballast_kg": round(kb, 1), "ballast_cg": [round(float(v), 3) for v in cb],
        "hull_rig_kg": round(kr, 1), "hull_rig_cg": [round(float(v), 3) for v in cr],
        "radii": [round(v, 3) for v in radii],
        "residuary": K["residuary"],
        "wetted_coef": round(wet / math.sqrt(vol * lwl), 4), "form_factor": K["form_factor"],
        "added_resistance": K["added_resistance"],
        "hull_lateral": round(K["hull_lateral_share"] * keel_area, 2), "munk": K["munk"], "yaw_damping": K["yaw_damping"],
        "heave_damping": K["heave_damping"], "wave_slope": K.get("wave_slope", 1.0),
        "keel": {"x": round(kx, 3), "z": round(kz, 3), "area": round(keel_area, 2), "chord": round(plane_chord, 2),
                 "ar": K["keel_ar"], "stall": K["keel_stall_deg"], "profile_drag": K["keel_profile_drag"],
                 "contact": [round(float(xs[0]) + 4.0, 2), round(float(stations[-1]["x"]) - 6.0, 2)]},
        "rudder": {"x": round(rud["centre"][0], 3), "z": round(rud["centre"][1], 3), "area": round(flap["area_m2"], 2),
                   "chord": round(rud["chord_m"], 3), "ar": K["rudder_ar"], "stall": K["rudder_stall_deg"],
                   "profile_drag": K["rudder_profile_drag"]},
        "downwash": K["downwash"], "heel_yaw": K["heel_yaw"], "max_rudder_deg": K["max_rudder_deg"],
        "stock_to_cp": round(stock_to_cp, 4), "wheel_hard_over_s": K["wheel_hard_over_s"],
        "mast_x": mast_x[1], "masthead_z": round(rig["Yard_MainRoyal"]["origin_m"][2] + 3.0, 2), "mast_diameter": 0.9,
        "spanker": spanker, "jib": {**jib, **q["jib"]}, "staysail": {**stay, **q["staysail"]},
        "rig_windage": q["rig_windage_cda"], "hull_windage": q["hull_windage_cda"],
        "square": {**q["square"], "mast_x": mast_x, "sails": sq},
    }
    hull = {"wl_mid_x": round(0.5 * (hydro["wl_aft_m"] + hydro["wl_fwd_m"]), 4), "wl_half": round(0.5 * lwl, 4),
            "max_half_beam": round(float(hbmax[i_max]), 4), "max_beam_x": round(float(xs[i_max]), 4),
            "aft_length": round(float(xs[i_max] - xs[0]), 4), "transom_loss": round(float(hbmax[i_max] - hbmax[0]), 4),
            "sheer_z": round(float(sheer.min()), 4), "sheer_rise": round(float(sheer.max() - sheer.min()), 4)}
    period = 2 * math.pi * radii[0] / math.sqrt(9.81 * max(gm, 0.05))
    sheet = {
        "about": "the frigate Commonwealth as a ship for the game's physics (docs/frigate-physics), from "
                 "Tools/shipkit/frigate/physics.py: measured on the lines and the build, or estimated in physics_frigate.json",
        "build": os.path.abspath(build),
        "hull": hull,
        "hydrostatics": {k: round(v, 4) for k, v in hydro.items()},
        "tumblehome_added_m": round(clamp, 4),
        "profile": prof,
        "rudder_flap": {k: round(v, 4) for k, v in flap.items()},
        "weights": {"target_kg": round(target, 1), "ballast_kg": round(ballast, 1),
                    "parts": {k: round(M.total(k)[0], 1) for k in M.parts},
                    "crew_kg": crew_kg, "cg_m": [round(float(v), 3) for v in cg], "gm_m": round(gm, 3),
                    "roll_period_s": round(period, 2), "radii_m": [round(v, 3) for v in radii]},
        "sail_area_m2": {"square": round(sum(s["area"] for s in sq), 1), "headsails": round(jib["area"], 1),
                         "staysails": round(stay["area"], 1), "spanker": round(spanker["area"], 1)},
        "config": config,
    }
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "physics.json"), "w") as f:
        json.dump(sheet, f, indent=1)
    write_hull_inl(os.path.join(out, "CommonwealthHullData.inl"), stations, hydro, prof)
    sheet["hull"] = hull
    write_config_inl(os.path.join(out, "commonwealth_trial.inl"), sheet)
    if source:
        # The game's copies (Fleet.cpp includes them for EBoatType::Commonwealth): the same two files.
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "Source", "SailingPhysics", "Private")
        write_hull_inl(os.path.join(here, "CommonwealthHullData.inl"), stations, hydro, prof)
        write_config_inl(os.path.join(here, "CommonwealthConfig.inl"), sheet)
    print(json.dumps({"hydrostatics": sheet["hydrostatics"], "weights": sheet["weights"], "profile": prof,
                      "flap": sheet["rudder_flap"], "sails": sheet["sail_area_m2"], "tumblehome_added_m": clamp}, indent=1))


if __name__ == "__main__":
    # physics.py <build dir> [out dir] [--limits <limits.json>] [--source]
    # (--source also writes the game's copies into Source/SailingPhysics/Private.)
    args = sys.argv[1:]
    source = "--source" in args
    if source:
        args.remove("--source")
    lim_path = None
    if "--limits" in args:
        k = args.index("--limits")
        lim_path = args[k + 1]
        del args[k:k + 2]
    main(args[0], args[1] if len(args) > 1 else args[0], lim_path, source)
