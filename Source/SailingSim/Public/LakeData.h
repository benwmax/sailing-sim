#pragma once

#include "CoreMinimal.h"
#include "BoatModel.h"
#include "LakeTerrain.h"
#include "Lights.h"
#include "Tides.h"

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

/** A buoy, beacon or light from the NOAA chart, with its light's character. S-57 codes are kept as charted. */
struct FNavaid
{
	double X = 0.0, Y = 0.0;
	FString Kind;              // "buoy", "beacon" or "light" (a light on its own structure)
	FString Layer;             // S-57 object class: BOYLAT, BCNLAT, BOYSPP, ...
	FString Name;
	int32 Shape = 0;           // BOYSHP (1 conical/nun, 2 can, 3 spherical, 4 pillar, 5 spar) or BCNSHP
	TArray<int32> Colours;     // S-57 colours: 1 white, 2 black, 3 red, 4 green, 6 yellow
	int32 CatLam = 0;          // lateral category: 1 port (green, can, odd), 2 starboard (red, nun, even)
	bool bLit = false;
	Sailing::FLightCharacter Light;
	int32 DaymarkShape = 0;
	TArray<int32> DaymarkColours;
	FLinearColor DisplayColour() const;
};

/** A charted landmark (tank, tower, stack): something to take a bearing on. */
struct FLandmark
{
	double X = 0.0, Y = 0.0, Height = 0.0;
	FString Name;
	bool bConspicuous = false;
};

/**
 * A sailing area as baked by Tools/terrain/build_rayhubbard.py (Lake Ray Hubbard) or Tools/coast/build_galveston.py
 * (Galveston Bay): terrain and tree heights for the physics, docks, bridges, buildings, launch spots, shoreline
 * checkpoints, and on the coast the chart's navaids and landmarks, the tide and current model and the variation.
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
	/** The most recent gauge reading baked in (feet, same datum as the pool) and its date (YYYY-MM-DD). */
	double LevelFeet = 0.0;
	FString LevelDate;
	TArray<uint8> TreeBytes;
	TArray<uint8> CurrentBytes;

	// Coast.
	TArray<FNavaid> Navaids;
	TArray<FLandmark> Landmarks;
	Sailing::FTideModel Tides;
	bool IsTidal() const { return Tides.IsValid(); }
	double VariationDeg = 0.0;   // magnetic variation, + = east
	double MeanHighWater = 0.0;  // m above the datum
	double Latitude = 32.82, Longitude = -96.50;
	FString FileName;            // "RayHubbard", "GalvestonBay"

	/** The coast's extras: navaids, landmarks, tides and currents, variation. */
	void LoadCoast(const class FJsonObject& Root, const FString& Directory, const FString& Name);

	/** Default content location of the baked lake. */
	static FString DefaultDirectory();
};
