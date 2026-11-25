"""GBIF requests, the response cache and the world boxes for the wildlife tools (docs/wildlife-0/README.md).

Every response is cached under Data/Wildlife/raw/cache (git-ignored) by the SHA-1 of its URL, so the tables rebuild
offline and a fetch can be finished by any machine that reaches api.gbif.org: fetch_gbif.py --offline lists the
missing URLs, Tools/wildlife/browser_fetch.js fetches them in a browser on the api.gbif.org origin, and
fetch_gbif.py --ingest stores what it returns. Occurrence pages are cut down to the few fields the tables use
(reduce_page), the same way in Python and in browser_fetch.js.
"""
import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(REPO, "Data", "Wildlife", "raw")
CACHE = os.path.join(RAW, "cache")
API = "https://api.gbif.org/v1"
PAGE = 300
AVES = 212  # GBIF backbone class key for birds


def load_catalogue():
    with open(os.path.join(HERE, "species.json")) as f:
        return json.load(f)


def cast_for(cat, world):
    c = cat["casts"][world]
    if isinstance(c, str):
        c = cat["casts"][c.lstrip("@")]
    return c


def world_box(cat, world):
    """[west, south, east, north] in degrees."""
    w = cat["worlds"][world]
    if "box_union" in w:
        boxes = [world_box(cat, o) for o in w["box_union"]]
        return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    with open(os.path.join(REPO, w["box_from"])) as f:
        d = json.load(f)
    if "bbox" in d:
        return [float(v) for v in d["bbox"]]
    # A baked terrain file: grid in metres on a transverse Mercator about lat_0/lon_0. A query box only needs to
    # be close, so metres become degrees on the sphere.
    g = d["grid"]
    lat0 = float(re.search(r"\+lat_0=([-\d.]+)", d["projection"]).group(1))
    lon0 = float(re.search(r"\+lon_0=([-\d.]+)", d["projection"]).group(1))
    n0, e0 = g["origin_north_m"], g["origin_east_m"]
    n1, e1 = n0 + g["rows_north"] * g["cell_m"], e0 + g["cols_east"] * g["cell_m"]
    m_lat = 111132.0
    m_lon = 111320.0 * math.cos(math.radians(lat0))
    return [round(lon0 + e0 / m_lon, 4), round(lat0 + n0 / m_lat, 4), round(lon0 + e1 / m_lon, 4), round(lat0 + n1 / m_lat, 4)]


def polygon(box):
    w, s, e, n = box
    return "POLYGON((%s %s,%s %s,%s %s,%s %s,%s %s))" % (w, s, e, s, e, n, w, n, w, s)


def _q(params):
    return urllib.parse.urlencode(params, doseq=True, quote_via=urllib.parse.quote)


def match_url(name):
    return API + "/species/match?" + _q([("name", name), ("strict", "true")])


def dataset_url(key):
    return API + "/dataset/" + key


def observed(cat, kind):
    """Sightings only (no specimens), since 2000, for this kind of animal? (species.json "observed")"""
    return kind in cat["observed"]["kinds"]


def occ_params(cat, box, taxon_keys, seen):
    p = [("geometry", polygon(box)), ("occurrenceStatus", "PRESENT"), ("hasGeospatialIssue", "false")]
    p += [("license", l) for l in cat["licences"]]
    if seen:
        p += [("basisOfRecord", b) for b in cat["observed"]["basisOfRecord"]] + [("year", cat["observed"]["year"])]
    p += [("taxonKey", str(k)) for k in sorted(taxon_keys)]
    return p


def other_left_out(cat):
    """Datasets left out besides eBird (species.json left_out_datasets: unclear licences)."""
    return sorted(k for k in cat.get("left_out_datasets", {}) if not k.startswith("_"))


def left_out(cat):
    return {cat["ebird_dataset"]} | set(other_left_out(cat))


def facet_url(cat, box, taxon_keys, seen, ebird_only=False, only=None):
    """Month and dataset facets for these taxa in this box; ebird_only = the same, eBird's dataset alone, and only =
    these datasets alone (to take away: the search API has no 'not this dataset'). seen = sightings since 2000 only
    (observed())."""
    p = occ_params(cat, box, taxon_keys, seen) + [("limit", "0"), ("facet", "month")]
    if ebird_only:
        only = [cat["ebird_dataset"]]
    if only:
        p += [("datasetKey", k) for k in sorted(only)] + [("facetLimit", "12")]
    else:
        p += [("facet", "datasetKey"), ("facetLimit", "100")]
    return API + "/occurrence/search?" + _q(p)


def page_url(cat, box, taxon_keys, seen, dataset_keys, offset):
    p = occ_params(cat, box, taxon_keys, seen) + [("datasetKey", k) for k in sorted(dataset_keys)]
    p += [("limit", str(PAGE)), ("offset", str(offset))]
    return API + "/occurrence/search?" + _q(p)


def reduce_page(body):
    """An occurrence page cut to what the tables use: per record [dataset index, species key, count (0 = none),
    latitude, longitude] (3 decimals, about 100 m), with the page's dataset keys listed once in "ds"."""
    ds, idx, rows = [], {}, []
    for o in body.get("results", []):
        k = o.get("datasetKey")
        if k not in idx:
            idx[k] = len(ds)
            ds.append(k)
        la, lo = o.get("decimalLatitude"), o.get("decimalLongitude")
        has = la is not None and lo is not None
        rows.append([idx[k], o.get("speciesKey"), o.get("individualCount") or 0,
                     round(la, 3) if has else None, round(lo, 3) if has else None])
    return {"offset": body.get("offset"), "limit": body.get("limit"), "endOfRecords": body.get("endOfRecords"),
            "count": body.get("count"), "reduced": 2, "ds": ds, "r": rows}


def page_records(page):
    """A reduced page's records as dicts: k (dataset), s (species key), n (count), la, lo."""
    ds = page["ds"]
    return [{"k": ds[r[0]], "s": r[1], "n": r[2], "la": r[3], "lo": r[4]} for r in page["r"]]


def reduce_dataset(body):
    return {"key": body.get("key"), "title": body.get("title"), "license": body.get("license"), "doi": body.get("doi"),
            "publishingOrganizationKey": body.get("publishingOrganizationKey")}


def reduce_body(url, body):
    if "/occurrence/search?" in url:
        if "limit=0" in url:
            return {"count": body.get("count"), "facets": body.get("facets", [])}
        return reduce_page(body)
    if "/dataset/" in url:
        return reduce_dataset(body)
    return body


def cache_path(url):
    return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest()[:20] + ".json")


class Fetcher:
    """get(url) returns the cached body, fetches it when online, or records it as missing and returns None."""

    def __init__(self, offline=False, pause=0.15):
        self.offline = offline
        self.pause = pause
        self.missing = []
        self.fetched = 0
        os.makedirs(CACHE, exist_ok=True)

    def get(self, url):
        path = cache_path(url)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)["body"]
        if self.offline:
            if url not in self.missing:
                self.missing.append(url)
            return None
        body = None
        for attempt in range(6):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ReadyAbout-wildlife-tool"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = json.loads(r.read().decode())
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue
                raise
            except urllib.error.URLError:
                time.sleep(2 ** attempt)
        if body is None:
            self.missing.append(url)
            return None
        store(url, reduce_body(url, body))
        self.fetched += 1
        time.sleep(self.pause)
        return load(url)


def store(url, body):
    os.makedirs(CACHE, exist_ok=True)
    with open(cache_path(url), "w") as f:
        json.dump({"url": url, "body": body}, f, separators=(",", ":"))


def load(url):
    path = cache_path(url)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)["body"]
