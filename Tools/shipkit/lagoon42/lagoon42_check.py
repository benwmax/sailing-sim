"""The Lagoon 42's size check (docs/lagoon42-1): every slice of her rebuild runs it against the size card.

    python3 -I lagoon42_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]

<stats.json> is what Tools/shapeloop/measure.py writes for a built boat (with Tools/shapeloop/sections_lagoon42.json for
today's model, or the rebuild's own sections file from slice 1 on: Blender frame, X forward, Y to port, Z up, metres);
<sockets.json> is the build's sockets file (the game's Lagoon42_sockets.json shape: Unreal frame, X forward, Y to
starboard, Z up, centimetres). It compares each measure with specs_lagoon42.json's target and fails if any is off by
more than the card's tolerance (3%). With --slice N it also checks the triangles of each section built by slice N or
earlier against that slice's budget (the card's budget_triangles.sections; 0 checks none). The card's 'measured_by'
says where each target comes from: the shape, the sockets, a later slice ("not yet"), or a slice's own build report.

How each is measured (the Hobie 16's check, hobie16_check.py, for a cruising cat with keels and a mast on a roof):
  hull length, beam       the hull object's bounds (stats.json 'hull'): both hulls in one object, so the beam is
                          outside to outside, as published; the bowsprit is not part of the hull object
  waterline length        measure.py's cut of the hulls at the game's waterline (z = 0), stem to stern ('lwl')
  draft                   the keels' lowest point less the card's game.load_sink_m: the model floats at the game's
                          waterline with her stores and crew aboard, and Lagoon's 1.26 m is the light boat's
  air draft               the masthead socket's height (Masthead, or today's MastheadAft) plus game.load_sink_m
  weight                  the two canoe bodies' volume under z = 0 (the build's report) times 1,000 kg/m^3, less the
                          load and crew the game floats her with (game.load_kg, game.crew_kg): the physics floats every
                          boat in water of 1,000 kg/m^3 (kWaterDensity), and Lagoon's 12.1 t is the light boat
  sail areas              the sails' build report (main_area_m2, jib_area_m2, slice 7)
Plain Python: no Blender needed.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WATER_KG_M3 = 1000.0          # the physics' kWaterDensity
USAGE = "usage: python3 -I lagoon42_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]"


def measure(stats, sockets, card):
    m = {}
    game = card["game"]
    sink = game.get("load_sink_m") or 0.0
    hull = stats.get("hull") or {}
    if hull:
        m["length_hull_m"] = hull.get("loa")
        m["beam_m"] = hull.get("beam")
        if hull.get("lwl"):
            m["length_waterline_m"] = hull["lwl"]
    keels = [o for o in stats.get("objects", {}).values() if o.get("section") == "keels"]
    if keels:
        m["draft_m"] = -min(o["min"][2] for o in keels) - sink
    phys = stats.get("physics") or {}
    if phys.get("canoe_volume_m3"):
        m["weight_kg"] = phys["canoe_volume_m3"] * WATER_KG_M3 - game["load_kg"] - game["crew_kg"]
    for k in ("main_area_m2", "jib_area_m2"):
        if phys.get(k):
            m[k] = phys[k]
    if sockets:
        s = sockets.get("sockets", {})
        top = s.get("Masthead") or s.get("MastheadAft")
        if top:
            m["air_draft_m"] = top[2] / 100.0 + sink
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
    card = json.load(open(os.path.join(HERE, "specs_lagoon42.json")))
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
    print(f"Lagoon 42 size check ({card['boat']['years']}), tolerance {tol:.0%}")
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
