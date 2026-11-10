"""Shape loop, step 5: score a round against the baseline and the card (docs/shape-loop).

    python3 score.py <card.json> <baseline dir> <round dir> [--refs <dir>]

Both dirs hold measure.py's stats.json, fairness.py's fairness.json, seams.py's seams.json and render_set.py's
renders. Writes <round dir>/score.json and score.md (the table that goes in the PR) and exits 1 if a hard check fails.
Checks (docs/shape-loop/README.md):
  size      the card's "targets": {id: {"value": m, "tol": fraction or "tol_m": m}} against the round's hull numbers
            (loa, beam, freeboard_bow, freeboard_stern) or an object's bounds ("Cabin.length", "Cabin.height", ...)
  outline   sil_<view>.png against <refs>/<view>.mask.png (a traced drawing, black boat on white, git-ignored, with
            <view>.mask.json {"m_per_px": ...} from the drawing's scale), both resampled to 5 mm per pixel so size
            counts, bottom-aligned (and bow-aligned on profile and plan): intersection over union, pass 0.92
  fairness  no line gains inflections or kinks or goes missing against the baseline (hard)
  seams     no join loses contact (10% fewer bins), opens a bin that touched in the baseline (now over 3 mm) or gets a gap 0.5 mm
            wider (hard)
  A check whose file is missing (a tool crashed, the hull was renamed) is a hard fail, never a silent pass.
  physics   canoe volume within 1% and centre of buoyancy within 2 cm of the baseline (hard; the underwater shape
            stays matched to the physics, Bean Nov 10), also printed against the physics' own numbers
  moved     every object centre (bounds centre; the bake's sockets come from the objects) that moved more than 5 mm;
            outside the card's sections a move is a hard fail unless the card lists the section in
            "moves_ok_sections" or the name in "moves_ok" (rules as in the sections file), and so is a shape-section
            object added or removed outside them ("removes_ok" lists exact names)
  budget    triangles per section and in total, against the card's "tris_max" (Ultra; the derived tiers are gated in
            game, not here)
Needs numpy, scipy and Pillow (Blender's pip-bpy venv has them; any Python with them works).
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
if bs is None or rs is None:
    line = (f"| stats (hard) | missing stats.json in the {'round' if rs is None else 'baseline'} | NO | measure.py failed "
            "(a renamed hull or a failed build) |")
    os.makedirs(ROUND, exist_ok=True)
    json.dump({"card": CARD.get("id"), "rows": [{"check": "stats", "pass": False, "hard": True}], "hard_fail": True},
              open(os.path.join(ROUND, "score.json"), "w"), indent=1)
    open(os.path.join(ROUND, "score.md"), "w").write("| Check | Result | Pass | Note |\n| --- | --- | --- | --- |\n" + line + "\n")
    print(line)
    sys.exit(1)


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


def at_scale(m, m_per_px, mm=0.005):
    """The mask cropped to the boat and resampled to `mm` metres per pixel: the size stays in the comparison, so a
    boat 10% too long scores lower, not the same."""
    ys, xs = np.nonzero(m)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    f = m_per_px / mm
    w, h = max(1, int(round(m.shape[1] * f))), max(1, int(round(m.shape[0] * f)))
    return np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)) > 127


def iou(a, b, centre=False):
    """Bottom-aligned (keel line on keel line); profile and plan also aligned at the bow end (left), bow and stern
    views centred side to side."""
    h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
    pa, pb = np.zeros((h, w), bool), np.zeros((h, w), bool)
    for src, dst in ((a, pa), (b, pb)):
        x0 = (w - src.shape[1]) // 2 if centre else 0
        dst[h - src.shape[0]:, x0:x0 + src.shape[1]] = src
    return float((pa & pb).sum() / max((pa | pb).sum(), 1))


sil_scale = load(ROUND, "sil_scale.json") or {}
base_scale = load(BASE, "sil_scale.json") or {}
for view in CARD.get("outline_views", []):
    ref = os.path.join(REFS, f"{view}.mask.png") if REFS else None
    refj = load(REFS, f"{view}.mask.json") if REFS else None
    img = os.path.join(ROUND, f"sil_{view}.png")
    if not ref or not os.path.exists(ref) or not refj:
        row(f"outline {view}", "no reference mask", False,
            note="trace the drawing to <refs>/<view>.mask.png with its <view>.mask.json {m_per_px} first")
        continue
    if view not in sil_scale:
        row(f"outline {view}", "round has no sil_scale.json", False, hard=True)
        continue
    centre = view in ("bow", "stern")
    rm = at_scale(mask(ref), refj["m_per_px"])
    v = iou(at_scale(mask(img), sil_scale[view]["m_per_px"]), rm, centre)
    bimg = os.path.join(BASE, f"sil_{view}.png")
    vb = iou(at_scale(mask(bimg), base_scale[view]["m_per_px"]), rm, centre) if os.path.exists(bimg) and view in base_scale else None
    row(f"outline {view}", f"IoU {v:.3f}" + (f" (before {vb:.3f})" if vb is not None else ""), v >= 0.92)


def need(name, b, r):
    """A check whose file is missing in the round (or the baseline) fails: a tool that crashed must not pass."""
    if b is None or r is None:
        row(name, f"missing {name}.json in the {'round' if r is None else 'baseline'}", False, hard=True,
            note="rerun the tool; a crash or a renamed object leaves no file")
        return False
    return True


# fairness -----------------------------------------------------------
bf, rf = load(BASE, "fairness.json"), load(ROUND, "fairness.json")
if need("fairness", bf, rf):
    worse = []
    for k, v in bf["lines"].items():
        n = rf["lines"].get(k)
        if n is None:
            worse.append(f"{k} missing in the round")
        elif n["inflections"] > v["inflections"] or n["kinks"] > v["kinks"]:
            worse.append(f"{k} +{n['inflections'] - v['inflections']} infl/+{n['kinks'] - v['kinks']} kinks")
    row("fairness", f"inflections {bf['total_inflections']}→{rf['total_inflections']}, kinks {bf['total_kinks']}→{rf['total_kinks']}",
        not worse and rf.get("object") == bf.get("object"), hard=True, note="; ".join(worse))

# seams --------------------------------------------------------------
bj, rj = load(BASE, "seams.json"), load(ROUND, "seams.json")
if need("seams", bj, rj):
    worse = []
    for k, b in bj.items():
        v = rj.get(k)
        if v is None or v.get("missing"):
            worse.append(f"{k}: missing in the round")
            continue
        if b.get("missing") or not b.get("bins"):
            continue
        if v["bins"] < 0.9 * b["bins"]:
            worse.append(f"{k}: contact lost, {b['bins']}→{v['bins']} bins within 2 cm")
        # bin by bin: a stretch of the join that touched in the baseline and is open now (a denser mesh can only close
        # bins, so totals could hide new gaps; the bins themselves can't)
        # (touching = within 0.5 mm in the baseline, opened = more than 3 mm now: the margin keeps a re-triangulated
        # surface of the same shape, a millimetre or two off on a curved bilge, from reading as a gap)
        bb, vb = b.get("bin_mm", {}), v.get("bin_mm", {})
        newly = sorted(x for x, d in vb.items() if x in bb and bb[x] <= 0.5 and 3.0 < d < 20)
        if newly:
            worse.append(f"{k}: {len(newly)} bins opened at {', '.join(newly[:12])} m")
        if v["widest_mm"] > b["widest_mm"] + 0.5:
            worse.append(f"{k}: widest gap {b['widest_mm']}→{v['widest_mm']} mm")
    row("seams", f"{len(rj)} joins", not worse, hard=True, note="; ".join(worse))

# physics ------------------------------------------------------------
bp, rp = bs.get("physics") or None, rs.get("physics") or None
if need("physics (j22_hero_report)", bp, rp):
    dv = (rp["canoe_volume_m3"] - bp["canoe_volume_m3"]) / bp["canoe_volume_m3"]
    dcb = math.hypot(rp["cb_x"] - bp["cb_x"], rp["cb_z"] - bp["cb_z"])
    phys = f"physics {rp.get('physics_volume_m3')} m³, CB {rp.get('physics_cb')}"
    row("physics", f"volume {dv * 100:+.2f}%, CB moved {dcb * 100:.1f} cm", abs(dv) <= 0.01 and dcb <= 0.02, hard=True,
        note=f"round {rp['canoe_volume_m3']} m³ CB ({rp['cb_x']}, {rp['cb_z']}); {phys}")

# moved, added, removed --------------------------------------------------
# Objects in the card's own sections may move, appear and go. Outside them: a section listed in "moves_ok_sections"
# may move (the hull card lists the sections built on its curves, and those sections re-run their checks), a name
# matching a "moves_ok" rule may move; anything else that moves, and any shape-section object added or removed
# outside the card's sections, is a hard fail for the QA review to look at.
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("common_rules", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
mine = set(CARD.get("sections", []))
ok_secs = set(CARD.get("moves_ok_sections", []))
ok_rules = CARD.get("moves_ok", [])
moved, foreign = [], []
for name, o in rs["objects"].items():
    b = bs["objects"].get(name)
    if not b:
        continue
    d = math.dist(o["centre"], b["centre"])
    if d > 0.005:
        moved.append(f"{name} {d * 1000:.0f} mm")
        if o["section"] not in mine | ok_secs and not any(R.matches(name, r) for r in ok_rules):
            foreign.append(name)
added = sorted(set(rs["objects"]) - set(bs["objects"]))
removed = sorted(set(bs["objects"]) - set(rs["objects"]))
bad_add = [n for n in added if rs["objects"][n]["section"] not in mine | {"other"}]
bad_rm = [n for n in removed if bs["objects"][n]["section"] not in mine | {"other"} and n not in CARD.get("removes_ok", [])]
shape = [o for o in rs["objects"].values() if o["section"] != "other"]
lo3 = [min(o["min"][i] for o in shape) for i in range(3)]
hi3 = [max(o["max"][i] for o in shape) for i in range(3)]
inside = [n for n in added if rs["objects"][n]["section"] == "other" and
          all(rs["objects"][n]["max"][i] >= lo3[i] and rs["objects"][n]["min"][i] <= hi3[i] for i in range(3))]
if inside:
    row("unsectioned", f"{len(inside)} new objects in no section, inside the hull's bounds", False,
        note="add them to sections_j22.json if they are part of a moulding (they are hidden from the shape renders): "
             + ", ".join(inside[:20]))
row("moved", f"{len(moved)} moved, {len(added)} added, {len(removed)} removed", not (foreign or bad_add or bad_rm), hard=True,
    note=("moved outside this card's sections: " + ", ".join(foreign[:20]) + ". ") * bool(foreign) +
         ("shape objects added outside its sections: " + ", ".join(bad_add[:20]) + ". ") * bool(bad_add) +
         ("shape objects removed outside its sections: " + ", ".join(bad_rm[:20]) + ". ") * bool(bad_rm) +
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
