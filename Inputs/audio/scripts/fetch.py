import json,sys,time,re,os,urllib.request,urllib.parse,html
UA="SailingSimAudioPack/1.0 (https://github.com/benwmax/sailing-sim; research script) python-urllib"
OUT=sys.argv[1]; titles=[l.strip() for l in open(sys.argv[2]) if l.strip()]
def req(u):
  for i in range(10):
    try: return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA}),timeout=120).read()
    except urllib.error.HTTPError as e:
      if e.code==429: print("429 wait",flush=True); time.sleep(20*(i+1)); continue
      raise
meta={}
for i in range(0,len(titles),20):
  chunk=titles[i:i+20]
  u="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","format":"json","titles":"|".join("File:"+t for t in chunk),"prop":"imageinfo","iiprop":"url|extmetadata|size","iiextmetadatafilter":"LicenseShortName|LicenseUrl|Artist|Credit|DateTimeOriginal"})
  r=json.loads(req(u))
  norm={n["to"]:n["from"] for n in r["query"].get("normalized",[])}
  for p in r["query"]["pages"].values():
    if "imageinfo" not in p: print("MISSING",p["title"]); continue
    ii=p["imageinfo"][0]; m=ii["extmetadata"]
    g=lambda k: html.unescape(re.sub("<[^>]+>","",m.get(k,{}).get("value",""))).strip()
    meta[p["title"][5:]]=dict(url=ii["url"],page=ii["descriptionurl"],license=g("LicenseShortName"),license_url=m.get("LicenseUrl",{}).get("value",""),author=g("Artist"),credit=g("Credit")[:200],size=ii["size"])
  time.sleep(2)
json.dump(meta,open(os.path.join(OUT,"meta.json"),"w"),indent=1)
if os.environ.get("META_ONLY"): sys.exit(0)
for t,d in meta.items():
  fn=os.path.join(OUT,t.replace(" ","_"))
  if not os.path.exists(fn):
    open(fn,"wb").write(req(d["url"])); time.sleep(6)
  d["local"]=fn
json.dump(meta,open(os.path.join(OUT,"meta.json"),"w"),indent=1)
for t,d in meta.items(): print(f'{t[:60]:60} | {d["license"]:14} | {d["author"][:40]}')
