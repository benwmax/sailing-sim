#include "CoastMarinasActor.h"
#include "SailingSim.h"
#include "LakeData.h"
#include "MarinaActor.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "WorldKit.h"
#include "Components/InstancedStaticMeshComponent.h"

ACoastMarinasActor::ACoastMarinasActor()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent->SetMobility(EComponentMobility::Static);
}

void ACoastMarinasActor::PlaceBoats(const FLakeData& Lake, TArray<FBerthedBoat>& Out)
{
	using namespace Sailing;
	// Lengths overall of the berthed models (FBoatConfig::Make): J/22 6.86 m, Catalina 22 6.71, Catalina 30 9.14; the
	// runabout is 6.4 m and the trawler yacht 11 m (build_vessels.py).
	for (const FMooredBoat& M : Lake.MooredBoats)
	{
		FBerthedBoat B;
		B.Center = M.Center;
		B.HeadingDeg = M.HeadingDeg;
		const uint32 H = uint32(M.Center.X * 13.0 + M.Center.Y * 7.0) * 2654435761u;
		float Model = 0.f;
		if (M.bMast)
		{
			if (M.Length < 7.8f) { B.Type = (H >> 7) & 1 ? uint8(EBoatType::J22) : uint8(EBoatType::Catalina22); Model = B.Type == uint8(EBoatType::J22) ? 6.86f : 6.71f; }
			else { B.Type = uint8(EBoatType::Catalina30); Model = 9.14f; }
		}
		else if (M.Length < 9.5f) { B.Type = FBerthedBoat::PowerBoat; Model = 6.4f; }
		else { B.Type = FBerthedBoat::PowerYacht; Model = 11.f; }
		B.Scale = FMath::Clamp(M.Length / Model, 0.75f, 1.6f);
		Out.Add(B);
	}
}

void ACoastMarinasActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !GM->GetLake().IsLoaded()) return;
	const FLakeData& Lake = GM->GetLake();
	TArray<FBerthedBoat> Placed;
	PlaceBoats(Lake, Placed);
	SpawnBerthedBoats(this, RootComponent, Placed, 1.f, EComponentMobility::Static, Boats);
	// The floating walkways and fingers: decking on floats, 0.45 m above the water like the club's (AMarinaActor).
	FKitGeometry G;
	int32 Count = 0;
	for (const FLakeDock& D : Lake.Docks)
	{
		if (D.Kind != TEXT("floating")) continue;
		++Count;
		const float W = D.Width > 0.f ? D.Width : 1.8f;
		for (int32 I = 1; I < D.Points.Num(); ++I)
		{
			G[EKitLook::Decking].Span(D.Points[I - 1], D.Points[I], W, AMarinaActor::FloatingDeckHeight - 0.12f, AMarinaActor::FloatingDeckHeight, true);
			G[EKitLook::Floats].Span(D.Points[I - 1], D.Points[I], W * 0.85f, -0.25f, AMarinaActor::FloatingDeckHeight - 0.12f, true);
		}
	}
	if (Count)
	{
		TMap<FIntPoint, FKitGeometry> Tiles;
		G.SplitTiles(UWorldKitLibrary::ShoreTileM, Tiles);
		SpawnKitTiles(this, Tiles, TEXT("Walkways_") + Lake.FileName, true, KitMaterial, Walkways, EComponentMobility::Static);
	}
	UE_LOG(LogSailing, Display, TEXT("Coast marinas: %d moored boats in %d instanced meshes, %d floating walkways"), Placed.Num(), Boats.Num(), Count);
}
