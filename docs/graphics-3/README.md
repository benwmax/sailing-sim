# Graphics G3: boats and crew

G3 works on what's closest to the camera most of the time: the boats and the people on them. All the clothing is free:
I built it by script on top of three CC0 scans. Nothing was bought.

![The crew close up, High](bench/crew-high.png)

## Boats

- **Liveries from the catalogue.** `Tools/fleet/make_liveries.py` turns `Inputs/g3/boat-catalogue.json` into
  `BoatLiveryData.inl`. It covers each class's builder schemes, weighted by how common they are (a J/22 is 60% factory
  white, 6% navy, 4% red), plus stripes, bottom paint and wear profiles.
  - `SampleBoatLivery(type, seed)`: seed 0 gives the player's boat, which is the commonest scheme as a club boat.
  - AI boats seed from their id, and marina neighbours from their slip, so every boat in the marina differs.
- **Wear in `M_BoatSurface`.**
  - Oxidation chalks pale gelcoat. Dark paint only greys.
  - A brown waterline stain, strongest forward.
  - Soft fender smudges in the topside band, and thin rust runs below fittings.
  - Grimy non-skid.
  - Per boat on the player's and AI hulls. Per instance (custom data) on the marina's berthed boats.
- **Sail numbers per boat**, composed in `M_SailCloth` from a digit strip in the marks atlas.
- **Published dimensions.** The Hobie 16 and Corsair 880 hulls now sit at their published beams (2.41 m and 6.78 m).
  The Lagoon's bowsprit is counted out of its LOA. `SailingSim.Visual.FleetMesh` now holds every class to its
  published LOA and beam. The Hobie's trimmer heel limit went from 10° to 10.7°, so it still flies a hull in 15 kn.

## Crew

- **MetaHumans at High quality** (bigger textures, more LODs). The rebuild reuses the cloud rig saved with each source
  character.
- **Hair, brows and beards** (MetaHuman grooms on the face, `LoadMetaHumanGrooms`).
  - Strands need the Metal SM6 shader platform and this project is SM5, so the Mac draws cards.
  - On the Mac, brows and moustache are left off, and so is the hair voxelization (about 1 ms with the crew in view).
  - Windows High and Ultra get the full strands.
  - The helm goes bare-headed. Under a cap the scalp groom is left off, so it can't poke through the crown.
- **Polo shirts** (`Tools/blender/build_polo.py`).
  - The optimized MetaHuman body has no torso under its clothes, so each polo is tailored from that sailor's own
    T-shirt: the facings are dropped, a collar on a stand is built from a smooth neck ring, then a two-button placket,
    rib cuffs, and folds at the waist and sleeve heads.
  - Unreal copies the T-shirt's skin weights onto it (Geometry Script `TransferBoneWeightsFromMesh`, then
    `CreateNewSkeletalMeshAssetFromMesh` on the outfit's bones).
  - The pawn hides the T-shirt's sections and adds the polo.
- **Deck shoes** (`build_shoes.py`). Each foot is measured along its own heel-to-toe axis, and a moccasin is lofted over
  it: vamp, white rubber sole, rawhide lace with a bow. The shoe is skinned from the feet.
- **Life jacket and cap** (`build_crew_gear.py`).
  - Life jacket: a quilted shell over foam panels, webbing binding, two straps with side-release buckles, a zip with
    its pull, and reflective patches. 24k triangles.
  - Cap: six panels with seams, a button, eyelets, a brim with thickness and stitching, and the back strap.
- **Cloth** (`M_CrewFabric`). Each sailor's colour sits over a CC0 ambientCG scan: Fabric070 knit for the polo,
  Fabric048 polyester for the life jacket shell, Fabric036 twill for the shorts and cap, Leather038 for the shoes.
  The material adds fuzz for the sheen at grazing angles and fades the relief past a few metres.
  `Tools/fabrics/fetch_fabrics.sh` fetches the scans.

`scripts/make-crew-clothes.sh` runs the whole clothing pipeline: export, Blender, import.

## Found and fixed on the way

- **The coast's frame rate.** G2's riprap boulders put about 950,000 instances along Galveston's jetties. The render
  thread's visibility pass took 25 ms (coast-day High: 33 fps).
  - On coasts the boulders are now bigger, three across every 3 m, hierarchical and culled at 1.5 km: 237,000.
  - The reeds are hierarchical and thinned on 10 m grids.
  - The tide now moves the terrain in 2 cm steps, not every frame. Before, every frame re-sent 83,000 instance
    transforms.
- **House roofs.** `M_HouseRoof` read an input it didn't have (`D2`), so it never compiled. Every roof had drawn the
  default material since V6. The house shaders also take the vertex normal in the ray-tracing hit and compute shaders,
  which have no screen derivatives.

## Performance (packaged, fps)

| View | Medium G1 | Medium G3 | High G1 | High G3 |
|---|---|---|---|---|
| beam8 | 93.7 | 95.0 | 52.3 | 51.6 |
| beat15 | 93.3 | 90.1 | 50.4 | 49.2 |
| storm | 87.0 | 85.3 | 51.8 | 50.1 |
| marina | 89.5 | 87.7 | 47.3 | 46.9 |
| coast-day | 86.4 | 86.8 | 48.8 | 48.6 |
| coast-night | 118.9 | 113.5 | 64.7 | 56.5 |
| gulf-sea | 116.2 | 113.3 | 67.1 | 60.1 |
| helm-eye | 90.4 | 86.7 | 51.3 | 45.3 |
| slip | 76.4 | 76.4 | 48.3 | 47.4 |
| bridge | 96.9 | 94.3 | 52.5 | 51.9 |
| crew | – | 73.1 | – | 46.9 |
| marina-night | 89.7 | 91.9 | 56.5 | 57.5 |

Every view clears the gates: Medium 60, High 45. Helm-eye and crew carry the hair and the High MetaHumans: about 5 fps
on High, against 51 in G1. `crew` is a new view: the three sailors at 2.6 m.

## Compare and blind test

- [Before and after](compare/index.html): G1 against G3 on the reference scenes. The crew score 2 instead of 3 in every
  close scene. On the hulls, only the Catalina in the squall improved (3 to 2), and that came after I fixed the
  scuff cells; the rest are unchanged.
- [Real or Game: Boats](https://claude.ai/artifact/RbPtDkyEaFpNkuB5QKXtQq): five Commons photos (credits in
  `blind/credits.md`) against five frames (`blind/scenes.csv`). The answer key is in `blind/answer-key.csv`.

## Open

- **Shoes** read a little chunky next to real deck shoes.
- **Strand hair** has only been checked on the Mac (cards). It needs a Windows build on the 4090.
- **Private docks** (G2) are still not physics obstacles.
