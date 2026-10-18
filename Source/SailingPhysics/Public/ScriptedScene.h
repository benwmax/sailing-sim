#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * Prologue step 1 (docs/prologue/README.md): a scripted crew scene read from data (Content/Prologue/prologue.json).
	 * A scene is a list of steps; each waits for its trigger (the scene clock, a gust, the true wind angle, heel, boat
	 * speed, a distance sailed, or simply the step before), then the captain makes a call and the scene judges the
	 * crew's answer from the boat's telemetry and the controls they give. A missed call is repeated (with softer
	 * wording if the step has one) and after a few repeats the rest of the crew does it: the scene never fails, it only
	 * counts. Pure logic on the sim clock like FDrillRunner, so the tests play it headless and the game shows it.
	 */
	enum class ESceneTrigger : unsigned char
	{
		Previous,  // the step before succeeded (after AfterSeconds)
		Time,      // the scene clock reaches AtSeconds
		Gust,      // the true wind at the boat passes the scene's mean wind by OverMeanKn
		Twa,       // |TWA| inside [TwaMinDeg, TwaMaxDeg]
		Heel,      // |heel| above HeelAboveDeg
		Speed,     // boat speed above SpeedAboveKn
		PastMark,  // the boat has sailed Meters along BearingDeg (true, from north) from where the scene started
		Count
	};

	enum class ESceneExpect : unsigned char
	{
		None,      // narration: done after Seconds
		Sheet,     // a sheet ("main" or "jib") eased or trimmed By from where it was at the call, or past AtLeast / AtMost
		Tack,      // the bow through the wind: the true wind on the other side, |TWA| 30..100 (settled, not hung in irons)
		Gybe,      // the stern through the wind (the true wind changes sides with |TWA| over 100)
		Hold,      // a TWA band, a heel limit, a speed and / or a station held for HoldSeconds
		Station,   // the crew member has taken a station ("helm", "grinder", ...)
		Action,    // a named crew action has been done ("clip-on", "grind")
		Count
	};

	SAILINGPHYSICS_API const char* SceneTriggerName(ESceneTrigger T);
	SAILINGPHYSICS_API const char* SceneExpectName(ESceneExpect E);

	struct FSceneTrigger
	{
		ESceneTrigger Type = ESceneTrigger::Previous;
		double AtSeconds = 0.0;      // Time
		double AfterSeconds = 0.0;   // every trigger: at least this long after the step became current
		double OrAfterSeconds = -1.0; // every trigger but Time: fire anyway this long after (unset: wait as long as it takes)
		double OverMeanKn = 0.0;     // Gust
		double TwaMinDeg = 0.0, TwaMaxDeg = 180.0; // Twa
		double HeelAboveDeg = 0.0;   // Heel
		double SpeedAboveKn = 0.0;   // Speed
		double BearingDeg = 0.0, Meters = 0.0; // PastMark
	};

	struct FSceneExpectation
	{
		ESceneExpect Type = ESceneExpect::None;
		std::string Sheet;           // "main" or "jib"
		double By = 0.0;             // + eased, - trimmed, from the sheet at the first call (0: unused)
		double AtLeast = -1.0, AtMost = -1.0; // sheet's absolute value (unset < 0)
		double WithinSeconds = 10.0; // the call repeats when the crew have not answered within this
		double HoldSeconds = 0.0;    // Hold
		double TwaMinDeg = -1.0, TwaMaxDeg = -1.0; // Hold: |TWA| band (unset < 0)
		double MaxHeelDeg = -1.0;    // Hold
		double MinSpeedKn = -1.0;    // Hold
		std::string Station;         // Station, or Hold's station
		std::string Action;          // Action
		double Seconds = 0.0;        // None
	};

	struct FSceneCall
	{
		std::string Id;              // "captain.ease-jib": the voice line's id (a sound cue, if one exists)
		std::string Caption;         // what the captain shouts
		std::string Retry;           // the repeat's wording (empty: the caption again)
		std::string Ok;              // said on success (may be empty)
	};

	struct FSceneStep
	{
		std::string Id;
		FSceneTrigger Trigger;
		FSceneCall Call;
		FSceneExpectation Expect;
		double RetryAfterSeconds = 4.0; // quiet time after a missed window before the call repeats
		int CrewTakesOverAfter = 3;     // repeats before the crew does it for you (0: never)
		std::string Next;               // the next step's id; empty: the following step; "end": the scene ends
		bool bCheckpoint = false;       // a restart point
		bool bRestartPose = false;      // the boat's pose for a restart here (the game puts her there)
		double RestartTwaDeg = 0.0, RestartSpeedKn = 0.0;
		std::string Camera;             // a named view the renderer may use
	};

	/** Where the scene is meant to be sailed, and its stand-in until that boat and weather exist. */
	struct FSceneSetting
	{
		std::string Boat, World, Weather, Rain;
		double WindKn = 0.0, GustKn = 0.0, SeaHsM = 0.0;
		std::string StandInBoat;
		double StandInWindKn = 0.0, StandInGustKn = 0.0;
		std::string ThenCut, ThenTier; // where the scene hands over when it ends
	};

	/** What the crew gives the scene each step: the controls, the station held and the actions done this step. */
	struct FSceneInput
	{
		FBoatControls Controls;
		std::string Station;
		std::vector<std::string> Actions;
	};

	/** A finished (or abandoned) scene, for the save (string ids only). */
	struct FSceneResult
	{
		std::string SceneId;
		bool bComplete = false;
		int StepsPassed = 0;   // answered by the crew member
		int StepsAssisted = 0; // done by the rest of the crew after the repeats
		int Retries = 0;       // calls repeated
		int Restarts = 0;      // from a checkpoint
		double Seconds = 0.0;  // on the sim clock
	};

	class SAILINGPHYSICS_API FScriptedScene
	{
	public:
		/** Reads and checks a scene. On failure the scene is left empty and Error says why (first problem found). */
		bool LoadText(const std::string& Json, std::string* Error = nullptr);
		bool IsLoaded() const { return !Steps.empty(); }

		/** Starts at the first step. MeanWindKn is what the Gust triggers count from (the scene's sailing wind). */
		void Start(const FBoatModel& Boat, double MeanWindKn);
		void SetMeanWindKn(double Kn) { MeanWindKn = Kn; }
		/** Call every physics step (or frame) with the sim's Dt. */
		void Update(const FBoatModel& Boat, const FSceneInput& Input, double Dt);
		/** Back to the last checkpoint reached (the game puts the boat at that step's restart pose first). */
		void RestartFromCheckpoint();

		enum class EPhase : unsigned char { Idle, Waiting, Calling, Done };
		EPhase GetPhase() const { return Phase; }
		bool IsActive() const { return Phase == EPhase::Waiting || Phase == EPhase::Calling; }
		bool IsComplete() const { return Phase == EPhase::Done; }
		double GetElapsed() const { return Elapsed; }

		const std::string& GetId() const { return Id; }
		const std::string& GetTitle() const { return Title; }
		const FSceneSetting& GetSetting() const { return Setting; }
		const std::vector<FSceneStep>& GetSteps() const { return Steps; }
		const std::vector<std::string>& GetCameras() const { return Cameras; }
		int GetStepIndex() const { return Current; }
		const FSceneStep* GetStep() const { return Current >= 0 && Current < int(Steps.size()) ? &Steps[size_t(Current)] : nullptr; }

		/** The captain's line on screen now: the call (or its repeat) while calling, the "ok" for a moment after. */
		const std::string& GetCaption() const;
		/** The voice line to play: its id and a serial that grows with every call and repeat (play when it changes). */
		const std::string& GetCallId() const;
		int GetCallSerial() const { return CallSerial; }
		int GetCallRepeats() const { return Repeats; }
		/** The camera hint of the current step (empty: none). */
		const std::string& GetCamera() const;
		/** The last checkpoint reached (step id; empty before the first). */
		const std::string& GetCheckpoint() const { return CheckpointId; }
		const FSceneResult& GetResult() const { return Result; }

	private:
		bool Triggered(const FSceneStep& S, const FBoatModel& Boat) const;
		bool Answered(const FSceneStep& S, const FBoatModel& Boat, const FSceneInput& In, double Dt);
		void MakeCall(const FBoatModel& Boat, const FSceneInput& In);
		void Succeed(bool bAssisted);
		void Enter(int Index);

		std::string Id, Title;
		std::string AssistCaption;  // said when the rest of the crew answer a call for you
		FSceneSetting Setting;
		std::vector<std::string> Cameras, Stations, Actions;
		std::vector<FSceneStep> Steps;

		EPhase Phase = EPhase::Idle;
		int Current = -1;
		double Elapsed = 0.0;
		double MeanWindKn = 0.0;
		double StartX = 0.0, StartY = 0.0;
		double EnteredAt = 0.0;  // when the current step became current
		double FirstCallAt = 0.0; // when the step's call was first made
		double CallAt = 0.0;     // when the call (or its repeat) was last made
		double WindowEnd = 0.0;  // the crew have until here before the next repeat is scheduled
		double RepeatAt = -1.0;  // when the next repeat goes out (< 0: none scheduled)
		int Repeats = 0;
		int CallSerial = 0;
		double SheetAtCall = 0.0;
		int SideAtCall = 0;
		double HeldFor = 0.0;
		std::vector<std::string> ActionsDone; // since the step's first call
		std::string OkCaption;
		double OkUntil = -1.0;
		std::string CheckpointId;
		int CheckpointIndex = 0;
		FSceneResult Result;
	};
}
