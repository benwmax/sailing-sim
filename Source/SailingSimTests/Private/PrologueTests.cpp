#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "SailingMath.h"
#include "ScriptedScene.h"
#include "Wind.h"
#include "SailingGameMode.h"
#include "SailSave.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace PrologueTestsLocal
{
	constexpr EAutomationTestFlags PrologueFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	constexpr double StandInKnots = 25.0;

	enum class ECrew : uint8 { Good, IgnoresFirstEase, Silent };

	/** What a playthrough saw: the calls in order (ids), the captions shown, the camera hints, the result. */
	struct FPlaythrough
	{
		TArray<FString> Calls;
		TArray<FString> Captions;
		TArray<FString> Cameras;
		FSceneResult Result;
		int32 MaxRepeats = 0;
		double Seconds = 0.0;
	};

	/**
	 * The J/22 stand-in in 25 kn with a scripted crew answering the captain: FAutoTrim on the sheets and FAutopilot on
	 * the tiller, plus what each call asks (clip on, ease the jib a hand's length, a heavy-air tack, grind the new sheet,
	 * the helm downwind, dump the main, bring her up to a reach). Gusts come when a step waits for one: the wind steps
	 * to 35 kn for a few seconds, the way a squall line hits.
	 */
	FPlaythrough Play(FScriptedScene& Scene, ECrew Crew, double MaxSeconds = 900.0, const TFunction<void(double)>& Each = nullptr)
	{
		FPlaythrough Out;
		FWindParams P;
		P.SpeedKnots = StandInKnots;
		P.FromDegrees = 0.0;
		const FWindField Base(P);
		P.SpeedKnots = StandInKnots + 10.0;
		const FWindField Gust(P);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 6.0 * kKnot); // close-hauled on starboard (TWA = wind from - heading)
		FAutoTrim Trim;
		FAutopilot Pilot;
		FBoatControls C;
		int32 Side = 1;
		Pilot.TargetTWADeg = 45.0;
		Scene.Start(Boat, StandInKnots);
		int32 LastSerial = 0, LastStep = -1;
		double T = 0.0, CallT = 0.0, StepT = 0.0, JibHold = -1.0, MainHold = -1.0;
		bool bLetFly = false, bTacking = false;
		std::string Station;
		for (int32 I = 0; I < int32(MaxSeconds * PhysicsHz) && !Scene.IsComplete(); ++I, T += PhysicsDt)
		{
			if (Scene.GetStepIndex() != LastStep) { LastStep = Scene.GetStepIndex(); StepT = T; JibHold = MainHold = -1.0; bTacking = false; }
			const FSceneStep* S = Scene.GetStep();
			const std::string Id = S ? S->Id : std::string();
			const bool bCalling = Scene.GetPhase() == FScriptedScene::EPhase::Calling;
			const bool bGustTrigger = S && S->Trigger.Type == ESceneTrigger::Gust;
			const double Waited = T - StepT - (S ? S->Trigger.AfterSeconds : 0.0);
			const bool bGusting = bGustTrigger && ((!bCalling && Waited > 2.0 && Waited < 10.0) || bCalling);
			if (Scene.GetCallSerial() != LastSerial)
			{
				LastSerial = Scene.GetCallSerial();
				CallT = T;
				Out.Calls.Add(UTF8_TO_TCHAR(Scene.GetCallId().c_str()));
				Out.Captions.Add(UTF8_TO_TCHAR(Scene.GetCaption().c_str()));
				if (!Scene.GetCamera().empty()) Out.Cameras.AddUnique(UTF8_TO_TCHAR(Scene.GetCamera().c_str()));
				Out.MaxRepeats = FMath::Max(Out.MaxRepeats, Scene.GetCallRepeats());
			}
			FSceneInput In;
			const bool bAnswer = bCalling && T - CallT > 0.8 && Crew != ECrew::Silent && !(Crew == ECrew::IgnoresFirstEase && Id == "ease-jib" && Scene.GetCallRepeats() == 0);
			if (bAnswer)
			{
				if (Id == "clip-on") In.Actions.push_back("clip-on");
				else if (Id == "ease-jib" && JibHold < 0.0) JibHold = FMath::Min(1.0, C.JibSheet + 0.25);
				else if (Id == "ready-about" && !bTacking)
				{
					Side = -Side;
					bTacking = true;
					Pilot.TargetTWADeg = 45.0 * Side;
					Pilot.MaxTiller = 0.8;
					Pilot.bKeepShortOfStall = false;
				}
				else if (Id == "grind") { bLetFly = false; JibHold = 0.3; }
				else if (Id == "take-helm") { Station = "helm"; Pilot.TargetTWADeg = 150.0 * Side; }
				else if (Id == "dump-main") MainHold = 1.0;
				else if (Id == "the-break") Pilot.TargetTWADeg = 90.0 * Side;
			}
			if (Id == "grind" && T - StepT < 0.5 * PhysicsDt && Crew != ECrew::Silent) bLetFly = true; // tacked: the old sheet let go
			if (Id != "ready-about" && Id != "grind") { Pilot.MaxTiller = 0.6; Pilot.bKeepShortOfStall = true; }
			C = Trim.Update(Boat, C, PhysicsDt);
			if (bLetFly) C.JibSheet = 1.0;
			if (JibHold >= 0.0) C.JibSheet = JibHold;
			if (MainHold >= 0.0) C.MainSheet = MainHold;
			C.bBackJib = false;
			if (Id == "ready-about" && bTacking)
			{
				// A heavy-air tack (the J/22 will not tack on the helm alone in 25 kn): jib let fly and the main hard in to
				// head up, then the jib held aback and the main eased to push the bow down onto the new tack.
				const double Twa = Boat.GetTelemetry().TrueWindAngle * kRadToDeg;
				if (Twa * Side < 0.0) { C.JibSheet = 1.0; C.MainSheet = 0.0; }
				else if (FMath::Abs(Twa) < 35.0) { C.bBackJib = true; C.MainSheet = 1.0; }
			}
			C.Tiller = Pilot.Update(Boat);
			In.Controls = C;
			In.Station = Station;
			Boat.Step(PhysicsDt, C, bGusting ? Gust : Base);
			Scene.Update(Boat, In, PhysicsDt);
			if (Each) Each(T);
		}
		Out.Result = Scene.GetResult();
		Out.Seconds = T;
		return Out;
	}

	bool Load(FAutomationTestBase& Test, FScriptedScene& Scene)
	{
		FString Error;
		if (!ASailingGameMode::LoadPrologue(Scene, &Error))
		{
			Test.AddError(Error);
			return false;
		}
		return true;
	}
}

/** The whole prologue played headless by a crew that answers every call: seven steps, no repeats, saved by id. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPrologueSceneTest, "SailingSim.Prologue.Scene", PrologueTestsLocal::PrologueFlags)
bool FSailingPrologueSceneTest::RunTest(const FString&)
{
	using namespace PrologueTestsLocal;
	FScriptedScene Scene;
	if (!Load(*this, Scene)) return false;
	TestEqual(TEXT("Seven steps"), int32(Scene.GetSteps().size()), 7);
	TestEqual(TEXT("Id"), FString(UTF8_TO_TCHAR(Scene.GetId().c_str())), FString(TEXT("prologue")));
	TestEqual(TEXT("Stand-in: the J/22"), FString(UTF8_TO_TCHAR(Scene.GetSetting().StandInBoat.c_str())), FString(TEXT("J22")));
	const FPlaythrough P = Play(Scene, ECrew::Good);
	AddInfo(FString::Printf(TEXT("Prologue on the J/22 stand-in in %.0f kn: %d answered, %d by the crew, %d repeats, %.0f s; calls %s"), StandInKnots,
		P.Result.StepsPassed, P.Result.StepsAssisted, P.Result.Retries, P.Result.Seconds, *FString::Join(P.Calls, TEXT(", "))));
	TestTrue(TEXT("The scene finishes"), Scene.IsComplete() && P.Result.bComplete);
	TestEqual(TEXT("Every step answered by the crew member"), P.Result.StepsPassed, 7);
	TestEqual(TEXT("... none done for them"), P.Result.StepsAssisted, 0);
	TestEqual(TEXT("... and no call repeated"), P.Result.Retries, 0);
	TArray<FString> Expected;
	for (const FSceneStep& S : Scene.GetSteps()) Expected.Add(UTF8_TO_TCHAR(S.Call.Id.c_str()));
	TestEqual(TEXT("The calls in the scene's order"), P.Calls, Expected);
	TestTrue(TEXT("Every call had a caption"), !P.Captions.ContainsByPredicate([](const FString& C) { return C.IsEmpty(); }));
	TestTrue(TEXT("Camera hints came with the steps"), P.Cameras.Num() >= 5);
	TestTrue(TEXT("About the length the scene is written for (under 10 minutes of sim time)"), P.Result.Seconds > 30.0 && P.Result.Seconds < 600.0);
	TestTrue(TEXT("The last step's 'ok' is on screen as it ends"), !Scene.GetCaption().empty());

	// The save keeps the finished scene by id (rule 7), with no version change.
	FSailSave Save;
	Save.Progress.RecordScene(P.Result, FDateTime(2026, 10, 18, 20, 0, 0));
	FSceneResult Slower = P.Result;
	Slower.Seconds += 30.0;
	Slower.Retries = 2;
	Save.Progress.RecordScene(Slower, FDateTime(2026, 10, 19, 9, 0, 0));
	FSceneResult Unfinished = P.Result;
	Unfinished.bComplete = false;
	Save.Progress.RecordScene(Unfinished, FDateTime(2026, 10, 19, 10, 0, 0));
	const FString Text = Save.ToJson();
	FSailSave Back;
	TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Text, Back)), int32(FSailSave::EResult::Ok));
	const FSailSave::FSceneRecord* R = Back.Progress.FindScene(TEXT("prologue"));
	if (TestNotNull(TEXT("The prologue's record"), R))
	{
		TestTrue(TEXT("Done (skippable from now on)"), Back.Progress.IsSceneDone(TEXT("prologue")));
		TestEqual(TEXT("Two finished plays (the unfinished one does not count)"), R->Plays, 2);
		TestEqual(TEXT("Best time is the quicker"), R->BestSeconds, P.Result.Seconds);
		TestEqual(TEXT("The last finish's repeats"), R->Retries, 2);
		TestEqual(TEXT("First finished on the first day"), R->CompletedAt, FDateTime(2026, 10, 18, 20, 0, 0));
	}
	TestEqual(TEXT("Still version 1"), Back.Version, 1);
	TestTrue(TEXT("Named by its id"), Text.Contains(TEXT("\"scenes\"")) && Text.Contains(TEXT("\"prologue\"")));
	return true;
}

/**
 * Missed calls: a crew member who lets the first "ease the jib" go by hears it again in the softer wording and the scene
 * still finishes; a crew member who never answers anything gets every step done by the rest of the crew (no hard fail);
 * a restart goes back to the last checkpoint.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPrologueRepeatsTest, "SailingSim.Prologue.Repeats", PrologueTestsLocal::PrologueFlags)
bool FSailingPrologueRepeatsTest::RunTest(const FString&)
{
	using namespace PrologueTestsLocal;
	{
		FScriptedScene Scene;
		if (!Load(*this, Scene)) return false;
		const FPlaythrough P = Play(Scene, ECrew::IgnoresFirstEase);
		AddInfo(FString::Printf(TEXT("Ignored the first ease: %d answered, %d by the crew, %d repeats, %.0f s"), P.Result.StepsPassed, P.Result.StepsAssisted, P.Result.Retries, P.Result.Seconds));
		const FSceneStep* Ease = nullptr;
		for (const FSceneStep& S : Scene.GetSteps()) if (S.Id == "ease-jib") Ease = &S;
		if (!TestNotNull(TEXT("The ease-jib step"), Ease)) return false;
		const int32 EaseCalls = P.Calls.FilterByPredicate([](const FString& C) { return C == TEXT("captain.ease-jib"); }).Num();
		TestTrue(TEXT("The call was repeated"), EaseCalls >= 2 && P.Result.Retries >= 1);
		TestTrue(TEXT("... in the softer wording"), P.Captions.Contains(UTF8_TO_TCHAR(Ease->Call.Retry.c_str())));
		TestTrue(TEXT("The scene still finishes"), P.Result.bComplete);
		TestEqual(TEXT("... every step answered in the end"), P.Result.StepsPassed, 7);
	}
	{
		FScriptedScene Scene;
		if (!Load(*this, Scene)) return false;
		const FPlaythrough P = Play(Scene, ECrew::Silent);
		AddInfo(FString::Printf(TEXT("A silent crew member: %d answered, %d by the crew, %d repeats, %.0f s"), P.Result.StepsPassed, P.Result.StepsAssisted, P.Result.Retries, P.Result.Seconds));
		TestTrue(TEXT("Never a hard fail: the scene finishes"), P.Result.bComplete);
		TestTrue(TEXT("The crew did the calls nobody answered"), P.Result.StepsAssisted >= 4);
		TestTrue(TEXT("... after the repeats"), P.Result.Retries >= 2 * P.Result.StepsAssisted);
		TestTrue(TEXT("The crew's line was shown"), !Scene.GetCaption().empty() || P.Result.StepsAssisted > 0);
	}
	{
		// Restart: play until the tack is called (a checkpoint), restart, and it is the current step again, waiting.
		FScriptedScene Scene;
		if (!Load(*this, Scene)) return false;
		int32 TackIndex = -1;
		for (int32 I = 0; I < int32(Scene.GetSteps().size()); ++I) if (Scene.GetSteps()[size_t(I)].Id == "ready-about") TackIndex = I;
		bool bRestarted = false;
		Play(Scene, ECrew::Good, 900.0, [&](double)
		{
			if (!bRestarted && Scene.GetStepIndex() == TackIndex + 1)
			{
				bRestarted = true;
				Scene.RestartFromCheckpoint();
			}
		});
		TestTrue(TEXT("Restarted from the tack's checkpoint"), bRestarted);
		TestEqual(TEXT("The checkpoint"), FString(UTF8_TO_TCHAR(Scene.GetCheckpoint().c_str())), FString(TEXT("the-break")));
		TestEqual(TEXT("One restart counted"), Scene.GetResult().Restarts, 1);
		TestTrue(TEXT("... and the scene still finishes"), Scene.IsComplete());
	}
	return true;
}

/** The loader refuses a broken scene with a reason: an unknown trigger, a dangling next, a repeated id, bad JSON. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPrologueValidatorTest, "SailingSim.Prologue.Validator", PrologueTestsLocal::PrologueFlags)
bool FSailingPrologueValidatorTest::RunTest(const FString&)
{
	FString Text;
	TestTrue(TEXT("The scene file is staged"), FFileHelper::LoadFileToString(Text, *(FPaths::ProjectContentDir() / TEXT("Prologue/prologue.json"))));
	FScriptedScene Scene;
	std::string Error;
	TestTrue(TEXT("The shipped scene loads"), Scene.LoadText(TCHAR_TO_UTF8(*Text), &Error));
	auto Rejects = [&](const TCHAR* What, const FString& Broken, const char* Expect)
	{
		FScriptedScene S;
		std::string E;
		const bool bLoaded = S.LoadText(TCHAR_TO_UTF8(*Broken), &E);
		AddInfo(FString::Printf(TEXT("%s: %s"), What, UTF8_TO_TCHAR(E.c_str())));
		TestTrue(FString::Printf(TEXT("Rejects %s"), What), !bLoaded && !S.IsLoaded() && E.find(Expect) != std::string::npos);
	};
	auto ReplaceFirst = [](const FString& In, const TCHAR* From, const TCHAR* To)
	{
		const int32 At = In.Find(From);
		return At == INDEX_NONE ? In : In.Left(At) + To + In.Mid(At + FCString::Strlen(From));
	};
	Rejects(TEXT("an unknown trigger"), ReplaceFirst(Text, TEXT("\"type\": \"gust\""), TEXT("\"type\": \"moonrise\"")), "unknown trigger \"moonrise\"");
	Rejects(TEXT("a dangling step id"), ReplaceFirst(Text, TEXT("\"next\": \"end\""), TEXT("\"next\": \"harbour\"")), "next names no step: \"harbour\"");
	Rejects(TEXT("a repeated step id"), ReplaceFirst(Text, TEXT("\"id\": \"grind\""), TEXT("\"id\": \"ready-about\"")), "repeated step id");
	Rejects(TEXT("an unknown expectation"), ReplaceFirst(Text, TEXT("\"type\": \"tack\""), TEXT("\"type\": \"dance\"")), "unknown expectation");
	Rejects(TEXT("a camera the scene does not list"), ReplaceFirst(Text, TEXT("\"camera\": \"grinder\""), TEXT("\"camera\": \"drone\"")), "not in the scene's cameras");
	Rejects(TEXT("a misspelt field"), ReplaceFirst(Text, TEXT("\"over_mean_kn\""), TEXT("\"over_mean\"")), "unknown field \"over_mean\"");
	Rejects(TEXT("broken JSON"), Text.LeftChop(Text.Len() - Text.Find(TEXT("\"steps\""))), "JSON line");
	return true;
}

#endif
