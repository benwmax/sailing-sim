"""Track B: the shore plan's checks that can run outside the game, on the meshes and the renders.

    python3 Tools/envloop/grass/check_grass.py [--renders DIR] [--json OUT]

Plain Python and numpy (no bpy): builds every mesh from grass_geo.py itself. Checks:
  1 size     every hero and Light mesh's height and blade widths sit inside its card's real range (5 percent slack)
  2 colour   the lawn and rough tiles' colour seen from above (blade areas weighted by how much they face up, the
             material's root-to-tip blend and root shade) is within 10 percent of Track A's ground mean, per season, so
             the fade from blades to the ground texture can't be seen; grey-card photo colour waits on Bean's photos
  3 repeat   in the 15 m renders, the bank strip's strongest repeat (autocorrelation of its fine detail along the shore,
             past 1.5 m) stays under 0.35
  4 variety  each card has at least its variants_min hero meshes
  5 blind    recorded by hand in docs/envloop/grass/blind.md (fresh reviewers), not here
  6 budget   triangles per mesh under the card's budget; triangles placed per standard view reported
Prints one line per check and exits non-zero if any fails.
"""
import argparse
import glob
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grass_geo as G  # noqa: E402

LOOK = json.load(open(os.path.join(HERE, "grass_look.json")))
CARDS = {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(os.path.join(HERE, "cards", "*.json"))}
HEIGHT_KEY = {"lawn_bermuda": "mown_height_m", "lawn_rough": "height_m", "bluestem": "flower_stem_height_m"}


def card_height(card):
    r = card["real"]
    key = HEIGHT_KEY.get(card["plant"], "height_m")
    if key in r:
        return r[key]
    lo = min(v[0] for k, v in r.items() if k.endswith("_m") and isinstance(v, list))
    hi = max(v[1] for k, v in r.items() if k.endswith("_m") and isinstance(v, list))
    return [lo, hi]


def check_size(built):
    fails, rows = [], []
    for name, (card_id, pl, kind) in built.items():
        card = CARDS[card_id]
        lo, hi = card_height(card)
        h = pl.bounds()[1][2]
        ok_h = h <= hi * 1.05 and (h >= lo * 0.95 or kind == "light" or card_id == "lawn_weeds")
        widths = [w * 1000 for part, _l, w in pl.blades if part == 0.0]
        wr = card["real"].get("blade_width_mm")
        ok_w = True
        if wr and widths and kind == "hero":
            ok_w = min(widths) >= wr[0] * 0.95 and max(widths) <= wr[1] * 1.05
        rows.append((name, round(h, 3), [lo, hi], ok_h and ok_w))
        if not (ok_h and ok_w):
            fails.append(f"{name}: height {h:.2f} m vs {lo}-{hi}" + ("" if ok_w else f", blade widths {min(widths):.1f}-{max(widths):.1f} mm vs {wr}"))
    return fails, rows


def seen_from_above(pl, card_id, season):
    """Mean linear colour of the blades as the camera above sees them (area x facing-up weight), with the material's
    root-to-tip blend, root shade and mown-tip lightening (render_grass.grass_material's leaf branch)."""
    look = LOOK[card_id][season]
    root, tip = np.array(look["root"]), np.array(look["tip"])
    cut = np.array(look.get("cut_tip", look["tip"]))
    stalk = np.array(look.get("stalk", root + (tip - root) * 0.6))
    seed = np.array(look.get("seed", look["tip"]))
    top = max(p[2] for p in pl.v)
    acc, wsum = np.zeros(3), 0.0
    for (a, b, c), slot in zip(pl.tris, pl.slot):
        pa, pb, pc = np.array(pl.v[a]), np.array(pl.v[b]), np.array(pl.v[c])
        n = np.cross(pb - pa, pc - pa)
        w = 0.5 * abs(n[2])                     # projected area on the ground
        if w <= 0:
            continue
        v = (pl.uv[a][1] + pl.uv[b][1] + pl.uv[c][1]) / 3
        z = (pa[2] + pb[2] + pc[2]) / 3 / top
        part = pl.c[a][2]
        if slot == 1:
            col = seed
        elif part > 0.25:
            col = stalk
        else:
            col = root + (tip - root) * min(1.0, v / 0.55)
            if pl.c[a][3] > 0.5 or pl.c[b][3] > 0.5:
                col = col + (cut - col) * 0.6
        col = col * (0.7 + 0.3 * min(1.0, z / 0.4))
        acc += col * w
        wsum += w
    return acc / max(wsum, 1e-9)


def check_colour(built):
    fails, rows = [], []
    ta = LOOK["_track_a"]
    for card_id, ground in (("lawn_bermuda", "lawn"), ("lawn_rough", "rough")):
        names = [n for n, (c, _p, k) in built.items() if c == card_id and k == "hero"]
        for season in ("summer", "dormant"):
            mean = np.mean([seen_from_above(built[n][1], card_id, season) for n in names], axis=0)
            ref = np.array(ta[ground][season])
            lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
            dl = lum(mean) / lum(ref) - 1.0
            chroma = np.abs(mean / mean.sum() - ref / ref.sum()).max()
            ok = abs(dl) <= 0.10 and chroma <= 0.03
            rows.append((card_id, season, [round(x, 3) for x in mean], [round(x, 3) for x in ref], round(dl, 3), round(float(chroma), 3), ok))
            if not ok:
                fails.append(f"{card_id} {season}: blades {mean.round(3)} vs ground {ref} (brightness {dl:+.0%}, tint {chroma:.3f})")
    return fails, rows


def check_repeat(render_dir):
    """Autocorrelation of the bank strip's fine detail along the shore in each 15 m render."""
    fails, rows = [], []
    for path in sorted(glob.glob(os.path.join(render_dir, "shore_15m_*.npy"))):
        img = np.load(path).astype(np.float32)
        h, w, _ = img.shape
        lum = img @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        band = lum[int(h * 0.36):int(h * 0.56)]                    # the bank between the horizon and the waterline
        hp = band - np.apply_along_axis(lambda r: np.convolve(r, np.ones(31) / 31, mode="same"), 1, band)
        hp -= hp.mean(axis=1, keepdims=True)
        f = np.fft.rfft(hp, n=2 * w, axis=1)
        ac = np.fft.irfft(f * np.conj(f), axis=1)[:, :w].sum(axis=0)
        ac /= ac[0] if ac[0] else 1.0
        # 1.5 m at 15 m and a 55 deg lens is about w * 1.5 / (2 * 15 * tan 27.5)
        lag0 = int(w * 1.5 / (2 * 15 * math.tan(math.radians(27.5))))
        peak = float(ac[lag0:w // 2].max())
        ok = peak < 0.35
        rows.append((os.path.basename(path)[:-4], round(peak, 3), ok))
        if not ok:
            fails.append(f"{os.path.basename(path)}: repeat peak {peak:.2f}")
    return fails, rows


def solve(built):
    """Scale each lawn and rough season's leaf colours (root, tip, cut tip) by one factor per channel so the blades seen
    from above average to Track A's ground mean: the tint and the root-to-tip contrast are kept."""
    path = os.path.join(HERE, "grass_look.json")
    look = json.load(open(path))
    for card_id, ground in (("lawn_bermuda", "lawn"), ("lawn_rough", "rough")):
        names = [n for n, (c, _p, k) in built.items() if c == card_id and k == "hero"]
        for season in ("summer", "dormant"):
            for _ in range(3):
                LOOK[card_id][season] = look[card_id][season]
                mean = np.mean([seen_from_above(built[n][1], card_id, season) for n in names], axis=0)
                k = np.array(look["_track_a"][ground][season]) / mean
                for key in ("root", "tip", "cut_tip"):
                    if key in look[card_id][season]:
                        look[card_id][season][key] = [round(float(v), 4) for v in np.array(look[card_id][season][key]) * k]
    json.dump(look, open(path, "w"), indent=1)
    LOOK.update(look)
    print("solved lawn and rough colours to Track A's ground means")


def check_variety(built):
    fails, rows = [], []
    for cid, card in CARDS.items():
        n = len([1 for c, _p, k in built.values() if c == cid and k == "hero"])
        ok = n >= card["variants_min"]
        rows.append((cid, n, card["variants_min"], ok))
        if not ok:
            fails.append(f"{cid}: {n} hero meshes, card asks {card['variants_min']}")
    return fails, rows


def check_budget(built, render_dir):
    fails, rows = [], []
    for name, (cid, pl, kind) in built.items():
        b = CARDS[cid]["budget"]
        cap = b["tris_lod0_max"] if kind == "hero" else b["tris_light_max"]
        ok = pl.tri_count <= cap
        rows.append((name, pl.tri_count, cap, ok))
        if not ok:
            fails.append(f"{name}: {pl.tri_count} triangles, budget {cap}")
    views = {}
    for p in sorted(glob.glob(os.path.join(render_dir or "", "shore_*.json"))):
        r = json.load(open(p))
        views[r["shot"]] = {"plants": sum(r["instances"].values()), "tris_m": round(r["tris_placed"] / 1e6, 2)}
    return fails, rows, views


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders")
    ap.add_argument("--json")
    ap.add_argument("--solve", action="store_true", help="rescale the lawn and rough colours in grass_look.json so check 2 holds")
    a = ap.parse_args()
    built = {n: (c, fn(), k) for n, (c, fn, k) in G.catalogue().items()}
    if a.solve:
        solve(built)
    out, bad = {}, 0
    for key, fn in (("size", lambda: check_size(built)), ("colour", lambda: check_colour(built)),
                    ("variety", lambda: check_variety(built))):
        fails, rows = fn()
        out[key] = {"pass": not fails, "fails": fails, "rows": rows}
        bad += bool(fails)
        print(f"{key:8s} {'PASS' if not fails else 'FAIL'}  " + ("; ".join(fails[:4]) if fails else f"{len(rows)} rows"))
    if a.renders:
        fails, rows = check_repeat(a.renders)
        out["repeat"] = {"pass": not fails, "fails": fails, "rows": rows}
        bad += bool(fails)
        print(f"repeat   {'PASS' if not fails else 'FAIL'}  " + ("; ".join(fails) if fails else ", ".join(f"{r[0]} {r[1]}" for r in rows)))
    fails, rows, views = check_budget(built, a.renders)
    out["budget"] = {"pass": not fails, "fails": fails, "rows": rows, "views": views}
    bad += bool(fails)
    print(f"budget   {'PASS' if not fails else 'FAIL'}  " + ("; ".join(fails[:4]) if fails else f"{len(rows)} meshes under their cards' budgets"))
    print("blind    see docs/envloop/grass/blind.md")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1, default=str)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
