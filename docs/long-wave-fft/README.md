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

### Cascade layout: one cascade per band

The engine builds two layouts (`ELongWaveLayout`). The game's is **PerBand**, which the coordinator chose after the
brief's layout failed SeaMapSwan on period (below).

**PerBand (the game's).** One 64² cascade per band 0-7 of FWaveField.
- Tile: 16 of the band's shortest waves at the world's depth, so four cells each.
- The band's longest waves are under 1.4 times its shortest, far inside tile / 2.
- Each cascade is turned by the golden angle from the one before, so no two lattices line up.
- The sea map scales each band, as it scales each sine today.
- An open sea's range under band 0 gets the swell cascade L3 (1,409 m).

| Band | Tile (deep) | Turned | Modes | Wavelengths |
|---|---|---|---|---|
| B0 | 557.6 m | 137.5° | 372 | 35.3 to 47.8 m |
| B1 | 403.3 m | 275.0° | 372 | 25.5 to 34.6 m |
| B2 | 291.8 m | 52.5° | 372 | 18.5 to 25.0 m |
| B3 | 211.1 m | 190.0° | 372 | 13.4 to 18.1 m |
| B4 | 152.7 m | 327.5° | 372 | 9.7 to 13.1 m |
| B5 | 110.5 m | 105.0° | 372 | 7.0 to 9.5 m |
| B6 | 79.9 m | 242.6° | 372 | 5.1 to 6.9 m |
| B7 | 57.8 m | 20.1° | 372 | 3.7 to 5.0 m |

**Ranges (the brief's, kept for comparison).** Three 128² cascades by wavelength:

| Cascade | Tile | Turned | Carries | Modes |
|---|---|---|---|---|
| L1 | 97.3 m | 0° | 3.6 to 12 m | 2,072 |
| L2 | 331 m | 27.4° | 12 to 48 m | 2,240 |
| L3 | 1,409 m | 61.9° | 44 m and up | open sea only |

Tile repeats in `NoWeave` at 20 kn: each band's lattice correlates at most 0.13 with itself (B5), against 0.17-0.23 at
L1's 97 m. The 24 sines correlate 0.67 at 81 m.

### Measured on the M5 Pro (clang -O2, standalone)

| What | Per band | Ranges | Budget or today |
|---|---|---|---|
| Kernel, 128² complex 2D inverse | | 0.09 ms | brief's estimate 0.10-0.15 |
| A key's grids at 20 kn, 1 thread | 1.23 ms (8 cascades, 2,976 modes) | 1.39 ms (2 cascades, 4,312 modes) | ≤ 2.0 ms |
| The same on 4 threads (deterministic join) | 0.42 ms | 0.50 ms | |
| One physics read (13 fields, 2 keys) | 0.40 µs | 0.10 µs | today's 48-sine `Sample`: 0.38 µs |

The GPU side waits for phase 2. Per band, the vertex shader reads 8 cascades × 2 textures (16 fetches) in place of today's
24 sincos and 7 atlas fetches. Phase 2's switch gives the measurement, through the gate on both settings.

### Checks (per band; the tool runs both layouts)

| Check | Result |
|---|---|
| Spectrum | variance equal to the sines' bands 0-7 (0.00%) at 10-28 kn, deep and 5 m; Tm01 within 0.6%; direction within 0.05° |
| MatchesDirectSum | every field within 2.4e-7 of the straight sum (also with an open sea's range and L3) |
| TimeBlend | 0.20% of band 7's RMS half way between keys |
| Spreading | the sech² within 0.013 of the energy per 20° bin (10° bins alias on the coarser lattices) |
| Growth | every band reaches 1 - 1/e in exactly its `GrowthSeconds` |
| WindShift | 30° and 90°: no height step (4.9 mm per 1/120 s at most, inside the waves' own motion); the old direction under 0.01% after 3 τ |
| FrameRateFree | 30, 60, 144 fps give the same grids to the bit |
| Determinism | 1, 2 and 8 workers, and a restart at 300 s, to the bit |
| LongClock | t = 1e6 s: 7.4e-8 m from the straight sum |
| Golden | 64 heights (`LongWaveGolden.inl`, made on the Mac). The PC holds them to 1e-5 m in its next build |
| NoWeave | 0.18 away from zero lag (limit 0.25); the sines reach 0.67 |
| SeaMapSwan | Tp bias +2.6% (limit 5%), Hs 0.069 |

### SeaMapSwan: why per band

Run with `scripts/long-wave-check.sh --swan`: 1,050 cases at SWAN's ten points (`Artifacts/long-wave-sea-map.csv`).

| Sea map channels for the long waves | Median abs(log Hs error) | Median abs(log Tp error) | Tp bias |
|---|---|---|---|
| One per sine (today) | 0.070 | 0.108 | +2.3% |
| One per cascade, ranges (2) | 0.069 | 0.203 | **+22%** |
| 3 groups of bands (0-2, 3-5, 6-7) | 0.071 | 0.159 | +10% |
| 4 groups (0-1, 2-3, 4-5, 6-7) | 0.071 | 0.126 | +6.4% |
| One per cascade, per band (8) | 0.069 | 0.106 | +2.6% |

Height is right with any channel count. The period is not. On a short fetch the long bands fall away faster than the
short ones, so the local peak moves to shorter waves. One scale per cascade can't move the peak when a cascade spans
several bands. The brief's fallback, three lake cascades, still leaves the period 10% long.

### Gate

`scripts/gate.sh --scope water` on 2026-10-28 (main 6bbe9b09 merged in) passed: 275 tests.

The game doesn't call the engine yet, so the bench should match main's last water gate, and it does:

| View | Tier | fps | Last water gate on main |
|---|---|---|---|
| beam8 | High | 57.2 | 55.7 |
| beat15 | High | 53.9 | 53.0 |
| storm | High | 47.2 | 47.2 |
| marina | High | 54.8 | 55.2 |
| coast-day | High | 52.7 | 52.3 |
| gulf-sea | High | 59.7 | 60.7 |
| helm-eye | High | 56.6 | 58.2 |
| bridge | High | 55.7 | 57.1 |
| storm | Medium | 66.8 | 66.3 |
