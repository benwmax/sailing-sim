"""numpy port of the boat shader's rust block (old and new) on a vertical white gelcoat topside panel."""
import numpy as np
def sat(x): return np.clip(x,0,1)
def frac(x): return x-np.floor(x)
def smooth(a,b,x):
    t=sat((x-a)/(b-a)); return t*t*(3-2*t)
LEVELS={'L0':(0.0,1.0),'L1':(0.3,0.9),'L2':(6.0,0.5),'L3':(30.0,0.9),'L4':(20.0,0.1)}
HULL=np.array([0.8879,0.8714,0.8228])
def base(age,care,shape):
    ageK=sat(age/20)*(1-0.6*care); ox=ageK*0.55
    col=HULL.copy(); lum=col@[0.3,0.59,0.11]
    chalk=np.array([lum]*3)*0.5+np.array([0.82,0.80,0.74])*0.5; chalk*=1.02
    col=col+(chalk-col)*0.4*ox
    return np.broadcast_to(col,shape+(3,)).copy()
def old_block(col,x,y,z,wearw,salt=0.0,**k):
    laneX=x/9.0+y/23.0; lane=frac(np.sin(np.floor(laneX)*91.7)*437.5)
    thin=1-smooth(0.02,0.10,np.abs(frac(laneX)-0.5))
    runLen=20+60*frac(lane*7.3); top=60+40*frac(lane*3.1)
    rust=wearw*(lane>=0.93-0.05*salt)*thin*sat((z-(top-runLen))/runLen)*(z<=top)
    a=(0.5*rust*(1+0.6*salt))[...,None]
    return col+(np.array([0.30,0.13,0.05])-col)*a, a[...,0]
P=dict(slot=25.0,share=0.6,top0=50.0,topR=28.0,len0=6.0,lenR=24.0,w0=0.60,wT=-0.15,decay=1.2,head=0.9,core=(0.11,0.033,0.011),T=(0.149,0.045,0.017),amax=1.0,careK=0.85,age0=1.5,ageR=12.0)
def new_block(col,x,y,z,age,care,depth,salt=0.0,wearw=0.0,p=P):
    rwN=sat((age-p['age0'])/p['ageR']) if age>=0 else 0.5*wearw
    rwA=(1-p['careK']*sat(care)) if age>=0 else 0.8*wearw
    rwN=sat(rwN*(1+0.5*salt)); rwA=sat(rwA*(1+0.3*salt))
    rwX=x/p['slot']+y/61.0; I=np.floor(rwX)
    h=frac(np.sin(I*91.7)*437.5); h2=frac(np.sin(I*23.3+1.7)*4375.5); h3=frac(np.sin(I*7.9+5.1)*43758.5)
    on=(h>=1-p['share']*rwN).astype(float)
    top=p['top0']+p['topR']*h2
    L=(p['len0']+p['lenR']*rwN)*(0.6+0.8*h3)
    d=top-z; t=sat(d/L)
    dx=(frac(rwX)-(0.3+0.4*h3))*p['slot']+0.5*np.sin(z*0.31+I*2.1)*t
    ws=0.7+0.9*frac(h*13.1)
    w=ws*p['w0']*(1+p['wT']/p['w0']*t)
    px=np.maximum(depth,1.0)*1.25e-3*0.7
    we=np.sqrt(w*w+px*px)
    zq=z/3.0+I*7.0; zi=np.floor(zq); zf=zq-zi; zf=zf*zf*(3-2*zf)
    blot=0.7+0.6*(frac(np.sin(zi*12.9)*4375.5)*(1-zf)+frac(np.sin((zi+1)*12.9)*4375.5)*zf)
    run=blot*(w/we)*np.exp(-dx*dx/(we*we))*np.exp(-p['decay']*t)*(1-smooth(0.75,1.0,t))*(d>=0)
    fdx=dx-0.9-0.6*h; fw=np.sqrt(0.18**2+px*px)
    fg=(0.18/fw)*np.exp(-fdx*fdx/(fw*fw))*smooth(0.15,0.35,t)*np.exp(-3*t)*(1-smooth(0.6,0.9,t))*(h2>=0.5)
    hr=np.sqrt(p['head']**2+px*px)
    head=(p['head']/hr)**2*np.exp(-(dx*dx+d*d)/(hr*hr))
    k=on*sat(rwA*(1.25*np.maximum(run,0.6*fg)+1.6*head))
    a=(p['amax']*k)[...,None]
    # rust crust mottle: smooth value noise on 0.6 cm cells, darker and lighter rust
    q=np.stack([x/0.6,z/0.6],-1); qi=np.floor(q); qf=q-qi; qf=qf*qf*(3-2*qf)
    hh=lambda o: frac(np.sin((qi+o)@np.array([27.1,61.7]))*4375.5)
    mn=(hh(np.array([0,0]))*(1-qf[...,0])+hh(np.array([1,0]))*qf[...,0])*(1-qf[...,1])+(hh(np.array([0,1]))*(1-qf[...,0])+hh(np.array([1,1]))*qf[...,0])*qf[...,1]
    core=np.array(p['core'])*(0.7+0.6*mn)[...,None]; T=np.array(p['T'])*(0.7+0.6*mn)[...,None]
    return 0.5*(col+(core-col)*a)+0.5*col*T**a, a[...,0]
def lin_to_srgb8(c):
    c=np.clip(c,0,1); return (np.where(c<=0.0031308,c*12.92,1.055*c**(1/2.4)-0.055)*255+0.5).astype(np.uint8)
def render(kind,level,x0,x1,z0,z1,ppcm,depth=60.0,ss=2,wearw=0.5,p=P,salt=0.0):
    age,care=LEVELS[level]
    nx=int((x1-x0)*ppcm); nz=int((z1-z0)*ppcm)
    xs=x0+(np.arange(nx*ss)+0.5)/(ppcm*ss); zs=z1-(np.arange(nz*ss)+0.5)/(ppcm*ss)
    X,Z=np.meshgrid(xs,zs); Y=np.full_like(X,110.0)
    col=base(age,care,X.shape)
    if kind=='old': col,a=old_block(col,X,Y,Z,wearw,salt)
    else: col,a=new_block(col,X,Y,Z,age,care,depth,salt,wearw,p)
    col=col.reshape(nz,ss,nx,ss,3).mean((1,3)); a=a.reshape(nz,ss,nx,ss).mean((1,3))
    return col,a
