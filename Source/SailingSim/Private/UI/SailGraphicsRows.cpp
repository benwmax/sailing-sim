#include "UI/SailGraphicsRows.h"
#include "UI/SailWidgets.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"

namespace SailGraphicsRowsImpl
{
	/** Picks an option from a list of values (the first that matches, else the first). */
	int32 IndexOf(const TArray<int32>& Values, int32 V)
	{
		const int32 I = Values.IndexOfByKey(V);
		return I == INDEX_NONE ? 0 : I;
	}
}

namespace SailGraphicsRows
{
	TSharedRef<SWidget> Quality(ASailingGameMode* GM)
	{
		USailingSettings* S = USailingSettings::Get();
		TWeakObjectPtr<ASailingGameMode> Mode = GM;
		return SNew(SSailChoice).Label(TEXT("Quality")).Options({ TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Ultra") })
			.Index_Lambda([S]() { return int32(S->Quality); })
			.OnChanged_Lambda([S, Mode](int32 I) { S->Quality = ESailingQuality(I); S->ResetGraphicsRows(); S->Save(); if (Mode.IsValid()) Mode->ApplyQualitySettings(); });
	}

	TSharedRef<SWidget> AntiAliasing(ASailingGameMode* GM, bool bNote)
	{
		using namespace SailGraphicsRowsImpl;
		USailingSettings* S = USailingSettings::Get();
		TWeakObjectPtr<ASailingGameMode> Mode = GM;
		// Bean's playtest: anti-aliasing and each feature's detail on their own, Auto following the tier.
		// NVIDIA DLSS's modes join the list where the optional plugin is installed and the GPU is NVIDIA's.
		TArray<int32> AAValues = { -1, 0, 2, 4, 5 };
		TArray<FString> AANames = { TEXT("Auto"), TEXT("Off"), TEXT("TAA"), TEXT("TSR"), TEXT("SMAA") };
		const bool bDLSS = USailingSettings::DLSSAvailable();
		if (bDLSS)
		{
			AAValues.Append({ 10, 11, 12, 13 });
			AANames.Append({ TEXT("DLAA"), TEXT("DLSS Quality"), TEXT("DLSS Balanced"), TEXT("DLSS Performance") });
		}
		const FString Note = !bNote ? FString()
			: bDLSS ? TEXT("TSR: the sharpest of the engine's own. DLAA and DLSS: NVIDIA's AI anti-aliasing and upscaling (DLSS sets its own render scale).")
			: TEXT("TSR: the sharpest, upscales from the render resolution. TAA: lighter. SMAA: no ghosting, more shimmer.");
		return SNew(SSailChoice).Label(TEXT("Anti-aliasing")).Options(AANames)
			.Index_Lambda([S, AAValues]() { return IndexOf(AAValues, S->AntiAliasing); })
			.OnChanged_Lambda([S, Mode, AAValues](int32 I) { S->AntiAliasing = AAValues[I]; S->Save(); if (Mode.IsValid()) Mode->ApplyQualitySettings(); })
			.Note(Note);
	}

	TSharedRef<SWidget> Detail(ASailingGameMode* GM, const TCHAR* Label, int32 USailingSettings::* Field, const TCHAR* Note)
	{
		USailingSettings* S = USailingSettings::Get();
		TWeakObjectPtr<ASailingGameMode> Mode = GM;
		return SNew(SSailChoice).Label(Label).Options({ TEXT("Auto"), TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Ultra") })
			.Index_Lambda([S, Field]() { return FMath::Clamp(S->*Field + 1, 0, 4); })
			.OnChanged_Lambda([S, Mode, Field](int32 I) { S->*Field = I - 1; S->Save(); if (Mode.IsValid()) Mode->ApplyQualitySettings(); })
			.Note(Note);
	}

	TSharedRef<SWidget> MotionBlur(ASailingGameMode* GM)
	{
		using namespace SailGraphicsRowsImpl;
		USailingSettings* S = USailingSettings::Get();
		TWeakObjectPtr<ASailingGameMode> Mode = GM;
		static const TArray<int32> BlurValues = { -1, 0, 1 };
		return SNew(SSailChoice).Label(TEXT("Motion blur")).Options({ TEXT("Auto"), TEXT("Off"), TEXT("On") })
			.Index_Lambda([S]() { return IndexOf(BlurValues, S->MotionBlur); })
			.OnChanged_Lambda([S, Mode](int32 I) { S->MotionBlur = BlurValues[I]; S->Save(); if (Mode.IsValid()) Mode->ApplyQualitySettings(); });
	}

	TSharedRef<SWidget> RenderScale(ASailingGameMode* GM, bool bNote)
	{
		using namespace SailGraphicsRowsImpl;
		USailingSettings* S = USailingSettings::Get();
		TWeakObjectPtr<ASailingGameMode> Mode = GM;
		static const TArray<int32> Scales = { 0, 100, 82, 67, 50 };
		return SNew(SSailChoice).Label(TEXT("Render scale")).Options({ TEXT("Auto"), TEXT("100%"), TEXT("82%"), TEXT("67%"), TEXT("50%") })
			.Index_Lambda([S]() { return IndexOf(Scales, S->ResolutionScale); })
			.OnChanged_Lambda([S, Mode](int32 I) { S->ResolutionScale = Scales[I]; S->Save(); if (Mode.IsValid()) Mode->ApplyQualitySettings(); })
			.Note(bNote ? TEXT("Auto is the tier's own: 67% with TAA on Medium, native on High with the governor stepping to 82% in heavy views.") : TEXT(""));
	}
}
