# Storm look 1: the whitecap life cycle

Bean's report (sailing-feedback #24) was that the caps read as crackled white plates, all one size, with no streaks.
Three things in `V4_SHADE` (`scripts/make_materials.py`, M_WaterV4) caused it:

- the cap's opacity followed the marbling channel, from 0.4 to 1 by bubble cell, so its dark veins drew the crackle;
- every cap was drawn the same way from birth to death;
- the drawn caps sat exactly on the mask, so neighbouring breakers were all the same size.

## What a whitecap does

- **Stage A, the active crest.** It is a dense, bright heap of bubbles (Monahan and Lu 1990).
- **Stage B, the patch it leaves.** The patch opens into lace, its holes growing as it thins. The last of it is drawn out
  by the wind into strings and dissolves. Callaghan, de Leeuw, Cohen and O'Dowd (2008) filmed both stages.
- **Breakers gather.** They come in a wave group's highest waves (Banner, Babanin and Young 2000), so they are bigger and
  longer-lived at a group's peak and smaller between.

## What the shader does now

Only the drawn foam changes. `crest`, `residue` and `caps`, the mask that the cover tests and `-SailingDebugFoam`
measure, are untouched. `FoamLife` (a material scalar, 1 by default) blends the new look over the old one;
`-SailingClassicFoam` sets it to 0.

- **Groups (`capVar`, 0..1).** Value noise on two scales:
  - the group's: 90 m along the wind by 50 m across, moving downwind at a fifth of the wind (about half the chop's phase
    speed);
  - the cap's own: 12 m.
  It moves the drawn edge (not the mask) by `STORM_CAP_VARY` (0.8) of the cover's e-fold either way. Drawn cover is
  scaled by e^+-0.8 from group to group, and the mean is about the same.
- **Age (`capAge`).** It is 0 in a crest's core, about a quarter at its feathered rim and 1 in its residue. Holes open in
  the lace channel as it ages: the low values open first, so they grow as a network of films. The hole threshold is
  `STORM_FOAM_HOLES` (0.3) x age, times 0.6 to 1.4 by group (a small cap opens sooner).
- **Opacity.** The core follows the marbling gently (0.8 to 1), not by 0.4 to 1. Far out, where the patterns fade, it
  goes to 0.9 on a crest and 0.55 in residue.
- **The trail (stage B).** AWaterSurface's foam grid fades the foam as exp(-t / 4 s), so the trail's value is its age:
  - just off the crest it is lace with small holes;
  - the holes grow as it fades;
  - from about half its life it turns into strings along the wind (the streak channel, thinning as it goes) that
    dissolve.
  A group's bigger breakers leave foam that lasts longer. The trail's tone goes from 0.75 to 0.5 with age.
- **Relief.** Fresh foam stands a centimetre or two proud of the water, so the light catches it. Its height comes from
  the drawn foam, its freshness and its marbling. The slope is solved from the screen derivatives through the pixel's
  footprint (the 2x2 inverse of `fdx`, `fdy`), faded out with the patterns and capped at 0.4. The foam and the water
  share one normal (Single Layer Water). The derivatives are taken outside every branch. `STORM_FOAM_BUMP` 0 turns it
  off.

## Cost

Two value-noise lookups, a few smoothsteps and one pair of derivatives per water pixel, all outside the far table's
branch. The Mac's water gate and the PC's 4K storm view measure it against the 3 ms budget.
