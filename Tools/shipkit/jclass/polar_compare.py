"""The trial against the estimate, and docs/jclass-13's charts (slice 13; run by polar_bluebonnet.py --compare).

    python polar_bluebonnet.py <build dir> --compare [<docs dir>]

Reads the build dir's physics.json, polar_estimate.json and trial.json (trial/trial.sh); writes compare.json there
and, with a docs dir, body_plan.jpg (her physics sections over the lines' outline, the lateral plane, the keel foil's
and the rudder's centres, her centres of gravity and buoyancy), polar.jpg (the estimate, the trial and the races) and
baseline/ (BASELINE's files).
"""
import json
import math
import os
import shutil
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402

# What docs/jclass-13/baseline keeps of a run: the sheet, its two .inl files for the Mac, the estimate, the trial and
# the comparison.
BASELINE = ("physics.json", "BluebonnetHullData.inl", "bluebonnet_trial.inl", "polar_estimate.json", "trial.json",
            "compare.json")
INK, MUTED, GRID = "#1f2a33", "#6b7780", "#d9dee2"
BLUE, ORANGE, GREEN = "#2f6db5", "#d0702a", "#3d8a5a"


def compare(d):
    est = json.load(open(os.path.join(d, "polar_estimate.json")))
    tri = json.load(open(os.path.join(d, "trial.json")))
    rows = []
    for e in est["points"]:
        t = next(p for p in tri["points"] if p["tws"] == e["tws"] and p["twa"] == e["twa"])
        ratio = t["speed"] / e["speed"]
        rows.append({"tws": e["tws"], "twa": e["twa"], "spinnaker": e["spinnaker"], "estimate": e["speed"],
                     "trial": round(t["speed"], 2), "ratio": round(ratio, 3),
                     "tolerance": e["tolerance"], "within": abs(ratio - 1.0) <= e["tolerance"],
                     "twa_sailed": round(t["twa_sailed"], 1),
                     "heel": round(t["heel"], 1), "leeway": round(t["leeway"], 1), "rudder": round(t["rudder"], 1)})
        if "why" in e:
            rows[-1]["why"] = e["why"]
    vmg = []
    for e in est["vmg"]:
        b = next(p for p in tri["beat"] if p["tws"] == e["tws"])
        r = next(p for p in tri["run"] if p["tws"] == e["tws"])
        vmg.append({"tws": e["tws"], "beat_estimate": e["beat_vmg"], "beat_trial": round(b["vmg"], 2),
                    "beat_twa": round(b["twa_sailed"], 1), "beat_speed": round(b["speed"], 2),
                    "beat_heel": round(b["heel"], 1), "beat_leeway": round(b["leeway"], 1),
                    "beat_rudder": round(b["rudder"], 1), "run_estimate": e["run_vmg"], "run_trial": round(r["vmg"], 2),
                    "run_twa": round(r["twa_sailed"], 1), "run_speed": round(r["speed"], 2)})
    # How much more she heels than each reference did at the wind she is read at: the heeling moment goes as the wind
    # squared times sail area times its height, the righting as each boat's own (trial.json's stiffness), and she is
    # read at wind_read_factor of her wind.
    st = tri["stiffness"]
    heel_ratio = {r: round(st[r]["stiffness_pa"] / st["bluebonnet"]["stiffness_pa"]
                           / est["references"][r]["wind_read_factor"] ** 2, 2) for r in ("j22", "c30")}

    # The races against the trial's VMGs at the race's wind (between the trial's winds, a straight line; a course is
    # the beat and the run's harmonic mean, as polar_bluebonnet.period_check takes the estimate's).
    def at(rows_, w):
        ws = sorted(p["tws"] for p in rows_)
        v = {p["tws"]: p["vmg"] for p in rows_}
        w = min(max(w, ws[0]), ws[-1])
        a, b = next((a, b) for a, b in zip(ws, ws[1:]) if a <= w <= b)
        return v[a] + (v[b] - v[a]) * (w - a) / (b - a)
    period = []
    for p in est["period"]:
        if p["kind"] not in ("beat", "run", "course"):
            continue
        beat, run = at(tri["beat"], p["wind_kn"]), at(tri["run"], p["wind_kn"])
        t = {"beat": beat, "run": run, "course": 2.0 / (1.0 / beat + 1.0 / run)}[p["kind"]]
        period.append({"what": p["what"], "kind": p["kind"], "wind_kn": p["wind_kn"], "race_vmg_kn": p["vmg_kn"],
                       "trial_vmg_kn": round(t, 2), "ratio": round(t / p["vmg_kn"], 3)})
    out = {"points": rows, "within": sum(r["within"] for r in rows), "of": len(rows), "stiffness": st,
           "heel_ratio_at_read_wind": heel_ratio, "period": period,
           "mean_ratio": round(sum(r["ratio"] for r in rows) / len(rows), 3), "vmg": vmg,
           "statics": {k: tri[k] for k in ("mass_kg", "cg", "canoe_depth_m", "station_depth_m",
                                           "design_canoe_volume_m3", "design_canoe_centre", "capsize_tilt_deg",
                                           "rest", "righting")}}
    with open(os.path.join(d, "compare.json"), "w") as f:
        json.dump(out, f, indent=1)
    return est, tri, out


def body_plan(sheet, path):
    fig, (ax, ap) = plt.subplots(1, 2, figsize=(11.0, 4.4), gridspec_kw={"width_ratios": [1.0, 2.3]})
    st = sheet["hull"]["stations"]
    mid = len(st) // 2
    for i, s in enumerate(st):
        y = [p[0] for p in s["half_section"]]
        z = [p[1] for p in s["half_section"]]
        sign = 1 if i >= mid else -1                   # forward sections to the right, aft ones to the left
        ax.plot([sign * v for v in y], z, color=BLUE if sign > 0 else ORANGE, lw=0.8)
    ax.axhline(0.0, color=MUTED, lw=0.6, ls="--")
    ax.set_aspect("equal")
    ax.set_title("Physics sections: canoe body cut at the canoe line\n(forward right, aft left)", fontsize=9, color=INK)
    ax.set_xlabel("half breadth (m)", fontsize=8)
    ax.set_ylabel("height above the waterline (m)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(color=GRID, lw=0.5)

    # the profile: sheer, keel line, canoe line, lateral plane and the centres
    x0, x1 = loft.END["transom_bottom"][0], loft.END["stem_head"][0]
    xs = [x0 + i * 0.25 for i in range(int((x1 - x0) / 0.25) + 1)]
    ap.plot(xs, [float(loft.SHEER(x)) for x in xs], color=INK, lw=1.0, label="sheer")
    ap.plot(xs, [float(loft.CANOE(x)) for x in xs], color=MUTED, lw=0.8, ls=":", label="canoe line (the cut)")
    k = loft.KEEL
    keel = [tuple(k["leading_edge"][0]), tuple(k["leading_edge"][1]), tuple(k["bottom"][1]), tuple(k["post"][1])]
    ap.plot([p[0] for p in keel], [p[1] for p in keel], color=INK, lw=1.0, label="keel and post")
    rp = sheet["foils"]["rudder"]["polygon"]
    ap.fill([p[0] for p in rp], [p[1] for p in rp], color=ORANGE, alpha=0.35, lw=0, label="rudder (the keel's flap)")
    ap.axhline(0.0, color=MUTED, lw=0.6, ls="--")
    m, f = sheet["mass"], sheet["foils"]
    ap.plot(m["cg"][0], m["cg"][2], "o", color=INK, ms=6, label="centre of gravity (sails set)")
    cb = sheet["hull"]["canoe_centre"]
    a = sheet["appendage"]
    V = sheet["hull"]["volume_m3"]
    bx = (sheet["hull"]["canoe_volume_m3"] * cb[0] + a["volume_m3"] * a["centre"][0]) / V
    bz = (sheet["hull"]["canoe_volume_m3"] * cb[1] + a["volume_m3"] * a["centre"][1]) / V
    ap.plot(bx, bz, "s", color=BLUE, ms=6, label="centre of buoyancy")
    ap.plot(f["keel"]["centre"][0], f["keel"]["centre"][2], "^", color=GREEN, ms=7, label="keel foil's centre")
    ap.plot(f["rudder"]["centre"][0], f["rudder"]["centre"][2], "v", color=ORANGE, ms=7, label="rudder foil's centre")
    ap.set_aspect("equal")
    ap.set_ylim(-5.2, 2.8)
    ap.set_title("Profile below the sheer (body frame, m)", fontsize=9, color=INK)
    ap.tick_params(labelsize=7)
    ap.grid(color=GRID, lw=0.5)
    ap.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=110, pil_kwargs={"quality": 85})
    plt.close(fig)


def polar_chart(est, tri, path):
    fig = plt.figure(figsize=(11.0, 4.8))
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_thetamin(0)
    ax.set_thetamax(180)
    colours = {6: GREEN, 10: BLUE, 16: ORANGE}
    for w, c in colours.items():
        e = [p for p in est["points"] if p["tws"] == w]
        ax.plot([math.radians(p["twa"]) for p in e], [p["speed"] for p in e], color=c, lw=1.2, ls="--")
        t = [p for p in tri["points"] if p["tws"] == w]
        ax.plot([math.radians(p["twa_sailed"]) for p in t], [p["speed"] for p in t], "o", color=c, ms=5,
                label=f"{w} kn: trial (dots), estimate (dashes)")
        b = next(p for p in tri["beat"] if p["tws"] == w) if any(p["tws"] == w for p in tri["beat"]) else None
        if b:
            ax.plot(math.radians(b["twa_sailed"]), b["speed"], "D", color=c, ms=5, mfc="white")
    ax.set_title("Boat speed (kn) by true wind angle", fontsize=9, color=INK)
    ax.tick_params(labelsize=7)
    ax.plot([], [], "D", color=MUTED, ms=5, mfc="white", label="trial's best beat (diamonds)")
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(-1.05, 1.0), frameon=False)

    bx = fig.add_subplot(1, 2, 2)
    ws = [v["tws"] for v in est["vmg"]]
    bx.plot(ws, [v["beat_vmg"] for v in est["vmg"]], "--", color=BLUE, lw=1.2, label="beat VMG, estimate")
    bx.plot([p["tws"] for p in tri["beat"]], [p["vmg"] for p in tri["beat"]], "o-", color=BLUE, ms=4, lw=1.0,
            label="beat VMG, trial")
    bx.plot(ws, [v["run_vmg"] for v in est["vmg"]], "--", color=ORANGE, lw=1.2, label="run VMG, estimate")
    bx.plot([p["tws"] for p in tri["run"]], [p["vmg"] for p in tri["run"]], "o-", color=ORANGE, ms=4, lw=1.0,
            label="run VMG, trial")
    for p in est["period"]:
        if p["kind"] == "beat":
            bx.errorbar(p["wind_kn"], p["vmg_kn"], xerr=[[0.0], [2.0]], fmt="*", color=INK, ms=9, capsize=3,
                        label="Ranger 1937, record beat (wind 12-14 kn)")
        if p["kind"] == "run":
            lo, hi = p["vmg_range_kn"]
            bx.errorbar(p["wind_kn"], 0.5 * (lo + hi), yerr=0.5 * (hi - lo), fmt="P", color=INK, ms=7, capsize=3,
                        label="Ranger 1937, the run")
    bx.set_xlabel("true wind (kn)", fontsize=8)
    bx.set_ylabel("VMG (kn)", fontsize=8)
    bx.set_title("Up and down the wind", fontsize=9, color=INK)
    bx.tick_params(labelsize=7)
    bx.grid(color=GRID, lw=0.5)
    bx.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=110, pil_kwargs={"quality": 85})
    plt.close(fig)


def main(d, docs=None):
    est, tri, out = compare(d)
    if docs:
        sheet = json.load(open(os.path.join(d, "physics.json")))
        body_plan(sheet, os.path.join(docs, "body_plan.jpg"))
        polar_chart(est, tri, os.path.join(docs, "polar.jpg"))
        base = os.path.join(docs, "baseline")
        os.makedirs(base, exist_ok=True)
        for name in BASELINE:
            shutil.copy(os.path.join(d, name), os.path.join(base, name))
    print("points within tolerance: %d of %d, trial / estimate mean %.3f" % (out["within"], out["of"],
                                                                             out["mean_ratio"]))
    print("she heels %(j22).2fx the J/22 and %(c30).2fx the Catalina 30 at the wind each is read at"
          % out["heel_ratio_at_read_wind"])
    for r in out["points"]:
        print(r)
    for v in out["vmg"]:
        print(v)
    for p in out["period"]:
        print("%s in %g kn: race %.2f kn, trial %.2f (%.2f)"
              % (p["kind"], p["wind_kn"], p["race_vmg_kn"], p["trial_vmg_kn"], p["ratio"]))
    return out


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None)
