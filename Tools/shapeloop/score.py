"""Shape loop, step 5: score a round against the baseline and the card (docs/shape-loop).

    python3 score.py <card.json> <baseline dir> <round dir> [--refs <dir>]

Both dirs hold measure.py's stats.json, fairness.py's fairness.json, seams.py's seams.json and render_set.py's
renders. Writes <round dir>/score.json and score.md (the table that goes in the PR) and exits 1 if a hard check fails.
Checks (docs/shape-loop/README.md):
  size      the card's "targets": {id: {"value": m, "tol": fraction or "tol_m": m}} against the round's hull numbers
            (loa, beam, freeboard_bow, freeboard_stern) or an object's bounds ("Cabin.length", "Cabin.height", ...)
  outline   sil_<view>.png against <refs>/<view>.mask.png (a traced drawing, black boat on white, git-ignored), both
            cropped to the boat and scaled to the same length: intersection over union, pass 0.92
  fairness  no line gains inflections or kinks against the baseline (hard)
  seams     no join opens more 5 cm bins or gets a wider gap against the baseline (hard)
  physics   canoe volume within 1% and centre of buoyancy within 2 cm of the baseline (hard; the underwater shape
            stays matched to the physics, Bean Nov 10), also printed against the physics' own numbers
  moved     every object centre (the bake's sockets come from them) that moved more than 5 mm, for the QA review;
            moves outside the card's sections are a hard fail unless the card lists them in "moves_ok"
  budget    triangles per section and in total, against the card's "tris_max" (Ultra; the derived tiers are gated in
            game, not here)
Needs numpy, scipy and Pillow (any Python).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ARGS = sys.argv[1:]
CARD, BASE, ROUND = (json.load(open(ARGS[0])), ARGS[1], ARGS[2])
REFS = ARGS[ARGS.index("--refs") + 1] if "--refs" in ARGS else None


def load(d, f):
    p = os.path.join(d, f)
    return json.load(open(p)) if os.path.exists(p) else None


bs, rs = load(BASE, "stats.json"), load(ROUND, "stats.json")
rows, hard_fail = [], False


def row(check, result, ok, hard=False, note=""):
    global hard_fail
    rows.append({"check": check, "result": result, "pass": ok, "hard": hard, "note": note})
    if hard and not ok:
        hard_fail = True


# size ---------------------------------------------------------------
def value_of(stats, key):
    if "." in key:
        name, what = key.split(".", 1)
        o = stats["objects"].get(name)
        if not o:
            return None
        ext = [b - a for a, b in zip(o["min"], o["max"])]
        return {"length": ext[0], "width": ext[1], "height": ext[2], "top": o["max"][2], "fwd": o["max"][0],
                "aft": o["min"][0]}.get(what)
    return stats["hull"].get(key)


for key, t in CARD.get("targets", {}).items():
    v = value_of(rs, key)
    if v is None:
        row(f"size {key}", "not measured", False, note=t.get("source", ""))
        continue
    tol = t.get("tol_m", abs(t["value"]) * t.get("tol", 0.02))
    row(f"size {key}", f"{v:.3f} vs {t['value']:.3f} m (±{tol:.3f})", abs(v - t["value"]) <= tol,
        note=f"tier {t.get('tier', '?')}: {t.get('source', '')}")


# outline ------------------------------------------------------------
def mask(path):
    return ndi.binary_fill_holes(np.asarray(Image.open(path).convert("L")) < 128)


def crop_scale(m, w=1200):
    ys, xs = np.nonzero(m)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h = max(1, int(round(m.shape[0] * w / m.shape[1])))
    return np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)) > 127


def iou(a, b):
    h = max(a.shape[0], b.shape[0])
    pa = np.zeros((h, a.shape[1]), bool)
    pb = np.zeros((h, b.shape[1]), bool)
    pa[h - a.shape[0]:] = a                 # bottom-aligned (keel to keel line on profiles)
    pb[h - b.shape[0]:] = b
    return float((pa & pb).sum() / max((pa | pb).sum(), 1))


for view in CARD.get("outline_views", []):
    ref = os.path.join(REFS, f"{view}.mask.png") if REFS else None
    img = os.path.join(ROUND, f"sil_{view}.png")
    if not ref or not os.path.exists(ref):
        row(f"outline {view}", "no reference mask", False, note="trace the drawing first (docs/shape-loop)")
        continue
    v = iou(crop_scale(mask(img)), crop_scale(mask(ref)))
    vb = iou(crop_scale(mask(os.path.join(BASE, f"sil_{view}.png"))), crop_scale(mask(ref))) \
        if os.path.exists(os.path.join(BASE, f"sil_{view}.png")) else None
    row(f"outline {view}", f"IoU {v:.3f}" + (f" (before {vb:.3f})" if vb is not None else ""), v >= 0.92)

# fairness -----------------------------------------------------------
bf, rf = load(BASE, "fairness.json"), load(ROUND, "fairness.json")
if bf and rf:
    worse = [f"{k} +{rf['lines'][k]['inflections'] - v['inflections']} infl/+{rf['lines'][k]['kinks'] - v['kinks']} kinks"
             for k, v in bf["lines"].items() if k in rf["lines"] and
             (rf["lines"][k]["inflections"] > v["inflections"] or rf["lines"][k]["kinks"] > v["kinks"])]
    row("fairness", f"inflections {bf['total_inflections']}→{rf['total_inflections']}, kinks {bf['total_kinks']}→{rf['total_kinks']}",
        not worse, hard=True, note="; ".join(worse))

# seams --------------------------------------------------------------
bj, rj = load(BASE, "seams.json"), load(ROUND, "seams.json")
if bj and rj:
    worse = [f"{k}: open bins {bj[k]['open_bins']}→{v['open_bins']}, widest {bj[k]['widest_mm']}→{v['widest_mm']} mm"
             for k, v in rj.items() if k in bj and "open_bins" in v and "open_bins" in bj[k] and
             (v["open_bins"] > bj[k]["open_bins"] or v["widest_mm"] > bj[k]["widest_mm"] + 0.5)]
    row("seams", f"{len(rj)} joins", not worse, hard=True, note="; ".join(worse))

# physics ------------------------------------------------------------
bp, rp = bs.get("physics") or {}, rs.get("physics") or {}
if bp and rp:
    dv = (rp["canoe_volume_m3"] - bp["canoe_volume_m3"]) / bp["canoe_volume_m3"]
    dcb = math.hypot(rp["cb_x"] - bp["cb_x"], rp["cb_z"] - bp["cb_z"])
    phys = f"physics {rp.get('physics_volume_m3')} m³, CB {rp.get('physics_cb')}"
    row("physics", f"volume {dv * 100:+.2f}%, CB moved {dcb * 100:.1f} cm", abs(dv) <= 0.01 and dcb <= 0.02, hard=True,
        note=f"round {rp['canoe_volume_m3']} m³ CB ({rp['cb_x']}, {rp['cb_z']}); {phys}")

# moved ----------------------------------------------------------------
mine = set(CARD.get("sections", []))
ok_moves = set(CARD.get("moves_ok", []))
moved, foreign = [], []
for name, o in rs["objects"].items():
    b = bs["objects"].get(name)
    if not b:
        continue
    d = math.dist(o["centre"], b["centre"])
    if d > 0.005:
        moved.append(f"{name} {d * 1000:.0f} mm")
        if o["section"] not in mine and name.split(".")[0] not in ok_moves:
            foreign.append(name)
added = sorted(set(rs["objects"]) - set(bs["objects"]))
removed = sorted(set(bs["objects"]) - set(rs["objects"]))
row("moved", f"{len(moved)} moved, {len(added)} added, {len(removed)} removed", not foreign, hard=True,
    note=("outside this card's sections: " + ", ".join(foreign) + ". ") * bool(foreign) +
         "; ".join(moved[:40]) + (f"; added {', '.join(added[:20])}" if added else "") +
         (f"; removed {', '.join(removed[:20])}" if removed else ""))

# budget ---------------------------------------------------------------
tri_note = ", ".join(f"{k} {bs['sections'].get(k, {}).get('tris', 0):,}→{v['tris']:,}" for k, v in sorted(rs["sections"].items()))
tmax = CARD.get("tris_max")
row("budget", f"{bs['triangles']:,}→{rs['triangles']:,} tris", tmax is None or rs["triangles"] <= tmax, note=tri_note)

out = {"card": CARD.get("id"), "rows": rows, "hard_fail": hard_fail}
json.dump(out, open(os.path.join(ROUND, "score.json"), "w"), indent=1)
md = ["| Check | Result | Pass | Note |", "| --- | --- | --- | --- |"]
md += [f"| {r['check']}{' (hard)' if r['hard'] else ''} | {r['result']} | {'yes' if r['pass'] else 'NO'} | {r['note']} |" for r in rows]
open(os.path.join(ROUND, "score.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))
sys.exit(1 if hard_fail else 0)
