#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SailingEnvironment.generated.h"

class ADirectionalLight;
class ASkyLight;
class AExponentialHeightFog;
class AVolumetricCloud;
class UStaticMeshComponent;
class UProceduralMeshComponent;
class UMaterialInstanceDynamic;
class UDirectionalLightComponent;

/**
 * Turns the weather state into the sky: sun position for the time of day at Lake Ray Roberts (33.4 N),
 * volumetric clouds (coverage, towering storm cells, darkness), haze from visibility, rain around the camera,
 * lightning bolts and flashes. Thunder is scheduled at the speed of sound for the audio.
 */
UCLASS()
class SAILINGSIM_API ASailingEnvironment : public AActor
{
	GENERATED_BODY()

public:
	ASailingEnvironment();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Sun elevation and azimuth (degrees, azimuth clockwise from +X / north) for a local solar hour. */
	static void SunPosition(double Hour, double DayOfYear, double LatitudeDeg, double& OutElevation, double& OutAzimuth);

	/** A thunderclap reaching the listener: loudness 0..1 (distance) and how long ago it started. */
	struct FThunder { float Loudness; float Age; float Duration; };
	const TArray<FThunder>& GetActiveThunder() const { return Thunder; }

	/** 0..1 brightness of the current lightning flash, for the HUD and audio. */
	float GetFlash() const { return Flash; }

private:
	void FindSceneActors();
	void UpdateSun(double Hour);
	void UpdateClouds(float DeltaSeconds);
	void UpdateRain(const FVector& CameraPos);
	void UpdateLightning(float DeltaSeconds, const FVector& CameraPos);
	void BuildBolt(const FVector& Ground, float CloudBaseCm);

	UPROPERTY(Transient) TObjectPtr<ADirectionalLight> Sun;
	UPROPERTY(Transient) TObjectPtr<ASkyLight> SkyLightActor;
	UPROPERTY(Transient) TObjectPtr<AExponentialHeightFog> Fog;
	UPROPERTY(Transient) TObjectPtr<AVolumetricCloud> Clouds;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> CloudMaterial;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> RainNear;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> RainFar;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> RainMaterial;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UProceduralMeshComponent> Bolt;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> BoltMaterial;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UDirectionalLightComponent> FlashLight;

	int32 NextStrike = 0;
	float Flash = 0.f;
	float BoltTime = -1.f;
	TArray<FThunder> Thunder;
	struct FPendingThunder { float Delay; float Loudness; };
	TArray<FPendingThunder> PendingThunder;
	float SunIntensity = 10.f;
	float SkyIntensity = 1.f;
	float FogBaseDensity = 0.02f;
};
