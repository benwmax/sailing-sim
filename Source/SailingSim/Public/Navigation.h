#pragma once

#include "CoreMinimal.h"
#include "GeoAnchor.h"

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

	/**
	 * The physics/Unreal boundary for places on the earth (online readiness rule 6, docs/geo-anchor): a map-frame point
	 * (X north, Y east, metres, as everything here takes) to lat/lon and back through the world's anchor
	 * (FLakeData::Anchor). Bearings, fixes and dead reckoning stay in the map frame; only what persists or is shown as a
	 * position goes through these.
	 */
	SAILINGSIM_API Sailing::FLatLon LatLonAt(const Sailing::FGeoAnchor& Anchor, const FVector2D& Map);
	SAILINGSIM_API FVector2D MapAt(const Sailing::FGeoAnchor& Anchor, const Sailing::FLatLon& Geo);

	/** "2.3 nm" style distance. */
	SAILINGSIM_API FString FormatDistance(double Meters);

	/**
	 * The navigator's plot: bearings taken, the latest fix and the dead-reckoning track from it. A fix is plotted
	 * whenever the bearings taken within FixWindow seconds include two that cross at a good angle (30 degrees or more);
	 * dead reckoning then runs from the fix on the compass heading and the log's speed, as on a paper chart (it does
	 * not know the current or leeway, which is why the next fix lands somewhere else).
	 */
	struct SAILINGSIM_API FPlot
	{
		static constexpr double FixWindow = 600.0;       // s: bearings older than this don't make a fix
		static constexpr double TrackInterval = 30.0;    // s between DR track points
		static constexpr int32 MaxBearings = 8;

		TArray<FBearing> Bearings;
		bool bHasFix = false;
		FVector2D Fix = FVector2D::ZeroVector;
		double FixTime = 0.0;
		double FixSpread = 0.0;    // m, the cocked hat
		FVector2D Dr = FVector2D::ZeroVector;
		TArray<FVector2D> DrTrack; // from the last fix
		double LastTrackTime = 0.0;

		/** Clears the plot and starts DR from a known position (the departure). */
		void Start(const FVector2D& Known, double Time);
		/** Adds a bearing; returns true if it made a new fix. */
		bool AddBearing(const FBearing& Bearing, double VariationEastDeg);
		/** Dead reckoning: heading (true, degrees) and speed through the water (m/s) for Dt seconds. */
		void Advance(double HeadingTrueDeg, double SpeedThroughWater, double Dt, double Time);
	};
}
