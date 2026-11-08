import sys,glob,os,json,numpy as np
from PIL import Image
sys.path.insert(0,os.path.dirname(__file__)); from lab import *
res={}
files=sorted(glob.glob('/home/user/refs/rust/*/*_Color.jpg'))+sorted(glob.glob('/home/user/refs/ph/*.jpg'))
allrust=[]
for f in files:
    im=np.asarray(Image.open(f).convert('RGB').resize((512,512)),dtype=np.float64)
    lab=srgb8_to_lab(im).reshape(-1,3)
    C=np.hypot(lab[:,1],lab[:,2]); h=np.degrees(np.arctan2(lab[:,2],lab[:,1]))
    m=(C>18)&(h>35)&(h<75)
    n=os.path.basename(f).split('_1K')[0].replace('.jpg','')
    if m.sum()<500: res[n]=dict(frac=float(m.mean())); continue
    r=lab[m]; allrust.append(r)
    res[n]=dict(frac=round(float(m.mean()),3),L=round(float(r[:,0].mean()),1),a=round(float(r[:,1].mean()),1),b=round(float(r[:,2].mean()),1),sdL=round(float(r[:,0].std()),1),hue=round(float(h[m].mean()),1),C=round(float(C[m].mean()),1))
for k,v in res.items(): print(k,v)
a=np.concatenate(allrust); print('ALL',a.mean(0).round(1),a.std(0).round(1))
lin=lab_to_lin(a.mean(0)); print('lin',lin.round(3),'srgb8',(lin_to_srgb(lin)*255).round())
for q in (25,50,75): print(q,np.percentile(a,q,axis=0).round(1))
