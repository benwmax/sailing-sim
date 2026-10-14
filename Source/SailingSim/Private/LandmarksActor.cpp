#include "LandmarksActor.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "LakeData.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
#include "WorldKit.h"

using namespace Sailing;

ALandmarksActor::ALandmarksActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 1.f;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void ALandmarksActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FLakeData& Lake = GM->GetLake();
	bTidal = Lake.Tides.HeightStations.size() > 0;
	RootComponent->SetMobility(EComponentMobility::Movable); // the tide and the curvature move them
	// Chart name -> model and its modelled height (m).
	struct FKind { const TCHAR* Chart; const TCHAR* Mesh; double Height; };
	static const FKind Kinds[] = {
		{ TEXT("Platform"), TEXT("SM_Landmark_Platform"), 8.6 }, { TEXT("Tower"), TEXT("SM_Landmark_WaterTower"), 41.6 },
		{ TEXT("Mast"), TEXT("SM_Landmark_Mast"), 100.0 }, { TEXT("Windmill"), TEXT("SM_Landmark_Windmill"), 13.3 },
		{ TEXT("Chimney"), TEXT("SM_Landmark_Stack"), 60.0 }, { TEXT("Spire"), TEXT("SM_Landmark_Spire"), 30.0 },
		{ TEXT("Flagstaff"), TEXT("SM_Landmark_Flagstaff"), 15.35 }, { TEXT("Landmark"), TEXT("SM_Landmark_WaterTower"), 41.6 },
	};
	TArray<FVector2D> Seen;
	for (int32 I = 0; I < Lake.Landmarks.Num(); ++I)
	{
		const FLandmark& L = Lake.Landmarks[I];
		const FVector2D P(L.X, L.Y);
		if (Seen.ContainsByPredicate([&](const FVector2D& Q) { return FVector2D::DistSquared(P, Q) < 25.0; })) continue; // charted in two cells
		Seen.Add(P);
		const FKind* K = nullptr;
		for (const FKind& Candidate : Kinds) if (L.Name.StartsWith(Candidate.Chart)) { K = &Candidate; break; }
		if (!K) continue;
		TObjectPtr<UInstancedStaticMeshComponent>& Ism = Meshes.FindOrAdd(K->Mesh);
		if (!Ism)
		{
			UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Landmarks/%s.%s"), K->Mesh, K->Mesh));
			if (!Mesh) continue;
			Ism = NewObject<UInstancedStaticMeshComponent>(this);
			Ism->SetMobility(RootComponent->Mobility);
			Ism->SetupAttachment(RootComponent);
			Ism->SetStaticMesh(Mesh);
			Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Ism->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
			Ism->SetCullDistances(0, 30000 * 100);
			Ism->RegisterComponent();
		}
		// Platforms stand in the water (the datum is the water's chart datum on a coast); the rest stand on the ground.
		const bool bPlatform = FCString::Strcmp(K->Mesh, TEXT("SM_Landmark_Platform")) == 0;
		const double Ground = bPlatform ? 0.0 : FMath::Max(Lake.Terrain.HeightAt(L.X, L.Y), 0.0);
		const double Scale = L.Height > 1.0 && !bPlatform ? L.Height / K->Height : 1.0;
		const float Yaw = FMath::Frac(FMath::Sin(I * 12.9898) * 43758.5453) * 360.f;
		Ism->AddInstance(FTransform(FRotator(0.f, Yaw, 0.f), FVector(L.X, L.Y, Ground) * CmPerMeter, FVector(Scale)));
		Instances.Add({ Ism, Ism->GetInstanceCount() - 1, FVector(L.X, L.Y, Ground), Yaw, float(Scale) });
		++Placed;
	}
	UE_LOG(LogSailing, Display, TEXT("Landmarks: %d of %d placed with %d models"), Placed, Lake.Landmarks.Num(), Meshes.Num());
}

void ALandmarksActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (bTidal)
	{
		const double Z = FMath::RoundToDouble(-GM->GetTideHeight() / 0.02) * 0.02 * CmPerMeter;
		if (!FMath::IsNearlyEqual(GetActorLocation().Z, Z, 0.1)) SetActorLocation(FVector(0.0, 0.0, Z));
	}
	// Far landmarks sink with the earth's curvature (a tower's foot goes below the horizon before its top): placed again
	// when the camera has moved 200 m.
	FVector Camera = FVector::ZeroVector;
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0)) Camera = Cam->GetCameraLocation() / CmPerMeter;
	if (FVector2D::Distance(FVector2D(Camera), CurvedFrom) < 200.0) return;
	CurvedFrom = FVector2D(Camera);
	TSet<UInstancedStaticMeshComponent*> Dirty;
	for (const FInstance& I : Instances)
	{
		const double Drop = CurvatureDrop(FVector2D::Distance(FVector2D(I.Base), CurvedFrom));
		I.Ism->UpdateInstanceTransform(I.Index, FTransform(FRotator(0.f, I.Yaw, 0.f), (I.Base - FVector(0.0, 0.0, Drop)) * CmPerMeter, FVector(I.Scale)), false, false, true);
		Dirty.Add(I.Ism);
	}
	for (UInstancedStaticMeshComponent* Ism : Dirty) Ism->MarkRenderStateDirty();
}
