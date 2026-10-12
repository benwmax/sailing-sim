#include "LakeTerrainActor.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "LakeData.h"
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
	constexpr int32 kChunkCells = 64;
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
		PlaceTrees();
	}
}

void ALakeTerrainActor::BeginPlay()
{
	Super::BeginPlay();
	const FLakeData* Lake = GetLake();
	if (!Lake)
	{
		return;
	}
	const FLakeTerrain& T = Lake->Terrain;
	ChunkRows = FMath::DivideAndRoundUp(T.GetRows() - 1, kChunkCells);
	ChunkCols = FMath::DivideAndRoundUp(T.GetCols() - 1, kChunkCells);
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

ALakeTerrainActor::FChunkMesh ALakeTerrainActor::BuildChunk(const FLakeData* Lake, int32 ChunkRow, int32 ChunkCol, int32 Step)
{
	// Runs on a worker thread: reads only the immutable lake data.
	FChunkMesh M;
	if (!Lake) return M;
	const FLakeTerrain& T = Lake->Terrain;
	const int32 N = kChunkCells / Step;
	const double Cell = T.GetCell();
	auto H = [&](int32 R, int32 C) { return T.NodeHeight(R, C); };
	const int32 R0 = ChunkRow * kChunkCells, C0 = ChunkCol * kChunkCells;

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
			M.Triangles.Append({ V0, V1, V2, V1, V3, V2 });
		}
	}
	// Skirts hide cracks between chunks at different levels of detail.
	auto AddSkirt = [&](int32 A, int32 B, bool bFlip)
	{
		// Copy first: adding an element of an array to itself can reallocate under the reference.
		const FVector VA = M.Vertices[A], VB = M.Vertices[B], NA = M.Normals[A], NB = M.Normals[B];
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

void ALakeTerrainActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (Chunks.Num() == 0) return;
	const FLakeData* Lake = GetLake();
	if (!Lake) return;

	FVector Cam = FVector::ZeroVector;
	if (APlayerCameraManager* CM = UGameplayStatics::GetPlayerCameraManager(this, 0)) Cam = CM->GetCameraLocation();
	const double CamX = Cam.X / CmPerMeter, CamY = Cam.Y / CmPerMeter;
	const FLakeTerrain& T = Lake->Terrain;
	const double ChunkSize = kChunkCells * T.GetCell();

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
		Ch.Future = Async(EAsyncExecution::ThreadPool, [Lake, Row, Col, Step]() { return BuildChunk(Lake, Row, Col, Step); });
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
		Ch.bBuilding = false;
	}
}

void ALakeTerrainActor::PlaceTrees()
{
	const FLakeData* Lake = GetLake();
	if (!Lake) return;
	const FLakeTerrain& T = Lake->Terrain;
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

	// Trees within about 1.5 km of the water (what you can see from the lake), from the density map.
	TArray<FTransform> Oak, Elm, Cedar, Trunk;
	const double Step = 20.0;
	const int32 Rows = int32(T.GetRows() * T.GetCell() / Step), Cols = int32(T.GetCols() * T.GetCell() / Step);
	// Coarse water proximity: 100 m cells within 15 cells of water.
	const int32 CR = Rows / 5 + 1, CC = Cols / 5 + 1;
	TArray<uint8> NearWater;
	NearWater.SetNumZeroed(CR * CC);
	for (int32 R = 0; R < CR; ++R)
		for (int32 C = 0; C < CC; ++C)
			if (T.HeightAt(T.GetOriginX() + (R + 0.5) * 100.0, T.GetOriginY() + (C + 0.5) * 100.0) < 0.0)
				for (int32 DR = -15; DR <= 15; ++DR)
					for (int32 DC = -15; DC <= 15; ++DC)
						if (R + DR >= 0 && R + DR < CR && C + DC >= 0 && C + DC < CC && DR * DR + DC * DC <= 225) NearWater[(R + DR) * CC + C + DC] = 1;

	for (int32 R = 0; R < Rows; ++R)
	{
		for (int32 C = 0; C < Cols; ++C)
		{
			if (!NearWater[(R / 5) * CC + C / 5]) continue;
			const double X = T.GetOriginX() + (R + 0.5) * Step, Y = T.GetOriginY() + (C + 0.5) * Step;
			const double Density = T.CanopyAt(X, Y) / 12.0 * TreeFraction;
			const uint32 Seed = uint32(R * 92821 + C * 68917);
			const int32 Count = int32(Density * 1.6 + Rand01(Seed));
			for (int32 K = 0; K < Count; ++K)
			{
				const double PX = X + (Rand01(Seed + K * 13 + 1) - 0.5) * Step, PY = Y + (Rand01(Seed + K * 13 + 2) - 0.5) * Step;
				const double Ground = T.HeightAt(PX, PY);
				if (Ground < 0.8) continue;
				const float Kind = Rand01(Seed + K * 13 + 3);
				const float Height = 6.f + 8.f * Rand01(Seed + K * 13 + 4);
				const FVector Base(PX * CmPerMeter, PY * CmPerMeter, Ground * CmPerMeter);
				if (Kind < 0.3f)
				{
					Cedar.Add(FTransform(FRotator::ZeroRotator, Base + FVector(0, 0, Height * 50.f), FVector(Height * 0.35f, Height * 0.35f, Height)));
				}
				else
				{
					const float W = Height * (Kind < 0.75f ? 0.9f : 0.7f);
					(Kind < 0.75f ? Oak : Elm).Add(FTransform(FRotator::ZeroRotator, Base + FVector(0, 0, Height * 60.f), FVector(W, W, Height * 0.7f)));
					Trunk.Add(FTransform(FRotator::ZeroRotator, Base + FVector(0, 0, Height * 20.f), FVector(0.4f, 0.4f, Height * 0.4f)));
				}
			}
		}
	}
	TreeMeshes[0]->AddInstances(Oak, false, true);
	TreeMeshes[1]->AddInstances(Elm, false, true);
	TreeMeshes[2]->AddInstances(Cedar, false, true);
	TreeMeshes[3]->AddInstances(Trunk, false, true);
	UE_LOG(LogSailing, Display, TEXT("Trees: %d post oak, %d cedar elm, %d red cedar"), Oak.Num(), Elm.Num(), Cedar.Num());
}

void ALakeTerrainActor::PlaceBuildings()
{
	const FLakeData* Lake = GetLake();
	if (!Lake) return;
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
	for (int32 K = 0; K < Lake->Buildings.Num(); ++K)
	{
		const FLakeBuilding& B = Lake->Buildings[K];
		Lists[Hash(K) % 3].Add(FTransform(FRotator(0, B.YawDeg, 0), FVector(B.X, B.Y, B.Ground + B.Height * 0.5) * CmPerMeter, FVector(B.Length, B.Width, B.Height)));
	}
	for (int32 K = 0; K < 3; ++K) BuildingMeshes[K]->AddInstances(Lists[K], false, true);
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
	for (const FLakeBridge& Br : Lake->Bridges)
	{
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
	for (const FLakeDock& Dock : Lake->Docks)
	{
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
