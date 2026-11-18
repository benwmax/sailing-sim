#pragma once

#include "CoreMinimal.h"

struct FLakeData;

/**
 * Shore plan Track A (docs/envloop/ground): what the terrain builder hands M_Ground besides today's vertex colour.
 * Plain maths, mirrored by Tools/envloop/ground (scene.py's test shore and ground_material.py), held by
 * SailingSim.Visual.GroundDress.
 */
namespace SailingGround
{
	/**
	 * The bank's tone between clay (0) and sand (1) at a point, in 20-40 m stretches along the shore (scene.py's
	 * `smooth` bank noise). BuildChunk used each 5 m grid cell's own random, which the textured bank showed as a
	 * checkerboard of sand and clay squares.
	 */
	SAILINGSIM_API double BankTone(double X, double Y);

	/**
	 * The lawns' and the rough grass's season (MPC_World.Season): 0 summer green, 1 winter dormant (bermuda and the
	 * prairie grasses are straw from December to mid-March here; they brown through November and green through April).
	 */
	SAILINGSIM_API float SeasonAmount(int32 DayOfYear);

	/**
	 * Where the ground is mown (M_Ground's lawn against its rough grass): within reach of a house in the full-detail
	 * band (as PlaceReeds keeps the cattails off those lots) and on the home club's lawn round its clubhouse. Built once
	 * from the lake's houses and marina; read per vertex on the chunk workers (immutable after Build).
	 */
	struct SAILINGSIM_API FMownSource
	{
		/** A house's centre, by 50 m cell of the map frame. */
		TMap<FIntPoint, TArray<FVector2D>> Houses;
		/** The club's lawn: a box round each club building (map metres). */
		TArray<FBox2D> Lawns;

		static constexpr double CellM = 50.0;
		/** Mown this far from a house's centre, with the edge ragged over the next FadeM (a mower's line is never straight). */
		static constexpr double ReachM = 26.0;
		static constexpr double FadeM = 10.0;
		/** The club's lawn runs this far past its buildings' footprints. */
		static constexpr double ClubLawnM = 35.0;

		void Build(const FLakeData& Lake);
		void AddHouse(double X, double Y);
		/** 0 unmown .. 1 mown at a point (map metres). */
		float At(double X, double Y) const;
		bool IsEmpty() const { return Houses.Num() == 0 && Lawns.Num() == 0; }
	};
}
