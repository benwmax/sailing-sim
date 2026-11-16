"""Today's frame cost at each shore station (docs/env-loop/README.md, Track 0), and the shore's share of it.

    python3 Tools/envloop/frame_cost.py plan [--quality Ultra] [--platform pc|mac]  # print the bench runs to make
    python3 Tools/envloop/frame_cost.py collect DIR                                  # DIR of <shot>.bench.json -> frame_cost.csv

Each station is benched twice from its 15 m camera on the packaged build: facing the bank (env-<id>-15m) and, from the
same spot, turned 180 degrees to open water (env-<id>-15m-water). The shore's share is the difference in GPU time
(bench.json "gpu" total and its base slice, where geometry and shadows land). Uncooked runs (run-game) are not
representative of frame rate: use bench-mac.sh / bench-win.ps1 on a package. Each run writes Artifacts/bench.json and
its screenshot; copy bench.json to DIR/<shot>.bench.json.
"""
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def views():
    data = json.load(open(os.path.join(HERE, "stations.json")))
    out = []
    for s in data["stations"]:
        c = next(c for c in s["cameras"] if c["distance_m"] == 15)
        args = c["args"].replace(" -SailingNoGpuSlices", "")
        out.append((c["scene"], args))
        b = (c["bearing_deg"] + 180.0) % 360.0
        head, cam = args.rsplit("-SailingCamWorld=", 1)
        p = cam.split(",")
        p[3] = "%.1f" % b
        p[4] = "0.0"
        out.append((c["scene"] + "-water", head + "-SailingCamWorld=" + ",".join(p)))
    return out


def plan(quality, platform):
    for shot, args in views():
        if platform == "mac":
            print('ARGS="%s -SailingCapture=Drone -SailingQuality=%s" SHOT=%s scripts/bench-mac.sh 12 && cp Artifacts/bench.json OUT/%s.bench.json'
                  % (args, quality, shot, shot))
        else:
            print('scripts\\windows\\bench-win.ps1 -Seconds 12 -Quality %s -Shot %s -GameArgs "%s -SailingCapture=Drone"; '
                  'Copy-Item Artifacts\\bench.json OUT\\%s.bench.json' % (quality, shot, args, shot))


def collect(d):
    rows = {}
    for p in sorted(glob.glob(os.path.join(d, "*.bench.json"))):
        shot = os.path.basename(p)[:-len(".bench.json")]
        j = json.load(open(p))
        g = j.get("gpu", {})
        rows[shot] = dict(shot=shot, avg_fps=j.get("avg_fps", j.get("fps")), p99_ms=j.get("p99_ms"),
                          gpu_ms=g.get("total_ms"), base_ms=g.get("base_ms"), lumen_ms=g.get("lumen_ms"), other_ms=g.get("other_ms"))
    out = os.path.join(d, "frame_cost.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["station", "avg_fps", "gpu_ms", "base_ms", "water_view_gpu_ms", "water_view_base_ms", "shore_share_ms", "shore_base_ms"])
        for shot, r in rows.items():
            if shot.endswith("-water"):
                continue
            o = rows.get(shot + "-water", {})
            share = (r["gpu_ms"] - o["gpu_ms"]) if r.get("gpu_ms") is not None and o.get("gpu_ms") is not None else None
            sb = (r["base_ms"] - o["base_ms"]) if r.get("base_ms") is not None and o.get("base_ms") is not None else None
            w.writerow([shot, r["avg_fps"], r["gpu_ms"], r["base_ms"], o.get("gpu_ms"), o.get("base_ms"),
                        None if share is None else round(share, 2), None if sb is None else round(sb, 2)])
    print(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "plan":
        q = a[a.index("--quality") + 1] if "--quality" in a else "Ultra"
        pf = a[a.index("--platform") + 1] if "--platform" in a else "pc"
        plan(q, pf)
    elif a[0] == "collect":
        collect(a[1])
