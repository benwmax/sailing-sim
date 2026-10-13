#include "GpuSlices.h"

#include "Internationalization/Regex.h"

namespace
{
	const TCHAR* const GpuColumnBar = TEXT("┃"); // the box-drawing bar ProfileGPU separates its columns with

	struct FGpuPass
	{
		FString Name;
		int32 Depth = 0;
		double InclusiveMs = 0.0;
	};

	bool ParsePassLine(const FString& Line, FGpuPass& Out)
	{
		TArray<FString> Parts;
		Line.ParseIntoArray(Parts, GpuColumnBar, /*InCullEmpty*/ false);
		// "    ┃ exclusive columns ┃ inclusive columns ┃ name ┃": Parts[0] is the indent before the first bar.
		if (Parts.Num() < 4)
		{
			return false;
		}
		FRegexMatcher Ms(FRegexPattern(TEXT("([0-9]+\\.[0-9]+) ms")), Parts[2]);
		bool bFound = false;
		while (Ms.FindNext())
		{
			Out.InclusiveMs = FCString::Atod(*Ms.GetCaptureGroup(1));
			bFound = true;
		}
		if (!bFound)
		{
			return false;
		}
		const FString& Name = Parts[3];
		int32 Indent = 0;
		while (Indent < Name.Len() && Name[Indent] == TEXT(' ')) ++Indent;
		Out.Depth = Indent / 3;
		Out.Name = Name.TrimStartAndEnd();
		return !Out.Name.IsEmpty();
	}

	void AddTo(FGpuSlices& S, EGpuSlice Slice, double Ms)
	{
		switch (Slice)
		{
		case EGpuSlice::Base: S.BaseMs += Ms; break;
		case EGpuSlice::Lumen: S.LumenMs += Ms; break;
		case EGpuSlice::Water: S.WaterMs += Ms; break;
		case EGpuSlice::CloudsFog: S.CloudsFogMs += Ms; break;
		case EGpuSlice::Niagara: S.NiagaraMs += Ms; break;
		case EGpuSlice::Post: S.PostMs += Ms; break;
		}
	}
}

void FGpuSlices::Accumulate(const FGpuSlices& F)
{
	TotalMs += F.TotalMs; BaseMs += F.BaseMs; LumenMs += F.LumenMs; WaterMs += F.WaterMs;
	CloudsFogMs += F.CloudsFogMs; NiagaraMs += F.NiagaraMs; PostMs += F.PostMs; OtherMs += F.OtherMs;
	Frames += FMath::Max(F.Frames, 1);
}

FGpuSlices FGpuSlices::Average() const
{
	FGpuSlices A;
	if (Frames <= 0)
	{
		return A;
	}
	const double K = 1.0 / Frames;
	A.TotalMs = TotalMs * K; A.BaseMs = BaseMs * K; A.LumenMs = LumenMs * K; A.WaterMs = WaterMs * K;
	A.CloudsFogMs = CloudsFogMs * K; A.NiagaraMs = NiagaraMs * K; A.PostMs = PostMs * K; A.OtherMs = OtherMs * K;
	A.Frames = Frames;
	return A;
}

FString FGpuSlices::ToJsonField() const
{
	return FString::Printf(TEXT("\"gpu\":{\"frames\":%d,\"total_ms\":%.2f,\"base_ms\":%.2f,\"lumen_ms\":%.2f,\"water_ms\":%.2f,\"clouds_fog_ms\":%.2f,\"niagara_ms\":%.2f,\"post_ms\":%.2f,\"other_ms\":%.2f}"),
		Frames, TotalMs, BaseMs, LumenMs, WaterMs, CloudsFogMs, NiagaraMs, PostMs, OtherMs);
}

EGpuSlice ClassifyGpuPass(const FString& N)
{
	auto Has = [&N](const TCHAR* S) { return N.Contains(S, ESearchCase::IgnoreCase); };
	if (Has(TEXT("SingleLayerWater")) || Has(TEXT("Water"))) return EGpuSlice::Water;
	if (Has(TEXT("Lumen")) || Has(TEXT("DiffuseIndirect")) || Has(TEXT("Reflections")) || Has(TEXT("StochasticLighting"))) return EGpuSlice::Lumen;
	if (Has(TEXT("VolumetricCloud")) || Has(TEXT("VolCloud")) || Has(TEXT("SkyAtmosphere")) || Has(TEXT("Fog"))) return EGpuSlice::CloudsFog;
	if (Has(TEXT("Niagara")) || Has(TEXT("FXSystem")) || Has(TEXT("GPUParticles"))) return EGpuSlice::Niagara;
	if (Has(TEXT("PostProcessing")) || Has(TEXT("TemporalSuperResolution")) || Has(TEXT("TSR ")) || Has(TEXT("Upscale"))) return EGpuSlice::Post;
	return EGpuSlice::Base;
}

bool ParseProfileGpu(const TArray<FString>& Lines, FGpuSlices& Out)
{
	TArray<FGpuPass> Passes;
	for (const FString& Line : Lines)
	{
		FGpuPass P;
		if (ParsePassLine(Line, P)) Passes.Add(P);
	}
	int32 SceneIndex = Passes.IndexOfByPredicate([](const FGpuPass& P) { return P.Name == TEXT("Scene"); });
	if (SceneIndex == INDEX_NONE)
	{
		return false;
	}
	Out = FGpuSlices();
	Out.Frames = 1;
	// The frame's total is its outermost pass ("<root>" or "Frame N").
	for (const FGpuPass& P : Passes) Out.TotalMs = FMath::Max(Out.TotalMs, P.InclusiveMs);

	const int32 SceneDepth = Passes[SceneIndex].Depth;
	double SceneSum = 0.0;
	for (int32 I = SceneIndex + 1; I < Passes.Num() && Passes[I].Depth > SceneDepth; ++I)
	{
		const FGpuPass& P = Passes[I];
		if (P.Depth != SceneDepth + 1)
		{
			continue;
		}
		SceneSum += P.InclusiveMs;
		if (P.Name.StartsWith(TEXT("RenderDeferredLighting")))
		{
			// Split the deferred lighting: Lumen's children to Lumen, the direct lights to Base.
			double LumenPart = 0.0;
			for (int32 J = I + 1; J < Passes.Num() && Passes[J].Depth > P.Depth; ++J)
			{
				if (Passes[J].Depth == P.Depth + 1 && ClassifyGpuPass(Passes[J].Name) == EGpuSlice::Lumen) LumenPart += Passes[J].InclusiveMs;
			}
			Out.LumenMs += LumenPart;
			Out.BaseMs += FMath::Max(P.InclusiveMs - LumenPart, 0.0);
			continue;
		}
		AddTo(Out, ClassifyGpuPass(P.Name), P.InclusiveMs);
	}
	Out.OtherMs = FMath::Max(Out.TotalMs - SceneSum, 0.0);
	return true;
}

void FGpuProfileCapture::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& Category)
{
	static const FName RhiCategory(TEXT("LogRHI"));
	if (Category != RhiCategory)
	{
		return;
	}
	FScopeLock ScopeLock(&Lock);
	Lines.Add(V);
}

TArray<TArray<FString>> FGpuProfileCapture::Take()
{
	FScopeLock ScopeLock(&Lock);
	TArray<TArray<FString>> Dumps;
	for (const FString& Line : Lines)
	{
		// Each dump starts with "GPU Profile for Frame N".
		if (Line.Contains(TEXT("GPU Profile for Frame")) || Dumps.Num() == 0)
		{
			Dumps.AddDefaulted();
		}
		Dumps.Last().Add(Line);
	}
	Lines.Reset();
	return Dumps;
}
