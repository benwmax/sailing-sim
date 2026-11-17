#include "HullName.h"
#include "BoatModel.h"
#include "SailingSim.h"
#include "UI/SailUIStyle.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Misc/App.h"
#include "Rendering/SlateRenderer.h"
#include "Slate/WidgetRenderer.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Text/STextBlock.h"

bool SailingHullName::Place(int32 BoatType, float Aspect, FHullNamePlace& Out)
{
	if (BoatType != int32(Sailing::EBoatType::J22) || !(Aspect > 0.f)) return false;
	// The J/22's quarters: the band between the boot stripe (to 9.65 cm) and the sheer (56.8 cm aft), from 16 cm
	// forward of the transom (X -346). Letters about 7 cm tall (3 in, what a 22-footer wears); a long name is made
	// smaller rather than run forward of the cockpit.
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

UTextureRenderTarget2D* SailingHullName::Draw(UObject* Outer, const FString& Name, FVector2D& OutSizePx)
{
	if (Name.IsEmpty() || !FApp::CanEverRender() || !FSlateApplication::IsInitialized())
	{
		SAIL_LOG(Log, TEXT("Hull name: not drawn (name %d letters, can render %d, Slate %d)"), Name.Len(), FApp::CanEverRender() ? 1 : 0, FSlateApplication::IsInitialized() ? 1 : 0);
		return nullptr;
	}
	// The menus' title face at its largest (Besley Bold; the fallback face before the overhaul's fonts are in).
	const FSlateFontInfo Face = SailUI::Font(SailUI::EType::Logo);
	const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
	const FString Shown = Name;
	const float TextW = float(Measure->Measure(Shown, Face).X);
	const float TextH = float(Measure->GetMaxCharacterHeight(Face));
	constexpr float PadPx = 12.f;
	const int32 W = FMath::Clamp(FMath::CeilToInt(TextW + 2.f * PadPx), 64, 2048);
	const int32 H = FMath::Clamp(FMath::CeilToInt(TextH + 2.f * PadPx), 32, 512);
	UTextureRenderTarget2D* Target = NewObject<UTextureRenderTarget2D>(Outer);
	Target->ClearColor = FLinearColor::Black;
	Target->Filter = TF_Bilinear;
	Target->AddressX = TA_Clamp;
	Target->AddressY = TA_Clamp;
	Target->InitCustomFormat(W, H, PF_B8G8R8A8, false);
	const TSharedRef<SWidget> Widget = SNew(SBox).WidthOverride(float(W)).HeightOverride(float(H)).HAlign(HAlign_Center).VAlign(VAlign_Center)
	[
		SNew(STextBlock).Text(FText::FromString(Shown)).Font(Face).ColorAndOpacity(FLinearColor::White)
	];
	// (deleted on the render thread once its draw has gone through)
	FWidgetRenderer* Renderer = new FWidgetRenderer(true, true);
	Renderer->DrawWidget(Target, Widget, FVector2D(W, H), 0.f);
	BeginCleanup(Renderer);
	OutSizePx = FVector2D(W, H);
	return Target;
}
