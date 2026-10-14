#pragma once

#include "CoreMinimal.h"
#include "Fonts/SlateFontInfo.h"
#include "Styling/SlateBrush.h"
#include "Styling/SlateTypes.h"

/**
 * Graphics G4: the front end's and HUD's look (Inputs/g4/ui-spec.md section 3), in code: colour tokens, the three type
 * families (Saira Condensed, Saira Semi Condensed, Source Sans 3; SIL OFL, Content/UI/Fonts, staged as loose files),
 * brushes and the measures. Sizes are Slate units at the 1920x1080 reference; the viewport's DPI curve scales them.
 */
namespace SailUI
{
	// Colour (3.1).
	extern const FLinearColor Ink, Panel, PanelSolid, Raise, Line, Fg, Muted, Dim, Accent, AccentInk, Selected, Chart, Water,
		Land, Port, Starboard, Warn, WindTrue;
	FLinearColor Hex(uint32 RGB, float Alpha = 1.f);

	// Type (3.2).
	enum class EType : uint8 { Logo, ScreenTitle, CardTitle, CardTitleM, CardTitleS, MenuItem, Eyebrow, Label, Ui, Button, Value, InstrumentBig, Body, Small };
	FSlateFontInfo Font(EType Type);
	/** Upper-case styles are drawn upper case: the text helpers apply it. */
	bool IsUpper(EType Type);
	FText Txt(const FString& S, EType Type);

	// Brushes: rounded panels, borders, focus rings.
	const FSlateBrush* Rounded(const FLinearColor& Fill, float Radius, const FLinearColor& Outline = FLinearColor::Transparent, float OutlineWidth = 0.f);
	const FSlateBrush* White();

	// Measures (3.3).
	constexpr float SafeX = 64.f, SafeTop = 50.f, HudMargin = 30.f, RadiusButton = 5.f, RadiusCard = 7.f;

	/** Low quality: solid panels, no blur, no slides (8.2). */
	bool IsLow();
	/** The player last used a gamepad (glyphs follow the device). */
	bool UsingGamepad();
	void RegisterInputTracker();
}
