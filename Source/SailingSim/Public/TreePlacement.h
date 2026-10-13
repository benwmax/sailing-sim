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
};

/**
 * Where the trees stand: on land within about 1.5 km of the water (what shows from the lake), in 20 m cells whose
 * expected count follows the baked canopy map (density = canopy height / 12 m x Fraction x 1.6 trees per cell), placed
 * at deterministic random points in the cell. Species by a mix weighted to the cross-timbers: post oak and cedar elm
 * most, live oak in the open, eastern red cedar on the slopes. SailingSim.Visual.Canopy holds this to the canopy map.
 */
SAILINGSIM_API void PlaceTreeInstances(const Sailing::FLakeTerrain& Terrain, float Fraction, TArray<FTreeInstance>& Out);
