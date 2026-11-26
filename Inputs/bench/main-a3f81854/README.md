# Main a3f81854 as Bean's play build: package and checks (PC, Nov 26 2026)

**Build:** main a3f81854, with #834, #835, #837, #838, #840 and #841, in the new worktree
`D:\dev\ss-fix-wt\main-a3f81854`.
- MSVC succeeded, 0 project warnings.
- Development package `Packaged\Windows-a3f81854` in 4 min. It's complete, `SailingSim-Windows.ucas` included.

**Checks:** a warm-up run, then a 1 h Marseille soak (`../soak-a3f81854-marseille/`), then these. All are on the lake,
demo, crew off. Bean's Saved was held aside and restored for every run (7B5CA7BE).

| Run | Settings | Exit | fps | p99 | Game / render / GPU ms | Birds in view |
|---|---|---|---|---|---|---|
| warm-up | 1080p Ultra, 12 s | 0 | 63.5 | 22.6 | 11.9 / - / 9.6 | 242 |
| **lake smoke** | **4K Ultra, 60 s** | **0** | **49.1** | **23.5** | 11.4 / - / 19.8 | 415 |
| **beam8** | **4K Ultra, the bench view, 20 s** | **0** | **49.8** | **23.1** | 11.6 / - / 19.5 | 236 |

**Logs and crash folders:**
- Each run logs only the two frame-0 ensures every run on this PC logs: the component PSO precache and the double-float
  origin.
- The package's crash folders are those ensures' UECC reports, two per launch.
- No fatal errors and no asserts.

**Against the 8ae5a0b1 baseline:** beam8 was 50.8 fps there (`../pr834/21b89105/`). The 1 fps difference is #834's birds:
game thread about +1 ms, GPU +0.4 ms.

**Fit as a play build: yes.** It starts, runs clean at 4K Ultra, exits 0, and the soak ran an hour with no crash and flat
memory. The stills are `*.webp`.
