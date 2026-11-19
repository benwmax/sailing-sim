#include "HullName.h"
#include "BoatModel.h"
#include "SailingSim.h"
#include "UI/SailUIStyle.h"
#include "BenchRunner.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/Texture2D.h"
#include "UObject/Package.h"
#include "Misc/Parse.h"
#include "TextureResource.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Misc/App.h"
#include "Rendering/SlateRenderer.h"
#include "Slate/WidgetRenderer.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Text/STextBlock.h"

bool SailingHullName::Place(int32 BoatType, float Aspect, FHullNamePlace& Out)
{
	using Sailing::EBoatType;
	if (!(Aspect > 0.f) || BoatType < 0 || BoatType >= int32(EBoatType::Count)) return false;
	const EBoatType Type = EBoatType(BoatType);
	// The frigate's name is her own, carved on her stern with the rest of her carving (Tools/shipkit/frigate), not vinyl.
	if (Type == EBoatType::Commonwealth) return false;
	Out = FHullNamePlace();
	if (Type == EBoatType::J22)
	{
		// The hero J/22's quarters (measured on her): the band between the boot stripe (to 9.65 cm) and the sheer (56.8 cm
		// aft), from 16 cm forward of the transom (X -346). Letters about 7 cm tall (3 in, what a 22-footer wears); a long
		// name is made smaller rather than run forward of the cockpit.
		constexpr float AftCm = -330.f;
		constexpr float MidCm = 33.f;
		constexpr float HeightCm = 15.f;
		constexpr float MaxLengthCm = 125.f;
		Out.LengthCm = FMath::Min(Aspect * HeightCm, MaxLengthCm);
		Out.HeightCm = Out.LengthCm / Aspect;
		Out.XAftCm = AftCm;
		Out.ZLowCm = MidCm - 0.5f * Out.HeightCm;
		return true;
	}
	// Every other class from her physics hull (the models are that hull below the waterline and follow its sheer): the
	// J/22's place scaled by length overall, so the capitals are what owners letter (about 2 in on a dinghy, 4 to 5 on a
	// 40-footer), on her main hull's quarters: 16 cm (scaled) forward of the stern, the band's middle at 58% of the
	// freeboard there (the J/22's 33 of 56.8 cm) and at most 45% of it tall, so a low dinghy's name stays between her
	// waterline and her deck edge.
	const Sailing::FBoatConfig Config = Sailing::FBoatConfig::Make(Type);
	if (Config.Hulls.empty()) return false;
	const Sailing::FHullShape& Main = Config.Hulls[0];
	const double HullLengthM = FMath::Max(Config.LengthOverall - Config.Bowsprit, 1.0);   // (a fixed sprit is in LOA, metres)
	const float Scale = float(HullLengthM / 6.86);
	const float WantCm = 15.f * Scale;
	const float MaxLengthCm = 125.f * Scale;
	if (!Main.HasStations())
	{
		const float AftCm = float(Main.SternX) * 100.f + 16.f * Scale;
		// (the freeboard read a little forward of the aft edge, where the letters' middle sits on a usual name)
		const float FreeboardCm = float(Main.SheerHeight((AftCm + 0.35f * MaxLengthCm) / 100.f)) * 100.f;
		if (!(FreeboardCm > 8.f)) return false;
		const float HeightCm = FMath::Min(WantCm, 0.45f * FreeboardCm);
		Out.LengthCm = FMath::Min(Aspect * HeightCm, MaxLengthCm);
		Out.HeightCm = Out.LengthCm / Aspect;
		Out.XAftCm = AftCm;
		Out.ZLowCm = 0.58f * FreeboardCm - 0.5f * Out.HeightCm;
	}
	else
	{
		// A hull drawn from her sections (the Catalina 22, the maxi, Bluebonnet) is her real shape, so the band keeps to
		// her topside proper: above where the side turns under (the section's height at 85% of the deck's half-breadth)
		// and under the sheer. A long counter (Bluebonnet's runs 7.5 m past her waterline) has only a strip of topside
		// over its curved underside, where the first stills put the name half in the water; there the place moves
		// forward, up to a fifth of her length, to the first spot with room for three-fifths of the letters' height.
		const double DepthM = Sailing::FBoatModel(Config).HullDepth();
		struct FFit { float AftCm = 0.f, LowCm = 0.f, LengthCm = 0.f, HeightCm = 0.f; };
		auto FitAt = [&](float AftCm, FFit& Fit)
		{
			float HeightCm = WantCm, LoCm = 0.f, TopCm = 0.f;
			for (int32 Pass = 0; Pass < 4; ++Pass)
			{
				const float RunCm = FMath::Min(Aspect * HeightCm, MaxLengthCm);
				LoCm = -1.e9f;
				TopCm = 1.e9f;
				for (int32 K = 0; K <= 4; ++K)
				{
					const double X = (AftCm + RunCm * K / 4.0) / 100.0;
					LoCm = FMath::Max(LoCm, float(FMath::Max(0.0, Main.BottomZ(X, 0.85 * Main.DeckHalfBeam(X), DepthM))) * 100.f);
					TopCm = FMath::Min(TopCm, float(Main.SheerHeight(X)) * 92.f);
				}
				LoCm += 2.f * Scale;
				HeightCm = FMath::Min(HeightCm, 0.85f * (TopCm - LoCm));
			}
			Fit.LengthCm = FMath::Min(Aspect * HeightCm, MaxLengthCm);
			Fit.HeightCm = Fit.LengthCm / Aspect;
			if (!(Fit.HeightCm > 1.f) || TopCm - LoCm < Fit.HeightCm) return false;
			const float FreeboardCm = float(Main.SheerHeight((AftCm + 0.5f * Fit.LengthCm) / 100.f)) * 100.f;
			Fit.AftCm = AftCm;
			Fit.LowCm = FMath::Clamp(0.58f * FreeboardCm, LoCm + 0.5f * Fit.HeightCm, TopCm - 0.5f * Fit.HeightCm) - 0.5f * Fit.HeightCm;
			return true;
		};
		FFit Best;
		for (int32 Step = 0; Step <= 10; ++Step)
		{
			FFit Fit;
			if (!FitAt(float(Main.SternX) * 100.f + 16.f * Scale + float(Step) * 2.f * float(HullLengthM), Fit)) continue;
			if (Fit.HeightCm > Best.HeightCm) Best = Fit;
			if (Fit.HeightCm >= 0.6f * WantCm) { Best = Fit; break; }
		}
		if (!(Best.HeightCm > 1.f)) return false;
		Out.XAftCm = Best.AftCm;
		Out.ZLowCm = Best.LowCm;
		Out.LengthCm = Best.LengthCm;
		Out.HeightCm = Best.HeightCm;
	}
	// A trimaran wears it on her main hull only, not on the floats' outboard sides (a catamaran on both hulls' outboard
	// sides: her hulls are alike).
	if (Config.Hulls.size() >= 3) Out.MaxSideCm = float(Main.MaxHalfBeam) * 100.f + 30.f;
	return true;
}

UTexture2D* SailingHullName::Draw(UObject* Outer, const FString& Name, FVector2D& OutSizePx)
{
	if (Name.IsEmpty() || !FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		SAIL_LOG(Log, TEXT("Hull name: not drawn (name %d letters, can render %d, Slate %d)"), Name.Len(), FApp::CanEverRender() ? 1 : 0, FSlateApplication::IsInitialized() ? 1 : 0);
		return nullptr;
	}
	// The menus' title face at its largest (Besley Bold; the fallback face before the overhaul's fonts are in).
	const FSlateFontInfo Face = SailUI::Font(SailUI::EType::Logo);
	const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
	const float TextW = float(Measure->Measure(Name, Face).X);
	const float TextH = float(Measure->GetMaxCharacterHeight(Face));
	constexpr float PadPx = 12.f;
	const int32 W = FMath::Clamp(FMath::CeilToInt(TextW + 2.f * PadPx), 64, 2048);
	const int32 H = FMath::Clamp(FMath::CeilToInt(TextH + 2.f * PadPx), 32, 512);
	// Slate draws it into a render target, which is read straight back into a plain texture: a render target bound to
	// the hull's material sampled black in the game (its letters were there when read at once; the first stills showed
	// none), and a plain texture also keeps its pixels whatever recreates the render resources later. The read is a
	// stall of a few milliseconds, once per name (the pawn keeps the texture).
	UTextureRenderTarget2D* Target = NewObject<UTextureRenderTarget2D>(GetTransientPackage());
	Target->ClearColor = FLinearColor::Black;
	Target->InitCustomFormat(W, H, PF_B8G8R8A8, false);
	const TSharedRef<SWidget> Widget = SNew(SBox).WidthOverride(float(W)).HeightOverride(float(H)).HAlign(HAlign_Center).VAlign(VAlign_Center)
	[
		SNew(STextBlock).Text(FText::FromString(Name)).Font(Face).ColorAndOpacity(FLinearColor::White)
	];
	// (deleted on the render thread once its draw has gone through)
	FWidgetRenderer* Renderer = new FWidgetRenderer(true, true);
	Renderer->DrawWidget(Target, Widget, FVector2D(W, H), 0.f);
	BeginCleanup(Renderer);
	TArray<FColor> Pixels;
	FTextureRenderTargetResource* Resource = Target->GameThread_GetRenderTargetResource();
	const bool bRead = Resource && Resource->ReadPixels(Pixels) && Pixels.Num() == W * H;
	Target->ReleaseResource();
	// -SailingHullNameDraw=white (dev): the whole texture lit, so the material's rectangle shows as a solid block.
	FString How;
	FParse::Value(SailingArgs::Dev(), TEXT("SailingHullNameDraw="), How);
	const bool bWhite = How == TEXT("white");
	int32 Lit = 0;
	for (const FColor& C : Pixels) Lit += C.R >= 128 ? 1 : 0;
	SAIL_LOG(Log, TEXT("Hull name: \"%s\" %.0f x %.0f px in %d x %d, read %d px, %d lit%s"), *Name, TextW, TextH, W, H, Pixels.Num(), Lit, bWhite ? TEXT(" (all white asked)") : TEXT(""));
	if (!bRead || (Lit == 0 && !bWhite)) return nullptr;
	UTexture2D* Tex = UTexture2D::CreateTransient(W, H, PF_B8G8R8A8);
	if (!Tex || !Tex->GetPlatformData() || Tex->GetPlatformData()->Mips.Num() == 0) return nullptr;
	Tex->SRGB = true;   // (a Color sampler: the cover is 0 or 255 but at the letters' edges)
	Tex->Filter = TF_Bilinear;
	Tex->AddressX = TA_Clamp;
	Tex->AddressY = TA_Clamp;
	FTexture2DMipMap& Mip = Tex->GetPlatformData()->Mips[0];
	if (FColor* Out = static_cast<FColor*>(Mip.BulkData.Lock(LOCK_READ_WRITE)))
	{
		for (int32 I = 0; I < W * H; ++I)
		{
			const uint8 Cover = bWhite ? uint8(255) : Pixels[I].R;
			Out[I] = FColor(Cover, Cover, Cover, 255);
		}
	}
	Mip.BulkData.Unlock();
	Tex->UpdateResource();
	OutSizePx = FVector2D(W, H);
	return Tex;
}
