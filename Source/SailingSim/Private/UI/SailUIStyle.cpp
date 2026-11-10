#include "UI/SailUIStyle.h"
#include "SailingSim.h"
#include "SailingSettings.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Brushes/SlateColorBrush.h"
#include "Fonts/CompositeFont.h"
#include "Framework/Application/IInputProcessor.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformTime.h"
#include "Misc/Paths.h"
#include "Engine/Texture2D.h"
#include "UObject/GCObject.h"

namespace SailUI
{
	FLinearColor Hex(uint32 RGB, float Alpha)
	{
		return FLinearColor(FColor((RGB >> 16) & 255, (RGB >> 8) & 255, RGB & 255)).CopyWithNewOpacity(Alpha);
	}

	const FLinearColor Ink = Hex(0x0A141C), Panel = Hex(0x0D1D28, 0.8f), PanelSolid = Hex(0x102130), Raise = Hex(0x17303F),
		Line = Hex(0x2B4554), Fg = Hex(0xEAF0F2), Muted = Hex(0x93A8B4), Dim = Hex(0x71889A), Accent = Hex(0xF4C430),
		AccentInk = Hex(0x1D1600), Selected = Hex(0xEAF0F2, 0.75f), Chart = Hex(0xD14F9B), Water = Hex(0x2F6F97),
		Land = Hex(0xCDBF98), Port = Hex(0xE2483D), Starboard = Hex(0x2DB36A), Warn = Hex(0xFF9A2E), WindTrue = Hex(0x9FD3FF);

	namespace
	{
		TSharedPtr<const FCompositeFont> Family(const TCHAR* Name, std::initializer_list<TPair<const TCHAR*, const TCHAR*>> Faces)
		{
			TSharedRef<FStandaloneCompositeFont> F = MakeShared<FStandaloneCompositeFont>();
			const FString Dir = FPaths::ProjectContentDir() / TEXT("UI/Fonts");
			for (const TPair<const TCHAR*, const TCHAR*>& Face : Faces)
			{
				F->DefaultTypeface.AppendFont(Face.Key, Dir / Face.Value, EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
			}
			return F;
		}

		const TSharedPtr<const FCompositeFont>& Saira()
		{
			static TSharedPtr<const FCompositeFont> F = Family(TEXT("Saira Condensed"), { { TEXT("Bold"), TEXT("SairaCondensed-Bold.ttf") }, { TEXT("SemiBold"), TEXT("SairaCondensed-SemiBold.ttf") } });
			return F;
		}
		const TSharedPtr<const FCompositeFont>& SairaSemi()
		{
			static TSharedPtr<const FCompositeFont> F = Family(TEXT("Saira Semi Condensed"), { { TEXT("Regular"), TEXT("SairaSemiCondensed-Regular.ttf") },
				{ TEXT("Medium"), TEXT("SairaSemiCondensed-Medium.ttf") }, { TEXT("SemiBold"), TEXT("SairaSemiCondensed-SemiBold.ttf") } });
			return F;
		}
		const TSharedPtr<const FCompositeFont>& Sans()
		{
			static TSharedPtr<const FCompositeFont> F = Family(TEXT("Source Sans 3"), { { TEXT("Regular"), TEXT("SourceSans3.ttf") } });
			return F;
		}

		// Slate sizes are in points at 96 dpi: the spec's sizes are pixels at 1080p, so 0.75 of them.
		FSlateFontInfo Make(const TSharedPtr<const FCompositeFont>& F, const TCHAR* Face, float Px, int32 Tracking)
		{
			FSlateFontInfo Info(F, FMath::RoundToFloat(Px * 0.75f), Face);
			Info.LetterSpacing = Tracking;
			return Info;
		}
	}

	float TextScale()
	{
		return FMath::Clamp(USailingSettings::Get()->TextScale, 100, 150) / 100.f;
	}

	FSlateFontInfo Font(EType T)
	{
		switch (T)
		{
		case EType::Logo: return Make(Saira(), TEXT("Bold"), 120, 0);
		case EType::ScreenTitle: return Make(Saira(), TEXT("SemiBold"), 60, 20);
		case EType::CardTitle: return Make(Saira(), TEXT("SemiBold"), 38, 0);
		case EType::CardTitleM: return Make(Saira(), TEXT("SemiBold"), 30, 0);
		case EType::CardTitleS: return Make(Saira(), TEXT("SemiBold"), 22, 0);
		case EType::MenuItem: return Make(Saira(), TEXT("SemiBold"), 30, 40);
		case EType::Eyebrow: return Make(SairaSemi(), TEXT("SemiBold"), 14, 180);
		case EType::Label: return Make(SairaSemi(), TEXT("SemiBold"), 12, 140);
		case EType::Ui: return Make(SairaSemi(), TEXT("Medium"), 17 * TextScale(), 0);
		case EType::Button: return Make(SairaSemi(), TEXT("SemiBold"), 19, 60);
		case EType::Value: return Make(SairaSemi(), TEXT("SemiBold"), 19, 0);
		case EType::InstrumentBig: return Make(SairaSemi(), TEXT("SemiBold"), 48, 0);
		case EType::Body: return Make(Sans(), TEXT("Regular"), 17 * TextScale(), 0);
		case EType::Small: return Make(Sans(), TEXT("Regular"), 14 * TextScale(), 0);
		}
		return Make(Sans(), TEXT("Regular"), 17, 0);
	}

	bool IsUpper(EType T)
	{
		return T == EType::Logo || T == EType::ScreenTitle || T == EType::CardTitle || T == EType::CardTitleM || T == EType::CardTitleS
			|| T == EType::MenuItem || T == EType::Eyebrow || T == EType::Label || T == EType::Button;
	}

	FText Txt(const FString& S, EType T)
	{
		return FText::FromString(IsUpper(T) ? S.ToUpper() : S);
	}

	const FSlateBrush* Rounded(const FLinearColor& Fill, float Radius, const FLinearColor& Outline, float OutlineWidth)
	{
		static TMap<FString, TUniquePtr<FSlateRoundedBoxBrush>> Cache;
		const FString Key = FString::Printf(TEXT("%s|%.1f|%s|%.1f"), *Fill.ToString(), Radius, *Outline.ToString(), OutlineWidth);
		if (TUniquePtr<FSlateRoundedBoxBrush>* Found = Cache.Find(Key)) return Found->Get();
		TUniquePtr<FSlateRoundedBoxBrush> B = MakeUnique<FSlateRoundedBoxBrush>(Fill, Radius, Outline, OutlineWidth);
		const FSlateBrush* Out = B.Get();
		Cache.Add(Key, MoveTemp(B));
		return Out;
	}

	const FSlateBrush* White()
	{
		static FSlateColorBrush B(FLinearColor::White);
		return &B;
	}

	namespace
	{
		class FKeptTextures : public FGCObject
		{
		public:
			TMap<FString, TObjectPtr<UTexture2D>> Textures;
			virtual void AddReferencedObjects(FReferenceCollector& Collector) override { Collector.AddReferencedObjects(Textures); }
			virtual FString GetReferencerName() const override { return TEXT("SailUI textures"); }
		};
	}

	UTexture2D* KeptTexture(const FString& Path)
	{
		static FKeptTextures Kept;
		if (TObjectPtr<UTexture2D>* Found = Kept.Textures.Find(Path); Found && *Found) return *Found;
		UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
		if (Tex) Kept.Textures.Add(Path, Tex);
		return Tex;
	}

	bool IsLow()
	{
		return USailingSettings::Get()->Quality == ESailingQuality::Low;
	}

	namespace
	{
		bool GGamepad = false;
		bool GMouseActive = false;   // the mouse was used more recently than the keys or the pad
		double GMouseMovedAt = -1.0;   // when the mouse last really moved (FPlatformTime seconds)
		// Hover may move focus only this soon after a real move: a screen (or the window) that appears under a still
		// cursor keeps its default focus, even when the mouse was the last thing used (the suspected cause of the Nov 10
		// nightly's first-launch screen opening with the focus on Picture quality instead of Start your first job).
		constexpr double MouseHoverWindowSeconds = 0.5;

		class FDeviceTracker : public IInputProcessor
		{
		public:
			virtual void Tick(const float, FSlateApplication& App, TSharedRef<ICursor>) override
			{
				// While the app is in the background the cursor's position means nothing to us: the first move after it
				// comes back only sets where the cursor is (macOS reports a jump from wherever it last saw it).
				if (!App.IsActive()) bHaveCursor = false;
			}
			virtual bool HandleKeyDownEvent(FSlateApplication&, const FKeyEvent& E) override { GGamepad = E.GetKey().IsGamepadKey(); GMouseActive = false; return false; }
			virtual bool HandleMouseMoveEvent(FSlateApplication&, const FPointerEvent& E) override
			{
				// A real move is one measured from a position we saw ourselves: the window's first mouse event after it
				// opens or comes to the front carries a delta from an old or unknown position, and is only a baseline.
				const FVector2D At(E.GetScreenSpacePosition());
				if (bHaveCursor && E.GetCursorDelta().SizeSquared() > 4.f && FVector2D::DistSquared(At, LastCursor) > 4.0)
				{
					GMouseActive = true;
					GMouseMovedAt = FPlatformTime::Seconds();
				}
				LastCursor = At;
				bHaveCursor = true;
				return false;
			}
			virtual bool HandleAnalogInputEvent(FSlateApplication&, const FAnalogInputEvent& E) override
			{
				if (FMath::Abs(E.GetAnalogValue()) > 0.5f) { GGamepad = true; GMouseActive = false; }
				return false;
			}
			virtual bool HandleMouseButtonDownEvent(FSlateApplication&, const FPointerEvent&) override { GGamepad = false; return false; }
			virtual const TCHAR* GetDebugName() const override { return TEXT("SailUIDeviceTracker"); }
		private:
			FVector2D LastCursor = FVector2D::ZeroVector;
			bool bHaveCursor = false;
		};
	}

	bool UsingGamepad() { return GGamepad; }
	bool MouseIsActive() { return GMouseActive && FPlatformTime::Seconds() - GMouseMovedAt < MouseHoverWindowSeconds; }

	void FocusByHover(const TSharedRef<SWidget>& Widget)
	{
		FSlateApplication& App = FSlateApplication::Get();
		static int32 Logged = 0;   // the first few only: enough for a launch's first screens, quiet after
		if (Logged < 20)
		{
			++Logged;
			const FVector2D Cursor(App.GetCursorPos());
			SAIL_LOG(Display, TEXT("Menus: hover focus to %s '%s' (cursor %.0f,%.0f; %.2f s after a mouse move)"), *Widget->GetTypeAsString(),
				*Widget->GetTag().ToString(), Cursor.X, Cursor.Y, FPlatformTime::Seconds() - GMouseMovedAt);
		}
		App.SetUserFocus(0, Widget, EFocusCause::Mouse);
	}

	void RegisterInputTracker()
	{
		static bool bDone = false;
		if (bDone || !FSlateApplication::IsInitialized()) return;
		bDone = true;
		FSlateApplication::Get().RegisterInputPreProcessor(MakeShared<FDeviceTracker>());
	}
}
