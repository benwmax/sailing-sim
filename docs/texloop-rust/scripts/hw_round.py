import sys,os,json,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from hwport import *; from lab import *; from rustport import lin_to_srgb8
from PIL import Image
out=sys.argv[1]; os.makedirs(out,exist_ok=True); res={}
for surf in (3,12):
    for lv in LEVELS:
        col,metal,mask=shade(surf,lv)
        Image.fromarray(lin_to_srgb8(col)).save(f'{out}/s{surf}_{lv}.png')
        lab=lin_to_lab(col); C=np.hypot(lab[...,1],lab[...,2]); h=np.degrees(np.arctan2(lab[...,2],lab[...,1]))
        core=(mask>0.9) if surf==12 else (mask>0.5)
        r=dict(cover_pct=round(100*float((mask>0.5).mean()),2),mean_mask=round(float(mask.mean()),3))
        if core.sum()>50: v=lab[core]; r['rust_lab']=v.mean(0).round(1).tolist(); r['dE_core']=round(de76(v.mean(0),[30.8,18.4,25.0]),1); r['sdL']=round(float(v[:,0].std()),1); r['dE_stain']=round(de76(v.mean(0),[62.9,6.3,10.0]),1)
        res[f's{surf}_{lv}']=r; print(f's{surf}_{lv}',r)
json.dump(res,open(f'{out}/scores.json','w'),indent=1)
