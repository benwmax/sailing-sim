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
to its greatest turn between neighbouring cells). From slice 7 the running rigging in every suit must pass the build's
checks: each rope clear along its length but where it runs over its own gear, no fitting crossing anything but by
design, nothing in the slides' lane, each loaded lead rising onto its drum and meeting its sheaves within the json's
limits, and the winches and cleats no heavier than the size card's estimate for all the deck hardware. From slice 8
the rest of the deck hardware in every suit must pass the build's checks: no piece crossing anything but by design or
coming within 3 mm of it, each mooring line's lead from its fairlead to its cleat clear, the wires clear of it, each
running light's lens over the 1910 rules' arc (RULE_ARCS, fixed here) and showing over all of it, each side light's
screen reaching three feet forward of its lens and stopping its light across the bow, the fixed pieces bedded on the
deck (none floating, none sunk), the anchor clear of the deck, and all the deck hardware (the winches, cleats, sheet
tracks, slice 8's pieces and the ground tackle's estimate) no heavier than the size card's estimate. From slice 9 the
interior forward must close (each of its five objects), no piece of it may cross the structure, the ceiling, the
bulkheads and soles, the shell, the deck or another piece but by design (the build names the kinds allowed), the
fixed pieces (structure, ceiling, bulkheads, soles) may not cross each other, every piece must rest on something that
reaches the hull (none loose, no set of pieces floating), each room forward must have its headroom between the beams
over a 0.6 m walkway (HEADROOM_M), the ground tackle drawn below replaces slice 8's estimate in the deck hardware's
weight, and the accommodation forward must leave room in the card's accommodation for slice 10's cabins aft (whose
weight and centre are printed: what slice 10 must weigh, and where, to keep the card's centre). From slice 10 the
interior aft must close too (its five objects), the same crossing and support checks cover it, the saloon and the
owner's end must have standing headroom, the companion stairs' rise may not pass interior_bluebonnet.json's
'rise_max' (nor 0.27 m), every door aft must open at least 1.6 m high, the triangles below aft stay within slice 10's
900,000,
and the accommodation forward and aft together, measured, must weigh no more than the card's and replace its estimate
in the weight check, the trimming ballast taking what it leaves.
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
RULE_ARCS = {"starboard": (0.0, 112.5), "port": (-112.5, 0.0), "stern": (112.5, 247.5)}  # the 1910 rules (slice 8)
RULE_SCREEN_M = 0.9144      # the side lights' screens: three feet forward of the light (slice 8)
INTERIOR = ("Below.Structure", "Below.Ceiling", "Below.Joinery", "Below.Fittings", "Below.Canvas")  # slice 9
INTERIOR_AFT = ("Aft.Structure", "Aft.Panelling", "Aft.Joinery", "Aft.Fittings", "Aft.Upholstery")  # slice 10
DOOR_MIN_M = 1.6            # the least height of a door's opening below (slice 10)
STAIR_RISE_MAX_M = 0.27     # the companion stairs' steepest rise (slice 10): the json's 'rise_max' may only be less
SLICE_10_TRIANGLES = 900000  # below decks aft's budget (the plan's), whatever the build says
AFT_ROOMS = ("Pantry", "Saloon", "Aft cabins")
# the least headroom between the beams on the centreline in each room forward (slice 9): standing room (6 ft) where the
# crew live and work, stooping room in the sail locker, sitting room in the washroom, and none asked of the forepeak,
# whose platform is the chain locker's top
HEADROOM_M = {"Galley": 1.83, "Fo'c'sle": 1.83, "SailLocker": 1.6, "Washroom": 1.25,
              "Pantry": 1.83, "Saloon": 1.83, "Aft cabins": 1.83}         # (slice 10's: standing room aft too)
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
        # one for each spar, slice 5 for each rigging object, slice 6 for each sail's state, slice 7 for the winches,
        # the running fittings and each suit's running rigging, and slice 8 for the deck hardware, the ensign and each
        # suit's burgee
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
        if sl >= 7:
            need += ("Winches", "RunningFittings") + tuple(f"Running.{k}" for k in
                                                           ((b.get("sails") or {}).get("suits") or {}) if k != "note")
        if sl >= 9:
            need += INTERIOR
        if sl >= 10:
            need += INTERIOR_AFT
        if sl >= 8:
            suits8 = [k for k in ((b.get("sails") or {}).get("suits") or {}) if k != "note"]
            need += ("DeckHardware", "Ensign.Moored", "Cowls.Moored") + tuple(f"Burgee.{k}" for k in suits8) + tuple(
                f"CowlCaps.{k}" for k in suits8 if k != "Moored")
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
        if sl >= 7:
            # slice 7: the running rigging in every suit
            rn = b.get("running") or {}
            ok = True
            for name in [k for k in ((b.get("sails") or {}).get("suits") or {}) if k != "note"]:
                room = (rn.get("room") or {}).get(name) or {}
                cont = (rn.get("contacts") or {}).get(name) or {}
                least = room.get("least") or {}
                good = bool(room.get("ok")) and bool(cont.get("ok"))
                print(f"{'ok  ' if good else 'FAIL'} the running rigging in the {name} suit: least room "
                      f"{least.get('least_gap_mm')} mm ({least.get('rope')} to {least.get('against')}), none under "
                      f"{room.get('fail_under_mm')} mm; crossings {cont.get('crossing')}")
                ok = ok and good
            lanes = rn.get("slide_lane") or {}
            good = bool(lanes) and all(v.get("ok") for v in lanes.values())
            print(f"{'ok  ' if good else 'FAIL'} the running rigging out of the mainsail's slides' lane in every "
                  f"suit: { {k: v.get('crossing') for k, v in lanes.items() if not v.get('ok')} or 'nothing in it'}")
            ok = ok and good
            hr = rn.get("hitch_room") or {}
            least = min(((v.get("least") or {}) for v in hr.values()), key=lambda r: r.get("least_gap_mm", 1e9),
                        default={})
            good = bool(hr) and all(v.get("ok") for v in hr.values())
            print(f"{'ok  ' if good else 'FAIL'} every hitch clear of its cleat: least {least.get('least_gap_mm')} mm "
                  f"({least.get('rope')}, to {least.get('against')})")
            ok = ok and good
            sh = rn.get("shape") or {}
            sc = sh.get("self_clearance") or {}
            kk = sh.get("kinks") or {}
            worst_sc = min((r for v in sc.values() for r in v.get("rows", [])), key=lambda r: r["least_gap_mm"],
                           default={})
            worst_k = max((r for v in kk.values() for r in v.get("rows", [])), key=lambda r: r["worst_deg"],
                          default={})
            good = bool(sh.get("ok"))
            print(f"{'ok  ' if good else 'FAIL'} each rope clear of itself (least {worst_sc.get('least_gap_mm')} mm, "
                  f"{worst_sc.get('rope')}, {worst_sc.get('pieces')}) and without kinks (worst bend "
                  f"{worst_k.get('worst_deg')} deg over three diameters, {worst_k.get('rope')}, {worst_k.get('piece')})")
            ok = ok and good
            st = rn.get("settled") or {}
            good = st.get("worst_last_pass_mm") is not None and st["worst_last_pass_mm"] <= st.get("tolerance_mm", 0)
            print(f"{'ok  ' if good else 'FAIL'} every lead settled: the worst last pass moved "
                  f"{st.get('worst_last_pass_mm')} mm (under {st.get('tolerance_mm')})")
            ok = ok and good
            ld = rn.get("leads") or {}
            good = bool(ld.get("ok"))
            fails = "" if good else f"; failing {ld.get('failing')}"
            print(f"{'ok  ' if good else 'FAIL'} the leads: rise onto the drums {ld.get('rise_deg_range')} deg, the "
                  f"sheaves' fleet {ld.get('fleet_deg_max')} deg at most{fails}")
            ok = ok and good
            wc = ((rn.get("weights") or {}).get("winches_and_cleats") or {}).get("total_long_tons")
            card = SPECS["weights"]["winches_and_hardware"]
            good = wc is not None and wc <= card
            print(f"{'ok  ' if good else 'FAIL'} the winches and cleats weigh {wc} long tons (the card's "
                  f"{card} for all the deck hardware)")
            ok = ok and good
            if not ok:
                r["pass"] = False
        if sl >= 8:
            # slice 8: the rest of the deck hardware in every suit, the lights' arcs, and all the deck hardware's weight
            hw = b.get("hardware") or {}
            ok = True
            for name in [k for k in ((b.get("sails") or {}).get("suits") or {}) if k != "note"]:
                c = {k: (hw.get(k) or {}).get(name) or {} for k in ("contacts", "room", "lead_room", "wire_room")}
                rm = c["room"].get("within_reach") or {}
                near = min(rm.items(), key=lambda kv: kv[1]["gap_mm"], default=None)
                lr = min((r for r in c["lead_room"].get("rows") or [] if r.get("least_gap_mm") is not None
                          and not r.get("report_only")), key=lambda r: r["least_gap_mm"], default={})
                good = all(bool(v.get("ok")) for v in c.values())
                nearest = f"{near[0]} {near[1]['gap_mm']} mm to {near[1]['against']}" if near else "nothing"
                print(f"{'ok  ' if good else 'FAIL'} the deck hardware in the {name} suit: crossings "
                      f"{c['contacts'].get('crossing')}, nearest {nearest}"
                      f" (within {c['room'].get('reach_m')} m, none under {c['room'].get('fail_under_mm')} mm); the "
                      f"mooring lines' least room {lr.get('least_gap_mm')} mm ({lr.get('rope')}); the wires' "
                      f"{'clear' if c['wire_room'].get('ok') else c['wire_room'].get('tight')}")
                ok = ok and good
                lc = ((hw.get("lights_check") or {}).get(name) or {})
                lts = lc.get("lights") or {}
                good = bool(lc.get("ok")) and set(lts) == set(RULE_ARCS)
                for k, arc in RULE_ARCS.items():
                    v = lts.get(k) or {}
                    la = v.get("lens_arc_deg") or [None, None]
                    good = good and None not in la and all(abs(a - e) < 0.05 for a, e in zip(la, arc))
                    good = good and v.get("rays_showing") == v.get("rays_in_arc") and not v.get("blocked_by")
                    if k != "stern":
                        good = good and (v.get("board_forward_of_lens_m") or 0.0) >= RULE_SCREEN_M
                        seen = v.get("seen_across_bow_deg")
                        good = good and seen is not None and seen <= (lc.get("cutoff_across_bow_deg") or 0.0)
                shows = ", ".join(f"{k} {v.get('lens_arc_deg')} deg, {v.get('rays_showing')}/{v.get('rays_in_arc')}"
                                  " rays" + (f", board {v.get('board_forward_of_lens_m')} m forward of the lens, seen "
                                             f"{v.get('seen_across_bow_deg')} deg across the bow"
                                             if k != "stern" else "") for k, v in lts.items())
                print(f"{'ok  ' if good else 'FAIL'} the running lights in the {name} suit (the 1910 rules: side "
                      f"lights right ahead to two points abaft the beam behind three-foot screens, the stern light "
                      f"over twelve points): {shows}{'' if good else ' ' + str(lts)}")
                ok = ok and good
            seat = hw.get("seating") or {}
            low = (hw.get("anchor") or {}).get("lowest_iron_above_deck_m")
            good = bool(seat.get("ok")) and bool(seat.get("groups")) and low is not None and low >= 0.01
            print(f"{'ok  ' if good else 'FAIL'} the deck hardware is bedded on the deck and the rail "
                  f"({len(seat.get('groups') or {})} pieces, none floating or sunk"
                  f"{'' if seat.get('ok') else ': ' + str(seat.get('bad'))}); the anchor's iron {low} m off the deck")
            ok = ok and good
            hwt = (hw.get("all_deck_hardware_weight") or {}).get("total_long_tons")
            card = SPECS["weights"]["winches_and_hardware"]
            good = hwt is not None and hwt <= card
            print(f"{'ok  ' if good else 'FAIL'} all the deck hardware weighs {hwt} long tons (the card's {card})")
            ok = ok and good
            if not ok:
                r["pass"] = False
        if sl >= 9:
            # slice 9: the interior forward clear of itself and the hull, its headroom, the ground tackle's weight drawn
            # and the accommodation forward within the card's accommodation
            inr = b.get("interior") or {}
            hw_all = b.get("hardware") or {}
            ok = True
            ov = inr.get("overlaps") or {}
            good = (bool(ov.get("ok")) and not ov.get("crossing_faces") and not ov.get("fixed_crossing_faces")
                    and bool(ov.get("furniture_groups")))
            where = "below decks" if sl >= 10 else "below decks forward"
            print(f"{'ok  ' if good else 'FAIL'} {where} nothing crosses anything but by design "
                  f"({ov.get('furniture_groups')} groups of furniture in {ov.get('furniture_trees')} meshes, checked "
                  f"against each other, the hull and the deck; the {ov.get('fixed_groups')} fixed groups (structure, "
                  f"ceiling, bulkheads, soles, deck) against each other; {len(ov.get('allowed_by_design') or {})} "
                  f"pairs touching by design): crossings {ov.get('crossing_faces')}, fixed crossings "
                  f"{ov.get('fixed_crossing_faces')}")
            ok = ok and good
            su = inr.get("support") or {}
            good = bool(su.get("ok")) and bool(su.get("pieces")) and not su.get("loose") and not su.get("floating")
            print(f"{'ok  ' if good else 'FAIL'} every piece below rests on something that reaches the hull "
                  f"({su.get('pieces')} pieces, each joined to the hull through the pieces it touches"
                  f"{', within ' + str(su['gap_mm']) + ' mm' if su.get('gap_mm') else ''}): loose "
                  f"{su.get('loose')}, floating {su.get('floating')}")
            ok = ok and good
            hr = inr.get("headroom") or {}
            for room, need_m in HEADROOM_M.items():
                if room not in hr and sl < 10:
                    continue
                v = hr.get(room) or {}
                walk = v.get("walkway_0.6_m") or {}
                got = min((x for x in (v.get("between_beams_m"), walk.get("between_beams_m")) if x is not None),
                          default=None)
                good = got is not None and got >= need_m
                print(f"{'ok  ' if good else 'FAIL'} the {room}'s headroom between the beams over a 0.6 m walkway: "
                      f"{got} m (at least {need_m}); under the beams {walk.get('under_beams_m', v.get('headroom_m'))} "
                      f"m")
                ok = ok and good
            bc = hw_all.get("bow_chock") or {}
            print(f"     the bow chock: the cable turns {bc.get('turn_at_inboard_mouth_deg')} deg at its inboard mouth "
                  f"and {bc.get('turn_at_outboard_mouth_deg')} at its outboard one; leads checked clear at "
                  f"{bc.get('dips_tested_deg')} deg down, reported only at {bc.get('steep_dips_reported_deg')}")
            gt = (inr.get("weights") or {}).get("ground_tackle") or {}
            rows = (((b.get("hardware") or {}).get("all_deck_hardware_weight") or {}).get("rows") or {})
            drawn = rows.get("ground_tackle_below") or {}
            good = bool(gt.get("total_kg")) and drawn.get("kg") == gt.get("total_kg")
            print(f"{'ok  ' if good else 'FAIL'} the ground tackle below is drawn and weighed with the deck hardware: "
                  f"{gt.get('total_kg')} kg (in the deck hardware's weight: {drawn.get('kg')} kg)")
            ok = ok and good
            ac = inr.get("accommodation") or {}
            card = SPECS["weights"]["accommodation"]
            if sl < 10:
                fwd = ac.get("forward_measured_long_tons")
                good = fwd is not None and fwd < card and (ac.get("left_for_slice_10_long_tons") or 0.0) > 0.0
                tg = ac.get("slice_10_target") or {}
                print(f"{'ok  ' if good else 'FAIL'} the accommodation forward weighs {fwd} long tons of the card's "
                      f"{card} (left for the cabins aft: {ac.get('left_for_slice_10_long_tons')}, which slice 10 must "
                      f"centre at x {tg.get('centre_x')}, z {tg.get('centre_z')} m to keep the card's centre)")
                ok = ok and good
            else:
                # slice 10: the accommodation measured, forward and aft, in place of the card's estimate
                tot = ac.get("total_long_tons")
                measured = (b.get("weights") or {}).get("measured") or []
                # and the trimming ballast takes what it leaves of the card's (shell.retrim)
                left = ((b.get("finish") or {}).get("lead") or {}).get("for_the_accommodation_long_tons")
                good = (tot is not None and tot <= card and bool(ac.get("aft_long_tons"))
                        and "accommodation" in measured and left is not None and abs(left - (card - tot)) <= 0.011
                        and len(ac.get("centre") or []) == 3)
                print(f"{'ok  ' if good else 'FAIL'} the accommodation weighs {tot} long tons (forward "
                      f"{ac.get('forward_long_tons')}, aft {ac.get('aft_long_tons')}) of the card's {card}, centred at "
                      f"{ac.get('centre')} (the card's x, z {ac.get('card_centre_xz')}); measured in the weight check: "
                      f"{'accommodation' in measured}; the trimming ballast takes the {left} long tons left")
                ok = ok and good
                aft = inr.get("aft") or {}
                st = (aft.get("lobby") or {}).get("stairs") or {}
                rise_max = json.load(open(os.path.join(HERE, "interior_bluebonnet.json")))["aft"]["lobby"]["stairs"][
                    "rise_max"]
                rise_max = min(rise_max, STAIR_RISE_MAX_M)
                good = bool(st.get("rises")) and st.get("rise_m", 9.0) <= rise_max
                print(f"{'ok  ' if good else 'FAIL'} the companion stairs: {st.get('rises')} rises of "
                      f"{st.get('rise_m')} m (at most {rise_max}) at {st.get('lean_deg')} deg, {st.get('width_m')} m "
                      f"wide")
                ok = ok and good
                # the doors aft: the four in the partitions and those in the bulkheads between the rooms aft and to
                # the galley
                doors, nb = {}, 0
                for k, v in (aft.get("partitions") or {}).items():
                    for n, d in (v.get("doors") or {}).items():
                        doors[n] = d.get("opening_m")
                for k, v in (inr.get("bulkheads") or {}).items():
                    if v.get("kind") == "door" and set(v.get("between") or []) & set(AFT_ROOMS):
                        doors[" / ".join(v["between"])] = v.get("opening_m")
                        nb += 1
                high = all(o and o[1] >= DOOR_MIN_M for o in doors.values())
                good = len(doors) == 4 + nb and nb == len(AFT_ROOMS) and high
                print(f"{'ok  ' if good else 'FAIL'} the doors aft open at least {DOOR_MIN_M} m high (width, "
                      f"height): {doors}")
                ok = ok and good
                tri, bud = b.get("triangles_slice_10_below"), b.get("budget_slice_10")
                good = tri is not None and tri <= SLICE_10_TRIANGLES and bud == SLICE_10_TRIANGLES
                print(f"{'ok  ' if good else 'FAIL'} below decks aft has {tri} triangles (slice 10's "
                      f"{SLICE_10_TRIANGLES}; the build's budget {bud}), streamed in with slice 9's "
                      f"{b.get('triangles_slice_9_below')}")
                ok = ok and good
            if not ok:
                r["pass"] = False
    print(report(r))
    sys.exit(0 if r["pass"] else 1)
