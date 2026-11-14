"""Bluebonnet's spars (docs/jclass-4): the riveted duralumin mast with its spreaders, jumper struts, sail track and
fittings, the long boom on its gooseneck, and the spinnaker pole on its car, from rig_bluebonnet.json.

Three objects, each a set of closed solids:
  Mast           fixed: stepped on the keelson, through the deck's partners (its mast coat let into the deck) to the
                 truck; the spreaders, jumper struts, tracks, bands, tangs, the gooseneck's lug and pin and the pole's
                 car are part of it
  Boom           its own frame: origin on the gooseneck's pin, Z up the pin (the mast's axis), X aft along the boom;
                 it swings about that Z
  SpinnakerPole  its own frame: origin on the heel's pin on the car, Z upright, X out along the pole; it swings about
                 that Z, level, to either side
The spars' plating is drawn, not modelled: each vertex carries two UV maps, which the spars' paint reads as the hull's
paint reads its 'Plating' map (build_jclass.py's SparPlating group):
  Spar   (u, v)        u metres along the spar from its heel (the boom's forward end); v the fraction of the way round
                       from its forward face (the boom's top), toward starboard
  SparG  (girth, on)   the girth there (m); on = 1 where the spar is plated, -1 on fittings and the plain pole
Weights come from the same geometry: each spar's skin from its girth, length and wall, the fittings from their volume or
as castings (area x wall). The build also measures the sail plan's I, J, P and E on the spars and gives the rule check
its rated sail area, and reports the points slice 5's rigging will run to.

Geometry is in the hull's frame (X forward, Y starboard, Z up, metres); faces are wound so numpy's cross product of
their edges points out of their solid, as deck.py's are.
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
import deck  # noqa: E402

RG = json.load(open(os.path.join(HERE, "rig_bluebonnet.json")))
MAT = RG["material"]
DUR, BRZ = MAT["duralumin"], MAT["bronze"]
FT = 0.3048
LB_KG = 0.45359237
Y = np.array([0.0, 1.0, 0.0])
UP = np.array([0.0, 0.0, 1.0])
PLAIN = (0.0, -1.0)                       # SparG where there is no plating

M = RG["mast"]
RAKE = math.radians(M["rake_deg"])
A = np.array([-math.sin(RAKE), 0.0, math.cos(RAKE)])      # up the mast's axis (it rakes aft)
FW = np.array([math.cos(RAKE), 0.0, math.sin(RAKE)])      # forward, square to the axis
X_P = deck.DK["mast"]["x"]                                # the partners, on the deck's centreline
Z_P = float(shell.deck_z(np.array([X_P]), np.array([0.0]))[0])
P0 = np.array([X_P, 0.0, Z_P])
H = M["height_above_deck"]
S_TOP = H / math.cos(RAKE)                                # along the axis from the partners to the truck's top
S_HEEL = (M["step_z"] - Z_P) / math.cos(RAKE)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def s_at(h):
    """Along the mast's axis from the partners, for a height h above the deck."""
    return h / math.cos(RAKE)


def at(s, f=0.0, y=0.0):
    """A point s along the mast's axis from the partners, f forward of it (square to it) and y to starboard."""
    return P0 + s * A + f * FW + y * Y


# ------------------------------------------------------------------------------------------------ the mast's section
def _egg_max():
    t = np.linspace(0.0, math.pi, 20001)
    return float((np.sin(t) * (1.0 + M["fullness"] * np.cos(t))).max())


EGG_MAX = _egg_max()


def scale(s):
    """The mast's section at s as a fraction of its section at the partners: whole up to 'taper_from' of its height,
    then tapering to 'top_scale' at the truck."""
    h = s * math.cos(RAKE) / H
    t0 = M["taper_from"]
    if h <= t0:
        return 1.0
    t = min((h - t0) / (1.0 - t0), 1.0)
    return 1.0 - (1.0 - M["top_scale"]) * t ** M["taper_power"]


def egg(k, n, grow=0.0):
    """The mast's section at scale k as n points (f forward, y starboard) round from the forward face toward
    starboard: a pear, fuller forward, 'depth' by 'width' at k = 1; grow pushes it out (a band over the mast)."""
    th = 2 * math.pi * np.arange(n) / n
    a = 0.5 * M["depth"] * k + grow
    b = 0.5 * M["width"] * k
    f = a * np.cos(th)
    y = (b * np.sin(th) * (1.0 + M["fullness"] * np.cos(th)) / EGG_MAX) * (b + grow) / b
    return f, y


def half_depth(s):
    return 0.5 * M["depth"] * scale(s)


def ring_at(s, n, grow=0.0):
    f, y = egg(scale(s), n, grow)
    return at(s) + f[:, None] * FW + y[:, None] * Y


def girth(P):
    return float(np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1).sum())


def surface_y(s, f):
    """The mast's half-width at s, f forward of its axis (on the forward half if f > 0)."""
    a = half_depth(s)
    th = math.acos(max(min(f / a, 1.0), -1.0))
    b = 0.5 * M["width"] * scale(s)
    return b * math.sin(th) * (1.0 + M["fullness"] * math.cos(th)) / EGG_MAX


def surface_toward(s, direction):
    """The point on the mast's surface at s whose direction from the axis (in the section's plane) is `direction`."""
    f, y = egg(scale(s), 4096)
    d = np.asarray(direction, float)
    ang = math.atan2(d @ Y, d @ FW)
    k = int(np.argmin(np.abs(np.angle(np.exp(1j * (np.arctan2(y, f) - ang))))))
    return at(s, f[k], y[k])


def wall(s):
    w = np.array(M["wall"], float)
    return float(np.interp(s * math.cos(RAKE) / H, w[:, 0], w[:, 1]))


# ------------------------------------------------------------------------------------------------ the parts
class SparPart(deck.Part):
    """deck.Part with the spars' two UV maps instead of the deck's three, and each face's label (the sweeps leave out
    the pieces that meet by design: a jaw round its pin)."""

    def __init__(self, name, frame=None):
        super().__init__(name, frame)
        self.uv = {"Spar": [], "SparG": []}
        self.labels = []

    def add(self, V, F, slot, mass=None, label=None, orient=True, uv=None):
        V = np.asarray(V, float)
        F = [tuple(int(i) for i in f) for f in F]
        if orient and deck.signed_volume(V, F) < 0:
            F = [f[::-1] for f in F]
        off = len(self.V)
        self.V.extend(V.tolist())
        self.F.extend([tuple(i + off for i in f) for f in F])
        self.slot.extend(slot if isinstance(slot, list) else [slot] * len(F))
        self.labels.extend([label or self.name] * len(F))
        uv = uv or {}
        self.uv["Spar"].extend(np.asarray(uv.get("Spar", np.zeros((len(V), 2)))).tolist())
        self.uv["SparG"].extend(np.asarray(uv.get("SparG", np.tile(PLAIN, (len(V), 1)))).tolist())
        if mass:
            self.weigh(V, F, mass, label)

    def weigh(self, V, F, mass, label):
        """('solid', rho): rho x volume; ('cast', rho, t[, inside]): a hollow casting, rho x t x its area, less
        `inside` (m^2): the flat ends that only close the mesh where a sleeve's end lies inside the spar it fits over
        (a socket's or a cap's open end), which no metal fills."""
        V = np.asarray(V, float)
        if mass[0] == "cast":
            T = deck.tris_of(F)
            a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
            ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
            area = float(ar.sum()) - (mass[3] if len(mass) > 3 else 0.0)
            kg = mass[1] * mass[2] * area
            cen = (((a + b + c) / 3.0) * ar[:, None]).sum(0) / float(ar.sum())
        else:
            kg, cen, _ = deck.mass_of(V, F, mass[0], mass[1], mass[2] if len(mass) > 2 else None)
        self.masses.append({"part": label or self.name, "kg": round(float(kg), 1),
                            "centre": [round(float(v), 3) for v in cen], "how": mass[0]})

    def corner_uv(self):
        """Each face corner's UVs. Where a face crosses the seam round a spar (v running from near 1 back to 0 across
        it), its corners near 0 take v + 1, so the paint's pattern runs on across the seam."""
        S, G = np.asarray(self.uv["Spar"]), np.asarray(self.uv["SparG"])
        out = {"Spar": [], "SparG": []}
        for f in self.F:
            s = S[list(f)].copy()
            if s[:, 1].max() - s[:, 1].min() > 0.5:
                s[s[:, 1] < 0.5, 1] += 1.0
            out["Spar"].append(s.tolist())
            out["SparG"].append(G[list(f)].tolist())
        return out


def poly_area(ring):
    """The area inside a closed ring of points (a flat end's area)."""
    r = np.asarray(ring, float)
    c = r.mean(0)
    return 0.5 * float(np.linalg.norm(np.cross(r - c, np.roll(r, -1, axis=0) - c).sum(0)))


def disc(r, n=32):
    """The area of revolve()'s flat end of radius r, an n-sided polygon."""
    return 0.5 * n * r * r * math.sin(2 * math.pi / n)


def ring_uv(rings, u, plated=True):
    """UVs for loft_rings(rings) (flat-capped): each ring's u, v round it, its girth; the two cap centres last."""
    n = len(rings[0])
    sp, sg = [], []
    for r, uu in zip(rings, u):
        g = girth(r)
        sp += [(uu, j / n) for j in range(n)]
        sg += [(g, 1.0 if plated else -1.0)] * n
    sp += [(u[0], 0.0), (u[-1], 0.0)]
    sg += [PLAIN, PLAIN]
    return {"Spar": np.array(sp), "SparG": np.array(sg)}


def plate(part, origin, U, Vd, N, u0, u1, h, t, slot, label, round_end=True, mass=("solid", BRZ)):
    """A flat plate (a tang, a crane, a jaw's cheek): from u0 to u1 along U, h tall along Vd, t thick about N, its
    end at u1 rounded."""
    if round_end:
        a = np.linspace(-math.pi / 2, math.pi / 2, 9)
        P = [(u0, -h / 2)] + [(u1 - h / 2 + h / 2 * math.cos(q), h / 2 * math.sin(q)) for q in a] + [(u0, h / 2)]
    else:
        P = [(u0, -h / 2), (u1, -h / 2), (u1, h / 2), (u0, h / 2)]
    V, F = deck.slab(np.array(P), origin, U, Vd, N, -t / 2, t / 2)
    part.add(V, F, slot, mass, label)


def band(part, s, height, t, slot, label, rho=BRZ, n=64):
    """A band round the mast at s, 'height' tall and t proud of it (rho 0: paint, no weight). Its inner face is inside
    the mast, so it sits on it with no gap."""
    s0, s1 = s - height / 2, s + height / 2
    rings = [ring_at(s0, n, -0.012), ring_at(s0, n, t), ring_at(s1, n, t), ring_at(s1, n, -0.012)]
    V, F = deck.loft_rings(rings, closed=True)
    part.add(V, F, slot, None, label)
    if rho:
        part.masses.append({"part": label, "kg": round(girth(ring_at(s, n)) * height * t * rho, 1),
                            "centre": [round(float(v), 3) for v in at(s)], "how": "band"})


def _bisector(T, prev, nxt):
    """The direction from a strut's root to its tip T that bisects the stay's bend there (prev and nxt the stay's
    neighbouring points), so the strut takes the push along itself."""
    return -unit(unit(prev - T) + unit(nxt - T))


# ------------------------------------------------------------------------------------------------ the mast
def mast(part, rep):
    n, step = M["sides"], M["ring_step"]
    tr = M["truck"]
    s_tube = S_TOP - tr["height"] + 0.04                        # the tube runs 4 cm up into the truck
    ss = np.unique(np.concatenate([np.arange(S_HEEL, s_tube, step), [s_tube]]))
    rings = [ring_at(s, n) for s in ss]
    V, F = deck.loft_rings(rings)
    part.add(V, F, "Spar", None, "Mast", uv=ring_uv(rings, ss - S_HEEL))
    skin, mom = 0.0, np.zeros(3)
    for s0, s1 in zip(ss[:-1], ss[1:]):
        sm = 0.5 * (s0 + s1)
        kg = 0.5 * (girth(ring_at(s0, n)) + girth(ring_at(s1, n))) * (s1 - s0) * wall(sm) * DUR
        skin += kg
        mom += kg * at(sm)
    cen = mom / skin
    part.masses.append({"part": "Mast skin", "kg": round(skin, 1), "centre": [round(float(v), 3) for v in cen],
                        "how": "skin"})
    part.masses.append({"part": "Mast frames, stringers, laps and rivets", "kg": round(M["frames_fraction"] * skin, 1),
                        "centre": [round(float(v), 3) for v in cen], "how": "fraction of the skin"})
    # the truck: a bronze cap with a rounded top, over the tube's end
    rt = half_depth(S_TOP) + tr["radius_over"]
    th = tr["height"]
    V, F = deck.revolve([(rt, 0.0), (rt, 0.55 * th), (0.82 * rt, 0.88 * th), (0.45 * rt, th), (0.0, th)],
                        at(S_TOP - th), A, FW, 40)
    part.add(V, F, "Bronze", ("cast", BRZ, 0.006), "Truck")
    # the masthead band, the crane forward (the topmast stay's tang and the spinnaker halyard's block), the black band
    mb = M["masthead_band"]
    band(part, S_TOP - mb["below_top"], mb["height"], mb["thickness"], "Bronze", "Masthead band")
    cr = M["masthead_crane"]
    sc = S_TOP - cr["below_top"]
    a = half_depth(sc)
    plate(part, at(sc), FW, A, Y, a - 0.04, a + cr["reach"], cr["height"], cr["thickness"], "Bronze", "Masthead crane")
    bb = M["black_band"]
    s_bb = S_TOP - bb["below_top"]                                # the black band's lower edge: the top of P
    band(part, s_bb + bb["height"] / 2, bb["height"], 0.0015, "Black", "Black band", rho=0)
    for label, v in M["fixed_kg"].items():
        if label != "note":
            part.weight(label, v[0], at(s_at(v[1] * H)))
    rep["truck_top"] = at(S_TOP)
    rep["black_band_s"] = s_bb
    rep["masthead_crane_tip"] = at(sc, a + cr["reach"] - cr["height"] / 2)
    return ss


def partners(part):
    """The mast coat: a bronze collar from its flange let into the deck up to the mast."""
    pc = RG["partners"]
    n = M["sides"]
    g0 = pc["grow_bottom"]
    # (s along the axis, grow, flange: height above the deck where the flange follows the deck's camber, or None)
    rows = [(0.0, g0, -pc["let_in"]), (0.0, g0, 0.012), (0.045, 0.8 * g0, None), (0.5 * pc["height"], 0.18 * g0, None),
            (pc["height"], 0.006, None), (pc["height"] + 0.004, -0.008, None)]
    rings = []
    for s, g, fl in rows:
        r = ring_at(s, n, g)
        if fl is not None:
            r[:, 2] = shell.deck_z(r[:, 0], r[:, 1]) + fl
        rings.append(r)
    V, F = deck.loft_rings(rings)
    inside = poly_area(ring_at(0.0, n)) + poly_area(rings[-1])
    part.add(V, F, "Bronze", ("cast", BRZ, 0.008, inside), "Mast coat")


def hounds(part, rep):
    hd = RG["hounds"]
    s_h = s_at(hd["height_fraction"] * H)
    band(part, s_h + 0.05, hd["band_height"], hd["band_thickness"], "Bronze", "Hounds band")
    tg = hd["tang"]
    a = half_depth(s_h)
    plate(part, at(s_h), FW, A, Y, a - 0.03, a + hd["band_thickness"] + tg["reach"], tg["height"], tg["thickness"],
          "Bronze", "Forestay tang")
    rep["forestay_hounds"] = at(s_h, a + hd["band_thickness"] + tg["reach"] - tg["height"] / 2)
    rep["shroud_tangs"] = {}
    for sd, side in ((1, "starboard"), (-1, "port")):
        w = surface_y(s_h - 0.05, 0.0)
        plate(part, at(s_h - 0.05), sd * Y, A, FW, w - 0.03, w + hd["band_thickness"] + tg["reach"], tg["height"],
              tg["thickness"], "Bronze", "Shroud tangs")
        rep["shroud_tangs"][side] = at(s_h - 0.05, 0.0, sd * (w + hd["band_thickness"] + tg["reach"] - tg["height"] / 2))
    rep["hounds_s"] = s_h
    return s_h


def spreaders(part, rep, sheer, s_h):
    sp = RG["spreaders"]
    cp = RG["chainplates"]
    sheer = np.asarray(sheer, float)
    o = np.argsort(sheer[:, 0])
    hb = float(np.interp(cp["x"], sheer[o, 0], np.abs(sheer[o, 1]))) - cp["inboard_of_sheer"]
    nsd = sp["sides"]
    rep["chainplates"], rep["spreader_tips"], rep["spreaders"] = {}, {}, []
    sockets = [[] for _ in sp["heights"]]                        # where each socket sits on the mast (s), both sides
    for sd, side in ((1, "starboard"), (-1, "port")):
        chain = np.array([cp["x"], sd * hb, float(shell.deck_z(np.array([cp["x"]]), np.array([sd * hb]))[0])])
        tips = [at(s_at(h), 0.0, sd * ty) for h, ty in zip(sp["heights"], sp["tip_y"])]
        path = [chain] + tips + [np.asarray(rep["shroud_tangs"][side], float)]
        rep["chainplates"][side] = chain
        rep["spreader_tips"][side] = tips
        for i, T in enumerate(tips):
            s = s_at(sp["heights"][i])
            ax = _bisector(T, path[i], path[i + 2])
            w = surface_y(s, 0.0)
            L_out = (abs(T[1]) - w) / abs(ax[1])                  # from the mast's side to the tip
            L = (abs(T[1]) - 0.5 * w) / abs(ax[1])                # from inside the mast (its root is let in)
            root = T - L * ax
            ch = unit(FW - (FW @ ax) * ax)
            tk = np.cross(ax, ch)

            def sec(l, grow=0.0, shrink=1.0):
                tau = min(max((l - (L - L_out)) / L_out, 0.0), 1.0)
                c = sp["chord"][0] + tau * (sp["chord"][1] - sp["chord"][0])
                t = sp["thickness"][0] + tau * (sp["thickness"][1] - sp["thickness"][0])
                q = 2 * math.pi * np.arange(nsd) / nsd
                return (root + l * ax + ((0.5 * c + grow) * shrink * np.cos(q))[:, None] * ch
                        + ((0.5 * t + grow) * shrink * np.sin(q))[:, None] * tk)
            ls = np.linspace(0.0, L, 14)
            rings = [sec(l) for l in ls]
            V, F = deck.loft_rings(rings)
            part.add(V, F, "Spar", None, "Spreaders")
            q = 0.5 * (sp["chord"][0] + sp["chord"][1]), 0.5 * (sp["thickness"][0] + sp["thickness"][1])
            per = math.pi * (3 * (q[0] + q[1]) / 2 - math.sqrt((3 * q[0] / 2 + q[1] / 2) * (q[0] / 2 + 3 * q[1] / 2)))
            part.masses.append({"part": "Spreaders", "kg": round(per * L_out * sp["wall"] * DUR, 1),
                                "centre": [round(float(v), 3) for v in T - 0.5 * L_out * ax], "how": "skin"})
            so, tf = sp["socket"], sp["tip_fitting"]
            l0 = L - L_out
            rings = [sec(l0 - 0.06, so["grow"]), sec(l0 + so["length"] - 0.03, so["grow"]),
                     sec(l0 + so["length"], so["grow"] * 0.3)]
            V, F = deck.loft_rings(rings)
            inside = poly_area(rings[0]) + poly_area(sec(l0 + so["length"]))
            part.add(V, F, "Bronze", ("cast", BRZ, 0.006, inside), "Spreader sockets")
            sockets[i].append(float((root + l0 * ax - P0) @ A))  # where the spreader meets the mast's side
            rings = [sec(L - tf["length"], -0.001), sec(L - tf["length"] + 0.02, tf["grow"]), sec(L, tf["grow"]),
                     sec(L + 0.02, tf["grow"], 0.75), sec(L + 0.03, 0.0, 0.4)]
            V, F = deck.loft_rings(rings)
            part.add(V, F, "Bronze", ("cast", BRZ, 0.006, poly_area(rings[0])), "Spreader tips")
            if sd == 1:
                bend = math.degrees(math.acos(max(-1.0, min(1.0, float(unit(path[i] - T) @ unit(path[i + 2] - T))))))
                rep["spreaders"].append({"height_above_deck_m": sp["heights"][i], "tip_out_m": sp["tip_y"][i],
                                         "length_from_mast_m": round(float(L_out), 3),
                                         "tilt_up_deg": round(math.degrees(math.asin(float(ax @ UP))), 2),
                                         "shroud_bend_at_tip_deg": round(180.0 - bend, 2)})
    for ss in sockets:                                            # a band round the mast through each pair's sockets
        band(part, float(np.mean(ss)), sp["socket"]["length"] * 0.8, 0.006, "Bronze", "Spreader bands")


def jumpers(part, rep, s_h):
    """The jumper struts: each comes off the mast's surface 'splay_deg' round from its forward face, and its stay runs
    from the masthead to 'stay_foot_below' the hounds over the strut's tip, with both its ends on the mast's surface the
    same way round. So the stay's ends, the strut's root and its tip all lie in one plane through the mast's axis, and
    the strut can bisect the stay's bend at its tip (solved below), carrying the stay's push straight along itself."""
    jp = RG["jumpers"]
    s_j = s_h + s_at(jp["above_hounds"])
    s_top, s_foot = S_TOP - jp["stay_top_below_top"], s_h - jp["stay_foot_below"]
    rep["jumper_tips"], rep["jumper_stays"] = {}, {}
    r0, r1 = 0.5 * jp["diameter"][0], 0.5 * jp["diameter"][1]
    ps = math.radians(jp["splay_deg"])
    for sd, side in ((1, "starboard"), (-1, "port")):
        hdir = unit(math.cos(ps) * FW + sd * math.sin(ps) * Y)
        Rs = surface_toward(s_j, hdir)
        st, sf = surface_toward(s_top, hdir), surface_toward(s_foot, hdir)
        d = hdir
        for _ in range(100):
            d_new = _bisector(Rs + jp["length"] * d, st, sf)
            done = float(np.linalg.norm(d_new - d)) < 1e-12
            d = d_new
            if done:
                break
        T = Rs + jp["length"] * d
        off = math.degrees(math.acos(min(1.0, float(d @ _bisector(T, st, sf)))))
        if off > 0.01:
            raise ValueError(f"the {side} jumper strut is {off:.3f} degrees off its stay's bisector")
        rep["jumper_stays"][side] = {"top": st, "foot": sf}
        o = Rs - 0.15 * d
        L = jp["length"] + 0.15
        V, F = deck.revolve([(r0, 0.0), (r0, 0.2), (r1, L - 0.08), (r1, L - 0.04)], o, d, UP, 24)
        part.add(V, F, "Spar", None, "Jumper struts")
        part.masses.append({"part": "Jumper struts", "kg": round(math.pi * (r0 + r1) * jp["length"] * jp["wall"] * DUR, 1),
                            "centre": [round(float(v), 3) for v in Rs + 0.5 * jp["length"] * d], "how": "skin"})
        V, F = deck.revolve([(r1 - 0.002, L - 0.12), (r1 + 0.012, L - 0.1), (r1 + 0.012, L), (0.6 * r1, L + 0.03),
                             (0.0, L + 0.035)], o, d, UP, 24)
        part.add(V, F, "Bronze", ("cast", BRZ, 0.006, disc(r1 - 0.002, 24)), "Jumper strut tips")
        V, F = deck.revolve([(r0 + 0.02, 0.0), (r0 + 0.02, 0.3), (r0 + 0.004, 0.34), (r0 - 0.002, 0.35)], o, d, UP, 24)
        part.add(V, F, "Bronze", ("cast", BRZ, 0.006, disc(r0 + 0.02, 24) + disc(r0 - 0.002, 24)), "Jumper strut sockets")
        rep["jumper_tips"][side] = T
    hz = d - (d @ UP) * UP                                        # the last (port) strut's heading, level
    rep["jumper_struts"] = {"length_m": jp["length"],
                            "splay_deg": round(math.degrees(math.atan2(abs(float(hz @ Y)), float(hz @ FW))), 2),
                            "tilt_up_deg": round(math.degrees(math.asin(float(d @ UP))), 2),
                            "off_the_stays_bisector_deg": round(off, 4)}


def track(part, s0, s1, after=True, label="Mainsail track"):
    """A T-section bronze bar up the mast's after (or forward) face from s0 to s1, let into it."""
    tk = RG["track"]
    sg = -1.0 if after else 1.0
    rings = []
    for s in np.linspace(s0, s1, max(int((s1 - s0) / 0.5), 2) + 1):
        a = half_depth(s)
        f_in, f_out = sg * (a - tk["let_in"]), sg * (a + tk["proud"])
        w = tk["width"] / 2
        rings.append(np.array([at(s, f_in, -w), at(s, f_out, -w), at(s, f_out, w), at(s, f_in, w)]))
    V, F = deck.loft_rings(rings)
    part.add(V, F, "Bronze", None, label)
    part.masses.append({"part": label, "kg": round(tk["section_area"] * (s1 - s0) * BRZ, 1),
                        "centre": [round(float(v), 3) for v in at(0.5 * (s0 + s1), sg * half_depth(0.5 * (s0 + s1)))],
                        "how": "section"})


def gooseneck(part, rep):
    """The gooseneck on the mast: a band, a lug aft to an eye round the pin, and the pin (the boom's jaw takes it)."""
    g, bm = RG["gooseneck"], RG["boom"]
    d_end = bm["section_end"][0]
    s_pin = s_at(g["boom_top_above_deck"] - d_end / 2)
    a = half_depth(s_pin)
    G = at(s_pin, -(a + g["pin_aft"]))
    band(part, s_pin, g["band_height"], g["band_thickness"], "Bronze", "Gooseneck band")
    plate(part, at(s_pin), -FW, A, Y, a - 0.04, a + g["pin_aft"], g["lug_height"], 0.08, "Bronze", "Gooseneck lug",
          round_end=False)
    V, F = deck.revolve([(g["eye_radius"], -g["lug_height"] / 2), (g["eye_radius"], g["lug_height"] / 2)], G, A, FW, 24)
    part.add(V, F, "Bronze", ("solid", BRZ), "Gooseneck lug")
    V, F = deck.revolve([(g["pin_radius"], -0.125), (g["pin_radius"], 0.125), (g["pin_radius"] + 0.012, 0.13),
                         (g["pin_radius"] + 0.012, 0.15), (0.0, 0.15)], G, A, FW, 20)
    part.add(V, F, "Bronze", ("solid", BRZ), "Gooseneck pin")
    rep["gooseneck_pin"] = G
    return G, s_pin


def pole_car(part, rep):
    """The spinnaker pole's car on its track up the mast's forward face, with an eye round the pole's heel pin."""
    pl = RG["pole"]
    c = pl["car"]
    s_c = s_at(pl["heel_above_deck"])
    a = half_depth(s_c)
    Ph = at(s_c, a + c["reach"])
    plate(part, at(s_c), FW, Y, A, a - 0.03, a + c["reach"] - 0.075, c["width"], c["height"], "Bronze", "Pole car",
          round_end=False)
    plate(part, at(s_c), FW, Y, A, a + c["reach"] - 0.09, a + c["reach"], 0.06, 0.07, "Bronze", "Pole car",
          round_end=False)
    V, F = deck.revolve([(0.045, -0.035), (0.045, 0.035)], Ph, UP, FW, 24)
    part.add(V, F, "Bronze", ("solid", BRZ), "Pole car")
    V, F = deck.revolve([(0.022, -0.105), (0.022, 0.105), (0.034, 0.11), (0.034, 0.125), (0.0, 0.125)], Ph, UP, FW, 20)
    part.add(V, F, "Bronze", ("solid", BRZ), "Pole car pin")
    rep["pole_heel_pin"] = Ph
    return Ph


# ------------------------------------------------------------------------------------------------ the boom
def boom_line(G, s_pin):
    """The boom's straight top line: D aft along it, N up square to it, top0 its point over the gooseneck's pin, and
    t_a how far along D from top0 it meets the mast's after face (negative: forward of the pin). E and P are measured
    from that meeting point."""
    rho_ = math.radians(RG["boom"]["rise_deg"])
    D = np.array([-math.cos(rho_), 0.0, math.sin(rho_)])          # aft along the boom
    N = np.array([math.sin(rho_), 0.0, math.cos(rho_)])           # up, square to it
    top0 = G + 0.5 * RG["boom"]["section_end"][0] * N
    t_a = (-half_depth(s_pin) - (top0 - P0) @ FW) / (D @ FW)
    return D, N, top0, t_a


def boom(part, rep, G, s_pin, E):
    """The boom from its jaw on the pin to its outhaul cap, the black band E along it from the mast's after face."""
    bm, g = RG["boom"], RG["gooseneck"]
    d_end, w_end = bm["section_end"]
    d_mid, w_mid = bm["section_mid"]
    D, N, top0, t_a = boom_line(G, s_pin)                         # the top line starts over the pin
    t_band = t_a + E
    t0 = 0.3
    t1 = t_band + RG["mast"]["black_band"]["height"] + bm["beyond_band"]
    n = bm["sides"]
    p = 2.4                                                        # the section's squareness (2 is an ellipse)

    def size(t):
        tau = (t - t0) / (t1 - t0)
        if tau < bm["mid_from"]:
            f = tau / bm["mid_from"]
        elif tau > bm["mid_to"]:
            f = (1.0 - tau) / (1.0 - bm["mid_to"])
        else:
            f = 1.0
        f = f * f * (3 - 2 * f)
        return d_end + f * (d_mid - d_end), w_end + f * (w_mid - w_end)

    def ring(t, grow=0.0):
        d, w = size(t)
        q = 2 * math.pi * np.arange(n) / n
        cz, sy = np.cos(q), np.sin(q)
        z = (0.5 * d + grow) * np.sign(cz) * np.abs(cz) ** (2 / p)
        y = (0.5 * w + grow) * np.sign(sy) * np.abs(sy) ** (2 / p)
        c = G + t * D + 0.5 * (d_end - d) * N
        return c + z[:, None] * N + y[:, None] * Y

    ts = np.unique(np.concatenate([np.arange(t0, t1, bm["ring_step"]), [t1]]))
    rings = [ring(t) for t in ts]
    V, F = deck.loft_rings(rings)
    part.add(V, F, "Spar", None, "Boom", uv=ring_uv(rings, ts - t0))
    skin, mom = 0.0, np.zeros(3)
    for ta, tb in zip(ts[:-1], ts[1:]):
        kg = 0.5 * (girth(ring(ta)) + girth(ring(tb))) * (tb - ta) * bm["wall"] * DUR
        skin += kg
        mom += kg * (G + 0.5 * (ta + tb) * D)
    cen = mom / skin
    part.masses.append({"part": "Boom skin", "kg": round(skin, 1), "centre": [round(float(v), 3) for v in cen],
                        "how": "skin"})
    part.masses.append({"part": "Boom frames, laps and rivets", "kg": round(bm["frames_fraction"] * skin, 1),
                        "centre": [round(float(v), 3) for v in cen], "how": "fraction of the skin"})
    # the jaw forward (a socket over the boom's end, a knuckle and two cheeks round the pin) and the outhaul's cap aft
    rc = 0.5 * d_end + 0.015
    V, F = deck.revolve([(0.0, 0.1), (0.06, 0.1), (0.07, 0.14), (0.09, 0.19), (rc, t0 - 0.03), (rc, t0 + 0.12),
                         (rc - 0.012, t0 + 0.135), (0.0, t0 + 0.135)], G, D, N, 32)
    part.add(V, F, "Bronze", ("cast", BRZ, 0.008, disc(rc - 0.012)), "Boom jaw socket")
    Zb = A
    Xb = unit(D - (D @ Zb) * Zb)
    for sg in (1, -1):
        o = G + sg * 0.0625 * Zb                                  # 5 mm clear of the lug above and below
        P = [(0.16, -0.055)] + [(0.055 * math.cos(q), 0.055 * math.sin(q)) for q in np.linspace(3 * math.pi / 2,
                                                                                               math.pi / 2, 11)] \
            + [(0.16, 0.055)]
        V, F = deck.slab(np.array(P), o, Xb, np.cross(Zb, Xb), Zb, -0.0175, 0.0175)
        part.add(V, F, "Bronze", ("solid", BRZ), "Boom jaw")
    V, F = deck.revolve([(rc - 0.012, t1 - 0.14), (rc, t1 - 0.125), (rc, t1 + 0.04), (0.8 * rc, t1 + 0.11),
                         (0.4 * rc, t1 + 0.14), (0.0, t1 + 0.145)], G, D, N, 32)
    part.add(V, F, "Bronze", ("cast", BRZ, 0.008, disc(rc - 0.012)), "Boom end cap")
    # bands: the black band at E, the mainsheet's bands toward the end
    bb = RG["mast"]["black_band"]["height"]

    def boom_band(tc, width, t, slot, label, rho):
        rr = [ring(tc - width / 2, -0.012), ring(tc - width / 2, t), ring(tc + width / 2, t), ring(tc + width / 2, -0.012)]
        V, F = deck.loft_rings(rr, closed=True)
        part.add(V, F, slot, None, label)
        if rho:
            part.masses.append({"part": label, "kg": round(girth(ring(tc)) * width * t * rho, 1),
                                "centre": [round(float(v), 3) for v in G + tc * D], "how": "band"})
    boom_band(t_band + bb / 2, bb, 0.0015, "Black", "Boom black band", 0)
    for x in bm["sheet_bands"]:
        boom_band(t1 - x, bm["band_width"], bm["band_thickness"], "Bronze", "Mainsheet bands", BRZ)
    # the foot's track along the top, from the jaw's socket to the black band
    tk = RG["track"]
    rr = []
    for t in np.linspace(t0 + 0.13, t_band, max(int((t_band - t0) / 0.5), 2) + 1):
        d, _ = size(t)
        top = G + t * D + 0.5 * d_end * N
        w = tk["width"] / 2
        rr.append(np.array([top - tk["let_in"] * N - w * Y, top + tk["proud"] * N - w * Y,
                            top + tk["proud"] * N + w * Y, top - tk["let_in"] * N + w * Y]))
    V, F = deck.loft_rings(rr)
    part.add(V, F, "Bronze", None, "Boom track")
    part.masses.append({"part": "Boom track", "kg": round(tk["section_area"] * (t_band - t0) * BRZ, 1),
                        "centre": [round(float(v), 3) for v in top0 + 0.5 * (t0 + t_band) * D], "how": "section"})
    part.frame = (G, Xb, Zb)
    over = t1 + 0.145 + 0.055                                     # from the jaw's cheeks round the pin to the cap
    rep["boom"] = {"length_overall_m": round(float(over), 3),
                   "length_overall_ft": round(float(over) / FT, 1),
                   "from_mast_after_face_m": round(float(t1 + 0.145 - t_a), 3),
                   "end": G + (t1 + 0.145) * D, "black_band": G + t_band * D + 0.5 * d_end * N,
                   "rise_deg": bm["rise_deg"], "section_mid": bm["section_mid"], "section_end": bm["section_end"],
                   "sheet_bands_from_aft_m": bm["sheet_bands"]}
    return t_a


# ------------------------------------------------------------------------------------------------ the pole
def pole(part, rep, Ph):
    pl = RG["pole"]
    L = pl["length"]
    phi = math.radians(pl["set_deg"])
    X = np.array([math.cos(phi), math.sin(phi), 0.0])
    re, rm = 0.5 * pl["diameter_end"], 0.5 * pl["diameter_mid"]
    ta, tb = 0.25, L - 0.2

    def r(t):
        tau = min(max((t - ta) / (tb - ta), 0.0), 1.0)
        return re + (rm - re) * math.sin(math.pi * tau) ** 0.7
    ts = np.linspace(ta, tb, 60)
    prof = [(r(t), t) for t in ts]
    V, F = deck.revolve(prof, Ph, X, UP, pl["sides"])
    part.add(V, F, "Spar", None, "Spinnaker pole")
    kg = sum(math.pi * (r(t0) + r(t1)) * (t1 - t0) * pl["wall"] * DUR for t0, t1 in zip(ts[:-1], ts[1:]))
    part.masses.append({"part": "Spinnaker pole", "kg": round(kg, 1),
                        "centre": [round(float(v), 3) for v in Ph + 0.5 * (ta + tb) * X], "how": "skin"})
    rc = re + 0.012
    V, F = deck.revolve([(0.0, 0.07), (0.045, 0.07), (0.05, 0.11), (0.09, 0.19), (rc, 0.22), (rc, 0.38),
                         (re - 0.002, 0.395)], Ph, X, UP, 32)
    part.add(V, F, "Bronze", ("cast", BRZ, 0.008, disc(re - 0.002)), "Pole heel fitting")
    for sg in (1, -1):
        o = Ph + sg * 0.0575 * UP                                 # 5 mm clear of the car's eye above and below
        P = [(0.13, -0.045)] + [(0.045 * math.cos(q), 0.045 * math.sin(q)) for q in np.linspace(3 * math.pi / 2,
                                                                                               math.pi / 2, 11)] \
            + [(0.13, 0.045)]
        V, F = deck.slab(np.array(P), o, X, np.cross(UP, X), UP, -0.0175, 0.0175)
        part.add(V, F, "Bronze", ("solid", BRZ), "Pole jaw")
    V, F = deck.revolve([(re - 0.002, L - 0.395), (rc, L - 0.38), (rc, L - 0.16), (0.07, L - 0.06), (0.05, L - 0.01),
                         (0.0, L)], Ph, X, UP, 32)
    part.add(V, F, "Bronze", ("cast", BRZ, 0.008, disc(re - 0.002)), "Pole end fitting")
    part.frame = (Ph, X, UP)
    rep["pole"] = {"length_m": L, "length_ft": round(L / FT, 1), "set_deg_from_bow": pl["set_deg"],
                   "heel_above_deck_m": pl["heel_above_deck"], "end": Ph + L * X}


# ------------------------------------------------------------------------------------------------ the whole rig
def forestay_on_mast(fh):
    """Where the forestay, from its tack at the stem head to its tang at the hounds (fh), meets the mast's forward
    face: the line run on past the tang's hole, aft and up, until it reaches the face."""
    T0 = np.array([loft.END["stem_head"][0], 0.0, loft.END["stem_head"][1]])
    fh = np.asarray(fh, float)

    def ahead(u):                                                 # how far forward of the face the line is at u
        q = T0 + u * (fh - T0)
        return float((q - P0) @ FW) - half_depth(float((q - P0) @ A))
    lo, hi = 1.0, 1.5
    if not (ahead(lo) > 0.0 > ahead(hi)):
        raise ValueError("the forestay's line does not cross the mast's forward face above its tang")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if ahead(mid) > 0.0 else (lo, mid)
    return T0 + 0.5 * (lo + hi) * (fh - T0)


def sail_measures(fh, G, s_pin, E=None):
    """I, J, P (m) on the spars as rig_bluebonnet.json's sail_area note defines them, and E from the rated sail area's
    target if not given; S in square feet. fh is the forestay's tang hole at the hounds, G the gooseneck's pin."""
    I = float(forestay_on_mast(fh)[2]) - Z_P                      # upright from the deck at the partners
    x_front = (at(0.0, half_depth(0.0)))[0]
    J = loft.END["stem_head"][0] - x_front
    D, N, top0, t_a = boom_line(G, s_pin)
    s_foot = float((top0 + t_a * D - P0) @ A)                     # the boom's top at the after face, along the mast
    P = S_TOP - M["black_band"]["below_top"] - s_foot
    fore = I * J / 2 / FT ** 2
    if E is None:
        E = 2 * (RG["sail_area"]["target_ft2"] - fore) * FT ** 2 / P
    S = P * E / 2 / FT ** 2 + fore
    return {"I_m": I, "J_m": J, "P_m": P, "E_m": E, "I_ft": I / FT, "J_ft": J / FT, "P_ft": P / FT, "E_ft": E / FT,
            "fore_triangle_ft2": fore, "main_triangle_ft2": P * E / 2 / FT ** 2, "S_ft2": S}


def rnd(v, k=3):
    if isinstance(v, dict):
        return {a: rnd(b, k) for a, b in v.items()}
    if isinstance(v, (list, tuple)):
        return [rnd(b, k) for b in v]
    if isinstance(v, np.ndarray):
        return [round(float(b), k) for b in v.ravel()] if v.ndim == 1 else [rnd(b, k) for b in v]
    if isinstance(v, float):
        return round(v, k)
    return v


def build(sheer=None):
    """{Mast, Boom, SpinnakerPole: SparPart} and a report: the sail plan's measures and rated area, the weights, the
    attachment points for slice 5 and the moving spars' frames."""
    sheer = deck.loft_sheer() if sheer is None else np.asarray(sheer, float)
    parts = {k: SparPart(k) for k in ("Mast", "Boom", "SpinnakerPole")}
    pts = {}
    mp = parts["Mast"]
    mast(mp, pts)
    partners(mp)
    s_h = hounds(mp, pts)
    spreaders(mp, pts, sheer, s_h)
    jumpers(mp, pts, s_h)
    g = RG["gooseneck"]
    track(mp, s_at(g["boom_top_above_deck"] + 0.06), pts["black_band_s"] - 0.02)
    pt = RG["track"]["pole_track"]
    track(mp, s_at(pt[0]), s_at(pt[1]), after=False, label="Pole track")
    G, s_pin = gooseneck(mp, pts)
    Ph = pole_car(mp, pts)
    meas = sail_measures(pts["forestay_hounds"], G, s_pin)
    t_a = boom(parts["Boom"], pts, G, s_pin, meas["E_m"])
    pole(parts["SpinnakerPole"], pts, Ph)
    pts["stem_head_forestay_tack"] = np.array([loft.END["stem_head"][0], 0.0, loft.END["stem_head"][1]])
    rep = {"measures": rnd(meas, 3), "sail_area_ft2": round(meas["S_ft2"], 1),
           "sail_area_measure": "P x E / 2 + I x J / 2 (rig_bluebonnet.json's sail_area note)",
           "mast": {"height_above_deck_m": H, "height_above_deck_ft": round(H / FT, 1), "rake_deg": M["rake_deg"],
                    "partners": rnd(P0), "heel": rnd(at(S_HEEL)), "truck_top": rnd(pts["truck_top"]),
                    "length_overall_m": round(S_TOP - S_HEEL, 3), "length_overall_ft": round((S_TOP - S_HEEL) / FT, 1),
                    "section_at_partners_m": [M["depth"], M["width"]],
                    "section_at_top_m": [round(M["depth"] * M["top_scale"], 3), round(M["width"] * M["top_scale"], 3)]},
           "spreaders": pts["spreaders"], "jumper_struts": pts["jumper_struts"], "boom": rnd(pts["boom"]),
           "pole": rnd(pts["pole"]),
           "attachments": rnd({k: pts[k] for k in ("forestay_hounds", "shroud_tangs", "chainplates", "spreader_tips",
                                                   "jumper_tips", "jumper_stays", "masthead_crane_tip",
                                                   "stem_head_forestay_tack", "gooseneck_pin", "pole_heel_pin")})}
    D, N, top0, t_a_ = boom_line(G, s_pin)
    rep["measure_points"] = rnd({"forestay_on_mast_face": forestay_on_mast(pts["forestay_hounds"]),
                                 "mast_forward_face_at_deck": at(0.0, half_depth(0.0)),
                                 "boom_top_at_mast_after_face": top0 + t_a_ * D,
                                 "black_band_on_mast_lower_edge": at(S_TOP - M["black_band"]["below_top"],
                                                                     -half_depth(S_TOP - M["black_band"]["below_top"])),
                                 "black_band_on_boom_forward_edge": top0 + (t_a_ + meas["E_m"]) * D})
    rep["checks"] = {"pole_no_longer_than_J": pl_ok(meas), "pole_from_mast_face_m": round(pole_from_face(), 3),
                     "boom_end_forward_of_transom_m": round(float(pts["boom"]["end"][0] - loft.END["transom_top"][0]), 3)}
    rep["weights"] = spar_weights(parts)
    return parts, rep


def pole_from_face():
    """The pole's length from the mast's forward face, set square: its pin is the car's reach forward of the face."""
    return RG["pole"]["length"] + RG["pole"]["car"]["reach"]


def pl_ok(meas):
    return bool(pole_from_face() <= meas["J_m"] + 1e-9)


NOT_THE_MASTS = ("Mast coat",)          # on the Mast object, but the deck's: left out of the 1937 minimum


def spar_weights(parts):
    """Each part's weight by piece, each spar's together, the mast with its fittings against the 1937 minimum, and
    all three against the size card's estimate for the spars."""
    out = {"rows": {}, "spars": {}}
    tot, mom = 0.0, np.zeros(3)
    for name, p in parts.items():
        agg = {}
        for r in p.masses:
            a = agg.setdefault(r["part"], {"part": r["part"], "kg": 0.0, "m": np.zeros(3), "how": r["how"], "pieces": 0})
            a["kg"] += r["kg"]
            a["m"] += r["kg"] * np.array(r["centre"])
            a["pieces"] += 1
        rows = [{"part": a["part"], "kg": round(a["kg"], 1), "centre": rnd(a["m"] / a["kg"]), "how": a["how"],
                 "pieces": a["pieces"]} for a in agg.values()]
        kg = sum(a["kg"] for a in agg.values())
        m = sum((a["m"] for a in agg.values()), np.zeros(3))
        out["rows"][name] = rows
        out["spars"][name] = {"kg": round(kg, 1), "lb": round(kg / LB_KG, 0), "centre": rnd(m / kg)}
        tot += kg
        mom += m
    # the 1937 minimum: the mast with everything fixed to it, but not the mast coat, which is the deck's
    mk = out["spars"]["Mast"]["kg"] - sum(r["kg"] for r in out["rows"]["Mast"] if r["part"] in NOT_THE_MASTS)
    out["mast_with_fittings_kg"] = round(mk, 1)
    out["mast_with_fittings_lb"] = round(mk / LB_KG, 0)
    out["mast_with_fittings_leaves_out"] = list(NOT_THE_MASTS)
    out["minimum_1937_lb"] = M["minimum_1937_lb"]
    out["meets_1937_minimum"] = bool(mk / LB_KG >= M["minimum_1937_lb"])
    zc = out["spars"]["Mast"]["centre"][2]
    out["mast_centre_above_deck_fraction"] = round((zc - Z_P) / H, 3)
    out["total_kg"] = round(tot, 1)
    out["total_long_tons"] = round(tot / deck.LT_KG, 3)
    out["centre"] = rnd(mom / tot)
    out["card_long_tons"] = loft.SPECS["weights"]["spars"]
    out["card_centre_xz"] = loft.SPECS["weight_positions"]["spars"]
    return out


if __name__ == "__main__":
    _, r = build()
    print(json.dumps({k: r[k] for k in ("measures", "sail_area_ft2", "mast", "spreaders", "jumper_struts", "boom",
                                         "pole", "checks")}, indent=1))
    w = r["weights"]
    print(json.dumps({k: w[k] for k in w if k != "rows"}, indent=1))
