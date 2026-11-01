"""Shore dressing (pc/shore-polyhaven): CC0 models from Poly Haven (https://polyhaven.com, every asset CC0, no
attribution required), fetched through its public API (api.polyhaven.com) as FBX with their textures, into the
git-ignored Data/Shore/raw/<id>/ with credits.json (each asset's authors and page, for CREDITS.md). Nothing else is
fetched. scripts/import_world.py imports them to /Game/World/Shore (SM_Shore_*).

Usage: python Tools/shore/fetch_polyhaven.py [--dry-run]    (--dry-run prints the sizes and fetches nothing)
"""
import json
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "Data", "Shore", "raw")
API = "https://api.polyhaven.com"
BUDGET_MB = 500
# id -> texture resolution. Rocks and driftwood seen from the slip at 2k; grass tufts and small props at 1k.
# (The coast rock sets are heavy meshes, 70-120 MB each: four of them keep the whole set near 450 MB.)
ASSETS = {
    "coast_rocks_01": "2k", "coast_rocks_03": "2k", "coast_rocks_05": "2k",
    "coast_land_rocks_03": "2k", "rock_moss_set_01": "2k",
    "boulder_01": "2k", "dead_tree_trunk": "2k", "dead_tree_trunk_02": "2k", "tree_stump_01": "1k",
    "grass_medium_01": "1k", "grass_bermuda_01": "1k", "fern_02": "1k",
    "lifebuoy": "1k", "wooden_picnic_table": "1k", "painted_wooden_bench": "1k",
}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SailingSim-shore-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def plan():
    """For each asset: its licence check, authors and the FBX file plus its textures at the chosen size."""
    items, total = [], 0
    for aid, res in ASSETS.items():
        info = get_json(f"{API}/info/{aid}")
        files = get_json(f"{API}/files/{aid}")
        fbx = files.get("fbx", {}).get(res, {}).get("fbx")
        if not fbx:
            print(f"{aid}: no {res} FBX, skipped")
            continue
        parts = [(fbx["url"], os.path.basename(fbx["url"]), fbx["size"])]
        for rel, inc in fbx.get("include", {}).items():
            parts.append((inc["url"], rel, inc["size"]))
        size = sum(p[2] for p in parts)
        total += size
        items.append({"id": aid, "name": info.get("name", aid), "authors": list(info.get("authors", {}).keys()),
                      "page": f"https://polyhaven.com/a/{aid}", "licence": "CC0", "res": res, "parts": parts, "size": size})
        print(f"{aid}: {res}, {len(parts)} files, {size / 1e6:.1f} MB")
    print(f"Total {total / 1e6:.1f} MB (budget {BUDGET_MB} MB)")
    return items, total


def main():
    items, total = plan()
    if "--dry-run" in sys.argv:
        return
    if total / 1e6 > BUDGET_MB:
        raise SystemExit("Over budget: nothing fetched")
    os.makedirs(OUT, exist_ok=True)
    for it in items:
        folder = os.path.join(OUT, it["id"])
        for url, rel, size in it["parts"]:
            dest = os.path.normpath(os.path.join(folder, rel))
            if not dest.startswith(os.path.normpath(folder) + os.sep):
                raise SystemExit(f"{it['id']}: refusing a path outside its folder: {rel}")
            if os.path.exists(dest) and os.path.getsize(dest) == size:
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "SailingSim-shore-fetch"})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
                f.write(r.read())
        print(f"{it['id']}: fetched")
    credits = [{k: it[k] for k in ("id", "name", "authors", "page", "licence", "res")} for it in items]
    json.dump(credits, open(os.path.join(OUT, "credits.json"), "w"), indent=1)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
