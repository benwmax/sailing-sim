"""Turn downloaded Commons recordings into game-ready 48 kHz 16-bit WAVs.

Loops: the steadiest stretch of the recording is cut and its tail crossfaded (equal power, 1 s) into its head,
so the file loops end to start. One-shots: the loudest separate events are cut with a short pre-roll and fades.
Loops are set to -20 dBFS RMS (peak capped at -1 dBFS), one-shots to -1 dBFS peak, matching synth.py.
Usage: python3 process.py DOWNLOAD_DIR OUT_DIR
"""
import sys, os, json, subprocess, wave
import numpy as np

SR = 48000
DL, OUT = sys.argv[1], sys.argv[2]
meta = json.load(open(os.path.join(DL, 'meta.json')))

# title: (kind, out, params)
R = {
 'Gull 1.ogg': ('shots', 'Birds/gull_call', dict(n=3, maxlen=3.0, hp=250, use='Gull calls over the water and marina (both lakes)')),
 'Gull 2.ogg': ('shots', 'Birds/gull_call_b', dict(n=3, maxlen=3.0, hp=250, use='More gull calls (randomise with gull_call)')),
 'Larus atricilla.ogg': ('shots', 'Birds/laughing_gull', dict(n=3, maxlen=3.0, hp=300, use='Laughing gull, the common gull of Galveston Bay')),
 'XC707075 - European Herring Gull - Larus argentatus.mp3': ('shots', 'Birds/herring_gull', dict(n=4, maxlen=3.0, hp=300, use='Large gull calls (Galveston piers, winter on the lake)')),
 'Red-winged Blackbird (Agelaius phoeniceus).ogg': ('shots', 'Birds/redwinged_blackbird', dict(n=3, maxlen=2.5, hp=500, use='Red-winged blackbird from shore reeds near the slip')),
 'Quiscalus mexicanus - Great-tailed Grackle XC243017.mp3': ('shots', 'Birds/great_tailed_grackle', dict(n=4, maxlen=3.0, hp=400, use='Great-tailed grackle, the loud Texas marina and parking-lot bird')),
 'Geese Honking (distant).ogg': ('shots', 'Birds/canada_geese_distant', dict(n=2, maxlen=6.0, hp=200, use='Canada geese honking at a distance')),
 'Low flyover by five Canadian Geese.flac': ('shots', 'Birds/canada_geese_flyover', dict(n=1, maxlen=10.0, hp=150, gap=1.5, use='Geese flying low overhead')),
 'Great Blue Heron1.ogg': ('shots', 'Birds/great_blue_heron', dict(n=2, maxlen=3.0, hp=150, use='Great blue heron croak from the shallows')),
 'Charadrius vociferus.ogg': ('shots', 'Birds/killdeer', dict(n=2, maxlen=3.0, hp=500, use='Killdeer calling from the shore and riprap')),
 'Cicada calling in Irving, TX in June of 2012.ogg': ('loop', 'Ambience/cicadas_texas_summer_loop', dict(dur=8, hp=1000, use='Cicadas from shore trees on summer afternoons (Irving TX recording)')),
 'Rain on a veranda and t.ogg': ('loop', 'Weather/rain_on_roof_light_loop', dict(dur=16, hp=80, use='Light rain on a hard surface: layer for rain on deck and cabin top')),
 'Heavy Rain in Summer.ogg': ('loop', 'Weather/rain_heavy_loop', dict(dur=12, hp=60, use='Heavy summer downpour (storm cell over the lake)')),
 'Sound of light rainfall.ogg': ('loop', 'Weather/rain_light_loop', dict(dur=16, hp=60, use='Light rain falling on water and around the boat')),
 'Tonitrus.ogg': ('shots', 'Weather/thunder_rumble', dict(n=2, maxlen=12.0, hp=20, gap=2.0, thr=30, use='Distant thunder rumble (storm approaching)')),
 'Booming Thunder 2023-10-09 2-07-34 am.ogg': ('shots', 'Weather/thunder_boom', dict(n=2, maxlen=12.0, hp=20, gap=2.0, thr=30, use='Nearby thunder boom')),
 'Thunder crack 2B.ogg': ('shots', 'Weather/thunder_crack', dict(n=1, maxlen=12.0, hp=20, gap=2.0, thr=35, use='Close lightning strike crack and roll')),
 'Rhumphries - rbh-thunder-storm.ogg': ('shots', 'Weather/thunder_storm', dict(n=2, maxlen=12.0, hp=20, gap=2.0, thr=30, use='Thunder in a storm with rain behind it')),
 'Howling wind.ogg': ('loop', 'Wind/wind_howl_storm_loop', dict(dur=16, hp=40, use='Storm gust layer above wind_rigging_strong (squall line)')),
 'Lake Okeechobee Surf in April 2016.ogg': ('loop', 'Water/lake_shore_waves_loop', dict(dur=20, hp=40, use='Wind waves breaking on a lake shore (lee shore, beaching drill, near riprap)')),
 'Ocean Waves on a Tropical Beach.ogg': ('loop', 'Water/gulf_beach_surf_loop', dict(dur=20, hp=40, use='Surf on a sand beach (Galveston Island, Bolivar)')),
 'Water over rocks as tide recedes.ogg': ('loop', 'Water/water_over_rocks_loop', dict(dur=12, hp=60, use='Water washing over rocks: riprap breakwaters and jetties close by')),
 'Boat by a wharf 3.ogg': ('loop', 'Ambience/boat_by_wharf_loop', dict(dur=16, hp=40, use='Boat moving against a wharf: slip and fuel dock bed')),
 'Boat landing at a wharf.ogg': ('shots', 'Dock/boat_landing_wharf', dict(n=1, maxlen=10.0, hp=40, gap=2.0, thr=30, use='Boat coming alongside a dock (docking drill finish)')),
 'Burnham Overy harbour atmosphere (W PALEARCTIC COASTAL R4 C4).ogg': ('loop', 'Ambience/harbour_atmosphere_loop', dict(dur=20, hp=40, use='Small harbour bed: water, distant voices, halyards (Rush Creek, Galveston marinas)')),
 'Containerschip meert aan in haven - SoundCloud - Beeld en Geluid.ogg': ('loop', 'Ships/container_ship_engines_loop', dict(dur=16, hp=25, use='Container ship engines and machinery at a distance (Houston Ship Channel traffic)')),
 'WWS Rustondieselengine.ogg': ('loop', 'Engines/diesel_workboat_loop', dict(dur=8, hp=30, use='Slow diesel thump: tug or workboat passing (distance-filter in game)')),
 'WWS Seffleboatengine.ogg': ('loop', 'Engines/inboard_engine_loop', dict(dur=8, hp=30, use='Small inboard engine: keelboat auxiliary or launch')),
 'Cruise ship Albatros ship horn.ogg': ('shots', 'Ships/ship_horn', dict(n=1, maxlen=10.0, hp=30, gap=1.0, thr=40, use='Large ship whistle (prolonged blast, Navigation Rules signals)')),
 'Fog signal Bremerhaven.ogg': ('shots', 'Ships/fog_signal', dict(n=2, maxlen=6.0, hp=30, gap=1.0, thr=40, use='Fog signal / foghorn blast (restricted visibility)')),
}
STEREO = ('Ambience/', 'Weather/rain', 'Water/lake_shore', 'Water/gulf_beach', 'Wind/')

def decode(path, ch, hp):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-af', f'highpass=f={hp}', '-ac', str(ch), '-ar', str(SR),
                          '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, '<f4').astype(np.float64).reshape(-1, ch)

def save(rel, x, loop):
    if loop:
        x = x * (10**(-20/20) / (np.sqrt(np.mean(x**2)) + 1e-12))
        pk = np.max(np.abs(x))
        if pk > 10**(-1/20): x *= 10**(-1/20) / pk
    else:
        x = x * (10**(-1/20) / (np.max(np.abs(x)) + 1e-12))
    p = os.path.join(OUT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    pcm = np.clip(np.round(x*32767), -32768, 32767).astype('<i2')
    with wave.open(p, 'wb') as w:
        w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    return dict(file=rel, seconds=round(len(x)/SR, 3), channels=x.shape[1], loop=loop,
                loop_start=0 if loop else None, loop_end=len(x) if loop else None)

def frames_db(x, hop):
    m = x.mean(1); n = len(m)//hop
    return 10*np.log10(np.mean(m[:n*hop].reshape(n, hop)**2, 1) + 1e-12)

def make_loop(x, dur, xf=1.0):
    D, X = int(dur*SR), int(xf*SR)
    if len(x) < D + X:
        D = len(x) - X - 1
    hop = SR//10; db = frames_db(x, hop)
    w = (D+X)//hop; best, bi = 1e9, 0
    med = np.median(db)
    for i in range(0, len(db)-w+1):
        seg = db[i:i+w]
        cost = np.std(seg) + 0.5*max(0, med - seg.mean())
        if cost < best: best, bi = cost, i
    s = x[bi*hop: bi*hop + D + X].copy()
    t = np.linspace(0, np.pi/2, X)[:, None]
    out = s[:D].copy()
    out[:X] = s[:X]*np.sin(t) + s[D:D+X]*np.cos(t)
    return out, bi*hop/SR

def shots(x, n, maxlen, gap=0.15, thr=25):
    hop = SR//100; db = frames_db(x, hop)
    on = db > db.max() - thr
    ev = []; i = 0; g = int(gap*100)
    while i < len(on):
        if on[i]:
            j = i; last = i
            while j < len(on) and j - last <= g:
                if on[j]: last = j
                j += 1
            ev.append((i, last+1, db[i:last+1].max())); i = j
        else: i += 1
    ev = sorted(sorted(ev, key=lambda e: -e[2])[:n])
    outs = []
    for a, b, _ in ev:
        s = max(0, a*hop - int(0.03*SR)); e = min(len(x), b*hop + int(0.25*SR), s + int(maxlen*SR))
        y = x[s:e].copy(); fi, fo = int(0.005*SR), min(int(0.08*SR), len(y)//3)
        y[:fi] *= np.linspace(0, 1, fi)[:, None]; y[-fo:] *= np.linspace(1, 0, fo)[:, None]
        outs.append((y, s/SR))
    return outs

manifest = []
for title, (kind, out, p) in R.items():
    src = os.path.join(DL, title.replace(' ', '_'))
    if not os.path.exists(src) or title not in meta:
        print('SKIP (not downloaded)', title); continue
    ch = 2 if out.startswith(STEREO) else 1
    x = decode(src, ch, p['hp'])
    if len(x) < SR//4: print('SKIP (empty)', title); continue
    m = meta[title]
    src_info = dict(source_title=title, source_page=m['page'], author=m['author'] or m['credit'], license=m['license'],
                    license_url=m['license_url'], use=p['use'])
    if kind == 'loop':
        y, t0 = make_loop(x, p['dur'])
        rec = save(out + '.wav', y, True); rec.update(src_info, cut_from_s=round(t0, 2), kind='loop')
        manifest.append(rec)
    else:
        ev = shots(x, p['n'], p['maxlen'], p.get('gap', 0.15), p.get('thr', 25))
        for k, (y, t0) in enumerate(ev):
            rec = save(f'{out}_{k+1:02d}.wav', y, False); rec.update(src_info, cut_from_s=round(t0, 2), kind='one-shot')
            manifest.append(rec)
    print('OK', title, '->', out, len(x)/SR)
json.dump(manifest, open(os.path.join(OUT, 'recorded_manifest.json'), 'w'), indent=1)
