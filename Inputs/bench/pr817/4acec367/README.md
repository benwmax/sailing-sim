# PR #817 (film mode) on the PC at 4acec367, Nov 23 2026

`4acec367` ("Film mode: log the live cloud and reflection settings") on cc8e91cb. It ran in a new worktree (removed
afterwards) with nothing pushed, while the frigate light shards ran alongside.

- **Build:** `build.ps1` Succeeded, 0 errors.
- **Tests:** `SailingSim.Smoke.FilmMode` 4/4.
- **Package:** Development `Packaged\Windows-pr817-4acec367` (kept); cook 0 errors, 1 warning.
- **Runs:** two tripod runs, Ultra 3840x2160, `-SailingRecord=2` (120 of 120 frames each, about 1.3 s per frame),
  with the same settings as cc8e91cb.

## The "Film quality:" lines, verbatim

(a) `-SailingFilm -SailingMotionBlur=0`:

```
[2026.11.23-22.53.04:150][  0]LogSailing: Display: Film quality: r.VolumetricRenderTarget=1 r.VolumetricRenderTarget.Mode=3 r.VolumetricRenderTarget.UpsamplingMode=3 r.VolumetricCloud.ViewRaySampleMaxCount=512 r.Water.SingleLayer.Reflection.DownsampleFactor=1 r.Lumen.Reflections.DownsampleFactor=1 r.TSR.History.ScreenPercentage=200 r.AntiAliasingMethod=4 r.ScreenPercentage=100
```

(b) the same plus `-SailingCloudMode=1`:

```
[2026.11.23-22.56.46:845][  0]LogSailing: Display: Film quality: r.VolumetricRenderTarget=1 r.VolumetricRenderTarget.Mode=1 r.VolumetricRenderTarget.UpsamplingMode=3 r.VolumetricCloud.ViewRaySampleMaxCount=512 r.Water.SingleLayer.Reflection.DownsampleFactor=1 r.Lumen.Reflections.DownsampleFactor=1 r.TSR.History.ScreenPercentage=200 r.AntiAliasingMethod=4 r.ScreenPercentage=100
```

**The switch reaches the cloud render target:** (b) runs `r.VolumetricRenderTarget.Mode=1`, (a) `Mode=3`. Everything
else is the same.

## Cloud edges (`clouds-1to1-mode3-vs-mode1.png`: frame 60, 800x450 at 1:1 from (400,450))

- The two runs differ by 1.35 grey levels on average over the frame, a small, real change. On cc8e91cb, with the switch
  not reaching the target, they differed by 0.38.
- **Both still show the same regular blocky tiles, about 8 px,** along the cloud edges and through the thin parts.
  Mode 1 shifts a few edge pixels but doesn't remove the grid.
- So the stair-steps come from neither the render target's mode nor motion blur. Mode 3 at full resolution with 512
  view-ray samples still tiles. That points to something tiled in the cloud material itself (the weather map's or a
  noise texture's texel at this distance), not to the reconstruction.

Bean's Saved was held aside and restored (7B5CA7BE). Crew link unlinked only, 541 crew files intact.
