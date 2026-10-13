"""Shared config for the G2 shore datasets (cloud-side data prep)."""
import os, json, math
import numpy as np
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.jp2,.TIF")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
from pyproj import Transformer

WORK = "/tmp/g2/work"
SRC = "/tmp/g2/src"
OUT = "/mnt/project-files/sailing-sim-g2"
TNM = "https://prd-tnm.s3.amazonaws.com"
TNRIS = "https://tnris-data-warehouse.s3.us-east-1.amazonaws.com"
EPT = "https://usgs-lidar-public.s3.amazonaws.com"

REGIONS = {
    "RayHubbard": dict(
        local="+proj=tmerc +lat_0=32.8233 +lon_0=-96.5 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m +no_defs",
        # sim's existing grid (Content/TerrainData/RayHubbard.json): north/east extent in the local frame
        north=(-4795.0, -4795.0 + 5434 * 5.0), east=(-11235.0, -11235.0 + 3277 * 5.0),
        dem13=["n33w097", "n34w097"],
        dem1m_project="TX_Pecos_Dallas_2018_D19", utm_epsg=26914,
        ept=["TX_Pecos_Dallas_B3_2018"],
        cell=1.0, tile_px=1024,
        seed_xy=(630.0, -560.0),  # (north, east) open water off Rush Creek
        zero_note="sim Z=0 is the conservation pool 435.5 ft NGVD29",
    ),
    "GalvestonBay": dict(
        local="+proj=tmerc +lat_0=29.5446 +lon_0=-95.0193 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m +no_defs",
        north=(-27600.0, -27600.0 + 3651 * 10.0), east=(-9250.0, -9250.0 + 4356 * 10.0),
        dem13=["n30w095", "n30w096"],
        dem1m_project="TX_CoastalRegion_2018_A18", utm_epsg=26915,
        ept=["TX_Coastal_B3_2018", "TX_Coastal_B1_2018"],
        cell=2.0, tile_px=1024,
        seed_xy=(0.0, 3000.0),
        zero_note="sim Z=0 is MLLW; MLLW height = NAVD88 height + 0.094 m (GalvestonBay.json navd88_to_mllw_m)",
    ),
}


def tf(region, src, dst):
    r = REGIONS[region]
    a = r["local"] if src == "local" else src
    b = r["local"] if dst == "local" else dst
    return Transformer.from_crs(a, b, always_xy=True)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
