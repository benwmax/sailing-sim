#include "UI/SailCatalog.h"
#include "SailSession.h"
#include "SailSave.h"
#include "BoatModel.h"
#include "PolarReference.h"
#include "SailingEnvironment.h"
#include "LakeData.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "WeatherDay.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

using namespace Sailing;

namespace SailCatalog
{
	FString FeetInches(double M)
	{
		const int32 TotalIn = FMath::RoundToInt(M / 0.0254);
		return FString::Printf(TEXT("%d′%d″"), TotalIn / 12, TotalIn % 12);
	}

	FString ClockText(float Hour)
	{
		const int32 Mins = FMath::RoundToInt(Hour * 60.f);
		return FString::Printf(TEXT("%02d:%02d"), (Mins / 60) % 24, Mins % 60);
	}

	FString MonthName(int32 Month)
	{
		static const TCHAR* N[] = { TEXT("Jan"), TEXT("Feb"), TEXT("Mar"), TEXT("Apr"), TEXT("May"), TEXT("Jun"), TEXT("Jul"), TEXT("Aug"), TEXT("Sep"), TEXT("Oct"), TEXT("Nov"), TEXT("Dec") };
		return N[FMath::Clamp(Month, 1, 12) - 1];
	}

	namespace
	{
		void ReadWorld(FWorld& W)
		{
			FString Text;
			TSharedPtr<FJsonObject> Root;
			if (!FFileHelper::LoadFileToString(Text, *(FLakeData::DefaultDirectory() / (W.File + TEXT(".json"))))
				|| !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid()) return;
			if (const TSharedPtr<FJsonObject>* Grid = nullptr; Root->TryGetObjectField(TEXT("grid"), Grid))
			{
				const double Cell = (*Grid)->GetNumberField(TEXT("cell_m"));
				W.GridNorth = (*Grid)->GetNumberField(TEXT("origin_north_m"));
				W.GridEast = (*Grid)->GetNumberField(TEXT("origin_east_m"));
				W.GridHeightM = ((*Grid)->GetNumberField(TEXT("rows_north")) - 1) * Cell;
				W.GridWidthM = ((*Grid)->GetNumberField(TEXT("cols_east")) - 1) * Cell;
			}
			const TArray<TSharedPtr<FJsonValue>>* Spots = nullptr;
			if (Root->TryGetArrayField(TEXT("launch_spots"), Spots))
			{
				for (const TSharedPtr<FJsonValue>& V : *Spots)
				{
					const TSharedPtr<FJsonObject> O = V->AsObject();
					FSpot S;
					S.Name = O->GetStringField(TEXT("name"));
					// A renamed spot keeps its save id with an "id" field in the bake.
					if (!O->TryGetStringField(TEXT("id"), S.Id) || S.Id.IsEmpty()) S.Id = SpotId(S.Name);
					const TArray<TSharedPtr<FJsonValue>>& XY = O->GetArrayField(TEXT("xy"));
					S.North = XY[0]->AsNumber();
					S.East = XY[1]->AsNumber();
					S.Heading = O->GetNumberField(TEXT("heading"));
					W.Spots.Add(S);
				}
			}
			const TArray<TSharedPtr<FJsonValue>>* Navaids = nullptr;
			if (Root->TryGetArrayField(TEXT("navaids"), Navaids)) W.Facts.Insert({ FString::FromInt(Navaids->Num()), TEXT("Aids to navigation") }, 0);
		}

		TArray<FWorld> MakeWorlds()
		{
			TArray<FWorld> Out;
			{
				FWorld W;
				W.Index = 0; W.File = TEXT("RayHubbard"); W.Name = TEXT("Lake Ray Hubbard"); W.Tagline = TEXT("Fresh water · No tide");
				W.Description = TEXT("Your home lake east of Dallas. Leave from Rush Creek Yacht Club in Heath, short-tack under the I-30 "
					"causeway, and learn to read gusts coming off the trees. Pop-up afternoon storms in summer.");
				W.MapTexture = TEXT("/Game/UI/T_Map_RayHubbard.T_Map_RayHubbard");
				W.CardTexture = TEXT("/Game/UI/T_Card_RayHubbard.T_Card_RayHubbard");
				W.TitleTexture = TEXT("/Game/UI/T_Title_RayHubbard.T_Title_RayHubbard");
				for (int32 I = 0; I < 3; ++I) W.LoadingTextures.Add(FString::Printf(TEXT("/Game/UI/T_Load_RayHubbard_%d.T_Load_RayHubbard_%d"), I, I));
				ReadWorld(W);
				W.Facts.Add({ TEXT("22,745"), TEXT("Acres") });
				W.Facts.Add({ FString::FromInt(W.Spots.Num()), TEXT("Launch spots") });
				W.Facts.Add({ TEXT("6"), TEXT("ASA 101 drills") });
				W.Facts.Add({ TEXT("435.5 ft"), TEXT("Normal pool") });
				if (W.Spots.Num() > 0) { W.Spots[0].Tag = TEXT("Home"); W.Spots[0].StartType = TEXT("At the dock"); }
				Out.Add(W);
			}
			{
				FWorld W;
				W.Index = 1; W.File = TEXT("GalvestonBay"); W.Name = TEXT("Galveston Bay & Gulf"); W.Tagline = TEXT("Tide · Current · Ship traffic");
				W.Description = TEXT("Built from NOAA charts, with every buoy and light where it really is. Work the tide and current, cross the "
					"Houston Ship Channel with the ships, and take the 45-mile Gulf passage from Galveston to Freeport.");
				W.bTidal = true;
				W.MapTexture = TEXT("/Game/UI/T_Map_GalvestonBay.T_Map_GalvestonBay");
				W.CardTexture = TEXT("/Game/UI/T_Card_GalvestonBay.T_Card_GalvestonBay");
				W.TitleTexture = TEXT("/Game/UI/T_Title_GalvestonBay.T_Title_GalvestonBay");
				for (int32 I = 0; I < 3; ++I) W.LoadingTextures.Add(FString::Printf(TEXT("/Game/UI/T_Load_GalvestonBay_%d.T_Load_GalvestonBay_%d"), I, I));
				ReadWorld(W);
				W.Facts.Add({ FString::FromInt(W.Spots.Num()), TEXT("Launch spots") });
				W.Facts.Add({ TEXT("45 nm"), TEXT("Gulf passage") });
				W.Facts.Add({ TEXT("1°28′ E"), TEXT("Variation") });
				if (W.Spots.Num() > 1) W.Spots[1].Tag = TEXT("Busy");
				Out.Add(W);
			}
			for (FWorld& W : Out)
			{
				W.Id = FSailSave::WorldId(W.Index);
				for (FSpot& S : W.Spots)
				{
					if (S.StartType.IsEmpty()) S.StartType = TEXT("Under sail");
					if (S.Tag.IsEmpty()) S.Tag = W.Index == 0 ? TEXT("Lake") : TEXT("Bay");
					S.Detail = FString::Printf(TEXT("Heading %03.0f° · %s"), S.Heading, *S.StartType);
				}
			}
			return Out;
		}

		struct FWords { const TCHAR* TypeLine; const TCHAR* Description; int32 Handling; std::initializer_list<const TCHAR*> Flags; bool bDinghy; float Comfort, Reef; };

		const FWords& Words(int32 Type)
		{
			static const FWords W[] = {
				{ TEXT("Keelboat · 3 to 4 crew"), TEXT("The ASA 101 boat you sail at Rush Creek. Stable, responsive tiller, fractional rig. Shows every trim mistake without punishing it."), 2, { TEXT("Spinnaker") }, false, 14.f, 18.f },
				{ TEXT("Dinghy · single-handed"), TEXT("The beach classic: a lateen rig on a surfboard of a hull. Wet, simple and quick to capsize, and quick to right again."), 3, { TEXT("Capsize"), TEXT("Lateen rig") }, true, 10.f, 15.f },
				{ TEXT("Olympic dinghy · single"), TEXT("The Laser, now the ILCA 7. Hike hard upwind, steer through every wave. Rewards fitness and fine trim."), 4, { TEXT("Capsize"), TEXT("Hiking") }, true, 10.f, 16.f },
				{ TEXT("Trailerable keelboat"), TEXT("The family weekender: a swing keel, a cabin and an outboard. Forgiving, roomy, a little sluggish."), 2, { TEXT("Outboard"), TEXT("Reef") }, false, 12.f, 16.f },
				{ TEXT("Cruiser · ASA 103"), TEXT("A 30-foot cruiser with a wheel and an inboard diesel: the step up to coastal cruising and docking under power."), 3, { TEXT("Inboard"), TEXT("Wheel"), TEXT("Reef") }, false, 15.f, 20.f },
				{ TEXT("Beach catamaran"), TEXT("Twin hulls and a trapeze. Flies a hull in a breeze and goes very fast, until you bury a bow."), 4, { TEXT("Capsize"), TEXT("Trapeze") }, true, 12.f, 18.f },
				{ TEXT("Trailerable trimaran"), TEXT("Folding amas and a big rig: double-digit speeds on a reach, a light touch on the helm."), 4, { TEXT("Outboard"), TEXT("Spinnaker") }, false, 14.f, 20.f },
				{ TEXT("Cruising catamaran"), TEXT("Forty-two feet of steady platform with two engines. No heel, slow to tack, a lot of windage at the dock."), 3, { TEXT("Twin engines"), TEXT("Wheel") }, false, 16.f, 22.f },
			};
			return W[FMath::Clamp(Type, 0, int32(UE_ARRAY_COUNT(W)) - 1)];
		}

		TArray<FBoat> MakeBoats()
		{
			TArray<FBoat> Out;
			for (int32 T = 0; T < int32(EBoatType::Count); ++T)
			{
				const FBoatConfig C = FBoatConfig::Make(EBoatType(T));
				const FWords& W = Words(T);
				FBoat B;
				B.Type = T;
				B.Name = UTF8_TO_TCHAR(BoatTypeName(EBoatType(T)));
				B.TypeLine = W.TypeLine; B.Description = W.Description; B.Handling = W.Handling;
				for (const TCHAR* F : W.Flags) B.Flags.Add(F);
				B.bDinghy = W.bDinghy; B.bMultihull = C.bMultihull; B.ComfortKn = W.Comfort; B.ReefKn = W.Reef;
				B.Length = FeetInches(C.LengthOverall);
				B.Beam = FeetInches(C.Beam);
				B.Draft = FeetInches(C.Draft) + (C.HasBoard() ? TEXT(" board") : TEXT(""));
				const int32 Lb = FMath::RoundToInt((C.HullRigMass + C.BallastMass) / 0.45359237);
				B.Weight = FText::AsNumber(Lb).ToString() + TEXT(" lb");
				// Close-hauled at 12 kn: the reference polar's best upwind VMG point at the wind nearest 12 kn.
				const std::vector<FPolarPoint>& P = FleetReferencePolar(EBoatType(T));
				double BestTws = 1e9, BestVmg = 0.0, Speed = 0.0;
				for (const FPolarPoint& Pt : P) if (FMath::Abs(Pt.TrueWindKnots - 12.0) < FMath::Abs(BestTws - 12.0)) BestTws = Pt.TrueWindKnots;
				for (const FPolarPoint& Pt : P)
				{
					if (Pt.TrueWindKnots != BestTws || Pt.TrueWindAngleDeg > 70.0) continue;
					const double Vmg = Pt.BoatSpeedKnots * FMath::Cos(FMath::DegreesToRadians(Pt.TrueWindAngleDeg));
					if (Vmg > BestVmg) { BestVmg = Vmg; Speed = Pt.BoatSpeedKnots; }
				}
				B.CloseHauled = Speed > 0.0 ? FString::Printf(TEXT("%.1f kn"), Speed * 12.0 / BestTws) : FString(TEXT("–"));
				Out.Add(B);
			}
			return Out;
		}
	}

	const TArray<FWorld>& Worlds() { static TArray<FWorld> W = MakeWorlds(); return W; }
	const FWorld& World(int32 Index) { return Worlds()[FMath::Clamp(Index == 2 ? 1 : Index, 0, Worlds().Num() - 1)]; }
	const FMiniMap& MiniMap(int32 SettingsWorld)
	{
		static TArray<FMiniMap> Maps = []()
		{
			TArray<FMiniMap> Out;
			const TCHAR* Files[] = { TEXT("RayHubbard"), TEXT("GalvestonBay"), TEXT("GulfPassage") };
			for (int32 I = 0; I < 3; ++I)
			{
				FWorld W;
				W.File = Files[I];
				ReadWorld(W);
				FMiniMap M;
				M.Texture = FString::Printf(TEXT("/Game/UI/T_MiniMap_%s.T_MiniMap_%s"), Files[I], Files[I]);
				M.GridNorth = W.GridNorth; M.GridEast = W.GridEast; M.GridHeightM = W.GridHeightM; M.GridWidthM = W.GridWidthM;
				M.SpanM = I == 2 ? 8000.0 : 3000.0;   // offshore, the coast is further away
				Out.Add(M);
			}
			return Out;
		}();
		return Maps[FMath::Clamp(SettingsWorld, 0, 2)];
	}

	FString SpotId(const FString& Name)
	{
		FString Id;
		for (const TCHAR C : Name)
		{
			if (FChar::IsAlnum(C)) Id.AppendChar(FChar::ToLower(C));
			else if (!Id.IsEmpty() && !Id.EndsWith(TEXT("-"))) Id.AppendChar(TEXT('-'));
		}
		while (Id.EndsWith(TEXT("-"))) Id.LeftChopInline(1);
		return Id;
	}

	const TArray<FString>& SpotIds(int32 SettingsWorld)
	{
		static TArray<TArray<FString>> Ids = []()
		{
			TArray<TArray<FString>> Out;
			const TCHAR* Files[] = { TEXT("RayHubbard"), TEXT("GalvestonBay"), TEXT("GulfPassage") };
			for (const TCHAR* F : Files)
			{
				FWorld W;
				W.File = F;
				ReadWorld(W);
				TArray<FString>& List = Out.AddDefaulted_GetRef();
				for (const FSpot& S : W.Spots) List.Add(S.Id);
			}
			return Out;
		}();
		return Ids[FMath::Clamp(SettingsWorld, 0, 2)];
	}

	const TArray<FBoat>& Boats() { static TArray<FBoat> B = MakeBoats(); return B; }
	const FBoat& Boat(int32 Type) { return Boats()[FMath::Clamp(Type, 0, Boats().Num() - 1)]; }

	float SunsetHour(int32 Month, int32 Day, int32 WorldIndex)
	{
		const double Lat = WorldIndex == 0 ? 32.82 : 29.5, Lon = WorldIndex == 0 ? -96.5 : -94.9;
		const int32 Doy = FDateTime(2026, FMath::Clamp(Month, 1, 12), FMath::Clamp(Day, 1, 28)).GetDayOfYear();
		const double Utc = (Month >= 3 && Month <= 10) ? -5.0 : -6.0;   // CDT / CST
		for (double H = 15.0; H < 22.0; H += 1.0 / 60.0)
		{
			double El, Az;
			ASailingEnvironment::SunPosition(H, Doy, Lat, Lon, Utc, El, Az);
			if (El < -0.833) return float(H);
		}
		return 20.f;
	}

	FString Expect(float WindKn, float GustKn, int32 Sky, float Hour, int32 Month, int32 Day, int32 BoatType, int32 WorldIndex)
	{
		const FBoat& B = Boat(BoatType);
		FString S = FString::Printf(TEXT("%.0f kn, gusting %.0f. "), WindKn, GustKn);
		if (WindKn < 4.f) S += TEXT("Very light: expect to drift between puffs. ");
		else if (GustKn <= B.ComfortKn + 2.f) S += FString::Printf(TEXT("Good learning breeze for the %s. "), *B.Name);
		else if (GustKn <= B.ReefKn) S += FString::Printf(TEXT("Fresh. %s "), B.bDinghy ? *FString::Printf(TEXT("Hike hard and ease in the gusts on the %s."), *B.Name)
			: *FString::Printf(TEXT("Consider a reef on the %s."), *B.Name));
		else S += FString::Printf(TEXT("Strong. Realistic mode will %s the %s without a reef. "), B.bDinghy ? TEXT("capsize") : TEXT("overpower"), *B.Name);
		if (Sky == 3) S += TEXT("A storm cell builds through the afternoon, with a gust front of 35 kn or more. ");
		if (Sky == 4) S += WorldIndex == 1 ? TEXT("Visibility under half a mile; sound signals and radar matter. ") : TEXT("Low cloud and poor visibility. ");
		S += FString::Printf(TEXT("Sunset %s."), *ClockText(SunsetHour(Month, Day, WorldIndex)));
		return S;
	}
}

const TArray<SailCatalog::FRealDay>& SailCatalog::RealDays()
{
	// Plain data read once (no UObjects): every baked day, oldest first, with a summary from its own timeline.
	static TArray<FRealDay> Days = []
	{
		TArray<FRealDay> Out;
		const FString Dir = FPaths::ProjectContentDir() / TEXT("TerrainData") / TEXT("Weather");
		TArray<FString> Files;
		IFileManager::Get().FindFiles(Files, *(Dir / TEXT("*.wxday")), true, false);
		Files.Sort();
		for (const FString& F : Files)
		{
			TArray<uint8> Bytes;
			Sailing::FWeatherDay Day;
			if (!FFileHelper::LoadFileToArray(Bytes, *(Dir / F), FILEREAD_Silent) || !Day.LoadFromMemory(Bytes.GetData(), size_t(Bytes.Num()))) continue;
			FRealDay R;
			R.Date = UTF8_TO_TCHAR(Day.Date.c_str());
			R.Title = UTF8_TO_TCHAR(Day.Title.c_str());
			R.StartHour = float(Day.StartHour);
			R.Month = Day.Month();
			R.Day = Day.DayOfMonth();
			R.bStorm = Day.bStorm;
			const Sailing::FWeatherHour H = Day.At(Day.StartHour);
			R.Summary = FString::Printf(TEXT("%s · %.0f kn %s · %s"), *R.Date, H.WindKnots,
				*USailSessionSubsystem::CompassPoint(float(H.FromDegrees)), *ClockText(R.StartHour));
			Out.Add(R);
		}
		return Out;
	}();
	return Days;
}

namespace SailCatalog
{
	const TCHAR* const UnrealNotice = TEXT("Made with Unreal Engine. Unreal® is a trademark or registered trademark of Epic Games, Inc.");

	FString CreditsPath()
	{
		return FPaths::ProjectDir() / TEXT("CREDITS.md");
	}

	namespace
	{
		/** Inline Markdown to plain text: code spans and bold lose their marks, a link keeps its words and, unless it is a
		 *  Commons file page (the title names the file), its address in brackets. */
		FString PlainCredit(const FString& In)
		{
			FString S = In.Replace(TEXT("`"), TEXT("")).Replace(TEXT("**"), TEXT(""));
			FString Out;
			int32 I = 0;
			while (I < S.Len())
			{
				if (S[I] == TEXT('['))
				{
					// The label may hold brackets itself ("Laser 2000 [...]"): match the ] that is followed by (.
					int32 Depth = 0, Close = INDEX_NONE;
					for (int32 J = I; J < S.Len(); ++J)
					{
						if (S[J] == TEXT('[')) ++Depth;
						else if (S[J] == TEXT(']') && --Depth == 0) { Close = J; break; }
					}
					if (Close != INDEX_NONE && Close + 1 < S.Len() && S[Close + 1] == TEXT('('))
					{
						// The address runs to the ) that closes it (addresses can hold balanced brackets).
						int32 Paren = 0, UrlEnd = INDEX_NONE;
						for (int32 J = Close + 1; J < S.Len(); ++J)
						{
							if (S[J] == TEXT('(')) ++Paren;
							else if (S[J] == TEXT(')') && --Paren == 0) { UrlEnd = J; break; }
						}
						if (UrlEnd != INDEX_NONE)
						{
							const FString Label = S.Mid(I + 1, Close - I - 1), Url = S.Mid(Close + 2, UrlEnd - Close - 2);
							Out += Label;
							if (!Url.Contains(TEXT("commons.wikimedia.org/wiki/File"))) Out += TEXT(" (") + Url + TEXT(")");
							I = UrlEnd + 1;
							continue;
						}
					}
				}
				Out.AppendChar(S[I++]);
			}
			return Out;
		}
	}

	TArray<FCreditLine> ParseCredits(const FString& Markdown)
	{
		TArray<FCreditLine> Out;
		Out.Add({ ECreditKind::Notice, UnrealNotice });
		TArray<FString> Lines;
		Markdown.ParseIntoArrayLines(Lines, false);
		bool bOpen = false;   // the last line is a paragraph or bullet that the next indented or plain line continues
		for (const FString& Raw : Lines)
		{
			const FString Line = Raw.TrimEnd();
			const FString Trimmed = Line.TrimStart();
			if (Trimmed.IsEmpty()) { bOpen = false; continue; }
			if (Trimmed.StartsWith(TEXT("#")))
			{
				int32 Level = 0;
				while (Level < Trimmed.Len() && Trimmed[Level] == TEXT('#')) ++Level;
				const ECreditKind Kind = Level <= 1 ? ECreditKind::Heading1 : (Level == 2 ? ECreditKind::Heading2 : ECreditKind::Heading3);
				Out.Add({ Kind, PlainCredit(Trimmed.Mid(Level).TrimStartAndEnd()) });
				bOpen = false;
			}
			else if (Trimmed.StartsWith(TEXT("- ")) || Trimmed.StartsWith(TEXT("* ")))
			{
				Out.Add({ ECreditKind::Bullet, Trimmed.Mid(2).TrimStart() });
				bOpen = true;
			}
			else if (bOpen)
			{
				Out.Last().Text += TEXT(" ") + Trimmed;
			}
			else
			{
				Out.Add({ ECreditKind::Paragraph, Trimmed });
				bOpen = true;
			}
		}
		// Inline marks after joining, so a link broken over two lines still reads as one.
		for (FCreditLine& L : Out) if (L.Kind == ECreditKind::Paragraph || L.Kind == ECreditKind::Bullet) L.Text = PlainCredit(L.Text);
		return Out;
	}

	TArray<FCreditLine> Credits()
	{
		FString Text;
		if (FFileHelper::LoadFileToString(Text, *CreditsPath())) return ParseCredits(Text);
		TArray<FCreditLine> Out;
		Out.Add({ ECreditKind::Notice, UnrealNotice });
		Out.Add({ ECreditKind::Paragraph, TEXT("CREDITS.md is missing from this build.") });
		return Out;
	}
}
