#include "LakeTerrainActor.h"
#include "UObject/UObjectIterator.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "LakeData.h"
#include "Marina.h"
#include "TreePlacement.h"
#include "WorldKit.h"
#include "Async/Async.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
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
		static const double M = []
		{
			double V = USailingSettings::Get()->Quality >= ESailingQuality::High ? 250.0 : 200.0;
			FParse::Value(FCommandLine::Get(), TEXT("SailingNearTrees="), V);
			return V;
		}();
		return M;
	}
	// Graphics G6: the opaque crowns cast shadows out to this (m); beyond, none (the far crowns' virtual shadow pages cost
	// High 6.5 ms at the slip, and their shadows are lost at that range). -SailingMidTrees=<m> to measure.
	double MidTreesM()
	{
		static const double M = []
		{
			double V = USailingSettings::Get()->Quality >= ESailingQuality::High ? 1000.0 : 600.0;
			FParse::Value(FCommandLine::Get(), TEXT("SailingMidTrees="), V);
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

	/** Ear-clipping triangulation of a simple polygon (no holes). Returns triangle indices into Points. */
	TArray<int32> Triangulate(const TArray<FVector2D>& Points)
	{
		TArray<int32> Result;
		TArray<int32> Idx;
		const int32 N = Points.Num();
		if (N < 3) return Result;
		double Area = 0.0;
		for (int32 I = 0; I < N; ++I) Area += FVector2D::CrossProduct(Points[I], Points[(I + 1) % N]);
		for (int32 I = 0; I < N; ++I) Idx.Add(Area > 0.0 ? I : N - 1 - I);
		int32 Guard = 0;
		while (Idx.Num() > 3 && Guard++ < N * N)
		{
			bool bClipped = false;
			for (int32 I = 0; I < Idx.Num(); ++I)
			{
				const int32 A = Idx[(I + Idx.Num() - 1) % Idx.Num()], B = Idx[I], C = Idx[(I + 1) % Idx.Num()];
				const FVector2D PA = Points[A], PB = Points[B], PC = Points[C];
				if (FVector2D::CrossProduct(PB - PA, PC - PB) <= 0.0) continue; // reflex
				bool bInside = false;
				for (int32 K : Idx)
				{
					if (K == A || K == B || K == C) continue;
					const FVector2D P = Points[K];
					if (FVector2D::CrossProduct(PB - PA, P - PA) > 0.0 && FVector2D::CrossProduct(PC - PB, P - PB) > 0.0 && FVector2D::CrossProduct(PA - PC, P - PC) > 0.0)
					{
						bInside = true;
						break;
					}
				}
				if (bInside) continue;
				Result.Append({ A, B, C });
				Idx.RemoveAt(I);
				bClipped = true;
				break;
			}
			if (!bClipped) break;
		}
		if (Idx.Num() == 3) Result.Append({ Idx[0], Idx[1], Idx[2] });
		return Result;
	}
}

ALakeTerrainActor::ALakeTerrainActor()
{
	PrimaryActorTick.bCanEverTick = true;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Terrain(TEXT("/Game/Materials/M_Terrain.M_Terrain"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Shape(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	TerrainMaterial = Terrain.Object;
	ShapeMaterial = Shape.Object;
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
	HideBelow = USailingSettings::Get()->World == 2 ? -15.0 : -3.5;
	const FLakeData* Lake = GetLake();
	if (!Lake)
	{
		return;
	}
	const FLakeTerrain& T = Lake->Terrain;
	GChunkCells = T.GetCell() >= 9.99 ? 128 : 64;
	ChunkRows = FMath::DivideAndRoundUp(T.GetRows() - 1, GChunkCells);
	ChunkCols = FMath::DivideAndRoundUp(T.GetCols() - 1, GChunkCells);
	Chunks.SetNum(ChunkRows * ChunkCols);
	for (int32 R = 0; R < ChunkRows; ++R)
	{
		for (int32 C = 0; C < ChunkCols; ++C)
		{
			FChunk& Ch = Chunks[R * ChunkCols + C];
			Ch.Row = R;
			Ch.Col = C;
			const double Size = GChunkCells * T.GetCell();
			Ch.bHasDetail = T.HasDetailIn(T.GetOriginX() + R * Size, T.GetOriginY() + C * Size, T.GetOriginX() + (R + 1) * Size, T.GetOriginY() + (C + 1) * Size);
			UProceduralMeshComponent* Mesh = NewObject<UProceduralMeshComponent>(this);
			Mesh->SetupAttachment(RootComponent);
			Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Mesh->bUseAsyncCooking = true;
			Mesh->RegisterComponent();
			Mesh->SetMaterial(0, TerrainMaterial);
			Mesh->SetCullDistance(20000.f * 100.f); // past 20 km the land is a sliver on the horizon, under the haze
			Ch.Mesh = Mesh;
		}
	}
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
	for (FChunk& Ch : Chunks)
	{
		if (Ch.bBuilding) Ch.Future.Wait();
	}
	Super::EndPlay(Reason);
}

ALakeTerrainActor::FChunkMesh ALakeTerrainActor::BuildChunk(const FLakeData* Lake, int32 ChunkRow, int32 ChunkCol, int32 Step, double HideBelow)
{
	// Runs on a worker thread: reads only the immutable lake data.
	FChunkMesh M;
	if (!Lake) return M;
	const FLakeTerrain& T = Lake->Terrain;
	// Graphics G2: Step 0 is the near level on the shore: the chunk meshed at the 1 m lidar detail's spacing (HeightAt
	// takes the detail where a tile covers the point and the grid elsewhere in the chunk).
	const bool bFine = Step == 0;
	const double Cell = bFine ? T.GetDetailCell() : T.GetCell();
	const int32 Sub = bFine ? FMath::Max(1, FMath::RoundToInt(T.GetCell() / Cell)) : 1;
	if (bFine) Step = 1;
	const int32 N = GChunkCells * Sub / Step;
	const double OX = T.GetOriginX(), OY = T.GetOriginY();
	auto H = [&](int32 R, int32 C) { return bFine ? T.HeightAt(OX + R * Cell, OY + C * Cell) : T.NodeHeight(R, C); };
	const int32 R0 = ChunkRow * GChunkCells * Sub, C0 = ChunkCol * GChunkCells * Sub;
	const int32 MaxR = (T.GetRows() - 1) * Sub, MaxC = (T.GetCols() - 1) * Sub;

	M.Vertices.Reserve((N + 1) * (N + 1) + 4 * (N + 1));
	for (int32 I = 0; I <= N; ++I)
	{
		for (int32 J = 0; J <= N; ++J)
		{
			const int32 R = FMath::Min(R0 + I * Step, MaxR), C = FMath::Min(C0 + J * Step, MaxC);
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
			const int32 GR = R / Sub, GC = C / Sub; // the colour noise stays on the 5 m grid's cells at every level
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

void ALakeTerrainActor::UpdateModelTrees(const FVector2D& Camera)
{
	// Visual V6: leaf-card trees near the camera (alpha-masked Nanite is costly over many pixels), the opaque far
	// crowns beyond; regrouped when the camera has moved a quarter of the near radius.
	if (TreeModels.Num() == 0 || ModelTrees.Num() == 0 || FVector2D::Distance(Camera, TreeCenter) < FMath::Max(100.0, 0.25 * NearTreesM())) return;
	TreeCenter = Camera;
	TArray<TArray<FTransform>> Near, Mid, Far;
	Near.SetNum(TreeModels.Num());
	Mid.SetNum(TreeMid.Num());
	Far.SetNum(TreeFar.Num());
	const double R2 = FMath::Square(NearTreesM()), RM2 = FMath::Square(MidTreesM());
	for (const FTreeInstance& I : ModelTrees)
	{
		const int32 Index = int32(I.Species) * 2 + I.Variant;
		const double D2 = FVector2D::DistSquared(I.Position, Camera);
		const bool bNear = D2 < R2, bMid = !bNear && D2 < RM2 && TreeMid.Num() > 0;
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
		(bNear ? Near : (bMid ? Mid : Far))[Index].Add(FTransform(FRotator(0.f, I.Yaw, 0.f), FVector(I.Position.X * CmPerMeter, I.Position.Y * CmPerMeter, (I.Ground - Drop) * CmPerMeter), FVector(ScaleXY, ScaleXY, Scale)));
	}
	for (int32 M = 0; M < TreeModels.Num(); ++M)
	{
		TreeModels[M]->ClearInstances();
		TreeModels[M]->AddInstances(Near[M], false, true);
		TreeFar[M]->ClearInstances();
		TreeFar[M]->AddInstances(Far[M], false, true);
		if (TreeMid.IsValidIndex(M))
		{
			TreeMid[M]->ClearInstances();
			TreeMid[M]->AddInstances(Mid[M], false, true);
		}
	}
}

void ALakeTerrainActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
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
	if (Chunks.Num() == 0) return;
	const FLakeData* Lake = GetLake();
	if (!Lake) return;

	FVector Cam = FVector::ZeroVector;
	if (APlayerCameraManager* CM = UGameplayStatics::GetPlayerCameraManager(this, 0)) Cam = CM->GetCameraLocation();
	const double CamX = Cam.X / CmPerMeter, CamY = Cam.Y / CmPerMeter;
	UpdateModelTrees(FVector2D(CamX, CamY));
	const FLakeTerrain& T = Lake->Terrain;
	const double ChunkSize = GChunkCells * T.GetCell();

	// Wanted level of detail by distance to the camera; queue the closest chunks first.
	TArray<int32> Order;
	Pending = 0;
	int32 InFlight = 0;
	for (int32 I = 0; I < Chunks.Num(); ++I)
	{
		FChunk& Ch = Chunks[I];
		const double CX = T.GetOriginX() + (Ch.Row + 0.5) * ChunkSize, CY = T.GetOriginY() + (Ch.Col + 0.5) * ChunkSize;
		const double D = FMath::Max(0.0, FVector2D::Distance(FVector2D(CX, CY), FVector2D(CamX, CamY)) - 0.5 * ChunkSize);
		Ch.Wanted = D < 900.0 ? 1 : (D < 2200.0 ? 2 : (D < 5000.0 ? 4 : 8));
		// Graphics G2: the 1 m lidar mesh on the shore near the camera (Step 0), where the chunk has detail tiles.
		if (D < kFineTerrainM && Ch.bHasDetail) Ch.Wanted = 0;
		if (Ch.bBuilding) ++InFlight;
		if (Ch.Lod != Ch.Wanted && !Ch.bBuilding) { Order.Add(I); ++Pending; }
	}
	Order.Sort([&](int32 A, int32 B)
	{
		// Unbuilt chunks first (so the whole lake appears quickly at low detail), then nearest.
		const bool BuiltA = Chunks[A].Lod >= 0, BuiltB = Chunks[B].Lod >= 0;
		if (BuiltA != BuiltB) return !BuiltA;
		return Chunks[A].Wanted < Chunks[B].Wanted;
	});
	for (int32 Index : Order)
	{
		if (InFlight >= kMaxBuildsInFlight) break;
		FChunk& Ch = Chunks[Index];
		Ch.bBuilding = true;
		const int32 Row = Ch.Row, Col = Ch.Col, Step = Ch.Wanted;
		Ch.Lod = -2 - Step; // marks the step being built
		const double Hide = HideBelow;
		Ch.Future = Async(EAsyncExecution::ThreadPool, [Lake, Row, Col, Step, Hide]() { return BuildChunk(Lake, Row, Col, Step, Hide); });
		++InFlight;
	}

	// Upload finished chunks, a few per frame.
	int32 Uploads = 0;
	for (FChunk& Ch : Chunks)
	{
		if (!Ch.bBuilding || !Ch.Future.IsReady()) continue;
		if (Uploads++ >= kMaxUploadsPerFrame) break;
		FChunkMesh M = Ch.Future.Get();
		Ch.Mesh->ClearAllMeshSections();
		Ch.Mesh->CreateMeshSection_LinearColor(0, M.Vertices, M.Triangles, M.Normals, {}, M.Colors, {}, false);
		Ch.Lod = -2 - Ch.Lod;
		// Only chunks within about 2 km cast shadows: farther, the shadows are under a pixel but every chunk is a
		// draw in each cascade (Galveston Bay has some 4,000 chunks; facing the shore cost 15 fps on the render thread).
		const bool bShadow = Ch.Lod <= 2;
		if (Ch.Mesh->CastShadow != bShadow) Ch.Mesh->SetCastShadow(bShadow);
		Ch.bBuilding = false;
	}
}

void ALakeTerrainActor::PlaceTrees()
{
	const FLakeData* Lake = GetLake();
	if (!Lake) return;
	const FLakeTerrain& T = Lake->Terrain;
	TArray<FTreeInstance> Trees;
	// Graphics G6: the lidar's crowns where the G2 band has them (-SailingClassicTrees compares).
	if (Lake->Crowns.Num() > 0 && !FParse::Param(FCommandLine::Get(), TEXT("SailingClassicTrees"))) PlaceCrownTrees(T, Lake->Crowns, TreeFraction, Trees);
	else PlaceTreeInstances(T, TreeFraction, Trees);
	// Graphics G6: no tree inside a G2 house (the canopy grid only knew the OSM footprints).
	if (Lake->Houses.Num() > 0)
	{
		constexpr double Cell = 50.0;
		TMap<FIntPoint, TArray<int32, TInlineAllocator<4>>> Grid;
		for (int32 K = 0; K < Lake->Houses.Num(); ++K)
		{
			const FLakeHouse& H = Lake->Houses[K];
			Grid.FindOrAdd(FIntPoint(FMath::FloorToInt32(H.X / Cell), FMath::FloorToInt32(H.Y / Cell))).Add(K);
		}
		const int32 Before = Trees.Num();
		Trees.RemoveAll([&](const FTreeInstance& I)
		{
			const FIntPoint C(FMath::FloorToInt32(I.Position.X / Cell), FMath::FloorToInt32(I.Position.Y / Cell));
			for (int32 Dx = -1; Dx <= 1; ++Dx) for (int32 Dy = -1; Dy <= 1; ++Dy)
			{
				const auto* List = Grid.Find(C + FIntPoint(Dx, Dy));
				if (!List) continue;
				for (const int32 K : *List)
				{
					for (const FLakeHouse::FWing& W : Lake->Houses[K].Wings)
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
		UE_LOG(LogSailing, Display, TEXT("Trees: %d inside G2 houses removed"), Before - Trees.Num());
	}

	// Visual V6 (Medium and High): Nanite trees built in Blender (four species, two variants each), swaying in the wind
	// (M_TreeLeaves / M_TreeBark read MPC_World). Low keeps the Phase 3 shapes.
	static const TCHAR* SpeciesNames[] = { TEXT("LiveOak"), TEXT("PostOak"), TEXT("CedarElm"), TEXT("RedCedar") };
	const bool bModelTrees = USailingSettings::Get()->Quality != ESailingQuality::Low;
	if (bModelTrees && TreeModels.Num() == 0)
	{
		// Passes: leaf cards near, opaque crowns with shadows to MidTreesM, opaque crowns without beyond (Graphics G6).
		for (int32 Pass = 0; Pass < 3; ++Pass)
		{
			for (int32 S = 0; S < int32(ETreeSpecies::Count); ++S)
			{
				for (int32 V = 0; V < 2; ++V)
				{
					const FString Name = FString::Printf(TEXT("SM_%s_%d%s"), SpeciesNames[S], V, Pass >= 1 ? TEXT("_Far") : TEXT(""));
					UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Trees/%s.%s"), *Name, *Name));
					UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
					C->SetupAttachment(RootComponent);
					C->SetStaticMesh(Mesh);
					C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
					// Out of Lumen's scene and ray tracing: capturing thousands of leaf cards into Lumen's surface cache
					// cost 10 ms; the trees still take Lumen's lighting.
					C->bAffectDynamicIndirectLighting = false;
					C->bAffectDistanceFieldLighting = false;
					C->bVisibleInRayTracing = false;
					// Shadows (virtual shadow maps), cached as if still: the sway never re-renders the trees' shadow
					// pages (thousands of swaying trees would invalidate the cache every frame).
					// Graphics G6: the far band casts none (-SailingFarTreeShadows=1 to compare).
					int32 FarShadows = 0;
					FParse::Value(FCommandLine::Get(), TEXT("SailingFarTreeShadows="), FarShadows);
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
	TreeMeshes[0]->AddInstances(Oak, false, true);
	TreeMeshes[1]->AddInstances(Elm, false, true);
	TreeMeshes[2]->AddInstances(Cedar, false, true);
	TreeMeshes[3]->AddInstances(Trunk, false, true);
	UE_LOG(LogSailing, Display, TEXT("Trees: %d oak, %d cedar elm, %d red cedar"), Oak.Num(), Elm.Num(), Cedar.Num());
	bTreesPlaced = true;
}

void ALakeTerrainActor::PlaceReeds()
{
	const FLakeData* Lake = GetLake();
	if (!Lake || USailingSettings::Get()->Quality == ESailingQuality::Low || ReedModels.Num() > 0 || FParse::Param(FCommandLine::Get(), TEXT("SailingNoReeds"))) return;
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
		C->AddInstances(Out[Kind], false, true);
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
	for (int32 K = 0; K < 3; ++K) BuildingMeshes[K]->AddInstances(Lists[K], false, true);
}

bool ALakeTerrainActor::PlaceHouseModels(const FLakeData& Lake)
{
	// Visual V6 (Medium and High): each OSM footprint gets an archetype scaled to it (Tools/blender/build_houses.py): a
	// gable-roofed ranch for one storey, a hip-roofed two-storey, a flat-roofed block for the big footprints, with wall
	// (brick, siding, stucco) and roof colours from North Texas streets. Windows are drawn by M_HouseWall in world space.
	if (USailingSettings::Get()->Quality == ESailingQuality::Low) return false;
	// Graphics G6: the G2 houses (real footprints, lidar eaves and roofs, NAIP roof colours; WorldKit's HouseKit.cpp) replace
	// the archetypes below where the world has them (-SailingClassicHouses compares). The private docks stay.
	const bool bKitHouses = Lake.Houses.Num() > 0 && !FParse::Param(FCommandLine::Get(), TEXT("SailingClassicHouses"));
	if (bKitHouses)
	{
		TMap<FIntPoint, TArray<int32>> ByTile;
		HouseTiles(Lake, ByTile);
		TMap<FIntPoint, FKitGeometry> Tiles;
		int32 Procedural = 0;
		const FString Prefix = TEXT("Houses_") + Lake.FileName;
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
		I->NumCustomDataFloats = 10;
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
	for (const FNearKind& K : NearKinds) NearIsm.Add(MakeIsm(FString(TEXT("SM_HouseNear_")) + K.Name, 10, 6000.f));
	const bool bNear = !NearIsm.Contains(nullptr);
	if (bNear)
	{
		DockIsm[0] = MakeIsm(TEXT("SM_HouseNear_Dock"), 0, 3000.f);
		DockIsm[1] = MakeIsm(TEXT("SM_HouseNear_Boathouse"), 0, 3000.f);
	}
	TArray<FTransform> NearX[NumNear], DockX[2];
	TArray<float> NearD[NumNear];
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
					DockX[Which].Add(FTransform(FRotator(0, FMath::RadiansToDegrees(FMath::Atan2(WaterDir.Y, WaterDir.X)), 0), FVector(Shore.X, Shore.Y, 0.0) * CmPerMeter));
				}
			}
			continue;
		}
		if (bKitHouses) continue;
		X[Kind].Add(FTransform(FRotator(0, B.YawDeg, 0), FVector(B.X, B.Y, B.Ground) * CmPerMeter, FVector(B.Length, B.Width, Height)));
		D[Kind].Append({ Wall.R, Wall.G, Wall.B, float(Pat), Height, float((H >> 16) % 97) / 97.f, Roof.R, Roof.G, Roof.B, float(B.Ground) });
	}
	for (int32 K = 0; K < 3; ++K)
	{
		Ism[K]->AddInstances(X[K], false, true);
		for (int32 I = 0; I < X[K].Num(); ++I) Ism[K]->SetCustomData(I, TArrayView<const float>(&D[K][10 * I], 10), false);
		Ism[K]->MarkRenderStateDirty();
	}
	int32 NearCount = 0;
	for (int32 N = 0; N < NumNear && bNear; ++N)
	{
		NearIsm[N]->AddInstances(NearX[N], false, true);
		for (int32 I = 0; I < NearX[N].Num(); ++I) NearIsm[N]->SetCustomData(I, TArrayView<const float>(&NearD[N][10 * I], 10), false);
		NearIsm[N]->MarkRenderStateDirty();
		NearCount += NearX[N].Num();
	}
	for (int32 Which = 0; Which < 2; ++Which) if (DockIsm[Which]) DockIsm[Which]->AddInstances(DockX[Which], false, true);
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
		if (bShoreKit && (Dock.Kind == TEXT("breakwater") || bKitPiers)) continue;
		if (Dock.bClosed)
		{
			TArray<FVector2D> Pts = Dock.Points;
			Pts.Pop(); // closing point
			const TArray<int32> Ids = Triangulate(Pts);
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
	BridgeDecks->AddInstances(Decks, false, true);
	Pilings->AddInstances(Piles, false, true);
}
