#include "UI/SailFrontEnd.h"
#include "UI/SailWidgets.h"
#include "SailingSettings.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Text/STextBlock.h"

/**
 * UI overhaul (docs/ui-overhaul/): the component page. Every colour token, type style and shared widget on one screen,
 * so a single still shows what a change to SailUIStyle or SailWidgets did (developer tools only: Settings > Component
 * page, or -SailingFrontEnd=Components for stills). Nothing here is game state: the sample rows hold their own values.
 */
namespace SailComponentsImpl
{
	TSharedRef<SWidget> Swatch(const TCHAR* Name, const FLinearColor& Colour, const FLinearColor& TextColour)
	{
		const FColor C = Colour.ToFColor(true);
		return SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
			[
				SNew(SBox).WidthOverride(46.f).HeightOverride(24.f)
				[ SNew(SBorder).BorderImage(SailUI::Rounded(Colour.CopyWithNewOpacity(1.f), 3.f, SailUI::Line, 1.f)) ]
			]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(10.f, 0.f, 0.f, 0.f)
			[ SailUI::Text(FString::Printf(TEXT("%s  #%02X%02X%02X"), Name, C.R, C.G, C.B), SailUI::EType::Small, TextColour) ];
	}

	TSharedRef<SWidget> Section(const TCHAR* Name)
	{
		return SNew(SBox).Padding(FMargin(0.f, 14.f, 0.f, 6.f))[ SailUI::Text(Name, SailUI::EType::Eyebrow, SailUI::Accent) ];
	}
}

SSailFrontEnd::FEntry SSailFrontEnd::BuildComponents()
{
	using namespace SailUI;
	using namespace SailComponentsImpl;
	FEntry E;

	// ---- Column 1: colour and type.
	TSharedRef<SVerticalBox> One = SNew(SVerticalBox);
	auto AddOne = [&One](TSharedRef<SWidget> W) { One->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 4.f)[ W ]; };
	AddOne(Section(TEXT("Glass: afloat")));
	struct FToken { const TCHAR* Name; const FLinearColor* Colour; };
	const FToken Glass[] = { { TEXT("Ink"), &Ink }, { TEXT("Panel"), &Panel }, { TEXT("PanelSolid"), &PanelSolid }, { TEXT("Raise"), &Raise }, { TEXT("Line"), &Line },
		{ TEXT("Fg"), &Fg }, { TEXT("Muted"), &Muted }, { TEXT("Dim"), &Dim }, { TEXT("Accent"), &Accent }, { TEXT("Chart"), &Chart }, { TEXT("Water"), &Water },
		{ TEXT("Land"), &Land }, { TEXT("Port"), &Port }, { TEXT("Starboard"), &Starboard }, { TEXT("Warn"), &Warn }, { TEXT("Caution"), &Caution },
		{ TEXT("WindTrue"), &WindTrue }, { TEXT("Brass"), &Brass } };
	{
		TSharedRef<SWrapBox> Wrap = SNew(SWrapBox).UseAllottedSize(true).InnerSlotPadding(FVector2D(18.f, 6.f));
		for (const FToken& T : Glass) Wrap->AddSlot()[ SNew(SBox).WidthOverride(250.f)[ Swatch(T.Name, *T.Colour, Muted) ] ];
		AddOne(PanelBox(Wrap, FMargin(14.f)));
	}
	AddOne(Section(TEXT("Paper: ashore")));
	const FToken Sheet[] = { { TEXT("Paper"), &Paper }, { TEXT("PaperInk"), &PaperInk }, { TEXT("PaperMuted"), &PaperMuted }, { TEXT("PaperLine"), &PaperLine },
		{ TEXT("AccentDeep"), &AccentDeep }, { TEXT("Brass"), &Brass } };
	{
		TSharedRef<SWrapBox> Wrap = SNew(SWrapBox).UseAllottedSize(true).InnerSlotPadding(FVector2D(18.f, 6.f));
		for (const FToken& T : Sheet) Wrap->AddSlot()[ SNew(SBox).WidthOverride(250.f)[ Swatch(T.Name, *T.Colour, PaperMuted) ] ];
		AddOne(SNew(SBorder).BorderImage(Rounded(Paper, RadiusCard, PaperLine, 1.f)).Padding(FMargin(14.f))[ Wrap ]);
	}
	AddOne(Section(TEXT("Type")));
	struct FStyle { const TCHAR* Name; EType Type; };
	const FStyle Styles[] = { { TEXT("ScreenTitle"), EType::ScreenTitle }, { TEXT("CardTitle"), EType::CardTitle }, { TEXT("CardTitleM"), EType::CardTitleM },
		{ TEXT("MenuItem"), EType::MenuItem }, { TEXT("CardTitleS"), EType::CardTitleS }, { TEXT("Button"), EType::Button }, { TEXT("Value"), EType::Value },
		{ TEXT("Ui"), EType::Ui }, { TEXT("Body"), EType::Body }, { TEXT("Small"), EType::Small }, { TEXT("Eyebrow"), EType::Eyebrow }, { TEXT("Label"), EType::Label } };
	for (const FStyle& S : Styles)
	{
		const int32 Px = FMath::RoundToInt32(Font(S.Type).Size / 0.75f);
		AddOne(Text(FString::Printf(TEXT("%s %d: Ready about, 6.4 kn"), S.Name, Px), S.Type, Fg));
	}
	AddOne(Text(TEXT("12.4"), EType::InstrumentBig, Fg));

	// ---- Column 2: the focusable widgets.
	TSharedRef<SVerticalBox> Two = SNew(SVerticalBox);
	auto AddTwo = [&Two](TSharedRef<SWidget> W) { Two->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 8.f)[ W ]; };
	AddTwo(Section(TEXT("Menu rows")));
	const TSharedRef<SSailButton> FirstRow = MenuRow(TEXT("Sail"), TEXT("Pick world, boat and weather"), FSimpleDelegate());
	AddTwo(FirstRow);
	AddTwo(MenuRow(TEXT("Career"), TEXT("Day Sailor · 2 of 6 lessons"), FSimpleDelegate()));
	AddTwo(MenuRow(TEXT("Replays"), TEXT("Sail a run first"), FSimpleDelegate(), false));
	AddTwo(Section(TEXT("Buttons")));
	AddTwo(ActionButton(TEXT("Cast off"), FSimpleDelegate(), true));
	AddTwo(ActionButton(TEXT("Change conditions"), FSimpleDelegate(), false));
	AddTwo(SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)
		[ SNew(SSailButton).Look(EButtonLook::Chip).IsSelected(true).Padding(FMargin(14.f, 5.f))[ Text(TEXT("Chosen chip"), EType::Label, Ink) ] ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)
		[ SNew(SSailButton).Look(EButtonLook::Chip).Padding(FMargin(14.f, 5.f))[ Text(TEXT("Chip"), EType::Label, Fg) ] ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)
		[ SNew(SSailButton).Look(EButtonLook::Chip).IsEnabled(false).Padding(FMargin(14.f, 5.f))[ Text(TEXT("Disabled"), EType::Label, Fg) ] ]);
	AddTwo(Section(TEXT("Cards")));
	AddTwo(SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 10.f, 0.f)
		[
			SNew(SSailButton).Look(EButtonLook::Card).IsSelected(true)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Keelboat"), EType::Eyebrow, Accent) ]
				+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("J/22"), EType::CardTitleM, Fg) ]
				+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("The lesson boat: forgiving, quick to answer the tiller."), EType::Small, Muted, true) ]
			]
		]
		+ SHorizontalBox::Slot().FillWidth(1.f)
		[
			SNew(SSailButton).Look(EButtonLook::Card)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Dinghy"), EType::Eyebrow, Accent) ]
				+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Sunfish"), EType::CardTitleM, Fg) ]
				+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("One sail, one sheet, and you are the ballast."), EType::Small, Muted, true) ]
			]
		]);
	AddTwo(Section(TEXT("Rows")));
	const TSharedRef<float> SliderValue = MakeShared<float>(60.f);
	AddTwo(SNew(SSailSlider).Label(TEXT("Master volume")).Min(0.f).Max(100.f).Step(5.f)
		.Value_Lambda([SliderValue]() { return *SliderValue; })
		.ValueText_Lambda([SliderValue]() { return FString::Printf(TEXT("%.0f"), *SliderValue); })
		.OnChanged_Lambda([SliderValue](float V) { *SliderValue = V; }));
	const TSharedRef<int32> ChoiceValue = MakeShared<int32>(0);
	AddTwo(SNew(SSailChoice).Label(TEXT("Interface")).Options({ TEXT("Helpful"), TEXT("Natural"), TEXT("Off") })
		.Index_Lambda([ChoiceValue]() { return *ChoiceValue; })
		.OnChanged_Lambda([ChoiceValue](int32 I) { *ChoiceValue = I; })
		.Note(TEXT("A row's note: one or two plain sentences on what the choice does.")));

	// ---- Column 3: panels, prompts, paper.
	TSharedRef<SVerticalBox> Three = SNew(SVerticalBox);
	auto AddThree = [&Three](TSharedRef<SWidget> W) { Three->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 8.f)[ W ]; };
	AddThree(Section(TEXT("Glass panel")));
	AddThree(PanelBox(SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Learning tip"), EType::Eyebrow, Accent) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f)[ Text(TEXT("Ease the mainsheet"), EType::CardTitleS, Fg) ]
		+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("She is heeling more than she needs to. Let the sheet out until the boat stands up and the helm goes light."), EType::Body, Muted, true) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)[ Text(TEXT("The quietest text on glass (Dim)."), EType::Small, Dim, true) ]));
	AddThree(Section(TEXT("Pills and prompts")));
	AddThree(SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ Pill(TEXT("Lake"), false) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ Pill(TEXT("New"), true) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ KeyCap(TEXT("Enter"), TEXT("A")) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ KeyCap(TEXT("Esc"), TEXT("B")) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ KeyCap(TEXT("Q"), TEXT("LB")) ]
		+ SHorizontalBox::Slot().AutoWidth()[ KeyCap(TEXT("H"), TEXT("Y")) ]);
	AddThree(Section(TEXT("Port and starboard, caution")));
	AddThree(SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 16.f, 0.f)[ Text(TEXT("P  Port"), EType::Value, Port) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 16.f, 0.f)[ Text(TEXT("S  Starboard"), EType::Value, Starboard) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 16.f, 0.f)[ Text(TEXT("Shallow water"), EType::Value, Warn) ]
		+ SHorizontalBox::Slot().AutoWidth()[ Text(TEXT("Caution"), EType::Value, Caution) ]);
	AddThree(Section(TEXT("Paper sheet")));
	AddThree(SNew(SBorder).BorderImage(Rounded(Paper, RadiusCard, PaperLine, 1.f)).Padding(FMargin(20.f))
	[
		SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Logbook"), EType::Eyebrow, AccentDeep) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f)[ Text(TEXT("Rush Creek to the dam and back"), EType::CardTitleS, PaperInk, true) ]
		+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Ink on chart paper: 4.2 nautical miles, 10 knots from the south gusting 13, two tacks short of perfect."), EType::Body, PaperInk, true) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)[ Text(TEXT("The quieter line on paper (PaperMuted)."), EType::Small, PaperMuted, true) ]
	]);
	AddThree(Section(TEXT("Widgets on paper")));
	{
		// Built inside an FScopedPaper, the same widgets and glass tokens are drawn for paper (SailUI::Surface).
		const FScopedPaper PaperScope;
		const TSharedRef<float> PaperSlider = MakeShared<float>(40.f);
		const TSharedRef<int32> PaperChoice = MakeShared<int32>(1);
		AddThree(SNew(SBorder).BorderImage(Rounded(Paper, RadiusCard, PaperLine, 1.f)).Padding(FMargin(16.f))
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Display"), EType::Eyebrow, Accent) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f)
			[
				SNew(SSailChoice).Label(TEXT("Interface")).Options({ TEXT("Helpful"), TEXT("Natural"), TEXT("Off") })
				.Index_Lambda([PaperChoice]() { return *PaperChoice; })
				.OnChanged_Lambda([PaperChoice](int32 I) { *PaperChoice = I; })
				.Note(TEXT("A note in the quieter ink."))
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 6.f)
			[
				SNew(SSailSlider).Label(TEXT("Brightness")).Min(0.f).Max(100.f).Step(5.f)
				.Value_Lambda([PaperSlider]() { return *PaperSlider; })
				.ValueText_Lambda([PaperSlider]() { return FString::Printf(TEXT("%.0f%%"), *PaperSlider); })
				.OnChanged_Lambda([PaperSlider](float V) { *PaperSlider = V; })
			]
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 8.f, 0.f)[ ActionButton(TEXT("Cast off"), FSimpleDelegate(), true) ]
				+ SHorizontalBox::Slot().FillWidth(1.f)[ ActionButton(TEXT("Cancel"), FSimpleDelegate(), false) ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ Pill(TEXT("Lake"), false) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ Pill(TEXT("New"), true) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ KeyCap(TEXT("Enter"), TEXT("A")) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 12.f, 0.f)[ Text(TEXT("P  Port"), EType::Value, Port) ]
				+ SHorizontalBox::Slot().AutoWidth()[ Text(TEXT("S  Starboard"), EType::Value, Starboard) ]
			]
		]);
	}
	AddThree(Section(TEXT("Interface mode")));
	{
		const EUiMode Now = UiMode();
		AddThree(SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ Pill(UiModeName(EUiMode::Helpful), Now == EUiMode::Helpful) ]
			+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ Pill(UiModeName(EUiMode::Natural), Now == EUiMode::Natural) ]
			+ SHorizontalBox::Slot().AutoWidth()[ Pill(UiModeName(EUiMode::Off), Now == EUiMode::Off) ]);
	}

	auto Column = [](TSharedRef<SWidget> W)
	{
		return SNew(SScrollBox).ScrollWhenFocusChanges(EScrollWhenFocusChanges::AnimatedScroll).NavigationScrollPadding(24.f) + SScrollBox::Slot().Padding(0.f, 0.f, 12.f, 0.f)[ W ];
	};
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(TEXT("Developer"), TEXT("Component page"), 0) ]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 10.f, 0.f, 90.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(0.36f).Padding(0.f, 0.f, 24.f, 0.f)[ Column(One) ]
			+ SHorizontalBox::Slot().FillWidth(0.32f).Padding(0.f, 0.f, 24.f, 0.f)[ Column(Two) ]
			+ SHorizontalBox::Slot().FillWidth(0.32f)[ Column(Three) ]
		];
	E.Focus = FirstRow;
	TArray<TTuple<FString, FString, FString>> Prompts;
	Prompts.Add(MakeTuple(FString(TEXT("Enter")), FString(TEXT("A")), FString(TEXT("Select"))));
	Prompts.Add(MakeTuple(FString(TEXT("Esc")), FString(TEXT("B")), FString(TEXT("Back"))));
	E.Footer = PromptBar(Prompts, TEXT("Every token, type style and shared widget: docs/ui-overhaul"));
	return E;
}
