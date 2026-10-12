#pragma once

#include "CoreMinimal.h"
#include "BoatModel.h"
#include "LakeTerrain.h"

/** A named place to put the boat on the water. */
struct FLaunchSpot
{
	FString Name;
	double X = 0.0, Y = 0.0;    // world meters (X north, Y east)
	double HeadingDeg = 0.0;    // compass heading of the bow
};

/** A building near the shore, as a box. */
struct FLakeBuilding
{
	double X, Y, Ground, Length, Width, Height, YawDeg;
};

/** A dock, pier or breakwater from OpenStreetMap: a closed outline or an open line, world meters. */
struct FLakeDock
{
	TArray<FVector2D> Points;
	bool bClosed = false;
	FString Kind;
};

/** A bridge over the water: the deck follows the line at DeckHeight above the pool. */
struct FLakeBridge
{
	FString Name;
	TArray<FVector2D> Points;
	double DeckHeight = 7.0;
};

/**
 * Lake Ray Hubbard as baked by Tools/terrain/build_rayhubbard.py (Content/TerrainData/RayHubbard.*):
 * terrain and tree heights for the physics, plus docks, bridges, buildings, launch spots and shoreline checkpoints.
 */
struct SAILINGSIM_API FLakeData
{
	bool Load(const FString& Directory, const FString& Name);
	bool IsLoaded() const { return Terrain.IsValid(); }

	/** Obstacles for the boat: dock edges and bridge decks (clearance below the deck, a mast cannot pass). */
	void BuildObstacles();

	FString LakeName;
	Sailing::FLakeTerrain Terrain;
	std::vector<Sailing::FObstacleSegment> Obstacles;
	TArray<FLaunchSpot> LaunchSpots;
	TArray<FLakeDock> Docks;
	TArray<FLakeBridge> Bridges;
	TArray<FLakeBuilding> Buildings;
	TArray<TPair<FString, FVector2D>> Checkpoints;
	double PoolFeet = 0.0;
	TArray<uint8> TreeBytes;

	/** Default content location of the baked lake. */
	static FString DefaultDirectory();
};
