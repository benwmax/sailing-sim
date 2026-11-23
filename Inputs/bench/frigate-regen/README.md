# Frigate export regeneration on the PC (REGENERATE.md), Nov 23 2026

**Source:** main `906c9034` in the kept worktree `D:\dev\ss-fix-wt\main`.

**Environment:** a dedicated venv `D:\dev\frigate\venv` on Python 3.13.17 (installed beside 3.14 on Bean's OK, with no
PATH or default change), with `bpy==5.3.0 numpy scipy pillow` (bpy 5.3.0, numpy 2.5.5, scipy 1.18.1, Pillow 13.0.0).
Every script ran with `python -I`.

**Outputs, all kept on the PC and never on this branch:**

- the build: `D:\dev\frigate\build` (`frigate.blend` 110 MB plus the build json);
- the light copy: `D:\dev\frigate\lt` (8 shards, `frigate_light.blend`, `light.json`);
- the export: `D:\dev\frigate\out` (252 MB).

| Step | Result | Time |
|---|---|---|
| 1. `build_frigate.py D:\dev\frigate\build` | exit 0; `frigate.blend` 110 MB; anchors, berth_deck, berthdeck, boats, build, deck, gundeck, guns, orlop, rig, running and sails json. Berth deck 485,580 triangles below decks (0.486 of the budget). | 72 min, single-threaded |
| 2. `light.py ... --shard i/8 --report` x 8 | all 8 exit 0 with their reports on the first try. 3 at a time, then up to 6 at a time from 16:01 (the coordinator's speed-up; free RAM never under 29 GB). Shard 1 took 43 min; shards 0 and 2 took longer while #817's builds and 4K runs shared the CPU. | 15:10 to 17:00 |
| 3. `light.py ... --merge ... --report lt\light.json` | **`"ok": true`, `"failing": []`** | 13 s |
| 4. `export.py lt\frigate_light.blend D:\dev\frigate\out --build D:\dev\frigate\build` | exit 0; `Frigate_sockets.json` and `Frigate_materials.json` written | 4 min |

## Against the expected numbers

| | Expected (cloud) | PC |
|---|---|---|
| underway, light triangles | 962,170 | **962,320** (share 0.2001) |
| action | 985,222 | **985,314** (0.2234) |
| clewed | 971,531 | **971,342** (0.2017) |
| anchored | 943,121 | **942,955** (0.1982) |
| every state under 1,000,000 | yes | **yes** |
| worst_error_mm, under 15.04 | yes | **15.03** (paint slide p99 14.47, switch 15.03) |
| failing | [] | **[]** |
| export "files" | 484 | **484** |
| parts_without_twin | 0 | **0** |
| triangles Outside / Decks / Guns | 2,720,025 / 1,095,217 / 3,520,600 | **2,720,025 / 1,095,217 / 3,520,600** (exact) |
| twins | | 1,221 |

The light states are within 0.02% of the cloud's: twins match in outcome, not bytes, as expected. The detailed
triangle counts are identical. On disk: 959 `.fbx` files (the 484 exported meshes plus their `_Light` twins, as the
export writes them) and 252 MB in all.

Files here: `light.json` (the merged report), `light-summary.json` (it without the per-mesh list), `export-log.txt`
(export's own summary), `status.txt` (the run's timeline).

Held on the PC for the Nov 25 import.
