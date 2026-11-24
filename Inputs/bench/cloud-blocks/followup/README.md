# Cloud blocks follow-up: no sky cache, by cloud render mode (PC, Nov 23 2026)

The same tripod `cloudA-noblur` run on `Packaged\Windows-pr817-4acec367` (Ultra 3840x2160, `-SailingFilm
-SailingMotionBlur=0 -SailingRecord=2`, J/22, Lake, seed 7), all with `-SailingNoSkyCache`. Each run's "Film quality"
log line confirms the mode it ran in.

| Run | `r.VolumetricRenderTarget.Mode` | Frames | s/frame | Mean difference from (1) |
|---|---|---|---|---|
| (1) `-SailingNoSkyCache` (from the first A/B) | 3 | 120 | 1.18 | |
| (3) + `-SailingCloudMode=1` | 1 | 120 | 1.18 | 1.02 |
| (4) + `-SailingCloudMode=0` | 0 | 120 | 1.19 | 0.82 |

`clouds-1to1-nocache-mode3-mode1-mode0.png`: frame 60, an 800x450 crop at 1:1 from (400,450), runs (1), (3), (4) left to
right.

**Verdict: the dark stipple goes in (4), mode 0.**

- **(4) mode 0:** the cloud edges and the dark under-sides are smooth. The fine stippled noise of (1) is gone, with
  slightly softer edges.
- **(3) mode 1:** the stipple is **stronger and coarser** than in (1). The bright cloud edges break into speckled
  dots, and the dark patches are grainier.
- **No change in speed:** about 1.18 s/frame for all three on the recording PC.

So without the sky cache the stipple is the render target's reconstruction noise (modes 1 and 3), and mode 0 (full-res
direct) removes it at no cost to recording time here. Bean's Saved was held aside and restored (7B5CA7BE).
