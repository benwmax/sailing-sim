#include "NightLightsActor.h"
#include "SailingFrame.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingEnvironment.h"
#include "LakeData.h"
#include "Marina.h"
#include "MarinaActor.h"
#include "VisualPipeline.h"
#include "Components/PointLightComponent.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include <algorithm>

using namespace Sailing;

namespace
{
	struct FLightKind { float Lumens; FLinearColor Color; float RadiusM; };
	// Street lamps: 12,000 lm LED cobra heads (3000 K); dock lamps: 1,500 lm bollards; floodlights: 4,000 lm;
	// a waterfront business: its signs, patios and parking lights lumped into 6,000 lm, warmer.
	const FLightKind Kinds[] = {
		{ 12000.f, FLinearColor(1.0f, 0.80f, 0.60f), 40.f }, { 1500.f, FLinearColor(1.0f, 0.84f, 0.68f), 14.f },
		{ 4000.f, FLinearColor(1.0f, 0.90f, 0.80f), 25.f }, { 6000.f, FLinearColor(1.0f, 0.72f, 0.48f), 35.f },
	};
}

ANightLightsActor::ANightLightsActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.25f;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void ANightLightsActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FLakeData& Lake = GM->GetLake();
	bTidal = Lake.Tides.HeightStations.size() > 0;
	FKitGeometry Kit;
	BuildBridgeGeometry(Lake, Kit);
	if (Lake.Marina.IsLoaded()) AMarinaActor::BuildGeometry(Lake.Marina, &Lake.Terrain, [](const FString&) { return true; }, Kit);
	Fixtures = MoveTemp(Kit.Lights);
	// Waterfront businesses: the big blocks within 80 m of the water, a light on the side toward it.
	for (const FLakeBuilding& B : Lake.Buildings)
	{
		if (B.Length * B.Width < 600.0) continue;
		for (int32 K = 0; K < 8; ++K)
		{
			const double A = K * UE_PI / 4.0;
			const FVector2D P(B.X + 80.0 * FMath::Cos(A), B.Y + 80.0 * FMath::Sin(A));
			if (Lake.Terrain.HeightAt(P.X, P.Y) < -0.5)
			{
				const FVector2D Front = FVector2D(B.X, B.Y) + (P - FVector2D(B.X, B.Y)).GetSafeNormal() * (0.5 * FMath::Max(B.Length, B.Width) + 4.0);
				Fixtures.Add({ FVector(Front.X, Front.Y, B.Ground + 5.0), 3 });
				break;
			}
		}
	}
	const bool bHigh = USailingSettings::Get()->Quality >= ESailingQuality::High;
	const int32 N = FMath::Min(Fixtures.Num(), bHigh ? 160 : 48);
	for (int32 I = 0; I < N; ++I)
	{
		UPointLightComponent* L = NewObject<UPointLightComponent>(this);
		L->SetMobility(EComponentMobility::Movable);
		L->SetupAttachment(RootComponent);
		L->SetIntensityUnits(ELightUnits::Lumens);
		L->SetCastShadows(bHigh);         // shadowed through MegaLights on High
		L->SetSourceRadius(float(0.15 * CmPerMeter));
		L->SetVisibility(false);
		L->RegisterComponent();
		Pool.Add(L);
	}
	UE_LOG(LogSailing, Display, TEXT("Night lights: %d fixtures, a pool of %d"), Fixtures.Num(), Pool.Num());
}

void ANightLightsActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || Pool.Num() == 0) return;
	float Night = 0.f;
	for (TActorIterator<ASailingEnvironment> It(GetWorld()); It; ++It) Night = It->GetNightAmount();
	const double TideZ = bTidal ? -GM->GetTideHeight() * CmPerMeter : 0.0;
	if (Night < 0.25f)
	{
		if (Lit > 0) for (UPointLightComponent* L : Pool) L->SetVisibility(false);
		Lit = 0;
		return;
	}
	FVector Camera = FVector::ZeroVector;
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0)) Camera = SailingFrame::ToMapCm(GetWorld(), Cam->GetCameraLocation()) / CmPerMeter;
	// The nearest fixtures get the pool (a partial sort; a few thousand fixtures at 4 Hz).
	TArray<TPair<double, int32>> Near;
	Near.Reserve(Fixtures.Num());
	for (int32 I = 0; I < Fixtures.Num(); ++I) Near.Add({ FVector::DistSquared(Fixtures[I].Position, Camera), I });
	const int32 N = FMath::Min(Pool.Num(), Near.Num());
	std::nth_element(Near.GetData(), Near.GetData() + (N - 1), Near.GetData() + Near.Num(), [](const TPair<double, int32>& A, const TPair<double, int32>& B) { return A.Key < B.Key; });
	const float Scale = float(FMath::Pow(2.0, -SceneEVOffset())) * FMath::Clamp((Night - 0.25f) / 0.35f, 0.f, 1.f);
	for (int32 I = 0; I < N; ++I)
	{
		const FKitLight& F = Fixtures[Near[I].Value];
		const FLightKind& K = Kinds[F.Kind];
		UPointLightComponent* L = Pool[I];
		L->SetWorldLocation(SailingFrame::FromMapCm(GetWorld(), F.Position * CmPerMeter) + FVector(0.0, 0.0, TideZ));
		L->SetIntensity(K.Lumens * Scale);
		L->SetLightColor(K.Color);
		L->SetAttenuationRadius(K.RadiusM * CmPerMeter);
		L->SetVisibility(true);
	}
	Lit = N;
}
