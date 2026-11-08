import sys,os,glob,json,numpy as np
from PIL import Image
sys.path.insert(0,os.path.dirname(__file__)); from lab import *
R='/home/user/refs/rust/'
out={}
for n in ['Leaking010A','Leaking011A']:
    a=np.asarray(Image.open(glob.glob(R+n+'/*_Opacity.jpg')[0]).convert('L'),dtype=np.float64)/255
    c=np.asarray(Image.open(glob.glob(R+n+'/*_Color.jpg')[0]).convert('L'),dtype=np.float64)/255
    H,W=a.shape
    dark=(a>0.9)&(c<0.15)
    ys,xs=np.nonzero(dark); cy,cx=ys.mean(),xs.mean()
    diam=2*np.sqrt(dark.sum()/np.pi)
    rows=[]
    for y in range(int(cy+diam/2)+1,H):
        r=a[y]; 
        if r.max()<0.05: continue
        m=r>0.5*r.max(); w=m.sum(); rows.append((y-cy,r.max(),w,np.average(np.arange(W),weights=r+1e-9)))
    rows=np.array(rows)
    vis=rows[rows[:,1]>0.08]
    L=vis[:,0].max()
    seg=lambda t0,t1: vis[(vis[:,0]>=t0*L)&(vis[:,0]<t1*L)]
    prof=[dict(t=round((i+0.5)/5,2),opacity=round(float(seg(i/5,(i+1)/5)[:,1].mean()),3),fwhm_px=round(float(seg(i/5,(i+1)/5)[:,2].mean()),1)) for i in range(5)]
    wander=float(vis[:,3].std())
    out[n]=dict(size_px=[W,H],bolt_diam_px=round(diam,1),run_len_px=round(float(L),1),len_over_bolt=round(float(L/diam),2),head_width_over_bolt=round(prof[0]['fwhm_px']/diam,2),tail_width_over_bolt=round(prof[-1]['fwhm_px']/diam,2),wander_px=round(wander,1),profile=prof)
print(json.dumps(out,indent=1))
# dilute stain on white paint (halo) from PaintedMetal010/012
for n in ['PaintedMetal010','PaintedMetal012']:
    im=np.asarray(Image.open(glob.glob(R+n+'/*_Color.jpg')[0]).convert('RGB'),dtype=np.float64)
    lab=srgb8_to_lab(im).reshape(-1,3); C=np.hypot(lab[:,1],lab[:,2]); h=np.degrees(np.arctan2(lab[:,2],lab[:,1]))
    white=(C<6)&(lab[:,0]>70); halo=(lab[:,0]>50)&(C>8)&(C<30)&(h>35)&(h<85); core=(lab[:,0]<50)&(C>18)&(h>30)&(h<75)
    for k,m in (('white',white),('halo',halo),('core',core)):
        if m.sum()>50: print(n,k,round(m.mean(),4),lab[m].mean(0).round(1),lab[m].std(0).round(1))
