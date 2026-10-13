# Visual V7: the fleet, the crew and polish

The last visual phase. It covers:
- **Fleet:** the other seven boats go through the J/22's model and sail pipeline.
- **Marina:** the opening frame is full of rigged neighbours, on glassy water.
- **Crew:** MetaHumans on your boat on Medium and High.
- **Sound:** new layers, spatialised world sources, and a slot for recorded samples.
- **Camera:** a cockpit view and photo-mode depth of field.
- **Water:** a fix for the sea showing inside low cockpits.

The physics is unchanged. Every polar gate passes as before.

![The Catalina 30 at evening](captures/rh-c30-evening.png)

## What changed

### The fleet (`Tools/blender/build_fleet.py`)

The Sunfish, ILCA 7, Catalina 22, Catalina 30, Hobie 16, Corsair 880 and Lagoon 42 are built from the same exported physics as the J/22 (`Tools/BoatExport`).

**Hulls.** Below the waterline every hull is exactly the physics `FHullShape`. Volume and centre of buoyancy therefore match the physics: within 1.4% and 2 cm on all seven.

**Above the waterline**, per class:
- **Sunfish and ILCA:** footwell, daggerboard trunk, traveler rope.
- **Catalina 22 and 30:** cabin with ports, cockpit and seats, lifelines, winches, the Catalina 30's wheel and dodger, and the 22's outboard.
- **Hobie 16:** beams, trampoline, bridles.
- **Corsair 880:** akas, nets, bowsprit.
- **Lagoon 42:** bridgedeck, saloon, bimini.

**Rigs.** Each rig is built on its own sockets, and the game draws only the rigging those sockets carry. Twin rudders get two pivots.

**Sails.** They keep V3's cloth, with layouts per class:
- the Sunfish's striped lateen;
- the Hobie's coloured panels and seven full battens;
- tri-radial, full-batten mains on the multihulls;
- the ILCA's three short battens.

**Test.** `SailingSim.Visual.FleetMesh` holds each model to its physics hulls: length, beam, draft (rudder included), volume within 2%, centre of buoyancy within 2 cm, the mast step, Nanite and one pivot per rudder.

Three configs disagree with their own published dimensions. The test reports these as information:
- Hobie 16: beam 2.41 m vs 2.54 m published.
- Corsair 880: beam 6.78 m vs 7.00 m published.
- Lagoon 42: LOA 13.22 m vs 12.79 m published.

### The marina opening frame

- **Occupancy:** 90% of the slips are full.
- **Mix:** J/22s and Catalina 22s in the slips (60/40), Catalina 30s alongside the piers wherever the water is deep enough.
- **Berthed dress** (`build_berthed.py`): each neighbour has standing rigging, a furled jib, a navy sail cover, halyards, fenders, and bow, stern and spring lines.
- **Mast:** a static Nanite mast is baked into the berthed mesh.
- **Obstacles:** the berthed boats are physics obstacles.
- **Glassy water:** below 2 kn the water goes glassy (`glass` in `M_WaterV4`), and the masts reflect as in the Grapevine photo.

### MetaHuman crew

**The three crew.** `scripts/make-metahumans.sh` builds them from MetaHuman Creator presets: Bruce at the helm, Ada trimming, Omari on the bow.
- They are rigged by Epic's cloud auto-rig, which needs an Epic sign-in, and assembled with the optimized pipeline.
- Each wears the default shirt and shorts, recoloured per person.
- Each also gets a foam life jacket and a cap from `build_crew_gear.py`, scaled to their own skeleton.
- No groom hair: the caps cover the heads.

**Posing.** `FCrewRig` carries SK_Sailor's physics-driven stances to the MetaHuman skeleton:
- it turns the skeleton's facing (+Y);
- it straightens its A-pose into SK_Sailor's T-pose;
- it spreads the spine and neck over the extra bones.

The face and outfit follow the body by leader pose. `SailingSim.Visual.MetaHumanCrew` checks every stance: each limb and the trunk point within 15–20° of SK_Sailor's.

**Where they appear.** Your boat on Medium and High. Low, AI boats and `-SailingBlenderCrew` keep SK_Sailor.

**Not in the repo.** The built MetaHumans (about 440 MB) are git-ignored and rebuilt locally in about 10 minutes, for two reasons:
- they would take Git LFS past GitHub's free 1 GB;
- the MetaHuman licence covers using them in the game, not redistributing them.

### Sound

The synthesizer keeps every voice and gains these:
- a gust rumble over the mean wind;
- the hush in a wind shadow;
- hull lapping and halyard slap at rest;
- the sheet running through its block;
- rain on deck and rain on water as separate layers;
- a squall's hiss as the gust front approaches.

**World sources** (`USailingWorldSynth`), spatialised with distance falloff:
- marina halyards per dock row;
- two wheeling gulls;
- outboards on the powerboats;
- diesels on the trawlers, tugs and ships.

**Recorded samples.** `Audio/Samples/` takes a recording per cue: `scripts/import-audio.sh`, credits in `CREDITS.md`. Each one replaces the synth voice of the same name at the level the physics gives it. No samples are in yet:
- Freesound needs an account and a download per clip, and I didn't download files without your go-ahead.
- Your own recordings at Rush Creek would be better still.

The cue table is in `Audio/Samples/README.md`. `SailingSim.Smoke.SoundLayers` checks the new layers and every world voice.

### Camera

- **Cockpit view** (`\` or `-SailingCockpit`): the helm's eyes.
  - Head movement comes from the boat's filtered accelerations: about 1.2 cm per m/s², at most 10 cm.
  - The head leans a third of the heel, capped at 8°.
  - FOV 80°, and the helm's own figure is hidden.
- **Photo mode:** depth of field focused on the boat at f/2.8, plus the V1 lens profile (`M_LensDistortion`).

### Fixes found on the way

- **The sea showing inside low cockpits** (the Sunfish footwell, the Catalina 30 in Gulf swell). There were two causes:
  - The generated cockpits, cabins and dodgers are open shells whose faces were not all wound outward. Culled, they let the water under the boat show through. `M_BoatSurface` is two-sided now, and `build_fleet.py`'s boxes are wound for Unreal's axes.
  - The drawn water still crossed the cockpit floor of a boat deep in a wave. `M_WaterV4` now drops its surface 2 m inside your hull's plan (`HullClipA/B/C`; off for catamarans).
- **Wetness:** the hull's splash-line wetness no longer reaches up-facing surfaces, and wet non-skid stays satin.
- **Catalina 30 dodger:** it was built back to front; now it rises from the coachroof to an open aft end, with windows.
- **Capture mode** hides the engine's on-screen messages, which a VSM overflow warning had burned into two stills.
- **High-tier resolution governor:** High's screen percentage steps between 82% and 100% to hold about 50 fps. Steps go down above 21.6 ms and up below 18.5 ms. It is off on Low and Medium, in capture mode and with `-SailingScreenPct`. Without it, Bean's slip ran at 42 fps on High; with it, 50 fps at 82%. `bench.json` reports `render_pct`.

## Tests and physics

- Automation: 88 of 88 pass (`scripts/test.sh`), including the new `SailingSim.Visual.FleetMesh`, `SailingSim.Visual.MetaHumanCrew` and `SailingSim.Smoke.SoundLayers`, and every boat's polar gate.
- Reference checks (`scripts/reference-checks.sh`): 43 of 46. The three outs are the same as Phase 8's, and V7 changed no physics:
  - J/22 spinnaker peak, 12.10 kn against 12.0;
  - Catalina 22 Portsmouth DPN2, 0.93 against 0.96 to 1.13;
  - Hobie 16 Portsmouth DPN4, 0.67 against 0.74 to 0.87.

## Frame rate (`bench.csv`, packaged build, 12 s per view)

GPU time is split into: base / Lumen / water / clouds and fog. High uses the resolution governor (see above).

| View | Medium fps | Medium GPU ms | High fps | High GPU ms |
| --- | --- | --- | --- | --- |
| beam8 | 92.8 | 9.7 (3.37 / 1.59 / 1.67 / 1.87) | 52.1 | 17.6 (8.33 / 2.34 / 2.20 / 3.54) |
| beat15 | 86.9 | 10.2 (4.10 / 1.44 / 1.72 / 1.71) | 49.2 | 17.5 (8.10 / 2.26 / 1.98 / 3.96) |
| storm | 83.2 | 11.8 (3.61 / 1.38 / 1.63 / 3.97) | 49.4 | 20.7 (7.18 / 2.31 / 1.94 / 7.95) |
| marina | 88.9 | 10.7 (4.98 / 1.42 / 1.72 / 1.48) | 47.1 | 18.1 (10.24 / 1.88 / 2.01 / 2.71) |
| coast-day | 87.9 | 10.3 (4.14 / 1.72 / 1.67 / 1.60) | 49.5 | 16.6 (8.09 / 2.62 / 1.98 / 2.57) |
| coast-night | 117.4 | 8.0 (1.82 / 1.68 / 1.51 / 1.80) | 65.8 | 13.7 (4.64 / 2.64 / 1.89 / 3.30) |
| gulf-sea | 113.7 | 8.2 (2.65 / 1.41 / 1.67 / 1.38) | 67.2 | 13.6 (5.53 / 1.76 / 2.26 / 2.77) |
| helm-eye | 86.0 | 12.0 (4.55 / 2.39 / 1.37 / 2.55) | 48.6 | 21.5 (11.30 / 4.00 / 1.66 / 3.46) |
| slip | 75.7 | 12.8 (4.73 / 3.81 / 1.60 / 1.53) | 46.7 | 19.3 (8.17 / 4.71 / 1.53 / 3.73) |
| bridge | 95.7 | 9.0 (3.13 / 1.64 / 1.60 / 1.41) | 52.0 | 15.3 (7.10 / 2.01 / 2.23 / 2.79) |
| marina-night | 89.1 | 10.7 (3.09 / 3.01 / 1.58 / 2.11) | 56.9 | 16.1 (4.77 / 4.25 / 1.78 / 4.11) |

Gate: Medium ≥ 60 and High ≥ 45 on every view. Met: the lowest are 75.7 (Medium) and 46.7 (High), both the slip view.

**MetaHuman crew cost:** 0.2–0.8 ms on Medium and up to 1.3 ms on High, measured between the builds just before and after them; worst in the helm-eye view.

Medium's base pass is over 4 ms in five views, worst in the marina (4.98 ms) and Bean's slip (4.73), where the berthed boats and the near houses carry it.

## Comparison (`compare/index.html`) and blind round 6 (`blind/`)

Scores run 1 (the same as the reference) to 5 (obviously wrong). "Before" is V5's capture of the same scene (V6 did not re-score these).

| Scene | boat | sails | light | water | sky | Note |
| --- | --- | --- | --- | --- | --- | --- |
| j22-heavy-chase | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | Unchanged J/22; the crew on the rail are MetaHumans now (shirts, life jackets, caps), small in frame. |
| j22-light-chase | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | MetaHuman crew in the cockpit; otherwise as V5. |
| j22-moderate-chase | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | MetaHuman crew; as V5. |
| j22-helm-reservoir | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | From the helm the trimmer and bow are people at arm's length: skin, faces, cotton shirts, a cap's peak. The groomed hair is left off (caps). |
| j22-actioncam-lake | 3 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | The open item from V3 is closed: the stylised mannequins are MetaHumans posed from the same physics stances (helm on the tiller, trimmer and bow on the seat or rail). Faces don't animate. |
| rh-drone-cat | 4 → 2 | 3 → 2 | 2 → 2 | 1 → 1 | 2 → 2 | The Lagoon 42 is modelled: twin hulls exactly the physics', bridgedeck and saloon, bimini, trampoline forward, twin rudders; full-batten tri-radial main. |
| rh-c30-evening | 4 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | A Catalina 30 from its physics: cabin with ports, dodger, wheel, lifelines, the masthead rig on its own sockets. |
| storm-lake | 2 → 2 | 3 → 2 | 3 → 3 | 2 → 2 | 3 → 3 | Sails clean in silhouette. Not met (open): the shelf cloud's lip, bright gap and rain wall still don't read from under the storm. |
| squall-lake | 3 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 3 → 2 | The Catalina 30 modelled (it was the procedural box until V7); the jib flogs as the squall hits; lit towers beyond a dark storm base. |
| gulf-passage | 4 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | The Catalina 30 from the helm: dodger with windows, coachroof, side deck and lifelines in the swell. Fixed on the way: the sea showed through the cockpit (open shells culled; the water now also drops inside the hull). |
| bay-hobie | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | The Hobie 16: beams, trampoline, bridles, its coloured panel sail with seven full battens; MetaHuman crew in life jackets. |
| sunfish-reach | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 | 2 → 2 | The Sunfish: hull and footwell from its physics, the striped lateen sail; the sailor hiking is a MetaHuman. |

Above 2 after V7: storm-lake light, storm-lake sky, both the listed storm-lake open item. Every other category in every scene is 2 or better.

The V6 world views against North Texas photos, before (V6) and after:

| View | structures | boats | water | light | sky | overall |
| --- | --- | --- | --- | --- | --- | --- |
| marina | 2 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | – | 3 → 2 |
| causeway | 2 → 2 | – | 2 → 2 | 2 → 2 | 2 → 2 | 2 → 2 |
| riprap | 3 → 3 | – | 2 → 2 | 2 → 2 | 2 → 2 | 3 → 3 |

Marina 3 → 2 (met). Causeway unchanged at 2. Riprap 3: open, as above.

**Blind round 6** (https://claude.ai/artifact/GoytX4ZS6gBY1GPpcEGaM7): 20 stills, ten Phase 8 Commons photos and ten game frames. The answer key is in `blind/answer-key.csv`; don't open it before marking.

## Open items

- **Storm-lake sky and light (3):** the shelf cloud's curved lip, bright gap and rain wall don't read from under the storm. From the side the structure is there. The distant storm skies in two blind stills also show tiled cloud puffs.
- **Riprap shore (3):** three Blender rocks repeated read faceted at the camera's feet. A scan or a sculpted rock set would close it.
- **MetaHumans:**
  - no groom hair (caps instead);
  - faces don't animate;
  - the life jacket is a rigid shell that doesn't flex with the torso.
- **Medium base pass:** still over 4 ms in the marina (4.98 ms), slip (4.73), helm-eye (4.55), coast-day (4.14) and beat15 (4.10) views.
- **High resolution governor:** High holds 45+ fps by dropping to 82% resolution in the heaviest views (the slip, the marina) rather than at native.
- **Published dimensions:** the Hobie 16, Corsair 880 and Lagoon 42 configs disagree with their published beam or LOA (above).
- **Sound samples:** none downloaded yet (drop-in ready).
- **Galveston's piers:** still the legacy walkways.
- **Physics:** the three reference-check outs above.
