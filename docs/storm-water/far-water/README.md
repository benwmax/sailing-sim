# Storm water, step 1: far water and far caps (PC)

Bean's playtest (Oct 27): "the whitecap/foamy patches have strange repeated patterns, and in the distance the whitecaps
start to look like ice floating on the water". The plan ("Stormy waves and whitecaps: fix plan") gives the PC the
shader-only steps (1, 3, 6) and the Mac the wave code (2, 4, 5). This is step 1. It changes how foam is drawn and where it
sits, not how much there is: the cover tests (Whitecaps, WhitecapsSeen, FarCapFlecks, FarCapSprites) pass unchanged in
what they hold.

## What changed (`scripts/make_materials.py`; `WaterTests.cpp` mirrors the flecks)

- **Far roughness (a).** Past the mesh's fade (`WaveFadeMeters`, 900 m) the long waves left the normal and the far water
  went flat and glossy under the caps. Their slope variance now stays as roughness to the horizon (LEAN, as the chop's and
  the ripples' mips already do): about a third of Cox and Munk's mean square slope for the sea's mean wind, faded in as the
  mesh's waves fade out.
- **Far caps as dashes (b, c).** The round, world-fixed, one-brightness flecks (`FLK`) are now laid in the wind's frame.
  - Each cell holds a dash along the crest (half-lengths 0.42 by 0.09 of the cell) with a soft streak downwind (an
    elliptic cone at 0.35).
  - Each dash has its own brightness, 0.5 to 1.
  - Its 4 s life flares and then fades: min(1, 8 age) (1 - age)^1.5.
  - The cells drift downwind at 2 m/s with the waves.
  - Where the long waves are drawn, the caps gather on their crests and thin in the troughs (1 + clamp(4 (1 - J), -0.9,
    0.9), whose mean over a wave is 1).
  - The probability still makes the mean the cover: `SailingSim.Visual.FarCapFlecks` checks the new shape's mean at the
    lake's cover and a Gulf gale's.
- **The far sprites (`M_FarCap`, 300 m to 1.25 km, low views).** They read as the band of "ice" (smooth white ovals).
  - Each sprite now has a ragged top: seven heaps along it, each its own height.
  - Each has its own brightness (0.55 to 1), dimming as it ages.
  - Sprites drift downwind with `MPC_World.Wind`.
  - They are 1.45 times as wide, so they carry the same cover as before. AWaterSurface's tiles and their Monahan cover are
    untouched.
- **Foam under the reflection (d).** At a grazing view the sea reflects most of the sky, so the foam's opacity falls with
  Schlick's Fresnel for the flat sea (to 45% at the horizon). The haze then lies over both alike.

## Proof

Galveston Bay off Red Fish Bar, J/22 at TWA 60. Each sheet shows main (before) against this branch (after), at the helm
eye and in a 120 m chase.

| Wind | Ultra | High | Beaufort photo beside it |
| --- | --- | --- | --- |
| 15 kn (force 4) | `15kn-ultra.jpg` | `15kn-high.jpg` | (none in the set: forces 5 to 9) |
| 20 kn (force 5) | `20kn-ultra.jpg` | `20kn-high.jpg` | force 5 |
| 28 kn (force 7) | `28kn-ultra.jpg` | `28kn-high.jpg` | force 7 |
| 35 kn, Mistral, the Gulf (force 8) | `35kn-ultra.jpg` | `35kn-high.jpg` | force 8 |

- `clip-28kn-strip.jpg`: every tenth frame of a 10 s clip at 28 kn (chase, Ultra, 0.1 s frames, recorded at quarter speed).
  The GIFs (6.6 MB each, before and after) stay out of git, in `Artifacts/storm/` on the PC.
- `foam-mask-28.jpg`: the whitecaps alone (`-SailingDebugFoam=1`), straight down from 150 m, 250 m across.
- `foam-autocorr-before.png`, `foam-autocorr-after.png`: that mask's autocorrelation (`Tools/water/foam_autocorr.py`).
  Cover is 3.52% before and 3.56% after. Both have the same peak at **22.9 m**, 0.31 across the frame: the 23 m chop tile,
  in which every cap folds. This step doesn't touch it (it is near water, where the caps are the fold itself); the Mac's
  step 4 removes it.

What it fixes is the far band: at 35 kn the caps 300 m to 1 km out were a band of even white ovals. They are now ragged,
varied and dimmer at the horizon (compare the top strip of `35kn-ultra.jpg`).

## Cost

Main's `M_WaterV4` and `M_FarCap` against this branch's, alternating, two rounds; RTX 4090, 1920x1080, uncooked, 28 kn.
Each cell is main → branch:

| View | Tier | fps | GPU ms | water ms |
| --- | --- | --- | --- | --- |
| 120 m chase | Ultra | 67.2 → 67.4 | 8.46 → 8.58 | 0.47 → 0.48 |
| 120 m chase | High | 69.8 → 70.1 | 4.88 → 4.87 | 0.46 → 0.46 |
| Helm eye | Ultra | 64.9 → 63.4 | 8.69 → 8.84 | 0.31 → 0.32 |
| Helm eye | High | 68.8 → 71.5 | 5.12 → 5.11 | 0.31 → 0.32 |

The GPU cost is about 0.1-0.15 ms on Ultra and nothing on High; the fps differences are within run-to-run noise.

## Credits

The Beaufort sea-state photos (forces 5 to 9) are from the WMO/NOAA Beaufort scale set on Wikimedia Commons, in the
public domain:
- `File:Beaufort_scale_5.jpg` through `File:Beaufort_scale_9.jpg`
- <https://commons.wikimedia.org/wiki/File:Beaufort_scale_5.jpg> (and _6 to _9)

They are fetched into the git-ignored `Data/Reference/raw/beaufort/` with their `credits.json`.
