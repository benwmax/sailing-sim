"""Realism rules for the wildlife tables (docs/wildlife-0/README.md). python3 Tools/wildlife/test_wildlife.py

Checks the catalogue (Tools/wildlife/species.json) and the built tables (Content/TerrainData/<World>.wildlife.json):
nothing from the sea on Ray Hubbard, no whales anywhere in Texas, Marseille's deep-water rarities left out, every
animal only in its months, sharks rare and salt-water only, no eBird records anywhere, only CC0 / CC BY 4.0 records.
When the GBIF cache (Data/Wildlife/raw/cache) is here, it also rebuilds the tables and checks they match.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_tables  # noqa: E402
import fetch_gbif  # noqa: E402
import gbif  # noqa: E402

FAILS = []
SEA_KINDS = {"dolphin", "whale", "shark", "ray"}
DEEP_WATER_TAXA = {"Globicephala melas", "Grampus griseus", "Physeter macrocephalus"}


def ok(cond, what):
    print(("pass  " if cond else "FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def tables(cat):
    out = {}
    for w in cat["worlds"]:
        p = build_tables.out_path(w)
        if os.path.exists(p):
            with open(p) as f:
                out[w] = json.load(f)
    return out


def test_catalogue(cat):
    sp = cat["species"]
    used = set()
    for w in cat["worlds"]:
        for e in gbif.cast_for(cat, w):
            used.add(e["id"])
            ok(e["id"] in sp, "%s: %s is in the catalogue" % (w, e["id"]))
            ok(len(build_tables.months_of(e["months"])) > 0, "%s %s: a season" % (w, e["id"]))
            ok(not (build_tables.months_of(e["months"]) & build_tables.months_of(e.get("rare_months"))),
               "%s %s: rare months are outside the season" % (w, e["id"]))
            r = e["group"]["range"]
            ok(1 <= r[0] <= r[1], "%s %s: group range %s" % (w, e["id"], r))
    ok(used == set(sp), "every catalogue animal is cast somewhere (unused: %s)" % sorted(set(sp) - used))
    for k, s in sp.items():
        ok(s["style"] in cat["styles"], "%s: style %s is defined" % (k, s["style"]))
        ok(s["water"] in ("fresh", "salt", "any"), "%s: water %s" % (k, s["water"]))
        ok(s["size_m"] > 0, "%s: a size" % k)
    ok(set(cat["licences"]) <= {"CC0_1_0", "CC_BY_4_0"}, "only CC0 and CC BY 4.0 records are queried")
    ok("license=CC_BY_NC_4_0" not in gbif.facet_url(cat, [0, 0, 1, 1], [1], True), "no non-commercial licence in queries")
    ok("PRESERVED_SPECIMEN" not in gbif.facet_url(cat, [0, 0, 1, 1], [1], True), "sightings exclude museum specimens")
    ok(all(gbif.observed(cat, k) for k in ("bird", "dolphin", "whale")), "birds, dolphins and whales count sightings only")
    ok(cat["ebird_dataset"] == "4fa7b334-ce0d-4e88-aaae-2e0c138d049e", "eBird's GBIF dataset key")
    ok("6ff8b3b0-ef0f-4f79-a310-5a5615c6aa0b" in gbif.other_left_out(cat),
       "Birda left out (its records say CC BY 4.0, the dataset CC BY-NC 4.0)")


def test_realism(cat):
    sp = cat["species"]
    for w, info in cat["worlds"].items():
        cast = [sp[e["id"]] | {"id": e["id"]} for e in gbif.cast_for(cat, w)]
        if info["water"] == "fresh":
            sea = [s["id"] for s in cast if s["water"] == "salt" or s["kind"] in SEA_KINDS]
            ok(not sea, "%s (fresh): nothing from the sea (%s)" % (w, sea))
        else:
            fresh = [s["id"] for s in cast if s["water"] == "fresh"]
            ok(not fresh, "%s (salt): no freshwater-only animals (%s)" % (w, fresh))
        if w in cat["texas_worlds"]:
            whales = [s["id"] for s in cast if s["kind"] == "whale"]
            ok(not whales, "%s: no whales in Texas (%s)" % (w, whales))
        sharks = [e for e in gbif.cast_for(cat, w) if sp[e["id"]]["kind"] == "shark"]
        ok(all(e.get("rare") for e in sharks), "%s: sharks are marked rare" % w)
        if w == "Marseille":
            left = set(cat["left_out"]["Marseille"])
            ok(not (left & {e["id"] for e in gbif.cast_for(cat, w)}), "Marseille: deep-water rarities left out")
            taxa = {t for s in cast for t in s["taxa"]}
            ok(not (taxa & DEEP_WATER_TAXA), "Marseille: no pilot whale, Risso's dolphin or sperm whale taxa")
            whales = [e for e in gbif.cast_for(cat, w) if sp[e["id"]]["kind"] == "whale"]
            ok(all(e.get("rare") and "far_offshore" in e["habitats"] for e in whales),
               "Marseille: whales are rare and far offshore")
    ok(gbif.cast_for(cat, "TexasCoast") == gbif.cast_for(cat, "GalvestonBay"),
       "the Texas coast world has the Galveston Bay and Gulf passage cast")


def test_tables(cat, tabs):
    eb = cat["ebird_dataset"]
    ok(set(tabs) == set(cat["worlds"]), "a table for every world (%s)" % sorted(tabs))
    for w, t in tabs.items():
        cast = gbif.cast_for(cat, w)
        ok([r["id"] for r in t["species"]] == [e["id"] for e in cast], "%s: table rows follow the cast" % w)
        ok(all(c["gbif"] != eb for c in t["credits"]), "%s: eBird is not among the credited datasets" % w)
        out = set(gbif.other_left_out(cat))
        ok(not (out & {c["gbif"] for c in t["credits"]}), "%s: no dataset with an unclear licence is credited" % w)
        per_record = set(cat.get("per_record_licences", {}))
        odd = [c["dataset"] for c in t["credits"] if c.get("licence") not in ("CC0 1.0", "CC BY 4.0")
               and c["gbif"] not in per_record]
        ok(not odd, "%s: every credited dataset is CC0 or CC BY, or licenses each record (%s)" % (w, odd))
        ok(all(c.get("dataset") for c in t["credits"]), "%s: every credited dataset has a title" % w)
        for r, e in zip(t["species"], cast):
            season = build_tables.months_of(e["months"])
            rare = build_tables.months_of(e.get("rare_months"))
            m = r["months"]
            ok(len(m) == 12, "%s %s: 12 months" % (w, r["id"]))
            outside = [i + 1 for i in range(12) if m[i] > 0 and (i + 1) not in season | rare]
            ok(not outside, "%s %s: only in its months (seen in %s)" % (w, r["id"], outside))
            ok(all(m[i - 1] >= build_tables.FLOOR - 1e-9 for i in season), "%s %s: every season month counts" % (w, r["id"]))
            ok(all(0 < m[i - 1] <= build_tables.RARE + 1e-9 for i in rare), "%s %s: rare months are a trickle" % (w, r["id"]))
            g = r["group"]
            ok(1 <= g["typical"] <= g["p90"], "%s %s: group %s <= %s" % (w, r["id"], g["typical"], g["p90"]))
            if r["records"] >= 100 and r["in_season_share"] is not None:
                ok(r["in_season_share"] >= 0.6, "%s %s: %.0f%% of %d records fall in its season" % (
                    w, r["id"], 100 * r["in_season_share"], r["records"]))


def test_cache(cat):
    """With the cache here: no eBird record in any page, and the committed tables are what the cache builds."""
    if not os.path.isdir(gbif.CACHE) or not os.listdir(gbif.CACHE):
        print("skip  no GBIF cache (Data/Wildlife/raw/cache): run fetch_gbif.py to check the tables against it")
        return
    eb = cat["ebird_dataset"]
    pages = bad = 0
    for name in os.listdir(gbif.CACHE):
        with open(os.path.join(gbif.CACHE, name)) as f:
            d = json.load(f)
        if "/occurrence/search?" in d["url"] and "limit=0" not in d["url"]:
            pages += 1
            bad += (eb in d["url"]) + (eb in d["body"]["ds"])
    ok(bad == 0, "no eBird record in %d cached pages" % pages)
    fx = gbif.Fetcher(offline=True)
    keys, done = fetch_gbif.resolve_names(cat, fx)
    if not done:
        print("skip  cache has no names yet")
        return
    for w in cat["worlds"]:
        try:
            t = build_tables.build_world(cat, w, keys, fx)
        except build_tables.Incomplete:
            print("skip  %s: cache incomplete" % w)
            continue
        p = build_tables.out_path(w)
        same = os.path.exists(p) and open(p).read() == build_tables.dumps(t)
        ok(same, "%s: committed table matches the cache (rebuild with build_tables.py)" % w)


def main():
    cat = gbif.load_catalogue()
    test_catalogue(cat)
    test_realism(cat)
    test_tables(cat, tables(cat))
    test_cache(cat)
    print("\n%d failed" % len(FAILS) if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
