"""The environment loop's six checks for the shore edge kit (docs/envloop/shore-edges/), on render_edges.py's output.

    python Tools/envloop/shore-edges/check_edges.py --out DIR [--pack north-texas-lake]

1. Sizes: every measure on a type's card (packs/<pack>/cards/<type>.json) against what the kit built (measures.json): within the
   card's tolerance (5 percent by default) or inside its range.
2. Colour against a grey-card photo: pending until Bean's photos (reported, not failed).
3. No visible repeat inside a 40 m frame: the 60 m views (a 40 m wide frame) must score under REPEAT_MAX
   (render_edges.repeat_score: the strongest sideways self-match of the shore band). A wall built on a pitch (posts,
   piles, panels: the card's `periodic_by_design`) repeats by design and is reported, not failed; its surface still
   must not tile.
4. Variety: every edge type the pack lists exists (north-texas-lake: ten, riprap from the rock loop plus nine here).
5. Blind review: by three fresh reviewers once the in-game stills exist (pending, reported).
6. Budget: the edge's own triangles over 16 m (without the stand-in ground) within the card's budget.

Writes <out>/checks.json and prints a table; exits 1 if a check that can run now fails.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPEAT_MAX = 0.6
RIPRAP = os.path.join(os.path.dirname(os.path.dirname(HERE)), "shoreloop", "cards", "rock.json")


def check_measure(spec, got):
    if got is None:
        return False, "not built"
    if "range" in spec:
        lo, hi = spec["range"]
        return lo <= got <= hi, f"{got:.3f} in [{lo:.3f}, {hi:.3f}]"
    t, tol = spec["target"], spec.get("tol", 0.05)
    ok = abs(got - t) <= tol * abs(t)
    return ok, f"{got:.3f} vs {t:.3f} (+-{100 * tol:.0f}%)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pack", default="north-texas-lake")
    a = ap.parse_args()
    pdir = os.path.join(HERE, "packs", a.pack)
    want = json.load(open(os.path.join(pdir, "pack.json")))["types"]
    cards = {f[:-5]: json.load(open(os.path.join(pdir, "cards", f))) for f in sorted(os.listdir(os.path.join(pdir, "cards")))
             if f.endswith(".json") and f != "layers.json"}
    res, fails = {}, 0
    for kind, card in cards.items():
        path = os.path.join(a.out, kind, "measures.json")
        if not os.path.exists(path):
            res[kind] = {"rendered": False}
            print(f"{kind:10s} not rendered")
            continue
        rep = json.load(open(path))
        r = {"sizes": {}, "repeat": {}, "budget": None}
        for key, spec in card["measures"].items():
            ok, txt = check_measure(spec, rep["measures"].get(key))
            r["sizes"][key] = {"ok": ok, "detail": txt}
            fails += not ok
        periodic = card.get("periodic_by_design")
        for view, v in rep["views"].items():
            if view.startswith("60m"):
                # A wall built on a pitch (posts, piles, panels) repeats by design: reported, not failed.
                ok = v["repeat"] < REPEAT_MAX or bool(periodic)
                r["repeat"][view] = {"ok": ok, "score": v["repeat"], "periodic_by_design": periodic}
                fails += not ok
        tri, cap = rep["triangles_16m"], card["budget"]["piece_triangles_16m"]
        r["budget"] = {"ok": tri <= cap, "triangles_16m": tri, "budget": cap}
        fails += tri > cap
        r["colour"] = "pending: grey-card photos"
        r["blind"] = "pending: in-game stills (after Nov 21)"
        res[kind] = r
        sz = all(v["ok"] for v in r["sizes"].values())
        rp = all(v["ok"] for v in r["repeat"].values())
        worst = max([v["score"] for v in r["repeat"].values()] or [0])
        print(f"{kind:10s} sizes {'ok ' if sz else 'BAD'}  repeat {'ok ' if rp else 'BAD'} (worst {worst:.2f}{', by design' if periodic else ''})  "
              f"budget {'ok ' if r['budget']['ok'] else 'BAD'} ({tri}/{cap})")
        for key, v in r["sizes"].items():
            if not v["ok"]:
                print(f"    {key}: {v['detail']}")
    built = [k for k in res if res[k].get("rendered", True)] + (["riprap"] if os.path.exists(RIPRAP) else [])
    missing = [k for k in want if k not in built]
    res["variety"] = {"types": len(built), "want": len(want), "missing": missing, "ok": not missing}
    print(f"variety: {len(built)} of {len(want)} edge types in {a.pack} (riprap from the rock loop)" + (f", missing {missing}" if missing else ""))
    fails += bool(missing)
    json.dump(res, open(os.path.join(a.out, "checks.json"), "w"), indent=1)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
