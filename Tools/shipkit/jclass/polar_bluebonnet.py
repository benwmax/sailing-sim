"""Bluebonnet's estimated speed polar, its check against the 1930s races, and the trial's comparison (slice 13).

    python polar_bluebonnet.py <build dir>                 the estimate: <build dir>/polar_estimate.json
    python polar_bluebonnet.py <build dir> --compare [<docs dir>]
                                                           the trial (trial/trial.sh's trial.json) against it, and the
                                                           charts for docs/jclass-13 (polar_compare.py; matplotlib)

No polar exists for an invented yacht, so the fleet's two measured keelboat polars are scaled to her as the maxi's
were (Tools/boats/maxi/estimate_polar.py: Froude scaling of speed and wind, the wind made stronger for her sail area
against her weight, ITTC-57 friction at her Reynolds number), and averaged. One number differs: the J/22's sail area.
estimate_polar.py has (20.7 + 9.2) m^2 for her main and jib, which counts the jib twice (20.7 m^2, 223 sq ft, is main
and jib together: her published upwind area, and FBoatConfig's main 11.5 and jib 9.2); even main and 150% genoa make
only about 24.6. Here she has 20.7 (J22_SAIL_AREA_M2), and with it the two scaled references agree to within 7% at
every point of Bluebonnet's polar (with 29.9 they were up to 25% apart). The maxi's own estimate still uses 29.9.

Her displacement-length ratio (243) lies between the J/22's (151) and the Catalina 30's (317), inside the method's
range. Its own check, the Catalina 30 scaled to the J/22 (method_check), is rougher with the jib counted once: the
J/22 sails 10% faster than the scaled Catalina 30 on average and 4 to 20% at each point (estimate_polar.py's 4% came
from the doubled jib). So each point allows 20%: the method's own worst point, and the fleet's tolerance for a
hand-built estimate (PolarReference.h). Points the trial misses by more are listed in GAPS with the reason, as known
gaps for the Mac's tuning, never by widening their tolerance. Two kinds of point are weaker than the rest:
  - in 6 kn the references are read at 3.3 kn (the J/22) and 3.9 kn (the Catalina 30), under their lightest measured
    wind (6 kn), where their tables are straight lines to zero;
  - in a breeze the references are read where they sail far more upright than she can (polar_compare.py's stiffness:
    at the matched wind she meets 2.2 times the J/22's heeling against her righting), so close-hauled she is held to
    her heel limit and the estimate runs ahead of her.

The 1930s give two kinds of check, both rough: race times (a leg's length over its time is a VMG, tacks, sea and tide
included, the wind a reporter's figure) and the modern Js' speeds under modern sails (an upper bound). The numbers and
their sources are in PERIOD below; the J/22's ORC beat and run VMGs, scaled the same way, give her flat-water VMGs to
set them against.
"""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

_spec = importlib.util.spec_from_file_location("estimate_polar", os.path.join(REPO, "Tools", "boats", "maxi",
                                                                              "estimate_polar.py"))
EP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EP)

# The J/22's main and jib counted once (see above); the rest of her row (LWL, volume) is estimate_polar.py's.
J22_SAIL_AREA_M2 = 20.7
EP.BOATS["j22"] = (EP.BOATS["j22"][0], J22_SAIL_AREA_M2, EP.BOATS["j22"][2])

TWS = [6, 10, 16]
TOLERANCE = 0.20
# Points the trial misses by more than TOLERANCE, with why: (tws, twa) -> reason. They are reported, not failed
# (rule_check.py), and stay at TOLERANCE in the polar the Mac takes: closing them is the Mac's tuning.
_PRESSED = ("close-hauled in 16 kn she is held to her heel limit (25 deg) where the references, read at 8.8 and 10.4 "
            "kn, sail far more upright (at the matched wind she meets 2.2 times the J/22's heeling for her righting), "
            "and her overhangs' longer waterline under way is not in the physics (residuary_factor, docs/jclass-13)")
GAPS = {(16, 52): _PRESSED, (16, 60): _PRESSED}
# The J/22's ORC beat and run (172 deg, spinnaker) VMGs at 6 / 10 / 15 kn (PolarReference.cpp's J22ReferencePolar).
J22_BEAT = {6: [2.85], 10: [3.87], 15: [4.20]}
J22_BEAT_TWA = {6: 43.5, 10: 40.9, 15: 38.6}
# The 172 deg speeds there are these VMGs over cos 8 deg, so these are the VMGs themselves.
J22_RUN = {6: [3.1], 10: [4.7], 15: [5.8 + 1.3 / 6]}
VMG_WINDS = [6, 10, 12, 16]

# The races: what was timed, over what, in what wind; each with where the figure comes from. The newspaper archives
# and Wikipedia were not reachable from the cloud session that wrote this: the figures are from search results quoting
# them, so each is marked with how far to trust it.
PERIOD = [
    {"what": "Ranger's beat, 1937 America's Cup, third race (4 Aug 1937, off Brenton Reef): 15 nm dead to windward",
     "leg_nm": 15.0, "time": "2:03:55", "wind_kn": 12.0, "kind": "beat",
     "source": "Grey River Argus, 6 Aug 1937 (Papers Past, paperspast.natlib.govt.nz/newspapers/"
               "GRA19370806.2.99): 'on the windward leg her time was 2h 3m 55s, thus breaking the Rainbow's record by "
               "30s'; the wind about 12 kn at the start (the caption of A. D. Blake's painting of the third race's "
               "start, J. Russell Jinishian Gallery), reported rising to 14 kn at the mark in the second race",
     "trust": "the time is good (several papers, 2:03:40 unofficial); the wind is one caption's"},
    {"what": "Ranger's run, the same race: 15 nm dead to leeward, the rest of her time for the course",
     "leg_nm": 15.0, "time": "1:50:35", "time_range": ["1:47:35", "1:50:35"], "wind_kn": 12.0, "kind": "run",
     "source": "the same reports: corrected time for the course 3:54:30 (another 'correct elapsed time' 3:51:30), less "
               "the beat's 2:03:55",
     "trust": "the course time differs by three minutes between reports; the run's VMG is 8.1 to 8.4 kn"},
    {"what": "Endeavour, 1934 America's Cup, first race (17 Sep 1934): 15 nm to windward and back",
     "leg_nm": 30.0, "time": "3:38:44", "wind_kn": 15.0, "kind": "course",
     "source": "the 1934 America's Cup's Wikipedia table (Endeavour 3:38:44, Rainbow 3:40:53), the wind 'a fresh south "
               "westerly of 15 knots, gusting more than 20' (an account of race 1 on historic-brand.com)",
     "trust": "low: the table's columns are jumbled in the search's copy; kept only as a course average"},
    {"what": "Endeavour today (restored, modern rig and sails): a sea trial in a breeze rising to about 17 kn",
     "speed_kn": [9.5, 10.5], "reach_kn": 12.0, "wind_kn": 17.0, "kind": "modern",
     "source": "Yachting World, 'At the helm of J Class yacht Endeavour' (yachtingworld.com/j-class/...-105489): "
               "'upwind speeds of 9.5 to 10.5 knots and up to 12 knots reaching', typical for a J",
     "trust": "good for a modern J; an upper bound for 1937 cotton and steel"},
]


def hours(t):
    h, m, s = (int(v) for v in t.split(":"))
    return h + m / 60.0 + s / 3600.0


def boat_from_sheet(sheet):
    """Her LWL, sail area (main and genoa, as the references' main and jib) and sailing volume from physics.json."""
    r = sheet["rig"]
    return (sheet["hull"]["lwl_m"], r["main"]["area_m2"] + r["jib"]["area_m2"], sheet["hull"]["volume_m3"])


def estimate(sheet):
    EP.BOATS["bluebonnet"] = boat_from_sheet(sheet)
    L, S, V = EP.BOATS["bluebonnet"]
    points = []
    for w in TWS:
        for i, a in enumerate(EP.ANGLES):
            c30 = EP.scaled("c30", EP.C30, "bluebonnet", w, i)
            j22 = EP.scaled("j22", EP.J22, "bluebonnet", w, i)
            points.append({"tws": w, "twa": a, "speed": round(0.5 * (c30 + j22), 2), "c30": round(c30, 2),
                           "j22": round(j22, 2), "spinnaker": a >= 120, "tolerance": TOLERANCE})
            if (w, a) in GAPS:
                points[-1]["gap"] = GAPS[(w, a)]
    vmg = []
    for w in VMG_WINDS:
        beat = EP.scaled("j22", J22_BEAT, "bluebonnet", w, 0)
        run = EP.scaled("j22", J22_RUN, "bluebonnet", w, 0)
        s = math.sqrt(L / EP.BOATS["j22"][0])
        q = math.sqrt(EP.sad("bluebonnet") / EP.sad("j22"))
        w_ref = w / s * q
        keys = sorted(J22_BEAT_TWA)
        twa = (J22_BEAT_TWA[keys[0]] if w_ref <= keys[0] else J22_BEAT_TWA[keys[-1]] if w_ref >= keys[-1] else
               next(J22_BEAT_TWA[a] + (J22_BEAT_TWA[b] - J22_BEAT_TWA[a]) * (w_ref - a) / (b - a)
                    for a, b in zip(keys, keys[1:]) if a <= w_ref <= b))
        vmg.append({"tws": w, "beat_vmg": round(beat, 2), "beat_twa": round(twa, 1), "run_vmg": round(run, 2),
                    "j22_wind_read_kn": round(w_ref, 2)})
    period = []
    for p in PERIOD:
        q = dict(p)
        if "time" in p:
            q["vmg_kn"] = round(p["leg_nm"] / hours(p["time"]), 2)
            if "time_range" in p:
                q["vmg_range_kn"] = sorted(round(p["leg_nm"] / hours(t), 2) for t in p["time_range"])
        period.append(q)
    refs = {}
    for r in ("j22", "c30"):
        sc = math.sqrt(L / EP.BOATS[r][0])
        q = math.sqrt(EP.sad("bluebonnet") / EP.sad(r))
        refs[r] = {"speed_scale": round(sc, 4), "wind_read_factor": round(q / sc, 4),
                   "wind_read_kn": {str(w): round(w * q / sc, 2) for w in VMG_WINDS}}
    check = [EP.interp(EP.J22, w, i) / EP.scaled("c30", EP.C30, "j22", w, i) for w in (6, 10, 15)
             for i in range(len(EP.ANGLES))]
    method_check = {"what": "the J/22's ORC polar over the Catalina 30's scaled to her, at 6, 10 and 15 kn",
                    "mean": round(sum(check) / len(check), 3), "min": round(min(check), 3), "max": round(max(check), 3)}
    return {"method_check": method_check,
            "boat": {"lwl_m": L, "sail_area_m2": S, "volume_m3": V, "sa_d": round(EP.sad("bluebonnet"), 2),
                     "disp_length": round((V * 1.0 / 1.016047) / (0.01 * L / 0.3048) ** 3, 0)}, "references": refs,
            "method": "Tools/boats/maxi/estimate_polar.py's: the Catalina 30's ORC certificate and the J/22's ORC "
                      "polar scaled to her (Froude, SA/D, ITTC-57 friction) and averaged; the J/22's beat and run VMGs "
                      "scaled the same way",
            "points": points, "vmg": vmg, "period": period}


def period_check(est):
    """Each race figure against her estimated flat-water VMGs at its wind."""
    vm = {v["tws"]: v for v in est["vmg"]}

    def at(w, k):
        ws = sorted(vm)
        if w <= ws[0]:
            return vm[ws[0]][k]
        for a, b in zip(ws, ws[1:]):
            if a <= w <= b:
                return vm[a][k] + (vm[b][k] - vm[a][k]) * (w - a) / (b - a)
        return vm[ws[-1]][k]
    out = []
    for p in est["period"]:
        if p["kind"] == "beat":
            e = at(p["wind_kn"], "beat_vmg")
            out.append((p["what"], "beat VMG %.2f kn in %g kn" % (p["vmg_kn"], p["wind_kn"]), "estimate %.2f" % e,
                        e / p["vmg_kn"]))
        elif p["kind"] == "run":
            e = at(p["wind_kn"], "run_vmg")
            out.append((p["what"], "run VMG %.2f-%.2f kn" % tuple(p["vmg_range_kn"]), "estimate %.2f" % e,
                        e / p["vmg_kn"]))
        elif p["kind"] == "course":
            e = 2.0 / (1.0 / at(p["wind_kn"], "beat_vmg") + 1.0 / at(p["wind_kn"], "run_vmg"))
            out.append((p["what"], "course VMG %.2f kn in %g kn" % (p["vmg_kn"], p["wind_kn"]), "estimate %.2f" % e,
                        e / p["vmg_kn"]))
    return out


def main(d):
    sheet = json.load(open(os.path.join(d, "physics.json")))
    est = estimate(sheet)
    est["period_check"] = [{"what": a, "race": b, "estimate": c, "ratio": round(r, 3)} for a, b, c, r in
                           period_check(est)]
    with open(os.path.join(d, "polar_estimate.json"), "w") as f:
        json.dump(est, f, indent=1)
    return est


if __name__ == "__main__":
    d = os.path.abspath(sys.argv[1])
    if "--compare" in sys.argv[2:]:
        sys.path.insert(0, HERE)
        import polar_compare  # noqa: E402  (matplotlib only here)
        rest = [a for a in sys.argv[2:] if a != "--compare"]
        polar_compare.main(d, os.path.abspath(rest[0]) if rest else None)
    else:
        e = main(d)
        print("method check", e["method_check"])
        print("boat", e["boat"])
        print("references", e["references"])
        print("TWA", [a for a in EP.ANGLES])
        for w in TWS:
            print("%2d kn:" % w, [p["speed"] for p in e["points"] if p["tws"] == w])
        for v in e["vmg"]:
            print(v)
        for c in e["period_check"]:
            print(c)
