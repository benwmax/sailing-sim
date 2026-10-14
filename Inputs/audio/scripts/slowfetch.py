import json,sys,time,os,urllib.request
UA="SailingSimAudioPack/1.0 (https://github.com/benwmax/sailing-sim; one-off download of ~40 CC/PD clips, paced)"
OUT=sys.argv[1]; meta=json.load(open(sys.argv[2]))
for t,d in meta.items():
  fn=os.path.join(OUT,t.replace(" ","_"))
  if os.path.exists(fn) and os.path.getsize(fn)>0: continue
  while True:
    try:
      data=urllib.request.urlopen(urllib.request.Request(d["url"],headers={"User-Agent":UA}),timeout=300).read()
      open(fn,"wb").write(data); print("OK",t,len(data),time.strftime("%H:%M:%S"),flush=True); time.sleep(45); break
    except urllib.error.HTTPError as e:
      ra=int(e.headers.get("retry-after") or 120) if e.code==429 else 60
      print("HTTP",e.code,"wait",ra,t,time.strftime("%H:%M:%S"),flush=True); time.sleep(90)
print("DONE",flush=True)
