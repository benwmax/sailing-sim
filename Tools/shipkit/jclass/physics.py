"""Bluebonnet as a boat for the game's physics (slice 13, the cloud half; docs/jclass-13).

    python physics.py <build dir>

Reads the build's build.json (every slice's measured weights and its rig and sails) and the lines (loft.py), and
writes into the build dir:

  physics.json            the sheet: everything FBoatConfig needs for her, each number with where it comes from, and
                          which numbers are measured on the model and which are starting points for the Mac's tuning
  BluebonnetHullData.inl  her hull's half sections as the physics reads them (the maxi's MaxiHullData.inl's form)
  bluebonnet_trial.inl    a config body built from the sheet, for trial/trial_sail.cpp (the standalone physics)

Nothing is written into Source/: the game's wiring is slice 13's Mac half, after the vertical slice ships. Pure Python
(numpy and scipy, through loft.py), no Blender.

The physics floats a hull drawn by its stations (FHullShape::Stations: half sections from the centreline to the sheer)
on a grid of columns 26 long by 12 across, and adds the fixed appendages' own buoyancy at their centre
(FBoatConfig::AppendageVolume). A J's keel is part of her hull surface, a few tenths of a metre thick under a hull
6.5 m wide, so the columns would miss most of it: her stations are the canoe body, cut flat along the canoe line (the
canoe body's centreline, lines_bluebonnet.json's canoe_bottom, below which the keel hangs: loft.hydrostatics' own
split), and the keel and rudder under it are the appendage, their volume and centre measured from the same sections.
The physics' water is fresh (1,000 kg/m^3: SailingMath.h), so she weighs what her hull displaces in it, and every
part of her weight budget is scaled by the same share, which keeps her centre of gravity and radii of gyration.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402

LT_KG = 1016.047
RHO_FRESH = 1000.0
N_STATIONS = 31
N_POINTS = 24


# ----------------------------------------------------------------------------------------------------- the hull

def _resample(p, n):
    """n points evenly along the polyline p (k, 2), its ends kept."""
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)


def canoe_section(sec, zc, n=N_POINTS):
    """The half section `sec` (keel to sheer) with the keel cut off flat at the canoe line's height zc: from the
    centreline at zc out to where the section crosses it, then up the hull to the sheer, n points in all (the corner
    kept). Where no keel hangs below zc the section is kept whole, from the centreline at its lowest point."""
    p = np.asarray(sec, float)
    if p[0, 1] >= zc:
        pts = _resample(p, n)                             # no keel here: the section from its own foot
    else:
        k = int(np.nonzero(p[:, 1] >= zc)[0][0])          # sections never fold back (loft.control_net): one crossing
        t = (zc - p[k - 1, 1]) / (p[k, 1] - p[k - 1, 1])
        yc = float(p[k - 1, 0] + t * (p[k, 0] - p[k - 1, 0]))
        pts = np.vstack([[(0.0, zc)], _resample(np.vstack([[yc, zc], p[k:]]), n - 1)])
    raw = pts[:, 0].copy()
    pts[:, 0] = np.maximum.accumulate(pts[:, 0])          # the physics wants half breadths never decreasing
    return pts, float(np.max(pts[:, 0] - raw))


def _girth_below(pts, z=0.0, skip_flat=True):
    """The section's girth below height z (m), leaving out the flat cut along the canoe line."""
    g = 0.0
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        if skip_flat and abs(z1 - z0) < 1e-9 and min(y0, y1) < 1e-9:
            continue
        if z0 >= z and z1 >= z:
            continue
        if z0 < z <= z1:                                  # up through z: keep the part below, from the start
            t = (z - z0) / (z1 - z0)
            y1, z1 = y0 + t * (y1 - y0), z
        elif z1 < z <= z0:                                # down through z: keep the part below, to the end
            t = (z - z0) / (z1 - z0)
            y0, z0 = y0 + t * (y1 - y0), z
        g += math.hypot(y1 - y0, z1 - z0)
    return g


def _area_below(pts, z=0.0):
    """Area and centroid z of a half section below z by the physics' own sums (Tools/boats/maxi/make_maxi_hull.py's
    trapezoids under each segment)."""
    a = m = 0.0
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        z0c, z1c = min(z0 - z, 0.0), min(z1 - z, 0.0)
        seg = 0.5 * (-z0c - z1c) * (y1 - y0)
        a += seg
        m += seg * (z + 0.25 * (z0c + z1c))
    return a, (m / a if a > 0 else 0.0)


def hull_sections(S):
    """The canoe body's half sections at N_STATIONS stations from the transom's foot to the stem, and what they hold."""
    x_lo, x_hi = loft.END["transom_bottom"][0] + 0.05, float(S[..., 0].max()) - 0.05
    out, clamp = [], 0.0
    for x in np.linspace(x_lo, x_hi, N_STATIONS):
        sec = loft.station_cut(S, x)
        if not sec:
            continue
        pts, c = canoe_section(sec, float(loft.CANOE(x)))
        clamp = max(clamp, c)
        out.append({"x": round(float(x), 4), "sheer": round(float(pts[-1, 1]), 4),
                    "half_section": [[round(float(y), 4), round(float(z), 4)] for y, z in pts]})
    return out, clamp


def sections_volume(stations):
    """Volume, centre (x, z) and wetted girth area below the DWL of the sections, as the physics would sum them."""
    xs = np.array([s["x"] for s in stations])
    A, Z, G = [], [], []
    for s in stations:
        p = np.array(s["half_section"])
        a, zc = _area_below(p)
        A.append(2 * a)
        Z.append(zc)
        G.append(2 * _girth_below(p))
    A, Z, G = np.array(A), np.array(Z), np.array(G)
    V = float(np.trapezoid(A, xs))
    return V, float(np.trapezoid(A * xs, xs) / V), float(np.trapezoid(A * Z, xs) / V), float(np.trapezoid(G, xs))


def canoe_lateral(stations):
    """The canoe body's lateral profile below the DWL (down to the canoe line on the centreline): area and centre."""
    xs = np.array([s["x"] for s in stations])
    d = np.array([max(0.0, -s["half_section"][0][1]) for s in stations])
    a = float(np.trapezoid(d, xs))
    return a, (float(np.trapezoid(d * xs, xs) / a), float(np.trapezoid(-0.5 * d * d, xs) / a))


def keel_appendage(S, n=600):
    """The keel and rudder below the canoe line and the water: volume, centre and lateral profile, from the hull's own
    sections (loft.hydrostatics splits her the same way)."""
    x_lo, x_hi = float(S[..., 0].min()) + 1e-3, float(S[..., 0].max()) - 1e-3
    xs = np.linspace(x_lo, x_hi, n)
    A, Z, D, B = [], [], [], []
    for x in xs:
        sec = loft.station_cut(S, x)
        zc = min(float(loft.CANOE(x)), 0.0)
        if not sec:
            for lst, v in ((A, 0.0), (Z, 0.0), (D, 0.0), (B, zc)):
                lst.append(v)
            continue
        a, _, cz = loft._clip_area_below(sec, zc)
        A.append(2 * a)
        Z.append(cz)
        zb = float(sec[0][1])
        D.append(max(0.0, zc - zb))                      # the keel's depth below the canoe line here
        B.append(zb)
    A, Z, D = np.array(A), np.array(Z), np.array(D)
    V = float(np.trapezoid(A, xs))
    lat = float(np.trapezoid(D, xs))
    zmid = np.array([min(float(loft.CANOE(x)), 0.0) for x in xs]) - 0.5 * D
    return {"volume_m3": V, "centre": [float(np.trapezoid(A * xs, xs) / V), float(np.trapezoid(A * Z, xs) / V)],
            "lateral_m2": lat, "lateral_centre": [float(np.trapezoid(D * xs, xs) / lat),
                                                  float(np.trapezoid(D * zmid, xs) / lat)],
            "xs": xs, "depth": D}


def helmbold(ar):
    """A finite wing's lift slope per radian (Helmbold; FFoilParams::LiftSlope)."""
    return 2.0 * math.pi * ar / (2.0 + math.sqrt(ar * ar + 4.0))


def flapped_band(head_z, n=20001):
    """The part of her lateral plane the rudder spans: below the rudder's head, down to the keel's bottom (loft.profile,
    the centreline's lowest point; the rudder's own profile included, it is the band's after end). Area, depth and the
    mean chord (area over depth)."""
    xs = np.linspace(loft.END["transom_bottom"][0], loft.END["stem_head"][0], n)
    zb = loft.profile(xs)
    area = float(np.trapezoid(np.maximum(0.0, head_z - zb), xs))
    depth = float(head_z - zb.min())
    return {"head_z": head_z, "area_m2": area, "depth_m": depth, "chord_m": area / depth}


def rudder_as_flap(band, keel_ar, blade_area, blade_chord, blade_ar, ar):
    """The rudder as the keel's trailing-edge flap, as one foil at the blade (FFoilDef has no flaps). Turning a flap
    turns the flow over the foil ahead of it: thin-aerofoil theory gives the lift per radian of flap as the foil's
    own lift slope times tau = 1 - (theta - sin theta) / pi, theta = acos(2E - 1), E the flap's share of the chord
    (Abbott and von Doenhoff, Theory of Wing Sections, 8.4); tau counts the flap's own load too. The blade spans only
    the deep part of her lateral plane (flapped_band: below its head), so that band is the foil it flaps, E is the
    blade's chord over the band's mean chord, and the slope is the whole plane's (`keel_ar`). On a foil as slender as
    a J's lateral plane that lift is made where the flap is (slender-body theory: the lift grows where the incidence
    changes along the chord), so it is put at the blade as one foil of aspect `ar` (an end-plated flap) whose area
    gives the same lift per radian. This is thin-aerofoil theory's value; a low aspect ratio raises a flap's
    effectiveness above it (USAF DATCOM's 3D flap factor), so the trial checks she can be steered with it.
    The blade's own lift (its area at its own aspect, `blade_ar`) is its share of that load, which sets the wheel's
    hinge moment (physics.py scales RudderStockToCP by it)."""
    E = blade_chord / band["chord_m"]
    theta = math.acos(2.0 * E - 1.0)
    tau = 1.0 - (theta - math.sin(theta)) / math.pi
    lift = band["area_m2"] * helmbold(keel_ar) * tau
    blade = blade_area * helmbold(blade_ar)
    return {"band_area_m2": band["area_m2"], "band_depth_m": band["depth_m"], "band_chord_m": band["chord_m"],
            "chord_share": E, "tau": tau, "lift_m2_per_rad": lift, "blade_m2_per_rad": blade,
            "blade_lift_share": min(1.0, blade / lift), "aspect_ratio": ar, "area_m2": lift / helmbold(ar)}


def _shoelace(poly):
    p = np.asarray(poly, float)
    x, z = p[:, 0], p[:, 1]
    c = x * np.roll(z, -1) - np.roll(x, -1) * z
    a = 0.5 * c.sum()
    return abs(a), float(((x + np.roll(x, -1)) * c).sum() / (6 * a)), float(((z + np.roll(z, -1)) * c).sum() / (6 * a))


def rudder_profile(finish):
    """The rudder's side profile: between its stock line and the keel's after edge (the post, its trailing edge), from
    the keel's bottom up to its head (slice 2's finish report)."""
    st = finish["rudder"]["stock_line"]
    (sx, sz), k = st["through"], st["dz_dx"]
    (px, pz), (px1, pz1) = loft.KEEL["post"]
    head_from, head_to = finish["rudder"]["head_from"], finish["rudder"]["head_to"]
    poly = [(sx, sz), (px, pz), tuple(head_to), tuple(head_from)]
    a, cx, cz = _shoelace(poly)
    span = head_from[1] - sz
    stock_to_centre = abs(k * (cx - sx) - (cz - sz)) / math.hypot(1.0, k)    # the centre's distance from the stock line
    return {"polygon": [[round(float(u), 3), round(float(v), 3)] for u, v in poly], "area_m2": a, "centre": [cx, cz],
            "span_m": span, "chord_m": loft.KEEL["rudder_chord"], "built_area_m2": finish["rudder"]["area_m2"],
            "stock_to_centre_m": stock_to_centre}


# ----------------------------------------------------------------------------------------------- weights and inertia

class Masses:
    """Point masses (kg, x, y, z) gathered part by part; each part can be moved as a whole onto the weight check's
    centre for it, keeping its own spread (what the radii of gyration need)."""

    def __init__(self):
        self.parts = {}

    def add(self, part, kg, x, y, z):
        self.parts.setdefault(part, []).append((float(kg), float(x), float(y), float(z)))

    def line(self, part, kg, a, b, n=40, taper=1.0):
        """kg spread along the segment a-b, the mass per metre falling linearly to `taper` times its foot's at b."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        t = (np.arange(n) + 0.5) / n
        w = 1.0 + (taper - 1.0) * t
        w = w / w.sum() * kg
        for ti, wi in zip(t, w):
            p = a + ti * (b - a)
            self.add(part, wi, *p)

    def path(self, part, kg, pts, step=0.5):
        pts = np.asarray(pts, float)
        segs = list(zip(pts[:-1], pts[1:]))
        L = sum(float(np.linalg.norm(q - p)) for p, q in segs)
        for p, q in segs:
            ln = float(np.linalg.norm(q - p))
            self.line(part, kg * ln / L, p, q, n=max(1, int(ln / step)))

    def triangle(self, part, kg, a, b, c, n=12):
        a, b, c = (np.asarray(v, float) for v in (a, b, c))
        pts = []
        for i in range(n):
            for j in range(n - i):
                u, v = (i + 1 / 3) / n, (j + 1 / 3) / n
                pts.append(a + u * (b - a) + v * (c - a))
                if i + j < n - 1:
                    u2, v2 = (i + 2 / 3) / n, (j + 2 / 3) / n
                    pts.append(a + u2 * (b - a) + v2 * (c - a))
        for p in pts:
            self.add(part, kg / len(pts), *p)

    def total(self, part=None):
        rows = self.parts[part] if part else [r for v in self.parts.values() for r in v]
        m = np.array(rows)
        kg = m[:, 0].sum()
        return kg, (m[:, 0:1] * m[:, 1:]).sum(axis=0) / kg

    def move_to(self, part, x, z):
        kg, c = self.total(part)
        dx, dz = x - c[0], z - c[2]
        self.parts[part] = [(k, a + dx, b, d + dz) for k, a, b, d in self.parts[part]]
        return dx, dz

    def radii(self, cg):
        m = np.array([r for v in self.parts.values() for r in v])
        kg = m[:, 0].sum()
        d = m[:, 1:] - np.asarray(cg, float)
        ixx = float((m[:, 0] * (d[:, 1] ** 2 + d[:, 2] ** 2)).sum())
        iyy = float((m[:, 0] * (d[:, 0] ** 2 + d[:, 2] ** 2)).sum())
        izz = float((m[:, 0] * (d[:, 0] ** 2 + d[:, 1] ** 2)).sum())
        return [math.sqrt(i / kg) for i in (ixx, iyy, izz)], [ixx, iyy, izz]


def _rows(d):
    """Weight rows as (name, kg, centre) from a report's rows (a list of dicts or a dict of dicts)."""
    if isinstance(d, dict):
        return [(k, v["kg"], v["centre"]) for k, v in d.items()]
    return [(r["part"], r["kg"], r["centre"]) for r in d]


def sail_corners(b):
    """The main's and the genoa's corners as set in the centreline plane (x, z), from the rig and sails reports and
    sails_bluebonnet.json: the main's luff on the mast's track (raked with the mast), the genoa's on the forestay."""
    sj = json.load(open(os.path.join(HERE, "sails_bluebonnet.json")))
    rig, sails = b["rig"], b["sails"]["sails"]
    ms = sj["mainsail"]
    mast = rig["mast"]
    rake = math.radians(mast["rake_deg"])
    t0 = np.array(rig["measure_points"]["boom_top_at_mast_after_face"], float)[[0, 2]]
    tack = t0 + np.array([-ms["luff_off"], ms["foot_off"]])
    luff = sails["Mainsail"]["head_y_m"]
    head = tack + luff * np.array([-math.sin(rake), math.cos(rake)])
    clew = tack + sails["Mainsail"]["foot_m"] * np.array([-math.cos(math.radians(1.0)), math.sin(math.radians(1.0))])
    fs = next(w for w in b["rigging"]["wires"] if w["key"] == "forestay")
    lo, hi = np.array(fs["path"][-1], float)[[0, 2]], np.array(fs["path"][0], float)[[0, 2]]
    u = (hi - lo) / np.linalg.norm(hi - lo)
    g = sj["headsails"]["genoa"]
    gt = lo + g["tack_up"] * u
    gh = hi - g["head_below"] * u
    deck_z = float(loft.SHEER(g["clew"][0])) + 0.12            # the deck's crown on the centreline over the sheer
    gc = np.array([g["clew"][0], deck_z + g["clew"][1]])
    return {"main": {"tack": tack, "head": head, "clew": clew, "area": sails["Mainsail"]["area_m2"],
                     "roach_m2": sails["Mainsail"]["roach_m2"], "headboard": ms["headboard"],
                     "luff": luff, "foot": sails["Mainsail"]["foot_m"], "kg": sails["Mainsail"]["total_kg"]},
            "genoa": {"tack": gt, "head": gh, "clew": gc, "area": sails["Genoa"]["area_m2"],
                      "kg": sails["Genoa"]["total_kg"], "foot": sails["Genoa"]["foot_m"], "lp": sails["Genoa"]["lp_m"],
                      "luff": sails["Genoa"]["luff_m"]}}


def weights(b, S, corners, crew_count, crew_kg):
    """Every part of her weight budget as point masses, each part on the weight check's own centre (so she floats on
    her lines as the build checked her), with the sails she sails under set (the weight check keeps them all below)."""
    M = Masses()
    w = b["weights"]
    lead = w["lead"]
    # the lead: the casting fills the keel below its top; the trimming ballast is a block in the bilge
    zt = lead["top_z_m"]
    cast_kg = lead["casting_long_tons"] * LT_KG
    xs = np.linspace(float(S[..., 0].min()) + 1e-3, float(S[..., 0].max()) - 1e-3, 300)
    cells = []
    for x in xs:
        sec = loft.station_cut(S, x)
        if not sec or sec[0][1] >= zt:
            continue
        for z in np.arange(sec[0][1] + 0.025, zt, 0.05):
            hb = loft._half_breadth_at(sec, z)
            if hb > 0:
                cells.append((2 * hb, x, z, hb))
    tot = sum(c[0] for c in cells)
    for a, x, z, hb in cells:
        # each cell a thin slab 2 hb wide: put its mass at y = +-hb / sqrt(3), which holds its own sum of y^2
        for s in (-1, 1):
            M.add("lead_keel", cast_kg * a / tot / 2, x, s * hb / math.sqrt(3), z)
    tb = lead["trim_ballast_centre"]
    M.add("lead_keel", lead["trim_ballast_long_tons"] * LT_KG, tb[0], 0.0, tb[1])
    # the hull's steel and frames (the card's estimate): spread over the shell's surface, both sides
    q = S
    d1 = q[1:, 1:] - q[:-1, :-1]
    d2 = q[1:, :-1] - q[:-1, 1:]
    qa = 0.5 * np.linalg.norm(np.cross(d1, d2), axis=-1)
    qc = 0.25 * (q[1:, 1:] + q[:-1, :-1] + q[1:, :-1] + q[:-1, 1:])
    steel = loft.SPECS["weights"]["hull_steel_and_frames"] * LT_KG
    sel = qa.ravel() > 0
    A = qa.ravel()[sel]
    C = qc.reshape(-1, 3)[sel]
    idx = np.argsort(-A)[:6000]                                 # the largest quads carry the spread
    A, C = A[idx], C[idx]
    for a, c in zip(A, C):
        for s in (-1, 1):
            M.add("hull_steel_and_frames", steel * a / A.sum() / 2, c[0], s * c[1], c[2])
    # the deck: the planking over the deck's plan, the rest where the deck report puts each piece
    for name, kg, c in _rows(b["deck"]["weights"]["rows"]):
        if name.startswith("Deck planking"):
            xs_d = np.linspace(loft.END["transom_top"][0] + 0.3, loft.END["stem_head"][0] - 0.3, 60)
            hb = np.array([float(loft.DECK_HB(x)) for x in xs_d])
            hb = np.maximum(hb, 0.05)
            for x, h in zip(xs_d, hb):
                for f in (-0.75, -0.25, 0.25, 0.75):
                    M.add("deck_and_deckhouses", kg * h / hb.sum() / 4, x, f * h, c[2])
        else:
            M.add("deck_and_deckhouses", kg, *c)
    # the spars: the mast's skin and frames along its length, tapering as its section does; the boom along its length
    rig = b["rig"]
    mast = rig["mast"]
    for name, kg, c in _rows(rig["weights"]["rows"]["Mast"]):
        if name in ("Mast skin", "Mast frames, stringers, laps and rivets"):
            M.line("spars", kg, mast["heel"], mast["truck_top"], n=80, taper=mast["section_at_top_m"][0]
                   / mast["section_at_partners_m"][0])
        else:
            M.add("spars", kg, *c)
    bo = rig["boom_frame"]["origin"]
    for name, kg, c in _rows(rig["weights"]["rows"]["Boom"]):
        if "spar" in name.lower() or "skin" in name.lower():
            M.line("spars", kg, bo, rig["boom"]["end"], n=40, taper=rig["boom"]["section_end"][0]
                   / rig["boom"]["section_mid"][0])
        else:
            M.add("spars", kg, *c)
    for name, kg, c in _rows(rig["weights"]["rows"]["SpinnakerPole"]):
        M.add("spars", kg, *c)
    # the standing rigging: each wire along its path (starboard tack: the starboard runner and checkstay set, the
    # port ones let off), its fittings where the rigging report puts them
    gw = b["rigging"]
    wires = {"Cap shrouds (V1)": "cap", "Upper diagonals (D3)": "d3", "Diagonals (D2)": "d2",
             "Lower shrouds (D1)": "d1", "Forestay": "forestay", "Staysail stay": "staysail", "Backstay": "backstay",
             "Jumper stays": "jumper", "Runner pendants": "runner", "Checkstay pendants": "checkstay"}
    for name, kg, c in _rows(gw["weights"]["rows"]):
        key = wires.get(name)
        paths = [wv["path"] for wv in gw["wires"] if wv["key"] == key and not (
            ("starboard" in wv["name"] and "letoff" in wv["name"])
            or ("port" in wv["name"] and wv["name"].endswith("set")))]
        if key and paths:
            for p in paths:
                M.path("standing_rigging", kg / len(paths), p)
        else:
            M.add("standing_rigging", kg, *c)
    run = b["running"]["weights"]
    for name, kg, c in _rows(run["running_rigging"]["rows"]):
        M.add("running_rigging", kg, *c)
    hw = b["hardware"]
    for name, kg, c in _rows(run["winches_and_cleats"]["rows"]):
        M.add("winches_and_hardware", kg, *c)
    M.add("winches_and_hardware", run["sheet_tracks"]["total_kg"], *run["sheet_tracks"]["centre"])
    for name, kg, c in _rows(hw["weights"]["rows"]):
        M.add("winches_and_hardware", kg, *c)
    for name, kg, c in _rows(b["interior"]["weights"]["ground_tackle"]["rows"]):
        M.add("winches_and_hardware", kg, *c)
    for k in ("accommodation_forward", "accommodation_aft"):
        for name, kg, c in _rows(b["interior"]["weights"][k]["rows"]):
            M.add("accommodation", kg, *c)
    # every measured part onto the weight check's centre for it (x, z); the card's estimates likewise
    meas = {"deck_and_deckhouses": b["deck"]["weights"], "spars": rig["weights"], "standing_rigging": gw["weights"],
            "running_rigging": run["running_rigging"]}
    moved = {}
    for part in ("hull_steel_and_frames", "deck_and_deckhouses", "spars", "standing_rigging", "running_rigging",
                 "winches_and_hardware", "accommodation", "lead_keel"):
        if part == "lead_keel":
            x, z = lead["centroid_x_m"], lead["centroid_z_m"]
        elif part in meas:
            x, z = meas[part]["centre"][0], meas[part]["centre"][2]
        elif part == "winches_and_hardware":
            c = hw["all_deck_hardware_weight"]["centre"]
            x, z = c[0], c[2]
        elif part == "accommodation":
            c = b["interior"]["accommodation"]["centre"]
            x, z = c[0], c[2]
        else:
            x, z = loft.SPECS["weight_positions"][part]
        moved[part] = [round(v, 3) for v in M.move_to(part, x, z)]
    # the sails aboard (the card's 3.0 long tons below): the main and the genoa set, the rest in their bags below
    card = loft.SPECS["weights"]["sails_aboard"] * LT_KG
    sx, sz = loft.SPECS["weight_positions"]["sails_aboard"]
    for k in ("main", "genoa"):
        s = corners[k]
        M.triangle("sails_set", s["kg"], *[(p[0], 0.0, p[1]) for p in (s["tack"], s["head"], s["clew"])])
    M.add("sails_aboard", card - corners["main"]["kg"] - corners["genoa"]["kg"], sx, 0.0, sz)
    # crew and stores (the card's 5 long tons): the crew on deck, the stores below so the two keep the card's centre
    cs = loft.SPECS["weights"]["crew_and_stores"] * LT_KG
    cx, cz = loft.SPECS["weight_positions"]["crew_and_stores"]
    crew = crew_count * crew_kg
    crew_z = float(loft.SHEER(cx)) + 0.12 + 0.35                # sitting on deck: the body's centre 0.35 m up
    M.add("crew", crew, cx, 0.0, crew_z)
    M.add("stores", cs - crew, cx, 0.0, (cs * cz - crew * crew_z) / (cs - crew))
    return M, moved


# ----------------------------------------------------------------------------------------------------------- sails

def strip_recipe(tack, head, clew, head_chord):
    """FSailGeometry's strip recipe for a triangle in the centreline plane: horizontal strips from the foot's middle
    height to the head, the luff's x along the luff, the foot's chord the clew's distance aft of the luff, so the
    strips' centre of area stands where the triangle's does (BuildSail then scales the chords to the sail's area)."""
    tack, head, clew = (np.asarray(p, float) for p in (tack, head, clew))
    z0 = 0.5 * (tack[1] + clew[1])
    zh = head[1]
    luff_x0 = tack[0] + (head[0] - tack[0]) * (z0 - tack[1]) / (head[1] - tack[1])
    c0 = luff_x0 - clew[0]
    ce_tri = (tack[1] + head[1] + clew[1]) / 3.0
    ce_strip = z0 + (zh - z0) * (c0 + 2 * head_chord) / (3 * (c0 + head_chord))
    return {"foot_z": z0, "head_z": zh, "foot_chord": c0, "head_chord": head_chord, "luff_x": luff_x0,
            "luff_x_head": float(head[0]), "centre_of_area_z": float(ce_tri), "strips_centre_z": float(ce_strip)}


# ------------------------------------------------------------------------------------------------------------ main

def build(d):
    b = json.load(open(os.path.join(d, "build.json")))
    S = loft.surface()
    h = loft.hydrostatics(S)
    spec = json.load(open(os.path.join(HERE, "physics_bluebonnet.json")))
    stations, clamp = hull_sections(S)
    V_c, cbx, cbz, wet_c = sections_volume(stations)
    keel = keel_appendage(S)
    rud = rudder_profile(b["finish"])
    V = V_c + keel["volume_m3"]

    crew = spec["crew"]
    corners = sail_corners(b)
    M, moved = weights(b, S, corners, crew["count"], crew["kg_each"])
    real_kg, cg = M.total()
    k, inertia = M.radii(cg)
    scale = RHO_FRESH * V / real_kg
    lead_kg, lead_c = M.total("lead_keel")
    crew_kg, crew_c = M.total("crew")
    rest = [p for p in M.parts if p not in ("lead_keel", "crew")]
    rest_kg = sum(M.total(p)[0] for p in rest)
    rest_c = sum(M.total(p)[0] * M.total(p)[1] for p in rest) / rest_kg
    by_part = {p: {"kg": round(M.total(p)[0], 1), "centre": [round(float(v), 3) for v in M.total(p)[1]]}
               for p in M.parts}

    # the keel as the physics' lifting foil: her whole lateral plane below the water (the canoe body's and the keel's
    # profiles, one long low foil, as the maxi's keel carries her canoe body's side force), less the rudder's
    c_lat, (cx, cz) = canoe_lateral(stations)
    k_lat, (kx, kz) = keel["lateral_m2"], keel["lateral_centre"]
    r_a, (rx, rz) = rud["area_m2"], rud["centre"]
    f_a = c_lat + k_lat - r_a
    fx, fz = (c_lat * cx + k_lat * kx - r_a * rx) / f_a, (c_lat * cz + k_lat * kz - r_a * rz) / f_a
    span = h["draft_m"]
    chord = f_a / span
    bot = loft.KEEL["bottom"]
    fk = spec["foils"]
    band = flapped_band(max(p[1] for p in rud["polygon"]))
    fl = rudder_as_flap(band, fk["keel_effective_aspect_ratio"], rud["built_area_m2"], rud["chord_m"],
                        fk["rudder_blade_aspect_ratio"], fk["rudder_effective_aspect_ratio"])
    area_share = rud["built_area_m2"] / fl["area_m2"]        # the blade's share of the foil's area: its drag
    lift_share = fl["blade_lift_share"]                      # and of its lift: the hinge moment the wheel feels

    sheet = {
        "about": "Bluebonnet for the game's physics (slice 13, the cloud half; docs/jclass-13): what FBoatConfig "
                 "needs, measured on the model where the model says it ('measured'), and the tuning knobs' starting "
                 "points where only sailing her will (physics_bluebonnet.json, 'spec'). Frame: metres, X forward, "
                 "Y starboard, Z up, origin on the centreline at the middle of the load waterline (the physics' body "
                 "frame).",
        "build": os.path.basename(os.path.abspath(d)),
        "water": {"density_kg_m3": RHO_FRESH, "note": "the physics' water is fresh (SailingMath.h kWaterDensity), so "
                  "she weighs what her hull displaces in it on her lines: every part of her budget scaled by 'scale'"},
        "hull": {
            "measured": True, "stations": stations, "points": N_POINTS, "half_breadth_clamped_m": round(clamp, 4),
            "station_depth_m": round(-min(s["half_section"][0][1] for s in stations), 4),
            "canoe_volume_m3": round(V_c, 3), "canoe_centre": [round(cbx, 3), round(cbz, 3)],
            "canoe_volume_loft_m3": h["canoe_volume_m3"], "canoe_wetted_m2": round(wet_c, 2),
            "wetted_loft_m2": h["wetted_m2"],
            "volume_m3": round(V, 3), "volume_loft_m3": h["volume_m3"],
            "lwl_m": h["lwl_m"], "lwl_mid_x": round(0.5 * sum(h["lwl_ends_m"]), 3), "loa_m": h["loa_m"],
            "beam_m": h["beam_m"], "beam_wl_m": h["beam_wl_m"], "draft_m": h["draft_m"],
            "bow_x": stations[-1]["x"], "stern_x": stations[0]["x"],
            "max_half_beam": round(max(s["half_section"][-1][0] for s in stations), 3),
            "max_beam_x": max(stations, key=lambda s: s["half_section"][-1][0])["x"],
            "transom_half_beam": stations[0]["half_section"][-1][0],
            "sheer_amidships": round(float(loft.SHEER(0.0)), 3), "sheer_at_stem": round(float(loft.SHEER(
                loft.END["stem_head"][0] - 0.05)), 3)},
        "appendage": {"measured": True, "volume_m3": round(keel["volume_m3"], 3),
                      "centre": [round(v, 3) for v in keel["centre"]],
                      "note": "the keel and the rudder below the canoe line and the water: the physics floats them as "
                              "fixed buoyancy at their centre (FBoatConfig::AppendageVolume, AppendageCentre)"},
        "mass": {
            "measured": True, "real_kg": round(real_kg, 1), "real_long_tons": round(real_kg / LT_KG, 2),
            "weight_check_long_tons": b["weights"]["total_long_tons"], "scale": round(scale, 5),
            "sim_kg": round(scale * real_kg, 1), "cg": [round(float(v), 3) for v in cg],
            "weight_check_cg_xz": [b["weights"]["lcg_m"], b["weights"]["vcg_m"]],
            "ballast": {"kg": round(scale * lead_kg, 1), "centre": [round(float(v), 3) for v in lead_c]},
            "crew": {"kg": round(scale * crew_kg, 1), "centre": [round(float(v), 3) for v in crew_c],
                     "count": crew["count"]},
            "hull_rig": {"kg": round(scale * rest_kg, 1), "centre": [round(float(v), 3) for v in rest_c]},
            "parts": by_part, "parts_moved_onto_weight_check_m": moved,
            "radii_of_gyration_m": [round(v, 3) for v in k],
            "gm_lines_m": round(b["hydrostatics"]["vcb_m"] + b["hydrostatics"]["bm_t_m"] - float(cg[2]), 4),
            "inertia_kg_m2": [round(scale * v, 0) for v in inertia]},
        "foils": {
            "keel": {"measured": True, "area_m2": round(f_a, 3), "centre": [round(fx, 3), 0.0, round(fz, 3)],
                     "span_m": round(span, 3), "chord_m": round(chord, 3),
                     "geometric_aspect_ratio": round(span * span / f_a, 3),
                     "canoe_lateral_m2": round(c_lat, 3), "canoe_lateral_centre": [round(cx, 3), round(cz, 3)],
                     "keel_lateral_m2": round(k_lat, 3), "keel_lateral_centre": [round(kx, 3), round(kz, 3)],
                     "rudder_cut_m2": round(r_a, 3), "foot_x": [bot[0][0], bot[1][0]],
                     "note": "her lateral plane below the DWL: the canoe body's profile (down to the canoe line) "
                             "and the keel's (below it) less the rudder's (cut out of the keel's after end); span "
                             "her draft, chord the area over it. The effective aspect ratio and the balance shift "
                             "are physics_bluebonnet.json's"},
            "rudder": {"measured": True, "area_m2": rud["built_area_m2"], "profile_m2": round(r_a, 3),
                       "centre": [round(rx, 3), 0.0, round(rz, 3)], "span_m": round(rud["span_m"], 3),
                       "chord_m": rud["chord_m"], "polygon": rud["polygon"],
                       "stock_to_centre_m": round(rud["stock_to_centre_m"], 3),
                       "geometric_aspect_ratio": round(rud["span_m"] ** 2 / rud["built_area_m2"], 3),
                       "flap": {k: round(v, 4) for k, v in fl.items()},
                       "physics_area_m2": round(fl["area_m2"], 3),
                       "physics_stock_to_cp_m": round(rud["stock_to_centre_m"] * lift_share, 4),
                       "physics_profile_drag": round(fk["rudder_profile_drag"] * area_share, 6),
                       "note": "the blade as slice 2 built it (its area less the groove, shoulder and gaps); its "
                               "profile between the stock and the post is what the keel's lateral plane loses to "
                               "it. In the physics it is the keel's flap (rudder_as_flap, over the band of her "
                               "lateral plane it spans): 'physics_area_m2' at aspect 'flap.aspect_ratio'. The "
                               "physics takes a foil's hinge moment as its whole lift times RudderStockToCP, so that "
                               "arm is scaled by the blade's own share of the lift (the wheel feels the blade's load, "
                               "not the keel's); its profile drag by the blade's share of the area"}},
        "rig": {}, "spec": spec,
    }
    rig = b["rig"]
    m, g = corners["main"], corners["genoa"]
    main = strip_recipe(m["tack"], m["head"], m["clew"], m["headboard"])
    main.update({"area_m2": m["area"], "roach_m2": m["roach_m2"],
                 "roach_fraction": round(m["roach_m2"] / (m["foot"] * (2 / math.pi) * m["luff"]), 4),
                 "foot_chord": m["foot"], "luff_x": float(m["tack"][0]), "foot_z": float(m["tack"][1])})
    jib = strip_recipe(g["tack"], g["head"], g["clew"], spec["sails"]["jib_head_chord"])
    jib["area_m2"] = g["area"]
    sp = b["sails"]["sails"]["Spinnaker"]
    att = rig["attachments"]
    sj = json.load(open(os.path.join(HERE, "sails_bluebonnet.json")))["spinnaker"]
    head = np.array(att["masthead_crane_tip"], float) + np.array([sj["head_fwd"], 0.0, -sj["head_below_crane"]])
    pole_z = rig["pole"]["end"][2]
    spin = {"foot_z": round(0.5 * (pole_z + sj["clew"][2]), 3), "head_z": round(float(head[2]), 3),
            "foot_chord": sp["foot_m"],
            "head_chord": round(spec["sails"]["spinnaker_head_chord_of_foot"] * sp["foot_m"], 3),
            "luff_x": round(float(rig["mast"]["partners"][0] + rig["pole"]["length_m"]), 3),
            "luff_x_head": round(float(head[0]), 3), "area_m2": sp["area_m2"]}
    mast = rig["mast"]
    sheet["rig"] = {
        "measured": True, "mast_x": mast["partners"][0], "masthead_z": mast["truck_top"][2],
        "mast_diameter": round(0.5 * sum(mast["section_at_partners_m"]) * 0.5
                               + 0.5 * sum(mast["section_at_top_m"]) * 0.5, 3),
        "boom_z": rig["boom_frame"]["origin"][2], "main": main, "jib": jib, "spinnaker": spin,
        "sail_area_rated_ft2": rig["sail_area_ft2"],
        "reef_luff_fraction": [round((m["luff"] - r) / m["luff"], 3) for r in sj_reefs(b)],
        "boom_sweep_deg": max(abs(t["turn_deg"]) for t in rig["boom_sweep"]["turns"]
                              if all(t.get(k, 0) == 0 for k in t if k.startswith("touching"))),
        "windage": windage(b, S, crew["count"])}
    sheet["mass"]["sail_note"] = ("the weight check keeps every sail below (the card's 3.0 long tons at "
                                  f"{loft.SPECS['weight_positions']['sails_aboard']}); here the main and the genoa are "
                                  "set, which raises her centre of gravity by "
                                  f"{round(float(cg[2]) - b['weights']['vcg_m'], 3)} m")
    return sheet


def sj_reefs(b):
    return json.load(open(os.path.join(HERE, "sails_bluebonnet.json")))["mainsail"]["reefs"]


def windage(b, S, crew_count):
    """Frontal drag areas (Cd x A, m^2): the mast's tube and the wires (each its length x diameter x 1.2, round wire
    across the wind), and the hull's topsides bow on, the deckhouses and the crew."""
    rig = b["rig"]
    mast = rig["mast"]
    L = mast["length_overall_m"] - (mast["partners"][2] - mast["heel"][2])
    width = 0.5 * (mast["section_at_partners_m"][1] + mast["section_at_top_m"][1])
    mast_cda = 0.9 * L * width
    wires = 0.0
    for w in b["rigging"]["wires"]:
        if "letoff" in w["name"] or w["name"].endswith(", port, set"):
            continue
        p = np.asarray(w["path"], float)
        wires += 1.2 * float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) * 2 * w["r"]
    beam = b["hydrostatics"]["beam_m"]
    free = float(loft.SHEER(0.0))
    hull = 0.7 * beam * free + 0.9 * 4.0 + 0.5 * crew_count * 0.15
    return {"rig_cda_m2": round(mast_cda + wires, 2), "mast_cda_m2": round(mast_cda, 2),
            "wires_cda_m2": round(wires, 2),
            "hull_cda_m2": round(hull, 2),
            "note": "mast: 0.9 x its length above the partners x its mean fore-and-aft width; wires: 1.2 x length x "
                    "diameter (starboard tack's set runners only); hull: 0.7 x the topsides bow on (beam x freeboard "
                    "amidships), 0.9 x 4 m^2 of deckhouses, wheel and gear, 0.15 m^2 of each crew lying low"}


def fmt(v):
    return ("%.6f" % v).rstrip("0").rstrip(".") if abs(v) > 1e-9 else "0"


def write_inl(sheet, path):
    h, a = sheet["hull"], sheet["appendage"]
    st = h["stations"]
    lines = [
        "// Generated by Tools/shipkit/jclass/physics.py from Bluebonnet's lines (slice 1) and build: do not edit.",
        "// Her canoe body's half sections, transom to stem: body frame metres (X forward, Y starboard, Z up,",
        "// origin on the DWL at the middle of the waterline), each from the centreline (Y 0) to the sheer, half",
        "// breadths never decreasing; the keel is cut off flat along the canoe line and floats as the appendage.",
        "",
        "constexpr int kBluebonnetStations = %d;" % len(st),
        "constexpr int kBluebonnetSectionPoints = %d;" % h["points"],
        "constexpr double kBluebonnetCanoeVolume = %s;   // m^3 at the DWL (these sections, trapezoids)" % fmt(
            h["canoe_volume_m3"]),
        "constexpr double kBluebonnetBuoyancyX = %s; constexpr double kBluebonnetBuoyancyZ = %s;" % (
            fmt(h["canoe_centre"][0]), fmt(h["canoe_centre"][1])),
        "constexpr double kBluebonnetKeelVolume = %s; constexpr double kBluebonnetKeelX = %s; "
        "constexpr double kBluebonnetKeelZ = %s;" % (fmt(a["volume_m3"]), fmt(a["centre"][0]), fmt(a["centre"][1])),
        "",
        "struct FBluebonnetSection",
        "{",
        "\tdouble X, Sheer;",
        "\tdouble Y[kBluebonnetSectionPoints], Z[kBluebonnetSectionPoints];",
        "};",
        "const FBluebonnetSection kBluebonnetSections[kBluebonnetStations] = {",
    ]
    for s in st:
        ys = ", ".join(fmt(p[0]) for p in s["half_section"])
        zs = ", ".join(fmt(p[1]) for p in s["half_section"])
        lines.append("\t{ %s, %s, { %s }, { %s } }," % (fmt(s["x"]), fmt(s["sheer"]), ys, zs))
    lines.append("};")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def v3(v):
    return "Vec3(%s, %s, %s)" % tuple(fmt(float(x)) for x in v)


def write_trial(sheet, path):
    """A config body for trial/trial_sail.cpp: sets every field of an FBoatConfig from the sheet (the starting points
    from physics_bluebonnet.json), in the order Fleet.cpp's boats use."""
    h, m, f, r, sp = sheet["hull"], sheet["mass"], sheet["foils"], sheet["rig"], sheet["spec"]
    kz = sp["foils"]
    res = ", ".join("{ %s, %s }" % (fmt(a), fmt(c)) for a, c in sheet["resistance"]["residuary"])
    L = [
        "// Generated by Tools/shipkit/jclass/physics.py: Bluebonnet's trial config from the sheet (physics.json).",
        "static void ApplyBluebonnet(Sailing::FBoatConfig& C)",
        "{",
        "\tusing namespace Sailing;",
        "\tC.Name = \"Bluebonnet\";",
        "\tFHullShape H;",
        "\tfor (const FBluebonnetSection& M : kBluebonnetSections)",
        "\t{",
        "\t\tFHullShape::FStation St; St.X = M.X; St.Sheer = M.Sheer;",
        "\t\tSt.Y.assign(M.Y, M.Y + kBluebonnetSectionPoints); St.Z.assign(M.Z, M.Z + kBluebonnetSectionPoints);",
        "\t\tH.StationDepth = std::max(H.StationDepth, -M.Z[0]); H.Stations.push_back(St);",
        "\t}",
        "\tH.BowX = kBluebonnetSections[kBluebonnetStations - 1].X; H.SternX = kBluebonnetSections[0].X;",
        "\tH.WaterlineMidX = %s; H.WaterlineHalfLength = %s;" % (fmt(h["lwl_mid_x"]), fmt(0.5 * h["lwl_m"])),
        "\tH.MaxHalfBeam = %s; H.MaxBeamX = %s; H.AftLength = %s; H.TransomBeamLoss = %s;" % (
            fmt(h["max_half_beam"]), fmt(h["max_beam_x"]), fmt(h["max_beam_x"] - h["stern_x"]),
            fmt(h["max_half_beam"] - h["transom_half_beam"])),
        "\tH.SheerZ = %s; H.SheerRise = %s; H.SheerRiseFromX = 0.0;" % (
            fmt(h["sheer_amidships"]), fmt(h["sheer_at_stem"] - h["sheer_amidships"])),
        "\tC.Hulls = { H };",
        "\tC.LengthOverall = %s; C.WaterlineLength = %s; C.Beam = %s; C.WaterlineBeam = %s; C.Draft = %s;" % (
            fmt(h["loa_m"]), fmt(h["lwl_m"]), fmt(h["beam_m"]), fmt(h["beam_wl_m"]), fmt(h["draft_m"])),
        "\tC.TrimHeelLimitDeg = %s; C.TrimMaxEaseDeg = %s;" % (
            fmt(sp["trim"]["heel_limit_deg"]), fmt(sp["trim"]["max_ease_deg"])),
        "\tC.CrewMass = %s; C.CrewCount = %d; C.CrewCG = %s;" % (
            fmt(m["crew"]["kg"]), m["crew"]["count"], v3(m["crew"]["centre"])),
        "\tC.CrewSitOut = %s; C.CrewHikeOut = %s; C.CrewMoveSpeed = %s;" % (
            fmt(sp["crew"]["sit_out_m"]), fmt(sp["crew"]["hike_out_m"]), fmt(sp["crew"]["move_speed"])),
        "\tC.BallastMass = %s; C.BallastCG = %s;" % (fmt(m["ballast"]["kg"]), v3(m["ballast"]["centre"])),
        "\tC.AppendageVolume = kBluebonnetKeelVolume;",
        "\tC.AppendageCentre = Vec3(kBluebonnetKeelX, 0.0, kBluebonnetKeelZ);",
        "\tC.HullRigMass = %s; C.HullRigCG = %s;" % (fmt(m["hull_rig"]["kg"]), v3(m["hull_rig"]["centre"])),
        "\tC.RadiiOfGyration = %s;" % v3(m["radii_of_gyration_m"]),
        "\tC.Residuary = { %s };" % res,
        "\tC.WettedAreaCoef = %s; C.FormFactor = %s;" % (
            fmt(sheet["resistance"]["wetted_area_coef"]), fmt(sp["resistance"]["form_factor"])),
        "\tC.AddedResistanceCoef = %s;" % fmt(sp["resistance"]["added_resistance_coef"]),
        "\tC.HullLateralArea = %s; C.MunkAddedMass = %s; C.YawDampingLinear = %s; C.HeaveDamping = %s;" % (
            fmt(sheet["resistance"]["hull_lateral_area"]), fmt(sheet["resistance"]["munk_added_mass"]),
            fmt(sheet["resistance"]["yaw_damping"]), fmt(sp["resistance"]["heave_damping"])),
        "\tFFoilDef Keel = Foil(EFoilRole::Keel, Vec3(%s, 0.0, %s), %s, %s, %s, %s);" % (
            fmt(f["keel"]["centre"][0] + kz["keel_centre_shift_x"]), fmt(f["keel"]["centre"][2]),
            fmt(f["keel"]["area_m2"] * kz["keel_area_factor"]), fmt(f["keel"]["chord_m"]),
            fmt(kz["keel_effective_aspect_ratio"]), fmt(kz["keel_stall_deg"])),
        "\tKeel.Params.ProfileDrag = %s;" % fmt(kz["keel_profile_drag"]),
        "\tKeel.ContactLeadingX = %s; Keel.ContactTrailingX = %s;" % (
            fmt(f["keel"]["foot_x"][0]), fmt(f["keel"]["foot_x"][1])),
        "\tFFoilDef Rudder = Foil(EFoilRole::Rudder, %s, %s, %s, %s, %s);   // the keel's flap (physics.json)" % (
            v3(f["rudder"]["centre"]), fmt(f["rudder"]["physics_area_m2"]), fmt(f["rudder"]["chord_m"]),
            fmt(kz["rudder_effective_aspect_ratio"]), fmt(kz["rudder_stall_deg"])),
        "\tRudder.Params.ProfileDrag = %s; Rudder.VentStartDeg = %s; Rudder.VentEndDeg = %s; Rudder.VentDepth = %s;" % (
            fmt(f["rudder"]["physics_profile_drag"]), fmt(kz["rudder_vent_start_deg"]), fmt(kz["rudder_vent_end_deg"]),
            fmt(kz["rudder_vent_depth"])),
        "\tKeel.VentStartDeg = %s; Keel.VentEndDeg = %s;" % (
            fmt(kz["keel_vent_start_deg"]), fmt(kz["keel_vent_end_deg"])),
        "\tC.Foils = { Keel, Rudder };",
        "\tC.KeelDownwashFactor = %s; C.HeelYawCoef = %s;" % (fmt(kz["keel_downwash"]), fmt(kz["heel_yaw_coef"])),
        "\tC.MaxRudderAngleDeg = %s; C.RudderStockToCP = %s; C.TillerLength = %s; C.HelmStiffness = %s; "
        "C.RudderResponseTime = %s;" % (fmt(sp["helm"]["max_rudder_deg"]), fmt(f["rudder"]["physics_stock_to_cp_m"]),
                                        fmt(sp["helm"]["tiller_length"]), fmt(sp["helm"]["stiffness"]),
                                        fmt(sp["helm"]["response_s"])),
        "\tC.WheelHardOverSeconds = %s;" % fmt(sp["helm"]["wheel_hard_over_s"]),
        "\tC.MastX = %s; C.MastheadZ = %s; C.MastDiameter = %s;" % (
            fmt(r["mast_x"]), fmt(r["masthead_z"]), fmt(r["mast_diameter"])),
    ]
    mn, jb, sn, ss = r["main"], r["jib"], r["spinnaker"], sp["sails"]
    L += [
        "\tSetMain(C, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);" % tuple(fmt(v) for v in (
            mn["foot_z"], mn["head_z"], mn["foot_chord"], mn["head_chord"], mn["roach_fraction"], mn["luff_x"],
            mn["luff_x_head"], mn["area_m2"], ss["main"][0], ss["main"][1], ss["main"][2])),
        "\tC.BoomZ = %s;" % fmt(r["boom_z"]),
        "\tC.JibFootZ = %s; C.JibHeadZ = %s; C.JibFootChord = %s; C.JibHeadChord = %s; C.JibLuffX = %s; "
        "C.JibLuffXHead = %s; C.JibArea = %s;" % tuple(fmt(v) for v in (
            jb["foot_z"], jb["head_z"], jb["foot_chord"], jb["head_chord"], jb["luff_x"], jb["luff_x_head"],
            jb["area_m2"])),
        "\tSetSail(C.Jib, C.JibFootZ, C.JibHeadZ, C.JibFootChord, C.JibHeadChord, C.JibLuffX, C.JibLuffXHead, "
        "C.JibArea, %s, %s, %s);" % tuple(fmt(v) for v in ss["jib"]),
        "\tSetSail(C.Spinnaker, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);" % tuple(fmt(v) for v in (
            sn["foot_z"], sn["head_z"], sn["foot_chord"], sn["head_chord"], sn["luff_x"], sn["luff_x_head"],
            sn["area_m2"], ss["spinnaker"][0], ss["spinnaker"][1], ss["spinnaker"][2])),
        "\tC.bAsymmetricSpinnaker = false;",
        "\tC.MainMaxEaseDeg = %s; C.TravelerRangeDeg = %s; C.JibMinAngleDeg = %s; C.JibMaxAngleDeg = %s;" % tuple(
            fmt(v) for v in (sp["trim"]["main_max_ease_deg"], sp["trim"]["traveler_range_deg"],
                             sp["trim"]["jib_min_deg"], sp["trim"]["jib_max_deg"])),
        "\tC.RigWindageCdA = %s; C.HullWindageCdA = %s;" % (
            fmt(r["windage"]["rig_cda_m2"]), fmt(r["windage"]["hull_cda_m2"])),
        "\tC.ReefLuffFraction = { %s };" % ", ".join(fmt(v) for v in r["reef_luff_fraction"]),
        "\tC.ReefJibFraction = { %s };" % ", ".join(fmt(v) for v in sp["sails"]["reef_jib_fraction"]),
        "\tC.Engines.clear();",
        "}",
    ]
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def resistance(sheet):
    """Wetted area, residuary table and the low-speed hull terms, from the J/22's and the maxi's by her proportions."""
    sp = sheet["spec"]["resistance"]
    h = sheet["hull"]
    V = h["volume_m3"]
    slender = h["lwl_m"] / V ** (1 / 3)
    j22 = sp["j22_residuary"]
    f = (sp["j22_slenderness"] / slender) ** 3 * V / h["canoe_volume_m3"] * sp["residuary_factor"]
    res = [[fn, float("%.5g" % (c * f))] for fn, c in j22]
    maxi = sp["maxi"]
    return {"wetted_area_coef": round(h["wetted_loft_m2"] / math.sqrt(h["canoe_volume_m3"] * h["lwl_m"]), 3),
            "slenderness": round(slender, 3), "residuary_scale_from_j22": round(f, 4), "residuary": res,
            "hull_lateral_area": round(0.5 * sheet["foils"]["keel"]["canoe_lateral_m2"], 2),
            "munk_added_mass": round(maxi["munk"] * V / maxi["volume"], -2),
            "yaw_damping": round(maxi["yaw_damping"] * (V / maxi["volume"]) * (h["lwl_m"] / maxi["lwl"]) ** 2, -3),
            "note": "wetted area: the whole hull's below the DWL, keel and all (the lines' hydrostatics; the "
                    "rudder's friction is its foil's profile drag), over sqrt(canoe volume x LWL), since the physics "
                    "sums friction on the canoe body's volume and the keel's lateral plane carries only a form drag; "
                    "residuary per unit weight: the J/22's table (FBoatConfig's) times (her slenderness LWL / "
                    "V^(1/3) against the J/22's)^-3 (the Delft series' fall with slenderness, the maxi's rule), "
                    "times her whole volume over the canoe body's (the physics charges it on the canoe body's "
                    "weight), times 'residuary_factor' (a knob, 1 to start); the hull's lateral area (its low-speed "
                    "sway drag, at each of two stations) half the canoe body's profile below the DWL, as the maxi's; "
                    "Munk added mass by volume from the maxi's, yaw damping by volume and length squared from the "
                    "maxi's"}


def main(d):
    sheet = build(d)
    sheet["resistance"] = resistance(sheet)
    with open(os.path.join(d, "physics.json"), "w") as f:
        json.dump(sheet, f, indent=1)
    write_inl(sheet, os.path.join(d, "BluebonnetHullData.inl"))
    write_trial(sheet, os.path.join(d, "bluebonnet_trial.inl"))
    return sheet


if __name__ == "__main__":
    s = main(os.path.abspath(sys.argv[1]))
    h, m = s["hull"], s["mass"]
    print("canoe %.2f m^3 (loft %.2f) + keel %.2f = %.2f m^3 (loft %.2f); wetted canoe %.1f m^2" % (
        h["canoe_volume_m3"], h["canoe_volume_loft_m3"], s["appendage"]["volume_m3"], h["volume_m3"],
        h["volume_loft_m3"], h["canoe_wetted_m2"]))
    print("mass real %.0f kg (%.1f LT; weight check %.1f), sim %.0f kg, scale %.4f; CG %s (weight check %s)" % (
        m["real_kg"], m["real_long_tons"], m["weight_check_long_tons"], m["sim_kg"], m["scale"], m["cg"],
        m["weight_check_cg_xz"]))
    print("radii of gyration", m["radii_of_gyration_m"], "ballast", m["ballast"], "crew", m["crew"],
          "hull+rig", m["hull_rig"])
    print("keel", s["foils"]["keel"])
    print("rudder", {k: v for k, v in s["foils"]["rudder"].items() if k != "polygon"})
    print("rig", {k: v for k, v in s["rig"].items() if k not in ("main", "jib", "spinnaker")})
    for k in ("main", "jib", "spinnaker"):
        print(k, s["rig"][k])
    print("resistance", {k: v for k, v in s["resistance"].items() if k != "note"})
