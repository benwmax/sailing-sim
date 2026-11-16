"""Fetches Track D's CC0 leaf and bark sets named in cards/*.json (and the dried oak for post oak's winter) into
Inputs/trees/<source>/<set>/, the folder the atlas and the materials read. Both sources are CC0, so the files may live in
the public repo (through Git LFS: the Mac or PC commits them; cloud sessions can't push LFS).

  ambientcg/<Id>     https://ambientcg.com/get?file=<Id>_1K-JPG.zip  -> <Id>_1K-JPG_{Color,NormalGL,NormalDX,Opacity,Roughness}.jpg
  polyhaven/<slug>   https://api.polyhaven.com/files/<slug> 1k jpg    -> <slug>_{diff,nor_gl,nor_dx,rough}_1k.jpg

Usage: python3 -I Tools/envloop/trees/fetch_sets.py [--root <dir>] [--dry-run]
Already present files are kept. Prints one line per set and the licence rows for docs/licences/assets.csv.
"""
import argparse
import glob
import io
import json
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
UA = {"User-Agent": "sailing-sim-envloop/1.0"}
ACG_MAPS = ("Color", "NormalGL", "NormalDX", "Opacity", "Roughness")
PH_MAPS = {"Diffuse": "diff", "nor_gl": "nor_gl", "nor_dx": "nor_dx", "Rough": "rough"}


def sets_from_cards():
    out = set()
    for path in sorted(glob.glob(os.path.join(HERE, "cards", "*.json"))):
        card = json.load(open(path))
        for key in ("leaf", "bark", "winter"):
            s = (card.get(key) or {}).get("set")
            if s:
                out.add(s)
    return sorted(out)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def fetch_ambientcg(asset, dest, dry):
    want = [f"{asset}_1K-JPG_{m}.jpg" for m in ACG_MAPS]
    if all(os.path.exists(os.path.join(dest, w)) for w in want if not w.endswith("Opacity.jpg")):
        return "kept"
    if dry:
        return "would fetch"
    z = zipfile.ZipFile(io.BytesIO(get(f"https://ambientcg.com/get?file={asset}_1K-JPG.zip")))
    os.makedirs(dest, exist_ok=True)
    got = 0
    for name in z.namelist():
        if name in want:
            open(os.path.join(dest, name), "wb").write(z.read(name))
            got += 1
    return f"fetched {got} maps"


def fetch_polyhaven(slug, dest, dry):
    files = json.loads(get(f"https://api.polyhaven.com/files/{slug}"))
    todo = []
    for key, short in PH_MAPS.items():
        url = ((files.get(key) or {}).get("1k") or {}).get("jpg", {}).get("url")
        if url:
            todo.append((url, os.path.join(dest, f"{slug}_{short}_1k.jpg")))
    todo = [(u, p) for u, p in todo if not os.path.exists(p)]
    if not todo:
        return "kept"
    if dry:
        return f"would fetch {len(todo)} maps"
    os.makedirs(dest, exist_ok=True)
    for url, path in todo:
        open(path, "wb").write(get(url))
    return f"fetched {len(todo)} maps"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=os.path.join(REPO, "Inputs", "trees"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    rows = []
    for s in sets_from_cards():
        source, asset = s.split("/", 1)
        dest = os.path.join(a.root, source, asset)
        how = fetch_ambientcg(asset, dest, a.dry_run) if source == "ambientcg" else fetch_polyhaven(asset, dest, a.dry_run)
        print(f"Sets: {s} {how}")
        url = f"https://ambientcg.com/view?id={asset}" if source == "ambientcg" else f"https://polyhaven.com/a/{asset}"
        rows.append(f"Inputs/trees/{source}/{asset}/*,{'ambientCG' if source == 'ambientcg' else 'Poly Haven'} {asset} ({url}),CC0,yes,none")
    print("Licence rows (docs/licences/assets.csv covers Content/ and Audio/; these are Inputs, listed for the record):")
    for r in rows:
        print("  " + r)


if __name__ == "__main__":
    sys.exit(main())
