# Storm on High at full resolution (Oct 26 2026)

Since the benches pin High to 100% (#343), the storm view on High measured 42.1 fps, under its 45 floor (GPU 23.4 ms:
base 8.3, clouds and fog 7.4, water 3.7, lumen 1.9).

## Where the time went

In the ProfileGPU dumps (packaged, High, full resolution), the clouds are one pass: `VolumetricCloud / CloudView (PS)
360x270` at 5.9 ms (quarter resolution, rebuilt over frames). That is about 60 ns a traced pixel: the storm's material run
for every view sample, and for every shadow sample toward the sun. Volumetric fog's `GenerateConservativeDepthBuffer`
showed 1.1 ms. Turning it off (`r.VolumetricFog.ConservativeDepth 0`) removed the pass but saved only 0.3 ms of the frame,
so most of its time was a wait the timer counted.

Measured on the storm view (one launch each, pinned, same session):

| Variant | fps | GPU ms | clouds and fog ms |
|---|---|---|---|
| main | 41.5 | 22.89 | 7.39 |
| view samples up to 56 | 43.0 | 22.95 | 7.11 |
| view sample scale 0.75 | 42.2 | 23.17 | 7.62 |
| shadow sample scale 0.5 | 43.9 | 22.52 | 5.95 |
| shadow rays 2 km | 41.7 | 22.59 | 7.53 |
| shadow 0.5 + no conservative depth | 44.8 | 20.84 | 5.88 |
| **shadow 0.5 + view samples up to 56** | **44.9** | **20.35** | **5.62** |

## The change (`ASailingEnvironment::UpdateClouds`)

On High, under a storm deck, the clouds take half the shadow samples and at most 56 view samples (from 80). It eases in
with the deck's darkness: `smoothstep(0.4, 0.75, CloudDarkness)`, 0.85 under the storm.
- A deck that dark gets little sun: the shelf's face is lit by emission, not scattering. So the shadow rays toward the sun
  decide little.
- A dense grey mass seen through rain shows no grain at 56 samples.
- The approach, with the shelf lit in a clear sky, keeps the full counts.

Changes are applied against the live values (in 0.1 steps of the scale: a set rebuilds the cloud proxy). The measuring
arguments `-SailingCloudScale` and `-SailingCloudSamples` leave it alone, and `-SailingFullStormSamples` compares.

## Stills (`-SailingFullStormSamples` left, this change right; same build, uncooked, no HUD)

- `under-deck.jpg`: the storm view, weather time 200. Cloud darkness 0.85, so the change is fully applied. The cloud forms
  are the same; the towers at top left are a touch softer, within the rain's frame-to-frame variance (mean 80.6 against
  78.7 of 255, with the boat and rain moving between the two runs).
- `approach.jpg`: weather time 60, the shelf over the far shore. The same to within the motion blur (mean difference
  1.2 of 255).

## Gate (clouds scope, main 9d10c6e3 + this): pass

Tests 227/227.

| View | Tier | fps | GPU ms |
|---|---|---|---|
| beam8 | High | 56.7 | 16.11 |
| beat15 | High | 54.2 | 16.73 |
| **storm** | **High** | **48.4** | **19.2** |
| gulf-sea | High | 60.4 | 15.26 |
| helm-eye | High | 54.1 | 17.75 |
| bridge | High | 58.1 | 15.98 |
| storm | Medium | 69.1 | 14.64 |

- Storm High's clouds and fog slice went from 7.36 to 5.38 ms.
- Storm Medium ran 41.0 on its first launch; beside main on the rerun it was 69.1 against 68.7 (flapping).
- Every run in this gate reported `foreground` 0.0. The desktop was most likely locked, so no app was in front, and
  launch-to-launch variance was high: the gate's 48.4 fps for storm High is above the same-session A/B's 44.9.
- The like-for-like figure is the A/B above: -2.54 ms of GPU.
