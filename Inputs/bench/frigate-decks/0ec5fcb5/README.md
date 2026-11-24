# Frigate decks (#823) at 0ec5fcb5 on the PC, Nov 24 2026

**Head:** `claude/project-thread-xkunbh` at **0ec5fcb5**: 1186594d's lanterns lit within 15 m of the eye and shadowed
on High and Ultra only, plus their volumetric-fog scattering off. Code only, on main 9291fbf6. It ran in my partial
worktree from the stopped 1186594d run, checked out at 0ec5fcb5 (removed afterwards, crew link unlinked only). There
are no separate 1186594d numbers. Nothing was pushed.

- **MSVC build:** Succeeded, 0 errors.
- **Tests:** ShipOutside 4/4, ShipWalk 8/8, Smoke 36/36.
- **Package:** Development `Packaged\Windows-pr823-0ec5fcb5` (kept); cook 0 errors, 1 warning.

## "Ship decks" lines (each deck run's log)

```
Ship decks Gun: 0 copies, 15 lanterns (1 shadowed)
Ship decks Berth: 406 copies, 12 lanterns (6 shadowed)
Ship decks Orlop: 0 copies, 2 lanterns (2 shadowed)
```

The gun-deck run logs only the Gun line. The berth-deck run logs all three as the walker passes down.

## Perf (Ultra, 100%, 20 s)

| Run | fps | p99 | GPU ms | base | Lumen | game | render | 44733c87 | Last night's gun deck (3946b08c) |
|---|---|---|---|---|---|---|---|---|---|
| berth 1080p | 65.0 | 19.92 | 10.43 | 4.64 | 0.90 | 11.62 | 15.34 | 73.7 fps, GPU 10.42, base 4.72 | |
| gun 1080p | **74.4** | 18.73 | 9.96 | **4.08** | 1.09 | 9.45 | 13.40 | 72.6 fps, base 4.78 | 76.4 fps, base 3.14 |
| berth 4K | **GPU hang** | | | | | | | 41.0 fps | |
| gun 4K | **GPU hang** (twice) | | | | | | | 45.4 fps | 54.0 |
| gun 4K, `ShowFlag.PointLights 0` | 51.0 | | 19.06 | 5.58 | | | | | |

- **The gun deck at 1080p improves:** base 4.78 to 4.08 ms, 74.4 fps.
  - That's under the 5.1 ms mark, though still above last night's 3.14 ms at 1080p.
  - Lit in that view: **15 lanterns, 1 shadowed** ("Ship decks Gun: 0 copies, 15 lanterns (1 shadowed)").
- **The berth deck at 1080p is 65.0 fps.** The GPU is the same as 44733c87 (10.43 against 10.42). The game and render
  threads were 2 ms heavier in this run, and the warm-up run was also slow (59 fps), so part of it is the PC.

## The 4K GPU hang (new at 0ec5fcb5)

**Both 4K runs, berth and gun, crashed at frame 34-37**, and a repeat of the gun deck crashed again (`gundeck-4k-repeat`).
The log (`berthdeck-4k-gpu-crash.txt`):

```
LogD3D12RHI: Error: GPU crash detected:
	- Device 0 Removed: DXGI_ERROR_DEVICE_HUNG
Active GPU breadcrumbs:  Frame 34 > SceneRender > Scene > ShadowDepths >
	RenderVirtualShadowMaps(Nanite) > Nanite::DrawGeometry > MainPass/PostPass (InstanceCulling, NodeAndClusterCull, PatchSplit)
	RenderVirtualShadowMaps(Non-Nanite) > Batched > CullingPasses   [active when it hung]
LogWindows: FPlatformMisc::RequestExit(1, D3D12Util.TerminateOnGPUCrash)
```

VRAM was 10.9 of 23.4 GB, so it isn't memory. Two crash folders are in the package's `Saved/Crashes`.

**With `ShowFlag.PointLights 0` the same 4K gun deck runs** (51.0 fps, base 5.58 ms). So the hang is the **lanterns'
shadows in the virtual shadow maps**. 44733c87's lanterns traced their shadows through MegaLights at 4K without trouble.
This head's change to shadow them on High and Ultra puts them in the VSM, and at 4K that hangs in the Nanite and
non-Nanite VSM culling on the first frames. The 1080p runs don't hang.

Bean's Saved was held aside and restored (7B5CA7BE). The GPU recovered after each hang (the process exited), and later
runs were normal.
