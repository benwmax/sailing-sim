#include "Career.h"
#include "SailingSim.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace CareerLocal
{
	const TCHAR* const MedalIds[] = { TEXT(""), TEXT("bronze"), TEXT("silver"), TEXT("gold") };

	TArray<FString> Strings(const FJsonObject& O, const TCHAR* Key)
	{
		TArray<FString> Out;
		const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
		if (O.TryGetArrayField(Key, List))
		{
			for (const TSharedPtr<FJsonValue>& V : *List)
			{
				FString S;
				if (V.IsValid() && V->TryGetString(S)) Out.Add(S);
			}
		}
		return Out;
	}

	TSharedPtr<FJsonObject> Child(const FJsonObject& O, const TCHAR* Key)
	{
		const TSharedPtr<FJsonObject>* C = nullptr;
		return O.TryGetObjectField(Key, C) && C ? *C : TSharedPtr<FJsonObject>();
	}

	FCareerUnlocks ReadUnlocks(const TSharedPtr<FJsonObject>& O)
	{
		FCareerUnlocks U;
		if (!O) return U;
		U.Tiers = Strings(*O, TEXT("tiers"));
		U.Worlds = Strings(*O, TEXT("worlds"));
		U.Boats = Strings(*O, TEXT("boats"));
		return U;
	}

	FCareerMedalRule ReadRule(const TSharedPtr<FJsonObject>& O)
	{
		FCareerMedalRule R;
		if (!O) return R;
		R.Outcomes = Strings(*O, TEXT("outcomes"));
		O->TryGetNumberField(TEXT("max_seconds"), R.MaxSeconds);
		O->TryGetNumberField(TEXT("max_contact_kn"), R.MaxContactKnots);
		O->TryGetNumberField(TEXT("max_collisions"), R.MaxCollisions);
		O->TryGetNumberField(TEXT("max_infractions"), R.MaxInfractions);
		return R;
	}

	/** True when A (the better medal) asks at least what B asks. */
	bool Stricter(const FCareerMedalRule& A, const FCareerMedalRule& B)
	{
		if (B.Outcomes.Num() && (!A.Outcomes.Num() || A.Outcomes.ContainsByPredicate([&B](const FString& O) { return !B.Outcomes.Contains(O); }))) return false;
		auto Limit = [](double Hi, double Lo) { return Lo < 0.0 || (Hi >= 0.0 && Hi <= Lo); };
		return Limit(A.MaxSeconds, B.MaxSeconds) && Limit(A.MaxContactKnots, B.MaxContactKnots) && Limit(A.MaxCollisions, B.MaxCollisions)
			&& Limit(A.MaxInfractions, B.MaxInfractions);
	}
}

bool FCareerMedalRule::Holds(const FCareerRun& Run) const
{
	if (!Run.bComplete) return false;
	if (Outcomes.Num() && !Outcomes.Contains(Run.Outcome)) return false;
	if (MaxSeconds >= 0.0 && Run.Seconds > MaxSeconds) return false;
	if (MaxContactKnots >= 0.0 && Run.MaxContactKnots > MaxContactKnots) return false;
	if (MaxCollisions >= 0 && Run.Collisions > MaxCollisions) return false;
	if (MaxInfractions >= 0 && Run.Infractions > MaxInfractions) return false;
	return true;
}

// ---------------------------------------------------------------- content

FString FCareerContent::Dir()
{
	return FPaths::ProjectContentDir() / TEXT("Career");
}

const FCareerContent& FCareerContent::Get()
{
	static FCareerContent Content;
	static bool bTried = false;
	if (!bTried)
	{
		bTried = true;
		FString Error;
		if (!Content.Load(Dir(), &Error)) UE_LOG(LogSailing, Warning, TEXT("Career content: %s"), *Error);
	}
	return Content;
}

bool FCareerContent::Load(const FString& Directory, FString* OutError)
{
	FString Text;
	const FString Path = Directory / TEXT("career.json");
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		*this = FCareerContent();
		if (OutError) *OutError = FString::Printf(TEXT("cannot read %s"), *Path);
		return false;
	}
	return LoadText(Text, OutError);
}

bool FCareerContent::LoadText(const FString& Json, FString* OutError)
{
	using namespace CareerLocal;
	*this = FCareerContent();
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root) || !Root.IsValid())
	{
		if (OutError) *OutError = TEXT("career.json is not a JSON object");
		return false;
	}
	int32 Schema = 0;
	if (!Root->TryGetNumberField(TEXT("schema_version"), Schema) || Schema != 1)
	{
		if (OutError) *OutError = FString::Printf(TEXT("career.json schema_version %d (this game reads 1)"), Schema);
		return false;
	}
	Root->TryGetStringField(TEXT("school"), School);
	AlwaysOpen = ReadUnlocks(Child(*Root, TEXT("always_open")));
	const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
	if (Root->TryGetArrayField(TEXT("tiers"), List))
	{
		for (const TSharedPtr<FJsonValue>& V : *List)
		{
			const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
			if (!O) continue;
			FCareerTier T;
			O->TryGetStringField(TEXT("id"), T.Id);
			O->TryGetStringField(TEXT("name"), T.Name);
			O->TryGetStringField(TEXT("status"), T.Status);
			O->TryGetStringField(TEXT("summary"), T.Summary);
			O->TryGetStringField(TEXT("learning"), T.Learning);
			O->TryGetStringField(TEXT("world"), T.WorldId);
			O->TryGetStringField(TEXT("notes"), T.Notes);
			T.Boats = Strings(*O, TEXT("boats"));
			const TArray<TSharedPtr<FJsonValue>>* Lessons = nullptr;
			if (O->TryGetArrayField(TEXT("lessons"), Lessons))
			{
				for (const TSharedPtr<FJsonValue>& LV : *Lessons)
				{
					const TSharedPtr<FJsonObject> LO = LV.IsValid() ? LV->AsObject() : nullptr;
					if (!LO) continue;
					FCareerLesson L;
					L.TierId = T.Id;
					LO->TryGetStringField(TEXT("id"), L.Id);
					LO->TryGetStringField(TEXT("title"), L.Title);
					LO->TryGetStringField(TEXT("drill"), L.DrillId);
					LO->TryGetStringField(TEXT("quiz"), L.QuizId);
					LO->TryGetNumberField(TEXT("quiz_pass"), L.QuizPass);
					L.Drill = FLearningContent::DrillFromId(L.DrillId);
					L.QuizDrill = FLearningContent::DrillFromId(L.QuizId);
					if (const TSharedPtr<FJsonObject> M = Child(*LO, TEXT("medals")))
					{
						for (int32 I = 0; I < 3; ++I) L.Medals[I] = ReadRule(Child(*M, MedalIds[I + 1]));
					}
					T.Lessons.Add(MoveTemp(L));
				}
			}
			if (const TSharedPtr<FJsonObject> C = Child(*O, TEXT("checkride")))
			{
				C->TryGetStringField(TEXT("id"), T.Checkride.Id);
				C->TryGetStringField(TEXT("title"), T.Checkride.Title);
				T.Checkride.Lessons = Strings(*C, TEXT("lessons"));
				FString Min;
				if (C->TryGetStringField(TEXT("min_medal"), Min)) T.Checkride.MinMedal = MedalFromId(Min);
				if (const TSharedPtr<FJsonObject> Q = Child(*C, TEXT("quiz")))
				{
					T.Checkride.Quiz.DrillIds = Strings(*Q, TEXT("drills"));
					for (const FString& D : T.Checkride.Quiz.DrillIds) T.Checkride.Quiz.Drills.Add(FLearningContent::DrillFromId(D));
					Q->TryGetNumberField(TEXT("questions"), T.Checkride.Quiz.Questions);
					Q->TryGetNumberField(TEXT("pass"), T.Checkride.Quiz.Pass);
				}
			}
			if (const TSharedPtr<FJsonObject> C = Child(*O, TEXT("certificate")))
			{
				C->TryGetStringField(TEXT("id"), T.CertificateId);
				C->TryGetStringField(TEXT("name"), T.CertificateName);
			}
			T.Unlocks = ReadUnlocks(Child(*O, TEXT("unlocks")));
			Tiers.Add(MoveTemp(T));
		}
	}
	if (Tiers.Num() == 0)
	{
		if (OutError) *OutError = TEXT("career.json has no tiers");
		return false;
	}
	bLoaded = true;
	return true;
}

TArray<FString> FCareerContent::Validate(const FLearningContent& Learning) const
{
	using namespace CareerLocal;
	TArray<FString> Bad;
	auto Check = [&Bad](bool bOk, const FString& Message) { if (!bOk) Bad.Add(Message); };
	TSet<FString> TierIds, LessonIds, Certificates;
	for (const FCareerTier& T : Tiers)
	{
		Check(!TierIds.Contains(T.Id) && !T.Id.IsEmpty(), FString::Printf(TEXT("tier id '%s' empty or repeated"), *T.Id));
		TierIds.Add(T.Id);
	}
	for (const FString& T : AlwaysOpen.Tiers) Check(TierIds.Contains(T), FString::Printf(TEXT("always_open: unknown tier %s"), *T));
	for (const FString& W : AlwaysOpen.Worlds) Check(FSailSave::WorldIndex(W) >= 0, FString::Printf(TEXT("always_open: unknown world %s"), *W));
	for (const FString& B : AlwaysOpen.Boats) Check(FSailSave::BoatIndex(B) >= 0, FString::Printf(TEXT("always_open: unknown boat %s"), *B));
	for (const FCareerTier& T : Tiers)
	{
		Check(FSailSave::WorldIndex(T.WorldId) >= 0, FString::Printf(TEXT("%s: unknown world %s"), *T.Id, *T.WorldId));
		for (const FString& B : T.Boats) Check(FSailSave::BoatIndex(B) >= 0, FString::Printf(TEXT("%s: unknown boat %s"), *T.Id, *B));
		Check(T.Status == TEXT("ready") || T.Status == TEXT("stub"), FString::Printf(TEXT("%s: status '%s'"), *T.Id, *T.Status));
		Check(T.Status != TEXT("ready") || T.Lessons.Num() > 0, FString::Printf(TEXT("%s: a ready tier needs lessons"), *T.Id));
		Check(!T.CertificateId.IsEmpty() && !T.CertificateName.IsEmpty() && !Certificates.Contains(T.CertificateId), FString::Printf(TEXT("%s: certificate id and name, unique"), *T.Id));
		Certificates.Add(T.CertificateId);
		for (const FCareerLesson& L : T.Lessons)
		{
			Check(!LessonIds.Contains(L.Id) && L.Id.StartsWith(T.Id + TEXT(".")), FString::Printf(TEXT("%s: lesson id repeated or outside its tier"), *L.Id));
			LessonIds.Add(L.Id);
			Check(L.Drill != ESailingDrill::None && Learning.Briefing(L.Drill), FString::Printf(TEXT("%s: drill %s is not in Content/Learning"), *L.Id, *L.DrillId));
			const FDrillBriefing* Q = Learning.Briefing(L.QuizDrill);
			Check(L.QuizDrill != ESailingDrill::None && Q && Q->QuizAfter > 0, FString::Printf(TEXT("%s: quiz %s has no quiz in Content/Learning"), *L.Id, *L.QuizId));
			Check(L.QuizPass > 0.0 && L.QuizPass <= 1.0, FString::Printf(TEXT("%s: quiz_pass %.2f"), *L.Id, L.QuizPass));
			const TArray<FString> Outcomes = FDrillRunner::Outcomes(L.Drill);
			for (int32 M = 0; M < 3; ++M)
			{
				for (const FString& O : L.Medals[M].Outcomes) Check(Outcomes.Contains(O), FString::Printf(TEXT("%s %s: '%s' is not an outcome of the drill"), *L.Id, MedalIds[M + 1], *O));
			}
			Check(Stricter(L.Medals[1], L.Medals[0]), FString::Printf(TEXT("%s: silver asks less than bronze"), *L.Id));
			Check(Stricter(L.Medals[2], L.Medals[1]), FString::Printf(TEXT("%s: gold asks less than silver"), *L.Id));
		}
		Check(T.Checkride.Id == T.Id + TEXT(".checkride"), FString::Printf(TEXT("%s: checkride id '%s'"), *T.Id, *T.Checkride.Id));
		Check(T.Checkride.MinMedal != ECareerMedal::None, FString::Printf(TEXT("%s: checkride min_medal"), *T.Id));
		for (const FString& L : T.Checkride.Lessons) Check(T.Lesson(L) != nullptr, FString::Printf(TEXT("%s checkride: %s is not one of its lessons"), *T.Id, *L));
		if (T.IsReady())
		{
			Check(T.Checkride.Lessons.Num() == T.Lessons.Num(), FString::Printf(TEXT("%s checkride: covers %d of %d lessons"), *T.Id, T.Checkride.Lessons.Num(), T.Lessons.Num()));
			Check(T.Checkride.Quiz.IsSet(), FString::Printf(TEXT("%s checkride: no quiz"), *T.Id));
			int32 Available = 0;
			for (const FQuizQuestion& Q : Learning.Questions)
			{
				Available += Q.Drills.Num() == 0 || Q.Drills.ContainsByPredicate([&T](ESailingDrill D) { return T.Checkride.Quiz.Drills.Contains(D); });
			}
			for (const ESailingDrill D : T.Checkride.Quiz.Drills) Check(D != ESailingDrill::None, FString::Printf(TEXT("%s checkride quiz: unknown drill"), *T.Id));
			Check(T.Checkride.Quiz.Questions <= Available, FString::Printf(TEXT("%s checkride quiz: %d questions, %d available"), *T.Id, T.Checkride.Quiz.Questions, Available));
		}
		for (const FString& U : T.Unlocks.Tiers) Check(Tiers.ContainsByPredicate([&U](const FCareerTier& X) { return X.Id == U; }) && U != T.Id, FString::Printf(TEXT("%s unlocks: unknown tier %s"), *T.Id, *U));
		for (const FString& W : T.Unlocks.Worlds) Check(FSailSave::WorldIndex(W) >= 0, FString::Printf(TEXT("%s unlocks: unknown world %s"), *T.Id, *W));
		for (const FString& B : T.Unlocks.Boats) Check(FSailSave::BoatIndex(B) >= 0, FString::Printf(TEXT("%s unlocks: unknown boat %s"), *T.Id, *B));
	}
	return Bad;
}

const FCareerTier* FCareerContent::Tier(const FString& Id) const
{
	return Tiers.FindByPredicate([&Id](const FCareerTier& T) { return T.Id == Id; });
}

const FCareerTier* FCareerContent::TierOfCertificate(const FString& CertificateId) const
{
	return Tiers.FindByPredicate([&CertificateId](const FCareerTier& T) { return T.CertificateId == CertificateId; });
}

const FCareerLesson* FCareerContent::Lesson(const FString& Id) const
{
	for (const FCareerTier& T : Tiers)
	{
		if (const FCareerLesson* L = T.Lesson(Id)) return L;
	}
	return nullptr;
}

TArray<FQuizQuestion> FCareerContent::MakeCheckrideQuiz(const FCareerTier& T, const FLearningContent& Learning, FRandomStream& Rng) const
{
	TArray<const FQuizQuestion*> Pool;
	for (const FQuizQuestion& Q : Learning.Questions)
	{
		if (Q.Drills.Num() == 0 || Q.Drills.ContainsByPredicate([&T](ESailingDrill D) { return T.Checkride.Quiz.Drills.Contains(D); })) Pool.Add(&Q);
	}
	for (int32 I = Pool.Num() - 1; I > 0; --I) Pool.Swap(I, Rng.RandRange(0, I));
	TArray<FQuizQuestion> Out;
	for (int32 I = 0; I < Pool.Num() && Out.Num() < T.Checkride.Quiz.Questions; ++I)
	{
		FQuizQuestion Q = *Pool[I];
		const FString Right = Q.Options.IsValidIndex(Q.Answer) ? Q.Options[Q.Answer] : FString();
		for (int32 K = Q.Options.Num() - 1; K > 0; --K) Q.Options.Swap(K, Rng.RandRange(0, K));
		Q.Answer = Q.Options.IndexOfByKey(Right);
		Out.Add(MoveTemp(Q));
	}
	return Out;
}

ECareerMedal FCareerContent::Grade(const FCareerLesson& Lesson, const FCareerRun& Run)
{
	if (!Run.bComplete || Run.Drill != Lesson.Drill) return ECareerMedal::None;
	ECareerMedal Best = ECareerMedal::None;
	for (int32 I = 0; I < 3; ++I)
	{
		if (!Lesson.Medals[I].Holds(Run)) break;   // a medal needs every medal below it
		Best = ECareerMedal(I + 1);
	}
	return Best;
}

FString FCareerContent::MedalId(ECareerMedal Medal) { return CareerLocal::MedalIds[FMath::Clamp(int32(Medal), 0, 3)]; }

ECareerMedal FCareerContent::MedalFromId(const FString& Id)
{
	for (int32 I = 1; I < 4; ++I) if (Id == CareerLocal::MedalIds[I]) return ECareerMedal(I);
	return ECareerMedal::None;
}

FString FCareerContent::MedalName(ECareerMedal Medal)
{
	if (Medal == ECareerMedal::Gold) return TEXT("Gold");
	if (Medal == ECareerMedal::Silver) return TEXT("Silver");
	if (Medal == ECareerMedal::Bronze) return TEXT("Bronze");
	return TEXT("No medal");
}

// ---------------------------------------------------------------- progress

const FCareerLesson* FCareerProgress::LessonForRun(const FCareerRun& Run, bool bOpenEverything) const
{
	const FCareerLesson* Found = nullptr;
	for (const FCareerTier& T : Content.Tiers)
	{
		if (!IsTierOpen(T.Id, bOpenEverything) || (T.Boats.Num() && !T.Boats.Contains(Run.BoatId))) continue;
		for (const FCareerLesson& L : T.Lessons)
		{
			if (L.Drill != Run.Drill) continue;
			if (T.WorldId == Run.WorldId) return &L;
			if (!Found) Found = &L;
		}
	}
	return Found;
}

FCareerProgress::FAward FCareerProgress::RecordRun(const FCareerRun& Run, bool bOpenEverything)
{
	FAward A;
	const FCareerLesson* L = LessonForRun(Run, bOpenEverything);
	if (!L || !Run.bComplete) return A;
	A.LessonId = L->Id;
	A.Seconds = Run.Seconds;
	A.Medal = FCareerContent::Grade(*L, Run);
	FSailSave::FLessonRecord* R = Progress.FindLesson(L->Id);
	if (!R)
	{
		FSailSave::FLessonRecord New;
		New.Id = L->Id;
		R = &Progress.Lessons.Add_GetRef(New);
	}
	++R->Runs;
	const ECareerMedal Before = FCareerContent::MedalFromId(R->Medal);
	if (A.Medal > Before)
	{
		R->Medal = FCareerContent::MedalId(A.Medal);
		A.bNewBest = true;
	}
	if (A.Medal != ECareerMedal::None && (R->BestSeconds <= 0.0 || Run.Seconds < R->BestSeconds))
	{
		A.bBestTime = R->BestSeconds > 0.0;
		R->BestSeconds = Run.Seconds;
	}
	A.Best = FCareerContent::MedalFromId(R->Medal);
	return A;
}

bool FCareerProgress::RecordLessonQuiz(const FString& LessonId, int32 Right, int32 Of)
{
	const FCareerLesson* L = Content.Lesson(LessonId);
	if (!L || Of <= 0) return false;
	FSailSave::FLessonRecord* R = Progress.FindLesson(LessonId);
	if (!R)
	{
		FSailSave::FLessonRecord New;
		New.Id = LessonId;
		R = &Progress.Lessons.Add_GetRef(New);
	}
	const bool bPass = double(Right) >= L->QuizPass * double(Of) - 1e-9;
	if (R->QuizOf == 0 || double(Right) / Of > double(R->QuizBest) / FMath::Max(R->QuizOf, 1)) { R->QuizBest = Right; R->QuizOf = Of; }
	R->bQuizPassed |= bPass;
	return bPass;
}

ECareerMedal FCareerProgress::LessonMedal(const FString& LessonId) const
{
	const FSailSave::FLessonRecord* R = Progress.FindLesson(LessonId);
	return R ? FCareerContent::MedalFromId(R->Medal) : ECareerMedal::None;
}

bool FCareerProgress::IsLessonClosed(const FString& LessonId) const
{
	const FSailSave::FLessonRecord* R = Progress.FindLesson(LessonId);
	return R && R->bQuizPassed && FCareerContent::MedalFromId(R->Medal) != ECareerMedal::None;
}

int32 FCareerProgress::LessonsAtLeast(const FCareerTier& Tier, ECareerMedal Medal) const
{
	int32 N = 0;
	for (const FCareerLesson& L : Tier.Lessons) N += LessonMedal(L.Id) >= Medal && LessonMedal(L.Id) != ECareerMedal::None;
	return N;
}

int32 FCareerProgress::LessonsClosed(const FCareerTier& Tier) const
{
	int32 N = 0;
	for (const FCareerLesson& L : Tier.Lessons) N += IsLessonClosed(L.Id);
	return N;
}

bool FCareerProgress::IsCheckrideReady(const FString& TierId, FString* OutWhy) const
{
	auto Why = [OutWhy](const FString& S) { if (OutWhy) *OutWhy = S; return false; };
	const FCareerTier* T = Content.Tier(TierId);
	if (!T) return Why(TEXT("Unknown tier"));
	if (!T->IsReady() || !T->Checkride.Quiz.IsSet() || T->Checkride.Lessons.Num() == 0) return Why(TEXT("Lessons for this tier are still being written"));
	int32 Short = 0;
	for (const FString& L : T->Checkride.Lessons) Short += LessonMedal(L) < T->Checkride.MinMedal || LessonMedal(L) == ECareerMedal::None;
	if (Short > 0)
	{
		return Why(FString::Printf(TEXT("Earn %s or better in %d more lesson%s"), *FCareerContent::MedalName(T->Checkride.MinMedal).ToLower(), Short, Short == 1 ? TEXT("") : TEXT("s")));
	}
	if (OutWhy) OutWhy->Reset();
	return true;
}

bool FCareerProgress::RecordCheckrideQuiz(const FString& TierId, int32 Right, int32 Of, const FDateTime& WhenUtc)
{
	const FCareerTier* T = Content.Tier(TierId);
	if (!T || !IsCheckrideReady(TierId) || Of <= 0) return false;
	FSailSave::FCheckrideRecord* R = Progress.FindCheckride(T->Checkride.Id);
	if (!R)
	{
		FSailSave::FCheckrideRecord New;
		New.Id = T->Checkride.Id;
		R = &Progress.Checkrides.Add_GetRef(New);
	}
	if (R->QuizOf == 0 || double(Right) / Of > double(R->QuizBest) / FMath::Max(R->QuizOf, 1)) { R->QuizBest = Right; R->QuizOf = Of; }
	if (!T->Checkride.Quiz.Passes(Right, Of)) return false;
	R->bPassed = true;
	if (Progress.HasCertificate(T->CertificateId)) return false;
	FSailSave::FCertificateRecord C;
	C.Id = T->CertificateId;
	C.EarnedAt = WhenUtc;
	Progress.Certificates.Add(C);
	return true;
}

bool FCareerProgress::IsTierOpen(const FString& TierId, bool bOpenEverything) const
{
	if (!Content.Tier(TierId)) return false;
	if (bOpenEverything || Content.AlwaysOpen.Tiers.Contains(TierId)) return true;
	for (const FSailSave::FCertificateRecord& C : Progress.Certificates)
	{
		const FCareerTier* By = Content.TierOfCertificate(C.Id);
		if (By && By->Unlocks.Tiers.Contains(TierId)) return true;
	}
	return false;
}

void FCareerProgress::Opens(const FCareerTier& T, TSet<FString>& Worlds, TSet<FString>& Boats) const
{
	Worlds.Append(T.Unlocks.Worlds);
	Boats.Append(T.Unlocks.Boats);
	for (const FString& Id : T.Unlocks.Tiers)
	{
		if (const FCareerTier* X = Content.Tier(Id))
		{
			Worlds.Add(X->WorldId);
			Boats.Append(X->Boats);
		}
	}
}

bool FCareerProgress::IsWorldOpen(const FString& WorldId, bool bOpenEverything) const
{
	if (bOpenEverything || Content.AlwaysOpen.Worlds.Contains(WorldId)) return true;
	for (const FCareerTier& T : Content.Tiers)
	{
		if (Content.AlwaysOpen.Tiers.Contains(T.Id) && T.WorldId == WorldId) return true;
	}
	TSet<FString> Worlds, Boats;
	for (const FSailSave::FCertificateRecord& C : Progress.Certificates)
	{
		if (const FCareerTier* By = Content.TierOfCertificate(C.Id)) Opens(*By, Worlds, Boats);
	}
	return Worlds.Contains(WorldId);
}

bool FCareerProgress::IsBoatOpen(const FString& BoatId, bool bOpenEverything) const
{
	if (bOpenEverything || Content.AlwaysOpen.Boats.Contains(BoatId)) return true;
	for (const FCareerTier& T : Content.Tiers)
	{
		if (Content.AlwaysOpen.Tiers.Contains(T.Id) && T.Boats.Contains(BoatId)) return true;
	}
	TSet<FString> Worlds, Boats;
	for (const FSailSave::FCertificateRecord& C : Progress.Certificates)
	{
		if (const FCareerTier* By = Content.TierOfCertificate(C.Id)) Opens(*By, Worlds, Boats);
	}
	return Boats.Contains(BoatId);
}

FString FCareerProgress::LockReason(const FString& Id, bool bWorld) const
{
	// The first certificate (in the file's order) whose earning would open it.
	for (const FCareerTier& T : Content.Tiers)
	{
		TSet<FString> Worlds, Boats;
		Opens(T, Worlds, Boats);
		if ((bWorld ? Worlds : Boats).Contains(Id)) return FString::Printf(TEXT("Earn the %s"), *T.CertificateName);
	}
	return TEXT("Not in the career yet: open it with Settings > Gameplay > Open everything");
}

FString FCareerProgress::WorldLockReason(const FString& WorldId, bool bOpenEverything) const
{
	return IsWorldOpen(WorldId, bOpenEverything) ? FString() : LockReason(WorldId, true);
}

FString FCareerProgress::BoatLockReason(const FString& BoatId, bool bOpenEverything) const
{
	return IsBoatOpen(BoatId, bOpenEverything) ? FString() : LockReason(BoatId, false);
}

void FCareerProgress::AddSession(double SimSeconds, int32 LogEntries, double LogMiles)
{
	if (SimSeconds <= 0.0) return;
	Progress.HoursSailed += SimSeconds / 3600.0;
	++Progress.LogbookSessions;
	Progress.LogbookEntries += FMath::Max(0, LogEntries);
	Progress.LogbookMiles += FMath::Max(0.0, LogMiles);
}

void FCareerProgress::RecordRace(bool bFinished, int32 Place)
{
	++Progress.RacesSailed;
	if (bFinished && Place == 1) ++Progress.RacesWon;
}
