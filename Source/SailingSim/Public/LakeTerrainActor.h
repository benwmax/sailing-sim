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
		int32 Lod = -1;           // step in cells (1, 2, 4, 8), -1 = not built
		int32 Wanted = 8;
		bool bBuilding = false;
		TObjectPtr<UProceduralMeshComponent> Mesh;
		TFuture<FChunkMesh> Future;
	};

	const FLakeData* GetLake() const;
	/** HideBelow: the bed deeper than this (m, map frame) is not meshed (it can't be seen through the water). */
	static FChunkMesh BuildChunk(const FLakeData* Lake, int32 ChunkRow, int32 ChunkCol, int32 Step, double HideBelow);
	/** How deep the water hides the bed: where its colour has absorbed 99% of the light coming back (Visual V4). */
	double HideBelow = -1e9;
	void PlaceTrees();
	void PlaceBuildings();
	void PlaceBridgesAndDocks();

	TArray<FChunk> Chunks;
	int32 ChunkRows = 0, ChunkCols = 0;
	int32 Pending = 0;
	float TreeFraction = 1.f;
	bool bTreesPlaced = false;

	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> TerrainMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> TreeMeshes;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> TreeModels; // Visual V6: leaf-card trees near the camera
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> TreeFar;    // and their opaque crowns beyond
	TArray<struct FTreeInstance> ModelTrees;
	FVector2D TreeCenter = FVector2D(1e12, 1e12);
	void UpdateModelTrees(const FVector2D& Camera);
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> BuildingMeshes;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> BridgeDecks;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> Pilings;
	UPROPERTY(Transient) TObjectPtr<UProceduralMeshComponent> DockMesh;
};
