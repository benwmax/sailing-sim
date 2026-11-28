#include "ObjectStreaming.h"
#include "BenchRunner.h"
#include "SailingSim.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "StaticMeshResources.h"
#include "UObject/UObjectGlobals.h"

#include <algorithm>

namespace SailingObjects
{
	bool Enabled()
	{
		static SailingArgs::FCachedFlag Whole(TEXT("SailingWholeWorldObjects"));
		return !Whole.Get();
	}

	Sailing::FObjectRing NoCullRing()
	{
		Sailing::FObjectRing R;
		FString Arg;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingObjectRing="), Arg, false))
		{
			FString A, B;
			if (Arg.Split(TEXT(","), &A, &B))
			{
				Sailing::FObjectRing Asked;
				Asked.LoadM = FCString::Atod(*A) * 1000.0;
				Asked.KeepM = FCString::Atod(*B) * 1000.0;
				if (Asked.IsValid()) R = Asked;
			}
		}
		return R;
	}

	Sailing::FObjectRing RingForCullCm(float CullCm)
	{
		return Sailing::ObjectRingForCull(double(CullCm) / 100.0, NoCullRing());
	}

	void ClearClonedPlacement(USceneComponent* C)
	{
		if (!C) return;
		// A clone made from a template copies its relative transform and its "component-to-world is up to date" flag, but
		// not the component-to-world itself (identity). SetRelativeTransform(Identity) then sees no move (identity to
		// identity) and leaves the copied relative transform in place, so the owner's transform was applied twice: a clone
		// of a template kept 30 cm down with the tide stood 60 cm down. Set the fields directly and recompute.
		C->SetRelativeLocation_Direct(FVector::ZeroVector);
		C->SetRelativeRotation_Direct(FRotator::ZeroRotator);
		C->SetRelativeScale3D_Direct(FVector::OneVector);
		C->UpdateComponentToWorld();
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// FTiledInstances

void FTiledInstances::Init(AActor* InOwner, TFunction<void(USceneComponent*)> InKeep, TArray<TObjectPtr<UPrimitiveComponent>>* InHolder)
{
	Owner = InOwner;
	Keep = MoveTemp(InKeep);
	Holder = InHolder;
}

int32 FTiledInstances::AddKind(UInstancedStaticMeshComponent* Template, double CellM)
{
	return AddKind(Template, SailingObjects::RingForCullCm(Template ? float(Template->InstanceEndCullDistance) : 0.f), CellM);
}

int32 FTiledInstances::AddKind(UInstancedStaticMeshComponent* Template, const Sailing::FObjectRing& Ring, double CellM)
{
	TUniquePtr<FKind> K = MakeUnique<FKind>(CellM);
	K->Template = Template;
	K->Ring = Ring;
	K->Floats = Template ? Template->NumCustomDataFloats : 0;
	return Kinds.Add(MoveTemp(K));
}

void FTiledInstances::Add(int32 Kind, const FTransform& Local, TConstArrayView<float> Custom)
{
	if (!Kinds.IsValidIndex(Kind)) return;
	FKind& K = *Kinds[Kind];
	const FVector P = Local.GetTranslation() / 100.0;   // cm in the owner's frame: map metres for the terrain actor
	const int32 Cell = K.Cells.Add(P.X, P.Y);
	if (Cell >= K.X.Num())
	{
		K.X.SetNum(Cell + 1);
		K.D.SetNum(Cell + 1);
		K.SlotOf.SetNum(Cell + 1);
		K.SlotOf[Cell] = INDEX_NONE;
		K.MadeFlags.resize(size_t(Cell) + 1, 0);
	}
	K.X[Cell].Add(Local);
	if (K.Floats > 0)
	{
		// Exactly the kind's floats (short data padded with zeros), so object i's floats start at i * Floats.
		const int32 At = K.D[Cell].AddZeroed(K.Floats);
		for (int32 I = 0; I < FMath::Min(K.Floats, Custom.Num()); ++I) K.D[Cell][At + I] = Custom[I];
	}
}

int32 FTiledInstances::NumCellsLive() const
{
	int32 N = 0;
	for (const TUniquePtr<FKind>& K : Kinds) N += K->Pool.NumInUse();
	return N;
}

int32 FTiledInstances::NumComponents() const
{
	int32 N = 0;
	for (const TUniquePtr<FKind>& K : Kinds) N += K->Pool.NumSlots();
	return N;
}

int64 FTiledInstances::NumObjects() const
{
	int64 N = 0;
	for (const TUniquePtr<FKind>& K : Kinds) for (const TArray<FTransform>& X : K->X) N += X.Num();
	return N;
}

bool FTiledInstances::IsMade(int32 Kind, int32 Cell) const
{
	return Kinds.IsValidIndex(Kind) && Cell >= 0 && size_t(Cell) < Kinds[Kind]->MadeFlags.size() && Kinds[Kind]->MadeFlags[size_t(Cell)] != 0;
}

UInstancedStaticMeshComponent* FTiledInstances::ComponentOf(int32 Kind, int32 Cell) const
{
	if (!IsMade(Kind, Cell)) return nullptr;
	const FKind& K = *Kinds[Kind];
	return K.Slots.IsValidIndex(K.SlotOf[Cell]) ? K.Slots[K.SlotOf[Cell]].Get() : nullptr;
}

void FTiledInstances::MakeCell(FKind& K, int32 Cell)
{
	UInstancedStaticMeshComponent* Template = K.Template.Get();
	AActor* O = Owner.Get();
	if (!Template || !O) return;
	bool bReused = false;
	const int32 Slot = K.Pool.Acquire(bReused);
	if (Slot >= K.Slots.Num()) K.Slots.SetNum(Slot + 1);
	UInstancedStaticMeshComponent* C = K.Slots[Slot].Get();
	if (!C)
	{
		// A clone of the template (its class too: mesh, materials, cull distances, shadows, lighting, custom floats), as the
		// crown tiles are made (ALakeTerrainActor::TileComponent). It stays for the life of the owner and passes from cell
		// to cell.
		C = NewObject<UInstancedStaticMeshComponent>(O, Template->GetClass(), NAME_None, RF_NoFlags, Template);
		C->ClearInstances();
		SailingObjects::ClearClonedPlacement(C);   // the template's placement is the owner's; Keep gives it again
		if (Keep) Keep(C);
		else C->SetupAttachment(O->GetRootComponent());
		C->RegisterComponent();
		if (Holder) Holder->Add(C);
		K.Slots[Slot] = C;
	}
	const TArray<FTransform>& X = K.X[Cell];
	const int32 First = C->GetInstanceCount();   // 0: a pooled component comes back empty
	C->AddInstances(X, false, false);            // in the component's own frame, the owner's (see the class comment)
	if (K.Floats > 0)
	{
		const TArray<float>& D = K.D[Cell];
		for (int32 I = 0; I < X.Num(); ++I) C->SetCustomData(First + I, TArrayView<const float>(&D[I * K.Floats], K.Floats), false);
	}
	C->MarkRenderStateDirty();
	K.SlotOf[Cell] = Slot;
	K.MadeFlags[size_t(Cell)] = 1;
	InstancesLive += X.Num();
	++Made;
}

void FTiledInstances::DropCell(FKind& K, int32 Cell)
{
	const int32 Slot = K.SlotOf[Cell];
	if (K.Slots.IsValidIndex(Slot))
	{
		// Emptied (its instance buffers go), not destroyed: the next cell of this kind takes it.
		if (UInstancedStaticMeshComponent* C = K.Slots[Slot].Get()) C->ClearInstances();
		K.Pool.Release(Slot);
	}
	K.SlotOf[Cell] = INDEX_NONE;
	K.MadeFlags[size_t(Cell)] = 0;
	InstancesLive -= K.X[Cell].Num();
	++Dropped;
}

void FTiledInstances::Start(const FVector2D& Camera)
{
	PlannedAt = FVector2D(1e12, 1e12);
	Update(Camera, -1);
}

int32 FTiledInstances::Update(const FVector2D& Camera, int32 MaxMakes)
{
	// Planned again after 250 m, or while cells are still wanted (a few made a frame).
	if (Pending == 0 && FVector2D::Distance(Camera, PlannedAt) < 250.0) return 0;
	PlannedAt = Camera;
	struct FWant { double D; int32 Kind; int32 Cell; };
	TArray<FWant> Wanted;
	std::vector<int> Make, Drop;
	for (int32 KI = 0; KI < Kinds.Num(); ++KI)
	{
		FKind& K = *Kinds[KI];
		Sailing::PlanObjectCells(K.Cells, K.MadeFlags, Camera.X, Camera.Y, K.Ring, -1, Make, Drop);
		for (const int D : Drop) DropCell(K, D);
		for (const int M : Make) Wanted.Add({ K.Cells.DistanceTo(M, Camera.X, Camera.Y), KI, M });
	}
	// The nearest first, across the kinds.
	Wanted.Sort([](const FWant& A, const FWant& B) { return A.D < B.D; });
	int32 Done = 0;
	for (const FWant& W : Wanted)
	{
		if (MaxMakes >= 0 && Done >= MaxMakes) break;
		MakeCell(*Kinds[W.Kind], W.Cell);
		++Done;
	}
	Pending = Wanted.Num() - Done;
	return Pending;
}

// ---------------------------------------------------------------------------------------------------------------------
// FTiledMeshes

void FTiledMeshes::Init(TFunction<UStaticMeshComponent*()> InMake, TArray<TObjectPtr<UPrimitiveComponent>>* InHolder, const Sailing::FObjectRing& InRing, double TileM)
{
	Reset();
	MakeComponent = MoveTemp(InMake);
	Holder = InHolder;
	Ring = InRing;
	Cells = Sailing::FObjectCells(TileM);
	Tiles.Reset();
	WantedFlags.clear();
	Answers = MakeShared<FAnswers>();
}

void FTiledMeshes::Add(const FVector2D& Center, const FString& ObjectPath)
{
	const int32 Cell = Cells.Add(Center.X, Center.Y);
	if (Cell >= Tiles.Num())
	{
		Tiles.SetNum(Cell + 1);
		WantedFlags.resize(size_t(Cell) + 1, 0);
	}
	Tiles[Cell].Path = ObjectPath;
}

void FTiledMeshes::Reset()
{
	// Answers still on their way go to the old state, which nobody reads.
	Answers = MakeShared<FAnswers>();
	Waiting.Reset();
	for (int32 T = 0; T < Tiles.Num(); ++T) if (Tiles[T].State == 2) Drop(T);
	for (FTile& T : Tiles) { T.State = 0; ++T.Ask; }
	std::fill(WantedFlags.begin(), WantedFlags.end(), uint8_t(0));
	PlannedAt = FVector2D(1e12, 1e12);
	Pending = 0;
}

void FTiledMeshes::Request(int32 Tile)
{
	FTile& T = Tiles[Tile];
	T.State = 1;
	const uint32 Ask = ++T.Ask;
	const FString Package = FPackageName::ObjectPathToPackageName(T.Path);
	// The callback runs on the game thread when the package is in; it only notes the mesh (the answers outlive this).
	TSharedPtr<FAnswers> A = Answers;
	LoadPackageAsync(Package, FLoadPackageAsyncDelegate::CreateLambda([A, Tile, Ask](const FName&, UPackage* Loaded, EAsyncLoadingResult::Type Result)
	{
		UStaticMesh* Mesh = Loaded && Result == EAsyncLoadingResult::Succeeded ? FindObject<UStaticMesh>(Loaded, *FPackageName::GetShortName(Loaded)) : nullptr;
		A->Arrived.Emplace(Tile, Ask, TStrongObjectPtr<UStaticMesh>(Mesh));
	}));
}

bool FTiledMeshes::Draw(int32 Tile, UStaticMesh* Mesh)
{
	// Uncooked with a cold DDC the mesh can still be building; registering it then asserts on its render data (as the far
	// ring found): not yet.
	FStaticMeshRenderData* RenderData = Mesh->IsCompiling() ? nullptr : Mesh->GetRenderData();
	if (!RenderData || !RenderData->IsInitialized()) return false;
	bool bReused = false;
	const int32 Slot = Pool.Acquire(bReused);
	if (Slot >= Slots.Num()) Slots.SetNum(Slot + 1);
	UStaticMeshComponent* C = Slots[Slot].Get();
	if (!C && MakeComponent)
	{
		C = MakeComponent();
		if (C && Holder) Holder->Add(C);
		Slots[Slot] = C;
	}
	if (!C) { Pool.Release(Slot); return true; }
	// A registered Static mesh refuses a new mesh after play has begun, so the component is out of the scene while it changes.
	if (C->IsRegistered()) C->UnregisterComponent();
	C->SetStaticMesh(Mesh);
	C->RegisterComponent();
	Tiles[Tile].Slot = Slot;
	Tiles[Tile].State = 2;
	++Made;
	return true;
}

void FTiledMeshes::Drop(int32 Tile)
{
	FTile& T = Tiles[Tile];
	if (T.State == 2 && Slots.IsValidIndex(T.Slot))
	{
		// The component lets go of the mesh (nothing else holds a baked tile, so the engine frees it) and waits in the pool.
		if (UStaticMeshComponent* C = Slots[T.Slot].Get())
		{
			if (C->IsRegistered()) C->UnregisterComponent();
			C->SetStaticMesh(nullptr);
		}
		Pool.Release(T.Slot);
		++Dropped;
	}
	T.Slot = INDEX_NONE;
	T.State = 0;
	++T.Ask;   // an answer still on its way is ignored
}

void FTiledMeshes::Start(const FVector2D& Camera)
{
	std::vector<int> Make, DropList;
	Sailing::PlanObjectCells(Cells, WantedFlags, Camera.X, Camera.Y, Ring, -1, Make, DropList);
	for (const int T : Make)
	{
		WantedFlags[size_t(T)] = 1;
		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Tiles[T].Path);
		if (!Mesh) { ++Failed; Tiles[T].State = 3; continue; }   // 3: wanted, but there is no mesh
		if (!Draw(T, Mesh)) { Tiles[T].State = 1; Waiting.Emplace(T, Tiles[T].Ask, TStrongObjectPtr<UStaticMesh>(Mesh)); }
	}
	PlannedAt = Camera;
	Pending = Waiting.Num();
}

int32 FTiledMeshes::Update(const FVector2D& Camera, int32 MaxAdds)
{
	if (!Answers.IsValid()) return 0;
	// What arrived since the last frame (answers to an older ask of a tile are dropped with their mesh).
	for (TTuple<int32, uint32, TStrongObjectPtr<UStaticMesh>>& A : Answers->Arrived)
	{
		const int32 T = A.Get<0>();
		if (!Tiles.IsValidIndex(T) || Tiles[T].State != 1 || Tiles[T].Ask != A.Get<1>()) continue;
		if (!A.Get<2>().IsValid()) { ++Failed; Tiles[T].State = 3; continue; }
		Waiting.Add(MoveTemp(A));
	}
	const bool bArrived = Answers->Arrived.Num() > 0;
	Answers->Arrived.Reset();
	int32 Added = 0;
	for (int32 I = 0; I < Waiting.Num() && Added < MaxAdds;)
	{
		const int32 T = Waiting[I].Get<0>();
		if (Tiles[T].State != 1 || Tiles[T].Ask != Waiting[I].Get<1>()) { Waiting.RemoveAtSwap(I); continue; }
		if (!Draw(T, Waiting[I].Get<2>().Get())) { ++I; continue; }
		Waiting.RemoveAtSwap(I);
		++Added;
	}
	// The ring, planned again after 250 m.
	const bool bPlan = FVector2D::Distance(Camera, PlannedAt) >= 250.0;
	if (bPlan)
	{
		PlannedAt = Camera;
		std::vector<int> Make, DropList;
		Sailing::PlanObjectCells(Cells, WantedFlags, Camera.X, Camera.Y, Ring, -1, Make, DropList);
		for (const int T : DropList) { WantedFlags[size_t(T)] = 0; Drop(T); }
		for (const int T : Make) { WantedFlags[size_t(T)] = 1; Request(T); }
	}
	if (bPlan || bArrived || Added > 0)
	{
		Pending = 0;
		for (const FTile& T : Tiles) Pending += T.State == 1;
	}
	return Pending;
}
