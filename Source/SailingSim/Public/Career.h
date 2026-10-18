#pragma once

#include "CoreMinimal.h"
#include "Math/RandomStream.h"
#include "Drills.h"
#include "Learning.h"
#include "SailSave.h"

/**
 * The learn-to-sail career (docs/career/README.md): tiers that mirror real certification, each with lessons (a drill
 * from Content/Learning graded bronze, silver or gold, then its quiz), a checkride (the lessons at a medal plus a
 * written quiz) and the certificate it awards, which unlocks further tiers, worlds and boats. The content is
 * Content/Career/career.json, read at start like Content/Learning; progress lives in the save (FSailSave::FProgress).
 * Plain logic, no world: the tests play a whole tier through it.
 */
enum class ECareerMedal : uint8 { None, Bronze, Silver, Gold };

/** One finished drill run as the sim saw it (online rule 8: FDrillRunner and the boat's telemetry, never the HUD). */
struct FCareerRun
{
	ESailingDrill Drill = ESailingDrill::None;
	bool bComplete = false;
	FString Outcome;                 // FDrillRunner::GetOutcome
	double Seconds = 0.0;            // FDrillRunner::GetElapsed, on the sim clock
	double MaxContactKnots = 0.0;    // hardest touch on a dock or hull
	int32 Collisions = 0;            // contacts begun during the drill
	int32 Infractions = 0;           // rules coach penalties during the drill
	FString WorldId, BoatId;         // FSailSave ids
};

/** A finished (or stopped) drill as a career run: the runner's drill, outcome and time, plus what the boat counted. */
SAILINGSIM_API FCareerRun MakeCareerRun(const FDrillRunner& Drill, double MaxContactKnots, int32 Collisions, int32 Infractions, const FString& WorldId,
	const FString& BoatId);

/** What a medal asks of a run; an unset limit (negative, or no outcomes) asks nothing. */
struct FCareerMedalRule
{
	TArray<FString> Outcomes;
	double MaxSeconds = -1.0;
	double MaxContactKnots = -1.0;
	int32 MaxCollisions = -1;
	int32 MaxInfractions = -1;
	bool Holds(const FCareerRun& Run) const;
};

struct FCareerLesson
{
	FString Id, Title, TierId;
	FString DrillId, QuizId;         // Content/Learning ids
	ESailingDrill Drill = ESailingDrill::None;
	ESailingDrill QuizDrill = ESailingDrill::None;
	double QuizPass = 0.66;          // share of the quiz right to close the lesson
	FCareerMedalRule Medals[3];      // bronze, silver, gold
};

struct FCareerQuizSpec
{
	TArray<FString> DrillIds;
	TArray<ESailingDrill> Drills;
	int32 Questions = 0;             // 0: no quiz
	double Pass = 0.8;
	bool IsSet() const { return Questions > 0; }
	bool Passes(int32 Right, int32 Of) const { return Of > 0 && double(Right) >= Pass * double(Of) - 1e-9; }
};

struct FCareerCheckride
{
	FString Id, Title;
	TArray<FString> Lessons;
	ECareerMedal MinMedal = ECareerMedal::Silver;
	FCareerQuizSpec Quiz;
};

struct FCareerUnlocks
{
	TArray<FString> Tiers, Worlds, Boats;
};

struct FCareerTier
{
	FString Id, Name, Status, Summary, Learning, WorldId, Notes;
	TArray<FString> Boats;           // FSailSave boat ids; empty: any boat counts
	TArray<FCareerLesson> Lessons;
	FCareerCheckride Checkride;
	FString CertificateId, CertificateName;
	FCareerUnlocks Unlocks;
	bool IsReady() const { return Status == TEXT("ready") && Lessons.Num() > 0; }
	const FCareerLesson* Lesson(const FString& LessonId) const { return Lessons.FindByPredicate([&LessonId](const FCareerLesson& L) { return L.Id == LessonId; }); }
};

class SAILINGSIM_API FCareerContent
{
public:
	/** Content/Career/career.json, loaded on first use. */
	static const FCareerContent& Get();
	static FString Dir();
	bool Load(const FString& Directory, FString* OutError = nullptr);
	bool LoadText(const FString& Json, FString* OutError = nullptr);
	bool IsLoaded() const { return bLoaded; }
	/** Every id against the game: drills and quizzes in the learning content, worlds and boats the save knows, outcomes
	 *  the drill can end with, medals that only get stricter, checkrides over their tier's lessons, unlocks that name
	 *  tiers. Empty when all is well (Tools/career/validate.py checks the same file without the game). */
	TArray<FString> Validate(const FLearningContent& Learning) const;

	const FCareerTier* Tier(const FString& Id) const;
	const FCareerTier* TierOfCertificate(const FString& CertificateId) const;
	const FCareerLesson* Lesson(const FString& Id) const;
	/** The checkride's written quiz: its questions from the listed drills (and Any), shuffled, options shuffled. */
	TArray<FQuizQuestion> MakeCheckrideQuiz(const FCareerTier& Tier, const FLearningContent& Learning, FRandomStream& Rng) const;

	/** The best medal a run earns in a lesson (None if the drill was not finished or misses bronze). */
	static ECareerMedal Grade(const FCareerLesson& Lesson, const FCareerRun& Run);
	static FString MedalId(ECareerMedal Medal);          // "", bronze, silver, gold
	static ECareerMedal MedalFromId(const FString& Id);
	static FString MedalName(ECareerMedal Medal);        // Bronze, Silver, Gold, or "No medal"

	FString School;
	FCareerUnlocks AlwaysOpen;
	TArray<FCareerTier> Tiers;

private:
	bool bLoaded = false;
};

/**
 * The player's career over the save's progress (edits it in place): records drill runs and quizzes, decides
 * checkrides and certificates, and answers what is open. Nothing here reads the HUD or a "current player".
 */
class SAILINGSIM_API FCareerProgress
{
public:
	FCareerProgress(const FCareerContent& InContent, FSailSave::FProgress& InProgress) : Content(InContent), Progress(InProgress) {}

	struct FAward
	{
		FString LessonId;
		ECareerMedal Medal = ECareerMedal::None;   // this run's
		ECareerMedal Best = ECareerMedal::None;    // the lesson's best after it
		bool bNewBest = false;                     // a better medal than before
		bool bBestTime = false;                    // a faster medal run than before
		double Seconds = 0.0;
		bool IsValid() const { return !LessonId.IsEmpty(); }
	};
	/** The lesson a run counts for: the drill's lesson in an open tier whose boats include the run's (the run's world's
	 *  tier first). Null when the run counts for no lesson. */
	const FCareerLesson* LessonForRun(const FCareerRun& Run, bool bOpenEverything = false) const;
	/** Grades a finished run and keeps the lesson's best medal and time. Invalid award: the run counts for no lesson. */
	FAward RecordRun(const FCareerRun& Run, bool bOpenEverything = false);
	/** A lesson's quiz: kept as its best score; true when this one passes. */
	bool RecordLessonQuiz(const FString& LessonId, int32 Right, int32 Of);
	ECareerMedal LessonMedal(const FString& LessonId) const;
	/** A lesson is closed once it holds a medal and its quiz is passed. */
	bool IsLessonClosed(const FString& LessonId) const;
	int32 LessonsAtLeast(const FCareerTier& Tier, ECareerMedal Medal) const;
	int32 LessonsClosed(const FCareerTier& Tier) const;

	/** The checkride's practical part: every listed lesson at the minimum medal (and the tier has a quiz). */
	bool IsCheckrideReady(const FString& TierId, FString* OutWhy = nullptr) const;
	/** The checkride's written quiz: the certificate is awarded when the practical part holds and this passes. True
	 *  when the certificate was awarded by this call. */
	bool RecordCheckrideQuiz(const FString& TierId, int32 Right, int32 Of, const FDateTime& WhenUtc);
	bool HasCertificate(const FString& CertificateId) const { return Progress.HasCertificate(CertificateId); }

	bool IsTierOpen(const FString& TierId, bool bOpenEverything = false) const;
	bool IsWorldOpen(const FString& WorldId, bool bOpenEverything) const;
	bool IsBoatOpen(const FString& BoatId, bool bOpenEverything) const;
	/** One line on why a world or boat is locked ("Earn the Day Sailor certificate"); empty when it is open. */
	FString WorldLockReason(const FString& WorldId, bool bOpenEverything) const;
	FString BoatLockReason(const FString& BoatId, bool bOpenEverything) const;

	/** The sim's session end: time on the world clock and the logbook's counts go to the totals. */
	void AddSession(double SimSeconds, int32 LogEntries, double LogMiles);
	void RecordRace(bool bFinished, int32 Place);

	const FSailSave::FProgress& Get() const { return Progress; }

private:
	/** What earning a certificate opens: its unlocks plus the worlds and boats of the tiers it opens. */
	void Opens(const FCareerTier& Tier, TSet<FString>& Worlds, TSet<FString>& Boats) const;
	FString LockReason(const FString& Id, bool bWorld) const;
	const FCareerContent& Content;
	FSailSave::FProgress& Progress;
};
