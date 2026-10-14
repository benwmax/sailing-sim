"""Fetch Overture Maps buildings for each region's bbox (row-group pruning via parquet stats)."""
import pyarrow.fs as pfs, pyarrow.parquet as pq, pyarrow as pa, json, os
from concurrent.futures import ThreadPoolExecutor
from common import *
# Behind an HTTPS proxy that only allows <bucket>.s3.amazonaws.com (cloud sessions), go through it with virtual-host addressing.
_px = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
fs = (pfs.S3FileSystem(anonymous=True, region="us-west-2", proxy_options=_px, endpoint_override="https://s3.amazonaws.com", force_virtual_addressing=True)
      if _px else pfs.S3FileSystem(anonymous=True, region="us-west-2"))
REL = "2026-09-23.1"
base = f"overturemaps-us-west-2/release/{REL}/theme=buildings/type=building/"
files = [f.path for f in fs.get_file_info(pfs.FileSelector(base))]
BB = {"RayHubbard": (-96.64, 32.77, -96.42, 33.03), "GalvestonBay": (-95.13, 29.28, -94.65, 29.64), "GalvestonGulf": (-95.13, 29.19, -94.65, 29.31)}
BB = {k: v for k, v in BB.items() if k in active_regions()}
def rg_hits(path):
    md = pq.ParquetFile(path, filesystem=fs).metadata
    names = [md.schema.column(i).path for i in range(md.num_columns)]
    ix = {n: names.index(n) for n in ("bbox.xmin", "bbox.xmax", "bbox.ymin", "bbox.ymax")}
    out = []
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        st = {k: rg.column(i).statistics for k, i in ix.items()}
        xmin, xmax, ymin, ymax = st["bbox.xmin"].min, st["bbox.xmax"].max, st["bbox.ymin"].min, st["bbox.ymax"].max
        for reg, b in BB.items():
            if xmax >= b[0] and xmin <= b[2] and ymax >= b[1] and ymin <= b[3]:
                out.append((reg, path, g))
    return out
with ThreadPoolExecutor(32) as ex:
    hits = [h for r in ex.map(rg_hits, files) for h in r]
print(len(hits), "row groups")
cols = ["id", "sources", "height", "num_floors", "class", "subtype", "roof_shape", "roof_color", "roof_material", "facade_color", "facade_material", "roof_height", "geometry", "bbox"]
def rd(h):
    reg, path, g = h
    t = pq.ParquetFile(path, filesystem=fs).read_row_group(g, columns=cols)
    b = BB[reg]; bx = t.column("bbox").combine_chunks()
    import pyarrow.compute as pc
    m = pc.and_(pc.and_(pc.greater_equal(bx.field("xmax"), b[0]), pc.less_equal(bx.field("xmin"), b[2])), pc.and_(pc.greater_equal(bx.field("ymax"), b[1]), pc.less_equal(bx.field("ymin"), b[3])))
    return reg, t.filter(m)
res = {r: [] for r in BB}
with ThreadPoolExecutor(16) as ex:
    for reg, t in ex.map(rd, hits):
        if t.num_rows: res[reg].append(t)
for reg, ts in res.items():
    t = pa.concat_tables(ts)
    pq.write_table(t, f"{SRC}/bldg/overture_{reg}.parquet")
    print(reg, t.num_rows)
