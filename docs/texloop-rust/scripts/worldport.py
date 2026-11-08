"""numpy port of M_WorldSurface pattern 5 (weathered steel), round 1 of the rust lane's world pass. Mirrors the HLSL."""
import numpy as np
def sat(x): return np.clip(x,0,1)
def frac(x): return x-np.floor(x)
def sm(x): return x*x*(3-2*x)
def smooth(a,b,x): t=sat((x-a)/(b-a)); return t*t*(3-2*t)
def lerp(a,b,t): return a+(b-a)*t
LEVELS={'L0':(0.0,1.0),'L1':(0.3,0.9),'L2':(6.0,0.5),'L3':(30.0,0.9),'L4':(20.0,0.1)}
def h2(i,k1,k2): return frac(np.sin(i[...,0]*k1+i[...,1]*k2)*43758.5)
def vnoise(q,k1,k2):
    i=np.floor(q); f=sm(q-i); o=lambda a,b: h2(i+np.array([a,b]),k1,k2)
    return lerp(lerp(o(0,0),o(1,0),f[...,0]),lerp(o(0,1),o(1,1),f[...,0]),f[...,1])
PRM=dict(s1=0.022,s2=0.007,kAge=14.0,tSpan=0.42,blotK=0.25)
def shade(colp,metp,level,uv,fw,salt=0.0,p=PRM):
    """colp: slot colour, metp: slot Metallic, uv metres (H,W,2), fw metres per pixel."""
    age,care=LEVELS[level]; aged=min(age/25,1)
    H,W=uv.shape[:2]; c=np.broadcast_to(np.array(colp,float),(H,W,3)).copy(); met=np.full((H,W),metp)
    q=uv*0.7; blot=vnoise(q,12.99,78.23)
    bare=metp>0.4
    k=sat((age-1.0)/p['kAge'])*(1-0.7*care)*(1+0.5*salt); k=min(k,1.0)
    # two octaves of value noise in the part's own metres (2.2 cm, and 0.7 cm on a turned lattice), lost to their mean
    # as a pixel grows past them (no shimmer at a distance)
    n0=vnoise(uv/0.08,53.3,19.1)   # 8 cm: patches gather in clusters
    n1=vnoise(uv/p['s1'],27.1,61.7)
    r=np.stack([uv[...,0]*0.8-uv[...,1]*0.6,uv[...,0]*0.6+uv[...,1]*0.8],-1)
    n2=vnoise(r/p['s2'],41.3,17.7)
    f1=1-smooth(0.5*p['s1'],1.5*p['s1'],fw); f2=1-smooth(0.5*p['s2'],1.5*p['s2'],fw)
    F=0.5+0.7*(n0-0.5)+0.35*(n1-0.5)+0.15*(n2-0.5)*f2+p['blotK']*(blot-0.5)
    t=(0.867-0.346*k**1.5) if bare else (0.961-0.359*k)   # cover by level: CC0 rusty-steel and painted-metal scans
    on=float(k>0.02)
    # the mask where the noise resolves; its expected cover where it doesn't
    near=smooth(t,t+0.06,F); far=smooth(0.36,-0.47,t-0.5-p['blotK']*(blot-0.5))
    w=f1; rust=lerp(far,near,w)*on   # far: the share of the pixel that is rust
    halo=smooth(t-0.07,t,F)*(1-rust)*on*f1
    if bare:
        dull=sat(age/3)
        c=lerp(c,np.array([0.30,0.31,0.31]),0.6*dull)
        c*=(0.93+0.14*(0.6*n1+0.4*n2)*w+0.07*(1-w))[...,None]
        bloom=dull*(1-care)*sat((0.6*n0+0.4*n1)*3-1.7)*w
        c=lerp(c,np.array([0.55,0.55,0.53]),(0.6*bloom)[...,None]); met=met*(1-0.8*bloom)
    else:
        # paint fades on, chalks a little
        c*=(1+0.12*aged)
    # weeps: thin runs down from seams every 0.67 m of the part, each its own length (painted and bare alike)
    lane=np.floor(uv[...,0]*1.5); hl=frac(np.sin(lane*91.7)*4375.5); hl2=frac(np.sin(lane*17.3+7.0)*4375.5)
    wx=(frac(uv[...,0]*1.5)-(0.3+0.4*hl2))/1.5; fy=frac(uv[...,1]*0.35+hl)
    wwid=0.012+0.018*hl2; wfw=np.sqrt(wwid**2+(1.5*fw)**2)
    run=(hl>=1.0-0.5*k-0.15*salt)*(wwid/wfw)*np.exp(-(wx/wfw)**2)*sat(1-fy/(0.2+0.5*hl2))*smooth(0,0.01,fy)*sat(k*2)
    rk=(0.8*run)[...,None]; c=0.5*lerp(c,np.array([0.11,0.033,0.011]),rk)+0.5*c*np.array([0.149,0.045,0.017])**rk   # dye and deposit, as the boats' weeps
    c=lerp(c,np.array([0.24,0.12,0.05]),(0.45*halo)[...,None])
    rc=lerp(np.array([0.075,0.024,0.010]),np.array([0.256,0.071,0.020]),(sat(1.3-(F-t)/0.18)*(0.4+0.6*n2*w+0.3*(1-w)))[...,None])
    c=lerp(c,rc,rust[...,None])
    met=met*sat(1-rust-0.4*halo)
    return c,met,rust

def shade_old(colp,metp,level,uv,salt=0.0,sun=0.5):
    age,care=LEVELS[level]; aged=min(age/25,1)
    H,W=uv.shape[:2]; c=np.broadcast_to(np.array(colp,float),(H,W,3)).copy()
    blot=vnoise(uv*0.7,12.99,78.23); lane=np.floor(uv[...,0]*1.5); hl=frac(np.sin(lane*91.7)*4375.5)
    weep=(hl>=0.6-0.2*salt-0.2*aged*(1-care))*sat(1-frac(uv[...,1]*0.35+hl))*0.8
    c*=((0.9+0.2*blot)*(1+0.12*aged*sun))[...,None]
    c=lerp(c,np.array([0.30,0.14,0.06]),(sat((weep+0.25*sat(blot-0.6))*(0.7+0.5*aged))*0.6)[...,None])
    return c,np.full((H,W),metp)
