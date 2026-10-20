"""The maxi's hull and appendages from ref.json: pure geometry (no bpy), shared by the Blender build and the section export.

The hull is lofted from the reference stations: each station's section runs keel -> waterline -> chine -> sheer with a
fixed number of points, the stations are interpolated along the length (Catmull-Rom on each parameter), and the result
is a quad grid the Blender build smooths with a subdivision surface (the chine kept by a crease that fades forward).
Body frame: metres, X forward, Y starboard, Z up, origin on the design waterline amidships.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REF = json.load(open(os.path.join(HERE, "ref.json")))

BOTTOM_PTS = 7   # keel to the chine (or to the round bilge's turn)
SIDE_PTS = 4     # the chine to the sheer
ROWS = BOTTOM_PTS + SIDE_PTS   # points per half section (keel..sheer)


def sheer_z(x):
    """The sheer line: a parabola through the stern, amidships (x 0) and the bow heights."""
    s = REF["sheer"]
    xb, xs = REF["bow_x"], REF["stern_x"]
    if x >= 0:
        t = x / xb
        return s["mid"] + (s["bow"] - s["mid"]) * t * t
    t = x / xs
    return s["mid"] + (s["stern"] - s["mid"]) * t * t


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def _filled(key, st, i):
    """A station parameter, with the round forward sections' stand-in chine (on the section's turn of bilge)."""
    v = st[key]
    if v is not None:
        return v
    if key == "half_chine":
        return st["half_wl"] + 0.72 * (st["half_deck"] - st["half_wl"])
    if key == "z_chine":
        return 0.42 * sheer_z(st["x"])
    raise KeyError(key)


def station_at(x):
    """The station parameters at x (interpolated between the reference stations)."""
    sts = REF["stations"]
    xs = [s["x"] for s in sts]
    x = min(max(x, xs[0]), xs[-1])
    i = max(0, min(len(sts) - 2, max(k for k in range(len(sts)) if xs[k] <= x)))
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    out = {"x": x}
    for key in ("half_deck", "half_chine", "z_chine", "half_wl", "z_keel"):
        vals = [_filled(key, sts[max(0, min(len(sts) - 1, k))], k) for k in (i - 1, i, i + 1, i + 2)]
        out[key] = _catmull(*vals, t)
    # How hard the chine is: 1 aft, gone by u 0.6 (the round forward sections).
    u = (x - REF["stern_x"]) / (REF["bow_x"] - REF["stern_x"])
    out["crease"] = max(0.0, min(1.0, (0.62 - u) / 0.12))
    out["sheer"] = sheer_z(x)
    return out


def section(st):
    """Half section points (y >= 0), keel to sheer: (y, z) pairs, ROWS of them."""
    hk, zk = 0.0, st["z_keel"]
    hw, hc, zc = st["half_wl"], max(st["half_chine"], st["half_wl"] + 0.02), max(st["z_chine"], 0.02)
    hd, zs = st["half_deck"], st["sheer"]
    pts = []
    # Bottom: a deadrise run from the keel, turning up through the waterline breadth into the chine. A quadratic Bezier
    # (keel, a control point at the waterline's height under the chine, the chine).
    ctrl = (0.62 * hw, zk * 0.2)
    for k in range(BOTTOM_PTS):
        t = k / (BOTTOM_PTS - 1)
        t = t ** 0.85
        y = (1 - t) ** 2 * hk + 2 * (1 - t) * t * ctrl[0] + t * t * hc
        z = (1 - t) ** 2 * zk + 2 * (1 - t) * t * ctrl[1] + t * t * zc
        pts.append((y, z))
    # Topsides: chine to sheer, flaring out a little (the deck edge is the widest).
    for k in range(1, SIDE_PTS + 1):
        t = k / SIDE_PTS
        y = hc + (hd - hc) * (1 - (1 - t) ** 1.6)
        z = zc + (zs - zc) * t
        pts.append((y, z))
    return pts


def hull_grid(n_long=48):
    """The lofted half-hull: a list of stations (x, [(y, z) * ROWS], crease), transom first."""
    xs, xb = REF["stern_x"], REF["bow_x"]
    rows = []
    for i in range(n_long + 1):
        u = i / n_long
        # More stations toward the bow, where the sections change fastest.
        uu = u ** 0.92
        x = xs + (xb - xs) * uu
        st = station_at(x)
        rows.append((x, section(st), st["crease"]))
    return rows


def foil_section(chord, thickness, n=14):
    """A NACA 00xx section (x along the chord from the leading edge, y half thickness), closed, n points a side."""
    pts = []
    for k in range(n + 1):
        b = math.pi * k / n
        x = 0.5 * (1 - math.cos(b))
        yt = 5 * thickness * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        pts.append((x * chord, yt * chord))
    return pts


def canoe_volume(n_long=200):
    """Displaced volume (m^3) and the centre of buoyancy (x, z) of the canoe body below z 0 (trapezoid sections)."""
    xs, xb = REF["stern_x"], REF["bow_x"]
    vol = mx = mz = 0.0
    dx = (xb - xs) / n_long
    for i in range(n_long):
        x = xs + (i + 0.5) * dx
        sec = section(station_at(x))
        area = az = 0.0
        for (y0, z0), (y1, z1) in zip(sec, sec[1:]):
            if z0 >= 0 and z1 >= 0:
                continue
            if z1 > 0:
                y1 = y0 + (y1 - y0) * (0 - z0) / (z1 - z0)
                z1 = 0.0
            # The strip between the centreline and the section edge from z0 to z1.
            a = 0.5 * (y0 + y1) * (z1 - z0)
            area += a
            az += a * 0.5 * (z0 + z1)
        area *= 2
        vol += area * dx
        mx += area * dx * x
        mz += 2 * az * dx
    return vol, (mx / vol if vol else 0.0), (mz / vol if vol else 0.0)


def export_sections(path, n=21):
    """The hull's sections for the Mac's physics class (body frame, metres): n stations, half sections keel to sheer."""
    xs, xb = REF["stern_x"], REF["bow_x"]
    out = {"tag": REF["tag"], "frame": "metres, X forward, Y starboard, Z up, origin on the DWL amidships", "stations": []}
    for i in range(n):
        x = xs + (xb - xs) * i / (n - 1)
        st = station_at(x)
        out["stations"].append({"x": round(x, 4), "half_section": [[round(y, 4), round(z, 4)] for y, z in section(st)],
                                "sheer": round(st["sheer"], 4), "half_wl": round(st["half_wl"], 4)})
    vol, cbx, cbz = canoe_volume()
    out["canoe_volume_m3"] = round(vol, 3)
    out["canoe_displacement_kg"] = round(vol * 1025.0)
    out["centre_of_buoyancy"] = [round(cbx, 3), round(cbz, 3)]
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    import sys
    o = export_sections(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "sections.json"))
    print(f"Maxi sections: canoe {o['canoe_volume_m3']} m^3 ({o['canoe_displacement_kg']} kg), CB {o['centre_of_buoyancy']}")
