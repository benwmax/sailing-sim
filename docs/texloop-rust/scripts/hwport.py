"""numpy port of BOAT_CODE's hardware rust (stainless tea stain, surface 3; galvanised/plain steel, surface 12) on a flat
vertical 20 x 20 cm plate (LP.x across, LP.z up, LP.y fixed)."""
import numpy as np
from rustport import sat, frac, LEVELS
def sm(x): x=sat(x); return x*x*(3-2*x)
def smooth(a,b,x): return sm((x-a)/(b-a))
def h2(qi,k1=12.99,k2=78.23,m=43758.5): return frac(np.sin(qi[...,0]*k1+qi[...,1]*k2)*m)
def vnoise(P):   # the grime's 3-octave value noise (37, 9, 2.2 cm)
    vn=0; amp=0.6; sc=37.0
    for o in range(3):
        q=(P[...,:2]+P[...,2:3]*np.array([0.6,-0.4]))/sc+o*17.3
        qi=np.floor(q); qf=q-qi; qf=qf*qf*(3-2*qf)
        a00=h2(qi);a10=h2(qi+[1,0]);a01=h2(qi+[0,1]);a11=h2(qi+[1,1])
        vn=vn+amp*((a00*(1-qf[...,0])+a10*qf[...,0])*(1-qf[...,1])+(a01*(1-qf[...,0])+a11*qf[...,0])*qf[...,1])
        amp*=0.5; sc/=4.1
    return vn/1.05
def hwnoise(P,axis='y'):
    # dominant-axis projection: the two boat axes across the face (here a face whose normal is along y)
    q=np.stack([P[...,0],P[...,2]],-1)/1.3; n=0
    for o,w in ((0,0.65),(1,0.35)):
        qi=np.floor(q); qf=sm(q-qi)
        f=lambda d: h2(qi+d,27.1,61.7,4375.5)
        n=n+w*((f([0,0])*(1-qf[...,0])+f([1,0])*qf[...,0])*(1-qf[...,1])+(f([0,1])*(1-qf[...,0])+f([1,1])*qf[...,0])*qf[...,1])
        q=np.stack([q[...,0]*0.8-q[...,1]*0.6,q[...,0]*0.6+q[...,1]*0.8],-1)*2.9+5.3
    return n
def lerp(a,b,t): return a+(b-a)*t
def fnoise(P):   # one octave at 0.5 cm on a rotated lattice: tea stain specks
    q=np.stack([P[...,0]*0.8-P[...,2]*0.6,P[...,0]*0.6+P[...,2]*0.8],-1)/0.5
    qi=np.floor(q); qf=sm(q-qi); f=lambda d: h2(qi+d,41.3,17.7,4375.5)
    return (f([0,0])*(1-qf[...,0])+f([1,0])*qf[...,0])*(1-qf[...,1])+(f([0,1])*(1-qf[...,0])+f([1,1])*qf[...,0])*qf[...,1]
def shade(surf,level,ppcm=20,salt=0.0,size=20.0,y=3.0):
    age,care=LEVELS[level]; ageK=min(age/20,1)*(1-0.6*care)
    n=int(size*ppcm); xs=(np.arange(n)+0.5)/ppcm; zs=size-(np.arange(n)+0.5)/ppcm
    X,Z=np.meshgrid(xs,zs); P=np.stack([X,np.full_like(X,y),Z],-1)
    vn=vnoise(P); hwN=hwnoise(P)
    mt=np.abs(frac(hwN*3.5)*2-1)[...,None]
    rustc=lerp(np.array([0.075,0.024,0.010]),np.array([0.256,0.071,0.020]),mt)
    if surf==3:
        col=np.broadcast_to(np.array([0.62,0.62,0.63]),X.shape+(3,)).copy(); metal=np.ones_like(X)
        teaK=(min(age/10,1)*(1-0.9*care))*(0.45+0.55*salt)
        fn=fnoise(P)
        tea=sat(teaK*2.6*sat(hwN*1.6+fn*1.2+0.5*vn-1.55))
        col=lerp(col,np.array([0.24,0.13,0.055])*(0.8+0.4*mt),(0.8*tea)[...,None]); metal*=1-0.35*tea
        mask=tea
    else:
        col=np.broadcast_to(np.array([0.34,0.36,0.37]),X.shape+(3,)).copy(); metal=np.full_like(X,0.85)
        dull=min(age/3,1); stK=sat((age-1)/12)*(1-0.7*care)
        col=lerp(col,np.array([0.30,0.31,0.31]),0.6*dull)
        fn0=fnoise(P); col=col*(0.93+0.14*(0.6*hwN+0.4*fn0))[...,None]   # zinc's tonal mottle
        bloom=dull*(1-care)*sat(hwN*3-1.6); col=lerp(col,np.array([0.55,0.55,0.53]),(0.6*bloom)[...,None]); metal*=1-0.8*bloom
        t=1.0-0.286*stK; fn=fnoise(P); f=hwN+0.25*vn+0.12*(fn-0.5)   # a fine octave rags the edges
        r=smooth(t,t+0.10,f)*(stK>=0.02)
        mt2=sat(1.3-(f-t)/0.18)*(0.4+0.6*fn)   # orange at the edges, dark crust at the heart (no rim)
        rustc=lerp(np.array([0.075,0.024,0.010]),np.array([0.256,0.071,0.020]),mt2[...,None])
        halo=smooth(t-0.09,t,f)*(1-r)*(stK>=0.02)
        col=lerp(col,np.array([0.24,0.12,0.05]),(0.45*halo)[...,None])
        fl=smooth(0.72,0.80,fn)*smooth(t-0.16,t-0.04,f)*(1-r)*(stK>=0.02)   # flecks scattered round each patch
        col=lerp(col,rustc,r[...,None]); col=lerp(col,np.array([0.20,0.065,0.020]),(0.8*fl)[...,None]); metal*=1-r-0.4*halo-0.8*fl; mask=r
    return col,metal,mask
def shade_old(surf,level,ppcm=20,size=20.0,y=3.0):
    age,care=LEVELS[level]; ageK=min(age/20,1)*(1-0.6*care)
    n=int(size*ppcm); xs=(np.arange(n)+0.5)/ppcm; zs=size-(np.arange(n)+0.5)/ppcm
    X,Z=np.meshgrid(xs,zs); P=np.stack([X,np.full_like(X,y),Z],-1); vn=vnoise(P)
    base=np.array([0.62,0.62,0.63]) if surf==3 else np.array([0.34,0.36,0.37])
    col=np.broadcast_to(base,X.shape+(3,)).copy()
    tea=ageK*0.35*sat(vn*1.6-0.35)
    return lerp(col,np.array([0.28,0.17,0.09]),(0.45*tea)[...,None])
