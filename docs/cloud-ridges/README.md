# Mid-distance cumulus: layers and blocky lobes (Oct 25 2026)

The Ultra re-audit (`docs/ultra-audit-1025`) found the chase's cumulus 3 to 10 km out streaked and bladed: flat stacked
layers and blocky, vertically stretched lobes. On c9b7e9f1 they were soft puffs. A bisect of the chase on the Mac
(AfternoonBreeze 14:00, 14 kn, sun held) found two causes.

## 1. The flat layers: #313 (cumulus-shape), High and Ultra

#313 set a cell's height to cuSize^1.4 for every cell. That was meant for the humilis scraps, which had been round balls.
It also flattened every mid-size cell into a lens, and from a few kilometres the lenses stacked into layers.

Two changes in CLOUD_CODE:

- **Height by size.** The exponent goes from 1.4 for the scraps (cuSize under 0.25, under about 300 m across) to 1.0
  from 0.5 up. A cumulus mediocris stands about as tall as it is wide, as before #313. The scraps stay shallow lenses.
- **A flat base without a slab.** #313 filled each cell's lowest 120 to 360 m with its core footprint: a vertical-sided
  block, wider than the body above it. Now the shape noise is looked up 60 m above the condensation level for anything
  below that (`CU_BASE_SLICE`). The flat underside is the cell's own cross-section, carried down to the base, and the sides
  bulge out of the noise straight above it. On its own this barely changes the stills; the height rule was most of it.

`chase-high.jpg` and `chase-ultra.jpg` each show pre-#313, main, then this change. `under.jpg` is the clouds from under
them, main on the left and this change on the right: the bases still read flat and dark.

## 2. The blocky, vertically stretched lobes: #316 (ultra-cloud-tops), Ultra only

`ultra-bisect.jpg` shows the Ultra chase at #313, #316 and #317 (top row), then #321, #325 and main (bottom row). The blocky
lobes appear at #316 and stay; #317, #321 and #325 add nothing.

#316 sets three Ultra settings together: noise footprint floor 60 m, top edge ramp 5, second billow octave 1.5. Turning
them off one at a time leaves the other two on, which fits the PC's finding that it persisted. That is for the PC (Ultra)
to settle, with all three off together, then each alone. Not changed here.

## With the sky cache off

The PC traced Ultra's pillars to the sky cache's far march, which snaps to its 200 m coarse grid (`-SailingNoSkyCache`
removes them; the PC is fixing the march). High uses the same cache past 5 km. `nocache-high.jpg` and
`nocache-ultra.jpg` are the chase with `-SailingNoSkyCache`, main on top and this change below. On main the cells are
cuSize^1.4 tall, and that thin layer cuts the round billow lobes (`T_CloudBillow`, round in metres) into flat lenses: the
blade-like lobes. With the size-dependent height, mid-size cells are tall enough for the lobes to stay round. The
remaining flat undersides are the cells' condensation-level bases.
