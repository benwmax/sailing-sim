import sys,os,json,numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from rustport import *
from PIL import Image,ImageDraw
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
# the first bolt slot (y = 110 cm) that weeps at L4: its centre and its source height
for I in range(40):
    h=frac(np.sin(I*91.7)*437.5); h2=frac(np.sin(I*23.3+1.7)*4375.5); h3=frac(np.sin(I*7.9+5.1)*43758.5)
    if h>=1-P['share']: break
x0=(I-110/61.0+0.3+0.4*h3)*P['slot']
SRC=(x0,P['top0']+P['topR']*h2); print('close-up bolt',SRC)
for kind in ('old','new'):
    for lv in LEVELS:
        c,a=render(kind,lv,0,200,0,90,4,depth=150)      # 2 m x 0.9 m topside panel, 4 px/cm
        Image.fromarray(lin_to_srgb8(c)).save(f'{out}/{kind}_{lv}_panel.png')
        cx,ct=SRC; c,a=render(kind,lv,cx-10,cx+10,ct-30,ct+5,40,depth=40,ss=1)   # close-up 20 x 35 cm at 4 px/mm round a weep's bolt
        Image.fromarray(lin_to_srgb8(c)).save(f'{out}/{kind}_{lv}_close.png')
        np.save(f'{out}/{kind}_{lv}_close_alpha.npy',a)
        for dist,box in ((50,(90,140,40,80)),(200,(0,200,0,90)),(800,(0,400,0,90))):   # one 1080p pixel = 1.25e-3 cm per cm of depth
            ppcm=1/(dist*1.25e-3); ss=max(1,int(round(8/ppcm)))
            c,a=render(kind,lv,box[0],box[1],box[2],box[3],ppcm,depth=dist,ss=ss)
            im=Image.fromarray(lin_to_srgb8(c)); im.save(f'{out}/{kind}_{lv}_d{dist}.png')
print('done')
