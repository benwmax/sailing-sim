#include "Chart.h"
#include "LakeData.h"
#include "SailingSim.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	/** A flat [x, y, x, y, ...] array starting at Offset. */
	void ReadPoints(const TArray<TSharedPtr<FJsonValue>>& A, int32 Offset, FChartData::FLine& Line)
	{
		for (int32 I = Offset; I + 1 < A.Num(); I += 2)
		{
			const FVector2D P(A[I]->AsNumber(), A[I + 1]->AsNumber());
			Line.Points.Add(P);
			Line.Bounds += P;
		}
	}

	void ReadLines(const FJsonObject& Root, const TCHAR* Field, bool bLeadingValue, bool bLeadingKind, TArray<FChartData::FLine>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
		if (!Root.TryGetArrayField(Field, Array)) return;
		Out.Reserve(Array->Num());
		for (const TSharedPtr<FJsonValue>& V : *Array)
		{
			const TArray<TSharedPtr<FJsonValue>>& A = V->AsArray();
			FChartData::FLine Line;
			int32 Offset = 0;
			if (bLeadingValue && A.Num() > 0) { Line.Value = A[0]->AsNumber(); Offset = 1; }
			if (bLeadingKind && A.Num() > 0) { Line.Kind = A[0]->AsString(); Offset = 1; }
			ReadPoints(A, Offset, Line);
			if (Line.Points.Num() >= 2) Out.Add(MoveTemp(Line));
		}
	}
}

bool FChartData::Load(const FString& Path)
{
	FString Json;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		UE_LOG(LogSailing, Warning, TEXT("No chart at %s"), *Path);
		return false;
	}
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root) || !Root.IsValid())
	{
		UE_LOG(LogSailing, Warning, TEXT("Could not parse the chart %s"), *Path);
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
	if (Root->TryGetArrayField(TEXT("areas"), Array))
	{
		Triangles.Reserve(Array->Num() * 3);
		TriangleClass.Reserve(Array->Num());
		for (const TSharedPtr<FJsonValue>& V : *Array)
		{
			const TArray<TSharedPtr<FJsonValue>>& A = V->AsArray();
			if (A.Num() < 7) continue;
			if (TriangleClass.Num() % TrianglesPerBlock == 0) TriangleBounds.Add(FBox2D(ForceInit));
			TriangleClass.Add(uint8(A[0]->AsNumber()));
			for (int32 K = 0; K < 3; ++K)
			{
				const FVector2D P(A[1 + 2 * K]->AsNumber(), A[2 + 2 * K]->AsNumber());
				Triangles.Add(P);
				TriangleBounds.Last() += P;
				Bounds += P;
			}
		}
	}
	ReadLines(*Root, TEXT("contours"), true, false, Contours);
	ReadLines(*Root, TEXT("coast"), false, false, Coast);
	ReadLines(*Root, TEXT("channels"), false, false, Channels);
	ReadLines(*Root, TEXT("bridges"), false, true, Bridges);
	ReadLines(*Root, TEXT("docks"), false, true, Docks);
	if (Root->TryGetArrayField(TEXT("soundings"), Array))
	{
		for (const TSharedPtr<FJsonValue>& V : *Array)
		{
			const TArray<TSharedPtr<FJsonValue>>& A = V->AsArray();
			if (A.Num() >= 3) Soundings.Add(FVector3d(A[0]->AsNumber(), A[1]->AsNumber(), A[2]->AsNumber()));
		}
	}
	UE_LOG(LogSailing, Display, TEXT("Chart: %d triangles, %d contours, %d soundings, %d coast lines"),
		TriangleClass.Num(), Contours.Num(), Soundings.Num(), Coast.Num());
	return IsLoaded();
}

namespace SailingChart
{
	ESymbol SymbolFor(const FNavaid& Aid)
	{
		if (Aid.Kind == TEXT("light")) return ESymbol::LightMajor;
		if (Aid.Kind == TEXT("beacon")) return ESymbol::Beacon;
		// S-57 BOYSHP: 1 conical (nun), 2 can, 3 spherical, 4 pillar, 5 spar, 6 barrel, 7 super-buoy, 8 ice buoy.
		switch (Aid.Shape)
		{
		case 1: return ESymbol::Nun;
		case 2: return ESymbol::Can;
		case 3: return ESymbol::Sphere;
		case 5: return ESymbol::Spar;
		default: return ESymbol::Pillar;
		}
	}

	FString AidNumber(const FNavaid& Aid)
	{
		// The chart prints the aid's number from its name: "Clear Creek Channel Light 23" -> "23", "... Buoy 4A" -> "4A".
		// AIS-equipped aids carry ", MMSI 993682791" after the name.
		FString Name = Aid.Name, Suffix;
		Aid.Name.Split(TEXT(","), &Name, &Suffix);
		FString Last;
		if (!Name.Split(TEXT(" "), nullptr, &Last, ESearchCase::IgnoreCase, ESearchDir::FromEnd)) Last = Name;
		if (Last.IsEmpty() || Last.Len() > 4) return FString();
		// Digits and capitals only ("12", "4A", "GB"); a word like "Light" or "Tower" is not a number.
		for (const TCHAR Ch : Last)
		{
			if (!FChar::IsDigit(Ch) && !FChar::IsUpper(Ch)) return FString();
		}
		return Last;
	}

	FString AidLabel(const FNavaid& Aid)
	{
		const FString Number = AidNumber(Aid);
		const FString Quoted = Number.IsEmpty() ? FString() : FString::Printf(TEXT(" \"%s\""), *Number);
		if (Aid.bLit)
		{
			// Lit aids: the light's character, then the number ("Fl G 4s \"5\"").
			return FString(UTF8_TO_TCHAR(Aid.Light.Label().c_str())) + Quoted;
		}
		FString Colour;
		for (int32 C : Aid.Colours) Colour += UTF8_TO_TCHAR(Sailing::ColourAbbreviation(C));
		if (Aid.Kind == TEXT("buoy"))
		{
			// Unlit buoys: color and shape letters, "G C" for a green can, "R N" for a red nun.
			const ESymbol S = SymbolFor(Aid);
			const TCHAR* Shape = S == ESymbol::Can ? TEXT(" C") : (S == ESymbol::Nun ? TEXT(" N") : (S == ESymbol::Sphere ? TEXT(" Sp") : TEXT("")));
			return Colour + Shape + Quoted;
		}
		return Colour + Quoted;
	}

	FLinearColor AreaColour(uint8 DepthClass)
	{
		// The NOAA paper chart palette: land buff, drying green, blue tints to the 6 and 12 ft curves, white beyond.
		switch (DepthClass)
		{
		case FChartData::Drying: return FLinearColor::FromSRGBColor(FColor(166, 200, 138));
		case FChartData::Shoal: return FLinearColor::FromSRGBColor(FColor(136, 181, 228));
		case FChartData::Shallow: return FLinearColor::FromSRGBColor(FColor(196, 222, 245));
		case FChartData::Land: return FLinearColor::FromSRGBColor(FColor(250, 228, 170));
		default: return FLinearColor::FromSRGBColor(FColor(255, 255, 255));
		}
	}

	FLinearColor AidColour(const FNavaid& Aid)
	{
		const int32 C = Aid.Colours.Num() > 0 ? Aid.Colours[0] : (Aid.DaymarkColours.Num() > 0 ? Aid.DaymarkColours[0] : (Aid.CatLam == 1 ? 4 : (Aid.CatLam == 2 ? 3 : 2)));
		switch (C)
		{
		case 3: return FLinearColor::FromSRGBColor(FColor(214, 30, 40));
		case 4: return FLinearColor::FromSRGBColor(FColor(20, 150, 60));
		case 6: return FLinearColor::FromSRGBColor(FColor(230, 190, 20));
		case 1: return FLinearColor::FromSRGBColor(FColor(240, 240, 240));
		default: return FLinearColor::FromSRGBColor(FColor(30, 30, 30));
		}
	}

	FString SoundingText(double DepthM)
	{
		const double Feet = DepthM / 0.3048;
		// Drying heights are printed underlined with the height above datum; we prefix them as the ENC viewers do.
		if (Feet < 0.0) return FString::Printf(TEXT("_%d"), FMath::RoundToInt(-Feet));
		return FString::Printf(TEXT("%d"), FMath::FloorToInt(Feet)); // charts round soundings down (to the safe side)
	}
}
