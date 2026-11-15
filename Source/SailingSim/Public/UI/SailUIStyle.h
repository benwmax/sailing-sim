#pragma once

#include "CoreMinimal.h"
#include "Fonts/SlateFontInfo.h"
#include "Styling/SlateBrush.h"
#include "Styling/SlateTypes.h"

class SWidget;

/**
 * Graphics G4: the front end's and HUD's look (Inputs/g4/ui-spec.md section 3), in code: colour tokens, the three type
 * families (Saira Condensed, Saira Semi Condensed, Source Sans 3; SIL OFL, Content/UI/Fonts, staged as loose files),
 * brushes and the measures. Sizes are Slate units at the 1920x1080 reference; the viewport's DPI curve scales them.
 *
 * UI overhaul (docs/ui-overhaul/): "paper for planning, glass for sailing". The glass tokens (Ink .. WindTrue) are ink-blue
 * glass with chart-paper text and chart magenta for focus and the main action; yellow is only Caution now. The paper
 * tokens (Paper .. AccentDeep) are for surfaces drawn as chart paper: ink text on Paper, AccentDeep for magenta on it.
 */
namespace SailUI
{
	// Colour (3.1).
	extern const FLinearColor Ink, Panel, PanelSolid, Raise, Line, Fg, Muted, Dim, Accent, AccentInk, Selected, Chart, Water,
		Land, Port, Starboard, Warn, WindTrue;
	// Paper surfaces (the focus label, and the menus' sheets as they are converted), brass for medals, yellow for caution.
	extern const FLinearColor Paper, PaperInk, PaperMuted, PaperLine, AccentDeep, Brass, Caution;
	FLinearColor Hex(uint32 RGB, float Alpha = 1.f);

	// Type (3.2).
	enum class EType : uint8 { Logo, ScreenTitle, CardTitle, CardTitleM, CardTitleS, MenuItem, Eyebrow, Label, Ui, Button, Value, InstrumentBig, Body, Small };
	/** Settings > Accessibility > Text size: every style under 30 px (body, notes, labels, buttons, values). Titles and
	 *  the big instrument numerals are large already and keep their size, so the fixed title layouts hold. */
	float TextScale();
	FSlateFontInfo Font(EType Type);
	/** Upper-case styles are drawn upper case: the text helpers apply it. Only the short tracked labels (Eyebrow, Label)
	 *  since the UI overhaul: sentence case reads faster from a couch. */
	bool IsUpper(EType Type);
	FText Txt(const FString& S, EType Type);

	// Brushes: rounded panels, borders, focus rings.
	const FSlateBrush* Rounded(const FLinearColor& Fill, float Radius, const FLinearColor& Outline = FLinearColor::Transparent, float OutlineWidth = 0.f);
	const FSlateBrush* White();

	/** A UI texture by path, kept referenced for the garbage collector (a Slate brush alone does not hold its texture: a
	 *  level reload collected the minimap's map under the HUD). Null if missing. */
	class UTexture2D* KeptTexture(const FString& Path);

	// Measures (3.3). The margins keep text off a television's edges (the title-safe area is the inner 90%: 96 x 54 px
	// at 1080p; these are most of the way there until the margin slider lands with the display rows).
	constexpr float SafeX = 80.f;
	constexpr float SafeTop = 54.f;
	constexpr float HudMargin = 40.f;
	constexpr float RadiusButton = 5.f;
	constexpr float RadiusCard = 7.f;

	/** The player's interface mode (Bean, Nov 15 2026): Helpful has the full text and explainers, Natural only a glimpse
	 *  of what is hard to see with few words, Off nothing but warnings. Saved as USailingSettings::UiMode; SSailHud::Mode
	 *  is the same number while sailing (0, 1, 2) and the H key cycles it. */
	enum class EUiMode : uint8 { Helpful, Natural, Off };
	EUiMode UiMode();
	/** Sets it, keeps the HUD in step and saves the settings. */
	void SetUiMode(EUiMode Mode);
	const TCHAR* UiModeName(EUiMode Mode);

	/** Low quality: solid panels, no blur, no slides (8.2). */
	bool IsLow();
	/** The player last used a gamepad (glyphs follow the device). */
	bool UsingGamepad();
	/** The mouse moved more recently than a key or the pad was used, and within the last half second: only then does
	 *  hovering move focus (a screen, or the window, that opens under a still cursor keeps its default focus). */
	bool MouseIsActive();
	/** Hover's focus move (the widgets' OnMouseEnter, when MouseIsActive): sets it and logs the first few, with the cursor
	 *  and the time since the last real move, so a nightly log shows when hover took the focus. */
	void FocusByHover(const TSharedRef<SWidget>& Widget);
	void RegisterInputTracker();
}
