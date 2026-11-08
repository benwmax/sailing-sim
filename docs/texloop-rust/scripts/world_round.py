import sys,os,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import worldport as W
from rustport import lin_to_srgb8
from PIL import Image
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
SLOTS={'Steel':((0.30,0.36,0.40),0.6),'Trailer':((0.80,0.80,0.78),0.3)}
def grid(x0,y0,size,px):
    a=x0+(np.arange(px)+0.5)*size/px; b=y0+size-(np.arange(px)+0.5)*size/px
    return np.stack(np.meshgrid(a,b),-1)
for s,(col,met) in SLOTS.items():
    for lv in W.LEVELS:
        for nm,(size,px) in (('close',(0.25,500)),('far',(3.0,500))):
            uv=grid(1.3,1.0,size,px)
            ss=2; uvs=grid(1.3,1.0,size,px*ss); fw=size/px
            c,m,r=W.shade(col,met,lv,uvs,fw); c=c.reshape(px,ss,px,ss,3).mean((1,3))
            Image.fromarray(lin_to_srgb8(c)).save(f'{out}/{s}_{lv}_{nm}.png')
            co,_=W.shade_old(col,met,lv,uvs); co=co.reshape(px,ss,px,ss,3).mean((1,3))
            Image.fromarray(lin_to_srgb8(co)).save(f'{out}/old_{s}_{lv}_{nm}.png')
print('ok')
