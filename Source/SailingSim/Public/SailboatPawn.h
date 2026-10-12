#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "InputActionValue.h"
#include "Drills.h"
#include "Navigation.h"
#include "Logbook.h"
#include "Replay.h"
#include "ReferenceCapture.h"
#include "SailboatPawn.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class UProceduralMeshComponent;
class UInputAction;
class UInputMappingContext;
class UMaterialInterface;
class UAudioComponent;
class USailingSynthWave;
class AWaterSurface;

/**
 * The player's boat (any of the fleet; the J/22 by default). Physics (Sailing::FBoatModel) steps at a fixed
 * 120 Hz; this actor builds the boat's visuals from its particulars (hulls, foils, rig, crew), shapes the sails
 * from the physics strips, and turns the player's input into tiller, sheets, traveler, sail shape, crew weight,
 * spinnaker, reefs, board, engine and righting.
 */
UCLASS()
class SAILINGSIM_API ASailboatPawn : public APawn
{
	GENERATED_BODY()

public:
	ASailboatPawn();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;

	const Sailing::FBoatModel& GetBoatModel() const { return Boat; }
	const Sailing::FBoatControls& GetControls() const { return Controls; }
	const Sailing::FWindField& GetWind() const;
	bool IsTrimAssistActive() const;

	/** Puts the boat back at its start (the launch spot on the lake), with a little way on. */
	void ResetBoat();

	/** Dock lines: tie up to the nearest dock (within reach of the cleats, nearly stopped), or cast off. */
	bool ToggleDockLines();
	bool IsTiedUp() const { return Boat.GetMooringLines().size() > 0; }

	/** Starts a learning drill (positions the boat for docking drills). */
	void StartDrill(ESailingDrill Drill);
	const FDrillRunner& GetDrill() const { return DrillRunner; }
	/** A short message for the HUD (tie-up results and the like), empty when none. */
	FString GetStatusMessage() const { return Boat.GetState().Time < StatusUntil ? StatusMessage : FString(); }
	/** Index of the selected drill in the settings menu. */
	ESailingDrill GetMenuDrill() const { return MenuDrill; }

	/** Applies the current difficulty to the physics (helm feel, damping). */
	void ApplyDifficulty();

	/** Switches to another boat in the fleet (Sailing::EBoatType) and puts it at the launch spot. */
	void SetBoat(int32 Type);

	/** Settings menu (Tab / controller Menu) and controls card (? / controller View). */
	bool IsMenuOpen() const { return bMenuOpen; }
	int32 GetMenuIndex() const { return MenuIndex; }
	bool IsControlsCardOpen() const { return bControlsCard; }
	/** The keys screen (Tab > Keys): every command with its keyboard key; Enter rebinds, Backspace restores. */
	struct FKeyRow { FName Action; bool bNegative = false; FString Label; FKey Key; };
	bool IsKeysOpen() const { return bKeysOpen; }
	const TArray<FKeyRow>& GetKeyRows() const { return KeyRows; }
	int32 GetKeysIndex() const { return KeysIndex; }
	bool IsCapturingKey() const { return bCapturingKey; }
	const FString& GetKeysMessage() const { return KeysMessage; }
	/** Rebinds a command's keyboard key (as the keys screen does; for tests). Returns false if no such command. */
	bool Rebind(FName Action, bool bNegative, const FKey& Key);
	/** Menu rows: label and current value, for the HUD. */
	TArray<TPair<FString, FString>> GetMenuRows() const;
	/** Seconds of physics time since the boat was put on the water (resets don't restart the weather clock). */
	double GetSessionTime() const { return Boat.GetState().Time; }

	/** Navigation (on the coast): the chart view, the plot of bearings, fixes and dead reckoning, and the GPS. */
	bool IsChartOpen() const { return bChartOpen; }
	FVector2D GetChartCenter() const { return ChartCenter; }
	double GetChartMetersPerPixel() const { return ChartMetersPerPixel; }
	const SailingNav::FPlot& GetPlot() const { return Plot; }
	bool IsGpsShown() const { return bShowGps; }
	/** Where the boat really is (map frame, m) and her heading (true, degrees). */
	FVector2D GetMapPosition() const;
	double GetHeadingTrueDeg() const;
	/** Takes a bearing with the hand-bearing compass on the charted object nearest the line of sight. */
	bool TakeBearing();
	/** Records a bearing on a charted object (what TakeBearing does once it has found one). */
	bool RecordBearing(const FString& Name, const FVector2D& Object);

	/**
	 * Traffic: an AI sailboat drawn by this same actor. Set before BeginPlay (spawn deferred); the traffic simulation
	 * steps the returned model and hands over the controls each frame; this actor only draws her.
	 */
	UPROPERTY() bool bTrafficBoat = false;
	FLinearColor TrafficHullColor = FLinearColor(0.94f, 0.94f, 0.92f);
	Sailing::FBoatModel* InitTraffic(int32 Type, double X, double Y, double HeadingRad);
	void SetTrafficControls(const Sailing::FBoatControls& InControls) { Controls = InControls; }
	Sailing::FBoatModel& GetMutableBoatModel() { return Boat; }
	/** The ship's log (Y shows it). Other systems add events (race results, rules judgments). */
	const FLogbook& GetLogbook() const { return Logbook; }
	bool IsLogOpen() const { return bLogOpen; }
	void AddLogEvent(const FString& Remarks);
	/** The passage plan's next waypoint on the coast (index into the area's plan), or -1. */
	int32 GetPassageIndex() const { return PassageIndex; }

	/** Replays: each run (from a reset, a drill or a race start) is recorded; watch the last one (,) or sail against
	 *  it as a ghost (Tab > Ghost). Photo mode (9) freezes the world for pictures. */
	UPROPERTY() bool bGhost = false;  // a traffic-mode actor drawn translucent: the replay's boat
	void BeginRun(const FString& Label);
	bool IsWatching() const { return bWatching; }
	bool IsPhotoMode() const { return bPhoto; }
	bool IsGhostOn() const { return bGhostOn; }
	const FReplay& GetLastRun() const { return LastRun; }
	double GetWatchTime() const { return WatchTime; }
	float GetWatchSpeed() const { return WatchSpeed; }
	double GetPhotoHintUntil() const { return PhotoHintUntil; }
	void SetGhostFrame(const FReplayFrame& Frame);

	/** Reference capture (-SailingCapture=<preset>): a reference camera, locked exposure, no HUD, telemetry CSV. */
	bool IsCaptureMode() const { return CapturePreset != ECapturePreset::None; }
	ECapturePreset GetCapturePreset() const { return CapturePreset; }
	UCameraComponent* GetCaptureCamera() const { return CaptureCamera; }
	void AddCameraOrbit(const FVector2D& Delta, float ZoomDelta);

	/** Another vessel's whistle or the committee's horn, heard aboard (0 = silent). */
	void SetHorn(float Level, float Hz);
	/** The player's status under the rules: sailing, or power-driven with the engine running. */
	bool IsMotoring() const;

	/** Initial speed through the water in knots. */
	UPROPERTY(EditAnywhere, Category = "Boat")
	float StartSpeedKnots = 3.f;

	UPROPERTY(VisibleAnywhere, Category = "Boat")
	TObjectPtr<USceneComponent> BoatRoot;

	/** Hull shells and decks, generated from the physics hull shapes. */
	UPROPERTY(VisibleAnywhere, Category = "Boat")
	TObjectPtr<UProceduralMeshComponent> HullMesh;

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<UCameraComponent> Camera;

	/** The reference camera (capture mode only): rigid on the boat, or standing off her on the water. */
	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<UCameraComponent> CaptureCamera;

private:
	UStaticMeshComponent* AddPart(FName Name, UStaticMesh* Mesh, const FVector& LocationCm, const FVector& SizeCm, const FRotator& Rotation = FRotator::ZeroRotator, USceneComponent* Parent = nullptr);
	/** A runtime part of the current boat (rebuilt when the boat changes), colored. */
	UStaticMeshComponent* AddBoatPart(UStaticMesh* Mesh, const FVector& LocationCm, const FVector& SizeCm, const FLinearColor& Color, const FRotator& Rotation = FRotator::ZeroRotator, USceneComponent* Parent = nullptr);
	/** A cylinder from one body point to another (stays, beams). */
	UStaticMeshComponent* AddRod(const Sailing::Vec3& A, const Sailing::Vec3& B, double DiameterM, const FLinearColor& Color);
	void RebuildBoatVisuals();
	void BuildHullMesh();
	void ApplyStateToTransform();
	void UpdateRigVisuals(float DeltaSeconds);
	void BuildSailMesh(UProceduralMeshComponent* Mesh, const Sailing::FSailGeometry& Geo, const Sailing::FSailStripState* Strips, int32 Side, bool bMain);
	void UpdateTelltales();
	void CreateInput();
	void ApplyHeldInputs(float DeltaSeconds);

	void OnAxis(const FInputActionValue& Value, FName Action);
	void OnAxisReleased(const FInputActionValue& Value, FName Action);
	void OnLook(const FInputActionValue& Value);
	void OnZoom(const FInputActionValue& Value);
	void OnButton(const FInputActionValue& Value, FName Action);
	void ChangeMenuValue(int32 Direction);
	void UpdateSound(float DeltaSeconds);

	Sailing::FBoatModel Boat;
	Sailing::FBoatControls Controls;
	Sailing::FFixedStepper Stepper;
	Sailing::FAutoTrim TrimAssist;
	/** -SailingDemo: the autopilot sails close-hauled and tacks every few seconds, for recordings and the QA gate. */
	bool bDemo = false;
	FString StatusMessage;
	FDrillRunner DrillRunner;
	ESailingDrill MenuDrill = ESailingDrill::None;
	double MaxContactKnots = 0.0;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> MarkMeshes;
	UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> DummyMesh;
	void UpdateDrillVisuals();
	void UpdateNavLights();
	void UpdateLogbook(float DeltaSeconds);
	void UpdateGhost(float DeltaSeconds);
	void BuildKeyRows();
	void AssignKey(int32 Row, const FKey& Key);
	void RebuildMappings();
	void PollKeyCapture();
	bool bKeysOpen = false, bCapturingKey = false;
	uint64 CaptureFrame = 0;
	int32 KeysIndex = 0;
	TArray<FKeyRow> KeyRows;
	FString KeysMessage;
	ASailboatPawn* EnsureGhost();
	void ApplyGhostMaterial();
	void SetWatching(bool bOn);
	void SetPhoto(bool bOn);
	void TakePhoto();
	FReplay Recording, LastRun;
	void SetupCapture();
	void UpdateCapture(float DeltaSeconds);
	void WriteCaptureSettings() const;
	ECapturePreset CapturePreset = ECapturePreset::None;
	FCaptureTelemetry CaptureTelemetry;
	FString CaptureName;
	float CaptureBearing = NAN;       // degrees off the bow; NAN until the leeward side is known
	float CaptureEV = NAN;            // -SailingEV; NAN = auto exposure, frozen once settled
	double CaptureElapsed = 0.0, CaptureSettingsWritten = -1.0;
	bool bExposureFrozen = false;
	bool bShoreStandSet = false;
	float HelmSide = 0.f;             // helm eye: -1 port .. +1 starboard, moving across after a tack
	FVector ShoreStand = FVector::ZeroVector;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> LensDistortionMaterial;
	UPROPERTY() TObjectPtr<UMaterialInterface> LensDistortionAsset; // referenced for the cook
	bool bGhostOn = false, bWatching = false, bPhoto = false;
	double WatchTime = 0.0;
	float WatchSpeed = 1.f;
	double PhotoHintUntil = 0.0;
	UPROPERTY(Transient) TObjectPtr<ASailboatPawn> GhostBoat;
	FLogEntry MakeLogEntry(const TCHAR* Kind, const FString& Remarks) const;
	FLogbook Logbook;
	bool bLogOpen = false;
	bool bLogStarted = false;
	double LogNm = 0.0;
	double NextWatchUnix = 0.0;
	int32 PassageIndex = -1;
	bool bWasAground = false, bWasCapsized = false, bWasTouching = false, bWasDrillComplete = false;
	void SetChartOpen(bool bOpen);
	SailingNav::FPlot Plot;
	bool bChartOpen = false;
	bool bShowGps = true;
	bool bChartArgsApplied = false;
	FVector2D ChartCenter = FVector2D::ZeroVector;
	double ChartMetersPerPixel = 8.0;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> NavLights; // port, starboard, stern, steaming
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> EmissiveMaterial;
	// Not transient: the default object's reference is what puts M_Ghost into the cook (it is only used at runtime).
	UPROPERTY() TObjectPtr<UMaterialInterface> GhostMaterial;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> SphereMesh;
	double StatusUntil = 0.0;
	bool bDemoTacks = true;
	bool bMenuOpen = false;
	bool bControlsCard = false;
	int32 MenuIndex = 0;
	double PrevMainSheet = 0.0, PrevJibSheet = 0.0;
	Sailing::FAutopilot DemoPilot;
	double DemoFirstSign = 1.0;
	Sailing::FWindField FallbackWind;
	double WaterSurfaceZ = 0.0; // cm
	FVector StartLocation = FVector::ZeroVector;
	float StartYaw = 0.f;

	/** Held axis values from the input system, applied each frame as rates. */
	TMap<FName, float> HeldAxes;
	float KeyboardTiller = 0.f;
	double LastManualTrimTime = -100.0;
	float CameraYaw = 0.f;
	float CameraPitch = -14.f;
	float CameraDistance = 1600.f;
	float VisualTime = 0.f;

	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TObjectPtr<UProceduralMeshComponent> MainSail;
	UPROPERTY(Transient) TObjectPtr<UProceduralMeshComponent> JibSail;
	UPROPERTY(Transient) TObjectPtr<UProceduralMeshComponent> SpinSail;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> CubeMesh;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> CylinderMesh;
	UPROPERTY(Transient) TArray<TObjectPtr<USceneComponent>> BoatParts;     // everything rebuilt with the boat
	UPROPERTY(Transient) TArray<TObjectPtr<USceneComponent>> RudderPivots;  // one per rudder
	UPROPERTY(Transient) TObjectPtr<USceneComponent> BoomPivot;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> MastheadFly;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Crew;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> JibTelltales;  // windward/leeward pairs at three heights
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> LeechTelltales; // main leech, three heights

	UPROPERTY(Transient) TObjectPtr<UAudioComponent> SoundComponent;
	UPROPERTY(Transient) TObjectPtr<USailingSynthWave> Synth;
	UPROPERTY(Transient) TObjectPtr<AWaterSurface> Water;

	UPROPERTY(Transient) TObjectPtr<UInputMappingContext> MappingContext;
	UPROPERTY(Transient) TMap<FName, TObjectPtr<UInputAction>> Actions;
};
