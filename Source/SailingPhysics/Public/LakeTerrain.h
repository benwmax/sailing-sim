#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include <cstdint>
#include <vector>

namespace Sailing
{
	/**
	 * Lake bed and surrounding land as a height grid (meters, Z = 0 at the conservation pool), baked by
	 * Tools/terrain/build_rayhubbard.py from USGS 3DEP, TWDB bathymetry and the OpenStreetMap shoreline.
	 * Rows run north (+X), columns east (+Y).
	 */
	class SAILINGPHYSICS_API FLakeTerrain
	{
	public:
		/** Parses a .height file ("SSHT" header + int16 cm). Returns false if the data is not valid. */
		bool LoadHeight(const uint8_t* Data, size_t Size);
		/** Parses a .trees file ("SSTR" header + uint8 density, 0..255). Optional. */
		bool LoadTrees(const uint8_t* Data, size_t Size);
		/** Builds a synthetic grid (tests). */
		void InitSynthetic(int Rows, int Cols, double Cell, double OriginX, double OriginY, const std::vector<float>& Heights);

		bool IsValid() const { return Rows > 0; }

		/** Ground height (m, relative to pool) at a world XY, bilinear; far outside the grid returns high land. */
		double HeightAt(double X, double Y) const;
		/** Water depth below the pool level (0 on land). */
		double DepthAt(double X, double Y, double WaterLevel = 0.0) const { const double H = HeightAt(X, Y); return H < WaterLevel ? WaterLevel - H : 0.0; }
		/** Tree canopy height (m) at a world XY: density x 12 m (post oak / cedar elm / red cedar). */
		double CanopyAt(double X, double Y) const;
		/** Open water distance (m) from a point toward where the wind comes from, until land; capped at MaxDistance. */
		double FetchToward(double X, double Y, double FromRadians, double MaxDistance = 15000.0) const;

		int GetRows() const { return Rows; }
		int GetCols() const { return Cols; }
		double GetCell() const { return Cell; }
		double GetOriginX() const { return OriginX; }
		double GetOriginY() const { return OriginY; }
		/** Height of a grid node (row north, column east), meters above the water. */
		double NodeHeight(int Row, int Col) const;

		/**
		 * The water stands this far (m) below the conservation pool: the whole bed and shore are raised by it, so
		 * the water surface stays at Z = 0 and shoals and banks show the way they do at today's level.
		 */
		void SetLevelBelowPool(double Meters) { LevelBelowPool = Meters; }
		double GetLevelBelowPool() const { return LevelBelowPool; }

	private:
		int Rows = 0, Cols = 0;
		double Cell = 10.0, OriginX = 0.0, OriginY = 0.0, Unit = 0.01;
		double LevelBelowPool = 0.0;
		std::vector<int16_t> Heights;
		int TreeRows = 0, TreeCols = 0;
		double TreeCell = 20.0, TreeOriginX = 0.0, TreeOriginY = 0.0;
		std::vector<uint8_t> Trees;
	};

	/**
	 * Wind shelter behind land and trees: for each point, how much the upwind terrain and canopy slow the
	 * wind. Behind an obstacle of height H the wind recovers over roughly 20-30 H, gustier on the way.
	 * Precomputed on a coarse grid for one wind direction (recompute when the wind swings).
	 */
	class SAILINGPHYSICS_API FShelterMap
	{
	public:
		void Build(const FLakeTerrain& Terrain, double FromRadians, double Cell = 40.0);
		/** 1 = full wind, about 0.3 right behind a wooded bluff. */
		double FactorAt(double X, double Y) const;
		double GetFromRadians() const { return FromRadians; }
		bool IsValid() const { return Rows > 0; }

	private:
		int Rows = 0, Cols = 0;
		double Cell = 40.0, OriginX = 0.0, OriginY = 0.0, FromRadians = 0.0;
		std::vector<float> Factor;
	};
}
