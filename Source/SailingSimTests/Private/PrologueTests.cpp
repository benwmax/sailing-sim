#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "CrewStation.h"
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
		TArray<FString> Stations; // where the crew member was at each call
		FSceneResult Result;
		double GrindMeters = 0.0; // sheet the crew member ground in
		int32 MaxRepeats = 0;
		double Seconds = 0.0;
	};

	/**
	 * The J/22 stand-in in 25 kn with a scripted crew member answering the captain at the station the scene puts them
	 * at (step 2), and the rest of the crew (FStationControls: FAutoTrim, FAutopilot and the heavy-air tack) holding
	 * everything else: clip on, ease the jib a hand's length, steer the tack with the wheel, grind the new sheet in, the
	 * wheel downwind, dump the traveller then the main, the wheel up to a reach. Gusts come when a step waits for one:
	 * the wind steps to 35 kn for a few seconds, the way a squall line hits.
	 */
	FPlaythrough Play(FScriptedScene& Scene, ECrew Crew, double MaxSeconds = 900.0, const TFunction<void(double)>& Each = nullptr, FStationControls* OutStations = nullptr)
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
		FStationControls Stations;
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		Stations.Reset(Boat, FBoatControls(), ECrewStation::JibTrimmer);
		FAutopilot Hand; // where the crew member means to steer when they have the wheel
		int32 Side = 1;
		Scene.Start(Boat, StandInKnots);
		int32 LastSerial = 0, LastStep = -1, StationSerial = 0;
		double T = 0.0, CallT = 0.0, StepT = 0.0, JibAim = -1.0;
		bool bTacking = false, bDumped = false;
		for (int32 I = 0; I < int32(MaxSeconds * PhysicsHz) && !Scene.IsComplete(); ++I, T += PhysicsDt)
		{
			if (Scene.GetStepIndex() != LastStep) { LastStep = Scene.GetStepIndex(); StepT = T; JibAim = -1.0; bTacking = bDumped = false; }
			if (Scene.GetStationSerial() != StationSerial)
			{
				StationSerial = Scene.GetStationSerial();
				Stations.MoveTo(Boat, CrewStationFromName(Scene.GetStation()));
			}
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
				Out.Stations.Add(UTF8_TO_TCHAR(CrewStationName(Stations.GetStation())));
				Out.MaxRepeats = FMath::Max(Out.MaxRepeats, Scene.GetCallRepeats());
			}
			FSceneInput In;
			FStationInput Hands;
			const bool bAnswer = bCalling && T - CallT > 0.8 && Crew != ECrew::Silent && !(Crew == ECrew::IgnoresFirstEase && Id == "ease-jib" && Scene.GetCallRepeats() == 0);
			const FBoatControls& Now = Stations.GetControls();
			if (bAnswer)
			{
				if (Id == "clip-on") In.Actions.push_back("clip-on");
				else if (Id == "ease-jib")
				{
					if (JibAim < 0.0) JibAim = FMath::Min(1.0, Now.JibSheet + 0.2);
					if (Now.JibSheet < JibAim) Hands.JibSheet = 1.0;
				}
				else if (Id == "ready-about")
				{
					if (!bTacking) { Side = -Side; bTacking = true; }
					Hand.TargetTWADeg = 45.0 * Side;
					Hand.MaxTiller = 0.8;
					Hand.bKeepShortOfStall = false;
				}
				else if (Id == "grind") Hands.Grind = 1.0;
				else if (Id == "take-helm") Hand.TargetTWADeg = 150.0 * Side;
				else if (Id == "dump-main")
				{
					if (!bDumped) { Hands.bTravellerDump = true; bDumped = true; }
					else Hands.MainSheet = 1.0;
				}
				else if (Id == "the-break") Hand.TargetTWADeg = 90.0 * Side;
			}
			if (Id != "ready-about") { Hand.MaxTiller = 0.6; Hand.bKeepShortOfStall = true; }
			if (Stations.GetStation() == ECrewStation::Helm && Crew != ECrew::Silent)
			{
				// The wheel is a rate: turn it toward where the hand wants the rudder (before the tack, the course she is on).
				if (!bAnswer && !bTacking && Id == "ready-about") Hand.TargetTWADeg = 45.0 * Side;
				Hands.Wheel = FMath::Clamp((Hand.Update(Boat) - Now.Tiller) * 8.0, -1.0, 1.0);
			}
			const FBoatControls& C = Stations.Step(Boat, Hands, PhysicsDt);
			In.Controls = C;
			In.Station = CrewStationName(Stations.GetStation());
			In.Worked = Stations.TakeWorked();
			Boat.Step(PhysicsDt, C, bGusting ? Gust : Base);
			Scene.Update(Boat, In, PhysicsDt);
			if (Each) Each(T);
		}
		Out.Result = Scene.GetResult();
		Out.Seconds = T;
		Out.GrindMeters = Stations.GetPlayerGrindM();
		if (OutStations) *OutStations = Stations;
		return Out;
	}

	/** Seconds of grinding (the key held) to bring the jib sheet from fully eased in to Home, close-hauled on the J/22
	 *  stand-in in a steady wind with the rest of the crew steering and on the main. */
	double GrindSeconds(double Knots, double Home)
	{
		FWindParams P;
		P.SpeedKnots = Knots;
		P.FromDegrees = 0.0;
		const FWindField Wind(P);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 6.0 * kKnot);
		FStationControls Stations;
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		Stations.Reset(Boat, FBoatControls(), ECrewStation::JibTrimmer);
		int32 Phase = 0;
		double T = 0.0, Ground = 0.0;
		for (int32 I = 0; I < int32(90.0 * PhysicsHz); ++I, T += PhysicsDt)
		{
			FStationInput Hands;
			if (Phase == 0) { Hands.Grind = 1.0; if (T > 20.0) Phase = 1; } // sailing, trimmed
			if (Phase == 1) { Hands.JibSheet = 1.0; if (Stations.GetControls().JibSheet >= 0.999) Phase = 2; } // let fly
			if (Phase == 2)
			{
				if (Stations.GetControls().JibSheet <= Home) return Ground;
				Hands.Grind = 1.0;
				Ground += PhysicsDt;
			}
			Boat.Step(PhysicsDt, Stations.Step(Boat, Hands, PhysicsDt), Wind);
		}
		return -1.0;
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
	TArray<FString> StepStations;
	for (const FSceneStep& S : Scene.GetSteps()) StepStations.Add(UTF8_TO_TCHAR(S.Station.c_str()));
	TestEqual(TEXT("Step 2: at each call the crew member is at the step's station"), P.Stations, StepStations);

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
	Rejects(TEXT("a control the step's station does not work"), ReplaceFirst(Text, TEXT("\"controls\": [\"grinder\"]"), TEXT("\"controls\": [\"wheel\"]")), "is not worked at the step's station");
	Rejects(TEXT("an unknown control"), ReplaceFirst(Text, TEXT("\"controls\": [\"grinder\"]"), TEXT("\"controls\": [\"capstan\"]")), "unknown control \"capstan\"");
	Rejects(TEXT("a station the scene does not list"), ReplaceFirst(Text, TEXT("\"station\": \"helm\""), TEXT("\"station\": \"pit\"")), "not in the scene's stations");
	Rejects(TEXT("broken JSON"), Text.LeftChop(Text.Len() - Text.Find(TEXT("\"steps\""))), "JSON line");
	return true;
}

/**
 * Step 2, crew stations: the merge gives the crew every control the player does not work; a player at the jib who moves
 * the tiller changes nothing; the grinder brings a fully eased sheet home in 4-12 s of grinding in 25 kn and faster in
 * 12 kn; the whole scene still finishes with the scripted crew member grinding, steering the wheel and dumping.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPrologueStationsTest, "SailingSim.Prologue.Stations", PrologueTestsLocal::PrologueFlags)
bool FSailingPrologueStationsTest::RunTest(const FString&)
{
	using namespace PrologueTestsLocal;
	// The merge.
	FBoatControls Player, Crew;
	Player.Tiller = 0.7; Player.JibSheet = 0.9; Player.MainSheet = 0.8; Player.Traveler = 1.0; Player.bBackJib = true; Player.Vang = 0.9; Player.Hike = -1.0;
	Crew.Tiller = -0.2; Crew.JibSheet = 0.1; Crew.MainSheet = 0.2; Crew.Traveler = -0.5; Crew.bBackJib = false; Crew.Vang = 0.4; Crew.Hike = 1.0;
	auto Same = [](const FBoatControls& A, const FBoatControls& B)
	{
		return A.Tiller == B.Tiller && A.JibSheet == B.JibSheet && A.MainSheet == B.MainSheet && A.Traveler == B.Traveler && A.bBackJib == B.bBackJib && A.Vang == B.Vang && A.Hike == B.Hike;
	};
	FBoatControls Expect = Crew;
	Expect.Tiller = Player.Tiller;
	TestTrue(TEXT("Helm: the wheel is the player's, the rest the crew's"), Same(FStationControls::Merge(ECrewStation::Helm, Player, Crew), Expect));
	Expect = Crew;
	Expect.JibSheet = Player.JibSheet;
	Expect.bBackJib = Player.bBackJib;
	TestTrue(TEXT("Jib trimmer: the jib sheet (and backing it) only"), Same(FStationControls::Merge(ECrewStation::JibTrimmer, Player, Crew), Expect));
	Expect = Crew;
	Expect.MainSheet = Player.MainSheet;
	Expect.Traveler = Player.Traveler;
	TestTrue(TEXT("Main trimmer: mainsheet and traveller only"), Same(FStationControls::Merge(ECrewStation::MainTrimmer, Player, Crew), Expect));
	TestTrue(TEXT("No station (normal sailing): every control is the player's"), Same(FStationControls::Merge(ECrewStation::None, Player, Crew), Player));
	for (int32 S = 1; S < int32(ECrewStation::Count); ++S)
	{
		int32 Owned = 0;
		for (int32 C = 0; C < int32(EStationControl::Count); ++C) Owned += StationOwns(ECrewStation(S), EStationControl(C));
		TestTrue(FString::Printf(TEXT("%hs works some controls, not all"), CrewStationName(ECrewStation(S))), Owned > 0 && Owned < int32(EStationControl::Count));
		TestTrue(TEXT("Names round-trip"), CrewStationFromName(CrewStationName(ECrewStation(S))) == ECrewStation(S));
	}

	// A player at the jib who moves the tiller changes nothing (the crew have the wheel).
	{
		FWindParams P;
		P.SpeedKnots = StandInKnots;
		const FWindField Wind(P);
		FVector2D End[2];
		double Heading[2] = { 0.0, 0.0 };
		for (int32 Run = 0; Run < 2; ++Run)
		{
			FBoatModel Boat;
			Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 6.0 * kKnot);
			FStationControls Stations;
			Stations.Reset(Boat, FBoatControls(), ECrewStation::JibTrimmer);
			for (int32 I = 0; I < int32(20.0 * PhysicsHz); ++I)
			{
				FStationInput Hands;
				Hands.Wheel = Run == 1 ? (I / 240 % 2 ? 1.0 : -1.0) : 0.0;
				Hands.MainSheet = Run == 1 ? 1.0 : 0.0; // the main is not theirs either
				Hands.bTravellerDump = Run == 1;
				Boat.Step(PhysicsDt, Stations.Step(Boat, Hands, PhysicsDt), Wind);
			}
			const Vec3 O = Boat.OriginPosition();
			End[Run] = FVector2D(O.X, O.Y);
			Heading[Run] = Boat.GetTelemetry().Heading;
			TestTrue(TEXT("Nothing the jib trimmer does not work counts as worked"), (Stations.TakeWorked() & ~(StationControlBit(EStationControl::JibSheet) | StationControlBit(EStationControl::Grinder))) == 0u);
		}
		TestTrue(TEXT("Jib trimmer on the wheel, mainsheet and traveller: the boat sails exactly as without"), End[0] == End[1] && Heading[0] == Heading[1]);
	}

	// The grinder: from fully eased to the scene's "all the way" in a gale and in a sailing breeze.
	FScriptedScene Scene;
	if (!Load(*this, Scene)) return false;
	double Home = 0.15;
	for (const FSceneStep& S : Scene.GetSteps()) if (S.Id == "grind") Home = S.Expect.AtMost;
	const double Gale = GrindSeconds(StandInKnots, Home);
	const double Breeze = GrindSeconds(12.0, Home);
	AddInfo(FString::Printf(TEXT("Grinding the J/22's jib sheet home (fully eased to %.2f): %.1f s in %.0f kn, %.1f s in 12 kn"), Home, Gale, StandInKnots, Breeze));
	TestTrue(TEXT("A grind in 25 kn takes real seconds: 4 to 12"), Gale >= 4.0 && Gale <= 12.0);
	TestTrue(TEXT("... and is quicker in 12 kn"), Breeze > 0.0 && Breeze < Gale);
	FStationControls Winch;
	TestTrue(TEXT("Against no load the line runs at the winch's top speed"), FMath::IsNearlyEqual(Winch.GrindLineSpeed(0.0, 1.0), Winch.Config.MaxLineSpeedMs));
	TestTrue(TEXT("Twice the load, half the speed (power-limited)"), FMath::IsNearlyEqual(Winch.GrindLineSpeed(4000.0, 1.0) * 2.0, Winch.GrindLineSpeed(2000.0, 1.0)));

	// The whole scene with the crew member at the stations: every call answered there, the grind by grinding.
	const FPlaythrough Good = Play(Scene, ECrew::Good);
	AddInfo(FString::Printf(TEXT("Stations playthrough: %d answered, %d by the crew, %d repeats, %.0f s, %.1f m of sheet ground; stations %s"),
		Good.Result.StepsPassed, Good.Result.StepsAssisted, Good.Result.Retries, Good.Result.Seconds, Good.GrindMeters, *FString::Join(Good.Stations, TEXT(", "))));
	TestTrue(TEXT("The scene finishes"), Good.Result.bComplete);
	TestEqual(TEXT("All seven steps answered at their stations"), Good.Result.StepsPassed, 7);
	TestTrue(TEXT("The new sheet was ground in by the crew member (over a metre of it)"), Good.GrindMeters > 1.0);
	int32 GrindIndex = -1;
	for (int32 I = 0; I < int32(Scene.GetSteps().size()); ++I) if (Scene.GetSteps()[size_t(I)].Id == "grind") GrindIndex = I;
	TestTrue(TEXT("The grind step asks for the grinder"), GrindIndex >= 0 && Scene.GetSteps()[size_t(GrindIndex)].Expect.Controls == std::vector<std::string>{ "grinder" });
	return true;
}

#endif
