"""Fetch the GBIF records behind the wildlife tables (docs/wildlife-0/README.md).

    python3 Tools/wildlife/fetch_gbif.py             # online: fetch whatever the cache lacks
    python3 Tools/wildlife/fetch_gbif.py --offline   # no network: write Data/Wildlife/raw/missing.json, exit 3
    python3 Tools/wildlife/fetch_gbif.py --ingest results.json   # store {url: body} fetched elsewhere, then run

Stages, each needing the one before: (1) names to GBIF taxon keys; (2) per world, month and dataset facets for every
cast entry and for all birds (the effort baseline), all records, eBird's alone and the other left-out datasets
alone (species.json left_out_datasets); (3) record pages from the non-eBird
datasets, for bird group sizes and dolphin and shark places; (4) dataset titles and licences for the credits. Only
records licensed CC0 or CC BY 4.0, present, without geospatial issues, inside the world's box; for birds, dolphins and
whales only sightings since 2000 (species.json "observed").
Exit 0 when the cache holds everything, 3 when URLs are still missing (run again, or fetch them elsewhere).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gbif  # noqa: E402

MAX_PAGES = 10        # 3,000 records for bird group sizes
MAX_PAGES_DENSITY = 20  # 6,000 records for dolphin and shark places
TOP_DATASETS = 40     # page the biggest non-eBird datasets only (keeps URLs short)


def facet_counts(body, field):
    for f in (body or {}).get("facets", []):
        if f["field"].lower() == field.lower():
            return {c["name"]: c["count"] for c in f["counts"]}
    return {}


def resolve_names(cat, fx):
    names = sorted({t for s in cat["species"].values() for t in s["taxa"]})
    keys = {}
    for n in names:
        b = fx.get(gbif.match_url(n))
        if b is None:
            continue
        k = b.get("acceptedUsageKey") or b.get("usageKey")
        if not k or b.get("matchType") not in ("EXACT", "FUZZY"):
            raise SystemExit("GBIF has no clean match for %r: %s" % (n, json.dumps(b)[:300]))
        keys[n] = k
    return keys, len(keys) == len(names)


def non_ebird_datasets(cat, body):
    """The datasets to page: the biggest non-eBird ones. (Datasets left out for unclear licences are paged too, to keep
    the cached URLs, and their rows dropped at build.)"""
    ds = facet_counts(body, "DATASET_KEY")
    ds.pop(cat["ebird_dataset"], None)
    return dict(sorted(ds.items(), key=lambda kv: -kv[1])[:TOP_DATASETS])


def other_left_out_url(cat, box, taxon_keys, seen, allb, always=False):
    """The facet URL of the datasets left out besides eBird, when they may hold some of these records (they show in
    the dataset facet, or the facet is cut at its limit), else None."""
    other = gbif.other_left_out(cat)
    if not other:
        return None
    ds = facet_counts(allb, "DATASET_KEY")
    if always or len(ds) >= 100 or any(k in ds for k in other):
        return gbif.facet_url(cat, box, taxon_keys, seen, only=other)
    return None


def run(cat, fx):
    keys, names_done = resolve_names(cat, fx)
    if not names_done:
        return
    datasets = set()
    for world in cat["worlds"]:
        box = gbif.world_box(cat, world)
        fx.get(gbif.facet_url(cat, box, [gbif.AVES], True))
        fx.get(gbif.facet_url(cat, box, [gbif.AVES], True, ebird_only=True))
        u = other_left_out_url(cat, box, [gbif.AVES], True, None, always=True)
        if u:
            fx.get(u)
        for entry in gbif.cast_for(cat, world):
            sp = cat["species"][entry["id"]]
            tk = [keys[t] for t in sp["taxa"]]
            seen = gbif.observed(cat, sp["kind"])
            allb = fx.get(gbif.facet_url(cat, box, tk, seen))
            fx.get(gbif.facet_url(cat, box, tk, seen, ebird_only=True))
            if allb is None:
                continue
            u = other_left_out_url(cat, box, tk, seen, allb)
            if u:
                fx.get(u)
            ds = non_ebird_datasets(cat, allb)
            datasets.update(k for k in facet_counts(allb, "DATASET_KEY") if k not in gbif.left_out(cat))
            if not ds or not (sp["kind"] == "bird" or sp.get("density")):
                continue
            pages = MAX_PAGES_DENSITY if sp.get("density") else MAX_PAGES
            pages = min(pages, math.ceil(sum(ds.values()) / gbif.PAGE))
            for i in range(pages):
                b = fx.get(gbif.page_url(cat, box, tk, seen, ds, i * gbif.PAGE))
                if b is None or b.get("endOfRecords"):
                    break
    for k in sorted(datasets):
        fx.get(gbif.dataset_url(k))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="never touch the network; list what is missing")
    ap.add_argument("--ingest", help="JSON file of {url: body} fetched elsewhere (browser_fetch.js)")
    a = ap.parse_args()
    if a.ingest:
        with open(a.ingest) as f:
            got = json.load(f)
        n = 0
        for url, body in got.items():
            if body is None or (isinstance(body, dict) and body.get("error")):
                continue
            gbif.store(url, body if (isinstance(body, dict) and body.get("reduced") == 2) else gbif.reduce_body(url, body))
            n += 1
        print("ingested %d responses" % n)
    cat = gbif.load_catalogue()
    # Rounds: each pass can reveal the next stage's URLs.
    while True:
        fx = gbif.Fetcher(offline=a.offline or bool(a.ingest))
        run(cat, fx)
        if fx.missing or fx.fetched == 0:
            break
    os.makedirs(gbif.RAW, exist_ok=True)
    out = os.path.join(gbif.RAW, "missing.json")
    if fx.missing:
        with open(out, "w") as f:
            json.dump(fx.missing, f, indent=0)
        print("%d URLs missing -> %s" % (len(fx.missing), os.path.relpath(out, gbif.REPO)))
        return 3
    if os.path.exists(out):
        os.remove(out)
    print("cache complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
