#include "Learning.h"
#include "SailingSettings.h"
#include "SailingBindings.h"
#include "UI/SailUIStyle.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace LearningLocal
{
	TSharedPtr<FJsonObject> ReadJson(const FString& Path, FString* OutError)
	{
		FString Text;
		TSharedPtr<FJsonObject> Root;
		if (!FFileHelper::LoadFileToString(Text, *Path))
		{
			if (OutError) *OutError = FString::Printf(TEXT("cannot read %s"), *Path);
			return nullptr;
		}
		if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
		{
			if (OutError) *OutError = FString::Printf(TEXT("bad JSON in %s"), *Path);
			return nullptr;
		}
		return Root;
	}

	TArray<FString> Strings(const TSharedPtr<FJsonObject>& O, const TCHAR* Field)
	{
		TArray<FString> Out;
		O->TryGetStringArrayField(Field, Out);
		return Out;
	}

	FString Str(const TSharedPtr<FJsonObject>& O, const TCHAR* Field)
	{
		FString S;
		O->TryGetStringField(Field, S);
		return S;
	}

	TArray<ESailingDrill> Drills(const TSharedPtr<FJsonObject>& O)
	{
		TArray<ESailingDrill> Out;
		for (const FString& Id : Strings(O, TEXT("drills")))
		{
			const ESailingDrill D = FLearningContent::DrillFromId(Id);
			if (D != ESailingDrill::None) Out.AddUnique(D);
		}
		return Out;
	}

	FString MinSec(double Seconds) { return FString::Printf(TEXT("%d:%02d"), int32(Seconds) / 60, int32(Seconds) % 60); }

	/** The binding for a token's action: {key:JibSheet.trim} is the JibSheet key with scale -1. */
	bool FindKey(const FString& Token, FString& OutName)
	{
		FString Action = Token, Dir;
		Token.Split(TEXT("."), &Action, &Dir);
		// Each token's direction, as SailingSettings.cpp binds them (trim and hauling in are the negative scale).
		const bool bNegative = Dir == TEXT("trim");
		if (!Dir.IsEmpty() && Dir != TEXT("trim") && Dir != TEXT("ease") && Dir != TEXT("out")) return false;
		// The live binding: the controller's while the player is on the pad, else the keyboard's.
		const FString Name = SailingBindings::Label(FName(*Action), bNegative, SailUI::UsingGamepad());
		if (Name == TEXT("?")) return false;
		OutName = Name;
		return true;
	}
}

FString FDrillBriefing::StepText(int32 Index) const
{
	if (!Steps.IsValidIndex(Index)) return FString();
	return FLearningContent::ResolveKeys(Steps[Index].Text.IsEmpty() ? Steps[Index].SimText : Steps[Index].Text);
}

FString FLearningContent::Dir()
{
	return FPaths::ProjectContentDir() / TEXT("Learning");
}

const FLearningContent& FLearningContent::Get()
{
	static FLearningContent Content;
	static bool bTried = false;
	if (!bTried)
	{
		bTried = true;
		FString Error;
		if (!Content.Load(Dir(), &Error)) UE_LOG(LogTemp, Warning, TEXT("Learning content: %s"), *Error);
	}
	return Content;
}

ESailingDrill FLearningContent::DrillFromId(const FString& Id)
{
	for (int32 I = 1; I < int32(ESailingDrill::Count); ++I) if (DrillId(ESailingDrill(I)) == Id) return ESailingDrill(I);
	return ESailingDrill::None;
}

FString FLearningContent::DrillId(ESailingDrill Drill)
{
	switch (Drill)
	{
	case ESailingDrill::LeaveTheDock: return TEXT("LeaveTheDock");
	case ESailingDrill::SailATriangle: return TEXT("SailATriangle");
	case ESailingDrill::HeaveTo: return TEXT("HeaveTo");
	case ESailingDrill::CrewOverboardFigureEight: return TEXT("CrewOverboardFigureEight");
	case ESailingDrill::CrewOverboardQuickStop: return TEXT("CrewOverboardQuickStop");
	case ESailingDrill::ReturnAndDock: return TEXT("ReturnAndDock");
	default: return TEXT("Any");
	}
}

int32 FLearningContent::LevelFromName(const FString& Name)
{
	return Name == TEXT("good") ? 1 : (Name == TEXT("warn") ? 2 : (Name == TEXT("danger") ? 3 : 0));
}

bool FLearningContent::Load(const FString& Directory, FString* OutError)
{
	using namespace LearningLocal;
	*this = FLearningContent();
	const TSharedPtr<FJsonObject> B = ReadJson(Directory / TEXT("drill-briefings.json"), OutError);
	const TSharedPtr<FJsonObject> T = ReadJson(Directory / TEXT("learning-tips.json"), OutError);
	const TSharedPtr<FJsonObject> Q = ReadJson(Directory / TEXT("quiz-bank.json"), OutError);
	if (!B || !T || !Q) return false;

	const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
	if (B->TryGetArrayField(TEXT("drills"), List))
	{
		for (const TSharedPtr<FJsonValue>& V : *List)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			FDrillBriefing D;
			D.Id = Str(O, TEXT("id"));
			D.Drill = DrillFromId(D.Id);
			D.Name = Str(O, TEXT("name"));
			D.AsaSkill = Str(O, TEXT("asa_skill"));
			D.Goal = Str(O, TEXT("goal"));
			D.Why = Str(O, TEXT("why_it_matters"));
			D.Setup = Str(O, TEXT("setup"));
			D.LakeNotes = Str(O, TEXT("lake_notes"));
			D.Good = Strings(O, TEXT("good"));
			D.QuizAfter = O->GetIntegerField(TEXT("quiz_after"));
			const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
			if (O->TryGetArrayField(TEXT("commands"), Items))
				for (const TSharedPtr<FJsonValue>& C : *Items) D.Commands.Add({ Str(C->AsObject(), TEXT("call")), Str(C->AsObject(), TEXT("reply")), Str(C->AsObject(), TEXT("meaning")) });
			if (O->TryGetArrayField(TEXT("steps"), Items))
				for (const TSharedPtr<FJsonValue>& S : *Items) D.Steps.Add({ Str(S->AsObject(), TEXT("sim_text")), Str(S->AsObject(), TEXT("text")), Str(S->AsObject(), TEXT("coach")) });
			if (O->TryGetArrayField(TEXT("mistakes"), Items))
				for (const TSharedPtr<FJsonValue>& M : *Items) D.Mistakes.Add({ Str(M->AsObject(), TEXT("mistake")), Str(M->AsObject(), TEXT("fix")) });
			const TSharedPtr<FJsonObject>* Debrief = nullptr;
			if (O->TryGetObjectField(TEXT("debrief"), Debrief))
				for (const TPair<FString, TSharedPtr<FJsonValue>>& P : (*Debrief)->Values) D.Debrief.Add(P.Key, P.Value->AsString());
			Briefings.Add(MoveTemp(D));
		}
	}
	const TSharedPtr<FJsonObject>* EventObj = nullptr;
	if (T->TryGetObjectField(TEXT("events"), EventObj))
		for (const TPair<FString, TSharedPtr<FJsonValue>>& P : (*EventObj)->Values) Events.Add(P.Key, P.Value->AsString());
	if (T->TryGetArrayField(TEXT("tips"), List))
	{
		for (const TSharedPtr<FJsonValue>& V : *List)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			FLearningTip Tip;
			Tip.Id = Str(O, TEXT("id"));
			Tip.Event = Str(O, TEXT("event"));
			Tip.Topic = Str(O, TEXT("asa_topic"));
			Tip.Text = Str(O, TEXT("text"));
			Tip.Drills = Drills(O);
			Tip.Level = LevelFromName(Str(O, TEXT("level")));
			Tip.Cooldown = O->GetNumberField(TEXT("cooldown_s"));
			Tip.bOncePerSession = O->GetBoolField(TEXT("once_per_session"));
			Tips.Add(MoveTemp(Tip));
		}
	}
	if (Q->TryGetArrayField(TEXT("questions"), List))
	{
		for (const TSharedPtr<FJsonValue>& V : *List)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			FQuizQuestion Qn;
			Qn.Id = Str(O, TEXT("id"));
			Qn.Topic = Str(O, TEXT("topic"));
			Qn.Question = Str(O, TEXT("q"));
			Qn.Why = Str(O, TEXT("why"));
			Qn.Drills = Drills(O);
			Qn.Options = Strings(O, TEXT("options"));
			Qn.Answer = O->GetIntegerField(TEXT("answer"));
			Questions.Add(MoveTemp(Qn));
		}
	}
	bLoaded = Briefings.Num() > 0 && Tips.Num() > 0 && Questions.Num() > 0;
	if (!bLoaded && OutError) *OutError = TEXT("no briefings, tips or questions");
	return bLoaded;
}

const FDrillBriefing* FLearningContent::Briefing(ESailingDrill Drill) const
{
	return Briefings.FindByPredicate([Drill](const FDrillBriefing& B) { return B.Drill == Drill; });
}

TArray<FQuizQuestion> FLearningContent::MakeQuiz(ESailingDrill Drill, FRandomStream& Rng) const
{
	const FDrillBriefing* B = Briefing(Drill);
	const int32 Count = B ? B->QuizAfter : 3;
	TArray<const FQuizQuestion*> Own, Any;
	for (const FQuizQuestion& Q : Questions)
	{
		if (Q.Drills.Contains(Drill)) Own.Add(&Q);
		else if (Q.Drills.Num() == 0) Any.Add(&Q);
	}
	auto Shuffle = [&Rng](TArray<const FQuizQuestion*>& A) { for (int32 I = A.Num() - 1; I > 0; --I) A.Swap(I, Rng.RandRange(0, I)); };
	Shuffle(Own);
	Shuffle(Any);
	Own.Append(Any);
	TArray<FQuizQuestion> Out;
	for (int32 I = 0; I < Own.Num() && Out.Num() < Count; ++I)
	{
		FQuizQuestion Q = *Own[I];
		// Shuffle the options and carry the answer with its text.
		const FString Right = Q.Options.IsValidIndex(Q.Answer) ? Q.Options[Q.Answer] : FString();
		for (int32 K = Q.Options.Num() - 1; K > 0; --K) Q.Options.Swap(K, Rng.RandRange(0, K));
		Q.Answer = Q.Options.IndexOfByKey(Right);
		Out.Add(MoveTemp(Q));
	}
	return Out;
}

FString FLearningContent::Debrief(ESailingDrill Drill, const FString& Outcome, double ElapsedSeconds, double ContactKnots) const
{
	using namespace LearningLocal;
	const FDrillBriefing* B = Briefing(Drill);
	const FString* Line = B ? B->Debrief.Find(Outcome) : nullptr;
	if (!Line) return FString();
	return Line->Replace(TEXT("{time}"), *MinSec(ElapsedSeconds)).Replace(TEXT("{contact_kn}"), *FString::Printf(TEXT("%.1f"), ContactKnots));
}

FString FLearningContent::ResolveKeys(const FString& Text)
{
	using namespace LearningLocal;
	FString Out;
	int32 From = 0;
	while (true)
	{
		const int32 Start = Text.Find(TEXT("{key:"), ESearchCase::CaseSensitive, ESearchDir::FromStart, From);
		if (Start == INDEX_NONE) break;
		const int32 End = Text.Find(TEXT("}"), ESearchCase::CaseSensitive, ESearchDir::FromStart, Start);
		if (End == INDEX_NONE) break;
		FString Name;
		Out += Text.Mid(From, Start - From);
		Out += FindKey(Text.Mid(Start + 5, End - Start - 5), Name) ? Name : FString(TEXT("?"));
		From = End + 1;
	}
	return Out + Text.Mid(From);
}

bool FLearningContent::KeysResolve(const FString& Text, FString* OutBad)
{
	using namespace LearningLocal;
	int32 From = 0;
	while (true)
	{
		const int32 Start = Text.Find(TEXT("{key:"), ESearchCase::CaseSensitive, ESearchDir::FromStart, From);
		if (Start == INDEX_NONE) return true;
		const int32 End = Text.Find(TEXT("}"), ESearchCase::CaseSensitive, ESearchDir::FromStart, Start);
		FString Name;
		const FString Token = End == INDEX_NONE ? Text.Mid(Start) : Text.Mid(Start + 5, End - Start - 5);
		if (End == INDEX_NONE || !FindKey(Token, Name)) { if (OutBad) *OutBad = Token; return false; }
		From = End + 1;
	}
}

// ---------------------------------------------------------------- events

const TArray<FString>& FLearningEvents::Known()
{
	static const TArray<FString> Ids = {
		TEXT("jib.luffing"), TEXT("jib.stalled"), TEXT("main.luffing"), TEXT("main.stalled"), TEXT("trim.good"), TEXT("pinching"),
		TEXT("irons"), TEXT("irons.escaped"), TEXT("head_up"), TEXT("bear_away"), TEXT("tack.start"), TEXT("tack.complete"), TEXT("tack.slow"),
		TEXT("jibe.start"), TEXT("jibe.complete"), TEXT("jibe.main_loose"), TEXT("by_the_lee"), TEXT("heel.excessive"), TEXT("weather_helm"),
		TEXT("gust"), TEXT("shallow"), TEXT("aground"),
		TEXT("cob.start"), TEXT("cob.far"), TEXT("cob.fast_approach"), TEXT("cob.downwind_approach"), TEXT("cob.alongside"),
		TEXT("heaveto.jib_released"), TEXT("heaveto.tiller_wrong"), TEXT("heaveto.main_drawing"), TEXT("heaveto.settled"),
		TEXT("dock.cast_off"), TEXT("dock.fenders"), TEXT("dock.approach_fast"), TEXT("dock.approach_downwind"), TEXT("dock.contact"), TEXT("dock.lines_on"),
		TEXT("rules.port_starboard.give_way"), TEXT("rules.port_starboard.stand_on"), TEXT("rules.same_tack.give_way"), TEXT("rules.same_tack.stand_on"),
		TEXT("rules.overtaking.give_way"), TEXT("rules.overtaking.stand_on"), TEXT("rules.power_vs_sail.stand_on"), TEXT("rules.player_motoring"),
		TEXT("rules.fishing"), TEXT("rules.restricted"), TEXT("rules.constrained"), TEXT("rules.anchored"), TEXT("rules.head_on"), TEXT("rules.crossing"),
		TEXT("rules.standon_must_act"), TEXT("rules.five_blasts"), TEXT("rules.collision"), TEXT("rules.wake"),
		TEXT("weather.storm_building"), TEXT("weather.gust_front"), TEXT("weather.lightning"), TEXT("weather.heat"), TEXT("weather.front"), TEXT("weather.calm"),
		TEXT("mark.rounding"), TEXT("drill.complete") };
	return Ids;
}

bool FLearningEvents::Hold(const FString& Key, bool bCond, double Seconds, const FLearningFrame& F)
{
	double& Since = Held.FindOrAdd(Key, -1.0);
	if (!bCond) { Since = -1.0; return false; }
	if (Since < 0.0) Since = F.Time;
	return F.Time - Since >= Seconds;
}

void FLearningEvents::Update(const FLearningFrame& F, TArray<FString>& Out)
{
	using namespace Sailing;
	const double AbsTwa = FMath::Abs(F.TwaDeg);
	const int32 NowSide = F.TwaDeg >= 0.0 ? 1 : -1;
	if (!bInit)
	{
		bInit = true;
		Last = F;
		Side = NowSide;
	}
	auto Fire = [&Out](const TCHAR* Id) { Out.AddUnique(Id); };
	// The tiller toward the boom (leeward) turns the bow toward the wind; positive tiller turns the bow to starboard.
	const double TillerToLeeward = F.Tiller * NowSide;
	const bool bSailing = !F.bTiedUp && !F.bMotoring;

	// History at 4 Hz for the rates (head up, bear away, gust, front, pinching).
	if (F.Time >= NextSample)
	{
		NextSample = F.Time + 0.25;
		History.Add({ F.Time, AbsTwa, F.TwaDeg, F.TwsKnots, F.Knots });
		while (History.Num() && F.Time - History[0].Time > 60.0) History.RemoveAt(0);
	}
	auto Ago = [this, &F](double Seconds) -> const FSample*
	{
		for (int32 I = History.Num() - 1; I >= 0; --I) if (F.Time - History[I].Time >= Seconds) return &History[I];
		return nullptr;
	};

	// Trim.
	if (bSailing && !F.bInIrons && AbsTwa >= 35.0)
	{
		if (Hold(TEXT("jl"), F.JibLuff >= 2, 1.5, F)) Fire(TEXT("jib.luffing"));
		if (Hold(TEXT("js"), F.JibStall >= 2, 1.5, F)) Fire(TEXT("jib.stalled"));
		if (Hold(TEXT("ml"), F.MainLuff >= 2, 1.5, F)) Fire(TEXT("main.luffing"));
		if (Hold(TEXT("ms"), F.MainStall >= 2, 1.5, F)) Fire(TEXT("main.stalled"));
	}
	else
	{
		Hold(TEXT("jl"), false, 0.0, F); Hold(TEXT("js"), false, 0.0, F); Hold(TEXT("ml"), false, 0.0, F); Hold(TEXT("ms"), false, 0.0, F);
	}
	const bool bAllDrawing = F.JibLuff + F.JibStall + F.MainLuff + F.MainStall == 0;
	if (Hold(TEXT("tg"), bSailing && bAllDrawing && AbsTwa >= 38.0 && AbsTwa <= 120.0 && F.Knots > 2.0, 10.0, F)) Fire(TEXT("trim.good"));
	{
		const FSample* S = Ago(3.0);
		if (Hold(TEXT("pin"), bSailing && AbsTwa >= 30.0 && AbsTwa < 38.0 && S && S->Knots - F.Knots > 0.2, 1.0, F)) Fire(TEXT("pinching"));
	}

	// Irons.
	if (F.bInIrons && !Last.bInIrons && bSailing) Fire(TEXT("irons"));
	if (Hold(TEXT("irons"), F.bInIrons && bSailing, 4.0, F)) Fire(TEXT("irons"));
	if (!F.bInIrons && Last.bInIrons && bSailing) Fire(TEXT("irons.escaped"));

	// Heading up and bearing away: |TWA| changes 25 degrees inside 5 s on the same tack.
	for (int32 I = History.Num() - 1; I >= 0 && F.Time - History[I].Time <= 5.0; --I)
	{
		const FSample& S = History[I];
		if ((S.Twa >= 0.0) != (F.TwaDeg >= 0.0)) break;   // through the wind: a tack or a jibe, not this
		if (S.AbsTwa - AbsTwa > 25.0 && F.Time - LastHeadUp > 8.0 && bSailing) { Fire(TEXT("head_up")); LastHeadUp = F.Time; break; }
		if (AbsTwa - S.AbsTwa > 25.0 && F.Time - LastBearAway > 8.0 && bSailing) { Fire(TEXT("bear_away")); LastBearAway = F.Time; break; }
	}

	// Tacks: in under 30 degrees with the tiller to leeward, through head to wind, out past 40 on the new side.
	if (bSailing && !bTacking && !bTackStarted && AbsTwa < 30.0 && Last.TwaDeg * F.TwaDeg > 0.0 && FMath::Abs(Last.TwaDeg) >= 30.0 && TillerToLeeward > 0.2 && Last.Knots > 2.0)
	{
		bTackStarted = true;
		Fire(TEXT("tack.start"));
	}
	if (AbsTwa < 30.0 && TackEnter < 0.0) { TackEnter = F.Time; TackMinKnots = F.Knots; }
	if (TackEnter >= 0.0) TackMinKnots = FMath::Min(TackMinKnots, F.Knots);
	if (NowSide != Side && AbsTwa > 3.0)
	{
		// Through the wind: a tack near head to wind, a jibe near dead downwind.
		if (AbsTwa < 90.0 && TackEnter >= 0.0) bTacking = true;
		else if (AbsTwa >= 90.0)
		{
			Fire(TEXT("jibe.complete"));
			if (F.MainSheet > 0.7) Fire(TEXT("jibe.main_loose"));
			bJibeStarted = false;
		}
		Side = NowSide;
	}
	if (bTacking && AbsTwa > 40.0)
	{
		const double Took = F.Time - TackEnter;
		Fire(Took > 8.0 || TackMinKnots < 1.0 ? TEXT("tack.slow") : TEXT("tack.complete"));
		if (F.Drill == ESailingDrill::HeaveTo && !F.bBackJib) Fire(TEXT("heaveto.jib_released"));
		bTacking = bTackStarted = false;
		TackEnter = -1.0;
	}
	if (!bTacking && AbsTwa > 45.0) { TackEnter = -1.0; bTackStarted = false; }

	// Jibes.
	if (bSailing && !bJibeStarted && AbsTwa > 160.0 && TillerToLeeward < -0.2)
	{
		bJibeStarted = true;
		Fire(TEXT("jibe.start"));
	}
	if (AbsTwa < 140.0) bJibeStarted = false;
	if (Hold(TEXT("btl"), bSailing && AbsTwa > 170.0, 2.0, F)) Fire(TEXT("by_the_lee"));

	// Heel, helm, gusts, depth.
	if (Hold(TEXT("heel"), F.HeelLeewardDeg > 22.0, 1.5, F)) Fire(TEXT("heel.excessive"));
	if (Hold(TEXT("helm"), F.HelmForce > 40.0, 3.0, F)) Fire(TEXT("weather_helm"));
	if (const FSample* S = Ago(3.0)) if (S->Tws > 3.0 && F.TwsKnots > S->Tws * 1.3 && bSailing) Fire(TEXT("gust"));
	if (!F.bTiedUp && F.DepthUnderKeel < 1.0 && !F.bAground) Fire(TEXT("shallow"));
	if (F.bAground && !Last.bAground) Fire(TEXT("aground"));

	// Crew overboard.
	const bool bCob = F.Drill == ESailingDrill::CrewOverboardFigureEight || F.Drill == ESailingDrill::CrewOverboardQuickStop;
	if (bCob && F.bDrillActive && F.DummyDistance >= 0.0)
	{
		if (!Last.bDrillActive || Last.Drill != F.Drill) Fire(TEXT("cob.start"));
		const double Far = F.Drill == ESailingDrill::CrewOverboardFigureEight ? 60.0 : 40.0;
		if (F.DummyDistance > Far) Fire(TEXT("cob.far"));
		if (F.DummyDistance < 15.0 && F.Knots > 2.0) Fire(TEXT("cob.fast_approach"));
		if (F.DummyDistance < 25.0 && AbsTwa > 120.0 && F.Knots > 0.5) Fire(TEXT("cob.downwind_approach"));
		if (F.DummyDistance < 3.0 && F.Knots < 1.2) Fire(TEXT("cob.alongside"));
	}

	// Heaving to.
	if (F.Drill == ESailingDrill::HeaveTo && F.bDrillActive)
	{
		if (Hold(TEXT("ht_t"), F.bBackJib && TillerToLeeward < 0.15 && F.Knots < 3.0, 5.0, F)) Fire(TEXT("heaveto.tiller_wrong"));
		if (F.bBackJib && F.MainSheet < 0.5 && F.Knots > 3.0) Fire(TEXT("heaveto.main_drawing"));
		if (F.DrillStep == 4) Fire(TEXT("heaveto.settled"));
	}

	// Docks.
	if (!F.bTiedUp && Last.bTiedUp) { Fire(TEXT("dock.cast_off")); LastCast = F.Time; }
	if (F.bTiedUp && !Last.bTiedUp) Fire(TEXT("dock.lines_on"));
	const bool bNearDock = F.DockDistance >= 0.0 && !F.bTiedUp;
	if (bNearDock && F.DockDistance < 150.0 && F.Time - LastCast > 120.0 && F.Knots > 0.5 && (F.Drill == ESailingDrill::ReturnAndDock || F.Drill == ESailingDrill::None)) Fire(TEXT("dock.fenders"));
	if (bNearDock && F.DockDistance < 30.0 && F.Knots > 2.0 && F.Time - LastCast > 60.0) Fire(TEXT("dock.approach_fast"));
	if (bNearDock && F.DockDistance < 50.0 && AbsTwa > 120.0 && F.Knots > 1.0 && F.Time - LastCast > 60.0) Fire(TEXT("dock.approach_downwind"));
	if (F.bCollision && !F.bVesselContact && !Last.bCollision && F.DockDistance >= 0.0 && F.DockDistance < 6.0) Fire(TEXT("dock.contact"));

	// The rules of the road.
	if (F.bAdvice)
	{
		const bool bSailVsSail = F.Encounter == EEncounter::SailingVessels;
		if (bSailVsSail && F.PlayerTack != F.OtherTack) Fire(F.bGiveWay ? TEXT("rules.port_starboard.give_way") : TEXT("rules.port_starboard.stand_on"));
		if (bSailVsSail && F.PlayerTack == F.OtherTack) Fire(F.bGiveWay ? TEXT("rules.same_tack.give_way") : TEXT("rules.same_tack.stand_on"));
		if (F.Encounter == EEncounter::Overtaking) Fire(F.bGiveWay ? TEXT("rules.overtaking.give_way") : TEXT("rules.overtaking.stand_on"));
		if (F.Encounter == EEncounter::Responsibilities && F.PlayerStatus == EVesselStatus::Sailing && F.OtherStatus == EVesselStatus::PowerDriven && F.bStandOn)
			Fire(TEXT("rules.power_vs_sail.stand_on"));
		if (F.PlayerStatus == EVesselStatus::PowerDriven && F.OtherStatus == EVesselStatus::Sailing) Fire(TEXT("rules.player_motoring"));
		if (F.OtherStatus == EVesselStatus::Fishing) Fire(TEXT("rules.fishing"));
		if (F.OtherStatus == EVesselStatus::RestrictedManeuverability || F.OtherStatus == EVesselStatus::NotUnderCommand) Fire(TEXT("rules.restricted"));
		if (F.OtherStatus == EVesselStatus::ConstrainedByDraft) Fire(TEXT("rules.constrained"));
		if (F.OtherStatus == EVesselStatus::Anchored) Fire(TEXT("rules.anchored"));
		if (F.Encounter == EEncounter::HeadOn) Fire(TEXT("rules.head_on"));
		if (F.Encounter == EEncounter::Crossing) Fire(TEXT("rules.crossing"));
		if (F.bStandOn && F.bRisk && F.Cpa < 30.0 && F.Tcpa > 0.0 && F.Tcpa < 15.0) Fire(TEXT("rules.standon_must_act"));
	}
	if (F.bFiveBlasts) Fire(TEXT("rules.five_blasts"));
	if (F.bVesselContact && !Last.bVesselContact) Fire(TEXT("rules.collision"));
	if (F.bBigWakeNear) Fire(TEXT("rules.wake"));

	// Weather.
	if (F.Storm == EStormPhase::Building) Fire(TEXT("weather.storm_building"));
	if (F.Storm == EStormPhase::GustFront) Fire(TEXT("weather.gust_front"));
	if (F.Storm == EStormPhase::Rain) Fire(TEXT("weather.lightning"));
	if (!F.bTidal && F.AirTempF > 95.0) Fire(TEXT("weather.heat"));
	{
		const FSample* S = Ago(60.0);
		const double From = FMath::Fmod(F.WindFromDeg + 360.0, 360.0);
		if (S && (From > 315.0 || From < 45.0) && S->Tws > 3.0 && F.TwsKnots > S->Tws * 1.4) Fire(TEXT("weather.front"));
	}
	if (Hold(TEXT("calm"), F.TwsKnots < 3.0, 60.0, F)) Fire(TEXT("weather.calm"));

	// The drill.
	if (F.Drill == ESailingDrill::SailATriangle && F.bDrillActive && F.MarkDistance >= 0.0 && F.MarkDistance < 30.0) Fire(TEXT("mark.rounding"));
	if (F.bDrillComplete && !Last.bDrillComplete && F.Drill != ESailingDrill::None) Fire(TEXT("drill.complete"));

	Last = F;
}

// ---------------------------------------------------------------- coach

void FLearningCoach::Reset()
{
	*this = FLearningCoach();
}

void FLearningCoach::Update(const FLearningFrame& F, const FLearningContent& Content)
{
	Fired.Reset();
	Events.Update(F, Fired);
	const FLearningTip* Best = nullptr;
	int32 BestScore = -1;
	for (const FString& Event : Fired)
	{
		for (const FLearningTip& T : Content.Tips)
		{
			if (T.Event != Event || !T.Fits(F.Drill)) continue;
			if (T.bOncePerSession && Shown.Contains(T.Id)) continue;
			if (const double* Last = LastShown.Find(T.Id); Last && F.Time - *Last < T.Cooldown) continue;
			// The running drill's own tip beats an Any tip; then the higher level.
			const int32 Score = T.Level * 2 + (T.IsAny() ? 0 : 10);
			if (Score > BestScore) { Best = &T; BestScore = Score; }
		}
	}
	if (!Best) return;
	// Keep a tip up at least 6 s unless something more urgent comes.
	if (Tip && F.Time - TipAt < 6.0 && Best->Level <= Tip->Level) return;
	Tip = Best;
	TipAt = F.Time;
	LastShown.Add(Best->Id, F.Time);
	Shown.Add(Best->Id);
}
