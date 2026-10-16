#!/usr/bin/env python3
"""Dock and slip materials: CC0 texture sets from Poly Haven (https://polyhaven.com, CC0, no attribution required) and
ambientCG (https://ambientcg.com, CC0), into Data/Dock/raw (git-ignored). scripts/import_dock_materials.py imports them
into /Game/World/Dock.

    python3 Tools/dock/fetch_dock_materials.py [--res 2k] [--ultra]

Each set lands in Data/Dock/raw/<name>/ as <name>_{diff,nor,rough,ao,disp}.jpg (Unreal's DirectX normals), and
Data/Dock/raw/manifest.json records every file's source URL and licence (docs/licences/dock-materials.csv is written
from it). Sets already downloaded are skipped. --ultra also fetches 4K for the decking, the one surface seen up close.
"""
import argparse
import io
import json
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "Data", "Dock", "raw")
UA = {"User-Agent": "SailingSim-dock-fetch/1.0"}

# name: (source, asset id, role). Roles follow the marina and pier looks in WorldKit (EKitLook).
SETS = {
    "DeckWeathered": ("polyhaven", "weathered_planks", "dock decking, grey weathered boards"),
    "DeckBrown": ("polyhaven", "weathered_brown_planks", "pier decking, browner boards"),
    "PaintedPlanks": ("polyhaven", "distressed_painted_planks", "painted wood: dock boxes, clubhouse trim"),
    "ConcreteWorn": ("polyhaven", "concrete_floor_worn_001", "launch ramp and seawall cap"),
    "RustyMetal": ("polyhaven", "rusty_metal_02", "piling caps, cleats' bases, ladders"),
    "PaintedMetal": ("polyhaven", "rusty_painted_metal", "painted steel: gangway frames, rails"),
    "TeakBase": ("polyhaven", "oak_wood_planks", "re-graded toward teak in the material (toe rails, trim)"),
    "PlanksACG": ("ambientcg", "Planks021", "alternate decking boards"),
    "ConcreteACG": ("ambientcg", "Concrete034", "floating dock pontoons"),
    "MetalRustACG": ("ambientcg", "Metal053B", "heavy rust: old pier hardware"),
}
ULTRA_4K = {"DeckWeathered", "DeckBrown"}

PH_MAPS = {"diff": "Diffuse", "nor": "nor_dx", "rough": "Rough", "ao": "AO", "disp": "Displacement"}
ACG_MAPS = {"diff": "_Color", "nor": "_NormalDX", "rough": "_Roughness", "ao": "_AmbientOcclusion", "disp": "_Displacement"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
        return r.read()


def fetch_polyhaven(name, aid, res, out):
    files = json.loads(get(f"https://api.polyhaven.com/files/{aid}"))
    info = json.loads(get(f"https://api.polyhaven.com/info/{aid}"))
    got = {}
    for k, m in PH_MAPS.items():
        e = files.get(m, {}).get(res, {}).get("jpg")
        if not e:
            continue
        p = os.path.join(out, f"{name}_{k}.jpg")
        open(p, "wb").write(get(e["url"]))
        got[k] = e["url"]
    return {"page": f"https://polyhaven.com/a/{aid}", "authors": sorted(info.get("authors", {})), "files": got}


def fetch_ambientcg(name, aid, res, out):
    url = f"https://ambientcg.com/get?file={aid}_{res.upper()}-JPG.zip"
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    got = {}
    for k, suffix in ACG_MAPS.items():
        hit = [n for n in z.namelist() if suffix in n and n.lower().endswith(".jpg")]
        if hit:
            open(os.path.join(out, f"{name}_{k}.jpg"), "wb").write(z.read(hit[0]))
            got[k] = f"{url}#{hit[0]}"
    return {"page": f"https://ambientcg.com/view?id={aid}", "authors": ["ambientCG (Lennart Demes)"], "files": got}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="2k")
    ap.add_argument("--ultra", action="store_true")
    a = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    mpath = os.path.join(RAW, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    jobs = [(n, a.res) for n in SETS] + ([(n, "4k") for n in sorted(ULTRA_4K)] if a.ultra else [])
    for name, res in jobs:
        key = name if res == a.res else f"{name}_{res}"
        out = os.path.join(RAW, key)
        if key in manifest and os.path.isdir(out):
            continue
        os.makedirs(out, exist_ok=True)
        src, aid, role = SETS[name]
        print(f"{key}: {src} {aid} {res}", flush=True)
        try:
            rec = (fetch_polyhaven if src == "polyhaven" else fetch_ambientcg)(name, aid, res, out)
        except Exception as e:  # one failed set shouldn't lose the rest
            print(f"  failed: {e}", file=sys.stderr)
            continue
        manifest[key] = dict(rec, source=src, asset=aid, role=role, resolution=res, licence="CC0 1.0")
        json.dump(manifest, open(mpath, "w"), indent=1)
    rows = ["name,source,asset,page,licence,commercial,conditions"]
    for k, r in sorted(manifest.items()):
        rows.append(f"{k},{r['source']},{r['asset']},{r['page']},CC0 1.0,yes,none (credit optional)")
    open(os.path.join(ROOT, "docs", "licences", "dock-materials.csv"), "w").write("\n".join(rows) + "\n")
    print(f"{len(manifest)} sets in {RAW}")


if __name__ == "__main__":
    main()
