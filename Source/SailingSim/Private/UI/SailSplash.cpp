#include "UI/SailSplash.h"
#include "UI/SailUIStyle.h"
#include "UI/SailWidgets.h"
#include "SailingSettings.h"
#include "BenchRunner.h"
#include "Framework/Application/IInputProcessor.h"
#include "Framework/Application/SlateApplication.h"
#include "Engine/Texture2D.h"
#include "Rendering/DrawElements.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace SailSplash
{
	namespace
	{
		bool GShown = false;

		float Unskipped(double T)
		{
			if (T <= 0.0) return 0.f;
			if (T < FadeInSeconds) return float(T / FadeInSeconds);
			if (T < FadeInSeconds + HoldSeconds) return 1.f;
			return float(FMath::Clamp(1.0 - (T - FadeInSeconds - HoldSeconds) / FadeOutSeconds, 0.0, 1.0));
		}
	}

	float ContentAlpha(double T, double SkippedAt)
	{
		if (SkippedAt < 0.0 || T < SkippedAt) return Unskipped(T);
		const float A0 = Unskipped(SkippedAt);
		return float(FMath::Clamp(1.0 - (T - SkippedAt) / SkipFadeSeconds, 0.0, 1.0)) * A0;
	}

	float BackdropAlpha(double T, double SkippedAt)
	{
		// Solid black first, so the first frames are black and the world loading behind it never shows; it lets go as the content leaves.
		if (SkippedAt >= 0.0 && T >= SkippedAt) return float(FMath::Clamp(1.0 - (T - SkippedAt) / SkipFadeSeconds, 0.0, 1.0));
		if (T < FadeInSeconds + HoldSeconds) return 1.f;
		return float(FMath::Clamp(1.0 - (T - FadeInSeconds - HoldSeconds) / FadeOutSeconds, 0.0, 1.0));
	}

	bool IsFinished(double T, double SkippedAt)
	{
		return SkippedAt >= 0.0 && T >= SkippedAt ? T >= SkippedAt + SkipFadeSeconds : T >= TotalSeconds;
	}

	bool NvidiaPluginPresent()
	{
		// No link to the plugin: the Mac and a fresh clone build without it (docs/windows/README.md, "NVIDIA DLSS").
		return IConsoleManager::Get().FindConsoleVariable(TEXT("r.NGX.DLSS.Enable")) != nullptr;
	}

	FString NvidiaAttribution()
	{
		// Wording to be confirmed with NVIDIA when the sample goes to them (docs/splash/README.md).
		return TEXT("Includes NVIDIA DLSS technology");
	}

	bool IsStillRun()
	{
		FString Screen;
		return FParse::Value(SailingArgs::Dev(), TEXT("SailingFrontEnd="), Screen) && Screen == TEXT("Splash");
	}

	bool Wanted()
	{
		if (GShown) return false;
		if (IsRunningCommandlet()) return false;
		// The still hook: every still run passes -SailingBench (IsMeasuring), so this case is let through before it.
		if (IsStillRun()) return true;
		if (USailingSettings::IsMeasuring()) return false;
		// Stills and scripted menu runs go straight to their screen.
		FString Ignore;
		if (FParse::Param(SailingArgs::Dev(), TEXT("SailingNoSplash"))
			|| FParse::Value(SailingArgs::Dev(), TEXT("SailingFrontEnd="), Ignore)
			|| FParse::Value(SailingArgs::Dev(), TEXT("SailingUIScript="), Ignore, false)) return false;
		return true;
	}

	void MarkShown() { GShown = true; }
}

/** Catches the first key, click or pad button while the splash is up, so that it skips and the menus underneath
	 *  never see it. */
	class FSplashSkipper : public IInputProcessor
	{
	public:
		explicit FSplashSkipper(TFunction<void()> InSkip) : SkipFn(MoveTemp(InSkip)) {}
		virtual void Tick(const float, FSlateApplication&, TSharedRef<ICursor>) override {}
		virtual bool HandleKeyDownEvent(FSlateApplication&, const FKeyEvent& E) override { if (!E.IsRepeat()) SkipFn(); return true; }
		virtual bool HandleKeyUpEvent(FSlateApplication&, const FKeyEvent&) override { return false; }
		virtual bool HandleMouseButtonDownEvent(FSlateApplication&, const FPointerEvent&) override { SkipFn(); return true; }
		virtual const TCHAR* GetDebugName() const override { return TEXT("SailSplashSkipper"); }
	private:
		TFunction<void()> SkipFn;
	};


void SSailSplash::Construct(const FArguments& A)
{
	using namespace SailUI;
	OnDone = A._OnDone;
	const FLinearColor Quiet(0.72f, 0.80f, 0.82f, 1.f), Eyebrow(0.43f, 0.60f, 0.64f, 1.f);

	auto MakePanel = [&](const FString& Label, TSharedRef<SWidget> Body)
	{
		return SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 4.f)[ SailUI::Text(Label.ToUpper(), EType::Small, Eyebrow) ]
			+ SVerticalBox::Slot().AutoHeight()[ Body ];
	};

	TSharedRef<SHorizontalBox> Credits = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom)
		[
			MakePanel(TEXT("Engine"), SailUI::Text(TEXT("Made with Unreal Engine"), EType::Body, Quiet))
		]
		+ SHorizontalBox::Slot().FillWidth(1.f)[ SNullWidget::NullWidget ];

	if (A._ShowNvidia)
	{
		// The mark itself goes in only after NVIDIA approves a sample in writing (docs/splash/README.md); until then, words in a box.
		UTexture2D* Mark = SailUI::KeptTexture(TEXT("/Game/UI/Splash/T_NvidiaDLSS"));
		TSharedRef<SWidget> Block = Mark
			? StaticCastSharedRef<SWidget>(SNew(SBox).HeightOverride(48.f)[ SNew(SImage).Image(new FSlateImageBrush(Mark, FVector2f(Mark->GetSizeX(), Mark->GetSizeY()))) ])
			: StaticCastSharedRef<SWidget>(SNew(SBorder).BorderImage(SailUI::Rounded(FLinearColor(0.02f, 0.07f, 0.11f, 0.5f), 3.f, FLinearColor(0.56f, 0.71f, 0.74f, 0.3f), 1.f))
				.Padding(FMargin(12.f, 8.f))[ SailUI::Text(TEXT("NVIDIA DLSS"), EType::Value, Fg) ]);
		Credits->AddSlot().AutoWidth().VAlign(VAlign_Bottom)
		[
			MakePanel(TEXT("Upscaling"), SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 12.f, 0.f)[ Block ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ SailUI::Text(SailSplash::NvidiaAttribution(), EType::Body, Quiet) ])
		];
	}

	Content = SNew(SOverlay)
		+ SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center).Padding(FMargin(0.f, 0.f, 0.f, 120.f))
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ SNew(STextBlock).Text(FText::FromString(TEXT("READY ABOUT"))).Font(SailUI::Font(EType::Logo)).ColorAndOpacity(Fg) ]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 6.f)[ SNew(STextBlock).Text(FText::FromString(TEXT("S A I L I N G"))).Font(SailUI::Font(EType::Label)).ColorAndOpacity(Accent) ]
		]
		+ SOverlay::Slot().VAlign(VAlign_Bottom).Padding(FMargin(64.f, 0.f, 64.f, 44.f))[ Credits ];

	Backdrop = SNew(SBorder).BorderImage(SailUI::White()).BorderBackgroundColor(FLinearColor(0.02f, 0.05f, 0.08f, 1.f));

	ChildSlot
	[
		SNew(SOverlay)
		+ SOverlay::Slot()[ Backdrop.ToSharedRef() ]
		+ SOverlay::Slot()[ Content.ToSharedRef() ]
	];
	Backdrop->SetRenderOpacity(1.f);
	Content->SetRenderOpacity(0.f);

	bHold = A._Hold;
	if (FSlateApplication::IsInitialized() && !bHold)
	{
		Skipper = MakeShared<FSplashSkipper>([this]() { Skip(); });
		FSlateApplication::Get().RegisterInputPreProcessor(Skipper, 0);
	}
}

SSailSplash::~SSailSplash()
{
	if (Skipper.IsValid() && FSlateApplication::IsInitialized()) FSlateApplication::Get().UnregisterInputPreProcessor(Skipper);
}

void SSailSplash::Skip()
{
	if (SkippedAt < 0.0 && !bDone) SkippedAt = T;
}

void SSailSplash::Advance(float DeltaSeconds)
{
	if (bDone) return;
	T += FMath::Clamp(double(DeltaSeconds), 0.0, 0.1);   // a hitch (a map loading behind it) must not eat the hold
	if (bHold) T = FMath::Min(T, SailSplash::FadeInSeconds + 0.5 * SailSplash::HoldSeconds);   // a still: full opacity
	if (Content.IsValid()) Content->SetRenderOpacity(SailSplash::ContentAlpha(T, SkippedAt));
	if (Backdrop.IsValid()) Backdrop->SetRenderOpacity(SailSplash::BackdropAlpha(T, SkippedAt));
	if (SailSplash::IsFinished(T, SkippedAt))
	{
		bDone = true;
		if (Skipper.IsValid() && FSlateApplication::IsInitialized()) FSlateApplication::Get().UnregisterInputPreProcessor(Skipper);
		Skipper.Reset();
		OnDone.ExecuteIfBound();
	}
}

void SSailSplash::Tick(const FGeometry& G, const double Now, const float Dt)
{
	SCompoundWidget::Tick(G, Now, Dt);
	Advance(Dt);
}
