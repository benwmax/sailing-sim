#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "SailingMath.h"
#include "ScriptedScene.h"
#include "Wind.h"
#include "SailingGameMode.h"
#include "Career.h"
#include "SailSave.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "FirstJobPlayer.h"
#include "UI/SailFrontEnd.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// #402 (docs/first-launch/): the first job, a guided first sail in the J/22 on Ray Hubbard. Played headless: a player
// who answers every call gets through all six steps with none done for them, in a few minutes; one who answers
// nothing still reaches the end (the instructor does each step after the repeats), so the job never fails.
namespace FirstLaunchTestsLocal
{
	constexpr EAutomationTestFlags FirstLaunchFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	using FirstJobPlayer::FJobRun;
	using FirstJobPlayer::Play;
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
	// The PC's soak: by design (docs/first-launch: "never a fail", the instructor does a step after its tries) a player who
	// touches nothing still finishes the job, in minutes; the session log's line says how long from the job's start and
	// how many steps were done for them (it used to print only the hand-off's 6 s timer, read as the job's time).
	TestTrue(TEXT("... in minutes on the sim clock, from the job's start"), Silent.Result.Seconds > 60.0 && Silent.Result.Seconds < 1200.0);
	const FString Line = UTF8_TO_TCHAR(SceneResultSummary(Silent.Result).c_str());
	AddInfo(Line);
	TestTrue(TEXT("The log line times the whole job"), Line.StartsWith(FString::Printf(TEXT("first-job done in %.0f s: "), Silent.Result.Seconds)));
	TestTrue(TEXT("... and counts the steps done for the player"), Line.Contains(FString::Printf(TEXT("%d done for the player"), Silent.Result.StepsAssisted)));
	return true;
}

/**
 * #402 wiring without a world: a new save opens on the first-launch screen and its record round-trips; every Career lesson
 * sails straight from its row in its own conditions, traffic off, on the tier's boat, the drill it names; the first job's
 * scene id is never saved, so Continue sails freely.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUIFirstLaunchTest, "SailingSim.UI.FirstLaunch", FirstLaunchTestsLocal::FirstLaunchFlags)
bool FSailingUIFirstLaunchTest::RunTest(const FString&)
{
	FSailSave Fresh;
	TestFalse(TEXT("A new save has not seen the first launch (it opens on it)"), Fresh.Progress.FirstLaunch.bSeen);
	TestFalse(TEXT("... and writes no firstLaunch record"), Fresh.ToJson().Contains(TEXT("firstLaunch")));
	FSailSave Seen = Fresh;
	Seen.Progress.FirstLaunch.bSeen = true;
	Seen.Progress.FirstLaunch.At = FDateTime(2026, 11, 1, 3, 0, 0);
	FSailSave Back;
	TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Seen.ToJson(), Back)), int32(FSailSave::EResult::Ok));
	TestTrue(TEXT("... seen, not skipped"), Back.Progress.FirstLaunch.bSeen && !Back.Progress.FirstLaunch.bSkipped);

	const FCareerContent& Content = FCareerContent::Get();
	int32 Lessons = 0;
	for (const FCareerTier& T : Content.Tiers)
	{
		for (const FCareerLesson& L : T.Lessons)
		{
			++Lessons;
			const FSailSessionConfig C = USailSessionSubsystem::MakeLesson(T.WorldId, T.Boats.Num() ? T.Boats[0] : FString(TEXT("J22")), int32(L.Drill) - 1, L.Conditions, L.Traffic);
			const FString What = L.Id;
			TestEqual(*(What + TEXT(": a drill session")), int32(C.Mode), int32(ESailMode::Drill));
			TestEqual(*(What + TEXT(": its drill")), C.DrillIndex, int32(L.Drill) - 1);
			TestEqual(*(What + TEXT(": the tier's world")), FSailSave::WorldId(C.World), T.WorldId);
			if (T.Boats.Num()) TestEqual(*(What + TEXT(": the tier's first boat")), FSailSave::BoatId(C.Boat), T.Boats[0]);
			TestEqual(*(What + TEXT(": its traffic")), C.Traffic, L.Traffic);
			TestEqual(*(What + TEXT(": its conditions")), C.Conditions.PresetId, FName(*L.Conditions));
			TestTrue(*(What + TEXT(": Learning mode, Career")), C.bLearningMode && !C.bFreeSail);
			TestTrue(*(What + TEXT(": no scene")), C.SceneId.IsEmpty());
		}
	}
	TestTrue(TEXT("Day Sailor and Club Racer's lessons checked"), Lessons >= 10);
	const FCareerTier* Day = Content.Tier(TEXT("day-sailor"));
	if (TestNotNull(TEXT("Day Sailor"), Day))
	{
		TestTrue(TEXT("Its lessons sail with traffic off by default"), !Day->Lessons.ContainsByPredicate([](const FCareerLesson& L) { return L.Traffic != 0; }));
		TestEqual(TEXT("The first job hands over to Leave the dock"), int32(Day->Lessons[0].Drill), int32(ESailingDrill::LeaveTheDock));
	}

	// The Career screen's starting focus (#439, the PC's checklist run of 5382a5f2): while the first job waits, its card has
	// the focus, so Enter starts the first job and doesn't skip it for Leave the dock.
	{
		using EFocus = SSailFrontEnd::ECareerFocus;
		FSailSave::FProgress P;
		TestFalse(TEXT("A save that never saw the first launch shows no First job card"), SSailFrontEnd::ShowsFirstJob(P));
		TestTrue(TEXT("... and starts on the next lesson"), SSailFrontEnd::CareerFocus(P, false) == EFocus::NextLesson);
		P.FirstLaunch.bSeen = true;
		P.FirstLaunch.bSkipped = true;
		TestTrue(TEXT("Skipped: the First job card shows"), SSailFrontEnd::ShowsFirstJob(P));
		TestTrue(TEXT("... and has the focus, not Leave the dock"), SSailFrontEnd::CareerFocus(P, false) == EFocus::FirstJob);
		TestTrue(TEXT("... until the player picks a tier"), SSailFrontEnd::CareerFocus(P, true) == EFocus::TierCard);
		// #599: once a lesson has been sailed, the next lesson has the focus (the card stays, Not sailed).
		FSailSave::FProgress Sailed = P;
		FSailSave::FLessonRecord L1;
		L1.Id = TEXT("day-sailor.leave-the-dock");
		L1.Medal = TEXT("silver");
		Sailed.Lessons.Add(L1);
		TestTrue(TEXT("A lesson sailed: the card still shows"), SSailFrontEnd::ShowsFirstJob(Sailed));
		TestTrue(TEXT("... but the next lesson has the focus"), SSailFrontEnd::CareerFocus(Sailed, false) == EFocus::NextLesson);
		FSailSave::FSceneRecord Done;
		Done.Id = TEXT("first-job");
		Done.bDone = true;
		P.Scenes.Add(Done);
		TestFalse(TEXT("The first job finished: no card"), SSailFrontEnd::ShowsFirstJob(P));
		TestTrue(TEXT("... and focus on the next lesson again"), SSailFrontEnd::CareerFocus(P, false) == EFocus::NextLesson);
	}

	// The first job's session: its scene id goes into the save's last session (#599: Continue resumes it until it is done);
	// any other scene's never does.
	FSailSessionConfig Job = USailSessionSubsystem::MakeDefault();
	Job.SceneId = TEXT("first-job");
	USailingSettings* Settings = NewObject<USailingSettings>();
	USailSessionSave* Session = NewObject<USailSessionSave>();
	Session->bHasLast = true;
	Session->Last = Job;
	FSailSave WithLast;
	WithLast.Capture(*Settings, *Session);
	TestTrue(TEXT("The last session is captured"), WithLast.bHasLast);
	TestTrue(TEXT("... with the first job's scene"), WithLast.ToJson().Contains(TEXT("first-job")));
	FSailSave ReadBack;
	TestEqual(TEXT("... which reads back"), int32(FSailSave::FromJson(WithLast.ToJson(), ReadBack)), int32(FSailSave::EResult::Ok));
	USailingSettings* Settings2 = NewObject<USailingSettings>();
	USailSessionSave* Session2 = NewObject<USailSessionSave>();
	ReadBack.Apply(*Settings2, *Session2);
	FSailSave::FProgress NewPlayer;
	NewPlayer.FirstLaunch.bSeen = true;
	TestTrue(TEXT("Continue resumes the first job while it isn't done"), SSailFrontEnd::ResumesFirstJob(Session2->Last, NewPlayer));
	FSailSave::FSceneRecord Finished;
	Finished.Id = TEXT("first-job");
	Finished.bDone = true;
	NewPlayer.Scenes.Add(Finished);
	TestFalse(TEXT("... and sails freely once it is"), SSailFrontEnd::ResumesFirstJob(Session2->Last, NewPlayer));
	FSailSessionConfig Other = Job;
	Other.SceneId = TEXT("prologue");
	Session->Last = Other;
	FSailSave WithOther;
	WithOther.Capture(*Settings, *Session);
	TestFalse(TEXT("Another scene never goes into the save"), WithOther.ToJson().Contains(TEXT("prologue")));
	return true;
}

#endif
