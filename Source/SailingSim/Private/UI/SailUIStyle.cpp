#include "UI/SailUIStyle.h"
#include "SailingSim.h"
#include "SailingSettings.h"
#include "UI/SailHud.h"
#include "BenchRunner.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Brushes/SlateColorBrush.h"
#include "Fonts/CompositeFont.h"
#include "Fonts/FontMeasure.h"
#include "Rendering/SlateRenderer.h"
#include "Framework/Application/IInputProcessor.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "TextureResource.h"
#include "Engine/Texture2D.h"
#include "UObject/GCObject.h"

namespace SailUI
{
	FLinearColor Hex(uint32 RGB, float Alpha)
	{
		return FLinearColor(FColor((RGB >> 16) & 255, (RGB >> 8) & 255, RGB & 255)).CopyWithNewOpacity(Alpha);
	}

	// Glass: ink-blue panels over the water, chart-paper text, sea aqua for focus and the main action (Bean, Nov 15 2026: not the chart magenta of the first pass). (The yellow of
	// the first UI is Caution now, and nothing else.) Contrast on Panel: Fg 13:1, Muted 7.7:1, Dim 5.2:1, Accent 4.7:1.
	const FLinearColor Ink = Hex(0x15222C), Panel = Hex(0x15222C, 0.82f), PanelSolid = Hex(0x1B2B36), Raise = Hex(0x26394A),
		Line = Hex(0x3B5161), Fg = Hex(0xF0E8D2), Muted = Hex(0xAEB6B0), Dim = Hex(0x8C968F), Accent = Hex(0x4FD1C9),
		AccentInk = Hex(0x15222C), Selected = Hex(0xF0E8D2, 0.75f), Chart = Hex(0xD14F9B), Water = Hex(0x2F6F97),
		Land = Hex(0xCDBF98), Port = Hex(0xE2483D), Starboard = Hex(0x2DB36A), Warn = Hex(0xFF9A2E), WindTrue = Hex(0x9FD3FF);
	// Paper: chart paper, ink, the accent deep enough for paper, brass for medals.
	const FLinearColor Paper = Hex(0xF0E8D2), PaperInk = Hex(0x15222C), PaperMuted = Hex(0x4A5A64), PaperLine = Hex(0xCFC4A6),
		AccentDeep = Hex(0x086068), Brass = Hex(0xA98A44), Caution = Hex(0xF4C430);
	// Paper's raised fill (a chip, a secondary button), and port, starboard and warning deep enough to read on paper.
	const FLinearColor PaperRaise = Hex(0xE4DABD), PaperPort = Hex(0xB3261F), PaperStarboard = Hex(0x17703F), PaperWarn = Hex(0x8A5200);

	namespace
	{
		bool GOnPaper = false;   // the game thread builds widgets; nothing else reads it
		bool Same(const FLinearColor& A, const FLinearColor& B) { return A.R == B.R && A.G == B.G && A.B == B.B; }
	}

	bool OnPaper() { return GOnPaper; }
	FScopedPaper::FScopedPaper(bool bOn) : bWas(GOnPaper) { GOnPaper = bOn; }
	FScopedPaper::~FScopedPaper() { GOnPaper = bWas; }

	FLinearColor Surface(bool bPaper, const FLinearColor& Glass)
	{
		if (!bPaper) return Glass;
		// (Compared without alpha, so a token with its opacity changed still finds its twin and keeps that opacity.)
		const float A = Glass.A;
		if (Same(Glass, Fg)) return PaperInk.CopyWithNewOpacity(A);
		if (Same(Glass, Muted) || Same(Glass, Dim)) return PaperMuted.CopyWithNewOpacity(A);
		if (Same(Glass, Accent)) return AccentDeep.CopyWithNewOpacity(A);
		if (Same(Glass, Ink) || Same(Glass, PanelSolid)) return Paper;   // (Panel is Ink with an opacity: a sheet is opaque)
		if (Same(Glass, Raise)) return PaperRaise.CopyWithNewOpacity(A);
		if (Same(Glass, Line)) return PaperLine.CopyWithNewOpacity(A);
		if (Same(Glass, Port)) return PaperPort.CopyWithNewOpacity(A);
		if (Same(Glass, Starboard)) return PaperStarboard.CopyWithNewOpacity(A);
		if (Same(Glass, Warn)) return PaperWarn.CopyWithNewOpacity(A);
		return Glass;
	}

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

		// The overhaul's faces (docs/ui-overhaul/, Phase 9): Besley for titles (a slab serif, the chart table's lettering),
		// Atkinson Hyperlegible Next for text and labels, B612 (drawn for aircraft displays) for instrument figures. All
		// static instances: Slate draws a variable font's lightest one.
		const TSharedPtr<const FCompositeFont>& Besley()
		{
			static TSharedPtr<const FCompositeFont> F = Family(TEXT("Besley"), { { TEXT("SemiBold"), TEXT("Besley-SemiBold.ttf") }, { TEXT("Bold"), TEXT("Besley-Bold.ttf") } });
			return F;
		}
		const TSharedPtr<const FCompositeFont>& Atkinson()
		{
			// Atkinson has no arrows (the prompts' "← →", the showroom's turn buttons, the wind's arrow drew as boxes on
			// the first stills): those come from B612, which has them.
			static TSharedPtr<const FCompositeFont> F = []()
			{
				TSharedRef<FStandaloneCompositeFont> Comp = MakeShared<FStandaloneCompositeFont>();
				const FString Dir = FPaths::ProjectContentDir() / TEXT("UI/Fonts");
				Comp->DefaultTypeface.AppendFont(TEXT("Regular"), Dir / TEXT("AtkinsonHyperlegibleNext-Regular.ttf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
				Comp->DefaultTypeface.AppendFont(TEXT("Medium"), Dir / TEXT("AtkinsonHyperlegibleNext-Medium.ttf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
				Comp->DefaultTypeface.AppendFont(TEXT("SemiBold"), Dir / TEXT("AtkinsonHyperlegibleNext-SemiBold.ttf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
				FCompositeSubFont& Arrows = Comp->SubTypefaces.AddDefaulted_GetRef();
				Arrows.CharacterRanges.Add(FInt32Range(FInt32Range::BoundsType::Inclusive(0x2190), FInt32Range::BoundsType::Inclusive(0x21FF)));
				Arrows.Typeface.AppendFont(TEXT("Regular"), Dir / TEXT("B612-Regular.ttf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
				Arrows.Typeface.AppendFont(TEXT("Medium"), Dir / TEXT("B612-Regular.ttf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
				Arrows.Typeface.AppendFont(TEXT("SemiBold"), Dir / TEXT("B612-Bold.ttf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
				return TSharedPtr<const FCompositeFont>(Comp);
			}();
			return F;
		}
		const TSharedPtr<const FCompositeFont>& B612()
		{
			static TSharedPtr<const FCompositeFont> F = Family(TEXT("B612"), { { TEXT("Regular"), TEXT("B612-Regular.ttf") }, { TEXT("Bold"), TEXT("B612-Bold.ttf") } });
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

	bool HasOverhaulFonts()
	{
		// The new faces are used only when every file is there (a checkout or package without them keeps Saira), and
		// -SailingClassicFonts keeps Saira for compared stills.
		static int32 State = -1;
		if (State < 0)
		{
			const FString Dir = FPaths::ProjectContentDir() / TEXT("UI/Fonts");
			bool bAll = !FParse::Param(FCommandLine::Get(), TEXT("SailingClassicFonts"));
			for (const TCHAR* File : { TEXT("Besley-SemiBold.ttf"), TEXT("Besley-Bold.ttf"), TEXT("AtkinsonHyperlegibleNext-Regular.ttf"),
				TEXT("AtkinsonHyperlegibleNext-Medium.ttf"), TEXT("AtkinsonHyperlegibleNext-SemiBold.ttf"), TEXT("B612-Regular.ttf"), TEXT("B612-Bold.ttf") })
			{
				bAll = bAll && FPaths::FileExists(Dir / File);
			}
			State = bAll ? 1 : 0;
		}
		return State == 1;
	}

	FSlateFontInfo Font(EType T)
	{
		if (HasOverhaulFonts())
		{
			// The same pixel sizes as Saira's would overflow every layout: Saira is condensed, these are not. Titles are set
			// at 0.8 of Saira's size, text at 0.88, figures at 0.84, which keeps line lengths close to what the layouts
			// were drawn for; nothing goes under 15 px at 1080p. Capitals labels keep a little tracking.
			const float S = TextScale();
			switch (T)
			{
			case EType::Logo: return Make(Besley(), TEXT("Bold"), 96, 0);
			case EType::ScreenTitle: return Make(Besley(), TEXT("SemiBold"), 44, 0);
			case EType::CardTitle: return Make(Besley(), TEXT("SemiBold"), 31, 0);
			case EType::CardTitleM: return Make(Besley(), TEXT("SemiBold"), 25, 0);
			case EType::CardTitleS: return Make(Besley(), TEXT("SemiBold"), 20 * S, 0);
			case EType::MenuItem: return Make(Besley(), TEXT("SemiBold"), 25, 0);
			case EType::Eyebrow: return Make(Atkinson(), TEXT("SemiBold"), 14 * S, 60);
			case EType::Label: return Make(Atkinson(), TEXT("SemiBold"), 14 * S, 30);
			case EType::Ui: return Make(Atkinson(), TEXT("Medium"), 18 * S, 0);
			case EType::Button: return Make(Atkinson(), TEXT("SemiBold"), 18 * S, 0);
			case EType::Value: return Make(B612(), TEXT("Bold"), 18 * S, 0);
			case EType::InstrumentBig: return Make(B612(), TEXT("Bold"), 44, 0);
			case EType::Body: return Make(Atkinson(), TEXT("Regular"), 18 * S, 0);
			case EType::Small: return Make(Atkinson(), TEXT("Regular"), 15 * S, 0);
			}
		}
		// UI overhaul: nothing under 15 px at 1080p (labels were 12, notes 14, body 17), sentence case without the wide
		// tracking, and the player's text size on every style under 30 px.
		const float K = TextScale();
		switch (T)
		{
		case EType::Logo: return Make(Saira(), TEXT("Bold"), 120, 0);
		case EType::ScreenTitle: return Make(Saira(), TEXT("SemiBold"), 56, 0);
		case EType::CardTitle: return Make(Saira(), TEXT("SemiBold"), 38, 0);
		case EType::CardTitleM: return Make(Saira(), TEXT("SemiBold"), 30, 0);
		case EType::CardTitleS: return Make(Saira(), TEXT("SemiBold"), 24 * K, 0);
		case EType::MenuItem: return Make(Saira(), TEXT("SemiBold"), 30, 10);
		case EType::Eyebrow: return Make(SairaSemi(), TEXT("SemiBold"), 16 * K, 120);
		case EType::Label: return Make(SairaSemi(), TEXT("SemiBold"), 15 * K, 80);
		case EType::Ui: return Make(SairaSemi(), TEXT("Medium"), 20 * K, 0);
		case EType::Button: return Make(SairaSemi(), TEXT("SemiBold"), 21 * K, 10);
		case EType::Value: return Make(SairaSemi(), TEXT("SemiBold"), 21 * K, 0);
		case EType::InstrumentBig: return Make(SairaSemi(), TEXT("SemiBold"), 52, 0);
		// (Source Sans 3 is a variable font and Slate draws its lightest instance: hairlines at this size. Until the overhaul's
		// text face is in, body and notes are Saira Semi Condensed Regular.)
		case EType::Body: return Make(SairaSemi(), TEXT("Regular"), 20 * K, 0);
		case EType::Small: return Make(SairaSemi(), TEXT("Regular"), 17 * K, 0);
		}
		return Make(Sans(), TEXT("Regular"), 20, 0);
	}

	void PreloadFonts()
	{
		// Measuring a string walks the same path as the first draw: the composite font's face for each codepoint is loaded
		// (the file read and the FreeType face) and kept by the font cache. The sample has the styles' letters, figures and
		// the HUD's symbols, and the arrows that Atkinson takes from B612 (its sub-typeface loads only for those codepoints).
		static bool bDone = false;
		if (bDone || !FSlateApplication::IsInitialized()) return;
		const TSharedPtr<FSlateRenderer> Renderer = FSlateApplication::Get().GetRenderer();
		if (!Renderer.IsValid()) return;
		const TSharedRef<FSlateFontMeasure> Measure = Renderer->GetFontMeasureService();
		const double Start = FPlatformTime::Seconds();
		static const FString Sample = FString(TEXT("Aa Gg Qq 0123456789 .,:;!?%+-/()")) + TCHAR(0x00B0) + TCHAR(0x00B7) + TCHAR(0x2013)
			+ TCHAR(0x2190) + TCHAR(0x2192);
		for (uint8 T = 0; T <= uint8(EType::Small); ++T)
		{
			Measure->Measure(Sample, Font(EType(T)));
			Measure->Measure(Sample.ToUpper(), Font(EType(T)));
		}
		bDone = true;
		UE_LOG(LogSailing, Log, TEXT("UI fonts preloaded in %.1f ms"), (FPlatformTime::Seconds() - Start) * 1000.0);
	}

	bool IsUpper(EType T)
	{
		return T == EType::Eyebrow || T == EType::Label;
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

	namespace
	{
		uint32 GrainHash(uint32 X, uint32 Y, uint32 Seed)
		{
			uint32 H = X * 374761393u + Y * 668265263u + Seed * 2246822519u;
			H = (H ^ (H >> 13)) * 1274126177u;
			return H ^ (H >> 16);
		}
		float GrainUnit(uint32 X, uint32 Y, uint32 Seed)
		{
			return float(GrainHash(X, Y, Seed) & 0xFFFFu) / 65535.f;
		}
		// Value noise on a lattice of Cells x Cells that wraps, so the tile has no seam.
		float GrainLattice(float U, float V, int32 Cells, uint32 Seed)
		{
			const float FX = U * Cells, FY = V * Cells;
			const int32 X0 = FMath::FloorToInt(FX), Y0 = FMath::FloorToInt(FY);
			const float TX = FMath::SmoothStep(0.f, 1.f, FX - X0), TY = FMath::SmoothStep(0.f, 1.f, FY - Y0);
			auto At = [Cells, Seed](int32 X, int32 Y) { return GrainUnit(uint32(((X % Cells) + Cells) % Cells), uint32(((Y % Cells) + Cells) % Cells), Seed); };
			return FMath::Lerp(FMath::Lerp(At(X0, Y0), At(X0 + 1, Y0), TX), FMath::Lerp(At(X0, Y0 + 1), At(X0 + 1, Y0 + 1), TX), TY);
		}
	}

	float PaperGrainValue(int32 X, int32 Y, int32 Size)
	{
		const int32 N = FMath::Max(Size, 8);
		const int32 PX = ((X % N) + N) % N, PY = ((Y % N) + N) % N;
		const float U = float(PX) / N, V = float(PY) / N;
		// Mottle (the sheet's uneven tone), a finer tooth, and per-texel fibre specks, stretched a little along X.
		const float Mottle = GrainLattice(U, V, 6, 42u) - 0.5f;	// a seed whose 36 lattice values average 0.5
		const float Tooth = GrainLattice(U, V, 96, 23u) - 0.5f;
		const float Speck = GrainUnit(uint32(PX / 2), uint32(PY), 37u) - 0.5f;
		// Mostly tooth and specks: with the mottle at 1.1 the first stills read as blotches 60 to 80 px across.
		return FMath::Clamp(Mottle * 0.45f + Tooth * 1.0f + Speck * 0.7f, -1.f, 1.f);
	}

	const FSlateBrush* PaperGrain()
	{
		static const bool bOff = FParse::Param(FCommandLine::Get(), TEXT("SailingNoPaperGrain"));
		if (bOff || !FSlateApplication::IsInitialized()) return nullptr;
		static FKeptTextures Kept;
		static FSlateBrush Brush;
		const FString Key(TEXT("PaperGrain"));
		if (TObjectPtr<UTexture2D>* Found = Kept.Textures.Find(Key); Found && *Found) return &Brush;
		const int32 N = 256;
		UTexture2D* Tex = UTexture2D::CreateTransient(N, N, PF_B8G8R8A8, TEXT("SailPaperGrain"));
		if (!Tex || !Tex->GetPlatformData() || Tex->GetPlatformData()->Mips.Num() == 0) return nullptr;
		Tex->SRGB = true;
		Tex->Filter = TF_Bilinear;
		Tex->AddressX = TA_Wrap;
		Tex->AddressY = TA_Wrap;
		FTexture2DMipMap& Mip = Tex->GetPlatformData()->Mips[0];
		if (FColor* Px = static_cast<FColor*>(Mip.BulkData.Lock(LOCK_READ_WRITE)))
		{
			// Light fibres are white, dark specks are ink; the alpha carries how much (at most about 7% of the sheet).
			const FColor SpeckInk = PaperInk.ToFColor(true);
			for (int32 Y = 0; Y < N; ++Y)
			{
				for (int32 X = 0; X < N; ++X)
				{
					const float G = PaperGrainValue(X, Y, N);
					FColor C = G >= 0.f ? FColor::White : SpeckInk;
					C.A = uint8(FMath::Clamp(FMath::RoundToInt(FMath::Abs(G) * (G >= 0.f ? 30.f : 22.f)), 0, 255));
					Px[Y * N + X] = C;
				}
			}
		}
		Mip.BulkData.Unlock();
		Tex->UpdateResource();
		Kept.Textures.Add(Key, Tex);
		Brush = FSlateBrush();
		Brush.SetResourceObject(Tex);
		Brush.ImageSize = FVector2D(N, N);
		Brush.DrawAs = ESlateBrushDrawType::Image;
		Brush.Tiling = ESlateBrushTileType::Both;
		return &Brush;
	}

	EUiMode UiMode()
	{
		// -SailingUiMode=helpful|natural|off for stills (photo mode's panel, docs/camera-views/); the setting otherwise.
		static SailingArgs::FOnce ArgRead;
		static int32 Arg = -1;
		if (ArgRead.Take())
		{
			FString V;
			Arg = !FParse::Value(SailingArgs::Dev(), TEXT("SailingUiMode="), V) ? -1
				: V.Equals(TEXT("natural"), ESearchCase::IgnoreCase) ? 1 : V.Equals(TEXT("off"), ESearchCase::IgnoreCase) ? 2
				: V.Equals(TEXT("helpful"), ESearchCase::IgnoreCase) ? 0 : -1;
		}
		return EUiMode(FMath::Clamp(Arg >= 0 ? Arg : USailingSettings::Get()->UiMode, 0, 2));
	}

	void SetUiMode(EUiMode Mode)
	{
		USailingSettings* S = USailingSettings::Get();
		S->UiMode = int32(Mode);
		S->bShowHud = true;
		SSailHud::Mode = int32(Mode);
		S->Save();
	}

	const TCHAR* UiModeName(EUiMode Mode)
	{
		return Mode == EUiMode::Helpful ? TEXT("Helpful") : Mode == EUiMode::Natural ? TEXT("Natural") : TEXT("Off");
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

	bool UsingGamepad()
	{
		// -SailingPad shows the controller's prompts without one plugged in (stills).
		static const bool bForce = FParse::Param(FCommandLine::Get(), TEXT("SailingPad"));
		return bForce || GGamepad;
	}
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
