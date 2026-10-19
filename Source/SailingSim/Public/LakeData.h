#pragma once

#include "CoreMinimal.h"
#include <limits>
#include "Marina.h"
#include "BoatModel.h"
#include "LakeTerrain.h"
#include "Lights.h"
#include "GeoAnchor.h"
#include "Tides.h"
#include "TreePlacement.h"

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

/** Graphics G6: a house from the G2 footprints (Tools/terrain/build_houses.py, <Name>.houses): its lidar eave and roof,
 *  NAIP roof colour and one rectangle per wing. Heights in metres above Ground; rectangles in the map frame. */
struct FLakeHouse
{
	enum ERoof : uint8 { Flat, Gable, Hip, Shed };
	struct FWing { double X, Y, HalfLength, HalfWidth, YawDeg; };
	double X = 0.0, Y = 0.0, Ground = 0.0;  // Ground below -900: not measured (take the terrain's)
	float Eave = 3.f, Ridge = 0.f, PitchDeg = 24.f;
	ERoof Roof = Hip;
	bool bFullDetail = false, bLidar = false, bCommercial = false;
	int32 Storeys = 1;
	FColor RoofColor = FColor(96, 96, 96);
	TArray<FWing, TInlineAllocator<4>> Wings;
};

/** A dock, pier or breakwater from OpenStreetMap: a closed outline or an open line, world meters. */
struct FLakeDock
{
	TArray<FVector2D> Points;
	bool bClosed = false;
	FString Kind;              // "pier", "breakwater"; Graphics G7 adds "dike", "seawall" and "floating" (inferred walkways)
	float Width = 0.f;         // Graphics G7: metres across at the waterline (0: the kit's default for the kind)
	float Crest = 0.f;         // Graphics G7: crest or deck height above the datum (0: the kit's default)
};

/** Graphics G7: an over-water structure on piles from the G2 lidar (Inputs/g2/piers): its deck outline and height. */
struct FLakeDeck
{
	TArray<FVector2D> Outline;  // closed, map frame
	float Deck = 1.5f;          // m above the datum (MLLW on the coast)
	bool bCovered = false;      // a covered slip or a building on piles
	FString Kind;               // pier, dock_complex, platform_or_wharf, covered_slip_or_building, deck
};

/** Graphics G7: a boat moored in the 2018 lidar, where the map has water under her. */
struct FMooredBoat
{
	FVector2D Center = FVector2D::ZeroVector;
	float HeadingDeg = 0.f;     // the bow
	float Length = 7.f, Beam = 2.5f;
	bool bMast = false;
	int32 Marina = INDEX_NONE;
};

/** A bridge over the water: the deck follows the line at DeckHeight above the pool. */
struct FLakeBridge
{
	FString Name;
	FString Kind;              // OSM highway/railway kind: motorway, primary, rail, path, ...
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

/** Wide World Rendering PR 3: what the world shows at night beyond its near lights (<Name>.farlights.json,
 *  Tools/terrain/build_far_lights.py). */
struct SAILINGSIM_API FFarLightsData
{
	struct FLight
	{
		FVector2D XY = FVector2D::ZeroVector;  // map frame, m
		double Z = 6.0;                         // the lantern, m above the datum
		Sailing::FLightCharacter Light;
		FString Name;
		int32 Navaid = INDEX_NONE;              // this world's navaid (ANavaidsActor draws it within the near pool)
	};
	struct FShore { FVector2D XY; double Z = 6.0; int32 Houses = 0; };
	struct FCity { FString Name; FVector2D XY; double Light = 0.0; };
	struct FLane { FString Name; double Knots = 12.0; int32 Ships = 3; TArray<FVector2D> Points; };
	TArray<FLight> Lights;
	TArray<FShore> Shore;
	TArray<FCity> Cities;
	TArray<FLane> Lanes;
	bool Load(const FString& Path);
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
	/** Graphics G6: reads <Name>.houses (Tools/terrain/build_houses.py) into Houses. */
	void LoadHouses(const FString& Path);
	/** Graphics G6: reads <Name>.crowns (Tools/terrain/build_crowns.py) into Crowns. */
	void LoadCrowns(const FString& Path);
	/** Graphics G7: reads <Name>.piers (Tools/coast/build_piers.py): decks, riprap, inferred walkways, moored boats. OSM piers
	 *  that a lidar deck covers are dropped (the deck has the measured height). */
	void LoadPiers(const FString& Path);

	FString LakeName;
	Sailing::FLakeTerrain Terrain;
	std::vector<Sailing::FObstacleSegment> Obstacles;
	TArray<FLaunchSpot> LaunchSpots;
	TArray<FLakeDock> Docks;
	/** Graphics G7: the lidar decks and the moored boats (<Name>.piers). */
	TArray<FLakeDeck> Decks;
	TArray<FMooredBoat> MooredBoats;
	/** Visual V6: the club's marina (rows, slips, piers, breakwater, buildings), when <Name>.marina.json exists. */
	FMarina Marina;
	TArray<FLakeBridge> Bridges;
	TArray<FLakeBuilding> Buildings;
	/** Graphics G6: the G2 houses, when <Name>.houses exists (the shore's buildings drawn from them instead of Buildings). */
	TArray<FLakeHouse> Houses;
	/** Graphics G6: the G2 lidar tree crowns, when <Name>.crowns exists (PlaceCrownTrees). */
	TArray<FLakeCrown> Crowns;
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
	/** world-marseille: a sea coast with a chart, navaids and the coast's look, tidal or not (Marseille has no tide
	 *  model: under 0.3 m). Chart, navigation HUD, coastal wear and sounds follow this; tides and currents IsTidal(). */
	bool IsCoast() const { return bCoast || IsTidal(); }
	bool bCoast = false;
	/** IALA buoyage region: 'A' (Europe: port red) or 'B' (the Americas: port green). */
	TCHAR Iala = TEXT('B');
	/** The local clock's rule: empty for the machine's own zone (Texas), "Europe/Paris" for central European time. */
	FString TimeZone;
	/** marseille-look: the land's dress (the bake's "land"): empty or "prairie" for Texas (grass, red clay at the water,
	 *  oak woods), "garrigue" for the Mediterranean (scrub over bare limestone, pines, white limestone cliffs). */
	FString Land;
	bool IsGarrigue() const { return Land == TEXT("garrigue"); }
	/** The open sea's usual swell and the strong wind's direction (degrees from), NaN when the world gives none. */
	double SwellFromDeg = std::numeric_limits<double>::quiet_NaN();
	double MistralFromDeg = std::numeric_limits<double>::quiet_NaN();
	/** Named launch spots by role ("home_slip", "anchorage", "gale"): indices into LaunchSpots. */
	TMap<FString, int32> SpotRoles;
	/** Wide World Rendering PR 3: far lights, lit shores, city domes and shipping lanes (<Name>.farlights.json). */
	FFarLightsData FarLights;
	/** The sources line for the chart's credit (the bake's "sources.chart"). */
	FString ChartSource;
	double VariationDeg = 0.0;   // magnetic variation, + = east
	double MeanHighWater = 0.0;  // m above the datum
	double Latitude = 32.82, Longitude = -96.50;
	/** Where the map frame sits on the earth (the bake's "projection", else the build script's centre): lat/lon <->
	 *  map metres for anything that persists (docs/geo-anchor). */
	Sailing::FGeoAnchor Anchor;
	FString FileName;            // "RayHubbard", "GalvestonBay", "GulfPassage"
	bool bOcean = false;         // open sea: the FFT ocean with swell (the Gulf passage)
	TArray<TPair<FString, FVector2D>> Passage; // the passage plan's waypoints, in order

	/** The coast's extras: navaids, landmarks, tides and currents, variation. */
	void LoadCoast(const class FJsonObject& Root, const FString& Directory, const FString& Name);

	/** Default content location of the baked lake. */
	static FString DefaultDirectory();
};
