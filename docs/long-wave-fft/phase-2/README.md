# Long-wave FFT phase 2: parked (Oct 30 2026)

Phase 2 was dropped when the second Mac lane was retired. This branch (`long-wave-fft-2`) holds the work as it stood.
Nothing here is on main; phase 1 (the engine, #379) is.

## Done and built in Unreal

- **Physics.** `FWaveField` reads the FFT for components 0-23 when an `FLongWaves` is attached, and never in the
  calibration sea (`SetLongWaves`, `UsesLongWaves`, `LongRatiosAt`).
  - The sea map scales each band by its three sines' energy-weighted ratio.
  - Bands, Hs, Tm01 and the mean direction come from the published summary (`FLongWaves::FSummary`, `Moments`).
  - The orbital flow decays per band at its mean wavenumber.
  - Check `FieldWiring`: Hs is the sines' exactly, and Height and Sample are the FFT plus the short sines to 1e-16.
    All 12 `SailingSim.Physics.LongWaves.*` tests pass.
- **Game.** `-SailingLongWaves=fft|sines` or `sailing.LongWaves 1` turns it on; the default is off.
  - The game mode produces keys two ahead of the clock on a worker, and synchronously after a hitch. Result: one sync
    miss per run, at the start.
  - It logs `Long waves (FFT): ...` every 2 s.
- **Renderer.** `AWaterSurface::UpdateLongWaves` packs the frame's grids on a worker into two bordered atlases (8 bands of
  64², 528 x 66: A float Dx, Dy, H, dDx/dy; B half Sx, Sy, dDx/dx, dDy/dy).
  - `M_WaterV4` takes a `[branch]` on `LongParams.x` (`long_fft_terms` in make_materials.py).
  - The cap threshold solve and the crest spray fold on the grids (`FLongWaves::FoldAt`).
- **Sign fix.** The choppy displacement's sign is now Gerstner (toward the crests), as the shader draws the sines.

## Not done

- **Water gates.** Neither the switch-off nor the switch-on water gate has finished.
  - The one switch-off run that got to its bench had storm on High at 44.5 against the 45 floor.
  - Its back-to-back run with main was cut off, so it is unjudged.
- **WaveMatch.** `SailingSim.Visual.WaveMatch` still mirrors only the sines.
- **GPU cost.** No GPU timing yet for the FFT branch (16 texture fetches a vertex against 24 sincos and 7 atlas fetches).
- **Proof stills.** The stills here are uncooked `run-game.sh` frames with motion blur on. The swirl in the 15 and 28 kn
  overhead FFT stills is the camera turning with the boat mid-tack, not the water. Reshoot with motion blur off before
  showing Bean.

## Proof stills

Today's 24 sines on the left, the FFT on the right; rows are 15, 20, 28 and 35 kn.

- `long-waves-helm.jpg`: from the helm.
- `long-waves-chase.jpg`: a 120 m chase.
- `long-waves-top.jpg`: straight down from 150 m.
