# The foam texture's cost on the Mac

The daily sweep after #383 (the foam texture, `docs/storm-water/foam-texture/`) read the High views 0.5-4 fps under the
sweep before it. Benched alternately on the packaged game (High, full resolution), #383's merge against its parent cost
0.7-0.9 ms of water GPU on the open-water views: gulf-sea 62.8 -> 59.3 fps, beat15 54.5 -> 52.6.

## Where it went

#383 samples `T_FoamLace` with hex tiling: three taps at each of two scales (3.2 m and 12.8 m). That is six
`Texture2DSampleGrad` reads, each with two hashes and a `pow`, on every water pixel near enough to resolve the pattern,
foam or not. Built locally and measured with `run-game.sh` (High, full resolution; water GPU slice, ms, two rounds):

| Variant | gulf-sea | beat15 |
|---|---|---|
| Main (833e757e) | 4.63 / 4.59 | 4.44 / 4.37 |
| The six taps off (the pattern at its means): the ceiling | 3.63 / 3.64 | 3.71 / 3.67 |
| The fine scale only (three taps; streaks from the fine tile) | 4.06 / 4.04 | 3.92 / 3.92 |

## The cut: the pattern only where foam is drawn

The pattern (lace, streaks, bubble cells) only ever shapes foam. It feeds:
- the crest's whiteness and the residue;
- `FoamTone` and the caps' cells;
- the trail's streaks;
- the shore's lapping line;
- the windrows' faint scum;
- #390's gale streaks.

So it is taken at most once (`FOAM_PAT`), at the first place that draws foam:
- **First site:** where a crest or the residue is drawn, a boat's wash breaks, the foam grid holds a trail, the swash
  laps, or the sea's mean wind is a gale (over 24 kn: the streaks cover the sea). The crest, residue, wash, trail and
  swash are worked out ahead of it; none of them needs the pattern.
- **Second site:** a windrow's line.

"Drawn" means visibly: 1/255 of opacity or more (`FOAM_SEEN`). The residue's ramp, the fold table's exponential cover
and the trail's decay never quite reach zero, so "above zero" took the pattern almost everywhere: gulf-sea 4.34 / 4.63 ms.
The trail is drawn as 0.85 trail^1.2 at 0.45 of its pattern or more, so it shows from a trail of 0.022, and its threshold
is that.

Where none of them shows, the pattern changes no displayed value. The one place it still could: where a windrow or the
player's waterline foam is a pixel's only foam, `FoamTone`'s bubble-cell factor takes its mean (0.85, the 0.7-1 range's
middle). A windrow is drawn at 5% opacity, and the waterline foam's tone runs to 1 where it is strong.

| Water GPU, ms (run-game, High) | Main | This cut | Ceiling |
|---|---|---|---|
| gulf-sea | 4.63 / 4.59 | **4.14 / 4.21** | 3.63 / 3.64 |
| beat15 | 4.44 / 4.37 | **3.75 / 3.77** | 3.71 / 3.67 |

beat15 is back to within 0.1 ms of the ceiling. gulf-sea gets back 0.44 of its 1.0 ms. With the crest and residue alone
deciding it (not exact: the wash, trail and swash then show the mean pattern), gulf-sea's water is 3.83 / 3.84 ms. So most
of what is left there is the boat's own wash near the camera, which is foam drawn. Pixels are shaded in SIMD groups (32 on
Apple GPUs), so a group pays the taps if any pixel in it draws foam.

## The look

`compare-15.jpg` and `compare-28.jpg`: main (left) against this cut (right), Gulf, High, 15 and 28 kn, the same camera.
The two runs are not frame-locked (the boat, waves and clouds move between them), so a pixel difference measures the
scene, not the foam. The foam reads the same in both: the caps' lace and holes, the streaks along the wind and the bubble
cells.

## Fallback, not in this change

Drop the coarse scale on Medium and High only, taking the streaks from the fine tile's G (variant three above): about
0.5 ms more where the pattern is taken, Ultra untouched. It changes the streaks' scale (3.2 m against 12.8 m tiles), so it
waits for a call on the look.
