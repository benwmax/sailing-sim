"""The six checks for one environment asset (docs/env-loop/README.md, step 6), in one score file.

    python3 Tools/envloop/score.py <card.json> [--colour <render.png> <box> <photo.jpg> <box> <neutral box>]
                                               [--repeat <render or texture.png> [<tile_m>]] [--bands <name>_bands.json]

  1 sizes    the card's measured values against the shared size card (check_card.py), 5 percent or inside the range
  2 colour   the render's Lab a*, b* against the reference photo's, white-balanced on its grey card (Tools/texloop/measure.py):
             dE(a*b*) 6 or less. Pending until a grey-card photo exists.
  3 repeat   no repeat in a 40 m frame (repeat_check.py): peak under 0.35
  4 variety  the card's variety counts summed over its track's cards against tracks.json's targets (a track-level check:
             pending until --milestone)
  5 blind    reviews/<asset>.json: the last A/B round kept (new beat old 2 of 3) and, at 15 m, a photo-or-game round kept
  6 budget   triangles and texture memory against the card's own budget and the track's (frame time is the Mac/PC's)
Writes Tools/envloop/scores/<asset>.json and prints one line a check. Pending checks are not failures; failures exit 1.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
import check_card  # noqa: E402
import repeat_check  # noqa: E402
import texel  # noqa: E402


def box(s):
    return [float(v) for v in s.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card")
    ap.add_argument("--colour", nargs=5)
    ap.add_argument("--repeat", nargs="+")
    ap.add_argument("--bands")
    ap.add_argument("--milestone", action="store_true", help="judge the track's variety (at a track milestone)")
    a = ap.parse_args()
    card = json.load(open(a.card))
    sc = json.load(open(os.path.join(HERE, "size_card.json")))
    tracks = json.load(open(os.path.join(HERE, "tracks.json")))["tracks"]
    stations = {s["id"] for s in json.load(open(os.path.join(HERE, "stations.json")))["stations"]}
    res = {}
    probs = check_card.check(a.card, sc["sizes"], sc["tolerance_pct"], stations, set(tracks))
    res["sizes"] = dict(ok=None if not card.get("measured") else not any(p.startswith("size") for p in probs),
                        card_problems=probs)
    if a.colour:
        import measure  # Tools/texloop/measure.py
        r = measure.measure(measure.load(a.colour[0]), box(a.colour[1]))
        p = measure.measure(measure.load(a.colour[2]), box(a.colour[3]), box(a.colour[4]))
        d = float(np.hypot(r["a"] - p["a"], r["b"] - p["b"]))
        res["colour"] = dict(ok=d <= 6.0, dE_ab=round(d, 2), render=r, photo=p)
    else:
        res["colour"] = dict(ok=None, note="no grey-card photo yet")
    if a.repeat:
        if len(a.repeat) > 1:
            img = repeat_check.lay(repeat_check.grey(a.repeat[0]), float(a.repeat[1]))
        else:
            img = repeat_check.grey(a.repeat[0])
        from PIL import Image
        img = np.asarray(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((400, 400), Image.BILINEAR), float)
        pk = repeat_check.repeat_peak(img)
        res["repeat"] = dict(ok=pk < repeat_check.PASS, repeat_peak=round(pk, 3))
    else:
        res["repeat"] = dict(ok=None, note="not run")
    tr = tracks.get(card["track"], {})
    want = tr.get("variety", {})
    have = {}
    for p in glob.glob(os.path.join(HERE, tr.get("cards", "cards/none"), "*.json")):
        for k, v in json.load(open(p)).get("variety", {}).items():
            have[k] = have.get(k, 0) + v
    met = all(have.get(k, 0) >= v for k, v in want.items() if isinstance(v, int)) if want else None
    res["variety"] = dict(ok=met if a.milestone else (True if met else None), have=have, want=want,
                          note=None if a.milestone else "track-level: judged with --milestone")
    rv_path = os.path.join(HERE, "reviews", card["id"] + ".json")
    if os.path.exists(rv_path):
        rounds = json.load(open(rv_path))["rounds"]
        ab = [r for r in rounds if r["kind"] == "ab"]
        ph = [r for r in rounds if r["kind"] == "photo"]
        res["blind"] = dict(ok=bool(ab and ab[-1]["kept"]) and (bool(ph and ph[-1]["kept"]) if ph else True),
                            ab=ab[-1] if ab else None, photo=ph[-1] if ph else None,
                            note=None if ph else "photo-or-game round still to run")
    else:
        res["blind"] = dict(ok=None, note="no reviews yet")
    bud = dict(ok=True, items=[])
    if a.bands:
        b = json.load(open(a.bands))
        lim = (card.get("triangles") or {}).get("hero")
        if lim:
            ok = b["triangles"] <= lim
            bud["ok"] &= ok
            bud["items"].append("triangles %d of %d" % (b["triangles"], lim))
    mb = sum(texel.megabytes(t["px"]) for t in card.get("textures", []))
    bud["items"].append("textures %.1f MB at full size (Ultra), %.1f High, %.1f Medium" % (mb, mb / 4, mb / 16))
    res["budget"] = bud
    os.makedirs(os.path.join(HERE, "scores"), exist_ok=True)
    json.dump(dict(asset=card["id"], **res), open(os.path.join(HERE, "scores", card["id"] + ".json"), "w"), indent=1, default=str)
    fail = False
    for k, v in res.items():
        print("%-8s %s  %s" % (k, {True: "pass", False: "FAIL", None: "pending"}[v["ok"]], {kk: vv for kk, vv in v.items() if kk not in ("ok", "render", "photo")}))
        fail |= v["ok"] is False
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
