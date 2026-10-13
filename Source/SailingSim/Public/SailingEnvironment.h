#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Async/Future.h"
#include "CloudSky.h"
#include "SailingEnvironment.generated.h"

class ADirectionalLight;
class ASkyLight;
class AExponentialHeightFog;
class AVolumetricCloud;
class UStaticMeshComponent;
class UProceduralMeshComponent;
class UMaterialInstanceDynamic;
class UDirectionalLightComponent;
class UMaterialInterface;
class UTexture2D;
class UPointLightComponent;

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
	/**
	 * Sun elevation and azimuth (degrees) for a local clock time: the clock hour is turned into apparent solar time
	 * with the longitude, the time zone and the equation of time (solar noon in Galveston on CDT is about 13:07).
	 */
	static void SunPosition(double ClockHour, double DayOfYear, double LatitudeDeg, double LongitudeDeg, double UtcOffsetHours, double& OutElevation, double& OutAzimuth);

	/** The moon's age in days since new moon (0 to 29.53) at a UTC time, from the mean synodic month and a known new moon
	 *  (2000-01-06 18:14 UTC): within about half a day of the almanac. */
	static double MoonAgeDays(double UnixUtc);
	/** Fraction of the moon's disc that is lit (0 new, 1 full). */
	static double MoonIllumination(double AgeDays);
	/** Where the moon is: it trails the sun across the sky by its elongation (rising about 50 minutes later each day), at
	 *  roughly the sun's declination for where the sun will be that far round the ecliptic. Degrees, like SunPosition. */
	static void MoonPosition(double ClockHour, double DayOfYear, double AgeDays, double LatitudeDeg, double LongitudeDeg, double UtcOffsetHours, double& OutElevation, double& OutAzimuth);

	/** A thunderclap reaching the listener: loudness 0..1 (distance) and how long ago it started. */
	struct FThunder { float Loudness; float Age; float Duration; };
	const TArray<FThunder>& GetActiveThunder() const { return Thunder; }

	/** 0..1 brightness of the current lightning flash, for the HUD and audio. */
	float GetFlash() const { return Flash; }

private:
	void FindSceneActors();
	void UpdateSun(double Hour);
	void ApplyCameraLook(bool bPhysicalCamera, double CloudDarkness);
	void UpdateClouds(float DeltaSeconds);
	void UpdateRain(const FVector& CameraPos);
	void UpdateLightning(float DeltaSeconds, const FVector& CameraPos);
	void BuildBolt(const FVector& Ground, float CloudBaseCm);
	/** Visual V5 (Medium and High): paints the weather map on a worker every couple of seconds and drives M_CloudLayers. */
	void UpdateCloudLayers(const FVector& CameraPos);
	/** Visual V5: the sky dome's sun disc, night sky, moon and cirrus. Directions are map-frame unit vectors. */
	void UpdateSkyDome(const FVector& SunTrue, const FVector& MoonTrue, float MoonLuminance, float MoonLit, float Night, double UnixUtc);
	/** Visual V5: height fog and volumetric fog from the visibility, the humidity haze and the water body. */
	void UpdateHaze();

	UPROPERTY(Transient) TObjectPtr<ADirectionalLight> Sun;
	UPROPERTY(Transient) TObjectPtr<ASkyLight> SkyLightActor;
	UPROPERTY(Transient) TObjectPtr<AExponentialHeightFog> Fog;
	UPROPERTY(Transient) TObjectPtr<AVolumetricCloud> Clouds;
	UPROPERTY(Transient) TObjectPtr<class APostProcessVolume> PostProcess;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> CloudMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> CloudLayersMaterial;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> SkyDome;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> SkyMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> LensWaterMaterial;
	UPROPERTY(Transient) TObjectPtr<class UMaterialParameterCollection> WorldCollection; // MPC_World (Visual V6: the wind)
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> LensMaterial;
	FVector LastCameraPos = FVector::ZeroVector;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> WeatherMapTexture;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UPointLightComponent> BoltLight;
	bool bLayeredClouds = false;
	float NightAmount = 0.f; // 0 day .. 1 night (from the sun's elevation, UpdateSun)
public:
	float GetNightAmount() const { return NightAmount; }
private:
	struct FWeatherMapFrame { Sailing::FWeatherMap Map; };
	Sailing::FWeatherMap LastWeatherMap;
	float SunVisibility = 1.f; // smoothed transmittance toward the sun through the clouds (layered clouds)
	bool bHasWeatherMap = false;
	TFuture<FWeatherMapFrame> PendingWeatherMap;
	bool bWeatherMapPending = false;
	double WeatherMapAge = 1e9;
	FVector4f FlashParams = FVector4f(0.f, 0.f, 0.f, 0.f);
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> RainNear;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> RainFar;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> RainMaterial;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UProceduralMeshComponent> Bolt;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> BoltMaterial;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UDirectionalLightComponent> FlashLight;
	/** Night: a dim, cool light from high in the sky (moonlight and the glow of the coast's towns). */
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UDirectionalLightComponent> MoonLight;

	int32 NextStrike = 0;
	float Flash = 0.f;
	float BoltTime = -1.f;
	TArray<FThunder> Thunder;
	struct FPendingThunder { float Delay; float Loudness; };
	TArray<FPendingThunder> PendingThunder;
	float SunIntensity = 10.f;
	float SkyIntensity = 1.f;
	float FogBaseDensity = 0.02f;
	int32 AppliedCloudShadowSamples = -1;
};
