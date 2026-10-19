"""A port's piers file from OpenStreetMap (no lidar pack): Content/TerrainData/<World>.piers, the format build_piers.py
writes for Galveston (FLakeData::LoadPiers reads both).

- "decks": fixed piers mapped as areas (man_made=pier, not floating), at the world's deck height above the datum.
- "riprap": breakwaters and groynes, centrelines with crest and width (OSM width= when mapped, else the world's
  defaults; a named breakwater is drawn with boulders, an unnamed one as a groin).
- "walkways": floating pontoons (man_made=pier + floating=yes), with OSM's width or 2.5 m.
- "boats": moored boats laid along both sides of every pontoon, Mediterranean style: stern-to on lazy lines,
  perpendicular to the pontoon, bow out, a metre of gangway between the transom and the pontoon. A boat goes only where
  the water under her is deeper than her draft and she crosses no land, pontoon or other boat. Lengths, power or sail
  and the gaps between them come from a hash of the position (stable across rebakes).
- "marinas": each harbour of the world json with its boat count.

Run: Tools/venv/bin/python -I Tools/coast/build_piers.py Marseille   (after build_coast.py Marseille)
"""
import glob
import json
import math
import os
import struct
import zlib

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "Content", "TerrainData")


def hash01(*k):
    return (zlib.crc32(":".join(str(x) for x in k).encode()) & 0xFFFFFF) / float(0xFFFFFF)


def draft_m(length, mast):
    """As build_piers.draft_m: keelboats 0.3 + 0.13 L, power boats 0.2 + 0.07 L."""
    return 0.3 + 0.13 * length if mast else 0.2 + 0.07 * length


def load_height(world):
    with open(os.path.join(DATA, f"{world}.height"), "rb") as f:
        data = f.read()
    _, _, nx, ny, cell, x0, y0, unit = struct.unpack("<4sIIIffff", data[:32])
    h = np.frombuffer(data[32:32 + nx * ny * 2], "<i2").reshape(ny, nx).astype(np.float64) * unit
    return h, cell, x0, y0


def build(world_name):
    cfg = json.load(open(os.path.join(os.path.dirname(__file__), "worlds", f"{world_name}.json")))
    meta = json.load(open(os.path.join(DATA, f"{world_name}.json")))
    raw = os.path.join(ROOT, "Data", world_name, "raw")
    to_map = Transformer.from_crs("EPSG:4326", meta["projection"], always_xy=True)
    H, CELL, X0, Y0 = load_height(world_name)
    NY, NX = H.shape
    hc = cfg.get("harbour_kit", {})
    deck_h = float(hc.get("deck_m", 1.4))
    bw_crest, bw_width = float(hc.get("breakwater_crest_m", 4.0)), float(hc.get("breakwater_width_m", 12.0))
    groyne_crest, groyne_width = float(hc.get("groyne_crest_m", 1.5)), float(hc.get("groyne_width_m", 6.0))

    def xy(coords):
        e, n = to_map.transform([c[0] for c in coords], [c[1] for c in coords])
        return [(nn, ee) for nn, ee in zip(n, e)]

    def height(p):
        r, c = int(round((p[0] - X0) / CELL)), int(round((p[1] - Y0) / CELL))
        return H[r, c] if 0 <= r < NY and 0 <= c < NX else 99.0

    def rnd(v):
        return round(float(v), 2)

    els = []
    for p in sorted(glob.glob(os.path.join(raw, "harbours_osm*.json"))):
        els += json.load(open(p)).get("elements", [])
    decks, riprap, walkways, pontoons, fixed_lines = [], [], [], [], []
    for el in els:
        t = el.get("tags", {})
        mm = t.get("man_made")
        if el["type"] != "way" or mm not in ("pier", "breakwater", "groyne") or len(el.get("geometry", [])) < 2:
            continue
        pts = xy([(q["lon"], q["lat"]) for q in el["geometry"]])
        closed = len(pts) >= 4 and pts[0] == pts[-1]
        try:
            width = float(str(t.get("width", "")).replace("m", "").strip())
        except ValueError:
            width = None
        if mm == "pier" and t.get("floating") == "yes":
            line = LineString(pts)
            if closed:
                # A pontoon mapped as an outline: its long axis.
                mrr = np.array(Polygon(pts).minimum_rotated_rectangle.exterior.coords)[:4]
                d0, d1 = np.linalg.norm(mrr[1] - mrr[0]), np.linalg.norm(mrr[2] - mrr[1])
                a, b = ((mrr[0] + mrr[3]) / 2, (mrr[1] + mrr[2]) / 2) if d0 >= d1 else ((mrr[0] + mrr[1]) / 2, (mrr[2] + mrr[3]) / 2)
                line, width = LineString([a, b]), width or float(min(d0, d1))
            w = float(np.clip(width or 2.5, 1.2, 6.0))
            walkways.append({"w": rnd(w), "pts": [[rnd(a), rnd(b)] for a, b in line.coords]})
            pontoons.append((line, w, el["id"]))
        elif mm == "pier":
            if not closed:
                # A pier drawn as a line inside a harbour is a berthing pier (Pointe Rouge, Cassis map theirs untagged):
                # boats go along it like a pontoon's (it stays in the world json as a fixed pier).
                fixed_lines.append((LineString(pts), float(np.clip(width or 2.5, 1.2, 6.0)), el["id"]))
            if closed:
                # A long thin outline (the cadastre's piers at Pointe Rouge) berths boats along its long axis too.
                mrr = np.array(Polygon(pts).minimum_rotated_rectangle.exterior.coords)[:4]
                d0, d1 = np.linalg.norm(mrr[1] - mrr[0]), np.linalg.norm(mrr[2] - mrr[1])
                if max(d0, d1) > 4.0 * min(d0, d1) and min(d0, d1) < 8.0:
                    a, b = ((mrr[0] + mrr[3]) / 2, (mrr[1] + mrr[2]) / 2) if d0 >= d1 else ((mrr[0] + mrr[1]) / 2, (mrr[2] + mrr[3]) / 2)
                    fixed_lines.append((LineString([a, b]), float(min(d0, d1)), el["id"]))
            if closed and Polygon(pts).area > 20.0:
                decks.append({"pts": [[rnd(a), rnd(b)] for a, b in pts], "deck": deck_h, "covered": False, "kind": "pier"})
        else:
            crest, wid = (bw_crest, bw_width) if mm == "breakwater" else (groyne_crest, groyne_width)
            line = LineString(pts)
            if closed:
                # A breakwater mapped as an area: its centreline is the long axis of each part; the width is its own.
                poly = Polygon(pts)
                wid = float(np.clip(2.0 * poly.area / max(poly.exterior.length, 1.0) * 2.0, 4.0, 40.0))
                mrr = np.array(poly.minimum_rotated_rectangle.exterior.coords)[:4]
                d0, d1 = np.linalg.norm(mrr[1] - mrr[0]), np.linalg.norm(mrr[2] - mrr[1])
                a, b = ((mrr[0] + mrr[3]) / 2, (mrr[1] + mrr[2]) / 2) if d0 >= d1 else ((mrr[0] + mrr[1]) / 2, (mrr[2] + mrr[3]) / 2)
                line = LineString([a, b])
            item = {"kind": "breakwater" if mm == "breakwater" else "groyne", "width": rnd(width or wid), "crest": rnd(crest),
                    "pts": [[rnd(a), rnd(b)] for a, b in line.coords]}
            if t.get("name") or mm == "breakwater":
                item["name"] = t.get("name") or "breakwater"
            riprap.append(item)

    # Harbours: polygons around the world's harbour points (the bake's harbour list), for the marina index.
    harbours = []
    for h in cfg.get("harbours", []):
        e, n = to_map.transform(h["lon"], h["lat"])
        harbours.append((h["name"], Point(n, e).buffer(float(h.get("radius_m", 700.0)))))

    # Berthing piers: the fixed pier lines inside a harbour.
    pontoons += [f for f in fixed_lines if any(poly.contains(f[0].centroid) for _, poly in harbours) and f[0].length < 400.0]

    # Moored boats along both sides of every pontoon.
    obstacles = shapely.STRtree([ln.buffer(w / 2.0 + 0.3) for ln, w, _ in pontoons])
    occupied = []
    boats, skipped = [], {"shallow": 0, "blocked": 0}
    for ln, w, pid in pontoons:
        L = ln.length
        if L < 6.0:
            continue
        for side in (+1, -1):
            s = 2.0
            while s < L - 2.0:
                p = np.array(ln.interpolate(s).coords[0])
                q = np.array(ln.interpolate(min(s + 0.5, L)).coords[0]) - np.array(ln.interpolate(max(s - 0.5, 0)).coords[0])
                q /= np.linalg.norm(q) + 1e-9
                normal = np.array([-q[1], q[0]]) * side
                u = hash01(world_name, pid, side, round(s, 1))
                mast = hash01(world_name, pid, side, round(s, 1), "m") < float(hc.get("sail_share", 0.65))
                length = 7.0 + 8.0 * u ** 1.6 if mast else 6.0 + 7.0 * u ** 1.4
                beam = 0.33 * length + 0.2
                stern = p + normal * (w / 2.0 + 1.0)
                centre = stern + normal * (length / 2.0)
                bowpt = stern + normal * length
                hull = shapely.Polygon([stern + q * beam / 2, bowpt + q * beam / 2 * 0.3, bowpt - q * beam / 2 * 0.3, stern - q * beam / 2])
                dr = draft_m(length, mast)
                if max(height(stern), height(centre), height(bowpt)) > -(dr + 0.2):
                    skipped["shallow"] += 1
                    s += beam + 0.6
                    continue
                if any(hull.intersects(obstacles.geometries[i]) for i in obstacles.query(hull)) or any(hull.intersects(o) for o in occupied[-400:]):
                    skipped["blocked"] += 1
                    s += 1.5
                    continue
                gap = beam + 0.4 + 0.6 * hash01(world_name, pid, side, round(s, 1), "g")
                if hash01(world_name, pid, side, round(s, 1), "e") < float(hc.get("empty_berths", 0.12)):
                    s += gap
                    continue   # an empty berth
                occupied.append(hull)
                hdg = math.degrees(math.atan2(normal[1], normal[0])) % 360.0
                owner = next((i for i, (_, poly) in enumerate(harbours) if poly.contains(Point(*centre))), -1)
                boats.append([rnd(centre[0]), rnd(centre[1]), rnd(hdg), rnd(length), rnd(beam), int(mast), owner])
                s += gap
    marinas = [{"name": n, "boats": sum(1 for b in boats if b[6] == i)} for i, (n, _) in enumerate(harbours)]
    out = {"schema": 1, "source": "OpenStreetMap piers, pontoons and breakwaters (ODbL); boats laid stern-to along the pontoons",
           "frame": "[north, east] m, heights m above the world's datum", "decks": decks, "riprap": riprap, "walkways": walkways,
           "boats": boats, "marinas": marinas}
    path = os.path.join(DATA, f"{world_name}.piers")
    with open(path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{world_name}: decks {len(decks)}, riprap {len(riprap)}, walkways {len(walkways)}, boats {len(boats)} "
          f"({sum(b[5] for b in boats)} masts; left out {skipped['shallow']} shallow, {skipped['blocked']} blocked); "
          f"{', '.join(f'{m['name']} {m['boats']}' for m in marinas)}; {os.path.getsize(path) / 1e6:.1f} MB -> {path}")
