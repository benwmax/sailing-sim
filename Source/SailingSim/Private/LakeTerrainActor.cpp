#include "LakeTerrainActor.h"
#include "SailingFrame.h"
#include "WorldStreaming.h"
#include "BenchRunner.h"
#include "PerfScopes.h"
#include "UObject/UObjectIterator.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "LakeData.h"
#include "Marina.h"
#include "TreePlacement.h"
#include "WorldKit.h"
#include "FarRing.h"
#include "Components/StaticMeshComponent.h"
#include "Async/Async.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "Misc/PackageName.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

using namespace Sailing;

namespace
{
	// Cells per chunk side: 64, or 128 on grids of 10 m or coarser (Galveston Bay: 1,000 chunks instead of 4,000;
	// culling every chunk each frame cost 4 ms of render thread).
	int32 GChunkCells = 64;
	// Leaf-card trees within this; opaque crowns beyond (Visual V6). -SailingNearTrees=<m> to measure.
	double NearTreesM()
	{
		// Graphics G6: 250 m on High, 200 m on Medium (were 600 and 350). The lidar crowns put three times as many trees on
		// the shore, and leaf cards out to 600 m cost High 8 ms of base pass at the marina; past 250 m the smooth opaque
		// crowns read the same.
		static uint32 Gen = MAX_uint32;
		static double M = 0.0;
		if (Gen == SailingArgs::Generation()) return M;
		Gen = SailingArgs::Generation();
		M = []
		{
			double V = USailingSettings::Get()->Quality >= ESailingQuality::High ? 250.0 : 200.0;
			FParse::Value(SailingArgs::Dev(), TEXT("SailingNearTrees="), V);
			return V;
		}();
		return M;
	}
	// Graphics G6: the opaque crowns cast shadows out to this (m); beyond, none (the far crowns' virtual shadow pages cost
	// High 6.5 ms at the slip, and their shadows are lost at that range). -SailingMidTrees=<m> to measure.
	double MidTreesM()
	{
		static uint32 Gen = MAX_uint32;
		static double M = 0.0;
		if (Gen == SailingArgs::Generation()) return M;
		Gen = SailingArgs::Generation();
		M = []
		{
			double V = USailingSettings::Get()->Quality >= ESailingQuality::High ? 1000.0 : 600.0;
			FParse::Value(SailingArgs::Dev(), TEXT("SailingMidTrees="), V);
			return V;
		}();
		return M;
	}
	constexpr int32 kMaxBuildsInFlight = 4;
	// Graphics G2: chunks this close (m, to their nearest edge) with lidar detail are meshed at 1 m.
	constexpr double kFineTerrainM = 300.0;
	constexpr int32 kMaxUploadsPerFrame = 3;

	uint32 Hash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return X;
	}
	float Rand01(uint32 Seed) { return (Hash(Seed) & 0xFFFFFF) / float(0xFFFFFF); }

}

ALakeTerrainActor::ALakeTerrainActor()
{
	PrimaryActorTick.bCanEverTick = true;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Terrain(TEXT("/Game/Materials/M_Terrain.M_Terrain"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Shape(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	TerrainMaterial = Terrain.Object;
	ShapeMaterial = Shape.Object;
	// Wide World Rendering PR 1: the far coast ring's land (a hard reference: cooked with the game).
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> FarLand(TEXT("/Game/World/M_FarLand.M_FarLand"));
	FarMaterialBase = FarLand.Object;
}

const FLakeData* ALakeTerrainActor::GetLake() const
{
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	return GM && GM->GetLake().IsLoaded() ? &GM->GetLake() : nullptr;
}

void ALakeTerrainActor::SetTreeFraction(float Fraction)
{
	TreeFraction = FMath::Clamp(Fraction, 0.f, 1.f);
	if (bTreesPlaced)
	{
		for (UHierarchicalInstancedStaticMeshComponent* T : TreeMeshes) T->ClearInstances();
		for (UInstancedStaticMeshComponent* T : TreeModels) T->ClearInstances();
		for (UInstancedStaticMeshComponent* T : TreeFar) T->ClearInstances();
		for (UInstancedStaticMeshComponent* T : TreeMid) T->ClearInstances();
		PlaceTrees();
	}
}

void ALakeTerrainActor::BeginPlay()
{
	Super::BeginPlay();
	// The bed is hidden where the water (Single Layer Water, Visual V4) absorbs 99% of the light coming back from it:
	// about 2 m in the lake's and the bay's silt, 14 m offshore; with a metre to spare for the lake level and the tide.
	HideBelow = (USailingSettings::Get()->World == 2 || USailingSettings::Get()->World == 3) ? -15.0 : -3.5;   // the Gulf and the clear Mediterranean
	const FLakeData* Lake = GetLake();
	if (!Lake)
	{
		return;
	}
	// World streaming (docs/world-streaming): the chunks are made as the camera comes near them (UpdateChunkSet), by the
	// world's tile index, and dropped behind it.
	GChunkCells = ChunkCellsFor(Lake->Terrain.IsValid() ? Lake->Terrain.GetCell() : 10.0);
	// Wide World Rendering PR 1: the far coast ring, if the world has one (Galveston Bay and the Gulf; -SailingNoFarRing).
	if (FarLoader.Start(Lake->FileName)) UE_LOG(LogSailing, Display, TEXT("Far ring: loading %s's tiles"), *Lake->FileName);
	PlaceTrees();
	PlaceReeds();
	PlaceBuildings();
	PlaceBridgesAndDocks();
	bTreesPlaced = true;
	// The instanced meshes by count (the render thread culls every instance: the coast's visibility cost).
	{
		TMap<FString, int32> ByMesh;
		int64 Total = 0;
		TArray<UInstancedStaticMeshComponent*> Ism;
		GetComponents(Ism);
		for (const UInstancedStaticMeshComponent* I : Ism)
		{
			const FString Name = I->GetStaticMesh() ? I->GetStaticMesh()->GetName() : TEXT("-");
			ByMesh.FindOrAdd(Name) += I->GetInstanceCount();
			Total += I->GetInstanceCount();
		}
		ByMesh.ValueSort([](int32 A, int32 B) { return A > B; });
		FString Top;
		int32 K = 0;
		for (const TPair<FString, int32>& P : ByMesh) { if (K++ >= 12) break; Top += FString::Printf(TEXT(" %s %d;"), *P.Key, P.Value); }
		UE_LOG(LogSailing, Display, TEXT("Terrain instances: %lld in %d components:%s"), Total, Ism.Num(), *Top);
	}
}

void ALakeTerrainActor::EndPlay(const EEndPlayReason::Type Reason)
{
	for (TPair<FIntPoint, TUniquePtr<FChunk>>& P : Chunks)
	{
		if (P.Value->bBuilding) P.Value->Future.Wait();
	}
	if (TreeTileJobTile != INDEX_NONE) TreeTileJob.Wait();
	FarLoader.Reset();
	FarArrived.Reset();
	Super::EndPlay(Reason);
}

ALakeTerrainActor::FChunkMesh ALakeTerrainActor::BuildChunk(const FChunkSource& Src, int32 Step, double HideBelow)
{
	// Runs on a worker thread: reads only its copy of the terrain and the tile (immutable).
	FChunkMesh M;
	const FLakeTerrain& T = Src.Terrain;
	if (!T.IsValid() && !Src.Tile) return M;
	// Graphics G2: Step 0 is the near level on the shore: the chunk meshed at the 1 m lidar detail's spacing (HeightAt
	// takes the detail where a tile covers the point and the grid elsewhere in the chunk).
	const bool bFine = Step == 0;
	const double Cell = bFine ? T.GetDetailCell() : Src.Cell;
	const int32 Sub = bFine ? FMath::Max(1, FMath::RoundToInt(Src.Cell / Cell)) : 1;
	if (bFine) Step = 1;
	const int32 N = Src.Cells * Sub / Step;
	// Node (R, C) of the chunk, counted from its corner on the chunk's spacing (Sub nodes a cell at the fine level).
	const double OX = Src.OriginX, OY = Src.OriginY;
	const FTerrainTile* Tile = Src.Tile.get();
	const double Level = T.GetLevelBelowPool();
	auto H = [&](int32 R, int32 C) -> double
	{
		if (bFine) return T.HeightAt(OX + R * Cell, OY + C * Cell);
		if (Tile)
		{
			// World streaming: the tile's own nodes; past its edge (a normal's neighbour) the terrain's, from the next tile.
			const int32 TR = Src.TileRow0 + R, TC = Src.TileCol0 + C;
			if (TR >= 0 && TC >= 0 && TR <= Tile->Cells && TC <= Tile->Cells) return Tile->Node(TR, TC) + Level;
			return T.HeightAt(OX + R * Cell, OY + C * Cell);
		}
		return T.NodeHeight(Src.GridRow0 + R, Src.GridCol0 + C);   // a whole grid (clamped at its edge)
	};
	// A whole grid's last chunk may run past its last node: those nodes repeat the edge, as NodeHeight clamps.
	const int32 MaxR = Tile ? N * Step : ((T.GetRows() - 1) - Src.GridRow0) * Sub, MaxC = Tile ? N * Step : ((T.GetCols() - 1) - Src.GridCol0) * Sub;
	const int32 GridR0 = (Tile ? Tile->Row * Tile->Cells + Src.TileRow0 : Src.GridRow0) * Sub;
	const int32 GridC0 = (Tile ? Tile->Col * Tile->Cells + Src.TileCol0 : Src.GridCol0) * Sub;

	M.Vertices.Reserve((N + 1) * (N + 1) + 4 * (N + 1));
	for (int32 I = 0; I <= N; ++I)
	{
		for (int32 J = 0; J <= N; ++J)
		{
			const int32 R = FMath::Min(I * Step, MaxR), C = FMath::Min(J * Step, MaxC);
			const double Z = H(R, C);
			M.Vertices.Add(FVector(OX + R * Cell, OY + C * Cell, Z) * CmPerMeter);
			const double DZX = (H(R + Step, C) - H(R - Step, C)) / (2.0 * Step * Cell);
			const double DZY = (H(R, C + Step) - H(R, C - Step)) / (2.0 * Step * Cell);
			const FVector Nrm = FVector(-DZX, -DZY, 1.0).GetSafeNormal();
			M.Normals.Add(Nrm);
			// Texas cross-timbers colors: muddy lake bed, red-brown clay and sand at the waterline, rock on steep
			// banks, dry grass above, darker under woods.
			const double Slope = 1.0 - Nrm.Z;
			const double Canopy = T.CanopyAt(OX + R * Cell, OY + C * Cell) / 12.0;
			const int32 GR = (GridR0 + R) / Sub, GC = (GridC0 + C) / Sub; // the colour noise stays on the grid's cells at every level
			const float Noise = 0.9f + 0.2f * Rand01(uint32(GR * 7919 + GC * 104729));
			// Graphics G6: how close open water is (1 at the edge, 0 past 14 m): the bare clay and sand band and the
			// material's wet band (alpha) are the waterline's, not every low flat's. A cove's head a few decimetres above
			// the pool read as a glossy mud plain hundreds of metres across from the drone.
			float Near = Z < -0.3 ? 1.f : 0.f;
			if (Z >= -0.3 && Z < 1.5)
			{
				const double X = OX + R * Cell, Y = OY + C * Cell;
				static const double Radii[] = { 4.0, 8.0, 14.0 };
				static const float Weights[] = { 1.f, 0.6f, 0.25f };
				for (int32 K = 0; K < 3 && Near == 0.f; ++K)
				{
					for (int32 A = 0; A < 8; ++A)
					{
						const double Ang = A * UE_DOUBLE_PI / 4.0;
						if (T.HeightAt(X + Radii[K] * FMath::Cos(Ang), Y + Radii[K] * FMath::Sin(Ang)) < -0.05) { Near = Weights[K]; break; }
					}
				}
			}
			FLinearColor Col;
			if (Z < -0.3) Col = FLinearColor(0.20f, 0.17f, 0.12f);
			else if (Z < 0.6)
			{
				// Low ground back from the edge: sedge and lush grass (the lake's flats grow over).
				const FLinearColor Bank = FMath::Lerp(FLinearColor(0.42f, 0.30f, 0.20f), FLinearColor(0.50f, 0.42f, 0.30f), float(Rand01(uint32(GR * 31 + GC * 17))));
				Col = FMath::Lerp(FLinearColor(0.24f, 0.28f, 0.12f), Bank, Near);
			}
			else Col = FMath::Lerp(FLinearColor(0.36f, 0.36f, 0.16f), FLinearColor(0.16f, 0.22f, 0.08f), float(Canopy));
			if (Slope > 0.08) Col = FMath::Lerp(Col, FLinearColor(0.40f, 0.33f, 0.27f), float(FMath::Clamp((Slope - 0.08) * 6.0, 0.0, 1.0)));
			Col = Col * Noise;
			Col.A = Near;
			M.Colors.Add(Col);
		}
	}
	for (int32 I = 0; I < N; ++I)
	{
		for (int32 J = 0; J < N; ++J)
		{
			const int32 V0 = I * (N + 1) + J, V1 = V0 + 1, V2 = V0 + N + 1, V3 = V2 + 1;
			// The bed deeper than light comes back from is left out: nobody sees it through the water, and drawn it
			// costs shading and shadow pages behind the Single Layer Water.
			const double Hide = HideBelow * CmPerMeter;
			if (M.Vertices[V0].Z < Hide && M.Vertices[V1].Z < Hide && M.Vertices[V2].Z < Hide && M.Vertices[V3].Z < Hide) continue;
			M.Triangles.Append({ V0, V1, V2, V1, V3, V2 });
		}
	}
	// Skirts hide cracks between chunks at different levels of detail.
	auto AddSkirt = [&](int32 A, int32 B, bool bFlip)
	{
		// Copy first: adding an element of an array to itself can reallocate under the reference.
		const FVector VA = M.Vertices[A], VB = M.Vertices[B], NA = M.Normals[A], NB = M.Normals[B];
		if (VA.Z < HideBelow * CmPerMeter && VB.Z < HideBelow * CmPerMeter) return;
		const FLinearColor CA = M.Colors[A], CB = M.Colors[B];
		const int32 SA = M.Vertices.Add(VA - FVector(0, 0, 400.0));
		M.Normals.Add(NA); M.Colors.Add(CA);
		const int32 SB = M.Vertices.Add(VB - FVector(0, 0, 400.0));
		M.Normals.Add(NB); M.Colors.Add(CB);
		if (bFlip) M.Triangles.Append({ A, SA, B, B, SA, SB, A, B, SA, B, SB, SA });
		else M.Triangles.Append({ A, B, SA, B, SB, SA, A, SA, B, B, SA, SB });
	};
	for (int32 K = 0; K < N; ++K)
	{
		AddSkirt(K, K + 1, false);
		AddSkirt(N * (N + 1) + K, N * (N + 1) + K + 1, true);
		AddSkirt(K * (N + 1), (K + 1) * (N + 1), true);
		AddSkirt(K * (N + 1) + N, (K + 1) * (N + 1) + N, false);
	}
	return M;
}

FTransform ALakeTerrainActor::TreeTransform(const FTreeInstance& I, bool bNear, const FVector2D& Camera, FTransform* OutProxy) const
{
	const int32 Index = int32(I.Species) * 2 + I.Variant;
	UStaticMesh* Mesh = (bNear ? TreeModels : TreeFar)[Index]->GetStaticMesh();
	const float MeshHeight = Mesh ? FMath::Max(100.f, float(Mesh->GetBounds().BoxExtent.Z * 2.0)) : 1000.f;
	const float Scale = I.Height * CmPerMeter / MeshHeight;
	// Graphics G6: a lidar crown's own width (about 0.85 of the model's half-extent is its crown's equal-area radius),
	// kept within a believable stretch of the model's proportions.
	float ScaleXY = Scale;
	if (I.Crown > 0.f && Mesh)
	{
		const float MeshRadius = FMath::Max(50.f, 0.85f * float(FMath::Max(Mesh->GetBounds().BoxExtent.X, Mesh->GetBounds().BoxExtent.Y)));
		ScaleXY = FMath::Clamp(I.Crown * CmPerMeter / MeshRadius, 0.8f * Scale, 1.3f * Scale);
	}
	// The earth's curvature (as M_Terrain's offset does for the ground): far trees sink with the shore they stand on.
	const double Drop = CurvatureDrop(FVector2D::Distance(I.Position, Camera));
	// T1: each tree's own look and a small lean (FTreeLook, from its position: the same after every regroup).
	const FTreeLook Look = bTreeLooks ? TreeLookFor(I) : FTreeLook();
	const FVector At(I.Position.X * CmPerMeter, I.Position.Y * CmPerMeter, (I.Ground - Drop) * CmPerMeter);
	const FRotator Rot(bTreeLean ? Look.LeanPitch : 0.f, I.Yaw, bTreeLean ? Look.LeanRoll : 0.f);
	// The lighting-only crown under a near tree, sized as the far crown would be for this tree, 85% of it.
	if (OutProxy)
	{
		UStaticMesh* FarMesh = TreeFar[Index]->GetStaticMesh();
		const float FarHeight = FarMesh ? FMath::Max(100.f, float(FarMesh->GetBounds().BoxExtent.Z * 2.0)) : MeshHeight;
		const float K = 0.85f * MeshHeight / FarHeight;
		*OutProxy = FTransform(Rot, At, FVector(ScaleXY * K, ScaleXY * K, Scale * K));
	}
	return FTransform(Rot, At, FVector(ScaleXY, ScaleXY, Scale));
}

int32 ALakeTerrainActor::TileComponent(int32 Tile, uint8 Band, int32 Model)
{
	const int32 Key = (Tile * 4 + Band) * TreeModels.Num() + Model;
	if (const int32* Found = TileComps.Find(Key)) return *Found;
	// A clone of the band's template component (TreeMid / TreeFar: mesh, lighting, shadow, cull and custom-data settings).
	UInstancedStaticMeshComponent* Template = Band == 2 ? TreeMid[Model].Get() : TreeFar[Model].Get();
	UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this, NAME_None, RF_NoFlags, Template);
	C->ClearInstances();
	C->SetupAttachment(RootComponent);
	C->SetRemoveSwap();
	// Bounds far past r.SceneCulling.MaxCellSize (10.5 km), as the lake-wide band components had: the renderer then
	// leaves the tile's crowns out of its culling hierarchy and culls them per instance on the GPU. Hashed into the
	// hierarchy, the tiles' 294,000 crowns cost the render thread 0.3 ms a frame (SceneCulling_Update_FinalizeAndClear on
	// the 4090) with the GPU no faster. A tile can hold a single tree, hence the large scale.
	C->SetBoundsScale(2000.f);
	C->RegisterComponent();
	const int32 Id = TreeComps.Add(C);
	CompTrees.AddDefaulted();
	CompPlacedAt.Add(FVector2D::ZeroVector);
	TileComps.Add(Key, Id);
	return Id;
}

void ALakeTerrainActor::UpdateModelTrees(const FVector2D& Camera)
{
	if (TreeModels.Num() == 0 || ModelTrees.Num() == 0) return;
	// A tile component placed from more than 2 km away gets fresh transforms, one component a frame: the far trees keep
	// the curvature drop they were placed with, which drifts by a pixel at the far crowns' range after a few km.
	if (TreeBand.Num() == ModelTrees.Num() && TreeComps.Num() > TreeModels.Num())
	{
		for (int32 Tries = 0; Tries < 64; ++Tries)
		{
			DriftCursor = (DriftCursor + 1) % (TreeComps.Num() - TreeModels.Num());
			const int32 Id = TreeModels.Num() + DriftCursor;
			if (FVector2D::Distance(CompPlacedAt[Id], Camera) < 2000.0 || CompTrees[Id].Num() == 0) continue;
			TArray<FTransform> X;
			X.Reserve(CompTrees[Id].Num());
			for (const int32 T : CompTrees[Id]) X.Add(TreeTransform(ModelTrees[T], false, Camera, nullptr));
			TreeComps[Id]->BatchUpdateInstancesTransforms(0, SailingFrame::ToWorldTransforms(GetWorld(), X), true, false, true);   // a teleport: static instances keep no previous transforms
			CompPlacedAt[Id] = Camera;
			break;
		}
	}
	// Visual V6: leaf-card trees near the camera (alpha-masked Nanite is costly over many pixels), the opaque far
	// crowns beyond; regrouped when the camera has moved a quarter of the near radius.
	if (FVector2D::Distance(Camera, TreeCenter) < FMath::Max(100.0, 0.25 * NearTreesM())) return;
	TreeCenter = Camera;
	// T1 follow-up (the D3D12 regroup traces): clearing and re-adding every tree at each regroup made it a 210 ms frame
	// on the 4090, 80 ms of game thread and 116 ms of the renderer re-adding every mid and far crown to the distance-field
	// scene. Now only the trees that cross a band's edge move, and only their tiles' components change.
	if (TreeBand.Num() != ModelTrees.Num())
	{
		for (UInstancedStaticMeshComponent* C : TreeComps) if (C) C->ClearInstances();
		for (UInstancedStaticMeshComponent* C : TreeProxy) C->ClearInstances();
		const TArray<TObjectPtr<UInstancedStaticMeshComponent>> Keep = TreeComps;
		TreeComps.Reset();
		CompTrees.Reset();
		CompPlacedAt.Reset();
		for (UInstancedStaticMeshComponent* C : TreeModels)
		{
			C->SetRemoveSwap();
			TreeComps.Add(C);
			CompTrees.AddDefaulted();
			CompPlacedAt.Add(Camera);
		}
		for (UInstancedStaticMeshComponent* C : TreeProxy) C->SetRemoveSwap();
		// The tile components of a placement before (SetTreeFraction) go; the tiles are made again as trees enter them.
		for (const TPair<int32, int32>& P : TileComps) if (Keep.IsValidIndex(P.Value) && Keep[P.Value]) Keep[P.Value]->DestroyComponent();
		TileComps.Reset();
		TreeTileIds.Reset();
		TreeTile.SetNumUninitialized(ModelTrees.Num());
		for (int32 T = 0; T < ModelTrees.Num(); ++T)
		{
			const FIntPoint Cell(FMath::FloorToInt32(ModelTrees[T].Position.X / kTreeTileM), FMath::FloorToInt32(ModelTrees[T].Position.Y / kTreeTileM));
			const int32* Found = TreeTileIds.Find(Cell);
			TreeTile[T] = Found ? *Found : TreeTileIds.Add(Cell, TreeTileIds.Num());
		}
		TreeBand.Init(0, ModelTrees.Num());
		TreeComp.Init(INDEX_NONE, ModelTrees.Num());
		TreeSlot.Init(INDEX_NONE, ModelTrees.Num());
	}
	// The trees leaving their component, then the ones entering one.
	const double R2 = FMath::Square(NearTreesM()), RM2 = FMath::Square(MidTreesM());
	// World streaming: on a streamed world the trees past the far crowns' cull (9 km) leave the components altogether
	// (band 0), so a long coast's trees do not pile up in them.
	const FWorldStreamer* St = GetStreamer();
	const double RF2 = St && St->IsStreamed() ? FMath::Square(9500.0) : 1e300;
	TArray<int32> Movers;
	TArray<uint8> NewBands;
	for (int32 T = 0; T < ModelTrees.Num(); ++T)
	{
		const double D2 = FVector2D::DistSquared(ModelTrees[T].Position, Camera);
		const uint8 Band = D2 < R2 ? 1 : (D2 < RM2 && TreeMid.Num() > 0 ? 2 : (D2 < RF2 ? 3 : 0));
		if (Band != TreeBand[T]) { Movers.Add(T); NewBands.Add(Band); }
	}
	for (const int32 T : Movers)
	{
		const int32 Id = TreeComp[T];
		if (Id == INDEX_NONE) continue;
		TArray<int32>& S = CompTrees[Id];
		const int32 Slot = TreeSlot[T], Last = S.Num() - 1;
		TreeComps[Id]->RemoveInstance(Slot);
		// The near proxies mirror the leaf cards instance for instance, so they swap the same way.
		if (Id < TreeModels.Num() && TreeProxy.IsValidIndex(Id)) TreeProxy[Id]->RemoveInstance(Slot);
		if (Slot != Last) { S[Slot] = S[Last]; TreeSlot[S[Slot]] = Slot; }
		S.Pop(EAllowShrinking::No);
		TreeComp[T] = INDEX_NONE;
		TreeSlot[T] = INDEX_NONE;
	}
	// The entering trees go on the end of their component (one batch each), their custom data after them as one range:
	// both are queued through the instance data manager, no scene-proxy rebuild.
	struct FAdds { TArray<FTransform> X, Proxy; TArray<float> D; TArray<int32> Trees; };
	TMap<int32, FAdds> Adds;
	for (int32 Mv = 0; Mv < Movers.Num(); ++Mv)
	{
		const int32 T = Movers[Mv];
		const FTreeInstance& I = ModelTrees[T];
		const int32 Model = int32(I.Species) * 2 + I.Variant;
		const bool bNear = NewBands[Mv] == 1;
		TreeBand[T] = NewBands[Mv];
		if (NewBands[Mv] == 0) continue;   // out of reach: in no component
		const int32 Id = bNear ? Model : TileComponent(TreeTile[T], NewBands[Mv], Model);
		FAdds& A = Adds.FindOrAdd(Id);
		FTransform Proxy;
		const bool bProxy = bNear && TreeProxy.IsValidIndex(Model);
		A.X.Add(TreeTransform(I, bNear, Camera, bProxy ? &Proxy : nullptr));
		if (bProxy) A.Proxy.Add(Proxy);
		const FTreeLook Look = bTreeLooks ? TreeLookFor(I) : FTreeLook();
		A.D.Append({ Look.Tint, Look.Deciduous, Look.AutumnHue });
		A.Trees.Add(T);
	}
	for (TPair<int32, FAdds>& P : Adds)
	{
		UInstancedStaticMeshComponent* C = TreeComps[P.Key];
		FAdds& A = P.Value;
		SailingFrame::ToWorldTransforms(GetWorld(), A.X);   // made in the map frame; added in world space
		SailingFrame::ToWorldTransforms(GetWorld(), A.Proxy);
		const int32 First = C->GetInstanceCount();
		C->AddInstances(A.X, false, true);
		if (bTreeLooks && C->NumCustomDataFloats >= 3) C->SetCustomData(First, First + A.X.Num() - 1, TConstArrayView<float>(A.D), false);
		if (A.Proxy.Num() > 0) TreeProxy[P.Key]->AddInstances(A.Proxy, false, true);
		for (int32 K = 0; K < A.Trees.Num(); ++K) { TreeComp[A.Trees[K]] = P.Key; TreeSlot[A.Trees[K]] = First + K; CompTrees[P.Key].Add(A.Trees[K]); }
		if (C->GetInstanceCount() == A.X.Num()) CompPlacedAt[P.Key] = Camera;
	}
	if (Adds.Num() > 64) UE_LOG(LogSailing, Display, TEXT("Trees: %d components (%d tiles)"), TreeComps.Num(), TileComps.Num());
}

void ALakeTerrainActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	SAILING_PERF_SCOPE(Terrain);
	// Once, 8 s in: every instanced mesh in the world by owner and mesh (the render thread culls each instance).
	if (!bLoggedInstances && GetWorld()->GetTimeSeconds() > 8.0)
	{
		bLoggedInstances = true;
		TMap<FString, int64> By;
		int64 Total = 0;
		for (TObjectIterator<UInstancedStaticMeshComponent> It; It; ++It)
		{
			if (It->GetWorld() != GetWorld() || !It->IsRegistered()) continue;
			const FString Key = FString::Printf(TEXT("%s/%s"), It->GetOwner() ? *It->GetOwner()->GetClass()->GetName() : TEXT("-"), It->GetStaticMesh() ? *It->GetStaticMesh()->GetName() : TEXT("-"));
			By.FindOrAdd(Key) += It->GetInstanceCount();
			Total += It->GetInstanceCount();
		}
		By.ValueSort([](int64 A, int64 B) { return A > B; });
		FString Top;
		int32 K = 0;
		for (const TPair<FString, int64>& P : By) { if (K++ >= 16) break; Top += FString::Printf(TEXT(" %s %lld;"), *P.Key, P.Value); }
		UE_LOG(LogSailing, Display, TEXT("World instances: %lld:%s"), Total, *Top);
	}
	const FLakeData* Lake = GetLake();
	if (!Lake) return;

	FVector Cam = FVector::ZeroVector;
	if (APlayerCameraManager* CM = UGameplayStatics::GetPlayerCameraManager(this, 0)) Cam = CM->GetCameraLocation();
	// World streaming: the camera in the map frame (the render origin moves; the world's data does not).
	const FVector2D CamMap = SailingFrame::ToMap(GetWorld(), Cam);
	const double CamX = CamMap.X, CamY = CamMap.Y;
	{ SAILING_PERF_SCOPE(Trees); UpdateTreeTiles(CamMap); UpdateModelTrees(CamMap); }
	UpdateFarRing(CamMap);   // inside the Terrain slice

	// Perf 1 fix 7: a chunk's wanted detail changes only as the camera moves, so look again after 20 m or half a second
	// (every frame while chunks are queued or building).
	const double Now = FPlatformTime::Seconds();
	const bool bLook = Pending > 0 || Building > 0 || FVector2D::Distance(CamMap, LodCamera) > 20.0 || Now - LodTime > 0.5;
	if (bLook)
	{
		LodCamera = CamMap;
		LodTime = Now;
		const int32 Unmade = UpdateChunkSet(*Lake, CamX, CamY);
		// Wanted level of detail by distance to the camera; queue the closest chunks first.
		TArray<FChunk*> Order;
		Pending = Unmade;
		int32 InFlight = 0;
		for (TPair<FIntPoint, TUniquePtr<FChunk>>& P : Chunks)
		{
			FChunk& Ch = *P.Value;
			const double Size = Ch.Cells * Ch.Cell;
			const double CX = Ch.OriginX + 0.5 * Size, CY = Ch.OriginY + 0.5 * Size;
			const double D = FMath::Max(0.0, FVector2D::Distance(FVector2D(CX, CY), CamMap) - 0.5 * Size);
			// Wide World Rendering PR 1: past the cap (the far ring's inner edge, or 20 km) a chunk is out of the scene
			// altogether, not only culled (world streaming: past it by a margin, dropped).
			const bool bDrawn = FarRing::NearChunkDrawn(D, NearCapM);
			if (Ch.Mesh->GetVisibleFlag() != bDrawn) Ch.Mesh->SetVisibility(bDrawn);
			if (!bDrawn) { InFlight += Ch.bBuilding; continue; }
			// Steps of the 5 and 10 m grids by distance; a coarse tile (50 m offshore) is meshed at its own spacing.
			Ch.Wanted = Ch.Cell >= 20.0 ? 1 : (D < 900.0 ? 1 : (D < 2200.0 ? 2 : (D < 5000.0 ? 4 : 8)));
			// Graphics G2: the 1 m lidar mesh on the shore near the camera (Step 0), where the chunk has detail tiles.
			if (D < kFineTerrainM && Ch.bHasDetail) Ch.Wanted = 0;
			Ch.bShadow = D < 2200.0;
			if (Ch.bBuilding) ++InFlight;
			if (Ch.Lod != Ch.Wanted && !Ch.bBuilding) { Order.Add(&Ch); ++Pending; }
		}
		Order.Sort([](const FChunk& A, const FChunk& B)
		{
			// Unbuilt chunks first (so the whole lake appears quickly at low detail), then nearest.
			const bool BuiltA = A.Lod >= 0, BuiltB = B.Lod >= 0;
			if (BuiltA != BuiltB) return !BuiltA;
			return A.Wanted < B.Wanted;
		});
		for (FChunk* ChP : Order)
		{
			if (InFlight >= kMaxBuildsInFlight) break;
			FChunk& Ch = *ChP;
			FChunkSource Src;
			Src.Terrain = Lake->Terrain;   // a copy: shares the heights, keeps the tiles it saw
			if (const FWorldStreamer* St = GetStreamer(); St && St->IsStreamed())
			{
				Src.Tile = St->GetTile(Ch.Tile);
				if (!Src.Tile) continue;   // dropped meanwhile
				const Sailing::FTileEntry& E = St->GetIndex().GetTiles()[Ch.Tile];
				Src.TileRow0 = Ch.Row * Ch.Cells - E.Row * E.Cells;
				Src.TileCol0 = Ch.Col * Ch.Cells - E.Col * E.Cells;
			}
			else
			{
				Src.GridRow0 = FMath::RoundToInt32((Ch.OriginX - Lake->Terrain.GetOriginX()) / Ch.Cell);
				Src.GridCol0 = FMath::RoundToInt32((Ch.OriginY - Lake->Terrain.GetOriginY()) / Ch.Cell);
			}
			Src.OriginX = Ch.OriginX;
			Src.OriginY = Ch.OriginY;
			Src.Cell = Ch.Cell;
			Src.Cells = Ch.Cells;
			Ch.bBuilding = true;
			const int32 Step = Ch.Wanted;
			Ch.Lod = -2 - Step; // marks the step being built
			const double Hide = HideBelow;
			Ch.Future = Async(EAsyncExecution::ThreadPool, [Src = MoveTemp(Src), Step, Hide]() { return BuildChunk(Src, Step, Hide); });
			++InFlight;
		}
		Building = InFlight;
	}
	if (Building == 0) return;

	// Upload finished chunks, a few per frame.
	int32 Uploads = 0;
	for (TPair<FIntPoint, TUniquePtr<FChunk>>& P : Chunks)
	{
		FChunk& Ch = *P.Value;
		if (!Ch.bBuilding || !Ch.Future.IsReady()) continue;
		if (Uploads++ >= kMaxUploadsPerFrame) break;
		// Consume moves the mesh out and frees the future's state: Get() copied it, and the future kept its own copy
		// until the chunk was rebuilt (a second 16 MB for a 1 m shore chunk; docs/budget/mac-soak-parked-2026-10-17.md).
		FChunkMesh M = Ch.Future.Consume();
		Ch.Mesh->ClearAllMeshSections();
		Ch.Mesh->CreateMeshSection_LinearColor(0, M.Vertices, M.Triangles, M.Normals, {}, M.Colors, {}, false);
		Ch.Lod = -2 - Ch.Lod;
		// Only chunks within about 2 km cast shadows: farther, the shadows are under a pixel but every chunk is a
		// draw in each cascade (facing the shore with Galveston Bay's 4,000 chunks cost 15 fps on the render thread).
		if (Ch.Mesh->CastShadow != Ch.bShadow) Ch.Mesh->SetCastShadow(Ch.bShadow);
		Ch.bBuilding = false;
		--Building;
	}
}

const FWorldStreamer* ALakeTerrainActor::GetStreamer() const
{
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	return GM && GM->GetStreamer().IsStarted() ? &GM->GetStreamer() : nullptr;
}

int32 ALakeTerrainActor::UpdateChunkSet(const FLakeData& Lake, double CamX, double CamY)
{
	const FWorldStreamer* St = GetStreamer();
	if (!St) return 0;
	const uint32 Gen = St->GetGeneration();
	// Again when the camera has moved a quarter of a chunk or the resident tiles changed.
	if (Gen == ChunkGeneration && FVector2D::Distance(FVector2D(CamX, CamY), ChunkCamera) < 300.0) return 0;
	ChunkGeneration = Gen;
	ChunkCamera = FVector2D(CamX, CamY);
	const Sailing::FTileIndex& Index = St->GetIndex();
	// Made within the cap and a chunk's diagonal; dropped past it and 2 km more (the gap keeps a chunk on the edge from
	// coming and going), or when its tile is no longer resident.
	const double MakeM = NearCapM + 1900.0, DropM = NearCapM + 4000.0;
	const FLakeTerrain& T = Lake.Terrain;
	int32 Made = 0, Unmade = 0;
	constexpr int32 kMaxMadePerLook = 24;   // components registered a look (a few hundred at the start, over a few frames)
	for (int32 K = 0; K < int32(Index.GetTiles().size()); ++K)
	{
		const Sailing::FTileEntry& E = Index.GetTiles()[K];
		if (!St->IsResident(K) || Index.DistanceTo(E, CamX, CamY) > MakeM) continue;
		const int32 Cells = FMath::Min(E.Cells, ChunkCellsFor(E.Cell));
		const int32 Per = FMath::Max(1, E.Cells / Cells);
		double TX0, TY0;
		Index.Corner(E, TX0, TY0);
		for (int32 SR = 0; SR < Per; ++SR)
			for (int32 SC = 0; SC < Per; ++SC)
			{
				const FIntPoint Key(E.Row * Per + SR, E.Col * Per + SC);
				if (Chunks.Contains(Key)) continue;
				const double OX = TX0 + SR * Cells * E.Cell, OY = TY0 + SC * Cells * E.Cell;
				// A whole grid's partial last tile: no chunk past the grid's last node.
				if (!St->IsStreamed() && (OX >= T.GetOriginX() + (T.GetRows() - 1) * E.Cell - 0.5 * E.Cell || OY >= T.GetOriginY() + (T.GetCols() - 1) * E.Cell - 0.5 * E.Cell)) continue;
				const double Size = Cells * E.Cell;
				const double D = FMath::Max(0.0, FVector2D::Distance(FVector2D(OX + 0.5 * Size, OY + 0.5 * Size), FVector2D(CamX, CamY)) - 0.5 * Size);
				if (D > MakeM || Made >= kMaxMadePerLook) { if (D <= MakeM) ++Unmade; continue; }
				TUniquePtr<FChunk> Ch = MakeUnique<FChunk>();
				Ch->Tile = K;
				Ch->Row = Key.X;
				Ch->Col = Key.Y;
				Ch->Cells = Cells;
				Ch->Cell = E.Cell;
				Ch->OriginX = OX;
				Ch->OriginY = OY;
				Ch->bHasDetail = T.HasDetailIn(OX, OY, OX + Size, OY + Size);
				UProceduralMeshComponent* Mesh = NewObject<UProceduralMeshComponent>(this);
				Mesh->SetupAttachment(RootComponent);
				Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				Mesh->bUseAsyncCooking = true;
				Mesh->RegisterComponent();
				Mesh->SetMaterial(0, TerrainMaterial);
				Mesh->SetCullDistance(20000.f * 100.f); // past 20 km the land is a sliver on the horizon, under the haze
				Ch->Mesh = Mesh;
				Chunks.Add(Key, MoveTemp(Ch));
				++Made;
				++ChunksMade;
			}
	}
	// Dropped: out of reach, or its tile gone.
	TArray<FIntPoint> Drop;
	for (TPair<FIntPoint, TUniquePtr<FChunk>>& P : Chunks)
	{
		const FChunk& Ch = *P.Value;
		const double Size = Ch.Cells * Ch.Cell;
		const double D = FMath::Max(0.0, FVector2D::Distance(FVector2D(Ch.OriginX + 0.5 * Size, Ch.OriginY + 0.5 * Size), FVector2D(CamX, CamY)) - 0.5 * Size);
		if (D > DropM || !St->IsResident(Ch.Tile)) Drop.Add(P.Key);
	}
	for (const FIntPoint& Key : Drop)
	{
		TUniquePtr<FChunk>& Ch = Chunks[Key];
		if (Ch->bBuilding) { Ch->Future.Wait(); --Building; }
		if (Ch->Mesh) Ch->Mesh->DestroyComponent();
		Chunks.Remove(Key);
		++ChunksDropped;
	}
	if (Made > 0 || Drop.Num() > 0)
	{
		UE_LOG(LogSailing, Verbose, TEXT("Terrain chunks: %d made, %d dropped, %d now"), Made, Drop.Num(), Chunks.Num());
	}
	if (Made >= kMaxMadePerLook) ChunkGeneration = 0;   // more to make: look again next time
	return Unmade;
}

int32 ALakeTerrainActor::GetFarTilesVisible() const
{
	int32 N = 0;
	for (const UStaticMeshComponent* C : FarTiles) N += C && C->GetVisibleFlag();
	return N;
}

void ALakeTerrainActor::UpdateFarRing(const FVector2D& Camera)
{
	FarLoader.Poll(Camera);
	const FFarRingData* Ring = FarLoader.Data();
	if (!Ring) return;
	if (FarTiles.Num() != Ring->Tiles.Num())
	{
		FarTiles.SetNum(Ring->Tiles.Num());
		if (FarMaterialBase)
		{
			const FLakeData* Lake = GetLake();
			const double ChunkM = Lake && Lake->Terrain.IsValid() ? GChunkCells * Lake->Terrain.GetCell() : 1280.0;
			FarMaterial = UMaterialInstanceDynamic::Create(FarMaterialBase, this);
			FarMaterial->SetScalarParameterValue(TEXT("InnerCm"), float(Ring->InnerM * CmPerMeter));
			FarMaterial->SetScalarParameterValue(TEXT("BandCm"), float(FarRing::BandEndM(Ring->InnerM, ChunkM) * CmPerMeter));
		}
	}
	// A few new tiles a frame (each is one static component; the meshes are already in memory).
	FarLoader.TakeArrived(FarArrived);
	int32 Added = 0;
	TArray<TPair<int32, UStaticMesh*>, TInlineAllocator<8>> NotReady;
	while (FarArrived.Num() > 0 && Added < 8)
	{
		const TPair<int32, UStaticMesh*> A = FarArrived.Pop(EAllowShrinking::No);
		if (!A.Value || !FarTiles.IsValidIndex(A.Key) || FarTiles[A.Key]) continue;
		// Uncooked with a cold DDC the mesh can still be building; registering it then asserts on its render data. Next frame.
		FStaticMeshRenderData* RenderData = A.Value->IsCompiling() ? nullptr : A.Value->GetRenderData();
		if (!RenderData || !RenderData->IsInitialized())
		{
			NotReady.Add(A);
			continue;
		}
		const FFarRingTile& Tile = Ring->Tiles[A.Key];
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetMobility(EComponentMobility::Static);
		C->SetupAttachment(RootComponent);
		C->SetRelativeLocation(FVector(Ring->TileOrigin(Tile) * CmPerMeter, 0.0));
		C->SetStaticMesh(A.Value);
		if (FarMaterial) C->SetMaterial(0, FarMaterial);
		// No shadows, not in the Lumen scene or the distance fields, not in ray tracing: at 8-40 km they are under the haze,
		// and each would cost shadow pages and scene updates.
		C->SetCastShadow(false);
		C->bAffectDistanceFieldLighting = false;
		C->bAffectDynamicIndirectLighting = false;
		C->bVisibleInRayTracing = false;
		C->bReceivesDecals = false;
		C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetVisibleFlag(FarRing::TileVisible(*Ring, Tile, Camera));
		C->RegisterComponent();
		FarTiles[A.Key] = C;
		++Added;
	}
	FarArrived.Append(NotReady);
	// The near chunks hand over once every tile is in (until then they draw to 20 km, so nothing goes missing).
	if (NearCapM != Ring->InnerM && FarLoader.IsDone() && FarArrived.Num() == 0)
	{
		NearCapM = Ring->InnerM;
		LodTime = -1e30;   // look at the chunks again now
		UE_LOG(LogSailing, Display, TEXT("Far ring: %d tiles in (%d failed), near terrain to %.0f km, longest game-thread call %.2f ms"),
			FarLoader.NumArrived(), FarLoader.NumFailed(), NearCapM / 1000.0, FarLoader.LongestCallMs());
	}
	// Tiles in or out of the band as the camera moves (whole tiles inside the burial or past the outer edge are left out);
	// world streaming: tiles past the loader's reach and another tile are dropped (and asked for again if it comes back).
	if (Added > 0 || FVector2D::Distance(Camera, FarCamera) > 250.0)
	{
		FarCamera = Camera;
		const double DropM = FarLoader.RequestM() + Ring->TileM;
		for (int32 K = 0; K < FarTiles.Num(); ++K)
		{
			UStaticMeshComponent* C = FarTiles[K];
			if (!C) continue;
			if (FarRing::TileDistance(*Ring, Ring->Tiles[K], Camera) > DropM)
			{
				C->DestroyComponent();
				FarTiles[K] = nullptr;
				FarLoader.Release(K);
				++FarDropped;
				continue;
			}
			const bool bShow = FarRing::TileVisible(*Ring, Ring->Tiles[K], Camera);
			if (C->GetVisibleFlag() != bShow) C->SetVisibility(bShow);
		}
	}
}

void ALakeTerrainActor::RemoveTreesInHouses(const FLakeData& Lake, TArray<FTreeInstance>& Trees)
{
	if (Lake.Houses.Num() == 0) return;
	constexpr double Cell = 50.0;
	TMap<FIntPoint, TArray<int32, TInlineAllocator<4>>> Grid;
	for (int32 K = 0; K < Lake.Houses.Num(); ++K)
	{
		const FLakeHouse& H = Lake.Houses[K];
		Grid.FindOrAdd(FIntPoint(FMath::FloorToInt32(H.X / Cell), FMath::FloorToInt32(H.Y / Cell))).Add(K);
	}
	Trees.RemoveAll([&](const FTreeInstance& I)
	{
		const FIntPoint C(FMath::FloorToInt32(I.Position.X / Cell), FMath::FloorToInt32(I.Position.Y / Cell));
		for (int32 Dx = -1; Dx <= 1; ++Dx) for (int32 Dy = -1; Dy <= 1; ++Dy)
		{
			const auto* List = Grid.Find(C + FIntPoint(Dx, Dy));
			if (!List) continue;
			for (const int32 K : *List)
			{
				for (const FLakeHouse::FWing& W : Lake.Houses[K].Wings)
				{
					const double Yaw = FMath::DegreesToRadians(W.YawDeg);
					const double Dx2 = I.Position.X - W.X, Dy2 = I.Position.Y - W.Y;
					const double A = Dx2 * FMath::Cos(Yaw) + Dy2 * FMath::Sin(Yaw), B = -Dx2 * FMath::Sin(Yaw) + Dy2 * FMath::Cos(Yaw);
					if (FMath::Abs(A) < W.HalfLength + 2.0 && FMath::Abs(B) < W.HalfWidth + 2.0) return true;
				}
			}
		}
		return false;
	});
}

void ALakeTerrainActor::UpdateTreeTiles(const FVector2D& Camera)
{
	// World streaming: the model trees of each tile as it becomes resident, placed on a worker one tile at a time (the
	// canopy map near the water, as PlaceTreeInstances does over a whole grid; none where the lidar crowns stand or in a
	// house), and added to the trees the bands draw.
	const FWorldStreamer* St = GetStreamer();
	const FLakeData* Lake = GetLake();
	if (!St || !St->IsStreamed() || !Lake || TreeModels.Num() == 0) return;
	if (TreeTileJobTile != INDEX_NONE)
	{
		if (!TreeTileJob.IsReady()) return;
		TArray<FTreeInstance> New = TreeTileJob.Consume();
		TreeTilesPlaced.Add(TreeTileJobTile);
		TreeTileJobTile = INDEX_NONE;
		if (New.Num() > 0 && TreeBand.Num() == ModelTrees.Num())
		{
			const int32 First = ModelTrees.Num();
			ModelTrees.Append(MoveTemp(New));
			TreeBand.SetNumZeroed(ModelTrees.Num());
			TreeComp.SetNum(ModelTrees.Num());
			TreeSlot.SetNum(ModelTrees.Num());
			TreeTile.SetNum(ModelTrees.Num());
			for (int32 T = First; T < ModelTrees.Num(); ++T)
			{
				TreeComp[T] = INDEX_NONE;
				TreeSlot[T] = INDEX_NONE;
				const FIntPoint Cell(FMath::FloorToInt32(ModelTrees[T].Position.X / kTreeTileM), FMath::FloorToInt32(ModelTrees[T].Position.Y / kTreeTileM));
				const int32* Found = TreeTileIds.Find(Cell);
				TreeTile[T] = Found ? *Found : TreeTileIds.Add(Cell, TreeTileIds.Num());
			}
			TreeCenter = FVector2D(1e12, 1e12);   // band them on the next regroup
		}
		else if (New.Num() > 0) ModelTrees.Append(MoveTemp(New));   // before the first regroup: banded with the rest
	}
	// The nearest resident tile not placed yet.
	const Sailing::FTileIndex& Index = St->GetIndex();
	int32 Next = INDEX_NONE;
	double Best = 1e300;
	for (int32 K = 0; K < int32(Index.GetTiles().size()); ++K)
	{
		if (!St->IsResident(K) || TreeTilesPlaced.Contains(K)) continue;
		const double D = Index.DistanceTo(Index.GetTiles()[K], Camera.X, Camera.Y);
		if (D < Best) { Best = D; Next = K; }
	}
	if (Next == INDEX_NONE) return;
	double X0, Y0;
	Index.Corner(Index.GetTiles()[Next], X0, Y0);
	const double TileM = Index.GetTileM();
	TreeTileJobTile = Next;
	TreeTileJob = Async(EAsyncExecution::ThreadPool, [Terrain = Lake->Terrain, Lake, X0, Y0, TileM, Fraction = TreeFraction, Band = CrownBand]()
	{
		TArray<FTreeInstance> Out;
		const FLakeTerrain Window = Terrain.WindowAround(X0 + 0.5 * TileM, Y0 + 0.5 * TileM, 0.5 * TileM);
		PlaceTreeInstances(Window, Fraction, Out);
		Out.RemoveAll([&](const FTreeInstance& I)
		{
			if (I.Position.X < X0 || I.Position.Y < Y0 || I.Position.X >= X0 + TileM || I.Position.Y >= Y0 + TileM) return true;
			return Band.IsValid() && Band->Contains(FIntPoint(FMath::FloorToInt32(I.Position.X / 100.0), FMath::FloorToInt32(I.Position.Y / 100.0)));
		});
		RemoveTreesInHouses(*Lake, Out);
		return Out;
	});
}

void ALakeTerrainActor::PlaceTrees()
{
	const FLakeData* Lake = GetLake();
	if (!Lake) return;
	const FLakeTerrain& T = Lake->Terrain;
	TArray<FTreeInstance> Trees;
	// Graphics G6: the lidar's crowns where the G2 band has them (-SailingClassicTrees compares).
	if (Lake->Crowns.Num() > 0 && !FParse::Param(SailingArgs::Dev(), TEXT("SailingClassicTrees"))) PlaceCrownTrees(T, Lake->Crowns, TreeFraction, Trees);
	else PlaceTreeInstances(T, TreeFraction, Trees);
	// Graphics G6: no tree inside a G2 house (the canopy grid only knew the OSM footprints).
	if (Lake->Houses.Num() > 0)
	{
		const int32 Before = Trees.Num();
		RemoveTreesInHouses(*Lake, Trees);
		UE_LOG(LogSailing, Display, TEXT("Trees: %d inside G2 houses removed"), Before - Trees.Num());
	}
	// World streaming: on a streamed world these are the trees of the tiles resident now; the others are placed as their
	// tiles arrive (UpdateTreeTiles).
	if (const FWorldStreamer* St = GetStreamer(); St && St->IsStreamed())
	{
		for (int32 K = 0; K < int32(St->GetIndex().GetTiles().size()); ++K) if (St->IsResident(K)) TreeTilesPlaced.Add(K);
		if (Lake->Crowns.Num() > 0 && !FParse::Param(SailingArgs::Dev(), TEXT("SailingClassicTrees")))
		{
			TSharedPtr<TSet<FIntPoint>> Band = MakeShared<TSet<FIntPoint>>();
			for (const FLakeCrown& C : Lake->Crowns)
			{
				const FIntPoint Cell(FMath::FloorToInt32(C.X / 100.f), FMath::FloorToInt32(C.Y / 100.f));
				for (int32 Dx = -2; Dx <= 2; ++Dx) for (int32 Dy = -2; Dy <= 2; ++Dy) Band->Add(Cell + FIntPoint(Dx, Dy));
			}
			CrownBand = Band;
		}
	}

	// Visual V6 (Medium and High): Nanite trees built in Blender (four species, two variants each), swaying in the wind
	// (M_TreeLeaves / M_TreeBark read MPC_World). Low keeps the Phase 3 shapes.
	static const TCHAR* SpeciesNames[] = { TEXT("LiveOak"), TEXT("PostOak"), TEXT("CedarElm"), TEXT("RedCedar") };
	const bool bModelTrees = USailingSettings::Get()->Quality != ESailingQuality::Low;
	if (bModelTrees && TreeModels.Num() == 0)
	{
		// Passes: leaf cards near, opaque crowns with shadows to MidTreesM, opaque crowns without beyond (Graphics G6), and
		// T1's lighting-only crowns under the near leaf cards. -SailingNoTreeLight leaves the lighting without trees and
		// -SailingNoTreeLooks every tree its model's own green, upright (both compare).
		const bool bTreeLight = !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoTreeLight"));
		// The Mac gate (#126): on High the crowns and proxies in the ray-tracing scene cost Metal's render thread 2 to 3.5 ms
		// a frame (GPU flat). Only Ultra (the desktop GPU) traces them; below it they are in Lumen's scene and the distance
		// fields only. -SailingTreeRayTracing=0|1 overrides, for measuring.
		int32 TreeRT = USailingSettings::Get()->Quality == ESailingQuality::Ultra ? 1 : 0;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingTreeRayTracing="), TreeRT);
		const bool bTreeRayTracing = bTreeLight && TreeRT != 0;
		bTreeLooks = !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoTreeLooks"));
		// Measuring (docs/budget/storm-high-2026-10-18.md): the looks without the lean or without the custom data, the
		// lighting without the proxies or without the mid and far crowns.
		bTreeLean = !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoTreeLean"));
		const bool bTreeData = bTreeLooks && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoTreeData"));
		const bool bTreeProxies = !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoTreeProxy"));
		const bool bCrownLight = bTreeLight && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoCrownLight"));
		for (int32 Pass = 0; Pass < (bTreeLight && bTreeProxies ? 4 : 3); ++Pass)
		{
			for (int32 S = 0; S < int32(ETreeSpecies::Count); ++S)
			{
				for (int32 V = 0; V < 2; ++V)
				{
					const FString Name = FString::Printf(TEXT("SM_%s_%d%s"), SpeciesNames[S], V, Pass >= 1 ? TEXT("_Far") : TEXT(""));
					if (Pass == 3)
					{
						// T1 (round 12: trees "lit evenly, the shoreline looks flat"): Lumen's scene had no trees at all (the leaf
						// cards cost 10 ms in it), so nothing shaded a crown's inside or the ground under it. These opaque crowns
						// stand in for the near trees in the lighting only: in ray tracing (Lumen on High and Ultra) and the
						// distance fields (Medium's software Lumen), never drawn, no shadow (the leaf cards cast that). Lumen takes
						// only primitives that affect indirect lighting into its scene, ray traced or not, so these do (an opaque
						// crown's few surface-cache cards, not a leaf card's thousands). A little smaller than the tree, so the
						// sunny outer leaves stay lit.
						UInstancedStaticMeshComponent* P = NewObject<UInstancedStaticMeshComponent>(this);
						// Static: a movable instanced primitive is re-culled as dynamic by the renderer every frame (scene culling's
						// IsOftenMoving), and the regroups only add and remove instances. The tiles cloned from these inherit it.
						P->SetMobility(EComponentMobility::Static);
						P->SetupAttachment(RootComponent);
						P->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Trees/%s.%s"), *Name, *Name)));
						P->SetCollisionEnabled(ECollisionEnabled::NoCollision);
						// Hidden, but in the indirect lighting (kept out of the main pass instead, Lumen left them out too).
						P->SetHiddenInGame(true);
						P->bAffectIndirectLightingWhileHidden = true;
						P->SetCastShadow(false);
						P->bAffectDynamicIndirectLighting = true;
						P->bAffectDistanceFieldLighting = true;
						P->bVisibleInRayTracing = bTreeRayTracing;
						P->SetCullDistances(0, (NearTreesM() + 200.0) * 100.0);
						P->RegisterComponent();
						TreeProxy.Add(P);
						continue;
					}
					UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Trees/%s.%s"), *Name, *Name));
					UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
					C->SetMobility(EComponentMobility::Static);   // as the proxies above
					C->SetupAttachment(RootComponent);
					C->SetStaticMesh(Mesh);
					C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
					// Out of Lumen's scene and ray tracing: capturing thousands of leaf cards into Lumen's surface cache
					// cost 10 ms; the trees still take Lumen's lighting.
					// T1: the opaque mid and far crowns are cheap occluders, so the lighting sees them (Lumen's scene: ray tracing
					// on High and Ultra, distance fields on Medium): their insides and the ground under them darken. The leaf
					// cards stay out.
					C->bAffectDynamicIndirectLighting = bCrownLight && Pass >= 1;
					C->bAffectDistanceFieldLighting = bCrownLight && Pass >= 1;
					C->bVisibleInRayTracing = bTreeRayTracing && Pass >= 1;
					// T1: each tree's tint, autumn turn and autumn colour (FTreeLook) for M_TreeLeaves / M_TreeCrown (without
					// them the materials take their defaults: the model's green, no season).
					C->NumCustomDataFloats = bTreeData ? 3 : 0;
					// Shadows (virtual shadow maps), cached as if still: the sway never re-renders the trees' shadow
					// pages (thousands of swaying trees would invalidate the cache every frame).
					// Graphics G6: the far band casts none (-SailingFarTreeShadows=1 to compare).
					int32 FarShadows = 0;
					FParse::Value(SailingArgs::Dev(), TEXT("SailingFarTreeShadows="), FarShadows);
					C->SetCastShadow(Pass < 2 || FarShadows != 0);
					C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
					C->SetCullDistances(0, (Pass == 0 ? NearTreesM() + 200.0 : (Pass == 1 ? MidTreesM() + 200.0 : 9000.0)) * 100.0);
					C->SetWorldPositionOffsetDisableDistance(int32((Pass == 0 ? NearTreesM() : 1500.0) * 100.0));
					C->RegisterComponent();
					(Pass == 0 ? TreeModels : (Pass == 1 ? TreeMid : TreeFar)).Add(C);
				}
			}
		}
	}
	if (bModelTrees && TreeModels.Num() > 0)
	{
		ModelTrees = MoveTemp(Trees);
		TreeCenter = FVector2D(1e12, 1e12); // rebuilt around the camera on the next tick
		TreeBand.Reset();                   // every band, not only the trees crossing an edge
		bTreesPlaced = true;
		UE_LOG(LogSailing, Display, TEXT("Trees: %d (Nanite models; leaf cards within %.0f m)"), ModelTrees.Num(), NearTreesM());
		return;
	}

	if (TreeMeshes.Num() == 0)
	{
		UStaticMesh* Sphere = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
		UStaticMesh* Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"));
		UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
		const TPair<UStaticMesh*, FLinearColor> Kinds[] = {
			{ Sphere, FLinearColor(0.11f, 0.17f, 0.06f) },  // post oak
			{ Sphere, FLinearColor(0.14f, 0.21f, 0.07f) },  // cedar elm
			{ Cone, FLinearColor(0.06f, 0.11f, 0.06f) },    // eastern red cedar
			{ Cylinder, FLinearColor(0.18f, 0.13f, 0.09f) } // trunks
		};
		for (const auto& K : Kinds)
		{
			UHierarchicalInstancedStaticMeshComponent* H = NewObject<UHierarchicalInstancedStaticMeshComponent>(this);
			H->SetupAttachment(RootComponent);
			H->SetStaticMesh(K.Key);
			H->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			H->SetCastShadow(false);
			H->SetCullDistances(0, 9000 * 100);
			H->RegisterComponent();
			UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShapeMaterial, this);
			Mid->SetVectorParameterValue(TEXT("Color"), K.Value);
			H->SetMaterial(0, Mid);
			TreeMeshes.Add(H);
		}
	}
	// Low: the Phase 3 shapes (spheres and cones) at the same places.
	TArray<FTransform> Oak, Elm, Cedar, Trunk;
	for (const FTreeInstance& I : Trees)
	{
		const float Height = I.Height;
		const FVector Base(I.Position.X * CmPerMeter, I.Position.Y * CmPerMeter, I.Ground * CmPerMeter);
		if (I.Species == ETreeSpecies::RedCedar)
		{
			Cedar.Add(FTransform(FRotator::ZeroRotator, Base + FVector(0, 0, Height * 50.f), FVector(Height * 0.35f, Height * 0.35f, Height)));
		}
		else
		{
			const bool bOak = I.Species != ETreeSpecies::CedarElm;
			const float W = I.Crown > 0.f ? FMath::Clamp(I.Crown * 2.f, Height * 0.45f, Height * 1.2f) : Height * (bOak ? 0.9f : 0.7f);
			(bOak ? Oak : Elm).Add(FTransform(FRotator::ZeroRotator, Base + FVector(0, 0, Height * 60.f), FVector(W, W, Height * 0.7f)));
			Trunk.Add(FTransform(FRotator::ZeroRotator, Base + FVector(0, 0, Height * 20.f), FVector(0.4f, 0.4f, Height * 0.4f)));
		}
	}
	TreeMeshes[0]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Oak), false, true);
	TreeMeshes[1]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Elm), false, true);
	TreeMeshes[2]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Cedar), false, true);
	TreeMeshes[3]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Trunk), false, true);
	UE_LOG(LogSailing, Display, TEXT("Trees: %d oak, %d cedar elm, %d red cedar"), Oak.Num(), Elm.Num(), Cedar.Num());
	bTreesPlaced = true;
}

void ALakeTerrainActor::PlaceReeds()
{
	const FLakeData* Lake = GetLake();
	if (!Lake || USailingSettings::Get()->Quality == ESailingQuality::Low || ReedModels.Num() > 0 || FParse::Param(SailingArgs::Dev(), TEXT("SailingNoReeds"))) return;
	UStaticMesh* Meshes[2] = { LoadObject<UStaticMesh>(nullptr, TEXT("/Game/World/Props/SM_Reeds_0.SM_Reeds_0")),
		LoadObject<UStaticMesh>(nullptr, TEXT("/Game/World/Props/SM_Reeds_1.SM_Reeds_1")) };
	if (!Meshes[0] || !Meshes[1]) return;
	const FLakeTerrain& T = Lake->Terrain;
	// Every grid node: gentle ground from 0.4 m under the water to 0.6 m above it, in patches
	// (a low-frequency field gates them, so coves fill and open banks stay bare), clear of the club's marina.
	const int32 Step = 1;
	auto Hash = [](uint32 X) { X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16; return X; };
	TArray<FTransform> Out[2];
	for (int32 R = 1; R < T.GetRows() - 1; R += Step)
	{
		for (int32 C = 1; C < T.GetCols() - 1; C += Step)
		{
			const double H = T.NodeHeight(R, C);
			if (H < -0.4 || H > 0.6) continue;
			const double Slope = FMath::Max(FMath::Abs(T.NodeHeight(R + 1, C) - T.NodeHeight(R - 1, C)), FMath::Abs(T.NodeHeight(R, C + 1) - T.NodeHeight(R, C - 1))) / (2.0 * T.GetCell());
			if (Slope > 0.2) continue;
			// At the water's edge only: open water within three cells (15 m on the lake), not a flat meadow at lake level.
			if (H > -0.05 && R > 3 && C > 3 && R < T.GetRows() - 4 && C < T.GetCols() - 4
				&& FMath::Min(FMath::Min(T.NodeHeight(R + 3, C), T.NodeHeight(R - 3, C)), FMath::Min(T.NodeHeight(R, C + 3), T.NodeHeight(R, C - 3))) > -0.05) continue;
			const double X = T.GetOriginX() + R * T.GetCell(), Y = T.GetOriginY() + C * T.GetCell();
			if (X * X + Y * Y < 350.0 * 350.0) continue;
			const double Patch = FMath::Sin(X * 0.011 + FMath::Sin(Y * 0.007) * 2.0) * FMath::Sin(Y * 0.013 + FMath::Sin(X * 0.005) * 2.0);
			const uint32 Hh = Hash(uint32(R) * 73856093u ^ uint32(C) * 19349663u);
			// The coasts' 10 m grid would put four times the lake's clumps along Galveston's marshes: thin them to the lake's spacing.
			const uint32 Keep = T.GetCell() >= 9.99 ? 260 : 760;
			if (Patch < -0.1 || (Hh & 1023) > Keep) continue;
			const int32 Kind = H < 0.05 ? 0 : int32((Hh >> 10) & 1);   // cattails stand in the water, rushes on the bank
			for (int32 K = 0; K < 2; ++K)
			{
				const uint32 Hk = Hash(Hh + K * 2654435761u);
				const double Dx = (((Hk & 255) / 255.0) - 0.5) * T.GetCell() * Step, Dy = ((((Hk >> 8) & 255) / 255.0) - 0.5) * T.GetCell() * Step;
				const double Ground = FMath::Max(T.HeightAt(X + Dx, Y + Dy), -0.35);
				const float S = 0.75f + 0.55f * ((Hk >> 16) & 255) / 255.f;
				Out[Kind].Add(FTransform(FRotator(0.f, ((Hk >> 24) & 255) * 1.41f, 0.f), FVector(X + Dx, Y + Dy, Ground) * CmPerMeter, FVector(S)));
			}
		}
	}
	for (int32 Kind = 0; Kind < 2; ++Kind)
	{
		// Hierarchical: a few hundred thousand clumps are culled by cluster, not one by one on the render thread.
		UHierarchicalInstancedStaticMeshComponent* C = NewObject<UHierarchicalInstancedStaticMeshComponent>(this);
		C->SetupAttachment(RootComponent);
		C->SetStaticMesh(Meshes[Kind]);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->bAffectDynamicIndirectLighting = false;
		C->bAffectDistanceFieldLighting = false;
		C->bVisibleInRayTracing = false;
		C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		C->SetCullDistances(0, 400.f * 100.f);
		C->RegisterComponent();
		C->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Out[Kind]), false, true);
		ReedModels.Add(C);
	}
	UE_LOG(LogSailing, Display, TEXT("Reeds: %d cattail and %d rush clumps (first at %s)"), Out[0].Num(), Out[1].Num(),
		Out[0].Num() ? *(Out[0][Out[0].Num() / 2].GetLocation() / CmPerMeter).ToString() : TEXT("-"));
}

void ALakeTerrainActor::PlaceBuildings()
{
	const FLakeData* Lake = GetLake();
	if (!Lake) return;
	if (PlaceHouseModels(*Lake)) return;
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	const FLinearColor Colors[] = { FLinearColor(0.75f, 0.72f, 0.66f), FLinearColor(0.55f, 0.40f, 0.32f), FLinearColor(0.85f, 0.84f, 0.80f) };
	for (const FLinearColor& Col : Colors)
	{
		UInstancedStaticMeshComponent* I = NewObject<UInstancedStaticMeshComponent>(this);
		I->SetupAttachment(RootComponent);
		I->SetStaticMesh(Cube);
		I->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		I->SetCullDistances(0, 6000 * 100);
		I->RegisterComponent();
		UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShapeMaterial, this);
		Mid->SetVectorParameterValue(TEXT("Color"), Col);
		I->SetMaterial(0, Mid);
		BuildingMeshes.Add(I);
	}
	TArray<FTransform> Lists[3];
	// The marina actor draws the club's own buildings: leave out the OSM boxes under them.
	const bool bMarina = Lake->Marina.IsLoaded();
	for (int32 K = 0; K < Lake->Buildings.Num(); ++K)
	{
		const FLakeBuilding& B = Lake->Buildings[K];
		if (bMarina && Lake->Marina.Buildings.ContainsByPredicate([&](const FMarinaBuilding& M)
			{ return FVector2D::Distance(M.Center, FVector2D(B.X, B.Y)) < 0.5 * M.Size.Size() + 5.0; }))
		{
			continue;
		}
		Lists[Hash(K) % 3].Add(FTransform(FRotator(0, B.YawDeg, 0), FVector(B.X, B.Y, B.Ground + B.Height * 0.5) * CmPerMeter, FVector(B.Length, B.Width, B.Height)));
	}
	for (int32 K = 0; K < 3; ++K) BuildingMeshes[K]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Lists[K]), false, true);
}

bool ALakeTerrainActor::PlaceHouseModels(const FLakeData& Lake)
{
	// Visual V6 (Medium and High): each OSM footprint gets an archetype scaled to it (Tools/blender/build_houses.py): a
	// gable-roofed ranch for one storey, a hip-roofed two-storey, a flat-roofed block for the big footprints, with wall
	// (brick, siding, stucco) and roof colours from North Texas streets. Windows are drawn by M_HouseWall in world space.
	if (USailingSettings::Get()->Quality == ESailingQuality::Low) return false;
	// Graphics G6: the G2 houses (real footprints, lidar eaves and roofs, NAIP roof colours; WorldKit's HouseKit.cpp) replace
	// the archetypes below where the world has them (-SailingClassicHouses compares). The private docks stay.
	const bool bKitHouses = Lake.Houses.Num() > 0 && !FParse::Param(SailingArgs::Dev(), TEXT("SailingClassicHouses"));
	if (bKitHouses)
	{
		TMap<FIntPoint, TArray<int32>> ByTile;
		HouseTiles(Lake, ByTile);
		TMap<FIntPoint, FKitGeometry> Tiles;
		int32 Procedural = 0;
		const FString Prefix = TEXT("Houses_") + Lake.SourceFor(TEXT("houses"));   // a composed world bakes nothing of its own: its member's tiles
		for (const auto& KV : ByTile)
		{
			FKitGeometry& G = Tiles.Add(KV.Key);
			if (!FPackageName::DoesPackageExist(TEXT("/Game/World/Baked/") + FKitGeometry::TileAssetName(Prefix, KV.Key)))
			{
				BuildHouseGeometry(Lake, KV.Value, G);
				++Procedural;
			}
		}
		const int32 Baked = SpawnKitTiles(this, Tiles, Prefix, false, [](EKitLook L) { return KitMaterial(L); }, HouseTileMeshes);
		UE_LOG(LogSailing, Display, TEXT("Houses: %d from the G2 footprints in %d tiles (%d baked, %d procedural)"), Lake.Houses.Num(), Tiles.Num(), Baked, Procedural);
	}
	static const TCHAR* Names[] = { TEXT("SM_House_Gable"), TEXT("SM_House_Hip"), TEXT("SM_House_Flat") };
	TArray<UInstancedStaticMeshComponent*> Ism;
	for (const TCHAR* Name : Names)
	{
		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Houses/%s.%s"), Name, Name));
		if (!Mesh) return false;
		UInstancedStaticMeshComponent* I = NewObject<UInstancedStaticMeshComponent>(this);
		I->SetMobility(EComponentMobility::Static);
		I->SetupAttachment(RootComponent);
		I->SetStaticMesh(Mesh);
		I->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		I->SetCullDistances(0, 8000 * 100);
		I->NumCustomDataFloats = FWearSeed::TotalFloats;  // paint 0-9, then the wear seed (Environment E1)
		I->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		I->RegisterComponent();
		Ism.Add(I);
		BuildingMeshes.Add(I);
	}
	static const FLinearColor Brick[] = { FLinearColor(0.30f, 0.11f, 0.07f), FLinearColor(0.38f, 0.18f, 0.10f), FLinearColor(0.42f, 0.30f, 0.20f), FLinearColor(0.25f, 0.13f, 0.09f) };
	static const FLinearColor Light[] = { FLinearColor(0.72f, 0.68f, 0.58f), FLinearColor(0.62f, 0.60f, 0.55f), FLinearColor(0.78f, 0.77f, 0.73f), FLinearColor(0.45f, 0.50f, 0.52f), FLinearColor(0.60f, 0.52f, 0.40f) };
	static const FLinearColor Roofs[] = { FLinearColor(0.10f, 0.10f, 0.10f), FLinearColor(0.16f, 0.14f, 0.12f), FLinearColor(0.20f, 0.20f, 0.21f), FLinearColor(0.22f, 0.16f, 0.11f) };
	TArray<FTransform> X[3];
	TArray<float> D[3];
	// Graphics G2: houses within 400 m of the water are real-size models with their windows, doors, porches and eaves
	// (Tools/blender/build_houses_near.py), the closest size to the footprint, turned so the back faces the water; the
	// lakefront ones get a private dock. Further away the unit archetypes above stay.
	struct FNearKind { const TCHAR* Name; float L, W; bool bTwo; };
	static const FNearKind NearKinds[] = { { TEXT("RanchS"), 13.f, 9.f, false }, { TEXT("RanchM"), 18.f, 11.f, false }, { TEXT("Cottage"), 10.f, 8.f, false },
		{ TEXT("TwoS"), 12.f, 9.f, true }, { TEXT("TwoL"), 17.f, 12.f, true }, { TEXT("Modern"), 15.f, 10.f, true } };
	constexpr int32 NumNear = UE_ARRAY_COUNT(NearKinds);
	TArray<UInstancedStaticMeshComponent*> NearIsm;
	UInstancedStaticMeshComponent* DockIsm[2] = { nullptr, nullptr };
	auto MakeIsm = [&](const FString& Name, int32 CustomFloats, float CullM) -> UInstancedStaticMeshComponent*
	{
		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Houses/%s.%s"), *Name, *Name));
		if (!Mesh) return nullptr;
		UInstancedStaticMeshComponent* I = NewObject<UInstancedStaticMeshComponent>(this);
		I->SetMobility(EComponentMobility::Static);
		I->SetupAttachment(RootComponent);
		I->SetStaticMesh(Mesh);
		I->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		I->SetCullDistances(0, CullM * 100.f);
		I->NumCustomDataFloats = CustomFloats;
		I->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		I->RegisterComponent();
		BuildingMeshes.Add(I);
		return I;
	};
	for (const FNearKind& K : NearKinds) NearIsm.Add(MakeIsm(FString(TEXT("SM_HouseNear_")) + K.Name, FWearSeed::TotalFloats, 6000.f));
	const bool bNear = !NearIsm.Contains(nullptr);
	if (bNear)
	{
		DockIsm[0] = MakeIsm(TEXT("SM_HouseNear_Dock"), FWearSeed::TotalFloats, 3000.f);
		DockIsm[1] = MakeIsm(TEXT("SM_HouseNear_Boathouse"), FWearSeed::TotalFloats, 3000.f);
	}
	TArray<FTransform> NearX[NumNear], DockX[2];
	TArray<float> NearD[NumNear], DockD[2];
	// Environment E1: every house and private dock carries its wear seed after its own floats (FWearSeed::Slot).
	const EWearSite Site = WearSiteFor(Lake);
	constexpr int32 Stride = FWearSeed::TotalFloats;
	static_assert(FWearSeed::Slot == 10, "the houses' paint fills slots 0-9");
	auto AppendWear = [](TArray<float>& D, const FWearSeed& W)
	{
		const int32 At = D.Num();
		D.AddZeroed(FWearSeed::NumFloats);
		W.Write(&D[At]);
	};
	TArray<FVector2D> Docks;
	const FLakeTerrain& Terr = Lake.Terrain;
	// The nearest open water within 400 m: rings every 25 m, 16 directions.
	auto WaterToward = [&Terr](double X0, double Y0, FVector2D& Dir) -> double
	{
		for (double R = 25.0; R <= 400.0; R += 25.0)
		{
			for (int32 A = 0; A < 16; ++A)
			{
				const double Ang = A * UE_DOUBLE_PI / 8.0;
				if (Terr.HeightAt(X0 + R * FMath::Cos(Ang), Y0 + R * FMath::Sin(Ang)) < -0.3)
				{
					Dir = FVector2D(FMath::Cos(Ang), FMath::Sin(Ang));
					return R;
				}
			}
		}
		return -1.0;
	};
	const bool bMarina = Lake.Marina.IsLoaded();
	for (int32 K = 0; K < Lake.Buildings.Num(); ++K)
	{
		const FLakeBuilding& B = Lake.Buildings[K];
		if (bMarina && Lake.Marina.Buildings.ContainsByPredicate([&](const FMarinaBuilding& M)
			{ return FVector2D::Distance(M.Center, FVector2D(B.X, B.Y)) < 0.5 * M.Size.Size() + 5.0; }))
		{
			continue;
		}
		const uint32 H = Hash(K);
		const double Area = B.Length * B.Width;
		const int32 Kind = Area > 600.0 ? 2 : (B.Height >= 6.5 || (H % 5) == 0 ? 1 : 0);
		const float Height = Kind == 2 ? FMath::Max(float(B.Height), 6.f) : float(B.Height);
		const int32 Pat = Kind == 2 ? 2 : int32((H >> 4) % 3);
		const FLinearColor Wall = Pat == 0 ? Brick[(H >> 8) % UE_ARRAY_COUNT(Brick)] : Light[(H >> 8) % UE_ARRAY_COUNT(Light)];
		const FLinearColor Roof = Roofs[(H >> 12) % UE_ARRAY_COUNT(Roofs)];
		FVector2D WaterDir;
		const double WaterM = bNear && Kind != 2 ? WaterToward(B.X, B.Y, WaterDir) : -1.0;
		if (WaterM > 0.0)
		{
			// The closest size among the right number of storeys (log-distance on length and width).
			const bool bTwo = Kind == 1;
			int32 Best = -1;
			double BestCost = 1e9;
			const double Lb = FMath::Max(B.Length, B.Width), Wb = FMath::Min(B.Length, B.Width);
			for (int32 N = 0; N < NumNear; ++N)
			{
				if (NearKinds[N].bTwo != bTwo) continue;
				const double Cost = FMath::Abs(FMath::Loge(Lb / NearKinds[N].L)) + FMath::Abs(FMath::Loge(Wb / NearKinds[N].W)) + ((H >> 20) % 7) * 0.02;
				if (Cost < BestCost) { BestCost = Cost; Best = N; }
			}
			const FNearKind& NK = NearKinds[Best];
			const float Sx = FMath::Clamp(float(Lb) / NK.L, 0.8f, 1.25f), Sy = FMath::Clamp(float(Wb) / NK.W, 0.8f, 1.25f);
			// The model's length runs along its X; its back (local -Y after the mirror into Unreal) faces the water.
			float Yaw = float(B.YawDeg) + (B.Length >= B.Width ? 0.f : 90.f);
			const FVector2D Back(FMath::Sin(FMath::DegreesToRadians(Yaw)), -FMath::Cos(FMath::DegreesToRadians(Yaw)));
			if (FVector2D::DotProduct(Back, WaterDir) < 0.0) Yaw += 180.f;
			if (!bKitHouses)
			{
				NearX[Best].Add(FTransform(FRotator(0, Yaw, 0), FVector(B.X, B.Y, B.Ground) * CmPerMeter, FVector(Sx, Sy, 1.f)));
				NearD[Best].Append({ Wall.R, Wall.G, Wall.B, float(Pat) + 10.f, Height, float((H >> 16) % 97) / 97.f, Roof.R, Roof.G, Roof.B, float(B.Ground) });
				AppendWear(NearD[Best], FWearSeed::Make(FWearSeed::IdAt(FVector2D(B.X, B.Y)), Site, EWearWater::Dry, Yaw));
			}
			// A private dock for the lakefront houses: from the bank toward the water, a few metres clear of the next.
			if (WaterM <= 75.0 && ((H >> 24) % 10) < 6)
			{
				FVector2D P(B.X, B.Y), Shore = P;
				for (double T = 0.0; T < 120.0; T += 2.0)
				{
					const FVector2D Q = P + WaterDir * T;
					if (Terr.HeightAt(Q.X, Q.Y) < 0.0) break;
					Shore = Q;
				}
				if (!Docks.ContainsByPredicate([&](const FVector2D& O) { return FVector2D::Distance(O, Shore) < 15.0; }))
				{
					Docks.Add(Shore);
					const int32 Which = ((H >> 28) % 4) == 0 ? 1 : 0;
					const float DockYaw = float(FMath::RadiansToDegrees(FMath::Atan2(WaterDir.Y, WaterDir.X)));
					DockX[Which].Add(FTransform(FRotator(0, DockYaw, 0), FVector(Shore.X, Shore.Y, 0.0) * CmPerMeter));
					DockD[Which].AddZeroed(FWearSeed::Slot);
					AppendWear(DockD[Which], FWearSeed::Make(FWearSeed::IdAt(Shore), Site, EWearWater::Fixed, DockYaw));
				}
			}
			continue;
		}
		if (bKitHouses) continue;
		X[Kind].Add(FTransform(FRotator(0, B.YawDeg, 0), FVector(B.X, B.Y, B.Ground) * CmPerMeter, FVector(B.Length, B.Width, Height)));
		D[Kind].Append({ Wall.R, Wall.G, Wall.B, float(Pat), Height, float((H >> 16) % 97) / 97.f, Roof.R, Roof.G, Roof.B, float(B.Ground) });
		AppendWear(D[Kind], FWearSeed::Make(FWearSeed::IdAt(FVector2D(B.X, B.Y)), Site, EWearWater::Dry, float(B.YawDeg)));
	}
	for (int32 K = 0; K < 3; ++K)
	{
		Ism[K]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), X[K]), false, true);
		for (int32 I = 0; I < X[K].Num(); ++I) Ism[K]->SetCustomData(I, TArrayView<const float>(&D[K][Stride * I], Stride), false);
		Ism[K]->MarkRenderStateDirty();
	}
	int32 NearCount = 0;
	for (int32 N = 0; N < NumNear && bNear; ++N)
	{
		NearIsm[N]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), NearX[N]), false, true);
		for (int32 I = 0; I < NearX[N].Num(); ++I) NearIsm[N]->SetCustomData(I, TArrayView<const float>(&NearD[N][Stride * I], Stride), false);
		NearIsm[N]->MarkRenderStateDirty();
		NearCount += NearX[N].Num();
	}
	for (int32 Which = 0; Which < 2; ++Which)
	{
		if (!DockIsm[Which]) continue;
		DockIsm[Which]->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), DockX[Which]), false, true);
		for (int32 I = 0; I < DockX[Which].Num(); ++I) DockIsm[Which]->SetCustomData(I, TArrayView<const float>(&DockD[Which][Stride * I], Stride), false);
		DockIsm[Which]->MarkRenderStateDirty();
	}
	UE_LOG(LogSailing, Display, TEXT("Buildings: %d ranch, %d two-storey, %d blocks; %d near the water modelled, %d private docks"),
		X[0].Num(), X[1].Num(), X[2].Num(), NearCount, DockX[0].Num() + DockX[1].Num());
	return true;
}

void ALakeTerrainActor::PlaceBridgesAndDocks()
{
	const FLakeData* Lake = GetLake();
	if (!Lake) return;
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	auto MakeIsm = [&](UStaticMesh* Mesh, const FLinearColor& Col)
	{
		UInstancedStaticMeshComponent* I = NewObject<UInstancedStaticMeshComponent>(this);
		I->SetupAttachment(RootComponent);
		I->SetStaticMesh(Mesh);
		I->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		I->RegisterComponent();
		UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShapeMaterial, this);
		Mid->SetVectorParameterValue(TEXT("Color"), Col);
		I->SetMaterial(0, Mid);
		return I;
	};
	BridgeDecks = MakeIsm(Cube, FLinearColor(0.55f, 0.55f, 0.52f));
	Pilings = MakeIsm(Cylinder, FLinearColor(0.45f, 0.44f, 0.42f));

	TArray<FTransform> Decks, Piles;
	// Medium and High draw the bridge kit (ABridgesActor); Low keeps these deck boxes and piles.
	const bool bBridgeKit = USailingSettings::Get()->Quality != ESailingQuality::Low;
	for (const FLakeBridge& Br : Lake->Bridges)
	{
		if (bBridgeKit) break;
		const float Width = Br.DeckHeight >= 7.0 ? 16.f : 8.f;
		for (int32 I = 1; I < Br.Points.Num(); ++I)
		{
			const FVector2D A = Br.Points[I - 1], B = Br.Points[I];
			const FVector2D D = B - A;
			const float Len = D.Size();
			if (Len < 0.5f) continue;
			const FVector2D Mid = (A + B) * 0.5;
			const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X));
			Decks.Add(FTransform(FRotator(0, Yaw, 0), FVector(Mid.X, Mid.Y, Br.DeckHeight + 0.75) * CmPerMeter, FVector(Len + 0.5f, Width, 1.5f)));
			for (float S = 0.f; S < Len; S += 30.f)
			{
				const FVector2D P = A + D * (S / Len);
				const double Bed = FMath::Min(Lake->Terrain.HeightAt(P.X, P.Y), 0.0);
				const double H = Br.DeckHeight - Bed;
				Piles.Add(FTransform(FRotator::ZeroRotator, FVector(P.X, P.Y, Bed + H * 0.5) * CmPerMeter, FVector(1.4f, 1.4f, H)));
			}
		}
	}

	// Docks: closed outlines become floating deck slabs; open lines become 2 m walkways. Pilings along the edges.
	DockMesh = NewObject<UProceduralMeshComponent>(this);
	DockMesh->SetupAttachment(RootComponent);
	DockMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	DockMesh->RegisterComponent();
	UMaterialInstanceDynamic* DockMat = UMaterialInstanceDynamic::Create(ShapeMaterial, this);
	DockMat->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.50f, 0.42f, 0.32f));
	DockMesh->SetMaterial(0, DockMat);
	TArray<FVector> V;
	TArray<int32> Tri;
	TArray<FVector> N;
	constexpr double Deck = 0.45;
	// The club's marina (AMarinaActor) replaces the OSM docks inside it, as in the physics (FLakeData::BuildObstacles).
	const FBox2D MarinaBox = Lake->Marina.Bounds();
	// Medium and High draw riprap (and a lake's piers) from the shore kit (ABridgesActor, BuildShoreGeometry).
	const bool bShoreKit = USailingSettings::Get()->Quality != ESailingQuality::Low;
	const bool bKitPiers = bShoreKit && KitDrawsPiers(*Lake);
	for (const FLakeDock& Dock : Lake->Docks)
	{
		if (MarinaBox.bIsValid && MarinaBox.IsInside(Dock.Points[0])) continue;
		if (bShoreKit && (Dock.Kind == TEXT("breakwater") || Dock.Kind == TEXT("groin") || bKitPiers)) continue;
		// Graphics G7: the dike and the Seawall are drawn by the shore kit (or the terrain on Low), floating walkways by
		// ACoastMarinasActor at the water's level.
		if (Dock.Kind == TEXT("dike") || Dock.Kind == TEXT("seawall") || Dock.Kind == TEXT("floating")) continue;
		if (Dock.bClosed)
		{
			TArray<FVector2D> Pts = Dock.Points;
			Pts.Pop(); // closing point
			const TArray<int32> Ids = KitTriangulate(Pts);
			const int32 Base = V.Num();
			for (const FVector2D& P : Pts) { V.Add(FVector(P.X, P.Y, Deck) * CmPerMeter); N.Add(FVector::UpVector); }
			for (int32 I = 0; I + 2 < Ids.Num(); I += 3) Tri.Append({ Base + Ids[I], Base + Ids[I + 2], Base + Ids[I + 1] });
		}
		else
		{
			for (int32 I = 1; I < Dock.Points.Num(); ++I)
			{
				const FVector2D A = Dock.Points[I - 1], B = Dock.Points[I];
				const FVector2D Dir = (B - A).GetSafeNormal(), Side(-Dir.Y, Dir.X);
				const int32 Base = V.Num();
				for (const FVector2D& P : { A - Side, A + Side, B - Side, B + Side }) { V.Add(FVector(P.X, P.Y, Deck) * CmPerMeter); N.Add(FVector::UpVector); }
				Tri.Append({ Base, Base + 1, Base + 2, Base + 1, Base + 3, Base + 2 });
			}
		}
		for (int32 I = 0; I < Dock.Points.Num(); I += 3)
		{
			const FVector2D P = Dock.Points[I];
			Piles.Add(FTransform(FRotator::ZeroRotator, FVector(P.X, P.Y, -0.5) * CmPerMeter, FVector(0.25f, 0.25f, 2.6f)));
		}
	}
	if (V.Num() > 0)
	{
		DockMesh->CreateMeshSection_LinearColor(0, V, Tri, N, {}, {}, {}, false);
	}
	BridgeDecks->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Decks), false, true);
	Pilings->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), Piles), false, true);
}
