"""Rough-water reflection over the frame's own sky (docs/grazing-reflection/): Cox-Munk facets, Smith shadowing, Fresnel,
integrated over the sky luminance the capture shows by elevation, against the water it renders (capture with
-SailingWaterAlbedo=0,0,0 -SailingWaterExtinction=100,100,100 so only the surface reflects).

    Tools/venv/bin/python -I Tools/water/sky_reflection_check.py <capture.png> <mean wind m/s>
"""
import sys, json, math, numpy as np
from PIL import Image
from scipy.special import erfc
def lin(a): a=a/255.; return np.where(a<=0.04045,a/12.92,((a+0.055)/1.055)**2.4)
def fresnel(c, n=1.333):
    c=np.clip(c,1e-6,1); s=np.sqrt(1-c*c)/n; t=np.sqrt(np.clip(1-s*s,0,1))
    return 0.5*(((c-n*t)/(c+n*t))**2+((n*c-t)/(n*c+t))**2)
p=sys.argv[1]; U=float(sys.argv[2])
im=lin(np.asarray(Image.open(p).convert('RGB'),float)); H,W,_=im.shape
cam=json.load(open(p.replace('.png','.camera.json'))); pitch=cam['camera_pitch_yaw_roll_deg'][0]; f=(W/2)/math.tan(math.radians(cam['hfov_deg']/2))
Y=lambda c: c@[0.2126,0.7152,0.0722]
cols=slice(int(.3*W),int(.7*W))
def row(el): return int(round(H/2-f*math.tan(math.radians(el-pitch))))
els=[e for e in np.arange(0.5,40,0.5) if 2<row(e)<H-3]
Lsky=np.array([np.median(Y(im[row(e)-1:row(e)+2,cols].reshape(-1,3))) for e in els])
def L(e):  # sky luminance by elevation (deg), held at the top row's value above the frame
    return np.interp(e, els, Lsky, left=Lsky[0], right=Lsky[-1])
rng=np.random.default_rng(3); N=300000; var=0.003+0.00512*U; s=math.sqrt(var/2)
sx=rng.normal(0,s,N); sy=rng.normal(0,s,N); nrm=np.stack([-sx,-sy,np.ones(N)],1); nrm/=np.linalg.norm(nrm,axis=1,keepdims=True)
print(f"{p.split('/')[-1]}  U {U} m/s  (sky known to {els[-1]:.0f} deg)")
for dep in (3,5,8,12):
    d=math.radians(dep); v=np.array([math.cos(d),0,-math.sin(d)])
    cosi=-(nrm@v); w=np.clip(cosi,0,None)/nrm[:,2]; r=v[None,:]+2*cosi[:,None]*nrm
    el=np.degrees(np.arcsin(np.clip(r[:,2],1e-6,1))); a=np.tan(np.radians(el))/(math.sqrt(2)*s)
    lam=0.5*(np.exp(-a*a)/(np.maximum(a,1e-9)*math.sqrt(math.pi))-erfc(a))
    fr=fresnel(np.clip(cosi,0,1))*(r[:,2]>0)/(1+np.maximum(lam,0))
    pred=float((fr*w*L(el)).sum()/w.sum())/float(L(dep)); unif=float((fr*w).sum()/w.sum())
    rw=int(round(H/2+f*math.tan(math.radians(dep+pitch)))); obs=float(np.median(Y(im[rw-2:rw+3,cols].reshape(-1,3))))/float(L(dep))
    print(f"  {dep:2d} deg  uniform sky {unif:.3f}   this sky {pred:.3f}   rendered {obs:.3f}   rendered/predicted {obs/pred:.2f}")
