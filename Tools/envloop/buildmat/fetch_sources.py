"""Fetch the CC0 scans the building materials take their fine grain from (Track E2, docs/envloop/buildmat).

    python3 -I Tools/envloop/buildmat/fetch_sources.py [--res 1k]

Every source is CC0 (Poly Haven or ambientCG), listed in sources.json with its page. The files land in the git-ignored
Data/BuildMat/raw/<id>/ (colour and height maps only); nothing downloaded is committed. make_textures.py reads them.

The layout of every wall and roof (brick sizes, board widths, shingle rows) is drawn by make_textures.py at the size card's
real dimensions; the scans only add what is hard to draw: the grain of a fired brick face, sand in mortar and stucco,
the fibre-cement wood grain, chopped stone, the paint skin on steel.
"""
import argparse
import hashlib
import io
import json
import os
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RAW = os.path.join(REPO, "Data", "BuildMat", "raw")
UA = {"User-Agent": "sailing-sim-envloop/1.0"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def polyhaven(asset, res):
    files = json.loads(get("https://api.polyhaven.com/files/" + asset))
    out = {}
    for key, name in (("Diffuse", "color"), ("Displacement", "height")):
        if key in files and res in files[key]:
            fmt = "jpg" if "jpg" in files[key][res] else "png"
            out[name] = files[key][res][fmt]["url"]
    return out


def ambientcg(asset, res):
    url = "https://ambientcg.com/get?file=%s_%s-JPG.zip" % (asset, res.upper())
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    out = {}
    for n in z.namelist():
        low = n.lower()
        for tag, name in (("_color", "color"), ("_displacement", "height")):
            if tag in low and low.endswith(".jpg"):
                out[name] = (n, z.read(n))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="1k")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    src = json.load(open(os.path.join(HERE, "sources.json")))
    for sid, s in src["sources"].items():
        d = os.path.join(RAW, sid)
        os.makedirs(d, exist_ok=True)
        want = [os.path.join(d, n + ".jpg") for n in ("color", "height")]
        if not a.force and all(os.path.exists(p) for p in want):
            continue
        print("fetch", sid, s["site"], s["asset"])
        if s["site"] == "polyhaven":
            for name, url in polyhaven(s["asset"], a.res).items():
                data = get(url)
                open(os.path.join(d, name + ".jpg"), "wb").write(data)
                print("  ", name, len(data), hashlib.sha256(data).hexdigest()[:12])
        else:
            for name, (zn, data) in ambientcg(s["asset"], a.res).items():
                open(os.path.join(d, name + ".jpg"), "wb").write(data)
                print("  ", name, zn, len(data), hashlib.sha256(data).hexdigest()[:12])


if __name__ == "__main__":
    main()
