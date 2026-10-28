# Storm water step 5: long waves as an FFT shared by physics and renderer (build brief)

For the Mac lane (wave code, physics, wiring, gate). Written Oct 28 2026 from main at 8e9972aa (#368) and the storm-water
plan "Stormy waves and whitecaps: fix plan" (https://claude.ai/artifact/4CjnGhbMFpfFmjqaMMHyCz, step 5). Class and file
names below are suggestions; the repo's real types win. Planning only: nothing here has been built or benched yet, and
every cost number marked "estimate" must be measured in phase 1 before later phases rely on it.

- Bean's problem (Oct 27 playtest): at 20 kn and up the waves look patterned. Step 5 removes the cause for the long waves:
  they are 24 fixed sine trains today. It also makes storms hold up close (random, grouped, steeper seas) and keeps the
  boat floating on exactly the drawn surface.
- Bean on this step (Oct 28 12:27 UTC): asked for parallel work, "you choose". This is the brief; the build is not started.
- Steps 1 (far water, #364) is merged. Steps 2 (direction jitter) and 4 (second chop cascade) are separate Mac items:
  section 9 says how they interact with this one.

## 0. Decisions this brief makes (change them before phase 1 if you disagree)

| # | Question | Brief's answer | Why |
|---|---|---|---|
| 1 | Where is the FFT computed? | **On the CPU, in SailingPhysics, once per world.** The renderer uploads the same grids the physics reads. No GPU FFT. | The physics needs the field on a headless server anyway (online rule 1). One computation means one truth: the boat floats on the drawn surface by construction. This is how `FOcean` and `FWaveDetail` already work. A GPU FFT would be a second implementation that has to match the first. |
| 2 | Does the quality tier change the physics grids? | **Never.** Every tier, the server and the standalone tools use the same cascades and sizes. A tier may only change how the renderer *draws* them (mips, distance fades). | Online: every machine must float boats on the same sea. Low tier is the min-spec stand-in, so the CPU cost must fit there too. |
| 3 | What stays as sines? | The **calibration sea** (`bCalibrationSea`: polars, reference checks) keeps its 48 sines, unchanged. The game sea's **short components 24-47** (under 3.6 m) stay sines in the physics as today. Only components 0-23 move to the FFT. | The fleet's polars were sailed in the calibration sea; moving it would move every polar. Short sines feel small to the boat and cost little. |
| 4 | Lake first or the Gulf first? | **Lake and bay first** (phases 2-3), then the open sea `FOcean` moves onto the same engine (phase 4). | The weave Bean saw is the lake's 24 sines. `FOcean` is already an FFT, just a coarse one (64²). |
| 5 | How does the sea map (W3, per-point fetch) survive? | **One ratio channel per cascade** instead of one per sine (24 → 2 or 3, plus the short scale). The cascades split the spectrum by wavelength, so each cascade is a frequency slice with its own ratio. | You can't scale individual FFT modes per point. Fetch mostly changes the sea by frequency (short fetch = lower and shorter waves). Its direction effect is already damped (`kSeaTowardWind` 0.75). Phase 1 proves this against SWAN before anything is wired. |

## 1. What the code has today (main 8e9972aa)

- **`FWaveField`** (`SailingPhysics/Public/Waves.h`, `Private/Waves.cpp`): 48 Airy trains, 16 log-spaced bands from 0.18 to
  2.4 Hz (48 m to 0.27 m deep), 3 directions per band.
  - `AnchorDirections` lays the 3 directions at -Δ, 0, +Δ about the wind (±3° jitter). It lays them again after a turn
    past 45°, keeping the phase continuous at `HoldX/HoldY`, which the game mode sets to the **player's boat position**.
  - Amplitudes approach a JONSWAP target band by band (`GrowthSeconds` = 8 T², 5-300 s) in `Update(Dt)`. The game mode
    calls `Update` with the **frame's** `DeltaSeconds` (`SailingGameMode.cpp` ~933).
  - `Height`, `Sample`, `OrbitalFlow`, `BandsAt` and `SignificantHeightAt` sum all 48 trains. Each is scaled by the sea
    map's ratio (`SeaRatiosAt`: 24 long channels, then one short channel). Then `FOcean` is added if there is one.
- **`FSeaMap` / `FSeaFetch`** (`SeaState.h`): 16-direction effective fetch per cell, and per cell 25 ratio channels
  (`kSeaChannels`). Built on a worker when the wind changes. The shader reads them as a 7-tile RGBA16F atlas (`SEA_ATLAS`
  in `make_materials.py`).
- **Renderer** (`AWaterSurface`, `SailingSim/Private/WaterSurface.cpp`, and `M_WaterV4` from `scripts/make_materials.py`):
  - `V4_WPO` evaluates the first 24 trains per vertex with Gerstner choppiness 1.5 (`long_wave_terms()`: 24 sincos plus
    slopes and the fold Jacobian). Each train fades before the ring spacing would alias it, and everything fades to flat
    by `WaveFadeMeters` (900 m).
  - Under 3.6 m (`SplitHz` 0.657) the waves come from `FWaveDetail`: a 128² chop FFT on a 23 m tile, plus ripples and
    capillaries on High. These are evaluated on a worker at 30 Hz, blended for the frame on a worker, uploaded with mips.
  - The open sea (`FOcean`, Gulf) is two 64² cascades (480 m, 60 m). It is evaluated on the game thread, blended there
    and uploaded every frame (`UpdateOcean`).
- **The CPU mirrors the drawn long waves in several places.** Each must move to the grids:
  - `FWaveDetail::LongJacobian` / `FLongJacobians`: the cap threshold solve in the upload worker.
  - The crest-spray loop in `AWaterSurface` (loops `LongComponents`).
  - `SailingSim.Visual.WaveMatch` and the cap tests in `WaterTests.cpp`.
- **Physics reads** (per boat, at 120 Hz, `PhysicsHz`; boats step in parallel since Perf 1):
  - `FBoatModel` calls `Sample` once per hull column near the water (`BoatModel.cpp` ~663).
  - It calls `OrbitalFlow` at 2 stations × 2 depths (~591).
  - Added resistance uses `BandsAt` (~809).
  - Other readers: buoys (`NavaidsActor`), the free camera, the HUD, `SeaTrials`, `AutoTrim`, `Wind`.
- **`FOcean`** (`Ocean.h/.cpp`) is the precedent to copy and improve.
  - The physics and the renderer read one CPU grid, 30 Hz keys blended linearly.
  - The cache is lock-free on a hit; a miss evaluates under a lock.
  - Its FFT is a naive double radix-2 (`Fft`, `Fft2`), duplicated in `WaveDetail.cpp`.
- Bench numbers to protect (`docs/budget/ledger.csv`, Mac, Oct 17): High helm-eye 55.1 fps (gate 45), Medium helm-eye
  85.9 (gate 60). Water GPU 2.29 ms (High helm-eye), 1.9 ms (Medium helm-eye). Water game-thread CPU 0.11-0.21 ms. Boat
  physics 0.012-0.055 ms. Since then helm-eye High has run close to its floor in several gates, so treat High helm-eye as
  the tight view.

## 2. Design

### 2.1 The engine: `FLongWaves` (new, `SailingPhysics/Public/LongWaves.h`)

A set of FFT **cascades**, each a 128² periodic grid on its own tile, carrying one wavelength range of the spectrum.

Proposed layout (phase 1 confirms or changes it by measurement):

| Cascade | Tile | Cell | Wavelengths it carries | When it runs |
|---|---|---|---|---|
| L1 "sea" | 97.3 m, sampled rotated 0° | 0.76 m | 3.6 m (the `SplitHz` edge) to 12 m | Always on lakes and bays |
| L2 "long" | 331 m, rotated 27.4° | 2.59 m | 12 m to 44 m (to tile/2 when L3 is off) | Always |
| L3 "swell" | 1,409 m, rotated 61.9° | 11 m | 44 m and up | Only when the spectrum has energy there (open sea, storms) |

- Each wavelength belongs to exactly one cascade, split by |k|, as `FOcean` does. A cascade carries waves at least four
  cells long, so bilinear sampling holds the slope.
- Tile sizes are mutually incommensurate and the cascades are turned against each other. Their repeats never line up,
  and none shares a lattice with the 23 m chop tile (or with step 4's new tiles).
- A cascade whose variance is under 1e-6 m² is not evaluated. On a calm lake that is most of them; on the lake L3 never runs.

**Spectrum.** It is the same one the sines carry today, so energy and growth laws are unchanged:
- JONSWAP (γ 3.3) at the target Hs/Tp of `FWaveField::TargetSignificantHeight` / `TargetPeakPeriod` at the reference
  fetch (the sea map's 15 km, or the params' fetch).
- Normalized exactly as `ComputeTargetAmplitudes` / `BandAmplitudeFactor` normalize the whole 0.18-2.4 Hz spectrum. The
  long cascades get precisely the variance bands 0-7 have today.
- Donelan-Hamilton-Hui / Banner sech² spreading (`DirectionalSpreading`), continuous in direction, nothing upwind.
- Mode energy = S(ω) D(θ) (dω/dk)/k Δk², as in `FOcean::Configure`. Depth dispersion ω² = g k tanh(k h) at the world's
  median depth (`SetDepth`).

**Modes.** Each mode has a fixed wavenumber on the grid and a random complex amplitude. Use Tessendorf's Hermitian form
h̃(k,t) = h0(k) e^{iωt} + conj(h0(-k)) e^{-iωt}, as `FWaveDetail` does, so every output field is real and two fields pack
into one complex transform.

**Growth (replaces `Update(Dt)` for these components).**
- Each mode's amplitude approaches its target with τ = `GrowthSeconds(1/f)`, stepped once per **key**, which is 1/30 s
  of world-clock time.
- Targets are recomputed from the sea's wind every 15th key (2 Hz). The pow/exp per mode is too dear at 30 Hz for 33k
  modes.
- **A wind shift needs no re-anchoring.** The old direction's modes decay over their τ while the new direction's grow.
  That gives the cross sea after a big shift that W3 asked for. `AnchorDirections`, `HoldX/HoldY` and the 45° re-anchor
  go away for the FFT sea, and with them the player's position in the wave field (online rule 2).

**Fields per cascade per key (13 real, packed two per complex transform = 7 inverse FFTs):**

| Field | Physics | Renderer |
|---|---|---|
| H (height) | yes | yes |
| Vz (dH/dt) | yes | no |
| Sx, Sy (slope) | yes | yes |
| U, V (surface orbital velocity) | yes | no |
| Ax, Ay (orbital acceleration, exact -ω² terms; `FOcean` differences frames, which is coarse for foils) | yes | no |
| Dx, Dy (choppy displacement, λ = `Choppiness`) | phase 3 option | yes |
| Jxx, Jyy, Jxy (fold Jacobian terms) | caps (CPU) | yes |

- Orbital velocity under the surface: per cascade, the velocity-weighted mean k with the finite-depth profile
  cosh(k(h-d))/sinh(kh) (exp(-kd) when deep), as `FOcean::OrbitalVelocity` does with its exponential. Each cascade is a
  narrow wavelength slice, so one k per cascade is close. `SurfingFlow` and `FoilInertia` check it.
- Added resistance needs bands: bin the modes' energy by wavelength (16 bins, as `FOcean::Bands`), per cascade. That lets
  `BandsAt` scale them by the sea map's per-cascade ratio.

**The FFT kernel.**
- Replace the duplicated naive double radix-2 with one float kernel in `SailingPhysics/Private/Fft.cpp`. Precompute
  twiddles (made in double, stored as float) and the bit-reverse table. Do rows, a transpose, then rows (cache friendly).
  The real-pair packing gives two fields per transform.
- Measured in the cloud on a slow core (2.1 GHz Xeon, clang -O2, 128² complex 2D): naive double radix-2 0.75 ms; float
  with a twiddle table and transpose 0.25 ms. 256² was 4.3 ms and 1.46 ms.
- Estimate for the M5 Pro: 0.1-0.15 ms per 128² transform, so 7 transforms × 2 lake cascades ≈ 1.5-2 ms of worker time
  per key.
- The transforms are independent, so cascades and field pairs can run in parallel with a deterministic join (each
  transform is single-threaded with a fixed order, so the result never depends on thread count).
- If the measured cost is over budget, use radix-4 and NEON/SSE next, then pocketfft. Pocketfft is BSD-3, which is fine
  commercially, but it needs a row in `docs/licences/` and a line in `CREDITS.md`.
- `FOcean` and `FWaveDetail` can switch to the new kernel in their own phases (4, and step 4's PR), not in phase 1.

### 2.2 Keys, the producer, and who reads what

```
world clock (sim time, fixed 120 Hz steps)
   │
   ├─ every key (1/30 s): FLongWaves::Advance(key)        ← SailingPhysics, deterministic, no Unreal
   │     amplitudes step toward targets (targets every 15th key)
   │     then Evaluate(key + 2) on a worker (game) / inline (server, standalone tools)
   │           │
   │           ▼
   │     ring of 4 keys × cascades × 13 float fields (≈ 0.85 MB per cascade-key; ≈ 7 MB for 2 cascades)
   │     published with a release store, as FOcean's cache
   │
   ├─ physics (boats in parallel, 120 Hz): FWaveField::Sample / Height / OrbitalFlow / BandsAt
   │     = Σ cascades [ ratio_c(x) × lerp_t( bilinear(key k), bilinear(key k+1) ) at R_c·x ]
   │       + short sines 24-47 (as today) + FOcean (until phase 4)
   │     a key not ready yet → evaluated under the lock (correct, slower); counted as long_fft_sync_misses (target 0)
   │
   └─ AWaterSurface (game thread starts it, worker does it, the detail path's pattern from Perf 1 fix 5):
         blend keys k, k+1 for the frame's time → pack render fields → build mips → UploadPackedMips
         per cascade: tex A RGBA32F (Dx, Dy, H, Jxy), tex B RGBA16F (Sx, Sy, Jxx-1, Jyy-1), with mips
         M_WaterV4 vertex shader: per cascade 2 SampleLevel at the mip the ring spacing needs (replaces each train's
         spacing fade), × the sea map's cascade ratio; same Gerstner convention as the physics
```

- **Heights stay float32 on both sides.** Physics reads the CPU float grid; the GPU reads the same values from RGBA32F.
  Slopes and Jacobian go in half floats (they feed shading and caps, not the boat). Precedent: `OceanA/B` are already
  `PF_A32B32G32R32F` sampled with `SampleLevel` on Metal.
- **Same convention as today in phase 2.** The physics reads H at the undisplaced point (today it ignores the choppy
  displacement too). Phase 3 measures a displaced lookup as an option: two fixed-point steps x₀ ← x − D(x₀). It matters
  for the water-through-hull work (`docs/water-hull-clip`), but it changes the physics, so it ships only with its own
  numbers.
- **Distance.** The mips do the anti-aliasing the per-train fade did. `WaveFadeMeters` stays. Step 1's far roughness
  (LEAN) can read the cascades' slope variance per mip instead of the analytic per-train sum.
- **Sea map.** `FSeaMap` keeps its 16-bin fetch build. Its channels become, per cell:
  - one ratio per long cascade (energy-weighted over that cascade's modes, each mode's own direction's fetch pulled 75%
    toward the wind, as now);
  - the short scale;
  - one spare (the ocean share in phase 4).

  That is one RGBA16F tile instead of seven, which is cheaper in the vertex shader.

### 2.3 What the game mode drives

- The sea's wind and fetch go into `FLongWaves` exactly as they go into `SetWind` today (`WaveParams`).
- Two spots read the **player's boat** today:
  - `HoldX/HoldY`, which this design removes;
  - the front's outflow test at `BoatPos`.

  Phase 3 moves the outflow test to the world's sea reference point (the lake's centre), if that doesn't visibly change
  how a front's sea arrives. Otherwise leave it and write it down as a known rule-2 gap in `docs/long-wave-fft/`.
- Advance on world-clock keys, never on `DeltaSeconds` (rule 3). Then the same world time gives the same sea at 30, 60
  or 144 fps.

## 3. Cost budget (Mac M5 Pro, packaged, the gate's views)

| What | Budget | How it is measured |
|---|---|---|
| Frame rate | Medium ≥ 60, High ≥ 45 on every view of `--scope water` plus the sentinels (helm-eye, slip, coast-day) and the storm view on Medium | `scripts/gate.sh` |
| GPU water slice | ≤ main + 0.10 ms on High helm-eye, beat15, storm. Expected to **drop**: 24 sincos and 7 atlas fetches per vertex become about 4-6 texture fetches | bench.json `gpu.water` (`-SailingProfileGPU`) |
| Game-thread water CPU | ≤ main + 0.10 ms (it only starts the worker and calls the upload) | `water_cpu_ms` |
| Worker: lake long FFT | ≤ 2.0 ms per key for all running cascades (≤ 6% of one core at 30 Hz); ≤ 4.0 ms with the ocean layer (phase 4) | new bench.json field `long_fft_ms` (mean and p99 per key) |
| Physics per boat (rule 10) | `boat_physics_ms` ≤ main + 10%. Bilinear reads of 2 cascades × 2 keys should cost less than 48 sin/cos per sample | ledger column, plus `SailingSim.Physics.ParallelBoatsShareTheSea` timing |
| Sync misses | 0 per bench run (a miss is a hitch) | new `long_fft_sync_misses` |
| Memory | CPU ≤ 16 MB, GPU textures ≤ 4 MB | `peak_ram_mb`, memreport |
| Low tier | Same physics grids; the renderer may sample one mip coarser on Low. Low must hold its current fps (≥ 100 on the bench views) | bench Low |

On a dedicated server the cost is per world, not per player: one evaluation per key serves every boat.

## 4. Determinism and online readiness

- **A pure function.** Grid at key k = f(world seed, cascade id, the amplitude state at key k). The amplitude state
  depends only on the wind and fetch history sampled at keys. Nothing reads the frame time, the quality tier or the
  player.
- **Seeds (rule 5).** Phases and Gaussian amplitudes come from `FPortableRandom` seeded with
  `HashCombine(HashCombine(WorldSeed, HashString("longwave")), HashString("L1"))` (the cascade's own name), never
  from evaluation order, never `std::` distributions.
- **Time precision.** Mode phase = φ − ω t, computed in **double** and reduced mod 2π before it goes to float, so a
  world clock days long still gives millimetre heights. A test runs at t = 1e6 s.
- **Threads.** The same key gives bitwise the same grid whatever the worker count or order. `AsyncPhysicsMatchesSync` and
  `ParallelBoatsShareTheSea` stay green.
- **Across platforms: close, not bitwise.**
  - Compile `Fft.cpp` and `LongWaves.cpp` with `-ffp-contract=off` on clang, so arm64 doesn't fuse multiply-adds that
    MSVC (`/fp:precise`) doesn't.
  - Apple libm and the MSVC CRT can still differ by an ulp in `cos`/`exp`/`pow` during spectrum setup. So a golden test
    holds Mac and PC to 1e-5 m, not to the bit.
  - Online, the server is the authority for boats, so tiny wave differences between clients don't accumulate.
- **The online-readiness rules, checked:**
  1. State lives in SailingPhysics (`FLongWaves`). `AWaterSurface` only draws.
  2. No player lookups: the anchor at the boat goes away; the front's outflow point is noted in 2.3.
  3. Keys come from the world clock.
  4. No input involved.
  5. Portable random and hashes from stable ids.
  6. Nothing persisted.
  7. Nothing saved.
  8. No scoring involved.
  9. Time compression stays at the top: keys follow world time however fast it runs.
  10. `long_fft_ms` and `boat_physics_ms` are in the gate.
  11. No secrets.

## 5. Tests

New, standalone (SailingPhysics, no Unreal: `scripts/long-wave-check.sh` builds `Tools/LongWaveCheck/main.cpp` like
`wave-check.sh`), mirrored as automation tests `SailingSim.Physics.LongWaves.*`:

| Test | Holds |
|---|---|
| `Spectrum` | Configured variance = the sines' bands 0-7 variance at 10, 15, 20, 28 kn (1%). Tm01 and mean direction within 2% / 2°. No energy outside each cascade's range. |
| `MatchesDirectSum` | At 64 random points and 3 times, every field (H, Vz, Sx, Sy, U, V, Ax, Ay, Dx, Dy, J terms) equals the direct sum over the cascade's modes within 1e-4 (catches sign, packing and axis mistakes). |
| `TimeBlend` | Linear blending between keys is within 2% of the exact height for L1's shortest wave (3.6 m, 1.5 s period at 30 Hz keys). |
| `Spreading` | Energy per direction bin, summed over modes, follows `DirectionalSpreading` (no three-spike structure). |
| `Growth` | Each band's approach time matches `GrowthSeconds` (as `WaveBandGrowth`). |
| `WindShift` | 30° and 90° shifts: the height at a point never steps (Δh per 1/120 s within the waves' own motion + 1 mm). After 3 τ the old direction's energy is under 5%. |
| `FrameRateFree` | 30 s of world time stepped at 30, 60 and 144 fps gives bitwise-equal grids. |
| `Determinism` | Bitwise equal for 1, 2 and 8 workers; equal after a save-less restart at the same world time. |
| `LongClock` | At t = 1e6 s, heights match the direct sum within 1 mm. |
| `Golden` | 64 heights from a fixed seed match a checked-in table within 1e-5 m. The table is made on the Mac; the PC runs it in its next build. |
| `NoWeave` | Over a 300 m patch at 20 kn, the 2D height autocorrelation has no peak over 0.25 away from zero lag except at the cascades' known tile lags, reported with their heights. Today's sines fail it (the diamond); the FFT must pass. |
| `SeaMapSwan` | `scripts/wave-check.sh --map` with per-cascade channels: median abs(log Hs error) against SWAN ≤ 0.10 (0.08 today) and Tp bias ≤ 5%. If it misses, try 3 lake cascades before anything else. |

Changed:
- `SailingSim.Visual.WaveMatch`: the shader's vertex formula mirrored against the grids (both modes in phase 2).
- The cap tests (`Whitecaps`, `WhitecapsSeen`, `WhitecapOnset`, `WhitecapSize`, `FarCapFlecks`, `FarCapSprites`) take
  the long fold from the grids. Cover still follows Monahan; any re-fit is written down.

Physics rebaseline (phase 3 for lakes, phase 4 for the open sea). Every tolerance change gets a written reason in
`docs/long-wave-fft/`:
- **Should be unchanged** (the calibration sea is untouched): `PolarGate`, `Fleet.Polar.*`, the polar side of
  `ReferenceChecks`. Confirm; any change is a bug.
- **May move** (the game sea's surface is now random and grouped): `WaveGrowthSwan`, `SeaStateSwan`, `WaveBandGrowth`,
  `WaveSpreading`, `AddedResistanceInWaves`, `WaveAddedResistanceScaling`, `Surfing`, `SurfingFlow`, `FoilInertia`,
  `BoatRidesTheWaves`, `ParallelBoatsShareTheSea`, `SailClothSeaway`, `MultihullCrewSeat`, `LongPassageStable`,
  `Race.AiFleetRace`.
- **Open sea (phase 4)**: `OceanSpectrum`, `GalvestonSwell`, `GaleTack`, `MaxiGale`, `Prologue.Gale`.
- **Boat motion check.** J/22 and Catalina 30 at 20 kn, beam and beat:
  - heave and pitch standard deviation within 15% of today;
  - added resistance within 10%;
  - peak events (the 1-in-100 heave) may rise. That is the wave groups and it is expected, but report it.

## 6. Proof for Bean

The same set as the storm plan, so he judges by eye:
- Helm eye and a 120 m chase at 15, 20, 28 and 35 kn, on High (Mac) and Ultra (PC's next build), sines against FFT
  through the phase 2 switch.
- A 10 s clip at 28 kn.
- Straight down from 150 m over 250 m (height shading), where the weave shows plainest.
- The `NoWeave` autocorrelation images before and after.
- The WMO Beaufort photos (forces 5-9) beside the matching winds in phase 4.

## 7. Phases (one PR each, against main, never stacked)

1. **Engine, no behaviour change.** Branch `long-wave-fft-1`, SailingPhysics only.
   - Contents: `FLongWaves`, the float FFT kernel, `Tools/LongWaveCheck` and `scripts/long-wave-check.sh`, the
     `LongWaves.*` tests. Nothing in the game calls it yet.
   - Exit: measured kernel and per-key ms on the M5 Pro; `NoWeave`, `SeaMapSwan`, `MatchesDirectSum` and `Golden` green.
   - Records the final cascade layout in `docs/long-wave-fft/README.md`, including the L1 tile decision. If L1's 97 m
     repeat shows in `NoWeave` or the overhead view, try 192² (mixed radix 2·3) or 256² for L1 and re-budget.
   - Gate: `--scope water` (the game is unchanged, so the bench must equal main).
2. **Draw it and float on it, behind a switch (default off).** Branch `long-wave-fft-2`.
   - The switch: `-SailingLongWaves=fft|sines` and a dev console variable. It is not saved and not in the player's
     settings.
   - When on:
     - `FWaveField`'s game sea reads `FLongWaves` for components 0-23;
     - the sea map writes per-cascade channels;
     - `AWaterSurface` uploads the cascades;
     - `M_WaterV4` takes the FFT branch (a uniform `[branch]`, both paths compiled; check the dead path costs ~0);
     - caps, crest spray, buoys and `WaveMatch` read the grids.
   - Proof sheets (section 6) for both settings.
   - Gate twice:
     - off must equal main;
     - on must meet section 3.
3. **Make it the default for lakes and bays.** Branch `long-wave-fft-3`.
   - Flip the default.
   - Advance on world-clock keys.
   - Drop the anchor and `HoldX/HoldY` for the FFT sea; move the front-outflow point (2.3).
   - Physics rebaseline (section 5); the displaced-lookup option is measured and either shipped with its numbers or left
     off.
   - Gate `--scope all` (it changes physics and every view).
   - Merge after Bean has seen the proof sheets and said yes: it is the biggest visible change to the water since W3.
     The coordinator brings him the sheets.
4. **The open sea on the same engine.** Branch `long-wave-fft-4`.
   - `FOcean` becomes an ocean layer of `FLongWaves`: its own spectrum and mask, 128² cascades in place of the two 64²
     ones, keeping `MakeMask`/`SetMask`, and moved off the game thread.
   - Storm steepness: choppiness rises with the sea's steepness, with a fold clamp (J ≥ 0.15 after the clamp, so crests
     sharpen but never self-intersect).
   - Beaufort comparison.
   - Rebaseline the open-sea tests (section 5).
   - Gate `--scope water` plus gulf-sea and coast-day.
5. **Cleanup.** Branch `long-wave-fft-5`.
   - Remove the 24-sine shader path, the seven-tile atlas and the switch.
   - Sines remain only in the calibration sea (physics only).
   - Docs. Small; gate `--scope water`.

Not in this plan: moving the calibration sea to the FFT. It would move every polar; only worth it if a later physics
round wants a new calibration anyway.

## 8. Risks

| Risk | Watch for it with | If it happens |
|---|---|---|
| L1's tile repeat shows (97 m) | `NoWeave`, the overhead view, the chase clip | Bigger L1 (192² or 256², about 2-4.5× L1's cost), or split L1's range across two tiles |
| The sea map loses fidelity at 2 channels | `SeaMapSwan` | 3 lake cascades (L1 3.6-8 m, L2 8-20 m, L3' 20 m+), about +50% worker cost |
| Boats behave differently in a grouped sea | Section 5 motion check, gale and surfing tests, Bean's helm feel | Expected in part (real seas are grouped). If heave or pitch statistics move more than 15%, look for a normalization bug before re-tuning boats |
| Worker hitch gives a sync miss | `long_fft_sync_misses` | Prefetch three keys ahead instead of two |
| Cross-platform drift | `Golden` on the PC | Find the libm call; table it if needed |
| Merge conflicts with steps 3, 4 and 6 | Section 9 order | Never run two branches on the cap code or `V4_WPO` at once |

## 9. How it fits with the other storm-water steps

- **Step 2 (jitter the 24 trains)** is replaced for the game sea once phase 3 lands. Do step 2 only if phase 3 is more
  than about a week away. It is small and has no GPU cost, but its look and tests get rewritten here.
- **Step 4 (second chop cascade, cap clustering)** touches the same cap code: `FWaveDetail`, the cap threshold solve and
  foam grid in `AWaterSurface`, and the cap section of `make_materials.py`.
  - Merge step 4 before phase 2 opens, or hold phase 2 until it does.
  - Step 4's wave-group factor (the long-wave envelope) should read "whatever the long field is" through one function.
    Phase 2 then swaps that function's source, and the clustering becomes the FFT's real wave groups.
  - Step 4 can move `FWaveDetail` onto the new FFT kernel only after phase 1 merges.
- **PC steps 3 (foam texture) and 6 (gale streaks)** are shader-only, in `V4_SHADE`. Phase 2 rewrites the long-wave part
  of `V4_WPO` and the sea atlas. Whoever merges second rebases; the PC lane re-runs its Ultra bench on the FFT path once
  phase 3 is in.
- **Order for the Mac lane:**
  1. step 4;
  2. this brief's phase 1 (it can run in parallel with step 4: SailingPhysics only, different files);
  3. phase 2, then 3, then 4, then 5.

## 10. Online-readiness rules (paste into every PR)

1. Game state lives in SailingPhysics or a sim layer; actors only draw and read input.
2. No new "the player" lookups in sim code (GetFirstPlayerController, PlayerId = 0); systems take a list of vessels.
3. Time comes from the world clock, never from a boat.
4. Input reaches a boat only as an FBoatControls step.
5. Seeded things use the shared portable random and hash, seeded from stable ids; no std:: distributions.
6. Things that persist are placed in lat/lon or by stable id, not map metres.
7. Saved data carries a version number and string ids.
8. Race finishes, drill passes and scores come from the sim, never the HUD.
9. Time compression is one single-player switch at the top, never assumed inside world systems.
10. The gate records physics cost per boat.
11. No keys, tokens or server secrets in the repo (it is public).

## Sources

- Code read: benwmax/sailing-sim main 8e9972aa: `Waves.h/.cpp`, `WaveDetail.h/.cpp`, `SeaState.h`, `Ocean.h/.cpp`,
  `WaterSurface.h/.cpp`, `BoatModel.cpp`, `SailingGameMode.cpp`, `scripts/make_materials.py` (`SEA_ATLAS`,
  `long_wave_terms`, `V4_WPO`), `scripts/wave-check.sh`, `docs/budget/ledger.csv`, `docs/bench-fast`,
  `docs/visual-4`, `docs/storm-water/far-water`.
- Tessendorf, "Simulating Ocean Water" (SIGGRAPH course notes): the Hermitian FFT ocean and choppy displacement.
- The storm-water plan's sources (Sea of Thieves SIGGRAPH 2018 talk; Crest ocean, open source) for cascaded FFT oceans
  shared with physics.
