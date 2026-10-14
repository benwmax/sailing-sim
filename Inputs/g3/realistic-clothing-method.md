# Realistic free clothing by script (Blender to Unreal 5.8, MetaHuman crew)

Written 2026-10-13 for the G3 phase. Bean chose free only (no Fab purchase). Goal: shorts, polo, cap, sunglasses, deck shoes, foam and inflatable PFDs, and a rain jacket that survive Bean's blind test, which caught the old stylised clothing every time.

Sourcing key: **[src]** = read on a linked page this session; **[know]** = standard practice from my own knowledge, not checked against a source today. Nothing here has been run yet. Treat the pipeline as a plan to prove on one garment (the polo) first.

## Why cheap clothes look fake, and the fix for each

| Giveaway | Fix | Scriptable? |
|---|---|---|
| Flat, plastic sheen | Cloth shading: sheen/fuzz at grazing angles, roughness near 0.3 [src: ArtStation UE 5.7 cloth shader post], fuzz colour near 0.1; in Substrate use the Slab's Fuzz input [src: Epic API page lists a Fuzz setup thread] | Yes, material instance parameters from a Python script in the editor |
| No weave or knit | Tiling weave normal map plus a second, larger "macro" normal so the tile never repeats visibly; UV scale ~5x on top [src] | Yes |
| Uniform colour | Per-garment multiplication by a low-frequency noise (dye variation), darker in seams and armpits, sun-fade on shoulders [know] | Yes, baked in Blender |
| Pristine seams | Real garments have stitched seams, hems with double-needle lines, plackets, buttons, collars. Model seams as a thin raised stitch line via a geometry-nodes or normal-map pass [know] | Yes |
| Perfectly smooth shape | Real folds come from simulation, not sculpting: drape cloth on the posed MetaHuman body, bake the result as the resting shape, then bake high-poly folds to a normal map on the game mesh [src: Blender Base Camp cloth settings, shrinkwrap, pinning] | Yes: Blender Python can run cloth sim and bake |
| Clean, new | Procedural wear: salt stains near hem, sweat darkening under arms/collar, edge wear on cap brim and deck shoe toe, dirt in creases using curvature and ambient occlusion masks [src: edge and cavity masking write-ups] | Yes |
| Same cloth on three sailors | One base with seeded random wear, colour, and fit offsets per sailor | Yes |

## Pipeline

**1. Patterns, not hand modelling.** Cut garments from flat sewing patterns and let cloth simulation sew them on the body. Free options:
- **GarmentCode / PyGarment** (MIT licence, Python, v2.0.2 Apr 2025) [src: pypi.org/project/pygarment]: parametric sewing-pattern programs with its own simulator (NVIDIA Warp). Page does not list garment types or output formats, so whether it can produce a polo or shorts out of the box is unconfirmed. Test it first; it is the most "scripted" route. It also needs a GPU; the Mac has no CUDA, but Bean's RTX 4090 PC does. Warp's Mac support is unverified.
- **Blender's own cloth modifier** [src: Blender Base Camp], driven from Python: build front/back/sleeve panels from measured patterns, set seam springs or sew via welding, drape onto the posed body, apply, then shrinkwrap-offset to avoid intersections. Fully scriptable and Mac-native, so this is the default.
- Pattern measurements: use real polo and shorts dimensions (chest, body length, sleeve, inseam). A photo of Bean's own clothes laid flat with a ruler gives the numbers.

**2. Two meshes per garment.** High-poly (sim result plus stitch geometry, micro-displaced weave, around a few hundred thousand tris) and game mesh (retopo or decimated, with LODs). Bake normal, AO and curvature from high to low in Blender via script [know]. Epic requires the resizable Outfit Asset workflow, with sizes built from Epic's four free construction presets, so repeat the drape on each of the four body presets [src: Epic forum on Construction Presets set of 4].

**3. Fabric textures.** Use CC0 scanned fabric from ambientCG: licence is CC0, commercial use and redistribution allowed, no attribution required [src: licenseorg.com summary; it does not specifically say "shipped game", but it lists commercial use as allowed]. Base: ambientCG cotton/pique/twill sets for roughness, normal and AO; add the procedural dye variation and wear on top. Procedural knit or weave shaders exist as free Blender assets, such as the free Pixelshatter knitwear shader [src: blenderartists; v0.1, Cycles, very complex node tree, licence not stated, so prefer ambientCG plus our own nodes].

**4. Wear and personality (script).** A Python pass per sailor with a seed: sweat mask (collar, armpits, lower back), salt tide line near hem, fade on shoulders, dirt in curvature creases, cap brim darkening, deck shoe scuffs [know]. Written as geometry-nodes or shader masks, baked into the texture set.

**5. Unreal side.** Substrate cloth material with fuzz, macro-normal tiling, optional thin translucency on pale cotton (light visibly passes through a white polo in sunlight) [know]. One master material, one instance per garment; a Python editor script sets parameters. Chaos cloth sim on loose items (rain jacket, shorts) is possible but expensive; fake wind flutter with baked vertex animation for the rain jacket in storms [know].

**6. Hard parts to be honest about.**
- Free polo realism will be one notch below a purchased 4K polo (collar roll, knit folds, button placket). That is the gap I noted when pricing the NDart polo.
- Convincing life jackets matter more than the polo: they cover the torso in most of the shots. Straps with buckles, foam panels with stitched quilting, reflective tape, and the zip. A photo of Bean's real PFD would remove most guesswork.
- Resizing across the three crew bodies uses Epic's parametric Outfit Asset path, which depends on Epic's current documentation. The two Epic pages I fetched (wardrobe items and Fab parametric clothing) pointed to a separate "Creating Parametric Clothing" tutorial and did not state the requirements, so the exact import steps for our 5.8.3 project still need reading and a test import.

## Test plan (one garment, measurable)

1. Polo end to end (pattern, drape, bake, material, MetaHuman fit) as a sample.
2. Side-by-side stills against reference photos in the same light; add to the next blind test.
3. If it fails, buy the NDart polo ($20 to $40) for this one item only.

## Photos that would help most

PFD front and back and a closeup of straps and buckles; a polo or shirt laid flat with a tape measure; closeup of fabric weave (phone macro, flat daylight); deck shoes side and sole; shorts laid flat.

## Sources

- [Blender Base Camp: cloth and drapery](https://www.blenderbasecamp.com/cloth-drapery-blender-modelling-tricks/)
- [GarmentCode / PyGarment (PyPI)](https://pypi.org/project/pygarment)
- [Pixelshatter free knitwear shader](https://blenderartists.org/t/procedural-knitwear-shader-free-download/1140349)
- [ambientCG licence summary](https://licenseorg.com/guide/3d-assets/ambientcg)
- [UE 5.7 cloth shader walkthrough](https://jsabbott.artstation.com/blog/EKReA/how-do-you-make-a-cloth-shader-in-unreal-engine-5-7)
- [Epic: Tailoring your own wardrobe items](https://dev.epicgames.com/documentation/metahuman/tailoring-your-own-wardrobe-items)
- [Epic: Creating parametric clothing for Fab](https://dev.epicgames.com/documentation/unreal-engine/creating-parametric-clothing-for-fab)
- [Epic Construction Presets thread](https://forums.unrealengine.com/t/epic-games-metahuman-clothing-construction-presets-set-of-4/2538920)
