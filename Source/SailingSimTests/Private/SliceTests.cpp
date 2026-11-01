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
}

/**
 * Save carry-over: every save in Source/SailingSimTests/Fixtures/Saves (one per Friday build, named <date>-<branch>-<commit>,
 * docs/save/README.md) loads in this build, and every lesson, medal, quiz, checkride, certificate, scene and the first
 * launch it holds come through, and again after it is written back. A new build that loses a tester's progress fails here.
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
			if (const FJsonObject* Lessons = Child(*P, TEXT("lessons")))
			{
				for (const auto& L : Lessons->Values)
				{
					const FSailSave::FLessonRecord* Rec = Out->Progress.FindLesson(L.Key);
					if (!TestNotNull(*FString::Printf(TEXT("%s, %s: lesson %s kept"), *Name, *When, *L.Key), Rec)) continue;
					const FJsonObject& O = *L.Value->AsObject();
					bool bPassed = false;
					O.TryGetBoolField(TEXT("quizPassed"), bPassed);
					TestEqual(*FString::Printf(TEXT("%s, %s: %s's quiz"), *Name, *When, *L.Key), Rec->bQuizPassed, bPassed);
					// The medal back out as the file wrote it.
					FString Medal;
					if (O.TryGetStringField(TEXT("medal"), Medal))
					{
						const TSharedPtr<FJsonObject> Written = Parse(Out->ToJson());
						const FJsonObject* WP = Written.IsValid() ? Child(*Written, TEXT("progress")) : nullptr;
						const FJsonObject* WL = WP ? Child(*WP, TEXT("lessons")) : nullptr;
						const FJsonObject* WO = WL ? Child(*WL, *L.Key) : nullptr;
						FString Back;
						if (WO) WO->TryGetStringField(TEXT("medal"), Back);
						TestEqual(*FString::Printf(TEXT("%s, %s: %s's medal"), *Name, *When, *L.Key), Back, Medal);
					}
				}
			}
			if (const FJsonObject* Certs = Child(*P, TEXT("certificates")))
				for (const auto& C : Certs->Values) TestTrue(*FString::Printf(TEXT("%s, %s: certificate %s kept"), *Name, *When, *C.Key), Out->Progress.HasCertificate(C.Key));
			if (const FJsonObject* Rides = Child(*P, TEXT("checkrides")))
				for (const auto& C : Rides->Values) TestNotNull(*FString::Printf(TEXT("%s, %s: checkride %s kept"), *Name, *When, *C.Key), Out->Progress.FindCheckride(C.Key));
			if (const FJsonObject* Scenes = Child(*P, TEXT("scenes")))
			{
				for (const auto& Sc : Scenes->Values)
				{
					bool bDone = false;
					Sc.Value->AsObject()->TryGetBoolField(TEXT("done"), bDone);
					TestEqual(*FString::Printf(TEXT("%s, %s: scene %s"), *Name, *When, *Sc.Key), Out->Progress.IsSceneDone(Sc.Key), bDone);
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
