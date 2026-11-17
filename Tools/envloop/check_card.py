"""Check an environment asset card (docs/env-loop/README.md): the card's fields, its sizes against the shared size card
(within size_card.json tolerance_pct, or inside the row's range), its textures against the sharpness rule, its stations
against stations.json, its region packs (packs/<id>), its references' licences, and its variety against its track's target.

    python3 Tools/envloop/check_card.py Tools/envloop/cards/<track>/<asset>.json [...]
    python3 Tools/envloop/check_card.py --all        # every card under Tools/envloop/cards (not _template.json)

Exit 1 on any failure. A card without "measured" values passes the size check as pending (a card comes before the build).
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import texel  # noqa: E402

REQUIRED = ("id", "track", "name", "what", "where", "bands", "closest_camera_m", "size_card", "references", "stations", "licence", "status")
SHIP_OK = ("CC0", "Public domain", "PD", "Own photo", "Fab Standard", "made here")
MEASURE_OK = SHIP_OK + ("CC BY", "CC BY-SA", "FAL")
STATUSES = ("card", "refs", "built", "rendered", "scored", "in-game", "done")


def _close(got, want, rng, tol):
    if isinstance(want, dict):
        return all(_close(got.get(k), v, (rng or {}).get(k), tol) for k, v in want.items() if k in got)
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return False
        return all(_close(g, w, None, tol) for g, w in zip(got, want))
    if got is None:
        return False
    if rng and isinstance(rng, list) and rng[0] <= got <= rng[1]:
        return True
    return abs(got - want) <= abs(want) * tol / 100.0


def check(path, card_sizes, tol, stations, tracks):
    c = json.load(open(path))
    out = []
    for k in REQUIRED:
        if k not in c:
            out.append("missing field %s" % k)
    if c.get("track") not in tracks:
        out.append("unknown track %r" % c.get("track"))
    if c.get("status") not in STATUSES:
        out.append("status must be one of %s" % ", ".join(STATUSES))
    for k in c.get("size_card", []):
        if k not in card_sizes:
            out.append("size_card row %r is not in size_card.json (add it there with a source first)" % k)
    for k, v in (c.get("measured") or {}).items():
        row = card_sizes.get(k)
        if row is None:
            out.append("measured %r has no size_card row" % k)
        elif not _close(v, row["value"], row.get("range"), tol):
            out.append("size %s: %s against the card's %s (range %s, %d%%)" % (k, v, row["value"], row.get("range"), tol))
    for t in c.get("textures", []):
        r = texel.check(t["px"], t["tile_m"], t.get("band", "hero"))
        if not r["ok"]:
            out.append("texture %s: %.0f px/m, the %s band wants %d" % (t["name"], r["px_per_m"], r["band"], r["want_px_per_m"]))
    for pk in c.get("packs", []):
        if not os.path.exists(os.path.join(HERE, "packs", pk, "pack.json")):
            out.append("unknown region pack %r (packs/<id>/pack.json)" % pk)
    for s in c.get("stations", []):
        if s not in stations:
            out.append("unknown station %r" % s)
    for r in c.get("references", []):
        lic, use = r.get("licence", ""), r.get("use", "measure")
        ok = SHIP_OK if use == "ship" else MEASURE_OK
        if not any(lic.startswith(x) for x in ok) or "NC" in lic or "ND" in lic:
            out.append("reference %s: licence %r not allowed for use %r" % (r.get("id"), lic, use))
    lic = c.get("licence", {})
    if lic and not lic.get("commercial", False):
        out.append("asset licence is not commercial-OK")
    return out


def main():
    paths = sys.argv[1:]
    if paths == ["--all"] or not paths:
        paths = [p for p in glob.glob(os.path.join(HERE, "cards", "**", "*.json"), recursive=True) if not os.path.basename(p).startswith("_")]
    sc = json.load(open(os.path.join(HERE, "size_card.json")))
    st = {s["id"] for s in json.load(open(os.path.join(HERE, "stations.json")))["stations"]}
    tr = set(json.load(open(os.path.join(HERE, "tracks.json")))["tracks"])
    bad = 0
    for p in paths:
        probs = check(p, sc["sizes"], sc["tolerance_pct"], st, tr)
        bad += bool(probs)
        print("%s: %s" % (os.path.relpath(p, HERE), "ok" if not probs else "\n  " + "\n  ".join(probs)))
    print("%d card(s), %d failing" % (len(paths), bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
