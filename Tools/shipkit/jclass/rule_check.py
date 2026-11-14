"""Bluebonnet's rule check (docs/jclass-1): the 1930s Universal Rule rating and the size card, run by every slice.

    python3 -I rule_check.py <build.json>       prints the check and exits 1 if anything fails

Rating R = 0.18 L sqrt(S) / cbrt(D) (feet, square feet, cubic feet), which must be 76 ft or less, with:
  L  the load waterline length (specs_bluebonnet.json explains why that is close enough),
  S  the rated sail area (build.json "sail_area_ft2"): the size card's target before slice 4, then the spars' measured
     triangles (slice 4: the fore triangle I x J / 2 plus the main's P x E / 2), which the rule measured rather than
     the cloth: slice 6's sails must lie within them (the mainsail's head under the mast's black band and its clew
     inside the boom's, the jibs' heads under the forestay's hounds, the spinnaker's pole no longer than J),
  D  the displaced volume in cubic feet: the hull's. The rudder is the keel's after part, inside the hull surface
     (slice 2 cuts it out along its stock line), so it is already counted; build.json's "appendage_ft3" adds anything
     hung outside the surface.
The draft must be 15 ft or less, and each size within the card's tolerance (5%). From slice 5 a build must also show
the boom swinging out past the let-off runner and checkstay with room to spare (LEE_RUNNER_MM at its least, nothing
touching on either tack), every wire and rope clear along its length, no fitting crossing anything but by design,
and nothing in the lane the mainsail's slides need up its track. From slice 6 every suit of sails (set, lowered,
doused, moored) must pass the build's check: no face of a sail crossing anything but by design, every free face of
a set sail's cloth clear of everything else, the spinnaker pole, where a suit has it lashed down on deck,
crossing nothing, and no set sail creased where it is pressed off what it lies on (PRESS_TURN_ADDED_DEG at most added
to its greatest turn between neighbouring cells).
Plain Python: no Blender needed.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPECS = json.load(open(os.path.join(HERE, "specs_bluebonnet.json")))
FT = 0.3048
LEE_RUNNER_MM = 100.0       # the boom's least room to the let-off runner and checkstay at full swing (slice 5)
PRESS_TURN_ADDED_DEG = 10.0  # the most the press may sharpen a set sail's greatest turn between cells (slice 6)
RIGGING = ("Shrouds", "Stays", "RunnerFittings") + tuple(f"{k}.{s}.{t}" for k in ("Runner", "Checkstay")
                                                         for s in ("Starboard", "Port") for t in ("Set", "LetOff"))


def rating(lwl_ft, sail_ft2, disp_ft3):
    return 0.18 * lwl_ft * math.sqrt(sail_ft2) / disp_ft3 ** (1.0 / 3.0)


def check(h, sail_ft2=None, appendage_ft3=None):
    """h: loft.hydrostatics(). Returns a dict of results with an overall 'pass'."""
    t, rule = SPECS["targets"], SPECS["rule"]
    tol = t["tolerance"]
    S = sail_ft2 if sail_ft2 is not None else t["sail_area_ft2"]
    app = 0.0 if appendage_ft3 is None else appendage_ft3
    D = h["volume_ft3"] + app
    R = rating(h["lwl_ft"], S, D)
    rows = []

    def row(name, value, target=None, limit=None, ok=None, unit="ft"):
        if ok is None:
            ok = abs(value - target) <= tol * target
        rows.append({"check": name, "value": round(float(value), 2), "target": target, "limit": limit, "unit": unit,
                     "ok": bool(ok)})

    row("rating", R, limit=rule["rating_max_ft"], ok=R <= rule["rating_max_ft"])
    row("draft limit", h["draft_ft"], limit=rule["draft_max_ft"], ok=h["draft_ft"] <= rule["draft_max_ft"] + 1e-6)
    row("length overall", h["loa_ft"], t["loa_ft"])
    row("load waterline", h["lwl_ft"], t["lwl_ft"])
    row("beam", h["beam_ft"], t["beam_ft"])
    row("draft", h["draft_ft"], t["draft_ft"])
    row("displacement", D / 35.0, t["displacement_long_tons"], unit="long tons")
    row("bow overhang", h["bow_overhang_ft"], t["bow_overhang_ft"])
    row("stern overhang", h["stern_overhang_ft"], t["stern_overhang_ft"])
    row("least freeboard", h["freeboard_min_m"] / FT, t["freeboard_min_ft"])
    return {"rating_ft": round(R, 2), "L_ft": h["lwl_ft"], "S_ft2": S, "D_ft3": round(D, 0),
            "D_long_tons": round(D / 35.0, 1), "rows": rows, "pass": all(r["ok"] for r in rows)}


def report(r):
    lines = [f"Rating {r['rating_ft']} ft (L {r['L_ft']} ft, S {r['S_ft2']} sq ft, D {r['D_ft3']} cu ft = "
             f"{r['D_long_tons']} long tons)"]
    for x in r["rows"]:
        aim = f"limit {x['limit']}" if x["limit"] is not None else f"target {x['target']}"
        lines.append(f"  {'ok  ' if x['ok'] else 'FAIL'} {x['check']:16s} {x['value']:9.2f} {x['unit']:9s} ({aim})")
    lines.append("PASS" if r["pass"] else "FAIL")
    return "\n".join(lines)


if __name__ == "__main__":
    b = json.load(open(sys.argv[1]))
    h = b.get("hydrostatics", b)
    r = check(h, b.get("sail_area_ft2"), b.get("appendage_ft3"))
    if "hydrostatics" in b:
        # a build's json must carry its closure checks: slice 1 wrote one shell's, slice 2 one per closed piece (the
        # shell with its transom and deck, the rudder, the stock), slice 3 one for each of the deck's parts too, slice 4
        # one for each spar, slice 5 for each rigging object and slice 6 for each sail's state
        shell = b.get("shell") or {}
        pieces = {"shell": shell} if "closed" in shell else shell
        sl = b.get("slice", 1)
        need = ("shell",) if sl < 2 else ("shell_transom_deck", "rudder", "stock")
        if sl >= 3:
            need += ("ToeRail", "Hatches", "Skylights", "Companionway", "Doghouse", "Cockpit", "Steering", "Wheel")
        if sl >= 4:
            need += ("Mast", "Boom", "SpinnakerPole")
        if sl >= 5:
            need += RIGGING
        if sl >= 6:
            # each sail's state is its own object (Mainsail.Set, Genoa.Bagged, ...): every one in a suit
            need += tuple(sorted({n for k, v in ((b.get("sails") or {}).get("suits") or {}).items() if k != "note"
                                  for n in v["sails"]}))
        for name in need:
            if name not in pieces:
                r["pass"] = False
                print(f"FAIL: the build has no closure check for its {name}")
        for name, c in pieces.items():
            if not c.get("closed"):
                r["pass"] = False
                print(f"FAIL: the build's {name} does not close: {c}")
        if sl >= 5:
            # the rule check of slice 5: the boom clears the lee runner and checkstay when they are let off
            bs = b["rig"]["boom_sweep"]
            lee = bs.get("least_clearance_lee_runners_mm")
            ok = bs.get("touching") == 0 and lee is not None and lee >= LEE_RUNNER_MM
            print(f"{'ok  ' if ok else 'FAIL'} the boom past the let-off runner and checkstay: {lee} mm at its least, "
                  f"at {bs.get('least_clearance_lee_runners_at_deg')} deg (limit {LEE_RUNNER_MM:.0f}); "
                  f"{bs.get('touching')} triangles touching")
            g = b.get("rigging") or {}
            for tack in ("starboard", "port"):
                room = (g.get("room") or {}).get(tack) or {}
                cont = (g.get("contacts") or {}).get(tack) or {}
                lane = (g.get("slide_lane") or {}).get(tack) or {}
                good = bool(room.get("ok")) and bool(cont.get("ok")) and bool(lane.get("ok"))
                least = room.get("least_to_rigging") or {}
                print(f"{'ok  ' if good else 'FAIL'} the rigging on {tack} tack: least room for a wire or rope "
                      f"{least.get('gap_mm')} mm ({least.get('wire')} to {least.get('against')}), none under "
                      f"{room.get('fail_under_mm')} mm; crossings {cont.get('crossing')}; in the mainsail's slides' "
                      f"lane {lane.get('crossing')}")
                ok = ok and good
            if not ok:
                r["pass"] = False
        if sl >= 6:
            # slice 6: the sails inside the measured triangles, and every suit clear
            sv = b.get("sails") or {}
            sr = sv.get("sails") or {}
            flags = {"Mainsail": ("within_P", "within_E"), "Genoa": ("head_below_forestay_hounds",),
                     "Quadrilateral": ("head_below_forestay_hounds",), "Staysail": ("head_below_forestay_hounds",),
                     "Spinnaker": ("pole_within_J",)}
            bad = [f"{k} {f}" for k, fs in flags.items() for f in fs if not (sr.get(k) or {}).get(f)]
            ok = not bad
            print(f"{'ok  ' if ok else 'FAIL'} the sails within the measured triangles (P, E, the forestay's hounds, "
                  f"J){': ' + ', '.join(bad) if bad else ''}")
            sc = sv.get("suit_checks") or {}
            suits = [k for k in (sv.get("suits") or {}) if k != "note"]
            for name in suits or ["(none)"]:
                c = sc.get(name) or {}
                least = min((g["gap_mm"] for row in (c.get("room") or {}).values() for g in row["least"].values()),
                            default=None)
                good = bool(c.get("ok"))
                room = (f"the cloth's least room {least} mm (limit {c.get('room_fail_under_mm')})" if least is not None
                        else "no sail set")
                print(f"{'ok  ' if good else 'FAIL'} the {name} suit: crossings {c.get('crossing')}, {room}")
                ok = ok and good
            # the pole lashed down on deck in each suit that stows it
            pc = sv.get("pole_stowed_checks") or {}
            for name in [k for k in suits if (sv["suits"][k] or {}).get("pole") == "stowed"]:
                c = pc.get(name) or {}
                good = bool(c.get("ok"))
                room = ", ".join(f"{k} {v['gap_mm']} mm" for k, v in (c.get("least") or {}).items())
                print(f"{'ok  ' if good else 'FAIL'} the pole stowed on deck in the {name} suit: crossings "
                      f"{c.get('crossing')}, least room {room or 'not measured'}")
                ok = ok and good
            # the press bends the cloth round what it lies on; it may not crease it
            for name, p in (sv.get("press") or {}).items():
                added = p.get("turn_deg_pressed", 99.0) - p.get("turn_deg_shaped", 0.0)
                good = added <= PRESS_TURN_ADDED_DEG
                print(f"{'ok  ' if good else 'FAIL'} {name} pressed: moved {p.get('most_moved_m')} m at most, its "
                      f"greatest turn between cells {p.get('turn_deg_shaped')} deg as shaped, "
                      f"{p.get('turn_deg_pressed')} pressed (limit {PRESS_TURN_ADDED_DEG:.0f} more)")
                ok = ok and good
            if not ok:
                r["pass"] = False
    print(report(r))
    sys.exit(0 if r["pass"] else 1)
