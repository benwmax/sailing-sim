#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "WorldStream.h"

#include <memory>

struct FLakeData;

/**
 * World streaming (Wide World Rendering PR 2, docs/world-streaming): keeps a world's height tiles resident around the boat.
 *
 * A streamed world (<World>.tiles, Tools/coast/compose_world.py) is read a tile at a time by one worker: the game thread
 * plans (FTileIndex, PlanStreaming: everything within LoadM, nearest first; dropped past KeepM), takes what the worker
 * finished, and swaps the terrain's tile set (FLakeTerrain::SetTiles: an immutable snapshot, so a reader on another thread
 * keeps the one it had). A world baked as one grid gets an index over its grid instead and every tile is resident from the
 * start (nothing to load): the terrain actor's chunks still go by tile, the same way on every world.
 */
class SAILINGSIM_API FWorldStreamer
{
public:
	~FWorldStreamer();

	/** Reads the index (<Directory>/<Name>.tiles, else an index over Lake's grid). False when the world has neither. */
	bool Start(FLakeData& Lake, const FString& Directory, const FString& Name);
	/** The loading screen: reads every tile within RadiusM of (X, Y) now, on all cores, and installs them. */
	void LoadAround(double X, double Y, double RadiusM);
	/** Game thread, each frame, with the boat's map position: plans, launches the next read, installs what arrived. */
	void Tick(double X, double Y);
	/** Waits for the worker (EndPlay, tests). */
	void Stop();

	bool IsStarted() const { return Lake != nullptr; }
	/** Whether the heights stream from a .tiles file (false: a whole grid, all resident). */
	bool IsStreamed() const { return Index.IsStreamed(); }
	const Sailing::FTileIndex& GetIndex() const { return Index; }
	bool IsResident(int32 Tile) const { return Tile >= 0 && size_t(Tile) < ResidentFlags.size() && ResidentFlags[Tile] != 0; }
	/** A resident tile's heights on a streamed world (null when it is not resident, and on a whole-grid world: its chunks read the grid). */
	std::shared_ptr<const Sailing::FTerrainTile> GetTile(int32 Tile) const { return Tiles.IsValidIndex(Tile) ? Tiles[Tile] : nullptr; }
	/** Changes whenever a tile comes or goes (the terrain actor looks at its chunks again). */
	uint32 GetGeneration() const { return Generation; }

	/** How far around the boat tiles are kept (WorldStream.h). */
	Sailing::FStreamRadii Radii;

	// Measures (the README, SailingSim.World.Streaming, the bench's world_* columns).
	int32 NumResident() const { return Resident; }
	int32 NumLoading() const { return InFlight.IsValid() ? 1 + Queue.Num() : Queue.Num(); }
	int64 ResidentBytes() const { return Bytes; }
	int32 NumLoads() const { return Loads; }
	int32 NumDrops() const { return Drops; }
	/** The longest any game-thread call of this has taken (ms), and the last frame's. */
	double LongestTickMs() const { return Longest; }
	double LastTickMs() const { return Last; }
	void ResetLongest() { Longest = 0.0; }

private:
	struct FLoaded
	{
		int32 Tile = INDEX_NONE;
		std::shared_ptr<const Sailing::FTerrainTile> Data;
	};
	FLakeData* Lake = nullptr;
	FString Path;
	Sailing::FTileIndex Index;
	TArray<std::shared_ptr<const Sailing::FTerrainTile>> Tiles;   // by index: resident data (null when not)
	std::vector<uint8_t> ResidentFlags, InFlightFlags;
	TArray<int32> Queue;           // planned reads, nearest first
	TFuture<FLoaded> InFlight;     // the one read on the worker
	int32 Resident = 0, Loads = 0, Drops = 0;
	int64 Bytes = 0;
	uint32 Generation = 1;
	double Longest = 0.0, Last = 0.0;
	double PlannedX = 1e300, PlannedY = 1e300;
	bool bDirty = false;

	/** Reads and inflates one tile (any thread). */
	static FLoaded ReadTile(const FString& File, const Sailing::FTileIndex& Index, int32 Tile);
	void Install(FLoaded&& L);
	void Drop(int32 Tile);
	/** Hands the resident tiles to the terrain (a new snapshot). */
	void Publish();
};
