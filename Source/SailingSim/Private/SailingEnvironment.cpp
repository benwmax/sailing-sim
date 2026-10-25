#include "SailingEnvironment.h"
#include "SailingFrame.h"
#include "BenchRunner.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailboatPawn.h"
#include "Async/Async.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/Texture2D.h"
#include "LakeData.h"
#include "WaterSurface.h"
#include "WorldKit.h"
#include "TreePlacement.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Storm.h"
#include "Haze.h"
#include "Skyline.h"
#include "Misc/FileHelper.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "VisualPipeline.h"
#include "SailingSettings.h"
#include "Engine/SkyLight.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Engine/Canvas.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Materials/MaterialParameterCollection.h"
#include "Misc/CommandLine.h"
#include "HAL/IConsoleManager.h"
#include "RHIGPUReadback.h"
#include "TextureResource.h"
#include <atomic>
#include "Misc/Parse.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

using namespace Sailing;

namespace
{
	constexpr float kCloudBaseKm = 1.4f;
}

namespace
{
	// docs/overcast-brightness/: a closed stratus deck (the cache steps aside over 0.8 too: bClosedDeck), its diffuse
	// transmission onto a level white surface, and the sky light's share of it under the deck.
	float ClosedDeck(const Sailing::FWeatherState& W) { return FMath::SmoothStep(0.8f, 0.95f, float(W.Sky[Sailing::ECloudLayer::Stratus].Coverage)); }
	constexpr float kDeckDiffuse = 0.3f;
	constexpr float kDeckSkyLight = 0.25f;
	// docs/horizon-sky-colour/: the share of the visibility's aerosol the atmosphere carries (the fog keeps the rest);
	// -SailingAtmoHaze=<share> for measuring.
	constexpr float kAtmosphereHazeShare = 0.3f;
	float AtmosphereHazeShare()
	{
		float Share = kAtmosphereHazeShare;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingAtmoHaze="), Share);
		return FMath::Clamp(Share, 0.f, 1.f);
	}
	// C2: the sky cache's panorama: 4096 x 512 half floats over elevations -3 to 33 degrees (a cumulus base at 2 km is
	// under 22 degrees from 5 km out), 96 steps from 5 km to 40 km, the sky light's share of the dome's view luminance.
	constexpr int32 kSkyCacheWidth = 4096;
	constexpr int32 kSkyCacheHeight = 512;
	constexpr float kSkyCacheElMin = -3.f;
	constexpr float kSkyCacheElMax = 33.f;
	constexpr int32 kSkyCacheSteps = 96;
	// pc/ultra-sky-cache (docs/ultra-sky-cache): Ultra's own, finer panorama (the far small cumulus are drawn from it).
	constexpr int32 kSkyCacheWidthUltra = 8192;
	constexpr int32 kSkyCacheHeightUltra = 1024;
	constexpr int32 kSkyCacheStepsUltra = 192;
	struct FSkyCacheSize { int32 Width, Height, Steps; };
	/** The panorama's size and march for this tier; -SailingSkyCacheSize=<w>,<h>,<steps> (measuring) overrides it. Read where
	 *  the targets are made and at each panorama's start (not cached: a bench list or a settings change can swap it); the
	 *  strips follow the targets' own size. */
	FSkyCacheSize SkyCacheSize()
	{
		const bool bUltra = USailingSettings::Get()->Quality == ESailingQuality::Ultra;
		FSkyCacheSize S = bUltra ? FSkyCacheSize{ kSkyCacheWidthUltra, kSkyCacheHeightUltra, kSkyCacheStepsUltra } : FSkyCacheSize{ kSkyCacheWidth, kSkyCacheHeight, kSkyCacheSteps };
		FString Arg;
		TArray<FString> Parts;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingSkyCacheSize="), Arg, false) && Arg.ParseIntoArray(Parts, TEXT(",")) == 3)
		{
			S = { FMath::Clamp(FCString::Atoi(*Parts[0]), 256, 16384), FMath::Clamp(FCString::Atoi(*Parts[1]), 32, 4096), FMath::Clamp(FCString::Atoi(*Parts[2]), 8, 512) };
		}
		return S;
	}
	constexpr float kSkyCacheSplitM = 5000.f;
	constexpr float kNightDeckFullAtKm = 3.f; // docs/night-clouds/: the distance below which a ray's samples thin, under a night deck
	constexpr float kSkyCacheFarM = 40000.f;
	// The two lighting terms' scales, matched to the live clouds' brightness at the seam (lake-towers, 17:00: the mean,
	// 90th and 20th percentiles of the cloud pixels): Ultra's live clouds, with twice the view and four times the shadow
	// samples, read brighter than High's.
	constexpr float kSkyCacheSunHigh = 1.45f, kSkyCacheSkyHigh = 2.1f;
	constexpr float kSkyCacheSunUltra = 1.7f, kSkyCacheSkyUltra = 1.2f;
	// pc/ultra-cloud-tops: Ultra's cloud noise footprint floor (m) and cumulus top ramp (the material's 110 and 4 elsewhere).
	constexpr float kUltraCloudFootM = 60.f;
	constexpr float kUltraCloudEdgeTop = 5.f;
	constexpr float kUltraCloudBillow2 = 1.5f;   // the second billow octave's weight (0, off, elsewhere)
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
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> CloudCache(TEXT("/Game/Materials/M_CloudCache.M_CloudCache"));
	CloudCacheMaterial = CloudCache.Object;
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SkyProbeMat(TEXT("/Game/Materials/M_SkyEnvProbe.M_SkyEnvProbe"));
	SkyProbeMaterial = SkyProbeMat.Object;
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
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> WallMat(TEXT("/Game/Materials/M_RainWall.M_RainWall"));
	RainWall = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("RainWall"));
	RainWall->SetupAttachment(RootComponent);
	RainWall->SetStaticMesh(Plane.Object);
	RainWall->SetMaterial(0, WallMat.Object);
	RainWall->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RainWall->SetCastShadow(false);
	RainWall->NumCustomDataFloats = 3;
	RainWall->bVisibleInRayTracing = false;
	RainWall->SetAffectDistanceFieldLighting(false);
	RainWall->bAffectDynamicIndirectLighting = false;
	RainWall->SetUsingAbsoluteLocation(true);
	RainWall->SetUsingAbsoluteRotation(true);
	RainWall->SetUsingAbsoluteScale(true);
	RainWall->SetVisibility(false);

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

namespace
{
	// Perf 2: a directional light's virtual shadow map cache is keyed on its direction, so a sun turned a little every tick
	// threw the whole cache away every frame (4.6 ms of shadow depths on High at the helm's eye, the same with the cache
	// off). The lights move in 0.05 deg steps instead: about one step every 12 s at the sun's rate, a 1 cm shift of the
	// masthead's shadow; each step re-renders the shadow pages once.
	constexpr double kLightStepDeg = 0.05;

	bool LightTurned(const FRotator& Current, const FRotator& Want)
	{
		const double CosStep = FMath::Cos(FMath::DegreesToRadians(kLightStepDeg));
		return FVector::DotProduct(Current.Vector(), Want.Vector()) < CosStep;
	}
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
	// docs/hull-water-bounce (measuring): -SailingSkyLowerHemisphere=<grey>: the sky light's lower hemisphere that colour
	// instead of black (what Lumen's rays below the horizon return where they miss: the water isn't in its scene).
	float LowerGrey = -1.f;
	if (SkyLightActor && FParse::Value(SailingArgs::Dev(), TEXT("SailingSkyLowerHemisphere="), LowerGrey) && LowerGrey >= 0.f)
	{
		USkyLightComponent* SkyComp = SkyLightActor->GetLightComponent();
		SkyComp->bLowerHemisphereIsBlack = false;
		SkyComp->SetLowerHemisphereColor(FLinearColor(LowerGrey, LowerGrey, LowerGrey));
		SkyComp->RecaptureSky();
	}
	if (TActorIterator<AExponentialHeightFog> It(GetWorld()); It) Fog = *It;
	if (TActorIterator<AVolumetricCloud> It(GetWorld()); It) Clouds = *It;
	// Realism audit Oct 23 (docs/cumulus-rims/): the planet's ground under the atmosphere's multiple scattering is open
	// water and woods, about 0.1, not the engine's 0.4 grey, which lit the low sky grey from below (red over blue 0.51 at
	// 20 deg on the bridge view, 0.42 at 0.1).
	if (TActorIterator<ASkyAtmosphere> It(GetWorld()); It)
	{
		Atmosphere = *It;
		USkyAtmosphereComponent* Atmo = It->GetComponent();
		Atmo->SetGroundAlbedo(FLinearColor(0.1f, 0.1f, 0.1f).ToFColor(true));
	}
	if (TActorIterator<APostProcessVolume> It(GetWorld()); It) PostProcess = *It;
	// docs/hull-water-bounce (measuring): -SailingWaterGIProxy=<albedo> lays a 4 km plane of that grey at the water line,
	// hidden but lighting indirectly, so Lumen sees a stand-in for the water (its rings are procedural meshes: no distance
	// field, no surface cache cards) and the hull's bounce from below can be compared with and without it.
	float ProxyAlbedo = -1.f;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingWaterGIProxy="), ProxyAlbedo) && ProxyAlbedo >= 0.f)
	{
		UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
		UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
		TActorIterator<AWaterSurface> Water(GetWorld());
		if (Plane && Base && Water)
		{
			UStaticMeshComponent* Proxy = NewObject<UStaticMeshComponent>(this);
			Proxy->SetStaticMesh(Plane);
			Proxy->SetWorldLocation(FVector(Water->GetActorLocation().X, Water->GetActorLocation().Y, Water->GetActorLocation().Z - 3.0));
			Proxy->SetWorldScale3D(FVector(4000.0, 4000.0, 1.0));
			Proxy->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Proxy->SetCastShadow(false);
			Proxy->SetHiddenInGame(!FParse::Param(SailingArgs::Dev(), TEXT("SailingWaterGIProxyVisible")));   // visible: 3 cm under the water, for checking Lumen sees it
			Proxy->bAffectIndirectLightingWhileHidden = true;
			Proxy->RegisterComponent();
			UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Base, this);
			Mid->SetVectorParameterValue(TEXT("Color"), FLinearColor(ProxyAlbedo, ProxyAlbedo, ProxyAlbedo));
			Proxy->SetMaterial(0, Mid);
			UE_LOG(LogSailing, Display, TEXT("Water GI proxy: albedo %.3f at z %.0f cm"), ProxyAlbedo, Water->GetActorLocation().Z);
		}
	}

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
		&& !FParse::Param(SailingArgs::Dev(), TEXT("SailingClassicSky"));
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
			// light is actually lost (a cloud's own few kilometres), so far less jitter (the grain) at no cost. On High, 3 km
			// (docs/storm-headroom/): 1.1 ms off the storm view, the clouds' slice 9.5 -> 7.9 ms, and the lake's cumulus, the
			// storm overhead and two storm skies from outside the same to within the frames' jitter.
			CloudComp->SetShadowTracingDistance(Q == ESailingQuality::High ? 3.f : 4.f);
			float ShadowKm = 0.f;
			if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudShadowKm="), ShadowKm)) CloudComp->SetShadowTracingDistance(ShadowKm);
			FString Scales;
			if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudScale="), Scales, false))
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
		CumulusTopTexture = UTexture2D::CreateTransient(FWeatherMap::N, FWeatherMap::N, PF_R16F);
		CumulusTopTexture->SRGB = false;
		CumulusTopTexture->Filter = TF_Bilinear;
		CumulusTopTexture->AddressX = TA_Clamp;
		CumulusTopTexture->AddressY = TA_Clamp;
		CumulusTopTexture->CompressionSettings = TC_HDR;
		CumulusTopTexture->UpdateResource();
		if (CloudMaterial) CloudMaterial->SetTextureParameterValue(TEXT("CumulusTop"), CumulusTopTexture);
		// Graphics G6 (measuring): each layer's extinction relative to CloudDensity, -SailingCloudLayerExt=<cu>,<st>,<storm>,<rain>
		// (the material's LayerExtinction default otherwise).
		FString LayerExt;
		if (CloudMaterial && FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudLayerExt="), LayerExt, false))
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
		if (CloudMaterial && FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudStepDepth="), MaxStepDepth)) CloudMaterial->SetScalarParameterValue(TEXT("MaxStepDepth"), MaxStepDepth);
		// pc/ultra-cloud-tops (docs/ultra-cloud-tops): Ultra's own noise footprint floor, cumulus top ramp and second billow
		// octave. The material's defaults (110 m, 4, 0) stay every other tier's. Measuring: -SailingCloudFoot=<m>, -SailingCloudEdge=<ramp>,
		// -SailingCloudBillow2=<weight>.
		if (CloudMaterial)
		{
			const bool bUltraClouds = USailingSettings::Get()->Quality == ESailingQuality::Ultra;
			float Foot = bUltraClouds ? kUltraCloudFootM : 0.f, Edge = bUltraClouds ? kUltraCloudEdgeTop : 0.f, Billow2 = bUltraClouds ? kUltraCloudBillow2 : -1.f;
			FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudFoot="), Foot);
			FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudEdge="), Edge);
			FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudBillow2="), Billow2);
			if (Foot > 0.f) CloudMaterial->SetScalarParameterValue(TEXT("CloudFootFloor"), Foot);
			if (Edge > 0.f) CloudMaterial->SetScalarParameterValue(TEXT("CloudEdgeTop"), Edge);
			if (Billow2 >= 0.f) CloudMaterial->SetScalarParameterValue(TEXT("CloudBillow2"), Billow2);
		}
		FString NoisePath; // measuring: -SailingCloudNoise=<volume texture path>
		if (CloudMaterial && FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudNoise="), NoisePath))
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
		// C2 (Inputs/clouds-trees/plan.md): the sky cache, two panoramas of the far clouds (radiance terms and transmittance,
		// half floats) the dome cross-fades between; -SailingNoSkyCache keeps every cloud in the live march.
		bSkyCache = SkyMaterial && CloudMaterial && CloudCacheMaterial && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoSkyCache"));
		if (bSkyCache)
		{
			CacheMaterial = UMaterialInstanceDynamic::Create(CloudCacheMaterial, this);
			CacheMaterial->SetTextureParameterValue(TEXT("WeatherMap"), WeatherMapTexture);
			CacheMaterial->SetTextureParameterValue(TEXT("CumulusTop"), CumulusTopTexture);
			for (int32 I = 0; I < 2; ++I)
			{
				CacheTargets[I] = UKismetRenderingLibrary::CreateRenderTarget2D(this, SkyCacheSize().Width, SkyCacheSize().Height, RTF_RGBA16f, FLinearColor(0.f, 0.f, 1.f, 1.f));
				CacheTargets[I]->AddressX = TA_Wrap;
				CacheTargets[I]->AddressY = TA_Clamp;
			}
			SkyMaterial->SetTextureParameterValue(TEXT("CacheOld"), CacheTargets[0]);
			SkyMaterial->SetTextureParameterValue(TEXT("CacheNew"), CacheTargets[1]);
			if (UVolumetricCloudComponent* CloudComp = Clouds->FindComponentByClass<UVolumetricCloudComponent>())
			{
				CacheTraceKm = CloudComp->TracingMaxDistance;
				CacheTraceMode = uint8(CloudComp->TracingMaxDistanceMode);
			}
		}
	}
	// Visual V5 (High, not in the capture mode): water on the lens.
	if (USailingSettings::Get()->Quality >= ESailingQuality::High && LensWaterMaterial && PostProcess
		&& !FCString::Strifind(SailingArgs::Dev(), TEXT("SailingCapture=")))
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
	UpdateSkyCache(CamPos, DeltaSeconds);
	UpdateLowerHemisphere(GetWorld()->GetTimeSeconds());
	UpdateHaze();
	UpdateSkyline(CamPos);
	UpdateRain(CamPos);
	UpdateRainCurtains(CamPos, DeltaSeconds);
	UpdateRainWall(CamPos);
	if (WorldCollection)
	{
		// The trees on the shore sway with the wind there (MPC_World.Wind: direction it blows toward, speed with gusts).
		const FVector2D CamMap = SailingFrame::ToMap(GetWorld(), CamPos);
		const Vec3 V = GM->GetWind().VelocityAt(Vec3(CamMap.X, CamMap.Y, 10.0), GM->GetSimTime());
		const double Speed = V.LengthXY();
		const double Mean = FMath::Max(W.Wind.SpeedKnots * kKnot, 0.5);
		UKismetMaterialLibrary::SetVectorParameterValue(this, WorldCollection, TEXT("Wind"),
			FLinearColor(float(V.X / FMath::Max(Speed, 1e-3)), float(V.Y / FMath::Max(Speed, 1e-3)), float(Speed), float(FMath::Clamp(Speed / Mean - 1.0, 0.0, 1.0))));
		// Graphics G2: the water's height, for the wet band along the shores (M_Terrain).
		if (!WaterActor.IsValid()) { TActorIterator<AWaterSurface> It(GetWorld()); if (It) WaterActor = *It; }
		if (WaterActor.IsValid()) UKismetMaterialLibrary::SetScalarParameterValue(this, WorldCollection, TEXT("WaterZ"), float(WaterActor->GetActorLocation().Z));
		// E1: the world's wear site (0 lake, 1 bay, 2 Gulf) for M_WorldSurface's baked tiles, which carry no seed of their own.
		UKismetMaterialLibrary::SetScalarParameterValue(this, WorldCollection, TEXT("Site"), GM->GetLake().IsLoaded() ? float(int32(WearSiteFor(GM->GetLake()))) : 0.f);
		// marseille-look: the land's dress for M_Terrain and M_FarLand (0 prairie, 1 garrigue).
		UKismetMaterialLibrary::SetScalarParameterValue(this, WorldCollection, TEXT("Land"), GM->GetLake().IsLoaded() && GM->GetLake().IsGarrigue() ? 1.f : 0.f);
		// T1: the season on the trees, from the session's date (AutumnAmount, SpringAmount).
		UKismetMaterialLibrary::SetScalarParameterValue(this, WorldCollection, TEXT("Autumn"), AutumnAmount(GM->GetDayOfYear()));
		UKismetMaterialLibrary::SetScalarParameterValue(this, WorldCollection, TEXT("Spring"), SpringAmount(GM->GetDayOfYear()));
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
		ApplyCinematicLook(PP, CloudDarkness); // bCinematic is false on Low: clears its overrides
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
	ApplyCinematicLook(PP, CloudDarkness);
}

void ASailingEnvironment::ApplyCinematicLook(FPostProcessSettings& PP, double CloudDarkness)
{
	// Graphics G8 (docs/graphics-8/cinematic): the look of a photograph, on top of the V1 look. Everything here is a
	// post-process setting or a constant: the sun and its light are not touched (Perf 2 steps the sun so the virtual
	// shadow map cache survives). The grade is a generated LUT (warm highlights, cool shadows, lifted blacks); the tone
	// curve a little steeper in the middle; bloom wider and softer (Ultra: an FFT convolution with a generated kernel
	// that carries a faint horizontal streak); lens flare on Ultra only; vignette and a fine grain on every tier.
	PP.bOverride_ColorGradingLUT = PP.bOverride_ColorGradingIntensity = bCinematic;
	PP.bOverride_FilmSlope = PP.bOverride_FilmToe = PP.bOverride_FilmShoulder = bCinematic;
	PP.bOverride_BloomMethod = PP.bOverride_BloomSizeScale = PP.bOverride_BloomConvolutionTexture = PP.bOverride_BloomConvolutionSize = bCinematic;
	PP.bOverride_LensFlareBokehSize = PP.bOverride_LensFlareThreshold = bCinematic;
	if (!bCinematic)
	{
		return;
	}
	// A member, not a static: the cast-off reload makes a new environment actor, whose textures must load again.
	if (!bTriedLookLoad)
	{
		bTriedLookLoad = true;
		CinematicLUT = LoadObject<UTexture>(nullptr, TEXT("/Game/Look/T_CinematicLUT.T_CinematicLUT"), nullptr, LOAD_Quiet | LOAD_NoWarn);
		BloomKernel = LoadObject<UTexture2D>(nullptr, TEXT("/Game/Look/T_BloomKernel.T_BloomKernel"), nullptr, LOAD_Quiet | LOAD_NoWarn);
	}
	const float Dark = FMath::Clamp(float(CloudDarkness), 0.f, 1.f);
	const bool bUltra = USailingSettings::Get()->Quality == ESailingQuality::Ultra;
	// Under a storm deck the grade fades: gloom is grey, not teal and amber.
	PP.ColorGradingLUT = CinematicLUT;
	PP.bOverride_ColorGradingLUT = CinematicLUT != nullptr;
	PP.ColorGradingIntensity = FMath::Lerp(1.f, 0.4f, Dark);
	PP.FilmSlope = 0.92f;      // engine 0.88
	PP.FilmToe = 0.58f;        // engine 0.55: a little deeper shadows before the LUT lifts them
	PP.FilmShoulder = 0.24f;   // engine 0.26
	PP.VignetteIntensity = 0.45f;
	PP.FilmGrainIntensity = 0.06f;
	if (bUltra)
	{
		PP.BloomMethod = EBloomMethod::BM_FFT;
		PP.BloomConvolutionTexture = BloomKernel; // null: the engine's default kernel
		PP.bOverride_BloomConvolutionTexture = BloomKernel != nullptr;
		PP.BloomConvolutionSize = 1.f;
		PP.BloomIntensity = 0.5f;
		PP.LensFlareIntensity = 0.12f;   // 0.25 with a 3-wide bokeh drew a halo disc round the sun (Galveston dusk)
		PP.LensFlareBokehSize = 1.2f;
		PP.LensFlareThreshold = 6.f;
	}
	else
	{
		PP.BloomMethod = EBloomMethod::BM_SOG;
		PP.BloomIntensity = 0.6f;
		PP.BloomSizeScale = 6.f;   // engine 4: wider, softer
		PP.bOverride_BloomConvolutionTexture = PP.bOverride_BloomConvolutionSize = false;
		PP.bOverride_LensFlareBokehSize = PP.bOverride_LensFlareThreshold = false;
	}
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
	if (PostProcess && !bPhysicalCamera && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoNightExposure")))
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
		if (APlayerCameraManager* CamMgr = UGameplayStatics::GetPlayerCameraManager(this, 0)) Cam = SailingFrame::ToMapCm(GetWorld(), CamMgr->GetCameraLocation()) / CmPerMeter;
		const FGustFront& F = W.Front;
		const double Seen = LastWeatherMap.SunTransmittance(W.Sky, F, F.SpeedMs * (GM->GetSimTime() - F.StartTime), GM->GetWeatherTime(), Cam.X, Cam.Y,
			FMath::Cos(E) * FMath::Cos(A), FMath::Cos(E) * FMath::Sin(A), FMath::Sin(E));
		SunVisibility = FMath::FInterpTo(SunVisibility, float(Seen), GetWorld()->GetDeltaSeconds(), 1.5f);
		// docs/overcast-brightness/: the 12% floor stood for the light a deck scatters down. Under a closed deck that light
		// now comes from the deck itself (its base glows, DeckGlow below, and the sky light carries it to the ground), so the
		// direct beam has no floor there.
		const float Floor = 0.12f * (1.f - ClosedDeck(W));
		CloudShade = Floor + (1.f - Floor) * SunVisibility;
	}
	// -SailingCloudShade=<0..1> (measuring): the direct sun reaching the camera held, so a cloud's shadow can be compared
	// still for still (the cells' shadows don't land at the same moment run to run).
	{
		static uint32 ShadeGen = MAX_uint32;
		static float ShadeArg = -1.f;
		if (ShadeGen != SailingArgs::Generation())
		{
			ShadeGen = SailingArgs::Generation();
			ShadeArg = -1.f;
			FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudShade="), ShadeArg);
		}
		if (ShadeArg >= 0.f) CloudShade = FMath::Clamp(ShadeArg, 0.f, 1.f);
	}
	if (PostProcess)
	{
		{
			const ASailboatPawn* Pawn = Cast<ASailboatPawn>(UGameplayStatics::GetPlayerPawn(this, 0));
			bCinematic = UsesCinematicLook(USailingSettings::Get()->Quality, USailingSettings::Get()->bCinematicLook, Pawn && Pawn->IsPhotoMode(), Pawn && Pawn->IsCaptureMode());
		}
		ApplyCameraLook(bPhysicalCamera, W.CloudDarkness);
		if (bPhysicalCamera)
		{
			// Visual V1: exposure follows the light, as an incident meter would (VisualPipeline.h), with a little room
			// for the histogram to react to framing.
			const double EV = CameraEV100(Elevation, CloudShade, W.CloudDarkness, MoonEl, MoonIllumination(MoonAge), NightFloorEV);
			LastCloudShade = CloudShade;
			LastCameraEV = EV;
			// Graphics G5: the haze is lit by the same light the exposure meters. A fixed inscattering colour stayed at
			// midday brightness while the exposure opened 4-5 stops for a low sun, so at sunset the horizon blew out
			// white and hid the sun's disc (the blind test's sunsets).
			static const double ClearNoonEV = CameraEV100(60.0, 1.0, 0.0, -90.0, 0.0, -20.0);
			HazeLight = FMath::Clamp(float(FMath::Pow(2.0, EV - ClearNoonEV)), 0.004f, 1.f);
			FPostProcessSettings& PP = PostProcess->Settings;
			PP.bOverride_AutoExposureMethod = PP.bOverride_AutoExposureMinBrightness = PP.bOverride_AutoExposureMaxBrightness = PP.bOverride_AutoExposureBias = true;
			PP.AutoExposureMethod = EAutoExposureMethod::AEM_Histogram;
			// Under a storm deck the band narrows: the eye does not brighten the gloom much (Phase 8, fix 7).
			// In clear air the band matches the Phase 8 look (a camera's auto exposure, as in the reference clips) and fades out
			// under the deck. No lift: Phase 8's half stop in clear air (from the reference video) put the clear sky on the tone
			// curve's shoulder, half a stop over a still camera's, and washed the low sky and the dusk glow (Bean's choice,
			// docs/exposure-choice/).
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
			PP.AutoExposureBias = USailingSettings::Get()->BrightnessBias();   // Settings > Brightness
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
		const FRotator MoonRot(-FMath::Max(MoonEl, 25.0), MoonAz + 180.0, 0.0);
		if (LightTurned(MoonLight->GetComponentRotation(), MoonRot)) MoonLight->SetWorldRotation(MoonRot);
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
		const FRotator SunRot(-FMath::Max(Elevation, -4.0), Azimuth + 180.0, 0.0);
		if (LightTurned(Sun->GetActorRotation(), SunRot)) Sun->SetActorRotation(SunRot);
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
		// Perf 3: two more setters rebuild the light the same way (the engine marks its render state dirty whenever the
		// value changes), and both follow the cloud shade, which the weather map moves a little every frame while the
		// clouds drift. A rebuilt light starts its virtual shadow map cache afresh, so every frame redrew every caster:
		// about 4 ms of render thread on the PC's parked soak, climbing as the sun's shadows lengthened (the +2 ms/h
		// frame-time drift; with the clock frozen the shade stopped moving and the drift went). They step by 0.04 like
		// the scales above, and snap to their sunshine value exactly.
		auto Stepped = [](float Current, float Want) { return FMath::Abs(Current - Want) > 0.04f || (Want >= 1.f && Current < 1.f); };
		// The haze and rain under a storm deck aren't sunlit: no glowing white fog (volumetric fog has no cloud shadow).
		const float Scatter = FMath::Clamp(CloudShade * 1.2f, 0.05f, 1.f);
		if (Stepped(SunComp->VolumetricScatteringIntensity, Scatter)) SunComp->SetVolumetricScatteringIntensity(Scatter);
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
			if (Stepped(Dir->AtmosphereSunDiskColorScale.R, Disk)) Dir->SetAtmosphereSunDiskColorScale(FLinearColor(Disk, Disk, Disk));
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
		// docs/overcast-brightness/: under a closed deck, a quarter. Lit from the glowing deck at full strength the ground
		// read about half the deck's brightness (a lawn's albedo is a fifth): grass, trees and water as bright as an overcast
		// that photos show near white over them. Measured against the G5 overcast shore (deck to trees about 9:1 there).
		SkyLightActor->GetLightComponent()->SetIntensity(SkyIntensity * FMath::Lerp(1.f, kDeckSkyLight, ClosedDeck(W)) * (1.f - 0.6f * float(W.CloudDarkness)) * FMath::Lerp(1.f, 0.08f, Night));
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
			// (No half-stop lift in clear air: docs/exposure-choice/.)
			PostProcess->Settings.AutoExposureBias = -1.5f * float(W.CloudDarkness) + USailingSettings::Get()->BrightnessBias();   // + Settings > Brightness
		}
		// Under the deck the light is grey, not blue: the sky's blue comes from above the cloud and never reaches the
		// lake (Phase 8 blind test: the storm frames read as a clear dusk). Fair-weather days are untouched.
		// (Not at night, docs/night-clouds/: under the deck then the light is the towns', warm off its base, and the grey cut
		// it to a colourless sheet.)
		const float Grey = FMath::SmoothStep(0.3f, 0.8f, float(W.CloudDarkness)) * (1.f - NightAmount);
		PostProcess->Settings.bOverride_ColorSaturation = true;
		PostProcess->Settings.ColorSaturation = FVector4(1.f, 1.f, 1.f, 1.f - 0.7f * Grey);
	}
}

void ASailingEnvironment::UpdateRain(const FVector& CameraPos)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FWeatherState& W = GM->GetWeatherState();
	// W5b: the rain where the camera is (a storm's falls under its core, not everywhere at once).
	const FVector2D CamMap = SailingFrame::ToMap(GetWorld(), CameraPos);
	const double RainHere = GM->GetRainAt(CamMap.X, CamMap.Y);
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
	const FVector2D CamMap = SailingFrame::ToMap(GetWorld(), CameraPos);   // the rain field is in the map frame
	const double Cx = CamMap.X, Cy = CamMap.Y;
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
			const double BaseM = W.Front.bActive && !W.bSquall ? FStormShape::CoreBaseM : FMath::Max(W.Sky[ECloudLayer::Stratus].BaseKm * 1000.0, 300.0);
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
	const double BaseM = W.Front.bActive && !W.bSquall ? FStormShape::CoreBaseM : FMath::Max(W.Sky[ECloudLayer::Stratus].BaseKm * 1000.0, 300.0);
	// The foot runs ahead of the core toward where the storm is going.
	const double Move = W.Front.MoveDegrees * kDegToRad;
	const FVector FootShift = W.Front.bActive && !W.bSquall ? FVector(FMath::Cos(Move), FMath::Sin(Move), 0.0) * FStormRain::FootReachM : FVector::ZeroVector;
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
		const FTransform Veil(Q, SailingFrame::FromMapCm(GetWorld(), (P + FVector(0, 0, 0.5 * BaseM)) * CmPerMeter), FVector(2200.0, BaseM, 1.0));
		const FTransform Foot(Q, SailingFrame::FromMapCm(GetWorld(), (P + FootShift + FVector(0, 0, 110.0)) * CmPerMeter), FVector(3300.0, 220.0, 1.0));
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

void ASailingEnvironment::UpdateRainWall(const FVector& CameraPos)
{
	// docs/storm-gloom/: seen from ahead of the storm, the air under its deck read as a lit, clear horizon (the gap under
	// the shelf, the horizon beneath the core: the height fog's inscatter, which takes no shadow from the deck). One long
	// card on the front's line under the core's leading edge, from the water to just under the shelf's base, unfogged and
	// lit by the sun through the deck (M_RainWall). It fades as the camera comes within a few kilometres of it: closer, the
	// haze and fog carry the storm's visibility (FWeatherState::LocalizeStorm). A marched gloom in the clouds looked the
	// same and cost 5 ms on the storm view (every view sample under the deck took shadow rays).
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !RainWall) return;
	static SailingArgs::FCachedFlag NoWallArg(TEXT("SailingNoRainWall"));
	const FWeatherState& W = GM->GetWeatherState();
	const FGustFront& F = W.Front;
	const double Now = GM->GetSimTime();
	const FVector2D Cam = SailingFrame::ToMap(GetWorld(), CameraPos);
	constexpr double BehindM = 1200.0, TopM = 420.0, WidthM = 40000.0;
	const double CamAhead = F.bActive ? F.DistanceAhead(Cam.X, Cam.Y, Now) + BehindM : -1e9;
	const double Amount = F.bActive && !W.bSquall && !NoWallArg.Get()
		? FMath::Clamp(W.Sky[ECloudLayer::Storm].Coverage * 1.5, 0.0, 1.0) * FMath::SmoothStep(1500.0, 3500.0, CamAhead) : 0.0;
	RainWall->SetVisibility(Amount > 0.01);
	if (Amount <= 0.01) return;
	if (RainWall->GetInstanceCount() != 1)
	{
		RainWall->ClearInstances();
		RainWall->AddInstance(FTransform::Identity, true);
	}
	// On the front's line BehindM behind it, abeam of the camera, facing the way the storm moves.
	const double A = F.MoveDegrees * kDegToRad;
	const FVector Dir(FMath::Cos(A), FMath::Sin(A), 0.0);
	const FVector At = FVector(Cam.X, Cam.Y, 0.0) - Dir * CamAhead;
	const FVector Up(0, 0, 1), Side = FVector::CrossProduct(Up, Dir);
	const FQuat Q(FMatrix(Side, Up, Dir, FVector::ZeroVector));
	RainWall->UpdateInstanceTransform(0, FTransform(Q, SailingFrame::FromMapCm(GetWorld(), (At + FVector(0, 0, 0.5 * TopM)) * CmPerMeter),
		FVector(WidthM, TopM, 1.0)), true, false, true);
	const double Shade = SunDirection.Z > 0.0 ? LastWeatherMap.SunTransmittance(W.Sky, F, F.SpeedMs * (Now - F.StartTime), GM->GetWeatherTime(),
		At.X, At.Y, SunDirection.X, SunDirection.Y, SunDirection.Z) : 0.0;
	RainWall->SetCustomDataValue(0, 0, float(Amount), false);
	RainWall->SetCustomDataValue(0, 1, float(TopM), false);
	RainWall->SetCustomDataValue(0, 2, float(Shade), false);
	RainWall->MarkRenderStateDirty();
}

void ASailingEnvironment::UpdateLightning(float DeltaSeconds, const FVector& CameraPos)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const auto& Strikes = GM->GetWeather().GetStrikes();
	const double T = GM->GetWeatherTime();
	const FVector2D Listener = SailingFrame::ToMap(GetWorld(), CameraPos);

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
			BuildBolt(SailingFrame::ToWorld(GetWorld(), S.X, S.Y, 0.0), (bLayeredClouds ? 0.7f : kCloudBaseKm) * 1000.f * CmPerMeter);
			BoltTime = 0.f;
			BoltLight->SetWorldLocation(SailingFrame::ToWorld(GetWorld(), S.X, S.Y, 300.0));
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
		if (CumulusTopTexture && Done.TopHalf.Num() == FWeatherMap::N * FWeatherMap::N)
		{
			uint8* TopCopy = new uint8[Done.TopHalf.Num() * sizeof(FFloat16)];
			FMemory::Memcpy(TopCopy, Done.TopHalf.GetData(), Done.TopHalf.Num() * sizeof(FFloat16));
			FUpdateTextureRegion2D* TopRegion = new FUpdateTextureRegion2D(0, 0, 0, 0, FWeatherMap::N, FWeatherMap::N);
			CumulusTopTexture->UpdateTextureRegions(0, 1, TopRegion, FWeatherMap::N * 2, 2, TopCopy, [](uint8* Data, const FUpdateTextureRegion2D* R) { delete[] Data; delete R; });
		}
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
		const FVector2D CamMap = SailingFrame::ToMap(GetWorld(), CameraPos);   // the weather map is painted in the map frame
		const double Cx = CamMap.X, Cy = CamMap.Y;
		// World streaming: a copy of the terrain (it shares the heights): the tiles may be swapped while the worker reads.
		TSharedPtr<const Sailing::FLakeTerrain> Terrain;
		if (Lake) Terrain = MakeShared<const Sailing::FLakeTerrain>(Lake->Terrain);
		PendingWeatherMap = Async(EAsyncExecution::ThreadPool, [Sky, Front, Terrain, Cx, Cy, Tw]()
		{
			FWeatherMap Map;
			if (Terrain)
			{
				// Cumulus build over the heated land, not the lake.
				Map.LandFraction = [Terrain](double X, double Y) { return FMath::Clamp((Terrain->HeightAt(X, Y) + 0.5) / 2.0, 0.0, 1.0); };
			}
			Map.Paint(Sky, Front, Cx, Cy, Tw);
			FWeatherMapFrame Out;
			Out.Half.SetNumUninitialized(int32(Map.Pixels().size()));
			for (int32 I = 0; I < Out.Half.Num(); ++I) Out.Half[I] = FFloat16(Map.Pixels()[I]);
			Out.TopHalf.SetNumUninitialized(int32(Map.CumulusTop().size()));
			for (int32 I = 0; I < Out.TopHalf.Num(); ++I) Out.TopHalf[I] = FFloat16(Map.CumulusTop()[I]);
			Out.Map = MoveTemp(Map);
			return Out;
		});
		bWeatherMapPending = true;
	}
	auto Layer = [](const FCloudLayer& L) { return FLinearColor(float(L.Coverage), float(L.BaseKm), float(L.TopKm), float(L.Density)); };
	CloudMaterial->SetVectorParameterValue(TEXT("LayerCumulus"), Layer(W.Sky[ECloudLayer::Cumulus]));
	CloudMaterial->SetVectorParameterValue(TEXT("LayerStratus"), Layer(W.Sky[ECloudLayer::Stratus]));
	// docs/overcast-brightness/: a closed deck's base glows with the sun diffused down through it, about 0.3 of it on a level
	// white surface for an overcast's stratus (optical depth about 20), less as the deck thickens toward rain and storm.
	CloudMaterial->SetVectorParameterValue(TEXT("DeckGlow"), FLinearColor(kDeckDiffuse * ClosedDeck(W) * (1.f - float(W.CloudDarkness)), 0.f, 0.f, 0.f));
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

/** docs/sky-lower-hemisphere: M_SkyEnvProbe's 1x1 target copied back without a stall (the render thread fills Value). */
struct FSkyProbeReadback
{
	TUniquePtr<FRHIGPUTextureReadback> Readback = MakeUnique<FRHIGPUTextureReadback>(TEXT("SkyEnvProbe"));
	std::atomic<bool> bInFlight{ false };
	FCriticalSection Guard;
	FLinearColor Value = FLinearColor::Black;   // the sky's mean radiance
	FLinearColor Sun = FLinearColor::Black;     // the sun's illuminance on the horizontal water
	bool bHasValue = false;
};

namespace
{
	// The water's reflectance of a diffuse sky (Fresnel averaged over the hemisphere, cosine weighted: about 0.066 for n
	// 1.33) and the body's upwelling seen from above: a deep body's diffuse reflectance from its single-scattering albedo,
	// (1 - sqrt(1 - a)) / (1 + sqrt(1 - a)) per channel, times 0.55 for the light crossing the surface down and back up.
	// The albedos mirror WaterBodyFor (WaterSurface.cpp): lake, bay, Gulf, Marseille.
	constexpr float kWaterSkyFresnel = 0.066f;
	FLinearColor WaterUpwelling(int32 World)
	{
		const FLinearColor A = (World == 1 || World == 4) ? FLinearColor(0.15f, 0.20f, 0.14f)
			: World == 2 ? FLinearColor(0.08f, 0.16f, 0.13f)
			: World == 3 ? FLinearColor(0.02f, 0.09f, 0.16f)
			: FLinearColor(0.16f, 0.18f, 0.11f);
		auto R = [](float Albedo) { const float S = FMath::Sqrt(FMath::Max(0.f, 1.f - Albedo)); return 0.55f * (1.f - S) / (1.f + S); };
		return FLinearColor(R(A.R), R(A.G), R(A.B));
	}
}

void ASailingEnvironment::UpdateLowerHemisphere(double Now)
{
	static SailingArgs::FCachedFlag NoBounceArg(TEXT("SailingNoWaterBounce"));
	USkyLightComponent* SkyComp = SkyLightActor ? SkyLightActor->GetLightComponent() : nullptr;
	float FixedGrey = -1.f;   // measuring: -SailingSkyLowerHemisphere=<grey> sets a fixed grey instead (FindSceneActors)
	FParse::Value(SailingArgs::Dev(), TEXT("SailingSkyLowerHemisphere="), FixedGrey);
	if (!SkyComp || NoBounceArg.Get() || FixedGrey >= 0.f || !SkyProbeMaterial || USailingSettings::Get()->Quality == ESailingQuality::Low) return;
	if (!SkyProbeTarget)
	{
		SkyProbeTarget = UKismetRenderingLibrary::CreateRenderTarget2D(this, 2, 1, RTF_RGBA16f, FLinearColor::Black);
		SkyProbe = MakeShared<FSkyProbeReadback, ESPMode::ThreadSafe>();
	}
	// The last readback, once it has landed. The water's radiance upward: its Fresnel reflection of the sky (0.066 of the
	// sky's mean radiance) and the body's upwelling of the sky and of the sun (R_body x their radiance and the sun's
	// horizontal illuminance over pi; the sun's specular glint isn't diffuse and stays out), in the sky light's own units
	// (the probe includes its intensity and colour, the lower hemisphere doesn't). Set only when it moves 2%.
	FLinearColor Probe = FLinearColor::Black, SunIll = FLinearColor::Black;
	bool bNew = false;
	{
		FScopeLock Lock(&SkyProbe->Guard);
		if (SkyProbe->bHasValue) { Probe = SkyProbe->Value; SunIll = SkyProbe->Sun; SkyProbe->bHasValue = false; bNew = true; }
	}
	if (bNew)
	{
		const FLinearColor Light = SkyComp->GetLightColor() * FMath::Max(SkyComp->Intensity, 1e-4f);
		const FLinearColor Body = WaterUpwelling(USailingSettings::Get()->World);
		// The probe's sun is the light through the atmosphere, not through the clouds: the clouds take the direct sun off the
		// scene by the light's diffuse scale (UpdateSun: its intensity keeps a 0.35 floor for the storm sky's sake), so the
		// sunlight that actually reaches the water is the probe's times that scale.
		const float SunDirect = Sun ? Sun->GetLightComponent()->DiffuseScale : 1.f;
		const FLinearColor Up = (FLinearColor(kWaterSkyFresnel, kWaterSkyFresnel, kWaterSkyFresnel) + Body) * Probe + Body * SunIll * (SunDirect / PI);
		const FLinearColor Lower(Up.R / FMath::Max(Light.R, 1e-4f), Up.G / FMath::Max(Light.G, 1e-4f), Up.B / FMath::Max(Light.B, 1e-4f));
		const float Change = FMath::Abs(Lower.GetLuminance() - AppliedLowerHemisphere.GetLuminance()) / FMath::Max(Lower.GetLuminance(), 1e-6f);
		if (AppliedLowerHemisphere.R < 0.f || Change > 0.02f)
		{
			SkyComp->bLowerHemisphereIsBlack = false;
			SkyComp->SetLowerHemisphereColor(Lower);
			const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
			UE_LOG(LogSailing, Log, TEXT("Water bounce: sky mean (%.4f, %.4f, %.4f), sun on the water (%.4f, %.4f, %.4f) x direct %.2f, lower hemisphere (%.5f, %.5f, %.5f), x sky light %.3f = (%.5f, %.5f, %.5f); sun light %.3f, cloud shade %.2f, cloud darkness %.2f"),
				Probe.R, Probe.G, Probe.B, SunIll.R, SunIll.G, SunIll.B, SunDirect, Lower.R, Lower.G, Lower.B, SkyComp->Intensity,
				Lower.R * SkyComp->Intensity, Lower.G * SkyComp->Intensity, Lower.B * SkyComp->Intensity,
				Sun ? Sun->GetLightComponent()->Intensity : -1.f, LastCloudShade, GM ? float(GM->GetWeatherState().CloudDarkness) : -1.f);
			AppliedLowerHemisphere = Lower;
		}
	}
	// A new probe every two seconds: draw, copy back on the render thread, and poll until the copy is ready.
	if (!SkyProbe->bInFlight && Now >= NextSkyProbe)
	{
		NextSkyProbe = Now + 2.0;
		UCanvas* Canvas = nullptr;
		FVector2D Size;
		FDrawToRenderTargetContext Context;
		UKismetRenderingLibrary::BeginDrawCanvasToRenderTarget(this, SkyProbeTarget, Canvas, Size, Context);
		if (Canvas) Canvas->K2_DrawMaterial(SkyProbeMaterial, FVector2D::ZeroVector, FVector2D(2.0, 1.0), FVector2D::ZeroVector);
		UKismetRenderingLibrary::EndDrawCanvasToRenderTarget(this, Context);
		SkyProbe->bInFlight = true;
		FTextureRenderTargetResource* Res = SkyProbeTarget->GameThread_GetRenderTargetResource();
		TSharedPtr<FSkyProbeReadback, ESPMode::ThreadSafe> State = SkyProbe;
		ENQUEUE_RENDER_COMMAND(SkyProbeCopy)([State, Res](FRHICommandListImmediate& RHICmdList)
		{
			if (Res && Res->GetRenderTargetTexture()) State->Readback->EnqueueCopy(RHICmdList, Res->GetRenderTargetTexture());
			else State->bInFlight = false;
		});
	}
	else if (SkyProbe->bInFlight)
	{
		TSharedPtr<FSkyProbeReadback, ESPMode::ThreadSafe> State = SkyProbe;
		ENQUEUE_RENDER_COMMAND(SkyProbePoll)([State](FRHICommandListImmediate& RHICmdList)
		{
			if (!State->bInFlight || !State->Readback->IsReady()) return;
			int32 RowPitch = 0;
			if (const FFloat16Color* Px = static_cast<const FFloat16Color*>(State->Readback->Lock(RowPitch)))
			{
				FScopeLock Lock(&State->Guard);
				State->Value = FLinearColor(Px[0].R.GetFloat(), Px[0].G.GetFloat(), Px[0].B.GetFloat());
				State->Sun = FLinearColor(Px[1].R.GetFloat(), Px[1].G.GetFloat(), Px[1].B.GetFloat());
				State->bHasValue = true;
			}
			State->Readback->Unlock();
			State->bInFlight = false;
		});
	}
}

void ASailingEnvironment::UpdateSkyCache(const FVector& CameraPos, float DeltaSeconds)
{
	if (!bSkyCache || !CacheMaterial || !CloudMaterial || !SkyMaterial) return;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const double Now = GetWorld()->GetTimeSeconds();
	const FWeatherState& W = GM->GetWeatherState();
	// Not under a storm (yet): the shelf's lit face is emission in CLOUD_CODE and the deck's slate albedo, which the
	// cache's two lighting terms don't carry (its storm came out a black-brown deck). While a storm is in the sky the
	// live clouds take the whole sky back, as they were before the cache; it starts again when the storm has gone.
	// docs/night-clouds/: nor under a deck at night: its base lit by the towns is emission too, and the cache's night
	// ambient met the live deck in a bright rim. Scattered night cumulus keep the cache (M_SkyDome adds their glow).
	const bool bNightDeck = NightAmount > 0.5f && W.Sky[ECloudLayer::Stratus].Coverage > 0.3;
	// Realism audit 6 (docs/overcast-edge/): nor under a closed deck by day. The far deck is behind the haze (90% at the
	// horizon), so the cache's panorama hardly shows, and with the live clouds stopped at 5 km the overcast ended there
	// in a curved edge with clear-looking sky below it. The live march carries a deck to the horizon (as with
	// -SailingNoSkyCache).
	const bool bClosedDeck = W.Sky[ECloudLayer::Stratus].Coverage > 0.8;
	const bool bStorm = (W.Front.bActive && W.Sky[ECloudLayer::Storm].Coverage > 0.02) || bNightDeck || bClosedDeck;
	// docs/night-clouds/ (banding): under that deck the rays up through it keep their samples. UE thins a ray's samples in
	// proportion below r.VolumetricCloud.DistanceToSampleMaxCount; at the live clouds' 15 km a ray up through a 0.7 km
	// deck got 80 x 0.7 / 15, about 4, and the overcast came out in rings round the zenith. 3 km (Ultra's): about 19.
	if (IConsoleVariable* FullAtCv = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.DistanceToSampleMaxCount")))
	{
		if (bNightDeck && FullAtCv->GetFloat() > kNightDeckFullAtKm)
		{
			NightDeckFullAtKm = FullAtCv->GetFloat();
			FullAtCv->Set(kNightDeckFullAtKm, ECVF_SetByCode);
		}
		else if (!bNightDeck && NightDeckFullAtKm > 0.f)
		{
			FullAtCv->Set(NightDeckFullAtKm, ECVF_SetByCode);
			NightDeckFullAtKm = 0.f;
		}
	}
	if (bStorm)
	{
		if (bCacheReady)
		{
			bCacheReady = false;
			CacheColumn = 0;
			CloudMaterial->SetVectorParameterValue(TEXT("CacheSplit"), FLinearColor(kSkyCacheSplitM - 500.f, kSkyCacheSplitM, 0.f, 0.f));
			if (UVolumetricCloudComponent* CloudComp = Clouds->FindComponentByClass<UVolumetricCloudComponent>())
			{
				CloudComp->TracingMaxDistanceMode = EVolumetricCloudTracingMaxDistanceMode(CacheTraceMode);
				CloudComp->SetTracingMaxDistance(CacheTraceKm);
			}
			if (CacheFullAtKm > 0.f) if (IConsoleVariable* FullAt = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.DistanceToSampleMaxCount"))) FullAt->Set(CacheFullAtKm, ECVF_SetByCode);
		}
		SkyMaterial->SetVectorParameterValue(TEXT("CacheParams"), FLinearColor(0.f, 1.f, kSkyCacheElMin, kSkyCacheElMax));
		return;
	}
	// The dome cross-fades from the old panorama to the new one over half a second; the next refresh waits for it (it
	// draws into the old one).
	const float Blend = float(FMath::Clamp((Now - CacheSwapTime) / 0.5, 0.0, 1.0));
	SkyMaterial->SetVectorParameterValue(TEXT("CacheParams"), FLinearColor(bCacheReady ? 1.f : 0.f, Blend, kSkyCacheElMin, kSkyCacheElMax));
	FLinearColor SunLum;
	CloudMaterial->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("SunLum")), SunLum);
	// Measuring: -SailingSkyCacheLight=<sun>,<sky> scales the two lighting terms (matching the live clouds at the seam).
	const bool bUltraSky = USailingSettings::Get()->Quality == ESailingQuality::Ultra;
	static float SunScale = 1.f, SkyScale = 1.f;
	static bool bScales = false;
	if (!bScales)
	{
		bScales = true;
		SunScale = bUltraSky ? kSkyCacheSunUltra : kSkyCacheSunHigh;
		SkyScale = bUltraSky ? kSkyCacheSkyUltra : kSkyCacheSkyHigh;
		FString L, A, B;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingSkyCacheLight="), L, false) && L.Split(TEXT(","), &A, &B)) { SunScale = FCString::Atof(*A); SkyScale = FCString::Atof(*B); }
	}
	SkyMaterial->SetVectorParameterValue(TEXT("CacheSun"), FLinearColor(SunScale, 0.f, 0.f, SkyScale));
	if (Blend < 1.f) return;

	// A whole panorama every four seconds: a strip of columns a frame (fair-weather cumulus drift a few tens of metres in
	// that time, nothing at 5 km and beyond).
	const double Refresh = 4.0;
	if (CacheColumn == 0)
	{
		// Not before the first weather map (about 2 s in): started at once, the first panorama read the empty map with the
		// default WeatherRect and drew another sky's clouds for its first 4 s (seen on the Mac's recording).
		if (!bHasWeatherMap) return;
		// One camera and one set of cloud parameters for the whole panorama, so its strips agree.
		CacheRefreshStart = Now;
		const FVector CacheCam = SailingFrame::ToMapCm(GetWorld(), CameraPos);   // the material's positions are in the map frame
		CacheMaterial->SetVectorParameterValue(TEXT("CacheCam"), FLinearColor(float(CacheCam.X), float(CacheCam.Y), float(CacheCam.Z), 0.f));
		static const TCHAR* Vectors[] = { TEXT("WeatherRect"), TEXT("LayerCumulus"), TEXT("LayerStratus"), TEXT("LayerCirrus"), TEXT("FrontA"), TEXT("FrontB"),
			TEXT("Drift"), TEXT("LayerExtinction"), TEXT("SunLum"), TEXT("SunDir"), TEXT("TracerShadow") };
		for (const TCHAR* Name : Vectors)
		{
			FLinearColor V;
			if (CloudMaterial->GetVectorParameterValue(FHashedMaterialParameterInfo(Name), V)) CacheMaterial->SetVectorParameterValue(Name, V);
		}
		for (const TCHAR* Name : { TEXT("CloudDensity"), TEXT("MaxStepDepth"), TEXT("CloudFootFloor"), TEXT("CloudEdgeTop"), TEXT("CloudBillow2") })   // pc/ultra-cloud-tops: Ultra's three as the live clouds
		{
			float S;
			if (CloudMaterial->GetScalarParameterValue(FHashedMaterialParameterInfo(Name), S)) CacheMaterial->SetScalarParameterValue(Name, S);
		}
		// The slab (m) and the march: from where the live clouds hand over to 40 km, SkyCacheSize().Steps steps; the material's
		// step caps (CLOUD_CODE) read Tracer as the live material does.
		double BaseKm = 0.0, TopKm = 0.0;
		W.Sky.Span(BaseKm, TopKm);
		TopKm = FMath::Max(TopKm, double(W.CloudTopKm));
		CacheMaterial->SetVectorParameterValue(TEXT("CacheMax"), FLinearColor(kSkyCacheFarM, float(BaseKm * 1000.0 - 50.0), float(TopKm * 1000.0 + 100.0), float(SkyCacheSize().Steps)));
		CacheMaterial->SetVectorParameterValue(TEXT("Tracer"), FLinearColor(float(TopKm - BaseKm + 0.15), float(SkyCacheSize().Steps), 0.f, kSkyCacheFarM / 1000.f));
		CacheMaterial->SetVectorParameterValue(TEXT("CacheSplit"), FLinearColor(kSkyCacheSplitM - 500.f, kSkyCacheSplitM, 0.f, 0.f));
		CacheMaterial->SetVectorParameterValue(TEXT("CacheEl"), FLinearColor(kSkyCacheElMin, kSkyCacheElMax, 0.f, 0.f));
		// Shadow step (m), this refresh's number (its jitter) and its weight against the panorama before. Each replaces
		// the last: blended a third at a time, the clouds' drift between refreshes stacked into ghosts.
		++CacheRefreshes;
		CacheMaterial->SetVectorParameterValue(TEXT("CacheShadow"), FLinearColor(300.f, float(CacheRefreshes % 97), 1.f, 0.f));
		CacheMaterial->SetTextureParameterValue(TEXT("CachePrev"), CacheTargets[1 - CacheBack]);
	}
	const int32 CacheW = CacheTargets[CacheBack]->SizeX, CacheH = CacheTargets[CacheBack]->SizeY;   // Ultra's finer panorama too
	CacheColumnCarry += float(CacheW) * DeltaSeconds / float(Refresh);
	const int32 Columns = FMath::Clamp(int32(CacheColumnCarry), 1, CacheW - CacheColumn);
	CacheColumnCarry = FMath::Max(0.f, CacheColumnCarry - float(Columns));
	UCanvas* Canvas = nullptr;
	FVector2D Size;
	FDrawToRenderTargetContext Context;
	UKismetRenderingLibrary::BeginDrawCanvasToRenderTarget(this, CacheTargets[CacheBack], Canvas, Size, Context);
	if (Canvas)
	{
		Canvas->K2_DrawMaterial(CacheMaterial, FVector2D(CacheColumn, 0.0), FVector2D(Columns, CacheH),
			FVector2D(double(CacheColumn) / CacheW, 0.0), FVector2D(double(Columns) / CacheW, 1.0));
	}
	UKismetRenderingLibrary::EndDrawCanvasToRenderTarget(this, Context);
	CacheColumn += Columns;
	if (CacheColumn < CacheW) return;

	// Done: the dome fades to it, and the next panorama goes into the other target.
	CacheColumn = 0;
	CacheRefreshSeconds = Now - CacheRefreshStart;
	SkyMaterial->SetTextureParameterValue(TEXT("CacheOld"), CacheTargets[1 - CacheBack]);
	SkyMaterial->SetTextureParameterValue(TEXT("CacheNew"), CacheTargets[CacheBack]);
	CacheBack = 1 - CacheBack;
	CacheSwapTime = Now;
	if (!bCacheReady)
	{
		// The first panorama: the live clouds hand the far ones over (fading out over the last 500 m before the cache's
		// start) and spend their samples on the near ones.
		bCacheReady = true;
		SkyMaterial->SetTextureParameterValue(TEXT("CacheOld"), CacheTargets[1 - CacheBack]);
		CloudMaterial->SetVectorParameterValue(TEXT("CacheSplit"), FLinearColor(kSkyCacheSplitM - 500.f, kSkyCacheSplitM, 1.f, 0.f));
		if (UVolumetricCloudComponent* CloudComp = Clouds->FindComponentByClass<UVolumetricCloudComponent>())
		{
			CloudComp->TracingMaxDistanceMode = EVolumetricCloudTracingMaxDistanceMode::DistanceFromPointOfView;
			CloudComp->SetTracingMaxDistance(kSkyCacheSplitM / 1000.f);
		}
		// And the near rays keep all their samples: UE thins them in proportion on rays shorter than
		// r.VolumetricCloud.DistanceToSampleMaxCount (15 km below Ultra), so cut to 5 km a ray kept 15 km / 80 = 190 m
		// steps on High, the grain. At 5 km they step about 60 m (Ultra's 3 km stays).
		if (IConsoleVariable* FullAt = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.DistanceToSampleMaxCount")))
		{
			if (FullAt->GetFloat() > kSkyCacheSplitM / 1000.f)
			{
				CacheFullAtKm = FullAt->GetFloat();
				FullAt->Set(kSkyCacheSplitM / 1000.f, ECVF_SetByCode);
			}
		}
		UE_LOG(LogSailing, Display, TEXT("Sky cache: first panorama in %.2f s (%dx%d, %d steps); live clouds now to %.1f km"), CacheRefreshSeconds,
			CacheTargets[0]->SizeX, CacheTargets[0]->SizeY, SkyCacheSize().Steps, kSkyCacheSplitM / 1000.f);
	}
	// This frame already shows the swapped textures: start the fade now. With the CacheParams set at the top (blend 1, and
	// before the first panorama, no cache) the dome flashed the new panorama for a frame, and the first handover showed
	// the sky without its far clouds for a frame (the live clouds already cut at 5 km).
	SkyMaterial->SetVectorParameterValue(TEXT("CacheParams"), FLinearColor(1.f, 0.f, kSkyCacheElMin, kSkyCacheElMax));
}

void ASailingEnvironment::UpdateSkyline(const FVector& CameraPos)
{
	constexpr int32 kAzimuths = 2048;
	constexpr double kFromM = 45000.0, kToM = 160000.0;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !SkyMaterial) return;
	if (!Skyline)
	{
		static SailingArgs::FCachedFlag NoSkylineArg(TEXT("SailingNoSkyline"));
		Skyline = MakeShared<Sailing::FSkyline, ESPMode::ThreadSafe>();
		TArray<uint8> Bytes;
		if (NoSkylineArg.Get() || !FFileHelper::LoadFileToArray(Bytes, *(FLakeData::DefaultDirectory() / (GM->GetLake().FileName + TEXT(".skyline"))), FILEREAD_Silent)
			|| !Skyline->Load(Bytes.GetData(), Bytes.Num()))
		{
			SkyMaterial->SetVectorParameterValue(TEXT("SkylineP"), FLinearColor(0.f, 25.f, 0.f, 0.f));
			return;
		}
		SkylineTex = UTexture2D::CreateTransient(kAzimuths, 1, PF_FloatRGBA);
		SkylineTex->SRGB = false;
		SkylineTex->Filter = TF_Bilinear;
		SkylineTex->AddressX = TA_Wrap;
		SkylineTex->AddressY = TA_Clamp;
		SkylineTex->UpdateResource();
		SkyMaterial->SetTextureParameterValue(TEXT("Skyline"), SkylineTex);
		UE_LOG(LogSailing, Display, TEXT("Skyline: %s.skyline loaded (mountains %.0f to %.0f km)"), *GM->GetLake().FileName, kFromM / 1000.0, kToM / 1000.0);
	}
	if (!Skyline->IsValid()) return;
	// The haze fades the mountains as it fades everything (Koschmieder: contrast exp(-3.912 d / V)).
	SkyMaterial->SetVectorParameterValue(TEXT("SkylineP"), FLinearColor(1.f, float(GM->GetWeatherState().VisibilityKm), 0.f, 0.f));
	if (bSkylinePending && PendingSkyline.IsReady())
	{
		bSkylinePending = false;
		const TArray<float> Result = PendingSkyline.Get();
		TArray<FFloat16Color>* Pixels = new TArray<FFloat16Color>();
		Pixels->SetNum(kAzimuths);
		for (int32 K = 0; K < kAzimuths; ++K)
		{
			FFloat16Color& P = (*Pixels)[K];
			P.R = FFloat16(Result[K]);                       // elevation angle, rad
			P.G = FFloat16(Result[kAzimuths + K] / 1000.f);  // distance, km
			P.B = FFloat16(0.f);
			P.A = FFloat16(1.f);
		}
		FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, kAzimuths, 1);
		SkylineTex->UpdateTextureRegions(0, 1, Region, kAzimuths * sizeof(FFloat16Color), sizeof(FFloat16Color), reinterpret_cast<uint8*>(Pixels->GetData()),
			[Pixels](uint8*, const FUpdateTextureRegion2D* Rg) { delete Pixels; delete Rg; });
	}
	// Re-marched every 500 m (the parallax of a summit 45 km off is under a pixel per 500 m).
	if (bSkylinePending || FVector::Dist2D(CameraPos, SkylineAt) < 50000.0) return;
	SkylineAt = CameraPos;
	bSkylinePending = true;
	const double X = CameraPos.X / CmPerMeter, Y = CameraPos.Y / CmPerMeter, Eye = FMath::Max(CameraPos.Z / CmPerMeter, 1.0);
	PendingSkyline = Async(EAsyncExecution::ThreadPool, [Sky = Skyline, X, Y, Eye, Count = kAzimuths, From = kFromM, To = kToM]()
	{
		std::vector<float> Angles, Distances;
		Sky->Compute(X, Y, Eye, Count, From, To, Angles, Distances);
		TArray<float> Out;
		Out.Append(Angles.data(), int32(Angles.size()));
		Out.Append(Distances.data(), int32(Distances.size()));
		return Out;
	});
}

void ASailingEnvironment::UpdateHaze()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!Fog || !GM) return;
	const FWeatherState& W = GM->GetWeatherState();
	const int32 World = USailingSettings::Get()->World;
	// Koschmieder: visibility ~ 3.9 / extinction. Tuned so 25 km is a clear lake day and 1.5 km a downpour.
	// Wide World Rendering PR 4: the clamp reaches 80 km now (a mistral day), FHaze (Haze.h).
	const float Density = float(Sailing::FHaze::FogDensity(W.VisibilityKm));
	UExponentialHeightFogComponent* F = Fog->GetComponent();
	// Perf 4: each fog setter marks the fog's render state dirty when its value changes, and the engine then rebuilds
	// the fog's scene proxy. The inscattering colour follows HazeLight (the metered light, new every frame) and the
	// density the visibility, so the fog was rebuilt every frame. Like the sun's setters (#110) they now move in steps,
	// 3% of the value here, and snap exactly to a lerp's ends (dry, full rain) and to zero.
	auto Stepped = [](float Current, float Want, float EndA = -1.f, float EndB = -1.f)
	{
		return Current != Want && (Want == EndA || Want == EndB || Want == 0.f || FMath::Abs(Current - Want) > 0.03f * FMath::Abs(Want));
	};
	auto SteppedColor = [](const FLinearColor& Current, const FLinearColor& Want)
	{
		return Current != Want && !Current.Equals(Want, 0.03f * FMath::Max3(Want.R, Want.G, Want.B));
	};
	// The haze's thickness: 50 m on the Texas coast and lake (falloff 0.2); a world can give its own scale height
	// (Marseille's sea haze lies under the dry air of a mistral, 400 m). Rain mixes it up toward 200 m.
	const double ScaleHeight = GM->GetLake().FogScaleHeightM;
	const float Dry = ScaleHeight > 0.0 ? float(Sailing::FHaze::HeightFalloff(ScaleHeight)) : 0.2f;
	const float Falloff = FMath::Lerp(Dry, 0.05f, float(W.Rain));
	if (Stepped(F->FogHeightFalloff, Falloff, Dry, 0.05f)) F->SetFogHeightFalloff(Falloff);
	// Visual V5: humidity haze. A humid Texas summer day is milky; a dry norther is crisp; on the bay and offshore,
	// sea-salt haze. The haze thickens the visibility's fog near the surface and whitens it.
	const bool bLow = USailingSettings::Get()->Quality == ESailingQuality::Low;
	const float Haze = FMath::Clamp(float(W.Sky.Haze) + (World >= 1 ? 0.2f : 0.f), 0.f, 1.f);
	const float HazeMul = bLow ? 1.f : FMath::Lerp(0.6f, 1.6f, Haze);
	const float Deck = FMath::SmoothStep(0.5f, 0.95f, float(W.Sky[ECloudLayer::Stratus].Coverage));
	// docs/horizon-sky-colour/: the haze's aerosol is a boundary layer a kilometre or so deep, and it is what whitens the
	// low sky. All of it was in the fog, 50 m deep, which does not reach the sky, so the atmosphere kept the engine's
	// alpine Mie (0.004 per km, about 200 km visibility): a pure Rayleigh horizon, cyan (green over blue 0.96 at 3 deg
	// before the tone curve, against 0.84 for a Preetham sky). Part of the visibility's aerosol now goes to the atmosphere
	// (Mie, its 1.2 km scale height, single-scattering albedo 0.9) and the fog keeps the rest, so the surface visibility
	// is unchanged. Not under a stratus deck or in rain: the clouds do not shadow the atmosphere, and its sunlit aerosol
	// would glow under them (the grey fog lights those skies). And not with the sun under about 12 degrees: there the
	// aerosol's long path dimmed the sunlit faces of the clouds to a dull brown and spread an orange glow over the sky
	// toward the sun, undoing the dusk stills' match (G5); the low sun keeps the fog's haze until the clouds' lighting
	// through the aerosol is checked on its own.
	{
		const double AerosolKm = Sailing::FHaze::AerosolExtinctionPerKm(W.VisibilityKm / HazeMul);
		const float Share = AtmosphereHazeShare() * (1.f - Deck) * (1.f - float(W.Rain)) * FMath::SmoothStep(2.f, 12.f, SunElevationDeg);
		const float MieKm = Share * float(AerosolKm);
		if (Atmosphere)
		{
			USkyAtmosphereComponent* Atmo = Atmosphere->GetComponent();
			const float Scatter = FMath::Max(0.003996f, 0.9f * MieKm), Absorb = FMath::Max(0.000444f, 0.1f * MieKm);
			if (Stepped(Atmo->MieScatteringScale, Scatter, 0.003996f)) Atmo->SetMieScatteringScale(Scatter);
			if (Stepped(Atmo->MieAbsorptionScale, Absorb, 0.000444f)) Atmo->SetMieAbsorptionScale(Absorb);
		}
		FogShare = 1.f - MieKm / float(3.912 * HazeMul / FMath::Clamp(W.VisibilityKm, 0.5, 80.0));
	}
	if (bLow)
	{
		if (Stepped(F->FogDensity, Density * FogShare)) F->SetFogDensity(Density * FogShare);
		return;
	}
	const float HazeDensity = Density * HazeMul * FogShare;
	if (Stepped(F->FogDensity, HazeDensity)) F->SetFogDensity(HazeDensity);
	const FLinearColor Milky(0.62f, 0.66f, 0.72f), Crisp(0.42f, 0.52f, 0.68f), Sea(0.55f, 0.63f, 0.72f);
	// Realism audit 6: under a closed stratus deck the air is lit by the grey deck, not the blue sky: the haze goes neutral
	// grey with the deck (Crisp's blue under an overcast read as clear sky between the deck and the horizon).
	// docs/gulf-haze-band/: and no brighter than the deck that lights it. At (0.58, 0.60, 0.63) the haze at the horizon
	// read a third brighter than the overcast above it, a pale band along the sea's horizon (most of all on the Gulf, with
	// nothing on the horizon to hide it); a real overcast darkens toward the horizon if anything.
	const FLinearColor DeckGrey(0.36f, 0.37f, 0.39f);
	const FLinearColor Tint = FMath::Lerp(FMath::Lerp(Crisp, World >= 1 ? Sea : Milky, Haze), DeckGrey, Deck);
	// The haze glows with the daylight it scatters: under a storm deck and at night it goes dark with the sky.
	static SailingArgs::FCachedFlag ClassicHazeArg(TEXT("SailingClassicHaze"));   // Graphics G5 compare
	const bool bClassicHaze = ClassicHazeArg.Get();
	if (bClassicHaze)
	{
		const FLinearColor Inscatter = Tint * FMath::Lerp(1.f, 0.25f, float(W.CloudDarkness)) * FMath::Lerp(1.f, 0.004f, NightAmount);
		if (SteppedColor(F->FogInscatteringLuminance, Inscatter)) F->SetFogInscatteringColor(Inscatter);
	}
	else
	{
		// Graphics G5: lit by the metered light (HazeLight, which already carries the storm's gloom and the night), and
		// toward sunset the haze takes the low sun's colour, as the sky at the horizon does.
		const float Warm = 1.f - FMath::SmoothStep(0.f, 12.f, SunElevationDeg);
		const FLinearColor Sunset(1.25f, 0.82f, 0.55f);
		const FLinearColor Lit = FMath::Lerp(Tint, Tint * Sunset, Warm * (1.f - NightAmount));
		const FLinearColor Inscatter = Lit * FMath::Lerp(1.f, 0.6f, float(W.CloudDarkness)) * HazeLight;
		if (SteppedColor(F->FogInscatteringLuminance, Inscatter)) F->SetFogInscatteringColor(Inscatter);
		// Analytic fog reaches full opacity at the horizon, which hid the low sun's disc completely; real haze lets a few
		// percent of the disc through, and the disc is thousands of times the sky's brightness.
		const float MaxOpacity = FMath::Lerp(0.9f, 1.f, float(W.Rain));
		if (Stepped(F->FogMaxOpacity, MaxOpacity, 0.9f, 1.f)) F->SetFogMaxOpacity(MaxOpacity);
	}
	// Graphics G8 cinematic look: the haze glows toward a low sun (the analytic fog's directional inscattering, a
	// constant cost), the veil over the far shore in every sunset photo. Off in the natural look and under a deck.
	// The natural look keeps the fog's own values (kept from the first call and restored).
	if (!bFogDirectionalSaved)
	{
		bFogDirectionalSaved = true;
		SavedFogDirectional = FVector4f(F->DirectionalInscatteringExponent, F->DirectionalInscatteringStartDistance, 0.f, 0.f);
		SavedFogDirectionalColor = F->DirectionalInscatteringLuminance;
	}
	if (bCinematic)
	{
		const float Glow = (1.f - FMath::SmoothStep(4.f, 25.f, SunElevationDeg)) * (1.f - FMath::SmoothStep(0.2f, 0.6f, float(W.CloudDarkness))) * (1.f - NightAmount);
		F->SetDirectionalInscatteringExponent(6.f);
		F->SetDirectionalInscatteringStartDistance(800.f * CmPerMeter);
		const FLinearColor GlowColor = FLinearColor(1.f, 0.62f, 0.32f) * (0.9f * Glow * HazeLight);
		if (SteppedColor(F->DirectionalInscatteringLuminance, GlowColor)) F->SetDirectionalInscatteringColor(GlowColor);
	}
	else if (F->DirectionalInscatteringExponent != SavedFogDirectional.X || F->DirectionalInscatteringLuminance != SavedFogDirectionalColor)
	{
		F->SetDirectionalInscatteringExponent(SavedFogDirectional.X);
		F->SetDirectionalInscatteringStartDistance(SavedFogDirectional.Y);
		F->SetDirectionalInscatteringColor(SavedFogDirectionalColor);
	}
	// Volumetric fog: the sun scatters in it, so shafts show through gaps in the cloud (forward-scattering haze).
	if (!F->bEnableVolumetricFog) F->SetVolumetricFog(true);
	F->SetVolumetricFogScatteringDistribution(0.75f);
	const float Extinction = FMath::Lerp(0.12f, 0.3f, Haze); // the volumetric fog reads much thicker than the analytic fog at the same density
	if (Stepped(F->VolumetricFogExtinctionScale, Extinction, 0.12f, 0.3f)) F->SetVolumetricFogExtinctionScale(Extinction);
	F->SetVolumetricFogAlbedo(FColor(240, 244, 250));
	const float VolumetricDistance = float(FMath::Lerp(3000.f, 1200.f, float(W.Rain)) * CmPerMeter);
	if (Stepped(F->VolumetricFogDistance, VolumetricDistance, float(3000.f * CmPerMeter), float(1200.f * CmPerMeter))) F->SetVolumetricFogDistance(VolumetricDistance);
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
	// City light domes (Visual V6; Wide World Rendering PR 3: from the world's <World>.farlights.json, up to four, the
	// brightest first: from Frioul, Marseille to the east and La Ciotat to the south-east at once). Each falls off with
	// distance from its light weight; the sky draws a dome toward each.
	struct FDome { float Glow, Az; };
	TArray<FDome, TInlineAllocator<8>> Domes;
	const TArray<FFarLightsData::FCity>& Cities = GM->GetLake().FarLights.Cities;
	if (Cities.Num() > 0)
	{
		FVector CamM = FVector::ZeroVector;
		if (APlayerCameraManager* PCM = UGameplayStatics::GetPlayerCameraManager(this, 0)) CamM = SailingFrame::ToMapCm(GetWorld(), PCM->GetCameraLocation()) / 100.0;   // the map frame (the city domes are)
		for (const FFarLightsData::FCity& C : Cities)
		{
			const double North = (C.XY.X - CamM.X) / 1000.0, East = (C.XY.Y - CamM.Y) / 1000.0;
			const double Km = FMath::Max(FMath::Sqrt(North * North + East * East), 5.0);
			// Capped: from inside a city's own lights (the Vieux-Port in Marseille) its dome is no brighter than Houston's
			// from Kemah.
			Domes.Add({ float(FMath::Min(C.Light * FMath::Pow(30.0 / Km, 1.5), 1.2)), float(FMath::Atan2(East, North)) });
		}
	}
	else
	{
		// A bake without far lights: the old Texas list (Dallas, Houston, Texas City, Fort Worth).
		struct FCityLL { double Lat, Lon, Light; };
		static const FCityLL Texas[] = { { 32.78, -96.80, 1.0 }, { 29.76, -95.37, 1.3 }, { 29.39, -94.92, 0.35 }, { 32.75, -97.33, 0.6 } };
		const double CosLat = FMath::Cos(GM->GetLake().Latitude * kDegToRad);
		for (const FCityLL& C : Texas)
		{
			const double North = (C.Lat - GM->GetLake().Latitude) * 111.2, East = (C.Lon - GM->GetLake().Longitude) * 111.2 * CosLat;
			const double Km = FMath::Max(FMath::Sqrt(North * North + East * East), 5.0);
			Domes.Add({ float(C.Light * FMath::Pow(30.0 / Km, 1.5)), float(FMath::Atan2(East, North)) });
		}
	}
	Domes.Sort([](const FDome& A, const FDome& B) { return A.Glow > B.Glow; });
	float GlowParams[8] = { 0.f, 0.f, 0.f, 0.f, 0.f, 0.f, 0.f, 0.f };
	float GlowTotal = 0.f;
	const float GlowUnit = float(SunIntensity) * 0.006f * NightAmount * 1.1f;
	// The domes share the brightest one's light (the sky's total stays what the single dome gave: more domes spread it
	// round the horizon, they do not brighten the night).
	float Sum = 0.f;
	for (int32 I = 0; I < FMath::Min(Domes.Num(), 4); ++I) Sum += Domes[I].Glow;
	const float Share = (Domes.Num() > 0 && Sum > 0.f) ? Domes[0].Glow / Sum : 0.f;
	for (int32 I = 0; I < FMath::Min(Domes.Num(), 4); ++I)
	{
		GlowParams[2 * I] = Domes[I].Az;
		GlowParams[2 * I + 1] = Domes[I].Glow * Share * GlowUnit;
		GlowTotal += GlowParams[2 * I + 1];
	}
	SkyMaterial->SetVectorParameterValue(TEXT("NightParams"), FLinearColor(StarScale, GlowTotal, GlowParams[0], GetWorld()->GetTimeSeconds()));
	SkyMaterial->SetVectorParameterValue(TEXT("GlowDomesA"), FLinearColor(GlowParams[0], GlowParams[1], GlowParams[2], GlowParams[3]));
	SkyMaterial->SetVectorParameterValue(TEXT("GlowDomesB"), FLinearColor(GlowParams[4], GlowParams[5], GlowParams[6], GlowParams[7]));
	// docs/night-clouds/: the same domes light the clouds' bases from below: GlowLum.rgb is an opaque base's glow (CLOUD_CODE,
	// the live clouds; w 1 at night) and CloudGlow the same per unit of the domes' total for the far clouds the sky draws
	// from the cache. kCloudGlow: a base's glow per unit of the domes' total strength; -SailingCloudGlow=<scale> measures.
	constexpr float kCloudGlow = 0.35f;
	static float GlowScale = -1.f;
	if (GlowScale < 0.f) { GlowScale = 1.f; FParse::Value(SailingArgs::Dev(), TEXT("SailingCloudGlow="), GlowScale); }
	SkyMaterial->SetScalarParameterValue(TEXT("CloudGlow"), kCloudGlow * GlowScale);
	if (CloudMaterial)
	{
		const float G = GlowTotal * kCloudGlow * GlowScale;
		CloudMaterial->SetVectorParameterValue(TEXT("GlowLum"), FLinearColor(G, 0.70f * G, 0.42f * G, GlowTotal > 0.f ? 1.f : 0.f));
		CloudMaterial->SetVectorParameterValue(TEXT("GlowDomesA"), FLinearColor(GlowParams[0], GlowParams[1], GlowParams[2], GlowParams[3]));
		CloudMaterial->SetVectorParameterValue(TEXT("GlowDomesB"), FLinearColor(GlowParams[4], GlowParams[5], GlowParams[6], GlowParams[7]));
	}
	SkyMaterial->SetVectorParameterValue(TEXT("MoonDir"), FLinearColor(float(MoonTrue.X), float(MoonTrue.Y), float(MoonTrue.Z), MoonTrue.Z > -0.02f ? MoonLuminance : 0.f));
	// Earthshine: the dark limb at about a few thousandths of the lit side (strongest near new moon).
	SkyMaterial->SetVectorParameterValue(TEXT("SunTrue"), FLinearColor(float(SunTrue.X), float(SunTrue.Y), float(SunTrue.Z), 0.004f * (1.f - MoonLit)));
}
