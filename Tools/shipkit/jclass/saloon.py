"""Bluebonnet below decks aft (docs/jclass-10): the rooms' partitions, furniture and fittings aft of the galley, from
interior_bluebonnet.json's "aft". interior.build calls build() after the structure, the panelling, the bulkheads and
the soles, and after the forward rooms' furniture.

  partitions  the owner's end under the doghouse split by tongue-and-groove mahogany partitions: two fore and aft
              round the lobby, their lobby faces under the doghouse sill's inside face, and one across each side on
              the frame between the cabins and the bathrooms; each scribed up under whatever is over it (the
              deckhead, the uncut beams, the doghouse's forward header, the sill's lining: Overhead), with the doors'
              frames, sills, leaves and hinges
  pantry      the steward's pantry: the counter to port with its lockers and dresser, the steward's lockers and a
              second dresser to starboard (furniture.cabinet and furniture.dresser, in the pantry's white)
  saloon      the settees with their seat and back cushions, a table before each on its pedestals, chairs, the
              sideboards against the forward bulkhead, the bookcases against the after one, the book shelves over the
              settees, the lamps on the stiles, the carpet
  lobby       the companion stairs down from the doghouse's doors, the navigator's desk with its drawers, shelf,
              barometer and clock, the stool, the runner
  stateroom   the owner's berth, chest of drawers and mirror, wardrobe, carpet
  bathroom    the owner's WC, the basin's vanity and mirror, the towel rail
  guest       the guest cabin's two berths and hanging locker, its carpet; the guest heads' WC, basin and mirror

Each takes the interior's parts and adds closed solids labelled "<group> | <kind>", weighed from their geometry (the
json's densities) or, where their works are not drawn, as fixed weights (the WCs). Units are metres in the hull's
frame (X forward, Y starboard, Z up). Contacts and clearances follow furniture.py's rules: what rests on something
touches it or stands a fraction of a millimetre into it, so build_jclass's support check sees it held and its overlap
check (the furniture shrunk 1 mm) does not see it cross. Against the panelled side a piece stands off the panelling's
face by its rails' and stiles' proud (PanelSide), touching the trim where it crosses it.
"""
import math

import numpy as np

import deck
import furniture as FU
import interior as IR
import shell
from deck import box, region_slab

IN = IR.IN
WT = IR.WT
AF = IN["aft"]
X, Y, Z = np.eye(3)
J, F, U = "Aft.Joinery", "Aft.Fittings", "Aft.Upholstery"
BOARD = FU.BOARD
MAH = ("solid", WT["mahogany"])
BRASS = ("solid", WT["brass"])
PT = AF["partition"]
TP = PT["thickness"]
YL = AF["lobby_half_width"]                      # the fore-and-aft partitions' lobby faces
YC = YL + TP                                     # and their cabin faces
DR = AF["door"]
ZS = IR.RM["Aft cabins"]["sole"]
LEAF = IR.BH["leaf"]
FW, PR, SO = IR.DOOR_FW, IR.DOOR_PR, IR.SILL_OVER


def lab(group, kind):
    return f"{group} | {kind}"


def ccw(P):
    P = np.asarray(P, float)
    return P if deck.poly_area(P) > 0 else P[::-1]


def rect(u0, u1, v0, v1):
    return np.array([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], float)


def lbox(part, o, Ud, Nd, u, z, n, slot, mass, label):
    """A box in a partition's frame: u along it (Ud), z up, n across it (Nd) from the plane through o."""
    V, Fc = deck.slab(rect(u[0], u[1], z[0], z[1]), o, Ud, Z, Nd, n[0], n[1])
    part.add(V, Fc, slot, mass, label)


# ------------------------------------------------------------------------------------------------ the panelled side
class PanelSide:
    """The panelled rooms' inside face less its trim (slice 10): the panelling's face (interior.ceiling_face) in by
    the rails' and stiles' proud and 0.2 mm, by the cornice's along its band, as a half-breadth at (x, z). A piece
    stood against it touches the trim where it crosses it and stands clear of the boards between."""

    def __init__(self, hull):
        self.hull, self._c = hull, {}
        self.trim = IR.PN["rail"][1] + 0.0005
        self.cornice = IR.PN["cornice"][1] + 0.0005

    def top(self, x):
        """The panelling's top edge at x (the cornice's top), its lowest station in the run."""
        name, _ = IR.room_at(x)
        c = IR.ceiling_rows(self.hull, name, IR.run_at(name, x))
        return min(max(lo[1], hi[1]) for lo, hi, _ in c["rows"][-1][1])

    def y(self, x, z):
        k = (round(float(x), 5), round(float(z), 5))
        if k not in self._c:
            f = IR.ceiling_face(self.hull, x, z)[0]
            zc = self.top(x) - IR.PN["cornice"][0] - 0.003
            self._c[k] = f - (self.cornice if z > zc else self.trim)
        return self._c[k]

    def ymin(self, x, z0, z1, n=3):
        """The least half-breadth over z0..z1 at x: where a piece of that height stands against the side."""
        return min(self.y(x, z) for z in np.linspace(z0, z1, n))


def xs_of(x0, x1, n, gap=0.01):
    """furniture.xs_over's stations (n over x0..x1 and the ceiling's stations between), less any within `gap` of the
    last kept (the ends kept): no sliver faces where a station falls next to a frame."""
    xs = FU.xs_over(x0, x1, n)
    out = [xs[0]]
    for x in xs[1:-1]:
        if x - out[-1] >= gap and xs[-1] - x >= gap:
            out.append(x)
    return np.array(out + [xs[-1]])


def side_sheet(ps, xs, zs, off, sd):
    """A sheet of points `off` in from the panelled side over the grid xs by zs: (len(xs), len(zs), 3)."""
    return np.array([[(x, sd * (ps.y(x, z) - off), z) for z in zs] for x in xs])


def mirror_poly(P, sd):
    """Plan points with y mirrored to side sd, wound counter-clockwise."""
    P = np.asarray(P, float) * np.array([1.0, sd])
    return ccw(P)


# ------------------------------------------------------------------------------------------------ overhead
class Overhead:
    """What hangs under the deck over the cabins: the deckhead, the deck beams (cut ones from their cut outward), the
    carlins under each opening's sides, the openings' headers, and the coamings' and sills' linings (their foot
    `interior.LINING` under the deck). z(x, y) is the lowest underside over (x, y); each piece is widened 0.5 mm, so
    what is scribed under it stands that clear."""

    def __init__(self, srep, holes):
        self.pieces = []                                        # (x0, x1, y0, y1, depth under the deckhead)
        self.carlins = {k: v for k, v in srep["carlins"].items() if k != "mast"}
        W = IR.WEB
        fl = float(IR.BEAM_L[:, 0].min())
        cut = IR.opened_names()
        for xk in IR.FRAMES:
            yc = max([c for c, _ in IR.beam_cuts(xk, holes, cut)], default=0.0)
            self.pieces += [(xk + fl, xk - W, yc, 9.0, IR.BM_T), (xk - W, xk + W, yc, 9.0, IR.BM_D)]
        for what, c in srep["carlins"].items():
            x0, x1 = c["x"]
            yw = c["half_y"]
            self.pieces += [(x0, x1, yw - W, yw + W, IR.BM_D), (x0, x1, yw - W, yw - W + IR.BM_F, IR.BM_T)]
            if what == "mast":
                continue
            spec = IR.opening_spec(what)
            for xe in c.get("headers_x", []):
                if isinstance(xe, str):                     # an uncut beam is the header there: already a piece
                    continue
                s = -1.0 if xe < spec["x"] else 1.0
                fa, fb = sorted((xe + s * W, xe + s * (IR.BM_F - W)))
                self.pieces += [(xe - W, xe + W, 0.0, yw - W, IR.BM_D), (fa, fb, 0.0, yw - W, IR.BM_T)]
        self.linings = []
        for name in cut:
            spec = IR.opening_spec(name)
            self.linings.append((spec["x"], spec.get("y", 0.0), spec["length"], spec["width"],
                                 spec.get("corner", 0.0)))

    @staticmethod
    def rr_half_x(L, W, r, dy):
        """A rounded rectangle's half length at dy off its middle (None outside it)."""
        dy = abs(dy)
        if dy > W / 2:
            return None
        if dy <= W / 2 - r:
            return L / 2
        return L / 2 - r + math.sqrt(max(r * r - (dy - (W / 2 - r)) ** 2, 0.0))

    def z(self, x, y, m=0.0005):
        ya = abs(y)
        out = float(IR.deckhead_z(x, y))
        for x0, x1, y0, y1, d in self.pieces:
            if x0 - m <= x <= x1 + m and y0 - m <= ya <= y1 + m:
                out = min(out, float(IR.deckhead_z(x, y)) - d)
        for cx, cy, L, W, r in self.linings:
            hx = self.rr_half_x(L + 2 * m, W + 2 * m, r + m, y - cy)
            if hx is not None and abs(x - cx) <= hx:
                out = min(out, float(shell.deck_z(x, y)) - IR.LINING)
        return out

    def edges(self, ya, yb, x0, x1, m=0.0005):
        """The x where what is over the strip |y| in ya..yb changes, inside x0..x1."""
        out = []
        for p0, p1, q0, q1, _ in self.pieces:
            if q0 - m <= yb and ya <= q1 + m:
                out += [p0 - m, p1 + m]
        for cx, cy, L, W, r in self.linings:
            hx = self.rr_half_x(L + 2 * m, W + 2 * m, r + m, min(abs(ya - cy), abs(yb - cy)))
            if hx is not None:
                out += [cx - hx, cx + hx]
        return sorted(e for e in out if x0 + 1e-6 < e < x1 - 1e-6)


# ------------------------------------------------------------------------------------------------ partitions
def door_head(oh, us, ns, frame, h):
    """A door's head: 'height' over the sole, or 'head_clear' under the lowest of what is over its frame's width."""
    o, Ud, Nd = frame
    under = min(oh.z(*(o + u * Ud + n * Nd)[:2]) for u in us for n in ns)
    return min(ZS + h, under - DR["head_clear"] - FW)


def door(part, frame, u0, u1, z0, z1, g, opened=None, hinge_u1=False):
    """A door in a partition (its frame o, Ud along it, Nd across it, the partition 0..TP across): the frame's jambs
    and head 'proud' of both faces, the sill, the leaf on two hinges with a knob each side: shut in its frame (2 mm
    clear all round, hinged at u0, or u1 with hinge_u1), or (`opened` = (the face it opens against, along u, past
    u1)) swung through 90 degrees about the jamb at u1 and standing square to the partition, its outer edge held off
    that face by a stop."""
    o, Ud, Nd = frame
    jo = part
    for a, b in ((u0 - FW, u0), (u1, u1 + FW)):
        lbox(jo, o, Ud, Nd, (a, b), (z0, z1 + FW), (-PR, TP + PR), "Varnish", ("solid", WT["teak"]),
             lab(g, "door frame"))
    lbox(jo, o, Ud, Nd, (u0 - 0.0005, u1 + 0.0005), (z1, z1 + FW), (-PR, TP + PR), "Varnish", ("solid", WT["teak"]),
         lab(g, "door frame"))
    lbox(jo, o, Ud, Nd, (u0 - 0.0005, u1 + 0.0005), (ZS, z0), (-PR - SO, TP + PR + SO), "Varnish",
         ("solid", WT["teak"]), lab(g, "sill"))
    za, zb = z0 + 0.002, z1 - 0.002
    w = u1 - u0
    zk = ZS + 1.0
    if opened is None:
        lbox(jo, o, Ud, Nd, (u0 + 0.002, u1 - 0.002), (za, zb), (0.5 * (TP - LEAF), 0.5 * (TP + LEAF)), "Mahogany",
             MAH, lab(g, "door"))
        uh = u1 - 0.001 if hinge_u1 else u0 + 0.001
        hinges = [o + uh * Ud + 0.5 * (TP + LEAF) * Nd + zh * Z for zh in (za + 0.2, zb - 0.2)]
        uk = u0 + 0.06 if hinge_u1 else u1 - 0.06
        knobs = [(o + uk * Ud + (0.5 * (TP - LEAF)) * Nd + zk * Z, -Nd),
                 (o + uk * Ud + (0.5 * (TP + LEAF)) * Nd + zk * Z, Nd)]
        rep = {"state": "shut"}
    else:
        uf = opened                                         # the face it opens against, its knob clear of it
        ub, ua = uf - 0.035, uf - 0.035 - LEAF
        n0, n1 = TP + PR + 0.002, TP + PR + 0.002 + w - 0.004
        V, Fc = deck.slab(rect(n0, n1, za, zb), o + 0.5 * (ua + ub) * Ud, Nd, Z, Ud, -0.5 * LEAF, 0.5 * LEAF)
        jo.add(V, Fc, "Mahogany", MAH, lab(g, "door"))
        lbox(jo, o, Ud, Nd, (ub - 0.0003, uf + 0.0003), (0.5 * (za + zb) - 0.03, 0.5 * (za + zb) + 0.03),
             (n1 - 0.06, n1 - 0.02), "Varnish", ("solid", WT["teak"]), lab(g, "door stop"))
        hinges = [o + 0.5 * (ua + ub) * Ud + (TP + PR + 0.001) * Nd + zh * Z for zh in (za + 0.2, zb - 0.2)]
        knobs = [(o + ua * Ud + (n1 - 0.06) * Nd + zk * Z, -Ud), (o + ub * Ud + (n1 - 0.06) * Nd + zk * Z, Ud)]
        rep = {"state": "open", "leaf_x": [round(float((o + ua * Ud)[0]), 4), round(float((o + ub * Ud)[0]), 4)]}
    for c in hinges:
        V, Fc = deck.revolve([(0.0, -0.05), (0.006, -0.05), (0.006, 0.05), (0.0, 0.05)], c, Z, X, 12)
        jo.add(V, Fc, "Brass", BRASS, lab(g, "hinge"))
    for at, N in knobs:
        FU.knob(jo, at, N, 0.014, "Brass", lab(g, "door knob"), WT["brass"])
    rep.update({"opening_m": [round(w, 3), round(z1 - z0, 3)], "sill_z": round(z0, 3), "head_z": round(z1, 3)})
    return rep


def strips(a, b, width, keep=()):
    """Board edges from a to b about `width` apart, with each of `keep` (a door's sides) an edge."""
    edges = list(np.arange(a, b, width)[1:])
    for k in keep:
        edges = [e for e in edges if abs(e - k) > 0.03] + [k]
    edges = sorted(set([a, b] + [e for e in edges if a + 0.03 < e < b - 0.03]))
    return list(zip(edges[:-1], edges[1:]))


def fore_and_aft(part, oh, sd, side):
    """A fore-and-aft partition: from the after bulkhead to the saloon's, its lobby face YL out from the centreline,
    boards standing on the sole, each scribed up under what is over it (Overhead), round its door."""
    xa, xb = IR.room_span("Aft cabins")
    xa, xb = xa + 0.0002, xb - 0.0002                   # 0.2 mm off each bulkhead's face
    g = f"Partition, {side}"
    o, Ud, Nd = np.array([0.0, sd * YL, 0.0]), X, sd * Y
    ys = [sd * y for y in np.linspace(YL, YC, 3)]
    top = lambda x: min(oh.z(x, y) for y in ys) - 0.0005  # noqa: E731
    steps = oh.edges(YL, YC, xa, xb)
    doors = [(k, d) for k, d in AF["doors"].items() if d["side"] == sd and "x" in d]
    keep = [v for _, d in doors for v in d["x"]]
    nb = 0
    rep = {"x": [round(xa, 4), round(xb, 4)], "faces_y": [round(sd * YL, 4), round(sd * YC, 4)], "doors": {}}
    heads = {}
    for k, d in doors:
        u0, u1 = d["x"]
        heads[k] = door_head(oh, np.linspace(u0 - FW, u1 + FW, 9), (0.0, TP), (o, Ud, Nd), DR["height"])
    for u0, u1 in strips(xa, xb, PT["board"], keep):
        a = u0 if u0 <= xa + 1e-9 else u0 + 0.0005
        b = u1 if u1 >= xb - 1e-9 else u1 - 0.0005
        z_lo = ZS - 0.0003
        for k, d in doors:
            if d["x"][0] - 1e-9 <= u0 and u1 <= d["x"][1] + 1e-9:
                z_lo = heads[k]                              # over the door: from its head up
        knots = sorted(set([a, b] + [s for s in steps if a < s < b] + list(np.arange(a, b, 0.1)[1:])))
        pts = []
        for kx in knots:
            if kx in steps:
                pts += [(kx, top(kx - 1e-7)), (kx, top(kx + 1e-7))]
            else:
                pts.append((kx, top(min(max(kx, a + 1e-7), b - 1e-7))))
        P = IR.clean_poly(np.array([(a, z_lo), (b, z_lo)] + pts[::-1]))
        to3 = lambda A, t: np.column_stack([A[:, 0], np.full(len(A), sd * (YL + t)), A[:, 1]])  # noqa: E731
        V, Fc = region_slab(P, [], to3, 0.0, TP)
        part.add(V, Fc, "Mahogany", MAH, lab(g, "bulkhead"))
        nb += 1
    # a lining's rounded corner leaves the cabin face before its lobby face, where the boards' tops step up: from the
    # arc to the step the boards stand under nothing but the deckhead, so a filler there on their tops up to it
    nf, m = 0, 0.0005
    for cx, cy, L, W, r in oh.linings:
        def hx(y, L=L, W=W, r=r, cy=cy):
            return oh.rr_half_x(L + 2 * m, W + 2 * m, r + m, sd * y - cy)
        hl, hc = hx(YL), hx(YC)
        if hl is None or hc is None or hl - hc < 0.002:
            continue
        for s in (-1.0, 1.0):
            xs = cx + s * (hl - 0.0002)                 # 0.2 mm short of the step
            if not (xa < min(xs, cx + s * hc) and max(xs, cx + s * hc) < xb):
                continue
            ya, yb = YL, YC - 0.0001                    # the arc meets the step's line at ya: find it
            for _ in range(40):
                ym = 0.5 * (ya + yb)
                ya, yb = (ym, yb) if hx(ym) > hl - 0.0002 else (ya, ym)
            P = [(xs, YC - 0.0001)] + [(cx + s * hx(y), y) for y in np.linspace(YC - 0.0001, yb, 16)[:-1]]
            P = IR.clean_poly(np.array(P + [(xs, ya)]))
            xr = [float(x) for x, _ in P]
            zb = max(top(x) for x in np.linspace(min(xr), max(xr), 9)) + 0.0002
            mids = [(cx + s * 0.5 * (hx(y) + hl), y) for y in np.linspace(YL + 0.001, YC - 0.001, 5)]
            zt = min([oh.z(x, sd * y) for x, y in mids] + [float(IR.deckhead_z(x, sd * y)) for x, y in P]) - 0.0005
            to3 = lambda A, t: np.column_stack([A[:, 0], A[:, 1], np.full(len(A), t)])  # noqa: E731
            V, Fc = region_slab(mirror_poly(P, sd), [], to3, zb, zt)
            part.add(V, Fc, "Mahogany", MAH, lab(g, "bulkhead"))
            nf += 1
    for k, d in doors:
        u0, u1 = d["x"]
        opened = IR.room_span("Aft cabins")[1] if d["open"] else None
        rep["doors"][k] = door(part, (o, Ud, Nd), u0, u1, ZS + DR["sill"], heads[k], g, opened)
    rep["boards"], rep["fillers"] = nb, nf
    rep["top_z"] = [round(min(top(x) for x in np.linspace(xa, xb, 200)), 3),
                    round(max(top(x) for x in np.linspace(xa, xb, 200)), 3)]
    return rep


def across(part, hull, oh, sd, side):
    """The partition across on frame 'cross_frame' (on its forward face, as the bulkheads stand), from the
    fore-and-aft partition's cabin face out to the hull: boards up to the deckhead (as interior.bulkheads draws
    them), those under the doghouse sill's lining and the carlin cut down under them; the bathroom's door in it."""
    xk = AF["cross_frame"]
    xa_ = xk + 0.5 * IR.FR_T
    g = f"Partition {xk:.2f}, {side}"
    o, Ud, Nd = np.array([xa_, 0.0, 0.0]), sd * Y, X
    outline = IR.section_outline(hull, xa_ + TP, ZS - 0.0003, IR.ST["plating"] + 0.0015, x2=xa_, clear=0.0005)
    ymax = float(np.abs(outline[:, 0]).max())
    doors = [(k, d) for k, d in AF["doors"].items() if d["side"] == sd and "y" in d]
    keep = [abs(v) for _, d in doors for v in d["y"]]
    heads = {}
    for k, d in doors:
        u0, u1 = d["y"]
        heads[k] = door_head(oh, np.linspace(u0 - FW, u1 + FW, 9), (-0.001, TP), (o - 0.004 * X, Ud, Nd),
                             DR["height"])
    # the boards under the doghouse sill's lining and its carlin first, their edges where the lining ends (the
    # web's inside face), where the web ends and where the flange ends, then boards out to the hull
    bounds = [YC]
    for c in oh.carlins.values():
        if c["x"][0] <= xa_ <= c["x"][1] and abs(c["half_y"] - YC) < 0.05:
            bounds += [c["half_y"] - IR.WEB, c["half_y"] + IR.WEB + 0.0005, c["half_y"] - IR.WEB + IR.BM_F + 0.0005]
    rows = list(zip(bounds[:-1], bounds[1:])) + strips(bounds[-1], ymax + 0.01, IR.CE["board"] + 0.02, keep)
    nb = 0
    for y0, y1 in rows:
        cuts = []
        for k, d in doors:
            if d["y"][0] - 1e-9 <= y0 and y1 <= d["y"][1] + 1e-9:
                cuts.append((ZS - 0.01, heads[k]))           # the opening: the sill takes its foot
        Q0 = IR.board_polys(outline, y0 + 0.0005, y1 - 0.0005, cuts)
        # what is over the strip besides the deckhead (not the beam on its own frame, which it laps 0.5 mm as every
        # bulkhead does): cut the board down under it, sampled inside the board (its neighbour's piece over its edge)
        zo = min(oh.z(x, sd * y) for x in (xa_ + 0.0012, xa_ + TP) for y in np.linspace(y0 + 0.001, y1 - 0.001, 4))
        zd = min(float(IR.deckhead_z(x, sd * y)) for x in (xa_, xa_ + TP) for y in np.linspace(y0, y1, 4))
        for Q in Q0:
            if zo < zd - 0.001:
                Q = deck.clip_halfplane(Q, 0.0, 1.0, zo - 0.0005)
                if len(Q) < 3:
                    continue
            Q = Q * np.array([sd, 1.0])
            V, Fc = deck.slab(ccw(Q), o, Y, Z, X, 0.0, TP)
            part.add(V, Fc, "Mahogany", MAH, lab(g, "bulkhead"))
            nb += 1
    rep = {"x": round(xa_, 4), "boards": nb, "doors": {}}
    for k, d in doors:
        u0, u1 = d["y"]
        rep["doors"][k] = door(part, (o, Y, X), u0, u1, ZS + DR["sill"], heads[k], g)
    return rep


def partitions(parts, hull, oh):
    jo = parts[J]
    rep = {}
    for sd, side in IR.SIDES:
        rep[f"fore_and_aft_{side}"] = fore_and_aft(jo, oh, sd, side)
        rep[f"across_{side}"] = across(jo, hull, oh, sd, side)
    return rep


# ------------------------------------------------------------------------------------------------ shared pieces
def wall_unit(part, xr, yr, zr, front, g, doors=0, drawers=0, kick=(0.08, 0.04), top=0.025, over=0.012,
              kind="locker"):
    """A cabinet standing on the sole against a flat face (a partition or a bulkhead) or more: its body (weighed as
    boards: 'skin'), a kick recessed under its front, its top overhanging the front and the free ends, and `doors`
    side by side or `drawers` one over another on its front, with brass knobs. `front` is the face the doors are on:
    '+x', '-x', '+y' or '-y'. Returns the top's height."""
    (x0, x1), (y0, y1), (z0, z1) = xr, yr, zr
    ax = {"x": 0, "y": 1}[front[1]]
    sg = 1.0 if front[0] == "+" else -1.0
    lo, hi = [x0, y0], [x1, y1]
    kh, kd = kick
    # the body, from the kick's top to the top's underside; the kick set back under it
    a, b = list(lo), list(hi)
    if sg > 0:
        b[ax] -= 0.016
    else:
        a[ax] += 0.016
    zt = z1 - top
    zb0, zb1 = z0 + kh + 0.0003, zt - 0.0003            # 0.3 mm off the kick and the top: no shared edges
    V, Fc = box((0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), 0.5 * (zb0 + zb1)),
                (0.5 * (b[0] - a[0]), 0.5 * (b[1] - a[1]), 0.5 * (zb1 - zb0)))
    part.add(V, Fc, "Mahogany", ("skin", WT["mahogany"], BOARD), lab(g, kind))
    ka, kb = list(a), list(b)
    if sg > 0:
        kb[ax] -= kd
    else:
        ka[ax] += kd
    V, Fc = box((0.5 * (ka[0] + kb[0]), 0.5 * (ka[1] + kb[1]), z0 + 0.5 * kh),
                (0.5 * (kb[0] - ka[0]), 0.5 * (kb[1] - ka[1]), 0.5 * kh))
    part.add(V, Fc, "Mahogany", ("skin", WT["mahogany"], BOARD), lab(g, "kick"))      # boards round a hollow
    if top <= 0:                                        # no top of its own (a desk's pedestal under the desk's)
        top = 0.0
        rows_only = True
    else:
        rows_only = False
    # the top: out over the front
    ta, tb = list(lo), list(hi)
    if sg > 0:
        tb[ax] += over
    else:
        ta[ax] -= over
    if not rows_only:
        V, Fc = box((0.5 * (ta[0] + tb[0]), 0.5 * (ta[1] + tb[1]), zt + 0.5 * top),
                    (0.5 * (tb[0] - ta[0]), 0.5 * (tb[1] - ta[1]), 0.5 * top))
        part.add(V, Fc, "Mahogany", MAH, lab(g, "top"))
    # the doors or drawers on the front, 16 mm thick, 4 mm apart
    fa = b[ax] if sg > 0 else a[ax]                     # the body's front face
    other = 1 - ax
    u0, u1 = (a[other], b[other])
    rows = []
    if doors:
        for k in range(doors):
            rows.append((u0 + (u1 - u0) * k / doors + 0.002, u0 + (u1 - u0) * (k + 1) / doors - 0.002,
                         z0 + kh + 0.004, zt - 0.004, "door"))
    if drawers:
        for k in range(drawers):
            za = z0 + kh + (zt - z0 - kh) * k / drawers
            zb = z0 + kh + (zt - z0 - kh) * (k + 1) / drawers
            rows.append((u0 + 0.004, u1 - 0.004, za + 0.002, zb - 0.002, "drawer"))
    N = np.zeros(3)
    N[ax] = sg
    for ua, ub, za, zb, what in rows:
        c = [0.0, 0.0]
        h = [0.0, 0.0]
        c[ax], h[ax] = fa + sg * 0.008, 0.008
        c[other], h[other] = 0.5 * (ua + ub), 0.5 * (ub - ua)
        V, Fc = box((c[0], c[1], 0.5 * (za + zb)), (h[0], h[1], 0.5 * (zb - za)))
        part.add(V, Fc, "Mahogany", MAH, lab(g, what))
        at = np.zeros(3)
        at[ax] = fa + sg * 0.016
        if what == "door":
            at[other] = ub - 0.04 if (ua - u0) < 0.01 and doors > 1 else ua + 0.04
            at[2] = zb - 0.08
            ks = [at]
        else:
            at[2] = 0.5 * (za + zb)
            ks = []
            for t in ((0.25, 0.75) if ub - ua > 0.5 else (0.5,)):
                q = at.copy()
                q[other] = ua + t * (ub - ua)
                ks.append(q)
        for q in ks:
            FU.knob(part, q, N, 0.011, "Brass", lab(g, "knob"), WT["brass"])
    return z1


def books(part, rng, x0, x1, y_back, z, sd, g, h_max, d_max=0.2, y_front=None):
    """Books standing along a shelf from x0 to x1 (their backs 3 mm off y_back(x), a half-breadth; their fronts no
    further in than y_front(x)), on its top z, each a leather-bound box of its own size."""
    x, n = x0, 0
    while True:
        t = rng.uniform(0.022, 0.05)
        if x + t > x1:
            break
        h = rng.uniform(0.17, max(h_max, 0.18))
        h = min(h, h_max)
        yb = min(y_back(x), y_back(x + t)) - 0.003
        ya = yb - rng.uniform(0.13, d_max)
        if y_front is not None:
            ya = max(ya, max(y_front(x), y_front(x + t)) + 0.002)
        V, Fc = box((x + 0.5 * t, sd * 0.5 * (ya + yb), z + 0.5 * h), (0.5 * t, 0.5 * (yb - ya), 0.5 * h))
        part.add(V, Fc, "Leather", ("solid", WT["books"]), lab(g, "book"))
        x += t + 0.0012
        n += 1
    return n


def sconce(part, at, N, g, r=0.04):
    """A brass wall lamp: its backplate (radius r) on the face at `at` (N out of the face), an arm out and up, a
    porcelain shade over the lamp. Returns the lamp's centre (where the renders put its light)."""
    at, N = np.asarray(at, float), np.asarray(N, float)
    V, Fc = deck.revolve([(0.0, 0.0), (r, 0.0), (r, 0.006), (r - 0.012, 0.014), (0.0, 0.016)], at, N, Z, 16)
    part.add(V, Fc, "Brass", BRASS, lab(g, "lamp"))
    tip = at + 0.12 * N + 0.07 * Z
    V, Fc = deck.tube([at + 0.01 * N, at + 0.09 * N, at + 0.115 * N + 0.03 * Z, tip], 0.007, 10)
    part.add(V, Fc, "Brass", BRASS, lab(g, "lamp"))
    V, Fc = deck.revolve([(0.0, -0.006), (0.016, -0.006), (0.02, 0.012), (0.012, 0.03), (0.0, 0.03)], tip, Z, N, 16)
    part.add(V, Fc, "Brass", BRASS, lab(g, "lamp"))
    # the tulip shade, open at the top (a porcelain cup 5 mm thick), and the bulb in it on the holder
    cup = [(0.0, 0.0), (0.024, 0.0), (0.06, 0.07), (0.064, 0.09), (0.059, 0.09), (0.0555, 0.0735), (0.02, 0.006),
           (0.0, 0.006)]
    V, Fc = deck.revolve(cup, tip + 0.012 * Z, Z, N, 20)
    part.add(V, Fc, "Porcelain", ("solid", FU.PORCELAIN), lab(g, "lamp shade"))
    bulb = [(0.0, 0.0)] + [(0.022 * math.sin(a), 0.022 - 0.022 * math.cos(a)) for a in np.linspace(0.3, math.pi, 8)]
    V, Fc = deck.revolve(bulb, tip + 0.0175 * Z, Z, N, 16)
    part.add(V, Fc, "Bulb", ("solid", WT["glass"]), lab(g, "lamp bulb"))
    return [round(float(v), 3) for v in tip + 0.04 * Z]


def mirror(part, o, Ud, Nd, ur, zr, g):
    """A mirror on a face (o on it, Ud along it, Nd out of it): its glass in a mahogany frame, both on the face."""
    (u0, u1), (z0, z1) = ur, zr
    P = rect(u0, u1, z0, z1)
    Pi = rect(u0 + 0.03, u1 - 0.03, z0 + 0.03, z1 - 0.03)
    V, Fc = deck.ring_slab(P, Pi, o, Ud, Z, Nd, 0.0, 0.02)
    part.add(V, Fc, "Mahogany", MAH, lab(g, "mirror frame"))
    V, Fc = deck.slab(rect(u0 + 0.025, u1 - 0.025, z0 + 0.025, z1 - 0.025), o, Ud, Z, Nd, 0.0, 0.008)
    part.add(V, Fc, "Mirror", ("solid", WT["glass"]), lab(g, "mirror"))


def carpet(part, P, z0, g, t=0.008):
    """A carpet (or a runner) over the plan outline P on the sole at z0, weighed by its area."""
    P = ccw(P)
    V, Fc = deck.crowned_slab(P, lambda xx, yy: np.full(len(xx), z0), lambda xx, yy: np.full(len(xx), z0 + t),
                              0.004, 0.4)
    part.add(V, Fc, "Carpet", ("solid", WT["carpet_kg_m2"] / t), lab(g, "carpet"))
    return round(abs(deck.poly_area(P)), 2)


def cushion(part, P, z0, z1, slot, rho, label, bevel=0.025, grid=0.12):
    """A cushion, mattress or pillow over the plan outline P, flat underneath at z0, its top at z1, its edges
    rounded."""
    V, Fc = deck.crowned_slab(ccw(P), lambda xx, yy: np.full(len(xx), z0), lambda xx, yy: np.full(len(xx), z1),
                              bevel, grid)
    part.add(V, Fc, slot, ("solid", rho), label)


def strip_plan(f_in, f_out, xs, sd):
    """A plan outline between half-breadths f_in(x) and f_out(x) over the stations xs, mirrored to side sd."""
    P = [(x, f_in(x)) for x in xs] + [(x, f_out(x)) for x in xs[::-1]]
    return mirror_poly(P, sd)


def wc(parts, c, pump_dy, g):
    """A pump WC (as the crew's, furniture.washroom, with a mahogany base and no pipes through the sole): the
    porcelain pan on its base, the seat and lid, the bronze pump beside it (pump_dy athwartships of the pan's
    centre, aft of it), its lever over the pan and its pipe into it; weighed as one estimate."""
    jo, fi = parts[J], parts[F]
    wx, wy = c
    V, Fc = box((wx, wy, ZS + 0.012), (0.22, 0.2, 0.012))
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "base"))
    zb = ZS + 0.024
    V, Fc = deck.revolve([(0.0, 0.0), (0.12, 0.0), (0.125, 0.02), (0.11, 0.06), (0.12, 0.2), (0.17, 0.33),
                          (0.185, 0.36), (0.18, 0.37), (0.165, 0.365), (0.11, 0.26), (0.05, 0.19), (0.0, 0.18)],
                         (wx, wy, zb), Z, X, 28)
    fi.add(V, Fc, "Porcelain", None, lab(g, "pan"))
    zr = zb + 0.37
    V, Fc = deck.ring_slab(deck.rrect(0.0, 0.0, 0.4, 0.4, 0.19, 6), deck.rrect(0.0, 0.0, 0.25, 0.25, 0.12, 6),
                           (wx, wy, zr), X, Y, Z, 0.0, 0.022)
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "seat"))
    V, Fc = deck.slab(deck.rrect(0.0, 0.0, 0.399, 0.399, 0.1895, 6), (wx, wy, zr + 0.022), X, Y, Z, 0.0, 0.018)
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "lid"))
    pc = np.array([wx - 0.275, wy + pump_dy, ZS])
    V, Fc = deck.revolve([(0.0, 0.0), (0.05, 0.0), (0.05, 0.01), (0.035, 0.02), (0.035, 0.384), (0.045, 0.394),
                          (0.045, 0.414), (0.0, 0.424)], pc, Z, X, 16)
    fi.add(V, Fc, "Bronze", None, lab(g, "pump"))
    V, Fc = deck.tube([pc + (0.0, 0.0, 0.414), pc + (0.03, 0.0, 0.444), pc + (0.32, -0.3 * pump_dy, 0.524)], 0.01, 8)
    fi.add(V, Fc, "Bronze", None, lab(g, "lever"))
    V, Fc = deck.tube([pc + (0.0, 0.0, 0.1), pc + (0.12, 0.0, 0.1), (wx - 0.1, wy + 0.3 * pump_dy, zb + 0.12)],
                      0.014, 8)
    fi.add(V, Fc, "Bronze", None, lab(g, "pipe"))
    fi.weight(f"{g} (the pan, pump and pipes: estimated)", AF["wc"]["kg"], (wx, wy, zb + 0.2))
    return {"x": wx, "y": wy, "seat_z": round(zr + 0.04, 3), "pump": [round(float(v), 3) for v in pc[:2]]}


def basin_on(parts, cx, cy, zt, tap_dir, g):
    """A porcelain basin standing on a top at zt, its brass tap behind it (tap_dir: toward the wall)."""
    fi = parts[F]
    V, Fc = deck.revolve([(0.0, 0.0), (0.08, 0.004), (0.14, 0.036), (0.16, 0.07), (0.155, 0.075), (0.135, 0.045),
                          (0.08, 0.015), (0.0, 0.01)], (cx, cy, zt), Z, X, 24)
    fi.add(V, Fc, "Porcelain", ("solid", FU.PORCELAIN), lab(g, "basin"))
    d = np.asarray(tap_dir, float)
    tp = np.array([cx, cy, zt]) + 0.19 * d
    V, Fc = deck.tube([tp, tp + (0.0, 0.0, 0.14), tp + (0.0, 0.0, 0.15) - 0.08 * d, tp + (0.0, 0.0, 0.12) - 0.1 * d],
                      0.009, 8)
    fi.add(V, Fc, "Brass", BRASS, lab(g, "tap"))


def towel_rail(part, o, Ud, Nd, ur, z, g):
    """A brass towel rail on a face (o on it, Ud along it, Nd out of it): two arms out 6 cm and the rail between."""
    (u0, u1) = ur
    pts = []
    for u in (u0, u1):
        a = o + u * Ud + z * Z
        V, Fc = deck.revolve([(0.0, 0.0), (0.022, 0.0), (0.022, 0.008), (0.0, 0.008)], a, Nd, Z, 12)
        part.add(V, Fc, "Brass", BRASS, lab(g, "towel rail"))
        pts.append(a + 0.06 * Nd)
        V, Fc = deck.tube([a + 0.004 * Nd, a + 0.06 * Nd], 0.008, 8)
        part.add(V, Fc, "Brass", BRASS, lab(g, "towel rail"))
    V, Fc = deck.tube([pts[0] - 0.01 * Ud, pts[1] + 0.01 * Ud], 0.009, 10)
    part.add(V, Fc, "Brass", BRASS, lab(g, "towel rail"))


# ------------------------------------------------------------------------------------------------ the pantry
def pantry(parts, hull):
    """The steward's pantry, white like the galley: each side a counter of lockers with its teak top and a dresser
    with its plate rack and mugs over it (furniture.cabinet and furniture.dresser, in this room's objects)."""
    pa = AF["pantry"]
    side = FU.Side(hull)
    aparts = {FU.J: parts[J], FU.F: parts[F], FU.C: parts[U]}
    zs = IR.RM["Pantry"]["sole"]
    c = pa["counter"]
    x0, x1 = c["x"]
    zt = zs + c["height"]
    rep = {}
    for sd, sname in IR.SIDES:
        g = f"Pantry counter, {sname}"
        f = FU.front_line(side, x0, x1, zt, c["depth"], zs + 0.005)
        FU.cabinet(aparts, side, x0, x1, zs, zt - 0.025, f, sd, g, doors=3)
        xs = xs_of(x0, x1, 8)
        V, Fc = FU.plan_strip(xs, lambda x: f(x) - 0.02, lambda x: side.y(x, zt - 0.025) - 0.002, zt - 0.025, zt,
                              sd)
        parts[J].add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "top"))
        rep[sname] = {"counter_x": [x0, x1], "top_z": round(zt, 3), "front_y": [round(sd * f(x0), 3),
                                                                                round(sd * f(x1), 3)],
                      "dresser": FU.dresser(aparts, side, {"dresser": pa["dresser"]}, zt, sd,
                                            gr=f"Pantry dresser, {sname}")}
    return rep


# ------------------------------------------------------------------------------------------------ the saloon
def settee(parts, ps, sd, sname):
    """A settee against the panelled side: its mahogany front over a kick and its end boards scribed to the side,
    the seat board, three seat cushions and three back cushions against the panelling."""
    st = AF["saloon"]["settee"]
    jo, up = parts[J], parts[U]
    x0, x1 = st["x"]
    z_seat = ZS + st["seat"]
    zb = z_seat - st["cushion"]
    g = f"Saloon settee, {sname}"
    f = FU.front_line(ps, x0, x1, zb, st["depth"], ZS)
    fr = FU.Front(x0 + BOARD, x1 - BOARD, f, sd)
    kh = 0.09
    fr.panel(jo, 0.0, fr.L, ZS + kh, zb - 0.02, -BOARD, 0.0, "Mahogany", WT["mahogany"], lab(g, "front"))
    fr.panel(jo, 0.0, fr.L, ZS, ZS + kh, -0.05 - BOARD, -0.05, "Mahogany", WT["mahogany"], lab(g, "kick"))
    for x in (x0, x1 - BOARD):
        FU.board_x(jo, FU.end_board(ps, x + BOARD / 2, f(x + BOARD / 2), ZS, z_seat + 0.16), x, BOARD, sd,
                   "Mahogany", WT["mahogany"], lab(g, "end"))
    xs = xs_of(x0 + BOARD, x1 - BOARD, 10)
    V, Fc = FU.plan_strip(xs, lambda x: f(x) - 0.012, lambda x: ps.ymin(x, zb - 0.02, zb) - 0.002, zb - 0.02, zb, sd)
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "seat"))
    n = 3
    edges = np.linspace(x0 + BOARD + 0.002, x1 - BOARD - 0.002, n + 1)
    zt_back = z_seat + st["back"][1]
    for a, b in zip(edges[:-1], edges[1:]):
        a, b = a + 0.002, b - 0.002
        xc = xs_of(a, b, 6)
        xp = np.linspace(a, b, 4)                       # (few stations: a clean triangulation underneath)
        cushion(up, strip_plan(lambda x: f(x) - 0.015, lambda x: ps.ymin(x, zb, z_seat) - 0.003, xp, sd), zb, z_seat,
                "Upholstery", WT["upholstery"], lab(g, "cushion"))
        zz = np.linspace(z_seat, zt_back, 6)
        V, Fc = IR.strip_solid(side_sheet(ps, xc, zz, st["back"][0] + 0.003, sd), side_sheet(ps, xc, zz, 0.003, sd))
        up.add(V, Fc, "Upholstery", ("solid", WT["upholstery"]), lab(g, "back cushion"))
    return {"x": [x0, x1], "seat_z": round(z_seat, 3), "front_y": [round(sd * f(x0), 3), round(sd * f(x1), 3)],
            "back_top_z": round(zt_back, 3)}, f


def table(parts, cx, cy, L, W, g, z_floor):
    """A saloon table: its mahogany top with rounded corners on one or two turned pedestals (one for each 1.2 m)."""
    jo = parts[J]
    zt = ZS + AF["saloon"]["table_height"]
    cushion(jo, deck.rrect(cx, cy, L, W, 0.08, 6), zt - 0.03, zt, "Mahogany", WT["mahogany"], lab(g, "top"),
            bevel=0.008, grid=0.25)
    n = 1 if L <= 1.2 else 2
    H = zt - 0.03 - z_floor
    prof = [(0.0, 0.0), (0.22, 0.0), (0.22, 0.03), (0.13, 0.06), (0.06, 0.1), (0.045, 0.2), (0.05, H - 0.1),
            (0.075, H - 0.03), (0.075, H), (0.0, H)]
    xs = [cx] if n == 1 else [cx - L / 4, cx + L / 4]
    for px in xs:
        V, Fc = deck.revolve(prof, (px, cy, z_floor), Z, X, 24)
        jo.add(V, Fc, "Mahogany", MAH, lab(g, "pedestal"))
    return {"centre": [round(cx, 3), round(cy, 3)], "size": [L, W], "top_z": round(zt, 3), "pedestals": n}


def chair(parts, cx, cy, fy, g, z_floor):
    """A saloon chair facing fy (+1: to starboard), its legs and back of mahogany, its seat and back padded."""
    jo, up = parts[J], parts[U]
    zs = z_floor + 0.40
    hl = 0.0175
    for u in (-0.19, 0.19):
        for v in (-0.19, 0.19):
            top = z_floor + 0.86 if v * fy < 0 else zs          # the back legs run on up as the back's posts
            V, Fc = box((cx + u, cy + v, 0.5 * (z_floor + top)), (hl, hl, 0.5 * (top - z_floor)))
            jo.add(V, Fc, "Mahogany", MAH, lab(g, "leg"))
    V, Fc = box((cx, cy, zs + 0.015), (0.19 + hl, 0.19 + hl, 0.015))
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "seat frame"))
    yb = cy - fy * 0.19
    V, Fc = box((cx, yb, z_floor + 0.83), (0.19 - hl + 0.0005, hl, 0.03))
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "back rail"))
    yp = yb + fy * (hl + 0.0002)
    V, Fc = box((cx, yp + fy * 0.0125, z_floor + 0.665), (0.15, 0.0125, 0.1348))     # up to the rail
    up.add(V, Fc, "Upholstery", ("solid", WT["upholstery"]), lab(g, "back pad"))
    ya, yb2 = sorted((cy - fy * (0.19 - hl - 0.0005), cy + fy * 0.205))
    cushion(up, deck.rrect(cx, 0.5 * (ya + yb2), 0.4, yb2 - ya, 0.03, 4), zs + 0.03, zs + 0.075, "Upholstery",
            WT["upholstery"], lab(g, "cushion"), bevel=0.015, grid=0.2)


def athwart_unit(part, ps, xr, y_in, zr, sd, g, doors, shelves=None, top=0.025, kind="sideboard"):
    """A unit against a bulkhead (at whichever end of xr is the room's end) from y_in out to the panelled side,
    scribed to it: a cupboard (its body weighed as boards, a kick, `doors` on its front facing away from the
    bulkhead) or, with `shelves` (their tops over the sole, the first the plinth's), an open bookcase (an end board
    inboard, the plinth and shelves); its top overhangs a cupboard's front and inboard end. Returns its report and the
    side's half-breadth yo(z) it is scribed to."""
    (x0, x1), (z0, z1) = xr, zr
    span = IR.room_span(IR.room_at(0.5 * (x0 + x1))[0])
    xb = x1 if abs(x1 - span[1]) < 0.01 else x0         # the bulkhead's end
    front = x0 if xb == x1 else x1
    sg = -1.0 if xb == x1 else 1.0                       # the front faces aft (-1) or forward (+1)
    yo = lambda z: min(ps.y(x, z) for x in (x0, x1)) - 0.002  # noqa: E731
    zt = z1 - top

    def section(za, zb, inset=0.0):
        P = [(y_in + inset, za)] + [(yo(z), z) for z in np.linspace(za, zb, 5)] + [(y_in + inset, zb)]
        return ccw(np.array(P) * np.array([sd, 1.0]))

    def along_x(P2, xa, xb_, slot, mass, kd):
        V, Fc = deck.slab(P2, (0.0, 0.0, 0.0), Y, Z, X, min(xa, xb_), max(xa, xb_))
        part.add(V, Fc, slot, mass, lab(g, kd))
    rep = {}
    if shelves is None:
        fa = front - sg * 0.016                          # the body's front face, the doors on it
        along_x(section(z0 + 0.08, zt), fa, xb, "Mahogany", ("skin", WT["mahogany"], BOARD), kind)
        along_x(section(z0, z0 + 0.08, 0.02), front - sg * 0.05, xb, "Mahogany", ("skin", WT["mahogany"], BOARD),
                "kick")
        ys = np.linspace(y_in + 0.004, yo(z0 + 0.08) - 0.004, doors + 1)
        for k in range(doors):
            ya, yb = ys[k] + 0.002, ys[k + 1] - 0.002
            V, Fc = box((fa + sg * 0.008, sd * 0.5 * (ya + yb), 0.5 * (z0 + 0.084 + zt - 0.004)),
                        (0.008, 0.5 * (yb - ya), 0.5 * (zt - z0 - 0.088)))
            part.add(V, Fc, "Mahogany", MAH, lab(g, "door"))
            FU.knob(part, (fa + sg * 0.016, sd * (yb - 0.04 if k % 2 == 0 else ya + 0.04), zt - 0.08), sg * X,
                    0.011, "Brass", lab(g, "knob"), WT["brass"])
        ox = 0.012
    else:
        V, Fc = box((0.5 * (x0 + x1), sd * (y_in + BOARD / 2), 0.5 * (z0 + zt - 0.0003)),
                    (0.5 * (x1 - x0), BOARD / 2, 0.5 * (zt - 0.0003 - z0)))
        part.add(V, Fc, "Mahogany", MAH, lab(g, "end"))
        rep["shelves_z"] = []
        for k, h in enumerate(shelves):
            za, zb = (z0, z0 + h) if k == 0 else (z0 + h - 0.02, z0 + h)
            P = np.array([(x0, y_in + BOARD + 0.0003), (x1, y_in + BOARD + 0.0003), (x1, yo(za)), (x0, yo(za))])
            V, Fc = deck.slab(mirror_poly(P, sd), (0.0, 0.0, 0.0), X, Y, Z, za, zb)
            mass = ("skin", WT["mahogany"], BOARD) if k == 0 else MAH          # the plinth boarded round, hollow
            part.add(V, Fc, "Mahogany", mass, lab(g, "plinth" if k == 0 else "shelf"))
            rep["shelves_z"].append(round(zb, 3))
        ox = 0.0
    xa_t, xb_t = (x0 - ox, x1) if sg < 0 else (x0, x1 + ox)
    P = np.array([(xa_t, y_in - ox), (xb_t, y_in - ox), (xb_t, yo(zt)), (xa_t, yo(zt))])
    V, Fc = deck.slab(mirror_poly(P, sd), (0.0, 0.0, 0.0), X, Y, Z, zt, z1)
    part.add(V, Fc, "Mahogany", MAH, lab(g, "top"))
    rep.update({"x": [round(x0, 4), round(x1, 4)], "y": [round(sd * y_in, 3), round(sd * yo(z0), 3)],
                "top_z": round(z1, 3), "faces": "aft" if sg < 0 else "forward"})
    return rep, yo


def books_across(part, rng, y0, y1, x_back, z, sd, g, h_max, d_max):
    """Books standing across a bookcase's shelf from y0 out to y1 (half-breadths), their backs 3 mm off the bulkhead
    face x_back and their spines facing forward, on its top z."""
    y, n = y0, 0
    while True:
        t = rng.uniform(0.022, 0.05)
        if y + t > y1:
            break
        h = min(rng.uniform(0.17, max(h_max, 0.18)), h_max)
        d = rng.uniform(0.13, d_max)
        V, Fc = box((x_back + 0.003 + 0.5 * d, sd * (y + 0.5 * t), z + 0.5 * h), (0.5 * d, 0.5 * t, 0.5 * h))
        part.add(V, Fc, "Leather", ("solid", WT["books"]), lab(g, "book"))
        y += t + 0.0012
        n += 1
    return n


def saloon(parts, hull, ps):
    """The saloon: settees, tables and chairs, sideboards forward, bookcases aft, book shelves and lamps over the
    settees, the carpet."""
    sa = AF["saloon"]
    jo, fi, up = parts[J], parts[F], parts[U]
    rng = np.random.default_rng(10)
    rep = {"settees": {}, "tables": [], "lamps": [], "books": 0}
    fronts = {}
    for sd, sname in IR.SIDES:
        rep["settees"][sname], fronts[sd] = settee(parts, ps, sd, sname)
    zc = ZS + 0.008                                    # the carpet's top
    # the carpet: between the settees' kick boards, from the bookcases to the sideboards
    cx0, cx1 = sa["carpet"]["x"]
    hw = sa["carpet"]["half_width"]
    if hw > min(fronts[sd](x) for sd in (1, -1) for x in np.linspace(*sa["settee"]["x"], 9)) - 0.05 - 0.04:
        raise ValueError(f"the saloon's carpet (half-width {hw}) runs under the settees' kicks: fronts "
                         f"{[round(fronts[1](x), 3) for x in np.linspace(*sa['settee']['x'], 9)]}")
    rep["carpet_m2"] = carpet(up, deck.rrect(0.5 * (cx0 + cx1), 0.0, cx1 - cx0, 2 * hw, 0.05, 4), ZS, "Saloon carpet")
    # a table before each settee, out over its front, and chairs on its inboard side
    for t in sa["tables"]:
        sd = t["side"]
        L, W = t["size"]
        y_out = fronts[sd](t["x"]) + sa["over_seat"]
        cy = sd * (y_out - W / 2)
        g = f"Saloon table, {'starboard' if sd > 0 else 'port'}"
        rep["tables"].append(table(parts, t["x"], cy, L, W, g, zc))
        nch = 2
        for k in range(nch):
            px = t["x"] + (k - 0.5 * (nch - 1)) * min(0.62, L / nch)
            py = sd * (y_out - W - 0.12)
            chair(parts, px, py, sd, f"Saloon chair, {'starboard' if sd > 0 else 'port'} {k + 1}", zc)
    # sideboards forward, bookcases aft
    rep["sideboards"], rep["bookcases"] = {}, {}
    for sd, sname in IR.SIDES:
        s = sa["sideboard"]
        r, _ = athwart_unit(jo, ps, s["x"], s["inboard"], (ZS, ZS + s["height"]), sd, f"Saloon sideboard, {sname}",
                            3)
        rep["sideboards"][sname] = r
        b = sa["bookcase"]
        g = f"Saloon bookcase, {sname}"
        r, yo = athwart_unit(jo, ps, b["x"], b["inboard"], (ZS, ZS + b["height"]), sd, g, 0, shelves=b["shelves"],
                             kind="bookcase")
        rep["bookcases"][sname] = r
        tops = r["shelves_z"]
        unders = [t - 0.02 for t in tops[1:]] + [ZS + b["height"] - 0.025]
        for za, zb in zip(tops, unders):
            rep["books"] += books_across(fi, rng, b["inboard"] + BOARD + 0.002, yo(za) - 0.004, b["x"][0], za, sd, g,
                                         min(0.3, zb - za - 0.012), min(0.24, b["x"][1] - b["x"][0] - 0.02))
    # the book shelves over the settees, on brackets on the stiles, with a fiddle; the lamps on the stiles
    sh = sa["shelf"]
    x0, x1 = sh["x"]
    z = ZS + sh["height"]
    for sd, sname in IR.SIDES:
        g = f"Saloon shelf, {sname}"
        xs = xs_of(x0, x1, 8)
        y_out = lambda x: ps.ymin(x, z - 0.02, z)  # noqa: E731
        y_in = lambda x: y_out(x) - sh["depth"]  # noqa: E731
        V, Fc = FU.plan_strip(xs, y_in, y_out, z - 0.02, z, sd)
        jo.add(V, Fc, "Mahogany", MAH, lab(g, "shelf"))
        V, Fc = FU.plan_strip(xs, lambda x: y_in(x) + 0.0005, lambda x: y_in(x) + 0.016, z, z + 0.04, sd)
        jo.add(V, Fc, "Mahogany", MAH, lab(g, "fiddle"))
        for xf in [f for f in IR.FRAMES if x0 + 0.05 < f < x1 - 0.05]:
            zb = z - 0.02
            poly = np.array([(ps.y(xf, zb - 0.16), zb - 0.16), (ps.y(xf, zb), zb), (ps.y(xf, zb) - 0.15, zb)])
            FU.board_x(jo, poly, xf - BOARD / 2, BOARD, sd, "Mahogany", WT["mahogany"], lab(g, "bracket"))
        # the books no taller than the panelling (over the frames' knees above it), their backs off the cornice
        # where they reach up into its band
        h_max = min(0.26, min(ps.top(x) for x in np.linspace(x0, x1, 5)) - z - 0.003)
        rep["books"] += books(fi, rng, x0 + 0.02, x1 - 0.02, lambda x: ps.ymin(x, z, z + h_max), z, sd, g, h_max,
                              sh["depth"] - 0.02, y_front=lambda x: y_in(x) + 0.016)
        for xf in sa["lamps"]["frames"]:
            rep["lamps"].append(stile_lamp(fi, ps, xf, ZS + sa["lamps"]["height"], sd, f"Saloon lamp, {sname}"))
    return rep


def stile_lamp(part, ps, xf, zl, sd, g):
    """A sconce on the panelled side's stile over frame xf at zl, facing inboard: its backplate within the stile, its
    back 0.2 mm off it."""
    rl = 0.028
    yl = min(ps.y(xf + rl * math.cos(a), zl + rl * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 9))
    return sconce(part, (xf, sd * (yl + 0.0003), zl), (0.0, -sd, 0.0), g, r=rl)


# ------------------------------------------------------------------------------------------------ the lobby
def stairs(parts, holes):
    """The companion stairs from the doghouse's doors down to the sole: two teak strings leaning 'lean_deg' from
    upright, their after edges' tops against the sill's lining under the doors, teak treads let into them at an even
    rise, and a brass handrail on posts along each string's upper edge."""
    sl = AF["lobby"]["stairs"]
    jo, fi = parts[J], parts[F]
    xa = float(holes["Doghouse"][:, 0].min()) + IN["openings"]["inset"]   # the sill's lining's inside face
    z_top = float(shell.deck_z(xa, 0.0)) + deck.DK["doghouse"]["sill"]
    lean = math.radians(sl["lean_deg"])
    s_t, s_d = sl["string"]
    t_d, t_t = sl["tread"]
    w = sl["width"]
    zl = z_top - 0.004
    xf = xa + (zl - ZS) * math.tan(lean)
    wx = s_d / math.cos(lean)
    P2 = np.array([(xf, ZS), (xf + wx, ZS), (xa + wx, zl), (xa, zl)])
    g = "Companion stairs"
    nrm = np.array([math.cos(lean), 0.0, math.sin(lean)])          # out of the strings' upper edges
    up_edge = np.array([[xf + wx, 0.0, ZS], [xa + wx, 0.0, zl]])
    rr, roff = sl["rail"]
    for sg in (1.0, -1.0):
        y0 = w / 2 if sg > 0 else -(w / 2 + s_t)
        V, Fc = deck.slab(P2, (0.0, y0, 0.0), X, Z, Y, 0.0, s_t)
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "string"))
        yc = sg * (w / 2 + s_t / 2)
        on = lambda t: up_edge[0] + t * (up_edge[1] - up_edge[0]) + np.array([0.0, yc, 0.0])  # noqa: E731
        for t in (0.12, 0.5, 0.88):
            V, Fc = deck.tube([on(t) + 0.0003 * nrm, on(t) + roff * nrm], 0.008, 8)
            fi.add(V, Fc, "Brass", BRASS, lab(g, "handrail"))
        V, Fc = deck.tube([on(0.06) + roff * nrm, on(0.94) + roff * nrm], rr, 12)
        fi.add(V, Fc, "Brass", BRASS, lab(g, "handrail"))
    n = max(int(math.ceil((z_top - ZS) / sl["rise_max"] - 1e-9)), 1)
    rise = (z_top - ZS) / n
    for k in range(1, n):
        z = ZS + k * rise
        xc = xa + (zl - z) * math.tan(lean) + 0.5 * wx
        V, Fc = box((xc, 0.0, z - t_t / 2), (t_d / 2, w / 2 + 0.012, t_t / 2))
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "tread"))
    return {"top_x": round(xa, 4), "top_z": round(z_top, 3), "foot_x": [round(xf, 3), round(xf + wx, 3)],
            "rises": n, "rise_m": round(rise, 3), "width_m": w, "lean_deg": sl["lean_deg"]}


def lobby(parts, holes, ps):
    """The lobby under the doghouse: the companion stairs, the navigator's desk against the port partition (a
    pedestal of drawers forward, an end board aft, the chart drawer under its top, a shelf of pilots over it on
    brackets, the barometer and the clock), the stool, the runner, the lamps."""
    lb = AF["lobby"]
    jo, fi, up = parts[J], parts[F], parts[U]
    rep = {"stairs": stairs(parts, holes), "lamps": []}
    d = lb["desk"]
    x0, x1 = d["x"]
    zt = ZS + d["height"]
    yw, yf = -(YL - 0.0002), -(YL - d["depth"])          # the partition's face, the top's front edge
    g = "Navigator's desk"
    wall_unit(jo, (x1 - d["pedestal"], x1), (yw, yf + 0.02), (ZS, zt - 0.03), "+y", g, drawers=4, top=0.0,
              kind="pedestal")
    end_c = (x0 + BOARD / 2, 0.5 * (yw + yf + 0.02), 0.5 * (ZS + zt - 0.03))
    end_h = (BOARD / 2, 0.5 * (yf + 0.02 - yw), 0.5 * (zt - 0.03 - ZS))
    V, Fc = box(end_c, end_h)
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "end"))
    V, Fc = box((0.5 * (x0 + x1), 0.5 * (yw + yf), zt - 0.015), (0.5 * (x1 - x0), 0.5 * (yf - yw), 0.015))
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "top"))
    fiddles = [(x0, x1, yf - 0.016, yf), (x0, x0 + 0.016, yw, yf - 0.0163), (x1 - 0.016, x1, yw, yf - 0.0163)]
    for xa, xb, ya, yb in fiddles:                      # 0.3 mm over the top and apart: no shared edges
        V, Fc = box((0.5 * (xa + xb), 0.5 * (ya + yb), zt + 0.0128), (0.5 * (xb - xa), 0.5 * (yb - ya), 0.0125))
        jo.add(V, Fc, "Mahogany", MAH, lab(g, "fiddle"))
    xd0, xd1 = x0 + BOARD + 0.003, x1 - d["pedestal"] - 0.003
    V, Fc = box((0.5 * (xd0 + xd1), 0.5 * (yw + 0.002 + yf + 0.02), zt - 0.03 - 0.04),
                (0.5 * (xd1 - xd0), 0.5 * (yf + 0.02 - yw - 0.002), 0.04))
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "chart drawer"))
    for xk in (xd0 + 0.15, xd1 - 0.15):
        FU.knob(jo, (xk, yf + 0.02, zt - 0.07), Y, 0.011, "Brass", lab(g, "knob"), WT["brass"])
    # the shelf of pilot books on the partition over the desk, on two brackets; the barometer and the clock
    zsh = zt + 0.77
    sx0, sx1 = x0 + 0.05, x1 - 0.05
    V, Fc = box((0.5 * (sx0 + sx1), yw + 0.1, zsh - 0.01), (0.5 * (sx1 - sx0), 0.1, 0.01))
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "shelf"))
    V, Fc = box((0.5 * (sx0 + sx1), yw + 0.192, zsh + 0.0203), (0.5 * (sx1 - sx0), 0.008, 0.02))
    jo.add(V, Fc, "Mahogany", MAH, lab(g, "fiddle"))
    for xb in (sx0 + 0.12, sx1 - 0.12):
        poly = np.array([(YL - 0.0002, zsh - 0.02), (YL - 0.0002, zsh - 0.17), (YL - 0.15, zsh - 0.02)])
        FU.board_x(jo, poly, xb - BOARD / 2, BOARD, -1, "Mahogany", WT["mahogany"], lab(g, "bracket"))
    rng = np.random.default_rng(11)
    rep["books"] = books(fi, rng, sx0 + 0.03, sx1 - 0.03, lambda x: YL - 0.0002, zsh, -1, g, 0.27, 0.17,
                         y_front=lambda x: YL - 0.184)
    for xi, what in ((x0 + 0.33, "barometer"), (x0 + 0.62, "clock")):
        c = np.array([xi, yw, zt + 0.45])
        V, Fc = deck.revolve([(0.0, 0.0), (0.085, 0.0), (0.085, 0.03), (0.072, 0.042), (0.0, 0.042)], c, Y, Z, 24)
        fi.add(V, Fc, "Brass", BRASS, lab(g, what))
        V, Fc = deck.revolve([(0.0, 0.04), (0.066, 0.04), (0.066, 0.044), (0.0, 0.044)], c, Y, Z, 24)
        fi.add(V, Fc, "Porcelain", ("solid", FU.PORCELAIN), lab(g, what))
    rep["desk"] = {"x": [x0, x1], "y": [round(yw, 4), round(yf, 4)], "top_z": round(zt, 3),
                   "shelf_z": round(zsh, 3)}
    # the stool (its pedestal hollow brass: weighed as an estimate), the runner
    st = lb["stool"]
    sx, sy = st["at"]
    zr = ZS + 0.008
    zc = ZS + st["seat"] - 0.06                          # the seat's leather cushion, 6 cm
    if zc + 0.06 > zt - 0.03 - 0.08 - 0.15:
        raise ValueError(f"the navigator's stool's seat ({st['seat']} m) leaves no room for a knee under the chart "
                         f"drawer")
    h = zc - zr
    V, Fc = deck.revolve([(0.0, 0.0), (0.19, 0.0), (0.19, 0.015), (0.06, 0.04), (0.028, 0.08), (0.028, h - 0.03),
                          (0.06, h), (0.0, h)], (sx, sy, zr), Z, X, 20)
    fi.add(V, Fc, "Brass", None, lab("Navigator's stool", "stool"))
    fi.weight("Navigator's stool (its hollow brass pedestal: estimated)", st["kg"], (sx, sy, zr + 0.4 * h))
    cushion(up, deck.rrect(sx, sy, 0.36, 0.36, 0.17, 8), zc, zc + 0.06, "Leather", WT["upholstery"],
            lab("Navigator's stool", "seat"), bevel=0.015, grid=0.2)
    rep["stool"] = {"at": [sx, sy], "seat_z": round(zc + 0.06, 3), "under_drawer_m": round(zt - 0.11 - zc - 0.06, 3)}
    rx0, rx1 = lb["runner"]["x"]
    hw = lb["runner"]["half_width"]
    rep["runner_m2"] = carpet(up, deck.rrect(0.5 * (rx0 + rx1), 0.0, rx1 - rx0, 2 * hw, 0.04, 4), ZS, "Lobby runner")
    lp = lb["lamp"]
    rep["lamps"].append(sconce(fi, (lp["x"], YL - 0.0002, ZS + lp["height"]), (0.0, -1.0, 0.0), "Lobby lamp"))
    rep["lamps"].append(sconce(fi, (x1 - 0.12, yw, zt + d["lamp_over_top"]), (0.0, 1.0, 0.0), "Navigator's lamp"))
    return rep


# ------------------------------------------------------------------------------------------------ the cabins aft
def berth(parts, ps, xr, z_top, width, sd, g, z_end, upper=None):
    """A berth against the panelled side: its front (a lee rail 6 cm over the mattress) over a kick with two drawers,
    an end board at each end scribed to the side up to z_end, the berth board and the mattress (and the pillow at
    its after end); with `upper` (its mattress's top) a second berth over it between the same end boards, on its own
    board behind a deeper lee board. Returns the report and the front."""
    jo, up = parts[J], parts[U]
    x0, x1 = xr
    zm = z_top - 0.13
    f = FU.front_line(ps, x0, x1, zm, width, ZS)
    fr = FU.Front(x0 + BOARD, x1 - BOARD, f, sd)
    fr.panel(jo, 0.0, fr.L, ZS + 0.09, z_top + 0.06, -BOARD, 0.0, "Mahogany", WT["mahogany"], lab(g, "front"))
    fr.panel(jo, 0.0, fr.L, ZS, ZS + 0.09, -0.05 - BOARD, -0.05, "Mahogany", WT["mahogany"], lab(g, "kick"))
    for k in range(2):
        u0, u1 = k * fr.L / 2 + 0.004, (k + 1) * fr.L / 2 - 0.004
        za, zb = ZS + 0.12, zm - 0.06
        fr.panel(jo, u0, u1, za, zb, 0.0, 0.016, "Mahogany", WT["mahogany"], lab(g, "drawer"))
        for t in (0.3, 0.7):
            FU.knob(jo, fr.at(u0 + t * (u1 - u0), 0.5 * (za + zb), 0.016), fr.N, 0.011, "Brass", lab(g, "knob"),
                    WT["brass"])
    for x in (x0, x1 - BOARD):
        FU.board_x(jo, FU.end_board(ps, x + BOARD / 2, f(x + BOARD / 2), ZS, z_end), x, BOARD, sd, "Mahogany",
                   WT["mahogany"], lab(g, "end"))
    xs = xs_of(x0 + BOARD, x1 - BOARD, 10)
    tiers = [(zm, z_top, 0.0)]
    if upper is not None:
        tiers.append((upper - 0.13, upper, 0.0))
        zu = upper - 0.13
        fr.panel(jo, 0.0, fr.L, zu - 0.08, upper + 0.12, -BOARD, 0.0, "Mahogany", WT["mahogany"], lab(g, "lee board"))
    for k, (za, zb, _) in enumerate(tiers):
        V, Fc = FU.plan_strip(xs, lambda x: f(x) + BOARD, lambda x: ps.ymin(x, za - 0.02, za) - 0.002, za - 0.02,
                              za, sd)
        jo.add(V, Fc, "Mahogany", MAH, lab(g, "berth board"))
        y_out = lambda x, za=za, zb=zb: ps.ymin(x, za, zb) - 0.003  # noqa: E731
        cushion(up, strip_plan(lambda x: f(x) + BOARD + 0.003, y_out, xs, sd), za, zb, "Linen", WT["mattress"],
                lab(g, "mattress"), bevel=0.04)
        y_mid = 0.5 * (f(x0) + BOARD + ps.y(x0, za))
        wy = min(0.6, ps.y(x0, za) - f(x0) - BOARD - 0.12)
        cushion(up, deck.rrect(x0 + BOARD + 0.24, sd * y_mid, 0.36, wy, 0.06, 4), zb, zb + 0.1, "Linen",
                WT["mattress"], lab(g, "pillow"), bevel=0.04, grid=0.2)
    return {"x": [x0, x1], "mattress_tops_z": [round(t[1], 3) for t in tiers],
            "front_y": [round(sd * f(x0), 3), round(sd * f(x1), 3)]}, f


def back_of(ps, x0, x1, z0, z1):
    """The half-breadth a box standing against the panelled side from z0 to z1 can reach: 2 mm off its least."""
    return min(ps.y(x, z) for x in np.linspace(x0, x1, 3) for z in np.linspace(z0, z1, 8)) - 0.002


def stateroom(parts, ps):
    """The owner's stateroom to starboard: the berth, the chest of drawers and its mirror, the wardrobe, the carpet
    and the reading lamp on the side over the berth."""
    sr = AF["stateroom"]
    jo, fi, up = parts[J], parts[F], parts[U]
    b = sr["berth"]
    rep = {"lamps": []}
    rep["berth"], f = berth(parts, ps, b["x"], ZS + b["top"], b["width"], 1, "Owner's berth", ZS + b["top"] + 0.25)
    c = sr["chest"]
    g = "Owner's chest"
    zt = wall_unit(jo, c["x"], (YC + 0.0002, YC + c["depth"]), (ZS, ZS + c["height"]), "+y", g, drawers=4)
    mirror(fi, (0.0, YC, 0.0), X, Y, (c["x"][0] + 0.08, c["x"][1] - 0.08), (zt + 0.15, zt + 0.75), g)
    rep["chest"] = {"x": c["x"], "y": [round(YC, 4), round(YC + c["depth"], 4)], "top_z": round(zt, 3)}
    w = sr["wardrobe"]
    yb = back_of(ps, w["x"][0], w["x"][1], ZS, ZS + w["height"])
    wall_unit(jo, w["x"], (w["inboard"], yb), (ZS, ZS + w["height"]), "-y", "Owner's wardrobe", doors=2,
              kind="wardrobe")
    rep["wardrobe"] = {"x": w["x"], "y": [w["inboard"], round(yb, 3)], "top_z": round(ZS + w["height"], 3)}
    ya, yb2 = YC + c["depth"] + 0.025, min(f(x) for x in np.linspace(b["x"][0], b["x"][1], 9)) - 0.02
    xa, xb_ = b["x"][0] + 0.06, w["x"][0] - 0.06
    rep["carpet_m2"] = carpet(up, deck.rrect(0.5 * (xa + xb_), 0.5 * (ya + yb2), xb_ - xa, yb2 - ya, 0.04, 4), ZS,
                              "Owner's carpet")
    rep["lamps"].append(stile_lamp(fi, ps, sr["lamp"]["frame"], ZS + sr["lamp"]["height"], 1, "Owner's lamp"))
    return rep


def bathroom(parts, ps):
    """The owner's bathroom aft of the stateroom: the WC, the basin's vanity against the partition with its mirror
    and lamp over it, the towel rail on the partition forward."""
    br = AF["bathroom"]
    jo, fi = parts[J], parts[F]
    # the pump outboard of the pan: the vanity's forward door swings open across its inboard side
    rep = {"wc": wc(parts, (br["wc"]["x"], br["wc"]["y"]), 0.12, "Owner's WC")}
    v = br["vanity"]
    g = "Owner's basin"
    x0, x1 = v["x"]
    zt = wall_unit(jo, v["x"], (YC + 0.0002, YC + v["depth"]), (ZS, ZS + v["height"]), "+y", g, doors=2)
    basin_on(parts, 0.5 * (x0 + x1), YC + 0.5 * v["depth"], zt, (0.0, -1.0, 0.0), g)
    mirror(fi, (0.0, YC, 0.0), X, Y, (x0 + 0.05, x1 - 0.05), (zt + 0.15, zt + 0.68), g)
    rep["vanity"] = {"x": v["x"], "top_z": round(zt, 3)}
    rep["lamps"] = [sconce(fi, (0.5 * (x0 + x1), YC, zt + 0.77), Y, "Owner's bathroom lamp")]
    xa_ = AF["cross_frame"] + 0.5 * IR.FR_T
    towel_rail(fi, np.array([xa_, 0.0, 0.0]), Y, -X, (1.8, 2.1), ZS + 1.0, "Owner's towel rail")
    return rep


def guest(parts, ps):
    """The guest cabin to port: the two berths, the hanging locker, the carpet, the lamp; and the guest heads aft of
    it: the WC, the basin's cabinet against the after bulkhead with its mirror and lamp, the towel rail."""
    gc, hd = AF["guest"], AF["heads"]
    jo, fi, up = parts[J], parts[F], parts[U]
    b = gc["berths"]
    lo, hi = b["tops"]
    rep = {"lamps": []}
    rep["berths"], f = berth(parts, ps, b["x"], ZS + lo, b["width"], -1, "Guest berths", ZS + hi + 0.15,
                             upper=ZS + hi)
    lk = gc["locker"]
    yb = back_of(ps, lk["x"][0], lk["x"][1], ZS, ZS + lk["height"])
    wall_unit(jo, lk["x"], (-yb, -lk["inboard"]), (ZS, ZS + lk["height"]), "+y", "Guest locker", doors=2,
              kind="locker")
    rep["locker"] = {"x": lk["x"], "y": [round(-yb, 3), -lk["inboard"]]}
    ya, yb2 = YC + 0.025, min(f(x) for x in np.linspace(b["x"][0], b["x"][1], 9)) - 0.02
    xa, xb_ = b["x"][0] + 0.05, lk["x"][0] - 0.06
    rep["carpet_m2"] = carpet(up, deck.rrect(0.5 * (xa + xb_), -0.5 * (ya + yb2), xb_ - xa, yb2 - ya, 0.04, 4), ZS,
                              "Guest carpet")
    rep["lamps"].append(sconce(fi, (gc["lamp"]["x"], -YC, ZS + gc["lamp"]["height"]), (0.0, -1.0, 0.0),
                               "Guest lamp"))
    # the heads
    rep["wc"] = wc(parts, (hd["wc"]["x"], hd["wc"]["y"]), 0.12, "Guest WC")
    xa_ = IR.room_span("Aft cabins")[0]
    bs = hd["basin"]
    g = "Guest basin"
    ys = sorted(bs["y"])
    if -ys[0] > back_of(ps, xa_, xa_ + bs["depth"], ZS, ZS + bs["height"]):
        raise ValueError("the guest heads' basin cabinet stands outside the panelling")
    zt = wall_unit(jo, (xa_ + 0.0002, xa_ + bs["depth"]), (ys[0], ys[1] - 0.0002), (ZS, ZS + bs["height"]), "+x", g,
                   doors=2)
    yc = 0.5 * (ys[0] + ys[1])
    basin_on(parts, xa_ + 0.5 * bs["depth"], yc, zt, (-1.0, 0.0, 0.0), g)
    mirror(fi, (xa_, 0.0, 0.0), Y, X, (ys[0] + 0.06, ys[1] - 0.06), (zt + 0.15, zt + 0.65), g)
    rep["basin"] = {"x": [round(xa_, 4), round(xa_ + bs["depth"], 4)], "y": ys, "top_z": round(zt, 3)}
    rep["lamps"].append(sconce(fi, (xa_, yc, zt + 0.75), X, "Guest heads lamp"))
    xp = AF["cross_frame"] + 0.5 * IR.FR_T
    towel_rail(fi, np.array([xp, 0.0, 0.0]), Y, -X, (-1.55, -1.25), ZS + 1.0, "Guest towel rail")
    return rep


# ------------------------------------------------------------------------------------------------ the whole
def build(parts, hull, holes, srep):
    """Slice 10's rooms into the 'Aft.' objects of `parts`; `srep` is interior.structure's report (the carlins and
    headers). Returns the report, with every lamp's centre (the renders light them)."""
    oh = Overhead(srep, holes)
    ps = PanelSide(hull)
    rep = {"partitions": partitions(parts, hull, oh)}
    rep["pantry"] = pantry(parts, hull)
    rep["saloon"] = saloon(parts, hull, ps)
    rep["lobby"] = lobby(parts, holes, ps)
    rep["stateroom"] = stateroom(parts, ps)
    rep["bathroom"] = bathroom(parts, ps)
    rep["guest"] = guest(parts, ps)
    rep["lamps"] = (rep["saloon"]["lamps"] + rep["lobby"]["lamps"] + rep["stateroom"]["lamps"]
                    + rep["bathroom"]["lamps"] + rep["guest"]["lamps"])
    return rep
