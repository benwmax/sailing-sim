# Storm water, step 3 on the PC: the foam texture

Bean's playtest (Oct 27): "the whitecap/foamy patches have strange repeated patterns". Close up, every cap carried a
tread-plate lattice: the products of crossed sines that drew its lace, its bubble cells and the residue's streaks. This
step replaces them with one baked foam texture. It changes what the foam looks like, not how much there is: the mask the
cover tests hold to Monahan (`caps`) is untouched, and each channel keeps the mean of the pattern it replaces.

## What changed

**The texture.** `T_FoamLace` (`/Game/Materials/Foam`, 1024², linear, uncompressed with mips, wrapping) is baked by
`Tools/water/make_foam_texture.py` from our own procedural noise, with no photographs, and imported by
`scripts/import_foam_texture.py` (run it before `make_materials.py`). It has three channels:

| Channel | What it draws | Made of | Tile |
| --- | --- | --- | --- |
| R lace | A crest's fresh foam: bubble films and holes | Worley cell walls at two sizes (about 16 and 6 cm), opened where fractal noise is low | 3.2 m |
| G streaks | Ageing foam drawn out by the wind | Ridged noise low-passed 9:1 along U (FFT on the torus, so no lattice), thinned in patches | 12.8 m |
| B cells | The foam's marbling | Bright bubble mass parted by thin, irregular dark veins (ridged filtered noise) | 3.2 m |

- Each channel is **histogram-matched** to the sine pattern it replaces (lace, streak × lace, cells). Means and spreads
  agree to 3 decimals (0.250, 0.125 and 0.250 means), so every factor in the shader set against them keeps its mean:
  the crest's 0.92 white, the residue's pattern, the cells' 0.6.
- Two tries that didn't survive: 2 cm bubble cells (mipped to flat white within a few metres) and one-size Worley
  clumps (they read as cobbles, another regular pattern).

**The shader** (`V4_SHADE` in `scripts/make_materials.py`; `FOAM_MEAN` holds the means):
- The texture is read in the local wind's frame (U downwind) with **hex tiling** (Mikkelsen, JCGT 2022). That is three taps on a
  triangle grid, each at a random offset, blended so the variance holds (around the channel means), at two scales:
  - the fine one (3.2 m) for R and B;
  - the coarse one (12.8 m) for G.
- **Drift and flow blending.** The foam drifts downwind at 3.5% of the wind. Each tap runs its own 6 s phase: its
  offset is redrawn and its weight falls to nothing at each phase's start, with the phases staggered by grid vertex. The
  drift therefore never stretches where the local wind turns. This is the two-phase flow blend's idea, carried by the
  tiling's own three taps, so it costs no taps beyond them.
- **Six taps at most**, only where the pattern resolves. Past `patFade` it is skipped and the factors take the means, as
  before.
- **What reads which channel:**
  - Fresh foam reads R: a crest's whiteness, `saturate(0.8 + 1.3 lace)`.
  - Ageing foam reads G: the residue's pattern and the foam grid's trails, which thin into strings along the wind.
  - Both are broken by B: the tone and the opacity's cells.
- The swash and windrow lines read the lace as before.

## Proof

Galveston Bay off Red Fish Bar, J/22 at TWA 60; the 35 kn row is the Gulf in the Mistral. Main **6bbe9b09** (with storm
steps 2 and 4) is the before; this branch's material on the same build is the after. Uncooked, 1920×1080. Each sheet shows
the 120 m chase (top) and the helm eye (bottom).

| Wind | Ultra | High | Beaufort photo |
| --- | --- | --- | --- |
| 15 kn (force 4) | `15kn-ultra.jpg` | `15kn-high.jpg` | (none: the set is forces 5 to 9) |
| 20 kn (force 5) | `20kn-ultra.jpg` | `20kn-high.jpg` | force 5 |
| 28 kn (force 7) | `28kn-ultra.jpg` | `28kn-high.jpg` | force 7 |
| 35 kn, Mistral, the Gulf (force 8) | `35kn-ultra.jpg` | `35kn-high.jpg` | force 8 |

- `close-28.jpg` is where the change shows: 12 m up at 28 kn, Ultra.
  - Before: the tread-plate lattice in every cap.
  - After: irregular marbling and lace, no repeat.
  - At the chase's 120 m and the helm eye the caps are a few pixels across, and the sheets look alike there, as they
    should: the far caps (flecks and sprites) are step 1's and unchanged.
- `clip-28kn-strip.jpg`: every tenth frame of a 10 s clip at 28 kn (chase, Ultra, 0.1 s frames, recorded at quarter
  speed). The GIFs stay out of git, in `Artifacts/storm2/` on the PC.
- `foam-mask-28.jpg`: the whitecaps alone (`-SailingDebugFoam=1`), straight down from 150 m, 250 m across.
- `foam-autocorr-main.png`, `foam-autocorr-branch.png`: that mask's autocorrelation (`Tools/water/foam_autocorr.py`).
  - Cover is 3.22% on main and 3.32% on the branch.
  - **The 22.9 m spike that step 1 measured is gone** on this main: the Mac's steps 2 and 4 (long-train jitter, the
    second chop cascade) removed it. Past 3 m the strongest peak is now 0.03 at 18 m along y (0.095 along x is the 3 m
    edge of the search, the caps' own size), on main and branch alike.

The Beaufort photos are WMO plates from Wikimedia Commons ("Beaufort scale 5", "7" and "8", public domain), kept in
the git-ignored `Data/Reference/raw/beaufort` with `credits.json`. Only the sheets carry them.

## Cost

Main's `M_WaterV4` against this branch's on the same build, alternating, two rounds of 20 s. RTX 4090, 1920×1080,
uncooked, 28 kn. Each cell is the mean of the two rounds, main → branch:

| View | Tier | fps | GPU frame (ms) | Water slice (ms) |
| --- | --- | --- | --- | --- |
| Chase, 120 m | Ultra | 62.0 → 65.1 | 8.89 → 9.10 | 0.48 → 0.49 |
| Helm eye | Ultra | 63.4 → 64.7 | 8.93 → 9.13 | 0.31 → 0.32 |
| Chase, 120 m | High | 68.4 → 72.6 | 5.07 → 5.03 | 0.47 → 0.47 |
| Helm eye | High | 69.8 → 67.0 | 5.18 → 5.26 | 0.31 → 0.31 |

- **GPU.** About +0.2 ms of GPU frame on Ultra and within ±0.1 ms on High. The water slice moves by 0.01 ms at most.
- **Why so little.** The six taps run only where the foam pattern resolves, a small share of the screen.
- **fps.** The changes are run-to-run noise (game-thread bound uncooked; they go both ways).

## Tests

The full suite passes on MSVC on 6bbe9b09: 264 of 264, including `SailingSim.Visual.Whitecaps`, `WhitecapsSeen`,
`FarCapFlecks` and `FarCapSprites` (the cover is the mask's, which this step doesn't change).
