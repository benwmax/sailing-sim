"""Bluebonnet's rule check (docs/jclass-1): the 1930s Universal Rule rating and the size card, run by every slice.

    python3 -I rule_check.py <build.json>       prints the check and exits 1 if anything fails

Rating R = 0.18 L sqrt(S) / cbrt(D) (feet, square feet, cubic feet), which must be 76 ft or less, with:
  L  the load waterline length (specs_bluebonnet.json explains why that is close enough),
  S  the rated sail area: the size card's target until slice 6 measures the sails (build.json "sail_area_ft2"),
  D  the displaced volume in cubic feet: the hull's. The rudder is the keel's after part, inside the hull surface
     (slice 2 cuts it out along its stock line), so it is already counted; build.json's "appendage_ft3" adds anything
     hung outside the surface.
The draft must be 15 ft or less, and each size within the card's tolerance (5%). Plain Python: no Blender needed.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPECS = json.load(open(os.path.join(HERE, "specs_bluebonnet.json")))
FT = 0.3048


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
        # shell with its transom and deck, the rudder, the stock)
        shell = b.get("shell") or {}
        pieces = {"shell": shell} if "closed" in shell else shell
        need = ("shell_transom_deck", "rudder", "stock") if b.get("slice", 1) >= 2 else ("shell",)
        for name in need:
            if name not in pieces:
                r["pass"] = False
                print(f"FAIL: the build has no closure check for its {name}")
        for name, c in pieces.items():
            if not c.get("closed"):
                r["pass"] = False
                print(f"FAIL: the build's {name} does not close: {c}")
    print(report(r))
    sys.exit(0 if r["pass"] else 1)
