#pragma once

#include "CoreMinimal.h"
#include "UObject/StrongObjectPtr.h"
#include "ObjectTiles.h"

#include <vector>

class AActor;
class UInstancedStaticMeshComponent;
class UPrimitiveComponent;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;

/**
 * World objects in tiles (docs/world-object-tiles): the houses, private docks and their kit tiles are drawn only in the
 * cells near the camera, the way the ground's chunks are (docs/world-streaming). The cells come and go by
 * Sailing::PlanObjectCells (ObjectTiles.h); the components that draw them are kept in a pool and handed to the next cell,
 * never made and destroyed one per cell. -SailingWholeWorldObjects puts back the old way (everything at the start), to
 * compare; -SailingObjectRing=<load km>,<keep km> sets the ring of the objects that never stop drawing (the kit tiles).
 */
namespace SailingObjects
{
	/** Off with -SailingWholeWorldObjects. */
	SAILINGSIM_API bool Enabled();
	/** The ring for objects whose meshes have no cull distance: 12 km / 14 km, or -SailingObjectRing. */
	SAILINGSIM_API Sailing::FObjectRing NoCullRing();
	/** The ring for a component's instances by its cull distance (cm; 0 = none). */
	SAILINGSIM_API Sailing::FObjectRing RingForCullCm(float CullCm);
	/** On every world (not only a streamed one) the model trees past this leave the instance lists (m): the far crowns stop
	 *  drawing at 9 km. */
	constexpr double TreeKeepM = 9500.0;
}

/**
 * Instanced objects by cell: each kind has a template component (made by the caller with its mesh, cull distance, shadow,
 * lighting and custom-data settings, registered and kept empty) that is cloned for a cell when it comes into the kind's
 * ring and emptied back into the pool when it leaves. Objects are added in the owner's frame (map centimetres for the
 * terrain actor, which stands at the map's origin), so a cell made late in the sail stands where one made at the start would.
 */
class SAILINGSIM_API FTiledInstances
{
public:
	/** Keep: places a new component with the owner (ALakeTerrainActor::KeepWithActor for Static components), before it
	 *  registers; null attaches it to the owner's root. Holder: an owner's UPROPERTY list the clones are added to. */
	void Init(AActor* InOwner, TFunction<void(USceneComponent*)> InKeep, TArray<TObjectPtr<UPrimitiveComponent>>* InHolder);
	/** A kind and its ring (by default from the template's cull distance). Returns its id. */
	int32 AddKind(UInstancedStaticMeshComponent* Template, double CellM = Sailing::FObjectCells::kDefaultCellM);
	int32 AddKind(UInstancedStaticMeshComponent* Template, const Sailing::FObjectRing& Ring, double CellM = Sailing::FObjectCells::kDefaultCellM);
	/** One object: its transform in the owner's frame (cm) and the kind's custom floats (template's NumCustomDataFloats). */
	void Add(int32 Kind, const FTransform& Local, TConstArrayView<float> Custom = {});
	/** Makes every cell within the rings of Camera (map m) at once: the start, before anything is drawn. */
	void Start(const FVector2D& Camera);
	/** Each frame: drops the cells past their ring and makes up to MaxMakes of the nearest wanted ones. Returns how many are
	 *  still wanted. */
	int32 Update(const FVector2D& Camera, int32 MaxMakes = 2);

	bool IsEmpty() const { return Kinds.Num() == 0; }
	int32 NumPending() const { return Pending; }
	int32 NumCellsLive() const;
	int32 NumCellsMade() const { return Made; }
	int32 NumCellsDropped() const { return Dropped; }
	/** Components in all the kinds' pools (in use or free): what a long sail must not keep growing. */
	int32 NumComponents() const;
	int64 NumInstancesLive() const { return InstancesLive; }
	int64 NumObjects() const;
	int32 NumKinds() const { return Kinds.Num(); }
	/** A kind's cells holding something, and whether one is made (tests). */
	const Sailing::FObjectCells* CellsOf(int32 Kind) const { return Kinds.IsValidIndex(Kind) ? &Kinds[Kind]->Cells : nullptr; }
	bool IsMade(int32 Kind, int32 Cell) const;
	UInstancedStaticMeshComponent* ComponentOf(int32 Kind, int32 Cell) const;

private:
	struct FKind
	{
		TWeakObjectPtr<UInstancedStaticMeshComponent> Template;
		Sailing::FObjectRing Ring;
		int32 Floats = 0;
		Sailing::FObjectCells Cells;
		TArray<TArray<FTransform>> X;     // by cell
		TArray<TArray<float>> D;          // by cell: Floats per object
		std::vector<uint8_t> MadeFlags;   // by cell
		TArray<int32> SlotOf;             // by cell: its pool slot (INDEX_NONE when not made)
		Sailing::FSlotPool Pool;
		TArray<TWeakObjectPtr<UInstancedStaticMeshComponent>> Slots;
		explicit FKind(double CellM) : Cells(CellM) {}
	};
	TWeakObjectPtr<AActor> Owner;
	TFunction<void(USceneComponent*)> Keep;
	TArray<TObjectPtr<UPrimitiveComponent>>* Holder = nullptr;
	TArray<TUniquePtr<FKind>> Kinds;   // by pointer: the std containers inside may not be moved bytewise
	FVector2D PlannedAt = FVector2D(1e12, 1e12);
	int32 Pending = 0, Made = 0, Dropped = 0;
	int64 InstancesLive = 0;
	void MakeCell(FKind& K, int32 Cell);
	void DropCell(FKind& K, int32 Cell);
};

/**
 * Baked tile meshes by cell (the G2 houses' 500 m Nanite tiles, /Game/World/Baked): a tile's mesh is loaded
 * asynchronously when it comes into the ring and drawn by a pooled component; when it leaves the ring the component lets go
 * of the mesh (and the engine of the mesh's memory, at its next garbage collection) and goes back to the pool. The tiles
 * within the ring at the start are loaded at once, as every tile was before.
 */
class SAILINGSIM_API FTiledMeshes
{
public:
	/** MakeComponent: a new Static component for a tile, kept with the owner, not registered (the pool registers it). */
	void Init(TFunction<UStaticMeshComponent*()> InMake, TArray<TObjectPtr<UPrimitiveComponent>>* InHolder, const Sailing::FObjectRing& InRing, double TileM);
	/** A tile: the cell holding Center and its mesh's object path (/Game/World/Baked/<Name>.<Name>). */
	void Add(const FVector2D& Center, const FString& ObjectPath);
	void Start(const FVector2D& Camera);
	/** Requests the tiles coming into the ring, lets go of those leaving it, draws up to MaxAdds that have arrived. Returns
	 *  how many are still wanted (asked for, not drawn yet). */
	int32 Update(const FVector2D& Camera, int32 MaxAdds = 4);
	/** Cancels the loads in flight (their answers are ignored) and empties the pool's components. */
	void Reset();
	/** Only cancels the loads in flight (EndPlay: the components go with their owner). */
	void Cancel() { Answers = MakeShared<FAnswers>(); Waiting.Reset(); }

	bool IsEmpty() const { return Tiles.Num() == 0; }
	int32 NumTiles() const { return Tiles.Num(); }
	int32 NumPending() const { return Pending; }
	int32 NumLive() const { return Pool.NumInUse(); }
	int32 NumComponents() const { return Pool.NumSlots(); }
	int32 NumMade() const { return Made; }
	int32 NumDropped() const { return Dropped; }
	int32 NumFailed() const { return Failed; }
	const Sailing::FObjectRing& GetRing() const { return Ring; }

private:
	struct FTile
	{
		FString Path;
		uint8 State = 0;   // 0 not wanted, 1 asked for, 2 drawn
		uint32 Ask = 0;    // which request an answer belongs to (a tile dropped and asked for again ignores the first)
		int32 Slot = INDEX_NONE;
	};
	struct FAnswers
	{
		TArray<TTuple<int32, uint32, TStrongObjectPtr<UStaticMesh>>> Arrived;   // tile, ask, mesh (null: failed)
	};
	TFunction<UStaticMeshComponent*()> MakeComponent;
	TArray<TObjectPtr<UPrimitiveComponent>>* Holder = nullptr;
	Sailing::FObjectRing Ring;
	Sailing::FObjectCells Cells;
	TArray<FTile> Tiles;   // by cell
	std::vector<uint8_t> WantedFlags;
	TSharedPtr<FAnswers> Answers;
	TArray<TTuple<int32, uint32, TStrongObjectPtr<UStaticMesh>>> Waiting;   // arrived, render data not ready yet
	Sailing::FSlotPool Pool;
	TArray<TWeakObjectPtr<UStaticMeshComponent>> Slots;
	FVector2D PlannedAt = FVector2D(1e12, 1e12);
	int32 Pending = 0, Made = 0, Dropped = 0, Failed = 0;
	void Request(int32 Tile);
	bool Draw(int32 Tile, UStaticMesh* Mesh);
	void Drop(int32 Tile);
};
