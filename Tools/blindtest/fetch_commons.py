#!/usr/bin/env python3
"""Graphics G5: finds and fetches Wikimedia Commons photos for a blind test, keeping only free licences we can show
(CC0, public domain, CC BY, CC BY-SA) and recording the credit for each.

  search <dir> <key> <query...>   (or a "Category:..." name) saves up to 12 candidate thumbnails (640 px) as <dir>/cand/<key>_NN.jpg and lists them
                                  in <dir>/cand/<key>.json (title, author, licence, size)
  pick <dir> <key> <NN>           fetches that candidate at 2400 px into <dir>/<key>.jpg and adds it to <dir>/credits.json
                                  (the format Tools/blindtest/make_blind_pack.py reads)

Usage: Tools/venv/bin/python -I Tools/blindtest/fetch_commons.py search Artifacts/commons-g5 shelf "shelf cloud over water"
"""
import html, json, os, re, sys, time, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "SailingSimBlindTest/1.0 (https://github.com/benwmax/sailing-sim)"
FREE = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? [0-9.]+)", re.I)


def get(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError("Commons API unreachable")


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def info(titles, width):
    d = get({"action": "query", "titles": "|".join(titles), "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime",
             "iiurlwidth": width})
    out = []
    for p in d.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata", {})
        lic = strip(m.get("LicenseShortName", {}).get("value"))
        if ii.get("mime") not in ("image/jpeg", "image/png") or not FREE.match(lic):
            continue
        out.append({"file": p["title"][5:].rsplit(".", 1)[0].replace("_", " "), "title": p["title"],
                    "author": strip(m.get("Artist", {}).get("value")) or "unknown", "license": lic,
                    "license_url": strip(m.get("LicenseUrl", {}).get("value")) or "https://creativecommons.org/publicdomain/zero/1.0/",
                    "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
                    "thumb": ii.get("thumburl"), "w": ii.get("width"), "h": ii.get("height")})
    return out


def search(d, key, query):
    os.makedirs(os.path.join(d, "cand"), exist_ok=True)
    if query.startswith("Category:"):
        # A category is far more precise than free text: its files, newest uploads mixed with old.
        r = get({"action": "query", "list": "categorymembers", "cmtitle": query, "cmtype": "file", "cmlimit": 50})
        titles = [m["title"] for m in r["query"]["categorymembers"]]
    else:
        r = get({"action": "query", "list": "search", "srnamespace": 6, "srsearch": query + " filetype:bitmap", "srlimit": 30})
        titles = [s["title"] for s in r["query"]["search"]]
    found = []
    for i in range(0, len(titles), 25):
        found += info(titles[i:i + 25], 640)
    found = [f for f in found if (f["w"] or 0) >= 1200 and (f["h"] or 0) >= 800 and f["w"] >= f["h"]][:12]   # landscape only
    for i, f in enumerate(found):
        download(f["thumb"], os.path.join(d, "cand", f"{key}_{i:02d}.jpg"))
    json.dump(found, open(os.path.join(d, "cand", key + ".json"), "w"), indent=1)
    for i, f in enumerate(found):
        print(f"{key}_{i:02d}  {f['license']:<12} {f['w']}x{f['h']}  {f['file'][:70]}")


def pick(d, key, n):
    f = json.load(open(os.path.join(d, "cand", key + ".json")))[int(n)]
    full = info([f["title"]], 2400)[0]
    path = os.path.join(d, key + ".jpg")
    download(full["thumb"], path)
    cpath = os.path.join(d, "credits.json")
    credits = [c for c in (json.load(open(cpath)) if os.path.exists(cpath) else []) if os.path.basename(c["local"]) != key + ".jpg"]
    credits.append({**{k: full[k] for k in ("file", "author", "license", "license_url", "page")}, "local": path})
    json.dump(credits, open(cpath, "w"), indent=1)
    print("picked", key, "->", full["file"], full["license"])


if __name__ == "__main__":
    cmd, d, key = sys.argv[1], sys.argv[2], sys.argv[3]
    search(d, key, " ".join(sys.argv[4:])) if cmd == "search" else pick(d, key, sys.argv[4])
