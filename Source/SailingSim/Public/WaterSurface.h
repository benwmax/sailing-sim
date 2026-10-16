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

	/** Number of mesh rings (quality tier): 4 on Low, 5 on Medium and High (past about 500 m the far grid carries the horizon). */
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
	/** Light air: the share of Monahan's cover that breaks below 12 kn. Monahan's power law is fitted in a breeze and
	 *  still gives 0.04% on the lake at 10 kn, enough for a few metre-long caps in view; Callaghan et al. (2008, GRL 35,
	 *  L23609) put the onset of breaking at 3.7 m/s with cover growing as the cube of the wind above it. 1 from 12 kn,
	 *  ((U - 3.7) / (U12 - 3.7))^3 under it (0.2 at 10 kn), 0 under 7.2 kn. */
	static float WhitecapOnset(float MeanKnots);
	/** W0: the folding threshold M_WaterV4 uses at a pixel: FoamThreshold shifted so coverage scales by the body's scale
	 *  times Monahan's (U_local / U_mean)^3.41, caps cluster in puffs and thin in lulls. CapSlope is the threshold shift
	 *  per e-fold of coverage, measured on the drawn waves (SailingSim.Visual.Whitecaps). Mirrored in make_materials.py. */
	static float FoamThresholdAt(float MeanKnots);
	/** W2: the threshold shift per e-fold grows with the wind (measured on the drawn waves: 0.034 at 10 kn, 0.069 at
	 *  25 kn), so a fixed CapSlope under-applied the lake's and the lulls' scale in a strong breeze (the lake capped 3.3
	 *  to 3.6 times its share at 20 and 25 kn). Mirrored in make_materials.py.
	 *  W8: both refit for the whitecaps' Jacobian (FWaveDetail::CapBlurTexels), which folds less in light air: the sea's
	 *  threshold for Monahan's cover is 0.671 at 10 kn (0.713 before the whitecap mask's finer light-air blur), 0.662 at 14, 0.641 at 20, 0.63 above, falling 0.03 a knot under 10 kn where crests stop breaking (FoamThresholdAt), and the
	 *  shift per e-fold 0.018 at 10 kn to 0.072 at 30 (CapSlopeAt). */
	static float CapSlopeAt(float MeanKnots);
	static float WhitecapThreshold(float LocalOverMean, float WaterScale, float MeanKnots = 14.f);
	/** W8: the fold table (DetailC): per texel of the chop, how folded it is against four thresholds First + k Step
	 *  (a ramp CapRamp wide centred on each). Its mips average cover, where a mip of the Jacobian averages toward 1 (flat)
	 *  and lost every cap past about 40 m from a low camera. CapTable centres the four on the mean wind's threshold, one
	 *  e-fold of cover (CapSlopeAt) apart: the mean reads at an entry, puffs and lulls between. A coarse mip's cover is
	 *  about exponential in the threshold, a single texel's a step: CapCover interpolates in log from mip CapLogMip,
	 *  linearly at mip 0, as M_WaterV4 does. */
	static constexpr float CapRamp = 0.05f;
	/** W8: the drawn surface folds a little less deeply than its CPU copy: on the 20 kn lake the screen's share of
	 *  Jt under 0.7 and 0.8 (-SailingDebugFoam=17, 18) matched the CPU's samples with their deviation from 1 scaled by
	 *  0.85 at both (the texture's bilinear filter and the vertex interpolation of the long trains' fold, not isolated).
	 *  Whitecap mask (docs/water-8/capshape-mac): fitted at 20 kn only, it let the drawn fold overshoot its CPU copy more
	 *  as the wind fell (hard-fold cover 1.55x the lake's target at 20 kn, 2.4x at 16, 3.3x at 12: Monahan's cover falls
	 *  5.8x from 20 to 12 kn, the drawn 2.7x). Each wind's excess over its solved slope gives the scale that lands it:
	 *  0.88 at 20 kn, 0.915 at 16, 0.94 at 12, linear in the wind, held below 12 kn (Callaghan's onset sets the target
	 *  there) and not under W8's 0.85. Likely the long trains, which lose depth to the mesh's interpolation where the
	 *  chop's blurred fold hardly loses any to the texture filter, carry more of the fold as the wind rises. */
	static float DrawnFoldScaleAt(float MeanKnots);
	static constexpr float CapLogMip = 3.f;
	static void CapTable(float MeanKnots, float WaterScale, float& OutFirst, float& OutStep);
	static float CapTableEntry(float J, int32 K, float First, float Step);
	static float CapCover(const float Table[4], float Threshold, float MeanKnots, float Mip, float First, float Step);
	/** Game-thread time spent on the water each frame (the FFT blend and upload, the wake grid), summed: bench.json. */
	static double WaterCpuSeconds;
	/** W2: game-thread time spent on the two-level wind map (bench.json windmap_cpu_ms). */
	static double WindMapCpuSeconds;

	/** Records the boat's stern/bow positions for wake foam (world meters), called by the boat each frame. */
	void SetBoatForWake(const FVector2D& PositionM, float HeadingRad, float SpeedMs, float HeelRad);

	UPROPERTY(EditAnywhere, Category = "Water")
	float FarPlaneSizeMeters = 40000.f;

	/** The far water past the rings (docs/water-8/edge-mac): square rings of cells that grow with the distance as the
	 *  rings' do (PerSide cells along each side, each square one cell larger than the last), from InnerHalfM to
	 *  OuterHalfM, in centimetres about the centre. Per-vertex curvature (d^2 / 2R) then stays within about 1.2 cm of the
	 *  true drop out to the edge (SailingSim.Visual.FarWaterCurvature); one 40 km quad lay 25 to 50 m down. */
	static void BuildFarGrid(float InnerHalfM, float OuterHalfM, int32 PerSide, TArray<FVector>& OutVerts, TArray<int32>& OutTris);
	/** Where the far grid starts for a ring count: one outer-ring cell inside the outer ring's edge. */
	static float FarGridInnerHalfMeters(int32 InRingCount);
	static constexpr int32 FarGridPerSide = 64;

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
	UPROPERTY(VisibleAnywhere, Category = "Water") TObjectPtr<UProceduralMeshComponent> FarPlane;
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
	UPROPERTY(Transient) TObjectPtr<UTexture2D> DetailCMap;
	/** W8: the whitecap threshold solved on the drawn sea (FWaveDetail::CapThreshold), smoothed over a couple of seconds. */
	float CapThrSmooth[4] = { 0.f, 0.f, 0.f, 0.f }, CapSlopeSmooth = 0.f;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> RippleBMap;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> WakeGridMap;
	/** W3: the sea map's atlas (SeaState.h): seven tiles of RGBA half floats, re-uploaded when the field gets a new map. */
	UPROPERTY(Transient) TObjectPtr<UTexture2D> SeaAtlas;
	uint32 UploadedSeaGeneration = 0;
	/** The atlas's half floats are packed on a worker (1.5M texels on the lake: a hitch on the game thread). */
	struct FSeaPixels { TArray<FFloat16> Pixels; int32 Width = 0, Rows = 0, Cols = 0; double OriginX = 0, OriginY = 0, Cell = 0; uint32 Generation = 0; };
	TFuture<TSharedPtr<FSeaPixels, ESPMode::ThreadSafe>> PendingSea;
	bool bSeaPending = false;
	/** Uploads the field's sea map (or unbinds it) when it changed, and sets SeaRect and SeaParams. */
	void UpdateSeaMap();

	int32 Tier = 2;
	bool bV4 = false;
	/** Graphics G8 Ultra showcase: the drawn detail on Ultra tiles twice as far at the same texel (chop 256^2 over 46 m,
	 *  ripples 128^2 over 6.2 m), so the pattern repeats a quarter as often; the wavelength bands, the caps' blur in metres
	 *  and the physics (which never reads this FFT) are unchanged. Opt-in (-SailingUltraDetail): the 4x FFT, cap solve and
	 *  mip packing outran the 30 Hz worker budget and the game thread waited for them (9.8 ms water CPU, Ultra 44 fps at
	 *  1440p against 70 without; docs/graphics-8/ultra). Needs a non-blocking detail pipeline first. */
	bool bUltraDetail = false;
	Sailing::FWaveDetail::FCascadeSpec DrawnChop() const;
	Sailing::FWaveDetail::FCascadeSpec DrawnRipple() const;
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
		TArray<uint8*> A, B, C, Ripple; // half-float RGBA mips, new[] blocks
		int32 N = 0, RippleN = 0;
		float CapFirst = 0.5f, CapStep = 0.05f; // the fold table's thresholds (CapTable)
		// W8: the thresholds that cap Monahan's share of this sea as the mesh draws it at vertex spacings CapSpacing[k]
		// (the long waves' fold fades with the spacing), and the slope at the nearest.
		float CapThr[4] = { 0.f, 0.f, 0.f, 0.f }, CapSlope = 0.f;
		~FDetailUpload() { for (uint8* P : A) delete[] P; for (uint8* P : B) delete[] P; for (uint8* P : C) delete[] P; for (uint8* P : Ripple) delete[] P; }
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
