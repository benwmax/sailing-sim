"""The Hobie 16's size check (docs/hobie16-1): every slice of her rebuild runs it against the size card.

    python3 -I hobie16_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]

<stats.json> is what Tools/shapeloop/measure.py writes for a built boat (with Tools/shapeloop/sections_hobie16.json for
today's model, or the rebuild's own sections file from slice 1 on: Blender frame, X forward, Y to port, Z up, metres);
<sockets.json> is the build's sockets file (the game's Hobie16_sockets.json shape: Unreal frame, X forward, Y to
starboard, Z up, centimetres). It compares each measure with specs_hobie16.json's target and fails if any is off by
more than the card's tolerance (3%). With --slice N it also checks the triangles of each section built by slice N or
earlier against that slice's budget (the card's budget_triangles.sections; 0 checks none). The card's 'measured_by'
says where each target comes from: the shape, the sockets, a later slice ("not yet"), or a slice's own build report.

How each is measured (the C22's check, catalina22/c22_check.py, for two hulls):
  length of hull, beam    the hull object's bounds (stats.json 'hull'): both hulls in one object, so the beam is
                          outside to outside, as published
  waterline length        the build report's lwl_empty_m (the rebuild: at the empty boat's waterline, like the draft),
                          else measure.py's cut of the hulls at the design waterline (z = 0), stem to stern ('lwl')
  hulls' draft            the hull object's lowest point less the crew's sink: the model floats at the game's waterline
                          with its two crew aboard, and the published 10 in is the empty boat's (rudders up). The sink
                          is the build report's crew_sink_m (the rebuild's own hulls), else the card's game.crew_sink_m
  heights from the floor  the deck at the bow (stern) station above the hulls' lowest point: Hobie's 'height from floor
                          to bow (stern)', the hull standing on its keel. Today's hulls are far taller than the real ones
  weight                  the two canoe bodies' volume under z = 0 (the build's report) times 1,000 kg/m^3, less the
                          crew the game floats her with (game.crew_kg): the physics floats every boat in water of
                          1,000 kg/m^3 (kWaterDensity) and its design volume is the boat's mass with her crew
  mast length             sockets MastBase (the mast's heel on the step) to Masthead (slice 4 adds Masthead)
  sail areas              the sails' build report (main_area_m2, jib_area_m2, slice 5)
Plain Python: no Blender needed.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WATER_KG_M3 = 1000.0          # the physics' kWaterDensity
USAGE = "usage: python3 -I hobie16_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]"


def measure(stats, sockets, card):
    m = {}
    hull = stats.get("hull") or {}
    if hull:
        m["length_hull_m"] = hull.get("loa")
        m["beam_m"] = hull.get("beam")
        if hull.get("lwl"):
            m["length_waterline_m"] = hull["lwl"]
    # the card's draft is the empty boat's (game.draft_condition, docs/hobie16-2): the model floats at the game's
    # waterline with her crew aboard, so their sink comes off; the rebuild's report measures it on her own hulls
    phys = stats.get("physics") or {}
    empty = card["game"].get("draft_condition", "empty") == "empty"
    sink = (phys.get("crew_sink_m") or card["game"].get("crew_sink_m") or 0.0) if empty else 0.0
    if empty and phys.get("lwl_empty_m"):
        m["length_waterline_m"] = phys["lwl_empty_m"]
    hulls = [o for o in stats.get("objects", {}).values() if o.get("section") == "hull"]
    if hulls:
        m["draft_hull_m"] = -min(o["min"][2] for o in hulls) - sink
    st = hull.get("stations") or []
    keels = [s["keel_z"] for s in st if s.get("keel_z") is not None]
    if st and keels:
        if st[-1].get("sheer_z") is not None:
            m["height_bow_m"] = st[-1]["sheer_z"] - min(keels)
        if st[0].get("sheer_z") is not None:
            m["height_stern_m"] = st[0]["sheer_z"] - min(keels)
    if phys.get("canoe_volume_m3"):
        m["weight_kg"] = phys["canoe_volume_m3"] * WATER_KG_M3 - card["game"]["crew_kg"]
    for k in ("main_area_m2", "jib_area_m2"):
        if phys.get(k):
            m[k] = phys[k]
    if sockets:
        s = sockets.get("sockets", {})
        if "MastBase" in s and "Masthead" in s:
            a, b = s["MastBase"], s["Masthead"]
            m["mast_length_m"] = sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5 / 100.0
    return m


def section_budgets(stats, card, upto):
    """[(name, triangles, max, ok)] for each budgeted section built by slice `upto` or earlier."""
    per = stats.get("sections", {})
    out = []
    for name, b in card["budget_triangles"]["sections"].items():
        if b["slice"] > upto:
            continue
        tris = sum(per.get(n, {}).get("tris", 0) for n in [name] + b.get("with", []))
        out.append((name, tris, b["max"], tris <= b["max"]))
    return out


def main():
    args = sys.argv[1:]
    out_json, upto = None, 0
    try:
        if "--json" in args:
            i = args.index("--json")
            out_json = args[i + 1]
            del args[i:i + 2]
        if "--slice" in args:
            i = args.index("--slice")
            upto = int(args[i + 1])
            del args[i:i + 2]
    except (IndexError, ValueError):
        sys.exit(USAGE)
    if not args:
        sys.exit(USAGE)
    stats = json.load(open(args[0]))
    sockets = json.load(open(args[1])) if len(args) > 1 else None
    card = json.load(open(os.path.join(HERE, "specs_hobie16.json")))
    tol = card["targets"]["tolerance"]
    how = card.get("measured_by", {})
    got = measure(stats, sockets, card)
    rows, fails = [], []
    for key, target in card["targets"].items():
        if key == "tolerance" or not isinstance(target, (int, float)):
            continue
        v = got.get(key)
        if v is None:
            src = how.get(key, "")
            res = ("not yet: " + src.split(": ", 1)[1]) if src.startswith("later") else \
                  ("by the build: " + src.split(": ", 1)[1]) if src.startswith("build") else "not measured"
            rows.append((key, target, None, None, res))
            continue
        err = (v - target) / target
        ok = abs(err) <= tol
        rows.append((key, target, v, err, "ok" if ok else "FAIL"))
        if not ok:
            fails.append(key)
    budgets = section_budgets(stats, card, upto)
    fails += [f"triangles ({n})" for n, _, _, ok in budgets if not ok]
    print(f"Hobie 16 size check ({card['boat']['version']}), tolerance {tol:.0%}")
    print(f"{'measure':26s} {'target':>9s} {'model':>9s} {'off':>7s}  result")
    for key, target, v, err, res in rows:
        vs = f"{v:9.3f}" if v is not None else f"{'':>9s}"
        es = f"{err:+7.1%}" if err is not None else f"{'':>7s}"
        print(f"{key:26s} {target:9.3f} {vs} {es}  {res}")
    tris = stats.get("triangles")
    if tris is not None:
        print(f"triangles {tris:,} in all")
    for name, t, mx, ok in budgets:
        print(f"  {name:10s} {t:>9,} of {mx:,}  {'ok' if ok else 'FAIL'}")
    if out_json:
        json.dump({"measured": got, "rows": [dict(zip(("measure", "target", "model", "off", "result"), r)) for r in rows],
                   "triangles": tris, "budgets": [dict(zip(("section", "triangles", "max", "ok"), b)) for b in budgets],
                   "fails": fails}, open(out_json, "w"), indent=1)
    if fails:
        print("FAIL:", ", ".join(fails))
        sys.exit(1)
    print("pass")


if __name__ == "__main__":
    main()
