#pragma once

#include "SailingPhysicsApi.h"
#include "LakeTerrain.h"

#include <cmath>
#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

namespace Sailing
{
	/**
	 * World streaming (Wide World Rendering PR 2, docs/world-streaming): a world's heights cut into square tiles, and the
	 * rules for which of them are resident around the boat and where the render frame's origin sits. Plain logic: the game
	 * (FWorldStreamer in SailingSim) reads the files on a worker and applies what these decide.
	 */

	/** A tile in a world's index: where it is and how it is stored (in <World>.tiles, or a window of a whole grid). */
	struct FTileEntry
	{
		int Row = 0, Col = 0;     // in tiles from the index's origin, north and east
		int Cells = 0;            // per side ((Cells + 1)^2 nodes)
		double Cell = 10.0;       // m
		double Unit = 0.01;       // m per height step
		uint32_t Flags = 0;       // kTileZlib, kTileHasWater, kTileHasLand
		uint64_t Offset = 0;      // byte offset of its data in the file
		uint32_t StoredSize = 0;  // bytes in the file (compressed when kTileZlib)
		int16_t MinHeight = 0, MaxHeight = 0;   // in Unit
	};

	constexpr uint32_t kTileZlib = 1;
	constexpr uint32_t kTileHasWater = 2;
	constexpr uint32_t kTileHasLand = 4;

	/**
	 * The tiles a world has. A streamed world reads it from the header of <World>.tiles ("SSTI", version 1: tile size, the
	 * origin, the finest spacing, the tile count, then one 40-byte entry per tile: row, column, cells, spacing, unit, flags,
	 * min and max height, offset, stored size; then the tiles' data, (Cells + 1)^2 int16 each, zlib-compressed). A world
	 * baked as one grid gets an index over its grid (ForGrid), so the terrain's chunks stream the same way everywhere.
	 */
	class SAILINGPHYSICS_API FTileIndex
	{
	public:
		/** The tile size streamed worlds are baked with: 640 cells of 10 m, 128 of 50 m (one chunk), and three of them make the
		 *  render frame's re-centre lattice (kRecentreLatticeM). */
		static constexpr double kTileM = 6400.0;
		/** Bytes of the header before the entries, and of one entry. */
		static constexpr size_t kHeaderBytes = 48;
		static constexpr size_t kEntryBytes = 40;

		/** Reads the header and entries. False when the bytes are not an index (or are cut short). */
		bool Parse(const uint8_t* Data, size_t Size);
		/** The index's tile count from the first bytes of a .tiles file (0 if not one): how many bytes Parse needs. */
		static size_t HeaderSize(const uint8_t* Data, size_t Size);
		/** An index over a whole grid: tiles of TileM from the grid's origin (the last row and column may be partial). */
		static FTileIndex ForGrid(const FLakeTerrain& Terrain, double TileM);

		bool IsValid() const { return !Tiles.empty(); }
		double GetTileM() const { return TileM; }
		double GetOriginX() const { return OriginX; }
		double GetOriginY() const { return OriginY; }
		double GetFinestCell() const { return Finest; }
		/** Whether its tiles come from a file (a streamed world) or a whole grid. */
		bool IsStreamed() const { return bStreamed; }
		const std::vector<FTileEntry>& GetTiles() const { return Tiles; }
		/** The tile at (Row, Col), -1 if the world has none there. */
		int Find(int Row, int Col) const;
		/** The tile row and column a map point falls in (whether or not the world has a tile there). */
		void TileOf(double X, double Y, int& Row, int& Col) const;
		/** A tile's corner (south-west, map frame) and the distance from a point to its nearest edge (0 inside). */
		void Corner(const FTileEntry& T, double& X, double& Y) const { X = OriginX + T.Row * TileM; Y = OriginY + T.Col * TileM; }
		double DistanceTo(const FTileEntry& T, double X, double Y) const;
		/** The map extent the tiles cover. */
		void Bounds(double& MinX, double& MinY, double& MaxX, double& MaxY) const;
		/** A tile's heights from its uncompressed bytes ((Cells + 1)^2 little-endian int16). */
		std::shared_ptr<const FTerrainTile> MakeTile(const FTileEntry& T, const uint8_t* Raw, size_t Size) const;
		/** A tile of a whole grid (ForGrid's), cut from the terrain's own nodes. */
		std::shared_ptr<const FTerrainTile> CutTile(const FTileEntry& T, const FLakeTerrain& Grid) const;

	private:
		double TileM = kTileM, OriginX = 0.0, OriginY = 0.0, Finest = 10.0;
		bool bStreamed = false;
		std::vector<FTileEntry> Tiles;
		std::unordered_map<int64_t, int> ByCell;
		static int64_t Key(int Row, int Col) { return (int64_t(Row) << 32) ^ int64_t(uint32_t(Col)); }
		void Reindex();
	};

	/** How far around the boat the tiles are kept (m, to a tile's nearest edge). */
	struct FStreamRadii
	{
		/** Loaded within this: the physics' window (FPhysicsWindow::HalfM) with a tile to spare. */
		double LoadM = 26000.0;
		/** Dropped past this (the gap stops a boat on a tile's edge loading and dropping it over and over). */
		double KeepM = 32000.0;
	};

	/**
	 * Which tiles to load and drop for a boat at (X, Y): load every tile within LoadM that is neither resident nor on its
	 * way, nearest first; drop every resident tile past KeepM. The tile under the boat and its neighbours always come first.
	 */
	SAILINGPHYSICS_API void PlanStreaming(const FTileIndex& Index, double X, double Y, const FStreamRadii& Radii,
		const std::vector<uint8_t>& Resident, const std::vector<uint8_t>& InFlight, std::vector<int>& OutLoad, std::vector<int>& OutDrop);

	/**
	 * The render frame (docs/world-streaming): Unreal draws in single-precision floats near the camera, so the game keeps its
	 * render origin near the boat and moves it in one frame when she has sailed RecentreM from it. The physics never moves:
	 * it stays in the world's map frame in doubles (FGeoAnchor gives lat/lon beside it). The origin sits on a lattice of
	 * kRecentreLatticeM (19.2 km: three tiles, a whole number of the water's 480 m and 60 m detail tiles and of every
	 * texture repeat that divides it, so nothing periodic in the materials jumps when it moves).
	 */
	constexpr double kRecentreLatticeM = 19200.0;
	constexpr double kRecentreM = 20000.0;
	/** Whether a boat at (X, Y) needs the origin moved from (OriginX, OriginY), and where to (the lattice point nearest her). */
	SAILINGPHYSICS_API bool NeedsRecentre(double OriginX, double OriginY, double X, double Y, double& OutX, double& OutY,
		double ThresholdM = kRecentreM, double LatticeM = kRecentreLatticeM);

	/**
	 * The physics' derived grids on a streamed world (the sea fetch, the ocean mask, the shelter map) are built over a window
	 * around the boat, not the whole world: HalfM covers the longest march (the fetch's 15 km) from anywhere within CoreM of
	 * the window's centre, so inside the core a window gives the whole world's answer. Re-marched on a worker when the boat
	 * leaves the core, and at each re-centre.
	 */
	struct FPhysicsWindow
	{
		double HalfM = 24000.0;
		double CoreM = 8000.0;
		double CenterX = 0.0, CenterY = 0.0;
		bool bValid = false;
		bool Contains(double X, double Y) const { return bValid && std::fabs(X - CenterX) <= CoreM && std::fabs(Y - CenterY) <= CoreM; }
	};
}
