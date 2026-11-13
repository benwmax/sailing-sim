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

/** Club docks pass 3: a launch ramp's concrete slab beside its pier (`*.ramp`), from dry ground down into the water. */
struct FMarinaRamp
{
	FString PierId;
	FVector2D In = FVector2D::ZeroVector, Out = FVector2D::ZeroVector;  // the slab's head corners, pier side first
	FVector2D Dir = FVector2D(1.0, 0.0);                                // down the ramp, toward the water
	float Top = 0.35f;                                                  // the head's height above the water (m)
	static constexpr float Width = 5.f;
	static constexpr float MaxLength = 18.f;
	static constexpr float Foot = -1.4f;
	static constexpr float MinLength = 4.f;
	/** The slab's grade (rise over run): real launch ramps are 12 to 15 % (docs/ramp-cut; Bean, Nov 13 2026). */
	static constexpr float Grade = 0.14f;
	/** The slab's length (m): Top to Foot at Grade, MinLength to MaxLength. The slab is level across its width and cut
	 *  into the bank where that is higher, on fill where it is lower (FLakeTerrain's ground patch, laid by FLakeData). */
	float Length = MaxLength;
	/** The ground patch's extra half width past the slab: the kerbs (m). */
	static constexpr float KerbWidth = 0.2f;
	static constexpr float KerbHeight = 0.15f;
	/** The slab's height (m above the water) at Along metres from the head. */
	float ZAt(double Along) const { return Top + (Foot - Top) * float(FMath::Clamp(Along / Length, 0.0, 1.0)); }
	/** How far down the slab it stays above the water (m): the part a boat can run into. */
	float DryLength() const { return Length * Top / (Top - Foot); }
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
	TArray<FMarinaRamp> Ramps;
	int32 HomeSlip = INDEX_NONE;

	bool IsLoaded() const { return Rows.Num() > 0 || Piers.Num() > 0; }
	/** Reads the layout and lays out the slips (deterministic occupancy). */
	bool Load(const FString& Path);
	/** Visual V7: Catalina 30s alongside the fixed piers, on whichever side has the water for them (and no launch ramp: PlaceRamps first). */
	void PlaceAlongside(TFunctionRef<double(double, double)> DepthAt);
	/** Club docks pass 3: the launch ramps beside the `*.ramp` piers, their heads walked up the beach to dry ground, each a
	 *  graded slab (FMarinaRamp::Grade) from there down to Foot. The caller then lays FLakeTerrain ground patches under
	 *  them (FLakeData::Load), so the bank is cut or filled to the slab. */
	void PlaceRamps(TFunctionRef<double(double, double)> HeightAt);
	/** Every deck, breakwater, berthed boat and the dry part of each ramp as polylines for the obstacles: (points, kind, half-width). */
	void ForEachObstacleLine(TFunctionRef<void(const TArray<FVector2D>&, const FString&, float)> Visit) const;
	/** The marina's footprint plus a margin: OSM docks inside it are replaced by the marina's own (drawn and in physics). */
	FBox2D Bounds(double Margin = 20.0) const;
};
