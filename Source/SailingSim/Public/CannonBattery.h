#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Cannons.h"
#include "CannonBattery.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UPointLightComponent;
class UStaticMesh;
class UMaterialInterface;
class UMaterialInstanceDynamic;

/** A gun went off (or flashed in the pan): for the sound, the camera and the ship's heel. */
struct FCannonFiredEvent
{
	int32 Gun = -1;
	Sailing::ECannonKind Kind = Sailing::ECannonKind::Long24;
	Sailing::ECannonSide Side = Sailing::ECannonSide::Port;
	FVector MuzzleWorld = FVector::ZeroVector;   // cm, the render's world
	FVector BoreWorld = FVector::ForwardVector;  // unit
	double ChargeKg = 0.0;
	double ImpulseNs = 0.0;                      // the recoil's impulse (0 for a flash in the pan)
	bool bMisfire = false;
};

DECLARE_MULTICAST_DELEGATE_OneParam(FOnCannonFired, const FCannonFiredEvent&);

/**
 * The frigate's guns in the game (docs/cannon-fire/): Sailing::FCannonBattery's drill drawn on the ship (barrels, carriages,
 * trucks, quoins, carronades' beds and slides, the gear swapped by pose, the lids), the smoke as lit camera-facing sprites
 * (M_CannonSmoke), the flame and sparks (M_CannonFlash) and a few pooled flash lights. Attach it to the ship's root, whose
 * frame is the model's (guns.json: X forward, Y to starboard, Z up, cm). Until the PC imports the guns (/Game/Boats/Frigate/
 * Guns/SM_Frigate_*) it draws stand-ins (the engine's cylinder and cube).
 *
 * Orders come from the orders panel (the walking-below thread) through Order/SetFireMode; GetSideStatus feeds the panel;
 * OnGunFired the camera shake and sound. GetForceOnShip/GetMomentOnShip hand the recoils' push to the ship's physics.
 * Tuning (docs/cannon-fire/tuning.md): -SailingCannonFx="Key=V,...", Saved/CannonFx.txt (re-read each second when it
 * changes, not in Shipping), console sailing.CannonFx [Key Value]. Bench and stills: -SailingBroadside=<s>[,side[,mode]],
 * -SailingBroadsideEvery=<s>, -SailingCannonStage[=<fwd m>,<right m>,<heading deg>] (a battery without the frigate, off the
 * player's boat), -SailingNoCannonSmoke, -SailingNoCannonLights, -SailingDebugCannons.
 */
UCLASS()
class SAILINGSIM_API ACannonBattery : public AActor
{
	GENERATED_BODY()

public:
	ACannonBattery();

	/** Spawn a battery on the ship's root (its frame the model's), the frigate's guns, housed. */
	static ACannonBattery* SpawnBattery(USceneComponent* ShipRoot);
	/** -SailingCannonStage: a battery on its own (stand-in guns) off the player's boat, for tuning before the frigate. */
	static ACannonBattery* SpawnStageIfAsked(UWorld* World);

	void Order(Sailing::ECannonOrder InOrder, Sailing::ECannonSide Side);
	void SetFireMode(Sailing::ECannonFireMode Mode);
	Sailing::ECannonFireMode GetFireMode() const { return Battery.GetFireMode(); }
	Sailing::FCannonSideStatus GetSideStatus(Sailing::ECannonSide Side) const { return Battery.Status(Side); }
	/** Every gun on a side run out, loaded and ready at once (benches, stills). */
	void MakeReady(Sailing::ECannonSide Side);

	/** The recoils' mean force on the ship over the last frame (N) and its moment about the ship's origin (N m), ship frame. */
	FVector GetForceOnShip() const { return FVector(Battery.ForceOnShip().X, Battery.ForceOnShip().Y, Battery.ForceOnShip().Z); }
	FVector GetMomentOnShip() const { return FVector(Battery.MomentOnShip().X, Battery.MomentOnShip().Y, Battery.MomentOnShip().Z); }

	const Sailing::FCannonBattery& GetBattery() const { return Battery; }
	const Sailing::FCannonSmoke& GetSmoke() const { return Smoke; }
	const Sailing::FCannonParams& GetParams() const { return Params; }
	/** Apply "Key=V,..." (or a file's lines) over the current parameters; returns how many applied. */
	int32 ApplyTuning(const FString& Text, FString* OutUnknown = nullptr);
	FString DumpTuning() const { return FString(UTF8_TO_TCHAR(Params.Dump().c_str())); }

	FOnCannonFired OnGunFired;

	/** The game thread's time in every battery's Tick (for bench.json's cannon_cpu_ms). */
	static double CpuSeconds;
	/** The puffs alive in every battery now (bench.json's cannon_puffs). */
	static int32 PuffsAlive;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

private:
	struct FPartMesh
	{
		TObjectPtr<UStaticMesh> Mesh;
		FTransform Fix = FTransform::Identity;   // a stand-in's own turn and scale into the part's frame
		bool bStandIn = false;
	};
	enum EPart : uint8 { LongBarrel, LongCarriage, LongQuoin, TruckFore, TruckHind, CarrBarrel, CarrBed, CarrSlide, Lid, PartCount };

	void InitParams();
	void BuildGunVisuals();
	FPartMesh LoadPart(const TCHAR* Name, EPart Part) const;
	void UpdateGunVisuals(bool bAll);
	void UpdateSmokeVisuals(const FVector& Cam);
	FVector SunDirection();
	void UpdateFlashVisuals(const FVector& Cam, double Now);
	void UpdateLights(double Now);
	void PollTuningFile(float DeltaSeconds);
	/** The look's parameters into the materials' instances. */
	void PushLook();
	void RunBenchArgs(double Now);
	/** -SailingCannonStage: keep station off the player's boat. */
	void FollowStage();
	double SimNow() const;
	/** The ship's frame (m) to the render's world (cm). */
	FVector ShipToWorld(const Sailing::Vec3& P) const;
	FVector ShipDirToWorld(const Sailing::Vec3& D) const;
	/** The render's world (cm) to the smoke's frame (map metres; z over the physics' water datum). */
	Sailing::Vec3 WorldToSmoke(const FVector& W) const;
	FVector SmokeToWorld(const Sailing::Vec3& P) const;
	FTransform PortFrame(const Sailing::FGun& G, double X, double Z) const;   // relative to the ship's root (cm)

	Sailing::FCannonBattery Battery;
	Sailing::FCannonSmoke Smoke;
	Sailing::FCannonParams Params;
	FString CommandLineTuning;

	UPROPERTY(Transient) TObjectPtr<USceneComponent> Root;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> PartISMs;   // by EPart
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Gear;                 // one per gun (its pose's gear)
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Lids;                 // one per gun with its own lid mesh (SM_Frigate_Lid_NN_S)
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> CoverISMs;   // the housed guns' tompions and aprons
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMesh>> GearMeshes;                    // gun x 3 poses (housed/run in/run out; carronade -/recoil/run out)
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> SmokeISM;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> FlashISM;
	UPROPERTY(Transient) TArray<TObjectPtr<UPointLightComponent>> Lights;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> SmokeMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> FlashMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> SmokeMID;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> FlashMID;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> QuadMesh;
	TArray<FPartMesh> Parts;
	/** Each gun's instance in its parts' ISMs (-1: none) and the pose its gear shows. */
	struct FGunDraw { int32 Barrel = -1, Carriage = -1, Quoin = -1, Trucks[4] = { -1, -1, -1, -1 }, Bed = -1, Slide = -1, Lid = -1, Covers[2] = { -1, -1 }; int32 GearPose = -1, CoversShown = -1; double LastX = 1e9, LastElev = 1e9, LastLid = 1e9, LastTurn = 1e9; };
	TArray<FGunDraw> Draw;
	TArray<int32> SmokeOrder;
	int32 SmokePool = 0, FlashPool = 0;
	double WaterZ0 = 0.0;          // the water actor's height (cm): the smoke's z datum
	double TuneCheckT = 0.0;
	double SunCheckT = -1.0;
	FVector SunToward = FVector::UpVector;
	FDateTime TuneStamp;
	double NextBroadside = -1.0, BroadsideEvery = 0.0;
	Sailing::ECannonSide BenchSide = Sailing::ECannonSide::Starboard;
	Sailing::ECannonFireMode BenchMode = Sailing::ECannonFireMode::Broadside;
	bool bStage = false;
	FVector StageOffsetCm = FVector::ZeroVector;   // ahead, to starboard of the player's boat
	double StageHeadingDeg = 0.0;
	bool bNoSmoke = false, bNoLights = false, bDebug = false;
	bool bBuilt = false;
	double LastNow = -1.0;
	FVector LastShipWorld = FVector::ZeroVector;
	bool bHaveLastShip = false;
};
