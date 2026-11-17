"""Slice 15's texture-loop checks for the frigate Commonwealth (docs/shipkit-15; the loop's method: docs/texture-loop).
The J-Class's wear_check.py (docs/jclass-11) with her cards, maps and sheets.

    python3 -I Tools/shipkit/frigate/wear_check.py <renders dir> [--fetch] [--out wear_check.json] [--sheets <dir>]
        [--blind-key <dir>/blind/key.json] [--pending-blind]

The renders are render_wear.py's: wear_<view>_<level>.png lit, wear_<view>_<level>_albedo.png each material's colour
alone (no light), wear_<view>_id.png each material in its own flat colour (wear_ids.json names them). From those it
measures each surface's colour at each level, where that surface shows in the views, and checks:

  colour     each CC0 reference scan's mean albedo (textures_1797.json 'refs': Poly Haven and ambientCG, fetched with
             --fetch to the git-ignored Data/Reference/raw/textures/Commonwealth) against the surface's measured colour
             at the level the scan stands for: a* and b* within 6 (the loop's rule; L* is reported, since a scan's
             exposure is its own). A 'rust' reference is held against the materials' rust colour itself.
  ladder     each kind's colour moves away from new as she ages and is neglected: L4 at least 8 (CIE76) from L0, L2 at
             least 4, the order L1 <= L2 <= L4 in that distance, and the kept L3 at least 6 from the neglected L4. Each
             material's distances are measured on its own and averaged over the kind by pixels. A kind no view shows
             fails.
  maps       her own map, from the PNGs: what textures.py makes now, tiles, shows no big repeat, gives at least
             closest_px_per_mm pixels a millimetre, and its pattern is the card's size.
  budget     her own maps' memory with mips (BC5 normals, BC1 masks), under the card's caps.
  blind      the blind reviewers' answers (reviews_1797.json) against the sheets' blind/key.json: each reviewer gives
             each surface's five shuffled levels one of the card's five descriptions, each once; all five right, or one
             swap of two neighbouring levels, passes, and every reviewer (three at least) must pass every surface.

--sheets writes each surface's ladder (ladder_<surface>.jpg) and the same crops shuffled for the blind reviewers
(blind/<surface>.jpg, A to E, with blind/key.json the level behind each letter).

Prints a summary and writes the numbers as JSON; exits 1 if a check fails.
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
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import weathering  # noqa: E402

RAW = os.path.join(REPO, "Data", "Reference", "raw", "textures", "Commonwealth")
CARDS = weathering.CARDS
LEVELS = ("L0", "L1", "L2", "L3", "L4")
UA = {"User-Agent": "texture-loop-reference-fetch/1.0"}


# ------------------------------------------------------------------------------------------------ colour
def to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def to_srgb(a):
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(np.clip(a, 0, None), 1 / 2.4) - 0.055)


def lab(lin):
    """Linear sRGB (..., 3) to CIE Lab (D65)."""
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = np.asarray(lin, float) @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def de(a, b):
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


def rnd(v, n=2):
    return [round(float(x), n) for x in v]


# ------------------------------------------------------------------------------------------------ references
def fetch(ref):
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, ref["id"] + ".jpg")
    if os.path.exists(path):
        return path
    if ref["site"] == "polyhaven":
        info = json.load(urllib.request.urlopen(urllib.request.Request(
            f"https://api.polyhaven.com/files/{ref['id']}", headers=UA)))
        url = info["Diffuse"]["1k"]["jpg"]["url"]
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()
        open(path, "wb").write(data)
    elif ref["site"] == "ambientcg":
        data = urllib.request.urlopen(urllib.request.Request(
            f"https://ambientcg.com/get?file={ref.get('asset', ref['id'])}_1K-JPG.zip", headers=UA)).read()
        z = zipfile.ZipFile(io.BytesIO(data))
        name = next(n for n in z.namelist() if n.endswith("_Color.jpg"))
        open(path, "wb").write(z.read(name))
    else:
        raise SystemExit(f"unknown site {ref['site']}")
    return path


def target(path):
    """A scan's mean albedo (averaged in linear light), as sRGB 0-255 and Lab."""
    a = np.asarray(Image.open(path).convert("RGB"), np.float64) / 255.0
    lin = to_lin(a).reshape(-1, 3).mean(0)
    return {"srgb": rnd(to_srgb(lin) * 255, 1), "lab": rnd(lab(lin))}


# ------------------------------------------------------------------------------------------------ the renders
def load(path):
    return np.asarray(Image.open(path).convert("RGB"), np.float64) / 255.0


def erode(mask):
    m = mask.copy()
    for ax in (0, 1):
        for d in (-1, 1):
            m &= np.roll(mask, d, ax)
    return m


def decode(path):
    """An id render's material code per pixel (weathering.material_id: each channel a third), and where it is sure:
    every channel within 0.1 of a third (a pixel blended at an edge, or dimmed, belongs to no material)."""
    raw = load(path)
    q = np.round(raw * 3.0)
    sure = np.all(np.abs(raw - q / 3.0) <= 0.1, axis=-1)
    q = q.astype(int)
    return q[..., 0] + 4 * q[..., 1] + 16 * q[..., 2], sure


def measure(rdir):
    """{material: {level: (linear mean colour, pixels)}} over every wear view, and the views each shows in."""
    ids = json.load(open(os.path.join(rdir, "wear_ids.json")))
    views = sorted({f[5:-7] for f in os.listdir(rdir) if f.startswith("wear_") and f.endswith("_id.png")})
    acc, seen = {}, {}
    for v in views:
        code, sure = decode(os.path.join(rdir, f"wear_{v}_id.png"))
        for k, name in ids.items():
            mask = erode(code == int(k)) & sure
            n = int(mask.sum())
            if n < 200:
                continue
            seen.setdefault(name, []).append(v)
            for lv in LEVELS:
                p = os.path.join(rdir, f"wear_{v}_{lv}_albedo.png")
                if not os.path.exists(p):
                    continue
                lin = to_lin(load(p))[mask].sum(0)
                s, c = acc.setdefault(name, {}).get(lv, (np.zeros(3), 0))
                acc[name][lv] = (s + lin, c + n)
    out = {name: {lv: (s / c, c) for lv, (s, c) in levels.items()} for name, levels in acc.items()}
    return out, seen


def by_kind(meas):
    """Each surface.kind's colour, pixel-weighted over its materials (for the colour targets), and its materials."""
    idx = weathering.material_index()
    out, mats = {}, {}
    for name, levels in meas.items():
        if name not in idx:
            continue
        key = "%s.%s" % idx[name]
        mats.setdefault(key, []).append(name)
        for lv, (col, n) in levels.items():
            s, c = out.setdefault(key, {}).get(lv, (np.zeros(3), 0))
            out[key][lv] = (s + col * n, c + n)
    return {k: {lv: (s / c, c) for lv, (s, c) in v.items()} for k, v in out.items()}, mats


# ------------------------------------------------------------------------------------------------ checks
def ladder_of(levels):
    L = {lv: lab(levels[lv][0]) for lv in LEVELS}
    return L, {lv: de(L["L0"], L[lv]) for lv in LEVELS}, de(L["L3"], L["L4"])


def check_ladder(meas, mats):
    """Each kind's ladder: every material's distances from new (CIE76, so a blue and a white enamel are never averaged
    into one colour first), averaged over the kind's materials by their pixels. A kind none of the views shows fails,
    unless UNSEEN_OK names it with the reason."""
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
                L, d, d34 = ladder_of(meas[n])
                per[n] = {"lab": {lv: rnd(L[lv], 1) for lv in LEVELS},
                          "from_new": {lv: round(d[lv], 1) for lv in LEVELS},
                          "kept_vs_neglected": round(d34, 1), "pixels": int(meas[n]["L0"][1])}
            wt = np.array([per[n]["pixels"] for n in names], float)
            d = {lv: float(np.dot(wt, [per[n]["from_new"][lv] for n in names]) / wt.sum()) for lv in LEVELS}
            d34 = float(np.dot(wt, [per[n]["kept_vs_neglected"] for n in names]) / wt.sum())
            ok = d["L4"] >= 8 and d["L2"] >= 4 and d["L1"] <= d["L2"] <= d["L4"] and d34 >= 6
            res[key] = {"from_new": {lv: round(d[lv], 1) for lv in LEVELS}, "kept_vs_neglected": round(d34, 1),
                        "pixels": int(wt.sum()), "materials": per, "pass": bool(ok)}
    return res


# kinds no wear view shows, and why that is acceptable
UNSEEN_OK = {"iron.lead": "the lead is the gun deck's (the 24-pounders' aprons over the vents, slice 12): checked with the gun deck's textures once it merges"}


def check_colour(kinds, fetch_refs):
    """Each group of references (same surface, target and level) averaged in Lab against our colour there."""
    groups = {}
    for s, card in CARDS["surfaces"].items():
        for ref in card.get("refs", []):
            path = os.path.join(RAW, ref["id"] + ".jpg")
            if fetch_refs:
                path = fetch(ref)
            g = groups.setdefault((s, ref["for"], ref["level"]), {"refs": [], "labs": []})
            g["refs"].append(ref["id"])
            if os.path.exists(path):
                g["labs"].append(target(path)["lab"])
    res = []
    for (s, f, lv), g in groups.items():
        row = {"surface": s, "for": f, "level": lv, "refs": g["refs"]}
        if len(g["labs"]) < len(g["refs"]):
            res.append(dict(row, status="not fetched (run with --fetch)", pass_=False))
            continue
        tg = np.mean(np.array(g["labs"]), 0)
        if f == "rust":
            ours = lab(np.array(weathering._lin(weathering.RUST)))
            what = "the rust colour"
        else:
            key = f"{s}.{f}"
            if key not in kinds or lv not in kinds[key]:
                res.append(dict(row, target=rnd(tg), status="not seen in the wear views", pass_=False))
                continue
            ours = lab(kinds[key][lv][0])
            what = f"{key} at {lv}"
        dab = math.hypot(ours[1] - tg[1], ours[2] - tg[2])
        res.append(dict(row, target=rnd(tg), ours=rnd(ours), what=what, d_ab=round(dab, 1),
                        d_L=round(float(ours[0] - tg[0]), 1), pass_=bool(dab <= 6.0)))
    return res


def check_maps():
    """Her own maps, from the files: each PNG must be what textures.py makes now (within one level, so a stale or
    hand-edited map fails), and the tiling, repeat, sharpness and pattern sizes are measured on it here; the memory is
    from the PNGs' sizes."""
    import textures
    JT = textures.JT
    d = os.path.join(REPO, "Inputs", "frigate-detail")
    res = {}
    total = 0.0
    for name, card in CARDS["maps"]["own"].items():
        hmm, m_new, tile, sizes = textures.MAKERS[name](card)
        n_new = JT.normal_map(hmm, tile)
        m_new = (np.clip(m_new, 0, 1) * 255 + 0.5).astype(np.uint8)
        n_png = np.asarray(Image.open(os.path.join(d, f"T_Frigate_{name}_N.png")).convert("RGB"))
        m_png = np.asarray(Image.open(os.path.join(d, f"T_Frigate_{name}_M.png")).convert("RGB"))
        same = (n_png.shape == n_new.shape and m_png.shape == m_new.shape
                and int(np.abs(n_png.astype(int) - n_new).max()) <= 1
                and int(np.abs(m_png.astype(int) - m_new).max()) <= 1)
        h, w = m_png.shape[:2]
        mb = (w * h * 1.0 + w * h * 0.5) * 4.0 / 3.0 / 2 ** 20      # BC5 normal + BC1 mask, with mips
        total += mb
        size = JT.size_report(sizes)
        r = {"same_as_generator": bool(same), "px": [w, h], "px_per_mm": round(min(w / tile[0], h / tile[1]), 2),
             "tiling_N": JT.tiling(n_png), "tiling_M": JT.tiling(m_png),
             "repeat_N": JT.repeat_share(n_png), "repeat_M": JT.repeat_share(m_png), "size": size,
             "mb_high": round(mb, 3)}
        r["pass_"] = bool(same and max(r["tiling_N"], r["tiling_M"]) <= 1.0 and max(r["repeat_N"], r["repeat_M"]) < 0.2
                          and r["px_per_mm"] >= CARDS["closest_px_per_mm"] and all(v["pass"] for v in size.values()))
        res[name] = r
    medium = sum(res[n]["mb_high"] for n, c in CARDS["maps"]["own"].items() if c.get("medium"))
    budget = {"high_mb": round(total, 3), "cap_mb": CARDS["budget"]["high_mb"], "medium_mb": round(medium, 3),
              "medium_cap_mb": CARDS["budget"]["medium_mb"],
              "pass_": bool(total <= CARDS["budget"]["high_mb"] and medium <= CARDS["budget"]["medium_mb"])}
    return res, budget


def check_blind(key_path, pending_ok=False):
    """The blind ladder (the loop's method): three fresh reviewers each see every surface's five levels shuffled under
    the letters A to E (blind/<surface>.jpg) beside the card's five descriptions, and give each letter a level, each
    level once. The key is the sheets' own blind/key.json, never the reviews file. A reviewer passes a surface with
    all five right, or with one swap of two neighbouring levels (L1 for L2, say: three right); a surface passes when
    all of at least three reviewers do. Every surface in SHEETS must have been reviewed: one with no answers fails
    (or is 'pending' with --pending-blind, for the run that makes the sheets before the review)."""
    path = os.path.join(HERE, "reviews_1797.json")
    if not os.path.exists(path):
        return {"status": "pending: no reviews_1797.json", "pass": {s: pending_ok for s in SHEETS}}
    if not key_path or not os.path.exists(key_path):
        return {"status": "no blind/key.json given (--blind-key)", "pass": {s: False for s in SHEETS}}
    key = json.load(open(key_path))["key"]
    rv = json.load(open(path))
    rank = {lv: i for i, lv in enumerate(LEVELS)}
    out, why = {}, {}
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
            elif (len(wrong) == 2 and wrong[0] == wrong[1][::-1]
                  and abs(rank[wrong[0][0]] - rank[wrong[0][1]]) == 1):
                verdict = "one neighbouring swap"
            else:
                verdict = f"{5 - len(wrong)} right"
            out[s][who] = verdict
        why[s] = "reviewed by %d" % len(out[s])
    passed = {s: len(r) >= 3 and all(v in ("all five", "one neighbouring swap") for v in r.values())
              for s, r in out.items()}
    return {"status": "reviewed", "verdicts": out, "reviewers": why, "pass": passed}


# ------------------------------------------------------------------------------------------------ sheets
# each surface's ladder from the view that shows it best, cropped to where its materials are (the id render)
SHEETS = {"paint": ("gallery", ("HullBlack", "HullOchre", "FigurePaint")),
          "copper": ("waterline", ("Copper",)),
          "wood": ("quarterdeck", ("Oak", "Rail")),
          "deck": ("waist", ("DeckPlanks",)),
          "rope": ("chains", ("Tarred", "Hemp")),
          "canvas": ("sail", ("Sailcloth",)),
          "iron": ("carronade", ("Blacking", "Iron")),
          "bright": ("gallery", ("Gilt",))}
SHEET_PX = 360                      # each level's crop is scaled to this height


def crop_box(rdir, view, names, below=0.0):
    """The bounding box (left, top, right, bottom) of the materials' pixels in the view (those in the frame's lower
    1 - below of its height only, when below is given), padded and at least a third of the frame each way."""
    ids = {v: int(k) for k, v in json.load(open(os.path.join(rdir, "wear_ids.json"))).items()}
    code, sure = decode(os.path.join(rdir, f"wear_{view}_id.png"))
    mask = np.isin(code, [ids[n] for n in names if n in ids]) & sure
    h, w = mask.shape
    mask[:int(below * h)] = False
    if mask.sum() < 200:
        return 0, 0, w, h
    ys, xs = np.nonzero(mask)
    x0, x1 = np.percentile(xs, (2, 98))
    y0, y1 = np.percentile(ys, (2, 98))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw, bh = max(x1 - x0 + 0.08 * w, w / 3), max(y1 - y0 + 0.08 * h, h / 3)
    bw, bh = max(bw, bh * 0.75), max(bh, bw / 1.6)                 # neither a sliver nor a strip
    bw, bh = min(bw, w), min(bh, h)
    left, top = min(max(cx - bw / 2, 0), w - bw), min(max(cy - bh / 2, 0), h - bh)
    return int(left), int(top), int(left + bw), int(top + bh)


def make_sheets(rdir, out):
    """docs: one sheet a surface, L0 to L4 left to right, labelled; blind: the same crops shuffled under the letters
    A to E (a fixed shuffle per surface), with blind/key.json the level behind each letter."""
    from PIL import ImageDraw, ImageFont
    font_path = os.path.join(REPO, "Tools", "shipkit", "jclass", "fonts", "LibreBaskerville-Regular.ttf")
    font = ImageFont.truetype(font_path, 22) if os.path.exists(font_path) else ImageFont.load_default()
    os.makedirs(os.path.join(out, "blind"), exist_ok=True)
    rng = np.random.default_rng(11)
    key = {}
    for surface, (view, names, *below) in SHEETS.items():
        box = crop_box(rdir, view, names, *below)
        crops = {}
        for lv in LEVELS:
            im = Image.open(os.path.join(rdir, f"wear_{view}_{lv}.png")).convert("RGB").crop(box)
            crops[lv] = im.resize((round(im.width * SHEET_PX / im.height), SHEET_PX), Image.LANCZOS)
        order = list(LEVELS)
        while order == list(LEVELS):
            order = [LEVELS[i] for i in rng.permutation(5)]
        key[surface] = order
        for name, seq, labels in (("ladder_" + surface, list(LEVELS), list(LEVELS)),
                                  (os.path.join("blind", surface), order, list("ABCDE"))):
            cw = crops["L0"].width
            sheet = Image.new("RGB", (5 * cw + 4 * 8, SHEET_PX + 40), (24, 24, 24))
            d = ImageDraw.Draw(sheet)
            for i, (lv, lab) in enumerate(zip(seq, labels)):
                sheet.paste(crops[lv], (i * (cw + 8), 40))
                d.text((i * (cw + 8) + 8, 8), lab, fill=(235, 235, 235), font=font)
            sheet.save(os.path.join(out, name + ".jpg"), quality=88, optimize=True, progressive=False)
    json.dump({"key": key, "about": "the level shown under each letter A to E of blind/<surface>.jpg"},
              open(os.path.join(out, "blind", "key.json"), "w"), indent=1)
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--sheets", default=None, help="write the ladder and blind sheets to this folder")
    ap.add_argument("--blind-key", default=None, help="the sheets' blind/key.json (default: <sheets>/blind/key.json)")
    ap.add_argument("--pending-blind", action="store_true", help="no reviews yet: report the blind check as pending")
    a = ap.parse_args()
    if a.sheets:
        make_sheets(a.renders, a.sheets)
    key_path = a.blind_key or (os.path.join(a.sheets, "blind", "key.json") if a.sheets else None)
    meas, seen = measure(a.renders)
    kinds, mats = by_kind(meas)
    ladder = check_ladder(meas, mats)
    colour = check_colour(kinds, a.fetch)
    maps, budget = check_maps()
    blind = check_blind(key_path, a.pending_blind)
    fails = [f"ladder {k}" + (f" ({v['status']})" if "status" in v else "") for k, v in ladder.items()
             if not v["pass"]]
    fails += [f"colour {c.get('what', c['surface'] + '.' + c['for'])} ({c.get('d_ab', c.get('status'))})"
              for c in colour if c.get("pass_") is False]
    fails += [f"map {k}" for k, v in maps.items() if not v["pass_"]]
    fails += [] if budget["pass_"] else ["budget"]
    fails += [f"blind {s} ({blind['status']})" for s, ok in blind["pass"].items() if not ok]
    unseen = sorted(set(weathering.material_index()) - set(seen))
    rep = {"ladder": ladder, "colour": colour, "maps": maps, "budget": budget, "blind": blind,
           "ab": "none: this is her first wear round, so there is no earlier version to hold it against",
           "seen_in": seen, "not_in_any_view": unseen, "fails": fails}
    out = a.out or os.path.join(a.renders, "wear_check.json")
    json.dump(rep, open(out, "w"), indent=1)
    for k, v in ladder.items():
        if "status" in v:
            print(f"ladder {k:24s} {v['status']}  {'pass' if v['pass'] else 'FAIL'}")
            continue
        print(f"ladder {k:24s} from new {v['from_new']}  kept/neglected {v['kept_vs_neglected']}  "
              f"{'pass' if v['pass'] else 'FAIL'}")
    for c in colour:
        if "d_ab" in c:
            print(f"colour {c['what']:34s} d_ab {c['d_ab']:5.1f} d_L {c['d_L']:6.1f} ({', '.join(c['refs'])})  "
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
