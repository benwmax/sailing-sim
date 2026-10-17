#include "LandmarksActor.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "LakeData.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
#include "WorldKit.h"

using namespace Sailing;

TArray<FLandmarkPlacement> LandmarkPlacements(const TArray<FLandmark>& Landmarks)
{
	// Chart name -> model, its modelled height (m) and the height drawn when the chart gives none. Round 12: a generic
	// charted tower (CATLMK 17, no name) is a slim tower, the lattice mast at 45 m, not a water tower; Kemah's real water
	// tower comes from OpenStreetMap ("Water tower", build_galveston.py).
	struct FKind { const TCHAR* Chart; const TCHAR* Mesh; double Height; double Default; };
	static const FKind Kinds[] = {
		{ TEXT("Platform"), TEXT("SM_Landmark_Platform"), 8.6, 0.0 }, { TEXT("Water tower"), TEXT("SM_Landmark_WaterTower"), 41.6, 0.0 },
		{ TEXT("Tower"), TEXT("SM_Landmark_Mast"), 100.0, 45.0 },
		{ TEXT("Mast"), TEXT("SM_Landmark_Mast"), 100.0, 0.0 }, { TEXT("Windmill"), TEXT("SM_Landmark_Windmill"), 13.3, 0.0 },
		{ TEXT("Chimney"), TEXT("SM_Landmark_Stack"), 60.0, 0.0 }, { TEXT("Spire"), TEXT("SM_Landmark_Spire"), 30.0, 0.0 },
		{ TEXT("Flagstaff"), TEXT("SM_Landmark_Flagstaff"), 15.35, 0.0 }, { TEXT("Landmark"), TEXT("SM_Landmark_WaterTower"), 41.6, 0.0 },
	};
	// Round 12: the chart repeats a landmark in two cells, and near Kemah it charts one structure as two or three towers
	// 60-80 m apart: one of a kind is drawn within 100 m (platforms within 5 m: a gas field's wells stand closer than 100).
	struct FSeen { FVector2D P; const FKind* Kind; };
	TArray<FSeen> Seen;
	TArray<FLandmarkPlacement> Out;
	for (int32 I = 0; I < Landmarks.Num(); ++I)
	{
		const FLandmark& L = Landmarks[I];
		const FVector2D P(L.X, L.Y);
		const FKind* K = nullptr;
		for (const FKind& Candidate : Kinds) if (L.Name.StartsWith(Candidate.Chart)) { K = &Candidate; break; }
		if (!K) continue;
		const bool bPlatform = K == &Kinds[0];
		const double MergeM = bPlatform ? 5.0 : 100.0;
		if (Seen.ContainsByPredicate([&](const FSeen& Q) { return Q.Kind == K && FVector2D::DistSquared(P, Q.P) < MergeM * MergeM; })) continue;
		Seen.Add({ P, K });
		const double Drawn = L.Height > 1.0 ? L.Height : K->Default;
		FLandmarkPlacement& Pl = Out.AddDefaulted_GetRef();
		Pl.Index = I;
		Pl.Mesh = K->Mesh;
		Pl.Scale = Drawn > 1.0 && !bPlatform ? Drawn / K->Height : 1.0;
		Pl.bPlatform = bPlatform;
	}
	return Out;
}

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
	for (const FLandmarkPlacement& Pl : LandmarkPlacements(Lake.Landmarks))
	{
		const FLandmark& L = Lake.Landmarks[Pl.Index];
		TObjectPtr<UInstancedStaticMeshComponent>& Ism = Meshes.FindOrAdd(Pl.Mesh);
		if (!Ism)
		{
			UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Landmarks/%s.%s"), Pl.Mesh, Pl.Mesh));
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
		const double Ground = Pl.bPlatform ? 0.0 : FMath::Max(Lake.Terrain.HeightAt(L.X, L.Y), 0.0);
		const float Yaw = FMath::Frac(FMath::Sin(Pl.Index * 12.9898) * 43758.5453) * 360.f;
		Ism->AddInstance(FTransform(FRotator(0.f, Yaw, 0.f), FVector(L.X, L.Y, Ground) * CmPerMeter, FVector(Pl.Scale)));
		Instances.Add({ Ism, Ism->GetInstanceCount() - 1, FVector(L.X, L.Y, Ground), Yaw, float(Pl.Scale) });
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
