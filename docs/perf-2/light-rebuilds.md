# Perf 2, step 2: the sun is no longer rebuilt under cloud

After step 1 (the sun turning in steps, PR #71), the engine's VSM counters (`-csvCategories=VSM`) still showed the
helm's-eye view and the storm caching nothing: every page allocated new each frame. The sun's `SetDiffuseScale`,
`SetSpecularScale` and `CloudScatteredLuminanceScale` call `MarkRenderStateDirty`, which rebuilds the light, and a
rebuilt light starts its shadow cache afresh. `ASailingEnvironment` set them from the cloud shade every frame, so
whenever the shade was under 0.35 (a storm deck, a cumulus over the boat) the light was rebuilt every frame.
They now move in steps: the diffuse scale by 0.04 (the specular follows it), the clouds' light scale by 3%.

Also: `ANavaidsActor` moved its fixed marks with the tide every frame (now in the terrain's 2 cm steps), and bobbed
its buoys by rebuilding each instanced component every frame (`MarkRenderStateDirty`); each buoy is now an instance
delta (`UpdateInstanceTransform` queues it), and the lights update only when they change.

## Numbers

The Mac ran about 2 fps slower in this session than during step 1's gate, Medium included, so step 2 is measured
against step 1's build in the same session (packaged, 12 s, High, two runs where shown):

| View | step 1 | step 2 |
|---|---|---|
| helm-eye | 50.5 | 53.4, 53.2 |
| storm | 45.7, 45.7 | 45.6, 45.9 |
| coast-day | 48.4, 48.0 | 48.3, 48.1 |
| slip | 51.4 | 51.5 |

The storm now keeps its static pages (713 cached a frame, none before) but gains nothing: nearly every page it uses
is redrawn for the moving boat anyway. Gate (`--scope clouds`, main + PR #71 + this): pass, 130 tests green;
`visual-bench-p2-lightdirty.csv`.
