#include "SailingEnvironment.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "HAL/IConsoleManager.h"
#include "Misc/Parse.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

using namespace Sailing;

namespace
{
	constexpr float kCloudBaseKm = 1.4f;
}

ASailingEnvironment::ASailingEnvironment()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Rain(TEXT("/Game/Materials/M_Rain.M_Rain"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Emissive(TEXT("/Game/Materials/M_Emissive.M_Emissive"));

	auto MakeRain = [&](const TCHAR* Name, float RadiusM, float HeightM)
	{
		UStaticMeshComponent* C = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		C->SetupAttachment(RootComponent);
		C->SetStaticMesh(Cylinder.Object);
		C->SetMaterial(0, Rain.Object);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		C->SetRelativeScale3D(FVector(RadiusM * 2.f, RadiusM * 2.f, HeightM));
		C->SetVisibility(false);
		return C;
	};
	RainNear = MakeRain(TEXT("RainNear"), 4.f, 16.f);
	RainFar = MakeRain(TEXT("RainFar"), 14.f, 40.f);

	Bolt = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Bolt"));
	Bolt->SetupAttachment(RootComponent);
	Bolt->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Bolt->SetCastShadow(false);
	Bolt->SetMaterial(0, Emissive.Object);

	MoonLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("MoonLight"));
	MoonLight->SetupAttachment(RootComponent);
	MoonLight->SetIntensity(0.f);
	MoonLight->SetLightColor(FLinearColor(0.62f, 0.72f, 1.f));
	MoonLight->SetCastShadows(false);
	MoonLight->SetAtmosphereSunLight(true);
	MoonLight->SetAtmosphereSunLightIndex(1); // the atmosphere's second light: a dim blue night sky
	MoonLight->SetMobility(EComponentMobility::Movable);
	MoonLight->SetRelativeRotation(FRotator(-38.f, 140.f, 0.f));
	MoonLight->SetForwardShadingPriority(-1); // the sun stays the light for water, translucency and fog

	FlashLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("LightningFlash"));
	FlashLight->SetupAttachment(RootComponent);
	FlashLight->SetIntensity(0.f);
	FlashLight->SetLightColor(FLinearColor(0.8f, 0.85f, 1.f));
	FlashLight->SetCastShadows(false);
	FlashLight->SetAtmosphereSunLight(false);
	FlashLight->SetForwardShadingPriority(-2);
	FlashLight->SetMobility(EComponentMobility::Movable);
}

void ASailingEnvironment::SunPosition(double ClockHour, double DayOfYear, double LatitudeDeg, double LongitudeDeg, double UtcOffsetHours, double& OutElevation, double& OutAzimuth)
{
	// Equation of time (minutes, Spencer's short form): sundials run up to 16 minutes ahead of or behind the clock.
	const double B = 2.0 * kPi * (DayOfYear - 81.0) / 365.0;
	const double EquationOfTime = 9.87 * std::sin(2.0 * B) - 7.53 * std::cos(B) - 1.5 * std::sin(B);
	const double Hour = ClockHour - UtcOffsetHours + LongitudeDeg / 15.0 + EquationOfTime / 60.0;
	const double Lat = LatitudeDeg * kDegToRad;
	// Declination (Spencer's Fourier series, good to a few hundredths of a degree).
	const double G = 2.0 * kPi * (DayOfYear - 1.0) / 365.0;
	const double Decl = 0.006918 - 0.399912 * std::cos(G) + 0.070257 * std::sin(G) - 0.006758 * std::cos(2.0 * G)
		+ 0.000907 * std::sin(2.0 * G) - 0.002697 * std::cos(3.0 * G) + 0.00148 * std::sin(3.0 * G);
	const double HourAngle = (Hour - 12.0) * 15.0 * kDegToRad;
	const double SinEl = std::sin(Lat) * std::sin(Decl) + std::cos(Lat) * std::cos(Decl) * std::cos(HourAngle);
	OutElevation = std::asin(Clamp(SinEl, -1.0, 1.0)) * kRadToDeg;
	// Azimuth clockwise from north (+X): east in the morning, west in the afternoon.
	const double Az = std::atan2(std::sin(HourAngle), std::cos(HourAngle) * std::sin(Lat) - std::tan(Decl) * std::cos(Lat));
	OutAzimuth = std::fmod(Az * kRadToDeg + 180.0 + 360.0, 360.0);
}

void ASailingEnvironment::FindSceneActors()
{
	for (TActorIterator<ADirectionalLight> It(GetWorld()); It; ++It)
	{
		const UDirectionalLightComponent* Light = Cast<UDirectionalLightComponent>(It->GetLightComponent());
		if (Light && Light->IsUsedAsAtmosphereSunLight())
		{
			Sun = *It;
		}
	}
	if (TActorIterator<ASkyLight> It(GetWorld()); It) SkyLightActor = *It;
	if (TActorIterator<AExponentialHeightFog> It(GetWorld()); It) Fog = *It;
	if (TActorIterator<AVolumetricCloud> It(GetWorld()); It) Clouds = *It;
	if (TActorIterator<APostProcessVolume> It(GetWorld()); It) PostProcess = *It;

	if (Sun) SunIntensity = Sun->GetLightComponent()->Intensity;
	if (Sun) if (UDirectionalLightComponent* SunDir = Cast<UDirectionalLightComponent>(Sun->GetLightComponent())) SunDir->SetForwardShadingPriority(1);
	if (SkyLightActor) SkyIntensity = SkyLightActor->GetLightComponent()->Intensity;
	if (Clouds)
	{
		UVolumetricCloudComponent* CloudComp = Clouds->FindComponentByClass<UVolumetricCloudComponent>();
		if (CloudComp && CloudComp->GetMaterial())
		{
			CloudMaterial = UMaterialInstanceDynamic::Create(CloudComp->GetMaterial(), this);
			CloudComp->SetMaterial(CloudMaterial);
		}
	}
}

void ASailingEnvironment::BeginPlay()
{
	Super::BeginPlay();
	FindSceneActors();
	RainMaterial = RainNear->CreateAndSetMaterialInstanceDynamic(0);
	RainFar->SetMaterial(0, RainMaterial);
	BoltMaterial = Bolt->CreateAndSetMaterialInstanceDynamic(0);
	if (BoltMaterial)
	{
		BoltMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.85f, 0.9f, 1.f));
	}

	// Skip strikes that already happened if the weather starts partway through.
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		const double T = GM->GetWeatherTime();
		const auto& Strikes = GM->GetWeather().GetStrikes();
		while (NextStrike < int32(Strikes.size()) && Strikes[NextStrike].Time < T) ++NextStrike;
	}
}

void ASailingEnvironment::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM)
	{
		return;
	}
	FVector CamPos = FVector::ZeroVector;
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		CamPos = Cam->GetCameraLocation();
	}
	const FWeatherState& W = GM->GetWeatherState();
	UpdateSun(W.HourOfDay);
	UpdateClouds(DeltaSeconds);
	UpdateRain(CamPos);
	UpdateLightning(DeltaSeconds, CamPos);
}

void ASailingEnvironment::UpdateSun(double Hour)
{
	const FWeatherState& W = GetWorld()->GetAuthGameMode<ASailingGameMode>()->GetWeatherState();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	double Elevation, Azimuth;
	// The sailing area's latitude and the session's date; through the whole day and night.
	SunPosition(Hour, GM->GetDayOfYear(), GM->GetLake().Latitude, GM->GetLake().Longitude, GM->GetUtcOffsetHours(), Elevation, Azimuth);
	// Night: below civil twilight the scene is lit by a dim, bluish sky (moonlight and town glow) and the eye does not
	// adapt all the way to darkness, so the water stays dark and the navigation lights stand out.
	const float Night = 1.f - FMath::SmoothStep(-12.f, -2.f, float(Elevation));
	if (PostProcess && !FParse::Param(FCommandLine::Get(), TEXT("SailingNoNightExposure")))
	{
		PostProcess->Settings.bOverride_AutoExposureMinBrightness = true;
		PostProcess->Settings.AutoExposureMinBrightness = FMath::Lerp(-5.f, -3.f, Night); // EV100 floor: no full adaptation to the dark
	}
	if (MoonLight)
	{
		// Moonlight is about a thousandth of the sun here (not the real four hundred thousandth: the eye adapts and the
		// exposure floor keeps the night dark); it lights the atmosphere as its second sun, a deep blue sky.
		static const bool bNoMoon = FParse::Param(FCommandLine::Get(), TEXT("SailingNoMoon")); // profiling
		MoonLight->SetIntensity(bNoMoon ? 0.f : SunIntensity * 0.0015f * Night);
		MoonLight->SetVisibility(!bNoMoon && Night > 0.f);
	}
	if (Sun)
	{
		// The light travels from the sun toward the ground.
		// Below the horizon the light stays just under it (the sky keeps its twilight glow) and fades out with the night.
		Sun->SetActorRotation(FRotator(-FMath::Max(Elevation, -4.0), Azimuth + 180.0, 0.0));
		// Cloud shadows already dim the sun where clouds pass; a solid overcast or storm deck also scatters it away.
		// How much direct sun reaches the water and boat through the clouds.
		const float CloudShade = (1.f - 0.82f * FMath::SmoothStep(0.45f, 1.f, float(W.CloudCover)) * (0.6f + 0.4f * float(W.CloudDarkness)))
			* (1.f - FMath::SmoothStep(0.3f, 0.7f, float(W.CloudDarkness)));
		// The sky atmosphere is lit by this light too, so keep enough intensity for a grey storm sky and take the
		// direct light off the scene with the diffuse and specular scales instead (no glitter, no hard shadows).
		const float Intensity = FMath::Max(CloudShade, 0.35f);
		ULightComponent* SunComp = Sun->GetLightComponent();
		SunComp->SetIntensity(SunIntensity * Intensity * FMath::Lerp(1.f, 0.002f, Night));
		SunComp->SetDiffuseScale(CloudShade / Intensity);
		SunComp->SetSpecularScale(FMath::Square(CloudShade / Intensity));
		// Once the sun is down it casts no shadows, and the clouds' shadow rays toward it (which run the whole layer
		// when the light skims the horizon: night ran at two-thirds of day's frame rate) get only a few samples.
		const bool bShadows = Elevation > 2.0; // shadows from a sun within 2 degrees of the horizon are too long to see
		if (SunComp->CastShadows != bShadows) SunComp->SetCastShadows(bShadows);
		const int32 CloudShadowSamples = Elevation < 0.0 ? 4 : (Elevation < 10.0 ? 6 : 80); // 80: the engine default
		if (CloudShadowSamples != AppliedCloudShadowSamples)
		{
			AppliedCloudShadowSamples = CloudShadowSamples;
			if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.Shadow.ViewRaySampleMaxCount")))
			{
				Var->Set(float(CloudShadowSamples), ECVF_SetByCode);
			}
		}
		if (UDirectionalLightComponent* Dir = Cast<UDirectionalLightComponent>(SunComp))
		{
			const float Disk = FMath::Square(CloudShade);
			Dir->SetAtmosphereSunDiskColorScale(FLinearColor(Disk, Disk, Disk));
		}
	}
	if (SkyLightActor)
	{
		SkyLightActor->GetLightComponent()->SetIntensity(SkyIntensity * (1.f + 0.8f * float(W.CloudDarkness)) * FMath::Lerp(1.f, 0.08f, Night));
		SkyLightActor->GetLightComponent()->SetLightColor(FMath::Lerp(FLinearColor::White, FLinearColor(0.55f, 0.65f, 1.f), Night));
	}
}

void ASailingEnvironment::UpdateClouds(float DeltaSeconds)
{
	const FWeatherState& W = GetWorld()->GetAuthGameMode<ASailingGameMode>()->GetWeatherState();
	if (CloudMaterial)
	{
		CloudMaterial->SetScalarParameterValue(TEXT("Cloud_GlobalCoverage"), FMath::Lerp(-0.2f, 0.6f, float(W.CloudCover)));
		CloudMaterial->SetScalarParameterValue(TEXT("Cloud_GlobalDensity"), FMath::Lerp(0.007f, 0.016f, float(W.CloudDarkness)));
		CloudMaterial->SetScalarParameterValue(TEXT("StormClouds"), 0.85f * float(W.CloudDarkness));
	}
	if (Clouds)
	{
		if (UVolumetricCloudComponent* C = Clouds->FindComponentByClass<UVolumetricCloudComponent>())
		{
			C->SetLayerBottomAltitude(kCloudBaseKm);
			C->SetLayerHeight(FMath::Max(1.f, float(W.CloudTopKm) - kCloudBaseKm));
		}
	}
	if (PostProcess)
	{
		// Eyes adapt to the gloom under a storm: lift exposure as the sky darkens.
		PostProcess->Settings.bOverride_AutoExposureBias = true;
		PostProcess->Settings.AutoExposureBias = 0.5f + 0.6f * float(W.CloudDarkness);
	}
	if (Fog)
	{
		// Koschmieder: visibility ~ 3.9 / extinction. Tuned so 25 km is a clear lake day and 1.5 km a downpour.
		const float Density = FMath::Clamp(0.03f * (2.f / FMath::Max(float(W.VisibilityKm), 0.3f)), 0.0015f, 0.12f);
		UExponentialHeightFogComponent* F = Fog->GetComponent();
		F->SetFogDensity(Density);
		F->SetFogHeightFalloff(FMath::Lerp(0.2f, 0.05f, float(W.Rain)));
	}
}

void ASailingEnvironment::UpdateRain(const FVector& CameraPos)
{
	const FWeatherState& W = GetWorld()->GetAuthGameMode<ASailingGameMode>()->GetWeatherState();
	const bool bRaining = W.Rain > 0.01;
	RainNear->SetVisibility(bRaining);
	RainFar->SetVisibility(bRaining);
	if (!bRaining || !RainMaterial)
	{
		return;
	}
	RainNear->SetWorldLocation(CameraPos + FVector(0.f, 0.f, 200.f));
	RainFar->SetWorldLocation(CameraPos + FVector(0.f, 0.f, 600.f));
	RainMaterial->SetScalarParameterValue(TEXT("Rain"), float(W.Rain) * 0.35f);
}

void ASailingEnvironment::UpdateLightning(float DeltaSeconds, const FVector& CameraPos)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const auto& Strikes = GM->GetWeather().GetStrikes();
	const double T = GM->GetWeatherTime();
	const FVector2D Listener(CameraPos.X / CmPerMeter, CameraPos.Y / CmPerMeter);

	while (NextStrike < int32(Strikes.size()) && Strikes[NextStrike].Time <= T)
	{
		const FLightningStrike& S = Strikes[NextStrike++];
		const float Distance = FVector2D::Distance(FVector2D(S.X, S.Y), Listener);
		const float Near = FMath::Clamp(1.f - Distance / 15000.f, 0.f, 1.f);
		Flash = FMath::Max(Flash, 0.35f + 0.65f * Near);
		if (S.bCloudToGround)
		{
			BuildBolt(FVector(S.X, S.Y, 0.0) * CmPerMeter, kCloudBaseKm * 1000.f * CmPerMeter);
			BoltTime = 0.f;
		}
		// Light from the strike's direction.
		const FVector Dir = (FVector(Listener.X - S.X, Listener.Y - S.Y, -1500.f)).GetSafeNormal();
		FlashLight->SetWorldRotation(Dir.Rotation());
		PendingThunder.Add({ float(FWeatherSystem::ThunderDelaySeconds(S, Listener.X, Listener.Y)), FMath::Clamp(2500.f / FMath::Max(Distance, 300.f), 0.1f, 1.f) });
	}

	// Flash: a few flickers, then gone.
	if (Flash > 0.f)
	{
		const float Flicker = 0.6f + 0.4f * FMath::Abs(FMath::Sin(GetWorld()->GetTimeSeconds() * 47.f));
		FlashLight->SetIntensity(14.f * Flash * Flicker);
		Flash = FMath::Max(0.f, Flash - DeltaSeconds * 3.5f);
	}
	else
	{
		FlashLight->SetIntensity(0.f);
	}
	if (BoltTime >= 0.f)
	{
		BoltTime += DeltaSeconds;
		const bool bVisible = BoltTime < 0.35f && FMath::Fmod(BoltTime, 0.12f) < 0.08f;
		Bolt->SetVisibility(bVisible);
		if (BoltMaterial) BoltMaterial->SetScalarParameterValue(TEXT("Intensity"), 400.f);
		if (BoltTime > 0.4f) BoltTime = -1.f;
	}
	else
	{
		Bolt->SetVisibility(false);
	}

	// Thunder arrives later, at the speed of sound.
	for (int32 I = PendingThunder.Num() - 1; I >= 0; --I)
	{
		PendingThunder[I].Delay -= DeltaSeconds;
		if (PendingThunder[I].Delay <= 0.f)
		{
			Thunder.Add({ PendingThunder[I].Loudness, 0.f, 3.f + 4.f * (1.f - PendingThunder[I].Loudness) });
			PendingThunder.RemoveAt(I);
		}
	}
	for (FThunder& Th : Thunder) Th.Age += DeltaSeconds;
	Thunder.RemoveAll([](const FThunder& Th) { return Th.Age > Th.Duration; });
}

void ASailingEnvironment::BuildBolt(const FVector& Ground, float CloudBaseCm)
{
	// A jagged channel from the cloud base to the water, as camera-facing ribbons.
	FVector CamPos = Ground + FVector(-100000.f, 0.f, 0.f);
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		CamPos = Cam->GetCameraLocation();
	}
	TArray<FVector> Points;
	FVector P = Ground + FVector(FMath::FRandRange(-30000.f, 30000.f), FMath::FRandRange(-30000.f, 30000.f), CloudBaseCm);
	const int32 Segments = 28;
	for (int32 I = 0; I <= Segments; ++I)
	{
		const float T = float(I) / Segments;
		const FVector Target = FMath::Lerp(P, Ground, T);
		Points.Add(Target + (I > 0 && I < Segments ? FVector(FMath::FRandRange(-6000.f, 6000.f), FMath::FRandRange(-6000.f, 6000.f), 0.f) : FVector::ZeroVector));
	}
	TArray<FVector> Verts;
	TArray<int32> Tris;
	const float Width = 400.f;
	for (int32 I = 0; I < Points.Num(); ++I)
	{
		const FVector Along = (Points[FMath::Min(I + 1, Points.Num() - 1)] - Points[FMath::Max(I - 1, 0)]).GetSafeNormal();
		const FVector ToCam = (CamPos - Points[I]).GetSafeNormal();
		const FVector Side = FVector::CrossProduct(Along, ToCam).GetSafeNormal() * Width * 0.5f;
		Verts.Add(Points[I] - Side);
		Verts.Add(Points[I] + Side);
		if (I > 0)
		{
			const int32 B = (I - 1) * 2;
			Tris.Append({ B, B + 1, B + 2, B + 1, B + 3, B + 2, B, B + 2, B + 1, B + 1, B + 2, B + 3 });
		}
	}
	Bolt->SetWorldLocation(FVector::ZeroVector);
	Bolt->SetWorldRotation(FRotator::ZeroRotator);
	Bolt->CreateMeshSection_LinearColor(0, Verts, Tris, {}, {}, {}, {}, false);
}
