#include "SailingEnvironment.h"
#include "BenchRunner.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "Async/Async.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/Texture2D.h"
#include "LakeData.h"
#include "WaterSurface.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Storm.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "VisualPipeline.h"
#include "SailingSettings.h"
#include "Engine/SkyLight.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialParameterCollection.h"
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
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> CloudLayers(TEXT("/Game/Materials/M_CloudLayers.M_CloudLayers"));
	CloudLayersMaterial = CloudLayers.Object;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SkyDomeMat(TEXT("/Game/Materials/M_SkyDome.M_SkyDome"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> LensWater(TEXT("/Game/Materials/M_LensWater.M_LensWater"));
	LensWaterMaterial = LensWater.Object;
	static ConstructorHelpers::FObjectFinder<UMaterialParameterCollection> WorldMpc(TEXT("/Game/World/MPC_World.MPC_World"));
	WorldCollection = WorldMpc.Object;
	// Visual V5: the sky dome, 200 km across the camera (a sky material: everything draws over it).
	SkyDome = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SkyDome"));
	SkyDome->SetupAttachment(RootComponent);
	SkyDome->SetStaticMesh(Sphere.Object);
	SkyDome->SetMaterial(0, SkyDomeMat.Object);
	SkyDome->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SkyDome->SetCastShadow(false);
	SkyDome->SetUsingAbsoluteScale(true);
	SkyDome->SetWorldScale3D(FVector(4.0e5f));
	SkyDome->SetVisibility(false);
	SkyDome->bVisibleInRayTracing = false;
	SkyDome->SetAffectDistanceFieldLighting(false);
	SkyDome->bAffectDynamicIndirectLighting = false;

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

	// W5b: the storm's rain curtains and their foot, seen from afar (UpdateRainCurtains places and turns them).
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Plane(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Curtain(TEXT("/Game/Materials/M_RainCurtain.M_RainCurtain"));
	RainCurtains = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("RainCurtains"));
	RainCurtains->SetupAttachment(RootComponent);
	RainCurtains->SetStaticMesh(Plane.Object);
	RainCurtains->SetMaterial(0, Curtain.Object);
	RainCurtains->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RainCurtains->SetCastShadow(false);
	RainCurtains->NumCustomDataFloats = 4;
	RainCurtains->bVisibleInRayTracing = false;
	RainCurtains->SetAffectDistanceFieldLighting(false);
	RainCurtains->bAffectDynamicIndirectLighting = false;
	RainCurtains->SetUsingAbsoluteLocation(true);
	RainCurtains->SetUsingAbsoluteRotation(true);
	RainCurtains->SetUsingAbsoluteScale(true);

	Bolt = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Bolt"));
	Bolt->SetupAttachment(RootComponent);
	Bolt->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Bolt->SetCastShadow(false);
	Bolt->SetMaterial(0, Emissive.Object);

	// The strike's channel lights the water and the boat around it (the cloud's inside is lit by M_CloudLayers).
	BoltLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("BoltLight"));
	BoltLight->SetupAttachment(RootComponent);
	BoltLight->SetIntensity(0.f);
	BoltLight->SetAttenuationRadius(2000000.f);
	BoltLight->SetCastShadows(false);
	BoltLight->SetLightColor(FLinearColor(0.8f, 0.85f, 1.f));
	BoltLight->SetMobility(EComponentMobility::Movable);

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
	// Visual V5: the layered clouds on Medium and High (-SailingClassicSky keeps the Phase 8 sky, for measuring).
	bLayeredClouds = USailingSettings::Get()->Quality != ESailingQuality::Low && CloudLayersMaterial && Clouds
		&& !FParse::Param(FCommandLine::Get(), TEXT("SailingClassicSky"));
	if (bLayeredClouds)
	{
		if (UVolumetricCloudComponent* CloudComp = Clouds->FindComponentByClass<UVolumetricCloudComponent>())
		{
			CloudMaterial = UMaterialInstanceDynamic::Create(CloudLayersMaterial, this);
			CloudComp->SetMaterial(CloudMaterial);
			// Graphics G1: more samples on the shadow rays inside the cloud (their jitter was most of the speckle) and, on
			// High and Ultra, along the view ray. -SailingCloudScale=<view>,<shadow> overrides, for measuring.
			const ESailingQuality Q = USailingSettings::Get()->Quality;
			CloudComp->SetViewSampleCountScale(Q == ESailingQuality::Ultra ? 2.f : 1.f);
			CloudComp->SetShadowViewSampleCountScale(Q == ESailingQuality::Ultra ? 4.f : 1.f);
			// The shadow rays' samples over 4 km instead of the default 15: the same count, three times as dense where the
			// light is actually lost (a cloud's own few kilometres), so far less jitter (the grain) at no cost.
			CloudComp->SetShadowTracingDistance(4.f);
			float ShadowKm = 0.f;
			if (FParse::Value(FCommandLine::Get(), TEXT("SailingCloudShadowKm="), ShadowKm)) CloudComp->SetShadowTracingDistance(ShadowKm);
			FString Scales;
			if (FParse::Value(FCommandLine::Get(), TEXT("SailingCloudScale="), Scales, false))
			{
				FString A, B;
				if (Scales.Split(TEXT(","), &A, &B))
				{
					CloudComp->SetViewSampleCountScale(FCString::Atof(*A));
					CloudComp->SetShadowViewSampleCountScale(FCString::Atof(*B));
				}
			}
		}
		WeatherMapTexture = UTexture2D::CreateTransient(FWeatherMap::N, FWeatherMap::N, PF_FloatRGBA); // half floats (1024^2)
		WeatherMapTexture->SRGB = false;
		WeatherMapTexture->Filter = TF_Bilinear;
		WeatherMapTexture->AddressX = TA_Clamp;
		WeatherMapTexture->AddressY = TA_Clamp;
		WeatherMapTexture->CompressionSettings = TC_HDR;
		WeatherMapTexture->UpdateResource();
		if (CloudMaterial) CloudMaterial->SetTextureParameterValue(TEXT("WeatherMap"), WeatherMapTexture);
		// Graphics G6 (measuring): each layer's extinction relative to CloudDensity, -SailingCloudLayerExt=<cu>,<st>,<storm>,<rain>
		// (the material's LayerExtinction default otherwise).
		FString LayerExt;
		if (CloudMaterial && FParse::Value(FCommandLine::Get(), TEXT("SailingCloudLayerExt="), LayerExt, false))
		{
			TArray<FString> Parts;
			LayerExt.ParseIntoArray(Parts, TEXT(","));
			if (Parts.Num() == 4)
			{
				CloudMaterial->SetVectorParameterValue(TEXT("LayerExtinction"), FLinearColor(FCString::Atof(*Parts[0]), FCString::Atof(*Parts[1]),
					FCString::Atof(*Parts[2]), FCString::Atof(*Parts[3])));
			}
		}
		float MaxStepDepth = 0.f; // measuring: -SailingCloudStepDepth=<optical depth> (the material's MaxStepDepth otherwise)
		if (CloudMaterial && FParse::Value(FCommandLine::Get(), TEXT("SailingCloudStepDepth="), MaxStepDepth)) CloudMaterial->SetScalarParameterValue(TEXT("MaxStepDepth"), MaxStepDepth);
		FString NoisePath; // measuring: -SailingCloudNoise=<volume texture path>
		if (CloudMaterial && FParse::Value(FCommandLine::Get(), TEXT("SailingCloudNoise="), NoisePath))
		{
			if (UTexture* Noise = LoadObject<UTexture>(nullptr, *NoisePath)) CloudMaterial->SetTextureParameterValue(TEXT("Shape"), Noise); // the shape volume (Graphics G1)
		}
	}
	if (bLayeredClouds)
	{
		SkyMaterial = SkyDome->CreateAndSetMaterialInstanceDynamic(0);
		SkyDome->SetVisibility(SkyMaterial != nullptr);
		if (SkyMaterial && WeatherMapTexture) SkyMaterial->SetTextureParameterValue(TEXT("WeatherMap"), WeatherMapTexture);
		// The moon's disc is drawn by the dome (with its phase); the atmosphere's own would be a flat white second sun.
		MoonLight->SetAtmosphereSunDiskColorScale(FLinearColor::Black);
	}
	// Visual V5 (High, not in the capture mode): water on the lens.
	if (USailingSettings::Get()->Quality >= ESailingQuality::High && LensWaterMaterial && PostProcess
		&& !FCString::Strifind(FCommandLine::Get(), TEXT("SailingCapture=")))
	{
		LensMaterial = UMaterialInstanceDynamic::Create(LensWaterMaterial, this);
		PostProcess->Settings.WeightedBlendables.Array.Add(FWeightedBlendable(1.f, LensMaterial));
	}
	RainMaterial = RainNear->CreateAndSetMaterialInstanceDynamic(0);
	RainFar->SetMaterial(0, RainMaterial);
	RainCurtainMaterial = RainCurtains->CreateAndSetMaterialInstanceDynamic(0);
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
	UpdateCloudLayers(CamPos);
	UpdateHaze();
	UpdateRain(CamPos);
	UpdateRainCurtains(CamPos, DeltaSeconds);
	if (WorldCollection)
	{
		// The trees on the shore sway with the wind there (MPC_World.Wind: direction it blows toward, speed with gusts).
		const Vec3 V = GM->GetWind().VelocityAt(Vec3(CamPos.X / CmPerMeter, CamPos.Y / CmPerMeter, 10.0), GM->GetSimTime());
		const double Speed = V.LengthXY();
		const double Mean = FMath::Max(W.Wind.SpeedKnots * kKnot, 0.5);
		UKismetMaterialLibrary::SetVectorParameterValue(this, WorldCollection, TEXT("Wind"),
			FLinearColor(float(V.X / FMath::Max(Speed, 1e-3)), float(V.Y / FMath::Max(Speed, 1e-3)), float(Speed), float(FMath::Clamp(Speed / Mean - 1.0, 0.0, 1.0))));
		// Graphics G2: the water's height, for the wet band along the shores (M_Terrain).
		if (!WaterActor.IsValid()) { TActorIterator<AWaterSurface> It(GetWorld()); if (It) WaterActor = *It; }
		if (WaterActor.IsValid()) UKismetMaterialLibrary::SetScalarParameterValue(this, WorldCollection, TEXT("WaterZ"), float(WaterActor->GetActorLocation().Z));
		// Street lamps, lit windows and vehicle lights come on through dusk (and under a storm's darkness).
		UKismetMaterialLibrary::SetScalarParameterValue(this, WorldCollection, TEXT("Night"),
			FMath::Max(NightAmount, FMath::Clamp(float(W.CloudDarkness) * 1.4f - 0.6f, 0.f, 0.6f)));
	}
	UpdateLightning(DeltaSeconds, CamPos);
}

namespace
{
	constexpr double kSynodicMonthDays = 29.530588853;
	constexpr double kNewMoon2000Unix = 947182440.0; // 2000-01-06 18:14 UTC
}

double ASailingEnvironment::MoonAgeDays(double UnixUtc)
{
	const double Age = FMath::Fmod((UnixUtc - kNewMoon2000Unix) / 86400.0, kSynodicMonthDays);
	return Age < 0.0 ? Age + kSynodicMonthDays : Age;
}

double ASailingEnvironment::MoonIllumination(double AgeDays)
{
	return 0.5 * (1.0 - FMath::Cos(2.0 * PI * AgeDays / kSynodicMonthDays));
}

void ASailingEnvironment::MoonPosition(double ClockHour, double DayOfYear, double AgeDays, double LatitudeDeg, double LongitudeDeg, double UtcOffsetHours, double& OutElevation, double& OutAzimuth)
{
	const double ElongationDeg = 360.0 * AgeDays / kSynodicMonthDays; // east of the sun
	SunPosition(ClockHour - ElongationDeg / 15.0, DayOfYear + 365.25 * ElongationDeg / 360.0, LatitudeDeg, LongitudeDeg, UtcOffsetHours, OutElevation, OutAzimuth);
}

void ASailingEnvironment::ApplyCameraLook(bool bPhysicalCamera, double CloudDarkness)
{
	// Visual V1: one filmic look on Medium and High. The engine's filmic tone curve with a slight warm bias for Texas
	// afternoons (neutral under a storm deck), local exposure so a white sail against a bright sky keeps its detail,
	// modest bloom and lens flare, a little vignetting, per-object motion blur at a 90 degree shutter, and no chromatic
	// aberration or film grain. Depth of field stays off outside photo mode. Low keeps the Phase 8 post.
	FPostProcessSettings& PP = PostProcess->Settings;
	PP.bOverride_WhiteTemp = PP.bOverride_LocalExposureHighlightContrastScale = PP.bOverride_LocalExposureShadowContrastScale = bPhysicalCamera;
	PP.bOverride_BloomIntensity = PP.bOverride_LensFlareIntensity = PP.bOverride_SceneFringeIntensity = PP.bOverride_VignetteIntensity = bPhysicalCamera;
	PP.bOverride_MotionBlurAmount = PP.bOverride_MotionBlurMax = PP.bOverride_FilmGrainIntensity = bPhysicalCamera;
	if (!bPhysicalCamera)
	{
		return;
	}
	PP.WhiteTemp = FMath::Lerp(6900.f, 6500.f, FMath::Clamp(float(CloudDarkness) * 1.5f, 0.f, 1.f));
	PP.LocalExposureHighlightContrastScale = 0.7f;
	PP.LocalExposureShadowContrastScale = 0.9f;
	PP.BloomIntensity = 0.35f;
	PP.LensFlareIntensity = 0.15f;
	PP.SceneFringeIntensity = 0.f;
	PP.VignetteIntensity = 0.25f;
	PP.MotionBlurAmount = 0.25f;
	PP.MotionBlurMax = 2.f;
	PP.FilmGrainIntensity = 0.f;
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
	NightAmount = Night;
	SunElevationDeg = float(Elevation);
	SunDirection = FVector(FMath::Cos(Elevation * kDegToRad) * FMath::Cos(Azimuth * kDegToRad), FMath::Cos(Elevation * kDegToRad) * FMath::Sin(Azimuth * kDegToRad), FMath::Sin(Elevation * kDegToRad));
	const float NightFloorEV = FMath::Lerp(-5.f, -3.f, Night); // EV100 floor: no full adaptation to the dark
	const bool bPhysicalCamera = UsesPhysicalCamera(USailingSettings::Get()->Quality);
	if (PostProcess && !bPhysicalCamera && !FParse::Param(FCommandLine::Get(), TEXT("SailingNoNightExposure")))
	{
		PostProcess->Settings.bOverride_AutoExposureMinBrightness = true;
		PostProcess->Settings.AutoExposureMinBrightness = NightFloorEV;
	}
	const double MoonAge = MoonAgeDays(GM->GetUnixTime());
	double MoonEl, MoonAz;
	MoonPosition(Hour, GM->GetDayOfYear(), MoonAge, GM->GetLake().Latitude, GM->GetLake().Longitude, GM->GetUtcOffsetHours(), MoonEl, MoonAz);
	// How much direct sun reaches the water and boat through the clouds: cloud shadows dim it where clouds pass, and a
	// solid overcast or storm deck also scatters it away.
	float CloudShade = (1.f - 0.82f * FMath::SmoothStep(0.45f, 1.f, float(W.CloudCover)) * (0.6f + 0.4f * float(W.CloudDarkness)))
		* (1.f - FMath::SmoothStep(0.3f, 0.7f, float(W.CloudDarkness)));
	// Visual V5: with the layered clouds, the sunlight on the lake is what passes through them toward the sun (a cumulus
	// shadow, the shelf cloud's arrival), not a guess from the cloud cover.
	if (bLayeredClouds && bHasWeatherMap && Elevation > 0.0)
	{
		const double E = Elevation * kDegToRad, A = Azimuth * kDegToRad;
		FVector Cam = FVector::ZeroVector;
		if (APlayerCameraManager* CamMgr = UGameplayStatics::GetPlayerCameraManager(this, 0)) Cam = CamMgr->GetCameraLocation() / CmPerMeter;
		const FGustFront& F = W.Front;
		const double Seen = LastWeatherMap.SunTransmittance(W.Sky, F, F.SpeedMs * (GM->GetSimTime() - F.StartTime), GM->GetWeatherTime(), Cam.X, Cam.Y,
			FMath::Cos(E) * FMath::Cos(A), FMath::Cos(E) * FMath::Sin(A), FMath::Sin(E));
		SunVisibility = FMath::FInterpTo(SunVisibility, float(Seen), GetWorld()->GetDeltaSeconds(), 1.5f);
		CloudShade = 0.12f + 0.88f * SunVisibility;
	}
	if (PostProcess)
	{
		ApplyCameraLook(bPhysicalCamera, W.CloudDarkness);
		if (bPhysicalCamera)
		{
			// Visual V1: exposure follows the light, as an incident meter would (VisualPipeline.h), with a little room
			// for the histogram to react to framing.
			const double EV = CameraEV100(Elevation, CloudShade, W.CloudDarkness, MoonEl, MoonIllumination(MoonAge), NightFloorEV);
			// Graphics G5: the haze is lit by the same light the exposure meters. A fixed inscattering colour stayed at
			// midday brightness while the exposure opened 4-5 stops for a low sun, so at sunset the horizon blew out
			// white and hid the sun's disc (the blind test's sunsets).
			static const double ClearNoonEV = CameraEV100(60.0, 1.0, 0.0, -90.0, 0.0, -20.0);
			HazeLight = FMath::Clamp(float(FMath::Pow(2.0, EV - ClearNoonEV)), 0.004f, 1.f);
			FPostProcessSettings& PP = PostProcess->Settings;
			PP.bOverride_AutoExposureMethod = PP.bOverride_AutoExposureMinBrightness = PP.bOverride_AutoExposureMaxBrightness = PP.bOverride_AutoExposureBias = true;
			PP.AutoExposureMethod = EAutoExposureMethod::AEM_Histogram;
			// Under a storm deck the band narrows: the eye does not brighten the gloom much (Phase 8, fix 7).
			// In clear air the band and the half-stop lift match the Phase 8 look (a camera's auto exposure, as in the
			// reference clips); both fade out under the deck.
			const float Dark = FMath::Clamp(float(W.CloudDarkness), 0.f, 1.f);
			const float Band = FMath::Lerp(1.f, 0.3f, Dark);
			// Graphics G5: looking into a low sun, a camera meters the bright sky and the scene goes deep (every sunset
			// photo); the incident meter alone left the blind test's sunsets nearly white. Up to 2.5 stops darker as the
			// view turns toward a sun below 20 degrees.
			float IntoSun = 0.f;
			static SailingArgs::FCachedFlag ClassicHazeArg(TEXT("SailingClassicHaze"));
			const bool bClassicHaze = ClassicHazeArg.Get();
			if (!bClassicHaze && Elevation > -2.0)
			{
				if (APlayerCameraManager* CamMgr = UGameplayStatics::GetPlayerCameraManager(this, 0))
				{
					const double E = Elevation * kDegToRad, A = Azimuth * kDegToRad;
					const FVector SunDir(FMath::Cos(E) * FMath::Cos(A), FMath::Cos(E) * FMath::Sin(A), FMath::Sin(E));
					const float Facing = float(FVector::DotProduct(CamMgr->GetCameraRotation().Vector(), SunDir));
					IntoSun = FMath::SmoothStep(0.5f, 0.95f, Facing) * (1.f - FMath::SmoothStep(8.f, 20.f, float(Elevation))) * (1.f - Dark);
				}
			}
			PP.AutoExposureMinBrightness = float(EV) - Band + 2.5f * IntoSun;
			PP.AutoExposureMaxBrightness = float(EV) + Band + 2.5f * IntoSun;
			PP.AutoExposureBias = 0.5f * (1.f - Dark);
		}
	}
	if (MoonLight)
	{
		// Moonlight is about a thousandth of the sun here (not the real four hundred thousandth: the eye adapts and the
		// exposure floor keeps the night dark); it lights the atmosphere as its second sun, a deep blue sky.
		// Phase 8: the moon has its phase and its place in the sky for the date (a new moon leaves only the town glow).
		static SailingArgs::FCachedFlag NoMoonArg(TEXT("SailingNoMoon")); // profiling
		const bool bNoMoon = NoMoonArg.Get();
		const double Age = MoonAge;
		const float Up = FMath::SmoothStep(-3.f, 4.f, float(MoonEl));
		const float Lit = 0.15f + 0.85f * float(MoonIllumination(Age)) * Up;
		// The light keeps the moon's bearing but stays at least 25 deg up: the clouds' shadow rays toward a light near
		// the horizon cost several ms a frame (as with a low sun), and a low moon's light is dim anyway (Up above).
		MoonLight->SetWorldRotation(FRotator(-FMath::Max(MoonEl, 25.0), MoonAz + 180.0, 0.0));
		MoonLight->SetIntensity(bNoMoon ? 0.f : SunIntensity * 0.0015f * Night * Lit);
		MoonLight->SetVisibility(!bNoMoon && Night > 0.f);
	}
	if (SkyMaterial)
	{
		auto Dir = [](double El, double Az) { const double E = El * kDegToRad, A = Az * kDegToRad; return FVector(FMath::Cos(E) * FMath::Cos(A), FMath::Cos(E) * FMath::Sin(A), FMath::Sin(E)); };
		const float Lit = float(MoonIllumination(MoonAge));
		// The moon's disc luminance: its light's illuminance over the disc's solid angle (as the atmosphere draws the sun).
		const float MoonLux = MoonLight ? MoonLight->Intensity : 0.f;
		UpdateSkyDome(Dir(Elevation, Azimuth), Dir(MoonEl, MoonAz), MoonLux / (PI * 0.0045f * 0.0045f) * 0.35f, Lit, Night * (1.f - float(W.CloudCover)), GM->GetUnixTime());
	}
	if (Sun)
	{
		// The light travels from the sun toward the ground.
		// Below the horizon the light stays just under it (the sky keeps its twilight glow) and fades out with the night.
		Sun->SetActorRotation(FRotator(-FMath::Max(Elevation, -4.0), Azimuth + 180.0, 0.0));
		// The sky atmosphere is lit by this light too, so keep enough intensity for a grey storm sky and take the
		// direct light off the scene with the diffuse and specular scales instead (no glitter, no hard shadows).
		const float Intensity = FMath::Max(CloudShade, 0.35f);
		ULightComponent* SunComp = Sun->GetLightComponent();
		SunComp->SetIntensity(SunIntensity * Intensity * FMath::Lerp(1.f, 0.002f, Night));
		// Perf 2: the diffuse and specular scales rebuild the light (MarkRenderStateDirty), and a rebuilt light starts its
		// virtual shadow map cache afresh: under a storm deck, where they follow the cloud shade, that was every frame.
		// They step by 0.04 instead (each step one ordinary uncached frame); in sunshine they sit at 1 as before.
		const float Direct = FMath::Clamp(CloudShade / Intensity, 0.f, 1.f);
		if (FMath::Abs(SunComp->DiffuseScale - Direct) > 0.04f || (Direct >= 1.f && SunComp->DiffuseScale < 1.f))
		{
			SunComp->SetDiffuseScale(Direct);
			SunComp->SetSpecularScale(FMath::Square(Direct));
		}
		// The haze and rain under a storm deck aren't sunlit: no glowing white fog (volumetric fog has no cloud shadow).
		SunComp->SetVolumetricScatteringIntensity(FMath::Clamp(CloudShade * 1.2f, 0.05f, 1.f));
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
			// Visual V5: the layered clouds shade themselves (their bases are dark because the cloud above shadows them),
			// so they are lit by the undimmed sun: the scene's light is cut for the deck's shadow, the clouds' is not.
			// That is what gives a storm its form: a lit shelf face and anvil top over a dark base.
			const float CloudLight = bLayeredClouds ? FMath::Clamp(1.f / FMath::Max(Intensity, 0.05f), 1.f, 4.f) : 1.f;
			// In 3% steps (perf-2): this rebuilds the light too, and its shadow cache with it.
			if (!Dir->CloudScatteredLuminanceScale.Equals(FLinearColor(CloudLight, CloudLight, CloudLight), 0.03f * CloudLight))
			{
				Dir->CloudScatteredLuminanceScale = FLinearColor(CloudLight, CloudLight, CloudLight);
				Dir->MarkRenderStateDirty();
			}
		}
	}
	if (CloudMaterial)
	{
		// W8: the sun as the shelf cloud's lit face sees it (M_CloudLayers emits it there): the luminance of a white
		// diffuser in the undimmed sun (the clouds get the undimmed sun, CloudScatteredLuminanceScale), warmer and
		// dimmer as it nears the horizon (the atmosphere's reddening, roughly).
		const float Low = 1.f - FMath::SmoothStep(4.f, 25.f, float(Elevation));
		const FLinearColor Tint = FMath::Lerp(FLinearColor(1.f, 0.97f, 0.93f), FLinearColor(1.f, 0.62f, 0.38f), Low) * (1.f - 0.6f * Low);
		const float Lum = Elevation > 0.0 ? SunIntensity / PI * (1.f - Night) : 0.f;
		const double E = Elevation * kDegToRad, A = Azimuth * kDegToRad;
		CloudMaterial->SetVectorParameterValue(TEXT("SunLum"), FLinearColor(Tint.R * Lum, Tint.G * Lum, Tint.B * Lum, float(FMath::Sin(E))));
		CloudMaterial->SetVectorParameterValue(TEXT("SunDir"), FLinearColor(float(FMath::Cos(E) * FMath::Cos(A)), float(FMath::Cos(E) * FMath::Sin(A)), float(FMath::Sin(E)), 0.f));
	}
	if (SkyLightActor)
	{
		// Under a storm's deck the whole sky is darker, not brighter: illuminance under a shelf cloud falls by one to two
		// orders of magnitude (Phase 8: STORM-001, SQ-001, C30-S-001 all go grey-dark as it passes over).
		SkyLightActor->GetLightComponent()->SetIntensity(SkyIntensity * (1.f - 0.6f * float(W.CloudDarkness)) * FMath::Lerp(1.f, 0.08f, Night));
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
			if (bLayeredClouds)
			{
				// The tracer spans only the layers present: its samples go where the cloud is.
				double Base, Top;
				W.Sky.Span(Base, Top);
				C->SetLayerBottomAltitude(float(FMath::Max(0.0, Base - 0.05)));
				C->SetLayerHeight(float(FMath::Max(0.6, Top - Base + 0.1)));
				// Graphics G6: what the material needs to know its own march step (slab km, samples, the distance below
				// which the sample count drops in proportion, the tracing cap): it keeps each step's optical depth bounded.
				if (CloudMaterial)
				{
					static IConsoleVariable* MaxCount = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"));
					static IConsoleVariable* FullAt = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.DistanceToSampleMaxCount"));
					const float Samples = FMath::Max(2.f, FMath::Min(UVolumetricCloudComponent::BaseViewRaySampleCount * C->ViewSampleCountScale,
						MaxCount ? MaxCount->GetFloat() : 96.f));
					CloudMaterial->SetVectorParameterValue(TEXT("Tracer"), FLinearColor(C->LayerHeight, Samples, FullAt ? FullAt->GetFloat() : 15.f, C->TracingMaxDistance));
					static IConsoleVariable* ShadowMax = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.Shadow.ViewRaySampleMaxCount"));
					const float ShadowSamples = FMath::Max(2.f, FMath::Min(UVolumetricCloudComponent::BaseShadowRaySampleCount * C->ShadowViewSampleCountScale,
						ShadowMax ? ShadowMax->GetFloat() : 80.f));
					CloudMaterial->SetVectorParameterValue(TEXT("TracerShadow"), FLinearColor(C->ShadowTracingDistance, ShadowSamples, 0.f, 0.f));
				}
			}
			else
			{
				C->SetLayerBottomAltitude(kCloudBaseKm);
				C->SetLayerHeight(FMath::Max(1.f, float(W.CloudTopKm) - kCloudBaseKm));
			}
		}
	}
	if (PostProcess)
	{
		// Eyes and cameras adapt only part of the way to the gloom under a storm: the scene should read dark (every storm
		// reference does), so hold exposure a stop and a half under where auto exposure would take it at full darkness.
		if (!UsesPhysicalCamera(USailingSettings::Get()->Quality)) // the physical camera meters the gloom itself
		{
			PostProcess->Settings.bOverride_AutoExposureBias = true;
			PostProcess->Settings.AutoExposureBias = 0.5f - 1.5f * float(W.CloudDarkness);
		}
		// Under the deck the light is grey, not blue: the sky's blue comes from above the cloud and never reaches the
		// lake (Phase 8 blind test: the storm frames read as a clear dusk). Fair-weather days are untouched.
		const float Grey = FMath::SmoothStep(0.3f, 0.8f, float(W.CloudDarkness));
		PostProcess->Settings.bOverride_ColorSaturation = true;
		PostProcess->Settings.ColorSaturation = FVector4(1.f, 1.f, 1.f, 1.f - 0.7f * Grey);
	}
}

void ASailingEnvironment::UpdateRain(const FVector& CameraPos)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FWeatherState& W = GM->GetWeatherState();
	// W5b: the rain where the camera is (a storm's falls under its core, not everywhere at once).
	const double RainHere = GM->GetRainAt(CameraPos.X / CmPerMeter, CameraPos.Y / CmPerMeter);
	const bool bRaining = RainHere > 0.01;
	if (LensMaterial)
	{
		// The air over the glass: the wind less the camera's own motion, in screen axes (+y down), with gravity.
		const float Dt = FMath::Max(GetWorld()->GetDeltaSeconds(), 1e-3f);
		const FVector CamVel = (CameraPos - LastCameraPos) / Dt / CmPerMeter;
		LastCameraPos = CameraPos;
		const double From = W.Wind.FromDegrees * kDegToRad;
		const FVector Air = FVector(-FMath::Cos(From), -FMath::Sin(From), 0.0) * (W.Wind.SpeedKnots * kKnot) - CamVel.GetClampedToMaxSize(30.0);
		FVector Right(0, 1, 0), Up(0, 0, 1);
		if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
		{
			const FRotator R = Cam->GetCameraRotation();
			Right = FRotationMatrix(R).GetUnitAxis(EAxis::Y);
			Up = FRotationMatrix(R).GetUnitAxis(EAxis::Z);
		}
		const FVector2D Screen(float(FVector::DotProduct(Air, Right)), float(-FVector::DotProduct(Air, Up)) + 3.f);
		float Spray = 0.f;
		for (TActorIterator<AWaterSurface> It(GetWorld()); It; ++It) Spray = It->GetLensSpray();
		LensMaterial->SetScalarParameterValue(TEXT("Rain"), float(RainHere));
		LensMaterial->SetScalarParameterValue(TEXT("Spray"), Spray);
		LensMaterial->SetVectorParameterValue(TEXT("WindScreen"), FLinearColor(float(Screen.X), float(Screen.Y), float(Screen.Size()), 0.f));
	}
	RainNear->SetVisibility(bRaining);
	RainFar->SetVisibility(bRaining);
	if (!bRaining || !RainMaterial)
	{
		return;
	}
	RainNear->SetWorldLocation(CameraPos + FVector(0.f, 0.f, 200.f));
	RainFar->SetWorldLocation(CameraPos + FVector(0.f, 0.f, 600.f));
	// Visual V5: the rain slants with the wind it falls through (drops fall at about 7 m/s): the sheet leans downwind.
	{
		const double From = W.Wind.FromDegrees * kDegToRad;
		const double Speed = W.Wind.SpeedKnots * kKnot;
		const FVector Down = FVector(-FMath::Cos(From) * Speed, -FMath::Sin(From) * Speed, -7.0).GetSafeNormal();
		const FQuat Lean = FQuat::FindBetweenNormals(FVector(0, 0, -1), Down);
		RainNear->SetWorldRotation(Lean);
		RainFar->SetWorldRotation(Lean);
	}
	RainMaterial->SetScalarParameterValue(TEXT("Rain"), float(RainHere) * 0.35f);
}

void ASailingEnvironment::UpdateRainCurtains(const FVector& CameraPos, float DeltaSeconds)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !RainCurtains) return;
	// -SailingNoRainCurtains: without them (comparisons, the cost on the bench).
	static SailingArgs::FCachedFlag NoCurtainsArg(TEXT("SailingNoRainCurtains"));
	const bool bOff = NoCurtainsArg.Get();
	if (bOff)
	{
		RainCurtains->SetVisibility(false);
		return;
	}
	const FWeatherState& W = GM->GetWeatherState();
	const double Now = GM->GetSimTime();
	const double Cx = CameraPos.X / CmPerMeter, Cy = CameraPos.Y / CmPerMeter;
	constexpr double Cell = 2000.0, Reach = 26000.0;
	CurtainClock -= DeltaSeconds;
	if (CurtainClock <= 0.f)
	{
		// Twice a second: the rain field over a world grid of 2 km cells round the camera; the rainiest, nearest cells get a
		// curtain (cells stay put in the world, so curtains don't swim as the camera moves).
		CurtainClock = 0.5f;
		Curtains.Reset();
		if (W.bStormRain)
		{
			const int32 MaxCurtains = USailingSettings::Get()->Quality == ESailingQuality::Low ? 16 : 32;
			const int64 I0 = int64(FMath::FloorToDouble(Cx / Cell)), J0 = int64(FMath::FloorToDouble(Cy / Cell));
			const int32 R = int32(Reach / Cell);
			TArray<TPair<double, FRainCurtain>> Scored;
			for (int32 DI = -R; DI <= R; ++DI)
			{
				for (int32 DJ = -R; DJ <= R; ++DJ)
				{
					const int64 I = I0 + DI, J = J0 + DJ;
					const uint32 H = HashCombine(GetTypeHash(I), GetTypeHash(J * 7919));
					FRainCurtain C;
					C.Seed = (H % 1000u) / 1000.0;
					C.X = (I + 0.5) * Cell + ((H >> 10) % 1000u / 1000.0 - 0.5) * 900.0;
					C.Y = (J + 0.5) * Cell + ((H >> 20) % 1000u / 1000.0 - 0.5) * 900.0;
					const double D = FMath::Sqrt(FMath::Square(C.X - Cx) + FMath::Square(C.Y - Cy));
					if (D > Reach) continue;
					C.Rate = W.RainRateAt(C.X, C.Y, 0.0, Now);
					if (C.Rate < 3.0) continue;
					Scored.Add({ FStormRain::Amount(C.Rate) / (1.0 + D / 8000.0), C });
				}
			}
			Scored.Sort([](const TPair<double, FRainCurtain>& A, const TPair<double, FRainCurtain>& B) { return A.Key > B.Key; });
			for (int32 K = 0; K < FMath::Min(MaxCurtains, Scored.Num()); ++K) Curtains.Add(Scored[K].Value);
			// Storm sky fix: each curtain is lit by what reaches it through the deck above it (toward the sun), not by the
			// open sky's light: under the shelf and core a veil read as a pale grey wall, lighter than the sea (game-04).
			const FGustFront& F = W.Front;
			for (FRainCurtain& C : Curtains)
			{
				C.Shade = SunDirection.Z > 0.0 ? LastWeatherMap.SunTransmittance(W.Sky, F, F.SpeedMs * (Now - F.StartTime), GM->GetWeatherTime(),
					C.X, C.Y, SunDirection.X, SunDirection.Y, SunDirection.Z) : 1.0;
			}
		}
		if (RainCurtainMaterial)
		{
			// The storm's rain falls from the core's base; other rain from the stratus deck's.
			const double BaseM = W.Front.bActive ? FStormShape::CoreBaseM : FMath::Max(W.Sky[ECloudLayer::Stratus].BaseKm * 1000.0, 300.0);
			RainCurtainMaterial->SetScalarParameterValue(TEXT("RainBase"), float(BaseM));
		}
	}
	// Two instances per curtain (the veil, its foot), turned to face the camera every frame.
	const int32 Want = Curtains.Num() * 2;
	if (RainCurtains->GetInstanceCount() != Want)
	{
		RainCurtains->ClearInstances();
		for (int32 K = 0; K < Want; ++K) RainCurtains->AddInstance(FTransform::Identity, true);
	}
	RainCurtains->SetVisibility(Want > 0);
	if (Want == 0) return;
	const double BaseM = W.Front.bActive ? FStormShape::CoreBaseM : FMath::Max(W.Sky[ECloudLayer::Stratus].BaseKm * 1000.0, 300.0);
	// The foot runs ahead of the core toward where the storm is going.
	const double Move = W.Front.MoveDegrees * kDegToRad;
	const FVector FootShift = W.Front.bActive ? FVector(FMath::Cos(Move), FMath::Sin(Move), 0.0) * FStormRain::FootReachM : FVector::ZeroVector;
	for (int32 K = 0; K < Curtains.Num(); ++K)
	{
		const FRainCurtain& C = Curtains[K];
		const FVector P(C.X, C.Y, 0.0);
		FVector N = FVector(Cx, Cy, 0.0) - P;
		const double D = N.Size();
		N = D > 1.0 ? N / D : FVector(1, 0, 0);
		const FVector Up(0, 0, 1), Side = FVector::CrossProduct(Up, N);
		const FQuat Q(FMatrix(Side, Up, N, FVector::ZeroVector));
		// Near the camera the rain cylinders show the rain; far off the haze takes it.
		const double Fade = FMath::SmoothStep(700.0, 2500.0, D) * (1.0 - FMath::SmoothStep(22000.0, Reach, D));
		const double Amount = FStormRain::Amount(C.Rate) * Fade;
		const FTransform Veil(Q, (P + FVector(0, 0, 0.5 * BaseM)) * CmPerMeter, FVector(2200.0, BaseM, 1.0));
		const FTransform Foot(Q, (P + FootShift + FVector(0, 0, 110.0)) * CmPerMeter, FVector(3300.0, 220.0, 1.0));
		RainCurtains->UpdateInstanceTransform(2 * K, Veil, true, false, true);
		RainCurtains->UpdateInstanceTransform(2 * K + 1, Foot, true, false, true);
		RainCurtains->SetCustomDataValue(2 * K, 0, float(Amount), false);
		RainCurtains->SetCustomDataValue(2 * K, 1, 0.f, false);
		RainCurtains->SetCustomDataValue(2 * K, 2, float(C.Seed), false);
		RainCurtains->SetCustomDataValue(2 * K + 1, 0, float(Amount * FMath::SmoothStep(15.0, 60.0, C.Rate)), false);
		RainCurtains->SetCustomDataValue(2 * K + 1, 1, 1.f, false);
		RainCurtains->SetCustomDataValue(2 * K + 1, 2, float(C.Seed), false);
		RainCurtains->SetCustomDataValue(2 * K, 3, float(C.Shade), false);
		RainCurtains->SetCustomDataValue(2 * K + 1, 3, float(C.Shade), false);
	}
	RainCurtains->MarkRenderStateDirty();
}

void ASailingEnvironment::UpdateLightning(float DeltaSeconds, const FVector& CameraPos)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const auto& Strikes = GM->GetWeather().GetStrikes();
	const double T = GM->GetWeatherTime();
	const FVector2D Listener(CameraPos.X / CmPerMeter, CameraPos.Y / CmPerMeter);

	// W8: -SailingNoLightning for stills compared before and after (a flash lights the water white at random times).
	static SailingArgs::FCachedFlag NoLightningArg(TEXT("SailingNoLightning"));
	const bool bNoLightning = NoLightningArg.Get();
	while (NextStrike < int32(Strikes.size()) && Strikes[NextStrike].Time <= T)
	{
		const FLightningStrike& S = Strikes[NextStrike++];
		if (bNoLightning) continue;
		const float Distance = FVector2D::Distance(FVector2D(S.X, S.Y), Listener);
		const float Near = FMath::Clamp(1.f - Distance / 15000.f, 0.f, 1.f);
		Flash = FMath::Max(Flash, 0.35f + 0.65f * Near);
		// Visual V5: the flash lights the cloud from inside around the strike (M_CloudLayers) and, for a ground
		// strike, the channel lights the water.
		FlashParams = FVector4f(float(S.X), float(S.Y), S.bCloudToGround ? 2500.f : 4500.f, 1.f);
		if (S.bCloudToGround)
		{
			BuildBolt(FVector(S.X, S.Y, 0.0) * CmPerMeter, (bLayeredClouds ? 0.7f : kCloudBaseKm) * 1000.f * CmPerMeter);
			BoltTime = 0.f;
			BoltLight->SetWorldLocation(FVector(S.X, S.Y, 300.0) * CmPerMeter);
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
		BoltLight->SetIntensity(bVisible ? 4.0e9f : 0.f);
		if (BoltTime > 0.4f) BoltTime = -1.f;
	}
	else
	{
		Bolt->SetVisibility(false);
		BoltLight->SetIntensity(0.f);
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
	// Visual V5: a branching channel. The main stroke steps down from the cloud base in short tortuous segments (each
	// turning a little at random, drifting overall to the ground point); branches fork from it at random, run down and
	// out, thinner and fainter, and stop short of the ground. Built as camera-facing ribbons.
	FVector CamPos = Ground + FVector(-100000.f, 0.f, 0.f);
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		CamPos = Cam->GetCameraLocation();
	}
	FRandomStream Rng(int32(Ground.X * 0.013f + Ground.Y * 0.007f));
	TArray<FVector> Verts;
	TArray<int32> Tris;
	TArray<FLinearColor> Colors;
	auto Ribbon = [&](const TArray<FVector>& Points, float Width, float Bright)
	{
		const int32 Base = Verts.Num();
		for (int32 I = 0; I < Points.Num(); ++I)
		{
			const FVector Along = (Points[FMath::Min(I + 1, Points.Num() - 1)] - Points[FMath::Max(I - 1, 0)]).GetSafeNormal();
			const FVector ToCam = (CamPos - Points[I]).GetSafeNormal();
			const float Taper = FMath::Lerp(1.f, 0.4f, float(I) / FMath::Max(1, Points.Num() - 1));
			const FVector Side = FVector::CrossProduct(Along, ToCam).GetSafeNormal() * Width * Taper * 0.5f;
			Verts.Add(Points[I] - Side);
			Verts.Add(Points[I] + Side);
			Colors.Add(FLinearColor(Bright, Bright, Bright));
			Colors.Add(FLinearColor(Bright, Bright, Bright));
			if (I > 0)
			{
				const int32 B = Base + (I - 1) * 2;
				Tris.Append({ B, B + 1, B + 2, B + 1, B + 3, B + 2, B, B + 2, B + 1, B + 1, B + 2, B + 3 });
			}
		}
	};
	// The stepped walk from a start toward a target.
	auto Walk = [&](FVector P, const FVector& Target, float StepCm, int32 MaxSteps, float Jitter)
	{
		TArray<FVector> Points = { P };
		for (int32 I = 0; I < MaxSteps; ++I)
		{
			const FVector ToTarget = Target - P;
			if (ToTarget.Size() < StepCm) { Points.Add(Target); break; }
			const FVector Dir = (ToTarget.GetSafeNormal() + FVector(Rng.FRandRange(-Jitter, Jitter), Rng.FRandRange(-Jitter, Jitter), Rng.FRandRange(-0.3f * Jitter, 0.3f * Jitter))).GetSafeNormal();
			P += Dir * StepCm * Rng.FRandRange(0.6f, 1.4f);
			Points.Add(P);
		}
		return Points;
	};
	const FVector Top = Ground + FVector(Rng.FRandRange(-1500.f, 1500.f) * CmPerMeter, Rng.FRandRange(-1500.f, 1500.f) * CmPerMeter, CloudBaseCm);
	const TArray<FVector> Main = Walk(Top, Ground, 4000.f, 200, 0.9f);
	Ribbon(Main, 350.f, 1.f);
	const int32 Branches = Rng.RandRange(4, 9);
	for (int32 B = 0; B < Branches; ++B)
	{
		const int32 From = Rng.RandRange(1, FMath::Max(2, Main.Num() / 2));
		const FVector Start = Main[FMath::Min(From, Main.Num() - 1)];
		const float Height = Start.Z - Ground.Z;
		const FVector Out = FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), 0.f).GetSafeNormal();
		const FVector End = Start + Out * Height * Rng.FRandRange(0.3f, 0.7f) - FVector(0, 0, Height * Rng.FRandRange(0.25f, 0.6f));
		Ribbon(Walk(Start, End, 3000.f, 60, 1.1f), 160.f, 0.45f);
	}
	Bolt->SetWorldLocation(FVector::ZeroVector);
	Bolt->SetWorldRotation(FRotator::ZeroRotator);
	Bolt->CreateMeshSection_LinearColor(0, Verts, Tris, {}, {}, Colors, {}, false);
}

void ASailingEnvironment::UpdateCloudLayers(const FVector& CameraPos)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!bLayeredClouds || !CloudMaterial || !GM) return;
	const FWeatherState& W = GM->GetWeatherState();
	const double Tw = GM->GetWeatherTime();
	if (bWeatherMapPending && PendingWeatherMap.IsReady())
	{
		FWeatherMapFrame Done = PendingWeatherMap.Get();
		LastWeatherMap = MoveTemp(Done.Map);
		LastWeatherMap.LandFraction = nullptr;
		bHasWeatherMap = true;
		bWeatherMapPending = false;
		struct { double X0, Y0; } Frame = { LastWeatherMap.OriginX(), LastWeatherMap.OriginY() };
		const int32 Bytes = Done.Half.Num() * int32(sizeof(FFloat16));
		uint8* Copy = new uint8[Bytes];
		FMemory::Memcpy(Copy, Done.Half.GetData(), Bytes);
		FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, FWeatherMap::N, FWeatherMap::N);
		WeatherMapTexture->UpdateTextureRegions(0, 1, Region, FWeatherMap::N * 8, 8, Copy, [](uint8* Data, const FUpdateTextureRegion2D* R) { delete[] Data; delete R; });
		CloudMaterial->SetVectorParameterValue(TEXT("WeatherRect"), FLinearColor(float(Frame.X0), float(Frame.Y0), float(FWeatherMap::SizeMeters), 0.f));
		if (SkyMaterial) SkyMaterial->SetVectorParameterValue(TEXT("WeatherRect"), FLinearColor(float(Frame.X0), float(Frame.Y0), float(FWeatherMap::SizeMeters), 0.f));
	}
	// Repainted every two seconds on a worker (the layers change slowly; the map drifts with the clouds in between).
	WeatherMapAge += GetWorld()->GetDeltaSeconds();
	if (!bWeatherMapPending && WeatherMapAge > 2.0)
	{
		WeatherMapAge = 0.0;
		const FCloudSky Sky = W.Sky;
		const FGustFront Front = W.Front;
		const FLakeData* Lake = GM->GetLake().IsLoaded() ? &GM->GetLake() : nullptr;
		const double Cx = CameraPos.X / CmPerMeter, Cy = CameraPos.Y / CmPerMeter;
		PendingWeatherMap = Async(EAsyncExecution::ThreadPool, [Sky, Front, Lake, Cx, Cy, Tw]()
		{
			FWeatherMap Map;
			if (Lake)
			{
				// Cumulus build over the heated land, not the lake.
				Map.LandFraction = [Lake](double X, double Y) { return FMath::Clamp((Lake->Terrain.HeightAt(X, Y) + 0.5) / 2.0, 0.0, 1.0); };
			}
			Map.Paint(Sky, Front, Cx, Cy, Tw);
			FWeatherMapFrame Out;
			Out.Half.SetNumUninitialized(int32(Map.Pixels().size()));
			for (int32 I = 0; I < Out.Half.Num(); ++I) Out.Half[I] = FFloat16(Map.Pixels()[I]);
			Out.Map = MoveTemp(Map);
			return Out;
		});
		bWeatherMapPending = true;
	}
	auto Layer = [](const FCloudLayer& L) { return FLinearColor(float(L.Coverage), float(L.BaseKm), float(L.TopKm), float(L.Density)); };
	CloudMaterial->SetVectorParameterValue(TEXT("LayerCumulus"), Layer(W.Sky[ECloudLayer::Cumulus]));
	CloudMaterial->SetVectorParameterValue(TEXT("LayerStratus"), Layer(W.Sky[ECloudLayer::Stratus]));
	CloudMaterial->SetVectorParameterValue(TEXT("LayerCirrus"), Layer(W.Sky[ECloudLayer::Cirrus]));
	CloudMaterial->SetVectorParameterValue(TEXT("Drift"), FLinearColor(float(W.Sky.DriftX * Tw), float(W.Sky.DriftY * Tw), 0.f, 0.f));
	if (SkyMaterial)
	{
		// Cirrus: coverage, the drift (m), its opacity.
		SkyMaterial->SetVectorParameterValue(TEXT("CirrusParams"), FLinearColor(float(W.Sky[ECloudLayer::Cirrus].Coverage), float(W.Sky.DriftX * Tw), float(W.Sky.DriftY * Tw), 0.8f));
		SkyDome->SetWorldLocation(CameraPos);
	}
	const FGustFront& F = W.Front;
	const double Move = F.MoveDegrees * kDegToRad;
	CloudMaterial->SetVectorParameterValue(TEXT("FrontA"), FLinearColor(float(F.StartX), float(F.StartY), float(FMath::Cos(Move)), float(FMath::Sin(Move))));
	// The game mode keeps the front on the physics clock (sim time), not the weather's.
	CloudMaterial->SetVectorParameterValue(TEXT("FrontB"), FLinearColor(float(F.SpeedMs * (GM->GetSimTime() - F.StartTime)), F.bActive ? 1.f : 0.f,
		float(W.Sky[ECloudLayer::Storm].Coverage), float(W.CloudDarkness)));
	CloudMaterial->SetVectorParameterValue(TEXT("Flash"), FLinearColor(FlashParams.X, FlashParams.Y, FlashParams.Z, Flash * FlashParams.W));
	// Extinction per metre at full density: thicker in a storm.
	CloudMaterial->SetScalarParameterValue(TEXT("CloudDensity"), FMath::Lerp(0.045f, 0.065f, float(W.CloudDarkness)) /* Graphics G1: real cumulus extinction, 0.05-0.1 /m */);
}

void ASailingEnvironment::UpdateHaze()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!Fog || !GM) return;
	const FWeatherState& W = GM->GetWeatherState();
	const int32 World = USailingSettings::Get()->World;
	// Koschmieder: visibility ~ 3.9 / extinction. Tuned so 25 km is a clear lake day and 1.5 km a downpour.
	const float Density = FMath::Clamp(0.03f * (2.f / FMath::Max(float(W.VisibilityKm), 0.3f)), 0.0015f, 0.12f);
	UExponentialHeightFogComponent* F = Fog->GetComponent();
	F->SetFogHeightFalloff(FMath::Lerp(0.2f, 0.05f, float(W.Rain)));
	if (USailingSettings::Get()->Quality == ESailingQuality::Low)
	{
		F->SetFogDensity(Density);
		return;
	}
	// Visual V5: humidity haze. A humid Texas summer day is milky; a dry norther is crisp; on the bay and offshore,
	// sea-salt haze. The haze thickens the visibility's fog near the surface and whitens it.
	const float Haze = FMath::Clamp(float(W.Sky.Haze) + (World >= 1 ? 0.2f : 0.f), 0.f, 1.f);
	F->SetFogDensity(Density * FMath::Lerp(0.6f, 1.6f, Haze));
	const FLinearColor Milky(0.62f, 0.66f, 0.72f), Crisp(0.42f, 0.52f, 0.68f), Sea(0.55f, 0.63f, 0.72f);
	const FLinearColor Tint = FMath::Lerp(Crisp, World >= 1 ? Sea : Milky, Haze);
	// The haze glows with the daylight it scatters: under a storm deck and at night it goes dark with the sky.
	static SailingArgs::FCachedFlag ClassicHazeArg(TEXT("SailingClassicHaze"));   // Graphics G5 compare
	const bool bClassicHaze = ClassicHazeArg.Get();
	if (bClassicHaze)
	{
		F->SetFogInscatteringColor(Tint * FMath::Lerp(1.f, 0.25f, float(W.CloudDarkness)) * FMath::Lerp(1.f, 0.004f, NightAmount));
	}
	else
	{
		// Graphics G5: lit by the metered light (HazeLight, which already carries the storm's gloom and the night), and
		// toward sunset the haze takes the low sun's colour, as the sky at the horizon does.
		const float Warm = 1.f - FMath::SmoothStep(0.f, 12.f, SunElevationDeg);
		const FLinearColor Sunset(1.25f, 0.82f, 0.55f);
		const FLinearColor Lit = FMath::Lerp(Tint, Tint * Sunset, Warm * (1.f - NightAmount));
		F->SetFogInscatteringColor(Lit * FMath::Lerp(1.f, 0.6f, float(W.CloudDarkness)) * HazeLight);
		// Analytic fog reaches full opacity at the horizon, which hid the low sun's disc completely; real haze lets a few
		// percent of the disc through, and the disc is thousands of times the sky's brightness.
		F->SetFogMaxOpacity(FMath::Lerp(0.9f, 1.f, float(W.Rain)));
	}
	// Volumetric fog: the sun scatters in it, so shafts show through gaps in the cloud (forward-scattering haze).
	if (!F->bEnableVolumetricFog) F->SetVolumetricFog(true);
	F->SetVolumetricFogScatteringDistribution(0.75f);
	F->SetVolumetricFogExtinctionScale(FMath::Lerp(0.12f, 0.3f, Haze)); // the volumetric fog reads much thicker than the analytic fog at the same density
	F->SetVolumetricFogAlbedo(FColor(240, 244, 250));
	F->SetVolumetricFogDistance(FMath::Lerp(3000.f, 1200.f, float(W.Rain)) * CmPerMeter);
}

void ASailingEnvironment::UpdateSkyDome(const FVector& SunTrue, const FVector& MoonTrue, float MoonLuminance, float MoonLit, float Night, double UnixUtc)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!SkyMaterial || !GM) return;
	// Stars: local sidereal time from the date (GMST, IAU 1982 to a few seconds), then the rotation from the lake's
	// horizon frame (X north, Y east, Z up) to equatorial (X toward RA 0, Z the celestial pole).
	const double JD = UnixUtc / 86400.0 + 2440587.5;
	const double Gmst = FMath::Fmod(18.697374558 + 24.06570982441908 * (JD - 2451545.0), 24.0);
	const double Lst = (Gmst + GM->GetLake().Longitude / 15.0) * 15.0 * kDegToRad;
	const double Phi = GM->GetLake().Latitude * kDegToRad;
	const FVector M0(-FMath::Sin(Phi), 0.0, FMath::Cos(Phi)), West(0.0, -1.0, 0.0), Pole(FMath::Cos(Phi), 0.0, FMath::Sin(Phi));
	const FVector R0 = M0 * FMath::Cos(Lst) + West * FMath::Sin(Lst);
	const FVector R1 = M0 * FMath::Sin(Lst) - West * FMath::Cos(Lst);
	SkyMaterial->SetVectorParameterValue(TEXT("StarRot0"), FLinearColor(float(R0.X), float(R0.Y), float(R0.Z), 0.f));
	SkyMaterial->SetVectorParameterValue(TEXT("StarRot1"), FLinearColor(float(R1.X), float(R1.Y), float(R1.Z), 0.f));
	SkyMaterial->SetVectorParameterValue(TEXT("StarRot2"), FLinearColor(float(Pole.X), float(Pole.Y), float(Pole.Z), 0.f));
	// Star brightness tracks the moonlight's scale (both exposed by the same night exposure); a bright moon washes the
	// faint stars and the Milky Way out a little.
	const float StarScale = float(SunIntensity) * 0.006f * Night * (1.f - 0.6f * MoonLit);
	// The nearest big city's light dome (Visual V6): Dallas from the lake, Houston from the bay, scaled by population light
	// and falling off with distance.
	struct FCity { double Lat, Lon, Light; };
	static const FCity Cities[] = { { 32.78, -96.80, 1.0 }, { 29.76, -95.37, 1.3 }, { 29.39, -94.92, 0.35 }, { 32.75, -97.33, 0.6 } };
	const double CosLat = FMath::Cos(GM->GetLake().Latitude * kDegToRad);
	float Glow = 0.f, GlowAz = 0.f;
	for (const FCity& C : Cities)
	{
		const double North = (C.Lat - GM->GetLake().Latitude) * 111.2, East = (C.Lon - GM->GetLake().Longitude) * 111.2 * CosLat;
		const double Km = FMath::Max(FMath::Sqrt(North * North + East * East), 5.0);
		const float G = float(C.Light * FMath::Pow(30.0 / Km, 1.5));
		if (G > Glow) { Glow = G; GlowAz = float(FMath::Atan2(East, North)); }
	}
	const float GlowScale = float(SunIntensity) * 0.006f * NightAmount * Glow * 1.1f;
	SkyMaterial->SetVectorParameterValue(TEXT("NightParams"), FLinearColor(StarScale, GlowScale, GlowAz, GetWorld()->GetTimeSeconds()));
	SkyMaterial->SetVectorParameterValue(TEXT("MoonDir"), FLinearColor(float(MoonTrue.X), float(MoonTrue.Y), float(MoonTrue.Z), MoonTrue.Z > -0.02f ? MoonLuminance : 0.f));
	// Earthshine: the dark limb at about a few thousandths of the lit side (strongest near new moon).
	SkyMaterial->SetVectorParameterValue(TEXT("SunTrue"), FLinearColor(float(SunTrue.X), float(SunTrue.Y), float(SunTrue.Z), 0.004f * (1.f - MoonLit)));
}
