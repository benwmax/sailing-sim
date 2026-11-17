# Cannon fire: tuning

Every knob of the guns and their effects is one number in `Sailing::FCannonParams`. They can be changed three ways, and
the game picks changes up while it runs:

1. **On the command line:** `-SailingCannonFx="SmokeAlbedo=0.8,FlameNits=80000"` (quote it: the commas).
2. **In a file:** `Saved/CannonFx.txt` (the packaged Mac app's is under `~/Library/Containers/com.benwmax.SailingSim/Data/Library/`),
   one `Key = value` per line, `#` starts a comment. The game re-reads it within a second of a save (not in Shipping).
   Start from the full list: `sailing.CannonFx` with no arguments writes it to `Saved/CannonFx.dump.txt`.
3. **In the console:** `sailing.CannonFx SmokeAlbedo 0.8`.

When a value looks right, put it in the default in `Source/SailingPhysics/Public/Cannons.h` (one line each) and say why in
its comment.

## Seeing it

| What | How |
|---|---|
| A battery without the frigate | `-SailingCannonStage` (60 m to starboard of the player's boat, keeping station with her as she sails) or `-SailingCannonStage=<fwd m>,<right m>,<heading deg relative to hers>`; any boat works (the stage draws the guns alone, no hull) |
| Fire on a timer | `-SailingBroadside=<s after start>[,port\|starboard\|both[,broadside\|ripple\|atwill]]`, again every `-SailingBroadsideEvery=<s>` (the guns start run out and loaded) |
| Fire now | console `sailing.Broadside [side] [mode]` |
| Orders as the panel gives them | console `sailing.CannonOrder <CastLoose\|Load\|RunOut\|Fire\|CeaseFire\|Secure> [side]` |
| Compare | `-SailingNoCannonSmoke`, `-SailingNoCannonLights` |
| Debug lines | `-SailingDebugCannons` |
| Without Unreal | `scripts/cannon-check.sh --smoke 60 --wind 6 --fx "Diffusivity=0.15"` prints the cloud's size, height and opacity over time |

A still for tuning, with the uncooked game:

    scripts/run-game.sh 14 -SailingCannonStage=10,70,0 -SailingBroadside=6,port -SailingCamYaw=90 -SailingCamPitch=-5 \
        -SailingNoHud -SailingQuality=High -SailingShot=cannon-broadside

The stage sails alongside 70 m to starboard and its port guns fire toward the camera (looking to starboard), so the still
(taken at the end, 8 s after the broadside) shows the cloud drifting between. The flame lasts 75 ms, so a still rarely
catches it: `-SailingBroadside=10,port,ripple` keeps guns going off through the last seconds.

## The bench

`bench.json` has `cannon_cpu_ms` (the game thread's time in every battery, per frame) and `cannon_puffs` (puffs alive at
the end). Bench a broadside with the views' usual args plus `-SailingCannonStage -SailingBroadside=1 -SailingBroadsideEvery=15`,
so every measured second has smoke in it. The smoke's draw cost is the translucent quads' overdraw: the budget per quality
(below) is the lever, then `SigmaStartM` and `PuffsLong` (fewer, bigger puffs).

| Quality | Smoke puffs (budget) | Flash lights |
|---|---|---|
| Low | 256 | 1 |
| Medium | 768 | 2 |
| High | 1,536 | 4 |
| Ultra | 3,072 | 6 |

Over budget, the oldest puff merges into its nearest neighbour (mass kept), so a long engagement's cloud gets coarser, not
thinner.

## The materials

`M_CannonSmoke` and `M_CannonFlash` are built by `scripts/import_cannon_fx.py` (run by `scripts/make-cannon-fx.sh` or
`scripts\windows\make-cannon-fx.ps1`); their textures come from `Tools/shipkit/frigate/make_cannon_textures.py`
(`--preview` writes `preview_smoke.png` and `preview_flame.png` beside them for a look without the editor). The look knobs
below are pushed into the materials by the battery. Luminances are real cd/m^2; the battery scales them into the scene's
units (2^-14.1, the exposure's offset) as it does the flash lights' candela.

## Every knob

| Knob | Default | What it does |
|---|---|---|
| **Drill** | | |
| `CrewTimeScale` | 1 | every crew time times this (0.5: twice as quick) |
| `CrewSpread` | 0.15 | each crew's own pace, +- this share |
| `CastLooseS` | 35 | s: lashings off, the gun eased in to load |
| `LidS` | 3 | s: a port lid hauled up or let down |
| `SpongeS` | 14 | s: wormed and sponged after a shot |
| `LoadS` | 24 | s: cartridge, wad, shot, wad, rammed, pricked, primed |
| `RunOutLongS` | 12 | s: a long 24 hauled out on its side tackles, level |
| `RunOutCarronadeS` | 5 | s: a carronade's bed run out on its slide |
| `RunOutUphill` | 2.5 | run out uphill takes 1 + this x sin(slope) longer |
| `SecureS` | 45 | s: hauled against the sill and lashed for sea |
| `PointS` | 3 | s: pointing before a shot at will |
| **Firing** | | |
| `LockDelayS` | 0.11 | s: lanyard to the charge (flint, pan, vent) |
| `LockSpreadS` | 0.04 | s: the lock's own scatter |
| `BroadsideSpreadS` | 0.3 | s: a broadside's lanyards within this |
| `RippleIntervalS` | 0.45 | s: ripple, gun after gun from forward |
| `MisfireChance` | 0.02 | a flash in the pan (0..1) |
| `ReprimeS` | 6 | s: primed again after a misfire |
| **Recoil** | | |
| `GasFactor` | 1.5 | powder gas momentum = charge x this x muzzle velocity |
| `RecoilScale` | 1 | every recoil impulse times this |
| `RollMu` | 0.08 | a truck carriage rolling on the deck |
| `SlideMu` | 0.3 | a carronade's bed sliding on its slide |
| `BreechingStretchM` | 0.12 | m: the breeching's give under a full recoil |
| `BreechingDamping` | 0.5 | the breeching's damping ratio |
| **Smoke** | | |
| `SmokePerChargeKg` | 0.55 | kg of smoke per kg of powder (black powder 0.55) |
| `SmokeExtinction` | 500 | m^2/kg: how much a kg of smoke hides |
| `SmokeOpacityCap` | 0.85 | the most one puff hides |
| `PuffsLong` | 18 | puffs from a long gun's muzzle |
| `PuffsCarronade` | 12 | puffs from a carronade's muzzle |
| `PuffsVent` | 2 | puffs from the vent and pan |
| `JetSpeedMs` | 75 | m/s: the blast's leading puff (long 24's charge) |
| `JetSpreadDeg` | 10 | deg: the jet's cone |
| `JetDecayS` | 0.22 | s: the jet slows to the wind in about this |
| `RingShare` | 0.3 | share of the puffs thrown round the muzzle |
| `SigmaStartM` | 0.5 | m: a puff's sigma at the muzzle |
| `Diffusivity` | 0.1 | m^2/s: eddy diffusivity at sigma 1 m |
| `DiffusivityPower` | 1.333 | K grows as sigma^this |
| `BuoyancyMs2` | 1.2 | m/s^2: the hot smoke's lift at first |
| `BuoyancyDecayS` | 2 | s: the lift falls off (cooling) |
| `WindTakeS` | 1.5 | s: a slow puff takes the wind's speed |
| `SmokeMaxAgeS` | 180 | s: the oldest smoke kept |
| `MinPuffOpacity` | 0.006 | a puff fainter than this is dropped |
| `WaterLift` | 0.4 | a puff's centre stays this many sigmas over the water |
| **Flash** | | |
| `FlashS` | 0.075 | s: the muzzle flame's life |
| `FlashLengthPerCbrtKg` | 2.3 | m of flame per cube root of the charge (kg) |
| `FlashGlowM` | 9 | m: smoke within this is lit by the flash |
| `FlashLightCd` | 300000 | cd: the flash's light at its peak |
| `FlashLightRadiusM` | 70 | m: the light's reach |
| `PanFlashS` | 0.05 | s: the pan's flash |
| `Sparks` | 20 | burning grains per shot |
| `SparkSpeedMs` | 55 | m/s: the sparks' speed |
| `SparkLifeS` | 0.35 | s: the sparks' life |
| **Look (materials)** | | |
| `FlameNits` | 60000 | cd/m^2: the flame's core at its peak |
| `SparkNits` | 20000 | cd/m^2: a burning grain |
| `SmokeGlowNits` | 4000 | cd/m^2: smoke at the flash, lit from inside |
| `SmokeAlbedo` | 0.85 | the smoke's colour (0..1 grey) |
| `SmokeForwardScatter` | 0.6 | Henyey-Greenstein g of the smoke toward the sun |
| `SmokeEdgeSoftness` | 0.5 | 0 billowed edges .. 1 a soft Gaussian |
| `SmokeDepthFadeM` | 1.5 | m: the smoke fades into surfaces over this |
