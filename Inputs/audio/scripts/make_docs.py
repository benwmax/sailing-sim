"""Write README.md, CREDITS.md and manifest.json for the pack from the two manifests."""
import json, os, sys
OUT = sys.argv[1]; S = os.path.join(OUT, 'Samples')
syn = json.load(open(os.path.join(S, 'synth_manifest.json')))
rec = json.load(open(os.path.join(S, 'recorded_manifest.json'))) if os.path.exists(os.path.join(S, 'recorded_manifest.json')) else []
for r in syn: r.update(source='script (synth.py)', license='CC0 (made for this project)', channels=1)
for r in rec: r['source'] = 'Wikimedia Commons'
allr = sorted(syn + rec, key=lambda r: r['file'])
json.dump(allr, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)

PARAM = {
 'Wind/': 'ApparentWind (crossfade light < 5 m/s, moderate 5-9, strong > 9; howl layer on gusts)',
 'Sails/sail_luff': 'Luff (0.1-0.4 light, 0.4-0.7 moderate)', 'Sails/sail_flog': 'Luff > 0.7 with ApparentWind > 7 m/s',
 'Sails/sail_fill': 'Luff falling from > 0.6 to < 0.2 (tack or gybe completes)',
 'Winch/winch_ratchet': 'TrimRate > 0 (rate scales pitch/playback)', 'Winch/winch_click': 'TrimRate > 0, small adjustments',
 'Rigging/sheet': 'TrimRate < 0 (easing)', 'Rigging/halyard': 'ApparentWind with the boat in the slip or head to wind',
 'Rigging/marina': 'Near the marina (Rush Creek slip, Galveston marinas)',
 'Water/hull_wash': 'BoatSpeed (1 kn ~0.5 m/s, 3 kn 1.5, 5 kn 2.6, 7 kn 3.6); raise 7 kn layer as HullSpeedRatio > 0.9',
 'Water/water_lapping_hull_choppy': 'BowSlam or low BoatSpeed in chop', 'Water/water_lapping': 'BoatSpeed < 0.3 m/s',
 'Water/lake_shore': 'Distance to a lee shore', 'Water/gulf_beach': 'Distance to the Galveston beaches',
 'Water/water_over_rocks': 'Distance to riprap and jetties',
 'Weather/rain': 'Rain (light < 0.5, heavy > 0.5)', 'Weather/thunder_crack': 'ThunderCrack', 'Weather/thunder': 'Thunder',
 'Ships/ship_horn': 'HornLevel with HornHz < 200 (ship)', 'Ships/fog_signal': 'Restricted visibility sound signals',
 'Ships/container': 'Distance to a ship (AI traffic)', 'Engines/': 'AI motor vessels and the instructor launch, by distance',
 'Birds/': 'Random one-shots from shore positions, by place and time of day', 'Ambience/cicadas': 'Summer afternoons near shore trees',
 'Ambience/': 'Marina and dock beds', 'Dock/': 'In the slip: dock line load and fender contact',
}
def param(f):
    for k in sorted(PARAM, key=len, reverse=True):
        if f.startswith(k): return PARAM[k]
    return ''

L = ['# Sailing sim sound sample pack', '',
 'Recorded and script-built sounds for the layers in `USailingSynthWave` (`Source/SailingSim/Private/SailingAudio.cpp`).',
 'Everything is 48 kHz 16-bit PCM WAV. Mono unless the table says 2 channels (stereo beds for ambience, rain, shore surf and storm wind).',
 '', '## Levels and loops', '',
 '- Loops are set to -20 dBFS RMS (peak capped at -1 dBFS) so they mix at matching loudness; one-shots peak at -1 dBFS.',
 '- Every loop loops on the whole file: loop start is sample 0 and loop end is the last sample. Script-built loops are',
 '  generated periodic (no seam at all); recorded loops have a 1 s equal-power crossfade baked into the head.',
 '- In Unreal set `Looping` on the Sound Wave (or loop in MetaSound Wave Player). No loop region markers are needed.',
 '- One-shots with numbered variants (`_01`, `_02`...) are meant for random selection, with a +-5 % pitch spread.',
 '', '## Import on the Mac', '',
 '1. Copy `Samples/` into `Content/Audio/Samples/` keeping the subfolders (or drag the folders into the Content Browser).',
 '2. Unreal creates one Sound Wave per WAV. Batch-set `Looping` on every `*_loop` asset.',
 '3. The `Game parameter` column suggests which `FSailingSoundParams` value drives each file. Recorded layers can sit under',
 '   or replace the synthesized ones; the synth keeps working with no samples present.',
 '4. Update `CREDITS.md` in the repo root: the Sound section says no recorded samples are used. Copy the',
 '   attribution lines from `CREDITS.md` here when any recorded file ships in a build (CC BY and CC BY-SA need credit).',
 '', '## Sources', '',
 '- Only Wikimedia Commons is reachable from the cloud environment that built this. Freesound, archive.org, Pixabay,',
 '  BigSoundBank and Sonniss were blocked, so sailing-specific sounds Commons does not have (rigging, halyards, luffing,',
 '  winches, blocks, hull wash, outboard) are script-built by `scripts/synth.py` (seeded, reproducible: `python3 synth.py OUT`).',
 '- Recorded clips are cut by `scripts/process.py` from the Commons files listed in `CREDITS.md`.',
 '- CC BY-SA clips: the derived WAVs here are CC BY-SA too. Shipping them in a game build is fine with credit; the licence',
 '  covers the sound files themselves, not the rest of the game.',
 '', '## Files', '', '| File | Type | Seconds | Ch | Use | Game parameter | Source |', '|---|---|---|---|---|---|---|']
for r in allr:
    src = 'script' if r['source'].startswith('script') else f"[{r['license']}]({r['source_page']})"
    kind = 'loop' if r['loop'] else 'one-shot'
    L.append(f"| `{r['file']}` | {kind} | {r['seconds']} | {r.get('channels',1)} | {r['use']} | {param(r['file'])} | {src} |")
open(os.path.join(OUT, 'README.md'), 'w').write('\n'.join(L) + '\n')

C = ['# Credits for recorded sounds', '',
 'Script-built files (`source: script` in `manifest.json`) were made for this project and are released CC0.',
 'Recorded files are cut, trimmed, filtered and level-normalised from these Wikimedia Commons recordings:', '']
seen = {}
for r in rec: seen.setdefault(r['source_title'], []).append(r['file'])
for t, files in seen.items():
    r = next(x for x in rec if x['source_title'] == t)
    lic = f"[{r['license']}]({r['license_url']})" if r['license_url'] else r['license']
    C.append(f"- **{t}** by {r['author'] or 'unknown'}, {lic}, {r['source_page']}. Modified (cut, filtered, normalised, resampled). Used in: " + ', '.join(f'`{f}`' for f in files))
C += ['', '## Attribution line for the game credits screen', '',
      'Sound effects include recordings from Wikimedia Commons by ' +
      ', '.join(sorted({(r['author'] or 'unknown') for r in rec if not r['license'].lower().startswith(('public', 'cc0'))})) +
      ' (CC BY / CC BY-SA; see Inputs/audio/CREDITS.md).']
open(os.path.join(OUT, 'CREDITS.md'), 'w').write('\n'.join(C) + '\n')
print(len(allr), 'files documented;', len(rec), 'recorded')
