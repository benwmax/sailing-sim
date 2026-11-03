#include "Misc/AutomationTest.h"
#include "SailSave.h"
#include "SailingSettings.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Internationalization/Regex.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "Career.h"
#include "Drills.h"
#include "FirstJobPlayer.h"
#include "FixedStepper.h"
#include "LakeData.h"
#include "Learning.h"
#include "Marina.h"
#include "SailingGameMode.h"
#include "SailingMath.h"
#include "Wind.h"

// #404 (the vertical slice, #399): the checks that make the first hour safe to hand a tester. Saves carry over from one
// Friday build to the next with their progress, and every action the first hour asks for can be done on a controller.
namespace SliceTestsLocal
{
	constexpr EAutomationTestFlags SliceFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	FString FixtureDir() { return FPaths::ProjectDir() / TEXT("Source/SailingSimTests/Fixtures/Saves"); }

	TSharedPtr<FJsonObject> Parse(const FString& Text)
	{
		TSharedPtr<FJsonObject> Root;
		FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
		return Root;
	}

	const FJsonObject* Child(const FJsonObject& O, const TCHAR* Key)
	{
		const TSharedPtr<FJsonObject>* C = nullptr;
		return O.TryGetObjectField(Key, C) && C && C->IsValid() ? C->Get() : nullptr;
	}

	/** Every value in Want (nested objects too) is the same in Got: the names of the ones that are not. */
	void Missing(const FJsonObject& Want, const FJsonObject& Got, const FString& At, TArray<FString>& Out)
	{
		for (const auto& W : Want.Values)
		{
			FString Key;
			Key = W.Key;
			const FString Path = At.IsEmpty() ? Key : At + TEXT(".") + Key;
			const TSharedPtr<FJsonValue> G = Got.TryGetField(Key);
			if (!G.IsValid()) { Out.Add(Path); continue; }
			if (W.Value->Type == EJson::Object && G->Type == EJson::Object) { Missing(*W.Value->AsObject(), *G->AsObject(), Path, Out); continue; }
			bool bSame = false;
			if (W.Value->Type == EJson::Number && G->Type == EJson::Number) bSame = FMath::IsNearlyEqual(W.Value->AsNumber(), G->AsNumber(), 1e-4);
			else if (W.Value->Type == EJson::Boolean && G->Type == EJson::Boolean) bSame = W.Value->AsBool() == G->AsBool();
			else if (W.Value->Type == EJson::String && G->Type == EJson::String) bSame = W.Value->AsString() == G->AsString();
			else bSame = W.Value->Type == G->Type;
			if (!bSame) Out.Add(Path);
		}
	}
}

/**
 * Save carry-over: every save in Source/SailingSimTests/Fixtures/Saves (one per Friday build, named <date>-<branch>-<commit>,
 * docs/save/README.md) loads in this build, and every lesson, medal, quiz, checkride, certificate, scene and the first
 * launch it holds come through, with the settings and the last session value for value, and again after it is written back. A new build that loses a tester's progress fails here.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSliceSaveCarryOverTest, "SailingSim.Slice.SaveCarryOver", SliceTestsLocal::SliceFlags)
bool FSailingSliceSaveCarryOverTest::RunTest(const FString&)
{
	using namespace SliceTestsLocal;
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *(FixtureDir() / TEXT("*.json")), true, false);
	Files.Sort();
	if (!TestTrue(TEXT("At least one Friday build's save to carry over"), Files.Num() > 0)) return false;
	for (const FString& Name : Files)
	{
		FString Text;
		if (!TestTrue(*(Name + TEXT(": reads")), FFileHelper::LoadFileToString(Text, *(FixtureDir() / Name)))) continue;
		const TSharedPtr<FJsonObject> Raw = Parse(Text);
		if (!TestTrue(*(Name + TEXT(": is JSON")), Raw.IsValid())) continue;
		FSailSave S;
		const FSailSave::EResult R = FSailSave::FromJson(Text, S);
		TestTrue(*(Name + TEXT(": loads in this build (not refused or invalid)")), R == FSailSave::EResult::Ok || R == FSailSave::EResult::Migrated);
		// Through a write and a read: what a tester's next session would load.
		FSailSave Again;
		TestEqual(*(Name + TEXT(": written back, reads again")), int32(FSailSave::FromJson(S.ToJson(), Again)), int32(FSailSave::EResult::Ok));
		const FJsonObject* P = Child(*Raw, TEXT("progress"));
		if (!P) continue;
		for (const FSailSave* Out : { &S, &Again })
		{
			const FString When = Out == &S ? FString(TEXT("loaded")) : FString(TEXT("after a write"));
			// The settings and the last session (Continue), value for value, as this build writes them back.
			if (const TSharedPtr<FJsonObject> Written = Parse(Out->ToJson()))
			{
				for (const TCHAR* Part : { TEXT("settings"), TEXT("lastSession") })
				{
					const FJsonObject* Want = Child(*Raw, Part);
					const FJsonObject* Got = Child(*Written, Part);
					if (!Want) continue;
					TArray<FString> Lost;
					if (Got) Missing(*Want, *Got, Part, Lost);
					TestTrue(*FString::Printf(TEXT("%s, %s: %s kept%s"), *Name, *When, Part, Lost.Num() ? *(TEXT(" (not: ") + FString::Join(Lost, TEXT(", ")) + TEXT(")")) : TEXT("")),
						Got && Lost.Num() == 0);
				}
			}
			if (const FJsonObject* Lessons = Child(*P, TEXT("lessons")))
			{
				for (const auto& L : Lessons->Values)
				{
					FString Id;
					Id = L.Key;
					const FSailSave::FLessonRecord* Rec = Out->Progress.FindLesson(Id);
					if (!TestNotNull(*FString::Printf(TEXT("%s, %s: lesson %s kept"), *Name, *When, *Id), Rec)) continue;
					const FJsonObject& O = *L.Value->AsObject();
					bool bPassed = false;
					O.TryGetBoolField(TEXT("quizPassed"), bPassed);
					TestEqual(*FString::Printf(TEXT("%s, %s: %s's quiz"), *Name, *When, *Id), Rec->bQuizPassed, bPassed);
					// The medal back out as the file wrote it.
					FString Medal;
					if (O.TryGetStringField(TEXT("medal"), Medal))
					{
						const TSharedPtr<FJsonObject> Written = Parse(Out->ToJson());
						const FJsonObject* WP = Written.IsValid() ? Child(*Written, TEXT("progress")) : nullptr;
						const FJsonObject* WL = WP ? Child(*WP, TEXT("lessons")) : nullptr;
						const FJsonObject* WO = WL ? Child(*WL, *Id) : nullptr;
						FString Back;
						if (WO) WO->TryGetStringField(TEXT("medal"), Back);
						TestEqual(*FString::Printf(TEXT("%s, %s: %s's medal"), *Name, *When, *Id), Back, Medal);
					}
				}
			}
			if (const FJsonObject* Certs = Child(*P, TEXT("certificates")))
				for (const auto& C : Certs->Values) { FString Id; Id = C.Key; TestTrue(*FString::Printf(TEXT("%s, %s: certificate %s kept"), *Name, *When, *Id), Out->Progress.HasCertificate(Id)); }
			if (const FJsonObject* Rides = Child(*P, TEXT("checkrides")))
				for (const auto& C : Rides->Values) { FString Id; Id = C.Key; TestNotNull(*FString::Printf(TEXT("%s, %s: checkride %s kept"), *Name, *When, *Id), Out->Progress.FindCheckride(Id)); }
			if (const FJsonObject* Scenes = Child(*P, TEXT("scenes")))
			{
				for (const auto& Sc : Scenes->Values)
				{
					FString Id;
					Id = Sc.Key;
					bool bDone = false;
					Sc.Value->AsObject()->TryGetBoolField(TEXT("done"), bDone);
					TestEqual(*FString::Printf(TEXT("%s, %s: scene %s"), *Name, *When, *Id), Out->Progress.IsSceneDone(Id), bDone);
				}
			}
			if (const FJsonObject* First = Child(*P, TEXT("firstLaunch")))
			{
				bool bSeen = false;
				First->TryGetBoolField(TEXT("seen"), bSeen);
				TestEqual(*FString::Printf(TEXT("%s, %s: the first launch answered"), *Name, *When), Out->Progress.FirstLaunch.bSeen, bSeen);
			}
			double Hours = 0.0;
			if (P->TryGetNumberField(TEXT("hoursSailed"), Hours))
				TestEqual(*FString::Printf(TEXT("%s, %s: hours sailed"), *Name, *When), Out->Progress.HoursSailed, Hours, 1e-6);
		}
	}
	AddInfo(FString::Printf(TEXT("%d Friday build save(s) carried over: %s"), Files.Num(), *FString::Join(Files, TEXT(", "))));
	return true;
}

/**
 * Controller coverage: every action the first hour asks for has a button or stick on the pad by default, both ways for
 * the sheets and the helm. The lessons' own words name their keys ({key:Action} in Content/Learning, resolved to the pad's
 * labels when the pad is in use), so every token there must have a pad binding; and the first job's steps need the helm
 * and the mainsheet, every lesson the menu (pause, the Retake and Next buttons).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSlicePadCoverageTest, "SailingSim.Slice.PadCoverage", SliceTestsLocal::SliceFlags)
bool FSailingSlicePadCoverageTest::RunTest(const FString&)
{
	const TArray<FSailingKeyBinding>& Bindings = GetDefault<USailingInputSettings>()->GetBindings();
	auto PadWays = [&Bindings](FName Action, bool& bUp, bool& bDown)
	{
		bUp = bDown = false;
		for (const FSailingKeyBinding& B : Bindings)
		{
			if (B.Action != Action || !B.Key.IsGamepadKey()) continue;
			if (B.Key.IsAxis1D() || B.Key.IsAxis2D()) { bUp = bDown = true; continue; }   // a stick or trigger pair covers both ways
			(B.Scale < 0.f ? bDown : bUp) = true;
		}
	};
	// The tokens the lessons' text uses.
	TSet<FString> Tokens;
	TArray<FString> Files;
	const FString Dir = FPaths::ProjectContentDir() / TEXT("Learning");
	IFileManager::Get().FindFiles(Files, *(Dir / TEXT("*.json")), true, false);
	for (const FString& F : Files)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *(Dir / F))) continue;
		// The file's "conventions" block only explains the token ({key:Action}); the lessons' text is the rest.
		if (const TSharedPtr<FJsonObject> Root = SliceTestsLocal::Parse(Text))
		{
			Root->RemoveField(TEXT("conventions"));
			Text.Reset();
			FJsonSerializer::Serialize(Root.ToSharedRef(), TJsonWriterFactory<>::Create(&Text));
		}
		FRegexMatcher M(FRegexPattern(TEXT("\\{key:([A-Za-z]+)")), Text);
		while (M.FindNext()) Tokens.Add(M.GetCaptureGroup(1));
	}
	TestTrue(TEXT("The lessons name their keys"), Tokens.Num() >= 5);
	// The first hour's own needs: the first job (helm, mainsheet), every drill (the sheets, dock lines), the menus.
	for (const TCHAR* Core : { TEXT("Tiller"), TEXT("MainSheet"), TEXT("JibSheet"), TEXT("DockLines"), TEXT("Menu") }) Tokens.Add(Core);
	TArray<FString> Missing;
	for (const FString& T : Tokens)
	{
		bool bUp = false, bDown = false;
		PadWays(FName(*T), bUp, bDown);
		const bool bBothWays = T == TEXT("Tiller") || T == TEXT("MainSheet") || T == TEXT("JibSheet");
		const bool bOk = bBothWays ? (bUp && bDown) : (bUp || bDown);
		TestTrue(*FString::Printf(TEXT("%s: on the pad%s"), *T, bBothWays ? TEXT(", both ways") : TEXT("")), bOk);
		if (!bOk) Missing.Add(T);
	}
	AddInfo(FString::Printf(TEXT("%d first-hour actions checked on the pad%s"), Tokens.Num(), Missing.Num() ? *(TEXT("; missing: ") + FString::Join(Missing, TEXT(", "))) : TEXT("")));
	return true;
}

// The first hour played on the physics: the first job, then Day Sailor's six lessons with scripted helmsmen, graded into a
// new save, the quizzes, the checkride and the certificate. Leave the dock starts in the J/22's own slip at Rush Creek and
// backs her out under the outboard (the game's start for the lesson); the others sail in open water as their drill tests do.
namespace SliceFirstHour
{
	using namespace Sailing;

	struct FLessonRun
	{
		FDrillRunner Drill;
		double MaxContactKn = 0.0;
		int32 Collisions = 0;
		FString Notes;
	};

	FAutoTrim Trimmer()
	{
		FAutoTrim Trim;
		Trim.Settings.bHands = false;   // the drill tests' sailors trim as the polars do: what's tested is the lesson
		return Trim;
	}

	FWindField WindFrom(double Knots, double FromDeg)
	{
		FWindParams P;
		P.SpeedKnots = Knots;
		P.FromDegrees = FromDeg;
		return FWindField(P);
	}

	/** Counts contacts begun and the hardest one (kn), as the pawn does for a lesson. */
	struct FContacts
	{
		bool bTouching = false;
		void Update(const FBoatModel& Boat, FLessonRun& Run)
		{
			const bool bNow = Boat.GetTelemetry().bCollision;
			if (bNow) Run.MaxContactKn = FMath::Max(Run.MaxContactKn, Boat.GetTelemetry().BoatSpeed / kKnot);
			Run.Collisions += bNow && !bTouching;
			bTouching = bNow;
		}
	};

	double SegmentDistance(const FVector2D& P, const FObstacleSegment& S)
	{
		const FVector2D A(S.AX, S.AY), B(S.BX, S.BY), AB = B - A;
		const double T = AB.SizeSquared() > 1e-9 ? FMath::Clamp(FVector2D::DotProduct(P - A, AB) / AB.SizeSquared(), 0.0, 1.0) : 0.0;
		return FVector2D::Distance(P, A + AB * T) - S.Radius;
	}

	/**
	 * A way out of the marina for a boat at From: the cheapest path on a 1 m grid (Dijkstra, eight neighbours) through water
	 * 1.8 m deep and 3 m clear of every dock, breakwater and berthed boat, costed to keep to the middle of the fairways,
	 * to the first point ClearOf metres from Start (the drill's 100 m, with room).
	 */
	TArray<FVector2D> PlanWayOut(const FLakeData& Lake, const FVector2D& From, const FVector2D& Start, double ClearOf)
	{
		constexpr int32 N = 360;
		constexpr double Cell = 1.0;
		const FVector2D Origin = From - FVector2D(N * Cell * 0.5, N * Cell * 0.5);
		TArray<const FObstacleSegment*> Near;
		for (const FObstacleSegment& S : Lake.Obstacles)
		{
			if (S.Bottom > 0.5) continue;   // a bridge deck: a mast's problem, not a hull's
			if (FVector2D::Distance(FVector2D(S.AX, S.AY), From) < 300.0 || FVector2D::Distance(FVector2D(S.BX, S.BY), From) < 300.0) Near.Add(&S);
		}
		TArray<float> Clearance;
		Clearance.SetNumUninitialized(N * N);
		for (int32 R = 0; R < N; ++R)
			for (int32 C = 0; C < N; ++C)
			{
				const FVector2D P = Origin + FVector2D((R + 0.5) * Cell, (C + 0.5) * Cell);
				double D = 50.0;
				for (const FObstacleSegment* S : Near) D = FMath::Min(D, SegmentDistance(P, *S));
				Clearance[R * N + C] = Lake.Terrain.DepthAt(P.X, P.Y) < 1.8 ? 0.f : float(D);
			}
		TArray<float> Cost;
		Cost.Init(1e30f, N * N);
		TArray<int32> Prev;
		Prev.Init(INDEX_NONE, N * N);
		auto IndexOf = [&](const FVector2D& P) { return FMath::Clamp(int32((P.X - Origin.X) / Cell), 0, N - 1) * N + FMath::Clamp(int32((P.Y - Origin.Y) / Cell), 0, N - 1); };
		const int32 First = IndexOf(From);
		Cost[First] = 0.f;
		TArray<TPair<float, int32>> Heap;
		auto Less = [](const TPair<float, int32>& A, const TPair<float, int32>& B) { return A.Key < B.Key; };
		Heap.HeapPush(TPair<float, int32>(0.f, First), Less);
		int32 Goal = INDEX_NONE;
		while (Heap.Num())
		{
			TPair<float, int32> Top;
			Heap.HeapPop(Top, Less);
			if (Top.Key > Cost[Top.Value]) continue;
			const int32 R = Top.Value / N, C = Top.Value % N;
			const FVector2D P = Origin + FVector2D((R + 0.5) * Cell, (C + 0.5) * Cell);
			if (FVector2D::Distance(P, Start) >= ClearOf) { Goal = Top.Value; break; }
			for (int32 DR = -1; DR <= 1; ++DR)
				for (int32 DC = -1; DC <= 1; ++DC)
				{
					const int32 R2 = R + DR, C2 = C + DC;
					if ((DR == 0 && DC == 0) || R2 < 0 || C2 < 0 || R2 >= N || C2 >= N) continue;
					const float Clear = Clearance[R2 * N + C2];
					if (Clear < 3.f && Top.Value != First) continue;
					const float Step = float(Cell * FMath::Sqrt(double(DR * DR + DC * DC))) * (1.f + 12.f / FMath::Max(Clear, 0.5f));
					if (Top.Key + Step < Cost[R2 * N + C2])
					{
						Cost[R2 * N + C2] = Top.Key + Step;
						Prev[R2 * N + C2] = Top.Value;
						Heap.HeapPush(TPair<float, int32>(Top.Key + Step, R2 * N + C2), Less);
					}
				}
		}
		TArray<FVector2D> Path;
		for (int32 I = Goal; I != INDEX_NONE; I = Prev[I]) Path.Insert(Origin + FVector2D((I / N + 0.5) * Cell, (I % N + 0.5) * Cell), 0);
		return Path;
	}

	/** The tiller that turns her toward Heading: forward the usual way, astern the other way round. */
	double HelmToward(const FBoatModel& Boat, double Heading, bool bAstern, double Max)
	{
		const double Err = WrapAngle(Heading - Boat.GetTelemetry().Heading);
		const double Rate = Boat.GetState().AngularVelocity.Z;
		return Clamp(bAstern ? -2.0 * Err + 1.0 * Rate : 2.0 * Err - 1.0 * Rate, -Max, Max);
	}

	/**
	 * Leave the dock as the lesson starts it: the J/22 bow in at her home slip, lines on, sails covered. Cast off, back
	 * straight out past the fingers, swing the stern so the bow faces the way out, then motor out along the planned path.
	 */
	FLessonRun LeaveTheDock(const FLakeData& Lake, const FWindField& Wind)
	{
		FLessonRun Run;
		const FMarinaSlip& Home = Lake.Marina.Slips[Lake.Marina.HomeSlip];
		FBoatModel Boat;
		Boat.SetTerrain(&Lake.Terrain);
		Boat.SetObstacles(&Lake.Obstacles);
		const double SlipHeading = Home.HeadingDeg * kDegToRad;
		Boat.Reset(Home.Center.X, Home.Center.Y, SlipHeading, 0.0);
		Boat.GetMooringLines() = FindDockLines(Boat, Lake.Obstacles);
		FBoatControls C;
		C.MainSheet = C.JibSheet = 0.6;
		C.bSailsDown = true;
		Run.Drill.Start(ESailingDrill::LeaveTheDock, Boat, 0.0);
		const FVector2D Bow(FMath::Cos(SlipHeading), FMath::Sin(SlipHeading));
		const FVector2D Out = Home.Center - Bow * 9.0;   // her middle in the fairway, the bow past the fingers' ends
		const TArray<FVector2D> Path = PlanWayOut(Lake, Out, Home.Center, 120.0);
		Run.Notes = FString::Printf(TEXT("%d lines at the slip, a way out of %d m"), int32(Boat.GetMooringLines().size()), Path.Num());
		if (Path.Num() < 10) return Run;
		const FVector2D Ahead = Path[FMath::Min(14, Path.Num() - 1)];
		const double WayOut = FMath::Atan2(Ahead.Y - Out.Y, Ahead.X - Out.X);
		FContacts Contacts;
		int32 Phase = 0, Along = 0;
		double T = 0.0;
		for (int32 I = 0; I < int32(300 * PhysicsHz) && Run.Drill.IsActive(); ++I, T += PhysicsDt)
		{
			const Vec3 O = Boat.OriginPosition();
			const FVector2D P(O.X, O.Y);
			const double Backed = FVector2D::DotProduct(Home.Center - P, Bow);
			if (Phase == 0 && T > 3.0) { Boat.GetMooringLines().clear(); Phase = 1; }   // cast off (the crew lets the lines go)
			if (Phase == 1)
			{
				// Dead slow astern between the fingers: the 3.6 m slip leaves the J/22 a few centimetres a side, so she rubs the
				// finger she lay against on the way out (at -0.4 throttle that rub was 0.9 kn, at -0.25 still 0.7: a dock
				// touch over 1 kn costs the clean departure).
				C.Throttle = Backed < 7.5 ? -0.15 : -0.4;
				// Hold the slip's centreline against the prop walk: off to starboard, turn the bow to starboard so the stern,
				// going first, comes back to port (and the other way round).
				const FVector2D Starboard(-Bow.Y, Bow.X);
				const double Off = FVector2D::DotProduct(P - Home.Center, Starboard);
				C.Tiller = HelmToward(Boat, SlipHeading + FMath::Clamp(0.15 * Off, -0.17, 0.17), true, 0.6);
				if (Backed > 8.5) { Phase = 2; Run.Notes += FString::Printf(TEXT("; backed out at %.0f s"), T); }
			}
			else if (Phase == 2)
			{
				// Still astern, the stern swung so she ends up facing the way out; a few metres more at most.
				C.Throttle = -0.4;
				C.Tiller = HelmToward(Boat, WayOut, true, 0.9);
				if (FMath::Abs(WrapAngle(WayOut - Boat.GetTelemetry().Heading)) < 25.0 * kDegToRad || Backed > 16.0)
				{
					Phase = 3;
					Run.Notes += FString::Printf(TEXT("; facing the way out (%.0f deg off) at %.0f s"), FMath::RadiansToDegrees(WrapAngle(WayOut - Boat.GetTelemetry().Heading)), T);
				}
			}
			else if (Phase == 3)
			{
				// Ahead along the path: the point 7 m past the nearest one.
				while (Along + 1 < Path.Num() && FVector2D::Distance(Path[Along + 1], P) < FVector2D::Distance(Path[Along], P)) ++Along;
				const FVector2D Aim = Path[FMath::Min(Along + 7, Path.Num() - 1)];
				const double Err = WrapAngle(FMath::Atan2(Aim.Y - P.Y, Aim.X - P.X) - Boat.GetTelemetry().Heading);
				C.Throttle = FMath::Abs(Err) > 50.0 * kDegToRad ? 0.25 : 0.45;
				C.Tiller = HelmToward(Boat, FMath::Atan2(Aim.Y - P.Y, Aim.X - P.X), false, 0.8);
			}
			Boat.Step(PhysicsDt, C, Wind);
			const int32 Before = Run.Collisions;
			Contacts.Update(Boat, Run);
			if (Run.Collisions > Before)
				Run.Notes += FString::Printf(TEXT("; touched in phase %d at %.0f s, %.1f kn, %.1f m astern of the slip"), Phase, T, Boat.GetTelemetry().BoatSpeed / kKnot, Backed);
			FDrillContext Ctx;
			Ctx.bTiedUp = Phase == 0;
			Ctx.MaxContactSpeed = Run.MaxContactKn;
			Run.Drill.Update(Boat, Ctx, PhysicsDt);
		}
		return Run;
	}

	FLessonRun SailATriangle()
	{
		FLessonRun Run;
		const FWindField Wind = WindFrom(10.0, 0.0);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -60.0 * kDegToRad, 4.0 * kKnot);
		Run.Drill.Start(ESailingDrill::SailATriangle, Boat, 0.0);
		FAutoTrim Trim = Trimmer();
		FAutopilot Pilot;
		FBoatControls C;
		FContacts Contacts;
		int32 Tack = 1;
		for (int32 I = 0; I < int32(900 * PhysicsHz) && Run.Drill.IsActive(); ++I)
		{
			const Vec3 O = Boat.OriginPosition();
			const FVector2D M = Run.Drill.GetMarks()[Run.Drill.GetNextMark()];
			const double MarkTwa = FMath::RadiansToDegrees(WrapAngle(0.0 - FMath::Atan2(M.Y - O.Y, M.X - O.X)));
			if (FMath::Abs(MarkTwa) < 46.0)
			{
				if (FMath::Abs(MarkTwa) > 2.0 && FMath::Sign(MarkTwa) != Tack && FMath::Abs(MarkTwa) > 44.0) Tack = -Tack;
				Pilot.TargetTWADeg = 45.0 * Tack;
			}
			else
			{
				Pilot.TargetTWADeg = MarkTwa;
				Tack = MarkTwa > 0.0 ? 1 : -1;
			}
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
			Contacts.Update(Boat, Run);
			Run.Drill.Update(Boat, FDrillContext(), PhysicsDt);
		}
		return Run;
	}

	FLessonRun HeaveTo()
	{
		FLessonRun Run;
		const FWindField Wind = WindFrom(12.0, 0.0);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 4.0 * kKnot);
		FAutopilot Pilot;
		Pilot.TargetTWADeg = 45.0;
		FAutoTrim Trim = Trimmer();
		FBoatControls C;
		C.MainSheet = C.JibSheet = 0.2;
		for (int32 I = 0; I < int32(30 * PhysicsHz); ++I) { C = Trim.Update(Boat, C, PhysicsDt); C.Tiller = Pilot.Update(Boat); Boat.Step(PhysicsDt, C, Wind); }
		Run.Drill.Start(ESailingDrill::HeaveTo, Boat, 0.0);
		C.bBackJib = true; C.JibSheet = 0.1; C.MainSheet = 0.8; C.Tiller = 0.0;
		FDrillContext Ctx;
		Ctx.bBackJib = true;
		FContacts Contacts;
		for (int32 I = 0; I < int32(120 * PhysicsHz) && Run.Drill.IsActive(); ++I)
		{
			if (I == int32(6 * PhysicsHz)) C.Tiller = 0.3;
			Boat.Step(PhysicsDt, C, Wind);
			Contacts.Update(Boat, Run);
			Run.Drill.Update(Boat, Ctx, PhysicsDt);
		}
		return Run;
	}

	/** The person-overboard return both methods end with: get downwind of them, then up on a close reach, luffing to stop. */
	struct FPickUp
	{
		bool bBelow = false;
		double Target(const FBoatModel& Boat, const FVector2D& Dummy) 
		{
			const Vec3 O = Boat.OriginPosition();
			const double Dist = FVector2D::Distance(FVector2D(O.X, O.Y), Dummy);
			if (!bBelow && O.X < Dummy.X - 25.0 && FMath::Abs(O.Y - Dummy.Y) < 25.0) bBelow = true;   // the wind blows from +X
			const FVector2D Aim = bBelow ? Dummy : Dummy - FVector2D(35.0, 0.0);
			const double MarkTwa = FMath::RadiansToDegrees(WrapAngle(0.0 - FMath::Atan2(Aim.Y - O.Y, Aim.X - O.X)));
			const double Sign = MarkTwa >= 0.0 ? 1.0 : -1.0;
			return Sign * FMath::Max(FMath::Abs(MarkTwa), bBelow && Dist < 20.0 ? 0.0 : 50.0);
		}
		bool Luffing(const FBoatModel& Boat, const FVector2D& Dummy) const
		{
			const Vec3 O = Boat.OriginPosition();
			const double Dist = FVector2D::Distance(FVector2D(O.X, O.Y), Dummy);
			return bBelow && Dist < 40.0 && Boat.GetTelemetry().BoatSpeed > FMath::Clamp(0.06 * Dist, 0.35, 2.0);
		}
	};

	FLessonRun CrewOverboard(ESailingDrill Method)
	{
		FLessonRun Run;
		const FWindField Wind = WindFrom(10.0, 0.0);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -100.0 * kDegToRad, 5.0 * kKnot);
		Run.Drill.Start(Method, Boat, 0.0);
		FAutoTrim Trim = Trimmer();
		FAutopilot Pilot;
		Pilot.MaxTiller = 0.7;
		FBoatControls C;
		FContacts Contacts;
		FPickUp PickUp;
		const bool bFigure8 = Method == ESailingDrill::CrewOverboardFigureEight;
		int32 Phase = 0;   // figure-eight: 0 away on the reach, 1 tacking, 2 the return
		double T = 0.0;
		for (int32 I = 0; I < int32(300 * PhysicsHz) && Run.Drill.IsActive(); ++I, T += PhysicsDt)
		{
			const Vec3 O = Boat.OriginPosition();
			const FVector2D Dummy = Run.Drill.GetDummy();
			const double Dist = FVector2D::Distance(FVector2D(O.X, O.Y), Dummy);
			const double Twa = FMath::RadiansToDegrees(Boat.GetTelemetry().TrueWindAngle);
			if (bFigure8 && Phase == 0)
			{
				Pilot.TargetTWADeg = 90.0;                          // away on a beam reach, about five lengths
				if (Dist > 40.0) Phase = 1;
			}
			else if (bFigure8 && Phase == 1)
			{
				Pilot.TargetTWADeg = -45.0;                         // tack (not jibe) to come back
				Pilot.MaxTiller = 0.8;
				if (Twa < -30.0) { Phase = 2; Pilot.MaxTiller = 0.7; }
			}
			else if (!bFigure8 && T < 6.0) Pilot.TargetTWADeg = -150.0;   // quick-stop: keep going a moment, then circle
			else Pilot.TargetTWADeg = PickUp.Target(Boat, Dummy);
			C = Trim.Update(Boat, C, PhysicsDt);
			if (PickUp.Luffing(Boat, Dummy)) { C.MainSheet = 1.0; C.JibSheet = 1.0; }
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
			Contacts.Update(Boat, Run);
			Run.Drill.Update(Boat, FDrillContext(), PhysicsDt);
		}
		return Run;
	}

	FLessonRun ReturnAndDock()
	{
		FLessonRun Run;
		std::vector<FObstacleSegment> Dock(1);
		Dock[0].AX = 60.0; Dock[0].AY = -30.0; Dock[0].BX = 60.0; Dock[0].BY = 30.0;
		const FWindField Wind = WindFrom(8.0, 30.0);
		FBoatModel Boat;
		Boat.SetObstacles(&Dock);
		Boat.Reset(0.0, 0.0, -20.0 * kDegToRad, 3.0 * kKnot);
		Run.Drill.Start(ESailingDrill::ReturnAndDock, Boat, 30.0 * kDegToRad);
		FBoatControls C;
		FAutoTrim Trim = Trimmer();
		FContacts Contacts;
		bool bTied = false;
		for (int32 I = 0; I < int32(300 * PhysicsHz) && Run.Drill.IsActive(); ++I)
		{
			const Vec3 O = Boat.OriginPosition();
			const double ToDock = 60.0 - O.X;
			const double Heading = ToDock > 8.0 ? FMath::Atan2(0.0 - O.Y, ToDock) : 90.0 * kDegToRad;
			C.Tiller = Clamp(2.0 * WrapAngle(Heading - Boat.GetTelemetry().Heading) - 1.0 * Boat.GetState().AngularVelocity.Z, -0.6, 0.6);
			const double Tiller = C.Tiller;
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Tiller;
			if (ToDock < 60.0 && Boat.GetTelemetry().BoatSpeed > FMath::Clamp(0.06 * ToDock, 0.35, 2.0)) { C.MainSheet = 1.0; C.JibSheet = 1.0; }
			Boat.Step(PhysicsDt, C, Wind);
			Contacts.Update(Boat, Run);
			if (!bTied && Boat.GetTelemetry().BoatSpeed < 1.0 * kKnot && ToDock < 4.0)
			{
				Boat.GetMooringLines() = FindDockLines(Boat, Dock);
				bTied = !Boat.GetMooringLines().empty();
			}
			FDrillContext Ctx;
			Ctx.bTiedUp = bTied;
			Ctx.MaxContactSpeed = Run.MaxContactKn;
			Run.Drill.Update(Boat, Ctx, PhysicsDt);
		}
		return Run;
	}
}

/**
 * #404: the first hour, start to finish, on the physics. The first job (every call answered), then each Day Sailor lesson
 * sailed by a scripted helmsman and graded as the game grades it; every lesson must reach at least silver (the
 * checkride's bar), every quiz pass, the checkride open and the certificate earned, Galveston and the Catalina 22 with it.
 * Leave the dock is the game's start: the J/22 bow in at her home slip, backed out under the outboard.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSliceFirstHourTest, "SailingSim.Slice.FirstHour", SliceTestsLocal::SliceFlags)
bool FSailingSliceFirstHourTest::RunTest(const FString&)
{
	using namespace SliceFirstHour;
	// The first job.
	FScriptedScene Scene;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("The first job loads (%s)"), *Error), ASailingGameMode::LoadFirstJob(Scene, &Error))) return false;
	const FirstJobPlayer::FJobRun Job = FirstJobPlayer::Play(Scene, true);
	AddInfo(FString::Printf(TEXT("First job: %d of %d steps answered, %.0f s"), Job.Result.StepsPassed, int32(Scene.GetSteps().size()), Job.Result.Seconds));
	TestTrue(TEXT("The first job finishes"), Job.Result.bComplete);
	TestEqual(TEXT("... every step the player's"), Job.Result.StepsAssisted, 0);

	// Day Sailor, lesson by lesson, into a new save.
	FCareerContent Content;
	if (!TestTrue(TEXT("career.json loads"), Content.Load(FCareerContent::Dir(), &Error))) return false;
	const FCareerTier* Day = Content.Tier(TEXT("day-sailor"));
	if (!TestNotNull(TEXT("Day Sailor"), Day)) return false;
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	if (!TestTrue(TEXT("The J/22's home slip"), Lake.Marina.HomeSlip != INDEX_NONE)) return false;
	FSailSave Save;
	FCareerProgress Career(Content, Save.Progress);
	const FLearningContent& Learning = FLearningContent::Get();
	double Sailed = Job.Result.Seconds;
	for (const FCareerLesson& L : Day->Lessons)
	{
		FLessonRun Run;
		switch (L.Drill)
		{
		case ESailingDrill::LeaveTheDock: Run = LeaveTheDock(Lake, WindFrom(8.0, 180.0)); break;
		case ESailingDrill::SailATriangle: Run = SailATriangle(); break;
		case ESailingDrill::HeaveTo: Run = HeaveTo(); break;
		case ESailingDrill::CrewOverboardFigureEight:
		case ESailingDrill::CrewOverboardQuickStop: Run = CrewOverboard(L.Drill); break;
		case ESailingDrill::ReturnAndDock: Run = ReturnAndDock(); break;
		default: break;
		}
		Sailed += Run.Drill.GetElapsed();
		const FCareerProgress::FAward A = Career.RecordRun(MakeCareerRun(Run.Drill, Run.MaxContactKn, Run.Collisions, 0, TEXT("ray-hubbard"), TEXT("J22")));
		AddInfo(FString::Printf(TEXT("%s: %s, %s in %.0f s, %d contacts (hardest %.1f kn)%s%s"), *L.Id, *FCareerContent::MedalName(A.Medal),
			Run.Drill.GetOutcome().IsEmpty() ? TEXT("not finished") : *Run.Drill.GetOutcome(), Run.Drill.GetElapsed(), Run.Collisions, Run.MaxContactKn,
			Run.Notes.IsEmpty() ? TEXT("") : TEXT(": "), *Run.Notes));
		TestTrue(FString::Printf(TEXT("%s sailed to the end"), *L.Id), Run.Drill.IsComplete());
		TestEqual(FString::Printf(TEXT("%s counts for its lesson"), *L.Id), A.LessonId, L.Id);
		TestTrue(FString::Printf(TEXT("%s at silver or better"), *L.Id), A.Medal >= ECareerMedal::Silver);
		FRandomStream Rng(5);
		const int32 Of = Learning.MakeQuiz(L.QuizDrill, Rng).Num();
		TestTrue(FString::Printf(TEXT("%s quiz passes at %d of %d"), *L.Id, Of - 1, Of), Career.RecordLessonQuiz(L.Id, Of - 1, Of));
	}
	FString Why;
	TestEqual(TEXT("Six lessons closed"), Career.LessonsClosed(*Day), Day->Lessons.Num());
	TestTrue(FString::Printf(TEXT("The checkride opens (%s)"), *Why), Career.IsCheckrideReady(Day->Id, &Why));
	FRandomStream Rng(9);
	const TArray<FQuizQuestion> Ride = Content.MakeCheckrideQuiz(*Day, Learning, Rng);
	TestTrue(TEXT("The checkride's quiz passes: the certificate"), Career.RecordCheckrideQuiz(Day->Id, Ride.Num() - 2, Ride.Num(), FDateTime(2026, 11, 21, 18, 0, 0)));
	TestTrue(TEXT("Day Sailor certificate"), Career.HasCertificate(Day->CertificateId));
	TestTrue(TEXT("Galveston opens"), Career.IsWorldOpen(TEXT("galveston-bay")));
	TestTrue(TEXT("The Catalina 22 opens"), Career.IsBoatOpen(TEXT("Catalina22")));
	AddInfo(FString::Printf(TEXT("The first hour on the water: %.0f min sailed"), Sailed / 60.0));
	return true;
}
