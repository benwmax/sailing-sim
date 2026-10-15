// Perf 1 fix 2: the player's fixed 120 Hz physics as a task off the game thread.
//
// The pawn's tick (TG_PrePhysics) reads the controls, decides this frame's step count and launches the steps as a task;
// the rest of the world's TG_PrePhysics ticks (terrain, bridges, lights, the AI boats' visuals) run meanwhile. The pawn's
// second tick function (FBoatPhysicsJoinTick, TG_PostPhysics) joins it and runs the rest of the old tick (transform,
// rig, sails, crew, sound, drills). Whoever reads or writes the player's boat in between ticks after the join
// (OrderReaders). Wind and waves are the game mode's, advanced in its tick, which runs before the pawn's.
//
// The steps are the same code on the same inputs in the same order, so the result is identical to the synchronous loop
// (SailingSim.Physics.TaskStep). -SailingSyncPhysics or sailing.AsyncPhysics 0 runs them inline.
#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "Tasks/Task.h"
#include "BoatModel.h"
#include "AutoTrim.h"
#include "BoatPhysicsTask.generated.h"

class ASailboatPawn;

/** One frame's fixed steps exactly as the pawn's tick ran them: the trim assist (or the simple layout's crew) trims,
 *  the helm's tiller and wing-on-wing stay, then the boat steps. */
struct SAILINGSIM_API FBoatStepJob
{
	Sailing::FBoatModel* Boat = nullptr;
	Sailing::FBoatControls* Controls = nullptr;
	Sailing::FAutoTrim* Trim = nullptr;
	const Sailing::FWindField* Wind = nullptr;
	const Sailing::FWaveField* Waves = nullptr;
	int32 Steps = 0;
	double StepDt = 1.0 / 120.0;
	bool bTrimAssist = false;          // the setting
	double LastManualTrimTime = 0.0;   // the assist trims once the boat's time is TrimIdleSeconds past the last manual trim
	double TrimIdleSeconds = 1e300;
	bool bSimple = false;              // the simple layout: the crew handles traveler and sail shape
	void Run() const;
};

/** Runs a step job on a task (UE::Tasks) or inline; Wait joins it. */
class SAILINGSIM_API FBoatPhysicsTask
{
public:
	~FBoatPhysicsTask() { Wait(); }
	/** Launches the job; returns true if it runs on a task (the pawn then finishes its tick in the join tick). */
	bool Start(ASailboatPawn* Pawn, FTickFunction& Join, const FBoatStepJob& Job);
	void Wait();
	bool IsPending() const { return bPending; }
	/** Whether the last Start launched a task (for the tests). */
	bool RanAsync() const { return bRanAsync; }
	static bool AsyncEnabled();

	/** Registers (or unregisters) the pawn's join tick with its level, after the pawn's own tick. */
	static void RegisterJoin(ASailboatPawn* Pawn, struct FBoatPhysicsJoinTick& Join, bool bRegister);

private:
	/** Everyone who touches the player's boat during the frame ticks after the join; the AI boats after the traffic.
	 *  Once a second; true if it added a prerequisite. */
	bool OrderReaders(ASailboatPawn* Pawn, FTickFunction& Join);

	UE::Tasks::FTask Task;
	bool bPending = false;
	bool bRanAsync = false;
	double LastOrdered = -1e30;
};

/** The pawn's second tick (TG_PostPhysics): joins the physics task and runs the rest of the pawn's tick. */
USTRUCT()
struct FBoatPhysicsJoinTick : public FTickFunction
{
	GENERATED_BODY()

	ASailboatPawn* Pawn = nullptr;

	virtual void ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread, const FGraphEventRef& MyCompletionGraphEvent) override;
	virtual FString DiagnosticMessage() override { return TEXT("FBoatPhysicsJoinTick"); }
	virtual FName DiagnosticContext(bool bDetailed) override { return TEXT("SailboatPhysicsJoin"); }
};

template<>
struct TStructOpsTypeTraits<FBoatPhysicsJoinTick> : public TStructOpsTypeTraitsBase2<FBoatPhysicsJoinTick>
{
	enum { WithCopy = false };
};
