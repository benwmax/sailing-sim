#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include <cstdint>
#include <memory>
#include <vector>

namespace Sailing
{
	/**
	 * World streaming (docs/world-streaming): one tile of a streamed world's heights, (Cells + 1)^2 nodes at its own spacing
	 * (10 m in the bay, 50 m offshore on the Texas coast), rows north and columns east from its south-west corner. Immutable
	 * once made: the loader builds it on a worker and every reader holds it by shared pointer.
	 */
	struct SAILINGPHYSICS_API FTerrainTile
	{
		int Row = 0, Col = 0;          // in tiles from the world's tile origin
		int Cells = 0;                 // per side
		double Cell = 10.0;            // m between nodes
		double OriginX = 0.0, OriginY = 0.0;  // its south-west node (map frame)
		double Unit = 0.01;            // m per height step
		std::vector<int16_t> Heights;  // (Cells + 1)^2

		double Node(int R, int C) const { return Heights[size_t(R) * (Cells + 1) + C] * Unit; }
		/** Bilinear inside the tile (clamped to its edge). */
		double HeightAt(double X, double Y) const;
	};

	/**
	 * The tiles resident now, as an immutable snapshot (FLakeTerrain holds one by shared pointer: swapping in a new set never
	 * disturbs a worker reading the old). Tile (R, C) covers [OriginX + R TileM, OriginX + (R + 1) TileM) north and the same
	 * east from OriginY. Where no tile is resident the ground is unknown and reads as land, as off a whole grid's edge.
	 */
	class SAILINGPHYSICS_API FTileSet
	{
	public:
		FTileSet(double InTileM, double InOriginX, double InOriginY, const std::vector<std::shared_ptr<const FTerrainTile>>& InTiles);
		const FTerrainTile* At(double X, double Y) const;
		double GetTileM() const { return TileM; }
		double GetOriginX() const { return OriginX; }
		double GetOriginY() const { return OriginY; }
		/** The resident tiles' bounding box in tiles (empty when none). */
		int GetRow0() const { return R0; }
		int GetCol0() const { return C0; }
		int GetNumRows() const { return NR; }
		int GetNumCols() const { return NC; }
		size_t Num() const { return Count; }
		/** The finest spacing among the resident tiles (m). */
		double GetFinestCell() const { return Finest; }
		const std::vector<std::shared_ptr<const FTerrainTile>>& GetSlots() const { return Slots; }

	private:
		double TileM = 6400.0, OriginX = 0.0, OriginY = 0.0, Finest = 10.0;
		int R0 = 0, C0 = 0, NR = 0, NC = 0;
		size_t Count = 0;
		std::vector<std::shared_ptr<const FTerrainTile>> Slots;   // NR x NC, null where nothing is resident
	};

	/**
	 * Lake bed and surrounding land as a height grid (meters, Z = 0 at the conservation pool), baked by
	 * Tools/terrain/build_rayhubbard.py from USGS 3DEP, TWDB bathymetry and the OpenStreetMap shoreline.
	 * Rows run north (+X), columns east (+Y).
	 *
	 * World streaming: the heights are either one whole grid or a set of resident tiles (SetTiles), and a terrain can be a
	 * window onto either (WindowAround): GetRows/GetCols/GetOriginX/GetOriginY/NodeHeight then describe the window, at the
	 * finest spacing, while HeightAt answers wherever there is data. Everything big is held by shared pointer, so copying a
	 * terrain is cheap: a worker takes its own copy (a snapshot) and the game thread may swap tiles meanwhile.
	 */
	class SAILINGPHYSICS_API FLakeTerrain
	{
	public:
		/** Parses a .height file ("SSHT" header + int16 cm). Returns false if the data is not valid. */
		bool LoadHeight(const uint8_t* Data, size_t Size);
		/** Parses a .trees file ("SSTR" header + uint8 density, 0..255). Optional. */
		bool LoadTrees(const uint8_t* Data, size_t Size);
		/**
		 * Graphics G2: parses the 1 m shore detail ("SSDT", uncompressed: Tools/terrain/build_shore_detail.py), lidar
		 * heights in 64 m tiles along the shoreline. Where a tile exists HeightAt uses it instead of the grid.
		 */
		bool LoadDetail(const uint8_t* Data, size_t Size);
		bool HasDetail() const { return Detail != nullptr; }
		double GetDetailCell() const { return Detail ? Detail->Cell : 1.0; }
		/** The 1 m height at a world XY, if a detail tile covers it. */
		bool DetailHeightAt(double X, double Y, double& Height) const;
		/** Whether any detail tile overlaps the box (world metres, X north, Y east). */
		bool HasDetailIn(double MinX, double MinY, double MaxX, double MaxY) const;
		/** Builds a synthetic grid (tests). */
		void InitSynthetic(int Rows, int Cols, double Cell, double OriginX, double OriginY, const std::vector<float>& Heights);
		/** Synthetic tree density (0..255, 255 = 12 m canopy) on its own grid (tests). */
		void InitSyntheticTrees(int Rows, int Cols, double Cell, double OriginX, double OriginY, const std::vector<uint8_t>& Density);

		/**
		 * World streaming: the heights become this tile set (the whole grid, if any, is dropped). The view is the set's
		 * bounding box at its finest spacing (or FinestCell when given, the world's: the view keeps its spacing as coarse
		 * tiles come and go).
		 */
		void SetTiles(std::shared_ptr<const FTileSet> Tiles, double FinestCell = 0.0);
		const FTileSet* GetTiles() const { return Tiles.get(); }
		bool IsTiled() const { return Tiles != nullptr; }
		/**
		 * A window onto the same heights: the view clipped to the square of half-side HalfM around (X, Y), snapped to the
		 * spacing (the physics' derived grids are built over it: the sea fetch, the ocean mask, the shelter map). Shares
		 * the data; the window is never larger than the view it is cut from.
		 */
		FLakeTerrain WindowAround(double X, double Y, double HalfM) const;

		bool IsValid() const { return Rows > 0; }

		/** Ground height (m, relative to pool) at a world XY, bilinear; far outside the grid returns high land. */
		double HeightAt(double X, double Y) const;
		/** Water depth below the pool level (0 on land). */
		double DepthAt(double X, double Y, double WaterLevel = 0.0) const { const double H = HeightAt(X, Y); return H < WaterLevel ? WaterLevel - H : 0.0; }
		/** Tree canopy height (m) at a world XY: density x 12 m (post oak / cedar elm / red cedar). */
		double CanopyAt(double X, double Y) const;
		/** Open water distance (m) from a point toward where the wind comes from, until land; capped at MaxDistance. */
		double FetchToward(double X, double Y, double FromRadians, double MaxDistance = 15000.0) const;
		/**
		 * W3: the fetch the sea grows on, Saville's cosine-weighted mean of FetchToward over +/-45 deg of the wind (nine rays):
		 * waves arrive from a spread of directions, so a spot sheltered dead upwind still sees chop grown along the lake.
		 */
		double EffectiveFetch(double X, double Y, double FromRadians, double MaxDistance = 15000.0) const;

		int GetRows() const { return Rows; }
		int GetCols() const { return Cols; }
		double GetCell() const { return Cell; }
		double GetOriginX() const { return OriginX; }
		double GetOriginY() const { return OriginY; }
		/** Height of a node of the view (row north, column east), meters above the water; clamped to the view's edge. */
		double NodeHeight(int Row, int Col) const;

		/**
		 * The water stands this far (m) below the conservation pool: the whole bed and shore are raised by it, so
		 * the water surface stays at Z = 0 and shoals and banks show the way they do at today's level.
		 */
		void SetLevelBelowPool(double Meters) { LevelBelowPool = Meters; }
		double GetLevelBelowPool() const { return LevelBelowPool; }

	private:
		struct FDetail
		{
			int Tile = 64, Rows = 0, Cols = 0;
			double Cell = 1.0, OriginX = 0.0, OriginY = 0.0, Unit = 0.01;
			std::vector<int32_t> Index;   // per tile of the grid's extent: index into Heights, or -1
			std::vector<int16_t> Heights; // (Tile + 1)^2 nodes per tile
		};
		struct FTrees
		{
			int Rows = 0, Cols = 0;
			double Cell = 20.0, OriginX = 0.0, OriginY = 0.0;
			std::vector<uint8_t> Density;
		};
		// The view: what the getters and NodeHeight describe.
		int Rows = 0, Cols = 0;
		double Cell = 10.0, OriginX = 0.0, OriginY = 0.0;
		double LevelBelowPool = 0.0;
		// A whole grid (the view is a window onto it, RowOff and ColOff nodes in).
		int GridRows = 0, GridCols = 0, RowOff = 0, ColOff = 0;
		double GridOriginX = 0.0, GridOriginY = 0.0, Unit = 0.01;
		std::shared_ptr<const std::vector<int16_t>> Heights;
		// Or resident tiles.
		std::shared_ptr<const FTileSet> Tiles;
		std::shared_ptr<const FTrees> Trees;
		std::shared_ptr<const FDetail> Detail;
		int DetailTileAt(double X, double Y, double& U, double& V) const;
		double GridNode(int Row, int Col) const;
		double GroundAt(double X, double Y) const;
	};

	/**
	 * Wind shelter behind land and trees: for each point, how much the upwind terrain and canopy slow the
	 * wind. Behind an obstacle of height H the wind recovers over roughly 20-30 H, gustier on the way.
	 * Precomputed on a coarse grid for one wind direction (recompute when the wind swings).
	 */
	/** W1: something on the shore that blocks the wind besides the terrain and its tree canopy (a house, a building). */
	struct FShelterObstacle
	{
		double X = 0.0, Y = 0.0;   // centre (m)
		double Radius = 5.0;       // plan half-size (m)
		double Top = 0.0;          // height of its top above the water (m)
	};

	/**
	 * The shore's effect on the wind over the water, for one wind direction: the lee of the terrain, its trees and houses
	 * (a deficit that is deepest within a few heights and has recovered by about 30 heights downwind, W1's analytic
	 * band), times the wind building over open water from the upwind shore (an internal boundary layer: 91 % at the
	 * shore, 97 % after 250 m, full by a kilometre; W6's LES), and the gusts easing over open water (GustAt).
	 */
	class SAILINGPHYSICS_API FShelterMap
	{
	public:
		void Build(const FLakeTerrain& Terrain, double FromRadians, double Cell = 40.0, const std::vector<FShelterObstacle>* Obstacles = nullptr);
		/** 1 = full wind, about 0.3 right behind a wooded bluff, a little under 1 close downwind of any shore. */
		double FactorAt(double X, double Y) const;
		/** The two parts: lee (1 = none) and the open-water building (1 = full fetch). */
		double LeeAt(double X, double Y) const { return Sample(Lee, X, Y); }
		double BuildAt(double X, double Y) const { return Sample(Building, X, Y); }
		/** W3: the gusts' strength over the water as a fraction of the shore's (1 at the upwind shore, 0.73 beyond 7 km). */
		double GustAt(double X, double Y) const { return Sample(Gust, X, Y); }
		double GetFromRadians() const { return FromRadians; }
		bool IsValid() const { return Rows > 0; }

		/** The lee deficit behind an obstacle at Ratio = distance / height (0 = none). */
		static double LeeDeficit(double Ratio);
		/** The wind over the water at a fetch from the upwind shore, as a fraction of the open-water wind. */
		static double OpenWaterBuild(double FetchMeters);
		/** The gust intensity over the water at a fetch from the upwind shore, as a fraction of the shore's. */
		static double OpenWaterGust(double FetchMeters);

	private:
		double Sample(const std::vector<float>& Grid, double X, double Y) const;
		int Rows = 0, Cols = 0;
		double Cell = 40.0, OriginX = 0.0, OriginY = 0.0, FromRadians = 0.0;
		std::vector<float> Lee, Building, Gust;
	};}
