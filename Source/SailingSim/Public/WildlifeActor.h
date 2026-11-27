#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Async/Future.h"
#include "Wildlife.h"
#include <memory>
#include "WildlifeActor.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;

/**
 * Wildlife Phase 1 (docs/wildlife-1/README.md): the distant birds. Runs Sailing::FBirdFlocks on the sim clock from the
 * world's table (<World>.wildlife.json) over a habitat map of the terrain round the camera (rebuilt on a worker once the
 * camera is 1.5 km from its centre), and draws what it returns: far birds (400 m to 2 km) as camera-facing quads whose
 * silhouette and wingbeat M_BirdFar draws from per-instance data, mid and near birds as low bodies per flight style
 * (SM_Bird_<Style>, Tools/blender/build_birds.py) whose wings M_BirdMid flaps. Until those meshes are imported every bird
 * is a quad. Everything is instanced, unshadowed and out of the distance-field and Lumen scenes.
 * -SailingNoWildlife leaves it out; -SailingWildlifeScale=<f> scales every bird's density (1 the tables');
 * -SailingDebugBirds[=<k>] draws every bird k times its size (10) and whole, and pins three quads and three bodies in the
 * view, to find them in a still; -SailingDebugBirdsPlain draws them all with the engine's default material.
 */
UCLASS()
class SAILINGSIM_API AWildlifeActor : public AActor
{
	GENERATED_BODY()

public:
	/** The habitat window's half size and cell (m); rebuilt when the camera is RebuildM from its centre. */
	static constexpr double MapHalfM = 4000.0;
	static constexpr double MapCellM = 50.0;
	static constexpr double RebuildM = 1500.0;
	/** A far bird is never drawn under this many pixels across: smaller, its quad keeps this size and its cover thins. */
	static constexpr double MinPixels = 2.0;
	/** A body only for a bird at least this many pixels across: smaller, its wings are thinner than a pixel and the quad's
	 *  silhouette (held a pixel thick) reads better. */
	static constexpr double BodyMinPixels = 12.0;
	/** The view cone's margin past the screen's corners (deg): birds just off screen are drawn first too. */
	static constexpr double ViewMarginDeg = 8.0;
	/** Per-instance floats of the quads (M_BirdFar) and the bodies (M_BirdMid); keep in step with scripts/import_birds.py. */
	static constexpr int32 FarFloats = 13;
	static constexpr int32 MidFloats = 11;

	AWildlifeActor();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;

	/** The flocks (for tests and the bench line). */
	const Sailing::FBirdFlocks& GetFlocks() const { return Flocks; }
	int32 GetDrawnQuads() const { return DrawnQuads; }
	int32 GetDrawnBodies() const { return DrawnBodies; }

	/**
	 * A far bird's quad (the engine's 1 m plane, +Z its face): turned to the camera with its x along the bird's span as the
	 * camera sees it (the wings foreshortened: OutSpanScale, 0.25..1) and its y up the screen. Sized at least MinPixels
	 * (PixelAngle: radians a pixel) both ways; OutCover is the share of the bird's own size that leaves (1 when it is big
	 * enough), OutWiden how much wider than the foreshortened span the quad is held (1 unless that is under MinPixels).
	 * Shared with SailingSim.Wildlife.Sprites.
	 */
	static FTransform FarQuad(const FVector& BirdCm, const FVector& CameraCm, double HeadingRad, double BankRad, double SpanM,
		double PixelAngle, double& OutSpanScale, double& OutCover, double* OutWiden = nullptr);
	/** A body's transform: its mesh is built along +X (forward), wings on Y, span 1 m (build_birds.py). */
	static FTransform BodyTransform(const FVector& BirdCm, double HeadingRad, double PitchRad, double BankRad, double SpanM);
	/** The flight style's mesh name (SM_Bird_<Name>). */
	static const TCHAR* StyleMeshName(Sailing::EBirdStyle Style);

private:
	UInstancedStaticMeshComponent* MakeIsm(const TCHAR* Name, UStaticMesh* Mesh, UMaterialInterface* Material, int32 Count, int32 Floats);
	void BuildWorld(Sailing::FWildlifeWorld& Out, double CenterN, double CenterE) const;
	void StartMapBuild(double CenterN, double CenterE, bool bWait);
	void GatherObservers(const FVector& CameraMapCm, Sailing::FBirdObservers& Out, double Dt);
	Sailing::FWildlifeConditions Conditions(const FVector& CameraMapCm) const;
	void DrawBirds(const FVector& CameraMapCm);
	/** -SailingDebugBirds / -SailingDebugBirdsPlain: the components and a pinned bird as the engine holds them, for the log. */
	FString DebugState(const FVector& CameraMapCm) const;

	UPROPERTY(Transient) TObjectPtr<UStaticMesh> QuadMesh;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> FarMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> MidMaterial;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> FarIsm;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> StyleIsms;   // by EBirdStyle; null: drawn as quads

	Sailing::FWildlifeTable Table;
	Sailing::FBirdFlocks Flocks;
	std::shared_ptr<const Sailing::FWildlifeHabitatMap> Map;
	TFuture<std::shared_ptr<const Sailing::FWildlifeHabitatMap>> PendingMap;
	bool bMapBuilding = false;
	bool bSecondMap = false;
	double MapTide = 0.0;
	TSet<FIntPoint> HarbourCells;            // 100 m cells holding docks, decks, moored boats or the marina
	TArray<Sailing::FBirdLook> Looks;        // per table bird
	TMap<TWeakObjectPtr<AActor>, FVector> LastVessel;   // power vessels' last place (map cm), for their speed
	double LastSimTime = -1.0;
	int32 Tier = 2;
	int32 FarPool = 0;
	TArray<int32> StylePool;
	int32 DrawnQuads = 0, DrawnBodies = 0, DrawnInView = 0;
	/** One pool's instances held to their birds (Sailing::FBirdDraw::Key) from frame to frame: a bird keeps its instance
	 *  while it is drawn in that pool, so the instance moves as the bird does and the renderer's motion vectors (TSR, motion
	 *  blur) are the bird's own. Handed out nearest first, the instances jumped between birds every frame and TSR smeared
	 *  every near bird (the reel's AA test, Nov 27: hard-edged with AA off). */
	struct FBirdPool
	{
		struct FBird
		{
			uint64 Key = 0;
			FTransform Xf;                // map frame, cm
			float Data[FarFloats] = {};   // its per-instance floats (a body uses the first MidFloats)
		};
		TArray<FBird> Now;                // this frame's birds in the pool, in draw order
		TMap<uint64, int32> SlotOf;       // last frame's birds and their instances
		TArray<uint64> Holder;            // each instance's bird last frame (0 none)
		TArray<FTransform> Last;          // each instance's transform last frame (map frame, cm)
		int32 Sent = 0;                   // instances sent last frame (every held one is below it)
	};
	FBirdPool FarSlots;
	TArray<FBirdPool> BodySlots;             // by EBirdStyle
	// What DrawBirds last sent (it sends only the instances held this frame or the last and, after a move, the parked ones).
	bool bParkedSent = false;
	FVector ParkedAtCm = FVector::ZeroVector;
	FVector ParkedOriginCm = FVector::ZeroVector;
	FString NearestInView;                   // the nearest drawn bird on screen, for the log line
	double DebugSize = 0.0;                  // -SailingDebugBirds: every bird this many times its size (0 off)
	int32 Markers = 0;                       // -SailingDebugBirds: birds pinned in the view (the pools' last slots)
	int32 MarkerQuad = -1;                   // the nearest pinned quad's instance (-1 none)
	bool bPlainDebug = false;                // -SailingDebugBirdsPlain: the engine's default material on every bird
	bool bRaftsLogged = false;               // -SailingBirdRaft's result logged
	double NextLog = 0.0;
};
