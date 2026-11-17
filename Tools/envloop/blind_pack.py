"""Blind review packs for the environment loop (docs/env-loop/README.md, check 5).

    python3 Tools/envloop/blind_pack.py ab <old.png> <new.png> --out DIR --pair <name> [--seed n]
    python3 Tools/envloop/blind_pack.py photo <game.png> <photo.jpg> --out DIR --pair <name> [--seed n]
    python3 Tools/envloop/blind_pack.py record DIR <asset> <reviewer answers json>

`ab` (new beats old) and `photo` (photo or game, at 15 m) crop both pictures to the same 4:3, strip metadata and save
them as A.jpg and B.jpg in DIR/<pair>/ with the sides shuffled; the key goes in DIR/<pair>/key.json (do not show it to a
reviewer). Give each of three fresh reviewers only the two pictures and the question in DIR/<pair>/question.txt, and tell
them the sides are shuffled and "can't tell" is allowed (reviewers lean to the right-hand picture: docs/shore-loop).
`record` turns the answers (a list of {"reviewer": .., "pick": "A"|"B"|"none", "why": ..}) into
Tools/envloop/reviews/<asset>.json rounds, the format score.py reads: a round is kept when new wins 2 of 3 (A/B), or when
at least 1 of 3 calls the game picture the photo or can't tell (photo or game).
"""
import argparse
import json
import os
import random

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = {
    "ab": "Two pictures of the same place on a lake shore, seen from a boat. Which looks more like a real photograph of "
          "a real place? Look at the ground, the grass, the walls and the water's edge. Answer A, B or can't tell, and say why "
          "in one sentence. The sides are shuffled.",
    "photo": "One of these two pictures is a photograph and one is from a video game. Which is the photograph? Answer A, B "
             "or can't tell, and say why in one sentence. The sides are shuffled.",
}


def fit(path, w=1200, h=900):
    im = Image.open(path).convert("RGB")
    iw, ih = im.size
    if iw / ih > w / h:
        nw = int(ih * w / h)
        im = im.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw * h / w)
        im = im.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    return im.resize((w, h), Image.LANCZOS)


def pack(kind, first, second, out, pair, seed):
    d = os.path.join(out, pair)
    os.makedirs(d, exist_ok=True)
    rng = random.Random(seed if seed is not None else hash(pair) & 0xFFFF)
    names = ("old", "new") if kind == "ab" else ("game", "photo")
    items = [(names[0], first), (names[1], second)]
    rng.shuffle(items)
    key = {}
    for side, (label, path) in zip("AB", items):
        fit(path).save(os.path.join(d, side + ".jpg"), quality=90)
        key[side] = dict(label=label, source=os.path.basename(path))
    json.dump(dict(kind=kind, key=key), open(os.path.join(d, "key.json"), "w"), indent=1)
    open(os.path.join(d, "question.txt"), "w").write(QUESTIONS[kind] + "\n")
    print(d)


def record(d, asset, answers_path):
    key = json.load(open(os.path.join(d, "key.json")))
    ans = json.load(open(answers_path))
    labels = {s: v["label"] for s, v in key["key"].items()}
    picks = [labels.get(a["pick"], "none") for a in ans]
    if key["kind"] == "ab":
        wins = sum(p == "new" for p in picks)
        kept = wins >= 2
        row = dict(kind="ab", new_wins=wins, of=len(picks), kept=kept)
    else:
        fooled = sum(p in ("game", "none") for p in picks)
        row = dict(kind="photo", fooled_or_unsure=fooled, of=len(picks), kept=fooled >= 1)
    row.update(pair=os.path.basename(d.rstrip("/")), answers=ans)
    path = os.path.join(HERE, "reviews", asset + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rv = json.load(open(path)) if os.path.exists(path) else dict(asset=asset, rounds=[])
    row["round"] = len(rv["rounds"]) + 1
    rv["rounds"].append(row)
    json.dump(rv, open(path, "w"), indent=1)
    print(json.dumps({k: v for k, v in row.items() if k != "answers"}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["ab", "photo", "record"])
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("c", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--pair")
    ap.add_argument("--seed", type=int)
    x = ap.parse_args()
    if x.mode == "record":
        record(x.a, x.b, x.c)
    else:
        pack(x.mode, x.a, x.b, x.out, x.pair, x.seed)
