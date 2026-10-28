# Long waves as an FFT (storm water step 5)

The plan is the build brief `Inputs/storm-water/long-wave-fft/brief.md` (inputs branch). The waves Bean saw weave at 20 kn
and up are FWaveField's 24 long sine trains (3.6 m to 48 m). This step replaces them with an FFT sea that the physics and
the renderer share.

## Phase 1: the engine (this PR)

Nothing in the game calls it yet.

- `FFft2D` (`Fft.h`) is one float radix-2 kernel: twiddles made in double, a bit-reverse table, and rows, transpose, rows.
  It is compiled without fused multiply-adds.
- `FLongWaves` (`LongWaves.h`) is the sea. It uses Tessendorf's Hermitian modes on 128² grids, with 13 real fields per
  cascade packed two per transform (7 transforms).
  - The fields are H, Vz, Sx, Sy, U, V, Ax, Ay, Dx, Dy, and the three Jacobian terms.
  - Spectrum: each of FWaveField's bands 0-7 carries exactly the variance the sines give it. The direction comes from the
    sech² spreading (nothing travels upwind). Dispersion is at the world's depth.
  - Growth: each mode approaches its target over its band's `GrowthSeconds`. It steps once per 1/30 s key, and the
    targets follow the wind every 15th key.
  - A wind shift needs no re-anchoring.
  - The grids at a key depend only on the world seed, the cascade's name and the amplitudes.
  - Physics reads `Sample`: bilinear, blended between two keys, from a ring of 4 keys. A hit is lock-free; a miss is
    counted.
- `LongWaveChecks.h` holds the checks. The automation tests `SailingSim.Physics.LongWaves.*` and
  `scripts/long-wave-check.sh` (standalone, about 2 s) both run them.

### Cascade layout (as built)

| Cascade | Tile | Rotation | Cell | Carries | Modes (lake) |
|---|---|---|---|---|---|
| L1 | 97.3 m | 0° | 0.76 m | 3.6 m to 12 m | 2,072 |
| L2 | 331 m | 27.4° | 2.59 m | 12 m to 48 m (to tile/2 when L3 is off) | 2,240 |
| L3 | 1,409 m | 61.9° | 11 m | 44 m and up | runs only when the spectrum reaches past 165 m (open sea); never on a lake |

L1's 97 m tile: `NoWeave` finds the sea correlated 0.17-0.23 with itself at L1's tile lags, which is L1's share of the
variance. The 24 sines reach 0.67 at 81 m. Whether the 97 m repeat shows by eye is a phase 2 question, for the overhead
view.

### Measured on the M5 Pro (clang -O2, standalone)

| What | Result | Budget |
|---|---|---|
| Kernel, 128² complex 2D inverse | 0.090 ms (p99 0.100) | brief's estimate 0.10-0.15 |
| Kernel, 256² | 0.53 ms | |
| A key's grids, 2 cascades, 4,312 modes, 1 thread | 1.36 ms (p99 1.40) | ≤ 2.0 ms per key |
| The same on 4 threads (deterministic join) | 0.49 ms (p99 0.51) | |
| One physics read (13 fields, 2 cascades, 2 keys) | 0.095 µs | today's 48-sine `Sample`: 0.38 µs |

### Checks

| Check | Result |
|---|---|
| Spectrum | variance equal to the sines' bands 0-7 (0.00%) at 10-28 kn, deep and 5 m; Tm01 within 0.3%; direction within 0.1° |
| MatchesDirectSum | every field within 3.6e-7 of the straight sum (L1, L2, and L3 on an open sea's range) |
| TimeBlend | 0.12% of L1's RMS half way between keys |
| Spreading | the sech² within a tenth of the peak bin, in 20° bins (10° bins alias on L1's 7° lattice at 12 m) |
| Growth | every band reaches 1 - 1/e in exactly its `GrowthSeconds` |
| WindShift | 30° and 90°: no height step (5.8 mm per 1/120 s at most, inside the waves' own motion); the old direction under 0.01% after 3 τ |
| FrameRateFree | 30, 60, 144 fps give the same grids to the bit |
| Determinism | 1, 2 and 8 workers, and a restart at 300 s, to the bit |
| LongClock | t = 1e6 s: 1.2e-7 m from the straight sum |
| Golden | 64 heights (`LongWaveGolden.inl`, made on the Mac). The PC holds them to 1e-5 m in its next build |
| NoWeave | 0.17 away from zero lag (limit 0.25); the sines reach 0.67 |
| SeaMapSwan | **fails on period**, see below |

### SeaMapSwan: one sea-map channel per cascade is not enough

Run with `scripts/long-wave-check.sh --swan`: 1,050 cases at SWAN's ten points, written to
`Artifacts/long-wave-sea-map.csv`.

| Sea map channels for the long waves | Median abs(log Hs error) | Median abs(log Tp error) | Tp bias |
|---|---|---|---|
| One per sine (today) | 0.070 | 0.108 | +2.3% |
| One per cascade (2) | 0.069 | 0.203 | **+22%** |
| 3 groups of bands (0-2, 3-5, 6-7) | 0.071 | 0.159 | +10% |
| 4 groups (0-1, 2-3, 4-5, 6-7) | 0.071 | 0.126 | +6.4% |
| One per band (8) | 0.071 | 0.113 | +2.4% |

Height is right with any channel count. The period is not. On a short fetch the long bands fall away faster than the
short ones, so the local peak moves to shorter waves. One scale for a whole cascade can't move the peak, so a sheltered
spot keeps the open lake's long period.

The brief's fallback, three lake cascades, leaves the period 10% long. Only a channel per band holds the 5% limit. To
scale per band, each band needs its own grids.

The layout is the open decision for phase 2. The alternative to measure is one 64² cascade per band: 8 small grids with
tiles of about 16 wavelengths. Their total transform cost is close to two 128² cascades, but the physics and the shader
read 8 cascades instead of 2.
