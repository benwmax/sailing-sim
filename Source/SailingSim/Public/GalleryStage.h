#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/StreamableManager.h"
#include "Gallery.h"
#include "Showroom.h"
#include "GalleryStage.generated.h"

class AFreeCamera;
class UStaticMeshComponent;
class UProceduralMeshComponent;
class URectLightComponent;
class UMaterialInterface;
class UTexture2D;

UENUM()
enum class EGalleryLight : uint8 { Studio, Noon, GoldenHour, Overcast };
UENUM()
enum class EGalleryView : uint8 { Lit, Wireframe, LitWire };
/** Auto, a forced LOD (non-Nanite), Nanite's fallback mesh, or a twin shown in its place. */
UENUM()
enum class EGalleryDetail : uint8 { Auto, Lod, Fallback, LightTwin, FarTwin };

/** What the stats card shows for the mesh on the stage. */
struct FGalleryStats
{
	FString Path;
	int32 Triangles = 0, Lods = 0, ShownLod = 0, Materials = 0;
	bool bNanite = false;
	FVector SizeM = FVector::ZeroVector;
	float ScreenPercentage = 100.f;
};

/**
 * The gallery's stage (docs/gallery-core/, Inputs/gallery/brief.md G1, section 4): a display mesh the free camera orbits
 * (AFreeCamera's code-driven orbit, the showroom's), in a studio cyclorama with three rect lights 1 km over open water,
 * or on the lake in a light preset (the conditions preview). Client-side presentation only: it spawns nothing the
 * simulation reads. The screen (G2, the PC's) drives it through these calls; launch args drive it for stills.
 */
UCLASS(NotBlueprintable)
class SAILINGSIM_API AGalleryStage : public AActor
{
	GENERATED_BODY()

public:
	AGalleryStage();
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

	/** Opens the stage: the camera takes the view, the graphics are snapshotted, the near clip comes in to 1 cm. */
	void Open(APlayerController* PC);
	/** Back as it was: the view, the conditions (if a lake preset changed them), the near clip. The graphics are the
	 *  caller's choice (Keep or Restore: RestoreGraphics). */
	void Close();
	bool IsOpen() const { return bOpen; }

	/** Shows an item (its mesh loads asynchronously; the one before stays until it lands). Whole boats come in G3. */
	void Show(const FGalleryItem& Item);
	/** The same after 200 ms without another call (the list's flick-through). */
	void Select(const FGalleryItem& Item);
	const FGalleryItem& GetItem() const { return Item; }
	bool IsLoading() const { return Load.IsValid(); }

	void SetLight(EGalleryLight Light);
	EGalleryLight GetLight() const { return LightPreset; }
	void SetView(EGalleryView View);
	EGalleryView GetView() const { return ViewMode; }
	/** Lod is the level for EGalleryDetail::Lod (0 = the finest). */
	void SetDetail(EGalleryDetail Detail, int32 Lod = 0);
	EGalleryDetail GetDetail() const { return DetailMode; }
	FGalleryStats GetStats() const;

	/** The orbit (the screen forwards mouse and stick here): degrees, zoom steps, a pan in view-plane cm, reset. */
	void Orbit(const FVector2D& DeltaDeg);
	void Zoom(float Steps);
	void Pan(const FVector2D& DeltaCm);
	void ResetView();
	AFreeCamera* GetCamera() const { return Camera; }

	/** Compare tiers: the same shot at two Quality tiers, each captured after it settles; then the tier goes back. */
	void StartCompare(uint8 TierA, uint8 TierB);
	bool IsComparing() const { return CompareStep > 0; }
	UTexture2D* GetCompareA() const { return CompareA; }
	UTexture2D* GetCompareB() const { return CompareB; }
	/** Called with the two captures once they are done (stills save them). */
	TFunction<void(const TArray<FColor>& A, const TArray<FColor>& B, FIntPoint Size)> OnCompareDone;

	/** The graphics as they were when the stage opened (Restore my settings, or the leaving prompt's Restore). */
	const SailGallery::FGraphicsSnapshot& GetGraphicsOnOpen() const { return GraphicsOnOpen; }
	bool GraphicsChanged() const { return SailGallery::FGraphicsSnapshot::Capture() != GraphicsOnOpen; }
	void RestoreGraphics();

	/**
	 * Stills and checks without the screen (G2): -SailingGallery=<path, key or name> opens the stage on that asset;
	 * -SailingGalleryLight=Studio|Noon|GoldenHour|Overcast, -SailingGalleryView=Lit|Wireframe|LitWire,
	 * -SailingGalleryDetail=Auto|Lod1|Lod2|Fallback|Light|Far, -SailingGalleryCompare=Low,Ultra (5 s in; saves
	 * Saved/Bench/<shot>-compare.png, tier A left of the split, B right). Developer tools only (bDeveloperTools).
	 */
	static AGalleryStage* OpenFromArgs(APlayerController* PC);
	/** A tier's name and back ("Low", "Medium", "High", "Ultra"); -1 for a name it doesn't know. */
	static int32 TierFromName(const FString& Name);
	/** The compare still: A's left half beside B's right half, a white split between (both Size). */
	static TArray<FColor> CompareSplit(const TArray<FColor>& A, const TArray<FColor>& B, FIntPoint Size);

	/** The display mesh's place for an item's bounds on the lake (map m): floating things at the waterline. */
	static bool Floats(const FGalleryItem& Item);
	/** The framing for a bounding sphere: the distance at which it fills Fill of the view's height. */
	static float FramingDistanceCm(float RadiusCm, float VerticalFovDeg, float Fill = 0.7f);

private:
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Turntable;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Display;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UProceduralMeshComponent> Cyclorama;
	UPROPERTY(VisibleAnywhere) TObjectPtr<URectLightComponent> Key;
	UPROPERTY(VisibleAnywhere) TObjectPtr<URectLightComponent> Fill;
	UPROPERTY(VisibleAnywhere) TObjectPtr<URectLightComponent> Rim;
	UPROPERTY(Transient) TObjectPtr<AFreeCamera> Camera;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> WireMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> StudioMaterial;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> CompareA;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> CompareB;
	TWeakObjectPtr<APlayerController> Player;
	TWeakObjectPtr<AActor> PreviousView;

	bool bOpen = false;
	FGalleryItem Item, Pending;
	FSailDebounce SelectDebounce;
	TSharedPtr<FStreamableHandle> Load, Shown;
	double LoadStart = 0.0;
	EGalleryLight LightPreset = EGalleryLight::Studio;
	EGalleryView ViewMode = EGalleryView::Lit;
	EGalleryDetail DetailMode = EGalleryDetail::Auto;
	int32 DetailLod = 0;
	bool bPreviewed = false;
	float SavedNearClip = 10.f;
	float CycloramaRadiusCm = 0.f;
	FVector StudioCentre = FVector::ZeroVector, LakeCentre = FVector::ZeroVector;
	SailGallery::FGraphicsSnapshot GraphicsOnOpen;
	FVector2D PanCm = FVector2D::ZeroVector;

	// Compare: the step (0 off), when this step started, the tiers, the tier to go back to, the captures.
	int32 CompareStep = 0;
	double CompareAt = 0.0;
	uint8 CompareTiers[2] = { 0, 3 };
	uint8 CompareRestoreTier = 0;
	TArray<FColor> CapturedA, CapturedB;
	FIntPoint CaptureSize = FIntPoint::ZeroValue;

	void FinishLoad();
	void EnsureMaterials();
	UStaticMesh* MeshForDetail() const;
	void ApplyMesh();
	void ApplyView();
	void ApplyFraming(bool bKeepAngle);
	void PlaceForLight();
	void BuildCyclorama(float RadiusCm);
	void SetTier(uint8 Tier);
	/** The capture goes through the engine's screenshot (the frame as shown, without the UI), into memory. */
	void RequestCapture();
	void OnCaptured(int32 Width, int32 Height, const TArray<FColor>& Colors);
	FDelegateHandle CaptureHandle;
	bool bCaptureWaiting = false, bCaptured = false;
	TArray<FColor> CapturedNow;
	FIntPoint CapturedNowSize = FIntPoint::ZeroValue;
	UTexture2D* MakeTexture(const TArray<FColor>& Pixels, FIntPoint Size);
	void TickCompare();
};
