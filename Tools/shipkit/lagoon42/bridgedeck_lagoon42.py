"""The Lagoon 42's bridge deck, crossbeam, centre beam, bowsprit and trampolines from bridgedeck_lagoon42.json: pure
geometry, no Blender (docs/lagoon42-3).

Everything here meets the hulls of hull_lagoon42.py: span(x, z) is the half-width of the open water between the two
hulls' inboard topsides at station x and height z, so the bridge deck's underside, its nose, the crossbeam and the
trampolines end on the hulls' own surface. build_lagoon42.py meshes them.

    python3 -I bridgedeck_lagoon42.py      prints the main numbers and writes nothing

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the game's waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_lagoon42 as H  # noqa: E402

BD = json.load(open(os.path.join(HERE, "bridgedeck_lagoon42.json")))
US, NOSE, FD = BD["underside"], BD["nose"], BD["foredeck"]
CB, CBM, SP, TR = BD["crossbeam"], BD["centre_beam"], BD["bowsprit"], BD["trampoline"]
N_BAND = 6               # columns round each fillet


def span(x, z):
    """Half-width of the gap between the hulls' inboard topsides at station x, height z (above the knuckle)."""
    return H.HULL_Y - H.topsides_y(x, z)


def deck_span(x):
    """Half-width of the gap between the hulls' inboard deck edges (the sheer) at x."""
    return H.HULL_Y - H.half_beam(x)


def deck_z(x, y):
    """The bridge deck's top at (x, y): the sheer at the hulls' edges, cambered up toward the centreline."""
    s = deck_span(x)
    t = min(abs(y) / s, 1.0) if s > 0 else 1.0
    return H.sheer_z(x) + FD["camber"] * (1 - t * t)


def nose_x(v, top=False):
    """The nose's bottom (or top) edge along x at v (-1 port hull, 0 centreline, 1 starboard hull): bowed forward."""
    x0 = NOSE["top_x"] if top else NOSE["bottom_x"]
    return x0 - NOSE["bow"] * v * v


def nose_top_z(v):
    return H.sheer_z(nose_x(v, True)) - NOSE["top_z_below_sheer"]


def nose_point(phi, v):
    """(x, z) on the nose's quarter ellipse at angle phi (0 at the underside, pi/2 at the deck's front edge)."""
    xb, xt = nose_x(v), nose_x(v, True)
    zt = nose_top_z(v)
    return xb + (xt - xb) * math.sin(phi), zt - (zt - US["z"]) * math.cos(phi)


def nose_x_at(z, v):
    """Where the nose is at height z (between the underside and the deck's front edge) at v."""
    zt = nose_top_z(v)
    c = min(max((zt - z) / (zt - US["z"]), 0.0), 1.0)
    return nose_x(v) + (nose_x(v, True) - nose_x(v)) * math.sqrt(1 - c * c)


def across(x_of_v, z_of_v, n_in, r_eff, deck=False):
    """One row of the bridge deck across the gap: [(x, y, z)] from the port hull to the starboard one. x_of_v and
    z_of_v give the row's station and base height at v; the outer N_BAND columns each side turn up into the hull
    through a fillet of radius r_eff (0: they only crowd toward the hull). deck: the base height is the cambered top."""
    r = US["fillet"]
    pts = []
    for c in range(-n_in - N_BAND, n_in + N_BAND + 1):
        if abs(c) <= n_in:
            v = c / n_in
            x, z0 = x_of_v(v), z_of_v(v)
            s = span(x, z0) if not deck else deck_span(x)
            y = v * (s - r)
            z = deck_z(x, y) if deck else z0
        else:
            sign = 1 if c > 0 else -1
            th = (abs(c) - n_in) / N_BAND * math.pi / 2
            x, z0 = x_of_v(sign), z_of_v(sign)
            s = span(x, z0) if not deck else deck_span(x)
            s1 = span(x, z0 + r_eff) if not deck else s
            y = sign * ((s - r) + (s1 - (s - r)) * math.sin(th))
            z = deck_z(x, y) if deck else z0 + r_eff * (1 - math.cos(th))
        pts.append((x, y, z))
    return pts


def bridgedeck_rows(n_in=40, n_under=90, n_nose=18, n_deck=14):
    """The bridge deck's skin as rows across, aft to forward along the underside, up the nose, then aft along the
    foredeck to the saloon's front: [[(x, y, z)]], every row the same length."""
    rows, ax, uz = [], US["aft_x"], US["z"]
    for i in range(n_under + 1):
        u = i / n_under
        rows.append(across(lambda v: ax + (nose_x(v) - ax) * u, lambda v: uz, n_in, US["fillet"]))
    for i in range(1, n_nose + 1):
        phi = math.pi / 2 * i / n_nose
        r_eff = US["fillet"] * math.cos(phi) ** 2
        rows.append(across(lambda v: nose_point(phi, v)[0], lambda v: nose_point(phi, v)[1], n_in, r_eff))
    for i in range(1, n_deck + 1):
        w = i / n_deck
        rows.append(across(lambda v: nose_x(v, True) + (FD["aft_x"] - nose_x(v, True)) * w, lambda v: 0.0, n_in, 0.0,
                           deck=True))
    return rows


def lid_rows(aft_x=None, n_in=40, n=60):
    """The placeholder lid at the sheer from the foredeck's aft edge to aft_x (the underside's aft end by default;
    slice 4 keeps it only inside the saloon, to its aft bulkhead, until slice 9 builds the saloon's floor)."""
    ax = US["aft_x"] if aft_x is None else aft_x
    n = max(4, round(n * (FD["aft_x"] - ax) / (FD["aft_x"] - US["aft_x"])))
    return [across(lambda v: FD["aft_x"] + (ax - FD["aft_x"]) * i / n, lambda v: 0.0, n_in, 0.0, deck=True)
            for i in range(n + 1)]


def aft_face(top=None, n_side=10):
    """The bridge deck's aft face at the underside's aft end: one flat outline from its port top corner down the port
    hull, round the fillet, across the underside and up the starboard hull. top: its upper edge (the sheer by default;
    slice 4's cockpit sole from then on)."""
    ax, uz, r = US["aft_x"], US["z"], US["fillet"]
    under = across(lambda v: ax, lambda v: uz, 6, r)
    at_sheer = top is None
    top = H.sheer_z(ax) if at_sheer else top
    port = [(ax, -span(ax, top - (top - (uz + r)) * k / n_side), top - (top - (uz + r)) * k / n_side) for k in range(n_side)]
    stbd = [(ax, span(ax, uz + r + (top - (uz + r)) * k / n_side), uz + r + (top - (uz + r)) * k / n_side)
            for k in range(1, n_side + 1)]
    edge = deck_span(ax) if at_sheer else span(ax, top)
    stbd[-1] = (ax, edge, top)
    port[0] = (ax, -edge, top)
    return port + under + stbd


def rounded_rect(w, h, r, n=5):
    """A rounded rectangle w x h (corner radius r) centred on the origin, counter-clockwise, as (a, b) points."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def crossbeam_ends():
    """The crossbeam's ends: 3 cm into each hull's inboard topsides at its height."""
    return span(CB["x"], CB["z"]) + 0.03


def centre_beam_ends():
    """(aft x, fore x) of the centre beam: 5 cm into the nose, to the crossbeam's middle."""
    return nose_x_at(CBM["z"], 0.0) - 0.05, CB["x"]


def bowsprit_axis(t):
    """(x, z, radius) along the bowsprit, t 0 at the crossbeam's middle and 1 at its tip."""
    return (CB["x"] + (SP["tip_x"] - CB["x"]) * t, CB["z"] + SP["rise"] * t,
            SP["root_radius"] + (SP["tip_radius"] - SP["root_radius"]) * t)


TUCK = 0.02


def trampoline_grid(side, nx=24, ny=30):
    """One trampoline (side 1 starboard, -1 port) as rows of (x, y, z): from the nose to the crossbeam's aft face, from
    the centre beam's side to the hull's inboard topsides, sagging in the middle. Its edges run TUCK into the beams
    (the beams' rounded corners leave a slot at the net's height that sunlight came through as a streak on the nose)."""
    z0 = TR["z"]
    rows = []
    for j in range(ny + 1):
        b = j / ny
        row = []
        for i in range(nx + 1):
            a = i / nx
            s_n = span(nose_x(0.0, True), z0)                        # roughly where across the gap, for the nose's bow
            v = side * (CBM["width"] / 2 + (s_n - CBM["width"] / 2) * b) / s_n
            x0 = nose_x_at(z0, v)
            x1 = CB["x"] - CB["chord"] / 2 + TUCK
            x = x0 + (x1 - x0) * a
            y0 = CBM["width"] / 2 - TUCK
            y1 = span(x, z0)
            y = side * (y0 + (y1 - y0) * b)
            z = z0 - TR["sag"] * math.sin(math.pi * a) * math.sin(math.pi * b)
            row.append((x, y, z))
        rows.append(row)
    return rows


if __name__ == "__main__":
    H.solve_depth()
    print(f"bridge deck: underside {US['z']:.2f} m over the game's waterline, from x {US['aft_x']:.2f} to the nose "
          f"{NOSE['bottom_x']:.2f}..{NOSE['top_x']:.2f}; gap between the hulls at the underside amidships "
          f"{2 * span(0.0, US['z']):.3f} m, at the nose {2 * span(NOSE['bottom_x'], US['z']):.3f} m")
    print(f"crossbeam at x {CB['x']:.2f}: {2 * span(CB['x'], CB['z']):.3f} m between the hulls; centre beam "
          f"{centre_beam_ends()[0]:.2f}..{centre_beam_ends()[1]:.2f}; trampolines from x {nose_x_at(TR['z'], 0):.2f} to "
          f"{CB['x'] - CB['chord'] / 2:.2f}; bowsprit tip {SP['tip_x']:.2f} ({SP['tip_x'] - H.TRANSOM_X:.2f} m overall)")
