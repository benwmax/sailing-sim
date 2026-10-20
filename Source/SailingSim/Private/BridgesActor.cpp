#include "BridgesActor.h"
#include "SailingFrame.h"
#include "BenchRunner.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "LakeData.h"
#include "WorldKit.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "SailingSettings.h"

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
	// On a coast the structures stand on the bottom: they follow the terrain's tide offset (Tick), so they move.
	bTidal = Lake.Tides.HeightStations.size() > 0;
	const EComponentMobility::Type Mobility = bTidal ? EComponentMobility::Movable : EComponentMobility::Static;
	RootComponent->SetMobility(Mobility);
	const bool bProcedural = FParse::Param(SailingArgs::Dev(), TEXT("SailingProceduralWorld"));
	FKitGeometry All, Shore;
	BuildBridgeGeometry(Lake, All);
	BuildShoreGeometry(Lake, Shore);
	TMap<FIntPoint, FKitGeometry> Tiles, ShoreTiles;
	All.SplitTiles(UWorldKitLibrary::BridgeTileM, Tiles);
	Shore.SplitTiles(UWorldKitLibrary::ShoreTileM, ShoreTiles);
	// World streaming: a composed world (the Texas coast) uses its frame member's baked tiles (the same metres); its other
	// members' structures fall back to procedural tiles until they are baked for it (docs/world-streaming).
	const FString Kit = Lake.SourceFor(TEXT("kit"));
	const int32 Baked = SpawnKitTiles(this, Tiles, TEXT("Bridges_") + Kit, bProcedural, KitMaterial, Tiled, Mobility);
	const int32 ShoreBaked = SpawnKitTiles(this, ShoreTiles, TEXT("Shore_") + Kit, bProcedural, KitMaterial, Tiled, Mobility);
	BuildTraffic();
	// Graphics G2 (Medium and up): the riprap is boulders. The baked mound is only its core now (WorldKit.cpp); the
	// world kit's six limestone blocks are piled over it, five across every 1.2 m, each sized, tipped and turned.
	int32 Boulders = 0;
	if (USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		constexpr int32 NumRocks = 6;
		TArray<FTransform> RockX[NumRocks];
		const FBox2D MarinaBox = Lake.Marina.Bounds();
		// A coast has hundreds of kilometres of jetty and seawall (Galveston's put 950,000 boulders in the scene and the render
		// thread's visibility pass took 25 ms): there the blocks are bigger, three across every 3 m, and drawn to 1.5 km.
		const bool bCoast = Lake.IsCoast();
		const double Spacing = bCoast ? 3.0 : 1.2;
		const int32 Rows = bCoast ? 1 : 2;
		const float SizeScale = bCoast ? 1.6f : 1.f;
		uint32 Seed = 11;
		auto Rand = [&Seed]() { Seed ^= Seed << 13; Seed ^= Seed >> 17; Seed ^= Seed << 5; return (Seed & 0xFFFFFF) / float(0xFFFFFF); };
		TArray<FRiprapBand> Bands;
		for (const FLakeDock& D : Lake.Docks)
		{
			// Graphics G7: groins along the shore keep only their baked core (73 km of them in the G2 pack); jetties,
			// breakwaters and the Texas City Dike's edges get the boulders.
			if (D.Kind == TEXT("groin") || (MarinaBox.bIsValid && MarinaBox.IsInside(D.Points[0]))) continue;
			Bands.Reset();
			RiprapBands(D, Bands);
			for (const FRiprapBand& Band : Bands)
			{
				const float WScale = Band.HalfWidth / 3.2f, CScale = Band.Crest / 0.8f;
				const int32 BandRows = FMath::Clamp(FMath::RoundToInt32(Rows * WScale), Rows, Rows + 2);
				for (int32 I = 1; I < Band.Points.Num(); ++I)
				{
					const FVector2D A = Band.Points[I - 1], B = Band.Points[I];
					const double Len = FVector2D::Distance(A, B);
					if (Len < 0.5) continue;
					const FVector2D Dir = (B - A) / Len, Left(-Dir.Y, Dir.X);
					for (double T = 0.0; T < Len; T += Spacing)
					{
						for (int32 K = -BandRows; K <= BandRows; ++K)
						{
							const float Across = (K * (bCoast ? 2.0f : 1.3f) + (Rand() - 0.5f) * 0.7f) * WScale * Rows / FMath::Max(BandRows, 1);
							const float Crest = (1.4f * (1.f - FMath::Square(Across / (3.4f * WScale))) - 0.2f) * FMath::Max(CScale * 0.6f, 1.f);
							const FVector2D P = A + Dir * (T + (Rand() - 0.5f) * 0.8) + Left * Across;
							const float Size = (0.9f + 0.9f * Rand()) * SizeScale;
							const int32 Kind = FMath::Min(int32(Rand() * NumRocks), NumRocks - 1);
							RockX[Kind].Add(FTransform(FRotator((Rand() - 0.5f) * 50.f, Rand() * 360.f, (Rand() - 0.5f) * 50.f),
								FVector(P.X, P.Y, Crest - 0.3f * Size) * CmPerMeter, FVector(Size)));
						}
					}
				}
			}
		}
		for (int32 K = 0; K < NumRocks; ++K)
		{
			UStaticMesh* Rock = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Props/SM_Rock_%d.SM_Rock_%d"), K, K));
			if (!Rock || RockX[K].Num() == 0) continue;
			UHierarchicalInstancedStaticMeshComponent* C = NewObject<UHierarchicalInstancedStaticMeshComponent>(this);  // culled by cluster
			C->SetMobility(Mobility);
			C->SetupAttachment(RootComponent);
			C->SetStaticMesh(Rock);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->SetCullDistances(0, (bCoast ? 1500.f : 4000.f) * 100.f);
			C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
			// Perf 2: out of the ray-tracing scene, like the trees and reeds: Galveston's 324,000 boulders were gathered into
			// it every frame (5 fps of render thread on High, coast-day). Lumen's screen traces still see them.
			C->bVisibleInRayTracing = false;
			// Out of the distance-field scene too: every shift of the actor (each 2 cm of tide, each re-centre) re-sent all their
			// instances to it, 53 ms of render thread for the Texas coast's 380,000 (docs/recentre-hitch). High's Lumen traces
			// the ray-tracing scene, which they were never in; a Medium still showed no difference.
			C->bAffectDistanceFieldLighting = false;
			// The bounds are cached in the component's frame, not rebuilt from every instance whenever it moves, and there is no
			// navigation bounds pass over them either (8 ms of game thread at a re-centre).
			C->SetUseConservativeBounds(true);
			C->SetCanEverAffectNavigation(false);
			C->RegisterComponent();
			C->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), RockX[K]), false, true);
			Tiled.Add(C);
			Boulders += RockX[K].Num();
		}
	}
	UE_LOG(LogSailing, Display, TEXT("Riprap: %d boulders"), Boulders);
	UE_LOG(LogSailing, Display, TEXT("Bridges %s: %d ways, %d quads in %d tiles (%d baked), %d lanes, %d vehicles; shore %d quads in %d tiles (%d baked)"), *Lake.FileName,
		Lake.Bridges.Num(), All.NumQuads(), Tiles.Num(), Baked, Lanes.Num(), Vehicles.Num(), Shore.NumQuads(), ShoreTiles.Num(), ShoreBaked);
}

void ABridgesActor::BuildTraffic()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FLakeData& Lake = GM->GetLake();
	if (FParse::Param(SailingArgs::Dev(), TEXT("SailingNoBridgeTraffic"))) return;
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
	if (bTidal)
	{
		// Follow the terrain's tide offset in 2 cm steps (moving them every frame would keep invalidating their shadows).
		const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
		const double Z = FMath::RoundToDouble(-GM->GetTideHeight() / 0.02) * 0.02 * CmPerMeter;
		if (!GetActorLocation().Equals(SailingFrame::MapAnchor(GetWorld()) + FVector(0.0, 0.0, Z), 0.1)) SetActorLocation(SailingFrame::MapAnchor(GetWorld()) + FVector(0.0, 0.0, Z));
	}
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
			X.Add(FTransform(FRotator(0.f, float(FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X))), 0.f), SailingFrame::FromMapCm(GetWorld(), P)));
		}
		VehicleMeshes[K]->BatchUpdateInstancesTransforms(0, X, true, true, false);
	}
}
