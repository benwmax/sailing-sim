#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "UObject/StrongObjectPtr.h"

class UStaticMesh;

/**
 * Wide World Rendering, PR 1 (docs/world-far): the far coast ring. Past the near terrain (ALakeTerrainActor's chunks, which
 * stop at InnerM from the camera when a world has a ring) the land is drawn out to OuterM from baked static Nanite meshes,
 * one per TileM tile (/Game/World/Far/SM_Far_<World>_<row>_<col>, UWorldKitLibrary::BakeFarRing) with M_FarLand: no shadow,
 * not in the Lumen scene or the distance fields, sunk under the water inside the hand-over and bent by the earth's
 * curvature in the material (FarRing::OffsetZ mirrors it). The heights come from <World>.far (Tools/terrain/build_far_ring.py).
 */
struct SAILINGSIM_API FFarRingTile
{
	int32 Row = 0, Col = 0;   // in tiles, north and east from the map origin
	int32 Cells = 0;          // per side
	int32 Offset = 0;         // byte offset of its heights in the file
};

struct SAILINGSIM_API FFarRingData
{
	double TileM = 8000.0, InnerM = 8000.0, OuterM = 40000.0;
	double Unit = 0.01;   // m per height step (0.05 where the land rises past 320 m)
	TArray<FFarRingTile> Tiles;
	/** The whole file when loaded with heights (tests, the bake); empty when only the index is read (the game). */
	TArray<uint8> Bytes;

	/** Reads <Directory>/<World>.far. */
	bool Load(const FString& Path, bool bHeights);
	static FString PathFor(const FString& World);
	bool IsValid() const { return Tiles.Num() > 0; }

	/** A tile's node height (m above the world's datum) and sky visibility (0..1); R north, C east. Needs the heights. */
	double NodeHeight(int32 Tile, int32 R, int32 C) const;
	double NodeSky(int32 Tile, int32 R, int32 C) const;
	/** The far mesh's height at a point (the bake's triangles: each cell split along R + C), if a tile with land covers it. */
	bool HeightAt(double X, double Y, double& Out) const;
	int32 FindTile(int32 Row, int32 Col) const;
	/** Its corner (m, map frame). */
	FVector2D TileOrigin(const FFarRingTile& T) const { return FVector2D(T.Row * TileM, T.Col * TileM); }

	/** /Game/World/Far/SM_Far_<World>_<row>_<col> (m for minus). */
	static FString AssetPath(const FString& World, const FFarRingTile& T);

private:
	TMap<FIntPoint, int32> ByCell;
};

namespace FarRing
{
	/** The near terrain hands over here: its chunks are drawn while their nearest edge is within InnerM. The far land is
	 *  buried under the water inside InnerM - SinkMarginM (so no far triangle reaches past InnerM half-buried), and sits
	 *  UnderM lower than the near terrain out to BandEndM (where both may be drawn, the near terrain wins the depth test),
	 *  coming back up over the next RiseM. */
	constexpr double SinkMarginM = 200.0;
	constexpr double BuryZ = -60.0;      // m: under any water's absorption (the near bed is not meshed below -15 m)
	constexpr double UnderM = 2.0;
	constexpr double RiseM = 1500.0;
	/** The world position offset M_FarLand applies (m, vertical) to a vertex at height Z (m, world) Distance metres from the
	 *  camera: the curvature drop (CurvatureDrop), the burial inside the hand-over and the under-band. Mirrors FAR_LAND_WPO. */
	SAILINGSIM_API double OffsetZ(double DistanceM, double Z, double InnerM, double BandEndM);
	/** Where the under-band ends for a near chunk of this size: InnerM plus the chunk's diagonal (the farthest a drawn chunk reaches). */
	inline double BandEndM(double InnerM, double ChunkM) { return InnerM + ChunkM * UE_DOUBLE_SQRT_2; }
	/** Whether a far tile is drawn for a camera at Cam: part of it lies outside the burial and its nearest point inside OuterM. */
	SAILINGSIM_API bool TileVisible(const FFarRingData& Ring, const FFarRingTile& Tile, const FVector2D& Cam);
	/** Whether a near chunk is drawn (its nearest edge within InnerM; with no ring, CapM = the old 20 km). */
	inline bool NearChunkDrawn(double NearestEdgeM, double CapM) { return NearestEdgeM < CapM; }
	/** -SailingNoFarRing turns the ring off (the near terrain then draws to 20 km as before). */
	SAILINGSIM_API bool Enabled();
}

/**
 * Loads a world's far tiles without blocking the game thread: the index (<World>.far) on a worker, then every tile's mesh
 * by an asynchronous package load; the game thread only polls and takes what has arrived (ALakeTerrainActor adds a few
 * components a frame). LongestCallMs is the longest any of its game-thread calls took (SailingSim.World.FarRing holds it).
 */
class SAILINGSIM_API FFarRingLoader
{
public:
	/** Starts reading World's index on a worker; returns at once. False when the world has no ring (or it is off). */
	bool Start(const FString& World);
	/** Game thread, each frame: once the index is in, requests the tiles' packages (asynchronously). */
	void Poll();
	/** The index, once read (null before, or when the world has none). */
	const FFarRingData* Data() const { return Ring.IsValid() && Ring->IsValid() ? Ring.Get() : nullptr; }
	/** The meshes that arrived since the last call: (tile index, mesh). */
	void TakeArrived(TArray<TPair<int32, UStaticMesh*>>& Out);
	/** Every tile's request answered (loaded or failed). */
	bool IsDone() const;
	int32 NumRequested() const { return Requested; }
	int32 NumArrived() const;
	int32 NumFailed() const;
	double LongestCallMs() const { return Longest; }
	void Reset();

private:
	struct FState
	{
		TArray<TPair<int32, TStrongObjectPtr<UStaticMesh>>> Arrived;
		int32 Answered = 0, Loaded = 0, Failed = 0;
	};
	FString World;
	TFuture<TSharedPtr<FFarRingData>> Index;
	TSharedPtr<FFarRingData> Ring;
	TSharedPtr<FState> State;
	int32 Requested = 0;
	double Longest = 0.0;
	void Note(double StartSeconds);
};
