"""Piers step 1: per 1 km tile, find candidate pixels (1 m) for
  A  over-water structures: the 3DEP DEM is hydro-flattened (water), but the lidar DSM stands >= DECK_MIN above it
     (piers, docks, boardwalks, bridges, platforms, and also moored boats, which step 2 separates);
  B  narrow raised land in the water: land narrower than NARROW_M (morphological opening) and at least RAISED_M above
     the flattened water (jetties, dikes, groins, breakwaters, causeway fills, spoil ridges).
Reads the G2 tiles (dem, dsm, cover) with Pillow only. Usage: stage1.py <Region> [nproc]
Writes <WORK>/<Region>/s1/<tile>.npz with global pixel coordinates and per-pixel values."""
import sys, os, json, numpy as np
from multiprocessing import Pool
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
G2 = os.environ.get("G2_OUT", os.path.dirname(os.path.dirname(HERE)))   # .../sailing-sim-g2
WORK = os.environ.get("PIERS_WORK", "/tmp/g2piers")
DECK_MIN = 0.85    # m above the flattened DEM water (lidar water returns sit ~0.5 m above it; 99th pct 2.4 m incl. boats)
RAISED_M = 0.75    # m above flattened water for B (about +0.2 m NAVD88; low rock jetties crest at only +0.5 to +1.2 m)
NARROW_M = 41      # opening window, m: land strips narrower than this are "narrow"
HALO = 48

def load(reg, name):
    out = {}
    for k in ("dem", "dsm", "cover"):
        p = f"{G2}/{reg}/{k}/{name}.tif"
        out[k] = np.array(Image.open(p)) if os.path.exists(p) else None
    return out

def minfilt(a, w, axis):
    """min over a centred window of w along axis (edges padded with the edge value)."""
    a = np.moveaxis(a, axis, 0); r = w // 2
    p = np.concatenate([np.repeat(a[:1], r, 0), a, np.repeat(a[-1:], w - 1 - r, 0)], 0)
    m, s = p, 1
    while s * 2 <= w:
        m = np.minimum(m[:-s], m[s:]); s *= 2
    res = np.minimum(m[:a.shape[0]], m[w - s:w - s + a.shape[0]])
    return np.moveaxis(res, 0, axis)

def erode(b, w):  return minfilt(minfilt(b.astype(np.uint8), w, 0), w, 1).astype(bool)
def dilate(b, w): return ~erode(~b, w)

def run(args):
    reg, e, n, tiles = args
    name = f"15_{e:04d}_{n:04d}"
    out = f"{WORK}/{reg}/s1/{name}.npz"
    if os.path.exists(out): return name, "skip"
    S = 1000 + 2 * HALO
    dem = np.full((S, S), np.nan, np.float32); dsm = dem.copy(); cov = np.full((S, S), 255, np.uint8); hard = np.zeros((S, S), bool)
    for dn in (-1, 0, 1):
        for de in (-1, 0, 1):
            nm = f"15_{e+de:04d}_{n+dn:04d}"
            if nm not in tiles: continue
            d = load(reg, nm)
            # window rows: row 0 = north edge of the window; tile (e+de, n+dn) occupies rows starting at HALO + (-dn)*1000
            r0 = HALO - dn * 1000; c0 = HALO + de * 1000
            rs, re_ = max(r0, 0), min(r0 + 1000, S); cs, ce = max(c0, 0), min(c0 + 1000, S)
            if rs >= re_ or cs >= ce: continue
            sl = (slice(rs - r0, re_ - r0), slice(cs - c0, ce - c0))
            x = d["dem"][sl].astype(np.float32); x[x < -9000] = np.nan; dem[rs:re_, cs:ce] = x
            if d["dsm"] is not None:
                x = d["dsm"][sl].astype(np.float32); x[x < -9000] = np.nan; dsm[rs:re_, cs:ce] = x
            if d["cover"] is not None:
                c = d["cover"].reshape(1000, 2, 1000, 2).transpose(0, 2, 1, 3).reshape(1000, 1000, 4)[sl]
                cov[rs:re_, cs:ce] = c[..., 0]
                hard[rs:re_, cs:ce] = (np.isin(c, (5, 6, 7))).sum(-1) >= 2
    wl = float(tiles[name]["water_level_navd88"])
    dsm = np.where(np.isnan(dsm), dem, dsm)
    valid = ~np.isnan(dem)
    # flattened water sits within a few dm of the tile's level (enclosed marinas a little higher); C-CAP water also counts
    water = valid & ((dem < wl + 0.45) | (cov == 0))
    hgt = dsm - dem
    A = water & (hgt >= DECK_MIN) & (hgt < 40)
    land = ~water                                    # nodata counts as land, so the band's inland edge is not "narrow"
    opened = dilate(erode(land, NARROW_M), NARROW_M)
    B = land & ~opened & valid & (dem >= wl + RAISED_M)
    c = (slice(HALO, HALO + 1000),) * 2
    wide = dilate(opened & ~water, 5)                # within 2 m of wide land (for "attached to shore")
    landn = dilate(land & ~A, 3)                     # A cells touching any land
    res = {}
    for k, m in (("A", A), ("B", B)):
        rr, cc = np.nonzero(m[c])
        res[k + "_e"] = (e * 1000 + cc).astype(np.int32)          # global UTM metre column (west edge of cell)
        res[k + "_n"] = (n * 1000 + 999 - rr).astype(np.int32)    # global UTM metre row (south edge of cell)
        res[k + "_dem"] = dem[c][rr, cc].astype(np.float32)
        res[k + "_dsm"] = dsm[c][rr, cc].astype(np.float32)
        res[k + "_cov"] = cov[c][rr, cc]
        res[k + "_hard"] = hard[c][rr, cc]
        res[k + "_adj"] = (wide if k == "B" else landn)[c][rr, cc]
    res["wl"] = wl
    np.savez_compressed(out, **res)
    return name, f"A {len(res['A_e'])} B {len(res['B_e'])}"

if __name__ == "__main__":
    reg = sys.argv[1]; npr = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    T = {t["name"]: t for t in json.load(open(f"{G2}/{reg}/tiles.json"))["tiles"]}
    os.makedirs(f"{WORK}/{reg}/s1", exist_ok=True)
    only = sys.argv[3:]
    jobs = [(reg, int(k.split("_")[1]), int(k.split("_")[2]), T) for k in T if not only or k in only]
    with Pool(npr) as p:
        for i, (nm, s) in enumerate(p.imap_unordered(run, jobs)):
            print(i + 1, len(jobs), nm, s, flush=True)
