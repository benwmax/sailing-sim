#pragma once

#include "SailingPhysicsApi.h"

#include <cstdint>
#include <unordered_map>
#include <vector>

namespace Sailing
{
	/**
	 * World objects in tiles (docs/world-object-tiles): the houses, private docks and lidar tree crowns of a world are cut
	 * into square cells (6.4 km, the world's height tiles by default) and only the cells near the camera are drawn. The ground
	 * already streams this way (WorldStream.h); before this, every house and dock of a world was put in its instanced meshes
	 * at the start, so the drawing side grew with the size of the map. Plain logic: the game (FTiledInstances, FTiledMeshes in
	 * SailingSim) fills and empties the cells these decide.
	 */

	/** How far from the camera a kind of object is drawn (m, to a cell's nearest edge). A cell is made within LoadM and let go
	 *  past KeepM: the gap stops a cell on the edge from coming and going as the boat sails along it. */
	struct FObjectRing
	{
		double LoadM = 12000.0;
		double KeepM = 14000.0;
		bool IsValid() const { return LoadM > 0.0 && KeepM >= LoadM; }
	};

	/** The ring for objects whose meshes stop drawing at CullM (0: they never do): made a kilometre before they would show,
	 *  let go 3 km after. */
	SAILINGPHYSICS_API FObjectRing ObjectRingForCull(double CullM, const FObjectRing& NoCull = FObjectRing());

	/** The cells a kind of object occupies (only cells holding something: a long coast's cells, not its whole box). */
	class SAILINGPHYSICS_API FObjectCells
	{
	public:
		static constexpr double kDefaultCellM = 6400.0;   // FTileIndex::kTileM
		explicit FObjectCells(double InCellM = kDefaultCellM) : CellM(InCellM > 0.0 ? InCellM : kDefaultCellM) {}

		/** The id of the cell holding (X, Y), made if it is new. */
		int Add(double X, double Y);
		/** The cell at (Row, Col), -1 if none. */
		int Find(int Row, int Col) const;
		/** The cell row and column a map point falls in. */
		void CellOf(double X, double Y, int& Row, int& Col) const;
		int Num() const { return int(Rows.size()); }
		double GetCellM() const { return CellM; }
		int Row(int Id) const { return Rows[size_t(Id)]; }
		int Col(int Id) const { return Cols[size_t(Id)]; }
		/** From (X, Y) to the cell's nearest edge (0 inside it). */
		double DistanceTo(int Id, double X, double Y) const;
		void Reset() { Rows.clear(); Cols.clear(); ByCell.clear(); }

	private:
		double CellM;
		std::vector<int> Rows, Cols;
		std::unordered_map<int64_t, int> ByCell;
		static int64_t Key(int Row, int Col) { return (int64_t(Row) << 32) ^ int64_t(uint32_t(Col)); }
	};

	/**
	 * Which cells to make and drop for a camera at (X, Y): every cell within Ring.LoadM that is not made, nearest first (at
	 * most MaxMake of them; < 0 for all), and every made cell past Ring.KeepM. Made[Id] is non-zero for a made cell.
	 */
	SAILINGPHYSICS_API void PlanObjectCells(const FObjectCells& Cells, const std::vector<uint8_t>& Made, double X, double Y,
		const FObjectRing& Ring, int MaxMake, std::vector<int>& OutMake, std::vector<int>& OutDrop);

	/**
	 * Reuse, never rebuild (docs/world-object-tiles, the tide-memory lesson): slots for the drawing components of the cells.
	 * A dropped cell's slot goes back on the free list and the next cell to be made takes it, so a long sail turns the same
	 * few components over instead of making and destroying one per cell. The game keeps its components by slot id.
	 */
	class SAILINGPHYSICS_API FSlotPool
	{
	public:
		/** A free slot (bReused true), else a new one at the end. */
		int Acquire(bool& bReused);
		/** Gives a slot back. A slot that is not in use is ignored. */
		void Release(int Slot);
		int NumSlots() const { return int(InUse.size()); }
		int NumInUse() const { return Live; }
		int NumReused() const { return Reused; }
		void Reset() { Free.clear(); InUse.clear(); Live = 0; Reused = 0; }

	private:
		std::vector<int> Free;
		std::vector<uint8_t> InUse;
		int Live = 0, Reused = 0;
	};
}
