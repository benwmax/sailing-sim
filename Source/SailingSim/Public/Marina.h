#pragma once

#include "CoreMinimal.h"

/**
 * Visual V6: a marina's layout (Rush Creek Yacht Club: Content/TerrainData/<Lake>.marina.json): the shore walkway, the
 * dock rows with their slips and finger piers, fixed piers, the rock breakwater and the club's buildings, in the map
 * frame (m). Build() lays out the slips and fingers; the docks become physics obstacles (FLakeData) and AMarinaActor
 * draws everything. Every structure has an id that a scan can replace (Content/World/Scans.json).
 */
struct FMarinaLine
{
	FString Id;
	TArray<FVector2D> Points;
	float Width = 1.8f;
	float Height = 0.5f;     // deck above the water (breakwaters: crest)
};

struct FMarinaRow : FMarinaLine
{
	float SlipWidth = 3.6f;
	float FingerLength = 7.3f;
	float StartOffset = 6.0f;
};

struct FMarinaSlip
{
	FString Id;
	FVector2D Center = FVector2D::ZeroVector;  // middle of the berth
	float HeadingDeg = 0.f;                    // bow pointing into the slip (toward the row)
	FVector2D FingerA = FVector2D::ZeroVector, FingerB = FVector2D::ZeroVector; // the finger pier beside it
	int32 Row = 0, Side = 1, Index = 0;
	bool bOccupied = false;
	bool bHome = false;
	uint8 BoatType = 0;                        // Sailing::EBoatType of the boat in it (J/22 or Catalina 22) when occupied
};

/** A bigger boat lying alongside a fixed pier (a Catalina 30 is too beamy for the 3.6 m slips). */
struct FMarinaAlongside
{
	FVector2D Center = FVector2D::ZeroVector;
	float HeadingDeg = 0.f;
	uint8 BoatType = 0;
};

struct FMarinaBuilding
{
	FString Id;
	FString Kind;          // "clubhouse", "pool"
	FVector2D Center = FVector2D::ZeroVector;
	FVector2D Size = FVector2D(10.0, 10.0);
	float HeadingDeg = 0.f;
	float Height = 4.f, Roof = 2.f;
};

struct SAILINGSIM_API FMarina
{
	FString Name;
	TArray<FMarinaLine> Walkways, Piers, Breakwaters;
	TArray<FMarinaRow> Rows;
	TArray<FMarinaBuilding> Buildings;
	TArray<FMarinaSlip> Slips;
	TArray<FMarinaAlongside> Alongside;
	int32 HomeSlip = INDEX_NONE;

	bool IsLoaded() const { return Rows.Num() > 0 || Piers.Num() > 0; }
	/** Reads the layout and lays out the slips (deterministic occupancy). */
	bool Load(const FString& Path);
	/** Visual V7: Catalina 30s alongside the fixed piers, on whichever side has the water for them. */
	void PlaceAlongside(TFunctionRef<double(double, double)> DepthAt);
	/** Every deck, breakwater and berthed boat as polylines for the obstacles: (points, kind, half-width). */
	void ForEachObstacleLine(TFunctionRef<void(const TArray<FVector2D>&, const FString&, float)> Visit) const;
	/** The marina's footprint plus a margin: OSM docks inside it are replaced by the marina's own (drawn and in physics). */
	FBox2D Bounds(double Margin = 20.0) const;
};
