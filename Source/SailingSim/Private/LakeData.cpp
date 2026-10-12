#include "LakeData.h"
#include "SailingSim.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

FString FLakeData::DefaultDirectory()
{
	return FPaths::ProjectContentDir() / TEXT("TerrainData");
}

bool FLakeData::Load(const FString& Directory, const FString& Name)
{
	TArray<uint8> HeightBytes;
	if (!FFileHelper::LoadFileToArray(HeightBytes, *(Directory / (Name + TEXT(".height")))) || !Terrain.LoadHeight(HeightBytes.GetData(), HeightBytes.Num()))
	{
		UE_LOG(LogSailing, Warning, TEXT("Lake %s: no terrain in %s"), *Name, *Directory);
		return false;
	}
	if (FFileHelper::LoadFileToArray(TreeBytes, *(Directory / (Name + TEXT(".trees")))))
	{
		Terrain.LoadTrees(TreeBytes.GetData(), TreeBytes.Num());
	}

	FString JsonText;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(JsonText, *(Directory / (Name + TEXT(".json"))))
		|| !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid())
	{
		UE_LOG(LogSailing, Warning, TEXT("Lake %s: no metadata"), *Name);
		return true;
	}
	LakeName = Root->GetStringField(TEXT("name"));
	PoolFeet = Root->GetNumberField(TEXT("pool_ft_ngvd29"));

	auto ReadPoints = [](const TArray<TSharedPtr<FJsonValue>>& Array)
	{
		TArray<FVector2D> Points;
		for (const TSharedPtr<FJsonValue>& P : Array)
		{
			const TArray<TSharedPtr<FJsonValue>>& XY = P->AsArray();
			Points.Add(FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber()));
		}
		return Points;
	};

	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("launch_spots")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		const TArray<TSharedPtr<FJsonValue>>& XY = O->GetArrayField(TEXT("xy"));
		LaunchSpots.Add({ O->GetStringField(TEXT("name")), XY[0]->AsNumber(), XY[1]->AsNumber(), O->GetNumberField(TEXT("heading")) });
	}
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("checkpoints")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		const TArray<TSharedPtr<FJsonValue>>& XY = O->GetArrayField(TEXT("shore"));
		Checkpoints.Add({ O->GetStringField(TEXT("name")), FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber()) });
	}
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("docks")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FLakeDock Dock;
		Dock.Points = ReadPoints(O->GetArrayField(TEXT("points")));
		Dock.Kind = O->GetStringField(TEXT("kind"));
		Dock.bClosed = Dock.Points.Num() > 3 && FVector2D::Distance(Dock.Points[0], Dock.Points.Last()) < 0.05;
		if (Dock.Points.Num() >= 2) Docks.Add(MoveTemp(Dock));
	}
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("bridges")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FLakeBridge Bridge;
		Bridge.Name = O->GetStringField(TEXT("name"));
		Bridge.Points = ReadPoints(O->GetArrayField(TEXT("points")));
		Bridge.DeckHeight = O->GetNumberField(TEXT("deck"));
		if (Bridge.Points.Num() >= 2) Bridges.Add(MoveTemp(Bridge));
	}
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("buildings")))
	{
		const TArray<TSharedPtr<FJsonValue>>& B = V->AsArray();
		if (B.Num() >= 7)
		{
			Buildings.Add({ B[0]->AsNumber(), B[1]->AsNumber(), B[2]->AsNumber(), B[3]->AsNumber(), B[4]->AsNumber(), B[5]->AsNumber(), B[6]->AsNumber() });
		}
	}
	BuildObstacles();
	UE_LOG(LogSailing, Display, TEXT("Lake %s: %dx%d terrain, %d docks, %d bridges, %d buildings, %d launch spots"), *LakeName,
		Terrain.GetCols(), Terrain.GetRows(), Docks.Num(), Bridges.Num(), Buildings.Num(), LaunchSpots.Num());
	return true;
}

void FLakeData::BuildObstacles()
{
	Obstacles.clear();
	for (const FLakeDock& Dock : Docks)
	{
		// Floating docks and fixed piers: decks about 0.5 m above the water, reaching below the hull.
		for (int32 I = 1; I < Dock.Points.Num(); ++I)
		{
			Sailing::FObstacleSegment S;
			S.AX = Dock.Points[I - 1].X; S.AY = Dock.Points[I - 1].Y;
			S.BX = Dock.Points[I].X; S.BY = Dock.Points[I].Y;
			S.Radius = Dock.Kind == TEXT("breakwater") ? 1.5 : 0.25;
			S.Bottom = -2.0;
			S.Top = Dock.Kind == TEXT("breakwater") ? 2.0 : 0.8;
			Obstacles.push_back(S);
		}
	}
	for (const FLakeBridge& Bridge : Bridges)
	{
		// The deck spans from its clearance upward: the hull passes under, the mast (9.2 m) does not.
		for (int32 I = 1; I < Bridge.Points.Num(); ++I)
		{
			Sailing::FObstacleSegment S;
			S.AX = Bridge.Points[I - 1].X; S.AY = Bridge.Points[I - 1].Y;
			S.BX = Bridge.Points[I].X; S.BY = Bridge.Points[I].Y;
			S.Radius = 8.0;
			S.Bottom = Bridge.DeckHeight - 1.0;
			S.Top = Bridge.DeckHeight + 3.0;
			Obstacles.push_back(S);
		}
	}
}
