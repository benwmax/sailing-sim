"""Minimal Entwine Point Tile reader (USGS 3DEP public lidar on AWS): bbox query -> numpy arrays."""
import json, io, os, hashlib, urllib.request, time, threading
import numpy as np, laspy
from concurrent.futures import ThreadPoolExecutor
from common import EPT, SRC

_cache = {}
_lock = threading.Lock()

def _get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)

def meta(name):
    if name not in _cache:
        _cache[name] = json.loads(_get(f"{EPT}/{name}/ept.json"))
        _cache[name + "/h"] = {}
    return _cache[name]

def _hier(name, key):
    h = _cache[name + "/h"]
    if key not in h:
        d = os.path.join(SRC, "ept", name, "h"); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, key + ".json")
        if os.path.exists(p):
            h[key] = json.load(open(p))
        else:
            h[key] = json.loads(_get(f"{EPT}/{name}/ept-hierarchy/{key}.json"))
            json.dump(h[key], open(p, "w"))
    return h[key]

def nodes(name, bbox, keep=None, max_depth=99):
    """Nodes (key, count) intersecting bbox=(xmin,ymin,xmax,ymax) in EPT srs. keep(xmin,ymin,xmax,ymax)->bool optional finer test."""
    m = meta(name); b = m["bounds"]
    out = []
    def bounds_of(d, x, y):
        s = (b[3] - b[0]) / 2 ** d
        return b[0] + x * s, b[1] + y * s, b[0] + (x + 1) * s, b[1] + (y + 1) * s
    def walk(hkey, d, x, y, z):
        h = _hier(name, hkey)
        stack = [(d, x, y, z)]
        while stack:
            d, x, y, z = stack.pop()
            k = f"{d}-{x}-{y}-{z}"
            if k not in h:
                continue
            nb = bounds_of(d, x, y)
            if nb[2] < bbox[0] or nb[0] > bbox[2] or nb[3] < bbox[1] or nb[1] > bbox[3]:
                continue
            if keep is not None and not keep(*nb):
                continue
            c = h[k]
            if c == -1:
                walk(k, d, x, y, z)
                continue
            if c > 0:
                out.append((k, c))
            if d < max_depth:
                for dx in (0, 1):
                    for dy in (0, 1):
                        for dz in (0, 1):
                            stack.append((d + 1, 2 * x + dx, 2 * y + dy, 2 * z + dz))
    walk("0-0-0-0", 0, 0, 0, 0)
    return out

def read_node(name, key):
    raw = _get(f"{EPT}/{name}/ept-data/{key}.laz")
    las = laspy.read(io.BytesIO(raw))
    return np.asarray(las.x), np.asarray(las.y), np.asarray(las.z, np.float32), np.asarray(las.classification, np.uint8), np.asarray(las.return_number, np.uint8), np.asarray(las.number_of_returns, np.uint8)

def query(name, bbox, keep=None, workers=16):
    ns = nodes(name, bbox, keep)
    parts = []
    with ThreadPoolExecutor(workers) as ex:
        for x, y, z, c, rn, nr in ex.map(lambda k: read_node(name, k[0]), ns):
            s = (x >= bbox[0]) & (x <= bbox[2]) & (y >= bbox[1]) & (y <= bbox[3])
            if s.any():
                parts.append((x[s], y[s], z[s], c[s], rn[s], nr[s]))
    if not parts:
        return [np.zeros(0)] * 6
    return [np.concatenate([p[i] for p in parts]) for i in range(6)]
