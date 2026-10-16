# W8 item 2: whitecaps seen versus measured

The W7 numbers had the lake at 20 kn breaking at about twice its fresh-water target (0.96 % against 0.44 %:
Monahan's W = 3.84e-6 U^3.41 times W0's 0.4 for fresh water). Yet round 11's `r11-lake-beat20` showed almost no caps.
Both were partly right. The test measured the cover it was built on, but the camera drew a different sea, as specks.

## How the camera was measured

`-SailingDebugFoam` (new) draws M_WaterV4's whitecaps alone: black water, no reflection, and a pixel white with the
probability of its cap cover (a fixed hash per pixel, so the temporal AA keeps it binary). `=2` shows the crests
alone, `=3` where the fold is under the threshold. The stills are counted by distance from the camera's pinhole geometry
(`camera.json`). The clean view is a free camera 2 m over open water, looking away from the boat toward the I-30
bridge (`-SailingCamWorld=5420,520,2,300,-6`). The helm and action-cam views are round 11's 20 kn beat.

## What was wrong

1. **Cap size.** The caps folded on the full Jacobian of the 23 m chop tile: specks about 0.4 m across (463 of them in
   6350 m^2 at the lake's 20 kn cover, from a standalone count on the grid). At 0.3 % of the surface they read as
   glints, not whitecaps. Caps break on whole crests. `FWaveDetail::JCap` is the Jacobian of the displacement
   box-blurred over 2 texels either way (0.36 m). The same cover then comes in 64 caps about 1 m across (1.5 m at
   25 kn), the size of a 20 kn reservoir's caps.
2. **The test's sea isn't the game's.** The threshold was calibrated on the test's 8 km-fetch sea. The lake grows its
   sea on the effective fetch at the boat (W3), and it folds far less at the same threshold. With the larger caps, the
   20 kn view showed three caps where Monahan's fresh-water share gives about fifty. The renderer now solves the
   threshold on the sea it draws, every detail frame, on a worker (`FWaveDetail::CapThreshold`). It takes the quantile
   of the whitecap Jacobian that caps Monahan's cover for the mean wind times the water body's share, and the shift
   per e-fold of cover about it (for puffs and lulls):
   - the long trains are scaled by the sea map at the camera (W3), and the chop by its short scale;
   - the long trains are sampled over about 170 m, not on the 23 m tile, which holds only one of their wavelengths;
   - the long trains' fold is faded with the mesh, as the vertex shader does: a train under 8 vertex spacings fades
     out. There are four solves, at spacings 0.5, 1, 2 and 4 m (within 32, 64, 128 and 256 m of the camera), and the
     shader picks by its distance;
   - `DrawnFoldScale` 0.85: the drawn surface folds a little less deeply than its CPU copy. The screen's share of
     Jt under 0.7 and under 0.8 matched the CPU's samples with their deviation from 1 scaled by 0.85 at both. Likely
     the texture's bilinear filter and the vertex interpolation of the long trains' fold; not isolated.
   `FoamThresholdAt` and `CapSlopeAt`, refit for the new Jacobian on the test's sea, are the fallback until the first
   solve, and what the tests hold to Monahan.
3. **Mips.** Thresholding a mip-mapped Jacobian loses the caps, because a mip averages J toward 1 (flat). In
   practice, anisotropic filtering keeps mip 0 at grazing angles, so this was not what the lake view lost. But from a
   higher camera it would be. Past a texel per pixel, the cover now comes from a fold table (`DetailC`: per texel, how
   folded it is against four thresholds about the solved one), whose mips average cover. It is read at the sampler's
   own mip (the short axis, or a sixteenth of the long one). A blend weight of zero had let the table's term leak
   speckle into the near water; it now sits in a branch.
4. **Lace.** The lace pattern multiplied a cap's whiteness by 0.62 on average. Its floor rose from 0.35 to 0.8 (mean
   0.92), so the white area is the folded area the tests hold to Monahan.

## Numbers

`SailingSim.Visual.Whitecaps` (the drawn waves at 8 km fetch, the fallback threshold):

| Wind | Monahan, salt | Sea | Lake (target 0.4x) | Bay (target 0.7x) |
|---|---|---|---|---|
| 6 kn | 0.02 % | 0.00 % | 0.00 % | 0.00 % |
| 10 kn | 0.10 % | 0.14 % | 0.07 % (0.04) | 0.11 % (0.07) |
| 14 kn | 0.32 % | 0.29 % | 0.12 % (0.13) | 0.21 % (0.22) |
| 20 kn | 1.09 % | 0.98 % | 0.42 % (0.44) | 0.70 % (0.76) |
| 25 kn | 2.33 % | 2.28 % | 0.89 % (0.93) | 1.56 % (1.63) |

W7 had the sea at twice Monahan from 14 kn up. It now matches within 10 % from 14 kn.

`SailingSim.Visual.WhitecapsSeen` (new): the fold table holds the grid's cover within 30 % at mips 1 to 5, where a
mip-mapped Jacobian has lost it by mip 2 or 3. A threshold solved on one stretch of the lake's sea caps another
stretch at 0.163 % (target 0.129 %) at 14 kn, 0.478 % (0.435 %) at 20 kn and 1.054 % (0.931 %) at 25 kn.

On screen, 20 kn, open water from 2 m (crests only, binary, `after/w8-open20-debug.png`):

| distance | 5-10 m | 10-20 m | 20-40 m | 40-80 m | 80-160 m | 160-320 m |
|---|---|---|---|---|---|---|
| crest cover | 0.29 % | 1.41 % | 0.60 % | 1.16 % | 0.39 % | 0.54 % |

The target at the mean wind is 0.44 %, more in puffs (`-SailingGust=0.2`). At 14 kn the near screen cover is 0.133 %
against 0.13 %. Before, the same view counted 0.22-0.35 % in 0.4 m specks (`before/w8-open20-debug.png`, caps with
their residue), which read as almost nothing.

![before (left) and after (right): round 11's 20 kn beat from the action cam, the helm view, open water at 20 kn](whitecaps-before-after.jpg)

## The reference

Photos of Texas reservoirs (Ray Hubbard, Lewisville, Grapevine) in a 15-20 kn southerly, the kind that clubs and
fishing reports post (described from general knowledge; nothing downloaded): a dark, short, steep chop with scattered
white horses across the open water. Each cap is a broken crest a metre or two long that lasts a second or two and
leaves a pale streak. A frame from the shore or a boat shows a dozen to a few dozen of them, thinning out of sight
toward the far shore; at 15 kn they are occasional. The after stills now read that way at 20 kn. The lake keeps W0's
0.4 of Monahan. If the blind round finds the lake still too smooth at 20 kn, that share is the knob
(`WhitecapScaleFor`), now that the screen follows it.

## Still open

- `DrawnFoldScale` is measured on one view and wind (20 kn, the lake), and matched at 14 kn. Its cause is not isolated.
- Far out (past a texel per pixel at the sampler's mip) the caps become their mean cover, a faint brightening. Real
  distant caps stay visible as flecks: they are brighter than their share of a pixel would make them.

## Gate

`scripts/gate.sh --scope water` passes (141 tests, including `SailingSim.Visual.Whitecaps`, `WhitecapsSeen`,
`WaveMatch` and the W3 `SailingSim.Lake.SeaStateSwan`).

| view | Medium fps | High fps |
|---|---|---|
| beam8 | 90.4 | 55.9 |
| beat15 | 85.9 | 52.0 |
| storm | 71.8 | 49.3 |
| marina | 89.9 | 50.9 |
| coast-day | 82.8 | 48.9 |
| gulf-sea | 105.5 | 61.6 |
| helm-eye | 81.6 | 47.8 |
| slip | 79.1 | 47.3 |
| bridge | 98.4 | 55.6 |
