# Storm water, step 6 on the PC: gale streaks and spindrift

The plan's last PC step: from Beaufort 7 up, foam blown into streaks along the wind over the whole sea, and the crests'
spray tied to the caps, with spindrift from Beaufort 8. Both fade in with the wind, so a 15 or 20 kn day is unchanged.
The caps' mask (what `Whitecaps`, `WhitecapsSeen` and `-SailingDebugFoam` measure) is untouched.

WMO's descriptions, which this follows:
- force 7: "white foam from breaking waves begins to be blown in streaks along the direction of the wind";
- force 8: "edges of crests begin to break into spindrift, foam blown in well marked streaks";
- force 9: "dense streaks".

## The streaks (`V4_SHADE` in `scripts/make_materials.py`, `M_WaterV4`)

- **Two sets of soft bands along the slow wind** (`WindSlow`, the frame the slicks and windrows use).
  - Rows are about 6 and 2.2 m apart.
  - Each row has its own place and width: 8-22% of its spacing, wandering along it.
  - They meander and are broken into dashes some 35 and 15 m long.
  - They drift downwind at 3% of the wind.
- **Ragged, not ruled.** Each band is broken up by T_FoamLace's streak channel (strings along the wind) and mottled by
  its marbling. The first cut drew clean thin lines that read like scratches on the water.
- **Wind.**
  - They fade in from 24 to 32 kn of the sea's mean wind (`WindParams.z`).
  - They fill in, with more rows drawn, toward 40 kn.
  - They are drawn at aged foam's tone (0.6), at 0.7 opacity.
- **Far out**, a band narrower than the pixel's footprint across it is drawn as its mean cover. The streaks turn into a
  faint whitening of the far sea rather than a moire.
- **Cost.** All of it sits in one branch that only runs in a gale. On a 20 kn day the shader is main's.

## Crest spray and spindrift (`AWaterSurface::UpdateSpray`, `WaterSurface.cpp`)

The crest spray already existed: 24 random points a frame within 60 m of the camera, firing where the waves fold past a
fixed 0.45. Three changes, scaled by `AWaterSurface::GaleSprayFor(mean kn)`:

- **Where.** The fold is now tested against the threshold the water draws its caps with (`CapCalib`'s, solved for this
  sea). It blends from the old 0.45 as the gale fades in, so below 24 kn nothing changes. A calm sea's solved -1 means
  no crest spray.
- **How much.** Up to four times the crest points (96) and twice the drops from each, by 32 kn.
- **Spindrift.** From 33 to 41 kn (Beaufort 8), a share of the breaking crests also throw a sheet of mist torn off the
  edge. It is 1.2 to 2.4 m across, carried at 60-85% of the wind and low over the water, with a short-lived torn sheet
  under it.

Each seeded draw is its own const: the order of draws inside one expression differs between compilers.

## Proof (`docs/storm-water/gale-streaks/`)

Galveston Bay off Red Fish Bar, J/22 at TWA 60; 35 kn is the Gulf in the Mistral. Before and after are both on main
abefe981 (the foam texture in): main's build and material against this branch's. Uncooked, 1920×1080.

Each sheet shows a 60 m chase, a 120 m chase and the helm eye, with the WMO Beaufort plate beside the Ultra ones:

| Wind | Ultra | High | Beaufort |
| --- | --- | --- | --- |
| 15 kn (force 4) | `15kn-ultra.jpg` | `15kn-high.jpg` | (none: the set is forces 5 to 9) |
| 20 kn (force 5) | `20kn-ultra.jpg` | `20kn-high.jpg` | force 5 |
| 28 kn (force 7) | `28kn-ultra.jpg` | `28kn-high.jpg` | force 7 |
| 35 kn, Mistral, the Gulf (force 8) | `35kn-ultra.jpg` | `35kn-high.jpg` | force 8 |

- **At 15 and 20 kn** the two sides are the same sea.
- **At 28 kn** faint streaks begin.
- **At 35 kn** the streaks run through the caps along the wind and the crests smoke.
  - They are still sparser than the WMO plate's force 8. Density and contrast are two numbers (`galeDens`, the 0.7 opacity)
    if Bean wants more.
- `clip-35kn-strip.jpg`: every tenth frame of a 10 s clip at 35 kn (60 m chase, Ultra, 0.1 s frames at quarter speed),
  where the spindrift shows. The GIFs stay in `Artifacts/gale/` on the PC.

## Cost

RTX 4090, 1920×1080, uncooked, 35 kn in the Mistral (the only wind where both halves run fully).

**The streak shader.** The same build with main's and this branch's `M_WaterV4`, alternating, two rounds of 20 s. Each
cell is main → branch:

| View | Tier | GPU frame (ms) | Water slice (ms) |
| --- | --- | --- | --- |
| Chase, 60 m | Ultra | 8.42 → 8.69 | 0.76 → 0.80 |
| Helm eye | Ultra | 9.17 → 9.26 | 0.43 → 0.43 |
| Chase, 60 m | High | 5.26 → 5.23 | 0.66 → 0.75 |
| Helm eye | High | 5.28 → 5.25 | 0.37 → 0.41 |

**The spray.** CPU: the water's game-thread time, which includes the spray, from the proof stills, main's build against
this branch's:

| View | Tier | water_cpu_ms |
| --- | --- | --- |
| Chase, 60 m | Ultra | 2.95 → 4.49 |
| Helm eye | Ultra | 3.06 → 4.67 |
| Chase, 60 m | High | 2.29 → 2.71 |
| Helm eye | High | 2.30 → 3.03 |

- **GPU.** In a full gale the shader costs up to about 0.3 ms on Ultra and nothing measurable on High.
- **CPU.** The spindrift costs about 1.5 ms on Ultra and 0.4-0.7 ms on High.
  - Ultra's spray pool is 3,000 instances against High's 1,200, and a gale keeps it full.
  - If that's too much, the spindrift's share or Ultra's pool is the knob.
- **Lighter winds.** Below 24 kn neither half runs. At 15 kn, and at 28 kn with the gale half in, water_cpu_ms is within run noise of main's.

## Tests

- `SailingSim.Visual.GaleSpray` (new) holds the fade-ins: 8-24 kn keep the usual 24 crest points with no gale and no
  spindrift; force 7 is half in; force 8 is a full gale with spindrift starting; force 9 has all of it; and it only grows
  with the wind.
- Full tests on MSVC: 280 of 280 pass on the branch merged with main 84dc2f4b.
