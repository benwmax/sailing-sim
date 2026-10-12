#include "Logbook.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

void FLogbook::Begin(const FString& InArea, const FString& InBoat, double UnixTime, const FString& Clock)
{
	Entries.Reset();
	Area = InArea;
	Boat = InBoat;
	MaxSpeedKnots = 0.0;
	SessionStartUnix = UnixTime;
	const FDateTime Start = FDateTime::FromUnixTimestamp(int64(UnixTime));
	FString SafeArea = Area;
	for (TCHAR& C : SafeArea.GetCharArray()) if (!FChar::IsAlnum(C) && C != 0) C = TEXT('_');
	FilePath = FPaths::ProjectSavedDir() / TEXT("Logbook") / FString::Printf(TEXT("%s %s.json"), *Start.ToString(TEXT("%Y-%m-%d %H%M")), *SafeArea.Left(40));
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(FilePath), true);
}

void FLogbook::Add(const FLogEntry& Entry)
{
	Entries.Add(Entry);
	MaxSpeedKnots = FMath::Max(MaxSpeedKnots, Entry.SpeedKnots);
	if (Entries.Num() > 2000) Entries.RemoveAt(0);
	Save();
}

FString FLogbook::FormatPosition(double Latitude, double Longitude)
{
	auto Part = [](double V, TCHAR Pos, TCHAR Neg)
	{
		const double A = FMath::Abs(V);
		const int32 Deg = int32(A);
		return FString::Printf(TEXT("%d%c%05.2f'%c"), Deg, TCHAR(0xB0), (A - Deg) * 60.0, V >= 0.0 ? Pos : Neg);
	};
	return Part(Latitude, TEXT('N'), TEXT('S')) + TEXT("  ") + Part(Longitude, TEXT('E'), TEXT('W'));
}

void FLogbook::Save() const
{
	if (FilePath.IsEmpty()) return;
	TArray<TSharedPtr<FJsonValue>> List;
	for (const FLogEntry& E : Entries)
	{
		TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
		O->SetNumberField(TEXT("unix"), E.UnixTime);
		O->SetStringField(TEXT("clock"), E.Clock);
		O->SetStringField(TEXT("kind"), E.Kind);
		O->SetNumberField(TEXT("lat"), E.Latitude);
		O->SetNumberField(TEXT("lon"), E.Longitude);
		O->SetNumberField(TEXT("course_true"), FMath::RoundToDouble(E.CourseTrue));
		O->SetNumberField(TEXT("speed_kn"), FMath::RoundToDouble(E.SpeedKnots * 10.0) / 10.0);
		O->SetNumberField(TEXT("heading_magnetic"), FMath::RoundToDouble(E.HeadingMagnetic));
		O->SetNumberField(TEXT("log_nm"), FMath::RoundToDouble(E.LogNm * 100.0) / 100.0);
		O->SetNumberField(TEXT("wind_from"), FMath::RoundToDouble(E.WindFromDeg));
		O->SetNumberField(TEXT("wind_kn"), FMath::RoundToDouble(E.WindKnots));
		O->SetNumberField(TEXT("sea_m"), FMath::RoundToDouble(E.SeaMeters * 10.0) / 10.0);
		O->SetStringField(TEXT("remarks"), E.Remarks);
		List.Add(MakeShared<FJsonValueObject>(O));
	}
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("area"), Area);
	Root->SetStringField(TEXT("boat"), Boat);
	Root->SetArrayField(TEXT("entries"), List);
	FString Json;
	FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Json));
	FFileHelper::SaveStringToFile(Json, *FilePath);
}
