#pragma once

#include "CoreMinimal.h"
#include "BoatModel.h"
#include "LakeTerrain.h"

/** Learning-mode drills for the ASA 101 practical skills, in the order a lesson usually runs. */
enum class ESailingDrill : uint8
{
	None,
	LeaveTheDock,
	SailATriangle,
	HeaveTo,
	CrewOverboardFigureEight,
	CrewOverboardQuickStop,
	ReturnAndDock,
	Count
};

SAILINGSIM_API const TCHAR* DrillName(ESailingDrill Drill);

/** What a drill needs to know each step, beyond the boat itself. */
struct FDrillContext
{
	bool bTiedUp = false;
	bool bBackJib = false;
	double MaxContactSpeed = 0.0; // knots at the hardest touch on a dock this drill
};

/**
 * Runs one drill: sets up marks or a crew-overboard dummy, follows the boat and the crew's actions, and decides
 * when the drill is done. Pure logic over the physics state, so tests can drive it headless.
 */
class SAILINGSIM_API FDrillRunner
{
public:
	/** Starts a drill for a boat at its current position, with the true wind coming from WindFromRad. */
	void Start(ESailingDrill InDrill, const Sailing::FBoatModel& Boat, double WindFromRad);
	void Stop() { Drill = ESailingDrill::None; }

	/** Call every physics step (or frame). Returns true while the drill is running. */
	bool Update(const Sailing::FBoatModel& Boat, const FDrillContext& Context, double Dt);

	ESailingDrill GetDrill() const { return Drill; }
	bool IsComplete() const { return bComplete; }
	bool IsActive() const { return Drill != ESailingDrill::None && !bComplete; }
	double GetElapsed() const { return Elapsed; }

	/** Steps in ASA wording, with the current one marked by GetStep. */
	const TArray<FString>& GetSteps() const { return Steps; }
	int32 GetStep() const { return Step; }
	FString GetStatus() const { return Status; }

	/** Marks to sail around (world XY, meters) and the next one to round. */
	const TArray<FVector2D>& GetMarks() const { return Marks; }
	int32 GetNextMark() const { return NextMark; }
	/** The crew-overboard dummy, if this drill has one. */
	bool HasDummy() const { return bDummy; }
	FVector2D GetDummy() const { return Dummy; }

private:
	ESailingDrill Drill = ESailingDrill::None;
	TArray<FString> Steps;
	int32 Step = 0;
	FString Status;
	bool bComplete = false;
	double Elapsed = 0.0;
	double Hold = 0.0;
	FVector2D Start2D = FVector2D::ZeroVector;
	TArray<FVector2D> Marks;
	int32 NextMark = 0;
	bool bDummy = false;
	FVector2D Dummy = FVector2D::ZeroVector;
	FVector2D DummyDrift = FVector2D::ZeroVector;
	double MaxDistance = 0.0;
	int32 TacksOrGybes = 0;
	int32 LastSide = 0;
};

/**
 * A berth to tie up at: alongside a dock face (Top <= 1.5 m obstacles) within MaxRange of Near, with enough water under
 * the whole hull and no other dock or the shore in the way. Picks the one nearest Near, bow as close to the wind as
 * the face allows. Returns false if there is none.
 */
SAILINGSIM_API bool FindBerth(const Sailing::FLakeTerrain& Terrain, const std::vector<Sailing::FObstacleSegment>& Obstacles, FVector2D Near,
	double MaxRange, double WindFromRad, FVector2D& OutPosition, double& OutHeading);

/**
 * Dock lines: from the boat's cleats (bow, quarters, springs) to the nearest dock edge within reach.
 * Returns the lines (empty if fewer than two cleats can reach a dock).
 */
SAILINGSIM_API std::vector<Sailing::FMooringLine> FindDockLines(const Sailing::FBoatModel& Boat, const std::vector<Sailing::FObstacleSegment>& Obstacles, double Reach = 3.5);
