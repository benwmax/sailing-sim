# USGS north Texas reservoir reflectance spectra (ScienceBase 5fe38f8ed34ea5387deb4923, SpectroradiometricData.csv: the
# ratio to a white reference) to linear sRGB under D65, per lake, site and visit (docs/lake-body/). The CSV stays out of
# the repo: python3 Tools/water/usgs_reflectance_rgb.py <SpectroradiometricData.csv>
import csv, math, sys, collections
import numpy as np
def g(x, mu, s1, s2): s = s1 if x < mu else s2; return math.exp(-0.5*((x-mu)/s)**2)
def cmf(l):   # Wyman, Sloan & Shirley 2013, multi-lobe fit to CIE 1931
    x = 1.056*g(l,599.8,37.9,31.0)+0.362*g(l,442.0,16.0,26.7)-0.065*g(l,501.1,20.4,26.2)
    y = 0.821*g(l,568.8,46.9,40.5)+0.286*g(l,530.9,16.3,31.1)
    z = 1.217*g(l,437.0,11.8,36.0)+0.681*g(l,459.0,26.0,13.8)
    return x, y, z
def d65(l):   # D65 relative SPD, coarse table (every 10 nm, 380-780), linear in between
    t = [49.98,54.65,82.75,91.49,93.43,86.68,104.86,117.01,117.81,114.86,115.92,108.81,109.35,107.80,104.79,107.69,104.41,104.05,100.00,96.33,95.79,88.69,90.01,89.60,87.70,83.29,83.70,80.03,80.21,82.28,78.28,69.72,71.61,74.35,61.60,69.89,75.09,63.59,46.42,66.81,63.38]
    i = (l-380)/10.0; k = int(min(max(math.floor(i),0),len(t)-2)); f=i-k; return t[k]*(1-f)+t[k+1]*f
M = np.array([[3.2406,-1.5372,-0.4986],[-0.9689,1.8758,0.0415],[0.0557,-0.2040,1.0570]])
spec = collections.defaultdict(lambda: collections.defaultdict(list))
with open(sys.argv[1], encoding='latin1') as fh:
    for r in csv.DictReader(fh):
        if r['Waterbody'] not in ('Ray Hubbard Lake','Lake Tawakoni','Tawakoni Lake'): continue
        l = int(float(r['Wavelength']))
        if 380 <= l <= 780: spec[(r['Waterbody'], r['Site'], r['Date'])][l].append(float(r['Reflectance']))
for key in sorted(spec):
    S = spec[key]; L = sorted(S)
    XYZ = np.zeros(3); Yw = 0.0
    for l in L:
        R = float(np.median(S[l])); x,y,z = cmf(l); w = d65(l)
        XYZ += R*w*np.array([x,y,z]); Yw += w*y
    XYZ /= Yw; rgb = M @ XYZ
    r550 = float(np.median(S[550])); r450=float(np.median(S[450])); r650=float(np.median(S[650]))
    print(f"{key[0][:12]:12s} {key[1]:4s} {key[2]:10s}  R(450,550,650) {r450:.3f} {r550:.3f} {r650:.3f}   Y {XYZ[1]:.3f}  linear sRGB {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f}  r/b {rgb[0]/rgb[2]:.2f} g/b {rgb[1]/rgb[2]:.2f}")
