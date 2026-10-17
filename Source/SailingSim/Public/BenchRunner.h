#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "BenchRunner.generated.h"

/**
 * Bench-fast: the game's arguments as the code reads them now. A bench list (USailingBenchRunner) swaps the command line
 * between views; Generation() moves on each swap, so a value cached from the command line is read again, as a fresh
 * process would read it.
 */
namespace SailingArgs
{
	/** The command line the -Sailing switches read: the real one in development builds, empty in Shipping, so the bench,
	 *  capture, test and tuning switches (and -SailingExecAt's console commands) can't change a shipped game. Session
	 *  choices from the front end don't go through it. */
	SAILINGSIM_API const TCHAR* Dev();

	/** The release smoke's switches out of a command line: empty unless it has -SailingShippingSmoke, then only
	 *  -SailingUIScript, -SailingWorld, -SailingLaunch, -SailingShot and -SailingBench (at most 60 s) pass. Dev() returns this
	 *  in Shipping: it lets the release smoke load each world and take a screenshot, and nothing a player can't do. */
	SAILINGSIM_API FString ShippingSmokeArgs(const TCHAR* CommandLine);

	SAILINGSIM_API uint32 Generation();
	/** Replaces the command line (FCommandLine::Set) and moves the generation on. */
	SAILINGSIM_API void SetCommandLine(const FString& CommandLine);

	/** FParse::Param on the command line, read again after each swap. Declare it static where it is used. */
	struct SAILINGSIM_API FCachedFlag
	{
		explicit FCachedFlag(const TCHAR* InName) : Name(InName) {}
		bool Get();
	private:
		const TCHAR* Name;
		uint32 Gen = MAX_uint32;
		bool bValue = false;
	};

	/** A once-per-run latch (a one-off screenshot or dump): set again on each swap. */
	struct SAILINGSIM_API FOnce
	{
		/** True the first time it is asked in this generation. */
		bool Take();
		bool Taken() const;
	private:
		uint32 Gen = MAX_uint32;
	};
}

/** One view of a bench list: its name (the screenshot and the result file) and its own arguments. */
struct FSailingBenchView
{
	FString Name;
	FString Args;
};

/**
 * Bench-fast (docs/bench-fast): -SailingBenchList=<file in Saved/Bench> runs a list of views in one process. Each line is
 * `name|args`; the process's own command line (tier, window, -SailingBench=<s>, -SailingDemo) is the base every view
 * adds its arguments to. Between views the runner puts back everything a fresh process starts with (the settings' class
 * defaults, the front-end session, every console variable the last view changed, the command line itself) and reloads
 * the map; each view leaves Saved/Bench/<name>.bench.json (and bench.json, as a single run does).
 */
UCLASS()
class SAILINGSIM_API USailingBenchRunner : public UGameInstanceSubsystem
{
	GENERATED_BODY()
public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	/** The running list, if this process runs one. */
	static USailingBenchRunner* Get(const UObject* WorldContext);
	/** The game mode's measured result for the current view: saves it, then loads the next view or quits. */
	void ViewFinished(const FString& Json, UObject* WorldContext);
	int32 CurrentView() const { return Current; }
	int32 NumViews() const { return Views.Num(); }

	/** `name|args` lines; blank lines and lines starting with # are skipped. */
	static TArray<FSailingBenchView> ParseList(const FString& Text);
	/** The command line a view runs with: the base without the list and the base's shot, then -SailingShot and the view's. */
	static FString ViewCommandLine(const FString& Base, const FSailingBenchView& View);

	/** Every console variable's value now (read-only ones left out). */
	static TMap<FString, FString> SnapshotCVars();
	/**
	 * Puts back the console variables that differ from Snapshot, except those the next StartPlay sets again anyway (the
	 * tier's QualityCVars and the scalability groups' values): toggling ray tracing would recreate every render state.
	 * Returns how many it set.
	 */
	static int32 RestoreCVars(const TMap<FString, FString>& Snapshot, const TSet<FString>& Keep);
	/** The settings' class defaults and an empty front-end session: what a measuring process starts from. */
	static void ResetRunState(UGameInstance* GameInstance);

private:
	void StartView(int32 Index);

	TArray<FSailingBenchView> Views;
	FString BaseCommandLine;
	TMap<FString, FString> CVarsAtStart;
	int32 Current = -1;
	int32 PendingView = -1;
	double ViewStartSeconds = 0.0;
};
