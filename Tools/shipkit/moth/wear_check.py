"""Slice 6's texture-loop checks for the moth (docs/moth-10; the loop's method: docs/texture-loop), as the J-Class's
slice 11 (Tools/shipkit/jclass/wear_check.py, whose colour helpers this borrows).

    python3 -I Tools/shipkit/moth/wear_check.py <renders dir> [--fetch] [--out wear_check.json] [--sheets <dir>]
        [--pending-blind]

The renders are render_wear.py's: wear_<view>_<level>.png lit, wear_<view>_<level>_albedo.png each material's colour
alone, wear_<view>_id.png each material in its id colour (wear_ids.json). Checks:

  ladder   each kind's colour moves away from new: L4 at least 8 (CIE76) from L0, L2 at least 4, L1 no further than L2
           and L2 no further than L4, and the kept L3 at least 6 from the neglected L4; each material measured on its
           own over every view that shows it, averaged over the kind by pixels. A kind no view shows fails.
  colour   each CC0 scan in a card's refs (fetched with --fetch to the git-ignored Data/Reference/raw/textures/Moth)
           against the surface's colour at its level: a* and b* within 6 (L* reported only: a scan's exposure is its
           own).
  maps     her own maps, from the PNGs: each is what textures.py makes now (within one level), wraps (the edge no
           rougher than the roughest interior line), gives at least 4 pixels a millimetre, its pattern the card's size
           within 10%.
  budget   her own maps' memory with mips (BC5 normals, BC1 masks) from the PNGs, under the card's caps.
  blind    reviews_moth.json's answers against the sheets' blind/key.json: each reviewer gives each of a sheet's five
           shuffled crops one of the card's five descriptions, each once; all five right or one swap of neighbouring
           levels passes; a sheet passes when every one of at least three reviewers does, and when none of them called
           the material something it is not. No reviews fails (--pending-blind: pending).

--sheets writes each ladder (ladder_<surface>.jpg, L0 to L4 left to right, cropped from its view to its materials) and
the same crops shuffled under A to E for the reviewers (blind/<surface>.jpg; blind/key.json the level behind each).
Prints the failures and writes the numbers as JSON; exits 1 if a check fails.
"""
import argparse
import io
import json
import math
import os
import sys
import urllib.request
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import weathering_moth as WE  # noqa: E402


def _jclass_check():
    """The J-Class's wear_check (to_lin, lab, de, rnd, load, erode, target), loaded by path: it shares this file's name."""
    import importlib.util
    jdir = os.path.join(REPO, "Tools", "shipkit", "jclass")
    sys.path.insert(1, jdir)
    spec = importlib.util.spec_from_file_location("jclass_wear_check", os.path.join(jdir, "wear_check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


JC = _jclass_check()

RAW = os.path.join(REPO, "Data", "Reference", "raw", "textures", "Moth")
CARDS = WE.CARDS
LEVELS = ("L0", "L1", "L2", "L3", "L4")
UA = {"User-Agent": "texture-loop-reference-fetch/1.0"}
SHEET_PX = 360


def fetch(ref):
    """A CC0 scan's colour map (ambientCG), measured only, never shipped."""
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, ref["id"] + ".jpg")
    if os.path.exists(path):
        return path
    if ref["site"] != "ambientcg":
        raise SystemExit(f"unknown site {ref['site']}")
    data = urllib.request.urlopen(urllib.request.Request(
        f"https://ambientcg.com/get?file={ref['id']}_1K-JPG.zip", headers=UA)).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    name = next(n for n in z.namelist() if n.endswith("_Color.jpg"))
    open(path, "wb").write(z.read(name))
    return path


def decode(path):
    """An id render's material code per pixel (WE.material_id) and where it is sure (every channel within 0.1 of a
    third: an edge's blend, or a pixel seen through the mesh or the film, is no one's)."""
    raw = JC.load(path)
    q = np.round(raw * 3.0)
    sure = np.all(np.abs(raw - q / 3.0) <= 0.1, axis=-1)
    q = q.astype(int)
    return q[..., 0] + 4 * q[..., 1] + 16 * q[..., 2], sure


def ids_of(rdir):
    return json.load(open(os.path.join(rdir, "wear_ids.json")))["ids"]


def measure(rdir):
    """{material: {level: (linear mean colour, pixels)}} over every view, and the views each shows in."""
    ids = ids_of(rdir)
    views = sorted({f[5:-7] for f in os.listdir(rdir) if f.startswith("wear_") and f.endswith("_id.png")})
    acc, seen = {}, {}
    for v in views:
        code, sure = decode(os.path.join(rdir, f"wear_{v}_id.png"))
        for name, k in ids.items():
            mask = JC.erode(code == int(k)) & sure
            n = int(mask.sum())
            if n < 150:
                continue
            seen.setdefault(name, []).append(v)
            for lv in LEVELS:
                p = os.path.join(rdir, f"wear_{v}_{lv}_albedo.png")
                if os.path.exists(p):
                    s, c = acc.setdefault(name, {}).get(lv, (np.zeros(3), 0))
                    acc[name][lv] = (s + JC.to_lin(JC.load(p))[mask].sum(0), c + n)
    return {name: {lv: (s / c, c) for lv, (s, c) in lv_.items()} for name, lv_ in acc.items()}, seen


# kinds no wear view shows, and why that is acceptable
UNSEEN_OK = {"carbon.batten": "inside the sail's pockets, behind the film in every view; its terms and dresser are the "
                              "tubes' (carbon.tube), measured there"}


def check_ladder(meas):
    idx = WE.material_index()
    res = {}
    for s, card in CARDS["surfaces"].items():
        for k, names in card["kinds"].items():
            key = f"{s}.{k}"
            names = [n for n in names if n in meas and all(lv in meas[n] for lv in LEVELS)]
            if not names:
                res[key] = {"pass": key in UNSEEN_OK, "status": UNSEEN_OK.get(key, "not in any wear view")}
                continue
            per = {}
            for n in names:
                L = {lv: JC.lab(meas[n][lv][0]) for lv in LEVELS}
                per[n] = {"lab": {lv: JC.rnd(L[lv], 1) for lv in LEVELS},
                          "from_new": {lv: round(JC.de(L["L0"], L[lv]), 1) for lv in LEVELS},
                          "kept_vs_neglected": round(JC.de(L["L3"], L["L4"]), 1), "pixels": int(meas[n]["L0"][1])}
            wt = np.array([per[n]["pixels"] for n in names], float)
            d = {lv: float(np.dot(wt, [per[n]["from_new"][lv] for n in names]) / wt.sum()) for lv in LEVELS}
            d34 = float(np.dot(wt, [per[n]["kept_vs_neglected"] for n in names]) / wt.sum())
            ok = d["L4"] >= 8 and d["L2"] >= 4 and d["L1"] <= d["L2"] <= d["L4"] and d34 >= 6
            res[key] = {"from_new": {lv: round(d[lv], 1) for lv in LEVELS}, "kept_vs_neglected": round(d34, 1),
                        "pixels": int(wt.sum()), "materials": per, "pass": bool(ok)}
    assert set(idx) >= {n for r in res.values() for n in r.get("materials", {})}
    return res


def check_colour(meas, fetch_refs):
    res = []
    for s, card in CARDS["surfaces"].items():
        for ref in card.get("refs", []):
            path = fetch(ref) if fetch_refs else os.path.join(RAW, ref["id"] + ".jpg")
            row = {"surface": s, "ref": ref["id"], "level": ref["level"]}
            if not os.path.exists(path):
                res.append(dict(row, status="not fetched (run with --fetch)", pass_=False))
                continue
            tg = np.array(JC.target(path)["lab"])
            names = [n for names in card["kinds"].values() for n in names if n in meas and ref["level"] in meas[n]]
            if not names:
                res.append(dict(row, status="not seen in the wear views", pass_=False))
                continue
            wt = np.array([meas[n][ref["level"]][1] for n in names], float)
            col = sum(meas[n][ref["level"]][0] * w for n, w in zip(names, wt)) / wt.sum()
            ours = JC.lab(col)
            dab = math.hypot(ours[1] - tg[1], ours[2] - tg[2])
            res.append(dict(row, target=JC.rnd(tg), ours=JC.rnd(ours), d_ab=round(dab, 1),
                            d_L=round(float(ours[0] - tg[0]), 1), pass_=bool(dab <= 6.0)))
    return res


def check_maps():
    import importlib.util
    argv, sys.argv = sys.argv, [sys.argv[0]]       # textures.py reads its own arguments at import
    spec = importlib.util.spec_from_file_location("moth_textures", os.path.join(HERE, "textures.py"))
    TX = importlib.util.module_from_spec(spec)      # by path: the J-Class has a textures.py too
    spec.loader.exec_module(TX)
    sys.argv = argv
    d = os.path.join(REPO, "Inputs", "moth-detail")
    res, total = {}, 0.0
    for name, card in CARDS["maps"]["own"].items():
        hmm, m_new, tile, sizes = TX.BUILD[name](card)
        n_new = TX.normal_map(hmm * card.get("normal_strength", 1.0), tile)
        m_new = (np.clip(m_new, 0, 1) * 255 + 0.5).astype(np.uint8)
        n_png = np.asarray(Image.open(os.path.join(d, f"T_Moth_{name}_N.png")).convert("RGB"))
        m_png = np.asarray(Image.open(os.path.join(d, f"T_Moth_{name}_M.png")).convert("RGB"))
        same = (n_png.shape == n_new.shape and m_png.shape == m_new.shape
                and int(np.abs(n_png.astype(int) - n_new).max()) <= 1
                and int(np.abs(m_png.astype(int) - m_new).max()) <= 1)
        h, w = m_png.shape[:2]
        mb = TX.mb(w)
        total += mb
        size = {k: {"map_mm": a, "card_mm": b, "off": round(a / b - 1, 3)} for k, (a, b) in sizes.items()}
        r = {"same_as_generator": bool(same), "px": [w, h], "px_per_mm": round(w / tile[0], 2),
             "tiling_N": TX.seam(n_png), "tiling_M": TX.seam(m_png), "size": size, "mb_high": round(mb, 3)}
        r["pass_"] = bool(same and max(r["tiling_N"], r["tiling_M"]) <= 1.0
                          and r["px_per_mm"] >= CARDS["closest_px_per_mm"]
                          and all(abs(v["off"]) <= 0.1 for v in size.values()))
        res[name] = r
    budget = {"high_mb": round(total, 3), "cap_mb": CARDS["budget"]["high_mb"], "medium_mb": 0.0,
              "medium_cap_mb": CARDS["budget"]["medium_mb"], "pass_": bool(total <= CARDS["budget"]["high_mb"])}
    return res, budget


def sheets():
    """{sheet: (view, the materials it is cropped to, the card whose descriptions it is judged by)}."""
    out = {}
    for key, (view, _) in CARDS["views"]["ladder"].items():
        s, _, k = key.partition(".")
        kinds = CARDS["surfaces"][s]["kinds"]
        names = kinds[k] if k else ([n for kk, ns in kinds.items() if kk != "foil" for n in ns] if s == "paint"
                                    else [n for ns in kinds.values() for n in ns])
        out[key] = (view, names)
    return out


def check_blind(key_path, pending_ok=False):
    path = os.path.join(HERE, "reviews_moth.json")
    sh = sheets()
    if not os.path.exists(path):
        return {"status": "pending: no reviews_moth.json", "pass": {s: pending_ok for s in sh}}
    if not key_path or not os.path.exists(key_path):
        return {"status": "no blind/key.json", "pass": {s: False for s in sh}}
    key = json.load(open(key_path))["key"]
    rv = json.load(open(path))
    rank = {lv: i for i, lv in enumerate(LEVELS)}
    out, wrong_material = {}, {}
    for s in sh:
        out[s] = {}
        for who, ans in rv.get("reviewers", {}).items():
            got = ans.get("ladder", {}).get(s)
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
            if ans.get("material_ok", {}).get(s) is False:
                wrong_material.setdefault(s, []).append(who)
    passed = {s: len(r) >= 3 and all(v in ("all five", "one neighbouring swap") for v in r.values())
              and s not in wrong_material for s, r in out.items()}
    return {"status": "reviewed", "verdicts": out, "wrong_material": wrong_material, "pass": passed}


def crop_box(rdir, view, names):
    ids = ids_of(rdir)
    code, sure = decode(os.path.join(rdir, f"wear_{view}_id.png"))
    mask = np.isin(code, [ids[n] for n in names if n in ids]) & sure
    h, w = mask.shape
    if mask.sum() < 150:
        return 0, 0, w, h
    ys, xs = np.nonzero(mask)
    x0, x1 = np.percentile(xs, (2, 98))
    y0, y1 = np.percentile(ys, (2, 98))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw, bh = max(x1 - x0 + 0.08 * w, w / 2.5), max(y1 - y0 + 0.08 * h, h / 2.5)
    bw, bh = max(bw, bh * 0.75), max(bh, bw / 1.6)
    bw, bh = min(bw, w), min(bh, h)
    left, top = min(max(cx - bw / 2, 0), w - bw), min(max(cy - bh / 2, 0), h - bh)
    return int(left), int(top), int(left + bw), int(top + bh)


def make_sheets(rdir, out, round_=3):
    font = ImageFont.load_default(size=22) if hasattr(ImageFont, "load_default") else None
    os.makedirs(os.path.join(out, "blind"), exist_ok=True)
    rng = np.random.default_rng(6 + round_)          # a new shuffle each review round
    key = {}
    for sheet, (view, names) in sheets().items():
        box = crop_box(rdir, view, names)
        crops = {}
        for lv in LEVELS:
            im = Image.open(os.path.join(rdir, f"wear_{view}_{lv}.png")).convert("RGB").crop(box)
            crops[lv] = im.resize((round(im.width * SHEET_PX / im.height), SHEET_PX), Image.LANCZOS)
        order = list(LEVELS)
        while order == list(LEVELS):
            order = [LEVELS[i] for i in rng.permutation(5)]
        key[sheet] = order
        for name, seq, labels in (("ladder_" + sheet.replace(".", "_"), list(LEVELS), list(LEVELS)),
                                  (os.path.join("blind", sheet.replace(".", "_")), order, list("ABCDE"))):
            cw = crops["L0"].width
            im = Image.new("RGB", (5 * cw + 4 * 8, SHEET_PX + 40), (24, 24, 24))
            d = ImageDraw.Draw(im)
            for i, (lv, lab) in enumerate(zip(seq, labels)):
                im.paste(crops[lv], (i * (cw + 8), 40))
                d.text((i * (cw + 8) + 8, 8), lab, fill=(235, 235, 235), font=font)
            im.save(os.path.join(out, name + ".jpg"), quality=86, optimize=True)
    json.dump({"key": key, "about": "the level shown under each letter A to E of blind/<sheet>.jpg"},
              open(os.path.join(out, "blind", "key.json"), "w"), indent=1)
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--sheets", default=None)
    ap.add_argument("--pending-blind", action="store_true")
    ap.add_argument("--round", type=int, default=3, help="the review round: its own shuffle of the blind sheets")
    a = ap.parse_args()
    if a.sheets:
        make_sheets(a.renders, a.sheets, a.round)
    key_path = os.path.join(a.sheets, "blind", "key.json") if a.sheets else None
    meas, seen = measure(a.renders)
    ladder = check_ladder(meas)
    colour = check_colour(meas, a.fetch)
    maps, budget = check_maps()
    blind = check_blind(key_path, a.pending_blind)
    fails = [f"ladder {k}" + (f" ({v['status']})" if "status" in v else "") for k, v in ladder.items() if not v["pass"]]
    fails += [f"colour {c['surface']} {c['ref']} ({c.get('d_ab', c.get('status'))})" for c in colour if not c["pass_"]]
    fails += [f"map {k}" for k, v in maps.items() if not v["pass_"]]
    fails += [] if budget["pass_"] else ["budget"]
    fails += [f"blind {s} ({blind['status']})" for s, ok in blind["pass"].items() if not ok]
    rep = {"ladder": ladder, "colour": colour, "maps": maps, "budget": budget, "blind": blind,
           "ab": "none: her first textured round, so there is no earlier textured version to hold it against",
           "seen_in": seen, "not_in_any_view": sorted(set(WE.material_index()) - set(seen)), "fails": fails}
    path = a.out or os.path.join(a.renders, "wear_check.json")
    json.dump(rep, open(path, "w"), indent=1)
    for k, v in ladder.items():
        if "from_new" in v:
            print(f"{k:16s} " + " ".join(f"{lv} {v['from_new'][lv]:5.1f}" for lv in LEVELS[1:])
                  + f"  L3-L4 {v['kept_vs_neglected']:5.1f}  {'ok' if v['pass'] else 'FAIL'}")
    for c in colour:
        print("colour", c)
    print("budget", budget)
    print("fails:", fails or "none")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
