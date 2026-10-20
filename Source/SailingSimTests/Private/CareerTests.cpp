#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "Career.h"
#include "Drills.h"
#include "FixedStepper.h"
#include "Learning.h"
#include "SailSave.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "Wind.h"

using namespace Sailing;

// The learn-to-sail career (docs/career/README.md): the content against the game, medal grading, the checkride and its
// certificate, what is open, the save round trip, and a whole Day Sailor tier played through in logic.
namespace CareerTestsLocal
{
	constexpr EAutomationTestFlags CareerFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	const TCHAR* const Lake = TEXT("ray-hubbard");

	const FCareerContent* Load(FAutomationTestBase& Test)
	{
		static FCareerContent Content;
		FString Error;
		if (!Test.TestTrue(FString::Printf(TEXT("Loads %s (%s)"), *FCareerContent::Dir(), *Error), Content.Load(FCareerContent::Dir(), &Error))) return nullptr;
		return &Content;
	}

	/** A finished run of a lesson's drill on the lake in the J/22. */
	FCareerRun Run(ESailingDrill Drill, const FString& Outcome, double Seconds, int32 Collisions = 0, int32 Infractions = 0, double ContactKn = 0.0)
	{
		FCareerRun R;
		R.Drill = Drill;
		R.bComplete = true;
		R.Outcome = Outcome;
		R.Seconds = Seconds;
		R.Collisions = Collisions;
		R.Infractions = Infractions;
		R.MaxContactKnots = ContactKn;
		R.WorldId = Lake;
		R.BoatId = TEXT("J22");
		return R;
	}

	/** The outcome that earns a medal in each drill (the first one FDrillRunner lists). */
	FString GoodOutcome(ESailingDrill Drill) { return FDrillRunner::Outcomes(Drill)[0]; }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerContentTest, "SailingSim.Career.Content", CareerTestsLocal::CareerFlags)
bool FSailingCareerContentTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	const FLearningContent& Learning = FLearningContent::Get();
	for (const FString& Bad : C->Validate(Learning)) AddError(Bad);
	TArray<FString> Ids;
	for (const FCareerTier& T : C->Tiers) Ids.Add(T.Id);
	TestEqual(TEXT("Four tiers in order"), Ids, TArray<FString>{ TEXT("day-sailor"), TEXT("club-racer"), TEXT("coastal-cruiser"), TEXT("passage-maker") });
	const FCareerTier* Day = C->Tier(TEXT("day-sailor"));
	if (!TestNotNull(TEXT("Day Sailor"), Day)) return false;
	TestTrue(TEXT("Day Sailor is ready"), Day->IsReady());
	TestEqual(TEXT("Day Sailor on the lake"), Day->WorldId, FString(Lake));
	TestEqual(TEXT("Day Sailor certificate"), Day->CertificateName, FString(TEXT("Day Sailor certificate")));
	TSet<ESailingDrill> Drills;
	for (const FCareerLesson& L : Day->Lessons)
	{
		Drills.Add(L.Drill);
		TestTrue(FString::Printf(TEXT("%s: drill resolves"), *L.Id), Learning.Briefing(L.Drill) != nullptr);
		TestTrue(FString::Printf(TEXT("%s: quiz resolves"), *L.Id), Learning.Briefing(L.QuizDrill) && Learning.Briefing(L.QuizDrill)->QuizAfter > 0);
		FRandomStream Rng(5);
		TestTrue(FString::Printf(TEXT("%s: its quiz has questions"), *L.Id), Learning.MakeQuiz(L.QuizDrill, Rng).Num() > 0);
	}
	TestEqual(TEXT("The six drills are the six lessons"), Drills.Num(), int32(ESailingDrill::Count) - 1);
	for (const FCareerTier& T : C->Tiers)
	{
		TestFalse(FString::Printf(TEXT("%s has a name and a certificate"), *T.Id), T.Name.IsEmpty() || T.CertificateId.IsEmpty() || T.CertificateName.IsEmpty());
		TestFalse(FString::Printf(TEXT("%s: no ASA in the names"), *T.Id), T.Name.Contains(TEXT("ASA")) || T.CertificateName.Contains(TEXT("ASA")));
		if (T.Id != Day->Id && T.Id != TEXT("club-racer")) TestEqual(FString::Printf(TEXT("%s is a stub"), *T.Id), T.Status, FString(TEXT("stub")));
	}
	// Club Racer: the Sunfish's dinghy lessons (the Free Sail job), sailed in the tier's first boat.
	if (const FCareerTier* Club = C->Tier(TEXT("club-racer")))
	{
		TestTrue(TEXT("Club Racer is ready"), Club->IsReady() && Club->Lessons.Num() == 4);
		TestTrue(TEXT("... in the Sunfish first"), Club->Boats.Num() > 0 && Club->Boats[0] == TEXT("Sunfish"));
		TestTrue(TEXT("... its certificate opens the ILCA 7"), Club->Unlocks.Boats.Contains(TEXT("ILCA7")));
		FRandomStream ClubRng(3);
		TestEqual(TEXT("... its checkride quiz length"), C->MakeCheckrideQuiz(*Club, Learning, ClubRng).Num(), Club->Checkride.Quiz.Questions);
		for (const FCareerLesson& L : Club->Lessons) TestFalse(FString::Printf(TEXT("%s: no ASA in the title"), *L.Id), L.Title.Contains(TEXT("ASA")) || L.Title.Contains(TEXT("Rush Creek")));
	}
	FRandomStream Rng(11);
	const TArray<FQuizQuestion> Ride = C->MakeCheckrideQuiz(*Day, Learning, Rng);
	TestEqual(TEXT("Checkride quiz length"), Ride.Num(), Day->Checkride.Quiz.Questions);
	TSet<FString> Seen;
	for (const FQuizQuestion& Q : Ride)
	{
		TestTrue(FString::Printf(TEXT("%s: the answer is an option"), *Q.Id), Q.Options.IsValidIndex(Q.Answer));
		TestFalse(FString::Printf(TEXT("%s: asked once"), *Q.Id), Seen.Contains(Q.Id));
		Seen.Add(Q.Id);
	}

	// A broken file is caught: gold looser than silver, an unknown drill, boat and unlock.
	FCareerContent Broken;
	const FString Bad = TEXT(R"({"schema_version":1,"always_open":{"tiers":["t"]},"tiers":[{"id":"t","name":"T","status":"ready","world":"ray-hubbard","boats":["Dragon"],
		"lessons":[{"id":"t.a","title":"A","drill":"HeaveTo","quiz":"Nope","quiz_pass":0.5,"medals":{"bronze":{},"silver":{"max_seconds":100},"gold":{"max_seconds":200}}}],
		"checkride":{"id":"t.checkride","lessons":["t.a"],"min_medal":"silver","quiz":{"drills":["HeaveTo"],"questions":3,"pass":0.8}},
		"certificate":{"id":"t","name":"T certificate"},"unlocks":{"tiers":["nowhere"]}}]})");
	if (TestTrue(TEXT("The broken file parses"), Broken.LoadText(Bad)))
	{
		const TArray<FString> Problems = Broken.Validate(Learning);
		AddInfo(FString::Printf(TEXT("Broken file: %s"), *FString::Join(Problems, TEXT("; "))));
		auto Has = [&Problems](const TCHAR* Part) { return Problems.ContainsByPredicate([Part](const FString& P) { return P.Contains(Part); }); };
		TestTrue(TEXT("... gold looser than silver"), Has(TEXT("gold asks less")));
		TestTrue(TEXT("... unknown quiz"), Has(TEXT("quiz Nope")));
		TestTrue(TEXT("... unknown boat"), Has(TEXT("unknown boat Dragon")));
		TestTrue(TEXT("... unknown unlock"), Has(TEXT("unknown tier nowhere")));
	}
	TestFalse(TEXT("A newer schema is refused"), Broken.LoadText(TEXT(R"({"schema_version":2,"tiers":[]})")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerGradingTest, "SailingSim.Career.Grading", CareerTestsLocal::CareerFlags)
bool FSailingCareerGradingTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	const FCareerLesson* Dock = C->Lesson(TEXT("day-sailor.leave-the-dock"));
	const FCareerLesson* Tri = C->Lesson(TEXT("day-sailor.sail-a-triangle"));
	const FCareerLesson* Cob = C->Lesson(TEXT("day-sailor.crew-overboard-quick-stop"));
	const FCareerLesson* Home = C->Lesson(TEXT("day-sailor.return-and-dock"));
	if (!TestTrue(TEXT("Lessons found"), Dock && Tri && Cob && Home)) return false;
	auto Is = [this](const TCHAR* What, const FCareerLesson& L, const FCareerRun& R, ECareerMedal Want)
	{
		TestEqual(What, FCareerContent::MedalName(FCareerContent::Grade(L, R)), FCareerContent::MedalName(Want));
	};
	const ESailingDrill D = ESailingDrill::LeaveTheDock;
	Is(TEXT("Leave the dock: clean, 2:50, no contact: gold"), *Dock, Run(D, TEXT("clean"), 170.0), ECareerMedal::Gold);
	Is(TEXT("... clean at 3:20: silver"), *Dock, Run(D, TEXT("clean"), 200.0), ECareerMedal::Silver);
	Is(TEXT("... clean but a light touch: silver"), *Dock, Run(D, TEXT("clean"), 120.0, 1), ECareerMedal::Silver);
	Is(TEXT("... touched a dock hard: bronze"), *Dock, Run(D, TEXT("contact"), 100.0, 1, 0, 2.0), ECareerMedal::Bronze);
	Is(TEXT("... a rules penalty: bronze"), *Dock, Run(D, TEXT("clean"), 100.0, 0, 1), ECareerMedal::Bronze);
	Is(TEXT("... over 5:00: bronze"), *Dock, Run(D, TEXT("clean"), 301.0), ECareerMedal::Bronze);
	FCareerRun Unfinished = Run(D, FString(), 60.0);
	Unfinished.bComplete = false;
	Is(TEXT("... not finished: no medal"), *Dock, Unfinished, ECareerMedal::None);
	Is(TEXT("... another drill's run: no medal"), *Dock, Run(ESailingDrill::HeaveTo, TEXT("done"), 30.0), ECareerMedal::None);
	// The triangle the autopilot sails in SailingSim.Drills.SailATriangle (4:36) is gold; 6:30 silver; a collision bronze.
	Is(TEXT("Triangle in 4:36: gold"), *Tri, Run(ESailingDrill::SailATriangle, TEXT("done"), 276.0), ECareerMedal::Gold);
	Is(TEXT("Triangle in 6:30: silver"), *Tri, Run(ESailingDrill::SailATriangle, TEXT("done"), 390.0), ECareerMedal::Silver);
	Is(TEXT("Triangle with a collision: bronze"), *Tri, Run(ESailingDrill::SailATriangle, TEXT("done"), 276.0, 1), ECareerMedal::Bronze);
	Is(TEXT("Quick-stop, proper, 0:51: gold"), *Cob, Run(ESailingDrill::CrewOverboardQuickStop, TEXT("proper"), 51.0), ECareerMedal::Gold);
	Is(TEXT("Quick-stop the wrong way: bronze"), *Cob, Run(ESailingDrill::CrewOverboardQuickStop, TEXT("improper"), 51.0), ECareerMedal::Bronze);
	Is(TEXT("Docked gently at 0.4 kn: gold"), *Home, Run(ESailingDrill::ReturnAndDock, TEXT("gentle"), 200.0, 1, 0, 0.4), ECareerMedal::Gold);
	Is(TEXT("Docked gently at 1.2 kn: silver"), *Home, Run(ESailingDrill::ReturnAndDock, TEXT("gentle"), 200.0, 1, 0, 1.2), ECareerMedal::Silver);
	Is(TEXT("Docked hard: bronze"), *Home, Run(ESailingDrill::ReturnAndDock, TEXT("hard"), 200.0, 1, 0, 2.5), ECareerMedal::Bronze);

	// The best medal and time are kept; a worse run changes neither.
	FSailSave::FProgress P;
	FCareerProgress Career(*C, P);
	FCareerProgress::FAward A = Career.RecordRun(Run(D, TEXT("contact"), 150.0, 1, 0, 2.0));
	TestTrue(TEXT("First run: bronze, a new best"), A.IsValid() && A.Medal == ECareerMedal::Bronze && A.bNewBest);
	A = Career.RecordRun(Run(D, TEXT("clean"), 170.0));
	TestTrue(TEXT("Second: gold"), A.Medal == ECareerMedal::Gold && A.Best == ECareerMedal::Gold && A.bNewBest);
	A = Career.RecordRun(Run(D, TEXT("clean"), 260.0));
	TestTrue(TEXT("Third, slower: silver, the best stays gold"), A.Medal == ECareerMedal::Silver && A.Best == ECareerMedal::Gold && !A.bNewBest && !A.bBestTime);
	const FSailSave::FLessonRecord* R = P.FindLesson(Dock->Id);
	TestTrue(TEXT("Kept: gold, best 150 s, three runs"), R && R->Medal == TEXT("gold") && R->BestSeconds == 150.0 && R->Runs == 3);
	// A run in a boat the tier doesn't use counts for no lesson.
	FCareerRun Hobie = Run(D, TEXT("clean"), 100.0);
	Hobie.BoatId = TEXT("Hobie16");
	TestFalse(TEXT("A Hobie run counts for no Day Sailor lesson"), Career.RecordRun(Hobie).IsValid());
	// The lesson's quiz closes it: 1 of 3 fails, 2 of 3 passes.
	TestFalse(TEXT("Quiz 1 of 3 fails"), Career.RecordLessonQuiz(Dock->Id, 1, 3));
	TestFalse(TEXT("... not closed yet"), Career.IsLessonClosed(Dock->Id));
	TestTrue(TEXT("Quiz 2 of 3 passes"), Career.RecordLessonQuiz(Dock->Id, 2, 3));
	TestTrue(TEXT("... closed"), Career.IsLessonClosed(Dock->Id));
	TestTrue(TEXT("Best quiz kept"), R && P.FindLesson(Dock->Id)->QuizBest == 2 && P.FindLesson(Dock->Id)->QuizOf == 3);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerCheckrideTest, "SailingSim.Career.Checkride", CareerTestsLocal::CareerFlags)
bool FSailingCareerCheckrideTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	const FCareerTier& Day = *C->Tier(TEXT("day-sailor"));
	FSailSave::FProgress P;
	FCareerProgress Career(*C, P);
	FString Why;
	TestFalse(TEXT("Not ready with no lessons"), Career.IsCheckrideReady(Day.Id, &Why));
	AddInfo(Why);
	// Five lessons at silver, the last at bronze: not ready, and the quiz can't award the certificate.
	for (int32 I = 0; I < Day.Lessons.Num(); ++I)
	{
		const FCareerLesson& L = Day.Lessons[I];
		const double Silver = L.Medals[1].MaxSeconds;
		const FCareerRun R = I < Day.Lessons.Num() - 1 ? Run(L.Drill, GoodOutcome(L.Drill), Silver - 1.0) : Run(L.Drill, GoodOutcome(L.Drill), Silver + 5.0);
		Career.RecordRun(R);
	}
	TestEqual(TEXT("Five at silver or better"), Career.LessonsAtLeast(Day, ECareerMedal::Silver), 5);
	TestFalse(TEXT("Not ready with one bronze"), Career.IsCheckrideReady(Day.Id, &Why));
	TestEqual(TEXT("... and says why"), Why, FString(TEXT("Earn silver or better in 1 more lesson")));
	TestFalse(TEXT("A perfect quiz before the lessons awards nothing"), Career.RecordCheckrideQuiz(Day.Id, 12, 12, FDateTime(2026, 10, 18)));
	TestFalse(TEXT("No certificate"), Career.HasCertificate(Day.CertificateId));
	// The last lesson at gold: ready.
	const FCareerLesson& Last = Day.Lessons.Last();
	Career.RecordRun(Run(Last.Drill, GoodOutcome(Last.Drill), 60.0));
	TestTrue(TEXT("Ready at silver everywhere"), Career.IsCheckrideReady(Day.Id));
	TestFalse(TEXT("Quiz 9 of 12 (75%) fails"), Career.RecordCheckrideQuiz(Day.Id, 9, 12, FDateTime(2026, 10, 18)));
	TestFalse(TEXT("... no certificate"), Career.HasCertificate(Day.CertificateId));
	TestTrue(TEXT("Quiz 10 of 12 (83%) passes and awards it"), Career.RecordCheckrideQuiz(Day.Id, 10, 12, FDateTime(2026, 10, 18, 12, 0, 0)));
	TestTrue(TEXT("... the Day Sailor certificate"), Career.HasCertificate(TEXT("day-sailor")));
	TestFalse(TEXT("Passing again awards nothing new"), Career.RecordCheckrideQuiz(Day.Id, 12, 12, FDateTime(2026, 10, 19)));
	TestEqual(TEXT("One certificate"), P.Certificates.Num(), 1);
	TestTrue(TEXT("Best checkride score kept"), P.FindCheckride(Day.Checkride.Id) && P.FindCheckride(Day.Checkride.Id)->QuizBest == 12 && P.FindCheckride(Day.Checkride.Id)->bPassed);
	TestEqual(TEXT("Earned when it was passed"), P.Certificates[0].EarnedAt, FDateTime(2026, 10, 18, 12, 0, 0));
	// Club Racer is open now but none of its Sunfish lessons is sailed; a stub tier has no checkride at all.
	TestFalse(TEXT("Club Racer: not ready without its lessons"), Career.IsCheckrideReady(TEXT("club-racer"), &Why));
	AddInfo(FString::Printf(TEXT("Club Racer: %s"), *Why));
	TestFalse(TEXT("Coastal Cruiser (a stub): no checkride yet"), Career.IsCheckrideReady(TEXT("coastal-cruiser"), &Why));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerUnlocksTest, "SailingSim.Career.Unlocks", CareerTestsLocal::CareerFlags)
bool FSailingCareerUnlocksTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	FSailSave::FProgress P;
	FCareerProgress Career(*C, P);
	// A new sailor: the lake and the J/22.
	TestTrue(TEXT("The lake is open"), Career.IsWorldOpen(Lake));
	TestFalse(TEXT("Galveston is locked"), Career.IsWorldOpen(TEXT("galveston-bay")));
	TestEqual(TEXT("... until the Day Sailor certificate"), Career.WorldLockReason(TEXT("galveston-bay")), FString(TEXT("Earn the Day Sailor certificate")));
	TestEqual(TEXT("The Gulf: the Coastal Cruiser certificate"), Career.WorldLockReason(TEXT("gulf")), FString(TEXT("Earn the Coastal Cruiser certificate")));
	TestTrue(TEXT("The J/22 is open"), Career.IsBoatOpen(TEXT("J22")));
	TestEqual(TEXT("The Catalina 22: the Day Sailor certificate"), Career.BoatLockReason(TEXT("Catalina22")), FString(TEXT("Earn the Day Sailor certificate")));
	TestEqual(TEXT("The Sunfish: the Day Sailor certificate (it opens Club Racer)"), Career.BoatLockReason(TEXT("Sunfish")), FString(TEXT("Earn the Day Sailor certificate")));
	TestTrue(TEXT("A boat no tier names yet says so"), Career.BoatLockReason(TEXT("Hobie16")).StartsWith(TEXT("Not in the career yet")));
	TestTrue(TEXT("Day Sailor open, Club Racer not"), Career.IsTierOpen(TEXT("day-sailor")) && !Career.IsTierOpen(TEXT("club-racer")));
	// Free Sail: every world and boat, no reasons (FreeSail tests the rest).
	FCareerProgress Free(*C, P, true);
	for (int32 W = 0; W < 3; ++W)
	{
		TestTrue(FString::Printf(TEXT("Free Sail: %s"), *FSailSave::WorldId(W)), Free.IsWorldOpen(FSailSave::WorldId(W)) && Free.WorldLockReason(FSailSave::WorldId(W)).IsEmpty());
	}
	for (int32 B = 0; B < int32(EBoatType::Count); ++B)
	{
		TestTrue(FString::Printf(TEXT("Free Sail: %s"), *FSailSave::BoatId(B)), Free.IsBoatOpen(FSailSave::BoatId(B)));
	}
	TestTrue(TEXT("Free Sail opens the tiers"), Free.IsTierOpen(TEXT("passage-maker")));
	TestFalse(TEXT("... but awards nothing"), Free.HasCertificate(TEXT("day-sailor")));
	// The Day Sailor certificate opens Club Racer and Coastal Cruiser: Galveston and the Catalinas, not yet the Gulf.
	FSailSave::FCertificateRecord Cert;
	Cert.Id = TEXT("day-sailor");
	P.Certificates.Add(Cert);
	TestTrue(TEXT("Club Racer and Coastal Cruiser open"), Career.IsTierOpen(TEXT("club-racer")) && Career.IsTierOpen(TEXT("coastal-cruiser")));
	TestFalse(TEXT("Passage Maker still closed"), Career.IsTierOpen(TEXT("passage-maker")));
	TestTrue(TEXT("Galveston open"), Career.IsWorldOpen(TEXT("galveston-bay")));
	TestTrue(TEXT("Catalina 22 and 30 open"), Career.IsBoatOpen(TEXT("Catalina22")) && Career.IsBoatOpen(TEXT("Catalina30")));
	TestTrue(TEXT("Club Racer opens the Sunfish"), Career.IsBoatOpen(TEXT("Sunfish")));
	// A Sunfish run counts for the Club Racer lesson (SailingSim.Drills.SunfishLessons sails the course in 5:00); the
	// J/22's run of the same drill still counts for Day Sailor.
	FCareerRun Fish = Run(ESailingDrill::SailATriangle, FString(), 301.0);
	Fish.BoatId = TEXT("Sunfish");
	const FCareerProgress::FAward FishAward = Career.RecordRun(Fish);
	TestEqual(TEXT("The Sunfish's triangle is the Club Racer course"), FishAward.LessonId, FString(TEXT("club-racer.sunfish-course")));
	TestTrue(TEXT("... gold at the scripted helmsman's pace"), FishAward.Medal == ECareerMedal::Gold);
	TestEqual(TEXT("The J/22's triangle is still Day Sailor's"), Career.LessonForRun(Run(ESailingDrill::SailATriangle, FString(), 301.0)) ? Career.LessonForRun(Run(ESailingDrill::SailATriangle, FString(), 301.0))->Id : FString(),
		FString(TEXT("day-sailor.sail-a-triangle")));
	TestEqual(TEXT("The ILCA 7: the Club Racer certificate"), Career.BoatLockReason(TEXT("ILCA7")), FString(TEXT("Earn the Club Racer certificate")));
	TestFalse(TEXT("The Gulf still locked"), Career.IsWorldOpen(TEXT("gulf")));
	FSailSave::FCertificateRecord Coastal;
	Coastal.Id = TEXT("coastal-cruiser");
	P.Certificates.Add(Coastal);
	TestTrue(TEXT("Coastal Cruiser opens the Gulf"), Career.IsWorldOpen(TEXT("gulf")));
	// An unknown certificate (a later game's) opens nothing and breaks nothing.
	FSailSave::FCertificateRecord Later;
	Later.Id = TEXT("ocean-voyager");
	P.Certificates.Add(Later);
	TestFalse(TEXT("A later game's certificate opens no boat here"), Career.IsBoatOpen(TEXT("Lagoon42")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerSaveTest, "SailingSim.Career.SaveRoundTrip", CareerTestsLocal::CareerFlags)
bool FSailingCareerSaveTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	FSailSave A;
	FCareerProgress Career(*C, A.Progress);
	Career.RecordRun(Run(ESailingDrill::HeaveTo, TEXT("done"), 75.0));
	Career.RecordLessonQuiz(TEXT("day-sailor.heave-to"), 3, 3);
	Career.AddSession(5400.0, 9, 4.25);
	Career.RecordRace(true, 1);
	Career.RecordRace(true, 3);
	FSailSave::FCertificateRecord Cert;
	Cert.Id = TEXT("day-sailor");
	Cert.EarnedAt = FDateTime(2026, 10, 18, 15, 0, 0);
	A.Progress.Certificates.Add(Cert);
	A.Settings.bFreeSail = true;
	A.bHasLast = true;
	A.Last.bFreeSail = true;
	const FString Text = A.ToJson();
	FSailSave B;
	TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Text, B)), int32(FSailSave::EResult::Ok));
	FCareerProgress Back(*C, B.Progress);
	TestEqual(TEXT("Heave to: gold"), FCareerContent::MedalName(Back.LessonMedal(TEXT("day-sailor.heave-to"))), FString(TEXT("Gold")));
	TestTrue(TEXT("... closed"), Back.IsLessonClosed(TEXT("day-sailor.heave-to")));
	TestTrue(TEXT("Certificate kept"), Back.HasCertificate(TEXT("day-sailor")));
	TestTrue(TEXT("Galveston open after the round trip"), Back.IsWorldOpen(TEXT("galveston-bay")));
	TestEqual(TEXT("Hours"), B.Progress.HoursSailed, 1.5);
	TestEqual(TEXT("Sessions"), B.Progress.LogbookSessions, 1);
	TestEqual(TEXT("Entries"), B.Progress.LogbookEntries, 9);
	TestEqual(TEXT("Miles"), B.Progress.LogbookMiles, 4.25);
	TestTrue(TEXT("Races: two sailed, one won"), B.Progress.RacesSailed == 2 && B.Progress.RacesWon == 1);
	TestTrue(TEXT("Free Sail kept"), B.Settings.bFreeSail && B.Last.bFreeSail);
	TestEqual(TEXT("Still version 1"), B.Version, 1);
	// Ids only: the medal is a word, the lesson its id (rule 7).
	TestTrue(TEXT("The file names the lesson by id and the medal by name"), Text.Contains(TEXT("\"day-sailor.heave-to\"")) && Text.Contains(TEXT("\"gold\"")));
	// A version-1 file from before the career reads as no career progress, and a later game's lesson survives a write.
	FSailSave Old;
	TestEqual(TEXT("An old file reads"), int32(FSailSave::FromJson(TEXT(R"({"version":1,"progress":{"drillsPassed":["HeaveTo"]}})"), Old)), int32(FSailSave::EResult::Ok));
	TestTrue(TEXT("... with no lessons or certificates"), Old.Progress.Lessons.Num() == 0 && Old.Progress.Certificates.Num() == 0 && !Old.Settings.bFreeSail);
	FSailSave Newer;
	FSailSave::FromJson(TEXT(R"({"version":1,"progress":{"lessons":{"ocean.night-watch":{"medal":"gold","runs":2,"future":7}}}})"), Newer);
	FCareerProgress NewerCareer(*C, Newer.Progress);
	NewerCareer.RecordRun(Run(ESailingDrill::HeaveTo, TEXT("done"), 75.0));
	const FString Again = Newer.ToJson();
	TestTrue(TEXT("A later game's lesson is kept, its unknown field too"), Again.Contains(TEXT("ocean.night-watch")) && Again.Contains(TEXT("\"future\"")));
	return true;
}

/**
 * The Texas coast (world streaming's one-piece Galveston Bay and Gulf, "texas-coast") opens with the lake's Day Sailor
 * certificate (Bean, Oct 20 2026: "Career unlocks the Texas coast after the lake"). Locks are menu-only: the World
 * screen shows the reason; Free Sail keeps it open; the save names it by its string id.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerTexasCoastTest, "SailingSim.Career.TexasCoastUnlock", CareerTestsLocal::CareerFlags)
bool FSailingCareerTexasCoastTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	const FString Coast = FSailSave::WorldId(4);
	TestEqual(TEXT("World 4's id"), Coast, FString(TEXT("texas-coast")));
	TestEqual(TEXT("...and back"), FSailSave::WorldIndex(Coast), 4);
	FSailSave Save;
	FCareerProgress Career(*C, Save.Progress);
	TestFalse(TEXT("A new sailor: the Texas coast is locked"), Career.IsWorldOpen(Coast));
	TestEqual(TEXT("...until the Day Sailor certificate"), Career.WorldLockReason(Coast), FString(TEXT("Earn the Day Sailor certificate")));
	TestTrue(TEXT("Free Sail keeps it open"), FCareerProgress(*C, Save.Progress, true).IsWorldOpen(Coast));
	FSailSave::FCertificateRecord Cert;
	Cert.Id = TEXT("day-sailor");
	Cert.EarnedAt = FDateTime(2026, 10, 20, 6, 0, 0);
	Save.Progress.Certificates.Add(Cert);
	TestTrue(TEXT("The Day Sailor certificate opens it"), Career.IsWorldOpen(Coast) && Career.WorldLockReason(Coast).IsEmpty());
	TestTrue(TEXT("...beside Galveston Bay"), Career.IsWorldOpen(TEXT("galveston-bay")));
	TestFalse(TEXT("Marseille is not in the career yet"), Career.IsWorldOpen(TEXT("marseille")));
	// The save keeps the certificate and names the world by its id.
	Save.Settings.WorldId = Coast;
	const FString Text = Save.ToJson();
	FSailSave Back;
	TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Text, Back)), int32(FSailSave::EResult::Ok));
	TestTrue(TEXT("The world by its string id"), Text.Contains(TEXT("\"texas-coast\"")) && Back.Settings.WorldId == Coast);
	TestTrue(TEXT("Still open after the round trip"), FCareerProgress(*C, Back.Progress).IsWorldOpen(Coast));
	return true;
}

/**
 * A new sailor's Day Sailor tier in logic: one drill sailed for real on the physics (heave to, graded from the
 * FDrillRunner), the other five as the sim would report them at silver, each lesson's quiz, the checkride's quiz,
 * the certificate, Galveston and the Catalinas unlocked, the hours on the world clock.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerPlaythroughTest, "SailingSim.Career.DaySailorPlaythrough", CareerTestsLocal::CareerFlags)
bool FSailingCareerPlaythroughTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	const FLearningContent& Learning = FLearningContent::Get();
	const FCareerTier& Day = *C->Tier(TEXT("day-sailor"));
	FSailSave Save;
	FCareerProgress Career(*C, Save.Progress);
	TestFalse(TEXT("Start: Galveston locked"), Career.IsWorldOpen(TEXT("galveston-bay")));

	// Heave to, sailed: close-hauled in 12 kn, then the jib backed, the main eased, the tiller to leeward.
	FWindParams WP;
	WP.SpeedKnots = 12.0;
	const FWindField Wind(WP);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 4.0 * kKnot);
	FAutopilot Pilot;
	Pilot.TargetTWADeg = 45.0;
	FAutoTrim Trim;
	FBoatControls Ctl;
	Ctl.MainSheet = Ctl.JibSheet = 0.2;
	for (int32 I = 0; I < int32(30 * PhysicsHz); ++I) { Ctl = Trim.Update(Boat, Ctl, PhysicsDt); Ctl.Tiller = Pilot.Update(Boat); Boat.Step(PhysicsDt, Ctl, Wind); }
	FDrillRunner Drill;
	Drill.Start(ESailingDrill::HeaveTo, Boat, 0.0);
	Ctl.bBackJib = true; Ctl.JibSheet = 0.1; Ctl.MainSheet = 0.8; Ctl.Tiller = 0.0;
	FDrillContext Ctx;
	Ctx.bBackJib = true;
	int32 Collisions = 0;
	bool bWasTouching = false;
	const double SimStart = Boat.GetState().Time;
	for (int32 I = 0; I < int32(90 * PhysicsHz) && Drill.IsActive(); ++I)
	{
		if (I == int32(6 * PhysicsHz)) Ctl.Tiller = 0.3;
		Boat.Step(PhysicsDt, Ctl, Wind);
		Drill.Update(Boat, Ctx, PhysicsDt);
		Collisions += Boat.GetTelemetry().bCollision && !bWasTouching;
		bWasTouching = Boat.GetTelemetry().bCollision;
	}
	if (!TestTrue(TEXT("Hove to on the physics"), Drill.IsComplete())) return false;
	const FCareerProgress::FAward Heave = Career.RecordRun(MakeCareerRun(Drill, 0.0, Collisions, 0, Lake, TEXT("J22")));
	AddInfo(FString::Printf(TEXT("Heave to: %s in %.0f s"), *FCareerContent::MedalName(Heave.Medal), Drill.GetElapsed()));
	TestEqual(TEXT("Heave to counts for its lesson"), Heave.LessonId, FString(TEXT("day-sailor.heave-to")));
	TestTrue(TEXT("Heave to at silver or better"), Heave.Medal >= ECareerMedal::Silver);

	// The other five at silver (inside the silver time, outside the gold).
	for (const FCareerLesson& L : Day.Lessons)
	{
		if (L.Drill == ESailingDrill::HeaveTo) continue;
		const FCareerProgress::FAward A = Career.RecordRun(Run(L.Drill, GoodOutcome(L.Drill), L.Medals[1].MaxSeconds - 10.0));
		TestTrue(FString::Printf(TEXT("%s: silver or better"), *L.Id), A.Medal >= ECareerMedal::Silver);
	}
	// Each lesson's quiz, answered two of three right (or the quiz's length less one, at least two thirds).
	for (const FCareerLesson& L : Day.Lessons)
	{
		FRandomStream Rng(3);
		const int32 Of = Learning.MakeQuiz(L.QuizDrill, Rng).Num();
		TestTrue(FString::Printf(TEXT("%s quiz passes at %d of %d"), *L.Id, Of - 1, Of), Career.RecordLessonQuiz(L.Id, Of - 1, Of));
	}
	TestEqual(TEXT("Six lessons closed"), Career.LessonsClosed(Day), 6);
	TestTrue(TEXT("Checkride ready"), Career.IsCheckrideReady(Day.Id));
	FRandomStream Rng(42);
	const TArray<FQuizQuestion> Ride = C->MakeCheckrideQuiz(Day, Learning, Rng);
	int32 Right = 0;
	for (int32 I = 0; I < Ride.Num(); ++I) Right += I < Ride.Num() - 2;   // two wrong
	TestTrue(TEXT("Checkride quiz passed: the certificate"), Career.RecordCheckrideQuiz(Day.Id, Right, Ride.Num(), FDateTime(2026, 10, 18, 16, 30, 0)));
	TestTrue(TEXT("Day Sailor certificate held"), Career.HasCertificate(Day.CertificateId));
	TestTrue(TEXT("Galveston unlocked"), Career.IsWorldOpen(TEXT("galveston-bay")));
	TestTrue(TEXT("The Catalina 22 unlocked"), Career.IsBoatOpen(TEXT("Catalina22")));
	TestTrue(TEXT("The Gulf not yet"), !Career.IsWorldOpen(TEXT("gulf")));
	// The session ends: the sim clock's time goes to the hours sailed.
	Career.AddSession(Boat.GetState().Time - SimStart + 3600.0, 12, 3.0);
	TestTrue(TEXT("Hours sailed from the world clock"), Save.Progress.HoursSailed > 1.0 && Save.Progress.HoursSailed < 1.1);
	// And it all survives the save.
	FSailSave Back;
	FSailSave::FromJson(Save.ToJson(), Back);
	FCareerProgress Reloaded(*C, Back.Progress);
	TestTrue(TEXT("Reloaded: certificate and Galveston"), Reloaded.HasCertificate(TEXT("day-sailor")) && Reloaded.IsWorldOpen(TEXT("galveston-bay")));
	TestEqual(TEXT("Reloaded: six lessons closed"), Reloaded.LessonsClosed(Day), 6);
	return true;
}

/**
 * Easy mode's honest grading (docs/easy-mode/README.md): a run on Easy earns at most career.json's easy_max_medal
 * (bronze), the lesson remembers that its medal was an Easy one until the same medal or better is sailed on Realistic,
 * the save keeps it, and the checkride (silver) cannot be reached on Easy alone.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerEasyMedalTest, "SailingSim.Career.EasyMedal", CareerTestsLocal::CareerFlags)
bool FSailingCareerEasyMedalTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	TestEqual(TEXT("career.json caps Easy at bronze"), FCareerContent::MedalName(C->EasyMaxMedal), FString(TEXT("Bronze")));
	const FCareerLesson* Dock = C->Lesson(TEXT("day-sailor.leave-the-dock"));
	if (!TestNotNull(TEXT("Leave the dock"), Dock)) return false;
	const ESailingDrill D = ESailingDrill::LeaveTheDock;
	auto Easy = [](FCareerRun R) { R.bEasy = true; return R; };
	// The grade alone: a gold run is bronze on Easy; a run that misses bronze earns nothing either way.
	TestEqual(TEXT("A gold run on Realistic: gold"), FCareerContent::MedalName(FCareerContent::Grade(*Dock, Run(D, TEXT("clean"), 170.0), C->EasyMaxMedal)), FString(TEXT("Gold")));
	TestEqual(TEXT("The same run on Easy: bronze"), FCareerContent::MedalName(FCareerContent::Grade(*Dock, Easy(Run(D, TEXT("clean"), 170.0)), C->EasyMaxMedal)), FString(TEXT("Bronze")));
	FCareerRun Unfinished = Easy(Run(D, FString(), 60.0));
	Unfinished.bComplete = false;
	TestEqual(TEXT("Unfinished on Easy: none"), FCareerContent::MedalName(FCareerContent::Grade(*Dock, Unfinished, C->EasyMaxMedal)), FString(TEXT("No medal")));
	// A content without the cap grades Easy runs like any other.
	FCareerContent NoCap;
	TestTrue(TEXT("A career.json without easy_max_medal loads"), NoCap.LoadText(TEXT(R"({"schema_version":1,"tiers":[{"id":"t","name":"T","status":"stub","world":"ray-hubbard","lessons":[]}]})")));
	TestEqual(TEXT("... and caps nothing"), FCareerContent::MedalName(NoCap.EasyMaxMedal), FString(TEXT("Gold")));

	FSailSave Save;
	FCareerProgress Career(*C, Save.Progress);
	FCareerProgress::FAward A = Career.RecordRun(Easy(Run(D, TEXT("clean"), 170.0)));
	TestTrue(TEXT("Easy gold run: bronze, capped, an Easy best"), A.Medal == ECareerMedal::Bronze && A.bEasyCapped && A.bBestEasy && A.bNewBest);
	TestTrue(TEXT("... the lesson says Easy"), Career.IsLessonMedalEasy(Dock->Id));
	A = Career.RecordRun(Easy(Run(D, TEXT("contact"), 150.0, 1, 0, 2.0)));
	TestTrue(TEXT("An Easy bronze run is not capped"), A.Medal == ECareerMedal::Bronze && !A.bEasyCapped);
	// The round trip keeps the Easy mark (a string id and a flag, rule 7).
	{
		FSailSave Back;
		const FString Text = Save.ToJson();
		TestEqual(TEXT("Reads back"), int32(FSailSave::FromJson(Text, Back)), int32(FSailSave::EResult::Ok));
		TestTrue(TEXT("... the Easy mark kept"), FCareerProgress(*C, Back.Progress).IsLessonMedalEasy(Dock->Id) && Text.Contains(TEXT("\"medalEasy\": true")));
	}
	A = Career.RecordRun(Run(D, TEXT("contact"), 150.0, 1, 0, 2.0));
	TestTrue(TEXT("The same bronze on Realistic clears the mark"), A.Medal == ECareerMedal::Bronze && !A.bBestEasy && !Career.IsLessonMedalEasy(Dock->Id));
	A = Career.RecordRun(Run(D, TEXT("clean"), 170.0));
	TestTrue(TEXT("Gold on Realistic: gold, not Easy"), A.Best == ECareerMedal::Gold && !Career.IsLessonMedalEasy(Dock->Id));
	A = Career.RecordRun(Easy(Run(D, TEXT("clean"), 120.0)));
	TestTrue(TEXT("A later Easy run keeps the Realistic gold"), A.Best == ECareerMedal::Gold && !A.bBestEasy && !Career.IsLessonMedalEasy(Dock->Id));

	// Every Day Sailor lesson at gold pace on Easy: all bronze, so the checkride (silver) is not ready.
	const FCareerTier& Day = *C->Tier(TEXT("day-sailor"));
	FSailSave EasySave;
	FCareerProgress EasyCareer(*C, EasySave.Progress);
	for (const FCareerLesson& L : Day.Lessons)
	{
		EasyCareer.RecordRun(Easy(Run(L.Drill, GoodOutcome(L.Drill), 30.0)));
		EasyCareer.RecordLessonQuiz(L.Id, 3, 3);
	}
	TestEqual(TEXT("Easy alone: every lesson bronze"), EasyCareer.LessonsAtLeast(Day, ECareerMedal::Bronze), Day.Lessons.Num());
	TestEqual(TEXT("... none at silver"), EasyCareer.LessonsAtLeast(Day, ECareerMedal::Silver), 0);
	TestTrue(TEXT("The checkride asks for more than Easy earns"), Day.Checkride.MinMedal > C->EasyMaxMedal);
	TestFalse(TEXT("... so it is not ready"), EasyCareer.IsCheckrideReady(Day.Id));
	TestFalse(TEXT("... and a perfect written quiz awards nothing"), EasyCareer.RecordCheckrideQuiz(Day.Id, 12, 12, FDateTime(2026, 10, 18)));
	return true;
}

/**
 * Free Sail (docs/free-sail/README.md): the title screen's second mode opens every tier, world and boat from the start
 * and earns no medals, quizzes or certificates, while the logbook (sessions, races) still counts. The save keeps the
 * mode (settings.career.freeSail, lastSession.freeSail); a file from before reads Career 1's Open everything as it.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCareerFreeSailTest, "SailingSim.Career.FreeSail", CareerTestsLocal::CareerFlags)
bool FSailingCareerFreeSailTest::RunTest(const FString&)
{
	using namespace CareerTestsLocal;
	const FCareerContent* C = Load(*this);
	if (!C) return false;
	FSailSave Save;
	FCareerProgress Free(*C, Save.Progress, true);
	TestTrue(TEXT("Free Sail says so"), Free.IsFreeSail());
	// Everything open from the start: every tier, world and boat, with no lock reason.
	for (const FCareerTier& T : C->Tiers) TestTrue(FString::Printf(TEXT("Tier %s open"), *T.Id), Free.IsTierOpen(T.Id));
	for (int32 W = 0; W < 3; ++W) TestTrue(FString::Printf(TEXT("World %s open"), *FSailSave::WorldId(W)), Free.WorldLockReason(FSailSave::WorldId(W)).IsEmpty());
	for (int32 B = 0; B < int32(EBoatType::Count); ++B) TestTrue(FString::Printf(TEXT("Boat %s open"), *FSailSave::BoatId(B)), Free.BoatLockReason(FSailSave::BoatId(B)).IsEmpty());
	// No medals: a gold run counts for no lesson, a perfect quiz closes nothing.
	const FCareerProgress::FAward A = Free.RecordRun(Run(ESailingDrill::HeaveTo, TEXT("done"), 60.0));
	TestFalse(TEXT("A gold run in Free Sail earns no award"), A.IsValid());
	TestFalse(TEXT("... nor a passed quiz"), Free.RecordLessonQuiz(TEXT("day-sailor.heave-to"), 3, 3));
	TestEqual(TEXT("... and nothing is recorded"), Save.Progress.Lessons.Num(), 0);
	// No certificates, even with every lesson at gold from a Career run.
	FCareerProgress Career(*C, Save.Progress);
	const FCareerTier& Day = *C->Tier(TEXT("day-sailor"));
	for (const FCareerLesson& L : Day.Lessons) Career.RecordRun(Run(L.Drill, GoodOutcome(L.Drill), 30.0));
	TestTrue(TEXT("The Career runs made the checkride ready"), Career.IsCheckrideReady(Day.Id));
	TestFalse(TEXT("Free Sail: the written checkride awards nothing"), Free.RecordCheckrideQuiz(Day.Id, 12, 12, FDateTime(2026, 10, 18)));
	TestFalse(TEXT("... no certificate"), Save.Progress.HasCertificate(Day.CertificateId) || Save.Progress.FindCheckride(Day.Checkride.Id));
	TestFalse(TEXT("... and Free Sail opened nothing for Career"), Career.IsWorldOpen(TEXT("galveston-bay")));
	// The logbook still counts.
	Free.AddSession(3600.0, 4, 2.5);
	Free.RecordRace(true, 1);
	TestTrue(TEXT("Free Sail: the logbook and races count"), Save.Progress.LogbookSessions == 1 && Save.Progress.HoursSailed == 1.0 && Save.Progress.RacesWon == 1);

	// The save: freeSail is written, Career 1's openEverything is gone, and an old file's switch reads as Free Sail.
	Save.Settings.bFreeSail = true;
	const FString Text = Save.ToJson();
	TestTrue(TEXT("Written as settings.career.freeSail"), Text.Contains(TEXT("\"freeSail\": true")) && !Text.Contains(TEXT("openEverything")));
	FSailSave Old;
	FSailSave::FromJson(TEXT(R"({"version":1,"settings":{"career":{"openEverything":true}}})"), Old);
	TestTrue(TEXT("A Career 1 file with Open everything on reads as Free Sail"), Old.Settings.bFreeSail);
	TestFalse(TEXT("... and writes without the old field"), Old.ToJson().Contains(TEXT("openEverything")));
	FSailSave Both;
	FSailSave::FromJson(TEXT(R"({"version":1,"settings":{"career":{"openEverything":true,"freeSail":false}}})"), Both);
	TestFalse(TEXT("freeSail wins over the old field"), Both.Settings.bFreeSail);
	TestEqual(TEXT("Still version 1"), Old.Version, 1);

	// The game's edge: the settings carry the mode, a session config carries it over the reload.
	USailingSettings* S = USailingSettings::Get();
	const bool bFree0 = S->bFreeSail;
	S->bFreeSail = true;
	TestTrue(TEXT("Settings in Free Sail: SailCareer is"), SailCareer::IsFreeSail() && SailCareer::Progress().IsFreeSail());
	TestTrue(TEXT("A new session takes the title's mode"), USailSessionSubsystem::MakeDefault().bFreeSail);
	FSailSessionConfig Session = USailSessionSubsystem::MakeDefault();
	Session.bFreeSail = false;
	USailSessionSubsystem::ApplyToSettings(Session);
	TestFalse(TEXT("A Career session puts the settings in Career"), S->bFreeSail || SailCareer::IsFreeSail());
	S->bFreeSail = bFree0;
	S->Save();
	return true;
}
