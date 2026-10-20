"""GeoTIFF elevation rasters for the bakes, without GDAL or imagecodecs.

read(path) returns (array float64, georef) where georef maps pixel centres to lon/lat (or any CRS the file is in):
    x = georef.x0 + col * georef.dx,  y = georef.y0 + row * georef.dy   (dy is negative for north-up files)
It reads the georeferencing from the file's own tags (ModelTiepoint + ModelPixelScale, or ModelTransformation) and
honours RasterPixelIsPoint (the Copernicus DEM) versus PixelIsArea (USGS, EMODnet): CLAUDE.md's bake gotcha, the export
service widens the requested box, so never assume the box you asked for.

Copernicus DEM COGs use deflate with the floating-point predictor (3), which tifffile only decodes through imagecodecs;
decode_float_predictor undoes it here (byte planes, big-endian, horizontally differenced per row).
"""
import collections
import zlib

import numpy as np
import tifffile
from scipy import ndimage

Georef = collections.namedtuple("Georef", "x0 y0 dx dy")


def _geokeys(page):
    keys = {}
    if "GeoKeyDirectoryTag" in page.tags:
        v = page.tags["GeoKeyDirectoryTag"].value
        for i in range(4, len(v), 4):
            keys[v[i]] = v[i + 3]
    return keys


def decode_float_predictor(raw, rows, cols, bytes_per_sample=4):
    """Undoes TIFF predictor 3 on one decompressed tile or strip: rows x cols samples, little-endian float out."""
    b = np.frombuffer(raw, np.uint8)[:rows * cols * bytes_per_sample].reshape(rows, cols * bytes_per_sample)
    b = np.cumsum(b, axis=1, dtype=np.uint8)            # horizontal differencing wraps mod 256
    planes = b.reshape(rows, bytes_per_sample, cols)     # most significant byte plane first
    return np.ascontiguousarray(planes.transpose(0, 2, 1)).view(">f4").reshape(rows, cols).astype(np.float32)


def _asarray(page):
    if page.predictor != 3:
        return page.asarray()
    if page.compression not in (8, 32946):
        raise ValueError(f"floating-point predictor with compression {page.compression} is not handled")
    out = np.zeros(page.shape[:2], np.float32)
    fh = page.parent.filehandle
    if page.is_tiled:
        th, tw = page.tilelength, page.tilewidth
        across = (page.imagewidth + tw - 1) // tw
        for i, (off, n) in enumerate(zip(page.dataoffsets, page.databytecounts)):
            if n == 0:
                continue
            fh.seek(off)
            tile = decode_float_predictor(zlib.decompress(fh.read(n)), th, tw)
            r0, c0 = (i // across) * th, (i % across) * tw
            r1, c1 = min(r0 + th, out.shape[0]), min(c0 + tw, out.shape[1])
            out[r0:r1, c0:c1] = tile[:r1 - r0, :c1 - c0]
    else:
        rps = page.rowsperstrip
        for i, (off, n) in enumerate(zip(page.dataoffsets, page.databytecounts)):
            fh.seek(off)
            r0 = i * rps
            rows = min(rps, out.shape[0] - r0)
            out[r0:r0 + rows] = decode_float_predictor(zlib.decompress(fh.read(n)), rows, out.shape[1])
    return out


def read(path, nodata=None):
    """The first image of a GeoTIFF as float64 (nodata -> NaN) and the georef of its pixel centres."""
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        data = _asarray(page).astype(np.float64)
        if data.ndim == 3:
            data = data[..., 0]
        point = _geokeys(page).get(1025, 1) == 2   # GTRasterTypeGeoKey: 2 = RasterPixelIsPoint
        if "ModelTransformationTag" in page.tags:
            m = page.tags["ModelTransformationTag"].value
            dx, dy, x, y = m[0], m[5], m[3], m[7]
            ti, tj = 0.0, 0.0
        else:
            tie = page.tags["ModelTiepointTag"].value
            scale = page.tags["ModelPixelScaleTag"].value
            ti, tj, x, y = tie[0], tie[1], tie[3], tie[4]
            dx, dy = scale[0], -scale[1]
        if "GDAL_NODATA" in page.tags and nodata is None:
            try:
                nodata = float(str(page.tags["GDAL_NODATA"].value).strip("\x00 "))
            except ValueError:
                nodata = None
    if nodata is not None:
        data[data == nodata] = np.nan
    # The tie point names a raster point (ti, tj): its pixel's corner for PixelIsArea, its centre for PixelIsPoint.
    half = 0.0 if point else 0.5
    x0 = x + (half - ti) * dx
    y0 = y + (half - tj) * dy
    return data, Georef(x0, y0, dx, dy)


def sample(data, ref, xs, ys, order=1, fill=np.nan):
    """Bilinear (order 1) samples at coordinates in the raster's CRS; outside the raster -> fill."""
    fc = (np.asarray(xs) - ref.x0) / ref.dx
    fr = (np.asarray(ys) - ref.y0) / ref.dy
    valid = np.isfinite(data)
    filled = np.where(valid, data, 0.0)
    v = ndimage.map_coordinates(filled, [fr, fc], order=order, mode="nearest")
    w = ndimage.map_coordinates(valid.astype(np.float64), [fr, fc], order=order, mode="nearest")
    out = np.where(w > 0.5, v / np.maximum(w, 1e-9), fill)
    inside = (fr >= -0.5) & (fr <= data.shape[0] - 0.5) & (fc >= -0.5) & (fc <= data.shape[1] - 0.5)
    return np.where(inside, out, fill)
