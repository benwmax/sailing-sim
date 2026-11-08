import numpy as np
def srgb_to_lin(c):
    c=np.asarray(c,dtype=np.float64)
    return np.where(c<=0.04045,c/12.92,((c+0.055)/1.055)**2.4)
def lin_to_srgb(c):
    c=np.clip(c,0,1); return np.where(c<=0.0031308,c*12.92,1.055*c**(1/2.4)-0.055)
M=np.array([[0.4124564,0.3575761,0.1804375],[0.2126729,0.7151522,0.0721750],[0.0193339,0.1191920,0.9503041]])
WP=np.array([0.95047,1.0,1.08883])
def lin_to_lab(c):
    xyz=c@M.T/WP
    f=np.where(xyz>0.008856,np.cbrt(xyz),7.787*xyz+16/116)
    L=116*f[...,1]-16; a=500*(f[...,0]-f[...,1]); b=200*(f[...,1]-f[...,2])
    return np.stack([L,a,b],-1)
def srgb8_to_lab(im): return lin_to_lab(srgb_to_lin(im/255.0))
def de76(a,b): return float(np.linalg.norm(np.asarray(a)-np.asarray(b)))
def lab_to_lin(lab):
    L,a,b=lab[...,0],lab[...,1],lab[...,2]
    fy=(L+16)/116; fx=fy+a/500; fz=fy-b/200
    def inv(f): return np.where(f**3>0.008856,f**3,(f-16/116)/7.787)
    xyz=np.stack([inv(fx),inv(fy),inv(fz)],-1)*WP
    return xyz@np.linalg.inv(M).T
