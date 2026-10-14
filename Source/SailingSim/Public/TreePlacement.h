#pragma once

#include "CoreMinimal.h"

namespace Sailing { class FLakeTerrain; }

/** Visual V6: the shore's tree species (Tools/blender/build_trees.py builds two variants of each). */
enum class ETreeSpecies : uint8 { LiveOak, PostOak, CedarElm, RedCedar, Count };

struct FTreeInstance
{
	FVector2D Position = FVector2D::ZeroVector; // map frame, m
	float Ground = 0.f;                         // m above the water
	float Height = 10.f;                        // m
	float Yaw = 0.f;                            // degrees
	ETreeSpecies Species = ETreeSpecies::PostOak;
	uint8 Variant = 0;
	float Crown = 0.f;                          // Graphics G6: crown radius (m) from the lidar; 0 = the model's own proportions
};

/** Graphics G6: a tree crown found on the G2 lidar canopy model (Tools/terrain/build_crowns.py, <World>.crowns). */
struct FLakeCrown
{
	float X = 0.f, Y = 0.f, Ground = 0.f, Height = 10.f, Radius = 3.f;   // map frame (m); Ground below -900: not measured
	bool bCedar = false;    // narrow, dark and under 14 m: eastern red cedar
	bool bFullDetail = false;   // within 400 m of the water
	uint8 Weight = 1;       // crowns it stands for (beyond the full-detail band one in three is kept)
};

/**
 * Where the trees stand: on land within about 1.5 km of the water (what shows from the lake), in 20 m cells whose
 * expected count follows the baked canopy map (density = canopy height / 12 m x Fraction x 1.6 trees per cell), placed
 * at deterministic random points in the cell. Species by a mix weighted to the cross-timbers: post oak and cedar elm
 * most, live oak in the open, eastern red cedar on the slopes. SailingSim.Visual.Canopy holds this to the canopy map.
 */
SAILINGSIM_API void PlaceTreeInstances(const Sailing::FLakeTerrain& Terrain, float Fraction, TArray<FTreeInstance>& Out);

/**
 * Graphics G6: the trees where the lidar found them (the G2 crowns: real positions, heights and crown widths; the round 7
 * "odd tall trees" were canopy-map trees of one shape scaled by height). Species by the crown: red cedar where the source
 * says so, else by height from the local mix (the tall ones post oak and live oak, the short ones cedar elm). Outside the
 * crowns' band (land over about 1 km from the water) the canopy-map placement fills in. Fraction thins both.
 */
SAILINGSIM_API void PlaceCrownTrees(const Sailing::FLakeTerrain& Terrain, TConstArrayView<FLakeCrown> Crowns, float Fraction, TArray<FTreeInstance>& Out);
