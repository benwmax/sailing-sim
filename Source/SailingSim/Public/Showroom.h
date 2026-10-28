#pragma once

#include "CoreMinimal.h"
#include "SailSession.h"

class ASailboatPawn;
class ASailingGameMode;
enum class ESailScreen : uint8;

/**
 * The boat showroom and the live conditions preview behind the menus (docs/showroom-wiring/, Inputs/ui-showroom/brief.md
 * Mac PR 1): the wiring the Boat and Conditions screens sit on. Local presentation only: the session that Cast off
 * starts replaces all of it.
 */
enum class EShowroomStage : uint8
{
	None,     // the chase camera, the boat held still (the title and the other screens)
	Boat,     // the showroom: the free camera orbiting the boat, the boat afloat and sailing on her spot
	Weather,  // the conditions preview: wider and higher, the boat to the right of the panel
};

namespace SailShowroom
{
	/** The stage a screen shows (in game only Change conditions has one). */
	SAILINGSIM_API EShowroomStage StageFor(ESailScreen Screen, bool bInGame);
	/** Whether two sets of conditions would look the same (every field the weather reads). */
	SAILINGSIM_API bool SameConditions(const FSailConditions& A, const FSailConditions& B);
	/**
	 * A showroom spot near a point: the nearest place (rings of 25 m out to 1.5 km) with at least MinDepthM of water and no
	 * ground above the water within ClearM, so the background is open water and the boat never touches. Height(x, y) is
	 * the ground's height above the water (m). The point itself when it already qualifies, or when nothing does.
	 */
	SAILINGSIM_API FVector2D FindOpenWater(TFunctionRef<double(double, double)> Height, double X, double Y, double MinDepthM = 3.0, double ClearM = 60.0);
}

/** A value that fires once it has stood unchanged for a delay (sliders and the strip: don't load every boat flicked past). */
struct FSailDebounce
{
	double DelaySeconds = 0.2;
	/** Marks a change at Now. */
	void Changed(double Now) { ChangedAt = Now; bPending = true; }
	/** True once, DelaySeconds after the last change. */
	bool Fire(double Now)
	{
		if (!bPending || Now - ChangedAt < DelaySeconds) return false;
		bPending = false;
		return true;
	}
	bool IsPending() const { return bPending; }
	void Cancel() { bPending = false; }
private:
	double ChangedAt = 0.0;
	bool bPending = false;
};

/**
 * Drives the showroom from the front end: each frame it is told the screen, the boat to show and the pending conditions,
 * and puts the pawn on the right stage, swaps the boat in place (debounced 200 ms, loaded asynchronously) and previews
 * the conditions (debounced 200 ms; right away on entering the screen). Leaving Change conditions in game without
 * Apply restores the conditions it opened with; in game the world runs while that screen is open.
 */
class SAILINGSIM_API FSailShowroom
{
public:
	void Update(ASailboatPawn* Pawn, ASailingGameMode* GameMode, ESailScreen Screen, bool bInGame, int32 BoatToShow, const FSailConditions& Pending, double Now);
	/** The menus closed: back to the chase camera; an unapplied in-game preview is put back. */
	void End(ASailboatPawn* Pawn, ASailingGameMode* GameMode);
	EShowroomStage GetStage() const { return Stage; }

private:
	EShowroomStage Stage = EShowroomStage::None;
	bool bStageInGame = false;
	bool bUnpaused = false;
	int32 WantBoat = -1;
	FSailDebounce BoatDebounce, ConditionsDebounce;
	FSailConditions Previewed;
	bool bHavePreviewed = false;
	void SetStage(ASailboatPawn* Pawn, ASailingGameMode* GameMode, EShowroomStage NewStage, bool bInGame);
};
