#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "SailingMath.h"
#include "ScriptedScene.h"
#include "Wind.h"
#include "SailingGameMode.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// #402 (docs/first-launch/): the first job, a guided first sail in the J/22 on Ray Hubbard. Played headless: a player
// who answers every call gets through all six steps with none done for them, in a few minutes; one who answers
// nothing still reaches the end (the instructor does each step after the repeats), so the job never fails.
namespace FirstLaunchTestsLocal
{
	constexpr EAutomationTestFlags FirstLaunchFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	struct FJobRun
	{
		FSceneResult Result;
		TArray<FString> Calls;
		double MaxSpeedAtStopKn = 0.0;
	};

	/**
	 * The J/22 on a beam reach in the scene's wind, the crew on the jib (FAutoTrim), the player on the tiller (FAutopilot,
	 * aimed where each call asks) and the mainsheet (the crew helper's trim plus the player's own ease). bAnswers false:
	 * the player holds the reach and touches nothing.
	 */
	FJobRun Play(FScriptedScene& Scene, bool bAnswers, double MaxSeconds = 600.0)
	{
		FJobRun Out;
		const FSceneSetting& Set = Scene.GetSetting();
		FWindParams P;
		P.SpeedKnots = Set.WindKn;
		P.FromDegrees = 0.0;
		const FWindField Wind(P);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -90.0 * kDegToRad, 5.0 * kKnot); // TWA 90 from starboard
		FAutoTrim Crew;
		FAutopilot Helm;
		Helm.TargetTWADeg = 90.0;
		FBoatControls C;
		C.MainSheet = C.JibSheet = 0.4;
		// Settle on the reach before the scene starts (the game starts her sailing, trimmed).
		for (int32 I = 0; I < int32(20.0 * PhysicsHz); ++I)
		{
			C = Crew.Update(Boat, C, PhysicsDt);
			C.Tiller = Helm.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
		}
		Scene.Start(Boat, Set.WindKn);
		int32 LastSerial = 0;
		double MainOffset = 0.0, Side = 1.0;
		bool bTacked = false;
		for (int32 I = 0; I < int32(MaxSeconds * PhysicsHz) && !Scene.IsComplete(); ++I)
		{
			if (Scene.GetCallSerial() != LastSerial)
			{
				LastSerial = Scene.GetCallSerial();
				Out.Calls.Add(UTF8_TO_TCHAR(Scene.GetCallId().c_str()));
			}
			const FSceneStep* S = Scene.GetStep();
			const std::string Id = S ? S->Id : std::string();
			const bool bCalling = Scene.GetPhase() == FScriptedScene::EPhase::Calling;
			FBoatControls Trimmed = Crew.Update(Boat, C, PhysicsDt);
			if (bAnswers && bCalling)
			{
				if (Id == "steer") Helm.TargetTWADeg = 90.0 * Side;
				else if (Id == "ease-main") MainOffset = 0.25;
				else if (Id == "trim-main") MainOffset = 0.0;
				else if (Id == "upwind") Helm.TargetTWADeg = 45.0 * Side;
				else if (Id == "tack" && !bTacked)
				{
					bTacked = true;
					Side = -Side;
					Helm.TargetTWADeg = 45.0 * Side;
					Helm.MaxTiller = 0.8;
					Helm.bKeepShortOfStall = false;
				}
				else if (Id == "stop") Helm.TargetTWADeg = 0.0;
			}
			if (Id != "tack") { Helm.MaxTiller = 0.6; Helm.bKeepShortOfStall = true; }
			const bool bStopping = bAnswers && Id == "stop";
			C.JibSheet = bStopping ? 1.0 : Trimmed.JibSheet;
			C.MainSheet = bStopping ? 1.0 : FMath::Clamp(Trimmed.MainSheet + MainOffset, 0.0, 1.0);
			C.Tiller = Helm.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
			FSceneInput In;
			In.Controls = C;
			Scene.Update(Boat, In, PhysicsDt);
			if (Id == "stop") Out.MaxSpeedAtStopKn = FMath::Max(Out.MaxSpeedAtStopKn, Boat.GetState().Velocity.Length() / kKnot);
		}
		Out.Result = Scene.GetResult();
		return Out;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFirstSailTest, "SailingSim.Scene.FirstSail", FirstLaunchTestsLocal::FirstLaunchFlags)
bool FSailingFirstSailTest::RunTest(const FString&)
{
	using namespace FirstLaunchTestsLocal;
	FScriptedScene Scene;
	FString Error;
	if (!ASailingGameMode::LoadFirstJob(Scene, &Error)) { AddError(Error); return false; }
	TestEqual(TEXT("Six steps"), int32(Scene.GetSteps().size()), 6);
	TestEqual(TEXT("Id"), FString(UTF8_TO_TCHAR(Scene.GetId().c_str())), FString(TEXT("first-job")));
	TestEqual(TEXT("The J/22"), FString(UTF8_TO_TCHAR(Scene.GetSetting().Boat.c_str())), FString(TEXT("J22")));
	TestEqual(TEXT("Hands over to Day Sailor"), FString(UTF8_TO_TCHAR(Scene.GetSetting().ThenTier.c_str())), FString(TEXT("day-sailor")));
	TArray<FString> Expected;
	for (const FSceneStep& S : Scene.GetSteps())
	{
		Expected.Add(UTF8_TO_TCHAR(S.Call.Id.c_str()));
		TestTrue(*FString::Printf(TEXT("%hs: the instructor speaks"), S.Id.c_str()), S.Call.Id.rfind("instructor.", 0) == 0);
	}

	const FJobRun Good = Play(Scene, true);
	AddInfo(FString::Printf(TEXT("First job, every call answered: %d answered, %d by the instructor, %d repeats, %.0f s; calls %s"),
		Good.Result.StepsPassed, Good.Result.StepsAssisted, Good.Result.Retries, Good.Result.Seconds, *FString::Join(Good.Calls, TEXT(", "))));
	TestTrue(TEXT("The job finishes"), Good.Result.bComplete);
	TestEqual(TEXT("Every step answered by the player"), Good.Result.StepsPassed, 6);
	TestEqual(TEXT("... none done for them"), Good.Result.StepsAssisted, 0);
	TestTrue(TEXT("Over a minute and under ten (a scripted helmsman is quicker than a first-timer)"), Good.Result.Seconds > 60.0 && Good.Result.Seconds < 600.0);

	FScriptedScene Again;
	ASailingGameMode::LoadFirstJob(Again, &Error);
	const FJobRun Silent = Play(Again, false);
	AddInfo(FString::Printf(TEXT("First job, nothing answered: %d answered, %d by the instructor, %d repeats, %.0f s"),
		Silent.Result.StepsPassed, Silent.Result.StepsAssisted, Silent.Result.Retries, Silent.Result.Seconds));
	TestTrue(TEXT("A player who answers nothing still reaches the end (no fail)"), Silent.Result.bComplete);
	TestTrue(TEXT("... with the instructor doing the steps"), Silent.Result.StepsAssisted >= 4);
	return true;
}

#endif
