#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "InputActionValue.h"
#include "Drills.h"
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
	/** Menu rows: label and current value, for the HUD. */
	TArray<TPair<FString, FString>> GetMenuRows() const;
	/** Seconds of physics time since the boat was put on the water (resets don't restart the weather clock). */
	double GetSessionTime() const { return Boat.GetState().Time; }

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
