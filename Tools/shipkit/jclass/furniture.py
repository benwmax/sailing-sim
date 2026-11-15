"""Bluebonnet below decks forward: the rooms' furniture and fittings (docs/jclass-9), from interior_bluebonnet.json.
interior.build calls these after the structure, ceiling, bulkheads and soles.

  mess        the fo'c'sle's table on its post with fiddles round it, and a fixed bench each side
  galley      to port: the counter's lockers and their doors, its teak top with the sink and the ice chest's lid let
              in, the range hung on gimbals in its recess with the zinc behind it, the sink's pump, and the dresser's
              shelves and plate rack over the ice chest
  bins        the slatted sail bins, their floors raised where the hull's turn would leave them too narrow, and the
              sail bags lying in them
  ladders     under the forecastle hatch and the sail hatch
  cots        the pipe cots: the frames, the canvas laced in, the hooks at the ceiling and the chains to the beams
  washroom    the pump WC, the folding basin's cabinet, the oilskin lockers
  forepeak    the chain locker's bulkhead and the platform's bearers, the hand windlass, the spurling and navel pipes,
              the cable over the gypsy and down into the locker, the stockless bower on its chocks, the bosun's
              shelves

Each takes the interior's parts ({"Below.Joinery": SparPart, ...}) and a Side (the inside face the furniture stands
against), adds closed solids labelled "<group> | <kind>", weighed from their geometry where they are drawn whole (the
json's densities) or as fixed weights where they are not (a range's works, an ice chest inside its counter, the cable
in its locker), and returns its report. Units are metres in the hull's frame (X forward, Y starboard, Z up).

Contacts and clearances. What rests on something touches it or stands a fraction of a millimetre into it (0.2 to
0.5 mm: a hook in the ceiling, a pipe in its hook, a cable link on the gypsy's shoulder), so build_jclass's support
check (interior_support: contact within 0.5 mm, every piece joined through its neighbours to the hull) sees it held
and the overlap check (interior_overlaps: the furniture shrunk 1 mm) does not see it cross. The small offsets of 2 to
6 mm are clearances between pieces that must not touch, each still held by something else it does touch; a piece
drawn off its support by more than 0.5 mm fails the build as loose or floating, so a new clearance cannot hide a
floating piece.
"""
import math

import numpy as np

import deck
import interior as IR
import shell
from deck import box, loft_rings, region_slab

IN = IR.IN
WT = IR.WT
X, Y, Z = np.eye(3)
J, F, C = "Below.Joinery", "Below.Fittings", "Below.Canvas"
IRON = WT["iron"]
BRONZE = 8600.0                                    # the deck's bronze (hardware.BRZ)
ZINC = 7140.0
PORCELAIN = 2400.0
BOARD = 0.019                                      # the joinery's boards


def lab(group, kind):
    return f"{group} | {kind}"


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# ------------------------------------------------------------------------------------------------ the inside face
class Side:
    """The inside face the furniture stands against: the ceiling's (or the galley lining's) inner face, the frames'
    inner edges carried in by a batten's thickness, as a half-breadth at (x, z)."""

    def __init__(self, hull):
        self.hull, self._c = hull, {}

    def face(self, x, bare=False):
        k = (round(float(x), 4), bare)
        if k not in self._c:
            if bare:
                self._c[k] = IR.web_edge(self.hull, x, -1.8, 3.2, step=0.02)
            else:
                pts, nn = IR.frame_edge(self.hull, x, -1.8, 3.2, step=0.02)
                self._c[k] = (pts + IR.CE["batten"][1] * nn, nn)
        return self._c[k]

    def y_at_station(self, x, z, bare=False):
        g = IR.level_point(*self.face(x, bare), z)
        return float(g[0][0]) if g else 0.0

    def y(self, x, z, bare=False):
        """The face's half-breadth at (x, z): the battens run straight between the ceiling's stations (a room's ends
        and the frames in it), so between two stations it is the line between them. `bare`: the frames' webs' own
        inner edges (IR.web_edge), where there is no ceiling (the forepeak), straight from frame to frame the same
        way: along the bevel, within a fraction of a millimetre of each web's inner edge."""
        name, _ = IR.room_at(x)
        x0, x1 = IR.room_span(name)
        if not x0 <= x <= x1:
            return self.y_at_station(x, z, bare)
        st = [x0] + [f for f in IR.FRAMES if x0 < f < x1 - 1e-6] + [x1]
        k = min(max(int(np.searchsorted(st, x)) - 1, 0), len(st) - 2)
        xa, xb = st[k], st[k + 1]
        ya, yb = self.y_at_station(xa, z, bare), self.y_at_station(xb, z, bare)
        return ya + (x - xa) / (xb - xa) * (yb - ya)

    def z_at(self, x, y):
        """The face's height where it is y out from the centreline (its lowest such point)."""
        pts, _ = self.face(x)
        k = np.where((pts[:-1, 0] - y) * (pts[1:, 0] - y) <= 0)[0]
        if len(k) == 0:
            return float(pts[0, 1])
        a, b = pts[k[0]], pts[k[0] + 1]
        t = 0.0 if b[0] == a[0] else (y - a[0]) / (b[0] - a[0])
        return float(a[1] + t * (b[1] - a[1]))


def front_line(side, x0, x1, z_ref, depth, z_floor, inner=0.0):
    """A unit's front in plan (a half-breadth for each x): straight, `depth` in from the face at z_ref at each end,
    kept inside the face at z_floor (so its front stands on the floor) and at least `inner` off the centreline."""
    ends = []
    for x in (x0, x1):
        ends.append(max(min(side.y(x, z_ref) - depth, side.y(x, z_floor) - 0.015), inner))
    f = lambda x: float(np.interp(x, [x0, x1], ends))  # noqa: E731
    for x in np.linspace(x0, x1, 9):
        if f(x) > side.y(x, z_floor) - 0.005:
            raise ValueError(f"a unit's front at x {x:.2f} stands outside the hull at its floor")
    return f


def end_board(side, x, f, z0, z1, n=12, t=BOARD):
    """A board square to x (its middle; t thick) from the front f to the face, z0 to z1: its outline in
    (half-breadth, z), 2 mm clear of the face at whichever of its two sides the face is nearer."""
    zs = np.linspace(z1, z0, n)
    return np.array([(f, z0), (f, z1)] + [(min(side.y(x - t / 2, z), side.y(x + t / 2, z)) - 0.002, z) for z in zs])


def board_x(part, poly, x, t, sd, slot, rho, label):
    """A board square to x (t thick forward of x) over its (half-breadth, z) outline, mirrored to side sd."""
    P = np.column_stack([sd * poly[:, 0], poly[:, 1]])
    V, Fc = deck.slab(P, (x, 0.0, 0.0), Y, Z, X, 0.0, t)
    part.add(V, Fc, slot, ("solid", rho) if rho else None, label)


def plan_strip(xs, y_in, y_out, z0, z1, sd):
    """A slab over the plan strip between half-breadths y_in(x) and y_out(x), z0 to z1 (z each a number or a function
    of x): a shelf, a counter's top, a bench."""
    za = (lambda x: z0) if not callable(z0) else z0
    zb = (lambda x: z1) if not callable(z1) else z1
    top = np.array([[(x, sd * y_in(x), zb(x)), (x, sd * y_out(x), zb(x))] for x in xs])
    bot = np.array([[(x, sd * y_in(x), za(x)), (x, sd * y_out(x), za(x))] for x in xs])
    return IR.strip_solid(top, bot)


def xs_over(x0, x1, n):
    """n stations x0..x1 and every ceiling station between (where the face turns), so a strip follows it."""
    st = [f for f in IR.FRAMES if x0 + 1e-6 < f < x1 - 1e-6]
    for name in IR.RM:
        if isinstance(IR.RM[name], dict) and "x" in IR.RM[name]:
            st += [e for e in IR.RM[name]["x"] if x0 + 1e-6 < e < x1 - 1e-6]
    return np.unique(np.round(np.concatenate([np.linspace(x0, x1, n), st]), 6))


class Front:
    """A straight front in plan from (x0, f0) to (x1, f1) on side sd: u along it, N its inboard normal."""

    def __init__(self, x0, x1, f, sd):
        self.x0, self.x1, self.f, self.sd = x0, x1, f, sd
        self.A = np.array([x0, sd * f(x0), 0.0])
        B = np.array([x1, sd * f(x1), 0.0])
        self.L = float(np.linalg.norm(B - self.A))
        self.U = (B - self.A) / self.L
        N = np.array([-self.U[1], self.U[0], 0.0])
        self.N = N if N[1] * -sd > 0 else -N

    def panel(self, part, u0, u1, z0, z1, t0, t1, slot, rho, label):
        """A panel in the front's plane from u0 to u1 along it, z0 to z1, t0 to t1 inboard of it."""
        P = np.array([(u0, z0), (u1, z0), (u1, z1), (u0, z1)])
        V, Fc = deck.slab(P, self.A, self.U, Z, self.N, t0, t1)
        part.add(V, Fc, slot, ("solid", rho) if rho else None, label)

    def at(self, u, z, t=0.0):
        return self.A + u * self.U + z * Z + t * self.N


def knob(part, at, N, r, slot, label, rho):
    V, Fc = deck.revolve([(0.0, 0.0), (0.4 * r, 0.0), (0.4 * r, 0.6 * r), (r, 1.1 * r), (r, 1.6 * r),
                          (0.7 * r, 2.0 * r), (0.0, 2.0 * r)], at, N, Z if abs(N[2]) < 0.9 else X, 12)
    part.add(V, Fc, slot, ("solid", rho), label)


def cabinet(parts, side, x0, x1, z0, z1, f, sd, group, doors=1, kick=(0.09, 0.05), knobs=True):
    """A run of lockers against the side from x0 to x1: its front panel (on a kick board recessed under it) and its
    doors on the front f, and an end board at each end out to the face, floor z0 to the top's underside z1. Returns
    the Front."""
    jo = parts[J]
    fr = Front(x0 + BOARD, x1 - BOARD, f, sd)
    kh, kd = kick
    label = lab(group, "locker")
    fr.panel(jo, 0.0, fr.L, z0 + kh, z1, -BOARD, 0.0, "WhitePaint", WT["pine"], label)
    if kh > 0:
        # recessed under the front, as far as the hull lets it at the floor
        room = min(side.y(x, z) - f(x) for x in np.linspace(x0 + BOARD, x1 - BOARD, 7) for z in (z0, z0 + kh))
        kd = min(kd, room - BOARD - 0.004)
        fr.panel(jo, 0.0, fr.L, z0, z0 + kh, -kd - BOARD, -kd, "WhitePaint", WT["pine"], label)
    for x, s in ((x0, 0.0), (x1 - BOARD, 0.0)):
        poly = end_board(side, x + 0.5 * BOARD, f(x + 0.5 * BOARD) - s, z0, z1)
        board_x(jo, poly, x, BOARD, sd, "WhitePaint", WT["pine"], label)
    if doors:
        n = doors
        for k in range(n):
            u0, u1 = k * fr.L / n + 0.004, (k + 1) * fr.L / n - 0.004
            za, zb = z0 + kh + 0.035, z1 - 0.035
            fr.panel(jo, u0, u1, za, zb, 0.0, 0.016, "WhitePaint", WT["pine"], lab(group, "locker door"))
            if knobs:
                knob(jo, fr.at(0.5 * (u0 + u1), zb - 0.07, 0.016), fr.N, 0.012, "Varnish", lab(group, "knob"),
                     WT["teak"])
    return fr


# ------------------------------------------------------------------------------------------------ the mess
def mess(parts, side):
    """The fo'c'sle's mess table on its centre post, fiddles round its top, and a fixed bench each side: a teak seat
    on two end boards and a back board, its front kicked in for the heels."""
    m = IN["mess"]
    jo = parts[J]
    zs = IR.RM["Fo'c'sle"]["sole"]
    x = m["x"]
    L, W, T = m["top"]
    zt = zs + m["height"]
    g = "Mess table"
    P = deck.rrect(0.0, 0.0, L, W, 0.06, 4)
    V, Fc = deck.slab(P, (x, 0.0, zt - T), X, Y, Z, 0.0, T)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "table top"))
    fd = m["fiddle"]
    Pi = deck.rrect(0.0, 0.0, L - 0.04, W - 0.04, 0.04, 4)
    Po = deck.rrect(0.0, 0.0, L - 0.001, W - 0.001, 0.0595, 4)   # half a millimetre in: no edge shared with the top
    V, Fc = deck.ring_slab(Po, Pi, (x, 0.0, zt), X, Y, Z, 0.0, fd)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "fiddle"))
    V, Fc = box((x, 0.0, 0.5 * (zs + zt - T)), (0.05, 0.05, 0.5 * (zt - T - zs)))
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "post"))
    V, Fc = box((x, 0.0, zs + 0.012), (0.2, 0.14, 0.012))
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "foot"))
    for sgn in (1.0, -1.0):                                      # the brackets under the top, fore and aft
        P2 = np.array([(0.05, zt - T), (0.42, zt - T), (0.42, zt - T - 0.03), (0.05, zt - T - 0.26)])
        V, Fc = deck.slab(np.column_stack([sgn * P2[:, 0], P2[:, 1]]), (x, -0.015, 0.0), X, Z, Y, 0.0, 0.03)
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "bracket"))
    bl, bw, bh = m["bench"]
    rep = {"top_z": round(zt, 3), "benches": []}
    for sd, side_name in IR.SIDES:
        gb = f"Mess bench, {side_name}"
        y0 = W / 2 + 0.07                                       # its inboard edge, clear of the table's edge
        y1 = y0 + bw
        for xe in (x - bl / 2, x + bl / 2 - BOARD):
            V, Fc = box((xe + BOARD / 2, sd * 0.5 * (y0 + y1 - 0.02), zs + 0.5 * (bh - 0.03)),
                        (BOARD / 2, 0.5 * (y1 - y0 - 0.02), 0.5 * (bh - 0.03)))
            jo.add(V, Fc, "WhitePaint", ("solid", WT["pine"]), lab(gb, "bench"))
        V, Fc = box((x, sd * (y1 - 0.02 - BOARD / 2), zs + 0.5 * (bh - 0.03)),
                    (bl / 2 - BOARD - 0.001, BOARD / 2, 0.5 * (bh - 0.03)))
        jo.add(V, Fc, "WhitePaint", ("solid", WT["pine"]), lab(gb, "bench"))
        V, Fc = box((x, sd * (y0 + 0.06), zs + 0.5 * (bh - 0.03 - 0.1) + 0.1),
                    (bl / 2 - BOARD - 0.001, BOARD / 2, 0.5 * (bh - 0.13)))
        jo.add(V, Fc, "WhitePaint", ("solid", WT["pine"]), lab(gb, "bench"))
        V, Fc = box((x, sd * 0.5 * (y0 + y1), zs + bh - 0.015), (bl / 2, bw / 2, 0.015))
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(gb, "seat"))
        rep["benches"].append({"side": side_name, "inboard_y": round(sd * y0, 3), "seat_z": round(zs + bh, 3)})
    rep["x"] = [round(x - L / 2, 3), round(x + L / 2, 3)]
    return rep


# ------------------------------------------------------------------------------------------------ the galley
def tray(c, L, W, depth, z_top, t, lip, r):
    """A sink or a basin let into a top whose surface is z_top: walls and bottom t thick, its hole L by W, a rim lip
    lying on the top round it. Rings of one rounded rectangle at several offsets."""
    cx, cy = c
    n = 5
    rr = lambda dl, z: np.column_stack([deck.rrect(cx, cy, L + 2 * dl, W + 2 * dl, max(r + dl, 0.006), n),  # noqa
                                        np.full(4 * (n + 1), z)])
    zb = z_top - depth
    rings = [rr(-0.002 - t, zb + t), rr(-0.002 - t, z_top + 0.004), rr(lip, z_top + 0.004), rr(lip, z_top + 0.0005),
             rr(-0.002, z_top + 0.0005), rr(-0.002, zb)]
    return loft_rings(rings)


def galley(parts, side):
    """To port, from aft: the ice chest (zinc-lined, inside the counter, its lid let into the top) under the dresser's
    shelves and plate rack, the paraffin range on its gimbals in a recess with zinc on the lining behind it, then the
    sink with its pump. The counter: lockers on a kick board, a teak top with a fiddle along its front."""
    g = IN["galley"]
    jo, fi = parts[J], parts[F]
    sd = -1
    zs = IR.RM["Galley"]["sole"]
    zt = zs + g["counter"]                                      # the top's surface
    tt = 0.03
    zc = zt - tt
    x0, x1 = g["x"]
    f = front_line(side, x0, x1, zt, g["depth"], zs + 0.005)
    rg = g["range"]
    rl, rw, rh = rg["size"]
    rx = rg["x"]
    gap = 0.07
    segs = [(x0, rx - rl / 2 - gap), (rx + rl / 2 + gap, x1)]
    rep = {"front_y": [round(sd * f(x0), 3), round(sd * f(x1), 3)], "top_z": round(zt, 3)}
    for a, b in segs:
        cabinet(parts, side, a, b, zs, zc, f, sd, "Galley counter", doors=max(int(round((b - a) / 0.48)), 1))
    # the top: from 25 mm over the front to the lining, round the sink and the ice chest's lid
    ic, sk = g["ice_chest"], g["sink"]
    lid_L, lid_W = ic["size"][0] - 0.2, 0.3
    lid_c = (ic["x"], sd * (f(ic["x"]) - 0.025 + 0.06 + lid_W / 2))
    sL, sW, sD = sk["size"]
    sk_c = (sk["x"], sd * (f(sk["x"]) - 0.025 + 0.07 + sW / 2))
    holes = {"lid": deck.rrect(lid_c[0], lid_c[1], lid_L + 0.006, lid_W + 0.006, 0.02, 3),
             "sink": deck.rrect(sk_c[0], sk_c[1], sL, sW, 0.03, 5)}
    for a, b in segs:
        xs = xs_over(a, b, max(int(math.ceil((b - a) / 0.1)), 2) + 1)
        front = [(x, sd * (f(x) - 0.025)) for x in xs]
        back = [(x, sd * (side.y(x, zc) - 0.002)) for x in xs[::-1]]
        P2 = np.array(front + back)
        hs = [h for k, h in holes.items() if a < h[:, 0].mean() < b]
        V, Fc = region_slab(P2, hs, lambda P, t: np.column_stack([P, np.full(len(P), zc + t)]), 0.0, tt, grid=0.12)
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab("Galley counter", "counter top"))
        V, Fc = plan_strip([a, b], lambda x: f(x) - 0.025, lambda x: f(x) - 0.003, zt, zt + 0.03, sd)
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab("Galley counter", "fiddle"))
    # the ice chest's lid, flush in its hole, with a bronze pull
    P = deck.rrect(lid_c[0], lid_c[1], lid_L, lid_W, 0.018, 3)
    V, Fc = deck.slab(P, (0.0, 0.0, zc), X, Y, Z, 0.0, tt)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab("Ice chest", "lid"))
    pull = np.array([lid_c[0], lid_c[1] - sd * (lid_W / 2 - 0.04), zt])
    V, Fc = deck.revolve([(0.016, 0.0), (0.022, 0.0), (0.022, 0.006), (0.016, 0.006)], pull, Z, X, 16, ring=True)
    fi.add(V, Fc, "Bronze", ("solid", BRONZE), lab("Ice chest", "pull"))
    fi.weight("Ice chest (zinc-lined, inside the counter: estimated)", ic.get("kg", 45.0),
              (ic["x"], sd * (f(ic["x"]) + 0.3), zs + 0.5 * ic["size"][2]))
    # the sink and its pump
    V, Fc = tray(sk_c, sL, sW, sD, zt, 0.003, 0.012, 0.03)
    fi.add(V, Fc, "Zinc", ("solid", ZINC), lab("Galley sink", "sink"))
    pc = np.array([sk_c[0], sk_c[1] + sd * (sW / 2 + 0.08), zt])
    V, Fc = deck.revolve([(0.0, 0.0), (0.045, 0.0), (0.045, 0.012), (0.032, 0.024), (0.032, 0.2), (0.04, 0.212),
                          (0.04, 0.232), (0.0, 0.244)], pc, Z, X, 16)
    fi.add(V, Fc, "Bronze", ("solid", 0.35 * BRONZE), lab("Galley pump", "pump"))
    V, Fc = deck.tube([pc + (0.0, 0.0, 0.17), pc + (0.0, -sd * 0.11, 0.17), pc + (0.0, -sd * 0.15, 0.13)], 0.011, 10)
    fi.add(V, Fc, "Bronze", ("solid", 0.4 * BRONZE), lab("Galley pump", "spout"))
    V, Fc = deck.tube([pc + (0.0, 0.0, 0.236), pc + (0.0, sd * 0.03, 0.255), pc + (0.0, sd * 0.2, 0.33)], 0.008, 8)
    fi.add(V, Fc, "Bronze", ("solid", BRONZE), lab("Galley pump", "handle"))
    rep["sink"] = {"x": sk["x"], "y": round(float(sk_c[1]), 3)}
    rep["range"] = range_on_gimbals(parts, side, rx, f, zt, segs, sd, zs)
    rep["dresser"] = dresser(parts, side, g, zt, sd)
    return rep


def range_on_gimbals(parts, side, rx, f, zt, segs, sd, zs):
    """The paraffin range hung on fore-and-aft pins between the counter's end boards so it stays level as she heels:
    its iron body proud of the counter, the oven door and its handle on the inboard face, two burners under a rail with
    pot clamps across, and the zinc on the lining behind. Weighed as a fixed estimate (its works are not drawn)."""
    fi = parts[F]
    rg = IN["galley"]["range"]
    rl, rw, rh = rg["size"]
    y_in = f(rx) - 0.05                                          # 50 mm proud of the counter's front
    ztop = zt + 0.01
    zb = ztop - rh
    yc = y_in + rw / 2
    g = "Galley range"
    V, Fc = box((rx, sd * yc, 0.5 * (ztop + zb)), (rl / 2, rw / 2, rh / 2))
    fi.add(V, Fc, "Black", None, lab(g, "range"))
    # the oven door, its handle and the burners
    V, Fc = box((rx, sd * (y_in - 0.006), zb + 0.21), (rl / 2 - 0.04, 0.006, 0.17))
    fi.add(V, Fc, "Black", None, lab(g, "range"))
    hy = sd * (y_in - 0.03)
    V, Fc = deck.tube([(rx - 0.2, sd * (y_in - 0.012), zb + 0.34), (rx - 0.2, hy, zb + 0.34), (rx + 0.2, hy, zb + 0.34),
                       (rx + 0.2, sd * (y_in - 0.012), zb + 0.34)], 0.007, 8)
    fi.add(V, Fc, "Bronze", None, lab(g, "handle"))
    for k in (-1, 1):
        V, Fc = deck.revolve([(0.04, 0.0), (0.065, 0.0), (0.065, 0.012), (0.04, 0.012)],
                             (rx + k * 0.15, sd * yc, ztop), Z, X, 20, ring=True)
        fi.add(V, Fc, "Black", None, lab(g, "burner"))
    # the rail round the top, its corners cut across, on a post under the middle of each cut, and two pot clamps
    # across
    hr = 0.06
    rail = [(rx + sx * (rl / 2 - 0.02), sd * (yc + sy * (rw / 2 - 0.02)), ztop + hr)
            for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    path = []
    for i in range(4):
        a, b = np.array(rail[i]), np.array(rail[(i + 1) % 4])
        path += [a + t * (b - a) for t in (0.08, 0.92)]
    V, Fc = IR.ring_tube(path, 0.007, 8)
    fi.add(V, Fc, "Bronze", None, lab(g, "rail"))
    for i in range(4):
        q = 0.5 * (path[2 * i + 1] + path[(2 * i + 2) % 8])
        V, Fc = deck.tube([(q[0], q[1], ztop), (q[0], q[1], ztop + hr)], 0.006, 8)
        fi.add(V, Fc, "Bronze", None, lab(g, "rail post"))
    for k in (-1, 1):
        V, Fc = deck.tube([(rx + k * 0.15, sd * (yc - rw / 2 + 0.02), ztop + hr + 0.001),
                           (rx + k * 0.15, sd * (yc + rw / 2 - 0.02), ztop + hr + 0.001)], 0.006, 8)
        fi.add(V, Fc, "Bronze", None, lab(g, "pot clamp"))
    # the gimbal pins and their bronze bearings on the counter's end boards
    zp = ztop - 0.12
    xa, xb = segs[0][1], segs[1][0]
    for x_end, x_brd, sgn in ((rx - rl / 2, xa, -1.0), (rx + rl / 2, xb, 1.0)):
        ln = abs(x_brd - x_end) + 0.01
        V, Fc = deck.revolve([(0.0, 0.0), (0.016, 0.0), (0.016, ln), (0.0, ln)], (x_end, sd * yc, zp), sgn * X, Z, 12)
        fi.add(V, Fc, "Iron", None, lab(g, "gimbal pin"))
        xf = x_brd if sgn > 0 else x_brd
        V, Fc = box((xf - sgn * 0.003, sd * yc, zp), (0.003, 0.05, 0.05))
        fi.add(V, Fc, "Bronze", None, lab(g, "gimbal bearing"))
    fi.weight("Paraffin range on gimbals (estimated)", rg.get("kg", 85.0), (rx, sd * yc, 0.5 * (ztop + zb)))
    # the zinc sheet nailed on the lining behind it: on the boards' faces (sampled every 3 cm, and at each frame,
    # where the boards turn), 3 mm thick
    xs = xs_over(xa + 0.02, xb - 0.02, 6)
    zz = np.linspace(zb - 0.05, ztop + 0.45, int(math.ceil((ztop + 0.5 - zb) / 0.03)) + 1)
    face = np.array([[IR.ceiling_face(side.hull, x, z)[0] - 0.0002 for z in zz] for x in xs])
    top = np.array([[(x, sd * (face[i, j] - 0.003), z) for j, z in enumerate(zz)] for i, x in enumerate(xs)])
    bot = np.array([[(x, sd * face[i, j], z) for j, z in enumerate(zz)] for i, x in enumerate(xs)])
    V, Fc = IR.strip_solid(top, bot)
    fi.add(V, Fc, "Zinc", ("solid", ZINC), lab(g, "zinc"))
    clear = min(side.y(rx + dx, z) - (yc + rw / 2) for dx in (-rl / 2, rl / 2) for z in (zb, ztop))
    return {"x": rx, "inboard_y": round(sd * y_in, 3), "top_z": round(ztop, 3), "bottom_z": round(zb, 3),
            "clear_of_lining_m": round(clear, 3), "pins_z": round(zp, 3)}


def dresser(parts, side, g, zt, sd):
    """The dresser over the ice chest: two end boards, shelves at even heights out from the lining with a fiddle along
    each, the lowest a plate rack with the plates standing in it, mugs on the next."""
    jo, fi = parts[J], parts[F]
    dx0, dx1 = g["dresser"]["x"]
    heights = g["dresser"]["shelves"]
    deep = 0.27
    z_top = zt + heights[-1] + 0.02
    gr = "Galley dresser"
    fdr = side.y(dx0, zt) - deep - 0.01
    for x in (dx0, dx1 - BOARD):
        board_x(jo, end_board(side, x + BOARD / 2, fdr, zt, z_top), x, BOARD, sd, "Varnish", WT["teak"],
                lab(gr, "dresser"))
    shelves = []
    for dz in heights:
        z = zt + dz
        xs = xs_over(dx0 + BOARD, dx1 - BOARD, 6)
        y_out = lambda x, z=z: side.y(x, z - 0.02) - 0.002  # noqa: E731
        y_in = lambda x, z=z: side.y(x, z - 0.02) - deep  # noqa: E731
        V, Fc = plan_strip(xs, y_in, y_out, z - 0.02, z, sd)
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(gr, "shelf"))
        V, Fc = plan_strip(xs, lambda x, y_in=y_in: y_in(x) + 0.0005, lambda x, y_in=y_in: y_in(x) + 0.016, z,
                           z + 0.045, sd)
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(gr, "fiddle"))
        shelves.append((z, y_in, y_out))
    # the plate rack on the lowest shelf: plates on edge standing on it between dowels, leaning back on a rail
    z, y_in, y_out = shelves[0]
    xm = np.arange(dx0 + 0.09, dx1 - 0.07, 0.05)
    pr, rr, zr = 0.1, 0.009, 0.12                             # the plates' radius; the rail's, its height
    yb = lambda x: y_out(x) - 0.015  # noqa: E731
    rail = lambda x: float(np.interp(x, [dx0 + BOARD, dx1 - BOARD], [yb(dx0), yb(dx1)]))  # noqa: E731
    # a plate's back at the rail's height: its rim is 24 straight sides from the top, so between the corners at 75 and
    # 90 degrees from it
    h = (zr - pr) / pr
    a0, a1 = math.radians(75.0), math.radians(90.0)
    tq = (math.cos(a0) - h) / (math.cos(a0) - math.cos(a1))
    back = pr * (math.sin(a0) + tq * (math.sin(a1) - math.sin(a0)))
    for k, x in enumerate(xm):
        yc = rail(x) - rr - back + 0.0003                     # touching the rail
        if yc - pr < y_in(x) + 0.041:
            raise ValueError(f"the dresser's plate at x {x:.2f} does not clear its dowels")
        c = np.array([x, sd * yc, z + pr])
        V, Fc = deck.revolve([(0.0, -0.005), (pr * 0.55, -0.005), (pr, -0.002), (pr, 0.003), (pr * 0.55, 0.0),
                              (0.0, 0.0)], c, X, Z, 24)
        fi.add(V, Fc, "Porcelain", ("solid", PORCELAIN), lab(gr, "plate"))
    for x in np.concatenate([[xm[0] - 0.025], xm + 0.025]):
        yd = y_in(x) + 0.035
        V, Fc = deck.tube([(x, sd * yd, z), (x, sd * yd, z + 0.13)], 0.006, 8)
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(gr, "dowel"))
    V, Fc = deck.tube([(dx0 + BOARD, sd * yb(dx0), z + zr), (dx1 - BOARD, sd * yb(dx1), z + zr)], rr, 8)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(gr, "rail"))
    # mugs on the middle shelf
    z, y_in, y_out = shelves[1]
    for x in np.arange(dx0 + 0.1, dx1 - 0.08, 0.11):
        c = np.array([x, sd * (0.5 * (y_in(x) + y_out(x))), z])
        V, Fc = deck.revolve([(0.0, 0.0), (0.04, 0.0), (0.042, 0.09), (0.038, 0.09), (0.035, 0.008), (0.0, 0.008)],
                             c, Z, X, 16)
        fi.add(V, Fc, "Porcelain", ("solid", PORCELAIN), lab(gr, "mug"))
    return {"x": [dx0, dx1], "shelves_z": [round(s[0], 3) for s in shelves], "plates": len(xm)}


# ------------------------------------------------------------------------------------------------ sail bins
def bag(c, half, seed, n_lat=8, n_lon=16):
    """A sail bag lying in a bin: a soft, squarish lump (a superellipsoid, flattened on top and lumpy), half sizes
    `half` (x, y, z) about c."""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 2 * math.pi, 3)
    sp = lambda c_, e: np.sign(c_) * np.abs(c_) ** e  # noqa: E731
    rings = []
    for eta in np.linspace(-0.47 * math.pi, 0.47 * math.pi, n_lat):
        w = np.linspace(-math.pi, math.pi, n_lon, endpoint=False)
        lump = 1.0 + 0.05 * np.sin(3 * w + ph[0]) + 0.03 * np.sin(5 * w + ph[1])
        r = sp(math.cos(eta), 0.55)
        px = half[0] * r * sp(np.cos(w), 0.35) * lump
        py = half[1] * r * sp(np.sin(w), 0.35) * lump
        pz = half[2] * sp(math.sin(eta), 0.6)
        if eta > 0:                                            # its top sags a little between the ends
            pz = pz - 0.18 * half[2] * (1.0 - (px / half[0]) ** 2) * math.sin(eta)
        rings.append(np.column_stack([c[0] + px, c[1] + py, np.full(n_lon, c[2]) + pz]))
    return loft_rings(rings)


def bins(parts, side):
    """Open-fronted pens of slats against the ceiling: posts along the front with a rail at the top and a board at the
    foot, slatted divisions out to the ceiling, a slatted floor (raised where the hull's turn would leave the pen too
    narrow at the sole), and sail bags lying in them."""
    b = IN["bins"]
    jo, ca = parts[J], parts[C]
    sw, st = b["slat"]
    pitch = sw + b["gap"]
    rep = []
    bag_n = 0
    for pi_, pl in enumerate(b["places"]):
        room = pl["room"]
        zs = IR.RM[room]["sole"]
        ztop = zs + b["height"]
        sd = pl["side"]
        side_name = "starboard" if sd > 0 else "port"
        x0, x1 = pl["x"]
        f = front_line(side, x0, x1, zs + 0.5 * b["height"], pl["depth"], zs + 0.005, inner=0.34)
        npen = max(int(round((x1 - x0) / 0.85)), 1)
        xd = np.linspace(x0, x1, npen + 1)
        g = f"Sail bins, {room}, {side_name}"
        for x in xd:                                           # the divisions: a post, slats out to the ceiling
            V, Fc = box((x, sd * (f(x) + 0.025), 0.5 * (zs + ztop + 0.02)), (0.025, 0.025, 0.5 * (ztop + 0.02 - zs)))
            jo.add(V, Fc, "Varnish", ("solid", WT["pine"]), lab(g, "post"))
        pens = []
        for k in range(npen):
            xa, xb = xd[k], xd[k + 1]
            # the floor: as low as leaves the pen 0.4 m deep everywhere along it
            zf = zs
            for x in np.linspace(xa, xb, 5):
                while side.y(x, zf) - f(x) < 0.4 and zf < ztop - 0.5:
                    zf += 0.02
            pens.append((xa, xb, zf))
            if zf > zs + 0.03:
                for xk in np.arange(xa + 0.06, xb - 0.04, 0.1):
                    yo = side.y(xk, zf - st) - 0.006
                    V, Fc = box((xk, sd * 0.5 * (f(xk) + 0.05 + yo), zf - st / 2),
                                (0.03, 0.5 * (yo - f(xk) - 0.05), st / 2))
                    jo.add(V, Fc, "Pine", ("solid", WT["pine"]), lab(g, "floor slat"))
                # the slats' front ends on a bearer let into the posts (behind the foot board)
                V, Fc = plan_strip([xa + 0.023, xb - 0.023], lambda x: f(x) + 0.025, lambda x: f(x) + 0.075,
                                   zf - st - 0.06, zf - st, sd)
                jo.add(V, Fc, "Varnish", ("solid", WT["pine"]), lab(g, "floor bearer"))
        for x in xd:
            zf = min(p[2] for p in pens if p[0] - 1e-6 <= x <= p[1] + 1e-6)
            nz = int((ztop - zf - 0.05) / pitch)
            for j in range(nz):
                z = zf + 0.04 + j * pitch + sw / 2
                yo = min(side.y(x - st / 2, z - sw / 2), side.y(x + st / 2, z - sw / 2)) - 0.004
                ya = f(x) + 0.05
                if yo - ya < 0.05:
                    continue
                V, Fc = box((x, sd * 0.5 * (ya + yo), z), (st / 2, 0.5 * (yo - ya), sw / 2))
                jo.add(V, Fc, "Pine", ("solid", WT["pine"]), lab(g, "bin slat"))
        # the front: a rail at the top and a board at the foot, between the posts and let into them
        for k in range(npen):
            xa, xb = xd[k] + 0.025, xd[k + 1] - 0.025
            fr = Front(xa, xb, f, sd)
            t0, t1 = -0.022, -0.002                           # in the posts' inboard half (they stand outboard of f)
            fr.panel(jo, -0.002, fr.L + 0.002, ztop - sw, ztop, t0, t1, "Varnish", WT["pine"], lab(g, "rail"))
            fr.panel(jo, -0.002, fr.L + 0.002, zs, pens[k][2] + 0.16, t0, t1, "Varnish", WT["pine"], lab(g, "rail"))
        # the bags: one or two to a pen, sized to the pen at their height
        for k, (xa, xb, zf) in enumerate(pens):
            stack = 2 if (k + pi_) % 3 != 1 else 1
            zb = zf + 0.004
            for j in range(stack):
                hz = 0.17 if stack == 2 else 0.21
                xm = 0.5 * (xa + xb)
                hx = 0.5 * (xb - xa) - 0.075 - 0.02 * j
                # its width the pen's least, square to the pen, and slanted along it as the pen follows the side in
                # (forward the hull narrows: the sail locker's pens run in 0.24 m over their length)
                xq = np.linspace(xa + 0.05, xb - 0.05, 5)
                yi_ = lambda x: f(x) + 0.06  # noqa: E731
                yo_ = lambda x, zb=zb: side.y(x, zb + 0.06) - 0.03  # noqa: E731
                wq = min(yo_(x) - yi_(x) for x in xq)
                if wq < 0.25:
                    break
                hy = 0.5 * wq
                mid = lambda x: 0.5 * (yi_(x) + yo_(x))  # noqa: E731
                slope = (mid(xq[-1]) - mid(xq[0])) / (xq[-1] - xq[0])
                V, Fc = bag((xm, sd * mid(xm), zb + hz), (hx, hy, hz), seed=100 * pi_ + 10 * k + j)
                V[:, 1] += sd * slope * (V[:, 0] - xm)
                if j == 0:                                    # the lowest lies on the floor
                    drop = float(V[:, 2].min()) - (zf + 0.0002)
                V = V - np.array([0.0, 0.0, drop])
                ca.add(V, Fc, "Canvas", None, lab(f"{g}, bag {k + 1}.{j + 1}", "sail bag"))
                bag_n += 1
                zb += 2 * hz - 0.05
        rep.append({"room": room, "side": side_name, "x": [x0, x1], "pens": npen,
                    "front_y": [round(sd * f(x0), 3), round(sd * f(x1), 3)],
                    "floors_z": [round(p[2], 3) for p in pens], "top_z": round(ztop, 3)})
    return {"places": rep, "bags": bag_n}


# ------------------------------------------------------------------------------------------------ ladders
def ladders(parts, holes):
    """A teak ladder under each hatch: its strings' after edges leaning `lean_deg` from upright with their tops
    against the hatch's after lining at the coaming's top, treads at an even rise from the sole, let into the
    strings."""
    ld = IN["ladders"]
    jo = parts[J]
    s_t, s_d = ld["string"]
    t_d, t_t = ld["tread"]
    w = ld["width"]
    lean = math.radians(ld["lean_deg"])
    rep = {}
    for name in ld["under"]:
        h = holes[name]
        xa = float(h[:, 0].min()) + IN["openings"]["inset"]     # the after lining's inside face
        hs = deck.DK["hatches"][name]
        z_top = float(shell.deck_z(xa, 0.0)) + hs["coaming"]
        # the foot: on whichever sole it lands on
        for _ in range(3):
            room, _r = IR.room_at(xa + 0.3)
            zs = None
            for nm in (room,):
                xf = xa + (z_top - (zs if zs is not None else IR.sole_at(nm, xa + 0.5))) * math.tan(lean)
                zs = IR.sole_at(nm, xf + 0.02)
            xf = xa + (z_top - zs) * math.tan(lean)
        if IR.sole_at(room, xf) != IR.sole_at(room, xf + s_d / math.cos(lean) + 0.02):
            raise ValueError(f"the ladder under the {name} lands on a step in the sole")
        wx = s_d / math.cos(lean)
        zl = z_top - 0.004                                       # the strings' tops: under the lid when it is shut
        xl = xa + 0.004 * math.tan(lean)
        P2 = np.array([(xf, zs), (xf + wx, zs), (xl + wx, zl), (xl, zl)])
        g = f"Ladder, {name}"
        for sg in (1.0, -1.0):
            y0 = sg * (w / 2) if sg > 0 else -(w / 2 + s_t)
            V, Fc = deck.slab(P2, (0.0, y0, 0.0), X, Z, Y, 0.0, s_t)
            jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "string"))
        n = max(int(math.ceil((z_top - zs) / ld["rise_max"] - 1e-9)), 1)
        rise = (z_top - zs) / n
        for k in range(1, n):
            z = zs + k * rise
            xc = xa + (z_top - z) * math.tan(lean) + 0.5 * wx
            V, Fc = box((xc, 0.0, z - t_t / 2), (t_d / 2, w / 2 + 0.012, t_t / 2))
            jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "tread"))
        rep[name] = {"room": room, "foot_x": round(xf, 3), "top_x": round(xa, 3), "sole_z": round(zs, 3),
                     "top_z": round(z_top, 3), "rises": n, "rise_m": round(rise, 3)}
    return rep


# ------------------------------------------------------------------------------------------------ cots
def stadium(c, t, n, L, W, k=4):
    """A chain link's centreline: a loop L long and W wide about c, its length along t, its width along n."""
    R = W / 2
    s = L / 2 - R
    pts = []
    for e, a0 in ((1.0, -90.0), (-1.0, 90.0)):
        for j in range(k + 1):
            a = math.radians(a0 + 180.0 * j / k)
            pts.append(c + e * s * t + R * (math.cos(a) * t + math.sin(a) * n))
    return np.array(pts)


def chain(part, path, d, slot, label, rho=None, start=0, long_link=False, fit=False):
    """A chain of links of wire diameter d along the polyline `path` (stud-less short links 5 d long and 3.5 d wide,
    or long links 7 d by 3.6 d, each turned a quarter turn on the last), the first link's outside at the path's start;
    with `fit` the links drawn a little closer (never further apart) so the last one's outside is at its end. Returns
    its length and link count."""
    P = np.asarray(path, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L, W = (7.0 * d, 3.6 * d) if long_link else (5.0 * d, 3.5 * d)
    pitch = L - 2.0 * d
    if fit:
        nl = int(math.ceil((s[-1] - L) / pitch - 1e-9)) + 1
        pitch = (s[-1] - L) / max(nl - 1, 1)
    n1 = None
    k = 0
    for sk in np.arange(0.5 * L, s[-1] - 0.5 * L + 1e-6, pitch):
        i = min(int(np.searchsorted(s, sk, side="right") - 1), len(P) - 2)
        c = P[i] + (sk - s[i]) / max(seg[i], 1e-9) * (P[i + 1] - P[i])
        t = unit(P[i + 1] - P[i])
        if n1 is None:                                        # the first link square to the path and level if it can
            n1 = unit(np.cross(t, Z if abs(t[2]) < 0.95 else X))
        else:                                                 # then carried along the path without twisting
            q_ = n1 - (n1 @ t) * t
            n1 = unit(q_) if np.linalg.norm(q_) > 0.2 else unit(np.cross(t, Z if abs(t[2]) < 0.95 else X))
        n2 = np.cross(t, n1)
        nk = n1 if (k + start) % 2 == 0 else n2
        V, Fc = IR.ring_tube(stadium(c, t, nk, L - d, W - d, 3), 0.5 * d, 4)
        part.add(V, Fc, slot, ("solid", rho) if rho else None, label)
        k += 1
    return float(s[-1]), k


def cots(parts, side, beams_x):
    """Pipe cots: a frame of galvanised pipe laced with canvas, its outboard pipe resting in hooks on the ceiling, its
    inboard pipe hung from the deck beams over it by a chain at each end, lowered for the night as drawn (they fold up
    against the ceiling by day). Each row is a cot each side, its outboard pipe straight along the ceiling at
    'off_ceiling' at the cot's ends."""
    ct = IN["cots"]
    fi, ca = parts[F], parts[C]
    r = ct["pipe"]
    w = ct["width"]
    rep = []
    for i, row in enumerate(ct["rows"]):
        room = row["room"]
        x0, x1 = row["x"]
        zs = IR.sole_at(room, x0 + 0.05)
        zc = zs + row["above_sole"]
        for sd, side_name in IR.SIDES:
            g = f"Cot, {room} {i + 1}, {side_name}"
            out = lambda x: side.y(x, zc) - ct["off_ceiling"] - r  # noqa: E731
            A0, A1 = np.array([x0, out(x0)]), np.array([x1, out(x1)])
            for x in np.linspace(x0, x1, 7):                   # the ceiling must not come in past the pipe between
                yl = float(np.interp(x, [x0, x1], [A0[1], A1[1]]))
                if side.y(x, zc) - r - 0.01 < yl:
                    raise ValueError(f"{g}: the ceiling comes in past its outboard pipe at x {x:.2f}")
            tv = unit(A1 - A0)
            wd = w / max(abs(tv[0]), 1e-6)                    # ends square across the boat, so the width along y
            B0, B1 = A0 - np.array([0.0, wd]), A1 - np.array([0.0, wd])
            corners = [A0, A1, B1, B0]
            rc = 0.07
            loop_pts = []
            for q in range(4):
                p, a, b = corners[q], corners[q - 1], corners[(q + 1) % 4]
                ua, ub = unit(a - p), unit(b - p)
                for t_ in np.linspace(0.0, 1.0, 4):           # a rounded corner (a quadratic arc)
                    qa, qb = p + rc * ua, p + rc * ub
                    loop_pts.append((1 - t_) ** 2 * qa + 2 * t_ * (1 - t_) * p + t_ ** 2 * qb)
            path = [(q[0], sd * q[1], zc) for q in loop_pts]
            V, Fc = IR.ring_tube(path, r, 10)
            fi.add(V, Fc, "Galvanised", None, lab(g, "cot frame"))
            Lp = float(sum(np.linalg.norm(np.subtract(path[k], path[k - 1])) for k in range(len(path))))
            fi.weight(f"{g} frame", WT["galvanised_pipe_kg_m"] * Lp, np.mean(path, axis=0))
            # the canvas: laced in 35 mm inside the pipes, sagging under its own weight
            m_, k_ = 12, 5
            inset = 0.035
            uu = np.linspace(0.0, 1.0, m_)
            vv = np.linspace(0.0, 1.0, k_)
            iu, iv = inset / (x1 - x0), inset / w
            top = []
            for u in uu:
                rowp = []
                for v in vv:
                    q = A0 + (iu + u * (1 - 2 * iu)) * (A1 - A0) + (iv + v * (1 - 2 * iv)) * (B0 - A0)
                    sag = 0.05 * math.sin(math.pi * u) * math.sin(math.pi * v) ** 0.7
                    rowp.append((q[0], sd * q[1], zc - sag))
                top.append(rowp)
            top = np.array(top)
            V, Fc = IR.strip_solid(top, top - np.array([0.0, 0.0, 0.004]))
            ca.add(V, Fc, "Canvas", ("top", WT["canvas_kg_m2"], 1.0), lab(g, "canvas"))
            # the lacing: a line zigzagging round the pipe and through the canvas's edge, each side; `clear`, each
            # side's points on the pipe where the lacing is out at the canvas (where the hooks and rings go)
            mid = (A0 + A1 + B0 + B1) / 4
            clear = []
            for e0, e1 in ((A0, A1), (A1, B1), (B1, B0), (B0, A0)):
                dvec = unit(e1 - e0)
                inn = unit(mid - (e0 + e1) / 2)
                inn = inn - (inn @ dvec) * dvec
                inn = unit(inn)
                Ls = float(np.linalg.norm(e1 - e0))
                npts = max(int((Ls - 2 * rc) / 0.06), 2)
                zz = []
                clear.append([])
                for j in range(npts + 1):
                    p = e0 + dvec * (rc + (Ls - 2 * rc) * j / npts)
                    if j % 2:
                        clear[-1].append(p)
                    if j % 2 == 0:                            # over the pipe's top
                        zz.append((p[0], sd * p[1], zc + r + 0.0025 - 0.0003))
                    else:                                     # through the canvas's edge, in its thickness
                        q = p + inset * inn
                        zz.append((q[0], sd * q[1], zc - 0.002))
                V, Fc = deck.tube(zz, 0.0025, 5)
                ca.add(V, Fc, "Rope", None, lab(g, "lacing"))
            # the hooks under the outboard pipe, screwed into the lowest batten over it (6 mm in): the pipe rests in
            # them (its sections have a corner straight down; a hook's eight sides leave at most 0.2 mm under it)
            rh = 0.0055
            for u in (0.18, 0.82):
                p = min(clear[0], key=lambda q, u=u: abs(q[0] - (A0[0] + u * (A1[0] - A0[0]))))
                xh = p[0]
                o = np.array([0.0, sd, 0.0])
                c3 = np.array([xh, sd * p[1], zc])
                R = r + rh - 0.0002
                za = None
                for k_ in range(len(IR.ceiling_rows(side.hull, room)["rows"])):
                    yf, _, (zlo, zhi) = IR.ceiling_face(side.hull, xh, zc, row=k_)
                    if zhi > zc + r + 0.02:
                        za = min(max(zc + 0.03, zlo + 0.012), zhi - 0.012)
                        break
                if za is None:
                    raise ValueError(f"{g}: no batten over its outboard pipe at x {xh:.2f}")
                yf = IR.ceiling_face(side.hull, xh, za)[0]
                hp = [np.array([xh, sd * (yf + 0.006), za]), c3 + R * o + (za - zc) * Z]
                for a in np.radians([0, -45, -90, -135, -180]):
                    hp.append(c3 + R * (math.cos(a) * o + math.sin(a) * Z))
                hp.append(c3 - R * o + 0.02 * Z)
                V, Fc = deck.tube(hp, rh, 8)
                fi.add(V, Fc, "Galvanised", ("solid", IRON), lab(g, "hook"))
            # the chains: from an eye under the beam over each end down to the inboard pipe
            xb_ = [x for x in beams_x if x0 + 0.12 < x < x1 - 0.12]
            ends = [min(xb_), max(xb_)] if len(xb_) >= 2 else [x0 + 0.2, x1 - 0.2]
            for xk in ends:
                yk = float(np.interp(xk, [x0, x1], [B0[1], B1[1]]))
                # the plate is flat and the beam's underside cambered: seat it under the beam's lowest point over it
                zbeam = min(float(IR.deckhead_z(xk + dx, yk + dy)) for dx in (-0.03, 0.0, 0.03)
                            for dy in (-0.03, 0.0, 0.03)) - IR.BM_D - 0.0005
                V, Fc = deck.revolve([(0.0, 0.0), (0.03, 0.0), (0.03, 0.006), (0.0, 0.006)],
                                     (xk, sd * yk, zbeam - 0.006), Z, X, 12)
                fi.add(V, Fc, "Galvanised", ("solid", IRON), lab(g, "eye plate"))
                V, Fc = IR.ring_tube(stadium(np.array([xk, sd * yk, zbeam - 0.0275]), Z, X, 0.036, 0.026), 0.004, 6)
                fi.add(V, Fc, "Galvanised", ("solid", IRON), lab(g, "eye"))
                # a ring round the inboard pipe (between the lacing's turns), the chain's last link through its top
                pr_ = min(clear[2], key=lambda q, xk=xk: abs(q[0] - xk))
                dv = unit(B1 - B0)
                ac = np.array([-dv[1], dv[0]])
                rg_ = r + 0.0025 - 0.0003
                across = np.array([ac[0], sd * ac[1], 0.0])
                rc3 = np.array([pr_[0], sd * pr_[1], zc])
                ring = [rc3 + rg_ * (math.cos(a) * Z + math.sin(a) * across)
                        for a in np.linspace(0.0, 2 * math.pi, 16, endpoint=False)]
                V, Fc = IR.ring_tube(ring, 0.0025, 6)
                fi.add(V, Fc, "Galvanised", ("solid", IRON), lab(g, "chain ring"))
                chain(fi, [(xk, sd * yk, zbeam - 0.045), rc3 + (rg_ + 0.0025 - 0.002) * Z], 0.005,
                      "Galvanised", lab(g, "chain"), IRON, long_link=True, fit=True)
            rep.append({"cot": g, "x": [x0, x1], "canvas_z": round(zc, 3),
                        "outboard_y": [round(sd * A0[1], 3), round(sd * A1[1], 3)],
                        "inboard_y": [round(sd * B0[1], 3), round(sd * B1[1], 3)],
                        "under_beams_m": round(float(IR.deckhead_z(x0 + 0.5 * (x1 - x0), A0[1])) - IR.BM_D - zc, 3)})
    return rep


# ------------------------------------------------------------------------------------------------ the washroom
def washroom(parts, side):
    """The crew's washroom: a pump WC to starboard on its teak base, the folding basin's cabinet forward of it, the
    oilskin lockers to port."""
    wr = IN["washroom"]
    jo, fi = parts[J], parts[F]
    zs = IR.RM["Washroom"]["sole"]
    rep = {}
    # the WC: a porcelain pan on its foot, a teak seat and lid, the pump and its lever beside it
    wx, wy = wr["wc"]["x"], wr["wc"]["y"]
    g = "Washroom WC"
    V, Fc = box((wx, wy, zs + 0.012), (0.22, 0.2, 0.012))
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "base"))
    zb = zs + 0.024
    V, Fc = deck.revolve([(0.0, 0.0), (0.12, 0.0), (0.125, 0.02), (0.11, 0.06), (0.12, 0.2), (0.17, 0.33),
                          (0.185, 0.36), (0.18, 0.37), (0.165, 0.365), (0.11, 0.26), (0.05, 0.19), (0.0, 0.18)],
                         (wx, wy, zb), Z, X, 28)
    fi.add(V, Fc, "Porcelain", None, lab(g, "pan"))                # weighed with the pump (below)
    zr = zb + 0.37
    P = deck.rrect(0.0, 0.0, 0.4, 0.4, 0.19, 6)
    Pi = deck.rrect(0.0, 0.0, 0.25, 0.25, 0.12, 6)
    V, Fc = deck.ring_slab(P, Pi, (wx, wy, zr), X, Y, Z, 0.0, 0.022)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "seat"))
    V, Fc = deck.slab(deck.rrect(0.0, 0.0, 0.399, 0.399, 0.1895, 6), (wx, wy, zr + 0.022), X, Y, Z, 0.0, 0.018)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "lid"))
    pc = wc_pump_at()
    ph = 0.024                                     # its foot on the sole, its head as high as when it stood on the base
    V, Fc = deck.revolve([(0.0, 0.0), (0.05, 0.0), (0.05, 0.01), (0.035, 0.02), (0.035, 0.36 + ph), (0.045, 0.37 + ph),
                          (0.045, 0.39 + ph), (0.0, 0.4 + ph)], pc, Z, X, 16)
    fi.add(V, Fc, "Bronze", None, lab(g, "pump"))
    V, Fc = deck.tube([pc + (0.0, 0.0, 0.39 + ph), pc + (0.03, 0.0, 0.42 + ph), pc + (0.32, 0.0, 0.5 + ph)], 0.01, 8)
    fi.add(V, Fc, "Bronze", None, lab(g, "lever"))
    V, Fc = deck.tube([pc + (0.0, 0.0, 0.1), pc + (0.12, 0.0, 0.1), (wx - 0.1, wy + 0.05, zb + 0.12)], 0.014, 8)
    fi.add(V, Fc, "Bronze", None, lab(g, "pipe"))
    for x, y, rp in wc_pipes():                                   # the inlet and the discharge, down through the sole
        V, Fc = deck.tube([(x, y, pc[2] + 0.03), (x, y, pc[2] - 0.2)], rp, 8)
        fi.add(V, Fc, "Bronze", None, lab(g, "pipe"))
    fi.weight("Washroom WC (the pan, pump and pipes: estimated)", wr["wc"].get("kg", 35.0), (wx, wy, zb + 0.2))
    clear = side.y(wx, zb + 0.36) - (wy + 0.2)
    rep["wc"] = {"x": wx, "y": wy, "seat_z": round(zr + 0.04, 3), "clear_of_ceiling_m": round(clear, 3)}
    # the folding basin's cabinet to starboard, the basin folded down on it
    bs = wr["basin"]
    bx0, bx1 = bs["x"]
    zt = zs + bs["height"]
    f = front_line(side, bx0, bx1, zt, bs["depth"], zs + 0.005)
    cabinet(parts, side, bx0, bx1, zs, zt - 0.025, f, 1, "Washroom basin", doors=1)
    xs = xs_over(bx0, bx1, 6)
    V, Fc = plan_strip(xs, lambda x: f(x) - 0.02, lambda x: side.y(x, zt - 0.025) - 0.002, zt - 0.025, zt, 1)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab("Washroom basin", "top"))
    bc = (0.5 * (bx0 + bx1), f(0.5 * (bx0 + bx1)) + 0.16)
    V, Fc = deck.revolve([(0.0, 0.0), (0.09, 0.005), (0.15, 0.04), (0.17, 0.075), (0.165, 0.08), (0.145, 0.05),
                          (0.085, 0.017), (0.0, 0.012)], (bc[0], bc[1], zt), Z, X, 24)
    fi.add(V, Fc, "Porcelain", ("solid", PORCELAIN), lab("Washroom basin", "basin"))
    tp = np.array([bc[0], bc[1] + 0.19, zt])
    V, Fc = deck.tube([tp, tp + (0.0, 0.0, 0.14), tp + (0.0, -0.08, 0.15), tp + (0.0, -0.1, 0.12)], 0.009, 8)
    fi.add(V, Fc, "Bronze", ("solid", BRONZE), lab("Washroom basin", "tap"))
    rep["basin"] = {"x": [bx0, bx1], "top_z": round(zt, 3), "front_y": [round(f(bx0), 3), round(f(bx1), 3)]}
    # the oilskin lockers to port, a shelf on top
    lk = wr["lockers"]
    lx0, lx1 = lk["x"]
    zt = zs + lk["height"]
    f = front_line(side, lx0, lx1, zs + 0.5 * lk["height"], lk["depth"], zs + 0.005)
    cabinet(parts, side, lx0, lx1, zs, zt - 0.022, f, -1, "Washroom lockers", doors=2)
    xs = xs_over(lx0, lx1, 6)
    V, Fc = plan_strip(xs, lambda x: f(x) - 0.02, lambda x: side.y(x, zt - 0.022) - 0.002, zt - 0.022, zt, -1)
    jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab("Washroom lockers", "top"))
    rep["lockers"] = {"x": [lx0, lx1], "top_z": round(zt, 3), "front_y": [round(-f(lx0), 3), round(-f(lx1), 3)]}
    return rep


def wc_pump_at():
    """The foot of the WC's pump, aft of the pan and outboard: on the sole, 5 mm clear of the pan's base (0.22 aft of
    the pan) so its pipes go down through the sole beside it."""
    wc = IN["washroom"]["wc"]
    return np.array([wc["x"] - 0.22 - 0.05 - 0.005, wc["y"] + 0.1, IR.RM["Washroom"]["sole"]])


def wc_pipes():
    """The WC's two seacock pipes down through the sole: (x, y, radius)."""
    pc = wc_pump_at()
    return [(float(pc[0]) + 0.03, float(pc[1]) + dy, 0.014) for dy in (0.04, -0.04)]


# ------------------------------------------------------------------------------------------------ the forepeak
def section_below(hull, x, z_top, x2=None):
    """1.5 mm inside the plating's inside face at x (and at x2: a board between the two) from the keel up to z_top,
    closed across there: (half-breadth, z) of one side and its mirror, as a closed polygon in (y, z)."""
    d = IR.ST["plating"] + 0.0015
    pts, _, _ = hull.inner(x, d, -9.0, z_top, step=0.03, y_min=0.0005)
    if x2 is not None:
        for p in pts:
            p[0] = min(p[0], hull.y_at(x2, d, p[1]) or p[0])
    port = pts[::-1] * np.array([-1.0, 1.0])
    P = np.concatenate([pts, port])
    return IR.clean_poly(P)


def chain_heap(hull, xr, kg, packing, steel=7850.0, n_v=11):
    """The cable heaped in the chain locker: lying over the frames' inner edges (FR_D inside the plating, where the
    frames' flanges are; between frames it bridges them) from xr[0] (the locker's bulkhead) to xr[1] (a frame: it
    stops at the frame's after face), level on top with a low mound (15 mm) along its middle, its top set so its
    volume is the chain's steel (kg / steel) over `packing`. Returns its mesh, its top's height, half-breadth and
    surface, its centre, and the numbers."""
    x0, x1 = xr[0] + 0.0003, xr[1] - 0.5 * IR.FR_T - 0.0003
    xs = np.unique(np.concatenate([np.linspace(x0, x1, 12), [f for f in IR.FRAMES if x0 < f < x1]]))
    curves = []
    for x in xs:
        pts, _ = IR.frame_edge(hull, x, -1.5, 1.5, step=0.02)
        k = int(np.argmin(pts[:, 1]))
        c = pts[k:]                                       # from the bottom up the side: y rising with z
        c = c[np.r_[True, np.diff(c[:, 0]) > 1e-6]]
        curves.append(c)
    z_at = lambda c, y: float(np.interp(abs(y), c[:, 0], c[:, 1]))    # noqa: E731
    y_at = lambda c, z: float(np.interp(z, c[:, 1], c[:, 0]))         # noqa: E731
    mound = lambda x, v: 0.015 * (1 - v * v) * math.sin(math.pi * (x - x0) / (x1 - x0))  # noqa: E731

    def mesh(zh):
        top, bot = [], []
        for x, c in zip(xs, curves):
            yh = y_at(c, zh - 0.01)
            rt, rb = [], []
            for v in np.linspace(-1.0, 1.0, n_v):
                y = v * yh
                rb.append((x, y, z_at(c, y)))
                rt.append((x, y, max(zh + mound(x, v), z_at(c, y) + 0.01)))
            top.append(rt)
            bot.append(rb)
        return IR.strip_solid(np.array(top), np.array(bot))

    def volume(V, F):
        vol = 0.0
        for f in F:
            for i in range(1, len(f) - 1):
                vol += np.dot(V[f[0]], np.cross(V[f[i]], V[f[i + 1]])) / 6.0
        return abs(vol)
    want = kg / steel / packing
    lo, hi = min(float(c[0, 1]) for c in curves) + 0.02, max(float(c[-1, 1]) for c in curves) - 0.02
    for _ in range(40):
        zh = 0.5 * (lo + hi)
        V, F = mesh(zh)
        lo, hi = (zh, hi) if volume(V, F) < want else (lo, zh)
    zh = 0.5 * (lo + hi)
    V, F = mesh(zh)
    ci = {round(float(x), 6): c for x, c in zip(xs, curves)}

    def curve(x):
        return ci[min(ci, key=lambda k: abs(k - x))]

    def half(x):
        return y_at(curve(x), zh - 0.01)

    def surface(x, y):
        c = curve(x)
        yh = y_at(c, zh - 0.01)
        if abs(y) >= yh:
            return z_at(c, y)
        return max(zh + mound(x, y / yh), z_at(c, y) + 0.01)
    Va = np.asarray(V, float)
    vol6, mom = 0.0, np.zeros(3)
    for f in F:                                       # the solid's centre, by tetrahedra from the origin
        for i in range(1, len(f) - 1):
            a, b, c = Va[f[0]], Va[f[i]], Va[f[i + 1]]
            v6 = float(np.dot(a, np.cross(b, c)))
            vol6 += v6
            mom += v6 * (a + b + c) / 4.0
    return {"mesh": (V, F), "top_z": round(zh, 3), "half": half, "surface": surface, "centre": mom / vol6,
            "x": [round(x0, 3), round(x1, 3)], "volume_m3": round(volume(V, F), 4), "steel_m3": round(kg / steel, 4),
            "packing": packing}


def anchor_stockless(part, c, heading, z0):
    """A stockless bower lying flat: its shank from the crown forward to the shackle, the crown's casting with the
    flukes lying along the shank each side of it, the tripping palms, and the shackle. c the crown's centre in plan,
    `heading` the shank's direction from forward (degrees, to starboard), z0 the underside."""
    an = IN["forepeak"]["bower"]
    q = math.radians(heading)
    S = np.array([math.cos(q), math.sin(q), 0.0])
    Lt = np.array([-S[1], S[0], 0.0])
    Ls, (sw0, sd0), (sw1, sd1) = an["shank_length"], an["shank_section"][0], an["shank_section"][1]
    cl, cw, ch = an["crown"]
    o = np.array([c[0], c[1], z0])
    g = "Bower anchor"
    zc = z0 + ch / 2
    # the crown: a block, rounded off
    P = deck.rrect(0.0, 0.0, cl, cw, 0.05, 4)
    rings = [o + P[:, :1] * S + P[:, 1:2] * Lt + z * Z for z in (0.0,)]
    Pt = deck.rrect(0.0, 0.0, cl - 0.03, cw - 0.03, 0.035, 4)
    rings = [o + P[:, :1] * S + P[:, 1:2] * Lt + 0.012 * Z, o + P[:, :1] * S + P[:, 1:2] * Lt + (ch - 0.012) * Z,
             o + Pt[:, :1] * S + Pt[:, 1:2] * Lt + ch * Z]
    Pb = deck.rrect(0.0, 0.0, cl - 0.03, cw - 0.03, 0.035, 4)
    rings.insert(0, o + Pb[:, :1] * S + Pb[:, 1:2] * Lt)
    V, Fc = loft_rings(rings)
    part.add(V, Fc, "Iron", ("solid", IRON), lab(g, "anchor"))
    # the shank: from inside the crown to its head, tapering
    secs = []
    ss = np.linspace(0.0, Ls, 8)
    for s in ss:
        fz = s / Ls
        hw, hd = 0.5 * (sw0 + (sw1 - sw0) * fz), 0.5 * (sd0 + (sd1 - sd0) * fz)
        R = deck.rrect(0.0, 0.0, 2 * hw, 2 * hd, 0.012, 3)
        secs.append(np.array([o + s * S + a * Lt + (zc + b - z0) * Z for a, b in R]))
    V, Fc = loft_rings(secs)
    part.add(V, Fc, "Iron", ("solid", IRON), lab(g, "anchor"))
    # the flukes: lying along the shank each side of it from the crown, tapering to their bills
    fl, fw, ft = an["fluke"]
    for sg in (1.0, -1.0):
        P2 = np.array([(cl / 2 - 0.02, sg * 0.03), (cl / 2 - 0.02, sg * (cw / 2 - 0.01)),
                       (cl / 2 + 0.6 * fl, sg * (cw / 2 + 0.01)), (cl / 2 + fl, sg * (sw0 / 2 + 0.06)),
                       (cl / 2 + fl - 0.05, sg * (sw0 / 2 + 0.03)), (cl / 2 + 0.05, sg * 0.03)])
        if sg < 0:
            P2 = P2[::-1]
        V, Fc = deck.slab(P2, o + (zc - z0) * Z, S, Lt, Z, -ft / 2, ft / 2)
        part.add(V, Fc, "Iron", ("solid", IRON), lab(g, "anchor"))
    # the tripping palms: wedges standing on the crown's after end
    for sg in (1.0, -1.0):
        P2 = np.array([(-cl / 2 + 0.01, 0.0), (-cl / 2 + 0.11, 0.0), (-cl / 2 + 0.03, 0.07)])
        V, Fc = deck.slab(P2, o + sg * (cw / 2 - 0.05) * Lt + ch * Z - 0.005 * Z, S, Z, Lt, -0.02, 0.02)
        part.add(V, Fc, "Iron", ("solid", IRON), lab(g, "anchor"))
    # the shackle at the shank's head
    hc = o + (Ls + 0.06) * S + (zc - z0) * Z
    V, Fc = IR.ring_tube(stadium(hc, S, Lt, 0.16, 0.1, 6), 0.013, 8)
    part.add(V, Fc, "Galvanised", ("solid", IRON), lab(g, "shackle"))
    pts = [o + s * S + a * Lt for s in (-cl / 2, Ls + 0.14) for a in (-cw / 2 - 0.03, cw / 2 + 0.03)]
    return {"crown": [round(float(c[0]), 3), round(float(c[1]), 3)], "heading_deg": heading,
            "head": [round(float(hc[0]), 3), round(float(hc[1]), 3)], "corners": [p[:2].tolist() for p in pts]}


def forepeak(parts, side, hull, beams_x):
    """The forepeak: the chain locker's after bulkhead under the platform, the hand
    windlass on the platform with its gypsy under the chain pipe's lead, the spurling pipe from the chain pipe down
    to the gypsy and the navel pipe through the platform to the locker, the cable over the gypsy into the locker and
    its heap there, the stockless bower on its chocks, and the bosun's shelves."""
    import hardware
    fp = IN["forepeak"]
    jo, fi = parts[J], parts[F]
    zp = IR.RM["Forepeak"]["sole"]
    th = IR.RM["sole_thickness"]
    rep = {}
    # the chain locker's after bulkhead under the platform's bearers (interior.soles)
    xl = fp["locker"][0]
    P = section_below(hull, xl, zp - th - 0.07, x2=xl - BOARD)          # up to the bearer over it
    V, Fc = deck.slab(P, (xl, 0.0, 0.0), Y, Z, X, -BOARD, 0.0)
    jo.add(V, Fc, "WhitePaint", ("solid", WT["pine"]), lab("Chain locker", "bulkhead"))
    rep["chain_locker"] = {"x": [xl, fp["locker"][1]], "under_z": round(zp - th - 0.07, 3)}
    # the windlass
    wl = fp["windlass"]
    wx, wy = wl["at"]
    rep["windlass"], sweep = windlass(parts, wx, wy, zp, wl)
    gy = rep["windlass"]["gypsy"]
    gx, gyy, gz, R = gy["x"], gy["y"], gy["z"], gy["pitch_r"]
    # the spurling pipe: from the chain pipe's foot one smooth bend ('bend_r') onto a straight lead that comes onto
    # the gypsy's top a little forward of it (its dip solved so the bend has that radius), in the vertical plane from
    # the chain pipe to the gypsy (3 degrees off fore and aft); it ends 'short' of the touch
    cp = hardware.HW["chain_pipe"]
    cx, cy = cp["at"]
    z_cp = float(shell.deck_z(cx, cy)) - deck.PL["thickness"] - 0.012
    sp_ = fp["spurling"]
    ro, ri = sp_["r"], sp_["r"] - sp_["wall"]
    Rb = sp_["bend_r"]
    h = unit(np.array([gx - cx, gyy - cy]))              # the pipe's plane, in plan, aft from the chain pipe
    on = lambda s_, z_: np.array([cx + s_ * h[0], cy + s_ * h[1], z_])  # noqa: E731

    def touch(dip):                                      # the lead's touch on the gypsy: (s along h, z)
        xt = gx - R * math.sin(dip)
        return (xt - cx) / h[0], gz + R * math.cos(dip)

    def bend_for(dip):
        s_t, z_t = touch(dip)
        return (z_cp - z_t - s_t * math.tan(dip)) * math.cos(dip) / (1.0 - math.sin(dip))
    lo_, hi_ = 0.0, math.radians(40.0)
    for _ in range(60):
        mid_ = 0.5 * (lo_ + hi_)
        lo_, hi_ = (mid_, hi_) if bend_for(mid_) > Rb else (lo_, mid_)
    dip = 0.5 * (lo_ + hi_)
    s_t, z_t = touch(dip)
    tau = 0.5 * math.pi - dip
    arc_pts = [on(Rb - Rb * math.cos(a), z_cp - Rb * math.sin(a)) for a in np.linspace(0.0, tau, 19)]
    T_in = on(s_t, z_t)
    d_in = unit(T_in - arc_pts[-1])
    p_end = T_in - sp_["short"] * d_in
    path = [on(0.0, z_cp + 0.0)] + arc_pts[1:] + [p_end]

    # the chain pipe's backing flange follows the deck's slope and camber: so do the pipe's mouth and its own flange,
    # half a millimetre under it
    def under_deck(V, top_only):
        V = np.array(V, float)
        sel = V[:, 2] > z_cp - 1e-6 if top_only else np.ones(len(V), bool)
        V[sel, 2] += shell.deck_z(V[sel, 0], V[sel, 1]) - shell.deck_z(cx, cy) - 0.0005
        return V
    V, Fc = pipe(path, ro, ri, 20)
    fi.add(under_deck(V, True), Fc, "Galvanised", ("solid", IRON), lab("Spurling pipe", "spurling pipe"))
    Ls = float(sum(np.linalg.norm(path[k + 1] - path[k]) for k in range(len(path) - 1)))
    V, Fc = deck.revolve([(ro + 0.03, 0.0), (ro + 0.03, -0.012), (ro + 0.0005, -0.012), (ro + 0.0005, 0.0)],
                         (cx, cy, z_cp), Z, X, 20, ring=True)
    fi.add(under_deck(V, False), Fc, "Galvanised", ("solid", IRON), lab("Spurling pipe", "flange"))
    # the navel pipe through the platform (the slats are cut round it: interior.soles), flanged on top
    nr = fp["navel"]
    nv = navel_at()
    zn = zp + 0.012
    V, Fc = deck.revolve([(nr["flange"], 0.012), (nr["flange"], 0.0), (nr["r"], 0.0), (nr["r"], -nr["length"]),
                          (nr["r"] - 0.008, -nr["length"]), (nr["r"] - 0.008, 0.012)], (nv[0], nv[1], zp), Z, X, 24,
                         ring=True)
    fi.add(V, Fc, "Bronze", ("solid", BRONZE), lab("Navel pipe", "navel pipe"))
    # the cable: from inside the pipe's straight lead (lying on the pipe's floor) onto the gypsy's top, round it, off
    # its after side down through the navel pipe, onto the heap
    d = fp["cable_d"]
    Wl = 3.5 * d
    ang_in = 0.5 * math.pi + dip
    ang_out = tangent_angle((gx, gz), R, np.array([nv[0], zn]), upper=False) % (2 * math.pi)
    n_dn = unit(np.cross(np.cross(d_in, Z), d_in)) * -1.0       # square to the lead, downward
    floor = (ri - 0.5 * Wl - 0.0003) * n_dn
    P0 = p_end - 0.35 * d_in + floor
    P1 = p_end + floor
    arc = [np.array([gx + R * math.cos(a), gyy, gz + R * math.sin(a)]) for a in np.linspace(ang_in, ang_out, 16)]
    hp = fp["heap"]
    heap = chain_heap(hull, hp["x"], fp["cable"]["m"] * fp["cable"]["kg_m"], hp["packing"])
    # out of the pipe's mouth it falls onto the heap's edge under it (the pipe stands over the locker's side, a
    # little outboard of the heap's level top)
    ye = math.copysign(min(abs(nv[1]), heap["half"](nv[0]) - 0.02), nv[1])
    zm = zp - nr["length"]
    run = [P0, P1] + arc + [np.array([nv[0], nv[1], zn]), np.array([nv[0], nv[1], zm]),
                            np.array([nv[0], nv[1], zm - 0.03]),
                            np.array([nv[0], ye, heap["surface"](nv[0], ye) + 0.5 * d])]
    L1, n1 = chain(fi, run, d, "Galvanised", lab("Cable", "chain"))
    # the whelps: ribs on the gypsy's shoulders beside each link standing on edge in its slot (the cable's links
    # lie with a flat one in each pocket), all round at the pockets' spacing
    Lk = 5.0 * d
    pitch = Lk - 2.0 * d
    s_in = float(np.linalg.norm(P1 - P0) + np.linalg.norm(arc[0] - P1))
    j = int(math.ceil((s_in - 0.5 * Lk) / pitch))
    if j % 2 == 0:
        j += 1                                                    # the first upright link on the gypsy
    a0 = ang_in + (0.5 * Lk + j * pitch - s_in) / R
    nwh = wl["whelps"]
    sh_r = R - 0.5 * d - 0.0002
    for k in range(nwh):
        a = a0 + 2 * math.pi * k / nwh
        tdir = np.array([-math.sin(a), 0.0, math.cos(a)])
        rdir = np.array([math.cos(a), 0.0, math.sin(a)])
        for sg in (1.0, -1.0):
            yc = gyy + sg * (0.5 * (0.5 * d + 0.004) + 0.5 * (0.5 * Wl + 0.004))
            c = np.array([gx, yc, gz]) + (sh_r + 0.004) * rdir
            hy = 0.5 * ((0.5 * Wl + 0.004) - (0.5 * d + 0.004))
            q4 = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
            V, Fc = loft_rings([np.array([c + su * 0.006 * tdir + sv * hy * Y + sw * 0.007 * rdir for su, sv in q4])
                                for sw in (-1, 1)])
            fi.add(V, Fc, "Iron", ("solid", IRON), lab("Windlass", "whelp"))
    rep["spurling_pipe"] = {"length_m": round(Ls, 3), "bend_r_m": Rb, "lead_dip_deg": round(math.degrees(dip), 1),
                            "fleet_deg": round(math.degrees(math.atan2(abs(h[1]), abs(h[0]))), 1),
                            "wrap_deg": round(math.degrees(ang_out - ang_in), 1)}
    # the heap: lying over the frames in the locker's V, its size from the chain's steel and its packing
    V, Fc = heap["mesh"]
    fi.add(V, Fc, "Galvanised", None, lab("Cable", "chain heap"))
    loops = 0
    xm = 0.5 * (hp["x"][0] + hp["x"][1])
    for rx_, ry_ in ((0.34, 0.62), (0.2, 0.38)):
        lp = []
        for a in np.linspace(0, 2 * math.pi * 0.92, 30):
            x = xm + rx_ * (hp["x"][1] - hp["x"][0]) * math.cos(a)
            yl = ry_ * heap["half"](x) * math.sin(a)
            lp.append(np.array([x, yl, heap["surface"](x, yl) + 0.5 * d]))
        Lk_, nk = chain(fi, lp, d, "Galvanised", lab("Cable", "chain"), start=loops)
        loops += nk
    ct = fp["cable"]
    cen = (heap["centre"] * (ct["m"] - L1) + np.mean(run, axis=0) * L1) / ct["m"]
    fi.weight(f"Cable: {ct['m']:.0f} m of {1000 * d:.0f} mm chain at {ct['kg_m']} kg/m", ct["m"] * ct["kg_m"], cen)
    rep["cable"] = {"links_drawn": n1 + loops, "m": ct["m"], "kg": round(ct["m"] * ct["kg_m"], 1),
                    "heap": {k: heap[k] for k in ("x", "top_z", "volume_m3", "steel_m3", "packing")}}
    # the bower on its chocks
    bw = fp["bower"]
    rep["bower"] = anchor_stockless(fi, bw["crown_at"], bw["heading_deg"], zp + bw["chocks_h"])
    # two chocks: one under the crown, one under the shank near its head, its top following the shank's taper
    q = math.radians(bw["heading_deg"])
    Sd = np.array([math.cos(q), math.sin(q)])
    (_, sd0), (_, sd1) = bw["shank_section"]

    def under(s_):                                         # the shank's underside s_ along it from the crown
        return zp + bw["chocks_h"] + 0.5 * bw["crown"][2] - 0.5 * (sd0 + (sd1 - sd0) * s_ / bw["shank_length"])
    for s, cl_ in ((0.0, bw["crown"][0] - 0.06), (bw["shank_length"] - 0.15, 0.14)):
        cxy = np.array(bw["crown_at"]) + s * Sd
        w_ = bw["crown"][1] - 0.04 if s == 0.0 else 0.2
        P = deck.rrect(0.0, 0.0, cl_, w_, 0.015, 2)
        Q = cxy + P[:, :1] * Sd + P[:, 1:2] * np.array([-Sd[1], Sd[0]])
        V, Fc = deck.slab(Q, (0.0, 0.0, zp), X, Y, Z, 0.0, bw["chocks_h"])
        if s > 0.0:
            top = V[:, 2] > zp + 1e-6
            V[top, 2] = [under((v[:2] - np.array(bw["crown_at"])) @ Sd) - 0.0002 for v in V[top]]
        jo.add(V, Fc, "Varnish", ("solid", WT["teak"]), lab("Bower chocks", "chock"))
    # the bosun's shelves, each side over the platform's after end, against the frames (the forepeak is not ceiled)
    # and the bulkhead
    bs = fp["shelves"]
    for sd, side_name in IR.SIDES:
        for z in bs["z"]:
            xs = xs_over(bs["x"][0], bs["x"][1], 6)
            yo = lambda x, z=z: side.y(x, z - 0.02, bare=True) - 0.0002  # noqa: E731
            yi = lambda x, z=z: side.y(x, z - 0.02, bare=True) - bs["depth"]  # noqa: E731
            V, Fc = plan_strip(xs, yi, yo, z - 0.02, z, sd)
            jo.add(V, Fc, "WhitePaint", ("solid", WT["pine"]), lab(f"Bosun's shelves, {side_name}", "shelf"))
            V, Fc = plan_strip(xs, lambda x, yi=yi: yi(x) + 0.0005, lambda x, yi=yi: yi(x) + 0.016, z, z + 0.05, sd)
            jo.add(V, Fc, "WhitePaint", ("solid", WT["pine"]), lab(f"Bosun's shelves, {side_name}", "fiddle"))
    rep["shelves"] = {"x": bs["x"], "z": bs["z"]}
    rep["windlass"]["crank"]["sweep"] = sweep
    return rep


def crank_clearance(parts, sweep, zp, hand=0.045):
    """The windlass's crank turned right round: the room left round the grip for a fist on it (`hand` out from the
    grip's axis) and round the arm, to the platform (zp, analytically) and to every corner of every face below decks
    that is not the windlass's own (the ship's shell and deck are far from it: above the arm's top by more than half a
    metre and well outboard). Returns the least clearances (m) and what is nearest the fist."""
    ax, az = sweep["axis"]
    r = sweep["r"]
    out = {"platform_under_fist_m": round(az - r - hand - zp, 3), "fist_m": 9.0, "arm_m": 9.0, "nearest": None}
    for part in parts.values():
        if not part.V:
            continue
        V = np.asarray(part.V, float)
        keep = np.ones(len(V), bool)
        for f, lb in zip(part.F, part.labels):
            if lb.split(" | ")[0] == "Windlass":
                keep[list(f)] = False
        rho = np.hypot(V[:, 0] - ax, V[:, 2] - az)
        y = V[:, 1]
        g = keep & (y > sweep["grip"][0] - hand) & (y < sweep["grip"][1] + hand)
        if g.any():
            c = np.abs(rho[g] - r) - hand
            k = int(np.argmin(c))
            if c[k] < out["fist_m"]:
                out["fist_m"] = round(float(c[k]), 3)
                out["nearest"] = [round(float(v), 3) for v in V[g][k]]
        a = keep & (y > sweep["arm"][0] - 0.01) & (y < sweep["arm"][1] + 0.01)
        if a.any():
            out["arm_m"] = min(out["arm_m"], round(float(np.min(rho[a]) - r - 0.02), 3))
    return out


def tangent_angle(c, R, q, upper=True):
    """The angle (from +x toward +z, in the plane of a wheel of radius R about c) of the point where a line from q
    touches the wheel: `upper`, the touch reached first going over the wheel's top from forward (the cable coming
    onto it), else the last (the cable leaving it)."""
    D = np.asarray(q, float) - np.asarray(c, float)
    phi = math.atan2(D[1], D[0])
    beta = math.acos(min(R / float(np.linalg.norm(D)), 1.0))
    return phi + beta if upper else phi - beta


def pipe(path, ro, ri, n=16):
    """A pipe along a polyline: outside ro, bore ri, its ends open (an annulus each end); its bends mitred as
    deck.tube's."""
    def rings(r):
        V, _ = deck.tube(path, r, n)
        return [V[k * n:(k + 1) * n] for k in range(len(path))]
    return loft_rings(rings(ro) + rings(ri)[::-1], closed=True)


def navel_at():
    """The navel pipe's plan point: under the gypsy's after side (from the windlass's json, so interior.soles can cut
    the platform's slats round it before the windlass is built)."""
    fp = IN["forepeak"]
    wl = fp["windlass"]
    wx, wy = wl["at"]
    return (wx - fp["navel"]["aft"], gypsy_y(wl))


def gypsy_y(wl):
    return wl["at"][1] - wl["cheek_gap"] / 2 - wl["cheek"] / 2 - wl["gypsy_off"] - wl["gypsy"][1] / 2


def gear_outline(R, N, m, phase=0.0, ratchet=False):
    """A toothed wheel's outline in its own plane (u, v about its axis): N teeth of module m on pitch radius R (tips
    m out, roots 1.25 m in), the first tooth's middle at `phase` (radians from u); a ratchet's teeth are saw teeth."""
    ra, rd, p = R + m, R - 1.25 * m, 2 * math.pi / N
    shape = ((0.0, rd), (0.7, ra), (0.72, rd)) if ratchet else ((0.0, rd), (0.2, ra), (0.4, ra), (0.6, rd))
    mid = 0.36 if ratchet else 0.3
    out = []
    for k in range(N):
        for f, r in shape:
            a = phase + (k + f - mid) * p
            out.append((r * math.cos(a), r * math.sin(a)))
    return np.array(out)


def windlass_frame(wl):
    """The windlass's layout across and fore and aft (from its json): the gypsy's y, the drum's, the barrel's and the
    crankshaft's ends, the crankshaft's distance aft of the barrel."""
    wy = wl["at"][1]
    cg, ct = wl["cheek_gap"], wl["cheek"]
    dr, dw = wl["drum"]
    gr = wl["gear"]
    m = 2 * gr["wheel_r"] / gr["wheel_teeth"]
    y_d = wy + cg / 2 + ct / 2 + 0.02 + dw / 2
    return {"y_g": gypsy_y(wl), "y_d": y_d, "y_end": y_d + dw / 2 + 0.02, "y_crank": y_d + dw / 2 + 0.05,
            "y_port": wy - cg / 2 - ct / 2 - 0.005, "module": m, "pinion_r": 0.5 * m * gr["pinion_teeth"],
            "crank_aft": gr["wheel_r"] + 0.5 * m * gr["pinion_teeth"]}


def windlass(parts, wx, wy, zp, wl):
    """A hand windlass of cast iron, geared: a bed plate on the platform, two cheeks carrying the barrel athwartships
    and the crankshaft aft of it, the crankshaft's pinion driving the barrel's spur wheel ('gear', about 2.8 to 1),
    the gypsy outboard of the port cheek (a slot round its middle for the links on edge, shoulders either side for the
    links lying flat: interior's forepeak adds the whelps between them, set to the cable as it lies), a warping drum
    outboard of the starboard cheek, the ratchet wheel and its pawl inside the port cheek, and the crank on the
    crankshaft's starboard end, its sweep clear of the platform. The bed stops short of the gypsy so the cable drops
    clear of it to the navel pipe. Weighed from its iron. Returns its report and the crank's sweep (axis, radius, the
    y bands of its arm and grip) for forepeak's clearance check."""
    fi = parts[F]
    g = "Windlass"
    L = windlass_frame(wl)
    bl, bw_, bt = wl["bed"]
    cg, ct = wl["cheek_gap"], wl["cheek"]
    ca = L["crank_aft"]
    sh_ = wl["shaft_h"]
    xb = wx - wl["bed_aft"]
    y_port = L["y_port"]
    V, Fc = box((xb, y_port + bw_ / 2, zp + bt / 2), (bl / 2, bw_ / 2, bt / 2))
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "windlass"))
    zs = zp + bt + sh_
    # the cheeks: round the barrel and, aft of it, the crankshaft
    for sg in (1.0, -1.0):
        P2 = np.array([(xb - wx - bl / 2 + 0.03, 0.0), (xb - wx + bl / 2 - 0.03, 0.0), (0.07, sh_ + 0.05),
                       (-ca - 0.06, sh_ + 0.05)])
        V, Fc = deck.slab(P2, (wx, wy + sg * cg / 2, zp + bt), X, Z, Y, -ct / 2, ct / 2)
        fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "windlass"))
    sr = 0.03
    Rp, gw = wl["gypsy"]
    y_g, y_d, y_end = L["y_g"], L["y_d"], L["y_end"]
    dr, dw = wl["drum"]
    V, Fc = deck.revolve([(0.0, y_g - gw / 2 - 0.02), (sr, y_g - gw / 2 - 0.02), (sr, y_end), (0.0, y_end)],
                         (wx, 0.0, zs), Y, Z, 16)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "windlass"))
    d = IN["forepeak"]["cable_d"]
    W = 3.5 * d
    hw = gw / 2
    shoulder = Rp - 0.5 * d - 0.0002                          # the flat links lie on it
    slot = Rp - 0.5 * W - 0.003                               # the links on edge stand 3 mm off its floor
    V, Fc = deck.revolve([(sr, -hw), (Rp + 0.024, -hw), (Rp + 0.024, -0.5 * W - 0.008), (shoulder, -0.5 * W - 0.004),
                          (shoulder, -0.5 * d - 0.004), (slot, -0.5 * d - 0.004), (slot, 0.5 * d + 0.004),
                          (shoulder, 0.5 * d + 0.004), (shoulder, 0.5 * W + 0.004), (Rp + 0.024, 0.5 * W + 0.008),
                          (Rp + 0.024, hw), (sr, hw)], (wx, y_g, zs), Y, Z, 48)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "gypsy"))
    V, Fc = deck.revolve([(sr, -dw / 2), (dr + 0.025, -dw / 2), (dr + 0.025, -dw / 2 + 0.01), (dr, -dw / 2 + 0.025),
                          (dr - 0.012, 0.0), (dr, dw / 2 - 0.025), (dr + 0.025, dw / 2 - 0.01), (dr + 0.025, dw / 2),
                          (sr, dw / 2)], (wx, y_d, zs), Y, Z, 28)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "drum"))
    # the gearing inside the starboard cheek: the barrel's spur wheel and the crankshaft's pinion, meshed on the line
    # between their axes (a wheel's tooth there in the pinion's gap)
    gr, m = wl["gear"], L["module"]
    y_in = wy + cg / 2 - ct / 2 - 0.005
    ya, yb = y_in - gr["width"], y_in
    pp = 2 * math.pi / gr["pinion_teeth"]
    V, Fc = deck.slab(gear_outline(gr["wheel_r"], gr["wheel_teeth"], m, phase=math.pi), (wx, 0.0, zs), X, Z, Y, ya, yb)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "spur wheel"))
    V, Fc = deck.slab(gear_outline(L["pinion_r"], gr["pinion_teeth"], m, phase=0.5 * pp), (wx - ca, 0.0, zs), X, Z,
                      Y, ya, yb)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "pinion"))
    # the crankshaft through both cheeks to the crank
    y_c = L["y_crank"]
    V, Fc = deck.revolve([(0.0, wy - cg / 2 - ct / 2), (0.022, wy - cg / 2 - ct / 2), (0.022, y_c + 0.012),
                          (0.0, y_c + 0.012)], (wx - ca, 0.0, zs), Y, Z, 16)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "crankshaft"))
    # the ratchet inside the port cheek, its pawl pivoted under it on a pin from the cheek
    y0 = wy - cg / 2 + ct / 2 + 0.005
    rr_, nr_ = 0.1, 24
    mr = 2 * rr_ / nr_
    V, Fc = deck.slab(gear_outline(rr_, nr_, mr, ratchet=True), (wx, 0.0, zs), X, Z, Y, y0, y0 + 0.03)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "ratchet"))
    piv = np.array([0.06, -0.16])
    a_t = math.radians(-60.0)
    tip = (rr_ + 0.25 * mr) * np.array([math.cos(a_t), math.sin(a_t)])      # on a tooth's back, under its tip
    ax_ = unit(tip - piv)
    nx_ = np.array([-ax_[1], ax_[0]])
    P2 = np.array([piv - 0.014 * nx_ - 0.012 * ax_, tip - 0.005 * nx_, tip + 0.005 * nx_,
                   piv + 0.014 * nx_ - 0.012 * ax_])
    V, Fc = deck.slab(P2, (wx, 0.0, zs), X, Z, Y, y0 + 0.006, y0 + 0.024)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "pawl"))
    V, Fc = deck.revolve([(0.0, wy - cg / 2), (0.01, wy - cg / 2), (0.01, y0 + 0.03), (0.0, y0 + 0.03)],
                         (wx + piv[0], 0.0, zs + piv[1]), Y, Z, 10)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "pawl pin"))
    # the crank: an arm from the crankshaft's squared end out to the grip, drawn at its json angle
    cr, cgrip, cang = wl["crank"]
    q = math.radians(cang)
    e = np.array([math.cos(q), math.sin(q)])
    nq = np.array([-e[1], e[0]])
    P2 = np.array([-0.035 * e - 0.03 * nq, cr * e - 0.02 * nq, cr * e + 0.02 * nq, -0.035 * e + 0.03 * nq])
    V, Fc = deck.slab(P2, (wx - ca, 0.0, zs), X, Z, Y, y_c - 0.012, y_c + 0.012)
    fi.add(V, Fc, "Iron", ("solid", IRON), lab(g, "crank"))
    ce = np.array([wx - ca + cr * e[0], y_c + 0.012, zs + cr * e[1]])
    V, Fc = deck.revolve([(0.0, 0.0), (0.018, 0.0), (0.018, cgrip), (0.0, cgrip)], ce, Y, Z, 12)
    parts[J].add(V, Fc, "Varnish", ("solid", WT["teak"]), lab(g, "crank grip"))
    sweep = {"axis": [wx - ca, zs], "r": cr, "grip_r": 0.018, "arm": [y_c - 0.012, y_c + 0.012],
             "grip": [y_c + 0.012, y_c + 0.012 + cgrip]}
    return {"at": [wx, wy], "barrel_z": round(zs, 3), "bed_y": [round(y_port, 3), round(y_port + bw_, 3)],
            "bed_x": [round(xb - bl / 2, 3), round(xb + bl / 2, 3)],
            "gypsy": {"x": wx, "y": round(y_g, 4), "z": round(zs, 3), "pitch_r": Rp},
            "gearing": {"ratio": round(gr["wheel_teeth"] / gr["pinion_teeth"], 2), "module_mm": round(1000 * m, 2),
                        "crankshaft_aft_m": round(ca, 3)},
            "crank": {"r": cr, "axis_z": round(zs, 3)}}, sweep
