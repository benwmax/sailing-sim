#pragma once

#include "CoreMinimal.h"

struct FNavaid;

/**
 * The vector chart baked from the NOAA ENC cells by Tools/coast/build_galveston.py (GalvestonBay.chart.json):
 * depth areas as triangles by depth class, depth contours, the coastline, soundings, dredged channels, bridges and
 * docks, all in the map frame (X north, Y east, meters; depths in meters below MLLW). The HUD draws it in the
 * colors of a NOAA paper chart; navaids and landmarks come from FLakeData.
 */
struct SAILINGSIM_API FChartData
{
	/** Depth classes of the area triangles (same as the bake). */
	enum EDepthClass : uint8 { Drying = 0, Shoal = 1, Shallow = 2, Deep = 3, Land = 4 };

	struct FLine
	{
		TArray<FVector2D> Points;
		FBox2D Bounds = FBox2D(ForceInit);
		double Value = 0.0;   // contour depth (m)
		FString Kind;         // bridges and docks
	};

	bool Load(const FString& Path);
	bool IsLoaded() const { return Triangles.Num() > 0; }

	TArray<FVector2D> Triangles;   // three per triangle
	TArray<uint8> TriangleClass;   // one per triangle
	TArray<FBox2D> TriangleBounds; // one per block of 1024 triangles, to skip blocks out of view
	TArray<FLine> Contours, Coast, Channels, Bridges, Docks;
	TArray<FVector3d> Soundings;   // X, Y, depth (m below MLLW; negative = dries)
	FBox2D Bounds = FBox2D(ForceInit);

	static constexpr int32 TrianglesPerBlock = 1024;
};

/** NOAA chart symbology (U.S. Chart No. 1) for the aids, and the units the chart prints. */
namespace SailingChart
{
	/** How an aid is drawn: the Chart No. 1 symbol it gets. */
	enum class ESymbol : uint8
	{
		Can,         // Q 21: can (cylindrical), drawn as a square-ended buoy
		Nun,         // Q 20: nun (conical), drawn as a pointed buoy
		Pillar,      // Q 23: pillar (lighted lateral buoys)
		Spar,        // Q 24
		Sphere,      // Q 22
		Beacon,      // Q 80-ish: beacon on a pile, with its daymark (square green, triangle red)
		LightMajor,  // P 1: a light on its own structure (light star)
	};

	SAILINGSIM_API ESymbol SymbolFor(const FNavaid& Aid);

	/** The aid's number or letter as the chart prints it in quotes ("2", "11", "A"), or empty. */
	SAILINGSIM_API FString AidNumber(const FNavaid& Aid);

	/**
	 * The chart legend beside the symbol: color and shape letters for unlit buoys ("G C \"1\"", "R N \"2\""),
	 * the light's character for lit aids ("Fl G 4s \"5\"", "Q R 17ft 4M \"8\""), and "R \"6\"" style for daybeacons.
	 */
	SAILINGSIM_API FString AidLabel(const FNavaid& Aid);

	/** Chart colors (NOAA paper chart palette): area fill by depth class, aid color by S-57 colour. */
	SAILINGSIM_API FLinearColor AreaColour(uint8 DepthClass);
	SAILINGSIM_API FLinearColor AidColour(const FNavaid& Aid);

	/** NOAA charts of Galveston Bay give soundings in feet: depth (m below MLLW) to the printed number. */
	SAILINGSIM_API FString SoundingText(double DepthM);
}
