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
	FileName = Name;
	LakeName = Root->GetStringField(TEXT("name"));
	Root->TryGetNumberField(TEXT("pool_ft_ngvd29"), PoolFeet);
	Root->TryGetNumberField(TEXT("mhw_m"), MeanHighWater);
	Root->TryGetNumberField(TEXT("latitude"), Latitude);
	Root->TryGetNumberField(TEXT("longitude"), Longitude);
	Root->TryGetBoolField(TEXT("ocean"), bOcean);
	const TArray<TSharedPtr<FJsonValue>>* PassageArray = nullptr;
	if (Root->TryGetArrayField(TEXT("passage"), PassageArray))
	{
		for (const TSharedPtr<FJsonValue>& V : *PassageArray)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			const TArray<TSharedPtr<FJsonValue>>& XY = O->GetArrayField(TEXT("xy"));
			Passage.Add({ O->GetStringField(TEXT("name")), FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber()) });
		}
	}
	LevelFeet = PoolFeet;
	for (const auto& Field : Root->Values)
	{
		// "level_2026_10_11_ft": the TWDB reading on the day of the bake.
		const FString Key(Field.Key);
		if (Key.StartsWith(TEXT("level_")) && Key.EndsWith(TEXT("_ft")))
		{
			LevelFeet = Field.Value->AsNumber();
			LevelDate = Key.Mid(6, 10).Replace(TEXT("_"), TEXT("-"));
		}
	}

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
		O->TryGetStringField(TEXT("kind"), Bridge.Kind);
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
	LoadCoast(*Root, Directory, Name);
	Marina.Load(FPaths::Combine(Directory, Name + TEXT(".marina.json")));
	BuildObstacles();
	UE_LOG(LogSailing, Display, TEXT("Lake %s: %dx%d terrain, %d docks, %d bridges, %d buildings, %d launch spots, %d navaids, %d tide stations"), *LakeName,
		Terrain.GetCols(), Terrain.GetRows(), Docks.Num(), Bridges.Num(), Buildings.Num(), LaunchSpots.Num(), Navaids.Num(), int32(Tides.HeightStations.size()));
	return true;
}

void FLakeData::BuildObstacles()
{
	Obstacles.clear();
	const FBox2D MarinaBox = Marina.Bounds();
	for (const FLakeDock& Dock : Docks)
	{
		if (MarinaBox.bIsValid && MarinaBox.IsInside(Dock.Points[0])) continue; // the marina's own docks stand in
		// Floating docks and fixed piers: decks about 0.5 m above the water, reaching below the hull.
		for (int32 I = 1; I < Dock.Points.Num(); ++I)
		{
			Sailing::FObstacleSegment S;
			S.AX = Dock.Points[I - 1].X; S.AY = Dock.Points[I - 1].Y;
			S.BX = Dock.Points[I].X; S.BY = Dock.Points[I].Y;
			// Breakwaters are rubble; open lines are drawn as 2 m walkways; closed outlines are the deck edge.
			// Breakwaters: the riprap band's half-width at the waterline (BuildShoreGeometry); piers as drawn.
			S.Radius = Dock.Kind == TEXT("breakwater") ? 2.2 : (Dock.bClosed ? 0.25 : 1.0);
			S.Bottom = -2.0;
			S.Top = Dock.Kind == TEXT("breakwater") ? 2.0 : 0.8;
			Obstacles.push_back(S);
		}
	}
	// Visual V6: the marina's docks, finger piers and breakwater stop the boat where they are drawn (AMarinaActor).
	Marina.ForEachObstacleLine([this](const TArray<FVector2D>& Points, const FString& Kind, float HalfWidth)
	{
		for (int32 I = 1; I < Points.Num(); ++I)
		{
			Sailing::FObstacleSegment S;
			S.AX = Points[I - 1].X; S.AY = Points[I - 1].Y;
			S.BX = Points[I].X; S.BY = Points[I].Y;
			S.Radius = HalfWidth;
			S.Bottom = -2.0;
			S.Top = Kind == TEXT("breakwater") ? 2.0 : 0.8;
			Obstacles.push_back(S);
		}
	});
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

namespace
{
	// The bake writes S-57 attributes as charted: a number, a string, or a list of strings.
	int32 JsonInt(const TSharedPtr<FJsonValue>& V)
	{
		if (!V.IsValid() || V->IsNull()) return 0;
		if (V->Type == EJson::Number) return int32(V->AsNumber());
		if (V->Type == EJson::String) return FCString::Atoi(*V->AsString());
		if (V->Type == EJson::Array && V->AsArray().Num() > 0) return JsonInt(V->AsArray()[0]);
		return 0;
	}

	TArray<int32> JsonInts(const TSharedPtr<FJsonValue>& V)
	{
		TArray<int32> Out;
		if (!V.IsValid() || V->IsNull()) return Out;
		if (V->Type == EJson::Array)
		{
			for (const TSharedPtr<FJsonValue>& E : V->AsArray())
			{
				// A colour list may arrive as "3" or "3,4".
				TArray<FString> Parts;
				(E->Type == EJson::String ? E->AsString() : FString::FromInt(int32(E->AsNumber()))).ParseIntoArray(Parts, TEXT(","));
				for (const FString& P : Parts) Out.Add(FCString::Atoi(*P));
			}
		}
		else
		{
			Out.Add(JsonInt(V));
		}
		return Out;
	}

	Sailing::FTideStation ReadStation(const FJsonObject& O)
	{
		Sailing::FTideStation S;
		S.Name = TCHAR_TO_UTF8(*O.GetStringField(TEXT("name")));
		S.X = O.GetNumberField(TEXT("x"));
		S.Y = O.GetNumberField(TEXT("y"));
		S.Z0 = O.GetNumberField(TEXT("z0"));
		double Flood = 0.0;
		if (O.TryGetNumberField(TEXT("flood_deg"), Flood)) S.FloodDirRad = FMath::DegreesToRadians(Flood);
		for (const TSharedPtr<FJsonValue>& C : O.GetArrayField(TEXT("constituents")))
		{
			const TArray<TSharedPtr<FJsonValue>>& A = C->AsArray();
			S.Constituents.push_back({ TCHAR_TO_UTF8(*A[0]->AsString()), A[1]->AsNumber(), A[2]->AsNumber() });
		}
		return S;
	}
}

FLinearColor FNavaid::DisplayColour() const
{
	const int32 C = Colours.Num() > 0 ? Colours[0] : (CatLam == 1 ? 4 : (CatLam == 2 ? 3 : 6));
	switch (C)
	{
	case 1: return FLinearColor(0.9f, 0.9f, 0.88f);
	case 2: return FLinearColor(0.03f, 0.03f, 0.03f);
	case 3: return FLinearColor(0.75f, 0.06f, 0.05f);
	case 4: return FLinearColor(0.04f, 0.45f, 0.12f);
	case 6: return FLinearColor(0.95f, 0.75f, 0.05f);
	case 11: return FLinearColor(0.95f, 0.45f, 0.05f);
	default: return FLinearColor(0.6f, 0.6f, 0.6f);
	}
}

void FLakeData::LoadCoast(const FJsonObject& Root, const FString& Directory, const FString& Name)
{
	const TSharedPtr<FJsonObject>* Variation = nullptr;
	if (Root.TryGetObjectField(TEXT("variation"), Variation) && Variation && Variation->IsValid())
	{
		(*Variation)->TryGetNumberField(TEXT("deg_east"), VariationDeg);
	}
	const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
	if (Root.TryGetArrayField(TEXT("navaids"), Array))
	{
		for (const TSharedPtr<FJsonValue>& V : *Array)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			FNavaid N;
			N.X = O->GetNumberField(TEXT("x"));
			N.Y = O->GetNumberField(TEXT("y"));
			N.Kind = O->GetStringField(TEXT("kind"));
			N.Layer = O->GetStringField(TEXT("layer"));
			O->TryGetStringField(TEXT("name"), N.Name);
			N.Shape = JsonInt(O->TryGetField(TEXT("shape")));
			N.Colours = JsonInts(O->TryGetField(TEXT("colour")));
			N.CatLam = JsonInt(O->TryGetField(TEXT("catlam")));
			const TSharedPtr<FJsonObject>* Light = nullptr;
			if (O->TryGetObjectField(TEXT("light"), Light) && Light && Light->IsValid())
			{
				const FJsonObject& L = **Light;
				N.bLit = true;
				N.Light.Litchr = FMath::Max(1, JsonInt(L.TryGetField(TEXT("litchr"))));
				FString Group;
				L.TryGetStringField(TEXT("siggrp"), Group);
				N.Light.SetGroup(TCHAR_TO_UTF8(*Group));
				double Value = 0.0;
				if (L.TryGetNumberField(TEXT("sigper"), Value)) N.Light.Period = Value;
				if (L.TryGetNumberField(TEXT("range"), Value)) N.Light.RangeNm = Value;
				if (L.TryGetNumberField(TEXT("height"), Value)) N.Light.HeightM = Value;
				for (int32 C : JsonInts(L.TryGetField(TEXT("colour")))) N.Light.Colours.push_back(C);
			}
			const TSharedPtr<FJsonObject>* Daymark = nullptr;
			if (O->TryGetObjectField(TEXT("daymark"), Daymark) && Daymark && Daymark->IsValid())
			{
				N.DaymarkShape = JsonInt((*Daymark)->TryGetField(TEXT("shape")));
				N.DaymarkColours = JsonInts((*Daymark)->TryGetField(TEXT("colour")));
			}
			Navaids.Add(MoveTemp(N));
		}
	}
	if (Root.TryGetArrayField(TEXT("landmarks"), Array))
	{
		for (const TSharedPtr<FJsonValue>& V : *Array)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			FLandmark L;
			L.X = O->GetNumberField(TEXT("x"));
			L.Y = O->GetNumberField(TEXT("y"));
			O->TryGetStringField(TEXT("name"), L.Name);
			O->TryGetBoolField(TEXT("conspicuous"), L.bConspicuous);
			O->TryGetNumberField(TEXT("height"), L.Height);
			Landmarks.Add(MoveTemp(L));
		}
	}
	if (Root.TryGetArrayField(TEXT("tide_stations"), Array))
	{
		for (const TSharedPtr<FJsonValue>& V : *Array) Tides.HeightStations.push_back(ReadStation(*V->AsObject()));
	}
	const TSharedPtr<FJsonObject>* Current = nullptr;
	if (Root.TryGetObjectField(TEXT("current_station"), Current) && Current && Current->IsValid())
	{
		Tides.CurrentStation = ReadStation(**Current);
		Tides.bHasCurrent = FFileHelper::LoadFileToArray(CurrentBytes, *(Directory / (Name + TEXT(".current"))))
			&& Tides.LoadCurrentField(CurrentBytes.GetData(), CurrentBytes.Num());
	}
}
