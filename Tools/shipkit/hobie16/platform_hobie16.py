"""The Hobie 16's platform (docs/hobie16-3, slice 2) as plain geometry: no Blender, so it can be checked and plotted.

    python3 -I platform_hobie16.py          prints where it stands: heights over the water, the trampoline, the bridle

platform_hobie16.json holds the sizes; hull_hobie16 the hulls it stands on (call hull_hobie16.solve_depth() first: the
deck's heights follow the solved keel depth). build() returns the parts as Part meshes (vertices, faces and a material
slot a face) in Blender's frame, X forward, Y to PORT, Z up, metres, which build_hobie16.py turns into objects:
  Frame   the two crossbars with their tracks, the sidebars, the four corner castings, the dolphin striker and the
          mast step
  Boss    the four pylons moulded in the decks under the castings (hull colour; their feet follow the deck)
  Tramp   the trampoline's two halves, the centre lacing and the two rear lacing lines
  Bridle  the bow tangs, the two bridle wires and the bridle plate the forestay ties to
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_hobie16 as H  # noqa: E402

P = json.load(open(os.path.join(HERE, "platform_hobie16.json")))
CY = H.CARD["game"]["hull_center_y_m"]


class Part:
    def __init__(self, name):
        self.name, self.v, self.f, self.slot, self.flat = name, [], [], [], []
        self.uv = {}            # vertex -> (UV0, UV1, UV2) for the sails' cloth (sails_hobie16); others box-project

    def add_verts(self, pts, uvs=None):
        i0 = len(self.v)
        self.v.extend([tuple(map(float, p)) for p in pts])
        if uvs is not None:
            for k, uv in enumerate(uvs):
                self.uv[i0 + k] = tuple(map(float, uv))
        return i0

    def face(self, idx, slot, flat=False):
        self.f.append(tuple(idx))
        self.slot.append(slot)
        self.flat.append(flat)

    def tris(self):
        return sum(len(f) - 2 for f in self.f)


# ---- profiles and solids --------------------------------------------------------------------------------------------

def rrect(w, h, r, n=5):
    """A rounded rectangle w across by h tall, corner radius r, counter-clockwise from the bottom's middle: (m, 2)."""
    r = min(r, w / 2 - 1e-4, h / 2 - 1e-4)
    pts = []
    for cx, cz, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return np.array(pts)


def circle(r, n=8):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.stack([r * np.cos(a), r * np.sin(a)], axis=1)


def sweep(part, path, prof, slot, up=(0.0, 0.0, 1.0), caps=True):
    """The closed profile prof (u across, v up) swept along path; frames from the path's tangent and `up`."""
    path = np.asarray(path, float)
    up = np.asarray(up, float)
    rings = []
    for i in range(len(path)):
        t = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
        t /= np.linalg.norm(t)
        s = np.cross(up, t)
        s /= np.linalg.norm(s)
        u = np.cross(t, s)
        rings.append(part.add_verts([path[i] + p[0] * s + p[1] * u for p in prof]))
    m = len(prof)
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(m):
            k = (j + 1) % m
            part.face((a + j, a + k, b + k, b + j), slot)
    if caps:
        part.face([rings[0] + j for j in range(m)][::-1], slot, flat=True)
        part.face([rings[-1] + j for j in range(m)], slot, flat=True)
    return rings


def lathe(part, cx, cy, prof, slot, n=20, close_bottom=True, close_top=True):
    """Revolve prof [(r, z)] about the vertical line through (cx, cy). Rings of r 0 close to a point."""
    rings = []
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    for r, z in prof:
        rings.append(part.add_verts([(cx + r * math.cos(t), cy + r * math.sin(t), z) for t in a]))
    for p, q in zip(rings[:-1], rings[1:]):
        for j in range(n):
            k = (j + 1) % n
            part.face((p + j, p + k, q + k, q + j), slot)
    if close_bottom and prof[0][0] > 0:
        part.face([rings[0] + j for j in range(n)][::-1], slot, flat=True)
    if close_top and prof[-1][0] > 0:
        part.face([rings[-1] + j for j in range(n)], slot, flat=True)
    return rings


RING_N = 32


def loft(part, cx, cy, rings, power, slot):
    """A solid through rounded-square rings [(half length in x, half width in y, z)] about (cx, cy), capped at both
    ends: superellipses of the given power (2 an ellipse, higher squarer). Returns each ring's first vertex index."""
    t = np.linspace(0, 2 * math.pi, RING_N, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    ex = 2.0 / power
    out = []
    for a, b, z in rings:
        out.append(part.add_verts([(cx + a * np.sign(ci) * abs(ci) ** ex, cy + b * np.sign(si) * abs(si) ** ex, z)
                                   for ci, si in zip(c, s)]))
    for p, q in zip(out[:-1], out[1:]):
        for j in range(RING_N):
            k = (j + 1) % RING_N
            part.face((p + j, p + k, q + k, q + j), slot)
    part.face([out[0] + j for j in range(RING_N)][::-1], slot, flat=True)
    part.face([out[-1] + j for j in range(RING_N)], slot, flat=True)
    return out


def box(part, c, size, slot):
    c, s = np.asarray(c, float), np.asarray(size, float) / 2
    i0 = part.add_verts([c + s * np.array(v) for v in
                         ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))])
    for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        part.face([i0 + k for k in q], slot, flat=True)


def sheet(part, grid, t, slot):
    """A grid (R, C, 3) of points as a slab t thick (the points its top face)."""
    R, C = grid.shape[:2]
    top = part.add_verts(grid.reshape(-1, 3))
    bot = part.add_verts((grid - np.array([0, 0, t])).reshape(-1, 3))
    idx = lambda b, i, j: b + i * C + j
    for i in range(R - 1):
        for j in range(C - 1):
            part.face((idx(top, i, j), idx(top, i + 1, j), idx(top, i + 1, j + 1), idx(top, i, j + 1)), slot)
            part.face((idx(bot, i, j), idx(bot, i, j + 1), idx(bot, i + 1, j + 1), idx(bot, i + 1, j)), slot)
    edge = [(i, 0) for i in range(R)] + [(R - 1, j) for j in range(1, C)] + \
           [(i, C - 1) for i in range(R - 2, -1, -1)] + [(0, j) for j in range(C - 2, 0, -1)]
    for (i0, j0), (i1, j1) in zip(edge, edge[1:] + edge[:1]):
        part.face((idx(top, i0, j0), idx(bot, i0, j0), idx(bot, i1, j1), idx(top, i1, j1)), slot)


# ---- where it stands -------------------------------------------------------------------------------------------------

def deck_z(x, inboard):
    """The deck's top at station x, `inboard` metres in from the hull's centre (negative: outboard)."""
    p = H.section(float(x), 96)
    y = -inboard
    zs = []
    for i in range(len(p)):
        q, r = p[i], p[(i + 1) % len(p)]
        if (q[0] - y) * (r[0] - y) <= 0 and q[0] != r[0]:
            zs.append(q[1] + (r[1] - q[1]) * (y - q[0]) / (r[0] - q[0]))
    return max(zs)


def layout(hounds=None):
    """The frame's numbers: corners, heights, the trampoline's outline and the bridle plate. Without `hounds` the plate
    stands junction_over_frame_m over the front crossbar (slice 2); with the rig's hounds (x, z: rig_hobie16.solve,
    slice 4) it rides where a stay from the hounds pulls it, on the circle the two wires allow nearest the hounds, so
    the wires line up with the forestay."""
    F, fc, rc, sb = P["frame"], P["front_crossbar"], P["rear_crossbar"], P["sidebar"]
    fx, rx, ci = F["front_x"], F["rear_x"], F["casting_inboard_m"]
    yc = CY - ci
    zf = deck_z(fx, ci) + F["standoff_m"] + fc["height_m"] / 2
    zr = deck_z(rx, ci) + F["standoff_m"] + rc["height_m"] / 2
    B = P["bridle"]
    tz = H.top_z(B["tang_x"])
    jz = zf + fc["height_m"] / 2 + B["junction_over_frame_m"]
    eye = 0.02
    dz = jz - (tz + eye)
    dx = math.sqrt(max(B["wire_length_m"] ** 2 - CY ** 2 - dz ** 2, 0.0))
    junction = (B["tang_x"] - dx, 0.0, jz)
    if hounds is not None:
        c = np.array([B["tang_x"], tz + eye])
        d = np.array(hounds, float) - c
        j = c + math.sqrt(B["wire_length_m"] ** 2 - CY ** 2) * d / np.linalg.norm(d)
        junction = (float(j[0]), 0.0, float(j[1]))
    T = P["trampoline"]
    x0 = rx + rc["width_m"] / 2 + T["rear_gap_m"]
    x1 = fx - fc["width_m"] / 2 + 0.004
    y_edge = yc - sb["width_m"] / 2 + sb["groove_m"] / 2
    return {"fx": fx, "rx": rx, "yc": yc, "zf": zf, "zr": zr, "tang": (B["tang_x"], CY, tz + eye),
            "junction": junction, "tramp_x": (x0, x1), "tramp_y": (T["centre_gap_m"] / 2, y_edge)}


def frame_z(L, x):
    """The frame's centre plane at x: linear between the crossbars' centres."""
    return L["zr"] + (L["zf"] - L["zr"]) * (x - L["rx"]) / (L["fx"] - L["rx"])


def tramp_top(L, x, y):
    T = P["trampoline"]
    (x0, x1), (_, ye) = L["tramp_x"], L["tramp_y"]
    u = min(max((x - x0) / (x1 - x0), 0.0), 1.0)
    v = min(max((y + ye) / (2 * ye), 0.0), 1.0)
    return frame_z(L, x) + T["thickness_m"] / 2 - T["sag_m"] * math.sin(math.pi * u) * math.sin(math.pi * v)


# ---- the parts -------------------------------------------------------------------------------------------------------

def build(hounds=None):
    L = layout(hounds)
    F, fc, rc, sb, ca = P["frame"], P["front_crossbar"], P["rear_crossbar"], P["sidebar"], P["casting"]
    fx, rx, yc, zf, zr = L["fx"], L["rx"], L["yc"], L["zf"], L["zr"]
    frame, boss, tramp, bridle = Part("Frame"), Part("Boss"), Part("Tramp"), Part("Bridle")
    span = yc + F["overhang_m"]

    # crossbars across the boat (symmetric profiles, so the sweep's side doesn't matter), their tracks on top
    sweep(frame, [(fx, -span, zf), (fx, span, zf)], rrect(fc["width_m"], fc["height_m"], fc["radius_m"]), "Bar")
    sweep(frame, [(rx, -span, zr), (rx, span, zr)], rrect(rc["width_m"], rc["height_m"], rc["radius_m"]), "Bar")
    tw, th = fc["track_width_m"], fc["track_height_m"]
    for s in (1, -1):        # the jib track either side of the mast step
        sweep(frame, [(fx - fc["track_aft_m"], s * 0.12, zf + fc["height_m"] / 2 - 0.004),
                      (fx - fc["track_aft_m"], s * (yc - 0.12), zf + fc["height_m"] / 2 - 0.004)],
              rrect(tw, th + 0.004, 0.003, 2) + np.array([0, th / 2]), "Bar")
    tw, th = rc["track_width_m"], rc["track_height_m"]
    sweep(frame, [(rx, -(yc - 0.1), zr + rc["height_m"] / 2 - 0.004), (rx, yc - 0.1, zr + rc["height_m"] / 2 - 0.004)],
          rrect(tw, th + 0.004, 0.004, 2) + np.array([0, th / 2]), "Bar")

    # sidebars between the castings, their inboard faces grooved for the trampoline's bolt rope
    prof = rrect(sb["width_m"], sb["height_m"], sb["radius_m"])
    for s in (1, -1):
        path = [(x, s * yc, frame_z(L, x)) for x in np.linspace(rx, fx, 12)]
        sweep(frame, path, prof, "Bar")

    # corner castings: a broad pylon moulded in the deck, a chunky casting on it with a sleeve for each tube
    pw = ca["plan_power"]
    for x, z, hh, ww in ((fx, zf, fc["height_m"], fc["width_m"]), (rx, zr, rc["height_m"], rc["width_m"])):
        for s in (1, -1):
            y = s * yc
            zd = deck_z(x, F["casting_inboard_m"])
            zp = zd + ca["pylon_height_m"]
            a, b, hp = ca["pylon_half_length_m"], ca["pylon_half_width_m"], ca["pylon_height_m"]
            rings = loft(boss, x, y, [(a, b, zd - 0.01), (a * 0.97, b * 0.96, zd + hp * 0.35), (a * 0.9, b * 0.88, zd + hp * 0.75),
                                      (a * 0.84, b * 0.8, zp)], pw, "Hull")
            for k in range(RING_N):      # the foot onto the deck, 4 mm under it
                vx, vy, _ = boss.v[rings[0] + k]
                boss.v[rings[0] + k] = (vx, vy, deck_z(vx, CY - abs(vy)) - 0.004)
            ab, bb, top = ca["body_half_length_m"], ca["body_half_width_m"], z + hh / 2 + ca["over_top_m"]
            loft(frame, x, y, [(ab * 1.08, bb * 1.05, zp - 0.004), (ab, bb, zp + 0.02), (ab, bb, top - 0.012),
                               (ab * 0.94, bb * 0.92, top - 0.003), (ab * 0.8, bb * 0.75, top)], pw, "Corner")
            w, ln = ca["sleeve_wall_m"], ca["sleeve_length_m"]
            # sleeve along the crossbar, inboard
            sweep(frame, [(x, y - s * bb * 0.8, z), (x, y - s * (bb * 0.8 + ln), z)],
                  rrect(ww + 2 * w, hh + 2 * w, 0.03), "Corner")
            # sleeve along the sidebar (aft from the front castings, forward from the rear)
            d = -1 if x == fx else 1
            x1, x2 = x + d * ab * 0.8, x + d * (ab * 0.8 + ln)
            sweep(frame, [(x1, y, frame_z(L, x1)), (x2, y, frame_z(L, x2))],
                  rrect(sb["width_m"] + 2 * w, sb["height_m"] + 2 * w, sb["radius_m"] + w), "Corner")

    # dolphin striker: a post under the front crossbar's middle, a rod from its foot to each front casting
    D = P["dolphin_striker"]
    zt = zf - fc["height_m"] / 2
    zfoot = zt - D["depth_m"]
    lathe(frame, fx, 0.0, [(0.0, zfoot - 0.012), (D["post_radius_m"] * 0.8, zfoot - 0.01), (D["post_radius_m"], zfoot),
                           (D["post_radius_m"], zt + 0.006), (D["post_radius_m"] * 1.8, zt - 0.004),
                           (D["post_radius_m"] * 1.8, zt + 0.008)], "Cast", n=16)
    for s in (1, -1):
        zc = deck_z(fx, F["casting_inboard_m"]) + ca["pylon_height_m"] + 0.025      # the casting's lower inboard face
        sweep(frame, [(fx, s * 0.006, zfoot + 0.008), (fx, s * (yc - ca["body_half_width_m"] * 0.9), zc)],
              circle(D["rod_radius_m"], 8), "Wire", up=(1.0, 0.0, 0.0))

    # the mast step: a plate on the crossbar's middle, a raised pedestal and the ball
    M = P["mast_step"]
    ztop = zf + fc["height_m"] / 2
    box(frame, (fx, 0.0, ztop + M["plate_m"][2] / 2 - 0.003), M["plate_m"], "Corner")
    pr, ph, br = M["pedestal_radius_m"], M["pedestal_height_m"], M["ball_radius_m"]
    z0 = ztop + M["plate_m"][2] - 0.004
    lathe(frame, fx, 0.0, [(pr * 1.1, z0), (pr, z0 + ph * 0.3), (pr * 0.8, z0 + ph), (0.0, z0 + ph + 0.001)], "Corner", n=20)
    zb0 = z0 + ph - 0.006
    ball = [(br * math.sin(a), zb0 + br - br * math.cos(a)) for a in np.linspace(0, math.pi, 10)]
    lathe(frame, fx, 0.0, ball, "Cast", n=20)

    # the trampoline: two halves, sides in the sidebars' grooves, front edge in the front crossbar
    T = P["trampoline"]
    (x0, x1), (yi, ye) = L["tramp_x"], L["tramp_y"]
    xs = np.linspace(x0, x1, 34)
    for s in (1, -1):
        ys = np.linspace(yi, ye, 16)
        grid = np.array([[(x, s * y, tramp_top(L, x, s * y)) for y in (ys if s > 0 else ys[::-1])] for x in xs])
        sheet(tramp, grid, T["thickness_m"], "Tramp")
    # centre lacing: a zigzag across the gap, through grommets 2 cm in from each half's edge
    lr = T["lacing_radius_m"]
    pts, k = [], 0
    for x in np.arange(x0 + 0.04, x1 - 0.02, T["lacing_pitch_m"] / 2):
        y = (yi + 0.02) * (1 if k % 2 == 0 else -1)
        pts.append((x, y, tramp_top(L, x, y) + lr * 0.6))
        k += 1
    sweep(tramp, pts, circle(lr, 6), "Line")
    # rear lacing: each half's rear edge laced to the rear crossbar's lower front face
    zlace = zr - rc["height_m"] * 0.2
    xl = rx + rc["width_m"] / 2 - 0.002
    for s in (1, -1):
        pts, k = [], 0
        for y in np.arange(yi + 0.03, ye - 0.02, T["rear_lacing_pitch_m"] / 2):
            if k % 2 == 0:
                pts.append((x0 + 0.02, s * y, tramp_top(L, x0 + 0.02, s * y) + lr * 0.6))
            else:
                pts.append((xl, s * y, zlace))
            k += 1
        sweep(tramp, pts, circle(lr, 6), "Line", up=(0.0, 0.0, 1.0))

    # the bridle: tangs on the bows, the wires, the bridle plate
    B = P["bridle"]
    tx, ty, tz = L["tang"]
    J = np.array(L["junction"])
    for s in (1, -1):
        box(bridle, (tx, s * ty, tz - 0.012), (0.07, 0.022, 0.012), "Cast")
        box(bridle, (tx + 0.01, s * ty, tz - 0.002), (0.028, 0.005, 0.022), "Cast")
        sweep(bridle, [(tx + 0.01, s * ty, tz), tuple(J + np.array([0, s * 0.02, -0.006]))],
              circle(B["wire_radius_m"], 6), "Wire")
    tri = [(0.0, -0.035, -0.012), (0.0, 0.035, -0.012), (0.0, 0.0, 0.04)]
    plate = Part("tmp")
    for dx in (-0.0025, 0.0025):
        plate.add_verts([J + np.array([dx, a, b]) for _, a, b in tri])
    i0 = bridle.add_verts(plate.v)
    bridle.face((i0, i0 + 1, i0 + 2), "Cast", flat=True)
    bridle.face((i0 + 5, i0 + 4, i0 + 3), "Cast", flat=True)
    for a, b in ((0, 1), (1, 2), (2, 0)):
        bridle.face((i0 + a, i0 + 3 + a, i0 + 3 + b, i0 + b), "Cast", flat=True)
    return [frame, boss, tramp, bridle], L


def report(L):
    """The numbers the docs and the check read: heights over the game's waterline (crew aboard) and empty."""
    hy = H.hydrostatics()
    sink = hy["crew_sink"]
    fc, rc = P["front_crossbar"], P["rear_crossbar"]
    (x0, x1), (yi, ye) = L["tramp_x"], L["tramp_y"]
    xs = np.linspace(x0, x1, 41)
    low = min(tramp_top(L, x, 0.0) for x in xs) - P["trampoline"]["thickness_m"]
    tx, ty, tz = L["tang"]
    J = L["junction"]
    wire = math.dist((tx + 0.01, ty, tz), (J[0], 0.02, J[2] - 0.006))
    zfoot = L["zf"] - fc["height_m"] / 2 - P["dolphin_striker"]["depth_m"]
    return {"front_crossbar_centre_z": round(L["zf"], 3), "front_crossbar_under_z": round(L["zf"] - fc["height_m"] / 2, 3),
            "rear_crossbar_centre_z": round(L["zr"], 3), "rear_crossbar_under_z": round(L["zr"] - rc["height_m"] / 2, 3),
            "tramp_lowest_z": round(low, 3), "tramp_lowest_z_empty": round(low + sink, 3),
            "tramp_length_m": round(x1 - x0, 3), "tramp_width_m": round(2 * ye, 3),
            "tramp_area_m2": round((x1 - x0) * 2 * (ye - yi), 3),
            "dolphin_striker_foot_z": round(zfoot, 3), "bridle_plate": [round(v, 3) for v in J],
            "bridle_wire_m": round(wire, 3), "bridle_tang": [round(v, 3) for v in L["tang"]],
            "mast_step_ball_top": [L["fx"], 0.0, round(L["zf"] + fc["height_m"] / 2 + P["mast_step"]["plate_m"][2] - 0.004
                                                       + P["mast_step"]["pedestal_height_m"] - 0.006
                                                       + 2 * P["mast_step"]["ball_radius_m"], 3)],
            "frame_corner_y": round(L["yc"], 3)}


if __name__ == "__main__":
    H.solve_depth()
    parts, L = build()
    print(json.dumps(report(L), indent=1))
    for p in parts:
        print(f"{p.name}: {len(p.v)} verts, {p.tris()} triangles")
