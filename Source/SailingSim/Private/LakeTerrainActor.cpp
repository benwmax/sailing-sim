#include "LakeTerrainActor.h"
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

using namespace Sailing;

namespace
{
	// Cells per chunk side: 64, or 128 on grids of 10 m or coarser (Galveston Bay: 1,000 chunks instead of 4,000;
	// culling every chunk each frame cost 4 ms of render thread).
	int32 GChunkCells = 64;
	// Leaf-card trees within this; opaque crowns beyond (Visual V6). -SailingNearTrees=<m> to measure.
	double NearTreesM()
	{
		// 600 m on High; 350 m on Medium, where the base pass is budgeted at 4 ms (cards within 300 m cost almost nothing,
		// out to 600 m about a millisecond there; the opaque crowns read the same at that size on its 67% resolution).
		static const double M = []
		{
			double V = USailingSettings::Get()->Quality >= ESailingQuality::High ? 600.0 : 350.0;
			FParse::Value(FCommandLine::Get(), TEXT("SailingNearTrees="), V);
			return V;
		}();
		return M;
	}
	constexpr int32 kMaxBuildsInFlight = 4;
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
	PlaceBuildings();
	PlaceBridgesAndDocks();
	bTreesPlaced = true;
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
	const int32 N = GChunkCells / Step;
	const double Cell = T.GetCell();
	auto H = [&](int32 R, int32 C) { return T.NodeHeight(R, C); };
	const int32 R0 = ChunkRow * GChunkCells, C0 = ChunkCol * GChunkCells;

	M.Vertices.Reserve((N + 1) * (N + 1) + 4 * (N + 1));
	for (int32 I = 0; I <= N; ++I)
	{
		for (int32 J = 0; J <= N; ++J)
		{
			const int32 R = FMath::Min(R0 + I * Step, T.GetRows() - 1), C = FMath::Min(C0 + J * Step, T.GetCols() - 1);
			const double Z = H(R, C);
			M.Vertices.Add(FVector(T.GetOriginX() + R * Cell, T.GetOriginY() + C * Cell, Z) * CmPerMeter);
			const double DZX = (H(R + Step, C) - H(R - Step, C)) / (2.0 * Step * Cell);
			const double DZY = (H(R, C + Step) - H(R, C - Step)) / (2.0 * Step * Cell);
			const FVector Nrm = FVector(-DZX, -DZY, 1.0).GetSafeNormal();
			M.Normals.Add(Nrm);
			// Texas cross-timbers colors: muddy lake bed, red-brown clay and sand at the waterline, rock on steep
			// banks, dry grass above, darker under woods.
			const double Slope = 1.0 - Nrm.Z;
			const double Canopy = T.CanopyAt(T.GetOriginX() + R * Cell, T.GetOriginY() + C * Cell) / 12.0;
			const float Noise = 0.9f + 0.2f * Rand01(uint32(R * 7919 + C * 104729));
			FLinearColor Col;
			if (Z < -0.3) Col = FLinearColor(0.20f, 0.17f, 0.12f);
			else if (Z < 0.6) Col = FMath::Lerp(FLinearColor(0.42f, 0.30f, 0.20f), FLinearColor(0.50f, 0.42f, 0.30f), float(Rand01(uint32(R * 31 + C * 17))));
			else Col = FMath::Lerp(FLinearColor(0.36f, 0.36f, 0.16f), FLinearColor(0.16f, 0.22f, 0.08f), float(Canopy));
			if (Slope > 0.08) Col = FMath::Lerp(Col, FLinearColor(0.40f, 0.33f, 0.27f), float(FMath::Clamp((Slope - 0.08) * 6.0, 0.0, 1.0)));
			M.Colors.Add(Col * Noise);
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
	if (TreeModels.Num() == 0 || ModelTrees.Num() == 0 || FVector2D::Distance(Camera, TreeCenter) < 0.25 * NearTreesM()) return;
	TreeCenter = Camera;
	TArray<TArray<FTransform>> Near, Far;
	Near.SetNum(TreeModels.Num());
	Far.SetNum(TreeFar.Num());
	const double R2 = FMath::Square(NearTreesM());
	for (const FTreeInstance& I : ModelTrees)
	{
		const int32 Index = int32(I.Species) * 2 + I.Variant;
		const bool bNear = FVector2D::DistSquared(I.Position, Camera) < R2;
		UStaticMesh* Mesh = (bNear ? TreeModels : TreeFar)[Index]->GetStaticMesh();
		const float MeshHeight = Mesh ? FMath::Max(100.f, float(Mesh->GetBounds().BoxExtent.Z * 2.0)) : 1000.f;
		const float Scale = I.Height * CmPerMeter / MeshHeight;
		// The earth's curvature (as M_Terrain's offset does for the ground): far trees sink with the shore they stand on.
		const double Drop = CurvatureDrop(FVector2D::Distance(I.Position, Camera));
		(bNear ? Near : Far)[Index].Add(FTransform(FRotator(0.f, I.Yaw, 0.f), FVector(I.Position.X * CmPerMeter, I.Position.Y * CmPerMeter, (I.Ground - Drop) * CmPerMeter), FVector(Scale)));
	}
	for (int32 M = 0; M < TreeModels.Num(); ++M)
	{
		TreeModels[M]->ClearInstances();
		TreeModels[M]->AddInstances(Near[M], false, true);
		TreeFar[M]->ClearInstances();
		TreeFar[M]->AddInstances(Far[M], false, true);
	}
}

void ALakeTerrainActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
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
	PlaceTreeInstances(T, TreeFraction, Trees);

	// Visual V6 (Medium and High): Nanite trees built in Blender (four species, two variants each), swaying in the wind
	// (M_TreeLeaves / M_TreeBark read MPC_World). Low keeps the Phase 3 shapes.
	static const TCHAR* SpeciesNames[] = { TEXT("LiveOak"), TEXT("PostOak"), TEXT("CedarElm"), TEXT("RedCedar") };
	const bool bModelTrees = USailingSettings::Get()->Quality != ESailingQuality::Low;
	if (bModelTrees && TreeModels.Num() == 0)
	{
		for (int32 Pass = 0; Pass < 2; ++Pass)
		{
			for (int32 S = 0; S < int32(ETreeSpecies::Count); ++S)
			{
				for (int32 V = 0; V < 2; ++V)
				{
					const FString Name = FString::Printf(TEXT("SM_%s_%d%s"), SpeciesNames[S], V, Pass == 1 ? TEXT("_Far") : TEXT(""));
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
					C->SetCastShadow(true);
					C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
					C->SetCullDistances(0, (Pass == 0 ? NearTreesM() + 200.0 : 9000.0) * 100.0);
					C->SetWorldPositionOffsetDisableDistance(int32((Pass == 0 ? NearTreesM() : 1500.0) * 100.0));
					C->RegisterComponent();
					(Pass == 0 ? TreeModels : TreeFar).Add(C);
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
			const float W = Height * (bOak ? 0.9f : 0.7f);
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
		X[Kind].Add(FTransform(FRotator(0, B.YawDeg, 0), FVector(B.X, B.Y, B.Ground) * CmPerMeter, FVector(B.Length, B.Width, Height)));
		const int32 Pat = Kind == 2 ? 2 : int32((H >> 4) % 3);
		const FLinearColor Wall = Pat == 0 ? Brick[(H >> 8) % UE_ARRAY_COUNT(Brick)] : Light[(H >> 8) % UE_ARRAY_COUNT(Light)];
		const FLinearColor Roof = Roofs[(H >> 12) % UE_ARRAY_COUNT(Roofs)];
		D[Kind].Append({ Wall.R, Wall.G, Wall.B, float(Pat), Height, float((H >> 16) % 97) / 97.f, Roof.R, Roof.G, Roof.B, float(B.Ground) });
	}
	for (int32 K = 0; K < 3; ++K)
	{
		Ism[K]->AddInstances(X[K], false, true);
		for (int32 I = 0; I < X[K].Num(); ++I) Ism[K]->SetCustomData(I, TArrayView<const float>(&D[K][10 * I], 10), false);
		Ism[K]->MarkRenderStateDirty();
	}
	UE_LOG(LogSailing, Display, TEXT("Buildings: %d ranch, %d two-storey, %d blocks"), X[0].Num(), X[1].Num(), X[2].Num());
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
