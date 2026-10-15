#pragma once

#include "CoreMinimal.h"

/**
 * Crew C5: falls. When the boat is knocked hard (a collision, grounding, a broach) or heels past where anyone can hold
 * on, the crew stop being posed and go to an active ragdoll (the Physics Control plugin: every body simulated, driven
 * toward the animated pose by controls whose strength this sets); when the boat is steady again they gather themselves
 * (the controls strengthen) and the animation takes them back.
 *
 * Pure logic, one per boat (the crew fall together), so the tests can drive it. The pawn does the physics
 * (CrewFallsVisuals.cpp). Inputs are the boat's own: heel past upright (Quat::Tilt, deg), the lateral and vertical
 * acceleration the crew feel (g, the 25 ms mean FBoatTelemetry::AccelBody), whether she is capsized.
 */
enum class ECrewFallPhase : uint8
{
	Posed,      // the animation poses the crew (no physics)
	Falling,    // ragdoll, the controls weak: thrown, sliding, hanging on
	Gathering,  // the boat is steady: the controls strengthen toward the pose
};

struct SAILINGSIM_API FCrewFallParams
{
	float KnockG = 1.0f;          // a lateral (or vertical, past 1 g of its own) acceleration that throws the crew
	float FallTiltDeg = 55.f;     // heel past which nobody stays put
	float SteadyTiltDeg = 30.f;   // heel under which the crew can gather themselves again
	float SteadyG = 0.35f;        // and the acceleration under which
	float SteadySeconds = 1.0f;   // for this long
	float GatherSeconds = 1.0f;   // the controls' climb back to full
	float HoldSeconds = 0.3f;     // at full strength before the animation takes over
	float KnockStrength = 0.35f;  // the controls during a fall from a knock (some grip: braced, staggering)
	float CapsizeStrength = 0.12f;// from a knockdown or capsize (hanging on, mostly limp)
	float MinFallSeconds = 0.8f;  // a fall lasts at least this long
};

class SAILINGSIM_API FCrewFalls
{
public:
	explicit FCrewFalls(const FCrewFallParams& InParams = FCrewFallParams()) : P(InParams) {}

	/** One game frame. LateralG: the felt acceleration across the deck plane (g); VerticalG: along the mast less 1 g. */
	void Update(float Dt, float TiltDeg, float LateralG, float VerticalG, bool bCapsized);

	ECrewFallPhase Phase() const { return Current; }
	bool IsSimulated() const { return Current != ECrewFallPhase::Posed; }
	/** The controls' strength, 0..1 of full: what the pawn hands Physics Control as a multiplier. */
	float Strength() const { return ControlStrength; }
	/** Set on the frame a fall starts, and on the frame the animation takes back over. */
	bool JustFell() const { return bJustFell; }
	bool JustRecovered() const { return bJustRecovered; }
	int32 FallCount() const { return Falls; }

private:
	FCrewFallParams P;
	ECrewFallPhase Current = ECrewFallPhase::Posed;
	float ControlStrength = 1.f;
	float FallFloor = 0.f;     // the weakest the controls have been in this fall
	float SinceFall = 0.f, Steady = 0.f, Gathered = 0.f;
	bool bJustFell = false, bJustRecovered = false;
	int32 Falls = 0;
};
