#include "LakeData.h"
#include "SailingSim.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/Compression.h"
#include "Misc/CommandLine.h"
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
	// Graphics G2: the 1 m lidar shore detail ("SSDZ" + raw size + zlib), where baked. -SailingNoShoreDetail compares.
	TArray<uint8> DetailBytes;
	if (!FParse::Param(FCommandLine::Get(), TEXT("SailingNoShoreDetail")) && FFileHelper::LoadFileToArray(DetailBytes, *(Directory / (Name + TEXT(".detail"))))
		&& DetailBytes.Num() > 8 && FMemory::Memcmp(DetailBytes.GetData(), "SSDZ", 4) == 0)
	{
		uint32 RawSize = 0;
		FMemory::Memcpy(&RawSize, DetailBytes.GetData() + 4, 4);
		TArray<uint8> Raw;
		Raw.SetNumUninitialized(RawSize);
		if (FCompression::UncompressMemory(NAME_Zlib, Raw.GetData(), RawSize, DetailBytes.GetData() + 8, DetailBytes.Num() - 8)
			&& Terrain.LoadDetail(Raw.GetData(), Raw.Num()))
		{
			UE_LOG(LogSailing, Log, TEXT("Lake %s: 1 m shore detail loaded (%.1f MB)"), *Name, RawSize / 1e6);
		}
		else
		{
			UE_LOG(LogSailing, Warning, TEXT("Lake %s: shore detail did not load"), *Name);
		}
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
	LoadHouses(Directory / (Name + TEXT(".houses")));
	LoadCrowns(Directory / (Name + TEXT(".crowns")));
	if (!FParse::Param(FCommandLine::Get(), TEXT("SailingNoPiers"))) LoadPiers(Directory / (Name + TEXT(".piers")));
	if (Marina.Load(FPaths::Combine(Directory, Name + TEXT(".marina.json"))))
	{
		Marina.PlaceAlongside([this](double X, double Y) { return -Terrain.HeightAt(X, Y); });
	}
	BuildObstacles();
	UE_LOG(LogSailing, Display, TEXT("Lake %s: %dx%d terrain, %d docks, %d decks, %d moored boats, %d bridges, %d buildings, %d houses, %d launch spots, %d navaids, %d tide stations"), *LakeName,
		Terrain.GetCols(), Terrain.GetRows(), Docks.Num(), Decks.Num(), MooredBoats.Num(), Bridges.Num(), Buildings.Num(), Houses.Num(), LaunchSpots.Num(), Navaids.Num(), int32(Tides.HeightStations.size()));
	return true;
}

void FLakeData::LoadPiers(const FString& Path)
{
	Decks.Reset();
	MooredBoats.Reset();
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path)) return;
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
	{
		UE_LOG(LogSailing, Warning, TEXT("Piers: bad JSON in %s"), *Path);
		return;
	}
	auto Points = [](const TArray<TSharedPtr<FJsonValue>>& A)
	{
		TArray<FVector2D> P;
		P.Reserve(A.Num());
		for (const TSharedPtr<FJsonValue>& V : A) { const TArray<TSharedPtr<FJsonValue>>& XY = V->AsArray(); P.Add(FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber())); }
		return P;
	};
	// -SailingPiersSkip=decks,riprap,walkways,boats leaves layers out (to compare).
	FString Skip;
	FParse::Value(FCommandLine::Get(), TEXT("SailingPiersSkip="), Skip, false);
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("decks")))
	{
		if (Skip.Contains(TEXT("decks"))) break;
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FLakeDeck D;
		D.Outline = Points(O->GetArrayField(TEXT("pts")));
		D.Deck = float(O->GetNumberField(TEXT("deck")));
		D.bCovered = O->GetBoolField(TEXT("covered"));
		D.Kind = O->GetStringField(TEXT("kind"));
		if (D.Outline.Num() >= 4) Decks.Add(MoveTemp(D));
	}
	// OSM piers a lidar deck covers are the same structure: keep the measured one.
	TArray<FBox2D> Boxes;
	for (const FLakeDeck& D : Decks) Boxes.Add(FBox2D(D.Outline).ExpandBy(1.5));
	auto Inside = [](const TArray<FVector2D>& Poly, const FVector2D& P)
	{
		bool bIn = false;
		for (int32 I = 0, J = Poly.Num() - 1; I < Poly.Num(); J = I++)
		{
			if (((Poly[I].Y > P.Y) != (Poly[J].Y > P.Y)) && (P.X < (Poly[J].X - Poly[I].X) * (P.Y - Poly[I].Y) / (Poly[J].Y - Poly[I].Y) + Poly[I].X)) bIn = !bIn;
		}
		return bIn;
	};
	const int32 Before = Docks.Num();
	Docks.RemoveAll([&](const FLakeDock& Dock)
	{
		if (Dock.Kind == TEXT("breakwater")) return false;
		int32 In = 0;
		for (const FVector2D& P : Dock.Points)
		{
			for (int32 K = 0; K < Decks.Num(); ++K) if (Boxes[K].IsInside(P) && Inside(Decks[K].Outline, P)) { ++In; break; }
		}
		return In * 2 > Dock.Points.Num();
	});
	const int32 Superseded = Before - Docks.Num();
	int32 Riprap = 0, Walkways = 0;
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("riprap")))
	{
		if (Skip.Contains(TEXT("riprap"))) break;
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FLakeDock D;
		D.Points = Points(O->GetArrayField(TEXT("pts")));
		const FString Kind = O->GetStringField(TEXT("kind"));
		// The named landmarks (both Galveston jetties, the Texas City Dike) are breakwaters and dikes with boulders; the
		// other pieces from the narrow-structures layer keep only the baked rock core, like groins (the boulders cost the
		// High tier 3 fps on the coast).
		const bool bNamed = O->HasField(TEXT("name"));
		D.Kind = Kind == TEXT("seawall") ? Kind : (!bNamed ? FString(TEXT("groin")) : (Kind == TEXT("dike") ? Kind : FString(TEXT("breakwater"))));
		D.Width = float(O->GetNumberField(TEXT("width")));
		D.Crest = float(O->GetNumberField(TEXT("crest")));
		if (D.Points.Num() >= 2) { Docks.Add(MoveTemp(D)); ++Riprap; }
	}
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("walkways")))
	{
		if (Skip.Contains(TEXT("walkways"))) break;
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FLakeDock D;
		D.Points = Points(O->GetArrayField(TEXT("pts")));
		D.Kind = TEXT("floating");
		D.Width = float(O->GetNumberField(TEXT("w")));
		if (D.Points.Num() >= 2) { Docks.Add(MoveTemp(D)); ++Walkways; }
	}
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("boats")))
	{
		if (Skip.Contains(TEXT("boats"))) break;
		const TArray<TSharedPtr<FJsonValue>>& B = V->AsArray();
		if (B.Num() < 7) continue;
		FMooredBoat M;
		M.Center = FVector2D(B[0]->AsNumber(), B[1]->AsNumber());
		M.HeadingDeg = float(B[2]->AsNumber());
		M.Length = float(B[3]->AsNumber());
		M.Beam = float(B[4]->AsNumber());
		M.bMast = B[5]->AsNumber() > 0.5;
		M.Marina = int32(B[6]->AsNumber());
		MooredBoats.Add(M);
	}
	UE_LOG(LogSailing, Display, TEXT("Piers: %d lidar decks (%d OSM piers they cover dropped), %d riprap lines, %d inferred walkways, %d moored boats"),
		Decks.Num(), Superseded, Riprap, Walkways, MooredBoats.Num());
}

void FLakeData::LoadHouses(const FString& Path)
{
	Houses.Reset();
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *Path, FILEREAD_Silent) || Bytes.Num() < 12 || FMemory::Memcmp(Bytes.GetData(), "HOUS", 4) != 0) return;
	int64 At = 4;
	auto U32 = [&] { uint32 V = 0; FMemory::Memcpy(&V, Bytes.GetData() + At, 4); At += 4; return V; };
	auto F32 = [&] { float V = 0.f; FMemory::Memcpy(&V, Bytes.GetData() + At, 4); At += 4; return V; };
	if (U32() != 1) return;
	const uint32 Count = U32();
	Houses.Reserve(Count);
	for (uint32 K = 0; K < Count && At + 32 <= Bytes.Num(); ++K)
	{
		FLakeHouse H;
		H.X = F32(); H.Y = F32(); H.Ground = F32(); H.Eave = F32(); H.Ridge = F32(); H.PitchDeg = F32();
		const uint8* B = Bytes.GetData() + At;
		At += 8;
		H.Roof = FLakeHouse::ERoof(FMath::Min<uint8>(B[0], 3));
		H.bFullDetail = B[1] != 0;
		const int32 NumWings = B[2];
		H.Storeys = FMath::Max<int32>(1, B[3]);
		H.RoofColor = FColor(B[4], B[5], B[6]);
		H.bLidar = (B[7] & 1) != 0;
		H.bCommercial = (B[7] & 2) != 0;
		if (At + 20 * NumWings > Bytes.Num()) break;
		for (int32 W = 0; W < NumWings; ++W)
		{
			FLakeHouse::FWing Wing;
			Wing.X = F32(); Wing.Y = F32(); Wing.HalfLength = F32(); Wing.HalfWidth = F32(); Wing.YawDeg = F32();
			H.Wings.Add(Wing);
		}
		if (H.Wings.Num() > 0) Houses.Add(MoveTemp(H));
	}
}

void FLakeData::LoadCrowns(const FString& Path)
{
	Crowns.Reset();
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *Path, FILEREAD_Silent) || Bytes.Num() < 12 || FMemory::Memcmp(Bytes.GetData(), "CROW", 4) != 0) return;
	uint32 Version = 0, Count = 0;
	FMemory::Memcpy(&Version, Bytes.GetData() + 4, 4);
	FMemory::Memcpy(&Count, Bytes.GetData() + 8, 4);
	constexpr int32 Stride = 24;
	if (Version != 1) return;
	Count = FMath::Min<uint32>(Count, uint32((Bytes.Num() - 12) / Stride));
	Crowns.SetNum(Count);
	for (uint32 K = 0; K < Count; ++K)
	{
		const uint8* P = Bytes.GetData() + 12 + int64(K) * Stride;
		float F[5];
		FMemory::Memcpy(F, P, sizeof(F));
		FLakeCrown& C = Crowns[K];
		C.X = F[0]; C.Y = F[1]; C.Ground = F[2]; C.Height = F[3]; C.Radius = F[4];
		C.bCedar = P[20] != 0;
		C.bFullDetail = P[21] != 0;
		C.Weight = FMath::Max<uint8>(1, P[22]);
	}
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
			const bool bRock = Dock.Kind == TEXT("breakwater") || Dock.Kind == TEXT("groin") || Dock.Kind == TEXT("dike") || Dock.Kind == TEXT("seawall");
			S.Radius = Dock.Width > 0.f ? (bRock ? 0.4 * Dock.Width : 0.5 * Dock.Width) : (Dock.Kind == TEXT("breakwater") ? 2.2 : (Dock.bClosed ? 0.25 : 1.0));
			S.Bottom = -2.0;
			S.Top = bRock ? FMath::Max(2.0, double(Dock.Crest)) : 0.8;
			Obstacles.push_back(S);
		}
	}
	// Graphics G7: the lidar decks stand on piles round their outline; the moored boats are hulls along their axis.
	for (const FLakeDeck& Deck : Decks)
	{
		for (int32 I = 1; I < Deck.Outline.Num(); ++I)
		{
			Sailing::FObstacleSegment S;
			S.AX = Deck.Outline[I - 1].X; S.AY = Deck.Outline[I - 1].Y;
			S.BX = Deck.Outline[I].X; S.BY = Deck.Outline[I].Y;
			S.Radius = 0.3;
			S.Bottom = -2.0;
			S.Top = FMath::Min(double(Deck.Deck), 1.5);   // a dock face to tie to (FindDockLines takes Top <= 1.5)
			Obstacles.push_back(S);
		}
	}
	for (const FMooredBoat& B : MooredBoats)
	{
		const double H = FMath::DegreesToRadians(B.HeadingDeg);
		const FVector2D Half = FVector2D(FMath::Cos(H), FMath::Sin(H)) * (0.5 * B.Length - 0.5 * B.Beam);
		Sailing::FObstacleSegment S;
		S.AX = B.Center.X - Half.X; S.AY = B.Center.Y - Half.Y;
		S.BX = B.Center.X + Half.X; S.BY = B.Center.Y + Half.Y;
		S.Radius = 0.45 * B.Beam;
		S.Bottom = -1.2;
		S.Top = 1.6;   // over 1.5: not a dock to tie to
		Obstacles.push_back(S);
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
			S.Top = Kind == TEXT("breakwater") ? 2.0 : (Kind == TEXT("boat") ? 1.5 : 0.8);
			if (Kind == TEXT("boat")) S.Bottom = -1.2;
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
