"""Downloads a ship's reference drawings from Wikimedia Commons (docs/shipkit-1).

    python3 -I fetch_refs.py <refs.json> <out dir> [--full]

Reads the "drawings" list of a refs.json (Tools/shipkit/frigate/refs.json) and saves each file to <out dir> (use the
git-ignored Data/Reference/raw/ships/<Ship>/). By default it takes Commons' 3840 px wide rendering, which is what the
offsets were read from (a drawing narrower than that comes as it is); --full asks for the original scan (6,000-15,000
px; Commons rate-limits these, so the script waits and retries) and saves it as <name>_full.jpg. Files already present
are skipped. Every drawing must be public domain, CC0 or CC BY (no NC, ND or SA), both as listed in refs.json and in
Commons' own licence field for the file, which is read before downloading: the script refuses anything else.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "SailingSimBlindTest/1.0 (https://github.com/benwmax/sailing-sim)"     # the same client as Tools/blindtest


def licence_ok(text):
    """Public domain (PD-...), CC0 or plain CC BY: not NC, ND or SA."""
    t = " ".join(str(text or "").lower().replace("_", " ").split())
    if re.search(r"\b(nc|nd|sa)\b|-nc|-nd|-sa|non-?commercial|no ?deriv|share ?alike", t):
        return False
    return bool(re.match(r"(public domain|pd\b|pd-|cc0|cc by \d|cc-by-\d|cc by$)", t))


def api_json(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:                       # 429: Commons asks us to slow down
            print(f"  retry {k + 1}: {e}")
            time.sleep(45 * (k + 1))
    return None


def get(url, dst, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r, open(dst + ".part", "wb") as f:
                f.write(r.read())
            os.replace(dst + ".part", dst)
            return True
        except Exception as e:                       # 429: Commons asks us to slow down
            print(f"  retry {k + 1}: {e}")
            time.sleep(45 * (k + 1))
    return False


def main(refs, out, full=False):
    os.makedirs(out, exist_ok=True)
    for d in json.load(open(refs))["drawings"]:
        if not licence_ok(d.get("licence")):
            print("skip (licence in refs.json):", d["file"])
            continue
        name = d["file"].replace(" ", "_")
        if not name or name != os.path.basename(name) or name.startswith(".") or "\\" in name:
            print("skip (not a plain file name):", d["file"])
            continue
        if full:                                     # the originals keep their own name: the readings are on the 3840 px copy
            stem, ext = os.path.splitext(name)
            name = f"{stem}_full{ext}"
        dst = os.path.join(out, name)
        if os.path.exists(dst):
            continue
        q = urllib.parse.quote(d["file"].replace(" ", "_"))
        small = full or d["size_px"][0] <= 3840         # no smaller rendering to ask for: take the original
        api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url|extmetadata"
               f"&titles=File:{q}" + ("" if small else "&iiurlwidth=3840"))
        res = api_json(api)
        pages = list(((res or {}).get("query") or {}).get("pages", {}).values())
        if not pages or not pages[0].get("imageinfo"):
            print("FAIL (not found on Commons):", name)
            continue
        info = pages[0]["imageinfo"][0]
        lic = ((info.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "")
        if not licence_ok(lic):
            print(f"skip (Commons licence {lic!r}):", name)
            continue
        url = info["url"] if small else info.get("thumburl", info["url"])
        print(("ok  " if get(url, dst) else "FAIL"), name)
        time.sleep(35)                               # one file at a time, politely


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--full" in sys.argv)
