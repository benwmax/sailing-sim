#include "BridgesActor.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "LakeData.h"
#include "WorldKit.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"

using namespace Sailing;

namespace
{
	uint32 BHash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return X;
	}
	float BRand(uint32& Seed) { Seed = BHash(Seed + 0x9e3779b9U); return (Seed & 0xFFFFFF) / float(0xFFFFFF); }

	bool OneWay(const FString& Kind)
	{
		return Kind == TEXT("motorway") || Kind == TEXT("motorway_link") || Kind == TEXT("construction") || Kind == TEXT("trunk") || Kind == TEXT("trunk_link");
	}
}

ABridgesActor::ABridgesActor()
{
	PrimaryActorTick.bCanEverTick = true;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent->SetMobility(EComponentMobility::Static);
}

void ABridgesActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !GM->GetLake().IsLoaded()) return;
	const FLakeData& Lake = GM->GetLake();
	FKitGeometry All;
	BuildBridgeGeometry(Lake, All);
	TMap<FIntPoint, FKitGeometry> Tiles;
	All.SplitTiles(UWorldKitLibrary::BridgeTileM, Tiles);
	const int32 Baked = SpawnKitTiles(this, Tiles, TEXT("Bridges_") + Lake.FileName, FParse::Param(FCommandLine::Get(), TEXT("SailingProceduralWorld")), KitMaterial, Tiled);
	BuildTraffic();
	UE_LOG(LogSailing, Display, TEXT("Bridges %s: %d ways, %d quads in %d tiles (%d baked), %d lanes, %d vehicles"), *Lake.FileName, Lake.Bridges.Num(), All.NumQuads(), Tiles.Num(), Baked,
		Lanes.Num(), Vehicles.Num());
}

void ABridgesActor::BuildTraffic()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FLakeData& Lake = GM->GetLake();
	if (FParse::Param(FCommandLine::Get(), TEXT("SailingNoBridgeTraffic"))) return;
	for (const FLakeBridge& Br : Lake.Bridges)
	{
		const float Road = BridgeWidth(Br);
		if (Br.Kind.IsEmpty() || Road == 0.f) continue; // charted bridges: no idea what they carry
		const int32 N = FMath::Max(1, int32(Road / 3.6f));
		const bool bOneWay = OneWay(Br.Kind);
		const float Speed = Br.Kind.StartsWith(TEXT("motorway")) || Br.Kind == TEXT("construction") ? 29.f : (Br.Kind == TEXT("primary") ? 22.f : 17.f);
		for (int32 L = 0; L < N; ++L)
		{
			// Lanes from the right edge (U = 0 in the asphalt's markings); on two-way roads the left half runs back.
			const double Off = -0.5 * Road + 0.6 + 3.6 * (L + 0.5);
			const bool bBack = !bOneWay && L >= N / 2 && N > 1;
			FLane Lane;
			Lane.Speed = Speed * (0.92f + 0.04f * L);
			const int32 P = Br.Points.Num();
			for (int32 I = 0; I < P; ++I)
			{
				const FVector2D Prev = Br.Points[FMath::Max(I - 1, 0)], Next = Br.Points[FMath::Min(I + 1, P - 1)];
				const FVector2D Dir = (Next - Prev).GetSafeNormal(), Left(-Dir.Y, Dir.X);
				const FVector2D Q = Br.Points[I] + Left * Off;
				Lane.Points.Add(FVector(Q.X, Q.Y, BridgeRoadZ(Br)) * CmPerMeter);
			}
			if (bBack) Algo::Reverse(Lane.Points);
			Lane.Cum.Add(0.0);
			for (int32 I = 1; I < Lane.Points.Num(); ++I) Lane.Cum.Add(Lane.Cum.Last() + FVector::Dist(Lane.Points[I - 1], Lane.Points[I]));
			if (Lane.Cum.Last() < 2000.0) continue;
			Lanes.Add(MoveTemp(Lane));
		}
	}
	// Sparse: a vehicle every 90 to 300 m in each lane; most are cars, some pickups, a few semis.
	static const TCHAR* Kinds[] = { TEXT("/Game/World/Vehicles/SM_Car_0.SM_Car_0"), TEXT("/Game/World/Vehicles/SM_Pickup_0.SM_Pickup_0"), TEXT("/Game/World/Vehicles/SM_Semi_0.SM_Semi_0") };
	static const FLinearColor Paint[] = { FLinearColor(0.80f, 0.80f, 0.78f), FLinearColor(0.02f, 0.02f, 0.02f), FLinearColor(0.45f, 0.46f, 0.47f), FLinearColor(0.18f, 0.18f, 0.19f),
		FLinearColor(0.45f, 0.03f, 0.02f), FLinearColor(0.03f, 0.08f, 0.25f), FLinearColor(0.70f, 0.70f, 0.70f), FLinearColor(0.06f, 0.12f, 0.08f) };
	TArray<UStaticMesh*> Meshes;
	for (const TCHAR* K : Kinds) Meshes.Add(LoadObject<UStaticMesh>(nullptr, K));
	if (Meshes.Contains(nullptr)) return;
	KindVehicles.SetNum(UE_ARRAY_COUNT(Kinds));
	TArray<TArray<float>> Custom;
	Custom.SetNum(UE_ARRAY_COUNT(Kinds));
	uint32 Seed = 12345;
	for (int32 L = 0; L < Lanes.Num(); ++L)
	{
		for (double S = BRand(Seed) * 15000.0; S < Lanes[L].Cum.Last(); S += 9000.0 + 21000.0 * BRand(Seed))
		{
			const float R = BRand(Seed);
			FVehicle V;
			V.Lane = L;
			V.S = S;
			V.Kind = R < 0.68f ? 0 : (R < 0.9f ? 1 : 2);
			KindVehicles[V.Kind].Add(Vehicles.Num());
			const FLinearColor C = V.Kind == 2 ? Paint[BHash(Seed) % 4] : Paint[BHash(Seed) % UE_ARRAY_COUNT(Paint)];
			Custom[V.Kind].Append({ C.R, C.G, C.B });
			Vehicles.Add(V);
		}
	}
	for (int32 K = 0; K < Meshes.Num(); ++K)
	{
		UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
		C->SetMobility(EComponentMobility::Movable);
		C->SetupAttachment(RootComponent);
		C->SetStaticMesh(Meshes[K]);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCullDistances(0, 4000 * 100);
		C->NumCustomDataFloats = 3;
		C->RegisterComponent();
		TArray<FTransform> X;
		X.Init(FTransform::Identity, KindVehicles[K].Num());
		C->AddInstances(X, false, true);
		for (int32 I = 0; I < KindVehicles[K].Num(); ++I)
		{
			C->SetCustomData(I, TArrayView<const float>(&Custom[K][3 * I], 3), false);
		}
		VehicleMeshes.Add(C);
	}
}

void ABridgesActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (VehicleMeshes.Num() == 0) return;
	const float Dt = FMath::Min(DeltaSeconds, 0.1f);
	for (FVehicle& V : Vehicles)
	{
		const FLane& L = Lanes[V.Lane];
		V.S = FMath::Fmod(V.S + L.Speed * 100.0 * Dt, L.Cum.Last());
	}
	for (int32 K = 0; K < VehicleMeshes.Num(); ++K)
	{
		TArray<FTransform> X;
		X.Reserve(KindVehicles[K].Num());
		for (const int32 Index : KindVehicles[K])
		{
			const FVehicle& V = Vehicles[Index];
			const FLane& L = Lanes[V.Lane];
			const int32 I = FMath::Clamp(Algo::UpperBound(L.Cum, V.S), 1, L.Points.Num() - 1);
			const double T = (V.S - L.Cum[I - 1]) / FMath::Max(L.Cum[I] - L.Cum[I - 1], 1.0);
			const FVector P = FMath::Lerp(L.Points[I - 1], L.Points[I], T);
			const FVector D = L.Points[I] - L.Points[I - 1];
			X.Add(FTransform(FRotator(0.f, float(FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X))), 0.f), P));
		}
		VehicleMeshes[K]->BatchUpdateInstancesTransforms(0, X, true, true, false);
	}
}
