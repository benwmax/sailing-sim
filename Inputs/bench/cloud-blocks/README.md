# Cloud blocks: sky cache A/B on Windows-pr817-4acec367 (PC, Nov 23 2026)

The 4acec367 `cloudA-noblur` tripod run, repeated on `Packaged\Windows-pr817-4acec367` with the same shot and args
(Ultra 3840x2160, `-SailingFilm -SailingMotionBlur=0 -SailingRecord=2`, J/22, Lake, seed 7). Both args exist in that
build (`SailingEnvironment.cpp:464` `-SailingNoSkyCache`, `:101` `-SailingSkyCacheSize=<w>,<h>,<steps>`).

| Run | Frames | s/frame | Mean difference from baseline (frame 60) |
|---|---|---|---|
| baseline (4acec367 cloudA, cache 8192x1024) | 120 | 1.33 | |
| (1) `-SailingNoSkyCache` | 120 | 1.18 | 14.10 grey levels |
| (2) `"-SailingSkyCacheSize=16384,2048,192"` | 120 | 1.19 | 2.14 |

The two new runs' logs both say "120 of 120 frames recorded", with the Film quality line unchanged (Mode=3,
512 samples).

**Verdict:** yes on both counts. **In (1) the tile grid is gone:** every cloud is marched live. They look different:
bluer-grey and softer-lit, with a fine stippled noise in place of the blocks. **In (2) the tiles are about half the size**
(about 4 px instead of 8), with the same look as the baseline. The blocks are the sky cache's panorama texels.

`clouds-1to1-baseline-nocache-cache16k.png`: frame 60, an 800x450 crop at 1:1 from (400,450), baseline, (1) and (2)
left to right. The s/frame are wall-clock on the recording PC, with nothing else running this time. Bean's Saved was
held aside and restored (7B5CA7BE).
