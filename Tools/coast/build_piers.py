"""Graphics G7: bakes the G2 piers pack (Inputs/g2/piers) into Content/TerrainData/GalvestonBay.piers for the game.

What it writes (JSON, the map frame: [north, east] metres, heights above MLLW like the rest of the coast bake):
- "decks": over-water structures standing on piles (lidar piers, dock complexes, wharves, covered slips, the better
  small decks), each an outline with its deck height. The game draws them with the pier kit and they stop the boat.
- "riprap": jetties, groins, breakwaters, the Texas City Dike and the Seawall, centrelines with crest and width. Pieces
  the OSM breakwaters already cover are left out.
- "walkways": floating docks, which the lidar cannot see (0.5 m above the water, inside its noise), inferred from the rows
  of moored boats inside each marina (README: "draw the walkways between the rows"): a main walkway along the bows of
  each row (between two facing rows when there are two) and a finger between each pair of neighbours.
- "boats": every moored boat: [north, east, bow heading deg, length, beam, mast 0/1, marina index or -1]. The bow points
  at the row's walkway in a marina (bow in), elsewhere at the nearest deck within 15 m, else along the hull axis.
- "marinas": each marina's hull and boat count.

Run: Tools/venv/bin/python Tools/coast/build_piers.py   (then scripts/test.sh SailingSim.Coast and rebake the shore)
"""
import gzip
import json
import math
import os
import sys

import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon, MultiPolygon
from shapely.prepared import prep

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.path.join(REPO, "Inputs", "g2", "piers")
# Galveston 2: the Gulf front (Inputs/g2/gulf-front, README there): the whole Seawall, both jetties to their head lights,
# the Gulf piers and groins, and the piers-pack layers for the island south of the old grid edge (piers/).
GULF = os.path.join(REPO, "Inputs", "g2", "gulf-front")
DATA = os.path.join(REPO, "Content", "TerrainData")
NAVD_TO_MLLW = 0.094

KEEP_DECKS = {"pier", "dock_complex", "platform_or_wharf", "covered_slip_or_building"}


def load(name, pack=PACK):
    path = os.path.join(pack, name)
    if os.path.exists(path + ".gz"):
        return json.load(gzip.open(path + ".gz"))
    return json.load(open(path))


def load_both(name):
    """A piers-pack layer from the bay pack and the Gulf front's piers/ (same fields), features together."""
    feats = list(load(name)["features"])
    if os.path.exists(os.path.join(GULF, "piers", name)) or os.path.exists(os.path.join(GULF, "piers", name + ".gz")):
        feats += load(name, os.path.join(GULF, "piers"))["features"]
    return feats


def draft_m(length, mast):
    """A moored boat's draft from her length: keelboats about 0.3 + 0.13 L (a J/22 1.2 m, a 40-footer 1.9 m), power boats
    0.2 + 0.07 L (a 25 ft runabout 0.7 m, a 50 ft trawler 1.3 m)."""
    return 0.3 + 0.13 * length if mast else 0.2 + 0.07 * length


def main():
    bay = json.load(open(os.path.join(DATA, "GalvestonBay.json")))
    to_map = Transformer.from_crs("EPSG:4326", bay["projection"], always_xy=True)

    def project(coords):
        xs, ys = to_map.transform([c[0] for c in coords], [c[1] for c in coords])
        return [(y, x) for x, y in zip(xs, ys)]   # (north, east)

    def r(v):
        return round(float(v), 2)

    # The pack's own sim coordinates agree with this projection (a check that the frame is the same).
    boats_in = load_both("moored_boats_2018.geojson")
    p0 = boats_in[0]
    n0, e0 = project([p0["geometry"]["coordinates"]])[0]
    assert abs(n0 - p0["properties"]["sim_north"]) < 1.0 and abs(e0 - p0["properties"]["sim_east"]) < 1.0, (n0, e0, p0["properties"])

    osm_breakwaters = [LineString([(p[0], p[1]) for p in d["points"]]) for d in bay["docks"] if d["kind"] == "breakwater" and len(d["points"]) >= 2]
    osm_bw_index = cKDTree(np.array([c for l in osm_breakwaters for c in l.coords])) if osm_breakwaters else None

    # The game's terrain (Content/TerrainData/GalvestonBay.height, 10 m, metres above MLLW).
    raw = open(os.path.join(DATA, "GalvestonBay.height"), "rb").read()
    nx, ny = (int(v) for v in np.frombuffer(raw, "<u4", 2, 8))
    cell, ox, oy, unit = (float(v) for v in np.frombuffer(raw, "<f4", 4, 16))
    H = np.frombuffer(raw, "<i2", nx * ny, 32).reshape(ny, nx).astype(np.float32) * unit

    def height(pt):
        rr = (pt[0] - ox) / cell
        cc = (pt[1] - oy) / cell
        if rr < -1.0 or cc < -1.0 or rr > ny or cc > nx:
            return 50.0   # off the map: land, as FLakeTerrain::HeightAt has it
        r0 = int(np.clip(math.floor(rr), 0, ny - 2))
        c0 = int(np.clip(math.floor(cc), 0, nx - 2))
        fr, fc = min(max(rr - r0, 0.0), 1.0), min(max(cc - c0, 0.0), 1.0)
        return float(H[r0, c0] * (1 - fr) * (1 - fc) + H[r0 + 1, c0] * fr * (1 - fc) + H[r0, c0 + 1] * (1 - fr) * fc + H[r0 + 1, c0 + 1] * fr * fc)

    # ---------------------------------------------------------------- decks
    decks = []
    deck_polys = []
    counts = {}
    gulf_named = load("gulf_piers.geojson", GULF)["features"]
    for f in gulf_named:
        f["properties"].setdefault("attached_to_shore", True)
        f["properties"].setdefault("fill", 1.0)
        f["properties"].setdefault("area_m2", f["properties"]["length_m"] * f["properties"]["width_m"])
        f["properties"].setdefault("surface_roughness_m", 0.0)
    for f in gulf_named + load_both("overwater_structures.geojson"):
        p = f["properties"]
        kind = p["kind"]
        small_ok = kind == "deck_small" and p["area_m2"] >= 25 and 0.4 <= p["deck_above_water_m"] <= 4.0 and p["surface_roughness_m"] < 0.25
        if kind not in KEEP_DECKS and not small_ok:
            continue
        # Free-standing and under 0.9 m above the water, smooth and ragged: oyster reef and shoal tops, not decks on piles.
        if not p["attached_to_shore"] and (p["deck_above_water_m"] < 0.9 or p["fill"] < 0.3):
            continue
        if kind == "covered_slip_or_building" and p["area_m2"] > 4000:
            continue   # big buildings on piles: the houses bake has them
        rings = f["geometry"]["coordinates"]
        poly = Polygon(project(rings[0]), [project(h) for h in rings[1:]]).buffer(0)
        if poly.is_empty:
            continue
        poly = poly.simplify(0.6, preserve_topology=True)
        polys = list(poly.geoms) if isinstance(poly, MultiPolygon) else [poly]
        for g in polys:
            if g.area < 8:
                continue
            # Only decks that reach the bay's water as the 10 m grid has it (the rest stand in canals it shows as land).
            if min(height(c) for c in g.exterior.coords) > 0.3:
                continue
            outline = [[r(n), r(e)] for n, e in g.exterior.coords]
            deck = {"kind": kind if kind != "deck_small" else "deck", "deck": r(p["sim_deck_z"]), "attached": bool(p["attached_to_shore"]),
                    "covered": kind == "covered_slip_or_building", "pts": outline}
            if p.get("name"):
                deck["name"] = p["name"]
            if any(g.intersects(o) and g.intersection(o).area > 0.5 * min(g.area, o.area) for o in deck_polys):
                continue   # the Gulf front's named piers come twice (the pack's polygons and gulf_piers): keep the first
            decks.append(deck)
            deck_polys.append(g)
            counts[kind] = counts.get(kind, 0) + 1
    # The chart's Gulf-front piers the lidar missed (too low over the water: the 61st Street pier's walkway, the T-headed
    # structure near -94.801). The chart gives no height: a Gulf fishing pier's deck stands about 3 m above MLLW.
    charted = load("charted_structures.geojson", GULF)["features"]
    chart_piers = 0
    for f in charted:
        if f["properties"].get("chart_kind") != "pier":
            continue
        cs = f["geometry"]["coordinates"]
        ring = cs[0] if f["geometry"]["type"] == "Polygon" else cs
        if len(ring) < 4:
            continue
        g = Polygon(project(ring)).buffer(0)
        if g.is_empty or g.area < 20:
            g = LineString(project(ring)).buffer(1.5)   # an open pier line: a 3 m walkway
        if isinstance(g, MultiPolygon):
            g = max(g.geoms, key=lambda q: q.area)
        covered = sum(g.intersection(o).area for o in deck_polys if g.intersects(o))
        if covered > 0.3 * g.area or min(height(c) for c in g.exterior.coords) > 0.3:
            continue
        g = g.simplify(0.6, preserve_topology=True)
        decks.append({"kind": "pier", "deck": 3.0, "attached": True, "covered": False, "charted": True,
                      "pts": [[r(n), r(e)] for n, e in g.exterior.coords]})
        deck_polys.append(g)
        chart_piers += 1
    counts["charted_pier"] = chart_piers

    deck_tree = None
    deck_pts = []
    for i, g in enumerate(deck_polys):
        for c in g.exterior.coords:
            deck_pts.append((c[0], c[1], i))
    if deck_pts:
        deck_tree = cKDTree(np.array([(a, b) for a, b, _ in deck_pts]))

    # ---------------------------------------------------------------- riprap
    riprap = []
    # The Gulf front's landmarks replace the bay pack's Seawall end and jetties (the whole wall, the jetties to their
    # head lights); the Texas City Dike stays the bay pack's. The lights and the named piers are points and decks.
    gulf_landmarks = [f for f in load("landmarks.geojson", GULF)["features"] if f["geometry"]["type"] == "LineString"]
    gulf_names = {f["properties"]["name"] for f in gulf_landmarks}
    landmarks = [f for f in load("landmarks.geojson")["features"] if f["properties"]["name"] not in gulf_names] + gulf_landmarks
    for f in landmarks:
        p = f["properties"]
        pts = project(f["geometry"]["coordinates"])
        if p["kind"] == "seawall":
            riprap.append({"kind": "seawall", "name": p["name"], "crest": r(p["sim_crest_z"]), "width": 5.0, "faces": r(p["faces_deg"]),
                           "pts": [[r(n), r(e)] for n, e in pts]})
        elif "Dike" in (p.get("name") or ""):
            riprap.append({"kind": "dike", "name": p["name"], "crest": r(p.get("sim_crest_z", 2.57)), "width": r(p.get("width_m_guess") or p.get("width_m") or 41.0),
                           "pts": [[r(n), r(e)] for n, e in pts]})
        else:
            riprap.append({"kind": "jetty", "name": p["name"], "crest": r(p.get("sim_crest_z", 1.3)), "width": r(p.get("width_m_guess", 12.0)),
                           "pts": [[r(n), r(e)] for n, e in pts]})
    landmark_lines = [LineString([(a, b) for a, b in rr["pts"]]) for rr in riprap]
    narrow_props = {f["properties"]["id"]: f["properties"] for f in load_both("narrow_structures.geojson")}
    for f in load("groins.geojson", GULF)["features"]:
        narrow_props.setdefault(f["properties"]["id"], f["properties"])
    skipped_osm = skipped_landmark = 0
    seen_ids = set()
    for f in load_both("narrow_structures_centrelines.geojson") + load("groins.geojson", GULF)["features"]:
        if f["properties"]["id"] in seen_ids:
            continue
        seen_ids.add(f["properties"]["id"])
        p = narrow_props.get(f["properties"]["id"], f["properties"])
        kind = p["kind"]
        if kind not in ("jetty", "groin", "breakwater", "dike_or_causeway"):
            continue
        line = LineString(project(f["geometry"]["coordinates"]))
        if line.length < 30:
            continue
        samples = [line.interpolate(t, normalized=True) for t in np.linspace(0, 1, 9)]
        if any(min(l.distance(s) for s in samples[3:6]) < 25 for l in landmark_lines):
            skipped_landmark += 1
            continue
        if osm_bw_index is not None:
            near = sum(1 for s in samples if osm_bw_index.query([s.x, s.y])[0] < 12.0)
            if near >= 6:
                skipped_osm += 1
                continue
        crest = p.get("crest_z_navd88", 1.0) + NAVD_TO_MLLW
        width = min(max(p.get("mean_width_m", 8.0), 4.0), 30.0)
        riprap.append({"kind": "dike" if kind == "dike_or_causeway" else kind, "crest": r(crest), "width": r(width),
                       "pts": [[r(c[0]), r(c[1])] for c in line.simplify(1.0).coords]})

    # The chart's Gulf groins and breakwaters the lidar didn't see (awash or low): a low rock line, unless one is there.
    have = [LineString([(a, b) for a, b in rr["pts"]]) for rr in riprap if len(rr["pts"]) >= 2]
    chart_groins = 0
    for f in charted:
        if f["properties"].get("chart_kind") != "breakwater" or f["geometry"]["type"] != "LineString":
            continue
        line = LineString(project(f["geometry"]["coordinates"]))
        if line.length < 20:
            continue
        samples = [line.interpolate(t, normalized=True) for t in np.linspace(0, 1, 7)]
        if sum(1 for q in samples if any(l.distance(q) < 15 for l in have)) >= 4:
            continue
        riprap.append({"kind": "groin", "crest": 1.0, "width": 8.0, "charted": True, "pts": [[r(c[0]), r(c[1])] for c in line.simplify(1.0).coords]})
        have.append(line)
        chart_groins += 1
    print(f"charted Gulf piers added {chart_piers}, groins and breakwaters added {chart_groins}")

    # ---------------------------------------------------------------- marinas and boats
    marinas_in = load_both("marinas.geojson")
    marina_polys = []
    marinas = []
    for f in marinas_in:
        g = Polygon(project(f["geometry"]["coordinates"][0])).buffer(0)
        marina_polys.append(prep(g.buffer(8)))
        marinas.append({"name": f["properties"].get("name") or "", "boats": f["properties"]["boats_2018"],
                        "pts": [[r(n), r(e)] for n, e in g.simplify(2.0).exterior.coords], "centre": [r(g.centroid.x), r(g.centroid.y)]})
    from shapely.strtree import STRtree
    pier_lines = [LineString([(p_[0], p_[1]) for p_ in dk["points"]]) for dk in bay["docks"] if dk["kind"] != "breakwater" and len(dk["points"]) >= 2]
    pier_index = STRtree(pier_lines)
    deck_index = STRtree(deck_polys)
    B = []
    on_land = shallow = overlapping = 0
    for f in boats_in:
        p = f["properties"]
        n, e = project([f["geometry"]["coordinates"]])[0]
        # Galveston 2: a boat floats only where the grid has water under her keel at MLLW (the chart datum, the lowest
        # normal tide): deeper than her draft, or wet at MLLW inside a marina (dredged basins the 10 m cells average
        # with their banks). Elsewhere (narrow canals the 10 m grid fills, boat yards, the flats at low water) she would
        # sit on the ground, so she is left out.
        ground = height((n, e))
        in_marina = any(mp.contains(Point(n, e)) for mp in marina_polys)
        if ground > 0.0:
            on_land += 1
            continue
        if ground > -draft_m(p["length_m"], p["mast_seen"]) and not in_marina:
            shallow += 1
            continue
        # Where the 2018 boat and a dock drawn later disagree (a hull through an OSM pier or a lidar deck), keep the dock.
        hull = Point(n, e).buffer(0.45 * p["beam_m"])
        if any(pier_lines[k].intersects(hull) for k in pier_index.query(hull)) or any(deck_polys[k].intersects(hull) for k in deck_index.query(hull)):
            overlapping += 1
            continue
        B.append([n, e, p["heading_deg"], p["length_m"], p["beam_m"], 1 if p["mast_seen"] else 0])
    B = np.array(B, dtype=float)
    owner = np.full(len(B), -1)
    for mi, mp in enumerate(marina_polys):
        for bi in range(len(B)):
            if owner[bi] < 0 and mp.contains(Point(B[bi, 0], B[bi, 1])):
                owner[bi] = mi
    bow = B[:, 2].copy()   # bow heading, decided below (the pack's heading is the hull axis, 0..180)
    decided = np.zeros(len(B), dtype=bool)

    walkways = []
    def axis(deg):
        a = math.radians(deg)
        return np.array([math.cos(a), math.sin(a)])   # (north, east) for a compass heading

    # Existing structure to tie to: OSM piers (open lines) and the lidar decks' outlines, sampled every 2 m.
    served = []
    for dk in bay["docks"]:
        if dk["kind"] == "breakwater":
            continue
        pts = dk["points"]
        for a_, b_ in zip(pts[:-1], pts[1:]):
            n_ = max(1, int(math.dist(a_, b_) / 2.0))
            for t in range(n_ + 1):
                served.append((a_[0] + (b_[0] - a_[0]) * t / n_, a_[1] + (b_[1] - a_[1]) * t / n_))
    for g in deck_polys:
        ring = g.exterior
        for t in np.arange(0, ring.length, 2.0):
            q = ring.interpolate(t)
            served.append((q.x, q.y))
    served_tree = cKDTree(np.array(served))

    def along(p0, p1, step=3.0):
        L_ = float(np.linalg.norm(p1 - p0))
        n_ = max(1, int(L_ / step))
        return [p0 + (p1 - p0) * t / n_ for t in range(n_ + 1)]

    rows_built = rows_served = 0
    for mi in range(len(marina_polys)):
        idx = np.where(owner == mi)[0]
        if len(idx) < 3:
            continue
        remaining = list(idx)
        while remaining:
            hs = B[remaining, 2]
            hist = np.histogram(hs, bins=18, range=(0, 180))[0]
            centre = (np.argmax(hist) + 0.5) * 10.0
            diff = np.abs(((hs - centre + 90) % 180) - 90)
            group = [remaining[k] for k in range(len(remaining)) if diff[k] < 15]
            if not group:
                group = [remaining[0]]
            gs = set(group)
            remaining = [b for b in remaining if b not in gs]
            hdg = float(np.median(((B[group, 2] - centre + 90) % 180) - 90) + centre)
            u, v = axis(hdg), axis(hdg + 90)
            P = B[group, :2]
            a = P @ u
            w = P @ v
            # Rows: runs of boats side by side (centres level along the hull axis, neighbours a beam or two apart).
            parent = list(range(len(group)))
            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x
            tree = cKDTree(P)
            for i, j in tree.query_pairs(12.0):
                if abs(a[i] - a[j]) < 3.0 and abs(w[i] - w[j]) < max(B[group[i], 4], B[group[j], 4]) + 5.0:
                    parent[find(i)] = find(j)
            comps = {}
            for k in range(len(group)):
                comps.setdefault(find(k), []).append(k)
            rows = [rw for rw in comps.values() if len(rw) >= 3]
            info = []
            for rw in rows:
                L = float(np.median(B[[group[k] for k in rw], 3]))
                info.append({"rw": rw, "a": float(np.median(a[rw])), "w0": float(min(w[rw])), "w1": float(max(w[rw])), "L": L})
            def bow_line(ri, side, off=1.2):
                it = info[ri]
                aa = it["a"] + side * (0.5 * it["L"] + off)
                return u * aa + v * (it["w0"] - 1.0), u * aa + v * (it["w1"] + 1.0)
            def served_frac(ri, side):
                pts = along(*bow_line(ri, side, 1.0))
                d, _ = served_tree.query(np.array(pts))
                return float(np.mean(d < 3.5))
            sides = {}
            for ri, it in enumerate(info):
                fr = {s_: served_frac(ri, s_) for s_ in (+1, -1)}
                best = max(fr, key=fr.get)
                if fr[best] >= 0.5:
                    sides[ri] = (best, "served")
            # Facing rows that share one walkway between their bows.
            for ri, it in enumerate(info):
                if ri in sides:
                    continue
                for rj, jt in enumerate(info):
                    if rj == ri or rj in sides or jt["a"] <= it["a"]:
                        continue
                    need = 0.5 * (it["L"] + jt["L"])
                    overlap = min(it["w1"], jt["w1"]) - max(it["w0"], jt["w0"])
                    if need + 1.5 <= jt["a"] - it["a"] <= need + 7.0 and overlap > 0.4 * min(it["w1"] - it["w0"], jt["w1"] - jt["w0"]):
                        mid = 0.5 * (it["a"] + 0.5 * it["L"] + jt["a"] - 0.5 * jt["L"])
                        w0, w1 = min(it["w0"], jt["w0"]) - 2.0, max(it["w1"], jt["w1"]) + 2.0
                        p0, p1 = u * mid + v * w0, u * mid + v * w1
                        walkways.append({"w": 1.8, "pts": [[r(p0[0]), r(p0[1])], [r(p1[0]), r(p1[1])]]})
                        sides[ri] = (+1, mid)
                        sides[rj] = (-1, mid)
                        rows_built += 2
                        break
            for ri, it in enumerate(info):
                if ri in sides:
                    continue
                # A single row: its walkway along the bows on the landward side (from the terrain).
                c = u * it["a"] + v * 0.5 * (it["w0"] + it["w1"])
                hp = {s_: height(c + u * s_ * (0.5 * it["L"] + 12.0)) for s_ in (+1, -1)}
                side = +1 if hp[+1] >= hp[-1] else -1
                p0, p1 = bow_line(ri, side)
                walkways.append({"w": 1.8, "pts": [[r(p0[0]), r(p0[1])], [r(p1[0]), r(p1[1])]]})
                sides[ri] = (side, it["a"] + side * (0.5 * it["L"] + 1.2))
                rows_built += 1
            for ri, it in enumerate(info):
                side, walk = sides[ri]
                if walk == "served":
                    rows_served += 1
                    walk = it["a"] + side * (0.5 * it["L"] + 1.0)
                # Fingers between neighbours, out from the walkway to about two-thirds of a boat length.
                ws = sorted(w[it["rw"]])
                for k in range(len(ws) - 1):
                    if ws[k + 1] - ws[k] > 9.0:
                        continue
                    mid = 0.5 * (ws[k] + ws[k + 1])
                    p0 = u * (walk - side * 0.9) + v * mid
                    p1 = u * (walk - side * (0.9 + 0.65 * it["L"])) + v * mid
                    if served_tree.query(0.5 * (p0 + p1))[0] < 1.0:
                        continue   # a finger is there already
                    walkways.append({"w": 0.6, "pts": [[r(p0[0]), r(p0[1])], [r(p1[0]), r(p1[1])]]})
                for k in it["rw"]:
                    b = group[k]
                    bow[b] = (hdg if side > 0 else hdg + 180.0) % 360.0
                    decided[b] = True
    print(f"rows: {rows_built} given walkways, {rows_served} on docks already there")

    # Boats outside the marinas (private docks on the canals): bow toward the nearest deck within 15 m.
    for bi in np.where(~decided)[0]:
        pt = B[bi, :2]
        best = None
        if deck_tree is not None:
            d, k = deck_tree.query(pt)
            if d < 15.0:
                best = deck_pts[k]
        u = axis(B[bi, 2])
        if best is not None:
            to = np.array(best[:2]) - pt
            bow[bi] = B[bi, 2] if to @ u >= 0 else (B[bi, 2] + 180.0) % 360.0
        else:
            bow[bi] = B[bi, 2] if (int(bi) * 2654435761) & 1 else (B[bi, 2] + 180.0) % 360.0

    boats = [[r(B[i, 0]), r(B[i, 1]), r(bow[i]), r(B[i, 3]), r(B[i, 4]), int(B[i, 5]), int(owner[i])] for i in range(len(B))]
    out = {"schema": 1, "source": "Inputs/g2/piers and Inputs/g2/gulf-front (G2 add-ons, 2018 USGS lidar, 2022 NAIP, NOAA ENC)", "frame": "[north, east] m, heights m above MLLW",
           "decks": decks, "riprap": riprap, "walkways": walkways, "boats": boats, "marinas": marinas}
    path = os.path.join(DATA, "GalvestonBay.piers")
    with open(path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"decks {len(decks)} {counts}; riprap {len(riprap)} (skipped {skipped_osm} on OSM breakwaters, {skipped_landmark} on the landmarks); "
          f"walkways {len(walkways)}; boats {len(boats)} (left out {on_land} on land in the 10 m grid at MLLW, {shallow} aground outside a marina, {overlapping} through a dock) ({int(B[:, 5].sum())} masts, {int((owner >= 0).sum())} in marinas); marinas {len(marinas)}; "
          f"{os.path.getsize(path) / 1e6:.1f} MB -> {path}")


if __name__ == "__main__":
    sys.exit(main())
