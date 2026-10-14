#pragma once

#include "CoreMinimal.h"
#include "Math/RandomStream.h"
#include "Drills.h"
#include "Rules.h"
#include "Weather.h"

/**
 * Graphics G7: the learning mode's written content (Content/Learning, from Inputs/drills): a briefing per drill, tips
 * keyed to sim events, and the quiz bank. Loaded once from loose JSON (staged like Content/TerrainData), plain structs.
 */
struct FDrillBriefing
{
	struct FCommand { FString Call, Reply, Meaning; };
	struct FStep { FString SimText, Text, Coach; };
	ESailingDrill Drill = ESailingDrill::None;
	FString Id, Name, AsaSkill, Goal, Why, Setup, LakeNotes;
	TArray<FCommand> Commands;
	TArray<FStep> Steps;          // same count and order as FDrillRunner's steps
	TArray<FString> Good;
	TArray<TPair<FString, FString>> Mistakes;   // mistake, fix
	TMap<FString, FString> Debrief;             // outcome (FDrillRunner::GetOutcome) -> line
	int32 QuizAfter = 0;
	/** The step's line for the HUD: the key-token version when there is one, keys resolved. */
	FString StepText(int32 Index) const;
};

struct FLearningTip
{
	FString Id, Event, Topic, Text;
	TArray<ESailingDrill> Drills;   // empty: Any
	int32 Level = 0;                // 0 info, 1 good, 2 warn, 3 danger (the tip card's severities)
	double Cooldown = 30.0;
	bool bOncePerSession = false;
	bool IsAny() const { return Drills.Num() == 0; }
	bool Fits(ESailingDrill Drill) const { return IsAny() || Drills.Contains(Drill); }
};

struct FQuizQuestion
{
	FString Id, Topic, Question, Why;
	TArray<ESailingDrill> Drills;   // empty: Any
	TArray<FString> Options;
	int32 Answer = 0;
};

class SAILINGSIM_API FLearningContent
{
public:
	/** The content from Content/Learning, loaded on first use. */
	static const FLearningContent& Get();
	static FString Dir();
	bool Load(const FString& Directory, FString* OutError = nullptr);
	bool IsLoaded() const { return bLoaded; }

	const FDrillBriefing* Briefing(ESailingDrill Drill) const;
	/** The quiz after a drill: QuizAfter questions, the drill's own first, then Any; options shuffled. */
	TArray<FQuizQuestion> MakeQuiz(ESailingDrill Drill, FRandomStream& Rng) const;
	/** The debrief line for a finished drill ({time} m:ss, {contact_kn}); empty if none. */
	FString Debrief(ESailingDrill Drill, const FString& Outcome, double ElapsedSeconds, double ContactKnots) const;

	/** {key:Action.trim|ease|out} or {key:Action}: the player's current keyboard binding. */
	static FString ResolveKeys(const FString& Text);
	/** True when every key token in the text names a bound action (the test checks the content). */
	static bool KeysResolve(const FString& Text, FString* OutBad = nullptr);
	static ESailingDrill DrillFromId(const FString& Id);
	static FString DrillId(ESailingDrill Drill);
	static int32 LevelFromName(const FString& Name);

	TArray<FDrillBriefing> Briefings;
	TMap<FString, FString> Events;   // event id -> what it means
	TArray<FLearningTip> Tips;
	TArray<FQuizQuestion> Questions;

private:
	bool bLoaded = false;
};

/** What the event detector reads each frame: the boat, the drill, the docks, the traffic and the weather. */
struct FLearningFrame
{
	double Time = 0.0;
	// The boat (degrees, knots; tiller and sheets as FBoatControls).
	double TwaDeg = 0.0, Knots = 0.0, TwsKnots = 0.0, HeelLeewardDeg = 0.0, HelmForce = 0.0, DepthUnderKeel = 100.0;
	double Tiller = 0.0, MainSheet = 0.3, JibSheet = 0.3;
	bool bInIrons = false, bAground = false, bCollision = false, bVesselContact = false, bBackJib = false, bTiedUp = false, bMotoring = false;
	int32 JibLuff = 0, JibStall = 0, MainLuff = 0, MainStall = 0;
	// The drill.
	ESailingDrill Drill = ESailingDrill::None;
	bool bDrillActive = false, bDrillComplete = false;
	int32 DrillStep = 0;
	double MarkDistance = -1.0;    // to the next drill mark, m (-1: none)
	double DummyDistance = -1.0;   // to the person in the water, m (-1: none)
	double DockDistance = -1.0;    // to the nearest dock face, m (-1: none near)
	// Traffic: the rules coach's most pressing encounter.
	bool bAdvice = false, bGiveWay = false, bStandOn = false, bRisk = false;
	Sailing::EEncounter Encounter = Sailing::EEncounter::None;
	Sailing::EVesselStatus PlayerStatus = Sailing::EVesselStatus::Sailing, OtherStatus = Sailing::EVesselStatus::PowerDriven;
	int32 PlayerTack = 0, OtherTack = 0;
	double Cpa = 0.0, Tcpa = 0.0;
	bool bFiveBlasts = false;      // five short blasts heard this frame
	bool bBigWakeNear = false;     // a large vessel at speed close by
	// Weather.
	Sailing::EStormPhase Storm = Sailing::EStormPhase::None;
	double WindFromDeg = 0.0, AirTempF = 74.0;
	bool bTidal = false;
};

/** Turns frames into the dotted event ids of learning-tips.json (jib.luffing, tack.slow, cob.fast_approach...). */
class SAILINGSIM_API FLearningEvents
{
public:
	/** Every event this detector can fire. */
	static const TArray<FString>& Known();
	void Reset() { *this = FLearningEvents(); }
	void Update(const FLearningFrame& F, TArray<FString>& Out);

private:
	struct FSample { double Time, AbsTwa, Twa, Tws, Knots; };
	TArray<FSample> History;            // the last 60 s at 4 Hz
	double NextSample = 0.0;
	bool bInit = false;
	FLearningFrame Last;
	// Held conditions: how long each has been true.
	TMap<FString, double> Held;
	bool Hold(const FString& Key, bool bCond, double Seconds, const FLearningFrame& F);
	// Maneuvers.
	double TackEnter = -1.0, TackMinKnots = 100.0, TurnFrom = -1.0;
	bool bTacking = false, bJibing = false, bTackStarted = false, bJibeStarted = false;
	int32 Side = 0;
	double LastHeadUp = -100.0, LastBearAway = -100.0, LastCast = -100.0;
};

/** Picks the tip to show: the running drill's own tip over an Any tip, the highest level first, cooldowns kept. */
class SAILINGSIM_API FLearningCoach
{
public:
	void Reset();
	void Update(const FLearningFrame& F, const FLearningContent& Content);
	/** The tip on show (null when none in the last ShowSeconds). */
	const FLearningTip* Current(double Now, double ShowSeconds = 9.0) const { return Tip && Now - TipAt < ShowSeconds ? Tip : nullptr; }
	FString CurrentText() const { return Tip ? FLearningContent::ResolveKeys(Tip->Text) : FString(); }
	double ShownAt() const { return TipAt; }
	const TArray<FString>& FiredEvents() const { return Fired; }
	int32 TipsShown() const { return Shown.Num(); }

private:
	FLearningEvents Events;
	TArray<FString> Fired;
	TMap<FString, double> LastShown;
	TSet<FString> Shown;
	const FLearningTip* Tip = nullptr;
	double TipAt = -100.0;
};
