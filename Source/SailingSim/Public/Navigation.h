#pragma once

#include "CoreMinimal.h"

/**
 * Chart work, the way it is taught for ASA 103/105: bearings with a hand-bearing compass, lines of position,
 * fixes, dead reckoning, true and magnetic. Pure functions over the map frame (X north, Y east, meters), so the
 * tests can check them against known positions.
 */
namespace SailingNav
{
	constexpr double MetersPerNauticalMile = 1852.0;

	/** A bearing taken from the boat to a charted object (magnetic, as read off the compass) and when. */
	struct FBearing
	{
		FString ObjectName;
		FVector2D Object = FVector2D::ZeroVector; // the object's charted position
		double MagneticDeg = 0.0;
		double Time = 0.0;                        // session seconds
	};

	/** Compass (magnetic) bearing <-> true, with variation east positive ("east is least": magnetic = true - east). */
	SAILINGSIM_API double MagneticToTrue(double MagneticDeg, double VariationEastDeg);
	SAILINGSIM_API double TrueToMagnetic(double TrueDeg, double VariationEastDeg);
	SAILINGSIM_API double NormalizeDeg(double Deg);

	/** True bearing (degrees, 0 = north, clockwise) and distance (m) from A to B. */
	SAILINGSIM_API double BearingDeg(const FVector2D& From, const FVector2D& To);

	/**
	 * Fix from two or more lines of position: each is the line through the object along the reciprocal of the
	 * bearing. Least-squares intersection; returns false if the lines are nearly parallel. OutSpread is the RMS
	 * distance from the fix to the lines (the size of the "cocked hat").
	 */
	SAILINGSIM_API bool PlotFix(const TArray<FBearing>& Bearings, double VariationEastDeg, FVector2D& OutFix, double& OutSpread);

	/** Dead reckoning: position after sailing a true course at a speed (m/s) for a time (s). */
	SAILINGSIM_API FVector2D DeadReckon(const FVector2D& From, double CourseTrueDeg, double SpeedMs, double Seconds);

	/** "2.3 nm" style distance. */
	SAILINGSIM_API FString FormatDistance(double Meters);
}
