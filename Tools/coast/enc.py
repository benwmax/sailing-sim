"""Reads NOAA ENC (S-57) cells into plain Python rows: {attribute: value, ..., 'geom': shapely geometry}."""
import glob
import warnings

import pyogrio
import pyogrio.raw
import shapely

warnings.filterwarnings("ignore")


def layers(path):
    return [name for name, _ in pyogrio.list_layers(path)]


def read(path, layer):
    meta, fids, geom, fields = pyogrio.raw.read(path, layer=layer)
    names = meta["fields"]
    rows = []
    count = len(geom) if geom is not None else (len(fields[0]) if len(fields) else 0)
    for i in range(count):
        row = {names[j]: fields[j][i] for j in range(len(names))}
        row["geom"] = shapely.from_wkb(geom[i]) if geom is not None and geom[i] is not None else None
        row["cell"] = path.rsplit("/", 1)[-1][:-4]
        rows.append(row)
    return rows


def cells(root):
    """Cell paths, most detailed (highest usage band, then largest scale) last so they overwrite coarser ones."""
    return sorted(glob.glob(f"{root}/ENC_ROOT/*/*.000"), key=lambda p: p.rsplit("/", 1)[-1][2])
