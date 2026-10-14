#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "Drills.h"
#include "Learning.h"

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags LearningFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

/**
 * Graphics G7: the learning content in Content/Learning (from Inputs/drills) against the game. Every briefing names a
 * drill, has the drill's steps in the same order with the same wording, and debrief lines for the drill's outcomes;
 * every tip keys on an event the detector fires and every key token resolves; every question has a valid answer and
 * each drill has enough questions for its quiz.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingLearningContentTest, "SailingSim.Drills.LearningContent", LearningFlags)
bool FSailingLearningContentTest::RunTest(const FString& Parameters)
{
	FLearningContent Content;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("Loads %s (%s)"), *FLearningContent::Dir(), *Error), Content.Load(FLearningContent::Dir(), &Error))) return false;
	AddInfo(FString::Printf(TEXT("%d briefings, %d events, %d tips, %d questions"), Content.Briefings.Num(), Content.Events.Num(), Content.Tips.Num(), Content.Questions.Num()));

	TSet<ESailingDrill> Seen;
	for (const FDrillBriefing& B : Content.Briefings)
	{
		if (!TestTrue(FString::Printf(TEXT("%s is a drill"), *B.Id), B.Drill != ESailingDrill::None)) continue;
		Seen.Add(B.Drill);
		TestEqual(FString::Printf(TEXT("%s name"), *B.Id), B.Name, FString(DrillName(B.Drill)));
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, 0.0, 2.0 * kKnot);
		FDrillRunner Runner;
		Runner.Start(B.Drill, Boat, 0.0);
		const TArray<FString>& Steps = Runner.GetSteps();
		if (TestEqual(FString::Printf(TEXT("%s step count"), *B.Id), B.Steps.Num(), Steps.Num()))
		{
			for (int32 I = 0; I < Steps.Num(); ++I)
			{
				TestEqual(FString::Printf(TEXT("%s step %d matches Drills.cpp"), *B.Id, I + 1), B.Steps[I].SimText, Steps[I]);
				TestFalse(FString::Printf(TEXT("%s step %d has a coach line"), *B.Id, I + 1), B.Steps[I].Coach.IsEmpty());
				FString Bad;
				TestTrue(FString::Printf(TEXT("%s step %d keys resolve (%s)"), *B.Id, I + 1, *Bad), FLearningContent::KeysResolve(B.Steps[I].Text + B.Steps[I].Coach, &Bad));
			}
		}
		for (const FString& Outcome : FDrillRunner::Outcomes(B.Drill))
		{
			TestTrue(FString::Printf(TEXT("%s has a debrief for '%s'"), *B.Id, *Outcome), B.Debrief.Contains(Outcome));
		}
		for (const TPair<FString, FString>& D : B.Debrief)
		{
			TestTrue(FString::Printf(TEXT("%s debrief '%s' is an outcome"), *B.Id, *D.Key), FDrillRunner::Outcomes(B.Drill).Contains(D.Key));
		}
		int32 Available = 0;
		for (const FQuizQuestion& Q : Content.Questions) Available += Q.Drills.Num() == 0 || Q.Drills.Contains(B.Drill);
		TestTrue(FString::Printf(TEXT("%s: %d questions for a quiz of %d"), *B.Id, Available, B.QuizAfter), B.QuizAfter > 0 && Available >= B.QuizAfter);
		FRandomStream Rng(7);
		const TArray<FQuizQuestion> Quiz = Content.MakeQuiz(B.Drill, Rng);
		TestEqual(FString::Printf(TEXT("%s quiz length"), *B.Id), Quiz.Num(), B.QuizAfter);
		for (const FQuizQuestion& Q : Quiz) TestTrue(FString::Printf(TEXT("%s shuffled answer kept"), *Q.Id), Q.Options.IsValidIndex(Q.Answer));
	}
	TestEqual(TEXT("A briefing for every drill"), Seen.Num(), int32(ESailingDrill::Count) - 1);

	// The crew-overboard pick-up: into the wind, either side (Bean, Oct 14 2026).
	{
		FBoatModel Boat;
		FDrillRunner Runner;
		Runner.Start(ESailingDrill::CrewOverboardFigureEight, Boat, 0.0);
		const FString Last = Runner.GetSteps().Last();
		TestTrue(TEXT("Figure-eight stops by turning into the wind"), Last.Contains(TEXT("into the wind")));
		TestFalse(TEXT("Figure-eight names no pick-up side"), Last.Contains(TEXT("windward of")) || Last.Contains(TEXT("leeward of")));
	}

	const TArray<FString>& Known = FLearningEvents::Known();
	for (const FLearningTip& T : Content.Tips)
	{
		TestTrue(FString::Printf(TEXT("Tip %s: event %s is in the event table"), *T.Id, *T.Event), Content.Events.Contains(T.Event));
		TestTrue(FString::Printf(TEXT("Tip %s: event %s is detected"), *T.Id, *T.Event), Known.Contains(T.Event));
		TestTrue(FString::Printf(TEXT("Tip %s fits the tip card"), *T.Id), T.Text.Len() <= 240);
		FString Bad;
		TestTrue(FString::Printf(TEXT("Tip %s keys resolve (%s)"), *T.Id, *Bad), FLearningContent::KeysResolve(T.Text, &Bad));
		TestFalse(FString::Printf(TEXT("Tip %s has no key token left after resolving"), *T.Id), FLearningContent::ResolveKeys(T.Text).Contains(TEXT("{key:")));
	}
	for (const TPair<FString, FString>& E : Content.Events) TestTrue(FString::Printf(TEXT("Event %s is detected"), *E.Key), Known.Contains(E.Key));
	for (const FQuizQuestion& Q : Content.Questions)
	{
		TestTrue(FString::Printf(TEXT("Question %s has four options and a valid answer"), *Q.Id), Q.Options.Num() == 4 && Q.Options.IsValidIndex(Q.Answer));
	}
	const FString Debrief = Content.Debrief(ESailingDrill::ReturnAndDock, TEXT("hard"), 125.0, 2.34);
	TestTrue(TEXT("Debrief fills {contact_kn}"), Debrief.Contains(TEXT("2.3")) && !Debrief.Contains(TEXT("{")));
	return true;
}

/** The event detector and the coach on scripted frames: a tack, irons, a fast crew-overboard approach, a stand-on call. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingLearningEventsTest, "SailingSim.Drills.LearningEvents", LearningFlags)
bool FSailingLearningEventsTest::RunTest(const FString& Parameters)
{
	FLearningContent Content;
	if (!TestTrue(TEXT("Content loads"), Content.Load(FLearningContent::Dir()))) return false;
	FLearningEvents Events;
	TSet<FString> Fired;
	FLearningFrame F;
	F.TwsKnots = 10.0;
	F.Knots = 4.0;
	auto Run = [&](double Seconds, TFunctionRef<void(double)> Set)
	{
		for (double T = 0.0; T < Seconds; T += 0.05)
		{
			Set(T);
			F.Time += 0.05;
			TArray<FString> Out;
			Events.Update(F, Out);
			for (const FString& E : Out) Fired.Add(E);
		}
	};
	// Close-hauled on starboard, then the tiller to leeward through head to wind onto port.
	Run(5.0, [&](double) { F.TwaDeg = 45.0; F.Tiller = 0.0; });
	Run(4.0, [&](double T) { F.TwaDeg = 45.0 - T * 22.5; F.Tiller = F.TwaDeg > 0.0 ? 0.5 : -0.5; F.Knots = 4.0 - T * 0.5; });
	Run(3.0, [&](double) { F.TwaDeg = -45.0; F.Tiller = 0.0; F.Knots = 3.5; });
	TestTrue(TEXT("tack.start"), Fired.Contains(TEXT("tack.start")));
	TestTrue(TEXT("tack.complete"), Fired.Contains(TEXT("tack.complete")));
	TestFalse(TEXT("No jibe in a tack"), Fired.Contains(TEXT("jibe.complete")));
	// In irons.
	Run(6.0, [&](double) { F.TwaDeg = -5.0; F.bInIrons = true; F.Knots = 0.2; });
	Run(1.0, [&](double) { F.TwaDeg = -50.0; F.bInIrons = false; F.Knots = 1.5; });
	TestTrue(TEXT("irons"), Fired.Contains(TEXT("irons")));
	TestTrue(TEXT("irons.escaped"), Fired.Contains(TEXT("irons.escaped")));
	// Crew overboard: too fast near the person.
	F.Drill = ESailingDrill::CrewOverboardFigureEight;
	F.bDrillActive = true;
	Run(2.0, [&](double T) { F.DummyDistance = 14.0 - T; F.Knots = 4.0; F.TwaDeg = -70.0; });
	TestTrue(TEXT("cob.start"), Fired.Contains(TEXT("cob.start")));
	TestTrue(TEXT("cob.fast_approach"), Fired.Contains(TEXT("cob.fast_approach")));
	// Starboard tack boat to leeward of us on port: we give way.
	F.Drill = ESailingDrill::None;
	F.bDrillActive = false;
	F.DummyDistance = -1.0;
	Run(1.0, [&](double) { F.bAdvice = true; F.Encounter = EEncounter::SailingVessels; F.PlayerTack = -1; F.OtherTack = 1; F.bGiveWay = true; F.bStandOn = false; });
	TestTrue(TEXT("rules.port_starboard.give_way"), Fired.Contains(TEXT("rules.port_starboard.give_way")));

	// The coach: a drill's own tip beats an Any tip on the same event, and cooldowns hold.
	FLearningCoach Coach;
	FLearningFrame C;
	C.Drill = ESailingDrill::CrewOverboardQuickStop;
	C.bDrillActive = true;
	C.DummyDistance = 12.0;
	C.Knots = 3.0;
	C.TwaDeg = 60.0;
	C.TwsKnots = 10.0;
	for (int32 I = 0; I < 20; ++I) { C.Time += 0.05; Coach.Update(C, Content); }
	const FLearningTip* Tip = Coach.Current(C.Time);
	if (TestNotNull(TEXT("A tip on a fast approach"), Tip))
	{
		AddInfo(FString::Printf(TEXT("%s: %s"), *Tip->Id, *Coach.CurrentText()));
		bool bDrillTipExists = false;
		for (const FLearningTip& T : Content.Tips) bDrillTipExists |= T.Drills.Contains(C.Drill) && (T.Event == TEXT("cob.fast_approach") || T.Event == TEXT("cob.start"));
		if (bDrillTipExists) TestTrue(TEXT("The drill's own tip wins"), Tip->Drills.Contains(C.Drill));
		TestFalse(TEXT("Keys resolved in the shown text"), Coach.CurrentText().Contains(TEXT("{key:")));
	}
	return true;
}
