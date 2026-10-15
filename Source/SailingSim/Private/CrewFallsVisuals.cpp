// Crew C5: the crew's falls on the player's boat (CrewFalls.h): Physics Control drives each MetaHuman body toward its
// animated pose; FCrewFalls decides how hard, and when the animation alone poses them again.
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "CrewFalls.h"
#include "SailingSettings.h"
#include "SailingGameMode.h"
#include "Waves.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsControlComponent.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "Engine/World.h"

namespace CrewFallsTuning
{
	// The controls at full strength (acceleration drive: independent of each body's mass). Parent space holds the pose
	// (each joint toward its animated angle); world space holds the sailor to the boat (relative to the deck box), weakly:
	// at full strength they are where the animation puts them, and in a fall the parent-space controls keep them looking
	// like people bracing while the world ones let them slide and swing.
	constexpr float ParentAngular = 40.f, ParentLinear = 0.f;
	constexpr float WorldAngular = 6.f, WorldLinear = 10.f;
	constexpr float DampingRatio = 1.0f;
	// Bodies in the water: a person floats with about 5% of the volume out, more with a life jacket (it is on the chest).
	constexpr float WaterLift = 1.12f;     // of g at full immersion
	constexpr float WaterDrag = 2.5f;      // 1/s on the body's velocity in the water
	constexpr float ImmersionCm = 20.f;    // the depth over which a body goes from dry to fully in
	constexpr float MaxDepenetration = 40.f; // cm/s: a body that starts inside the deck box is eased out, not thrown
}

void ASailboatPawn::SetupCrewFalls()
{
	if (CrewControl) { CrewControl->DestroyComponent(); CrewControl = nullptr; }
	if (CrewDeck) { CrewDeck->DestroyComponent(); CrewDeck = nullptr; }
	CrewFalls = FCrewFalls();
	bKnockdownDone = false;
	FString Knock;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingKnockdownAt="), Knock, false))
	{
		// -SailingKnockdownAt=<s>[,<deg>]: at that sim time the boat is laid over (the stills' and tests' capsize).
		FString At, Rate;
		if (!Knock.Split(TEXT(","), &At, &Rate)) At = Knock;
		KnockdownAt = FCString::Atod(*At);
		KnockdownRate = Rate.IsEmpty() ? 80.f : FCString::Atof(*Rate);
	}
	// Ultra by default (the PC first); -SailingCrewFalls=0|1 overrides. Only the MetaHumans have physics assets.
	int32 Arg = -1;
	FParse::Value(FCommandLine::Get(), TEXT("SailingCrewFalls="), Arg);
	bCrewFalls = (Arg >= 0 ? Arg != 0 : USailingSettings::Get()->Quality == ESailingQuality::Ultra) && !bTrafficBoat && HasMetaHumanCrew();
	if (!bCrewFalls) return;

	using namespace CrewFallsTuning;
	const Sailing::FBoatConfig& Cfg = Boat.GetConfig();
	const double DeckZ = Cfg.Hulls.empty() ? 0.6 : Cfg.Hulls[0].SheerZ;
	// Something to land on: a box the size of the deck a little under the sheer (the side decks and seats), moved with the
	// boat as a kinematic body. It is also the frame the world-space controls hold the crew in.
	CrewDeck = NewObject<UBoxComponent>(this, TEXT("CrewDeck"));
	CrewDeck->SetupAttachment(BoatRoot);
	CrewDeck->SetBoxExtent(FVector(Cfg.LengthOverall * 0.42 * Sailing::CmPerMeter, Cfg.Beam * 0.42 * Sailing::CmPerMeter, 4.0));
	CrewDeck->SetRelativeLocation(FVector(0.0, 0.0, (DeckZ - 0.15) * Sailing::CmPerMeter));
	CrewDeck->SetCollisionObjectType(ECC_PhysicsBody);
	CrewDeck->SetCollisionResponseToAllChannels(ECR_Ignore);
	CrewDeck->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
	CrewDeck->SetCollisionEnabled(ECollisionEnabled::PhysicsOnly);
	CrewDeck->SetHiddenInGame(true);
	CrewDeck->RegisterComponent();

	CrewControl = NewObject<UPhysicsControlComponent>(this, TEXT("CrewControl"));
	CrewControl->SetupAttachment(BoatRoot);
	CrewControl->RegisterComponent();

	// The MetaHuman body's limbs, leaves first and the spine (with the pelvis) last.
	auto Limb = [](const TCHAR* Name, const TCHAR* Start, bool bParent)
	{
		FPhysicsControlLimbSetupData D;
		D.LimbName = Name;
		D.StartBone = Start;
		D.bIncludeParentBone = bParent;
		D.bCreateWorldSpaceControls = true;
		D.bCreateParentSpaceControls = true;
		D.bCreateBodyModifiers = true;
		return D;
	};
	const TArray<FPhysicsControlLimbSetupData> Limbs = {
		Limb(TEXT("ArmLeft"), TEXT("clavicle_l"), false), Limb(TEXT("ArmRight"), TEXT("clavicle_r"), false),
		Limb(TEXT("LegLeft"), TEXT("thigh_l"), false), Limb(TEXT("LegRight"), TEXT("thigh_r"), false),
		Limb(TEXT("Head"), TEXT("neck_01"), false), Limb(TEXT("Spine"), TEXT("spine_01"), true) };
	FPhysicsControlData World;
	World.bEnabled = true;
	World.LinearStrength = WorldLinear;
	World.AngularStrength = WorldAngular;
	World.LinearDampingRatio = World.AngularDampingRatio = DampingRatio;
	World.bUseSkeletalAnimation = true;
	World.bUseAccelerationDriveMode = true;
	FPhysicsControlData Parent = World;
	Parent.LinearStrength = ParentLinear;
	Parent.AngularStrength = ParentAngular;
	FPhysicsControlModifierData Modifier;
	Modifier.MovementType = EPhysicsMovementType::Kinematic;
	Modifier.CollisionType = ECollisionEnabled::PhysicsOnly;

	for (USkeletalMeshComponent* Body : Crew)
	{
		if (!Body || !Body->GetPhysicsAsset()) continue;
		// The crew collide with the deck box and each other only (and never block a camera or a trace).
		Body->SetCollisionObjectType(ECC_PhysicsBody);
		Body->SetCollisionResponseToAllChannels(ECR_Ignore);
		Body->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
		Body->SetCollisionEnabled(ECollisionEnabled::PhysicsOnly);
		FPhysicsControlNames AllWorld, AllParent, AllModifiers;
		TMap<FName, FPhysicsControlNames> LimbWorld, LimbParent, LimbModifiers;
		CrewControl->CreateControlsAndBodyModifiersFromLimbBones(AllWorld, LimbWorld, AllParent, LimbParent, AllModifiers, LimbModifiers,
			Body, Limbs, World, Parent, Modifier, CrewDeck, NAME_None);
		for (FBodyInstance* BI : Body->Bodies)
		{
			if (BI) BI->SetMaxDepenetrationVelocity(MaxDepenetration);
		}
	}
	CrewControl->SetControlsInSetEnabled(TEXT("All"), false);
	// Nothing of this costs anything until a fall: the crew's bodies have no collision and the controls don't tick.
	SetCrewPhysicsActive(false);
	UE_LOG(LogTemp, Display, TEXT("Crew falls: on (%d crew, deck box at %.2f m)"), Crew.Num(), DeckZ - 0.15);
}

void ASailboatPawn::SetCrewPhysicsActive(bool bActive)
{
	// Posed, the crew's bodies have no collision (so the physics scene doesn't move dozens of kinematic bodies with them every
	// frame) and the controls don't tick: measured at 1.6 ms of game thread on Ultra otherwise.
	for (USkeletalMeshComponent* Body : Crew)
	{
		if (Body && Body->GetPhysicsAsset()) Body->SetCollisionEnabled(bActive ? ECollisionEnabled::PhysicsOnly : ECollisionEnabled::NoCollision);
	}
	if (CrewDeck) CrewDeck->SetCollisionEnabled(bActive ? ECollisionEnabled::PhysicsOnly : ECollisionEnabled::NoCollision);
	if (CrewControl)
	{
		CrewControl->SetComponentTickEnabled(bActive);
		CrewControl->SetControlsInSetEnabled(TEXT("All"), bActive);
	}
}

void ASailboatPawn::UpdateCrewFalls(float DeltaSeconds)
{
	const Sailing::FBoatState& S = Boat.GetState();
	if (KnockdownAt >= 0.0 && !bKnockdownDone && !bTrafficBoat && S.Time >= KnockdownAt)
	{
		// Laid over by that many degrees about her fore-and-aft axis (a roll rate alone is damped out within a tenth of a second).
		Sailing::FBoatState& M = Boat.GetMutableState();
		M.Orientation = M.Orientation * Sailing::Quat::FromAxisAngle({ 1.0, 0.0, 0.0 }, FMath::DegreesToRadians(double(KnockdownRate)));
		bKnockdownDone = true;
		UE_LOG(LogTemp, Display, TEXT("Crew falls: knockdown at %.1f s (laid over %.0f deg)"), S.Time, KnockdownRate);
	}
	if (!bCrewFalls || !CrewControl) return;

	using namespace CrewFallsTuning;
	const Sailing::FBoatTelemetry& T = Boat.GetTelemetry();
	const float Tilt = float(FMath::RadiansToDegrees(S.Orientation.Tilt()));
	const float LateralG = float(FMath::Sqrt(T.AccelBody.X * T.AccelBody.X + T.AccelBody.Y * T.AccelBody.Y) / 9.81);
	const float VerticalG = float(T.AccelBody.Z / 9.81);
	CrewFalls.Update(DeltaSeconds, Tilt, LateralG, VerticalG, T.bCapsized);

	if (CrewFalls.JustFell())
	{
		SetCrewPhysicsActive(true);
		CrewControl->SetBodyModifiersInSetMovementType(TEXT("All"), EPhysicsMovementType::Simulated);
		UE_LOG(LogTemp, Display, TEXT("Crew falls: thrown at %.1f s (heel %.0f deg, %.2f g across, %.2f g up)"), S.Time, Tilt, LateralG, VerticalG);
	}
	if (CrewFalls.JustRecovered())
	{
		CrewControl->ResetBodyModifiersInSetToCachedBoneTransforms(TEXT("All"));
		CrewControl->SetBodyModifiersInSetMovementType(TEXT("All"), EPhysicsMovementType::Kinematic);
		CrewControl->SetControlsInSetEnabled(TEXT("All"), false);
		SetCrewPhysicsActive(false);
		UE_LOG(LogTemp, Display, TEXT("Crew falls: back on their feet at %.1f s"), S.Time);
		return;
	}
	if (!CrewFalls.IsSimulated()) return;

	FPhysicsControlMultiplier M;
	const float K = CrewFalls.Strength();
	M.LinearStrengthMultiplier = FVector(K);
	M.AngularStrengthMultiplier = K;
	CrewControl->SetControlMultipliersInSet(TEXT("All"), M, true);

	// The water holds up whoever is in it (the sea's own height under each body).
	const ASailingGameMode* Mode = GetWorld() ? Cast<ASailingGameMode>(GetWorld()->GetAuthGameMode()) : nullptr;
	const Sailing::FWaveField* Waves = Mode ? &Mode->GetWaves() : nullptr;
	for (USkeletalMeshComponent* Body : Crew)
	{
		if (!Body) continue;
		for (FBodyInstance* BI : Body->Bodies)
		{
			if (!BI || !BI->IsInstanceSimulatingPhysics()) continue;
			const FVector P = BI->GetCOMPosition();
			const double SeaCm = (Waves ? Waves->Height(P.X / Sailing::CmPerMeter, P.Y / Sailing::CmPerMeter, S.Time) * Sailing::CmPerMeter : 0.0) + WaterSurfaceZ;
			const float In = FMath::Clamp(float(SeaCm - P.Z) / ImmersionCm, 0.f, 1.f);
			if (In <= 0.f) continue;
			const FVector Lift(0.0, 0.0, 981.0 * WaterLift * In);
			BI->AddForce(Lift - BI->GetUnrealWorldVelocity() * (WaterDrag * In), true, true);
		}
	}
}
