#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "Drills.h"
#include "Learning.h"
#include "Internationalization/Regex.h"

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

/**
 * #433-#435: on a boat with no jib (the Sunfish) the drills, briefings, quizzes and tips use the dinghy wording, and the
 * jib drills are not offered. The dinghy briefings match the runner's steps on the Sunfish, and nothing a Sunfish sailor
 * reads or is asked mentions a jib, a crew, a keel or the J/22.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingDinghyContentTest, "SailingSim.Drills.DinghyContent", LearningFlags)
bool FSailingDinghyContentTest::RunTest(const FString& Parameters)
{
	FLearningContent Content;
	if (!TestTrue(TEXT("Content loads"), Content.Load(FLearningContent::Dir()))) return false;
	const FBoatConfig Sunfish = FBoatConfig::Make(EBoatType::Sunfish);
	const FBoatConfig J22;
	TestTrue(TEXT("The Sunfish sails as a dinghy"), FDrillRunner::IsDinghy(Sunfish));
	TestFalse(TEXT("The J/22 does not"), FDrillRunner::IsDinghy(J22));
	const FRegexPattern Keelboat(TEXT("\\b(jib|J/22|keelboat|keel|crew|outboard|fenders?|lifelines?|winch)\\b"), ERegexPatternFlags::CaseInsensitive);
	auto Says = [&Keelboat](const FString& Text)
	{
		// "Crew overboard!" is the call itself, said on any boat.
		FRegexMatcher M(Keelboat, Text.Replace(TEXT("Crew overboard"), TEXT("")).Replace(TEXT("crew-overboard"), TEXT("")));
		return M.FindNext() ? M.GetCaptureGroup(0) : FString();
	};
	int32 Offered = 0;
	for (int32 I = 1; I < int32(ESailingDrill::Count); ++I)
	{
		const ESailingDrill Drill = ESailingDrill(I);
		TestTrue(FString::Printf(TEXT("The J/22 sails %s"), DrillName(Drill)), FDrillRunner::CanSail(Drill, J22));
		if (!FDrillRunner::CanSail(Drill, Sunfish)) continue;
		++Offered;
		FBoatModel Boat(Sunfish);
		Boat.Reset(0.0, 0.0, 0.0, 2.0 * kKnot);
		FDrillRunner Runner;
		Runner.Start(Drill, Boat, 0.0);
		TestTrue(FString::Printf(TEXT("%s on the Sunfish is a dinghy run"), DrillName(Drill)), Runner.IsDinghyRun());
		const FDrillBriefing* B = Content.Briefing(Drill, true);
		if (!TestNotNull(FString::Printf(TEXT("%s has a briefing"), DrillName(Drill)), B)) continue;
		TestTrue(FString::Printf(TEXT("%s has its own dinghy briefing"), DrillName(Drill)), B != Content.Briefing(Drill));
		if (TestEqual(FString::Printf(TEXT("%s dinghy step count"), DrillName(Drill)), B->Steps.Num(), Runner.GetSteps().Num()))
		{
			for (int32 S = 0; S < B->Steps.Num(); ++S)
			{
				TestEqual(FString::Printf(TEXT("%s dinghy step %d matches the runner"), DrillName(Drill), S + 1), B->Steps[S].SimText, Runner.GetSteps()[S]);
				FString Bad;
				TestTrue(FString::Printf(TEXT("%s dinghy step %d keys resolve (%s)"), DrillName(Drill), S + 1, *Bad), FLearningContent::KeysResolve(B->Steps[S].Text + B->Steps[S].Coach, &Bad));
			}
		}
		for (const FString& Outcome : FDrillRunner::Outcomes(Drill)) TestTrue(FString::Printf(TEXT("%s dinghy debrief for '%s'"), DrillName(Drill), *Outcome), B->Debrief.Contains(Outcome));
		// Everything the Sunfish sailor reads for the drill.
		TArray<FString> Read = { B->Goal, B->Why, B->Setup, B->LakeNotes, Runner.GetStatus() };
		Read.Append(Runner.GetSteps());
		Read.Append(B->Good);
		for (const FDrillBriefing::FCommand& C : B->Commands) Read.Append({ C.Call, C.Reply, C.Meaning });
		for (const FDrillBriefing::FStep& S : B->Steps) Read.Append({ S.Text, S.Coach });
		for (const TPair<FString, FString>& M : B->Mistakes) Read.Append({ M.Key, M.Value });
		for (const TPair<FString, FString>& D : B->Debrief) Read.Add(D.Value);
		for (const FString& Line : Read)
		{
			const FString Word = Says(Line);
			TestTrue(FString::Printf(TEXT("%s dinghy text says no '%s': %s"), DrillName(Drill), *Word, *Line), Word.IsEmpty());
		}
		// The quiz: the full length, no keelboat question, nothing that leans on a jib or a crew.
		for (int32 Seed = 1; Seed <= 20; ++Seed)
		{
			FRandomStream Rng(Seed);
			const TArray<FQuizQuestion> Quiz = Content.MakeQuiz(Drill, Rng, true);
			TestEqual(FString::Printf(TEXT("%s dinghy quiz length"), DrillName(Drill)), Quiz.Num(), B->QuizAfter);
			for (const FQuizQuestion& Q : Quiz)
			{
				TestNotEqual(FString::Printf(TEXT("%s asked on a dinghy"), *Q.Id), Q.Class, FString(TEXT("keelboat")));
				const FString Word = Says(Q.Question + TEXT(" ") + Q.Options[Q.Answer]);
				TestTrue(FString::Printf(TEXT("%s on a dinghy says no '%s'"), *Q.Id, *Word), Q.Class == TEXT("dinghy") || Word.IsEmpty());
			}
		}
		FRandomStream Rng(3);
		for (const FQuizQuestion& Q : Content.MakeQuiz(Drill, Rng, false)) TestNotEqual(FString::Printf(TEXT("%s asked on the J/22"), *Q.Id), Q.Class, FString(TEXT("dinghy")));
	}
	TestEqual(TEXT("A dinghy is offered four drills"), Offered, 4);
	TestFalse(TEXT("No heave to on the Sunfish"), FDrillRunner::CanSail(ESailingDrill::HeaveTo, Sunfish));
	TestFalse(TEXT("No figure-eight on the Sunfish"), FDrillRunner::CanSail(ESailingDrill::CrewOverboardFigureEight, Sunfish));
	// The J/22 keeps her own wording.
	{
		FBoatModel Boat;
		FDrillRunner Runner;
		Runner.Start(ESailingDrill::CrewOverboardQuickStop, Boat, 0.0);
		TestFalse(TEXT("The J/22 run is not a dinghy run"), Runner.IsDinghyRun());
		TestTrue(TEXT("The J/22 quick-stop keeps the jib backed"), Runner.GetSteps()[1].Contains(TEXT("jib")));
	}
	// Tips: on a dinghy no keelboat tip is shown, and every keelboat tip with a twin has a dinghy one for its event.
	for (const FLearningTip& T : Content.Tips)
	{
		if (T.Class.IsEmpty() && T.Fits(ESailingDrill::SailATriangle))
		{
			const FString Word = Says(T.Text);
			TestTrue(FString::Printf(TEXT("Tip %s, shown on any boat, says no '%s'"), *T.Id, *Word), Word.IsEmpty());
		}
		TestTrue(FString::Printf(TEXT("Tip %s has a known class"), *T.Id), T.Class.IsEmpty() || T.Class == TEXT("keelboat") || T.Class == TEXT("dinghy"));
	}
	FLearningCoach Coach;
	FLearningFrame F;
	F.bDinghy = true;
	F.Drill = ESailingDrill::CrewOverboardQuickStop;
	F.bDrillActive = true;
	F.DummyDistance = 8.0;
	F.TwsKnots = 10.0;
	F.Knots = 3.0;
	for (int32 I = 0; I < 200; ++I)
	{
		F.Time = I * 0.05;
		Coach.Update(F, Content);
		if (const FLearningTip* T = Coach.Current(F.Time)) TestNotEqual(FString::Printf(TEXT("Tip %s shown on a dinghy"), *T->Id), T->Class, FString(TEXT("keelboat")));
	}
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
