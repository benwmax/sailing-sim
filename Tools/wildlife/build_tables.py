"""Build Content/TerrainData/<World>.wildlife.json from the cached GBIF records (docs/wildlife-0/README.md).

    python3 Tools/wildlife/build_tables.py           # all worlds; needs fetch_gbif.py's cache complete
    python3 Tools/wildlife/build_tables.py --check   # build in memory and compare with the committed tables

Per cast entry: monthly weights (0 outside the curated season, a trickle in rare_months), from non-eBird records
divided by all non-eBird bird records that month (birdwatching effort varies a lot by month); group sizes (the median
count and the 9-in-10 count) when the records hold MIN_COUNTS counts, else the catalogue's rough range; record places
on a coarse grid for dolphins and sharks; and the datasets to credit. eBird is subtracted from every count and never
paged (Bean, Nov 24 2026: its terms need Cornell's written OK for commercial use); so are the datasets in species.json's
left_out_datasets (unclear licences), whose rows in the record pages are dropped here.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_gbif  # noqa: E402
import gbif  # noqa: E402

MIN_RECORDS = 50    # fewer non-eBird records than this: flat weights inside the season
FULL_RECORDS = 300  # from MIN_RECORDS up to this, the records' shape is blended with flat (a June bioblitz is not a season)
MIN_COUNTS = 30     # fewer counted groups than this: the catalogue's rough group range
FLOOR = 0.15        # least weight of an in-season month (thin months are under-recorded, not empty)
RARE = 0.1          # most weight of a rare month
CELL_DEG = 0.02     # density grid, about 2 km


class Incomplete(Exception):
    pass


def months_of(spec):
    out = set()
    for part in str(spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            m = a
            while True:
                out.add(m)
                if m == b:
                    break
                m = m % 12 + 1
        else:
            out.add(int(part))
    return out


def need(body, url):
    if body is None:
        raise Incomplete(url)
    return body


def month_vector(body):
    c = fetch_gbif.facet_counts(body, "MONTH")
    return [int(c.get(str(m), 0)) for m in range(1, 13)]


def pct(sorted_vals, q):
    """Nearest-rank percentile of an ascending list."""
    i = max(0, min(len(sorted_vals) - 1, int(round(q * len(sorted_vals) + 0.5)) - 1))
    return sorted_vals[i]


def weights(entry, rate, total):
    season, rare = months_of(entry["months"]), months_of(entry.get("rare_months"))
    peak = months_of(entry.get("peak"))
    w = [0.0] * 12
    data = total >= MIN_RECORDS
    top = max([rate[m - 1] for m in season] + [0])
    f = min(1.0, total / FULL_RECORDS)
    for m in range(1, 13):
        if m in season:
            if data and top > 0:
                w[m - 1] = max(FLOOR, f * rate[m - 1] / top + (1.0 - f))
            else:
                w[m - 1] = 1.0 if (not peak or m in peak) else 0.6
        elif m in rare:
            w[m - 1] = min(RARE, rate[m - 1] / top) if (data and top > 0) else 0.05
            w[m - 1] = max(w[m - 1], 0.02)
    return [round(x, 3) for x in w], ("records" if data else "season")


def other_left_out(cat, box, tk, seen, allb, fx, always=False):
    """Month vector and count of the records in the datasets left out besides eBird (zero when they hold none)."""
    u = fetch_gbif.other_left_out_url(cat, box, tk, seen, allb, always)
    if not u:
        return [0] * 12, 0
    b = need(fx.get(u), u)
    return month_vector(b), int(b["count"])


def licence_name(url):
    u = (url or "").lower()
    for k, v in (("publicdomain/zero", "CC0 1.0"), ("by-nc", "CC BY-NC 4.0"), ("licenses/by/", "CC BY 4.0")):
        if k in u:
            return v
    return url or "unknown"


def build_world(cat, world, keys, fx):
    box = gbif.world_box(cat, world)
    eb = cat["ebird_dataset"]
    out_keys = gbif.left_out(cat)
    u = gbif.facet_url(cat, box, [gbif.AVES], True)
    aves = need(fx.get(u), u)
    u = gbif.facet_url(cat, box, [gbif.AVES], True, ebird_only=True)
    aves_eb = need(fx.get(u), u)
    aves_ot, aves_ot_n = other_left_out(cat, box, [gbif.AVES], True, aves, fx, always=True)
    effort = [a - b - c for a, b, c in zip(month_vector(aves), month_vector(aves_eb), aves_ot)]
    credits = {}
    out = []
    for entry in gbif.cast_for(cat, world):
        sp = cat["species"][entry["id"]]
        tk = [keys[t] for t in sp["taxa"]]
        seen = gbif.observed(cat, sp["kind"])
        u = gbif.facet_url(cat, box, tk, seen)
        allb = need(fx.get(u), u)
        u = gbif.facet_url(cat, box, tk, seen, ebird_only=True)
        ebb = need(fx.get(u), u)
        ot, ot_n = other_left_out(cat, box, tk, seen, allb, fx)
        mv = [a - b - c for a, b, c in zip(month_vector(allb), month_vector(ebb), ot)]
        total = int(allb["count"]) - int(ebb["count"]) - ot_n
        ds = fetch_gbif.non_ebird_datasets(cat, allb)
        for k, n in fetch_gbif.facet_counts(allb, "DATASET_KEY").items():
            if k not in out_keys:
                credits[k] = credits.get(k, 0) + n
        if sp["kind"] == "bird":
            rate = [mv[i] / effort[i] if effort[i] > 0 else 0.0 for i in range(12)]
        else:
            rate = [float(x) for x in mv]
        w, wsrc = weights(entry, rate, total)
        season_months = months_of(entry["months"]) | months_of(entry.get("rare_months"))
        share = (sum(mv[m - 1] for m in season_months) / sum(mv)) if sum(mv) > 0 else None
        # Record pages (birds: counts; dolphins and sharks: places), never from eBird.
        recs = []
        if ds and (sp["kind"] == "bird" or sp.get("density")):
            pages = fetch_gbif.MAX_PAGES_DENSITY if sp.get("density") else fetch_gbif.MAX_PAGES
            for i in range(pages):
                if i * gbif.PAGE >= sum(ds.values()):
                    break
                u = gbif.page_url(cat, box, tk, seen, ds, i * gbif.PAGE)
                b = need(fx.get(u), u)
                recs += [r for r in gbif.page_records(b) if r["k"] not in out_keys]
                if b.get("endOfRecords"):
                    break
        gkey = keys.get(sp.get("group_taxon")) if sp.get("group_taxon") else None
        counts = sorted(int(r["n"]) for r in recs if r.get("n") and (gkey is None or r.get("s") == gkey))
        grp = {"words": entry["group"]["words"]}
        if len(counts) >= MIN_COUNTS and sp["kind"] == "bird":
            grp.update({"typical": pct(counts, 0.5), "p90": pct(counts, 0.9), "source": "records", "counts": len(counts)})
        else:
            grp.update({"typical": entry["group"]["range"][0], "p90": entry["group"]["range"][1], "source": "rough",
                        "counts": len(counts)})
        if "roost" in entry["group"]:
            grp["roost"] = entry["group"]["roost"]
        row = {
            "id": entry["id"], "name": sp["name"], "kind": sp["kind"], "water": sp["water"], "style": sp["style"],
            "size_m": sp["size_m"], "taxa": [{"name": t, "gbif": keys[t]} for t in sp["taxa"]],
            "season": entry["months"], "months": w, "months_from": wsrc,
            "habitats": entry["habitats"], "activity": entry["activity"], "group": grp,
            "records": total, "records_are": "sightings since 2000" if seen else "all records",
            "ebird_left_out": int(ebb["count"]), "unclear_licence_left_out": ot_n,
            "in_season_share": None if share is None else round(share, 3), "see": entry["see"],
        }
        for k in ("also", "flush_m"):
            if k in sp:
                row[k] = sp[k]
        for k in ("rare_months", "peak", "rare"):
            if k in entry:
                row[k] = entry[k]
        if sp.get("density"):
            cells = {}
            for r in recs:
                if r["la"] is not None and box[0] <= r["lo"] <= box[2] and box[1] <= r["la"] <= box[3]:
                    c = (int((r["lo"] - box[0]) / CELL_DEG), int((r["la"] - box[1]) / CELL_DEG))
                    cells[c] = cells.get(c, 0) + 1
            row["density"] = {"cell_deg": CELL_DEG, "origin": [box[0], box[1]], "placed": sum(cells.values()),
                              "cells": [[c[0], c[1], n] for c, n in sorted(cells.items())]}
        out.append(row)
    cred = []
    for k, n in sorted(credits.items(), key=lambda kv: (-kv[1], kv[0])):
        u = gbif.dataset_url(k)
        d = need(fx.get(u), u)
        cred.append({"dataset": d.get("title"), "gbif": k, "records": n, "doi": d.get("doi"),
                     "licence": licence_name(d.get("license")) + (", records CC0 or CC BY counted only"
                                                                   if k in cat.get("per_record_licences", {}) else "")})
    return {
        "_doc": "Generated by Tools/wildlife/build_tables.py from GBIF.org records licensed CC0 or CC BY 4.0, eBird "
                "and datasets with unclear licences left out (docs/wildlife-0/README.md). Do not edit by hand.",
        "world": world, "water": cat["worlds"][world]["water"], "box": box,
        "bird_records": sum(effort), "bird_records_ebird_left_out": int(aves_eb["count"]),
        "bird_records_unclear_licence_left_out": aves_ot_n,
        "species": out, "credits": cred,
    }


def out_path(world):
    return os.path.join(gbif.REPO, "Content", "TerrainData", world + ".wildlife.json")


def dumps(t):
    return json.dumps(t, indent=1, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare with the committed tables, write nothing")
    ap.add_argument("--world", action="append", help="only these worlds")
    a = ap.parse_args()
    cat = gbif.load_catalogue()
    fx = gbif.Fetcher(offline=True)
    keys, done = fetch_gbif.resolve_names(cat, fx)
    if not done:
        print("names not resolved yet: run fetch_gbif.py first")
        return 3
    bad = 0
    for world in a.world or cat["worlds"]:
        try:
            t = build_world(cat, world, keys, fx)
        except Incomplete as e:
            print("%s: cache incomplete (%s...): run fetch_gbif.py first" % (world, str(e)[:120]))
            return 3
        p = out_path(world)
        text = dumps(t)
        if a.check:
            same = os.path.exists(p) and open(p).read() == text
            print("%-13s %s" % (world, "same" if same else "DIFFERS"))
            bad += 0 if same else 1
            continue
        with open(p, "w") as f:
            f.write(text)
        thin = [r["id"] for r in t["species"] if r["months_from"] == "season"]
        rough = [r["id"] for r in t["species"] if r["group"]["source"] == "rough" and r["kind"] == "bird"]
        print("%-13s %2d animals, %7d bird records (%d eBird left out); flat seasons: %s; rough bird groups: %s" % (
            world, len(t["species"]), t["bird_records"], t["bird_records_ebird_left_out"], ", ".join(thin) or "none",
            ", ".join(rough) or "none"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
