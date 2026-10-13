"""Step 1: coarse (10 m) water mask and shore band per region from the USGS 3DEP 1/3 arc-second DEM (+ NOAA C-CAP water on the coast)."""
import sys, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from scipy import ndimage
from common import *

reg = sys.argv[1]; R = REGIONS[reg]
C = 10.0
n0, n1 = R["north"]; e0, e1 = R["east"]
H, W = int((n1 - n0) / C), int((e1 - e0) / C)
dst_t = from_origin(e0, n1, C, C)  # row 0 = north edge
dem = np.full((H, W), np.nan, np.float32)
for t in R["dem13"]:
    url = f"/vsicurl/{TNM}/StagedProducts/Elevation/13/TIFF/current/{t}/USGS_13_{t}.tif"
    with rasterio.open(url) as s:
        tmp = np.full((H, W), np.nan, np.float32)
        reproject(rasterio.band(s, 1), tmp, dst_transform=dst_t, dst_crs=R["local"], dst_nodata=np.nan, resampling=Resampling.bilinear)
        dem = np.where(np.isnan(dem), tmp, dem)
print(reg, "dem", np.nanmin(dem), np.nanmax(dem))
sr = int((n1 - R["seed_xy"][0]) / C); sc = int((R["seed_xy"][1] - e0) / C)
if reg == "RayHubbard":
    level = float(np.nanmedian(dem[sr-5:sr+5, sc-5:sc+5]))
    water = dem <= level + 0.15
else:
    # NOAA C-CAP 2020 1 m land cover, open water / aquatic bed classes, sampled at 10 m (mode-ish via nearest)
    cc = np.zeros((H, W), np.uint8)
    with rasterio.open(f"/vsicurl/{TNRIS}/LCD/collection/noaa-2020-ccap-landcover-1m/items/lcr/noaa-2020-ccap-landcover-1m_11111_20240612.tif") as s:
        reproject(rasterio.band(s, 1), cc, dst_transform=dst_t, dst_crs=R["local"], resampling=Resampling.mode)
    np.save(f"{WORK}/{reg}_ccap10.npy", cc)
    level = 0.0
    water = np.isin(cc, [21, 22, 23]) | (np.isnan(dem) & (cc == 0))
lab, n = ndimage.label(water)
sizes = ndimage.sum(water, lab, range(1, n + 1))
keep = np.zeros(n + 1, bool); keep[1:] = sizes * C * C > 1e6  # water bodies over 1 km2
keep[lab[sr, sc]] = True
lake = keep[lab]
land = ~lake
dist = ndimage.distance_transform_edt(land) * C      # land -> nearest main water
distw = ndimage.distance_transform_edt(lake) * C     # water -> nearest land
band = (land & (dist <= 1010.0)) | (lake & (distw <= 1010.0))
print(reg, "level", level, "lake km2", lake.sum() * C * C / 1e6, "band land km2", (band & land).sum() * C * C / 1e6)
np.savez_compressed(f"{WORK}/{reg}_mask10.npz", dem=dem, lake=lake, band=band, dist=dist, distw=distw, n_top=n1, e_left=e0, cell=C, level=level)
from PIL import Image
img = np.zeros((H, W, 3), np.uint8); img[band] = (200, 170, 90); img[lake & band] = (40, 80, 160)
Image.fromarray(img).save(f"{WORK}/{reg}_mask10.png")
