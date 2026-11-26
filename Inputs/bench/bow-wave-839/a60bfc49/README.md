# #839 at a60bfc49 (side-band foam rate tripled), PC, Nov 26 2026

**Shas:** a60bfc49, which has the same tree as ebbd4c63. **Package:** Development `Packaged\Windows-pr839-a60bfc49`.

## Build and BowCrest

- **MSVC build:** succeeded, 0 errors, 0 warnings in the project's `Source/`.
- **`SailingSim.Visual.BowCrest`: Success** (`test-bowcrest.json`), as expected:

| Speed | Crest at her bow's side | Foam there | Foam 6 m ahead |
|---|---|---|---|
| 3.0 kn | 0.008 m | 0.00 | 0.00 |
| 5.0 kn | 0.032 m | **0.11** | 0.00 |
| 6.0 kn | 0.041 m | **0.85** | 0.00 |

## The bow-quarter pair, new against `-SailingClassicBowWave`

**Framing:** the same as `../../pr839/fc9a8be/bow-path/`. A film shot file in her frame, 7 m ahead and 3 m to leeward,
1.2 m up, looking back at the stem: `"pos":[7,-3,1.2]`, `"look":[-6,143,0]`, fov 50. The demo at TWA 90, one frame at
14 s, 1080p Ultra.

**Files:** `bow-6kn-bowq-new.webp`, `bow-6kn-bowq-classic.webp`, `bow-7kn-bowq-new.webp`, `bow-7kn-bowq-classic.webp`.

- **6 kn:**
  - Both show streaky spray running up the topsides from the stem.
  - The new one has a slightly brighter thin lip at the waterline just aft of the stem.
  - **The tripled side-band foam doesn't show as a distinct white band from this camera.** The 0.85 foam isn't visible
    along her side in this view.
- **7 kn:**
  - **New:** a denser spray fan with white flecks along the waterline under the bow.
  - **Classic:** a softer mist puff, with fewer flecks.
- **Overall:** the difference is visible but modest at 1080p. To judge the side band, a lower and closer abeam view
  (for example `"pos":[2,-3.5,0.6]` looking in, fov 35) would show the waterline along her side better than this
  bow-quarter angle.
