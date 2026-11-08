"""Download a surface's reference photos into the git-ignored reference folder (docs/texture-loop).

    python Tools/texloop/fetch_refs.py gelcoat [--pace 30]

Reads Tools/texloop/refs/<surface>.json and saves each entry's `file` URL to
Data/Reference/raw/textures/<Surface>/<level>/<id>.jpg (skipping ones already there). The repo keeps only the links,
licences and the numbers measured from the photos; the photos never go in git (Data/*/raw/ is ignored).

Licences: each entry carries `licence` and `use`. "measure" (CC BY, CC BY-SA, editorial-free photos) means we only read
numbers off it; "ship" (CC0, public domain, our own photos) may also become texture data. Anything else is refused.
Wikimedia rate-limits the cloud: thumbnails at 1280 px, one every `--pace` seconds (30 by default).
"""
import argparse
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(REPO, "Data", "Reference", "raw", "textures")
UA = "ReadyAboutTextureLoop/0.1 (texture reference research; https://github.com/benwmax/sailing-sim)"
SHIP_OK = ("CC0", "Public domain", "PD", "Own photo")
MEASURE_OK = SHIP_OK + ("CC BY", "CC BY-SA", "FAL")  # FAL: Free Art License (copyleft, commercial OK)


def licence_ok(ref):
    lic = ref.get("licence", "")
    allowed = SHIP_OK if ref.get("use") == "ship" else MEASURE_OK
    return any(lic.startswith(x) for x in allowed) and "NC" not in lic and "ND" not in lic


def fetch(url, path, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                data = r.read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").write(data)
            return True
        except Exception as e:  # 429s: back off
            print("  retry", i + 1, e, file=sys.stderr)
            time.sleep(30 * (i + 1))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("surface")
    ap.add_argument("--pace", type=float, default=30.0)
    a = ap.parse_args()
    refs = json.load(open(os.path.join(HERE, "refs", a.surface + ".json")))["refs"]
    got = 0
    for r in refs:
        if not r.get("file"):
            continue
        if not licence_ok(r):
            print("refused (licence):", r["id"], r.get("licence"), file=sys.stderr)
            continue
        path = os.path.join(RAW, a.surface.capitalize(), r["level"], r["id"] + ".jpg")
        if os.path.exists(path):
            continue
        print("fetch", r["id"])
        if fetch(r["file"], path):
            got += 1
            time.sleep(a.pace if "wikimedia" in r["file"] else 1.0)
    print("fetched", got)


if __name__ == "__main__":
    main()
