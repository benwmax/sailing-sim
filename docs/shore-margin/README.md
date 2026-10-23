# Shore margin (realism audit 10)

`docs/realism-audit-1022`, item 10: the shorelines were clean. There were no reeds, weeds or grass at the waterline and
no wet margin; the trees stood straight out of mown grass to the water. The Tawakoni photos show reeds and green weed at
the edge.

- **Two new shore plants** (`Tools/blender/build_reeds.py`, imported to `/Game/World/Props` by `import_world.py`):
  - `SM_Reeds_2`: rank bank grass and weeds where the mowing stops. 140 arching blades 0.25 to 0.8 m and a few seed
    stalks, about 2,400 triangles.
  - `SM_Reeds_3`: a weed mat floating in the shallows (water primrose, pondweed). 260 small oval leaves across 1.6 m,
    about 2,100 triangles.

  Both use the cattails' `Reed` and `ReedHead` materials, so no new material slots.
- **Placement** (`ALakeTerrainActor::PlaceReeds`), on every world:
  - **Bank grass:** the band from the waterline to 1.2 m up, on banks up to a 0.6 slope, with open water within three
    cells. It is dense at the waterline (8 tufts a node on the lake, 4 on the coasts' 10 m grid) and sparse higher up,
    thinner outside the shore's patches.
  - **Weed:** floats at the surface just off the edge (land within two cells), in patches.
  - **Cattails and rushes:** now up to a 0.3 slope (it had been 0.2), so the coves' clay banks aren't bare.
  - **Draw distance:** grass and weed are drawn to 250 m, and the weed casts no shadow. The new meshes load optionally
    (an older import has neither).
- **Wet margin** (`M_Terrain`, `make_materials.py` `build_terrain`): the wet band reaches 0.6 m up the bank (it was
  0.45) and darkens to 50% (it was 55%). The first 8 cm over the water carry a green-brown film of algae and silt.

Counts: on the lake, 76,000 cattail, 19,500 rush, 332,000 bank grass and 3,400 weed clumps; on Galveston Bay, 161,000,
2,000, 149,000 and 3,700.

Frame cost (uncooked, 1920 x 1080, total GPU per frame):
- The cove view: High 13.18 ms before, 13.33 after; Ultra 16.87 ms before, 17.36 after.
- The marina view: High 14.23 ms before, 14.32 after; Ultra 18.68 ms before, 18.73 after.
- Galveston Bay on High: 13.97 ms.

Before and after: `cove-low-before-after.jpg` (low in a cove of the lake), `cove-edge-detail.jpg` (the edge up close),
`g5-marina-before-after.jpg`. The audit's distant overcast shore view (`g5-shore`) is past the plants' 250 m draw
distance and doesn't change. The pale strip back from the water on the gentle banks is the bank's own clay colour (the
vertex colour), as a drawn-down reservoir shows it.
