#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Async/Future.h"
#include "WakeGrid.h"
#include "WaveDetail.h"
#include "WaterSurface.generated.h"

class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UTexture2D;
namespace Sailing { class FWaveField; class FWindField; }

/**
 * The lake surface. Nested rings of mesh follow the camera (fine near, coarse far, like a geometry clipmap);
 * M_Water displaces them on the GPU with exactly the wave components the physics floats the boat on.
 * The actor also feeds the material a cat's-paw map from the wind field and a foam map for the boat's wake.
 * Its Z is the still-water level.
 *
 * Visual V4 (Medium and High): M_WaterV4 draws the physics' long waves exactly, the short waves from an FFT of the same
 * spectrum (FWaveDetail, evaluated off the game thread at 30 Hz), whitecaps where the crests fold, the waves every hull
 * in range makes (FWakeGrid) and Single Layer Water coloured per water body. Low keeps M_Water.
 */
UCLASS()
class SAILINGSIM_API AWaterSurface : public AActor
{
	GENERATED_BODY()

public:
	AWaterSurface();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;

	/** Still-water height in centimeters (world Z). */
	float GetSurfaceZ() const { return GetActorLocation().Z; }

	/** Number of mesh rings (quality tier): 4 on Low, 5 on Medium and High (past about 500 m the far plane carries the horizon). */
	void SetRingCount(int32 Count);

	/** Quality tier: 0 Low (M_Water), 1 Medium (M_WaterV4: FFT chop and the wake grid), 2 High (adds the ripples and
	 *  a larger wake grid). */
	void SetQualityTier(int32 InTier);
	bool IsDetailedWater() const { return bV4; }
	/** Visual V5: spray that just hit the camera's glass (1 = a fresh burst, fading over a few seconds). */
	float GetLensSpray() const { return LensSpray; }

	/** Horizontal choppiness of the drawn waves (Gerstner lambda) and the frequency below which the physics' own trains
	 *  are drawn (above it the FFT takes over): the upper edge of FWaveField's eighth band, so the long waves are exactly
	 *  its first LongComponents trains (wavelengths over 3.6 m). The material uses the same numbers (make_materials.py). */
	static constexpr float Choppiness = 1.5f;
	static constexpr double SplitHz = 0.65727;
	static constexpr int32 LongComponents = 24;
	/** W0: whitecap coverage against the open sea's (Monahan) by water body. Fresh water foams less (smaller, shorter-lived
	 *  bubbles: about 0.4 of the sea's coverage on the lake), the brackish bay about 0.7, the Gulf the full law. */
	static float WhitecapScaleFor(int32 World);
	/** W0: the folding threshold M_WaterV4 uses at a pixel: FoamThreshold shifted so coverage scales by the body's scale
	 *  times Monahan's (U_local / U_mean)^3.41, caps cluster in puffs and thin in lulls. CapSlope is the threshold shift
	 *  per e-fold of coverage, measured on the drawn waves (SailingSim.Visual.Whitecaps). Mirrored in make_materials.py. */
	static constexpr float FoamThreshold = 0.6f;
	static constexpr float CapSlope = 0.045f;
	/** W2: the threshold shift per e-fold grows with the wind (measured on the drawn waves: 0.034 at 10 kn, 0.069 at
	 *  25 kn), so a fixed CapSlope under-applied the lake's and the lulls' scale in a strong breeze (the lake capped 3.3
	 *  to 3.6 times its share at 20 and 25 kn). CapSlope is this at about 14 kn. Mirrored in make_materials.py. */
	static float CapSlopeAt(float MeanKnots);
	static float WhitecapThreshold(float LocalOverMean, float WaterScale, float MeanKnots = 14.f);
	/** Game-thread time spent on the water each frame (the FFT blend and upload, the wake grid), summed: bench.json. */
	static double WaterCpuSeconds;
	/** W2: game-thread time spent on the two-level wind map (bench.json windmap_cpu_ms). */
	static double WindMapCpuSeconds;

	/** Records the boat's stern/bow positions for wake foam (world meters), called by the boat each frame. */
	void SetBoatForWake(const FVector2D& PositionM, float HeadingRad, float SpeedMs, float HeelRad);

	UPROPERTY(EditAnywhere, Category = "Water")
	float FarPlaneSizeMeters = 40000.f;

private:
	void BuildRings();
	void UpdateMaterial();
	void UpdateGustMap();
	void UpdateWakeMap(float DeltaSeconds);
	/** Open sea: uploads the FFT ocean's grids (and its mask when rebuilt) for the material. */
	void UpdateOcean();
	/** Medium and High: (re)configures the FFT short waves from the sea state, blends its 30 Hz frames and uploads them. */
	void UpdateDetail();
	/** The water depth around the boat (shoaling, waves dying on the beach, lapping at the shore and the docks),
	 *  rebuilt on a worker as the boat moves. */
	void UpdateShoreMap();
	/** High: spray thrown up where a bow slams into a wave and blown off breaking crests (CPU droplets, instanced). */
	void UpdateSpray(float DeltaSeconds);
	/** Steps the wake grid with every hull in range and uploads it. */
	void UpdateWakeGrid(float DeltaSeconds);
	/** Medium and High: the player's hull plan for M_WaterV4, which drops the water inside it (no sea in the cockpit). */
	void UpdateHullClip();
	/** Makes the water material instance for the tier and binds every map to it. */
	void CreateWaterMaterial();
	/** Waits for the background FFT and wake-grid steps (before the grid is rebuilt, and at the end of play). */
	void WaitForWorkers();
	const Sailing::FWaveField* GetWaves() const;
	const Sailing::FWindField* GetWind() const;
	double GetSimTime() const;

	UPROPERTY(Transient) TArray<TObjectPtr<UProceduralMeshComponent>> Rings;
	UPROPERTY(VisibleAnywhere, Category = "Water") TObjectPtr<UStaticMeshComponent> FarPlane;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> WaterMaterial;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> GustMap;
	/** W2: the far wind map (16 km). GustMap is the near one (3.2 km). */
	UPROPERTY(Transient) TObjectPtr<UTexture2D> WindFarMap;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> WakeMap;
	UPROPERTY(Transient) TArray<TObjectPtr<UTexture2D>> OceanMaps;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> OceanMaskMap;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ClassicMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> DetailedMaterial;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> DetailAMap;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> DetailBMap;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> RippleBMap;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> WakeGridMap;

	int32 Tier = 2;
	bool bV4 = false;
	struct FDetailFrame
	{
		const Sailing::FWaveDetail* Source = nullptr;
		double Time = 0.0;
		Sailing::FWaveDetail::FGrid Chop, Ripple;
	};
	using FDetailFramePtr = TSharedPtr<FDetailFrame, ESPMode::ThreadSafe>;
	TSharedPtr<Sailing::FWaveDetail, ESPMode::ThreadSafe> Detail;
	Sailing::FWaveDetailParams DetailConfigured;
	FDetailFramePtr FramePrev, FrameNext;
	TFuture<FDetailFramePtr> PendingFrame;
	bool bFramePending = false;
	// Perf 1 fix 5: the detail maps' blend, mips and half-float packing run on a worker for the next frame's time; the
	// game thread hands the finished mips to the render thread (UpdateTextureRegions frees them).
	struct FDetailUpload
	{
		TArray<uint8*> A, B, Ripple; // half-float RGBA mips, new[] blocks
		int32 N = 0, RippleN = 0;
		~FDetailUpload() { for (uint8* P : A) delete[] P; for (uint8* P : B) delete[] P; for (uint8* P : Ripple) delete[] P; }
	};
	using FDetailUploadPtr = TSharedPtr<FDetailUpload, ESPMode::ThreadSafe>;
	TFuture<FDetailUploadPtr> PendingUpload;
	bool bUploadPending = false;
	FWakeGrid Wake;  // stepped on a worker: touched by the game thread only while no step is pending
	struct FWakeFrame { TArray<float> Pixels; FVector2D Origin = FVector2D::ZeroVector; int32 N = 0; float Cell = 0.f; };
	TFuture<FWakeFrame> PendingWake;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> ShoreMap;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> Spray;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> DropletMesh;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> SprayMaterial;
	struct FDroplet { FVector P = FVector::ZeroVector, V = FVector::ZeroVector; float Age = 0.f, Life = 1.f, Size = 0.03f; };
	TArray<FDroplet> Droplets;
	TMap<TWeakObjectPtr<AActor>, FVector> LastBow;
	FRandomStream SprayRng = FRandomStream(5);
	float LensSpray = 0.f;
	struct FShoreFrame { TArray<float> Depth; FVector2D Origin = FVector2D::ZeroVector; double Level = 0.0; };
	TFuture<FShoreFrame> PendingShore;
	bool bShorePending = false;
	bool bShoreValid = false;
	FVector2D ShoreOrigin = FVector2D::ZeroVector;
	double ShoreLevel = 0.0;
	bool bWakePending = false;
	float WakeDtPending = 0.f;
	const void* UploadedMask = nullptr;
	size_t UploadedMaskHash = 0;

	TArray<float> RingSpacing;
	int32 RingCount = 6;
	FVector2D GustCenter = FVector2D::ZeroVector;
	float GustTimer = 0.f;
	float WakeTimer = 0.f;
	/**
	 * W2: the two-level wind map. Each level is a square of texels fixed to the world and stored wrap-around (a texel
	 * at world index i lives at i mod Res, the texture wraps), so as the boat moves only the texels coming into view
	 * are new. Per texel: the roughness the water shows (rising in seconds, settling over ten), the local wind's
	 * direction, and a slow speed (half a minute) for slicks and windrows. The near level is updated in strips of rows
	 * from the full wind (VelocityAt); the far level from what a sailor reads (ReadableAt).
	 */
	struct FWindTexel { int32 IX = INT32_MIN, IY = INT32_MIN; float Rough = 0.f, Slow = 0.f, DirX = 1.f, DirY = 0.f; double T = 0.0; };
	struct FWindLevel
	{
		int32 Res = 0, Strips = 1, NextStrip = 0;
		float SizeM = 0.f;
		bool bStarted = false;
		FVector2D Center = FVector2D::ZeroVector;
		TArray<FWindTexel> Texels;
		TArray<uint8> Pixels;
	};
	FWindLevel NearWind, FarWind;
	/** W2: the wind's direction smoothed over minutes, which the windrows follow (they realign slowly after a shift). */
	FVector2D WindrowDir = FVector2D(1.0, 0.0);
	bool bWindrowDirSet = false;
	double LastWindrowTime = 0.0;
	void UpdateWindLevel(FWindLevel& Level, bool bNear, double T);
	/** W2: the trees read the far wind map: their materials (M_Tree*) on the terrain's instanced components are swapped
	 *  for one dynamic instance per material, bound to the map (rescanned every few seconds as trees are placed). */
	void BindTreeWind();
	UPROPERTY(Transient) TMap<TObjectPtr<UMaterialInterface>, TObjectPtr<UMaterialInstanceDynamic>> TreeWindMids;
	float TreeScanTimer = 0.f;
	TArray<uint8> WakePixels;
	FVector2D WakeCenter = FVector2D::ZeroVector;

	struct FWakePoint { FVector2D Pos; float Age; float Speed; };
	TArray<FWakePoint> WakeTrail;
	FVector2D BoatPos = FVector2D::ZeroVector;
	float BoatHeading = 0.f, BoatSpeed = 0.f, BoatHeel = 0.f;
	float TrailTimer = 0.f;
	bool bStaticParamsSet = false;
};
