#pragma once

#include "CoreMinimal.h"

/**
 * docs/cockpit-tack/: the cockpit view's eye through a tack or gybe. The view is the helm's own eyes; their head drops
 * half a metre to pass under the boom and bobs with every step of a crossing (FCrewCrossing), and the trimmer crosses
 * just ahead of it. A person's eyes stay steady while the body moves, so the eye follows the helm's head through
 * critically damped springs (across and fore and aft fully, down only 40 % of the crouch and never into the boom), eases
 * aft from another sailor's head closer than 40 cm ahead of it, and leads the look a little into a turn. Plain logic,
 * in the boat's frame (cm), so the tests drive it without a world.
 */
struct SAILINGSIM_API FCockpitEyeInput
{
	FVector RawEye = FVector::ZeroVector;    // the helm's head bone plus the eyes' offset, as the view had it before
	bool bCrossing = false;                  // the helm's crossing is running (FCrewCrossing::bActive)
	TArray<FVector, TInlineAllocator<12>> Heads; // the other sailors' head bones
	bool bBoomOver = false;                  // the boom is over the eye
	bool bBoomNear = false;                  // ... or within a metre across of it (the eye starts down before it arrives)
	double BoomUnderZ = 0.0;                 // the boom's underside over the eye
	double MinX = -1e9, MaxX = 1e9;          // where the eye may go fore and aft (the cockpit well, the transom less 10 cm)
	double TurnRate = 0.0;                   // rad/s (+ bow to starboard)
	bool bPlayerLooking = false;             // the player turned the view in the last 2 s
};

struct SAILINGSIM_API FCockpitEye
{
	FVector Eye = FVector::ZeroVector, EyeV = FVector::ZeroVector;
	float Gap = 0.f;                         // cm eased aft from a head ahead
	float Lift = 0.f;                        // cm lifted where easing aft could not keep the gap
	float Lead = 0.f, LeadV = 0.f;           // deg of yaw into the turn
	float SeatedZ = 0.f;                     // the eye's height as the crossing began
	float CrossY = 0.f, CrossDir = 0.f;      // the furthest across so far, and which way
	float Settle = 0.f;                      // s since the crossing ended (the soft springs hand back to the stiff ones)
	bool bStarted = false;
	bool bWasCrossing = false;

	static constexpr float GapCm = 45.f;
	static constexpr float BoomClearCm = 15.f;
	static constexpr float DropShare = 0.4f;
	static constexpr float MaxLeadDeg = 15.f;

	/** Starts at the raw eye, at rest (the view switched on, a boat swap, a teleport). */
	void Reset(const FVector& Raw);
	/** One frame: the eye (boat frame, cm); OutLeadDeg the yaw to add to the look. */
	FVector Step(const FCockpitEyeInput& In, float Dt, float& OutLeadDeg);
};
