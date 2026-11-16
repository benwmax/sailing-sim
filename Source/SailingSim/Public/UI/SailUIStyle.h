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
 * glass with chart-paper text and sea aqua for focus and the main action; yellow is only Caution now. The paper
 * tokens (Paper .. AccentDeep) are for surfaces drawn as chart paper: ink text on Paper, AccentDeep for the accent on it.
 */
namespace SailUI
{
	// Colour (3.1).
	extern SAILINGSIM_API const FLinearColor Ink, Panel, PanelSolid, Raise, Line, Fg, Muted, Dim, Accent, AccentInk, Selected, Chart, Water,
		Land, Port, Starboard, Warn, WindTrue;
	// Paper surfaces (the focus label, and the menus' sheets as they are converted), brass for medals, yellow for caution.
	extern SAILINGSIM_API const FLinearColor Paper, PaperInk, PaperMuted, PaperLine, AccentDeep, Brass, Caution;
	extern SAILINGSIM_API const FLinearColor PaperRaise, PaperPort, PaperStarboard, PaperWarn;

	/**
	 * Paper sheets (UI overhaul phase 2). While an FScopedPaper is alive, the shared widgets and text helpers built
	 * inside it are drawn for paper: they are given the glass tokens as before and Surface() turns each into its paper
	 * twin (Fg to ink, Muted to the quieter ink, Accent to the deeper aqua, Ink to paper, lines and raised fills to
	 * their paper tints). A widget asks OnPaper() once, when it is constructed, and keeps the answer. Map a colour once
	 * only: ink and paper are each other's twins, so a second pass would turn it back.
	 */
	SAILINGSIM_API bool OnPaper();
	struct SAILINGSIM_API FScopedPaper
	{
		explicit FScopedPaper(bool bOn = true);
		~FScopedPaper();
	private:
		bool bWas = false;
	};
	SAILINGSIM_API FLinearColor Surface(bool bPaper, const FLinearColor& Glass);
	inline FLinearColor OnSurface(const FLinearColor& Glass) { return Surface(OnPaper(), Glass); }
	FLinearColor Hex(uint32 RGB, float Alpha = 1.f);

	// Type (3.2).
	enum class EType : uint8 { Logo, ScreenTitle, CardTitle, CardTitleM, CardTitleS, MenuItem, Eyebrow, Label, Ui, Button, Value, InstrumentBig, Body, Small };
	/** Settings > Accessibility > Text size: every style under 30 px (body, notes, labels, buttons, values). Titles and
	 *  the big instrument numerals are large already and keep their size, so the fixed title layouts hold. */
	SAILINGSIM_API float TextScale();
	/** True when the overhaul's faces (Besley, Atkinson Hyperlegible Next, B612) are all in Content/UI/Fonts and
	 *  -SailingClassicFonts is not given; otherwise the styles stay on Saira. */
	SAILINGSIM_API bool HasOverhaulFonts();
	SAILINGSIM_API FSlateFontInfo Font(EType Type);
	/** Upper-case styles are drawn upper case: the text helpers apply it. Only the short tracked labels (Eyebrow, Label)
	 *  since the UI overhaul: sentence case reads faster from a couch. */
	SAILINGSIM_API bool IsUpper(EType Type);
	SAILINGSIM_API FText Txt(const FString& S, EType Type);

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
	SAILINGSIM_API EUiMode UiMode();
	/** Sets it, keeps the HUD in step and saves the settings. */
	SAILINGSIM_API void SetUiMode(EUiMode Mode);
	SAILINGSIM_API const TCHAR* UiModeName(EUiMode Mode);

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
