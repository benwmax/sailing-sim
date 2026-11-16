"""The Catalina 22's size check (docs/c22-1): every slice of her rebuild runs it against the size card.

    python3 -I c22_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]

<stats.json> is what Tools/shapeloop/measure.py writes for a built boat (with Tools/shapeloop/sections_c22.json for
today's model, or the rebuild's own sections file from slice 1 on: Blender frame, X forward, Y to port, Z up, metres);
<sockets.json> is the build's sockets file (the game's Catalina22_sockets.json shape: Unreal frame, X forward, Y to
starboard, Z up, centimetres). It compares each measure with specs_c22.json's target and fails if any is off by more
than the card's tolerance (3%). With --slice N it also checks the triangles of each section built by slice N or
earlier against that slice's budget (the card's budget_triangles.sections; 0 checks none). The card's 'measured_by'
says where each target comes from: the shape, the sockets, a later slice ("not yet": the tool will measure it from
then), or a slice's own build report (the keel's weight, the cabin's headroom: not a shape measure).

How each is measured:
  length of hull, beam    the hull object's bounds (stats.json 'hull'); the beam is the shell's, without a rub rail.
                          The hull object must be the bare shell: a deck or trunk merged into it moves the sheer.
  waterline length        measure.py's cut of the hull at the design waterline (z = 0), stem to stern ('lwl')
  draft, keel down        the keel section's lowest point, keel down being the build's default pose. The model floats
                          at the game's waterline, with its 227 kg crew aboard: published drafts are for the empty boat,
                          2 to 3 cm less, inside the tolerance.
  displacement            the canoe body's volume under z = 0 (the build's report) times 1,000 kg/m^3, less the crew the
                          game floats her with (the card's game.crew_kg): the physics floats every boat in water of
                          1,000 kg/m^3 (kWaterDensity) and its design volume is the boat's mass with her crew. Only the
                          hull's volume counts, as in the game (AppendageVolume 0): a hull drawn without the iron plate
                          reads about 0.033 m^3 (3%) low, so slice 3 adds the keel's volume here.
  I                       the forestay's top (socket Hounds) above the sheer at the mast (the hull's sheer interpolated
                          at MastStep's x)
  J                       the forestay's tack (ForestayTack) to the front of the mast (MastStep plus half the mast's
                          diameter, the card's game.mast_diameter_m)
  E                       the front of the boom's clew fitting (Boom_Clew) to the mast's aft face (MastStep less half its
                          diameter)
Plain Python: no Blender needed.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WATER_KG_M3 = 1000.0          # the physics' kWaterDensity
USAGE = "usage: python3 -I c22_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]"


def sheer_at(stations, x):
    """The hull's sheer height at x, by a straight line between the two cuts either side."""
    pts = sorted((s["x"], s.get("sheer_z")) for s in stations if s.get("sheer_z") is not None)
    for (xa, za), (xb, zb) in zip(pts, pts[1:]):
        if xa <= x <= xb:
            return za + (zb - za) * (x - xa) / (xb - xa) if xb > xa else za
    return None


def measure(stats, sockets, card):
    m = {}
    hull = stats.get("hull") or {}
    if hull:
        m["length_hull_m"] = hull.get("loa")
        m["beam_m"] = hull.get("beam")
        if hull.get("lwl"):
            m["length_waterline_m"] = hull["lwl"]
    keel = [o for o in stats.get("objects", {}).values() if o.get("section") == "keel"]
    if keel:
        m["draft_keel_down_m"] = -min(o["min"][2] for o in keel)
    phys = stats.get("physics") or {}
    if phys.get("canoe_volume_m3"):
        m["displacement_kg"] = phys["canoe_volume_m3"] * WATER_KG_M3 - card["game"]["crew_kg"]
    if sockets:
        s = sockets.get("sockets", {})
        r = card["game"]["mast_diameter_m"] / 2
        if "MastStep" in s:
            mast_x = s["MastStep"][0] / 100.0
            if "Hounds" in s and hull.get("stations"):
                deck = sheer_at(hull["stations"], mast_x)
                if deck is not None:
                    m["I_m"] = s["Hounds"][2] / 100.0 - deck
            if "ForestayTack" in s:
                m["J_m"] = s["ForestayTack"][0] / 100.0 - (mast_x + r)
            if "Boom_Clew" in s:
                m["E_m"] = (mast_x - r) - s["Boom_Clew"][0] / 100.0
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
    card = json.load(open(os.path.join(HERE, "specs_c22.json")))
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
    print(f"Catalina 22 size check ({card['boat']['version']}), tolerance {tol:.0%}")
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
