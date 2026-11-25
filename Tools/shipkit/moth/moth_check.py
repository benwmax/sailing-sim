"""The hydrofoil moth's size check (docs/moth-1): every slice of her build runs it against the size card.

    python3 -I moth_check.py --card [--json out.json]
    python3 -I moth_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]

--card checks the card itself (slice 0: there is no model yet): every target inside the class rules' limits, and the
foils' sums (moth_check.lift_table): the lift coefficient each foil needs to carry her at take-off and at speed, which
the physics slice (docs/moth-1/physics.md) must be able to give.

<stats.json> is what Tools/shapeloop/measure.py writes for a built boat (Blender frame, X forward, Y to port, Z up,
metres; objects tagged by section: hull, wings, strut, foil, elevator, rudder, gantry, wand, ...); <sockets.json> is the
build's sockets file (Unreal frame, X forward, Y to starboard, Z up, centimetres). Each measure is compared with
specs_moth.json's target and fails if off by more than the card's tolerance (3%), or if it is past the class rule's
limit at all (the card's 'limits': a moth may be under the rule, never over). With --slice N it also checks the
triangles of each section built by slice N or earlier against that slice's budget. The card's 'measured_by' says where
each target comes from: the shape, the sockets, a later slice ("not yet") or a build report.

How each is measured:
  length of hull          the hull object's bounds, stem to transom (rudder gantry, wand and bow fittings are their own
                          objects: class rule 6.1 leaves them out)
  beam                    the wings' bounds tip to tip (rule 6.2: the overall beam, racks included)
  hull beam, depth        the hull's widest section (stats 'hull'.beam) and deck edge to keel at its deepest station
  foils                   each foil object's span (its y extent) and the build report's planform areas
  strut, rudder depth     the object's lowest point below the hull's lowest point
  mast, luff, wand        sockets MastBase-Masthead, the report's luff, sockets WandPivot-WandTip
  rest displacement       the hull mesh's volume under the design waterline x 1,000 kg/m^3 (the report's
                          canoe_volume_m3): she must float her 115 kg of boat and sailor at rest
  rigged weight           the build report's parts_mass_kg (slice 7)
Plain Python: no Blender needed.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WATER_KG_M3 = 1000.0          # the physics' kWaterDensity (fresh water)
G = 9.81
KN = 0.514444
USAGE = ("usage: python3 -I moth_check.py --card [--json out.json]\n"
         "       python3 -I moth_check.py <stats.json> [<sockets.json>] [--slice N] [--json out.json]")


def lift_table(card, speeds_kn=(5, 6, 7, 8, 10, 15, 20, 25, 30), main_share=0.85):
    """The lift coefficient each foil needs to hold her whole weight up (boat + sailor), the main foil taking
    main_share of it and the elevator the rest (a moth flies with the elevator lifting lightly; the share moves with the
    sailor's fore-and-aft place). Planform areas from the card; no allowance for the struts' or the sail's vertical
    force (the rig tipped to windward lifts a little: physics.md)."""
    t, g = card["targets"], card["game"]
    w = (t["rigged_weight_kg"] + g["crew_kg"]) * G
    rows = []
    for v in speeds_kn:
        q = 0.5 * WATER_KG_M3 * (v * KN) ** 2
        rows.append({"knots": v, "q_pa": q,
                     "cl_main": w * main_share / (q * t["main_foil_area_m2"]),
                     "cl_elevator": w * (1 - main_share) / (q * t["elevator_area_m2"])})
    return w, rows


def measure(stats, sockets):
    m = {}
    objs = stats.get("objects", {}).values()

    def sect(name):
        return [o for o in objs if o.get("section") == name]

    def extent(os_, axis):
        return max(o["max"][axis] for o in os_) - min(o["min"][axis] for o in os_)

    hull = stats.get("hull") or {}
    hulls = sect("hull")
    if hulls:
        m["length_hull_m"] = hull.get("loa") or extent(hulls, 0)
        if hull.get("beam"):
            m["hull_beam_m"] = hull["beam"]
        st = hull.get("stations") or []
        depths = [s["sheer_z"] - s["keel_z"] for s in st if s.get("sheer_z") is not None and s.get("keel_z") is not None]
        if depths:
            m["hull_depth_m"] = max(depths)
        bottom = min(o["min"][2] for o in hulls)
        for key, name in (("main_strut_below_hull_m", "strut"), ("rudder_below_hull_m", "rudder")):
            if sect(name):
                m[key] = bottom - min(o["min"][2] for o in sect(name))
        aft = min(o["min"][0] for o in hulls)
        fwd = max(o["max"][0] for o in hulls)
    wings = sect("wings")
    if wings:
        m["beam_m"] = extent(wings + hulls, 1)
    for key, name in (("main_foil_span_m", "foil"), ("elevator_span_m", "elevator")):
        if sect(name):
            m[key] = extent(sect(name), 1)
    phys = stats.get("physics") or {}
    for k in ("main_foil_area_m2", "elevator_area_m2", "sail_area_m2", "luff_length_m", "parts_mass_kg"):
        if phys.get(k):
            m["rigged_weight_kg" if k == "parts_mass_kg" else k] = phys[k]
    if phys.get("canoe_volume_m3"):
        m["rest_displacement_kg"] = phys["canoe_volume_m3"] * WATER_KG_M3
    if sockets:
        s = sockets.get("sockets", {})

        def dist(a, b):
            return sum((p - q) ** 2 for p, q in zip(s[a], s[b])) ** 0.5 / 100.0
        if "MastBase" in s and "Masthead" in s:
            m["mast_length_m"] = dist("MastBase", "Masthead")
        if "WandPivot" in s and "WandTip" in s:
            m["wand_length_m"] = dist("WandPivot", "WandTip")
        if "RudderPivot" in s and hulls:
            m["gantry_aft_of_transom_m"] = aft - s["RudderPivot"][0] / 100.0
        if hulls:
            # class rule 6.1.5: a fitting reaching more than 0.5 m past the hull counts toward its length. Forward the
            # wand reaches furthest (its pivot or its tip, whichever is ahead); aft, the rudder's gantry.
            past = [s[k][0] / 100.0 - fwd for k in ("WandPivot", "WandTip") if k in s]
            if "RudderPivot" in s:
                past.append(aft - s["RudderPivot"][0] / 100.0)
            if past:
                m["fittings_past_hull_m"] = max(past)
    return m


def section_budgets(stats, card, upto):
    per = stats.get("sections", {})
    out = []
    for name, b in card["budget_triangles"]["sections"].items():
        if b["slice"] > upto:
            continue
        tris = sum(per.get(n, {}).get("tris", 0) for n in [name] + b.get("with", []))
        out.append((name, tris, b["max"], tris <= b["max"]))
    return out


def check_limits(values, limits):
    """[(key, value, limit)] for every value past its class-rule limit."""
    return [(k, v, limits[k]) for k, v in values.items()
            if isinstance(limits.get(k), (int, float)) and v is not None and v > limits[k] + 1e-9]


def card_mode(card, out_json):
    t, lim = card["targets"], card["limits"]
    targets = {k: v for k, v in t.items() if k != "tolerance"}
    over = check_limits(targets, lim)
    print(f"Moth size card ({card['boat']['class'].split(' (')[0]}): targets against the class rules")
    for k, v in targets.items():
        l = lim.get(k)
        print(f"  {k:26s} {v:8.3f}" + (f"   limit {l:.3f}  {'ok' if v <= l + 1e-9 else 'OVER'}" if isinstance(l, (int, float)) else ""))
    g = card["game"]
    vol = (t["rigged_weight_kg"] + g["crew_kg"]) / WATER_KG_M3
    print(f"  design volume {vol:.3f} m^3 (rigged {t['rigged_weight_kg']:.0f} + sailor {g['crew_kg']:.0f} kg), card {g['design_volume_m3']:.3f}")
    w, rows = lift_table(card)
    print(f"Lift each foil needs to fly her ({w:.0f} N; main foil 85%, elevator 15%):")
    print(f"  {'knots':>5s} {'q (Pa)':>8s} {'CL main':>8s} {'CL elev':>8s}")
    for r in rows:
        print(f"  {r['knots']:5.0f} {r['q_pa']:8.0f} {r['cl_main']:8.2f} {r['cl_elevator']:8.2f}")
    fails = [f"{k} over the rule ({v} > {l})" for k, v, l in over]
    if abs(vol - g["design_volume_m3"]) > 1e-6:
        fails.append("design volume")
    if out_json:
        json.dump({"over_limits": over, "weight_n": w, "lift": rows, "fails": fails}, open(out_json, "w"), indent=1)
    if fails:
        print("FAIL:", ", ".join(fails))
        sys.exit(1)
    print("pass")


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
    card = json.load(open(os.path.join(HERE, "specs_moth.json")))
    if args == ["--card"]:
        return card_mode(card, out_json)
    if not args:
        sys.exit(USAGE)
    stats = json.load(open(args[0]))
    sockets = json.load(open(args[1])) if len(args) > 1 else None
    tol = card["targets"]["tolerance"]
    how = card.get("measured_by", {})
    got = measure(stats, sockets)
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
    for k in ("fittings_past_hull_m",):     # class limits with no target of their own: shown against the limit
        if got.get(k) is not None:
            lim = card["limits"][k]
            rows.append((k, lim, got[k], None, "ok (limit)" if got[k] <= lim + 1e-9 else "OVER the class rule"))
    for k, v, l in check_limits(got, card["limits"]):
        fails.append(f"{k} over the class rule ({v:.3f} > {l})")
    budgets = section_budgets(stats, card, upto)
    fails += [f"triangles ({n})" for n, _, _, ok in budgets if not ok]
    print(f"Moth size check ({card['boat']['class'].split(' (')[0]}), tolerance {tol:.0%}")
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
