#!/usr/bin/env python3
"""The budget ledger (docs/budget/ledger.csv): one row per tier, view and metric with its cap and the latest value
measured on each machine. This script fills the value and date columns from bench runs; it never touches a cap
(caps are decided in review: fps 60/45 for Medium/High on the Mac and 60 for Ultra on the PC, GPU slices at the
measured value plus 10%, memory at 1.25x the measured peak, RAM growth under 100 MB/h, p99 drift under 1 ms/h).
The one exception is --seed-caps, which fills only empty caps by those rules, for a new row (measured caps from the
machine that gates the tier: the Mac for Low to High, the PC for Ultra).

    python scripts/budget-ledger.py --machine pc Artifacts/visual-bench-gate.csv Artifacts/bench-crew-high.json
    python scripts/budget-ledger.py --machine mac --view helm-eye --tier High Artifacts/bench.json
    python scripts/budget-ledger.py --machine pc --soak Artifacts/soak/soak.csv --view beat15 --tier Ultra

Inputs, any mix:
  - bench.json (scripts/windows/bench-win.ps1, scripts/bench-mac.sh). Its tier is its "quality"; its view comes from
    --view, or from a file name ending <view>-<tier>.json (bench-visual keeps them as <view>-<tier>).
  - visual-bench CSVs (bench-visual-win.ps1, bench-visual.sh): one row per view and tier.
  - --soak CSV (scripts/windows/soak-win.ps1): t_s, ram_mb, vram_mb, fps, p99_ms per sample; gives
    ram_growth_mb_per_hour and p99_drift_ms_per_hour (least-squares slopes after a 10 minute warm-up) and peak_vram_mb
    (nvidia-smi's whole-GPU memory.used; bench.json has no VRAM figure).
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "docs", "budget", "ledger.csv")
COLUMNS = ["tier", "view", "metric", "cap", "mac_value", "mac_date", "pc_value", "pc_date", "source"]
TIERS = ["Low", "Medium", "High", "Ultra"]
VIEWS = ["helm-eye", "slip", "coast-day", "beat15", "storm", "marina", "crew"]
SLICES = ["base", "lumen", "water", "clouds_fog", "niagara", "post", "other"]
METRICS = (["fps", "p99_ms", "game_ms", "gpu_ms"] + [f"gpu_{s}_ms" for s in SLICES] +
           ["water_cpu_ms", "windmap_cpu_ms", "boat_physics_ms", "peak_ram_mb", "peak_vram_mb",
            "ram_growth_mb_per_hour", "p99_drift_ms_per_hour"])
# Lower is better for everything but fps (a cap on fps is a floor).
FLOOR = {"fps"}


def from_bench(b):
    """bench.json -> {metric: value}."""
    out = {"fps": b.get("avg_fps"), "p99_ms": b.get("p99_ms"), "game_ms": b.get("game_ms"),
           "water_cpu_ms": b.get("water_cpu_ms"), "windmap_cpu_ms": b.get("windmap_cpu_ms"),
           "peak_ram_mb": b.get("mem_peak_mb"), "peak_vram_mb": b.get("vram_peak_mb")}
    gpu = b.get("gpu") or {}
    out["gpu_ms"] = gpu.get("total_ms", b.get("gpu_frame_ms"))
    for s in SLICES:
        out[f"gpu_{s}_ms"] = gpu.get(f"{s}_ms")
    # The game thread's boat physics is the player's boat (traffic boats step in traffic_step): per boat as it stands.
    out["boat_physics_ms"] = (b.get("gt") or {}).get("boat_physics")
    return {k: v for k, v in out.items() if v is not None}


def from_visual_csv(path):
    """visual-bench CSV -> [(view, tier, {metric: value})]."""
    rows = []
    for r in csv.DictReader(open(path, newline="")):
        if r.get("avg_fps") in (None, "", "error"):
            continue
        m = {"fps": r["avg_fps"], "p99_ms": r.get("p99_ms"), "gpu_ms": r.get("gpu_ms"), "water_cpu_ms": r.get("water_cpu_ms")}
        for s in SLICES:
            m[f"gpu_{s}_ms"] = r.get(f"{s}_ms")
        rows.append((r["view"], r["quality"], {k: float(v) for k, v in m.items() if v not in (None, "")}))
    return rows


def slope_per_hour(ts, ys):
    n = len(ts)
    if n < 2:
        return None
    mt, my = sum(ts) / n, sum(ys) / n
    den = sum((t - mt) ** 2 for t in ts)
    return None if den == 0 else sum((t - mt) * (y - my) for t, y in zip(ts, ys)) / den * 3600.0


def from_soak(path):
    """soak CSV -> {metric: value}. The first ten minutes are warm-up (shader and streaming caches filling)."""
    rows = [r for r in csv.DictReader(open(path, newline=""))]
    ts = [float(r["t_s"]) for r in rows]
    keep = [i for i, t in enumerate(ts) if t >= 600.0] or list(range(len(rows)))
    t = [ts[i] for i in keep]
    out = {}
    ram = [float(rows[i]["ram_mb"]) for i in keep if rows[i].get("ram_mb")]
    if ram:
        # (The growth only: the soak samples the process's private bytes, a different measure from the engine's
        # mem_peak_mb that bench.json gives peak_ram_mb from.)
        out["ram_growth_mb_per_hour"] = slope_per_hour(t[:len(ram)], ram)
    vram = [float(r["vram_mb"]) for r in rows if r.get("vram_mb")]
    if vram:
        out["peak_vram_mb"] = max(vram)
    p99 = [(ts[i], float(rows[i]["p99_ms"])) for i in keep if rows[i].get("p99_ms")]
    if p99:
        out["p99_drift_ms_per_hour"] = slope_per_hour([a for a, _ in p99], [b for _, b in p99])
    return {k: v for k, v in out.items() if v is not None}


def view_from_name(path):
    m = re.search(r"([a-z0-9]+(?:-[a-z0-9]+)*)-(low|medium|high|ultra)\.json$", os.path.basename(path).lower())
    return m.group(1) if m else None


def load_ledger():
    if not os.path.exists(LEDGER):
        return {}
    return {(r["tier"], r["view"], r["metric"]): r for r in csv.DictReader(open(LEDGER, newline=""))}


def seed_cap(tier, metric, machine, value):
    """The review's rules, for a row that has no cap yet."""
    if metric == "fps":   # fixed: the Mac gates Medium 60 and High 45, the PC Ultra 60 (Low has no floor yet)
        return {"Medium": 60, "High": 45, "Ultra": 60}.get(tier)
    # Measured caps come from the machine that gates the tier: the Mac for Low to High, the PC for Ultra.
    owner = machine == "mac" if tier != "Ultra" else machine == "pc"
    if metric.startswith("gpu_") and metric != "gpu_ms":
        return round(value * 1.1 + 0.005, 2) if owner else None
    if metric in ("peak_ram_mb", "peak_vram_mb"):
        return int(round(value * 1.25)) if owner else None
    if metric == "ram_growth_mb_per_hour":
        return 100
    if metric == "p99_drift_ms_per_hour":
        return 1
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", help="bench.json files and visual-bench CSVs")
    ap.add_argument("--machine", required=True, choices=("mac", "pc"))
    ap.add_argument("--view", help="view for bench.json / soak inputs whose names don't say")
    ap.add_argument("--tier", help="tier for a soak CSV (bench.json carries its own)")
    ap.add_argument("--soak", help="soak CSV")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--seed-caps", action="store_true", help="fill empty caps by the review's rules (new rows only)")
    a = ap.parse_args()

    found = []   # (tier, view, metrics, source)
    for p in a.inputs:
        if p.lower().endswith(".csv"):
            for view, tier, m in from_visual_csv(p):
                found.append((tier, view, m, os.path.basename(p)))
        else:
            b = json.load(open(p))
            view = a.view or view_from_name(p)
            if not view:
                sys.exit(f"{p}: no view (pass --view or name it <view>-<tier>.json)")
            found.append((b.get("quality", a.tier), view, from_bench(b), os.path.basename(p)))
    if a.soak:
        if not (a.view and a.tier):
            sys.exit("--soak needs --view and --tier")
        found.append((a.tier, a.view, from_soak(a.soak), os.path.basename(a.soak)))

    ledger = load_ledger()
    for tier in TIERS:
        for view in VIEWS:
            for metric in METRICS:
                ledger.setdefault((tier, view, metric), {c: "" for c in COLUMNS} | {"tier": tier, "view": view, "metric": metric})
    filled = 0
    for tier, view, metrics, source in found:
        tier = (tier or "").capitalize()
        for metric, value in metrics.items():
            row = ledger.setdefault((tier, view, metric), {c: "" for c in COLUMNS} | {"tier": tier, "view": view, "metric": metric})
            row[f"{a.machine}_value"] = f"{value:.3f}".rstrip("0").rstrip(".")
            row[f"{a.machine}_date"] = a.date
            row["source"] = source
            if a.seed_caps and row["cap"] == "":
                cap = seed_cap(tier, metric, a.machine, value)
                if cap is not None:
                    row["cap"] = str(cap)
            filled += 1

    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    order = {t: i for i, t in enumerate(TIERS)}
    vorder = {v: i for i, v in enumerate(VIEWS)}
    morder = {m: i for i, m in enumerate(METRICS)}
    rows = sorted(ledger.values(), key=lambda r: (order.get(r["tier"], 9), vorder.get(r["view"], 99), r["view"], morder.get(r["metric"], 99)))
    with open(LEDGER, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    over = []
    for r in rows:
        v, cap = r[f"{a.machine}_value"], r["cap"]
        if v and cap and r[f"{a.machine}_date"] == a.date:
            bad = float(v) < float(cap) if r["metric"] in FLOOR else float(v) > float(cap)
            if bad:
                over.append(f"  {r['tier']} {r['view']} {r['metric']}: {v} against cap {cap}")
    print(f"budget ledger: {filled} values from {len(found)} runs into {os.path.relpath(LEDGER, ROOT)}")
    if over:
        print("over budget:\n" + "\n".join(over))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
