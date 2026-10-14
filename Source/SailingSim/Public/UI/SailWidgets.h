#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "UI/SailUIStyle.h"

class SBorder;

/**
 * Graphics G4: the front end's shared widgets (ui-spec.md 3.4), in Slate. Every focusable is keyboard, gamepad and mouse
 * driven: hovering moves focus (one highlight at a time), Enter / A / click activates, Left and Right adjust a value
 * widget. Focus is the yellow ring (or the yellow bar on menu items); selection is the white edge and a tick.
 */
namespace SailUI
{
	enum class EButtonLook : uint8 { Card, MenuItem, Primary, Secondary, Chip, Pin };
}

/** A focusable surface: a card, a menu item, a button. */
class SAILINGSIM_API SSailButton : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailButton) : _Look(SailUI::EButtonLook::Card), _IsSelected(false), _IsEnabled(true), _Padding(FMargin(16.f)) {}
		SLATE_DEFAULT_SLOT(FArguments, Content)
		SLATE_ARGUMENT(SailUI::EButtonLook, Look)
		SLATE_ATTRIBUTE(bool, IsSelected)
		SLATE_ATTRIBUTE(bool, IsEnabled)
		SLATE_ARGUMENT(FMargin, Padding)
		SLATE_EVENT(FSimpleDelegate, OnClicked)
		SLATE_EVENT(FSimpleDelegate, OnFocused)
		/** Left (-1) and Right (+1) when the button takes them (chips, rotators); unbound: they navigate. */
		SLATE_EVENT(TDelegate<void(int32)>, OnAdjust)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual bool SupportsKeyboardFocus() const override { return IsEnabledNow(); }
	virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual void OnMouseEnter(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnFocusReceived(const FGeometry& Geometry, const FFocusEvent& Event) override;
	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& Culling, FSlateWindowElementList& Out,
		int32 Layer, const FWidgetStyle& Style, bool bParentEnabled) const override;
	bool IsEnabledNow() const { return Enabled.Get(true); }
	bool IsFocusedNow() const { return HasKeyboardFocus(); }

private:
	SailUI::EButtonLook Look = SailUI::EButtonLook::Card;
	TAttribute<bool> SelectedAttr, Enabled;
	FSimpleDelegate OnClicked, OnFocused;
	TDelegate<void(int32)> OnAdjust;
	bool bPressed = false;
};

/** A labelled slider row: name, track, value; Left/Right step (key repeat holds), the mouse drags the track. */
class SAILINGSIM_API SSailSlider : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailSlider) : _Min(0.f), _Max(1.f), _Step(1.f) {}
		SLATE_ARGUMENT(FString, Label)
		SLATE_ARGUMENT(float, Min)
		SLATE_ARGUMENT(float, Max)
		SLATE_ARGUMENT(float, Step)
		SLATE_ATTRIBUTE(float, Value)
		SLATE_ATTRIBUTE(FString, ValueText)
		SLATE_ATTRIBUTE(bool, IsEnabled)
		SLATE_EVENT(TDelegate<void(float)>, OnChanged)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual bool SupportsKeyboardFocus() const override { return Enabled.Get(true); }
	virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseMove(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual void OnMouseEnter(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& Culling, FSlateWindowElementList& Out,
		int32 Layer, const FWidgetStyle& Style, bool bParentEnabled) const override;

private:
	void SetFromMouse(const FGeometry& Geometry, const FPointerEvent& Event);
	void Set(float V);
	float Min = 0.f, Max = 1.f, Step = 1.f;
	TAttribute<float> Value;
	TAttribute<bool> Enabled;
	TDelegate<void(float)> OnChanged;
	TSharedPtr<SWidget> Track;
	bool bDragging = false;
};

/** A row of chips (one chosen): Left/Right cycles, click picks. */
class SAILINGSIM_API SSailChoice : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailChoice) {}
		SLATE_ARGUMENT(FString, Label)
		SLATE_ARGUMENT(TArray<FString>, Options)
		SLATE_ATTRIBUTE(int32, Index)
		SLATE_ATTRIBUTE(bool, IsEnabled)
		SLATE_ARGUMENT(FString, Note)
		SLATE_EVENT(TDelegate<void(int32)>, OnChanged)
	SLATE_END_ARGS()
	void Construct(const FArguments& InArgs);
	virtual bool SupportsKeyboardFocus() const override { return Enabled.Get(true); }
	virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	virtual void OnMouseEnter(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& Culling, FSlateWindowElementList& Out,
		int32 Layer, const FWidgetStyle& Style, bool bParentEnabled) const override;
private:
	TArray<FString> Options;
	TAttribute<int32> Index;
	TAttribute<bool> Enabled;
	TDelegate<void(int32)> OnChanged;
};

namespace SailUI
{
	TSharedRef<SWidget> Text(const FString& S, EType Type, const FLinearColor& Color = Fg, bool bWrap = false);
	TSharedRef<SWidget> TextAttr(TAttribute<FText> S, EType Type, TAttribute<FSlateColor> Color, bool bWrap = false);
	/** Eyebrow, title, and the step bar (step 1..5, 0 = none). */
	TSharedRef<SWidget> Header(const FString& Eyebrow, const FString& Title, int32 Step);
	/** A glass panel (a solid one on Low). */
	TSharedRef<SWidget> PanelBox(TSharedRef<SWidget> Content, FMargin Padding = FMargin(20.f), float Radius = RadiusCard);
	/** A keycap glyph for an action: "Enter" / "A", "Esc" / "B" and so on, following the last device. */
	TSharedRef<SWidget> KeyCap(const FString& Keyboard, const FString& Pad);
	/** The footer: actions the screen handles, plus a hint on the right. */
	TSharedRef<SWidget> PromptBar(TArray<TTuple<FString, FString, FString>> Prompts, const FString& Hint);
	TSharedRef<SWidget> Pill(const FString& S, bool bAccent = false);
	/** The primary (yellow) or secondary call to action. */
	TSharedRef<SSailButton> ActionButton(const FString& Label, FSimpleDelegate OnClicked, bool bPrimary = true);
	bool IsConfirmKey(const FKey& Key);
	bool IsBackKey(const FKey& Key);
}
