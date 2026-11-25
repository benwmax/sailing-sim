# The tide-step hitch (Galveston)

On a coast the terrain, bridges, landmarks and fixed navaids follow the tide in 2 cm steps (`ASailingGameMode::GetTideFollowZ`,
which all four read). The 2 h 4K Ultra Galveston soak on main 83aa7652 (`Inputs/bench/soak-83aa7652-galveston/`) had a
377-517 ms render-thread frame every 11-26 min, one per step: `PrepareDistanceFieldScene` took 443 ms of it
(`UpdateDistanceFieldObjectBuffers` 317 ms). The lake has no tide and had none.

## Where the time went

At 8 s the game now logs `Distance-field instances:` by owner. On Galveston (Ultra) there were 539,070, and 524,252 of them were
the terrain actor's kept crown tiles and tree proxies (`ALakeTerrainActor::KeepWithActor`). A step moved them all in one
frame. With them out of the distance fields the step still cost 210-240 ms: `SceneCulling_Update_FinalizeAndClear`
(142 ms) re-bins every instance that moved. So the number of instances moved in one frame is the cost, whatever scene they are in.

## The fix

1. **The step is spread over frames** (`ALakeTerrainActor::FollowActor`). The kept components move a budget of instances per
   frame, 20,000 by default (`-SailingTideBatch=<n>`; 0 moves everything at once). Each one remembers where it stands
   (`KeptAtEach`), so a world re-centre during the spread shifts everything and keeps each lag. The crowns take about 27 frames,
   half a second, and for that time some trees sit up to 2 cm off the ground they stand on, which doesn't show. A component
   bigger than the budget still moves whole.
2. **The followers leave the distance fields on High and Ultra** (`MarkTideFollower`, `TideFollowersSkipDistanceFields` in
   `WorldKit`). On a tidal world those tiers' hardware Lumen traces the ray-tracing scene, so there the kept components, the kit
   tiles, the bridge traffic, landmarks and navaids get `bAffectDistanceFieldLighting = false`, conservative instance bounds and
   no navigation (the `docs/recentre-hitch/` settings). Medium (software Lumen) and the lake keep their distance fields.
   `-SailingTideDF=1` keeps every follower in them (the old behaviour); `=2` takes out only the crowns on Ultra.

## Numbers (PC, RTX 4090, 4K Ultra, Galveston, 2 min runs with `-SailingTideStepEvery=20`)

`-SailingTideStepEvery=<s>` forces a 2 cm step every `<s>` s, so the hitch can be measured without a 2 h soak; every step logs
`Tide step: the followers stand at N cm`. Peak render-thread ms in each step's window (`Inputs/bench/tide-df-fix/`):

| Build | Peak render ms per step | DF instances |
| --- | --- | --- |
| Before (`-SailingTideDF=1 -SailingTideBatch=0`) | 403-809 | 539,070 |
| DF off only (`-SailingTideBatch=0`) | 212-432 | 11,198 |
| Batching only (`-SailingTideDF=1`) | 55-58 | 539,070 |
| **Both (this change)** | **52-56** | 11,198 |

The frames between steps take 19-20 ms of render thread. Dusk stills of the Kemah shore and docks on Ultra show no difference
from 83aa7652 (`Inputs/bench/tide-df-fix/compare-dusk-*.jpg`). Medium was not measured: there only the batching applies.

Tests: `SailingSim.Coast.TideStep` (the stepped offset, the forced steps), `SailingSim.Coast.TideStepBatched` (the spread,
and a re-centre in the middle of it), `SailingSim.Coast.KeptStaticFollowsTide`.
