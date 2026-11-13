#include "UI/SailFrontEnd.h"
#include "UI/SailWidgets.h"
#include "UI/SailUIStyle.h"
#include "UI/SailCatalog.h"
#include "BenchRunner.h"
#include "BoatLivery.h"
#include "BoatModel.h"
#include "BoatSkin.h"
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "SkinEditor.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

/**
 * Boat skins (docs/skins/README.md): the Customize screen, reached from the Boat screen, over the showroom. A panel on
 * the left with five tabs (Skins, Paint, Sails, Lines, Wear); the boat on the right wears the draft as it changes. The
 * draft, its undo and what saving does are FSkinEditor's (SkinEditor.h); this file is the Slate around it.
 *
 * Every control works from the keyboard, the pad and the mouse, as the other screens' do. Nothing is saved until Use
 * this look (or Save as new); Back with changes asks once.
 */
namespace SailCustomizeImpl
{
	using FPrompt = TTuple<FString, FString, FString>;

	// Colours real boats wear (sRGB): gelcoats, two-part paints and bottom paints. No chrome, no neon (Bean, Nov 12).
	struct FSwatch { const TCHAR* Name; uint32 Rgb; };
	const FSwatch PaintSwatches[] = {
		{ TEXT("Gelcoat white"), 0xF2F0EA }, { TEXT("Off white"), 0xE8E4D8 }, { TEXT("Cream"), 0xE6DCC3 }, { TEXT("Light grey"), 0xC9CCCF },
		{ TEXT("Grey"), 0x8A9096 }, { TEXT("Dark grey"), 0x3A3F45 }, { TEXT("Black"), 0x16181B }, { TEXT("Navy"), 0x1C2A44 },
		{ TEXT("Royal blue"), 0x1F4E9C }, { TEXT("Light blue"), 0x8FB8D8 }, { TEXT("Teal"), 0x1F6F6B }, { TEXT("Forest green"), 0x1F4D36 },
		{ TEXT("Red"), 0xB3201B }, { TEXT("Burgundy"), 0x5E1B24 }, { TEXT("Yellow"), 0xE3B321 }, { TEXT("Orange"), 0xD9652B } };
	const FSwatch ClothSwatches[] = {
		{ TEXT("White Dacron"), 0xFFFFFF }, { TEXT("Cream"), 0xEDE6D3 }, { TEXT("Tanbark"), 0x7A3B2E }, { TEXT("Light grey"), 0xC9CCCF },
		{ TEXT("Carbon grey"), 0x3A3F45 }, { TEXT("Pale blue"), 0xBFD4E6 }, { TEXT("Yellow"), 0xE8C84A }, { TEXT("Red"), 0xB3201B } };
	const TCHAR* const TabNames[] = { TEXT("Skins"), TEXT("Paint"), TEXT("Sails"), TEXT("Lines"), TEXT("Wear") };
	constexpr int32 NumTabs = 5;
	const TCHAR* const WearNotes[FBoatSkin::NumWearLevels] = {
		TEXT("Out of the mould: bright gelcoat, clean lines, crisp sails."),
		TEXT("A season in: the first scuffs, a faint waterline."),
		TEXT("A club boat: chalky topsides, a scum line, honest wear."),
		TEXT("Decades old and looked after: faded but cared for."),
		TEXT("Left on her mooring: oxidised, stained, rust at the fittings.") };
	const TCHAR* const LineNames[int32(FBoatSkin::ELine::Count)] = { TEXT("Mainsheet"), TEXT("Jib sheet, port"), TEXT("Jib sheet, starboard"), TEXT("Control lines") };

	// The custom colour's limits: strong enough for a red hull, never fluorescent; never pure black or burnt-out white.
	constexpr float MaxStrength = 0.85f;
	constexpr float MinLight = 0.05f;
	constexpr float MaxLight = 0.95f;

	FLinearColor SwatchColour(const FSwatch& S)
	{
		return FLinearColor(FColor(uint8((S.Rgb >> 16) & 255), uint8((S.Rgb >> 8) & 255), uint8(S.Rgb & 255)));
	}

	/** Hue (degrees), strength and lightness as the eye sees them (sRGB) to the linear colour a skin holds, and back. */
	FLinearColor FromHsv(const FVector& Hsv)
	{
		const FLinearColor Srgb = FLinearColor(float(Hsv.X), float(Hsv.Y), float(Hsv.Z)).HSVToLinearRGB();
		return FLinearColor::FromSRGBColor(Srgb.ToFColor(false));
	}
	FVector ToHsv(const FLinearColor& Linear)
	{
		const FColor C = Linear.GetClamped().ToFColorSRGB();
		const FLinearColor Hsv = FLinearColor(C.R / 255.f, C.G / 255.f, C.B / 255.f).LinearRGBToHSV();
		return FVector(Hsv.R, Hsv.G, Hsv.B);
	}

	bool SameColour(const FLinearColor& A, const FLinearColor& B)
	{
		// (as a skin's file holds them: eight bits a channel)
		return A.GetClamped().ToFColorSRGB() == B.GetClamped().ToFColorSRGB();
	}

	/** A paint colour's name: the swatch it is, or "Custom #RRGGBB". */
	FString PaintName(const FLinearColor& C)
	{
		for (const FSwatch& S : PaintSwatches) if (SameColour(SwatchColour(S), C)) return FString(S.Name);
		return FString::Printf(TEXT("Custom %s"), *FBoatSkin::ToHex(C));
	}

	/** A square of colour with a thin edge (so a dark colour shows on the dark panel). */
	TSharedRef<SWidget> ColourChip(TAttribute<FSlateColor> Colour, float Size)
	{
		return SNew(SBox).WidthOverride(Size).HeightOverride(Size)
		[
			SNew(SBorder).BorderImage(SailUI::Rounded(SailUI::Line, 3.f)).Padding(FMargin(1.f))
			[ SNew(SBorder).BorderImage(SailUI::White()).BorderBackgroundColor(Colour) ]
		];
	}

	/** A part's colour on a livery (what the boat shows for it). */
	FLinearColor LiveryPart(const FBoatLivery& L, FSkinEditor::EPart Part)
	{
		switch (Part)
		{
		case FSkinEditor::EPart::Hull: return L.Hull;
		case FSkinEditor::EPart::Deck: return L.Deck;
		case FSkinEditor::EPart::NonSkid: return L.NonSkid;
		case FSkinEditor::EPart::Bottom: return L.Bottom;
		case FSkinEditor::EPart::Boot: return L.bBoot ? L.Boot : L.Hull;
		case FSkinEditor::EPart::Cove: return L.bCove ? L.Cove : L.Hull;
		case FSkinEditor::EPart::Trim: return L.bTeak ? L.Teak : L.Deck;
		default: return L.Spar;
		}
	}
}

bool SSailFrontEnd::CustomizeEnabled()
{
	static SailingArgs::FCachedFlag Off(TEXT("SailingNoCustomize"));
	return !Off.Get();
}

void SSailFrontEnd::OpenCustomize(int32 BoatType)
{
	// Customizing a boat chooses her (the Boat screen comes back on her).
	if (Pending.Boat != BoatType) Pending.LessonId.Reset();
	Pending.Boat = BoatType;
	FocusedBoat = BoatType;
	SkinEdit.Open(BoatType);
	// (-SailingCustomTab=<0..4> opens on a tab, for stills)
	CustomTab = 0;
	if (int32 TabArg = 0; FParse::Value(SailingArgs::Dev(), TEXT("SailingCustomTab="), TabArg)) CustomTab = FMath::Clamp(TabArg, 0, SailCustomizeImpl::NumTabs - 1);
	CustomPart = 0;
	bViewMode = false;
	bCustomBefore = false;
	bCustomBeforeShown = false;
	bCustomLeaveArmed = false;
	bCustomDeleteArmed = false;
	SetCustomMessage(FString());
	CustomShownRevision = SkinEdit.GetRevision();   // she already wears it
	CustomPreviewAt = 0.0;
	CustomSyncHsv();
	Push(ESailScreen::Customize);
}

void SSailFrontEnd::SetCustomMessage(const FString& Message)
{
	// A message is about the draft as it stood: the next change of it takes the message away.
	CustomMessage = Message;
	CustomMessageRevision = SkinEdit.GetRevision();
}

void SSailFrontEnd::SetCustomTab(int32 Tab)
{
	CustomTab = (Tab % SailCustomizeImpl::NumTabs + SailCustomizeImpl::NumTabs) % SailCustomizeImpl::NumTabs;
	bCustomDeleteArmed = false;
	CustomSyncHsv();
	Stack.Last() = Build(ESailScreen::Customize);
	Show(Stack.Last(), true);
}

void SSailFrontEnd::CustomSyncHsv()
{
	const TOptional<FLinearColor> C = SkinEdit.PartColour(FSkinEditor::EPart(FMath::Clamp(CustomPart, 0, int32(FSkinEditor::EPart::Count) - 1)));
	if (!C.IsSet()) return;
	const FVector Hsv = SailCustomizeImpl::ToHsv(C.GetValue());
	// A grey keeps the hue the sliders had (it has none of its own).
	CustomHsv = FVector(Hsv.Y > 0.02 ? Hsv.X : CustomHsv.X, FMath::Min(Hsv.Y, double(SailCustomizeImpl::MaxStrength)),
		FMath::Clamp(Hsv.Z, double(SailCustomizeImpl::MinLight), double(SailCustomizeImpl::MaxLight)));
}

void SSailFrontEnd::TickCustomize(double Time)
{
	ASailboatPawn* P = Pawn();
	const uint32 Revision = SkinEdit.GetRevision();
	if (Revision != CustomShownRevision)
	{
		// A change is looked at as it is made: Before goes off, and the leave and delete guards start again.
		bCustomBefore = false;
		bCustomLeaveArmed = false;
	}
	if (!P) { CustomShownRevision = Revision; bCustomBeforeShown = bCustomBefore; return; }
	if (bCustomBefore != bCustomBeforeShown)
	{
		bCustomBeforeShown = bCustomBefore;
		if (bCustomBefore) P->ClearSkinPreview();
		else P->SetSkinPreview(SkinEdit.GetDraft());
		CustomShownRevision = Revision;
		CustomPreviewAt = Time;
		return;
	}
	// The boat's look is rebuilt for a preview, so a dragged slider is shown at most eight times a second.
	if (Revision != CustomShownRevision && Time - CustomPreviewAt >= 0.12)
	{
		P->SetSkinPreview(SkinEdit.GetDraft());
		CustomShownRevision = Revision;
		CustomPreviewAt = Time;
	}
}

void SSailFrontEnd::EndCustomize()
{
	if (ASailboatPawn* P = Pawn()) P->ClearSkinPreview();
	bCustomBefore = false;
	bCustomBeforeShown = false;
	bCustomLeaveArmed = false;
	bCustomDeleteArmed = false;
	CustomTextBoxes.Reset();
}

void SSailFrontEnd::CustomUse()
{
	if (!SkinEdit.Use())
	{
		SetCustomMessage(TEXT("The skin's file could not be written. Nothing was changed."));
		return;
	}
	if (ASailboatPawn* P = Pawn()) P->RefreshSkin();
	CustomShownRevision = SkinEdit.GetRevision();
	Pop();
}

FReply SSailFrontEnd::CustomizeKeyDown(const FKeyEvent& Event)
{
	const FKey K = Event.GetKey();
	// Typing a name or a sail number: the letters are the box's, not the screen's (V would hide the panels, Q change
	// the tab). Escape gives the focus back to the screen; Up, Down and Tab leave the box as anywhere.
	for (const TSharedPtr<SWidget>& Field : CustomTextBoxes)
	{
		if (!Field.IsValid() || !(Field->HasKeyboardFocus() || Field->HasFocusedDescendants())) continue;
		// (the pad's Back too: it leaves the box, not the screen, so the unsaved-changes question is still asked)
		if (K == EKeys::Escape || (K.IsGamepadKey() && SailUI::IsBackKey(K))) { FocusCurrent(); return FReply::Handled(); }
		if (K == EKeys::Up || K == EKeys::Down || K == EKeys::Tab || K.IsGamepadKey()) return FReply::Unhandled();
		return FReply::Handled();
	}
	if (bViewMode) return FReply::Unhandled();   // the panels are hidden: the stage's own keys only
	if (K == EKeys::Q || K == EKeys::Gamepad_LeftShoulder) { SetCustomTab(CustomTab + SailCustomizeImpl::NumTabs - 1); return FReply::Handled(); }
	if (K == EKeys::E || K == EKeys::Gamepad_RightShoulder) { SetCustomTab(CustomTab + 1); return FReply::Handled(); }
	if (K == EKeys::Z || K == EKeys::Gamepad_FaceButton_Left) { if (SkinEdit.Undo()) CustomSyncHsv(); return FReply::Handled(); }
	if (K == EKeys::Y || K == EKeys::Gamepad_FaceButton_Top) { if (SkinEdit.Redo()) CustomSyncHsv(); return FReply::Handled(); }
	if (K == EKeys::T || K == EKeys::Gamepad_LeftThumbstick) { bCustomBefore = !bCustomBefore; return FReply::Handled(); }
	if (K == EKeys::R || K == EKeys::Gamepad_Special_Right)
	{
		FRandomStream Random(int32(FPlatformTime::Cycles64() & 0x7fffffff));
		SkinEdit.Surprise(Random);
		CustomSyncHsv();
		return FReply::Handled();
	}
	if (SailUI::IsBackKey(K) && SkinEdit.IsUnsaved() && !(bCustomLeaveArmed && CustomLeaveRevision == SkinEdit.GetRevision()))
	{
		bCustomLeaveArmed = true;
		CustomLeaveRevision = SkinEdit.GetRevision();
		SetCustomMessage(TEXT("Not saved yet. Back again leaves without saving; Use this look keeps it."));
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

SSailFrontEnd::FEntry SSailFrontEnd::BuildCustomize()
{
	using namespace SailUI;
	using namespace SailCustomizeImpl;
	FEntry E;
	const int32 Type = SkinEdit.GetBoatType();
	const SailCatalog::FBoat& Boat = SailCatalog::Boat(Type);
	const FBoatLivery ClassLivery = SampleBoatLivery(Type, 0);
	CustomTextBoxes.Reset();
	auto Panels = [this]() { return bViewMode ? EVisibility::Hidden : EVisibility::Visible; };
	// What the boat shows for a part: the draft over her class's livery.
	auto Shown = [this, ClassLivery, Type](FSkinEditor::EPart Part)
	{
		FBoatLivery L = ClassLivery;
		SkinEdit.GetDraft().ApplyTo(L, Type);
		return LiveryPart(L, Part);
	};
	auto CurPart = [this]() { return FSkinEditor::EPart(FMath::Clamp(CustomPart, 0, int32(FSkinEditor::EPart::Count) - 1)); };

	// The tabs: pills (Q/E and LB/RB step along them; the footer says so: the panel is too narrow for keycaps at the ends).
	TSharedRef<SHorizontalBox> TabRow = SNew(SHorizontalBox);
	for (int32 I = 0; I < NumTabs; ++I)
	{
		TabRow->AddSlot().FillWidth(1.f).Padding(2.f, 0.f)
		[
			SNew(SSailButton).Look(EButtonLook::Chip).IsSelected(I == CustomTab).Padding(FMargin(4.f, 6.f)).OnClicked_Lambda([this, I]() { SetCustomTab(I); })
			[ SNew(SBox).HAlign(HAlign_Center)[ SailUI::Text(TabNames[I], EType::Label, I == CustomTab ? Ink : Fg) ] ]
		];
	}

	TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
	auto Add = [&](TSharedRef<SWidget> W, float Below = 6.f) { Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, Below)[ W ]; };
	auto First = [&](const TSharedRef<SWidget>& W) { if (!E.Focus.IsValid()) E.Focus = W; };
	auto Section = [&](const FString& Name) { Rows->AddSlot().AutoHeight().Padding(0.f, 8.f, 0.f, 6.f)[ SailUI::Text(Name, EType::Eyebrow, Accent) ]; };
	auto Note = [&](const FString& S) { Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 8.f)[ SailUI::Text(S, EType::Small, Muted, true) ]; };
	auto SmallButton = [](const FString& Label, TFunction<void()> Do, TAttribute<bool> Enabled = true)
	{
		return SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 7.f)).IsEnabled(Enabled).OnClicked_Lambda([Do]() { Do(); })
			[ SNew(SBox).HAlign(HAlign_Center)[ SailUI::Text(Label, EType::Label, Fg) ] ];
	};
	// A row of swatches: eight to a row, the chosen one ringed.
	auto SwatchRows = [&](const FSwatch* Swatches, int32 Num, TFunction<bool(const FLinearColor&)> IsChosen, TFunction<void(const FLinearColor&)> Choose)
	{
		TSharedRef<SVerticalBox> Grid = SNew(SVerticalBox);
		TSharedPtr<SHorizontalBox> Row;
		for (int32 I = 0; I < Num; ++I)
		{
			if (I % 8 == 0) Grid->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 6.f)[ SAssignNew(Row, SHorizontalBox) ];
			const FLinearColor C = SwatchColour(Swatches[I]);
			TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::Chip).Padding(FMargin(4.f))
				.IsSelected_Lambda([IsChosen, C]() { return IsChosen(C); })
				.OnClicked_Lambda([Choose, C]() { Choose(C); })
				.ToolTipText(FText::FromString(Swatches[I].Name))
			[ ColourChip(FSlateColor(C), 30.f) ];
			Row->AddSlot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)[ B ];
		}
		return Grid;
	};

	switch (CustomTab)
	{
	case 0:
	{
		// Skins: her class's own look, the built-in skins, then the player's. Choosing one puts it on the boat (not saved
		// until Use this look).
		const FString Worn = SailSaveStore::BoatSkin(FSailSave::BoatId(Type));
		auto SkinRow = [&](const FBoatSkin* Skin, const FString& Name)
		{
			const FString Id = Skin ? Skin->Id : FString();
			const TOptional<FBoatSkin> Copy = Skin ? TOptional<FBoatSkin>(*Skin) : TOptional<FBoatSkin>();
			FBoatLivery L = ClassLivery;
			if (Skin) Skin->ApplyTo(L, Type);
			TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::Card).Padding(FMargin(12.f, 8.f))
				.IsSelected_Lambda([this, Id]() { return SkinEdit.GetLoadedId() == Id && !SkinEdit.IsDirty(); })
				.OnClicked_Lambda([this, Copy]()
				{
					SkinEdit.Load(Copy.IsSet() ? &Copy.GetValue() : nullptr);
					bCustomDeleteArmed = false;
					CustomSyncHsv();
				})
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ ColourChip(FSlateColor(L.Hull), 22.f) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.f, 0.f, 10.f, 0.f)[ ColourChip(FSlateColor(L.Deck), 22.f) ]
				+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ SailUI::Text(Name, EType::Ui, Fg) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(8.f, 0.f, 26.f, 0.f)[ SailUI::Text(Worn == Id ? TEXT("On your boat") : TEXT(""), EType::Label, Accent) ]
			];
			Add(B);
			First(B);
		};
		SkinRow(nullptr, TEXT("Class look"));
		Section(TEXT("Built in"));
		const TArray<FBoatSkin> BuiltIn = BoatSkinStore::BuiltIn(Type);
		for (const FBoatSkin& S : BuiltIn) SkinRow(&S, S.Name);
		const TArray<FBoatSkin> Mine = BoatSkinStore::Mine(Type);
		Section(TEXT("Your skins"));
		if (Mine.Num() == 0) Note(TEXT("None yet. Change anything on the other tabs, then Use this look: it is saved here."));
		for (const FBoatSkin& S : Mine) SkinRow(&S, S.Name);
		// The loaded skin's name (the keyboard), and Delete for one of the player's (two presses).
		Section(TEXT("Name"));
		TSharedRef<SEditableTextBox> NameBox = SNew(SEditableTextBox).Font(Font(EType::Body)).HintText(FText::FromString(TEXT("A name for this look")))
			.Text_Lambda([this]() { return FText::FromString(SkinEdit.GetDraft().Name); })
			.ClearKeyboardFocusOnCommit(false)   // (Enter keeps the focus: with none, the keys and the pad have nowhere to go)
			.OnTextCommitted_Lambda([this](const FText& T, ETextCommit::Type) { if (!FBoatSkin::CleanName(T.ToString()).Equals(SkinEdit.GetDraft().Name, ESearchCase::CaseSensitive)) SkinEdit.SetName(T.ToString()); });
		CustomTextBoxes.Add(NameBox);
		Add(SNew(SBox).HeightOverride(40.f)[ NameBox ], 10.f);
		Add(SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 7.f))
			.IsEnabled_Lambda([this]() { return !SkinEdit.GetLoadedId().IsEmpty() && !SkinEdit.IsLoadedBuiltIn(); })
			.OnClicked_Lambda([this]()
			{
				if (!bCustomDeleteArmed) { bCustomDeleteArmed = true; return; }
				bCustomDeleteArmed = false;
				// (the draft is now the class's look; the next tick shows it on the boat, as any change of the draft)
				const bool bDeleted = SkinEdit.DeleteLoaded();
				SetCustomMessage(bDeleted ? FString(TEXT("Deleted.")) : FString(TEXT("That skin's file could not be deleted.")));
				SetCustomTab(0);
			})
			[ SNew(SBox).HAlign(HAlign_Center)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(bCustomDeleteArmed ? TEXT("Press again to delete this skin") : TEXT("Delete this skin")); }), EType::Label, FSlateColor(Fg)) ] ]);
		break;
	}
	case 1:
	{
		// Paint: pick a part, then a colour for it: a real boat's swatch, or your own from the three sliders.
		for (int32 I = 0; I < int32(FSkinEditor::EPart::Count); ++I)
		{
			const FSkinEditor::EPart Part = FSkinEditor::EPart(I);
			TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::Card).Padding(FMargin(12.f, 6.f))
				.IsSelected_Lambda([this, I]() { return CustomPart == I; })
				.OnClicked_Lambda([this, I]() { CustomPart = I; CustomSyncHsv(); })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 10.f, 0.f)
				[ ColourChip(TAttribute<FSlateColor>::CreateLambda([Shown, Part]() { return FSlateColor(Shown(Part)); }), 22.f) ]
				+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ SailUI::Text(FSkinEditor::PartName(Part), EType::Ui, Fg) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(8.f, 0.f, 26.f, 0.f)
				[
					TextAttr(TAttribute<FText>::CreateLambda([this, Part]()
					{
						if (SkinEdit.IsPartOff(Part)) return FText::FromString(Part == FSkinEditor::EPart::Spars ? TEXT("Bare aluminium") : TEXT("None"));
						const TOptional<FLinearColor> C = SkinEdit.PartColour(Part);
						return FText::FromString(C.IsSet() ? PaintName(C.GetValue()) : FString(TEXT("Class colour")));
					}), EType::Small, FSlateColor(Muted))
				]
			];
			Add(B, 4.f);
			First(B);
		}
		Section(TEXT("Colour"));
		Add(SwatchRows(PaintSwatches, int32(UE_ARRAY_COUNT(PaintSwatches)),
			[this, CurPart](const FLinearColor& C) { const TOptional<FLinearColor> Now = SkinEdit.PartColour(CurPart()); return Now.IsSet() && SameColour(Now.GetValue(), C); },
			[this, CurPart](const FLinearColor& C) { SkinEdit.SetPartColour(CurPart(), C); CustomSyncHsv(); }), 2.f);
		Add(SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 6.f, 0.f)[ SmallButton(TEXT("Class colour"), [this, CurPart]() { SkinEdit.ClearPart(CurPart()); }) ]
			+ SHorizontalBox::Slot().FillWidth(1.f)
			[
				SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 7.f))
					.IsEnabled_Lambda([CurPart]() { return FSkinEditor::PartCanBeOff(CurPart()); })
					.OnClicked_Lambda([this, CurPart]() { SkinEdit.SetPartOff(CurPart()); })
				[ SNew(SBox).HAlign(HAlign_Center)[ TextAttr(TAttribute<FText>::CreateLambda([CurPart]() { return FText::FromString(CurPart() == FSkinEditor::EPart::Spars ? TEXT("Bare aluminium") : CurPart() == FSkinEditor::EPart::Trim ? TEXT("No trim") : TEXT("No stripe")); }), EType::Label, FSlateColor(Fg)) ] ]
			], 8.f);
		Section(TEXT("Your own colour"));
		auto Slide = [&](const FString& Label, int32 Axis, float Lo, float Hi, float Step, const TCHAR* Unit)
		{
			Add(SNew(SSailSlider).Label(Label).Min(Lo).Max(Hi).Step(Step)
				.Value_Lambda([this, Axis]() { return float(Axis == 0 ? CustomHsv.X : 100.0 * CustomHsv[Axis]); })
				.ValueText_Lambda([this, Axis, Unit]() { return FString::Printf(TEXT("%.0f%s"), Axis == 0 ? CustomHsv.X : 100.0 * CustomHsv[Axis], Unit); })
				.OnChanged_Lambda([this, Axis, CurPart](float V)
				{
					if (Axis == 0) CustomHsv.X = V; else CustomHsv[Axis] = V / 100.0;
					SkinEdit.SetPartColour(CurPart(), FromHsv(CustomHsv), true);
				}), 2.f);
		};
		Slide(TEXT("Hue"), 0, 0.f, 355.f, 5.f, TEXT("°"));
		Slide(TEXT("Strength"), 1, 0.f, 100.f * MaxStrength, 5.f, TEXT("%"));
		Slide(TEXT("Lightness"), 2, 100.f * MinLight, 100.f * MaxLight, 5.f, TEXT("%"));
		break;
	}
	case 2:
	{
		// Sails: the cloth, the number, the class mark.
		Section(TEXT("Cloth"));
		TSharedRef<SVerticalBox> Cloth = SwatchRows(ClothSwatches, int32(UE_ARRAY_COUNT(ClothSwatches)),
			[this](const FLinearColor& C) { const TOptional<FLinearColor>& Now = SkinEdit.GetDraft().Sails.Cloth; return Now.IsSet() && SameColour(Now.GetValue(), C); },
			[this](const FLinearColor& C) { SkinEdit.SetSailCloth(C); });
		Add(Cloth, 2.f);
		TSharedRef<SSailButton> ClassCloth = SmallButton(TEXT("Class cloth"), [this]() { SkinEdit.SetSailCloth(TOptional<FLinearColor>()); });
		Add(ClassCloth, 8.f);
		First(ClassCloth);
		Section(TEXT("Sail number"));
		TSharedRef<SEditableTextBox> NumberBox = SNew(SEditableTextBox).Font(Font(EType::Body)).HintText(FText::FromString(TEXT("Up to six digits")))
			.Text_Lambda([this, ClassLivery]()
			{
				const TOptional<FString>& N = SkinEdit.GetDraft().Sails.Number;
				return FText::FromString(N.IsSet() ? N.GetValue() : ClassLivery.SailNumber);
			})
			.ClearKeyboardFocusOnCommit(false)
			.OnTextCommitted_Lambda([this, ClassLivery](const FText& T, ETextCommit::Type)
			{
				const TOptional<FString>& N = SkinEdit.GetDraft().Sails.Number;
				const FString Was = N.IsSet() ? N.GetValue() : ClassLivery.SailNumber;
				if (T.ToString() != Was) SkinEdit.SetSailNumber(T.ToString());
			});
		CustomTextBoxes.Add(NumberBox);
		Add(SNew(SBox).HeightOverride(40.f)[ NumberBox ], 6.f);
		Add(SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 6.f, 0.f)[ SmallButton(TEXT("Class number"), [this]() { SkinEdit.SetSailNumber(TOptional<FString>()); }) ]
			+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 6.f, 0.f)[ SmallButton(TEXT("No number"), [this]() { SkinEdit.SetSailNumber(FString()); }) ]
			+ SHorizontalBox::Slot().FillWidth(1.f)[ SmallButton(TEXT("Random"), [this]() { SkinEdit.SetSailNumber(FString::FromInt(FMath::RandRange(1, 9999))); }) ], 8.f);
		Add(SNew(SSailChoice).Label(TEXT("Class mark")).Options({ TEXT("Show"), TEXT("Hide") })
			.Index_Lambda([this]() { const TOptional<bool>& M = SkinEdit.GetDraft().Sails.bClassMark; return M.IsSet() && !M.GetValue() ? 1 : 0; })
			.OnChanged_Lambda([this](int32 I) { SkinEdit.SetClassMark(I == 1 ? TOptional<bool>(false) : TOptional<bool>()); }));
		Note(TEXT("Stripes and sail designs come in a later update."));
		break;
	}
	case 3:
	{
		// Lines: a colourway for each rope. Left and Right (or a click) step through them.
		const bool bJib = Sailing::FBoatConfig::Make(Sailing::EBoatType(FMath::Clamp(Type, 0, int32(Sailing::EBoatType::Count) - 1))).HasJib();
		for (int32 I = 0; I < int32(FBoatSkin::ELine::Count); ++I)
		{
			const FBoatSkin::ELine Role = FBoatSkin::ELine(I);
			if (!bJib && (Role == FBoatSkin::ELine::JibPort || Role == FBoatSkin::ELine::JibStarboard)) continue;
			auto Step = [this, Role, I](int32 Dir)
			{
				const int32 N = FBoatSkin::NumRopeColourways() + 1;   // and "the boat's own" (-1)
				const int32 Now = SkinEdit.GetDraft().Lines.Column[I] + 1;
				SkinEdit.SetLine(Role, ((Now + Dir) % N + N) % N - 1);
			};
			TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::Card).Padding(FMargin(12.f, 10.f))
				.OnClicked_Lambda([Step]() { Step(1); })
				.OnAdjust_Lambda([Step](int32 Dir) { Step(Dir); })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ SailUI::Text(LineNames[I], EType::Ui, Fg) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(8.f, 0.f)
				[
					SNew(SBox).Visibility_Lambda([this, I]() { return SkinEdit.GetDraft().Lines.Column[I] >= 0 ? EVisibility::Visible : EVisibility::Hidden; })
					[ ColourChip(TAttribute<FSlateColor>::CreateLambda([this, I]() { return FSlateColor(FSkinEditor::RopeChip(SkinEdit.GetDraft().Lines.Column[I])); }), 20.f) ]
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[ SNew(SBox).MinDesiredWidth(150.f)[ TextAttr(TAttribute<FText>::CreateLambda([this, I]() { return FText::FromString(FSkinEditor::RopeName(SkinEdit.GetDraft().Lines.Column[I])); }), EType::Small, FSlateColor(Muted)) ] ]
			];
			Add(B);
			First(B);
		}
		Note(TEXT("Left and Right change a rope's colour. Port is red and starboard green on most boats, so you can tell the jib sheets apart."));
		break;
	}
	default:
	{
		// Wear: the five levels, or her class's own.
		auto WearRow = [&](int32 Level, const FString& Name, const FString& About)
		{
			TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::Card).Padding(FMargin(12.f, 8.f))
				.IsSelected_Lambda([this, Level]() { return SkinEdit.GetDraft().Wear.Level == Level && !SkinEdit.GetDraft().Wear.AgeYears.IsSet(); })
				.OnClicked_Lambda([this, Level]() { SkinEdit.SetWearLevel(Level); })
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Name, EType::Ui, Fg) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 2.f, 30.f, 0.f)[ SailUI::Text(About, EType::Small, Muted, true) ]
			];
			Add(B);
			First(B);
		};
		WearRow(-1, TEXT("Class's own"), TEXT("As the class's boats are in the game: a club boat."));
		for (int32 L = 0; L < FBoatSkin::NumWearLevels; ++L) WearRow(L, FBoatSkin::WearLevelName(L).ToString(), WearNotes[L]);
		Note(TEXT("Wear that grows with the hours you sail her comes in a later update; you will be able to override it here."));
		break;
	}
	}

	// Under the tabs, always there: the state, Use this look, and the small actions.
	TSharedRef<SSailButton> Use = ActionButton(TEXT("Use this look"), FSimpleDelegate::CreateSP(this, &SSailFrontEnd::CustomUse));
	if (!E.Focus.IsValid()) E.Focus = Use;
	TSharedRef<SWidget> Actions = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 8.f)
		[
			TextAttr(TAttribute<FText>::CreateLambda([this]()
			{
				if (!CustomMessage.IsEmpty() && CustomMessageRevision == SkinEdit.GetRevision()) return FText::FromString(CustomMessage);
				if (bCustomBefore) return FText::FromString(TEXT("Showing her saved look. T or the left stick's click shows your changes again."));
				return FText::FromString(SkinEdit.IsDirty() ? TEXT("Changes not saved yet.") : SkinEdit.IsUnsaved() ? TEXT("Not on your boat yet: Use this look puts it on.") : TEXT(""));
			}), EType::Small, TAttribute<FSlateColor>::CreateLambda([this]() { return FSlateColor(bCustomLeaveArmed ? Warn : Muted); }), true)
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 8.f)[ Use ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 6.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 6.f, 0.f)
			[
				SmallButton(TEXT("Save as new"), [this]()
				{
					const bool bSaved = SkinEdit.SaveAsNew();
					SetCustomMessage(bSaved ? FString::Printf(TEXT("Saved as \"%s\" and put on your boat."), *SkinEdit.GetDraft().Name) : FString(TEXT("The skin's file could not be written.")));
					if (ASailboatPawn* P = Pawn()) { if (bSaved) P->RefreshSkin(); }
					if (bSaved) CustomShownRevision = SkinEdit.GetRevision();
					SetCustomTab(CustomTab);
				}, TAttribute<bool>::CreateLambda([this]() { return SkinEdit.SavePlan() != FSkinEditor::ESavePlan::ClassLook; }))
			]
			+ SHorizontalBox::Slot().FillWidth(1.f)
			[
				SmallButton(TEXT("Surprise me"), [this]()
				{
					FRandomStream Random(int32(FPlatformTime::Cycles64() & 0x7fffffff));
					SkinEdit.Surprise(Random);
					CustomSyncHsv();
				})
			]
		]
		+ SVerticalBox::Slot().AutoHeight()
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 6.f, 0.f)
			[ SmallButton(TEXT("Undo"), [this]() { if (SkinEdit.Undo()) CustomSyncHsv(); }, TAttribute<bool>::CreateLambda([this]() { return SkinEdit.CanUndo(); })) ]
			+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 6.f, 0.f)
			[ SmallButton(TEXT("Redo"), [this]() { if (SkinEdit.Redo()) CustomSyncHsv(); }, TAttribute<bool>::CreateLambda([this]() { return SkinEdit.CanRedo(); })) ]
			+ SHorizontalBox::Slot().FillWidth(1.f)
			[
				SNew(SSailButton).Look(EButtonLook::Chip).Padding(FMargin(12.f, 7.f)).IsSelected_Lambda([this]() { return bCustomBefore; })
					.OnClicked_Lambda([this]() { bCustomBefore = !bCustomBefore; })
				[ SNew(SBox).HAlign(HAlign_Center)[ TextAttr(TAttribute<FText>::CreateLambda([]() { return FText::FromString(TEXT("Before")); }), EType::Label,
					TAttribute<FSlateColor>::CreateLambda([this]() { return FSlateColor(bCustomBefore ? Ink : Fg); })) ] ]
			]
		];

	FSlateFontInfo TitleFont = Font(EType::ScreenTitle);
	TitleFont.Size = 44;
	TSharedRef<SWidget> Side = SNew(SBox).WidthOverride(430.f).Visibility_Lambda(Panels)
	[
		PanelBox(SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 12.f)[ TabRow ]
			+ SVerticalBox::Slot().FillHeight(1.f)
			[
				SNew(SScrollBox).ScrollWhenFocusChanges(EScrollWhenFocusChanges::AnimatedScroll).NavigationScrollPadding(24.f).ScrollBarThickness(FVector2D(3.f, 3.f))
				+ SScrollBox::Slot().Padding(0.f, 0.f, 8.f, 0.f)[ Rows ]
			]
			+ SVerticalBox::Slot().AutoHeight()[ Actions ],
			FMargin(18.f))
	];
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()
		[
			SNew(SVerticalBox).Visibility_Lambda(Panels)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Boat.Name, EType::Eyebrow, Accent) ]
			+ SVerticalBox::Slot().AutoHeight()[ SNew(STextBlock).Font(TitleFont).ColorAndOpacity(Fg).Text(FText::FromString(TEXT("CUSTOMIZE"))) ]
		]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 14.f, 0.f, 92.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth()[ Side ]
			+ SHorizontalBox::Slot().FillWidth(1.f)[ SNew(SSpacer) ]
		];
	E.Footer = PromptBar({ FPrompt(TEXT("Enter"), TEXT("A"), TEXT("Choose")), FPrompt(TEXT("Q / E"), TEXT("LB / RB"), TEXT("Tab")),
		FPrompt(TEXT("Z"), TEXT("X"), TEXT("Undo")), FPrompt(TEXT("Y"), TEXT("Y"), TEXT("Redo")), FPrompt(TEXT("T"), TEXT("L3"), TEXT("Before")),
		FPrompt(TEXT("R"), TEXT("Menu"), TEXT("Surprise me")), FPrompt(TEXT("Drag"), TEXT("R"), TEXT("Turn")), FPrompt(TEXT("V"), TEXT("View"), TEXT("Hide panels")),
		FPrompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, FString());
	return E;
}
