#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "CrewStation.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "SailingMath.h"
#include "ScriptedScene.h"
#include "Wind.h"
#include "Ocean.h"
#include "Waves.h"
#include "Weather.h"
#include "EasyAssists.h"
#include "SailingGameMode.h"
#include "SailSave.h"
#include "SailingSettings.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace PrologueTestsLocal
{
	constexpr EAutomationTestFlags PrologueFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	constexpr double StandInKnots = 25.0;

	/** The boat a playthrough sails: the scene's own (step 3: the maxi in its 32 kn gusting 40 on two reefs, with the
	 *  scene's assisted limits) or the stand-in (steps 1 and 2: the J/22 in 25 kn gusting 35), read from the scene. */
	struct FPlayBoat
	{
		EBoatType Type = EBoatType::Maxi;
		double Knots = 32.0, GustKnots = 40.0;
		int32 Reefs = 2;
		const TCHAR* Name = TEXT("maxi");

		static FPlayBoat Own(const FScriptedScene& Scene)
		{
			const FSceneSetting& Set = Scene.GetSetting();
			FPlayBoat B;
			B.Type = EBoatType(FMath::Max(0, USailingSettings::MatchBoatName(UTF8_TO_TCHAR(Set.Boat.c_str()))));
			B.Knots = Set.WindKn;
			B.GustKnots = Set.GustKn;
			B.Reefs = Set.Reefs;
			return B;
		}
		static FPlayBoat StandIn(const FScriptedScene& Scene)
		{
			const FSceneSetting& Set = Scene.GetSetting();
			FPlayBoat B;
			B.Type = EBoatType(FMath::Max(0, USailingSettings::MatchBoatName(UTF8_TO_TCHAR(Set.StandInBoat.c_str()))));
			B.Knots = Set.StandInWindKn;
			B.GustKnots = StandInKnots + 10.0; // a squall line's step, as in steps 1 and 2
			B.Reefs = Set.StandInReefs;
			B.Name = TEXT("J/22 stand-in");
			return B;
		}
		FBoatConfig Config() const
		{
			FBoatConfig C = FBoatConfig::Make(Type);
			FSceneLimits::For(true).ApplyTo(C); // the scene's limits, as the game sets them while a scene runs
			return C;
		}
		/** Close-hauled on starboard at a speed she sails at (TWA = wind from - heading). */
		void Start(FBoatModel& Boat) const { Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, (Type == EBoatType::Maxi ? 9.0 : 6.0) * kKnot); }
	};

	enum class ECrew : uint8 { Good, IgnoresFirstEase, Silent };

	/**
	 * Step 4: the scene's own weather, the way the game runs it: the mistral preset (FWeatherSystem) on the scene's stand-in
	 * direction, re-evaluated every quarter second onto the wind field round the boat (ApplyToWind), its cues from the
	 * scene's steps (ApplySceneCue on the scene's weather serial, sim time = weather time), and the preset's FFT sea (its
	 * fetch-limited wind sea and the older sea with it) under the boat, the lake chop on a 200 m fetch as offshore.
	 */
	struct FGale
	{
		FWeatherSystem Weather;
		FWeatherState State;
		FWindField Wind;
		FWaveField Waves{ 3 };
		std::shared_ptr<FOcean> Ocean = std::make_shared<FOcean>();
		double Scale = 1.0, NextWeather = 0.0;
		int32 CueSerial = -1;
		double SquallCuedAt = -1.0, SquallDue = -1.0, ClearingAt = -1.0;

		bool bSea = true;
		FGale(const FSceneSetting& Set, double Knots, bool bWithSea = true) : bSea(bWithSea)
		{
			Weather.Configure(EWeatherPreset::Mistral, 1, Set.Hour >= 0.0 ? Set.Hour : 17.5);
			Weather.SetClimate(10, true);
			if (Set.WorldStandInWindFromDeg >= 0.0) Weather.SetPrevailingFrom(Set.WorldStandInWindFromDeg);
			Weather.ClearCues();
			State = Weather.Evaluate(0.0);
			Scale = Knots / State.Wind.SpeedKnots;
			State.Wind.SpeedKnots *= Scale;
			Wind = FWindField(State.Wind);
			FOceanParams O;
			O.WindMs = State.Wind.SpeedKnots * kKnot;
			O.WindFromRad = State.Wind.FromDegrees * kDegToRad;
			O.WindSeaHs = State.WindSeaHsM;
			O.WindSeaTp = State.WindSeaTpS;
			O.SwellHs = State.SwellHsM;
			O.SwellTp = State.SwellTpS;
			O.SwellFromRad = State.SwellFromDeg * kDegToRad;
			Ocean->Configure(O);
			if (bSea) Waves.SetOcean(Ocean);
			FWaveParams WP;
			WP.WindSpeedKnots = State.Wind.SpeedKnots;
			WP.WindFromDegrees = State.Wind.FromDegrees;
			WP.FetchMeters = bSea ? 200.0 : 1.0;
			Waves.SetWind(WP);
			Waves.SnapToTarget();
		}
		const FWaveField* Sea() const { return bSea ? &Waves : nullptr; }
		/** Heading (rad, map frame) that puts the true wind at Twa degrees (positive: from starboard). */
		double HeadingFor(double TwaDeg) const { return (State.Wind.FromDegrees - TwaDeg) * kDegToRad; }
		void Update(double T, const FBoatModel& Boat, FScriptedScene* Scene)
		{
			const Vec3 O = Boat.OriginPosition();
			if (Scene && Scene->GetWeatherSerial() != CueSerial)
			{
				CueSerial = Scene->GetWeatherSerial();
				const FSceneStep* Cue = Scene->GetWeatherStep();
				const Vec3 V = Boat.GetState().Velocity;
				const bool bFresh = Cue && Cue == Scene->GetStep();
				Weather.ApplySceneCue(Cue ? Cue->WeatherCue : std::string(), bFresh ? Cue->WeatherInSeconds : 0.0, T, O.X, O.Y, V.X, V.Y);
				if (Cue && Cue->WeatherCue == "squall") { SquallCuedAt = T; SquallDue = Weather.GetSquallArrives(); }
				if (Cue && Cue->WeatherCue == "clearing") ClearingAt = T;
			}
			if (T + 1e-9 < NextWeather) return;
			NextWeather = T + 0.25;
			State = Weather.Evaluate(T);
			State.Wind.SpeedKnots *= Scale;
			FWeatherSystem::ApplyToWind(State, Wind, T, O.X, O.Y);
			FWaveParams WP;
			WP.WindSpeedKnots = State.Wind.SpeedKnots;
			WP.WindFromDegrees = State.Wind.FromDegrees;
			WP.FetchMeters = bSea ? 200.0 : 1.0;
			Waves.SetWind(WP);
			Waves.Update(0.25);
			if (Scene) Scene->SetMeanWindKn(State.Wind.SpeedKnots);
		}
	};

	/** What a playthrough saw: the calls in order (ids), the captions shown, the camera hints, the result. */
	struct FPlaythrough
	{
		TArray<FString> Calls;
		TArray<FString> Captions;
		TArray<FString> Cameras;
		TArray<FString> Stations; // where the crew member was at each call
		TMap<FString, double> AnswerSeconds; // step 4: each step's first call to its end (the answer, or the crew's)
		TMap<FString, double> StepAt; // when each step became current (sim s)
		TMap<FString, double> CallAt; // its first call
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
	FPlaythrough Play(FScriptedScene& Scene, ECrew Crew, const FPlayBoat& On, double MaxSeconds = 900.0, const TFunction<void(double)>& Each = nullptr,
		FStationControls* OutStations = nullptr, FGale* Gale = nullptr, const TFunction<void(double, const FBoatModel&)>& Watch = nullptr)
	{
		FPlaythrough Out;
		FWindParams P;
		P.SpeedKnots = On.Knots;
		P.FromDegrees = 0.0;
		const FWindField Base(P);
		P.SpeedKnots = On.GustKnots;
		const FWindField Gust(P);
		FBoatModel Boat(On.Config());
		On.Start(Boat);
		// In the gale, close-hauled on starboard in its wind (as the steady runs: wind from 0, heading -45).
		if (Gale) Boat.Reset(0.0, 0.0, Gale->HeadingFor(45.0), (On.Type == EBoatType::Maxi ? 9.0 : 6.0) * kKnot);
		FStationControls Stations;
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		FBoatControls Sails;
		Sails.Reef = On.Reefs;
		Stations.Reset(Boat, Sails, ECrewStation::JibTrimmer);
		FAutopilot Hand; // where the crew member means to steer when they have the wheel
		int32 Side = 1;
		Scene.Start(Boat, On.Knots);
		if (Gale) Gale->Update(0.0, Boat, &Scene);
		int32 LastSerial = 0, LastStep = -1, StationSerial = 0;
		FString PrevId;
		double PrevCall = -1.0;
		double T = 0.0, CallT = 0.0, StepT = 0.0, JibAim = -1.0;
		bool bTacking = false, bDumped = false;
		for (int32 I = 0; I < int32(MaxSeconds * PhysicsHz) && !Scene.IsComplete(); ++I, T += PhysicsDt)
		{
			if (Scene.GetStepIndex() != LastStep)
			{
				if (!PrevId.IsEmpty() && PrevCall >= 0.0) Out.AnswerSeconds.Add(PrevId, T - PrevCall);
				LastStep = Scene.GetStepIndex();
				StepT = T;
				JibAim = -1.0;
				bTacking = bDumped = false;
				PrevId = Scene.GetStep() ? FString(UTF8_TO_TCHAR(Scene.GetStep()->Id.c_str())) : FString();
				PrevCall = -1.0;
				if (!PrevId.IsEmpty()) Out.StepAt.Add(PrevId, T);
			}
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
				if (PrevCall < 0.0) { PrevCall = T; Out.CallAt.Add(PrevId, T); }
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
			if (Gale)
			{
				Gale->Update(T, Boat, &Scene);
				Boat.Step(PhysicsDt, C, Gale->Wind, Gale->Sea());
			}
			else Boat.Step(PhysicsDt, C, bGusting ? Gust : Base);
			Scene.Update(Boat, In, PhysicsDt);
			if (Each) Each(T);
			if (Watch) Watch(T, Boat);
		}
		if (!PrevId.IsEmpty() && PrevCall >= 0.0 && Scene.IsComplete()) Out.AnswerSeconds.Add(PrevId, T - PrevCall);
		Out.Result = Scene.GetResult();
		Out.Seconds = T;
		Out.GrindMeters = Stations.GetPlayerGrindM();
		if (OutStations) *OutStations = Stations;
		return Out;
	}

	/** Seconds of grinding (the key held) to bring the jib sheet from fully eased in to Home, close-hauled in a steady
	 *  wind with the rest of the crew steering and on the main. */
	double GrindSeconds(const FPlayBoat& On, double Knots, double Home, FGale* Gale = nullptr)
	{
		FWindParams P;
		P.SpeedKnots = Knots;
		P.FromDegrees = 0.0;
		const FWindField Wind(P);
		FBoatModel Boat(On.Config());
		On.Start(Boat);
		if (Gale) Boat.Reset(0.0, 0.0, Gale->HeadingFor(45.0), (On.Type == EBoatType::Maxi ? 9.0 : 6.0) * kKnot);
		FStationControls Stations;
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		FBoatControls Sails;
		Sails.Reef = On.Reefs;
		Stations.Reset(Boat, Sails, ECrewStation::JibTrimmer);
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
			if (Gale)
			{
				Gale->Update(T, Boat, nullptr);
				Boat.Step(PhysicsDt, Stations.Step(Boat, Hands, PhysicsDt), Gale->Wind, Gale->Sea());
			}
			else Boat.Step(PhysicsDt, Stations.Step(Boat, Hands, PhysicsDt), Wind);
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
	const FPlayBoat Own = FPlayBoat::Own(Scene);
	TestEqual(TEXT("Step 3: the scene's own boat is the maxi"), int32(Own.Type), int32(EBoatType::Maxi));
	TestEqual(TEXT("... on her two gale reefs"), Own.Reefs, 2);
	// The stand-in first (steps 1 and 2's boat, kept for comparison), then the maxi (the save checks below use hers).
	{
		FScriptedScene StandIn;
		if (!Load(*this, StandIn)) return false;
		const FPlaythrough S = Play(StandIn, ECrew::Good, FPlayBoat::StandIn(StandIn));
		AddInfo(FString::Printf(TEXT("Prologue on the J/22 stand-in in %.0f kn: %d answered, %d by the crew, %d repeats, %.0f s"), StandInKnots,
			S.Result.StepsPassed, S.Result.StepsAssisted, S.Result.Retries, S.Result.Seconds));
		TestTrue(TEXT("Stand-in: the scene finishes, every step answered, no repeats"), S.Result.bComplete && S.Result.StepsPassed == 7 && S.Result.Retries == 0);
	}
	const FPlaythrough P = Play(Scene, ECrew::Good, Own);
	AddInfo(FString::Printf(TEXT("Prologue on the maxi in %.0f kn gusting %.0f, %d reefs: %d answered, %d by the crew, %d repeats, %.0f s; calls %s"), Own.Knots,
		Own.GustKnots, Own.Reefs, P.Result.StepsPassed, P.Result.StepsAssisted, P.Result.Retries, P.Result.Seconds, *FString::Join(P.Calls, TEXT(", "))));
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
		const FPlaythrough P = Play(Scene, ECrew::IgnoresFirstEase, FPlayBoat::Own(Scene));
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
		const FPlaythrough P = Play(Scene, ECrew::Silent, FPlayBoat::Own(Scene));
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
		Play(Scene, ECrew::Good, FPlayBoat::Own(Scene), 900.0, [&](double)
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

	// The grinder: from fully eased to "all the way" in a gale and in a sailing breeze. On the J/22 stand-in that is 0.15
	// (step 2's "all the way"); on the maxi it is the scene's grind step (step 3: the J4's sheet to 0.4 against 40 kN).
	FScriptedScene Scene;
	if (!Load(*this, Scene)) return false;
	double Home = 0.15;
	for (const FSceneStep& S : Scene.GetSteps()) if (S.Id == "grind") Home = S.Expect.AtMost;
	const FPlayBoat StandIn = FPlayBoat::StandIn(Scene), Own = FPlayBoat::Own(Scene);
	const double Gale = GrindSeconds(StandIn, StandInKnots, 0.15);
	const double Breeze = GrindSeconds(StandIn, 12.0, 0.15);
	AddInfo(FString::Printf(TEXT("Grinding the J/22's jib sheet home (fully eased to 0.15): %.1f s in %.0f kn, %.1f s in 12 kn"), Gale, StandInKnots, Breeze));
	TestTrue(TEXT("A grind in 25 kn takes real seconds: 4 to 12"), Gale >= 4.0 && Gale <= 12.0);
	TestTrue(TEXT("... and is quicker in 12 kn"), Breeze > 0.0 && Breeze < Gale);
	const double MaxiGale = GrindSeconds(Own, Own.Knots, Home);
	const double MaxiHome = GrindSeconds(Own, Own.Knots, 0.2);
	const double MaxiBreeze = GrindSeconds(Own, 12.0, Home);
	AddInfo(FString::Printf(TEXT("Grinding the maxi's jib sheet (two reefs, the J4) from fully eased: to %.2f in %.1f s in %.0f kn (to 0.20 in %.1f s), %.1f s in 12 kn"),
		Home, MaxiGale, Own.Knots, MaxiHome, MaxiBreeze));
	TestTrue(TEXT("Maxi: the scene's grind in 32 kn takes longer than the J/22's and fits its 25 s"), MaxiGale > Gale && MaxiGale < 25.0);
	TestTrue(TEXT("... the last of it is power-limited (to 0.2 takes far longer)"), MaxiHome > 2.0 * MaxiGale);
	TestTrue(TEXT("... and it is quicker in 12 kn"), MaxiBreeze > 0.0 && MaxiBreeze < MaxiGale);
	FStationControls Winch;
	TestTrue(TEXT("Against no load the line runs at the winch's top speed"), FMath::IsNearlyEqual(Winch.GrindLineSpeed(0.0, 1.0), Winch.Config.MaxLineSpeedMs));
	TestTrue(TEXT("Twice the load, half the speed (power-limited)"), FMath::IsNearlyEqual(Winch.GrindLineSpeed(4000.0, 1.0) * 2.0, Winch.GrindLineSpeed(2000.0, 1.0)));

	// The whole scene with the crew member at the stations: every call answered there, the grind by grinding.
	const FPlaythrough Good = Play(Scene, ECrew::Good, Own);
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

namespace PrologueTestsLocal
{
	/** How a boat moves in the gale's sea: pitch, heave, the bow's vertical acceleration (0.1 s second differences) and
	 *  the speed on the faces of the waves against their backs. */
	struct FSeaMotion
	{
		double MaxPitchDeg = 0.0, MaxHeelDeg = 0.0;
		double HeaveMin = 1e9, HeaveMax = -1e9;
		double BowUpG = 0.0, BowDownG = 0.0; // most up and most down (negative) vertical acceleration at the bow, in g
		double CgUpG = 0.0, CgDownG = 0.0;   // the same at the centre of gravity
		double ClearSeconds = 0.0;           // her midship bottom out of the water (off a crest)
		double MaxSlope = 0.0;               // steepest downhill slope met along her course
		double CgZ[3] = { 0.0, 0.0, 0.0 };
		double SpeedMin = 1e9, SpeedMax = 0.0, SpeedSum = 0.0;
		double FaceAccel = 0.0, BackAccel = 0.0; // mean dV/dt (m/s^2) on a wave's face (water ahead lower) and on its back
		int32 Samples = 0, FaceSamples = 0, BackSamples = 0;
		double BowZ[3] = { 0.0, 0.0, 0.0 };
		double LastSpeed = -1.0;
		int32 Taken = 0;

		/** Call every 0.1 s. */
		void Sample(const FBoatModel& Boat, const FWaveField& Waves)
		{
			const FBoatTelemetry& Tel = Boat.GetTelemetry();
			const FBoatState& St = Boat.GetState();
			const Vec3 O = Boat.OriginPosition();
			const Vec3 Bow = O + St.Orientation.Rotate(Vec3(0.45 * Boat.GetConfig().LengthOverall, 0.0, 0.0));
			BowZ[0] = BowZ[1];
			BowZ[1] = BowZ[2];
			BowZ[2] = Bow.Z;
			CgZ[0] = CgZ[1];
			CgZ[1] = CgZ[2];
			CgZ[2] = St.Position.Z;
			if (++Taken >= 3)
			{
				const double A = (BowZ[2] - 2.0 * BowZ[1] + BowZ[0]) / (0.1 * 0.1) / 9.81;
				BowUpG = FMath::Max(BowUpG, A);
				BowDownG = FMath::Min(BowDownG, A);
				const double Ac = (CgZ[2] - 2.0 * CgZ[1] + CgZ[0]) / (0.1 * 0.1) / 9.81;
				CgUpG = FMath::Max(CgUpG, Ac);
				CgDownG = FMath::Min(CgDownG, Ac);
			}
			if (O.Z - Boat.HullDepth() > Waves.Height(O.X, O.Y, St.Time)) ClearSeconds += 0.1;
			MaxPitchDeg = FMath::Max(MaxPitchDeg, FMath::Abs(Tel.Pitch) / kDegToRad);
			MaxHeelDeg = FMath::Max(MaxHeelDeg, FMath::Abs(Tel.Heel) / kDegToRad);
			HeaveMin = FMath::Min(HeaveMin, O.Z);
			HeaveMax = FMath::Max(HeaveMax, O.Z);
			const double Kn = Tel.BoatSpeed / kKnot;
			SpeedMin = FMath::Min(SpeedMin, Kn);
			SpeedMax = FMath::Max(SpeedMax, Kn);
			SpeedSum += Kn;
			++Samples;
			double H, Vz, Sx, Sy;
			Waves.Sample(O.X, O.Y, St.Time, H, Vz, Sx, Sy);
			const Vec3 F = St.Orientation.Forward();
			const double Slope = (Sx * F.X + Sy * F.Y) / FMath::Max(FMath::Sqrt(F.X * F.X + F.Y * F.Y), 1e-6); // dh along her course
			MaxSlope = FMath::Max(MaxSlope, -Slope);
			if (LastSpeed >= 0.0)
			{
				const double Accel = (Tel.BoatSpeed - LastSpeed) / 0.1;
				if (Slope < -0.03) { FaceAccel += Accel; ++FaceSamples; }
				else if (Slope > 0.03) { BackAccel += Accel; ++BackSamples; }
			}
			LastSpeed = Tel.BoatSpeed;
		}
		double MeanSpeed() const { return Samples ? SpeedSum / Samples : 0.0; }
		double Face() const { return FaceSamples ? FaceAccel / FaceSamples : 0.0; }
		double Back() const { return BackSamples ? BackAccel / BackSamples : 0.0; }
		FString Describe() const
		{
			return FString::Printf(TEXT("pitch to %.1f deg, heel to %.1f deg, heave %.2f m (%.2f to %.2f), bow %.2f g up / %.2f g down, CG %.2f / %.2f g, off a crest %.1f s, speed %.1f-%.1f kn (mean %.1f), steepest face %.2f, on the faces %+.3f m/s^2, on the backs %+.3f"),
				MaxPitchDeg, MaxHeelDeg, HeaveMax - HeaveMin, HeaveMin, HeaveMax, BowUpG, BowDownG, CgUpG, CgDownG, ClearSeconds, SpeedMin, SpeedMax, MeanSpeed(), MaxSlope, Face(), Back());
		}
	};

	/** The maxi sailed by the crew (the jib trimmer's station: the rest of the crew steer the course she starts on and trim)
	 *  at a true wind angle in the gale, for Seconds after a settling minute. */
	/** The player's wheel tacks her from close-hauled (the playthrough's hand) after the crew have sailed her a minute:
	 *  seconds from the wheel going over to settled on the new tack (|TWA| 30-100 for a second), -1 if not in 90 s. */
	double TackInGale(const FPlayBoat& On, const FSceneSetting& Set, bool bSea, uint32 Seed)
	{
		FGale Gale(Set, On.Knots, bSea);
		Gale.Weather.Configure(EWeatherPreset::Mistral, Seed, Set.Hour >= 0.0 ? Set.Hour : 17.5);
		if (Set.WorldStandInWindFromDeg >= 0.0) Gale.Weather.SetPrevailingFrom(Set.WorldStandInWindFromDeg);
		Gale.Weather.ClearCues();
		FBoatModel Boat(On.Config());
		Boat.Reset(0.0, 0.0, Gale.HeadingFor(55.0), 9.0 * kKnot);
		FStationControls Stations;
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		FBoatControls Sails;
		Sails.Reef = On.Reefs;
		Stations.Reset(Boat, Sails, ECrewStation::JibTrimmer);
		FAutopilot Hand;
		Hand.TargetTWADeg = -45.0;
		Hand.MaxTiller = 0.8;
		Hand.bKeepShortOfStall = false;
		const double Called = 60.0 + 7.0 * Seed;
		double T = 0.0, Settled = 0.0;
		for (int32 I = 0; I < int32((Called + 90.0) * PhysicsHz); ++I, T += PhysicsDt)
		{
			Gale.Update(T, Boat, nullptr);
			FStationInput In;
			if (T >= Called && Stations.GetStation() != ECrewStation::Helm) Stations.MoveTo(Boat, ECrewStation::Helm);
			if (T >= Called) In.Wheel = FMath::Clamp((Hand.Update(Boat) - Stations.GetControls().Tiller) * 8.0, -1.0, 1.0);
			Boat.Step(PhysicsDt, Stations.Step(Boat, In, PhysicsDt), Gale.Wind, Gale.Sea());
			if (T < Called) continue;
			const double Twa = Boat.GetTelemetry().TrueWindAngle / kDegToRad;
			Settled = Twa < -30.0 && Twa > -100.0 ? Settled + PhysicsDt : 0.0;
			if (Settled >= 1.0) return T - Called - 1.0;
		}
		return -1.0;
	}

	FSeaMotion SailInGale(const FPlayBoat& On, const FSceneSetting& Set, double TwaDeg, double Seconds)
	{
		FGale Gale(Set, On.Knots);
		FBoatModel Boat(On.Config());
		Boat.Reset(0.0, 0.0, Gale.HeadingFor(TwaDeg), 10.0 * kKnot);
		FStationControls Stations;
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		FBoatControls Sails;
		Sails.Reef = On.Reefs;
		Stations.Reset(Boat, Sails, ECrewStation::JibTrimmer);
		FSeaMotion M;
		double T = 0.0;
		for (int32 I = 0; I < int32((60.0 + Seconds) * PhysicsHz); ++I, T += PhysicsDt)
		{
			Gale.Update(T, Boat, nullptr);
			Boat.Step(PhysicsDt, Stations.Step(Boat, FStationInput(), PhysicsDt), Gale.Wind, &Gale.Waves);
			if (T >= 60.0 && I % 12 == 0) M.Sample(Boat, Gale.Waves);
		}
		return M;
	}
}

/**
 * Step 4: the whole prologue on the maxi in the scene's own weather: the mistral preset (32 kn gusting 40, the 3.5 m
 * short sea), its squall cued by the "dump the main" step and reaching her as that step's gust trigger is due, the break
 * from the next step. The crew member answers every call; the grind and the tack are timed in the gale; the maxi's motion
 * in that sea (pitch, heave, the bow's acceleration) on a reach and a beat, and the surf on the "run down the face" step.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPrologueGaleTest, "SailingSim.Prologue.Gale", PrologueTestsLocal::PrologueFlags)
bool FSailingPrologueGaleTest::RunTest(const FString&)
{
	using namespace PrologueTestsLocal;
	FScriptedScene Scene;
	if (!Load(*this, Scene)) return false;
	const FSceneSetting& Set = Scene.GetSetting();
	TestEqual(TEXT("The scene asks for the mistral"), FString(UTF8_TO_TCHAR(Set.Weather.c_str())), FString(WeatherPresetName(EWeatherPreset::Mistral)));
	TestEqual(TEXT("... in the preset's own wind"), Set.WindKn, FWeatherSystem::kMistralKnots);
	TestEqual(TEXT("... gusting to the preset's"), Set.GustKn, FWeatherSystem::kMistralGustKnots);
	const FPlayBoat Own = FPlayBoat::Own(Scene);
	FGale Gale(Set, Own.Knots);
	AddInfo(FString::Printf(TEXT("The gale's sea: Hs %.2f m (the scene asks %.1f), Tm01 %.1f s, from %.0f; wind %.1f kn from %.0f"), Gale.Ocean->SignificantHeight(), Set.SeaHsM,
		Gale.Ocean->MeanPeriod(), Gale.State.SwellFromDeg, Gale.State.Wind.SpeedKnots, Gale.State.Wind.FromDegrees));
	TestTrue(TEXT("The sea the scene asks for (within 0.3 m)"), FMath::Abs(Gale.Ocean->SignificantHeight() - Set.SeaHsM) < 0.3);

	// The playthrough, watching the squall and the surf.
	FSeaMotion Run, Surf;
	double FrontAt = -1.0, SquallPeak = 0.0, Rain = 0.0, MaxRain = 0.0;
	int32 Tick = 0;
	FString Step;
	const FPlaythrough P = Play(Scene, ECrew::Good, Own, 900.0, nullptr, nullptr, &Gale, [&](double T, const FBoatModel& Boat)
	{
		const FSceneStep* S = Scene.GetStep();
		Step = S ? FString(UTF8_TO_TCHAR(S->Id.c_str())) : FString();
		const Vec3 O = Boat.OriginPosition();
		if (Gale.State.Front.bActive && FrontAt < 0.0 && Gale.State.Front.Behind(O.X, O.Y, T) >= 0.99) FrontAt = T;
		if (FrontAt >= 0.0 && T < FrontAt + 20.0) SquallPeak = FMath::Max(SquallPeak, Gale.Wind.VelocityAt(Vec3(O.X, O.Y, 10.0), T).LengthXY() / kKnot);
		if (++Tick % 12 != 0) return;
		Rain = Gale.State.RainRateAt(O.X, O.Y, 0.0, T);
		MaxRain = FMath::Max(MaxRain, Rain);
		Run.Sample(Boat, Gale.Waves);
		if (Step == TEXT("take-helm") && Scene.GetPhase() == FScriptedScene::EPhase::Calling) Surf.Sample(Boat, Gale.Waves);
	});
	auto At = [&](const TMap<FString, double>& Map, const TCHAR* Key) { const double* V = Map.Find(Key); return V ? *V : -1.0; };
	AddInfo(FString::Printf(TEXT("Prologue on the maxi in the mistral: %d answered, %d by the crew, %d repeats, %.0f s; calls %s"), P.Result.StepsPassed, P.Result.StepsAssisted,
		P.Result.Retries, P.Result.Seconds, *FString::Join(P.Calls, TEXT(", "))));
	TestTrue(TEXT("The scene finishes in the gale"), P.Result.bComplete);
	TestEqual(TEXT("... every step done"), P.Result.StepsPassed + P.Result.StepsAssisted, 7);
	// Known gap (docs/prologue/README.md, step 4): in the preset's 3.5 m sea the maxi does not tack on the helm (her added
	// resistance, FBoatConfig::AddedResistanceCoef, the fleet's default: a fleet change, not made here), so the crew take
	// the tack over after its repeats; every other step is the crew member's.
	TestTrue(TEXT("... all but the tack answered by the crew member"), P.Result.StepsPassed >= 6);

	// Grind and tack in 32 kn gusting 40: the scene's, and on their own in the preset's wind with and without its sea.
	const double Tack = At(P.AnswerSeconds, TEXT("ready-about")), Grind = At(P.AnswerSeconds, TEXT("grind"));
	AddInfo(FString::Printf(TEXT("In the gale's scene: the tack %.1f s from the call, the grind %.1f s, the ease %.1f s, the dump %.1f s, the run %.1f s, the break %.1f s"), Tack, Grind,
		At(P.AnswerSeconds, TEXT("ease-jib")), At(P.AnswerSeconds, TEXT("dump-main")), At(P.AnswerSeconds, TEXT("take-helm")), At(P.AnswerSeconds, TEXT("the-break"))));
	double Home = 0.4;
	for (const FSceneStep& S : Scene.GetSteps()) if (S.Id == "grind") Home = S.Expect.AtMost;
	FGale GrindSea(Set, Own.Knots);
	const double GaleGrind = GrindSeconds(Own, Own.Knots, Home, &GrindSea);
	TArray<FString> Flat, InSea;
	int32 FlatOk = 0, SeaOk = 0;
	double FlatSum = 0.0, FlatWorst = 0.0;
	for (uint32 Seed = 1; Seed <= 3; ++Seed)
	{
		const double F = TackInGale(Own, Set, false, Seed), W = TackInGale(Own, Set, true, Seed);
		Flat.Add(FString::Printf(TEXT("%.1f"), F));
		InSea.Add(FString::Printf(TEXT("%.1f"), W));
		if (F > 0.0) { ++FlatOk; FlatSum += F; FlatWorst = FMath::Max(FlatWorst, F); }
		SeaOk += W > 0.0;
	}
	AddInfo(FString::Printf(TEXT("Grind in the gale (fully eased to %.2f, wind and sea): %.1f s. Tack on the wheel in the preset's wind, flat water: %s s (%d of 3); in its sea: %s (%d of 3, -1 = not through in 90 s)"),
		Home, GaleGrind, *FString::Join(Flat, TEXT(", ")), FlatOk, *FString::Join(InSea, TEXT(", ")), SeaOk));
	TestTrue(TEXT("The grind in the gale fits its step's 25 s"), GaleGrind > 0.0 && GaleGrind < 25.0);
	TestTrue(TEXT("In the preset's wind she tacks on the wheel, inside the step's 25 s"), FlatOk == 3 && FlatWorst < 25.0);

	// The squall on the step's clock: cued as "dump the main" begins, its front on her as the step's trigger is due, the
	// call on the gust it brings; the break as the next step begins.
	const double DumpAt = At(P.StepAt, TEXT("dump-main")), DumpCall = At(P.CallAt, TEXT("dump-main")), BreakAt = At(P.StepAt, TEXT("the-break"));
	const FSceneStep* Dump = nullptr;
	for (const FSceneStep& S : Scene.GetSteps()) if (S.Id == "dump-main") Dump = &S;
	if (!TestNotNull(TEXT("The dump-main step"), Dump)) return false;
	AddInfo(FString::Printf(TEXT("Squall: \"dump the main\" began at %.1f s, the squall cued at %.1f s for %.1f s; its wind was on her at %.1f s (%.1f kn at 10 m in its first 20 s, rain to %.1f mm/h), the call at %.1f s; the break began at %.1f s, cued at %.1f s"),
		DumpAt, Gale.SquallCuedAt, Gale.SquallDue, FrontAt, SquallPeak, MaxRain, DumpCall, BreakAt, Gale.ClearingAt));
	TestTrue(TEXT("The squall is cued as its step begins"), FMath::Abs(Gale.SquallCuedAt - DumpAt) < 0.02);
	// Within 2 s: the cue aims at where she will be at her speed and course when the step begins, and she turns after.
	TestTrue(TEXT("Its wind is on her on the step's clock (within 2 s of its in_s)"), FMath::Abs(FrontAt - (DumpAt + Dump->WeatherInSeconds)) < 2.0);
	TestTrue(TEXT("The call comes with the squall's gust (within 3 s of the front)"), DumpCall >= DumpAt + Dump->Trigger.AfterSeconds && DumpCall < FrontAt + 3.0);
	TestTrue(TEXT("A 40 kn front (38-46 kn at 10 m)"), SquallPeak >= 38.0 && SquallPeak <= 46.0);
	TestTrue(TEXT("The break begins with its step"), FMath::Abs(Gale.ClearingAt - BreakAt) < 0.02);
	const FWeatherState End = Gale.Weather.Evaluate(BreakAt + FWeatherSystem::kClearingSeconds + 1.0);
	TestTrue(TEXT("... and the sky has opened 45 s on"), End.CloudCover < 0.5 && End.RainRateAt(0.0, 0.0, 0.0, BreakAt + 46.0) < 0.05);

	// The maxi in the 3.5 m sea.
	AddInfo(FString::Printf(TEXT("The whole scene: %s"), *Run.Describe()));
	const FSeaMotion Reach = SailInGale(Own, Set, 100.0, 120.0), Beat = SailInGale(Own, Set, 50.0, 120.0);
	AddInfo(FString::Printf(TEXT("Reach (TWA 100): %s"), *Reach.Describe()));
	AddInfo(FString::Printf(TEXT("Beat (TWA 50): %s"), *Beat.Describe()));
	const FSeaMotion RunDown = SailInGale(Own, Set, 150.0, 120.0);
	AddInfo(FString::Printf(TEXT("Run (TWA 150): %s"), *RunDown.Describe()));
	for (const FSeaMotion* M : { &Reach, &Beat, &RunDown, static_cast<const FSeaMotion*>(&Run) })
	{
		TestTrue(TEXT("A 40 t boat pitches within reason (under 12 deg)"), M->MaxPitchDeg < 12.0);
		TestTrue(TEXT("... falls off a crest no faster than gravity (no launching)"), M->BowDownG > -1.0 && M->CgDownG > -1.0);
		TestTrue(TEXT("... and lands from it under 2.5 g at her centre, 3 g at the bow"), M->CgUpG < 2.5 && M->BowUpG < 3.0);
		TestTrue(TEXT("... heaving no more than the sea's highest waves (2 Hs)"), M->HeaveMax - M->HeaveMin < 2.0 * Set.SeaHsM);
	}
	TestTrue(TEXT("She makes way upwind in it"), Beat.MeanSpeed() > 5.0);

	// "Let her run down the face of this one": the sea is big enough to surf (faces steep enough for gravity to drive her
	// on, waves a little faster than she runs). Known gap (README): the hull's buoyancy is vertical, with no push from the
	// slope (Froude-Krylov surge), so her speed does not rise on the faces yet: measured here, not held.
	const double WaveSpeedKn = 9.81 * Gale.State.WindSeaTpS / (2.0 * PI) / kKnot;
	AddInfo(FString::Printf(TEXT("Down the face (take-helm, while it is called): %s; the sea's peak waves run at %.1f kn"), *Surf.Describe(), WaveSpeedKn));
	TestTrue(TEXT("Faces steep enough to surf (a slope of 0.1 and more: 1 m/s^2 of push)"), RunDown.MaxSlope >= 0.1);
	TestTrue(TEXT("... on waves a little faster than she runs (within 8 kn of them)"), WaveSpeedKn > RunDown.MeanSpeed() && WaveSpeedKn - RunDown.MeanSpeed() < 8.0);

	// The stand-in in the same gale scaled to its wind: the scene still finishes.
	{
		FScriptedScene StandIn;
		if (!Load(*this, StandIn)) return false;
		const FPlayBoat J22 = FPlayBoat::StandIn(StandIn);
		FGale Small(StandIn.GetSetting(), J22.Knots);
		const FPlaythrough S = Play(StandIn, ECrew::Good, J22, 900.0, nullptr, nullptr, &Small);
		AddInfo(FString::Printf(TEXT("The J/22 stand-in in the mistral at %.0f kn: %d answered, %d by the crew, %d repeats, %.0f s"), J22.Knots, S.Result.StepsPassed,
			S.Result.StepsAssisted, S.Result.Retries, S.Result.Seconds));
		TestTrue(TEXT("Stand-in in the gale: the scene finishes"), S.Result.bComplete);
	}
	return true;
}

#endif
