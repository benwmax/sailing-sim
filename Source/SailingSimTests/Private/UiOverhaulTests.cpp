#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "SailSave.h"
#include "UI/SailUIStyle.h"

// UI overhaul (docs/ui-overhaul/): the rules the foundations hold, so a later palette or type change can't quietly break
// them: text contrast on glass and on paper, no type under 15 px at 1080p, capitals only on the short labels, and the
// interface mode (Helpful, Natural, Off) through the save.
namespace SailUiOverhaulTestsLocal
{
	constexpr EAutomationTestFlags OverhaulFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	/** WCAG contrast ratio of two opaque colours (FLinearColor is already linear light). */
	double Contrast(const FLinearColor& A, const FLinearColor& B)
	{
		auto Lum = [](const FLinearColor& C) { return 0.2126 * double(C.R) + 0.7152 * double(C.G) + 0.0722 * double(C.B); };
		const double La = Lum(A), Lb = Lum(B);
		return (FMath::Max(La, Lb) + 0.05) / (FMath::Min(La, Lb) + 0.05);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUiOverhaulTokensTest, "SailingSim.UI.Overhaul.Tokens", SailUiOverhaulTestsLocal::OverhaulFlags)
bool FSailingUiOverhaulTokensTest::RunTest(const FString&)
{
	using namespace SailUiOverhaulTestsLocal;
	// Glass: text on the ink panel.
	TestTrue(TEXT("Fg on Ink is at least 7:1"), Contrast(SailUI::Fg, SailUI::Ink) >= 7.0);
	TestTrue(TEXT("Muted on Ink is at least 4.5:1"), Contrast(SailUI::Muted, SailUI::Ink) >= 4.5);
	TestTrue(TEXT("Dim on Ink is at least 4.5:1"), Contrast(SailUI::Dim, SailUI::Ink) >= 4.5);
	TestTrue(TEXT("Accent on Ink is at least 4.5:1"), Contrast(SailUI::Accent, SailUI::Ink) >= 4.5);
	TestTrue(TEXT("The main button's text on Accent is at least 4.5:1"), Contrast(SailUI::AccentInk, SailUI::Accent) >= 4.5);
	// Paper: ink on chart paper.
	TestTrue(TEXT("PaperInk on Paper is at least 7:1"), Contrast(SailUI::PaperInk, SailUI::Paper) >= 7.0);
	TestTrue(TEXT("PaperMuted on Paper is at least 4.5:1"), Contrast(SailUI::PaperMuted, SailUI::Paper) >= 4.5);
	TestTrue(TEXT("AccentDeep on Paper is at least 4.5:1"), Contrast(SailUI::AccentDeep, SailUI::Paper) >= 4.5);
	// The focus ring is seen against a raised button too (3:1 for a graphic).
	TestTrue(TEXT("Accent on Raise is at least 3:1"), Contrast(SailUI::Accent, SailUI::Raise) >= 3.0);
	// Yellow is caution only: the accent is not yellow any more (aqua: far more blue than red, and not the starboard green).
	TestTrue(TEXT("The accent is aqua"), SailUI::Accent.B > SailUI::Accent.R * 2.f && SailUI::Accent.G > SailUI::Accent.R * 2.f);
	TestTrue(TEXT("The accent is not starboard's green"), SailUI::Accent.B > SailUI::Starboard.B * 2.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUiOverhaulTypeTest, "SailingSim.UI.Overhaul.Type", SailUiOverhaulTestsLocal::OverhaulFlags)
bool FSailingUiOverhaulTypeTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	const int32 Was = S->TextScale;
	ON_SCOPE_EXIT { S->TextScale = Was; };
	const SailUI::EType All[] = { SailUI::EType::Logo, SailUI::EType::ScreenTitle, SailUI::EType::CardTitle, SailUI::EType::CardTitleM, SailUI::EType::CardTitleS,
		SailUI::EType::MenuItem, SailUI::EType::Eyebrow, SailUI::EType::Label, SailUI::EType::Ui, SailUI::EType::Button, SailUI::EType::Value,
		SailUI::EType::InstrumentBig, SailUI::EType::Body, SailUI::EType::Small };
	S->TextScale = 100;
	for (const SailUI::EType T : All)
	{
		// Slate sizes are points at 96 dpi: 0.75 of the pixels at 1080p (rounded to a whole point, so 15 px reads 14.7).
		const double Px = double(SailUI::Font(T).Size) / 0.75;
		TestTrue(FString::Printf(TEXT("Style %d is at least 14.5 px at 1080p (%.1f)"), int32(T), Px), Px >= 14.5);
	}
	// The player's text size reaches the labels and notes, not only the body text.
	const double Label100 = double(SailUI::Font(SailUI::EType::Label).Size), Small100 = double(SailUI::Font(SailUI::EType::Small).Size);
	const double Title100 = double(SailUI::Font(SailUI::EType::ScreenTitle).Size);
	S->TextScale = 150;
	TestTrue(TEXT("Labels grow with the text size"), double(SailUI::Font(SailUI::EType::Label).Size) > Label100 * 1.3);
	TestTrue(TEXT("Notes grow with the text size"), double(SailUI::Font(SailUI::EType::Small).Size) > Small100 * 1.3);
	TestTrue(TEXT("Screen titles keep their size"), FMath::IsNearlyEqual(double(SailUI::Font(SailUI::EType::ScreenTitle).Size), Title100));
	// Capitals only on the short tracked labels.
	TestTrue(TEXT("Labels are capitals"), SailUI::IsUpper(SailUI::EType::Label) && SailUI::IsUpper(SailUI::EType::Eyebrow));
	TestFalse(TEXT("Menu items are sentence case"), SailUI::IsUpper(SailUI::EType::MenuItem));
	TestFalse(TEXT("Buttons are sentence case"), SailUI::IsUpper(SailUI::EType::Button));
	TestFalse(TEXT("Titles are sentence case"), SailUI::IsUpper(SailUI::EType::ScreenTitle));
	TestTrue(TEXT("Sentence case text is left as written"), SailUI::Txt(TEXT("Cast off"), SailUI::EType::Button).ToString() == TEXT("Cast off"));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUiOverhaulModeTest, "SailingSim.UI.Overhaul.Mode", SailUiOverhaulTestsLocal::OverhaulFlags)
bool FSailingUiOverhaulModeTest::RunTest(const FString&)
{
	// The three modes go through the save by name, and a file without one (or with a name this build doesn't know) reads
	// Helpful.
	USailingSettings* Settings = NewObject<USailingSettings>();
	USailSessionSave* Session = NewObject<USailSessionSave>();
	const TCHAR* const Names[] = { TEXT("helpful"), TEXT("natural"), TEXT("off") };
	for (int32 I = 0; I < 3; ++I)
	{
		Settings->UiMode = I;
		FSailSave Save;
		Save.Capture(*Settings, *Session);
		TestEqual(FString::Printf(TEXT("Mode %d is saved by name"), I), Save.Settings.UiMode, FString(Names[I]));
		FSailSave Read;
		FString Message;
		TestEqual(TEXT("The save reads back"), int32(FSailSave::FromJson(Save.ToJson(), Read, &Message)), int32(FSailSave::EResult::Ok));
		USailingSettings* Out = NewObject<USailingSettings>();
		USailSessionSave* OutSession = NewObject<USailSessionSave>();
		Out->UiMode = (I + 1) % 3;
		Read.Apply(*Out, *OutSession);
		TestEqual(FString::Printf(TEXT("Mode %d comes back"), I), Out->UiMode, I);
	}
	FSailSave Unknown;
	Unknown.Settings.UiMode = TEXT("cinematic");
	Settings->UiMode = 2;
	Unknown.Apply(*Settings, *Session);
	TestEqual(TEXT("An unknown mode reads Helpful"), Settings->UiMode, 0);
	TestEqual(TEXT("A new save is Helpful"), FSailSave().Settings.UiMode, FString(TEXT("helpful")));
	TestTrue(TEXT("The names"), FString(SailUI::UiModeName(SailUI::EUiMode::Natural)) == TEXT("Natural"));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingUiOverhaulPaperTest, "SailingSim.UI.Overhaul.Paper", SailUiOverhaulTestsLocal::OverhaulFlags)
bool FSailingUiOverhaulPaperTest::RunTest(const FString&)
{
	using namespace SailUiOverhaulTestsLocal;
	// Phase 2: inside an FScopedPaper the glass tokens are drawn as their paper twins, and only there.
	TestFalse(TEXT("Not on paper by default"), SailUI::OnPaper());
	TestTrue(TEXT("Off paper a token is itself"), SailUI::OnSurface(SailUI::Fg) == SailUI::Fg);
	{
		const SailUI::FScopedPaper Sheet;
		TestTrue(TEXT("On paper inside the scope"), SailUI::OnPaper());
		TestTrue(TEXT("Text is ink"), SailUI::OnSurface(SailUI::Fg) == SailUI::PaperInk);
		TestTrue(TEXT("Quiet text is the quieter ink"), SailUI::OnSurface(SailUI::Muted) == SailUI::PaperMuted && SailUI::OnSurface(SailUI::Dim) == SailUI::PaperMuted);
		TestTrue(TEXT("The accent is the deeper aqua"), SailUI::OnSurface(SailUI::Accent) == SailUI::AccentDeep);
		TestTrue(TEXT("Ink (text on a chosen chip) is paper"), SailUI::OnSurface(SailUI::Ink) == SailUI::Paper);
		TestTrue(TEXT("A token keeps its own opacity"), FMath::IsNearlyEqual(SailUI::OnSurface(SailUI::Accent.CopyWithNewOpacity(0.16f)).A, 0.16f));
		{
			const SailUI::FScopedPaper Glass(false);
			TestFalse(TEXT("A nested glass scope"), SailUI::OnPaper());
		}
		TestTrue(TEXT("Back on paper after it"), SailUI::OnPaper());
		// Every mapped colour reads on paper: text 4.5:1, the side colours and the warning too.
		const FLinearColor* const Texts[] = { &SailUI::Fg, &SailUI::Muted, &SailUI::Dim, &SailUI::Accent, &SailUI::Port, &SailUI::Starboard, &SailUI::Warn };
		for (const FLinearColor* T : Texts)
		{
			TestTrue(FString::Printf(TEXT("%s reads on paper"), *T->ToString()), Contrast(SailUI::OnSurface(*T), SailUI::Paper) >= 4.5);
		}
		TestTrue(TEXT("The main button's text on its fill"), Contrast(SailUI::OnSurface(SailUI::AccentInk), SailUI::OnSurface(SailUI::Accent)) >= 4.5);
	}
	TestFalse(TEXT("Off paper after the scope"), SailUI::OnPaper());
	return true;
}
