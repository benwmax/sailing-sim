import sys, os, pickle, traceback, time
from multiprocessing import Pool
from common import *
reg = sys.argv[1]; nproc = int(sys.argv[2]) if len(sys.argv) > 2 else 4
P = pickle.load(open(f"{WORK}/{reg}_prep.pkl", "rb"))
def job(t):
    import tile
    name = tile.tname(reg, *t)
    if os.path.exists(f"{WORK}/{reg}/tiles/{name}.pkl") and "--force" not in sys.argv:
        return name, "skip"
    for a in range(3):
        try:
            t0 = time.time(); tile.run(reg, *t); return name, f"ok {time.time()-t0:.0f}s"
        except Exception as e:
            err = traceback.format_exc()
            time.sleep(5)
    return name, "FAIL " + err[-600:]
with Pool(nproc, maxtasksperchild=8) as p:
    for i, (n, s) in enumerate(p.imap_unordered(job, P["tiles"])):
        print(i + 1, len(P["tiles"]), n, s, flush=True)
