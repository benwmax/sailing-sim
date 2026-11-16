"""Region packs (docs/env-loop/packs.md): everything specific to a region, as data. python3 Tools/envloop/pack.py check [pack ...]

A pack is a folder Tools/envloop/packs/<id>/ with pack.json (where it applies, climate and seasons, the map data its
rules read, sizes, material slots) and one file per track (tracks.json's pack_file: ground.json, grass.json, ...). Each
track file lists entries: an id, the track's asset it uses, a group and weight (entries in a group are alternatives
picked by weight), the seasons it has, and `where`, a placement rule made only of the map-data inputs in RULES. No
hand placement outside the home club (pack.json hand_placed). The building kit adds parts by slot and a recipe per
style (buildings.json). A pack may extend another: its track files then add entries, and replace an inherited entry
with the same id ("drop": true removes it).

    pack.py check            every pack
    pack.py show <pack> <track letter or file>
Other tools take the pack with --pack (load(pack_id)).
"""
import copy
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACKS = os.path.join(HERE, "packs")
ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# The placement rule's inputs: every one is read from map data (pack.json map_data names the files), none by hand.
# kind: range = [min, max]; set = list of names; bool.
RULES = {
    "water_m":        ("range", "horizontal distance to the waterline at the pack's reference level (heights)"),
    "above_water_m":  ("range", "ground height above the water level (heights)"),
    "depth_m":        ("range", "water depth at the spot, or for a dock the deepest point within its length (heights)"),
    "slope_deg":      ("range", "ground slope over 2 m (heights, 1 m detail where it exists)"),
    "cover":          ("set", ["open", "canopy_edge", "under_canopy"], "tree cover (trees: crowns, density)"),
    "crown_height_m": ("range", "the lidar crown's height, for picking a tree species per crown (trees)"),
    "landuse":        ("set", ["lawn", "yard", "park", "field", "wood", "road_verge", "shore", "marina", "bare"],
                       "land use (osm landuse, house lots, roads)"),
    "lot":            ("set", ["none", "house", "club"], "inside a house lot or the home club (houses, marina)"),
    "lot_edge":       ("set", ["none", "bulkhead", "riprap", "natural"], "the lot's bank type (lots)"),
    "boathouse":      ("bool", "the lot gets HouseKit's boathouse (lots)"),
    "house_m":        ("range", "distance to the nearest house wall (houses)"),
    "footprint_m2":   ("range", "the house's footprint area (houses)"),
    "storeys":        ("range", "the house's storeys (houses)"),
    "roof_shape":     ("set", ["flat", "gable", "hip", "shed"], "the house's lidar roof fit (houses)"),
    "commercial":     ("bool", "the building is commercial (houses)"),
}
SOCKET = re.compile(r"^[a-z]+(_[a-z]+)*_(\d+|N)$")


def pack_dir(pid):
    return os.path.join(PACKS, pid)


def ids():
    return sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(PACKS, "*", "pack.json")))


def tracks():
    return json.load(open(os.path.join(HERE, "tracks.json")))["tracks"]


def _merge(base, over):
    """A child track file over its parent's: entries and parts by id (drop removes), other keys replaced."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if k == "entries":
            have = {e["id"]: i for i, e in enumerate(out.get("entries", []))}
            ents = out.setdefault("entries", [])
            for e in v:
                if e["id"] in have:
                    ents[have[e["id"]]] = e
                else:
                    ents.append(e)
            out["entries"] = [e for e in ents if not e.get("drop")]
        elif k == "parts":
            parts = out.setdefault("parts", {})
            for slot, lst in v.items():
                cur = {p["id"]: p for p in parts.get(slot, [])}
                for p in lst:
                    cur[p["id"]] = p
                parts[slot] = [p for p in cur.values() if not p.get("drop")]
        else:
            out[k] = copy.deepcopy(v)
    return out


def load(pid, _seen=()):
    """The pack with its parents folded in: {'pack': pack.json, '<file stem>': track file, ...}."""
    if pid in _seen:
        raise ValueError("pack %s extends itself" % pid)
    d = pack_dir(pid)
    meta = json.load(open(os.path.join(d, "pack.json")))
    out = load(meta["extends"], _seen + (pid,)) if meta.get("extends") else {}
    out["pack"] = _merge(out.get("pack", {}), meta)
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        stem = os.path.splitext(os.path.basename(p))[0]
        if stem != "pack":
            out[stem] = _merge(out.get(stem, {}), json.load(open(p)))
    return out


def track_file(pack, track):
    """A track's file in a loaded pack, by letter (A) or file stem (ground)."""
    tr = tracks()
    stem = os.path.splitext(tr[track]["pack_file"])[0] if track in tr else track
    return pack.get(stem)


def known_assets(track):
    """The asset ids a track has made so far (tracks.json 'assets'), or None when it has none yet."""
    t = tracks().get(track, {})
    spec = t.get("assets")
    if not spec:
        return None
    path, _, how = spec.partition("#")
    full = os.path.join(HERE, path)
    if how == "keys":
        if not os.path.exists(full):
            return None
        return {k for k in json.load(open(full)) if not k.startswith("_")}
    files = glob.glob(full)
    if not files:
        return None
    return {os.path.splitext(os.path.basename(f))[0] for f in files}


def noon_sun_deg(pack, date=None):
    """The sun's height at solar noon on the pack's reference day (or date, YYYY-MM-DD): render_bands' midday light."""
    import datetime
    import math
    d = datetime.date.fromisoformat(date or pack["pack"]["place"]["reference_day"]["date"])
    n = d.timetuple().tm_yday
    dec = 23.44 * math.sin(math.radians(360.0 / 365.0 * (n - 81)))
    return 90.0 - abs(pack["pack"]["place"]["lat"] - dec)


def check_rule(where, ctx):
    out = []
    for k, v in where.items():
        if k not in RULES:
            out.append("%s: rule input %r is not map data (pack.py RULES)" % (ctx, k))
            continue
        kind = RULES[k][0]
        if kind == "range":
            if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and v[0] <= v[1]):
                out.append("%s: %s wants [min, max]" % (ctx, k))
        elif kind == "set":
            if not isinstance(v, list) or not v or any(x not in RULES[k][1] for x in v):
                out.append("%s: %s wants names from %s" % (ctx, k, RULES[k][1]))
        elif not isinstance(v, bool):
            out.append("%s: %s wants true or false" % (ctx, k))
    return out


def check(pid):
    out = []
    try:
        p = load(pid)
    except (OSError, ValueError, KeyError) as e:
        return ["cannot load: %s" % e]
    meta = p["pack"]
    if meta.get("id") != pid:
        out.append("pack.json id %r is not the folder name" % meta.get("id"))
    seasons = meta.get("seasons", {})
    for s in meta.get("required_seasons", []):
        if s not in seasons:
            out.append("required season %r not in seasons" % s)
    for need in ("applies_to", "place", "seasons", "map_data", "sizes", "hand_placed"):
        if need not in meta:
            out.append("pack.json has no %s" % need)
    base = meta.get("sizes", {}).get("base")
    if base and not os.path.exists(os.path.normpath(os.path.join(pack_dir(pid), base))):
        out.append("sizes.base %s not found" % base)
    slots = meta.get("material_slots", {})
    tr = tracks()
    for letter, t in tr.items():
        if "pack_file" not in t:
            continue
        stem = os.path.splitext(t["pack_file"])[0]
        f = p.get(stem)
        if f is None:
            continue    # a track that hasn't started its pack file yet
        ctx0 = "%s (%s)" % (t["pack_file"], letter)
        if f.get("track") != letter:
            out.append("%s: track is %r" % (ctx0, f.get("track")))
        made = known_assets(letter)
        seen = set()
        for e in f.get("entries", []):
            ctx = "%s %s" % (ctx0, e.get("id"))
            if not ID.match(str(e.get("id", ""))):
                out.append("%s: id must be lower-case words joined by '-'" % ctx)
            if e.get("id") in seen:
                out.append("%s: id twice" % ctx)
            seen.add(e.get("id"))
            if "group" not in e or not isinstance(e.get("weight", 1), (int, float)) or e.get("weight", 1) <= 0:
                out.append("%s: needs a group and a positive weight" % ctx)
            for s in e.get("seasons", []):
                if s not in seasons:
                    out.append("%s: season %r not in pack.json" % (ctx, s))
            if e.get("where") is not None:
                out += check_rule(e["where"], ctx)
            if made is not None and e.get("asset") and e["asset"] not in made:
                out.append("%s: asset %r is not one of track %s's (%s)" % (ctx, e["asset"], letter, t["assets"]))
            for s in e.get("sockets", []) + e.get("fills", []):
                if not SOCKET.match(s):
                    out.append("%s: socket %r is not name_N" % (ctx, s))
            if "where" not in e and "fills" not in e:
                out.append("%s: needs a where rule or the sockets it fills" % ctx)
        shares = f.get("lot_edge_shares")
        if shares and abs(sum(shares.values()) - 1) > 1e-6:
            out.append("%s: lot_edge_shares add to %.3f" % (ctx0, sum(shares.values())))
        if "parts" in f:
            pids = {}
            for slot, lst in f["parts"].items():
                if slot not in f.get("slots", []):
                    out.append("%s: part slot %r not in slots" % (ctx0, slot))
                for part in lst:
                    if not ID.match(part["id"]):
                        out.append("%s: part id %r" % (ctx0, part["id"]))
                    if part.get("slot_material") and part["slot_material"] not in slots:
                        out.append("%s: part %s's material slot %r not in pack.json" % (ctx0, part["id"], part["slot_material"]))
                    pids[part["id"]] = slot
            for e in f.get("entries", []):
                rec = e.get("recipe")
                if rec is None:
                    continue
                for slot in f.get("slots", []):
                    if slot not in rec:
                        out.append("%s %s: recipe has no %s" % (ctx0, e["id"], slot))
                for slot, pick in rec.items():
                    for part, w in pick.items():
                        if pids.get(part) != slot:
                            out.append("%s %s: %s is not a %s part" % (ctx0, e["id"], part, slot))
                        if not isinstance(w, (int, float)) or w <= 0:
                            out.append("%s %s: weight of %s" % (ctx0, e["id"], part))
    return out


def main():
    a = sys.argv[1:]
    if a[:1] == ["show"] and len(a) == 3:
        print(json.dumps(track_file(load(a[1]), a[2]), indent=1))
        return
    if a[:1] != ["check"]:
        print(__doc__)
        sys.exit(2)
    bad = 0
    for pid in a[1:] or ids():
        probs = check(pid)
        bad += bool(probs)
        p = load(pid)
        n = sum(len(v.get("entries", [])) for k, v in p.items() if k != "pack")
        print("%s: %s" % (pid, ("ok, %d entries" % n) if not probs else "\n  " + "\n  ".join(probs)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
