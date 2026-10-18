#pragma once

#include "SailingPhysicsApi.h"

#include <string>
#include <vector>

namespace Sailing
{
	/** A position on the earth: degrees, north and east positive (NAD83, which the bakes treat as WGS84: no shift). */
	struct FLatLon
	{
		double LatDeg = 0.0;
		double LonDeg = 0.0;
	};

	/** A position in a world's map frame: metres, +X north, +Y east (the bake's grid and every actor). */
	struct FMapPoint
	{
		double North = 0.0;
		double East = 0.0;
	};

	/**
	 * Online readiness rule 6 (docs/geo-anchor/README.md): where a world sits on the earth. Every bake projects its
	 * sources with "+proj=tmerc +lat_0=.. +lon_0=.. +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m" (pyproj, no datum shift
	 * from the WGS84 inputs), so the map frame's north is the projection's northing and east its easting. This is that
	 * projection exactly: Krueger's series to n^6 on the GRS80 ellipsoid (Karney 2011, "Transverse Mercator with an
	 * accuracy of a few nanometers"), good to well under a millimetre within a thousand kilometres of the central
	 * meridian, which is what PROJ's tmerc computes too. Things that persist (a save, a later shared world) store lat/lon
	 * or a stable id, never map metres: a rebaked grid then moves nothing.
	 */
	struct SAILINGPHYSICS_API FGeoAnchor
	{
		static constexpr double SemiMajor = 6378137.0;              // GRS80 (NAD83) a, m
		static constexpr double InverseFlattening = 298.257222101;  // GRS80 1/f

		double Lat0Deg = 0.0;     // the map frame's origin
		double Lon0Deg = 0.0;     // the central meridian (the origin's longitude in every bake)
		double ScaleK0 = 1.0;     // +k
		double FalseEasting = 0.0;
		double FalseNorthing = 0.0;
		bool bValid = false;

		FGeoAnchor() = default;
		FGeoAnchor(double InLat0Deg, double InLon0Deg);

		/** Reads +lat_0, +lon_0, +k (or +k_0), +x_0 and +y_0 from a proj4 tmerc string. False (and Out untouched) when it
		 *  is not a tmerc on NAD83/GRS80 with both origin values. */
		static bool ParseProj4(const std::string& Proj4, FGeoAnchor& Out);
		/** The anchor a world's bake was made on when its header has no projection (the build scripts' constants): by the
		 *  bake's file name ("RayHubbard", "GalvestonBay", "GulfPassage"). Invalid for an unknown name. */
		static FGeoAnchor ForWorld(const std::string& FileName);

		/** Lat/lon to the map frame (forward transverse Mercator). */
		FMapPoint ToMap(const FLatLon& Geo) const;
		/** The map frame to lat/lon (inverse). */
		FLatLon ToLatLon(const FMapPoint& Map) const;

		/** Metres between two map points (the map frame is conformal and k is within 1e-4 of 1 inside a world). */
		static double Distance(const FMapPoint& A, const FMapPoint& B);
	};

	/** A persistent placement: a stable id first, lat/lon as the fallback when the id is gone (rule 6). */
	struct FGeoPlacement
	{
		std::string Id;
		bool bHasLatLon = false;
		FLatLon Geo;
	};

	/** Something placed by id in a world's current data (a launch spot, a mark): where it is now. */
	struct FPlacedThing
	{
		std::string Id;
		FMapPoint Map;
	};

	/**
	 * Finds a placement among the things a world has now: the thing with its id; failing that (a renamed or removed id),
	 * the thing nearest its lat/lon if within SnapMeters; failing that, -1. OutMap is where the placement lands: the
	 * thing's position, or the lat/lon itself when nothing is near (so a placement survives losing its thing).
	 * OutMatchedById says which rule placed it.
	 */
	SAILINGPHYSICS_API int ResolvePlacement(const FGeoAnchor& Anchor, const std::vector<FPlacedThing>& Things, const FGeoPlacement& Placement,
		double SnapMeters, FMapPoint& OutMap, bool& OutMatchedById);
}
