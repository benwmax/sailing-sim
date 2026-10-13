"""Step 3: process one UTM 1 km tile.

Writes (UTM 14N / 15N GeoTIFFs, heights NAVD88 metres):
  dem/<tile>.tif     float32 1 m bare earth (USGS 3DEP 1 m DEM), nodata -9999 outside the band
  dsm/<tile>.tif     float32 1 m first-return surface (max lidar return per cell; gaps filled with the DEM)
  cover/<tile>.tif   uint8 0.5 m ground cover (classes in COVER), 255 outside the band
  ortho/<tile>.tif   NAIP 2022 RGB at native 0.6 m (written by ortho.py)
and keeps building, tree and shore records for merge.py.
Work grid: 1 m (0.5 m for cover), row 0 = north, with an apron round the tile.
"""
import sys, os, json, pickle, math, warnings, base64
import numpy as np, rasterio, shapely, shapely.affinity
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from rasterio import features
from scipy import ndimage
from skimage.segmentation import watershed
from skimage.measure import find_contours
from common import *
import ept

warnings.filterwarnings("ignore")
A = 48  # apron, m
CCAP = f"/vsicurl/{TNRIS}/LCD/collection/noaa-2020-ccap-landcover-1m/items/lcr/noaa-2020-ccap-landcover-1m_11111_20240612.tif"
COVER = ["water", "grass", "scrub", "bare_clay", "sand", "riprap_rock", "concrete", "asphalt", "tree_canopy", "building"]
CV = {n: i for i, n in enumerate(COVER)}
SHORE_TYPES = ["natural", "riprap", "bulkhead", "beach"]
_prep = {}
TAGS = {}


def tname(reg, e, n):
    return f"{REGIONS[reg]['utm_epsg'] - 26900}_{e:04d}_{n:04d}"


def wtif(path, arr, tr, crs, nodata, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prof = dict(driver="GTiff", height=arr.shape[-2], width=arr.shape[-1], count=1 if arr.ndim == 2 else arr.shape[0], dtype=arr.dtype,
                crs=crs, transform=tr, nodata=nodata, tiled=True, blockxsize=256, blockysize=256, compress="deflate", **kw)
    with rasterio.open(path, "w", **prof) as d:
        d.write(arr if arr.ndim == 3 else arr[None])
        d.update_tags(**TAGS)


def run(reg, te, tn):
    global TAGS
    R = REGIONS[reg]; U = f"EPSG:{R['utm_epsg']}"
    if reg not in _prep:
        _prep[reg] = pickle.load(open(f"{WORK}/{reg}_prep.pkl", "rb"))
    P = _prep[reg]
    simoff = -435.5 * 0.3048006096 if reg == "RayHubbard" else 0.094
    TAGS = dict(VERTICAL_DATUM="NAVD88 (GEOID12B), metres", SIM_Z_OFFSET_M=f"{simoff:.4f}",
                SIM_Z_NOTE=("sim Z = NAVD88 + offset; Z = 0 at the 435.5 ft conservation pool" if reg == "RayHubbard" else "sim Z = NAVD88 + 0.094 = metres above MLLW"))
    S = 1000 + 2 * A
    E0, N1 = te * 1000 - A, (tn + 1) * 1000 + A
    tr = from_origin(E0, N1, 1.0, 1.0)
    bbox = (E0, N1 - S, E0 + S, N1)
    name = tname(reg, te, tn)

    def isect(b):
        return not (b[2] < bbox[0] or b[0] > bbox[2] or b[3] < bbox[1] or b[1] > bbox[3])

    # ---- coarse 10 m masks (sim local frame) resampled to this grid
    m = np.load(f"{WORK}/{reg}_mask10.npz")
    mtr = from_origin(float(m["e_left"]), float(m["n_top"]), 10.0, 10.0)

    def from10(a, fill):
        out = np.full((S, S), fill, np.float32)
        reproject(a.astype(np.float32), out, src_transform=mtr, src_crs=R["local"], dst_transform=tr, dst_crs=U, resampling=Resampling.nearest)
        return out
    lake10 = from10(m["lake"], 0) > 0.5
    band10 = from10(m["band"], 0) > 0.5
    dist10 = from10(np.where(m["lake"], 0, m["dist"]), 1e6)
    distw10 = from10(m["distw"], 0)
    lake_hint = ndimage.binary_dilation(lake10, iterations=40)

    # ---- bare earth: USGS 3DEP 1 m DEM (same UTM zone, NAVD88)
    dtm = np.full((S, S), np.nan, np.float32)
    for d in P["dem"]:
        if not isect(d["bbox"]):
            continue
        tmp = np.full((S, S), np.nan, np.float32)
        with rasterio.open(d["url"]) as s:
            reproject(rasterio.band(s, 1), tmp, dst_transform=tr, dst_crs=U, src_nodata=s.nodata, dst_nodata=np.nan, resampling=Resampling.bilinear)
        dtm = np.where(np.isnan(dtm), tmp, dtm)

    has_land = bool((band10 & ~lake10).any())

    # ---- imagery at 0.5 m (cover) and 1 m (features): NAIP 2022 R, G, B, NIR
    tr5 = from_origin(E0, N1, 0.5, 0.5)
    img5 = np.zeros((4, 2 * S, 2 * S), np.float32); got5 = np.zeros((2 * S, 2 * S), bool)
    if has_land:
        for f in P["naip"]:
            if not isect(f["bbox"]):
                continue
            tmp = np.zeros((4, 2 * S, 2 * S), np.uint8)
            with rasterio.open(f["path"]) as s:
                reproject(rasterio.band(s, [1, 2, 3, 4]), tmp, dst_transform=tr5, dst_crs=U, dst_nodata=0, resampling=Resampling.bilinear, num_threads=2)
            ok = tmp.max(axis=0) > 0
            put = ok & ~got5
            img5[:, put] = tmp[:, put]; got5 |= ok
    img = img5.reshape(4, S, 2, S, 2).mean(axis=(2, 4)); wsum = got5.reshape(S, 2, S, 2).any(axis=(1, 3))
    red, grn, blu, nir = img
    ndvi = np.where(wsum, (nir - red) / np.maximum(nir + red, 1), 0)
    bright = (red + grn + blu) / 3

    ccap = None
    if reg == "GalvestonBay":
        ccap = np.zeros((2 * S, 2 * S), np.uint8)
        with rasterio.open(CCAP) as s:
            reproject(rasterio.band(s, 1), ccap, dst_transform=tr5, dst_crs=U, resampling=Resampling.nearest)
        ccap1 = ccap[::2, ::2]

    # ---- lidar points (USGS 3DEP EPT, EPSG:3857), only where there is land in the band
    to3857 = tf(reg, U, "EPSG:3857")
    X3, Y3 = to3857.transform([bbox[0], bbox[2], bbox[0], bbox[2]], [bbox[1], bbox[1], bbox[3], bbox[3]])
    qb = (min(X3) - 5, min(Y3) - 5, max(X3) + 5, max(Y3) + 5)
    parts = []
    if has_land:
        for nm in R["ept"]:
            b = ept.meta(nm)["boundsConforming"]
            if b[3] < qb[0] or b[0] > qb[2] or b[4] < qb[1] or b[1] > qb[3]:
                continue
            X, Y, Z, Cl, RN, NR = ept.query(nm, qb)
            if len(X):
                parts.append((X, Y, Z, Cl))
            if len(X) > 0.6 * S * S:
                break
    if parts:
        X = np.concatenate([p[0] for p in parts]); Y = np.concatenate([p[1] for p in parts])
        Z = np.concatenate([p[2] for p in parts]).astype(np.float32); Cl = np.concatenate([p[3] for p in parts])
        Ee, Nn = tf(reg, "EPSG:3857", U).transform(X, Y)
        r_ = np.floor(N1 - Nn).astype(np.int64); c_ = np.floor(Ee - E0).astype(np.int64)
        ok = (r_ >= 0) & (r_ < S) & (c_ >= 0) & (c_ < S) & ~np.isin(Cl, [7, 18])
        r_, c_, Z, Cl, Ee, Nn = r_[ok], c_[ok], Z[ok], Cl[ok], Ee[ok], Nn[ok]
    else:
        r_ = c_ = np.zeros(0, np.int64); Z = np.zeros(0, np.float32); Cl = np.zeros(0, np.uint8); Ee = Nn = np.zeros(0)
    lin = r_ * S + c_
    dsm = np.full(S * S, -1e9, np.float32); np.maximum.at(dsm, lin, Z); dsm = dsm.reshape(S, S)
    has_pts = dsm > -1e8
    dsm = np.where(has_pts, dsm, dtm)
    ndsm = np.nan_to_num(dsm - dtm, nan=0.0)
    w9 = np.zeros(S * S, np.int32); np.add.at(w9, lin[Cl == 9], 1)
    pond = ndimage.binary_closing(w9.reshape(S, S) > 0, iterations=2)  # lidar water returns (ponds, canals) inland too
    g = Cl == 2
    S2 = S // 2 + 1
    gl = (r_[g] // 2) * S2 + c_[g] // 2
    cnt = np.bincount(gl, minlength=S2 * S2); s1 = np.bincount(gl, Z[g], S2 * S2); s2 = np.bincount(gl, Z[g].astype(np.float64) ** 2, S2 * S2)
    var = np.where(cnt >= 4, s2 / np.maximum(cnt, 1) - (s1 / np.maximum(cnt, 1)) ** 2, np.nan).reshape(S2, S2)
    gy, gx = np.gradient(np.nan_to_num(dtm))
    slope = np.hypot(gx, gy)
    rough = np.nan_to_num(np.sqrt(np.clip(np.kron(var, np.ones((2, 2)))[:S, :S] - (slope * 0.58) ** 2, 0, None)), nan=0.0)

    # ---- water (main lake / bay only)
    if reg == "RayHubbard":
        lv = float(np.nanmedian(dtm[lake10])) if lake10.sum() > 500 and np.isfinite(dtm[lake10]).any() else float(m["level"])
        water = (dtm <= lv + 0.10) & lake_hint
    else:
        water = np.isin(ccap1, [21, 22, 23]) & lake_hint
        lv = float(np.nanmedian(dtm[water])) if water.sum() > 500 and np.isfinite(dtm[water]).any() else -0.5
    water |= lake10 & np.isnan(dtm)
    land = ~water
    dw, (ir, ic) = ndimage.distance_transform_edt(land, return_indices=True)

    # ---- buildings
    core = (te * 1000, tn * 1000, (te + 1) * 1000, (tn + 1) * 1000)
    blds = [b for b in P["buildings"] if isect(b["geom"].bounds)]
    bid = features.rasterize(((b["geom"], i + 1) for i, b in enumerate(blds)), out_shape=(S, S), transform=tr, dtype="int32") if blds else np.zeros((S, S), np.int32)
    bmask = bid > 0
    recs = []
    if blds:
        pb = bid[r_, c_]
        order = np.argsort(pb, kind="stable"); pbs = pb[order]
        starts = np.searchsorted(pbs, np.arange(1, len(blds) + 2))
        for i, b in enumerate(blds):
            c = b["geom"].centroid
            if not (core[0] <= c.x < core[2] and core[1] <= c.y < core[3]):
                continue
            sel = order[starts[i]:starts[i + 1]]
            sel = sel[ndvi[r_[sel], c_[sel]] < 0.2]  # drop returns on green (tree crowns over the roof)
            recs.append(roof(b, Ee[sel], Nn[sel], Z[sel], dtm, red, grn, blu, wsum, bid == i + 1))

    # ---- trees
    trees = []
    if has_land:
        veg = (ndvi > 0.12) & ~ndimage.binary_dilation(bmask, iterations=1) & land & has_pts
        chm = np.where(veg, ndsm, 0).astype(np.float32)
        chs = ndimage.gaussian_filter(chm, 0.8)
        peaks = (chs == ndimage.maximum_filter(chs, size=5)) & (chs >= 3.0) & (chm >= 3.0)
        mk, nmk = ndimage.label(peaks)
        if nmk:
            seg = watershed(-chs, mk, mask=chs > 1.8)
            areas = np.bincount(seg.ravel(), minlength=nmk + 1)
            idx = np.arange(1, nmk + 1)
            hts = ndimage.maximum(chm, seg, idx)
            brs = ndimage.mean(bright, seg, idx)
            com = ndimage.center_of_mass(peaks, mk, idx)
            for k in range(nmk):
                pr, pc = com[k]
                e_, n_ = E0 + pc + 0.5, N1 - pr - 0.5
                if not (core[0] <= e_ < core[2] and core[1] <= n_ < core[3]):
                    continue
                ri_, ci_ = int(pr), int(pc)
                if not band10[ri_, ci_]:
                    continue
                h = float(hts[k]); rad = min(math.sqrt(areas[k + 1] / math.pi), 0.6 * h + 2, 14.0)
                if rad < 1.0:
                    continue
                # eastern red cedar: narrow, dark evergreen crowns on the lake. Everything else stays unknown.
                sp = "eastern_red_cedar" if (rad < 0.28 * h and h < 14 and brs[k] < 62 and reg == "RayHubbard") else "unknown"
                gz = dtm[ri_, ci_]
                trees.append(dict(e=e_, n=n_, ground_z=round(float(gz), 2) if np.isfinite(gz) else None, height_m=round(h, 1), crown_radius_m=round(float(rad), 1),
                                  species_guess=sp, ndvi=round(float(ndvi[ri_, ci_]), 2), dist_to_water_m=round(float(dist10[ri_, ci_]), 0)))

    # ---- shore classification
    shore_px = land & (dw <= 1.5) & ndimage.binary_dilation(lake10, iterations=3)
    sr, sc = np.nonzero(shore_px)
    scls = np.zeros((S, S), np.int8) - 1
    crest_d = np.zeros((S, S), np.float32)
    srough = np.zeros((S, S), np.float32)
    if len(sr) and has_land:
        nr_ = (sr - ir[sr, sc]).astype(np.float32); nc_ = (sc - ic[sr, sc]).astype(np.float32)
        nn = np.maximum(np.hypot(nr_, nc_), 1e-3); nr_ /= nn; nc_ /= nn
        wl = dtm[ir[sr, sc], ic[sr, sc]]; wl = np.where(np.isfinite(wl), wl, lv)
        samp = lambda a, ks, o=0: np.stack([ndimage.map_coordinates(a, [sr + nr_ * k, sc + nc_ * k], order=o, mode="nearest") for k in ks])
        prof = samp(np.nan_to_num(dtm, nan=lv), range(9), 1)
        rgh = samp(rough, (1, 2, 3)).mean(0); nd = samp(ndvi, (1, 2, 3)).mean(0); br = samp(bright, (1, 2, 3)).mean(0); rb = samp(red - blu, (1, 2, 3)).mean(0)
        rise2 = prof[2] - wl; flat24 = np.abs(prof[5] - prof[2]); slope05 = (prof[5] - prof[0]) / 5.0
        cls = np.zeros(len(sr), np.int8)
        bulk = (rise2 >= 0.55) & (prof[1] - wl >= 0.4) & (flat24 <= 0.35)
        rip = ~bulk & (slope05 >= 0.15) & (slope05 <= 1.5) & (nd < 0.15) & ((rb < 22) | (rgh >= 0.07))
        beach = ~bulk & ~rip & (np.abs(slope05) < 0.12) & (nd < 0.10) & (br > 120)
        cls[rip] = 1; cls[bulk] = 2; cls[beach] = 3
        scls[sr, sc] = cls; crest_d[sr, sc] = np.argmax(prof, axis=0); srough[sr, sc] = rgh
    shore = shore_lines(water, lake10, scls, crest_d, srough, dtm, lv, E0, N1, S, core) if has_land else []

    # ---- outputs: core 1000 x 1000 (1 m) and 2000 x 2000 (0.5 m)
    c0, c1 = A, A + 1000
    valid = band10 | (land & (dist10 <= 1010)) | (water & (distw10 <= 1010))
    otr = from_origin(te * 1000, (tn + 1) * 1000, 1.0, 1.0)
    out_dem = np.where(valid & np.isfinite(dtm), dtm, -9999).astype(np.float32)[c0:c1, c0:c1]
    out_dsm = np.where(valid & np.isfinite(dsm), dsm, -9999).astype(np.float32)[c0:c1, c0:c1]
    wtif(f"{OUT}/{reg}/dem/{name}.tif", out_dem, otr, U, -9999, predictor=3)
    if has_land:
        wtif(f"{OUT}/{reg}/dsm/{name}.tif", out_dsm, otr, U, -9999, predictor=3)

    # cover at 0.5 m: imagery cues at 0.5 m, lidar heights and shore classes from the 1 m grid
    up = lambda a: np.kron(a, np.ones((2, 2), a.dtype))
    r5, g5, b5, n5 = img5
    ndvi5 = np.where(got5, (n5 - r5) / np.maximum(n5 + r5, 1), 0); br5 = (r5 + g5 + b5) / 3
    grey5 = (np.abs(r5 - g5) < 14) & (np.abs(g5 - b5) < 16)
    nds5 = up(ndsm.astype(np.float32))
    cov = np.full((2 * S, 2 * S), CV["grass"], np.uint8)
    nonveg = ndvi5 < 0.12
    cov[nonveg & (ndvi5 < 0.04) & ~grey5 & (r5 > b5 + 18)] = CV["bare_clay"]
    gm = nonveg & grey5
    cov[gm] = np.where(br5[gm] >= 135, CV["concrete"], CV["asphalt"])
    vg = ~nonveg
    cov[vg & (nds5 >= 0.6) & (nds5 < 2.5)] = CV["scrub"]
    cov[vg & (nds5 >= 2.5)] = CV["tree_canopy"]
    wat5 = up(water)
    if ccap is not None:
        cov[(ccap == 19) & ~wat5] = CV["sand"]
        im = (ccap == 2) & ~wat5 & nonveg
        cov[im] = np.where(br5[im] >= 135, CV["concrete"], CV["asphalt"])
    if (scls >= 0).any():
        dsh, (jr, jc) = ndimage.distance_transform_edt(scls < 0, return_indices=True)
        nc = scls[jr, jc]
        rip1 = land & (nc == 1) & (dsh <= np.maximum(crest_d[jr, jc], 2))
        blk1 = land & (nc == 2) & (dsh <= 1)
        sand1 = land & (nc == 3) & (dsh <= 12) & (ndvi < 0.12)
        cov[up(sand1)] = CV["sand"]; cov[up(rip1)] = CV["riprap_rock"]; cov[up(blk1)] = CV["concrete"]
    if blds:
        bm5 = features.rasterize(((b["geom"], 1) for b in blds), out_shape=(2 * S, 2 * S), transform=tr5, dtype="uint8") > 0
        cov[bm5] = CV["building"]
    cov[up(pond & ~bmask)] = CV["water"]
    cov[wat5] = CV["water"]
    cov[~up(valid)] = 255
    cov[~got5 & ~wat5] = 255
    otr5 = from_origin(te * 1000, (tn + 1) * 1000, 0.5, 0.5)
    if has_land:
        wtif(f"{OUT}/{reg}/cover/{name}.tif", cov[2 * c0:2 * c1, 2 * c0:2 * c1], otr5, U, 255)
    info = dict(name=name, utm_epsg=R["utm_epsg"], e_min=te * 1000, n_min=tn * 1000, points=int(len(Z)), has_land=has_land,
                valid_frac=round(float((out_dem > -9999).mean()), 4), water_level_navd88=round(float(lv), 3))
    os.makedirs(f"{WORK}/{reg}/tiles", exist_ok=True)
    pickle.dump(dict(info=info, buildings=recs, trees=trees, shore=shore), open(f"{WORK}/{reg}/tiles/{name}.pkl", "wb"))
    return info


def roof(b, Ee, Nn, Z, dtm, red, grn, blu, wsum, inmask):
    g = b["geom"]
    rr, cc = np.nonzero(inmask)
    gz = float(np.nanmedian(dtm[rr, cc])) if len(rr) and np.isfinite(dtm[rr, cc]).any() else float("nan")
    inner = ndimage.binary_erosion(inmask, iterations=1)
    pr, pc = np.nonzero(inner if inner.sum() >= 4 else inmask)
    colour = "#%02x%02x%02x" % tuple(int(np.median(ch[pr, pc])) for ch in (red, grn, blu)) if len(pr) and wsum[pr, pc].any() else None
    mrr = g.minimum_rotated_rectangle
    xs, ys = np.array(mrr.exterior.coords).T
    d1 = np.hypot(xs[1] - xs[0], ys[1] - ys[0]); d2 = np.hypot(xs[2] - xs[1], ys[2] - ys[1])
    if d1 >= d2:
        ax = np.array([xs[1] - xs[0], ys[1] - ys[0]]) / max(d1, 1e-6); L, W = float(d1), float(d2)
    else:
        ax = np.array([xs[2] - xs[1], ys[2] - ys[1]]) / max(d2, 1e-6); L, W = float(d2), float(d1)
    az = (math.degrees(math.atan2(ax[0], ax[1])) + 180) % 180  # grid azimuth (UTM grid north), deg clockwise
    ctr = np.array([mrr.centroid.x, mrr.centroid.y])
    rec = dict(b=b, area_m2=round(g.area, 1), length_m=round(L, 2), width_m=round(W, 2), long_axis_az=az,
               ground_z=round(gz, 2) if np.isfinite(gz) else None, roof_colour=colour)
    h = Z - gz if np.isfinite(gz) else Z * 0
    sel = h > 1.5
    n = int(sel.sum())
    rec["lidar_points"] = n
    if not np.isfinite(gz) or n < max(8, 0.125 * g.area):
        rec.update(roof_type=None, roof_detail="unknown", eave_m=None, height_m=None, pitch_deg=None, ridge_az=None, fit_rms=None, lidar="missing_or_sparse", roof_grid=None)
        return rec
    x, y, zz = Ee[sel] - ctr[0], Nn[sel] - ctr[1], h[sel]
    if n > 1500:
        k = np.random.default_rng(0).choice(n, 1500, replace=False); x, y, zz = x[k], y[k], zz[k]
    u = x * ax[0] + y * ax[1]; v = -x * ax[1] + y * ax[0]
    lo, hi = np.percentile(zz, [3, 98]); k = (zz >= lo - 0.3) & (zz <= hi + 0.3); u, v, zz = u[k], v[k], zz[k]
    one = np.ones_like(zz)

    def lsq(cols):
        M = np.column_stack(cols); w = np.ones(len(zz), bool)
        for _ in range(3):
            coef, *_ = np.linalg.lstsq(M[w], zz[w], rcond=None)
            res = zz - M @ coef
            rms = float(np.sqrt(np.mean(res[w] ** 2)))
            w = np.abs(res) <= max(2.5 * rms, 0.25)
        return coef, rms
    fits = {}
    c, r = lsq([one]); fits["flat"] = (r, c, None)
    c, r = lsq([one, u, v]); fits["shed"] = (r, c, None)
    for nm, fn in (("gable", lambda o: [one, W / 2 - np.abs(v - o)]), ("gable_x", lambda o: [one, L / 2 - np.abs(u - o)]),
                   ("hip", lambda o: [one, np.minimum(W / 2 - np.abs(v - o), L / 2 - np.abs(u))])):
        span = (W if nm != "gable_x" else L) / 4
        bestr = None
        for o in np.linspace(-span, span, 9):
            c, r = lsq(fn(o))
            if c[1] > 0.05 and (bestr is None or r < bestr[0]):
                bestr = (r, c, o)
        if bestr:
            fits[nm] = bestr
    slope_shed = math.hypot(*fits["shed"][1][1:])
    pen = {"flat": 0.0, "shed": 0.02, "gable": 0.03, "gable_x": 0.03, "hip": 0.04}
    if fits["flat"][0] < 0.18 or (slope_shed < 0.05 and fits["shed"][0] < 0.25):
        shape = "flat"
    else:
        shape = min((k for k in fits if k != "flat"), key=lambda k: fits[k][0] + pen[k])
    r, c, o = fits[shape]
    ridge_az = None; pitch = None
    if shape == "flat":
        eave = ridge = float(np.percentile(zz, 90))
    elif shape == "shed":
        pitch = math.degrees(math.atan(slope_shed)); eave = float(np.percentile(zz, 5)); ridge = float(np.percentile(zz, 98))
    else:
        eave = float(c[0]); pitch = math.degrees(math.atan(c[1]))
        ridge = float(c[0] + c[1] * (W / 2 if shape != "gable_x" else L / 2))
        ridge_az = az if shape in ("gable", "hip") else (az + 90) % 180
    # roof height grid in the footprint's axes, 1 m cells, decimetres above ground
    nu, nv = int(math.ceil(L)), int(math.ceil(W))
    iu = np.clip((u + L / 2).astype(int), 0, nu - 1); iv = np.clip((v + W / 2).astype(int), 0, nv - 1)
    grid = np.zeros((nv, nu), np.float32); cntg = np.zeros((nv, nu), np.int32)
    np.add.at(grid, (iv, iu), zz); np.add.at(cntg, (iv, iu), 1)
    have = cntg > 0
    grid = np.where(have, grid / np.maximum(cntg, 1), 0)
    if have.any() and not have.all():
        _, (gi, gj) = ndimage.distance_transform_edt(~have, return_indices=True)
        grid = grid[gi, gj]
    gl = shapely.affinity.affine_transform(g, [ax[0], ax[1], -ax[1], ax[0], -(ctr[0] * ax[0] + ctr[1] * ax[1]) + L / 2, -(-ctr[0] * ax[1] + ctr[1] * ax[0]) + W / 2])
    fp = features.rasterize([(gl, 1)], out_shape=(nv, nu), transform=rasterio.transform.Affine(1, 0, 0, 0, 1, 0), dtype="uint8")
    q = np.where(fp > 0, np.clip(np.round(grid * 10), 1, 255), 0).astype(np.uint8)
    rec["roof_grid"] = dict(cols_u=nu, rows_v=nv, centre_utm=[round(float(ctr[0]), 2), round(float(ctr[1]), 2)], b64=base64.b64encode(q.tobytes()).decode())
    detail = "gable" if shape == "gable_x" else shape
    if r > max(0.35, 0.22 * (ridge - eave)):
        rec["roof_fallback"] = detail
        detail = "complex"
    roof_type = detail if detail in ("flat", "gable", "hip", "complex") else "complex"  # shed -> complex; roof_detail keeps "shed"
    rec.update(roof_type=roof_type, roof_detail=detail, eave_m=round(max(eave, 2.0), 2), height_m=round(max(ridge, eave, 2.0), 2),
               pitch_deg=round(pitch, 1) if pitch is not None else None, ridge_az=ridge_az, fit_rms=round(r, 3), lidar="ok")
    return rec


def shore_lines(water, lake10, scls, crest_d, srough, dtm, lv, E0, N1, S, core):
    main = water & ndimage.binary_dilation(lake10, iterations=3)
    if not main.any() or (scls < 0).all():
        return []
    sm = ndimage.binary_opening(main, iterations=1)
    dsh, (jr, jc) = ndimage.distance_transform_edt(scls < 0, return_indices=True)
    out = []
    for cnt in find_contours(sm.astype(np.float32), 0.5):
        if len(cnt) < 8:
            continue
        seg = np.diff(cnt, axis=0); dd = np.r_[0, np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))]
        if dd[-1] < 8:
            continue
        s = np.arange(0, dd[-1], 1.0)
        pr = np.interp(s, dd, cnt[:, 0]); pc = np.interp(s, dd, cnt[:, 1])
        ri, ci = np.clip(np.round(pr).astype(int), 0, S - 1), np.clip(np.round(pc).astype(int), 0, S - 1)
        cls = np.where(dsh[ri, ci] <= 3, scls[jr[ri, ci], jc[ri, ci]], 0)
        oh = ndimage.uniform_filter1d(np.stack([(cls == k).astype(float) for k in range(4)]), 9, axis=1, mode="nearest")
        cls = oh.argmax(0)
        e_ = E0 + pc; n_ = N1 - pr
        inc = (e_ >= core[0]) & (e_ < core[2]) & (n_ >= core[1]) & (n_ < core[3])
        cls = np.where(inc, cls, -1)
        i = 0
        while i < len(cls):
            j = i
            while j + 1 < len(cls) and cls[j + 1] == cls[i]:
                j += 1
            k = int(cls[i])
            if k == 2 and j - i + 1 >= 8 and math.hypot(pr[j] - pr[i], pc[j] - pc[i]) < 0.85 * (j - i):
                k = 0  # wiggly vertical edge: eroded bank, not a bulkhead
            if k > 0 and j - i + 1 >= 8:
                idx = np.arange(i, j + 1)
                sri, sci = jr[ri[idx], ci[idx]], jc[ri[idx], ci[idx]]
                crest = []
                for rr_, cc_ in zip(sri[::2], sci[::2]):
                    w = max(int(crest_d[rr_, cc_]), 1)
                    zz = dtm[max(rr_ - w, 0):rr_ + w + 1, max(cc_ - w, 0):cc_ + w + 1]
                    if np.isfinite(zz).any():
                        crest.append(np.nanmax(zz))
                keep = list(idx[::2]) + ([idx[-1]] if (len(idx) - 1) % 2 else [])
                out.append(dict(type=SHORE_TYPES[k], length_m=float(j - i + 1), water_z=round(float(lv), 2),
                                crest_z=round(float(np.median(crest)), 2) if crest else None,
                                width_m=round(float(np.median(crest_d[sri, sci])), 1), roughness_m=round(float(np.median(srough[sri, sci])), 3),
                                utm=[[round(float(e_[q]), 2), round(float(n_[q]), 2)] for q in keep]))
            i = j + 1
    return out


if __name__ == "__main__":
    print(run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
