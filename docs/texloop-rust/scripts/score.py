"""Rust lane checks on one rendered round: colour (core and stain against the CC0 targets), size, ladder numbers."""
import sys,os,json,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lab import *; from rustport import *
from PIL import Image
d=sys.argv[1]; T=json.load(open(sys.argv[2]))
res={}
def masks(lab):
    C=np.hypot(lab[...,1],lab[...,2]); h=np.degrees(np.arctan2(lab[...,2],lab[...,1]))
    return dict(core=(lab[...,0]<50)&(C>18)&(h>30)&(h<75), stain=(lab[...,0]>50)&(C>8)&(C<30)&(h>35)&(h<85))
for kind in ('old','new'):
    for lv in LEVELS:
        im=np.asarray(Image.open(f'{d}/{kind}_{lv}_close.png').convert('RGB'),dtype=np.float64); lab=srgb8_to_lab(im)
        pan=np.asarray(Image.open(f'{d}/{kind}_{lv}_panel.png').convert('RGB'),dtype=np.float64); plab=srgb8_to_lab(pan)
        bg=np.median(plab.reshape(-1,3),0)
        stained=np.linalg.norm(plab-bg,axis=-1)>3     # visibly stained pixels on the 2 m panel
        r=dict(coverage_pct=round(100*float(stained.mean()),3))
        m=masks(lab)
        for k in ('core','stain'):
            if m[k].sum()>=20:
                v=lab[m[k]]; tgt=T[k]['lab']
                r[k]=dict(n=int(m[k].sum()),lab=v.mean(0).round(1).tolist(),dE=round(de76(v.mean(0),tgt),1),sdL=round(float(v[:,0].std()),1),sd_ok=bool(abs(v[:,0].std()-T[k]['sdL'])<=0.25*T[k]['sdL']+1.5))
        # weeps per metre and their lengths on the panel (4 px/cm): columns with a stained run
        cols=stained.any(0); runs=np.diff(np.concatenate([[0],cols.astype(int),[0]])); starts=np.nonzero(runs==1)[0]; ends=np.nonzero(runs==-1)[0]
        lens=[]; widths=[]
        for s0,e0 in zip(starts,ends):
            ys=np.nonzero(stained[:,s0:e0].any(1))[0]; lens.append((ys.max()-ys.min())/4.0); widths.append((e0-s0)/4.0)
        r['weeps_per_m']=round(len(starts)/2.0,2); r['len_cm']=[round(float(x),1) for x in lens]; r['width_cm']=[round(float(x),2) for x in widths]
        res[f'{kind}_{lv}']=r
json.dump(res,open(f'{d}/scores.json','w'),indent=1)
for k,v in res.items(): print(k,json.dumps(v))
