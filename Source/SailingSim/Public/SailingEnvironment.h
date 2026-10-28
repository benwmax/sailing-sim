#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Async/Future.h"
#include "CloudSky.h"
#include "SailingEnvironment.generated.h"

class ADirectionalLight;
class ASkyLight;
class ASkyAtmosphere;
class AExponentialHeightFog;
class AVolumetricCloud;
class UStaticMeshComponent;
class UProceduralMeshComponent;
class UMaterialInstanceDynamic;
class UDirectionalLightComponent;
class UMaterialInterface;
class UTexture2D;
struct FPostProcessSettings;
class UPointLightComponent;

/**
 * Turns the weather state into the sky: sun position for the time of day at Lake Ray Roberts (33.4 N),
 * volumetric clouds (coverage, towering storm cells, darkness), haze from visibility, rain around the camera,
 * lightning bolts and flashes. Thunder is scheduled at the speed of sound for the audio.
 */
namespace Sailing { class FSkyline; }

UCLASS()
class SAILINGSIM_API ASailingEnvironment : public AActor
{
	GENERATED_BODY()

public:
	/** Graphics G4: the first cloud weather map has been painted (the loading screen waits for it). */
	bool HasWeatherMap() const { return bHasWeatherMap; }
	/** The far clouds are drawn as they will stay: the sky cache's first panorama is in (or there is no cache, or a storm or
	 *  deck keeps the live clouds on the whole sky). The loading screen waits for it (docs/cloud-popin/). */
	bool IsSkyReady() const { return !bSkyCache || bCacheReady || bCacheSuspended; }
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
	/** The direct sun reaching the camera through the clouds (0..1) and the physical camera's EV100, for the capture metadata. */
	float GetCloudShade() const { return LastCloudShade; }
	double GetCameraEV() const { return LastCameraEV; }

	/** The scene's post-process settings as this frame left them (photo mode adds its exposure to the metered bias and
	 *  starts its vignette and grain from the look's). */
	const struct FPostProcessSettings* GetSceneLook() const;

	/** 0..1 brightness of the current lightning flash, for the HUD and audio. */
	float GetFlash() const { return Flash; }

private:
	void FindSceneActors();
	void UpdateSun(double Hour);
	void DumpExposureSettings(float EV, float Band, float IntoSun);
	void ApplyCameraLook(bool bPhysicalCamera, double CloudDarkness);
	/** Graphics G8: the cinematic look on top of the V1 look (grade LUT, tone curve, bloom, flare, vignette, grain). */
	void ApplyCinematicLook(FPostProcessSettings& PP, double CloudDarkness);
	void UpdateClouds(float DeltaSeconds);
	void UpdateRain(const FVector& CameraPos);
	/** W5b: the storm's rain curtains and rain foot from afar, where the rain field (FStormRain or the radar) says it rains. */
	void UpdateRainCurtains(const FVector& CameraPos, float DeltaSeconds);
	void UpdateRainWall(const FVector& CameraPos);
	void UpdateLightning(float DeltaSeconds, const FVector& CameraPos);
	void BuildBolt(const FVector& Ground, float CloudBaseCm);
	/** Visual V5 (Medium and High): paints the weather map on a worker every couple of seconds and drives M_CloudLayers. */
	void UpdateCloudLayers(const FVector& CameraPos);
	/** C2 (the sky cache): the far clouds marched into a panorama a strip per frame (M_CloudCache), shown by the sky dome;
	 *  the live clouds keep only the near ones (CacheSplit, TracingMaxDistance). -SailingNoSkyCache compares. */
	void UpdateSkyCache(const FVector& CameraPos, float DeltaSeconds);
	/** Visual V5: the sky dome's sun disc, night sky, moon and cirrus. Directions are map-frame unit vectors. */
	void UpdateSkyDome(const FVector& SunTrue, const FVector& MoonTrue, float MoonLuminance, float MoonLit, float Night, double UnixUtc);
	/** Visual V5: height fog and volumetric fog from the visibility, the humidity haze and the water body. */
	void UpdateHaze();
	/** Wide World Rendering PR 4, band D: the mountains past the far ring (<World>.skyline) marched from the camera on a
	 *  worker every 500 m into a 2048 x 1 elevation-angle texture the sky dome draws under. -SailingNoSkyline compares. */
	void UpdateSkyline(const FVector& CameraPos);
	UPROPERTY(Transient) TObjectPtr<class UTexture2D> SkylineTex;
	TSharedPtr<class Sailing::FSkyline, ESPMode::ThreadSafe> Skyline;
	TFuture<TArray<float>> PendingSkyline;
	FVector SkylineAt = FVector(1e12);
	bool bSkylinePending = false;

	/** docs/sky-lower-hemisphere: the sky light's lower hemisphere is what the water sends up (its Fresnel reflection of the
	 *  sky plus the body's upwelling, times the sky's mean radiance read back from M_SkyEnvProbe every two seconds), not
	 *  black. Lumen's rays below the horizon miss the water (procedural rings: no distance field or cards) and returned it.
	 *  -SailingNoWaterBounce compares (black, as before). */
	void UpdateLowerHemisphere(double Now);
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> SkyProbeMaterial;
	UPROPERTY(Transient) TObjectPtr<class UTextureRenderTarget2D> SkyProbeTarget;
	TSharedPtr<struct FSkyProbeReadback, ESPMode::ThreadSafe> SkyProbe;
	double NextSkyProbe = 0.0;
	FLinearColor AppliedLowerHemisphere = FLinearColor(-1.f, -1.f, -1.f);

	UPROPERTY(Transient) TObjectPtr<ADirectionalLight> Sun;
	UPROPERTY(Transient) TObjectPtr<ASkyLight> SkyLightActor;
	UPROPERTY(Transient) TObjectPtr<ASkyAtmosphere> Atmosphere;
	float FogShare = 1.f;   // the visibility's aerosol left to the fog (docs/horizon-sky-colour/)
	UPROPERTY(Transient) TObjectPtr<AExponentialHeightFog> Fog;
	UPROPERTY(Transient) TObjectPtr<AVolumetricCloud> Clouds;
	UPROPERTY(Transient) TObjectPtr<class APostProcessVolume> PostProcess;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> CloudMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> CloudLayersMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> CloudCacheMaterial;   // C2: M_CloudCache (a hard reference: cooked)
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> SkyDome;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> SkyMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> CacheMaterial;
	UPROPERTY(Transient) TObjectPtr<class UTextureRenderTarget2D> CacheTargets[2];
	bool bSkyCache = false;
	bool bCacheReady = false;      // a whole panorama has been drawn: the live clouds may hand the far ones over
	bool bCacheSuspended = false;  // a storm or deck: the live clouds draw the whole sky
	int32 CacheBack = 0;           // the target being drawn
	int32 CacheColumn = 0;         // the next column of the panorama to draw
	double CacheSwapTime = -1e9;   // when the last panorama finished (the dome cross-fades for half a second)
	float CacheColumnCarry = 0.f;
	float CacheTraceKm = 50.f;     // the live clouds' tracing distance before the cache took the far ones
	uint8 CacheTraceMode = 0;      // and how it was measured (EVolumetricCloudTracingMaxDistanceMode)
	float NightDeckFullAtKm = 0.f; // r.VolumetricCloud.DistanceToSampleMaxCount before a night deck shortened it (0: untouched)
	float CacheFullAtKm = 0.f;     // r.VolumetricCloud.DistanceToSampleMaxCount before the cache shortened it (0: untouched)
	double CacheRefreshSeconds = 0.0;  // the last full refresh's time, for the log
	double CacheRefreshStart = 0.0;
	int32 CacheRefreshes = 0;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> LensWaterMaterial;
	UPROPERTY(Transient) TObjectPtr<class UMaterialParameterCollection> WorldCollection; // MPC_World (Visual V6: the wind)
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> LensMaterial;
	FVector LastCameraPos = FVector::ZeroVector;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> WeatherMapTexture;
	/** Realism audit 1: each texel's cumulus cell size (FWeatherMap::CumulusTop), R16F like the map. */
	UPROPERTY(Transient) TObjectPtr<UTexture2D> CumulusTopTexture;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UPointLightComponent> BoltLight;
	bool bLayeredClouds = false;
	float NightAmount = 0.f; // 0 day .. 1 night (from the sun's elevation, UpdateSun)
	/** Graphics G5: the haze's light relative to a clear midday (the metered exposure's light), and the sun's elevation. */
	float HazeLight = 1.f;
	float LastCloudShade = 1.f;
	double LastCameraEV = 0.0;
	bool bCinematic = false; // Graphics G8: the cinematic look is on (UsesCinematicLook, re-read each sun update)
	bool bTriedLookLoad = false; // the cinematic LUT and bloom kernel were looked up (CinematicLUT, BloomKernel)
	bool bFogDirectionalSaved = false;
	FVector4f SavedFogDirectional = FVector4f(0.f, 0.f, 0.f, 0.f); // the fog's own directional inscattering (exponent, start)
	FLinearColor SavedFogDirectionalColor = FLinearColor::Black;
	UPROPERTY(Transient) TObjectPtr<class UTexture> CinematicLUT;   // /Game/Look/T_CinematicLUT (Tools/look/make_grade_lut.py)
	UPROPERTY(Transient) TObjectPtr<class UTexture2D> BloomKernel;  // /Game/Look/T_BloomKernel (Ultra convolution bloom)
	float SunElevationDeg = 45.f;
	FVector SunDirection = FVector(0.0, 0.0, 1.0); // toward the sun (map frame), for the storm's own shade (rain curtains)
public:
	float GetNightAmount() const { return NightAmount; }
private:
	struct FWeatherMapFrame { Sailing::FWeatherMap Map; TArray<FFloat16> Half; TArray<FFloat16> TopHalf; };
	Sailing::FWeatherMap LastWeatherMap;
	float SunVisibility = 1.f; // smoothed transmittance toward the sun through the clouds (layered clouds)
	bool bHasWeatherMap = false;
	TFuture<FWeatherMapFrame> PendingWeatherMap;
	bool bWeatherMapPending = false;
	TWeakObjectPtr<class AWaterSurface> WaterActor;
	double WeatherMapAge = 1e9;
	FVector4f FlashParams = FVector4f(0.f, 0.f, 0.f, 0.f);
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> RainNear;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<UStaticMeshComponent> RainFar;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> RainMaterial;
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<class UInstancedStaticMeshComponent> RainCurtains;
	/** docs/storm-gloom/: the grey air under the storm's deck seen from ahead, one card on the front (UpdateRainWall). */
	UPROPERTY(VisibleAnywhere, Category = "Weather") TObjectPtr<class UInstancedStaticMeshComponent> RainWall;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> RainCurtainMaterial;
	struct FRainCurtain { double X = 0.0, Y = 0.0, Rate = 0.0, Seed = 0.0, Shade = 1.0; };
	TArray<FRainCurtain> Curtains;
	float CurtainClock = 0.f;
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
