#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Async/Future.h"
#include "TreePlacement.h"
#include "LakeTerrainActor.generated.h"

class UProceduralMeshComponent;
class UHierarchicalInstancedStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
struct FLakeData;

/**
 * Renders the baked lake: terrain in 640 m chunks that stream in at four levels of detail around the camera
 * (built on worker threads, a few uploads per frame), cross-timbers trees from the density map, shoreline
 * buildings, bridge decks and the docks from OpenStreetMap. Physics uses the same data through the game mode.
 */
UCLASS()
class SAILINGSIM_API ALakeTerrainActor : public AActor
{
	GENERATED_BODY()

public:
	ALakeTerrainActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

	/** Tree density multiplier for the quality tier (0..1). */
	void SetTreeFraction(float Fraction);

	/** Chunks waiting to be built or upgraded (0 once streaming has caught up). */
	int32 GetPendingChunks() const { return Pending; }

private:
	struct FChunkMesh
	{
		TArray<FVector> Vertices;
		TArray<int32> Triangles;
		TArray<FVector> Normals;
		TArray<FLinearColor> Colors;
	};
	struct FChunk
	{
		int32 Row = 0, Col = 0;   // chunk indices
		int32 Lod = -1;           // step in cells (1, 2, 4, 8; 0 the 1 m shore detail), -1 = not built
		int32 Wanted = 8;
		bool bBuilding = false;
		bool bHasDetail = false;  // the lidar shore detail covers part of it
		TObjectPtr<UProceduralMeshComponent> Mesh;
		TFuture<FChunkMesh> Future;
	};

	const FLakeData* GetLake() const;
	/** HideBelow: the bed deeper than this (m, map frame) is not meshed (it can't be seen through the water). */
	static FChunkMesh BuildChunk(const FLakeData* Lake, int32 ChunkRow, int32 ChunkCol, int32 Step, double HideBelow);
	/** How deep the water hides the bed: where its colour has absorbed 99% of the light coming back (Visual V4). */
	double HideBelow = -1e9;
	void PlaceTrees();
	/** Graphics G2 (Medium and up): cattail and rush clumps in the shallows and at the water's edge. */
	void PlaceReeds();
	bool PlaceHouseModels(const struct FLakeData& Lake);
	void PlaceBuildings();
	void PlaceBridgesAndDocks();

	TArray<FChunk> Chunks;
	int32 ChunkRows = 0, ChunkCols = 0;
	int32 Pending = 0;
	// Perf 1 fix 7: where and when the chunks' detail was last chosen, and how many are building.
	FVector2D LodCamera = FVector2D(1e12, 1e12);
	double LodTime = -1e30;
	int32 Building = 0;
	float TreeFraction = 1.f;
	bool bTreesPlaced = false;

	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> TerrainMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> TreeMeshes;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> TreeModels; // Visual V6: leaf-card trees near the camera
	bool bLoggedInstances = false;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> ReedModels; // Graphics G2: cattails, rushes
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> TreeFar;    // and their opaque crowns beyond
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> TreeMid;    // Graphics G6: opaque crowns that still cast shadows
	/** T1: the near trees' opaque crowns, drawn for the lighting only (ray tracing and distance fields; not in the main or
	 *  depth pass, no shadow): Lumen sees a tree there, so its inside and the ground under it darken. */
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> TreeProxy;
	bool bTreeLooks = true;
	bool bTreeLean = true;   // measuring: -SailingNoTreeLean
	TArray<struct FTreeInstance> ModelTrees;
	FVector2D TreeCenter = FVector2D(1e12, 1e12);
	/** Regroups move only the trees that cross a band's edge, and the mid and far crowns live in 2 km tiles (one component
	 *  per tile, band and model, cloned from TreeMid / TreeFar), so a regroup touches only the components along the band
	 *  edges: the renderer re-adds a component's every instance to the distance-field and Lumen scenes when its instance
	 *  count changes. TreeComps holds the near leaf cards (TreeModels, the first entries) and the tiles' components;
	 *  CompTrees which tree each instance is, CompPlacedAt where the camera was when its transforms were made. */
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> TreeComps;
	TArray<TArray<int32>> CompTrees;
	TArray<FVector2D> CompPlacedAt;
	TMap<int32, int32> TileComps;   // (tile, band, model) -> TreeComps index
	TArray<int32> TreeTile;         // per tree: its tile
	TArray<uint8> TreeBand;         // per tree: 0 none, 1 near, 2 mid, 3 far
	TArray<int32> TreeComp, TreeSlot;
	int32 DriftCursor = 0;
	void UpdateModelTrees(const FVector2D& Camera);
	FTransform TreeTransform(const struct FTreeInstance& I, bool bNear, const FVector2D& Camera, FTransform* OutProxy) const;
	int32 TileComponent(int32 Tile, uint8 Band, int32 Model);
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> BuildingMeshes;
	/** Graphics G6: the G2 houses' tiles (baked Nanite, or procedural where a tile has no bake). */
	UPROPERTY(Transient) TArray<TObjectPtr<UPrimitiveComponent>> HouseTileMeshes;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> BridgeDecks;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> Pilings;
	UPROPERTY(Transient) TObjectPtr<UProceduralMeshComponent> DockMesh;
};
