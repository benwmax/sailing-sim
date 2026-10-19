"""A coast's chart without NOAA ENC cells: OpenStreetMap coastline, harbours and seamarks, EMODnet depths, NGA lights.

build_coast.py reads a world whose "chart" is "osm" through load(), which returns the same things its ENC reader
builds: depth ranges (none here), the land fraction per cell, depth samples, and S-57-shaped feature rows (COALNE,
SLCONS, PONTON, BOYLAT, LIGHTS, LNDMRK, ...) so everything after the chart stage (navaids, docks, landmarks, the chart
view) runs unchanged. OpenStreetMap's seamark tags are S-57's vocabulary already (OpenSeaMap mirrors it), so the
mapping is by name: seamark:type=buoy_lateral is BOYLAT, seamark:buoy_lateral:category=port is CATLAM 1, and a light's
character, group, period, colour, range and height become LITCHR, SIGGRP, SIGPER, COLOUR, VALNMR and HEIGHT.

Depths: EMODnet's 1/16' DTM (about 115 x 85 m here) is trusted only away from the shore, where its cells hold no land;
inside a harbour (OSM marina or harbour areas, or the world json's harbours) the depth is the harbour's dredged depth,
and the shore pin is the water's depth at the coast (a quay wall or a rocky shore is not a beach).
Lights: every OSM light is matched to NGA Pub 113 within 250 m; NGA's character wins where they differ (the list is the
authority), and NGA lights OSM lacks are added.
"""
import glob
import json
import math
import os
import re

import numpy as np
import shapely
from scipy import ndimage

import geotiff

# S-57 codes for OpenStreetMap's seamark values.
LAYER = {"buoy_lateral": "BOYLAT", "buoy_cardinal": "BOYCAR", "buoy_safe_water": "BOYSAW", "buoy_isolated_danger": "BOYISD",
         "buoy_special_purpose": "BOYSPP", "beacon_lateral": "BCNLAT", "beacon_cardinal": "BCNCAR", "beacon_safe_water": "BCNSAW",
         "beacon_isolated_danger": "BCNISD", "beacon_special_purpose": "BCNSPP"}
COLOUR = {"white": 1, "black": 2, "red": 3, "green": 4, "blue": 5, "yellow": 6, "grey": 7, "gray": 7, "brown": 8, "amber": 9,
          "violet": 10, "orange": 11, "magenta": 12, "pink": 13}
COLPAT = {"horizontal": 1, "vertical": 2, "diagonal": 3, "squared": 4, "stripes": 5, "border": 6}
CATLAM = {"port": 1, "starboard": 2, "preferred_channel_starboard": 3, "preferred_channel_port": 4}
BOYSHP = {"conical": 1, "can": 2, "spherical": 3, "pillar": 4, "spar": 5, "barrel": 6, "super-buoy": 7, "ice_buoy": 8}
BCNSHP = {"stake": 1, "pole": 1, "perch": 1, "post": 1, "withy": 2, "tower": 3, "lattice": 4, "pile": 5, "cairn": 6, "buoyant": 7}
LITCHR = {"F": 1, "Fl": 2, "LFl": 3, "Q": 4, "VQ": 5, "UQ": 6, "Iso": 7, "Oc": 8, "IQ": 9, "IVQ": 10, "IUQ": 11, "Mo": 12, "FFl": 13,
          "FlLFl": 14, "OcFl": 15, "FLFl": 16, "AlOc": 17, "AlLFl": 18, "AlFl": 19, "AlGr": 20, "Q+LFl": 25, "VQ+LFl": 26,
          "UQ+LFl": 27, "Al": 28, "AlFFl": 29}
CATLMK = {"tower": 17, "water_tower": 17, "chimney": 3, "mast": 7, "crane": 17, "obelisk": 9, "monument": 9, "church": 20,
          "cathedral": 20, "basilica": 15, "castle": 17, "fort": 17, "lighthouse": 17}
CODE = "OSM5"   # stands where an ENC cell name goes: [2] is the usage band the bake compares ('5' = harbour detail)


def elements(raw, pattern):
    out = []
    for p in sorted(glob.glob(os.path.join(raw, pattern))):
        try:
            out += json.load(open(p)).get("elements", [])
        except (ValueError, OSError):
            pass
    return out


def way_coords(el):
    return [(p["lon"], p["lat"]) for p in el.get("geometry", []) if p]


def area_polygons(el):
    """An OSM area (closed way or multipolygon relation) as lon/lat polygons."""
    if el["type"] == "way":
        c = way_coords(el)
        if len(c) >= 4 and c[0] == c[-1]:
            return [shapely.Polygon(c)]
        return []
    if el["type"] == "relation":
        outers = [shapely.LineString(way_coords(m)) for m in el.get("members", []) if m.get("role") == "outer" and len(m.get("geometry", [])) >= 2]
        inners = [shapely.LineString(way_coords(m)) for m in el.get("members", []) if m.get("role") == "inner" and len(m.get("geometry", [])) >= 2]
        outer = [p for p in shapely.polygonize(outers).geoms] if outers else []
        hole = shapely.unary_union(list(shapely.polygonize(inners).geoms)) if inners else None
        return [p.difference(hole) if hole is not None else p for p in outer]
    return []


def colours(v):
    if not v:
        return []
    return [str(COLOUR[c.strip()]) for c in re.split(r"[;,]", v) if c.strip() in COLOUR]


def num(v):
    if v is None:
        return None
    m = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", str(v))
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------- NGA Pub 113
NGA_CHAR = re.compile(r"^(Al\.)?(F\.Fl|L\.Fl|Fl|Q|V\.Q|U\.Q|Iso|Oc|I\.Q|I\.V\.Q|Mo|F)\.?(\([^)]*\))?\s*([A-Z.]*)")


def parse_nga_position(s):
    vals = re.findall(r"(\d+)\D(\d+)\D([\d.]+)\D*([NSEW])", s.replace("\n", " "))
    out = []
    for d, m, sec, h in vals:
        v = int(d) + int(m) / 60.0 + float(sec) / 3600.0
        out.append(-v if h in "SW" else v)
    return out if len(out) == 2 else None


def parse_nga_character(text):
    """'Fl.(2)W.\\nperiod 10s ...' -> (litchr, siggrp, period, colour codes)."""
    first = text.split("\n")[0].strip()
    m = NGA_CHAR.match(first)
    if not m:
        return None
    alt, kind, grp, cols = m.groups()
    key = {"F.Fl": "FFl", "L.Fl": "LFl", "V.Q": "VQ", "U.Q": "UQ", "I.Q": "IQ", "I.V.Q": "IVQ"}.get(kind, kind)
    if alt:
        key = "Al" + key
    if re.search(r"\+\s*L\.Fl", first) and key in ("Q", "VQ", "UQ"):
        key += "+LFl"   # a south cardinal: Q(6)+LFl
    code = LITCHR.get(key)
    per = re.search(r"period\s+([\d.]+)\s*s", text)
    cmap = {"W": "1", "R": "3", "G": "4", "Y": "6", "Bu": "5", "Or": "11", "Vi": "10"}
    tailcols = re.findall(r"\b(Bu|Or|Vi|W|R|G|Y)\b", first.split("+")[-1]) if "+" in first else []
    cl = [cmap[c] for c in re.findall(r"Bu|Or|Vi|W|R|G|Y", cols or "")] or [cmap[c] for c in tailcols]
    return code, (grp or "(1)").replace(" ", ""), float(per.group(1)) if per else None, cl


def nga_lights(raw, bbox):
    path = os.path.join(raw, "nga_pub113.json")
    if not os.path.exists(path):
        return []
    w, s, e, n = bbox
    out = []
    levels = {}
    for r in json.load(open(path)).get("ngalol", []):
        raw_name = (r.get("name") or "").strip()
        # Leading dashes are the list's indent: "-Dique du Large, S." then "--N." (the N. head of the same mole).
        depth = len(raw_name) - len(raw_name.lstrip("-"))
        name = raw_name.strip(" -.")
        levels = {k: v for k, v in levels.items() if k < depth}
        parent = levels[max(levels)] if levels else ""
        levels[depth] = name
        if depth > 1 and parent:
            name = f"{parent.split(',')[0]}, {name}"
        pos = parse_nga_position(r.get("position") or "")
        if not pos or not (s <= pos[0] <= n and w <= pos[1] <= e):
            continue
        ch = parse_nga_character(r.get("characteristic") or "")
        if not ch or ch[0] is None:
            continue
        hm = (r.get("heightFeetMeters") or "").split("\n")
        out.append({"lat": pos[0], "lon": pos[1], "name": name, "litchr": ch[0], "siggrp": ch[1],
                    "sigper": ch[2], "colour": ch[3], "range": num((r.get("range") or "").split("\n")[0]),
                    "height": num(hm[1]) if len(hm) > 1 else None, "number": (r.get("featureNumber") or "").replace("\n", " ")})
    return out


# ---------------------------------------------------------------- land from the OSM coastline
def land_polygons(coast_lines, box):
    """Faces of (coastline + box edge), each classed land or water by the side of its nearest coastline segment: OSM
    draws the coastline with the land on its left."""
    merged = shapely.line_merge(shapely.MultiLineString(coast_lines), directed=True)
    lines_in = [g for g in (merged.geoms if hasattr(merged, "geoms") else [merged])]
    clipped = shapely.intersection(shapely.MultiLineString(lines_in), box)
    noded = shapely.unary_union([clipped, box.boundary])
    faces = list(shapely.polygonize(list(noded.geoms) if hasattr(noded, "geoms") else [noded]).geoms)
    segs = []
    for ln in lines_in:
        c = np.asarray(ln.coords)
        for i in range(len(c) - 1):
            segs.append((c[i], c[i + 1]))
    seg_geoms = [shapely.LineString(s) for s in segs]
    tree = shapely.STRtree(seg_geoms)
    land = []
    for f in faces:
        p = f.representative_point()
        a, b = segs[int(tree.nearest(p))]
        cross = (b[0] - a[0]) * (p.y - a[1]) - (b[1] - a[1]) * (p.x - a[0])
        # The map frame is (north, east): x north, y east. Left of travel in (east, north) is right in (north, east).
        if cross < 0.0:
            land.append(f)
    return shapely.unary_union(land), len(faces)


def load(ctx):
    """ctx: build_coast's grid and helpers. Returns (depmin, depmax, dredged, land_frac, covered, samples, features, info)."""
    raw, W = ctx.raw, ctx.world
    NY, NX, CELL, X0, Y0 = ctx.NY, ctx.NX, ctx.CELL, ctx.X0, ctx.Y0
    box = shapely.box(X0 - CELL, Y0 - CELL, X0 + (NY + 1) * CELL, Y0 + (NX + 1) * CELL)

    def xy(g):
        return ctx.geom_xy(g)

    features = {k: [] for k in ("COALNE", "SLCONS", "PONTON", "BRIDGE", "LIGHTS", "DAYMAR", "TOPMAR", "LNDMRK", "FAIRWY", "MAGVAR",
                                "OBSTRN", "WRECKS", "OFSPLF", "SOUNDG", "DEPCNT", *LAYER.values())}
    # Coastline.
    coast = []
    for el in elements(raw, "coastline_osm.json"):
        c = way_coords(el)
        if len(c) >= 2:
            ln = xy(shapely.LineString(c))
            coast.append(ln)
            features["COALNE"].append({"geom_xy": ln, "cell": CODE})
    land, nfaces = land_polygons(coast, box)
    print(f"osm: {len(coast)} coastline ways, {nfaces} faces, land {land.area / box.area * 100:.0f}% of the box")
    land_hi = ctx.new_image(ctx.SS_LAND)
    for p in ctx.polygons(land):
        ctx.fill_polygon(land_hi[1], p, 255, ctx.SS_LAND)
    land_frac = np.asarray(land_hi[0], np.float64).reshape(NY, ctx.SS_LAND, NX, ctx.SS_LAND).mean(axis=(1, 3)) / 255.0
    water = land_frac < 0.5

    # Harbours: OSM areas that hold one of the world's harbour points (else a disc), at the harbour's depth.
    harbour_els = elements(raw, "harbours_osm.json")
    areas = []
    for el in harbour_els:
        t = el.get("tags", {})
        if t.get("leisure") == "marina" or t.get("landuse") == "harbour" or t.get("harbour") in ("yes", "marina") or t.get("seamark:type") == "harbour":
            areas += [xy(p) for p in area_polygons(el)]
    harbour_depth = np.full((NY, NX), np.nan)
    hdraw = []
    for h in W.get("harbours", []):
        hx, hy = ctx.ll2xy(h["lat"], h["lon"])
        pt = shapely.Point(hx, hy)
        poly = min((a for a in areas if a.buffer(30.0).contains(pt)), key=lambda a: a.area, default=None)
        if poly is None or poly.area > 4e6:
            poly = pt.buffer(250.0)
        hdraw.append((poly.buffer(20.0), float(h["depth_m"]), h["name"]))
    for poly, d, _ in sorted(hdraw, key=lambda t: -t[0].area):
        img = ctx.new_image(1)
        for p in ctx.polygons(poly):
            ctx.fill_polygon(img[1], p, 255, 1)
        m = (np.asarray(img[0]) > 0) & water
        harbour_depth[m] = d
    print(f"osm: harbours {', '.join(f'{n} {d:.1f} m' for _, d, n in hdraw)}")

    # Depth samples: EMODnet away from the shore, harbour depths inside the harbours.
    bath = W["bathymetry"]
    bd, bref = geotiff.read(os.path.join(raw, bath["path"]))
    rows, cols = np.mgrid[0:bd.shape[0], 0:bd.shape[1]]
    lon = bref.x0 + cols * bref.dx
    lat = bref.y0 + rows * bref.dy
    north, east = ctx.ll2xy(lat.ravel(), lon.ravel())
    z = bd.ravel()
    dist_land = ndimage.distance_transform_edt(water) * CELL
    r = np.clip(((north - X0) / CELL).round().astype(int), 0, NY - 1)
    c = np.clip(((east - Y0) / CELL).round().astype(int), 0, NX - 1)
    inside = (north >= X0) & (north <= X0 + (NY - 1) * CELL) & (east >= Y0) & (east <= Y0 + (NX - 1) * CELL)
    far_out = ~inside & (z < 0)
    keep = inside & (z < 0) & water[r, c] & (dist_land[r, c] >= bath.get("trust_from_shore_m", 180.0)) & np.isnan(harbour_depth[r, c])
    samples = [(a, b, -v) for a, b, v in zip(north[keep | far_out], east[keep | far_out], z[keep | far_out])]
    hr, hc = np.nonzero(np.isfinite(harbour_depth[::3, ::3]))
    samples += [(X0 + rr * 3 * CELL, Y0 + cc * 3 * CELL, float(harbour_depth[rr * 3, cc * 3])) for rr, cc in zip(hr, hc)]
    print(f"osm: depth samples {len(samples)} (EMODnet {int((keep | far_out).sum())}, harbour {len(hr)})")

    # The water's depth at the coast: the harbour's at a quay, else a rocky shore's (beaches pin to zero).
    beaches = []
    for el in elements(raw, "landuse_osm.json"):
        if el.get("tags", {}).get("natural") == "beach":
            beaches += [xy(p) for p in area_polygons(el)]
    beach_img = ctx.new_image(1)
    for b in beaches:
        for p in ctx.polygons(b.buffer(30.0)):
            ctx.fill_polygon(beach_img[1], p, 255, 1)
    beach = np.asarray(beach_img[0]) > 0
    rocky = float(W.get("shore_depth_m", 2.0))

    def shore_depth(xs, ys):
        rr = np.clip(((np.asarray(xs) - X0) / CELL).round().astype(int), 0, NY - 1)
        cc = np.clip(((np.asarray(ys) - Y0) / CELL).round().astype(int), 0, NX - 1)
        d = np.where(beach[rr, cc], 0.0, rocky)
        return np.where(np.isfinite(harbour_depth[rr, cc]), harbour_depth[rr, cc], d)

    # Harbour structures. A pontoon is a floating pier; quays are the coastline's own edge (not obstacles).
    for el in harbour_els:
        t = el.get("tags", {})
        mm = t.get("man_made")
        if el["type"] != "way" or mm not in ("pier", "breakwater", "groyne"):
            continue
        cs = way_coords(el)
        if len(cs) < 2:
            continue
        g = xy(shapely.Polygon(cs) if (len(cs) >= 4 and cs[0] == cs[-1] and t.get("area") != "no") else shapely.LineString(cs))
        row = {"geom_xy": g, "cell": CODE, "OBJNAM": t.get("name"), "osm_id": el["id"]}
        if mm == "pier" and t.get("floating") == "yes":
            features["PONTON"].append(row)
        else:
            row["CATSLC"] = {"breakwater": 1, "groyne": 3, "pier": 4}[mm]
            features["SLCONS"].append(row)

    # Seamarks.
    nga = nga_lights(raw, W["bbox"])
    used_nga = set()
    for el in elements(raw, "seamarks_osm.json"):
        t = el.get("tags", {})
        typ = t.get("seamark:type") or ("light_major" if t.get("man_made") == "lighthouse" else None)
        if typ is None:
            continue
        if el["type"] == "node":
            lon_, lat_ = el["lon"], el["lat"]
        elif el.get("geometry"):
            cs = way_coords(el)
            lon_, lat_ = float(np.mean([q[0] for q in cs])), float(np.mean([q[1] for q in cs]))
        elif el.get("center"):
            lon_, lat_ = el["center"]["lon"], el["center"]["lat"]
        else:
            continue
        g = shapely.Point(*ctx.ll2xy(lat_, lon_))
        name = t.get("seamark:name") or t.get("name")
        if typ in LAYER:
            pre = f"seamark:{typ}:"
            row = {"geom_xy": g, "cell": CODE, "OBJNAM": name, "COLOUR": colours(t.get(pre + "colour")),
                   "COLPAT": COLPAT.get(t.get(pre + "colour_pattern")), "CATLAM": CATLAM.get(t.get(pre + "category")),
                   "CATCAM": {"north": 1, "east": 2, "south": 3, "west": 4}.get(t.get(pre + "category"))}
            if not row["COLOUR"] and row["CATLAM"] in (1, 2):
                # IALA region A (Europe): port hand red, starboard hand green (region B's are the other way round).
                row["COLOUR"] = (["3"] if row["CATLAM"] == 1 else ["4"]) if W.get("iala", "A") == "A" else (["4"] if row["CATLAM"] == 1 else ["3"])
            shp = t.get(pre + "shape")
            row["BOYSHP" if typ.startswith("buoy") else "BCNSHP"] = (BOYSHP if typ.startswith("buoy") else BCNSHP).get(shp)
            features[LAYER[typ]].append(row)
            if t.get("seamark:topmark:shape"):
                features["TOPMAR"].append({"geom_xy": g, "cell": CODE, "TOPSHP": t.get("seamark:topmark:shape"),
                                           "COLOUR": colours(t.get("seamark:topmark:colour"))})
        if typ == "landmark" or t.get("man_made") == "lighthouse":
            features["LNDMRK"].append({"geom_xy": g, "cell": CODE, "OBJNAM": name, "CATLMK": CATLMK.get(t.get("seamark:landmark:category"), 17),
                                       "CONVIS": 1, "HEIGHT": num(t.get("height"))})
        # The light, from the plain keys or the first sector; NGA's entry wins where one is within 250 m.
        lt = {k[len("seamark:light:"):]: v for k, v in t.items() if k.startswith("seamark:light:")}
        if not lt:
            continue
        sector = {k.split(":", 1)[1]: v for k, v in lt.items() if k.startswith("1:")}
        get = lambda k: lt.get(k) or sector.get(k)
        cols = colours(get("colour"))
        for k, v in lt.items():
            if k.endswith(":colour"):
                cols += [cc for cc in colours(v) if cc not in cols]
        ch = (get("character") or "Fl").replace(".", "")
        grp = get("group")
        light = {"LITCHR": LITCHR.get(ch, 2), "SIGGRP": f"({grp})" if grp else "(1)", "SIGPER": num(get("period")),
                 "COLOUR": cols, "VALNMR": num(get("range")), "HEIGHT": num(get("height")), "source": "osm"}
        best = min(((math.dist(ctx.ll2xy(n_["lat"], n_["lon"]), (g.x, g.y)), i) for i, n_ in enumerate(nga)), default=None)
        if best and best[0] < 250.0:
            n_ = nga[best[1]]
            used_nga.add(best[1])
            light.update({"LITCHR": n_["litchr"], "SIGGRP": n_["siggrp"], "SIGPER": n_["sigper"] or light["SIGPER"],
                          "COLOUR": n_["colour"] or light["COLOUR"], "VALNMR": n_["range"] or light["VALNMR"],
                          "HEIGHT": n_["height"] or light["HEIGHT"], "source": "nga", "nga": n_["number"]})
        features["LIGHTS"].append({"geom_xy": g, "cell": CODE, **light})
    added = 0
    for i, n_ in enumerate(nga):
        if i in used_nga:
            continue
        g = shapely.Point(*ctx.ll2xy(n_["lat"], n_["lon"]))
        features["LIGHTS"].append({"geom_xy": g, "cell": CODE, "LITCHR": n_["litchr"], "SIGGRP": n_["siggrp"], "SIGPER": n_["sigper"],
                                   "COLOUR": n_["colour"], "VALNMR": n_["range"], "HEIGHT": n_["height"], "source": "nga", "nga": n_["number"],
                                   "OBJNAM": n_["name"]})
        added += 1
    print(f"osm: seamarks {sum(len(features[k]) for k in LAYER.values())} buoys and beacons, {len(features['LIGHTS'])} lights "
          f"({len(used_nga)} matched to NGA Pub 113, {added} from NGA only)")

    # Landmarks to take a bearing on: named castles and forts, churches, towers.
    for el in elements(raw, "landmarks_osm.json"):
        t = el.get("tags", {})
        cen = el.get("center") or ({"lat": el["lat"], "lon": el["lon"]} if "lat" in el else None)
        if not cen or not t.get("name") and t.get("man_made") not in ("water_tower", "chimney"):
            continue
        kind = t.get("historic") or t.get("building") or t.get("man_made") or "tower"
        if kind not in CATLMK:
            continue
        g = shapely.Point(*ctx.ll2xy(cen["lat"], cen["lon"]))
        features["LNDMRK"].append({"geom_xy": g, "cell": CODE, "OBJNAM": t.get("name"), "CATLMK": CATLMK[kind],
                                   "CONVIS": 1 if kind in ("basilica", "cathedral", "castle", "fort", "lighthouse") else None,
                                   "HEIGHT": num(t.get("height"))})

    info = {"chart": "OpenStreetMap coastline, harbours and seamarks (ODbL 1.0); EMODnet Bathymetry DTM (CC BY 4.0); "
                     "lights checked against NGA Pub 113 (public domain)",
            "shore_depth": shore_depth, "land": land, "harbours": [{"name": n, "depth_m": d} for _, d, n in hdraw]}
    nan = np.full((NY, NX), np.nan, np.float32)
    return nan, nan.copy(), nan.copy(), land_frac, np.ones((NY, NX), bool), samples, features, info


def chart(ctx, height, water, land):
    """The chart view's layers from the baked grid: depth-class areas, contours, thinned soundings, land."""
    import contourpy
    NY, NX, CELL, X0, Y0 = ctx.NY, ctx.NX, ctx.CELL, ctx.X0, ctx.Y0
    step = max(1, int(round(30.0 / CELL)))
    depth = np.where(water, -height, -1.0)[::step, ::step]
    depth = ndimage.median_filter(depth, 3)
    gx = X0 + np.arange(depth.shape[0]) * CELL * step
    gy = Y0 + np.arange(depth.shape[1]) * CELL * step
    gen = contourpy.contour_generator(gy, gx, depth, fill_type=contourpy.FillType.OuterOffset, line_type=contourpy.LineType.Separate)
    areas = []
    for cls, lo, hi in ((0, -0.5, 0.0), (1, 0.0, 1.8), (2, 1.8, 3.6), (3, 3.6, 1e5)):
        polys, offsets = gen.filled(lo, hi)
        for pts, off in zip(polys, offsets):
            rings = [pts[off[i]:off[i + 1]] for i in range(len(off) - 1)]
            rings = [[(p[1], p[0]) for p in r] for r in rings if len(r) >= 4]
            if rings:
                poly = shapely.Polygon(rings[0], rings[1:]).buffer(0)
                for p in ctx.polygons(poly.difference(land)):
                    areas.append((cls, p))
    for p in ctx.polygons(land):
        areas.append((4, p))
    contours = []
    for v in (2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0):
        for ln in gen.lines(v):
            if len(ln) >= 3:
                contours.append((shapely.LineString([(p[1], p[0]) for p in ln]), v))
    soundings = []
    s = int(350.0 / CELL)
    for r in range(s // 2, NY, s):
        for c in range(s // 2, NX, s):
            if water[r, c] and height[r, c] < -0.5:
                soundings.append((X0 + r * CELL, Y0 + c * CELL, round(float(-height[r, c]), 1)))
    return areas, contours, soundings
