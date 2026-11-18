"""Track A (shore plan, ground textures): download the eight CC0 ground scans a region pack names.

    python3 -I Tools/envloop/ground/fetch_ground.py [--pack north-texas-lake] [--res 2k] [--alternates]

Writes Data/Ground/raw/<pack>/<role>/ (git-ignored, like Data/Fabrics/raw): colour, normal (OpenGL convention), roughness,
displacement and, when the source has one, ambient occlusion, as JPG/PNG straight from Poly Haven or ambientCG, plus
source.json (asset, licence, URLs, sha256). Both sites are CC0: no attribution needed, and the files may live in the
public repo, but they are big, so the repo keeps this script and the machines fetch. prep_ground.py turns them into the
material's packed maps.
"""
import argparse
import hashlib
import io
import json
import os
import urllib.request
import zipfile

import pack as packs

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
UA = {"User-Agent": "sailingsim-envloop/1.0"}

# The map names this pipeline uses, and what each site calls them.
PH_MAPS = {"color": "Diffuse", "normal": "nor_gl", "rough": "Rough", "height": "Displacement", "ao": "AO"}
ACG_MAPS = {"color": "_Color.", "normal": "_NormalGL.", "rough": "_Roughness.", "height": "_Displacement.",
            "ao": "_AmbientOcclusion."}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600).read()


def save(path, data):
    with open(path, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def fetch_polyhaven(asset, res, out):
    files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
    rows = {}
    for key, name in PH_MAPS.items():
        if name not in files:
            continue
        fmt = "png" if key in ("height", "normal") and "png" in files[name][res] else "jpg"
        url = files[name][res][fmt]["url"]
        path = os.path.join(out, f"{key}.{fmt}")
        rows[key] = {"url": url, "sha256": save(path, get(url)), "file": os.path.basename(path)}
    return rows


def fetch_ambientcg(asset, res, out):
    url = f"https://ambientcg.com/get?file={asset}_{res.upper()}-JPG.zip"
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    rows = {}
    for key, tag in ACG_MAPS.items():
        names = [n for n in z.namelist() if tag in n]
        if not names:
            continue
        name = names[0]
        path = os.path.join(out, key + os.path.splitext(name)[1].lower())
        rows[key] = {"url": url, "member": name, "sha256": save(path, z.read(name)), "file": os.path.basename(path)}
    return rows


def fetch(site, asset, res, out):
    os.makedirs(out, exist_ok=True)
    if site == "Poly Haven":
        return fetch_polyhaven(asset, res, out)
    if site == "ambientCG":
        return fetch_ambientcg(asset, res, out)
    raise ValueError(site)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=None)
    ap.add_argument("--res", default="2k", choices=["1k", "2k", "4k"])
    ap.add_argument("--alternates", action="store_true", help="also fetch each surface's alternates (for blind rounds)")
    ap.add_argument("--only", default="", help="comma list of surface ids")
    args = ap.parse_args()
    card = packs.load(args.pack)
    RAW = packs.raw_dir(args.pack)
    only = set(filter(None, args.only.split(",")))
    for s in card["surfaces"]:
        if only and s["id"] not in only:
            continue
        jobs = [(s["source"]["site"], s["source"]["asset"], os.path.join(RAW, s["id"]))]
        if args.alternates:
            for alt in s.get("alternates", []):
                site, asset = alt.rsplit(" ", 1)
                jobs.append((site, asset, os.path.join(RAW, f"{s['id']}~{asset}")))
        for site, asset, out in jobs:
            meta = os.path.join(out, "source.json")
            if os.path.exists(meta) and json.load(open(meta)).get("res") == args.res:
                continue
            rows = fetch(site, asset, args.res, out)
            json.dump({"site": site, "asset": asset, "licence": "CC0", "res": args.res, "maps": rows},
                      open(meta, "w"), indent=1)
            print(f"{s['id']:8s} {site} {asset}: {', '.join(sorted(rows))}")


if __name__ == "__main__":
    main()
