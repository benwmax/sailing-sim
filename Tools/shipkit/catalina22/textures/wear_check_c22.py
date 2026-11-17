"""The Catalina 22's texture-loop checks (docs/c22-9; the loop's method: docs/texture-loop), the same checks as
Bluebonnet's slice 11 (Tools/shipkit/jclass/wear_check.py, whose measuring helpers this reuses).

    python3 -I Tools/shipkit/catalina22/textures/wear_check_c22.py <renders dir> [--fetch] [--out wear_check.json]
        [--sheets <dir>] [--blind-key <dir>/blind/key.json] [--pending-blind]

The renders are render_wear_c22.py's: wear_<view>_<level>.png lit, wear_<view>_<level>_albedo.png each material's
colour alone, wear_<view>_id.png each material in its own flat colour (wear_ids.json names them), wear_report.json the
build's coverage. Checks:

  coverage   every material the build uses is in a card or in 'unweathered' (with its reason)
  ladder     each kind's colour moves away from new as she ages and is neglected: L4 at least 8 (CIE76) from L0, L2 at
             least 4, L1 <= L2 <= L4 in that distance, and the kept L3 at least 6 from the neglected L4; each
             material's distances measured on its own and averaged over the kind by pixels. A kind no view shows
             fails unless LADDER_EXEMPT names it with the reason.
  colour     each CC0 reference scan's mean albedo (the cards' 'refs', fetched with --fetch to the git-ignored
             Data/Reference/raw/textures/C22) against the surface's colour at that level: a* b* within 6
  maps       her own maps (Inputs/c22-detail) are what textures_c22.py makes now, tile, show no big repeat (the
             tweed's plaid repeats with its tile by design), give 4 px/mm or more, and their patterns are the card's
  budget     her own maps' memory with mips under the card's cap
  blind      three fresh reviewers each give every sheet's five shuffled levels one of the card's five looks: all
             right, or one neighbouring swap, for every reviewer (reviews_c22.json against blind/key.json)

--sheets writes each surface's ladder (ladder_<sheet>.jpg, L0 to L4) cropped from its view to where its materials are,
and the same crops shuffled for the blind reviewers (blind/<sheet>.jpg, A to E, blind/key.json).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
import weathering_c22 as WC  # noqa: E402
sys.path.insert(0, os.path.join(REPO, "Tools", "shipkit", "jclass"))
import wear_check as JC  # noqa: E402  (Bluebonnet's: lab, de, decode, erode, target, fetch)
import textures as JT  # noqa: E402
import textures_c22 as TC  # noqa: E402

RAW = os.path.join(REPO, "Data", "Reference", "raw", "textures", "C22")
CARDS = WC.CARDS
LEVELS = ("L0", "L1", "L2", "L3", "L4")
# kinds whose ladder is held to a smaller step, and why (each still has to order L1 <= L2 <= L4)
LADDER_EXEMPT = {"metal.stainless": {"steps": (2, 1, 1), "why": "fresh water: 316 stainless barely tea-stains on a lake (the card's water rate), so it changes little; the blind ladder judges its gloss and spots"}}
# kinds no wear view shows, and why that is acceptable
UNSEEN_OK = {"canvas.bag": "the sail bags show only in the sail states' views (render_sails_c22.py), not at her mooring",
             "metal.painted": "no part of the rebuilt boat uses PaintedAluminium yet"}
# each blind sheet: the view that shows it best and the materials to crop to
SHEETS = {"topsides": ("hull", ("GelcoatHull",)),
          "bottom": ("bottom", ("GelcoatHull", "Antifouling", "Keel")),
          "deck": ("deck", ("NonSkid", "Deck")),
          "teak": ("cockpit", ("Teak", "Wood")),
          "canvas": ("poptop", ("SailCover",)),
          "liner": ("vberth", ("Liner",)),
          "headliner": ("aft", ("Headliner",)),
          "sole": ("aft", ("Sole",)),
          "joinery": ("saloon", ("Laminate",)),
          "cushions": ("vberth", ("Cushion", "Curtain"))}
SHEET_PX = 360


def measure(rdir):
    """{material: {level: (linear mean colour, pixels)}} over every wear view, and the views each shows in."""
    ids = json.load(open(os.path.join(rdir, "wear_ids.json")))
    views = sorted({f[5:-7] for f in os.listdir(rdir) if f.startswith("wear_") and f.endswith("_id.png")})
    acc, seen = {}, {}
    for v in views:
        code, sure = JC.decode(os.path.join(rdir, f"wear_{v}_id.png"))
        for k, name in ids.items():
            mask = JC.erode(code == int(k)) & sure
            n = int(mask.sum())
            if n < 200:
                continue
            seen.setdefault(name, []).append(v)
            for lv in LEVELS:
                p = os.path.join(rdir, f"wear_{v}_{lv}_albedo.png")
                if not os.path.exists(p):
                    continue
                lin = JC.to_lin(JC.load(p))[mask].sum(0)
                s, c = acc.setdefault(name, {}).get(lv, (np.zeros(3), 0))
                acc[name][lv] = (s + lin, c + n)
    return {name: {lv: (s / c, c) for lv, (s, c) in lvs.items()} for name, lvs in acc.items()}, seen


def by_kind(meas):
    idx = WC.material_index()
    out, mats = {}, {}
    for name, lvs in meas.items():
        if name not in idx:
            continue
        key = "%s.%s" % idx[name]
        mats.setdefault(key, []).append(name)
        for lv, (col, n) in lvs.items():
            s, c = out.setdefault(key, {}).get(lv, (np.zeros(3), 0))
            out[key][lv] = (s + col * n, c + n)
    return {k: {lv: (s / c, c) for lv, (s, c) in v.items()} for k, v in out.items()}, mats


def check_ladder(meas, mats):
    res = {}
    for s, card in CARDS["surfaces"].items():
        for k in card["kinds"]:
            key = f"{s}.{k}"
            names = [n for n in mats.get(key, []) if all(lv in meas[n] for lv in LEVELS)]
            if not names:
                res[key] = {"pass": key in UNSEEN_OK, "status": UNSEEN_OK.get(key, "not in any wear view")}
                continue
            per = {}
            for n in names:
                L, d, d34 = JC.ladder_of(meas[n])
                per[n] = {"lab": {lv: JC.rnd(L[lv], 1) for lv in LEVELS},
                          "from_new": {lv: round(d[lv], 1) for lv in LEVELS},
                          "kept_vs_neglected": round(d34, 1), "pixels": int(meas[n]["L0"][1])}
            wt = np.array([per[n]["pixels"] for n in names], float)
            d = {lv: float(np.dot(wt, [per[n]["from_new"][lv] for n in names]) / wt.sum()) for lv in LEVELS}
            d34 = float(np.dot(wt, [per[n]["kept_vs_neglected"] for n in names]) / wt.sum())
            l4, l2, k34 = LADDER_EXEMPT.get(key, {}).get("steps", (8, 4, 6))
            ok = d["L4"] >= l4 and d["L2"] >= l2 and d["L1"] <= d["L2"] <= d["L4"] and d34 >= k34
            res[key] = {"from_new": {lv: round(d[lv], 1) for lv in LEVELS}, "kept_vs_neglected": round(d34, 1),
                        "pixels": int(wt.sum()), "materials": per, "pass": bool(ok)}
            if key in LADDER_EXEMPT:
                res[key]["exempt"] = LADDER_EXEMPT[key]["why"]
    return res


def check_colour(kinds, fetch_refs):
    JC.RAW = RAW
    groups = {}
    for s, card in CARDS["surfaces"].items():
        for ref in card.get("refs", []):
            path = JC.fetch(ref) if fetch_refs else os.path.join(RAW, ref["id"] + ".jpg")
            g = groups.setdefault((s, ref["for"], ref["level"]), {"refs": [], "labs": []})
            g["refs"].append(ref["id"])
            if os.path.exists(path):
                g["labs"].append(JC.target(path)["lab"])
    res = []
    for (s, f, lv), g in groups.items():
        row = {"surface": s, "for": f, "level": lv, "refs": g["refs"]}
        if len(g["labs"]) < len(g["refs"]):
            res.append(dict(row, status="not fetched (run with --fetch)", pass_=False))
            continue
        tg = np.mean(np.array(g["labs"]), 0)
        if f == "rust":
            ours, what = JC.lab(np.array(WC._lin(WC.RUST))), "the rust colour"
        else:
            key = f"{s}.{f}"
            if key not in kinds or lv not in kinds[key]:
                res.append(dict(row, target=JC.rnd(tg), status="not seen in the wear views", pass_=False))
                continue
            ours, what = JC.lab(kinds[key][lv][0]), f"{key} at {lv}"
        dab = math.hypot(ours[1] - tg[1], ours[2] - tg[2])
        res.append(dict(row, target=JC.rnd(tg), ours=JC.rnd(ours), what=what, d_ab=round(dab, 1),
                        d_L=round(float(ours[0] - tg[0]), 1), pass_=bool(dab <= 6.0)))
    return res


def check_maps():
    d = WC.OWN_DIR
    res, total = {}, 0.0
    for name, card in CARDS["maps"]["own"].items():
        hmm, m_new, tile, sizes = TC.MAKERS[name](card)
        n_new = JT.normal_map(hmm, tile)
        m_new = (np.clip(m_new, 0, 1) * 255 + 0.5).astype(np.uint8)
        n_png = np.asarray(Image.open(os.path.join(d, f"T_C22_{name}_N.png")).convert("RGB"))
        m_png = np.asarray(Image.open(os.path.join(d, f"T_C22_{name}_M.png")).convert("RGB"))
        same = (n_png.shape == n_new.shape and m_png.shape == m_new.shape
                and int(np.abs(n_png.astype(int) - n_new).max()) <= 1 and int(np.abs(m_png.astype(int) - m_new).max()) <= 1)
        h, w = m_png.shape[:2]
        mb = (w * h * 1.0 + w * h * 0.5) * 4.0 / 3.0 / 2 ** 20
        total += mb
        size = JT.size_report(sizes)
        r = {"same_as_generator": bool(same), "px": [w, h], "px_per_mm": round(min(w / tile[0], h / tile[1]), 2),
             "tiling_N": JT.tiling(n_png), "tiling_M": JT.tiling(m_png), "repeat_N": JT.repeat_share(n_png),
             "repeat_M": JT.repeat_share(m_png), "size": size, "mb_high": round(mb, 3)}
        # the tweed's tone is its plaid, which repeats with the tile by design: its repeat is judged on the weave
        rep_m = JT.repeat_share(m_png[..., 1:]) if name == "Tweed" else r["repeat_M"]
        r["pass_"] = bool(same and max(r["tiling_N"], r["tiling_M"]) <= 1.0 and max(r["repeat_N"], rep_m) < 0.2
                          and r["px_per_mm"] >= CARDS["closest_px_per_mm"] and all(v["pass"] for v in size.values()))
        res[name] = r
    budget = {"high_mb": round(total, 3), "cap_mb": CARDS["budget"]["high_mb"],
              "pass_": bool(total <= CARDS["budget"]["high_mb"])}
    return res, budget


def check_blind(key_path, pending_ok=False):
    path = os.path.join(HERE, "reviews_c22.json")
    if not os.path.exists(path):
        return {"status": "pending: no reviews_c22.json", "pass": {s: pending_ok for s in SHEETS}}
    if not key_path or not os.path.exists(key_path):
        return {"status": "no blind/key.json given (--blind-key)", "pass": {s: False for s in SHEETS}}
    key = json.load(open(key_path))["key"]
    rv = json.load(open(path))
    rank = {lv: i for i, lv in enumerate(LEVELS)}
    out = {}
    for s in SHEETS:
        out[s] = {}
        for who, answers in rv.get("reviewers", {}).items():
            got = answers.get("ladder", {}).get(s)
            if not got:
                continue
            given = [got.get(letter) for letter in "ABCDE"]
            wrong = [(given[i], key[s][i]) for i in range(5) if given[i] != key[s][i]]
            if sorted(given, key=lambda x: rank.get(x, 9)) != list(LEVELS):
                verdict = "not a permutation"
            elif not wrong:
                verdict = "all five"
            elif len(wrong) == 2 and wrong[0] == wrong[1][::-1] and abs(rank[wrong[0][0]] - rank[wrong[0][1]]) == 1:
                verdict = "one neighbouring swap"
            else:
                verdict = f"{5 - len(wrong)} right"
            out[s][who] = verdict
    passed = {s: len(r) >= 3 and all(v in ("all five", "one neighbouring swap") for v in r.values())
              for s, r in out.items()}
    return {"status": "reviewed", "verdicts": out, "pass": passed}


def crop_box(rdir, view, names):
    ids = json.load(open(os.path.join(rdir, "wear_ids.json")))
    code, sure = JC.decode(os.path.join(rdir, f"wear_{view}_id.png"))
    mask = np.zeros(code.shape, bool)
    for k, n in ids.items():
        if n in names:
            mask |= (code == int(k)) & sure
    ys, xs = np.nonzero(mask)
    h, w = code.shape
    if len(xs) < 50:
        return (0, 0, w, h)
    x0, x1 = np.percentile(xs, [2, 98])
    y0, y1 = np.percentile(ys, [2, 98])
    pad = 0.05 * max(x1 - x0, y1 - y0)
    x0, x1 = max(0, int(x0 - pad)), min(w, int(x1 + pad))
    y0, y1 = max(0, int(y0 - pad)), min(h, int(y1 + pad))
    # keep it from going too thin: at least 0.6 of the height as wide, and the reverse
    if (x1 - x0) < 0.6 * (y1 - y0):
        c = (x0 + x1) // 2
        x0, x1 = max(0, c - int(0.3 * (y1 - y0))), min(w, c + int(0.3 * (y1 - y0)))
    return (x0, y0, x1, y1)


def make_sheets(rdir, out):
    from PIL import ImageDraw, ImageFont
    font = ImageFont.load_default(size=22)
    os.makedirs(os.path.join(out, "blind"), exist_ok=True)
    rng = np.random.default_rng(22)
    key = {}
    for sheet_name, (view, names) in SHEETS.items():
        box = crop_box(rdir, view, names)
        crops = {}
        for lv in LEVELS:
            im = Image.open(os.path.join(rdir, f"wear_{view}_{lv}.png")).convert("RGB").crop(box)
            crops[lv] = im.resize((round(im.width * SHEET_PX / im.height), SHEET_PX), Image.LANCZOS)
        order = list(LEVELS)
        while order == list(LEVELS):
            order = [LEVELS[i] for i in rng.permutation(5)]
        key[sheet_name] = order
        for name, seq, labels in (("ladder_" + sheet_name, list(LEVELS), list(LEVELS)),
                                  (os.path.join("blind", sheet_name), order, list("ABCDE"))):
            cw = crops["L0"].width
            sheet = Image.new("RGB", (5 * cw + 4 * 8, SHEET_PX + 40), (24, 24, 24))
            d = ImageDraw.Draw(sheet)
            for i, (lv, lab) in enumerate(zip(seq, labels)):
                sheet.paste(crops[lv], (i * (cw + 8), 40))
                d.text((i * (cw + 8) + 8, 8), lab, fill=(235, 235, 235), font=font)
            sheet.save(os.path.join(out, name + ".jpg"), quality=85, optimize=True)
    json.dump({"key": key, "about": "the level shown under each letter A to E of blind/<sheet>.jpg"},
              open(os.path.join(out, "blind", "key.json"), "w"), indent=1)
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--sheets", default=None)
    ap.add_argument("--blind-key", default=None)
    ap.add_argument("--pending-blind", action="store_true")
    a = ap.parse_args()
    if a.sheets:
        make_sheets(a.renders, a.sheets)
    key_path = a.blind_key or (os.path.join(a.sheets, "blind", "key.json") if a.sheets else None)
    rp = os.path.join(a.renders, "wear_report.json")
    report = json.load(open(rp)) if os.path.exists(rp) else None
    meas, seen = measure(a.renders)
    kinds, mats = by_kind(meas)
    ladder = check_ladder(meas, mats)
    colour = check_colour(kinds, a.fetch)
    maps, budget = check_maps()
    blind = check_blind(key_path, a.pending_blind)
    fails = [] if report and not report["uncovered"] else [f"coverage {report['uncovered'] if report else 'no wear_report.json'}"]
    fails += [f"ladder {k}" + (f" ({v['status']})" if "status" in v else "") for k, v in ladder.items() if not v["pass"]]
    fails += [f"colour {c.get('what', c['surface'] + '.' + c['for'])} ({c.get('d_ab', c.get('status'))})"
              for c in colour if c.get("pass_") is False]
    fails += [f"map {k}" for k, v in maps.items() if not v["pass_"]]
    fails += [] if budget["pass_"] else ["budget"]
    fails += [f"blind {s} ({blind['status']})" for s, ok in blind["pass"].items() if not ok]
    unseen = sorted(set(WC.material_index()) - set(seen))
    rep = {"coverage": report and {k: report[k] for k in ("uncovered", "not_built")}, "ladder": ladder,
           "colour": colour, "maps": maps, "budget": budget, "blind": blind, "seen_in": seen,
           "not_in_any_view": unseen, "fails": fails}
    json.dump(rep, open(a.out or os.path.join(a.renders, "wear_check.json"), "w"), indent=1)
    for k, v in ladder.items():
        if "status" in v:
            print(f"ladder {k:22s} {v['status']}  FAIL")
            continue
        print(f"ladder {k:22s} from new {v['from_new']}  kept/neglected {v['kept_vs_neglected']}  "
              f"{'pass' if v['pass'] else 'FAIL'}")
    for c in colour:
        if "d_ab" in c:
            print(f"colour {c['what']:28s} d_ab {c['d_ab']:5.1f} d_L {c['d_L']:6.1f} ({', '.join(c['refs'])})  "
                  f"{'pass' if c['pass_'] else 'FAIL'}")
        else:
            print(f"colour {c['surface']}.{c['for']} {c['level']}: {c['status']}")
    for k, v in maps.items():
        print(f"map {k}: tiling {v['tiling_N']}/{v['tiling_M']} repeat {v['repeat_N']}/{v['repeat_M']} "
              f"{v['px_per_mm']} px/mm {v['mb_high']} MB {'pass' if v['pass_'] else 'FAIL'}")
    print(f"budget {budget['high_mb']} of {budget['cap_mb']} MB on High")
    print(f"blind: {blind['status']}", blind.get("verdicts", ""))
    print("not in any wear view:", unseen)
    print("FAILS:" if fails else "all checks pass", fails if fails else "")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
